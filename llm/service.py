"""Provider-agnostic LLM tasks consumed by the checker and fixer modules.

These functions are the only LLM surface that ``checker`` and ``fixer`` import.
Each wraps a provider call and returns a safe fallback (``None`` / ``[]``) on any
failure, so a provider error, timeout, or unexpected response never breaks the
deterministic pipeline. The chosen suggestion text is the model output; the
caller keeps its deterministic template as the fallback.
"""

from __future__ import annotations

from typing import Any

from llm import prompts
from llm.base import LLMProvider
from models import Finding, RiskLevel
from utils.logging import get_logger
from utils.pptx_xml import slide_context_text, title_shape, title_text

LOGGER = get_logger(__name__)


def _safe(provider: LLMProvider, action: str, fn: Any) -> str | None:
    """Run a provider call, returning stripped text or ``None`` on failure."""
    try:
        text = fn()
    except Exception as exc:  # provider/SDK/network errors must never break the pipeline
        LOGGER.error("llm_call_failed", action=action, provider=provider.name, error=str(exc))
        return None
    text = (text or "").strip()
    return text or None


def suggest_alt_text(provider: LLMProvider, *, image_bytes: bytes, media_type: str, context: str) -> str | None:
    """Generate image alt text from the image and surrounding slide text."""
    return _safe(
        provider,
        "alt_text",
        lambda: provider.describe_image(
            image_bytes=image_bytes,
            media_type=media_type,
            system=prompts.ALT_TEXT_SYSTEM,
            prompt=prompts.alt_text_prompt(context),
        ),
    )


def suggest_link_text(provider: LLMProvider, *, address: str, context: str) -> str | None:
    """Generate descriptive link text for a generic hyperlink."""
    return _safe(
        provider,
        "link_text",
        lambda: provider.generate_text(
            system=prompts.LINK_TEXT_SYSTEM,
            prompt=prompts.link_text_prompt(address=address, context=context),
        ),
    )


def suggest_slide_title(provider: LLMProvider, *, context: str) -> str | None:
    """Generate a descriptive slide title from the slide's text content."""
    return _safe(
        provider,
        "slide_title",
        lambda: provider.generate_text(
            system=prompts.SLIDE_TITLE_SYSTEM,
            prompt=prompts.slide_title_prompt(context),
        ),
    )


def draft_high_risk_alternative(provider: LLMProvider, *, element_type: str, context: str) -> str | None:
    """Draft a long text-alternative for a high-risk object (human refines it)."""
    return _safe(
        provider,
        "high_risk_draft",
        lambda: provider.generate_text(
            system=prompts.HIGH_RISK_SYSTEM,
            prompt=prompts.high_risk_prompt(element_type=element_type, context=context),
        ),
    )


def detect_weak_titles(provider: LLMProvider, *, prs: Any) -> list[Finding]:
    """Flag slides whose existing title is weak, with an LLM-proposed replacement.

    Only slides that already carry a title shape are considered (absent titles
    are handled deterministically by ``missing_slide_title``). The model both
    judges vagueness and proposes the fix; a clear title yields no finding. Each
    finding targets the title shape so the suggestion can be applied on approval.
    """
    findings: list[Finding] = []
    for slide_index, slide in enumerate(prs.slides, start=1):
        shape = title_shape(slide)
        if shape is None:
            continue
        title = title_text(slide)
        context = slide_context_text(slide, exclude_shape_id=str(shape.shape_id))
        verdict = _safe(
            provider,
            "weak_title",
            lambda: provider.generate_text(
                system=prompts.WEAK_TITLE_SYSTEM,
                prompt=prompts.weak_title_prompt(title=title, context=context),
            ),
        )
        if not verdict or verdict.strip().upper() in {"OK", "NONE"}:
            continue
        suggestion = verdict.strip()
        if suggestion == title:
            continue
        findings.append(
            Finding(
                rule_id="weak_slide_title",
                slide_number=slide_index,
                element_id=str(shape.shape_id),
                element_type="slide_title",
                wcag_criterion="2.4.6 Headings and Labels",
                section_508_ref="E205.4",
                risk_level=RiskLevel.MEDIUM,
                issue_description=(
                    f"Slide title {title!r} is vague or non-descriptive. Descriptive "
                    "titles help screen reader users navigate the presentation."
                ),
                suggested_fix=suggestion,
                metadata={"detected_by": provider.name, "suggestion_source": provider.name},
            )
        )
    return findings


def detect_semantic_issues(provider: LLMProvider, *, prs: Any) -> list[Finding]:
    """Run an additive semantic detection pass over a presentation's slides.

    Returns findings tagged with ``metadata["detected_by"]`` provenance. These
    are MEDIUM risk (a human approves the suggested fix) and flow through the
    same triage/ledger/snapshot machinery as deterministic findings.
    """
    findings: list[Finding] = []
    for slide_index, slide in enumerate(prs.slides, start=1):
        title = title_text(slide)
        context = slide_context_text(slide)
        if not title and not context:
            continue
        verdict = _safe(
            provider,
            "detection",
            lambda: provider.generate_text(
                system=prompts.DETECTION_SYSTEM,
                prompt=prompts.detection_prompt(slide_number=slide_index, title=title, context=context),
            ),
        )
        if not verdict or verdict.strip().upper() == "NONE":
            continue
        findings.append(
            Finding(
                rule_id="llm_semantic_review",
                slide_number=slide_index,
                element_id=f"slide:{slide_index}",
                element_type="slide_content",
                wcag_criterion="2.4.6 Headings and Labels",
                section_508_ref="E205.4",
                risk_level=RiskLevel.MEDIUM,
                issue_description=f"LLM accessibility review: {verdict.strip()}",
                suggested_fix=None,
                metadata={"detected_by": provider.name},
            )
        )
    return findings
