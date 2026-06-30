# PowerPoint Accessibility Agent

> **From Checking to Fixing** — A human-in-the-loop PowerPoint accessibility remediation system grounded in WCAG 2.x and Section 508 compliance.

PowerPoint remains one of the most widely used formats for teaching, training, and public communication — yet accessible slide creation is still inconsistent and labor-intensive. Existing tools like Microsoft's built-in Accessibility Checker find *most* issues but explicitly not all, and private remediation services can cost $7+ per page, putting large-scale work out of reach for schools and public institutions.

This project addresses that gap with a practical, open-source agentic system that auto-fixes what it safely can, surfaces suggested fixes for human review, and flags complex issues for manual resolution — all with a full audit trail and rollback capability.

---

## Compliance References

- **WCAG 2.1 / 2.2**: https://www.w3.org/TR/WCAG21/
- **WCAG Quick Reference**: https://www.w3.org/WAI/WCAG21/quickref/
- **Section 508 Standards**: https://www.section508.gov/
- **Section 508 — Presentations Guidance**: https://www.section508.gov/create/presentations/
- **ADA Title II Digital Accessibility Rule**: https://www.ada.gov/resources/2024-03-08-web-rule/
  - Phase 1 compliance deadline: **April 2026** (state/large local governments)
  - Phase 2 compliance deadline: **April 2027** (smaller local governments)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Package & environment manager | `uv` (replaces pip + venv) |
| PPTX parsing & editing | `python-pptx` |
| PPTX generation (reports/exports) | `python-pptx` + Claude Code PPTX skill |
| Excel audit reports | `openpyxl` + Claude Code XLSX skill |
| PDF reports | `reportlab` + Claude Code PDF skill |
| CLI interface | `click` or `argparse` |
| Testing | `pytest` |
| Configuration | `pydantic-settings` / `.env` |
| Logging & audit trail | `structlog` + JSON log files |
| Diff / rollback storage | JSON snapshots per fix item |

---

## Open Source Resources Used

| Resource | Purpose | Link |
|---|---|---|
| `uv` | Python package & environment manager | https://docs.astral.sh/uv/ |
| `python-pptx` | Read and write `.pptx` files | https://python-pptx.readthedocs.io/ |
| Claude Code PPTX Skill | Generate polished PPTX output | `/mnt/skills/public/pptx/SKILL.md` |
| Claude Code XLSX Skill | Generate structured audit spreadsheets | `/mnt/skills/public/xlsx/SKILL.md` |
| Claude Code PDF Skill | Generate PDF summary reports | `/mnt/skills/public/pdf/SKILL.md` |
| `axe-core` (reference) | WCAG rule definitions reference | https://github.com/dequelabs/axe-core |
| `accessible_pptx` patterns | Community accessibility check patterns | https://github.com/topics/accessibility-checker |
| `pytest` | Unit & integration testing | https://docs.pytest.org/ |
| `structlog` | Structured JSON logging for audit trail | https://www.structlog.org/ |

---

## Architecture Overview

```
pptx_input/
│
├── checker/             # Issue detection engine
│   ├── rules/           # One module per WCAG/508 check rule
│   └── triage.py        # Risk classification (low / medium / high)
│
├── fixer/               # Remediation engine
│   ├── auto_fix.py      # Low-risk: applies fixes automatically
│   ├── suggest_fix.py   # Medium-risk: proposes fix, awaits approval
│   └── flag_manual.py   # High-risk: flags for human, no auto-action
│
├── audit/               # Audit trail & rollback
│   ├── ledger.py        # Itemized fix log (one entry per fix)
│   ├── snapshot.py      # Before/after snapshots per item
│   └── rollback.py      # Rollback engine (per-item or bulk)
│
├── report/              # Report generation
│   ├── interactive.py   # Interactive CLI report (approve / reject / rollback)
│   ├── export_xlsx.py   # Excel itemized audit report
│   └── export_pdf.py    # PDF summary report
│
├── cli.py               # Entry point
├── config.py            # Settings and thresholds
└── tests/               # pytest test suite
```

---

## Must-Have Features

### 1. Risk Triage Framework

Every detected accessibility issue is classified before any action is taken:

| Risk Level | Criteria | Examples |
|---|---|---|
| **Low** | Structural, deterministic, no content judgment needed | Missing slide title, broken/generic link text ("click here"), missing language metadata |
| **Medium** | Requires context but a good suggestion can be generated | Alt text that is missing or auto-generated, reading order that is likely wrong |
| **High** | Requires human understanding of meaning and intent | Complex diagrams, charts with embedded data, meaning-sensitive slide revisions, color-only information |

### 2. Auto-Fix (Low Risk)

Low-risk issues are fixed automatically without human interaction. Each fix is:
- Applied atomically to the PPTX
- Logged as a ledger entry with before/after state
- Individually revertible via rollback

Examples: adding a placeholder slide title, normalizing link text, injecting missing language metadata.

### 3. Suggestive Fix — Human Approves (Medium Risk)

