"""Shared data models for the PowerPoint accessibility agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class RiskLevel(StrEnum):
    """Supported accessibility remediation risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LedgerStatus(StrEnum):
    """Allowed ledger entry lifecycle states."""

    AUTO_APPLIED = "auto_applied"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FLAGGED_MANUAL = "flagged_manual"
    ROLLED_BACK = "rolled_back"


@dataclass(slots=True)
class Finding:
    """A single detected accessibility issue.

    Attributes:
        rule_id: Stable identifier for the checker rule.
        slide_number: 1-indexed slide number, or 0 for presentation-level issues.
        element_id: Stable shape ID or presentation property name.
        element_type: Human-readable target type.
        wcag_criterion: WCAG criterion tied to this issue.
        section_508_ref: Section 508 reference tied to this issue.
        risk_level: Low, medium, or high remediation risk.
        issue_description: Plain-language explanation of the issue.
        suggested_fix: Proposed remediation text, if available.
        metadata: Rule-specific context needed by fixers.
    """

    rule_id: str
    slide_number: int
    element_id: str
    element_type: str
    wcag_criterion: str
    section_508_ref: str
    risk_level: RiskLevel
    issue_description: str
    suggested_fix: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the finding."""
        data = asdict(self)
        data["risk_level"] = self.risk_level.value
        return data


@dataclass(slots=True)
class LedgerEntry:
    """Append-only audit record for one detected issue."""

    item_id: str
    slide_number: int
    element_id: str
    element_type: str
    wcag_criterion: str
    section_508_ref: str
    risk_level: RiskLevel
    issue_description: str
    suggested_fix: str | None
    status: LedgerStatus
    applied_at: str | None = None
    approved_by: str | None = None
    rolled_back_at: str | None = None
    snapshot_path: str | None = None
    rule_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_finding(
        cls,
        *,
        item_id: str,
        finding: Finding,
        status: LedgerStatus,
        snapshot_path: Path | None = None,
        applied_at: str | None = None,
        approved_by: str | None = None,
    ) -> "LedgerEntry":
        """Build a ledger entry from a checker finding."""
        return cls(
            item_id=item_id,
            slide_number=finding.slide_number,
            element_id=finding.element_id,
            element_type=finding.element_type,
            wcag_criterion=finding.wcag_criterion,
            section_508_ref=finding.section_508_ref,
            risk_level=finding.risk_level,
            issue_description=finding.issue_description,
            suggested_fix=finding.suggested_fix,
            status=status,
            applied_at=applied_at,
            approved_by=approved_by,
            snapshot_path=str(snapshot_path) if snapshot_path else None,
            rule_id=finding.rule_id,
            metadata=finding.metadata,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LedgerEntry":
        """Build a ledger entry from decoded JSON."""
        return cls(
            item_id=str(data["item_id"]),
            slide_number=int(data["slide_number"]),
            element_id=str(data["element_id"]),
            element_type=str(data["element_type"]),
            wcag_criterion=str(data["wcag_criterion"]),
            section_508_ref=str(data["section_508_ref"]),
            risk_level=RiskLevel(str(data["risk_level"])),
            issue_description=str(data["issue_description"]),
            suggested_fix=data.get("suggested_fix"),
            status=LedgerStatus(str(data["status"])),
            applied_at=data.get("applied_at"),
            approved_by=data.get("approved_by"),
            rolled_back_at=data.get("rolled_back_at"),
            snapshot_path=data.get("snapshot_path"),
            rule_id=data.get("rule_id"),
            metadata=dict(data.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the entry."""
        data = asdict(self)
        data["risk_level"] = self.risk_level.value
        data["status"] = self.status.value
        return data
