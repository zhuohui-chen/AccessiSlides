"""Text-over-background contrast checks (WCAG 1.4.3) — no slide renderer.

Tier 2: catches low-contrast text placed over an embedded picture or a gradient
fill — cases the XML-only rule (:mod:`checker.rules.contrast`) cannot measure
because the file has no single background color there. It samples the actual
image pixels with Pillow (already a python-pptx dependency) or reads gradient
stops from the XML, so it needs no LibreOffice, no headless renderer, and no
external binary.

Scope and limitations (findings are advisory, for human review):
    * Backgrounds handled: an overlapping top-level *picture* shape, or a
      *gradient* fill (on the text shape itself or an overlapping shape).
    * Geometry is bounding-box based; it does not model rotation, z-order beyond
      draw order, or picture transparency, and skips grouped-shape layouts.
    * For pictures it reports the *typical* (median) contrast across the region
      the text covers; for gradients it reports the worst-case stop.
"""

from __future__ import annotations

import io
import statistics
from typing import Any

from PIL import Image, UnidentifiedImageError

from config import Settings
from models import Finding, RiskLevel
from utils.color import contrast_ratio, required_ratio, suggest_accessible_color, to_hex
from utils.pptx_xml import (
    find_visual_background,
    get_image_blob,
    gradient_stops_rgb,
    iter_shapes,
    rect_intersection,
    resolve_run_rgb,
    run_is_large_text,
    shape_rect,
    slide_theme_palette,
)

# The overlap region is downsampled to this many pixels per side before sampling.
_SAMPLE_SIZE = 24


def _crop_fractions(picture: Any) -> tuple[float, float, float, float]:
    """Return a picture's (left, right, top, bottom) crop fractions, defaulting to 0."""

    def value(name: str) -> float:
        try:
            return float(getattr(picture, name) or 0.0)
        except (AttributeError, TypeError, ValueError):
            return 0.0

    return (value("crop_left"), value("crop_right"), value("crop_top"), value("crop_bottom"))


def _image_box(
    inter: tuple[int, int, int, int],
    pic_rect: tuple[int, int, int, int],
    crop: tuple[float, float, float, float],
    img_w: int,
    img_h: int,
) -> tuple[int, int, int, int] | None:
    """Map the overlap rect (EMU) into original-image pixel coordinates, honoring crop."""
    ix, iy, iw, ih = inter
    px, py, pw, ph = pic_rect
    crop_l, crop_r, crop_t, crop_b = crop
    visible_w = max(1e-6, 1.0 - crop_l - crop_r)
    visible_h = max(1e-6, 1.0 - crop_t - crop_b)
    fx0, fx1 = (ix - px) / pw, (ix + iw - px) / pw
    fy0, fy1 = (iy - py) / ph, (iy + ih - py) / ph
    ox0 = (crop_l + fx0 * visible_w) * img_w
    ox1 = (crop_l + fx1 * visible_w) * img_w
    oy0 = (crop_t + fy0 * visible_h) * img_h
    oy1 = (crop_t + fy1 * visible_h) * img_h
    x0 = max(0, min(img_w - 1, int(round(min(ox0, ox1)))))
    x1 = max(x0 + 1, min(img_w, int(round(max(ox0, ox1)))))
    y0 = max(0, min(img_h - 1, int(round(min(oy0, oy1)))))
    y1 = max(y0 + 1, min(img_h, int(round(max(oy0, oy1)))))
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1, y1)


def _sample_picture_pixels(
    picture: Any, text_rect: tuple[int, int, int, int]
) -> list[tuple[int, int, int]] | None:
    """Return downsampled RGB pixels of the image region a text shape covers, or None."""
    blob = get_image_blob(picture)
    pic_rect = shape_rect(picture)
    if blob is None or pic_rect is None:
        return None
    inter = rect_intersection(text_rect, pic_rect)
    if inter is None:
        return None
    image_bytes, _ = blob
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            rgb_image = image.convert("RGB")
            box = _image_box(inter, pic_rect, _crop_fractions(picture), *rgb_image.size)
            if box is None:
                return None
            region = rgb_image.crop(box).resize((_SAMPLE_SIZE, _SAMPLE_SIZE))
            raw = region.tobytes()  # RGB, 3 bytes per pixel — version-stable
            return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    except (OSError, UnidentifiedImageError, ValueError):
        return None


