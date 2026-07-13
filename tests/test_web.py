"""End-to-end tests for the local web app via FastAPI's TestClient."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.util import Inches

from web.jobs import JobStore
from web.server import create_app

ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p94AAAAASUVORK5CYII="


def _build_deck(tmp_path: Path) -> Path:
    """Create a deck with low-risk (link/title/language) and medium-risk (alt-text) issues."""
    image_path = tmp_path / "image001.png"
    image_path.write_bytes(base64.b64decode(ONE_PIXEL_PNG))
    pptx_path = tmp_path / "deck.pptx"

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    run = box.text_frame.paragraphs[0].add_run()
    run.text = "click here"
    run.hyperlink.address = "https://example.com/resource"
    slide.shapes.add_picture(str(image_path), Inches(1), Inches(3), width=Inches(1))
    prs.save(pptx_path)
    return pptx_path


def _client(tmp_path: Path) -> TestClient:
    app = create_app(store=JobStore.create(tmp_path / "jobs"))
    return TestClient(app)


def _analyze(client: TestClient, pptx_path: Path) -> dict:
    with pptx_path.open("rb") as handle:
        res = client.post(
            "/api/analyze",
            files={"file": ("deck.pptx", handle, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            data={"api_key": "", "provider": "anthropic", "reviewer": "tester"},
        )
    assert res.status_code == 200, res.text
    return res.json()


def test_index_served(tmp_path: Path) -> None:
    """The root serves the single-page app."""
    res = _client(tmp_path).get("/")
    assert res.status_code == 200
    assert "AccessiSlides" in res.text


def test_analyze_returns_job_and_ledger(tmp_path: Path) -> None:
    """Analyze auto-fixes low-risk items and stages medium-risk ones."""
    client = _client(tmp_path)
    data = _analyze(client, _build_deck(tmp_path))
    assert data["job_id"]
    assert data["llm_active"] is False
    assert data["counts"]["auto"] >= 1
    assert data["counts"]["pending"] >= 1
    statuses = {item["status"] for item in data["items"]}
    assert "auto_applied" in statuses
    assert "pending_approval" in statuses


def test_approve_and_reject_transitions(tmp_path: Path) -> None:
    """A pending suggestion can be approved; another can be rejected."""
    client = _client(tmp_path)
    data = _analyze(client, _build_deck(tmp_path))
    job_id = data["job_id"]
    pending = [it["item_id"] for it in data["items"] if it["status"] == "pending_approval"]
    assert pending

    approved = client.post(f"/api/jobs/{job_id}/items/{pending[0]}/approve").json()
    target = next(it for it in approved["items"] if it["item_id"] == pending[0])
    assert target["status"] == "approved"
    assert target["approved_by"] == "human:tester"

    rejected = client.post(f"/api/jobs/{job_id}/items/{pending[0]}/reject")
    # already approved → cannot reject
    assert rejected.status_code == 409


def test_rollback_auto_applied(tmp_path: Path) -> None:
    """An auto-applied low-risk fix can be rolled back."""
    client = _client(tmp_path)
    data = _analyze(client, _build_deck(tmp_path))
    job_id = data["job_id"]
    auto_item = next(it["item_id"] for it in data["items"] if it["status"] == "auto_applied")
    rolled = client.post(f"/api/jobs/{job_id}/items/{auto_item}/rollback").json()
    target = next(it for it in rolled["items"] if it["item_id"] == auto_item)
    assert target["status"] == "rolled_back"


def test_download_returns_valid_pptx(tmp_path: Path) -> None:
    """The download endpoint returns an openable presentation."""
    client = _client(tmp_path)
    data = _analyze(client, _build_deck(tmp_path))
    res = client.get(f"/api/jobs/{data['job_id']}/download")
    assert res.status_code == 200
    prs = Presentation(io.BytesIO(res.content))
    assert len(prs.slides) == 1


def test_export_xlsx_and_pdf(tmp_path: Path) -> None:
    """Audit reports export in both formats."""
    client = _client(tmp_path)
    job_id = _analyze(client, _build_deck(tmp_path))["job_id"]
    xlsx = client.get(f"/api/jobs/{job_id}/export", params={"format": "xlsx"})
    pdf = client.get(f"/api/jobs/{job_id}/export", params={"format": "pdf"})
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_unknown_job_is_404(tmp_path: Path) -> None:
    """Operations on an unknown job return 404."""
    res = _client(tmp_path).get("/api/jobs/nope/ledger")
    assert res.status_code == 404
