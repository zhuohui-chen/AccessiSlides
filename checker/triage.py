"""Risk triage helpers for accessibility findings."""

from __future__ import annotations

from models import Finding, RiskLevel


LOW_RISK_RULES = {
    "missing_slide_title",
    "generic_link_text",
    "missing_presentation_language",
}
MEDIUM_RISK_RULES = {
    "missing_image_alt_text",
    "weak_image_alt_text",
    "weak_slide_title",
    "reading_order_review",
    "llm_semantic_review",
    "low_contrast_text",
    "low_contrast_over_image",
    "low_contrast_over_gradient",
}
HIGH_RISK_RULES = {
    "chart_requires_manual_alt_text",
    "complex_table_review",
    "media_requires_captions",
}


def classify(finding: Finding) -> RiskLevel:
    """Return the risk level for a finding.

    The checker rules already emit a risk level, but this function centralizes
    the policy so new rules can be verified against the documented framework.
    """
    if finding.rule_id in LOW_RISK_RULES:
        return RiskLevel.LOW
    if finding.rule_id in MEDIUM_RISK_RULES:
        return RiskLevel.MEDIUM
    if finding.rule_id in HIGH_RISK_RULES:
        return RiskLevel.HIGH
    return finding.risk_level
