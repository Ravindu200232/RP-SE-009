"""Durable approval records for changes that can alter an existing project.

This lives above the agents: it records why work is allowed to start, while
the existing SRS transaction still owns all prototype, builder, and QA work.
"""
from __future__ import annotations

import time
import threading
import uuid
from pathlib import Path

from server_modules.services.project_state import atomic_json, read_json

ROLES = ("designer", "developer")
STATES = ("draft", "approved", "running", "completed", "failed")
_LOCK = threading.RLock()


def _folder(directory: Path) -> Path:
    return Path(directory) / ".agentforge" / "change-requests"


def _path(directory: Path, request_id: str) -> Path:
    return _folder(directory) / f"{request_id}.json"


def _safe_id(value: str) -> str:
    value = str(value or "").strip()
    if len(value) != 12 or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError("Invalid change request")
    return value


def _clean_targets(targets) -> list[str]:
    return [role for role in ROLES if role in set(targets or ())]


def _impact(kind: str, targets: list[str], summary: list[str]) -> dict:
    affected = []
    if kind == "design":
        affected += ["versioned design specification", "prototype visual system"]
    else:
        affected += ["SRS and linked handoffs"]
    affected += ["Prototype" if role == "designer" else "Builder and tests" for role in targets]
    return {"affected": affected, "summary": [str(line)[:500] for line in (summary or [])[:20]]}


def create(directory: Path, *, prompt: str, kind: str = "srs", targets=(),
           srs_version=None, design_spec_version=None, summary=(), owner: str = "") -> dict:
    with _LOCK:
        text = str(prompt or "").strip()
        if not text:
            raise ValueError("A change request needs a description")
        kind = str(kind or "srs")
        if kind not in ("srs", "design"):
            raise ValueError("Unknown change request type")
        chosen = _clean_targets(targets)
        request_id = uuid.uuid4().hex[:12]
        now = time.time()
        record = {
            "id": request_id,
            "project": Path(directory).name,
            "kind": kind,
            "status": "draft",
            "prompt": text[:12_000],
            "requested_targets": chosen,
            "targets": [],
            "base_srs_version": srs_version,
            "design_spec_version": design_spec_version,
            "impact": _impact(kind, chosen, list(summary or [])),
            "created_at": now,
            "updated_at": now,
            "owner": str(owner or "")[:160],
        }
        atomic_json(_path(directory, request_id), record)
        return record


def read(directory: Path, request_id: str) -> dict:
    request_id = _safe_id(request_id)
    record = read_json(_path(directory, request_id), None)
    if not record:
        raise ValueError("Change request not found")
    return record


def list_for(directory: Path) -> list[dict]:
    records = []
    folder = _folder(directory)
    paths = folder.glob("*.json") if folder.is_dir() else ()
    for path in paths:
        record = read_json(path, None)
        if isinstance(record, dict) and record.get("id"):
            # Prompts can be lengthy or confidential; list only audit metadata.
            records.append({key: value for key, value in record.items() if key != "prompt"})
    return sorted(records, key=lambda row: row.get("created_at", 0), reverse=True)


def update(directory: Path, request_id: str, **patch) -> dict:
    with _LOCK:
        record = read(directory, request_id)
        record.update(patch, updated_at=time.time())
        atomic_json(_path(directory, record["id"]), record)
        return record


def approve(directory: Path, request_id: str, targets) -> dict:
    with _LOCK:
        record = read(directory, request_id)
        if record.get("status") != "draft":
            raise ValueError("This change request is no longer awaiting approval")
        active = [row for row in list_for(directory)
                  if row.get("id") != record["id"] and row.get("status") in ("approved", "running")]
        if active:
            raise ValueError("Finish the active approved change before starting another one")
        chosen = _clean_targets(targets)
        if not chosen:
            raise ValueError("Choose a Prototype or Builder update")
        return update(directory, request_id, status="approved", targets=chosen,
                      approved_at=time.time(), approved_by="local-user")
