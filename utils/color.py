"""WCAG color-contrast math.

Pure functions with no python-pptx dependency, so they can be unit-tested in
isolation. Implements the relative-luminance and contrast-ratio formulas from
WCAG 2.1 SC 1.4.3 Contrast (Minimum), plus a helper that proposes the nearest
compliant foreground color for a failing text/background pair.
"""

from __future__ import annotations

# WCAG 2.1 SC 1.4.3 (Level AA) minimum contrast ratios.
MIN_RATIO_NORMAL = 4.5
MIN_RATIO_LARGE = 3.0

RGB = tuple[int, int, int]


def _channel_luminance(value: int) -> float:
    """Return the linearized luminance contribution of one 0-255 sRGB channel."""
    srgb = value / 255.0
    if srgb <= 0.03928:
        return srgb / 12.92
    return ((srgb + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: RGB) -> float:
    """Return the WCAG relative luminance of an sRGB color, in ``[0.0, 1.0]``."""
    red, green, blue = rgb
    return (
        0.2126 * _channel_luminance(red)
        + 0.7152 * _channel_luminance(green)
        + 0.0722 * _channel_luminance(blue)
    )


def contrast_ratio(fg: RGB, bg: RGB) -> float:
    """Return the WCAG contrast ratio between two colors, in ``[1.0, 21.0]``."""
    lum_a = relative_luminance(fg)
    lum_b = relative_luminance(bg)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def required_ratio(*, is_large: bool) -> float:
    """Return the minimum passing ratio for normal or large text."""
    return MIN_RATIO_LARGE if is_large else MIN_RATIO_NORMAL


def to_hex(rgb: RGB) -> str:
    """Return an uppercase ``#RRGGBB`` string for an RGB triple."""
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _blend(color: RGB, toward: RGB, ratio: float) -> RGB:
    """Return ``color`` moved ``ratio`` of the way toward ``toward``."""
    return tuple(round(c + (t - c) * ratio) for c, t in zip(color, toward))  # type: ignore[return-value]


def suggest_accessible_color(fg: RGB, bg: RGB, *, target: float) -> RGB:
    """Return a color close to ``fg`` that meets ``target`` contrast on ``bg``.

    The foreground is nudged toward black and toward white in small steps; the
    smallest change that reaches ``target`` wins, so brand hue is preserved as
    far as possible. Falls back to pure black or white when no blend reaches the
    target (only possible for a near-mid-gray background).

    Args:
        fg: Current foreground RGB triple.
        bg: Background RGB triple.
        target: Minimum contrast ratio the result must satisfy.

    Returns:
        An RGB triple with ``contrast_ratio(result, bg) >= target`` whenever one
        exists, otherwise whichever pure extreme maximizes contrast.
    """
    if contrast_ratio(fg, bg) >= target:
        return fg
    best: RGB | None = None
    best_distance: float | None = None
    for toward in ((0, 0, 0), (255, 255, 255)):
        for step in range(1, 21):
            candidate = _blend(fg, toward, step / 20)
            if contrast_ratio(candidate, bg) >= target:
                distance = sum((a - b) ** 2 for a, b in zip(candidate, fg))
                if best_distance is None or distance < best_distance:
                    best, best_distance = candidate, distance
                break
    if best is not None:
        return best
    black: RGB = (0, 0, 0)
    white: RGB = (255, 255, 255)
    return black if contrast_ratio(black, bg) >= contrast_ratio(white, bg) else white
