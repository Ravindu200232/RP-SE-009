from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import os

from .models import JobResult, resolve_path


class JobStore:
    def __init__(self, base_dir: str | None = None) -> None:
        root = base_dir or os.getenv("AGENT4_DATA_DIR") or "./data"
        self.base_dir = resolve_path(root)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir = self.base_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: str) -> Path:
        path = self.jobs_dir / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def result_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "result.json"

    def save(self, result: JobResult) -> None:
        path = self.result_path(result.job_id)
        path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

    def load(self, job_id: str) -> dict | None:
        path = self.result_path(job_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

