"""Project CRUD + input ingestion endpoints."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from ..extraction import read_image, read_pdf, transcribe_audio
from ..models import repositories as repo
from ..schemas.project import CreateProjectRequest, UploadRequest
from ..services import orchestrator, storage

router = APIRouter(prefix="/projects", tags=["projects"])

# Base64 inflates by a third, and the whole body is held in memory twice while
# it is decoded. A recording or a scan lands well under this; a video does not,
# and is the thing being turned away.
#
# The number is the transport's, measured rather than chosen: the studio reaches
# this service through a Next rewrite that refuses a body over 10 MiB with a
# bare 500 the service never sees. With base64's 4/3 inflation that is about
# 7.8 MB of file, so anything larger here would be a limit that only ever
# reported itself as a crash.
MAX_UPLOAD_BYTES = 7_500_000


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


async def _ingest(project_id: str, mode: str, data: bytes, fname: str, ctype: str) -> dict:
    """Save the upload, read it with whichever engine fits, record it as a source."""
    uploads = storage.project_dir(project_id) / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / Path(fname).name).write_bytes(data)

    lower = fname.lower()

    if mode == "pdf" or lower.endswith(".pdf") or "pdf" in ctype:
        res = await read_pdf(data, fname); resolved = "pdf"
    elif mode == "image" or ctype.startswith("image/") or lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")):
        res = await read_image(data, fname); resolved = "image"
    elif mode == "voice" or ctype.startswith("audio/") or lower.endswith((".webm", ".wav", ".mp3", ".m4a", ".ogg", ".flac")):
        res = await run_in_threadpool(transcribe_audio, data, fname); resolved = "voice"
    else:
        res = {"text": data.decode("utf-8", "ignore"), "engine": "raw"}; resolved = "text"

    src = await orchestrator.add_source(
        project_id, resolved, res.get("text", ""), fname,
        {k: v for k, v in res.items() if k != "text"},
    )

    note = res.get("warning") or res.get("error")
    return {"source": src, "extraction": {k: v for k, v in res.items() if k != "text"},
            "note": note}


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

    return await _ingest(project_id, mode, await file.read(),
                         file.filename or "upload", (file.content_type or "").lower())


@router.post("/{project_id}/inputs-json")
async def add_input_json(project_id: str, req: UploadRequest):
    """The same ingestion, with the file base64'd into a JSON body.

    Multipart cannot travel the studio's job shim, and the shim is what makes a
    slow upload survive: the browser reaches this service through a Next.js
    rewrite that abandons the request at 30 seconds, while transcribing a
    two-minute recording or showing a twelve-page scan to a vision model
    comfortably outruns that. The shim replays a *JSON* body in-process and
    hands back a job id to poll, so the upload has to be JSON to use it.
    """
    project = await repo.get_project(project_id)
    if not project:
        raise HTTPException(404, "project not found")

    if not req.data_base64:
        src = await orchestrator.add_source(project_id, req.mode, req.text or "", None, {})
        return {"source": src}

    raw = req.data_base64
    if "," in raw[:64] and raw.lstrip().startswith("data:"):
        raw = raw.split(",", 1)[1]          # a browser data: URL
    try:
        data = base64.b64decode(raw, validate=False)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"attachment is not valid base64: {exc}")

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"attachment is larger than {MAX_UPLOAD_BYTES // 1_000_000} MB")

    return await _ingest(project_id, req.mode, data,
                         req.filename or "upload", (req.content_type or "").lower())
