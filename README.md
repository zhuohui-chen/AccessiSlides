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
| CLI interface | `click` |
| Local web app | `FastAPI` + `uvicorn` (single static page, no build step) |
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

- Hosted / multi-user web service, accounts, or authentication *(future)* — the
  included web app is **local and single-user** (see "Run the app" above)
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

## Installation

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

# 4. (Optional) Activate the environment.
#    You do NOT need this if you always use `uv run` — uv activates the env for you.
source .venv/bin/activate      # macOS / Linux
# Windows: .venv\Scripts\activate
```

> **Lockfile**: `uv.lock` is committed to the repo. All contributors and CI runs use the exact same resolved versions. Never edit `uv.lock` by hand.

The tool runs fully offline by default. The optional LLM layer (smarter alt-text and
suggestion drafting) requires extra packages and an API key — see **Configuration** below.

---

## Configuration

All configuration is optional. Settings are read from environment variables or a `.env`
file in the project root, using the `pydantic-settings` model in `config.py`. **Every
setting uses the `PPTXA_` prefix.**

### Create a `.env` file

Create a file named `.env` in the project root (it is git-ignored — never commit API keys):

```dotenv
# .env — all keys are optional; shown with their defaults

# --- General behavior ---
PPTXA_DEFAULT_LANGUAGE=en-US          # language metadata injected when missing
PPTXA_DEFAULT_LEDGER_NAME=ledger.json # default ledger filename
PPTXA_SNAPSHOT_DIR_NAME=snapshots     # snapshot subdirectory name
PPTXA_AUTO_TITLE_PREFIX=Slide         # prefix for auto-generated slide titles

# --- Optional LLM layer (OFF by default) ---
PPTXA_LLM_ENABLED=false               # set true to turn on AI-assisted suggestions
PPTXA_LLM_PROVIDER=openai             # "openai" or "anthropic"

# Provide a key only for the provider you select:
PPTXA_OPENAI_API_KEY=sk-...           # required if provider = openai
PPTXA_ANTHROPIC_API_KEY=sk-ant-...    # required if provider = anthropic

PPTXA_OPENAI_MODEL=gpt-4o-mini        # model used for the openai provider
PPTXA_ANTHROPIC_MODEL=claude-opus-4-8 # model used for the anthropic provider
PPTXA_LLM_TIMEOUT_SECONDS=30          # per-request timeout
PPTXA_LLM_MAX_OUTPUT_TOKENS=300       # cap on generated suggestion length
```

You can also export any of these as shell environment variables instead of using `.env`;
environment variables take precedence.

### Enabling the optional LLM layer

The LLM layer is **off by default** — the tool works fully with deterministic rules and
template-based suggestions and needs no API key. Turn it on for higher-quality alt-text and
fix drafting:

```bash
# 1. Install the optional LLM SDKs (anthropic + openai)
uv sync --extra llm

# 2. In .env, enable the layer and supply a key for your chosen provider
#    PPTXA_LLM_ENABLED=true
#    PPTXA_LLM_PROVIDER=anthropic
#    PPTXA_ANTHROPIC_API_KEY=sk-ant-...
```

**The LLM layer fails safe.** If it is disabled, the SDK is not installed, the provider name
is unknown, or the API key is missing, the tool logs a warning and silently falls back to the
deterministic pipeline — a misconfiguration can never break a run. When active, `fix` prints
`LLM mode active: <provider>`; when it falls back it prints
`LLM enabled but unavailable; using deterministic fixes only.`

> **Get an API key:** OpenAI → https://platform.openai.com/api-keys ·
> Anthropic → https://console.anthropic.com/

---

## Run the app (no terminal)

For non-technical users, AccessiSlides ships a **local web app** — no commands to memorize:

1. **Double-click the launcher** in this folder:
   - macOS: `Start-AccessiSlides.command`
   - Windows: `Start-AccessiSlides.bat`

   (Or run `uv run python cli.py serve` yourself.) Your browser opens to
   `http://127.0.0.1:8765`.
2. **(Optional) Open Settings** and paste an API key to enable AI-written suggestions.
   The key is held in memory for the session only — never written to disk.
3. **Drag a `.pptx`** onto the page (or click to browse). Low-risk issues are fixed
   automatically, suggestions are staged for your **Approve / Edit / Reject** review,
   and complex items are flagged for you.
4. **Download the fixed `.pptx`**, and optionally export the XLSX audit or PDF summary.

Everything runs on your computer — your slides and API key never leave the machine.
The app is a thin wrapper over the same engine the CLI uses (`web/` → `cli.py` logic).

---

## Usage (CLI)

All commands are run through `cli.py`. Use `uv run` so the right environment is always used,
and pass `-h` / `--help` to any command for its full option list.

