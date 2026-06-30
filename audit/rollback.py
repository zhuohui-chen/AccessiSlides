"""Rollback engine for previously applied fixes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation

from audit import ledger
from audit.snapshot import load_snapshot
from models import LedgerStatus
from utils.pptx_xml import delete_shape_by_id, get_shape_by_id, get_slide, replace_shape_xml

ROLLBACK_ALLOWED_STATUSES = {LedgerStatus.AUTO_APPLIED, LedgerStatus.APPROVED}


def _restore_snapshot(prs: Any, snapshot_data: dict[str, Any]) -> None:
    """Restore a presentation from one snapshot object."""
    kind = snapshot_data.get("kind")
    if kind == "shape_xml":
        slide = get_slide(prs, int(snapshot_data["slide_number"]))
        shape = get_shape_by_id(slide, str(snapshot_data["shape_id"]))
        replace_shape_xml(shape, str(snapshot_data["xml"]))
        return
    if kind == "added_shape":
        slide = get_slide(prs, int(snapshot_data["slide_number"]))
        delete_shape_by_id(slide, str(snapshot_data["created_shape_id"]))
        return
    if kind == "core_property":
        setattr(prs.core_properties, str(snapshot_data["property_name"]), snapshot_data.get("before") or "")
        return
    raise ValueError(f"Unsupported snapshot kind: {kind}")


def rollback_item(*, pptx_path: Path, output_path: Path, ledger_path: Path, item_id: str) -> Path:
    """Roll back one applied fix and save a new PPTX.

    Args:
        pptx_path: Current PPTX containing the applied fix.
        output_path: Destination PPTX for the rollback result.
        ledger_path: JSON ledger containing the item.
        item_id: Ledger item ID to roll back.

    Returns:
        Path to the saved rollback PPTX.
    """
    entry = ledger.find_entry(ledger_path, item_id)
    if entry.status not in ROLLBACK_ALLOWED_STATUSES:
        raise ValueError(f"Item {item_id} cannot be rolled back from status {entry.status.value}")
    if not entry.snapshot_path:
        raise ValueError(f"Item {item_id} has no snapshot_path")

    prs = Presentation(pptx_path)
    snapshot_data = load_snapshot(Path(entry.snapshot_path))
    _restore_snapshot(prs, snapshot_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)
    ledger.update_entry(
        ledger_path,
        item_id,
        status=LedgerStatus.ROLLED_BACK,
        rolled_back_at=ledger.utc_now(),
    )
    return output_path
