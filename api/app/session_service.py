from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont

from . import state
from .common import guess_project_name, normalize_project_name, today_iso
from .config import DATA_ROOT
from .question_maker import normalize_existing_question_plan
from .srs_generator import build_srs, build_stack, validate_srs


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf")]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, used_font: ImageFont.ImageFont, width: int) -> list[str]:
    lines = []
    for paragraph in (text or "").splitlines() or [""]:
        words = paragraph.split() or [""]
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if draw.textbbox((0, 0), candidate, font=used_font)[2] <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def pdf_bytes(srs: dict[str, Any], validation: dict[str, Any]) -> bytes:
    width, height, margin = 1240, 1754, 90
    title_font, heading_font, body_font = font(34, True), font(22, True), font(16)
    pages, page = [], Image.new("RGB", (width, height), "white")
    draw, y = ImageDraw.Draw(page), margin

    def new_page() -> None:
        nonlocal page, draw, y
        pages.append(page)
        page = Image.new("RGB", (width, height), "white")
        draw, y = ImageDraw.Draw(page), margin

    def write_block(text: str, used_font: ImageFont.ImageFont, gap: int = 12) -> None:
        nonlocal y
        for line in wrap(draw, text, used_font, width - margin * 2):
            line_height = draw.textbbox((0, 0), line or " ", font=used_font)[3] + gap
            if y + line_height > height - margin:
                new_page()
            draw.text((margin, y), line, fill="#111827", font=used_font)
            y += line_height

    write_block(srs["document_type"], title_font)
    write_block(srs["metadata"]["project_name"], heading_font)
    write_block(f"Project ID: {srs['metadata']['project_id']} | Status: {srs['metadata']['status']} | Generated: {srs['metadata']['last_updated']}", body_font)
    write_block("1. Introduction", heading_font)
    write_block(srs["sections"]["introduction"]["purpose"], body_font)
    write_block(srs["sections"]["introduction"]["product_scope"]["summary"], body_font)
    write_block("2. Core Features", heading_font)
    for feature in srs["sections"]["system_features"]:
        write_block(f"{feature['feature_id']} - {feature['feature_name']}", heading_font, 8)
        write_block(feature["description_and_priority"]["description"], body_font)
        for requirement in feature["functional_requirements"]:
            write_block(f"{requirement['requirement_id']}: {requirement['description']}", body_font, 8)
    write_block("3. Validation Summary", heading_font)
    write_block(f"Status: {validation['status']} | Completeness: {validation['completeness_score']}", body_font)
    for issue in validation["issues"][:10]:
        write_block(f"- {issue['path']}: {issue['message']}", body_font, 8)
    pages.append(page)
    buffer = BytesIO()
    pages[0].save(buffer, format="PDF", resolution=150.0, save_all=True, append_images=pages[1:])
    return buffer.getvalue()


def session_dir(session_id: str) -> Path:
    path = DATA_ROOT / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def artifact_links(session_id: str) -> dict[str, str | None]:
    folder = session_dir(session_id)
    return {
        "json": f"/api/v1/sessions/{session_id}/artifacts/srs.json" if (folder / "srs.json").exists() else None,
        "pdf": f"/api/v1/sessions/{session_id}/artifacts/srs.pdf" if (folder / "srs.pdf").exists() else None,
    }


def serialize_session(session_id: str, session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "status": session.get("status"),
        "project_name": session.get("project_name"),
        "audience": session.get("audience"),
        "idea": session.get("idea"),
        "uploads": session.get("uploads", []),
        "messages": session.get("messages", []),
        "answers": session.get("answers", {}),
        "analysis_summary": session.get("analysis_summary", ""),
        "question_plan": session.get("question_plan"),
        "draft_srs": session.get("draft_srs"),
        "final_srs": session.get("final_srs"),
        "validation": session.get("validation"),
        "recommended_stack": session.get("recommended_stack"),
        "diagram_previews": session.get("diagram_previews", []),
        "artifacts": artifact_links(session_id),
    }


def persist_session(session_id: str, session: dict[str, Any]) -> None:
    folder = session_dir(session_id)
    (folder / "session.json").write_text(json.dumps(serialize_session(session_id, session), indent=2), encoding="utf-8")
    if session.get("final_srs"):
        (folder / "srs.json").write_text(json.dumps(session["final_srs"], indent=2), encoding="utf-8")
        (folder / "srs.pdf").write_bytes(pdf_bytes(session["final_srs"], session["validation"]))


def require_session(session_id: str) -> dict[str, Any]:
    session = state.SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    normalize_existing_question_plan(session)
    return session


def finalize_session(session_id: str, session: dict[str, Any]) -> dict[str, Any]:
    session["recommended_stack"] = build_stack(session)
    session["final_srs"] = build_srs(session, True)
    session["validation"] = validate_srs(session["final_srs"], session)
    session["diagram_previews"] = session["final_srs"].get("diagram_previews", [])
    session["status"] = "finalized"
    persist_session(session_id, session)
    return serialize_session(session_id, session)


def create_session_state(session_id: str, payload: Any) -> dict[str, Any]:
    return {
        "id": session_id,
        "status": "created",
        "project_name": normalize_project_name(payload.project_name or guess_project_name(payload.idea)),
        "idea": payload.idea.strip(),
        "audience": payload.audience.strip() or "General users",
        "uploads": [],
        "messages": [],
        "answers": {},
        "analysis_summary": "",
        "question_plan": None,
        "draft_srs": None,
        "final_srs": None,
        "validation": None,
        "recommended_stack": None,
        "diagram_previews": [],
        "created_on": today_iso(),
    }
