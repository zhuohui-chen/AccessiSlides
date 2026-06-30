"""Prompt builders for LLM-backed accessibility suggestions and detection.

Centralizing the prompts keeps the provider implementations free of task
wording and makes the wording reviewable in one place. All prompts instruct the
model to return plain text only, since the results are written verbatim into
ledger ``suggested_fix`` fields and slide alt text.
"""

from __future__ import annotations

ALT_TEXT_SYSTEM = (
    "You write concise, accurate alternative text for images in presentations, "
    "following WCAG 1.1.1 Non-text Content. Describe the image's content and its "
    "purpose in context. Do not start with 'image of' or 'picture of'. Return a "
    "single sentence of plain text with no quotation marks or preamble."
)

LINK_TEXT_SYSTEM = (
    "You rewrite vague hyperlink text into descriptive link text per WCAG 2.4.4 "
    "Link Purpose. The new text must make sense out of context and describe the "
    "destination. Return only the replacement link text — a few words, plain "
    "text, no quotation marks or preamble."
)

SLIDE_TITLE_SYSTEM = (
    "You write short, descriptive slide titles per WCAG 2.4.2 Page Titled. The "
    "title must reflect the slide's content so screen-reader users can navigate. "
    "Return only the title — a few words, plain text, no quotation marks or preamble."
)

HIGH_RISK_SYSTEM = (
    "You draft a long text-alternative for a complex presentation object (chart, "
    "table, or media) for a human accessibility reviewer to refine. Summarize what "
    "a sighted viewer would understand, noting that data-specific details must be "
    "verified by a human. Return plain text only."
)

DETECTION_SYSTEM = (
    "You are an accessibility reviewer inspecting one PowerPoint slide's text "
    "content for issues that deterministic rules miss: vague or non-descriptive "
    "titles, ambiguous wording, or reliance on color/visual cues described in the "
    "text. Be conservative — only report a clear issue. Return plain text only."
)


def alt_text_prompt(context: str) -> str:
    """Build the user prompt for image alt-text generation."""
    context = context.strip()
    if context:
        return f"Surrounding slide text for context: {context}\n\nWrite alt text for the image."
    return "Write alt text for this image."


def link_text_prompt(*, address: str, context: str) -> str:
    """Build the user prompt for descriptive link text."""
    parts = [f"The link points to: {address}"]
    context = context.strip()
    if context:
        parts.append(f"Surrounding slide text: {context}")
    parts.append("Write descriptive replacement link text.")
    return "\n".join(parts)


def slide_title_prompt(context: str) -> str:
    """Build the user prompt for a descriptive slide title."""
    context = context.strip()
    if context:
        return f"Slide text content: {context}\n\nWrite a short descriptive title for this slide."
    return "Write a short descriptive title for this slide."


def high_risk_prompt(*, element_type: str, context: str) -> str:
    """Build the user prompt for a high-risk long-description draft."""
    parts = [f"The object is a {element_type}."]
    context = context.strip()
    if context:
        parts.append(f"Surrounding slide text: {context}")
    parts.append("Draft a text alternative for a human reviewer to refine.")
    return "\n".join(parts)


def detection_prompt(*, slide_number: int, title: str, context: str) -> str:
    """Build the user prompt for the semantic detection pass on one slide."""
    return (
        f"Slide {slide_number}.\n"
        f"Detected title: {title or '(none)'}\n"
        f"Slide text: {context or '(none)'}\n\n"
        "If there is a clear accessibility issue with the title or wording, reply with "
        "one line: '<short issue summary>'. If there is no clear issue, reply with exactly 'NONE'."
    )
