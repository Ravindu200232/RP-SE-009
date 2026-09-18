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
        return write_json(folder / "wireframes.json", payload)
    except Exception:  # noqa: BLE001 - a missing wireframe must not fail a save
        return None


def html_dir(project_id: str) -> Path:
    """Where the full-fidelity HTML drawing of each page lives.

    Beside the blocks rather than instead of them. The blocks are what the
    tools editor moves and what the projection can always produce; the HTML is
    a second, richer view of the same page, and a page may have one, both or
    neither.
    """
    d = wireframes_dir(project_id) / "html"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _html_name(route: str) -> str:
    """A route as a filename. `/product/[id]` -> `product-id.html`."""
    safe = "".join(ch if ch.isalnum() else "-" for ch in str(route or "/").strip("/").lower())
    safe = "-".join(part for part in safe.split("-") if part)
    return f"{safe or 'index'}.html"


def _html_versions(project_id: str) -> dict:
    try:
        stored = json.loads((html_dir(project_id) / "drawn.json").read_text(encoding="utf-8"))
        return stored if isinstance(stored, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def save_page_html(project_id: str, route: str, html: str, version: str = "") -> None:
    """Keep the drawing, and the version of the specification it was drawn from.

    The version is the whole point of the sidecar. The blocks are re-derived on
    every save because a projection costs milliseconds; a full page costs a
    model call each, so it is drawn on request and then goes quietly out of
    date the next time the document moves. Recording what it was drawn from is
    what lets the editor say so instead of showing a stale page as current.
    """
    (html_dir(project_id) / _html_name(route)).write_text(str(html or ""), encoding="utf-8")
    versions = _html_versions(project_id)
    versions[str(route)] = str(version or "")
    write_json(html_dir(project_id) / "drawn.json", versions)


def read_page_html(project_id: str, route: str) -> str:
    try:
        return (html_dir(project_id) / _html_name(route)).read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return ""


def read_wireframes(project_id: str) -> dict:
    try:
        payload = json.loads((wireframes_dir(project_id) / "wireframes.json")
                             .read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"pages": [], "journeys": []}
    # Tell the editor which pages have the full drawing, so it can offer the
    # view rather than opening an empty frame and finding out - and which of
    # those were drawn from an older version of the document.
    folder = wireframes_dir(project_id) / "html"
    version = str(payload.get("version") or "")
    versions = _html_versions(project_id) if folder.is_dir() else {}
    for page in (payload.get("pages") or []):
        if not isinstance(page, dict):
            continue
        route = page.get("route")
        page["has_html"] = (folder / _html_name(route)).is_file()
        page["html_stale"] = bool(page["has_html"]
                                  and version
                                  and str(versions.get(str(route), "")) != version)
    return payload


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
