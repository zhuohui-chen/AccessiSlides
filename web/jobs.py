"""In-memory job store for the local web app.

Each uploaded presentation becomes one :class:`Job` with its own temporary work
directory holding the fixed ``.pptx``, the JSON ledger, and per-item snapshots —
exactly the layout the CLI produces. The loaded ``python-pptx`` presentation is
held in memory so interactive approvals mutate a single object; the output file
is re-saved after every mutation. The store is process-local and single-user: no
database, no auth. Nothing here is written outside the work directory, so slide
content and the API key never leak elsewhere.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any


@dataclass(slots=True)
class Job:
    """One analysis session for a single uploaded presentation.

    Attributes:
        job_id: Opaque identifier used in URLs.
        work_dir: Temporary directory holding all artifacts for this job.
        input_path: The originally uploaded presentation.
        output_path: The current fixed/reviewed presentation on disk.
        ledger_path: JSON ledger for this job.
        prs: The live ``python-pptx`` presentation kept in memory.
        reviewer: Name recorded as the human approver in the ledger.
        original_filename: The upload's filename, used for the download name.
    """

    job_id: str
    work_dir: Path
    input_path: Path
    output_path: Path
    ledger_path: Path
    prs: Any
    reviewer: str = "reviewer"
    original_filename: str = "presentation.pptx"

    def save(self) -> Path:
        """Persist the in-memory presentation to the output path."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(self.output_path)
        return self.output_path


@dataclass(slots=True)
class JobStore:
    """Thread-safe registry of active jobs backed by a temp root directory."""

    root: Path
    _jobs: dict[str, Job] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    @classmethod
    def create(cls, root: Path | None = None) -> "JobStore":
        """Build a store rooted at ``root`` (a fresh temp dir by default)."""
        resolved = root or Path(tempfile.mkdtemp(prefix="accessislides_"))
        resolved.mkdir(parents=True, exist_ok=True)
        return cls(root=resolved)

    def new_job(self, *, original_filename: str, reviewer: str = "reviewer") -> Job:
        """Allocate a job with its own work directory and register it.

        The presentation object is attached later by the caller once the upload
        has been written into the job's work directory.
        """
        job_id = uuid.uuid4().hex
        work_dir = self.root / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(original_filename).name or "presentation.pptx"
        job = Job(
            job_id=job_id,
            work_dir=work_dir,
            input_path=work_dir / "input.pptx",
            output_path=work_dir / "fixed.pptx",
            ledger_path=work_dir / "ledger.json",
            prs=None,
            reviewer=reviewer,
            original_filename=safe_name,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        """Return the job for ``job_id`` or ``None`` when unknown."""
        with self._lock:
            return self._jobs.get(job_id)

    def remove(self, job_id: str) -> None:
        """Drop a job and delete its work directory."""
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is not None:
            shutil.rmtree(job.work_dir, ignore_errors=True)

    def clear(self) -> None:
        """Delete every job and the entire temp root (used on shutdown/tests)."""
        with self._lock:
            self._jobs.clear()
        shutil.rmtree(self.root, ignore_errors=True)
