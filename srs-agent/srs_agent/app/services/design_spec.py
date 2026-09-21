"""Durable, versioned visual decisions that belong beside an approved SRS."""
from __future__ import annotations

import hashlib
import json

from ..schemas.project import now_iso
from . import storage


def _path(project_id: str):
    return storage.project_dir(project_id) / "design-spec.json"


def _read(project_id: str) -> dict:
    try:
        body = json.loads(_path(project_id).read_text(encoding="utf-8"))
        return body if isinstance(body, dict) else {}
    except (OSError, ValueError):
        return {}


def _clean(value):
    """Keep a JSON-only, bounded design record; never save arbitrary objects."""
    if isinstance(value, str):
        return " ".join(value.split())[:2_000]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        return [_clean(item) for item in value[:40]]
    if isinstance(value, dict):
        return {str(key)[:80]: _clean(item) for key, item in list(value.items())[:80]}
    return str(value)[:2_000]


def _fingerprint(spec: dict) -> str:
    raw = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _summary(previous: dict, current: dict) -> list[str]:
    labels = {
        "theme": "Theme", "colors": "Colours", "typography": "Typography",
        "layout": "Layout", "motion": "Motion", "wireframe_fidelity": "Wireframe fidelity",
        "direction": "Design direction", "images": "Image guidance",
    }
    out = []
    for key, label in labels.items():
        if previous.get(key) != current.get(key):
            out.append(f"{label} updated")
    return out or ["Design specification recorded"]


def get(project_id: str) -> dict:
    body = _read(project_id)
    return {
        "current": body.get("current"),
        "versions": body.get("versions", []),
        "current_version": body.get("current_version", 0),
    }


def draft(project_id: str, spec: dict, source: str = "design-customizer") -> dict:
    saved = _read(project_id)
    current = saved.get("current") if isinstance(saved.get("current"), dict) else {}
    current_spec = current.get("spec") if isinstance(current.get("spec"), dict) else {}
    clean = _clean(spec if isinstance(spec, dict) else {})
    version = int(saved.get("current_version") or 0) + 1
    entry = {
        "version": version,
        "status": "draft",
        "source": str(source or "design-customizer")[:80],
        "created_at": now_iso(),
        "fingerprint": _fingerprint(clean),
        "summary": _summary(current_spec, clean),
        "spec": clean,
    }
    versions = list(saved.get("versions") or [])[-24:]
    versions.append(entry)
    storage.write_json(_path(project_id), {
        "current_version": version,
        "current": entry,
        "versions": versions,
    })
    return entry


def approve(project_id: str, version: int) -> dict:
    saved = _read(project_id)
    current = saved.get("current") if isinstance(saved.get("current"), dict) else None
    if not current or int(current.get("version") or 0) != int(version):
        raise ValueError("A newer design specification draft is available")
    if current.get("status") == "approved":
        return current
    current = {**current, "status": "approved", "approved_at": now_iso(),
               "approved_by": "local-user"}
    versions = list(saved.get("versions") or [])
    if versions:
        versions[-1] = current
    storage.write_json(_path(project_id), {
        "current_version": current["version"], "current": current, "versions": versions,
    })
    return current
