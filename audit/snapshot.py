"""Snapshot persistence for atomic fixes and rollback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import Settings
from utils.pptx_xml import get_slide, get_shape_by_id, shape_xml


def snapshot_dir_for_ledger(ledger_path: Path, settings: Settings | None = None) -> Path:
    """Return the snapshot directory associated with a ledger path."""
    resolved_settings = settings or Settings()
    return ledger_path.parent / resolved_settings.snapshot_dir_name


def _write_snapshot(path: Path, data: dict[str, Any]) -> Path:
    """Write a JSON snapshot file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return path


def create_shape_snapshot(
    *,
    prs: Any,
    ledger_path: Path,
    item_id: str,
    slide_number: int,
    shape_id: str,
    settings: Settings | None = None,
) -> Path:
    """Serialize the current XML for one shape before applying a fix."""
    slide = get_slide(prs, slide_number)
    shape = get_shape_by_id(slide, shape_id)
    path = snapshot_dir_for_ledger(ledger_path, settings) / f"{item_id}.json"
    return _write_snapshot(
        path,
        {
            "kind": "shape_xml",
            "item_id": item_id,
            "slide_number": slide_number,
            "shape_id": str(shape_id),
            "xml": shape_xml(shape),
        },
    )


def create_added_shape_snapshot(
    *,
    ledger_path: Path,
    item_id: str,
    slide_number: int,
    created_shape_id: str,
    settings: Settings | None = None,
) -> Path:
    """Record a shape that was added so rollback can delete it."""
    path = snapshot_dir_for_ledger(ledger_path, settings) / f"{item_id}.json"
    return _write_snapshot(
        path,
        {
            "kind": "added_shape",
            "item_id": item_id,
            "slide_number": slide_number,
            "created_shape_id": str(created_shape_id),
        },
    )


def create_core_property_snapshot(
    *,
    prs: Any,
    ledger_path: Path,
    item_id: str,
    property_name: str,
    settings: Settings | None = None,
) -> Path:
    """Snapshot a presentation core property before it is changed."""
    before = getattr(prs.core_properties, property_name)
    path = snapshot_dir_for_ledger(ledger_path, settings) / f"{item_id}.json"
    return _write_snapshot(
        path,
        {
            "kind": "core_property",
            "item_id": item_id,
            "property_name": property_name,
            "before": before,
        },
    )


def load_snapshot(path: Path) -> dict[str, Any]:
    """Load a snapshot JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Snapshot must be a JSON object: {path}")
    return data
