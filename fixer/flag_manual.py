"""High-risk manual remediation workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from audit import ledger
from models import Finding, LedgerEntry, LedgerStatus, RiskLevel
from utils.logging import get_logger
from utils.pptx_xml import get_slide, slide_context_text

LOGGER = get_logger(__name__)


def _maybe_llm_draft(finding: Finding, prs: Any | None, provider: Any | None) -> None:
    """Attach an LLM long-description draft to the finding metadata, in place.

    The draft is stored in ``metadata["llm_draft"]`` for a human reviewer; the
    finding's ``suggested_fix`` stays ``None`` (high-risk items are never
    auto-applied), and the PPTX is never modified.
    """
    if provider is None or prs is None:
        return
    from llm import service

    context = ""
    try:
        context = slide_context_text(get_slide(prs, finding.slide_number))
    except (IndexError, ValueError):
        context = ""
    draft = service.draft_high_risk_alternative(
        provider, element_type=finding.element_type, context=context
    )
    if draft:
        finding.metadata = {
            **finding.metadata,
            "llm_draft": draft,
            "suggestion_source": provider.name,
        }


def record_manual_flag(
    finding: Finding,
    ledger_path: Path,
    *,
    prs: Any | None = None,
    provider: Any | None = None,
) -> LedgerEntry:
    """Write a flagged-manual ledger entry for one high-risk finding.

    When ``provider`` and ``prs`` are supplied, a long-description draft is
    generated and stored in the entry metadata for a human reviewer. The PPTX is
    never edited and ``suggested_fix`` remains ``None``.
    """
    if finding.risk_level != RiskLevel.HIGH:
        raise ValueError("Manual flags are only for high-risk findings")
    _maybe_llm_draft(finding, prs, provider)
    item_id = ledger.next_item_id(ledger_path)
    entry = LedgerEntry.from_finding(
        item_id=item_id,
        finding=finding,
        status=LedgerStatus.FLAGGED_MANUAL,
        snapshot_path=None,
    )
    ledger.append_entry(ledger_path, entry)
    LOGGER.info("manual_flag_recorded", item_id=item_id, rule_id=finding.rule_id)
    return entry
