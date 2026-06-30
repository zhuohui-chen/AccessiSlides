"""Generic hyperlink text accessibility checks."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from config import Settings
from models import Finding, RiskLevel

GENERIC_LINK_TEXT = {
    "click here",
    "here",
    "link",
    "learn more",
    "read more",
    "more",
    "this link",
    "website",
}


def normalize_link_text(text: str) -> str:
    """Normalize link text for generic-text detection."""
    text = text.strip().lower()
    text = re.sub(r"[\s\u00a0]+", " ", text)
    text = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", text)
    return text


def descriptive_link_text(address: str) -> str:
    """Build deterministic descriptive link text from a URL."""
    parsed = urlparse(address)
    if parsed.netloc:
        host = parsed.netloc.removeprefix("www.")
        return f"Open {host}"
    if parsed.scheme == "mailto" and parsed.path:
        return f"Email {parsed.path}"
    return "Open linked resource"


def _run_hyperlink_address(run: Any) -> str:
    """Return the hyperlink address for a text run, if any."""
    try:
        return str(run.hyperlink.address or "")
    except AttributeError:
        return ""


def check(prs: Any, settings: Settings) -> list[Finding]:
    """Detect links whose visible text is generic and ambiguous."""
    del settings
    findings: list[Finding] = []
    for slide_index, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            for paragraph_index, paragraph in enumerate(shape.text_frame.paragraphs):
                for run_index, run in enumerate(paragraph.runs):
                    address = _run_hyperlink_address(run)
                    if not address:
                        continue
                    visible_text = run.text or ""
                    if normalize_link_text(visible_text) not in GENERIC_LINK_TEXT:
                        continue
                    findings.append(
                        Finding(
                            rule_id="generic_link_text",
                            slide_number=slide_index,
                            element_id=str(shape.shape_id),
                            element_type="hyperlink_text",
                            wcag_criterion="2.4.4 Link Purpose (In Context)",
                            section_508_ref="E205.4",
                            risk_level=RiskLevel.LOW,
                            issue_description=(
                                f"Hyperlink text '{visible_text}' is generic. "
                                "Links should describe their destination or purpose."
                            ),
                            suggested_fix=descriptive_link_text(address),
                            metadata={
                                "address": address,
                                "paragraph_index": paragraph_index,
                                "run_index": run_index,
                                "before_text": visible_text,
                            },
                        )
                    )
    return findings
