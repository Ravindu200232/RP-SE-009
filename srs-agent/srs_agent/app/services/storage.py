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
    import os
    import uuid
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def write_json(path: Path, data: dict) -> Path:
    return write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def save_srs_json(project_id: str, srs: dict, version: str) -> Path:
    path = project_dir(project_id) / f"srs_v{version}.json"
    write_json(path, srs)
    write_json(project_dir(project_id) / "srs_latest.json", srs)
    save_wireframes(project_id, srs)
    return path


def wireframes_dir(project_id: str) -> Path:
    d = project_dir(project_id) / "wireframes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_wireframes(project_id: str, srs: dict) -> Path | None:
    """Re-derive the wireframes and journeys from whatever was just saved.

    Done on every write rather than on request, because the two can then never
    disagree: a page added by a prompt, by a prototype edit or by a build's
    report reaches the document through this function, and the wireframe for it
    exists the moment the document does. It is a projection, not a model call -
    measured at 2.9 ms for eleven pages - so there is nothing to schedule and
    nothing to invalidate.
    """
    try:
        from ..generators.wireframes import user_journeys_for, wireframes_for
        doc = (srs or {}).get("srs_document") or srs or {}
        frames = wireframes_for(doc)
        payload = {
            "version": str(doc.get("version") or ""),
            "generated_from": "specification",
            "pages": frames,
            "journeys": user_journeys_for(doc),
        }
        folder = wireframes_dir(project_id)
        # Hand edits live in their own file and are re-applied on top, so a
        # regeneration never silently discards what someone moved by hand.
        return write_json(folder / "wireframes.json", _with_edits(folder, payload))
    except Exception:  # noqa: BLE001 - a missing wireframe must not fail a save
        return None


def _with_edits(folder: Path, payload: dict) -> dict:
    """Lay saved per-page edits back over a freshly derived set."""
    try:
        edits = json.loads((folder / "edits.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return payload
    if not isinstance(edits, dict):
        return payload
    for page in payload.get("pages") or []:
        saved = edits.get(page.get("route"))
        if isinstance(saved, dict) and saved.get("blocks"):
            page["blocks"] = saved["blocks"]
            page["edited"] = True
    return payload


def save_drawn_wireframes(project_id: str, doc: dict, frames: list) -> dict:
    """Keep a set drawn for quality, hand edits still laid on top."""
    from ..generators.wireframes import user_journeys_for
    folder = wireframes_dir(project_id)
    payload = {"version": str((doc or {}).get("version") or ""),
               "generated_from": "model", "pages": frames,
               "journeys": user_journeys_for(doc or {})}
    write_json(folder / "wireframes.json", _with_edits(folder, payload))
    return read_wireframes(project_id)


def read_wireframes(project_id: str) -> dict:
    try:
        return json.loads((wireframes_dir(project_id) / "wireframes.json")
                          .read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"pages": [], "journeys": []}


def save_wireframe_edit(project_id: str, route: str, blocks: list) -> dict:
    """Keep one page's hand-edited layout, and nothing else.

    Only the page named here is written. The editor opens one wireframe at a
    time and may not reach any other, so a saved edit cannot disturb a page the
    person was not looking at.
    """
    folder = wireframes_dir(project_id)
    try:
        edits = json.loads((folder / "edits.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        edits = {}
    if not isinstance(edits, dict):
        edits = {}
    edits[str(route)] = {"blocks": blocks}
    write_json(folder / "edits.json", edits)
    current = read_wireframes(project_id)
    for page in current.get("pages") or []:
        if page.get("route") == route:
            page["blocks"] = blocks
            page["edited"] = True
    write_json(folder / "wireframes.json", current)
    return current


def save_review_round(project_id: str, round_no: int, payload: dict) -> Path:
    """Keep one reviewer round beside the document it judged.

    Rounds happen before a version exists, so they cannot live in the version
    table; and the full findings - raw scores, suggested rewrites, the model's
    own reasoning - are working notes, not part of the specification the
    builder reads. They stay on disk, where the studio can show them and the
    handoff never sees them.
    """
    directory = project_dir(project_id) / "reviews"
    write_json(directory / f"round-{int(round_no)}.json", payload)
    return write_json(directory / "latest.json", payload)


def read_reviews(project_id: str) -> list[dict]:
    """Every recorded round, oldest first."""
    directory = project_dir(project_id) / "reviews"
    if not directory.is_dir():
        return []
    rounds = []
    for path in sorted(directory.glob("round-*.json"),
                       key=lambda p: int(p.stem.split("-")[-1] or 0)):
        try:
            rounds.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return rounds


def snapshot_reviews(project_id: str, version: str) -> int:
    """Stamp the rounds that produced this version, the way diagrams are kept."""
    directory = project_dir(project_id) / "reviews"
    if not directory.is_dir():
        return 0
    target = directory / f"v{version}"
    target.mkdir(parents=True, exist_ok=True)
    kept = 0
    for path in sorted(directory.glob("round-*.json")):
        try:
            write_text(target / path.name, path.read_text(encoding="utf-8"))
            kept += 1
        except OSError:
            continue
    return kept


def srs_pdf_path(project_id: str, version: str | None = None) -> Path:
    name = f"SRS_v{version}.pdf" if version else "SRS_latest.pdf"
    return project_dir(project_id) / name


def snapshot_diagrams(project_id: str, version: str,
                      diagrams: list[dict] | None = None) -> list[dict]:
    """Keep this version's diagrams before the next revision overwrites them."""
    source = diagrams_dir(project_id)
    target = source / f"v{version}"
    target.mkdir(parents=True, exist_ok=True)

    moved: dict[str, str] = {}
    for path in list(source.glob("*.mmd")) + list(source.glob("*.svg")):
        if not path.is_file():
            continue
        copy = target / path.name
        try:
            copy.write_bytes(path.read_bytes())
            moved[str(path)] = str(copy)
        except OSError:

            continue

    out = []
    for diagram in (diagrams or []):
        if not isinstance(diagram, dict):
            continue
        shifted = dict(diagram)
        for key in ("mmd_path", "svg_path"):
            if shifted.get(key) in moved:
                shifted[key] = moved[shifted[key]]
        out.append(shifted)
    return out
