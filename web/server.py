"""FastAPI server for the local AccessiSlides web app.

This module is a thin orchestration layer over the existing engine, analogous to
``cli.py``. Every endpoint wraps functions from ``checker``, ``fixer``, ``audit``
and ``report``; no rule or fix logic lives here. The server is single-user and
local: jobs live in memory (see :mod:`web.jobs`), and slide content plus the API
key never leave the machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pptx import Presentation
from pydantic import BaseModel

from audit import ledger
from audit.rollback import ROLLBACK_ALLOWED_STATUSES, _restore_snapshot
from audit.snapshot import load_snapshot
from checker.engine import run_checks_on_presentation
from config import Settings
from fixer.auto_fix import apply_auto_fix
from fixer.flag_manual import record_manual_flag
from fixer.suggest_fix import (
    acknowledge_suggestion,
    approve_suggestion,
    is_applyable,
    record_pending_suggestion,
)
from models import LedgerStatus, RiskLevel
from report.export_pdf import export_ledger_pdf
from report.export_xlsx import export_ledger_xlsx
from utils.logging import get_logger
from web.jobs import Job, JobStore

LOGGER = get_logger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class ApproveBody(BaseModel):
    """Optional replacement text supplied when approving a suggestion."""

    replacement_text: str | None = None


def _build_settings(api_key: str, provider: str) -> Settings:
    """Build settings for one analysis run, enabling the LLM only with a key.

    The API key is used in-memory for this request only and is never written to
    disk. With no key (or an unknown provider) the deterministic pipeline runs.
    """
    normalized = (provider or "").strip().lower()
    if api_key and normalized in {"anthropic", "openai"}:
        overrides: dict[str, Any] = {"llm_enabled": True, "llm_provider": normalized}
        if normalized == "anthropic":
            overrides["anthropic_api_key"] = api_key
        else:
            overrides["openai_api_key"] = api_key
        return Settings(**overrides)
    return Settings(llm_enabled=False)


def _ledger_payload(job: Job) -> dict[str, Any]:
    """Return ledger rows plus per-risk counts for the frontend."""
    rows = ledger.ledger_rows(job.ledger_path)
    counts = {"auto": 0, "pending": 0, "flagged": 0, "other": 0}
    for row in rows:
        status = row.get("status")
        if status == LedgerStatus.AUTO_APPLIED.value:
            counts["auto"] += 1
        elif status == LedgerStatus.PENDING_APPROVAL.value:
            counts["pending"] += 1
        elif status == LedgerStatus.FLAGGED_MANUAL.value:
            counts["flagged"] += 1
        else:
            counts["other"] += 1
    return {"job_id": job.job_id, "filename": job.original_filename, "counts": counts, "items": rows}


def _require_job(store: JobStore, job_id: str) -> Job:
    """Fetch a job or raise 404."""
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}")
    return job


def create_app(store: JobStore | None = None) -> FastAPI:
    """Build the FastAPI application.

    Args:
        store: Job store to use. A fresh temp-backed store is created by default;
            tests pass their own so artifacts land under ``tmp_path``.
    """
    app = FastAPI(title="AccessiSlides", docs_url=None, redoc_url=None)
    resolved_store = store
    app.state.job_store = resolved_store

    def job_store_ref() -> JobStore:
        """Return the store, creating a temp-backed one on first use.

        Creation is deferred out of import time (no file I/O on import); tests
        inject their own store so nothing lands outside ``tmp_path``.
        """
        nonlocal resolved_store
        if resolved_store is None:
            resolved_store = JobStore.create()
            app.state.job_store = resolved_store
        return resolved_store

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        """Serve the single-page frontend."""
        return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))

    @app.post("/api/analyze")
    async def analyze(
        file: UploadFile = File(...),
        api_key: str = Form(""),
        provider: str = Form("anthropic"),
        reviewer: str = Form("reviewer"),
    ) -> JSONResponse:
        """Check and remediate an uploaded ``.pptx``, returning the ledger.

        Low-risk issues are auto-fixed, medium-risk staged for approval, and
        high-risk flagged. Mirrors the fix loop in ``cli.py``.
        """
        filename = file.filename or "presentation.pptx"
        if not filename.lower().endswith(".pptx"):
            raise HTTPException(status_code=400, detail="Please upload a .pptx file.")

        settings = _build_settings(api_key, provider)
        job = job_store_ref().new_job(original_filename=filename, reviewer=reviewer or "reviewer")
        job.input_path.write_bytes(await file.read())

        try:
            prs = Presentation(job.input_path)
        except Exception as exc:  # corrupt/unreadable upload
            job_store_ref().remove(job.job_id)
            raise HTTPException(status_code=400, detail=f"Could not read presentation: {exc}") from exc

        llm_provider = None
        if settings.llm_enabled:
            from llm.factory import get_provider

            llm_provider = get_provider(settings)

        findings = run_checks_on_presentation(prs, settings, provider=llm_provider)
        for finding in findings:
            if finding.risk_level == RiskLevel.LOW:
                apply_auto_fix(prs, finding, job.ledger_path, settings, provider=llm_provider)
            elif finding.risk_level == RiskLevel.MEDIUM:
                record_pending_suggestion(finding, job.ledger_path, prs=prs, provider=llm_provider)
            else:
                record_manual_flag(finding, job.ledger_path, prs=prs, provider=llm_provider)

        job.prs = prs
        job.save()
        payload = _ledger_payload(job)
        payload["llm_active"] = llm_provider is not None
        return JSONResponse(payload)

    @app.get("/api/jobs/{job_id}/ledger")
    def get_ledger(job_id: str) -> JSONResponse:
        """Return the current ledger for a job."""
        return JSONResponse(_ledger_payload(_require_job(job_store_ref(), job_id)))

    @app.post("/api/jobs/{job_id}/items/{item_id}/approve")
    def approve(job_id: str, item_id: str, body: ApproveBody | None = None) -> JSONResponse:
        """Approve a pending suggestion, applying its edit when applicable."""
        job = _require_job(job_store_ref(), job_id)
        entry = _find_or_404(job, item_id)
        replacement = body.replacement_text if body else None
        try:
            if is_applyable(entry.rule_id):
                approve_suggestion(
                    prs=job.prs,
                    ledger_path=job.ledger_path,
                    item_id=item_id,
                    approved_by=job.reviewer,
                    replacement_text=replacement,
                )
            else:
                acknowledge_suggestion(job.ledger_path, item_id, approved_by=job.reviewer)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        job.save()
        return JSONResponse(_ledger_payload(job))

    @app.post("/api/jobs/{job_id}/items/{item_id}/reject")
    def reject(job_id: str, item_id: str) -> JSONResponse:
        """Reject a pending suggestion (ledger only; no PPTX change)."""
        job = _require_job(job_store_ref(), job_id)
        _find_or_404(job, item_id)
        from fixer.suggest_fix import reject_suggestion

        try:
            reject_suggestion(job.ledger_path, item_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return JSONResponse(_ledger_payload(job))

    @app.post("/api/jobs/{job_id}/items/{item_id}/keep")
    def keep_auto(job_id: str, item_id: str) -> JSONResponse:
        """Confirm an LLM auto-applied low-risk fix flagged for review.

        Mirrors the "keep" branch of ``report.interactive.review_pending_suggestions``.
        """
        job = _require_job(job_store_ref(), job_id)
        entry = _find_or_404(job, item_id)
        metadata = {**entry.metadata}
        metadata.pop("needs_review", None)
        ledger.update_entry(
            job.ledger_path, item_id, approved_by=f"human:{job.reviewer}", metadata=metadata
        )
        return JSONResponse(_ledger_payload(job))

    @app.post("/api/jobs/{job_id}/items/{item_id}/rollback")
    def rollback(job_id: str, item_id: str) -> JSONResponse:
        """Roll back an applied fix by restoring its snapshot on the live PPTX.

        This replicates ``audit.rollback.rollback_item`` against the in-memory
        presentation so the live object and the saved file never diverge (the
        disk-based helper would reload from a stale file).
        """
        job = _require_job(job_store_ref(), job_id)
        entry = _find_or_404(job, item_id)
        if entry.status not in ROLLBACK_ALLOWED_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"Item {item_id} cannot be rolled back from status {entry.status.value}",
            )
        if not entry.snapshot_path:
            raise HTTPException(status_code=409, detail=f"Item {item_id} has no snapshot")
        _restore_snapshot(job.prs, load_snapshot(Path(entry.snapshot_path)))
        ledger.update_entry(
            job.ledger_path,
            item_id,
            status=LedgerStatus.ROLLED_BACK,
            rolled_back_at=ledger.utc_now(),
        )
        job.save()
        return JSONResponse(_ledger_payload(job))

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str) -> FileResponse:
        """Download the current fixed/reviewed presentation."""
        job = _require_job(job_store_ref(), job_id)
        job.save()
        return FileResponse(
            job.output_path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=_output_name(job, suffix="_accessible", ext=".pptx"),
        )

    @app.get("/api/jobs/{job_id}/export")
    def export(job_id: str, format: str) -> FileResponse:
        """Export the audit ledger as an XLSX or PDF report."""
        job = _require_job(job_store_ref(), job_id)
        if format == "xlsx":
            out = export_ledger_xlsx(job.ledger_path, job.work_dir / "audit_report.xlsx")
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            name = _output_name(job, suffix="_audit", ext=".xlsx")
        elif format == "pdf":
            out = export_ledger_pdf(job.ledger_path, job.work_dir / "summary.pdf")
            media = "application/pdf"
            name = _output_name(job, suffix="_summary", ext=".pdf")
        else:
            raise HTTPException(status_code=400, detail="format must be 'xlsx' or 'pdf'")
        return FileResponse(out, media_type=media, filename=name)

    return app


def _find_or_404(job: Job, item_id: str):
    """Return the ledger entry for ``item_id`` in a job or raise 404."""
    try:
        return ledger.find_entry(job.ledger_path, item_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _output_name(job: Job, *, suffix: str, ext: str) -> str:
    """Build a friendly download filename from the original upload name."""
    return f"{Path(job.original_filename).stem}{suffix}{ext}"


app = create_app()
