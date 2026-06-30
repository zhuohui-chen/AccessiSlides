# CLAUDE.md — PowerPoint Accessibility Agent

This file is read automatically by Claude Code at session start.
It defines project context, coding standards, module responsibilities,
and the commands needed to build, test, and run this project.

---

## Project Summary

A Python CLI tool that detects accessibility issues in PowerPoint (`.pptx`) files,
classifies them by risk level (low / medium / high), auto-fixes low-risk issues,
proposes fixes for medium-risk issues pending human approval, and flags high-risk
issues for manual remediation — all with a full per-item audit ledger and rollback.

Compliance standards: **WCAG 2.1** (https://www.w3.org/TR/WCAG21/) and
**Section 508** (https://www.section508.gov/create/presentations/).

---

## Language & Runtime

- Python **3.11+** only. Do not use `match` syntax below 3.10 or walrus operator below 3.8.
- All scripts must run with `uv run python cli.py <command> [args]`.
- Environment and packages are managed exclusively by **`uv`**. Never use `pip`, `pip install`, `python -m venv`, or `requirements.txt` directly.
- The virtual environment lives at `.venv/` and is created automatically by `uv sync`.
- The lockfile is `uv.lock` — always commit it. Never edit it by hand.

---

## Package Management with uv

Install uv once per machine:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # macOS / Linux
# Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

| Task | Command |
|---|---|
| Create env + install all deps | `uv sync` |
| Add a runtime dependency | `uv add <package>` |
| Add a dev-only dependency | `uv add --dev <package>` |
| Remove a dependency | `uv remove <package>` |
| Update a specific package | `uv lock --upgrade-package <package>` |
| Update all packages | `uv lock --upgrade` |
| Run a command in the env | `uv run <command>` |
| Show installed packages | `uv pip list` |

Project metadata and dependencies live in **`pyproject.toml`** (not `requirements.txt`). When Claude Code adds a new library, it must use `uv add <package>`, not edit `pyproject.toml` by hand, to keep `uv.lock` in sync.

---

## Key Dependencies

These are declared in `pyproject.toml` and resolved in `uv.lock`.

```toml
# Runtime
python-pptx       # PPTX read/write — primary file manipulation library
openpyxl          # XLSX audit report generation
reportlab         # PDF summary report generation
click             # CLI interface (preferred over argparse)
pydantic-settings # Config/env management
structlog         # Structured JSON logging for audit trail

# Dev
pytest            # Test runner
pytest-cov        # Coverage reporting
```

To install everything: `uv sync`
To add a new package: `uv add <package>` (runtime) or `uv add --dev <package>` (dev only)

---

## Project Structure

```
checker/
  rules/            # One .py file per WCAG/508 rule check
  triage.py         # Risk classifier → returns (issue, risk_level)

fixer/
  auto_fix.py       # Low-risk only: applies fix, writes snapshot, writes ledger entry
  suggest_fix.py    # Medium-risk: generates suggestion, writes PENDING ledger entry
  flag_manual.py    # High-risk: writes FLAGGED ledger entry, no file edit

audit/
  ledger.py         # Append-only JSON ledger of all fix items
  snapshot.py       # Save/restore element-level before/after snapshots
  rollback.py       # Apply rollback from snapshot; update ledger status

report/
  interactive.py    # CLI interactive report: approve / reject / rollback per item
  export_xlsx.py    # Generate XLSX with one row per ledger item
  export_pdf.py     # Generate PDF summary report

cli.py              # Entry point: check | fix | report | rollback commands
config.py           # Pydantic settings model; reads from .env
tests/              # pytest test suite; mirrors src structure
```

---

## Module Responsibilities (do not cross these boundaries)

| Module | Allowed to do | NOT allowed to do |
|---|---|---|
| `checker/rules/*` | Detect issues, return structured findings | Modify the PPTX, write to ledger |
| `checker/triage.py` | Assign risk levels | Apply or suggest any fix |
| `fixer/auto_fix.py` | Edit PPTX for LOW-risk items only, write snapshot + ledger | Touch MEDIUM or HIGH items |
| `fixer/suggest_fix.py` | Generate suggestion text for MEDIUM-risk, write PENDING ledger | Edit the PPTX directly |
| `fixer/flag_manual.py` | Write FLAGGED ledger entry for HIGH-risk | Edit the PPTX or generate suggestions |
| `audit/rollback.py` | Restore snapshot, update ledger | Create new snapshots or apply new fixes |
| `report/*` | Read ledger + PPTX, produce output | Edit the PPTX or write to ledger |

---

## Ledger Schema

Every issue must produce exactly one ledger entry. The ledger is an append-only
JSON array stored at `{output_dir}/ledger.json`.

```python
{
    "item_id": str,           # "fix_{YYYYMMDD}_{seq:03d}"
    "slide_number": int,      # 1-indexed
    "element_id": str,        # python-pptx shape.shape_id as string
    "element_type": str,      # "image" | "text_box" | "table" | "chart" | "slide_title" | etc.
    "wcag_criterion": str,    # e.g. "1.1.1 Non-text Content"
    "section_508_ref": str,   # e.g. "E205.4"
    "risk_level": str,        # "low" | "medium" | "high"
    "issue_description": str, # Plain-language description of the problem
    "suggested_fix": str,     # Proposed fix text (null for high-risk)
    "status": str,            # "auto_applied" | "pending_approval" | "approved" |
                              # "rejected" | "flagged_manual" | "rolled_back"
    "applied_at": str,        # ISO 8601 timestamp or null
    "approved_by": str,       # "auto" | "human:{name}" or null
    "rolled_back_at": str,    # ISO 8601 timestamp or null
    "snapshot_path": str      # Path to before/after snapshot file or null
}
```

---

## Risk Triage Rules

When adding new checker rules, assign risk level using these criteria:

**Low** — deterministic structural issues, no content judgment required:
- Missing slide title
- Generic link text ("click here", "here", "link", "read more")
- Missing presentation language metadata
- Duplicate slide titles
- Missing alt text on decorative images (when flagged as decorative)

**Medium** — fix requires context but a good suggestion can be generated:
- Missing alt text on non-decorative images (suggest from surrounding text)
- Alt text that is filename-like or auto-generated ("image001.png")
- Reading order that can be inferred from spatial position
- Contrast ratio violations where a nearby compliant color exists

**High** — requires human understanding of meaning and intent, no auto-fix:
- Complex charts and diagrams (content is data-dependent)
- Color-as-only-differentiator in charts or diagrams
- Ambiguous or meaning-sensitive text that may need human rewrite
- Nested tables or complex layouts
- Embedded media without transcripts or captions

---

## Coding Standards

- **Type hints required** on all function signatures.
- **Docstrings required** on all public functions and classes (Google style).
- **No bare `except`**: always catch specific exception types.
- **No side effects on import**: no file I/O, no network calls at module level.
- All file paths are `pathlib.Path` objects, never raw strings.
- PPTX objects must never be passed between modules as raw bytes; use paths.
- Ledger writes are always append-only; never mutate existing entries except
  to update `status`, `applied_at`, `approved_by`, or `rolled_back_at`.
- Log all state changes with `structlog` at INFO level; errors at ERROR level.

---

## Snapshot & Rollback Protocol

Before ANY auto-fix or approved medium-risk fix is applied:
1. Serialize the target element's current state to a snapshot file.
2. Record `snapshot_path` in the ledger entry.
3. Apply the fix.
4. Update ledger entry status and `applied_at`.

Rollback flow:
1. Load the snapshot for `item_id`.
2. Restore the element in the PPTX.
3. Save a new PPTX output (never overwrite the last clean state).
4. Update ledger entry: `status = "rolled_back"`, `rolled_back_at = now()`.

Rollback must be possible per item in any order — do not chain dependencies.

---

## Open-Source Skills Available (Claude Code)

These skills are available in this environment and should be used
when generating file outputs:

| Task | Skill path |
|---|---|
| Generate PPTX output/reports | `/mnt/skills/public/pptx/SKILL.md` |
| Generate XLSX audit reports | `/mnt/skills/public/xlsx/SKILL.md` |
| Generate PDF summary reports | `/mnt/skills/public/pdf/SKILL.md` |
| Read uploaded PPTX/DOCX/XLSX | `/mnt/skills/public/file-reading/SKILL.md` |

Always read the relevant SKILL.md before writing code that produces these file types.

---

## Run Commands

All commands use `uv run` — no manual environment activation needed.

```bash
# Check a file (no edits, report only)
uv run python cli.py check --input slides.pptx

# Full fix run (auto-fix low-risk, stage medium-risk, flag high-risk)
uv run python cli.py fix --input slides.pptx --output fixed.pptx --ledger ./audit/ledger.json

# Interactive report (approve / reject / rollback)
uv run python cli.py report --ledger ./audit/ledger.json --pptx fixed.pptx

# Roll back a single fix item
uv run python cli.py rollback --ledger ./audit/ledger.json --item-id fix_20240601_001 --pptx fixed.pptx

# Export audit report to XLSX
uv run python cli.py export --ledger ./audit/ledger.json --format xlsx --output audit_report.xlsx

# Export summary to PDF
uv run python cli.py export --ledger ./audit/ledger.json --format pdf --output summary.pdf

# Run all tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ -v --cov=. --cov-report=term-missing

# Add a new runtime dependency
uv add <package-name>

# Add a dev-only dependency
uv add --dev <package-name>
```

---

## Testing Expectations

- Every checker rule must have at least one positive test (issue found)
  and one negative test (no issue on a clean element).
- Every auto-fix must have a before/after test confirming the PPTX state.
- Every rollback must have a test confirming the element is restored to original state.
- Ledger entries must be tested for correct schema and status transitions.
- Use `tmp_path` (pytest fixture) for all file I/O in tests — never write to project root.

---

## What NOT to Build (Current Phase)

- No web UI, browser interface, or REST API — CLI only for now.
- No batch multi-file processing.
- No cloud storage or S3 integration.
- No email or Slack notifications.
- No real-time editor plugin.
- No user account system.

These are explicitly deferred to future phases. Do not scaffold them.

---

## Compliance Context

When writing issue descriptions and fix suggestions, always reference
the specific WCAG criterion and Section 508 provision. Examples:

- "Missing alt text violates **WCAG 1.1.1 Non-text Content** (Level A)
  and **Section 508 E205.4**. Screen readers will skip this image entirely."
- "Generic link text 'click here' violates **WCAG 2.4.4 Link Purpose**
  (Level A). Replace with descriptive text that makes sense out of context."

Rule definitions should link to:
- WCAG: `https://www.w3.org/TR/WCAG21/#<criterion-slug>`
- Section 508: `https://www.section508.gov/create/presentations/`
