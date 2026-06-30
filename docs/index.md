# AccessiSlides

> **From checking to fixing.** A human-in-the-loop CLI that detects accessibility
> issues in PowerPoint (`.pptx`) files, **auto-fixes** what is safe, **suggests**
> fixes that need context, and **flags** what needs human judgment — every change
> recorded in an append-only audit ledger and reversible per item.

Grounded in **[WCAG 2.1](https://www.w3.org/TR/WCAG21/)** and
**[Section 508](https://www.section508.gov/create/presentations/)**.

---

## Contents

- [Why this exists](#why-this-exists)
- [How it works](#how-it-works)
- [Feature overview](#feature-overview)
- [Install](#install)
- [Quick start](#quick-start)
- [Commands](#commands)
- [The audit ledger](#the-audit-ledger)
- [Optional: AI-assisted mode (OpenAI or Claude)](#optional-ai-assisted-mode-openai-or-claude)
- [What it checks today](#what-it-checks-today)
- [FAQ](#faq)

---

## Why this exists

PowerPoint is everywhere in teaching, training, and public communication, yet
accessible slides remain inconsistent and labor-intensive. Built-in checkers find
*most* issues but explicitly not all, and paid remediation can run \$7+ per page —
out of reach for schools and public institutions facing
[ADA Title II deadlines](https://www.ada.gov/resources/2024-03-08-web-rule/)
(April 2026 / April 2027).

AccessiSlides closes that gap: it fixes what it can prove is safe, proposes fixes a
human approves, flags the rest, and keeps a complete, reversible record of every
decision.

---

## How it works

```
slides.pptx
    │
    ▼
┌─────────────┐   detect issues (deterministic rules; optional LLM pass)
│   CHECK     │
└─────────────┘
    │  each issue is classified by risk
    ▼
┌──────────────────────── TRIAGE ────────────────────────┐
│  LOW            │  MEDIUM             │  HIGH            │
│  auto-fix now   │  suggest → approve  │  flag for human  │
└─────────────────┴─────────────────────┴─────────────────┘
    │                    │                      │
    ▼                    ▼                      ▼
 edits PPTX      staged in ledger        no edit; described
 + snapshot      pending approval        with WCAG guidance
    │                    │                      │
    └──────────── append-only ledger ───────────┘
                         │
            review · export (XLSX / PDF) · rollback
```

The deterministic rule engine is the authoritative source of findings. Every issue
— fixed or not — produces exactly one ledger entry, and every applied fix writes a
before-state snapshot so it can be rolled back individually, in any order.

---

## Feature overview

| Feature | What it does |
|---|---|
| **Risk triage** | Classifies each issue **low / medium / high** before any action is taken. |
| **Auto-fix (low risk)** | Deterministic, no-judgment fixes applied automatically and logged. |
| **Suggest + approve (medium risk)** | Generates a proposed fix; a human approves, edits, or rejects it. |
| **Flag (high risk)** | Describes the issue with WCAG/508 guidance; no automated edit. |
| **Interactive review** | CLI flow to approve / edit / reject staged fixes and keep/reject AI auto-fixes. |
| **Audit ledger** | Append-only JSON record, one entry per issue, with full status history. |
| **Per-item rollback** | Restore any applied fix from its snapshot without touching the others. |
| **Reports** | Export the ledger to **XLSX** (one row per issue) or a **PDF** summary. |
| **Optional AI mode** | Pluggable **OpenAI** or **Claude** layer for richer suggestions + a semantic detection pass. Off by default. |

---

## Install

AccessiSlides uses **[`uv`](https://docs.astral.sh/uv/)** for Python (3.11+),
environments, and packages — not `pip` or `venv` directly.

```bash
# 1. Install uv (once per machine)
curl -LsSf https://astral.sh/uv/install.sh | sh        # macOS / Linux
# Windows (PowerShell): powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Clone and enter the project
git clone https://github.com/your-org/AccessiSlides.git
cd AccessiSlides/development

# 3. Create the environment and install dependencies
uv sync

# (optional) include the AI providers for AI-assisted mode
uv sync --extra llm
```

`uv run <command>` activates the environment automatically — no manual `activate`
needed. The lockfile `uv.lock` is committed; never edit it by hand.

---

## Quick start

```bash
# Inspect a file — report only, no edits
uv run python cli.py check --input slides.pptx

# Remediate: auto-fix low-risk, stage medium-risk, flag high-risk
uv run python cli.py fix --input slides.pptx --output fixed.pptx --ledger audit/ledger.json

# Review staged suggestions interactively (approve / edit / reject)
uv run python cli.py report --ledger audit/ledger.json --pptx fixed.pptx --review --output reviewed.pptx

# Export an audit report
uv run python cli.py export --ledger audit/ledger.json --format xlsx --output audit_report.xlsx
```

---

## Commands

### `check` — detect only (no edits)

```bash
uv run python cli.py check --input slides.pptx [--json-output findings.json]
```

| Option | Description |
|---|---|
| `--input` | Path to the `.pptx` to inspect. *(required)* |
| `--json-output` | Also write findings to a JSON file. |

### `fix` — remediate and stage

```bash
uv run python cli.py fix --input slides.pptx --output fixed.pptx [--ledger audit/ledger.json] [--reset-ledger]
```

| Option | Description |
|---|---|
| `--input` | Source `.pptx`. *(required)* |
| `--output` | Destination for the fixed `.pptx`. *(required)* |
| `--ledger` | Ledger path (defaults to `<output>.ledger.json`). |
| `--reset-ledger` | Delete an existing ledger before this run. |

Prints a summary: `Auto-applied: N; pending approval: N; flagged manual: N`.

### `report` — view and review

```bash
uv run python cli.py report --ledger audit/ledger.json \
    [--pptx fixed.pptx] [--review] [--output reviewed.pptx] [--reviewer "Your Name"]
```

| Option | Description |
|---|---|
| `--ledger` | Ledger to summarize. *(required)* |
| `--pptx` | The PPTX to edit when reviewing. *(required with `--review`)* |
| `--review` | Interactively approve / edit / reject staged items. |
| `--output` | Where to save the reviewed PPTX. |
| `--reviewer` | Name recorded as the approver in the ledger. |

### `rollback` — undo one fix

```bash
uv run python cli.py rollback --ledger audit/ledger.json \
    --item-id fix_20240601_001 --pptx fixed.pptx --output rolled_back.pptx
```

Restores the element from its snapshot, writes a new PPTX (never overwriting the
prior clean state), and marks the ledger entry `rolled_back`.

### `export` — XLSX or PDF report

```bash
uv run python cli.py export --ledger audit/ledger.json --format xlsx --output audit_report.xlsx
uv run python cli.py export --ledger audit/ledger.json --format pdf  --output summary.pdf
```

---

## The audit ledger

Every issue produces exactly one append-only entry. Only lifecycle fields
(`status`, `applied_at`, `approved_by`, `rolled_back_at`, `snapshot_path`,
`suggested_fix`, `metadata`) are ever updated — the rest is immutable.

```json
{
  "item_id": "fix_20240601_001",
  "slide_number": 3,
  "element_type": "image",
  "wcag_criterion": "1.1.1 Non-text Content",
  "section_508_ref": "E205.4",
  "risk_level": "medium",
  "issue_description": "Image has no alt text",
  "suggested_fix": "Bar chart of Q3 revenue by region",
  "status": "pending_approval",
  "applied_at": null,
  "approved_by": null,
  "rolled_back_at": null,
  "snapshot_path": "audit/snapshots/fix_20240601_001.json"
}
```

Statuses: `auto_applied`, `pending_approval`, `approved`, `rejected`,
`flagged_manual`, `rolled_back`.

---

## Optional: AI-assisted mode (OpenAI or Claude)

AccessiSlides runs fully deterministically by default — **no API key required**.
Enabling AI mode adds an optional, pluggable layer that improves *suggestions* and
adds a *semantic detection pass*, while the deterministic rules and the audit
ledger remain the authoritative system. If a key, package, or the network is
missing, it silently falls back to deterministic behavior.

**Enable it** (install the extra, then set environment variables — `.env` is read
automatically):

```bash
uv sync --extra llm

export PPTXA_LLM_ENABLED=true
export PPTXA_LLM_PROVIDER=openai          # or "anthropic"
export PPTXA_OPENAI_API_KEY=sk-...        # or PPTXA_ANTHROPIC_API_KEY=sk-ant-...

uv run python cli.py fix --input slides.pptx --output fixed.pptx --ledger audit/ledger.json
```

| Variable | Default | Purpose |
|---|---|---|
| `PPTXA_LLM_ENABLED` | `false` | Master switch for suggestions **and** detection. |
| `PPTXA_LLM_PROVIDER` | `openai` | `openai` or `anthropic`. |
| `PPTXA_OPENAI_API_KEY` | — | Key for the OpenAI provider. |
| `PPTXA_ANTHROPIC_API_KEY` | — | Key for the Claude provider. |
| `PPTXA_OPENAI_MODEL` | `gpt-4o-mini` | Vision-capable OpenAI model. |
| `PPTXA_ANTHROPIC_MODEL` | `claude-opus-4-8` | Vision-capable Claude model. |
| `PPTXA_LLM_TIMEOUT_SECONDS` | `30` | Per-request timeout. |
| `PPTXA_LLM_MAX_OUTPUT_TOKENS` | `300` | Max tokens generated per call. |

**What AI mode changes:**

- **Alt text (medium):** generated from the actual image plus surrounding slide
  text, instead of a template — still staged for human approval.
- **Links & titles (low):** richer, context-aware text is auto-applied and
  **flagged for review** so you can keep or reject it in the `report --review` flow.
- **High-risk objects:** a long-description **draft** is attached to the ledger
  entry for a human to refine; the PPTX is never edited automatically.
- **Detection pass:** an additive review surfaces issues rules can't express
  (vague titles, ambiguous wording), tagged with provider provenance.

> Provenance is recorded in each ledger entry's `metadata` (`detected_by` /
> `suggestion_source`), so AI-originated findings and suggestions are always
> distinguishable from deterministic ones.

---

## What it checks today

**Low risk — auto-applied**
- Missing presentation language metadata
- Missing slide title
- Generic hyperlink text (e.g. "click here")

**Medium risk — suggested, pending approval**
- Missing image alt text
- Weak / filename-like image alt text
- *(AI mode)* semantic review findings

**High risk — flagged for manual remediation**
- Charts / data graphics needing a meaningful alternative
- Large tables needing structural review
- Embedded media needing captions or a transcript

---

## FAQ

**Does it change my file in place?**
No. `fix` writes a new output file; `rollback` writes another new file. Your
original is never modified.

**Do I need an API key?**
No. The default deterministic mode requires no keys and makes no network calls.
AI-assisted mode is entirely optional.

**Can I undo a fix?**
Yes — any applied fix is reversible per item via `rollback`, in any order, from its
snapshot.

**Is this a legal accessibility certification?**
No. It is a practical, auditable remediation workflow that leaves meaning-sensitive
fixes to human review by design.

---

<sub>WCAG 2.1 · Section 508 E205.4 · Built with Python, <code>python-pptx</code>, and
<code>uv</code>. Licensed under MIT.</sub>