def _picture_finding(
    *,
    text: str,
    foreground: tuple[int, int, int],
    pixels: list[tuple[int, int, int]],
    required: float,
    slide_index: int,
    shape: Any,
    paragraph_index: int,
    run_index: int,
) -> Finding | None:
    """Build a finding when text is unreadable over the sampled image region."""
    ratios = [contrast_ratio(foreground, pixel) for pixel in pixels]
    median_ratio = statistics.median(ratios)
    if median_ratio >= required:
        return None
    worst = min(ratios)
    channels = zip(*pixels)
    average_bg = tuple(round(sum(channel) / len(pixels)) for channel in channels)
    suggested = suggest_accessible_color(foreground, average_bg, target=required)  # type: ignore[arg-type]
    fraction_failing = sum(1 for ratio in ratios if ratio < required) / len(ratios)
    return Finding(
        rule_id="low_contrast_over_image",
        slide_number=slide_index,
        element_id=str(shape.shape_id),
        element_type="text_over_image",
        wcag_criterion="1.4.3 Contrast (Minimum)",
        section_508_ref="E205.4",
        risk_level=RiskLevel.MEDIUM,
        issue_description=(
            f"Text {text!r} sits over an image where the typical contrast is "
            f"{median_ratio:.2f}:1 (as low as {worst:.2f}:1), below the WCAG 2.1 AA "
            f"minimum of {required:.1f}:1. Text over busy or low-contrast image areas "
            "can be unreadable."
        ),
        suggested_fix=(
            f"Increase contrast — e.g. change the text color from {to_hex(foreground)} to "
            f"about {to_hex(suggested)}, or add a solid/semi-opaque background (scrim) "
            "behind the text."
        ),
        metadata={
            "foreground": to_hex(foreground),
            "background_type": "image",
            "median_ratio": round(median_ratio, 2),
            "worst_ratio": round(worst, 2),
            "fraction_below_min": round(fraction_failing, 2),
            "required_ratio": required,
            "average_background": to_hex(average_bg),  # type: ignore[arg-type]
            "suggested_color": to_hex(suggested),
            "paragraph_index": paragraph_index,
            "run_index": run_index,
        },
    )


def _gradient_finding(
    *,
    text: str,
    foreground: tuple[int, int, int],
    stops: list[tuple[int, int, int]],
    required: float,
    slide_index: int,
    shape: Any,
    paragraph_index: int,
    run_index: int,
) -> Finding | None:
    """Build a finding when text fails contrast against any part of a gradient."""
    ratios = [contrast_ratio(foreground, stop) for stop in stops]
    worst = min(ratios)
    if worst >= required:
        return None
    worst_stop = stops[ratios.index(worst)]
    suggested = suggest_accessible_color(foreground, worst_stop, target=required)
    return Finding(
        rule_id="low_contrast_over_gradient",
        slide_number=slide_index,
        element_id=str(shape.shape_id),
        element_type="text_over_gradient",
        wcag_criterion="1.4.3 Contrast (Minimum)",
        section_508_ref="E205.4",
        risk_level=RiskLevel.MEDIUM,
        issue_description=(
            f"Text {text!r} sits on a gradient where contrast drops to {worst:.2f}:1 "
            f"against {to_hex(worst_stop)}, below the WCAG 2.1 AA minimum of "
            f"{required:.1f}:1. Part of the gradient makes the text hard to read."
        ),
        suggested_fix=(
            f"Keep the text readable across the whole gradient — e.g. change the text color "
            f"from {to_hex(foreground)} to about {to_hex(suggested)}, or narrow the gradient's "
            "color range."
        ),
        metadata={
            "foreground": to_hex(foreground),
            "background_type": "gradient",
            "worst_ratio": round(worst, 2),
            "worst_stop": to_hex(worst_stop),
            "required_ratio": required,
            "suggested_color": to_hex(suggested),
            "paragraph_index": paragraph_index,
            "run_index": run_index,
        },
    )


def check(prs: Any, settings: Settings) -> list[Finding]:
    """Detect low-contrast text placed over a picture or gradient background."""
    del settings
    findings: list[Finding] = []
    for slide_index, slide in enumerate(prs.slides, start=1):
        palette = slide_theme_palette(slide)
        default_fg = palette.get("tx1")
        for shape in iter_shapes(slide.shapes):
            if not getattr(shape, "has_text_frame", False):
                continue
            source = find_visual_background(shape, slide)
            if source is None:
                continue
            kind, background_shape = source

            pixels: list[tuple[int, int, int]] | None = None
            stops: list[tuple[int, int, int]] = []
            if kind == "picture":
                text_rect = shape_rect(shape)
                if text_rect is None:
                    continue
                pixels = _sample_picture_pixels(background_shape, text_rect)
                if not pixels:
                    continue
            else:  # gradient
                stops = gradient_stops_rgb(background_shape, palette)
                if not stops:
                    continue

            for paragraph_index, paragraph in enumerate(shape.text_frame.paragraphs):
                for run_index, run in enumerate(paragraph.runs):
                    text = (run.text or "").strip()
                    if not text:
                        continue
                    foreground = resolve_run_rgb(run, palette) or default_fg
                    if foreground is None:
                        continue
                    required = required_ratio(is_large=run_is_large_text(run))
                    if kind == "picture":
                        finding = _picture_finding(
                            text=text,
                            foreground=foreground,
                            pixels=pixels or [],
                            required=required,
                            slide_index=slide_index,
                            shape=shape,
                            paragraph_index=paragraph_index,
                            run_index=run_index,
                        )
                    else:
                        finding = _gradient_finding(
                            text=text,
                            foreground=foreground,
                            stops=stops,
                            required=required,
                            slide_index=slide_index,
                            shape=shape,
                            paragraph_index=paragraph_index,
                            run_index=run_index,
                        )
                    if finding is not None:
                        findings.append(finding)
    return findings
