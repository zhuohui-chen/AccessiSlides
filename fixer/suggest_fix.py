"""Medium-risk suggestion and approval workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from audit import ledger
from audit.snapshot import create_shape_snapshot
from config import Settings
from models import Finding, LedgerEntry, LedgerStatus, RiskLevel
from utils.logging import get_logger
from utils.pptx_xml import get_image_blob, get_shape_by_id, get_slide, set_alt_text, set_title_text

LOGGER = get_logger(__name__)

_ALT_TEXT_RULES = {"missing_image_alt_text", "weak_image_alt_text"}

# Medium-risk rules whose approval applies a concrete edit to the PPTX.
# Other medium-risk rules (e.g. "llm_semantic_review", "reading_order_review")
# are advisory review notes with no auto-applicable shape edit; they are
# acknowledged via ``acknowledge_suggestion`` instead of ``approve_suggestion``.
APPLYABLE_RULES = _ALT_TEXT_RULES | {"weak_slide_title"}


def is_applyable(rule_id: str | None) -> bool:
    """Return True when an approved suggestion for this rule edits the PPTX.

    Advisory review notes return False: approving them records human
    acknowledgement in the ledger but makes no change to the presentation.
    """
    return rule_id in APPLYABLE_RULES


def _maybe_llm_alt_text(finding: Finding, prs: Any | None, provider: Any | None) -> None:
    """Replace an alt-text finding's suggested fix with LLM output, in place.

    No-op unless a provider and presentation are supplied and the image bytes
    can be read. On any miss the finding keeps its deterministic template text.
    """
    if provider is None or prs is None or finding.rule_id not in _ALT_TEXT_RULES:
        return
    from llm import service

    try:
        slide = get_slide(prs, finding.slide_number)
        shape = get_shape_by_id(slide, finding.element_id)
    except (IndexError, KeyError):
        return
    blob = get_image_blob(shape)
    if blob is None:
        return
    image_bytes, media_type = blob
    context = " ".join(part for part in (finding.suggested_fix or "", finding.issue_description) if part)
    suggestion = service.suggest_alt_text(
        provider, image_bytes=image_bytes, media_type=media_type, context=context
    )
    if suggestion:
        finding.suggested_fix = suggestion
        finding.metadata = {**finding.metadata, "suggestion_source": provider.name}


def record_pending_suggestion(
    finding: Finding,
    ledger_path: Path,
    *,
    prs: Any | None = None,
    provider: Any | None = None,
) -> LedgerEntry:
    """Write a pending approval ledger entry for one medium-risk finding.

    When ``provider`` and ``prs`` are supplied and the finding is an image
    alt-text issue, the suggested fix is regenerated from the image via the LLM;
    otherwise the finding's deterministic template suggestion is kept.
    """
    if finding.risk_level != RiskLevel.MEDIUM:
        raise ValueError("Pending suggestions are only for medium-risk findings")
    _maybe_llm_alt_text(finding, prs, provider)
    item_id = ledger.next_item_id(ledger_path)
    entry = LedgerEntry.from_finding(
        item_id=item_id,
        finding=finding,
        status=LedgerStatus.PENDING_APPROVAL,
        snapshot_path=None,
    )
    ledger.append_entry(ledger_path, entry)
    LOGGER.info("suggestion_recorded", item_id=item_id, rule_id=finding.rule_id)
    return entry


def reject_suggestion(ledger_path: Path, item_id: str) -> LedgerEntry:
    """Reject a pending medium-risk suggestion."""
    entry = ledger.find_entry(ledger_path, item_id)
    if entry.status != LedgerStatus.PENDING_APPROVAL:
        raise ValueError(f"Item {item_id} is not pending approval")
    return ledger.update_entry(ledger_path, item_id, status=LedgerStatus.REJECTED)


def acknowledge_suggestion(ledger_path: Path, item_id: str, *, approved_by: str) -> LedgerEntry:
    """Record human acknowledgement of an advisory medium-risk review note.

    Advisory findings (e.g. ``llm_semantic_review``) have no auto-applicable
    shape edit, so this marks the ledger entry approved without touching the
    PPTX. Use :func:`approve_suggestion` for rules in :data:`APPLYABLE_RULES`.
    """
    entry = ledger.find_entry(ledger_path, item_id)
    if entry.status != LedgerStatus.PENDING_APPROVAL:
        raise ValueError(f"Item {item_id} is not pending approval")
    if is_applyable(entry.rule_id):
        raise ValueError(f"Rule {entry.rule_id} must be applied via approve_suggestion")
    updated = ledger.update_entry(
        ledger_path,
        item_id,
        status=LedgerStatus.APPROVED,
        applied_at=ledger.utc_now(),
        approved_by=f"human:{approved_by}",
    )
    LOGGER.info("suggestion_acknowledged", item_id=item_id, rule_id=entry.rule_id)
    return updated


def approve_suggestion(
    *,
    prs: Any,
    ledger_path: Path,
    item_id: str,
    approved_by: str,
    replacement_text: str | None = None,
    settings: Settings | None = None,
) -> LedgerEntry:
    """Approve and apply a pending medium-risk suggestion.

    Applies image alt-text suggestions (``missing_image_alt_text``,
    ``weak_image_alt_text``) and weak-title rewrites (``weak_slide_title``).
    Advisory rules without a concrete edit are handled by
    :func:`acknowledge_suggestion` instead.
    """
    resolved_settings = settings or Settings()
    entry = ledger.find_entry(ledger_path, item_id)
    if entry.status != LedgerStatus.PENDING_APPROVAL:
        raise ValueError(f"Item {item_id} is not pending approval")
    if entry.risk_level != RiskLevel.MEDIUM:
        raise ValueError(f"Item {item_id} is not medium risk")

    if not is_applyable(entry.rule_id):
        raise ValueError(f"No approval handler for rule {entry.rule_id}")

    snapshot_path = create_shape_snapshot(
        prs=prs,
        ledger_path=ledger_path,
        item_id=item_id,
        slide_number=entry.slide_number,
        shape_id=entry.element_id,
        settings=resolved_settings,
    )
    slide = get_slide(prs, entry.slide_number)
    shape = get_shape_by_id(slide, entry.element_id)
    new_text = replacement_text or entry.suggested_fix or ""
    if entry.rule_id in _ALT_TEXT_RULES:
        set_alt_text(shape, new_text)
    else:  # weak_slide_title
        set_title_text(shape, new_text)
    updated = ledger.update_entry(
        ledger_path,
        item_id,
        status=LedgerStatus.APPROVED,
        applied_at=ledger.utc_now(),
        approved_by=f"human:{approved_by}",
        snapshot_path=str(snapshot_path),
        suggested_fix=replacement_text or entry.suggested_fix,
    )
    LOGGER.info("suggestion_approved", item_id=item_id, rule_id=entry.rule_id)
    return updated
