"""Filesystem artifact helpers under STORAGE_DIR/{projectId}/..."""
from __future__ import annotations

import json
from pathlib import Path

from ..config import settings


def project_dir(project_id: str) -> Path:
    return settings.project_dir(project_id)


def diagrams_dir(project_id: str) -> Path:
    d = project_dir(project_id) / "diagrams"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def write_json(path: Path, data: dict) -> Path:
    return write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def save_srs_json(project_id: str, srs: dict, version: str) -> Path:
    path = project_dir(project_id) / f"srs_v{version}.json"
    write_json(path, srs)
    write_json(project_dir(project_id) / "srs_latest.json", srs)
    return path


def srs_json_path(project_id: str) -> Path:
    return project_dir(project_id) / "srs_latest.json"


def srs_pdf_path(project_id: str, version: str | None = None) -> Path:
    name = f"SRS_v{version}.pdf" if version else "SRS_latest.pdf"
    return project_dir(project_id) / name