The system generates a proposed fix and presents it for human review. The human can:
- **Approve** → fix is applied and logged
- **Edit then approve** → modified fix is applied and logged
- **Reject** → issue is logged as unresolved, no change made

Examples: alt-text suggestions generated from slide context, reading-order resequencing proposals.

### 4. Suggestive Fix — Human Must Fix Manually (High Risk)

The system flags the issue, describes the problem in plain language, and provides guidance based on WCAG/508 criteria. No automated edit is attempted. The human is responsible for opening the file and making the change.

Examples: complex chart descriptions, diagrams that encode meaning through color alone, context-sensitive text revisions.

### 5. Interactive Report

After a run, the system presents an interactive CLI (or structured JSON output) report covering all issues found. For each item the human can:
- View the issue description and risk level
- View the proposed or applied fix
- **Approve** a pending medium-risk suggestion
- **Reject** a pending suggestion
- **Roll back** a previously applied fix (low or medium risk)

### 6. Itemized Fix Ledger (Human Audit)

Every detected issue — regardless of whether a fix was applied — produces a ledger entry containing:

```json
{
  "item_id": "fix_20240601_001",
  "slide_number": 3,
  "element_type": "image",
  "wcag_criterion": "1.1.1 Non-text Content",
  "section_508_ref": "E205.4",
  "risk_level": "medium",
  "issue_description": "Image has no alt text",
  "suggested_fix": "Diagram showing Q3 revenue by region",
  "status": "pending_approval",
  "applied_at": null,
  "rolled_back_at": null
}
```

The full ledger is exportable as XLSX (one row per item) and PDF summary.

### 7. Per-Item Rollback

Any applied fix can be independently rolled back without affecting other fixes:
- Restores the original element state from the pre-fix snapshot
- Updates ledger entry status to `rolled_back`
- Produces a new PPTX output reflecting the rollback

---

## Out of Scope (Current Phase)

- Web UI or browser-based interface *(planned for a future phase)*
- Batch processing of multiple files simultaneously *(future)*
- Cloud storage integration *(future)*
- Email notifications or team collaboration workflows *(future)*
- Real-time in-editor plugin *(future)*

---

## Project Phases

| Phase | Status | Description |
|---|---|---|
| Phase 1 — Core Engine | ✅ Prototyped | Triage framework, low-risk autofixes, medium/high pipelines |
| Phase 2 — Audit & Rollback | 🔄 In Progress | Ledger, snapshots, per-item rollback |
| Phase 3 — Interactive Report | 🔄 In Progress | CLI report, approve/reject/rollback flow |
| Phase 4 — Export Reports | 🔜 Next | XLSX itemized report, PDF summary |
| Phase 5 — Beta Testing | 🔜 Planned | Real-world testing with partner institutions |
| Phase 6 — UI Layer | ⏳ Future | Web-based interactive interface |

---

## Setup & Run

This project uses [`uv`](https://docs.astral.sh/uv/) for Python version management, virtual environments, and package installs. Do **not** use `pip`, `pip-tools`, or `python -m venv` directly.

```bash
# 1. Install uv (once per machine)
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS / Linux
# Windows (PowerShell):
# powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Clone the repo
git clone https://github.com/your-org/pptx-accessibility-agent.git
cd pptx-accessibility-agent

# 3. Create virtual environment + install all dependencies
#    uv reads pyproject.toml and pins everything to uv.lock
uv sync

# 4. Activate the environment (optional — uv run handles this automatically)
source .venv/bin/activate      # macOS / Linux
# Windows: .venv\Scripts\activate

# 5. Run the agent on a PPTX file
uv run python cli.py check --input path/to/slides.pptx

# 6. Run with auto-fix (low risk) + interactive report
uv run python cli.py fix --input path/to/slides.pptx --output path/to/fixed.pptx

# 7. Roll back a specific fix item
uv run python cli.py rollback --ledger path/to/ledger.json --item-id fix_20240601_001

# 8. Run tests
uv run pytest tests/ -v

# 9. Add a new dependency
uv add <package-name>

# 10. Add a dev-only dependency
uv add --dev <package-name>
```

> **Lockfile**: `uv.lock` is committed to the repo. All contributors and CI runs use the exact same resolved versions. Never edit `uv.lock` by hand.

---

## Target Users

- Educators and instructional designers producing slide decks
- Government and public-sector communications teams
- Disability services and accessibility offices at universities
- Mission-driven organizations working toward ADA/Section 508 compliance

---

## Social Impact

Inaccessible digital content can deny people with disabilities equal access to information and services. By lowering the cost and complexity of PowerPoint remediation, this tool helps schools, public institutions, and nonprofits make their presentations more inclusive, compliant, and usable — at scale, without expensive third-party services.

---

## Contributing

Contributions welcome. Please open an issue before submitting a PR for new WCAG rules or triage logic changes, as these require review against the compliance reference standards above.

---

## License

MIT License — see `LICENSE` for details.