### `check` — detect issues, make no edits

```bash
uv run python cli.py check --input slides.pptx

# Also write the findings to JSON:
uv run python cli.py check --input slides.pptx --json-output findings.json
```

### `fix` — auto-fix low risk, stage medium, flag high

```bash
uv run python cli.py fix \
  --input slides.pptx \
  --output fixed.pptx \
  --ledger audit/ledger.json     # optional; defaults to <output>.ledger.json

# Start a clean ledger for this run:
uv run python cli.py fix --input slides.pptx --output fixed.pptx --reset-ledger
```

This writes the remediated deck to `--output`, records every issue in the ledger, and prints a
summary like `Auto-applied: 4; pending approval: 3; flagged manual: 2`. Medium-risk items are
staged as `pending_approval` and applied **only** after you approve them in the review step below.

### `report` — view the ledger and run human review

```bash
# Read-only summary of everything in the ledger:
uv run python cli.py report --ledger audit/ledger.json

# Interactive human-in-the-loop review (approve / edit / reject):
uv run python cli.py report \
  --ledger audit/ledger.json \
  --pptx fixed.pptx \
  --review \
  --reviewer "Jane Doe" \
  --output reviewed.pptx        # optional; defaults to <pptx>_reviewed.pptx
```

### `rollback` — undo a single applied fix

```bash
uv run python cli.py rollback \
  --ledger audit/ledger.json \
  --item-id fix_20240601_001 \
  --pptx fixed.pptx \
  --output rolled_back.pptx
```

### `export` — produce an audit report

```bash
uv run python cli.py export --ledger audit/ledger.json --format xlsx --output audit_report.xlsx
uv run python cli.py export --ledger audit/ledger.json --format pdf  --output summary.pdf
```

### `serve` — launch the local web app

Starts the browser UI (see **Run the app** above) — the graphical, no-terminal way to run
the whole check → approve → download flow. Handy for non-technical users.

```bash
uv run python cli.py serve                       # opens http://127.0.0.1:8765
uv run python cli.py serve --port 9000            # use a different port
uv run python cli.py serve --no-browser           # start the server without opening a browser
```

The server is **local and single-user**: it binds to `127.0.0.1`, keeps each upload in a
temporary work directory, and holds the API key in memory only. It never writes your slides
or key outside that temp directory, and makes no request except (optionally) to your chosen
AI provider.

### A typical end-to-end run

```bash
uv run python cli.py check  --input slides.pptx
uv run python cli.py fix    --input slides.pptx --output fixed.pptx --ledger audit/ledger.json
uv run python cli.py report --ledger audit/ledger.json --pptx fixed.pptx --review --output reviewed.pptx
uv run python cli.py export --ledger audit/ledger.json --format pdf --output summary.pdf
```

---

## Human-in-the-Loop Review (Approve / Edit / Reject)

Medium-risk fixes are never applied silently — they wait in the ledger as `pending_approval`
until a human dispositions them. Running `report --review` walks you through two groups:

**1. Medium-risk pending suggestions.** For each item you see the issue and the proposed fix
text, then choose an action at the prompt `Action [approve/edit/reject/skip]`:

| Action | What happens |
|---|---|
| `approve` | The suggested fix is applied to the PPTX and the ledger entry becomes `approved`. |
| `edit`    | You are prompted: `Enter replacement text`. **Type your own wording**, press Enter, and *your* text (not the suggestion) is applied and logged as `approved`. This is how you supply a human-authored alt text or title. |
| `reject`  | No change is made; the entry is logged as `rejected`. |
| `skip`    | Leave the item untouched and `pending_approval` for a later pass (this is the default if you just press Enter). |

**2. LLM auto-applied low-risk items flagged for review.** When the LLM layer drafted a
low-risk fix, it is applied immediately but flagged for a human to confirm. The prompt is
`Action [keep/reject/skip]`: `keep` confirms it (records `human:<reviewer>` as approver),
`reject` rolls it back from its snapshot, and `skip` leaves it flagged.

Every edited or approved item is written into a single reviewed PPTX at `--output`, and the
`--reviewer` name is recorded in the ledger's `approved_by` field for the audit trail. Because
each fix has its own before/after snapshot, anything you approve can still be undone later with
`rollback`.

---

## Development

```bash
# Run the test suite
uv run pytest tests/ -v
uv run pytest tests/ -v --cov=. --cov-report=term-missing   # with coverage

# Manage dependencies (keeps uv.lock in sync — never edit pyproject.toml by hand)
uv add <package-name>          # runtime dependency
uv add --dev <package-name>    # dev-only dependency
uv sync --extra llm            # install the optional LLM SDKs
```

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
