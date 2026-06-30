"""Interactive CLI report workflow."""

from __future__ import annotations

from pathlib import Path

import click
from pptx import Presentation

from audit import ledger
from audit.rollback import _restore_snapshot
from audit.snapshot import load_snapshot
from fixer.suggest_fix import approve_suggestion, reject_suggestion
from models import LedgerStatus


def show_ledger_summary(ledger_path: Path) -> None:
    """Print a concise ledger summary to the terminal."""
    entries = ledger.load_ledger(ledger_path)
    if not entries:
        click.echo("No ledger entries found.")
        return
    for entry in entries:
        click.echo(
            f"{entry.item_id} | slide {entry.slide_number} | {entry.risk_level.value} | "
            f"{entry.status.value} | {entry.issue_description}"
        )
        if entry.suggested_fix:
            click.echo(f"  suggestion: {entry.suggested_fix}")
        if entry.metadata.get("llm_draft"):
            click.echo(f"  llm draft (for manual use): {entry.metadata['llm_draft']}")


def _needs_review(entry: object) -> bool:
    """Return True for LLM auto-applied low-risk items awaiting human review."""
    return entry.status == LedgerStatus.AUTO_APPLIED and bool(entry.metadata.get("needs_review"))


def review_pending_suggestions(*, pptx_path: Path, output_path: Path, ledger_path: Path, reviewer: str) -> Path:
    """Prompt the user to disposition staged suggestions and LLM auto-fixes.

    Two groups are surfaced: medium-risk pending suggestions (approve/edit/reject)
    and LLM-generated low-risk fixes already auto-applied but flagged for review
    (keep/reject). All edits are written to a single output PPTX.
    """
    entries = ledger.load_ledger(ledger_path)
    pending = [entry for entry in entries if entry.status == LedgerStatus.PENDING_APPROVAL]
    review_auto = [entry for entry in entries if _needs_review(entry)]
    if not pending and not review_auto:
        click.echo("No pending suggestions.")
        return pptx_path

    prs = Presentation(pptx_path)
    for entry in pending:
        click.echo("-" * 72)
        click.echo(f"{entry.item_id} | slide {entry.slide_number} | {entry.issue_description}")
        click.echo(f"Suggested fix: {entry.suggested_fix or ''}")
        action = click.prompt("Action [approve/edit/reject/skip]", default="skip").strip().lower()
        if action == "approve":
            approve_suggestion(prs=prs, ledger_path=ledger_path, item_id=entry.item_id, approved_by=reviewer)
            click.echo("Approved.")
        elif action == "edit":
            replacement = click.prompt("Enter replacement text", default=entry.suggested_fix or "")
            approve_suggestion(
                prs=prs,
                ledger_path=ledger_path,
                item_id=entry.item_id,
                approved_by=reviewer,
                replacement_text=replacement,
            )
            click.echo("Edited and approved.")
        elif action == "reject":
            reject_suggestion(ledger_path, entry.item_id)
            click.echo("Rejected.")
        else:
            click.echo("Skipped.")

    for entry in review_auto:
        click.echo("-" * 72)
        source = entry.metadata.get("suggestion_source", "llm")
        click.echo(f"{entry.item_id} | slide {entry.slide_number} | auto-applied by {source}")
        click.echo(f"Applied text: {entry.suggested_fix or ''}")
        action = click.prompt("Action [keep/reject/skip]", default="keep").strip().lower()
        if action == "keep":
            metadata = {**entry.metadata}
            metadata.pop("needs_review", None)
            ledger.update_entry(
                ledger_path, entry.item_id, approved_by=f"human:{reviewer}", metadata=metadata
            )
            click.echo("Kept.")
        elif action == "reject":
            if entry.snapshot_path:
                _restore_snapshot(prs, load_snapshot(Path(entry.snapshot_path)))
            ledger.update_entry(
                ledger_path,
                entry.item_id,
                status=LedgerStatus.ROLLED_BACK,
                rolled_back_at=ledger.utc_now(),
            )
            click.echo("Rejected and rolled back.")
        else:
            click.echo("Skipped.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)
    return output_path
