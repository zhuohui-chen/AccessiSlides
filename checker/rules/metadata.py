"""Presentation-level metadata accessibility checks."""

from __future__ import annotations

from typing import Any

from config import Settings
from models import Finding, RiskLevel


def check(prs: Any, settings: Settings) -> list[Finding]:
    """Detect missing presentation language metadata.

    Args:
        prs: Loaded python-pptx presentation.
        settings: Runtime settings.

    Returns:
        A list containing a finding when the language is missing.
    """
    language = str(getattr(prs.core_properties, "language", "") or "").strip()
    if language:
        return []
    return [
        Finding(
            rule_id="missing_presentation_language",
            slide_number=0,
            element_id="core_properties.language",
            element_type="presentation_metadata",
            wcag_criterion="3.1.1 Language of Page",
            section_508_ref="E205.4",
            risk_level=RiskLevel.LOW,
            issue_description=(
                "The presentation language metadata is missing. Screen readers "
                "may use the wrong pronunciation rules."
            ),
            suggested_fix=settings.default_language,
            metadata={"property": "language", "before": language},
        )
    ]
