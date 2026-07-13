"""Command-line entry point for the PowerPoint Accessibility Agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import click
from pptx import Presentation

from audit import ledger
from audit.rollback import rollback_item
from checker.engine import run_checks_on_presentation
from config import Settings
from fixer.auto_fix import apply_auto_fix
from fixer.flag_manual import record_manual_flag
from fixer.suggest_fix import record_pending_suggestion
from models import Finding, RiskLevel
from report.export_pdf import export_ledger_pdf
from report.export_xlsx import export_ledger_xlsx
from report.interactive import review_pending_suggestions, show_ledger_summary


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Check, fix, report, and roll back PowerPoint accessibility issues."""


@cli.command("check")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--json-output", "json_output", type=click.Path(dir_okay=False, path_type=Path))
def check_command(input_path: Path, json_output: Path | None) -> None:
    """Check a PPTX without editing it."""
    settings = Settings()
    prs = Presentation(input_path)
    findings = run_checks_on_presentation(prs, settings)
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(
            json.dumps([finding.to_dict() for finding in findings], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    _print_findings(findings)
    if not findings:
        click.echo("No accessibility issues found by configured rules.")


@cli.command("fix")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output", "output_path", required=True, type=click.Path(dir_okay=False, path_type=Path))
@click.option("--ledger", "ledger_path", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--reset-ledger", is_flag=True, help="Delete the existing ledger before this run.")
def fix_command(input_path: Path, output_path: Path, ledger_path: Path | None, reset_ledger: bool) -> None:
    """Auto-fix low-risk issues and stage medium/high-risk items."""
    settings = Settings()
    resolved_ledger = ledger_path or output_path.with_suffix(".ledger.json")
    if reset_ledger and resolved_ledger.exists():
        resolved_ledger.unlink()

    provider = None
    if settings.llm_enabled:
        from llm.factory import get_provider

        provider = get_provider(settings)
        if provider is not None:
            click.echo(f"LLM mode active: {provider.name}")
        else:
            click.echo("LLM enabled but unavailable; using deterministic fixes only.")

    prs = Presentation(input_path)
    findings = run_checks_on_presentation(prs, settings, provider=provider)
    applied = 0
    pending = 0
    flagged = 0

    for finding in findings:
        if finding.risk_level == RiskLevel.LOW:
            if apply_auto_fix(prs, finding, resolved_ledger, settings, provider=provider) is not None:
                applied += 1
        elif finding.risk_level == RiskLevel.MEDIUM:
            record_pending_suggestion(finding, resolved_ledger, prs=prs, provider=provider)
            pending += 1
        else:
            record_manual_flag(finding, resolved_ledger, prs=prs, provider=provider)
            flagged += 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(output_path)
    click.echo(f"Saved fixed PPTX: {output_path}")
    click.echo(f"Ledger: {resolved_ledger}")
    click.echo(f"Auto-applied: {applied}; pending approval: {pending}; flagged manual: {flagged}")


@cli.command("report")
@click.option("--ledger", "ledger_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--pptx", "pptx_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output", "output_path", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--review", is_flag=True, help="Interactively approve, edit, or reject pending suggestions.")
@click.option("--reviewer", default="reviewer", show_default=True)
def report_command(ledger_path: Path, pptx_path: Path | None, output_path: Path | None, review: bool, reviewer: str) -> None:
    """Show the ledger and optionally run human approval review."""
    show_ledger_summary(ledger_path)
    if not review:
        return
    if pptx_path is None:
        raise click.UsageError("--pptx is required when --review is used")
    resolved_output = output_path or pptx_path.with_name(f"{pptx_path.stem}_reviewed{pptx_path.suffix}")
    result = review_pending_suggestions(
        pptx_path=pptx_path,
        output_path=resolved_output,
        ledger_path=ledger_path,
        reviewer=reviewer,
    )
    click.echo(f"Saved reviewed PPTX: {result}")


@cli.command("rollback")
@click.option("--ledger", "ledger_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--item-id", required=True)
@click.option("--pptx", "pptx_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--output", "output_path", required=True, type=click.Path(dir_okay=False, path_type=Path))
def rollback_command(ledger_path: Path, item_id: str, pptx_path: Path, output_path: Path) -> None:
    """Roll back one applied fix by ledger item ID."""
    result = rollback_item(pptx_path=pptx_path, output_path=output_path, ledger_path=ledger_path, item_id=item_id)
    click.echo(f"Saved rollback PPTX: {result}")


@cli.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind (local only by default).")
@click.option("--port", default=8765, show_default=True, type=int)
@click.option("--no-browser", is_flag=True, help="Do not open a browser automatically.")
def serve_command(host: str, port: int, no_browser: bool) -> None:
    """Launch the local web app (drag-drop, approve, download in the browser)."""
    import uvicorn

    url = f"http://{host}:{port}"
    click.echo(f"AccessiSlides is running at {url}")
    click.echo("Leave this window open. Press Ctrl+C to stop.")
    if not no_browser:
        import threading
        import webbrowser

        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run("web.server:app", host=host, port=port, log_level="warning")


@cli.command("export")
@click.option("--ledger", "ledger_path", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--format", "export_format", required=True, type=click.Choice(["xlsx", "pdf"]))
@click.option("--output", "output_path", required=True, type=click.Path(dir_okay=False, path_type=Path))
def export_command(ledger_path: Path, export_format: str, output_path: Path) -> None:
    """Export the accessibility ledger to XLSX or PDF."""
    if export_format == "xlsx":
        result = export_ledger_xlsx(ledger_path, output_path)
    else:
        result = export_ledger_pdf(ledger_path, output_path)
    click.echo(f"Saved {export_format.upper()} report: {result}")


def _print_findings(findings: Iterable[Finding]) -> None:
    """Print checker findings in a compact human-readable form."""
    for finding in findings:
        click.echo(
            f"slide {finding.slide_number} | {finding.risk_level.value} | "
            f"{finding.rule_id} | {finding.issue_description}"
        )
        if finding.suggested_fix:
            click.echo(f"  suggested: {finding.suggested_fix}")


if __name__ == "__main__":
    cli()
