"""Append-only JSON audit ledger utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import LedgerEntry

MUTABLE_FIELDS = {
    "status",
    "applied_at",
    "approved_by",
    "rolled_back_at",
    "snapshot_path",
    "suggested_fix",
    "metadata",
}


def utc_now() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_ledger(path: Path) -> list[LedgerEntry]:
    """Load a ledger file, returning an empty list when it does not exist."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, list):
        raise ValueError(f"Ledger must be a JSON array: {path}")
    return [LedgerEntry.from_dict(item) for item in raw]


def write_ledger(path: Path, entries: list[LedgerEntry]) -> None:
    """Write ledger entries as a formatted JSON array."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump([entry.to_dict() for entry in entries], handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def next_item_id(path: Path) -> str:
    """Return the next deterministic item ID for the ledger date."""
    entries = load_ledger(path)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"fix_{today}_"
    existing_numbers: list[int] = []
    for entry in entries:
        if entry.item_id.startswith(prefix):
            try:
                existing_numbers.append(int(entry.item_id.rsplit("_", 1)[1]))
            except (IndexError, ValueError):
                continue
    sequence = (max(existing_numbers) + 1) if existing_numbers else 1
    return f"{prefix}{sequence:03d}"


def append_entry(path: Path, entry: LedgerEntry) -> LedgerEntry:
    """Append one entry to the ledger."""
    entries = load_ledger(path)
    if any(existing.item_id == entry.item_id for existing in entries):
        raise ValueError(f"Duplicate ledger item_id: {entry.item_id}")
    entries.append(entry)
    write_ledger(path, entries)
    return entry


def find_entry(path: Path, item_id: str) -> LedgerEntry:
    """Find an entry by item ID."""
    for entry in load_ledger(path):
        if entry.item_id == item_id:
            return entry
    raise KeyError(f"Ledger item not found: {item_id}")


def update_entry(path: Path, item_id: str, **updates: Any) -> LedgerEntry:
    """Update allowed lifecycle fields for one ledger entry."""
    invalid = set(updates) - MUTABLE_FIELDS
    if invalid:
        raise ValueError(f"Cannot update immutable ledger fields: {sorted(invalid)}")
    entries = load_ledger(path)
    for entry in entries:
        if entry.item_id != item_id:
            continue
        for key, value in updates.items():
            setattr(entry, key, value)
        write_ledger(path, entries)
        return entry
    raise KeyError(f"Ledger item not found: {item_id}")


def ledger_rows(path: Path) -> list[dict[str, Any]]:
    """Return ledger entries as dictionaries for reporting."""
    return [entry.to_dict() for entry in load_ledger(path)]
