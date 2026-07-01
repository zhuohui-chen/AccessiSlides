"""Low-level python-pptx XML helpers.

The public python-pptx API does not expose every accessibility-related field.
PowerPoint stores image alt text in the `p:cNvPr` XML element as the `descr`
attribute, so a few targeted XML helpers are needed.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from lxml import etree
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml import parse_xml


def _iter_elements_with_local_name(root: Any, local_name: str) -> Iterable[Any]:
    """Yield descendants whose tag has the requested XML local name."""
    for element in root.iter():
        if etree.QName(element).localname == local_name:
            yield element


def c_nv_pr(shape: Any) -> Any | None:
    """Return the non-visual properties element for a shape, if present."""
    return next(_iter_elements_with_local_name(shape._element, "cNvPr"), None)


def get_shape_name(shape: Any) -> str:
    """Return the PowerPoint shape name."""
    element = c_nv_pr(shape)
    return "" if element is None else str(element.get("name", ""))


def get_alt_text(shape: Any) -> str:
    """Return a shape's alt text description from the underlying XML."""
    element = c_nv_pr(shape)
    if element is None:
        return ""
    return str(element.get("descr") or "").strip()


def set_alt_text(shape: Any, alt_text: str) -> None:
    """Set a shape's alt text description in the underlying XML."""
    element = c_nv_pr(shape)
    if element is None:
        raise ValueError("Shape does not contain a p:cNvPr element")
    element.set("descr", alt_text.strip())


def shape_xml(shape: Any) -> str:
    """Serialize a shape XML element."""
    return etree.tostring(shape._element, encoding="unicode")


def replace_shape_xml(shape: Any, xml: str) -> None:
    """Replace an existing shape XML element with a serialized snapshot."""
    parent = shape._element.getparent()
    if parent is None:
        raise ValueError("Cannot replace shape XML because it has no parent")
    parent.replace(shape._element, parse_xml(xml))


def get_image_blob(shape: Any) -> tuple[bytes, str] | None:
    """Return a picture shape's raw bytes and MIME type, or None.

    Args:
        shape: A python-pptx shape expected to be a picture.

    Returns:
        A ``(blob, content_type)`` tuple, or ``None`` when the shape has no
        accessible image (e.g. it is not a picture, or its blob cannot be read).
    """
    image = getattr(shape, "image", None)
    if image is None:
        return None
    try:
        blob = image.blob
        content_type = image.content_type
    except (AttributeError, ValueError, KeyError):
        return None
    if not blob or not content_type:
        return None
    return blob, str(content_type)


def get_slide(prs: Any, slide_number: int) -> Any:
    """Return a 1-indexed slide from a presentation."""
    if slide_number < 1 or slide_number > len(prs.slides):
        raise IndexError(f"Slide number out of range: {slide_number}")
    return prs.slides[slide_number - 1]


def iter_shapes(shapes: Any) -> Iterable[Any]:
    """Yield every shape in a container, descending into group shapes.

    PowerPoint groups (``MSO_SHAPE_TYPE.GROUP``) nest their members, and
    iterating a slide's shape tree does not recurse into them. This walker
    yields each group shape and then its descendants, so a slide that groups
    several charts or pictures exposes every figure individually.
    """
    for shape in shapes:
        yield shape
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from iter_shapes(shape.shapes)


def get_shape_by_id(slide: Any, shape_id: str | int) -> Any:
    """Return a shape by PowerPoint shape ID, searching inside groups."""
    target = str(shape_id)
    for shape in iter_shapes(slide.shapes):
        if str(shape.shape_id) == target:
            return shape
    raise KeyError(f"Shape id {target} not found on slide")


def delete_shape_by_id(slide: Any, shape_id: str | int) -> None:
    """Remove a shape by PowerPoint shape ID."""
    shape = get_shape_by_id(slide, shape_id)
    parent = shape._element.getparent()
    if parent is None:
        raise ValueError("Cannot delete shape XML because it has no parent")
    parent.remove(shape._element)


def text_from_shape(shape: Any) -> str:
    """Return text for a shape when it has a text frame."""
    if not getattr(shape, "has_text_frame", False):
        return ""
    parts: list[str] = []
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            if run.text:
                parts.append(run.text)
        if paragraph.text and not paragraph.runs:
            parts.append(paragraph.text)
    return " ".join(part.strip() for part in parts if part.strip())


def slide_context_text(slide: Any, *, exclude_shape_id: str | None = None, limit: int = 180) -> str:
    """Return concise text context from a slide."""
    snippets: list[str] = []
    for shape in iter_shapes(slide.shapes):
        if exclude_shape_id is not None and str(shape.shape_id) == str(exclude_shape_id):
            continue
        text = text_from_shape(shape).strip()
        if text:
            snippets.append(text)
    context = " ".join(snippets)
    return context[:limit].strip()


def title_shape(slide: Any) -> Any | None:
    """Return the shape holding the slide's title text, if one carries text.

    Prefers the layout title placeholder, then falls back to any shape whose
    name contains "title". Returns ``None`` when no title-bearing shape exists.
    """
    placeholder = getattr(slide.shapes, "title", None)
    if placeholder is not None and text_from_shape(placeholder).strip():
        return placeholder
    for shape in slide.shapes:
        if "title" in get_shape_name(shape).lower() and text_from_shape(shape).strip():
            return shape
    return None


def title_text(slide: Any) -> str:
    """Return the best available slide title text."""
    shape = title_shape(slide)
    return "" if shape is None else text_from_shape(shape).strip()


def set_title_text(shape: Any, text: str) -> None:
    """Replace a title shape's text with ``text``, keeping its first run's font."""
    if not getattr(shape, "has_text_frame", False):
        raise ValueError("Title shape has no text frame")
    text_frame = shape.text_frame
    paragraph = text_frame.paragraphs[0]
    font = paragraph.runs[0].font if paragraph.runs else None
    size = font.size if font is not None else None
    text_frame.text = text.strip()
    new_paragraph = text_frame.paragraphs[0]
    if size is not None and new_paragraph.runs:
        new_paragraph.runs[0].font.size = size
