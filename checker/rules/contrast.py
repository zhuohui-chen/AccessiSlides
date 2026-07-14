"""Text color-contrast accessibility checks (WCAG 1.4.3).

Deterministic pass: for every visible text run, resolve its foreground font
color and effective background to concrete RGB — literal, theme/scheme, or
inherited — using the slide master's theme palette, then compute the WCAG
contrast ratio and flag runs below the Level AA minimum. Because WCAG 1.4.3
concerns the *rendered* color, inherited text is resolved to the theme's default
text/background colors rather than guessed at, so ordinary decks (dark text on a
light theme) produce no findings and only genuine low-contrast pairings surface.

Text placed over a picture or gradient has no single background color here; those
runs are deferred to :mod:`checker.rules.contrast_image`, which samples the
actual pixels/stops. This rule and that one partition the work via
:func:`utils.pptx_xml.find_visual_background`, so they never double-report.
"""

from __future__ import annotations

from typing import Any

from config import Settings
from models import Finding, RiskLevel
from utils.color import contrast_ratio, required_ratio, suggest_accessible_color, to_hex
from utils.pptx_xml import (
    find_visual_background,
    iter_shapes,
    resolve_run_rgb,
    run_is_large_text,
    shape_background_rgb,
    slide_theme_palette,
)


def check(prs: Any, settings: Settings) -> list[Finding]:
    """Detect text runs with insufficient contrast against their background."""
    del settings
    findings: list[Finding] = []
    for slide_index, slide in enumerate(prs.slides, start=1):
        palette = slide_theme_palette(slide)
        # Unstyled text renders in the theme's default text/background colors.
        default_fg = palette.get("tx1")
        default_bg = palette.get("bg1")
        for shape in iter_shapes(slide.shapes):
            if not getattr(shape, "has_text_frame", False):
                continue
            if find_visual_background(shape, slide) is not None:
                continue  # text over a picture/gradient — handled by contrast_image
            background = shape_background_rgb(shape, slide, palette) or default_bg
            if background is None:
                continue  # theme unreadable — cannot measure, so do not guess
            for paragraph_index, paragraph in enumerate(shape.text_frame.paragraphs):
                for run_index, run in enumerate(paragraph.runs):
                    text = (run.text or "").strip()
                    if not text:
                        continue
                    foreground = resolve_run_rgb(run, palette) or default_fg
                    if foreground is None:
                        continue
                    ratio = contrast_ratio(foreground, background)
                    is_large = run_is_large_text(run)
                    required = required_ratio(is_large=is_large)
                    if ratio >= required:
                        continue
                    suggested = suggest_accessible_color(foreground, background, target=required)
                    size_label = "large" if is_large else "normal"
                    findings.append(
                        Finding(
                            rule_id="low_contrast_text",
                            slide_number=slide_index,
                            element_id=str(shape.shape_id),
                            element_type="text_run",
                            wcag_criterion="1.4.3 Contrast (Minimum)",
                            section_508_ref="E205.4",
                            risk_level=RiskLevel.MEDIUM,
                            issue_description=(
                                f"Text {text!r} has a contrast ratio of {ratio:.2f}:1 "
                                f"against its background {to_hex(background)}, below the "
                                f"WCAG 2.1 AA minimum of {required:.1f}:1 for {size_label} "
                                "text. Low contrast text is hard to read for users with "
                                "low vision."
                            ),
                            suggested_fix=(
                                f"Change the text color from {to_hex(foreground)} to about "
                                f"{to_hex(suggested)} to reach {required:.1f}:1 contrast on "
                                f"{to_hex(background)}."
                            ),
                            metadata={
                                "foreground": to_hex(foreground),
                                "background": to_hex(background),
                                "ratio": round(ratio, 2),
                                "required_ratio": required,
                                "is_large_text": is_large,
                                "suggested_color": to_hex(suggested),
                                "paragraph_index": paragraph_index,
                                "run_index": run_index,
                            },
                        )
                    )
    return findings
