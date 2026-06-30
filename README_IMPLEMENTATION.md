# Essential Implementation - PowerPoint Accessibility Agent

This bundle implements the core project described in `README.md` and `From Checking to Fixing.docx`:

- `cli.py` is the entry point.
- `checker/` detects accessibility findings.
- `fixer/` auto-fixes low-risk issues, stages medium-risk suggestions, and flags high-risk issues.
- `audit/` writes the JSON ledger, snapshots fix targets, and rolls back individual items.
- `report/` exports the ledger to XLSX or PDF and provides an interactive approval flow.

## Implemented rules

Low risk, auto-applied:

- missing presentation language metadata
- missing slide title
- generic hyperlink text such as `click here`

Medium risk, pending approval:

- missing image alt text
- weak or filename-like image alt text

High risk, manual flag:

- charts that need meaningful alternatives
- large tables that need structural review
- embedded media that needs captions/transcripts

## Run

```bash
uv sync
uv run python cli.py check --input slides.pptx
uv run python cli.py fix --input slides.pptx --output fixed.pptx --ledger audit/ledger.json
uv run python cli.py report --ledger audit/ledger.json --pptx fixed.pptx --review --output reviewed.pptx
uv run python cli.py rollback --ledger audit/ledger.json --item-id fix_YYYYMMDD_001 --pptx fixed.pptx --output rolled_back.pptx
uv run python cli.py export --ledger audit/ledger.json --format xlsx --output audit_report.xlsx
uv run python cli.py export --ledger audit/ledger.json --format pdf --output summary.pdf
uv run pytest tests -q
```

## Notes

This is a practical core implementation, not a complete legal accessibility certification tool. It creates an auditable remediation workflow and leaves meaning-sensitive fixes to human review, matching the project's human-in-the-loop design.
