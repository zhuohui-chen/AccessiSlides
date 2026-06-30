"""Low-level python-pptx XML helpers.

The public python-pptx API does not expose every accessibility-related field.
PowerPoint stores image alt text in the `p:cNvPr` XML element as the `descr`
attribute, so a few targeted XML helpers are needed.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from lxml import etree
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


def get_shape_by_id(slide: Any, shape_id: str | int) -> Any:
    """Return a shape by PowerPoint shape ID."""
    target = str(shape_id)
    for shape in slide.shapes:
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
    for shape in slide.shapes:
        if exclude_shape_id is not None and str(shape.shape_id) == str(exclude_shape_id):
            continue
        text = text_from_shape(shape).strip()
        if text:
            snippets.append(text)
    context = " ".join(snippets)
    return context[:limit].strip()


def title_text(slide: Any) -> str:
    """Return the best available slide title text."""
    title_shape = getattr(slide.shapes, "title", None)
    if title_shape is not None:
        title = text_from_shape(title_shape).strip()
        if title:
            return title
    for shape in slide.shapes:
        name = get_shape_name(shape).lower()
        if "title" in name:
            title = text_from_shape(shape).strip()
            if title:
                return title
    return ""
