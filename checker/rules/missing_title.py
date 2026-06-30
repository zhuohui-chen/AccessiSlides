"""Slide title accessibility checks."""

from __future__ import annotations

from typing import Any

from config import Settings
from models import Finding, RiskLevel
from utils.pptx_xml import title_text


def check(prs: Any, settings: Settings) -> list[Finding]:
    """Detect slides that do not contain a usable title."""
    findings: list[Finding] = []
    for index, slide in enumerate(prs.slides, start=1):
        if title_text(slide):
            continue
        findings.append(
            Finding(
                rule_id="missing_slide_title",
                slide_number=index,
                element_id=f"slide:{index}",
                element_type="slide_title",
                wcag_criterion="2.4.2 Page Titled",
                section_508_ref="E205.4",
                risk_level=RiskLevel.LOW,
                issue_description=(
                    "Slide has no detectable title. Slide titles help screen "
                    "reader users navigate the presentation."
                ),
                suggested_fix=f"{settings.auto_title_prefix} {index}",
                metadata={"title_text": f"{settings.auto_title_prefix} {index}"},
            )
        )
    return findings
