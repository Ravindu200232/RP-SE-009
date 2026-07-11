"""Project CRUD + input ingestion endpoints."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..extraction import extract_image_text, extract_pdf_text, transcribe_audio
from ..models import repositories as repo
from ..schemas.project import CreateProjectRequest
from ..services import orchestrator, storage

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("")
async def create_project(req: CreateProjectRequest):
    project = await orchestrator.create_project(req.idea, req.language)
    return {"project": project}


@router.get("")
async def list_projects():
    return {"projects": await repo.list_projects()}


@router.get("/{project_id}")
async def get_project(project_id: str):
    try:
        return await orchestrator.project_detail(project_id)
    except KeyError:
        raise HTTPException(404, "project not found")


@router.post("/{project_id}/approve")
async def approve_project(project_id: str):
    project = await repo.get_project(project_id)
    if not project:
        raise HTTPException(404, "project not found")
    await repo.update_project(project_id, {"status": "approved"})
    return {"project": await repo.get_project(project_id)}


@router.post("/{project_id}/inputs")
async def add_input(
    project_id: str,
    mode: str = Form("text"),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    project = await repo.get_project(project_id)
    if not project:
        raise HTTPException(404, "project not found")

    if file is None:
        src = await orchestrator.add_source(project_id, mode, text or "", None, {})
        return {"source": src}

    data = await file.read()
    fname = file.filename or "upload"
    ctype = (file.content_type or "").lower()

    # Persist the original upload alongside generated artifacts.
    uploads = storage.project_dir(project_id) / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / fname).write_bytes(data)

    lower = fname.lower()
    if mode == "pdf" or lower.endswith(".pdf") or "pdf" in ctype:
        res = extract_pdf_text(data, fname); resolved = "pdf"
    elif mode == "image" or ctype.startswith("image/") or lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        res = extract_image_text(data, fname); resolved = "image"
    elif mode == "voice" or ctype.startswith("audio/") or lower.endswith((".webm", ".wav", ".mp3", ".m4a", ".ogg")):
        res = transcribe_audio(data, fname); resolved = "voice"
    else:
        res = {"text": data.decode("utf-8", "ignore"), "engine": "raw"}; resolved = "text"

    src = await orchestrator.add_source(
        project_id, resolved, res.get("text", ""), fname,
        {k: v for k, v in res.items() if k != "text"},
    )
    # Surface extractor warnings (e.g. speech not configured) to the console.
    note = res.get("warning") or res.get("error")
    return {"source": src, "extraction": {k: v for k, v in res.items() if k != "text"}, "note": note}
