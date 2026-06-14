import os
import uuid
import json
import zipfile
import io
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional

from app.graph import creation_app, update_app

app = FastAPI(title="AI Designer API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure folders exist
os.makedirs("output", exist_ok=True)
app.mount("/output", StaticFiles(directory="output"), name="output")

class PromptRequest(BaseModel):
    prompt: str
    project_id: Optional[str] = None
    intake: Optional[dict] = None   # answers from the requirements interview
    ai_sections: Optional[bool] = False   # opt-in: Gemma writes each section's JSX


class InterviewRequest(BaseModel):
    prompt: str
    app_type: Optional[str] = "hybrid"
    language: Optional[str] = "en"


class StepRequest(BaseModel):
    plan: dict
    answers: dict = {}


class EditElementRequest(BaseModel):
    project_id: str
    component_id: str
    prompt: str
    tag: Optional[str] = None        # clicked element's tag (h1, img, div...)
    text: Optional[str] = None       # its current text (enables deterministic edits)
    class_name: Optional[str] = None # its className (helps the diff locate the snippet)


class ReplaceImageRequest(BaseModel):
    project_id: str
    src: str                       # the <img> src, e.g. /assets/feature1.jpg
    data_b64: Optional[str] = None # Option A: uploaded file
    prompt: Optional[str] = None   # Option B: AI regenerate


class SetImageRequest(BaseModel):
    project_id: str
    component_id: str              # the clicked image's component id (locates the source file)
    src: str                       # its current src, e.g. /assets/about1.jpg
    data_b64: Optional[str] = None # Option A: uploaded file (base64, optional data: prefix)
    prompt: Optional[str] = None   # Option B: "Make changes with Fooocus AI"


class AddSectionRequest(BaseModel):
    project_id: str
    component_id: str              # an element on the page to add the section to
    prompt: str

def load_local_files(project_id: str) -> dict:
    """Reads all files in output/{project_id} and loads them into a dictionary."""
    project_dir = os.path.join("output", project_id)
    if not os.path.exists(project_dir):
        return {}
        
    files = {}
    for root, _, filenames in os.walk(project_dir):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, project_dir)
            # Use forward slashes for internal state mapping consistency
            rel_path_key = rel_path.replace("\\", "/")
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    files[rel_path_key] = f.read()
            except Exception:
                pass # skip binaries if any
    return files

# =========================================================================
# SSE LOG GENERATOR FOR NEW GENERATIONS
# =========================================================================
async def sse_creation_stream(prompt: str, project_id: str, intake: dict = None, ai_sections: bool = False):
    from app import interview as _interview
    state = {
        "ai_sections": bool(ai_sections),
        "project_id": project_id,
        "prompt": prompt,
        "history": [],
        "roles": [],
        "pages": [],
        "files": {},
        "intake": _interview.assemble_intake(intake) if intake else {},
        "status": "Initializing...",
        "logs": ["Starting agent graph workflow...", f"Allocated Project ID: {project_id}"]
    }
    
    # Send initial logs
    for log in state["logs"]:
        yield f"data: {json.dumps({'log': log, 'project_id': project_id, 'status': 'running'})}\n\n"
        
    sent_logs_count = len(state["logs"])
    
    try:
        # Run graph asynchronously
        async for event in creation_app.astream(state):
            # Inspect the node outputs
            for node_name, node_state in event.items():
                logs = node_state.get("logs", [])
                # Yield only new logs
                while sent_logs_count < len(logs):
                    new_log = logs[sent_logs_count]
                    yield f"data: {json.dumps({'log': new_log, 'project_id': project_id, 'status': 'running'})}\n\n"
                    sent_logs_count += 1
                    
        # Successfully finished
        yield f"data: {json.dumps({'log': 'Workflow completed successfully!', 'project_id': project_id, 'status': 'completed'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'log': f'CRITICAL ERROR: {str(e)}', 'project_id': project_id, 'status': 'failed'})}\n\n"

# =========================================================================
# SSE LOG GENERATOR FOR UPDATES (EDIT LOOP)
# =========================================================================
async def sse_update_stream(prompt: str, project_id: str):
    # Load previous files
    existing_files = load_local_files(project_id)
    if not existing_files:
        yield f"data: {json.dumps({'log': f'Error: Project {project_id} files not found on local disk.', 'project_id': project_id, 'status': 'failed'})}\n\n"
        return
        
    state = {
        "project_id": project_id,
        "prompt": prompt,
        "history": [],
        "roles": [],
        "pages": [],
        "files": existing_files,
        "status": "Analyzing modifications...",
        "logs": ["Analyzing previous codebase...", f"Workspace: output/{project_id}"]
    }
    
    for log in state["logs"]:
        yield f"data: {json.dumps({'log': log, 'project_id': project_id, 'status': 'running'})}\n\n"
        
    sent_logs_count = len(state["logs"])
    
    try:
        # Run update workflow
        async for event in update_app.astream(state):
            for node_name, node_state in event.items():
                logs = node_state.get("logs", [])
                while sent_logs_count < len(logs):
                    new_log = logs[sent_logs_count]
                    yield f"data: {json.dumps({'log': new_log, 'project_id': project_id, 'status': 'running'})}\n\n"
                    sent_logs_count += 1
                    
        # Run build/compile after update if build.js exists in the workspace
        project_dir = os.path.join("output", project_id)
        build_script = os.path.join(project_dir, "build.js")
        if os.path.exists(build_script):
            yield f"data: {json.dumps({'log': 'Compiling updated modules using build.js...', 'project_id': project_id, 'status': 'running'})}\n\n"
            # Execute node build.js locally
            import subprocess
            res = subprocess.run(["node", "build.js"], cwd=project_dir, capture_output=True, text=True)
            if res.returncode == 0:
                yield f"data: {json.dumps({'log': 'Standalone index.html compiled successfully.', 'project_id': project_id, 'status': 'running'})}\n\n"
            else:
                yield f"data: {json.dumps({'log': f'Warning during compile: {res.stderr}', 'project_id': project_id, 'status': 'running'})}\n\n"
                
        yield f"data: {json.dumps({'log': 'Modifications successfully saved and compiled!', 'project_id': project_id, 'status': 'completed'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'log': f'CRITICAL ERROR: {str(e)}', 'project_id': project_id, 'status': 'failed'})}\n\n"

# =========================================================================
# ENDPOINTS
# =========================================================================
@app.get("/api/interview/meta")
async def interview_meta():
    """Languages + app types for the studio's first screen."""
    from app import interview as _interview
    return {"languages": _interview.LANGUAGES, "app_types": _interview.APP_TYPES}


class SrsExtractRequest(BaseModel):
    filename: Optional[str] = "srs"
    data_b64: Optional[str] = None   # base64 of the file bytes (PDF or any)
    text: Optional[str] = None       # or plain text directly


@app.post("/api/srs/extract")
async def srs_extract(req: SrsExtractRequest):
    """Read an uploaded SRS (PDF or JSON/text, sent as base64) and return its
    text for the interview. JSON body -> no python-multipart dependency."""
    name = (req.filename or "").lower()
    if req.text:
        return {"text": req.text[:20000], "filename": req.filename}
    if not req.data_b64:
        raise HTTPException(status_code=400, detail="no file content")
    import base64
    try:
        raw = base64.b64decode(req.data_b64.split(",")[-1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"bad file data: {e}")
    if name.endswith(".pdf"):
        try:
            import io as _io
            from pypdf import PdfReader
            text = "\n".join((p.extract_text() or "") for p in PdfReader(_io.BytesIO(raw)).pages)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"could not read PDF: {e}")
    else:
        text = raw.decode("utf-8", errors="ignore")
    return {"text": text[:20000], "filename": req.filename}


@app.post("/api/interview/start")
async def interview_start(req: InterviewRequest):
    """LLM planner agent: build the tailored plan for this app + type + language,
    and return the FIRST question. The studio asks one question at a time."""
    from app import interview as _interview
    try:
        plan = _interview.build_plan(req.prompt, req.app_type or "hybrid", req.language or "en")
        first = _interview.next_step(plan, {})
        return {"plan": plan, **first}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"interview failed: {e}")


@app.post("/api/interview/step")
async def interview_step(req: StepRequest):
    """Given the plan + answers so far, return the NEXT question (its options may
    be LLM-generated for custom pages) or {done, answers} when complete."""
    from app import interview as _interview
    try:
        return _interview.next_step(req.plan, req.answers or {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"interview step failed: {e}")


@app.post("/api/generate")
async def generate_prototype(req: PromptRequest):
    project_id = f"prj_{uuid.uuid4().hex[:8]}"
    return StreamingResponse(
        sse_creation_stream(req.prompt, project_id, req.intake, req.ai_sections),
        media_type="text/event-stream"
    )

@app.post("/api/update")
async def update_prototype(req: PromptRequest):
    if not req.project_id:
        raise HTTPException(status_code=400, detail="project_id is required for updates")
    return StreamingResponse(
        sse_update_stream(req.prompt, req.project_id),
        media_type="text/event-stream"
    )

# =========================================================================
# V2: STATUS + MANAGED NEXT.JS PREVIEW
# =========================================================================
from app import nextgen as _nextgen
import socket as _socket
import subprocess as _subprocess
import time as _time

_previews: dict = {}  # project_id -> {"proc": Popen, "port": int}


def _port_free(port: int) -> bool:
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _port_for(project_id: str) -> int:
    return 3100 + (abs(hash(project_id)) % 400)


@app.get("/api/status")
async def project_status(project_id: str):
    out_dir = os.path.join("output", project_id)
    if not os.path.exists(out_dir):
        return {"phase": "planning", "detail": "Starting"}
    return _nextgen.read_status(out_dir)


@app.post("/api/preview")
async def start_preview(req: PromptRequest):
    """Start (or reuse) `next start` for a built project; one active preview at
    a time. Returns the URL for the studio iframe - only valid once phase=done."""
    pid = req.project_id
    if not pid:
        raise HTTPException(status_code=400, detail="project_id is required")
    out_dir = os.path.join("output", pid)
    if _nextgen.read_status(out_dir).get("phase") != "done":
        raise HTTPException(status_code=409, detail="Project is not ready yet")

    live = _previews.get(pid)
    if live and live["proc"].poll() is None:
        return {"url": f"http://localhost:{live['port']}"}

    # stop other previews (one Next server at a time keeps RAM sane)
    for other_pid, info in list(_previews.items()):
        if info["proc"].poll() is None:
            info["proc"].kill()
        _previews.pop(other_pid, None)

    port = _port_for(pid)
    if not _port_free(port):
        port = next(p for p in range(3100, 3600) if _port_free(p))
    proc = _subprocess.Popen(
        ["npm", "run", "dev", "--", "-p", str(port)],
        cwd=out_dir, shell=True,
        stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL,
    )
    _previews[pid] = {"proc": proc, "port": port}
    for _ in range(60):  # wait for the server to accept connections (~max 30s)
        if not _port_free(port):
            break
        if proc.poll() is not None:
            raise HTTPException(status_code=500, detail="Preview server exited early")
        _time.sleep(0.5)
    return {"url": f"http://localhost:{port}"}


def _restart_preview(pid: str):
    """Relaunch the project's `next start` so it serves the freshly-built output
    after a Select-Element edit."""
    info = _previews.get(pid)
    if not info:
        return
    try:
        if info["proc"].poll() is None:
            info["proc"].kill()
    except Exception:
        pass
    port = info["port"]
    for _ in range(20):
        if _port_free(port):
            break
        _time.sleep(0.3)
    proc = _subprocess.Popen(
        ["npm", "run", "dev", "--", "-p", str(port)],
        cwd=os.path.join("output", pid), shell=True,
        stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL,
    )
    _previews[pid] = {"proc": proc, "port": port}
    for _ in range(60):
        if not _port_free(port) or proc.poll() is not None:
            break
        _time.sleep(0.5)


@app.post("/api/edit-element")
async def edit_element(req: EditElementRequest):
    """Select-Element: edit ONLY the clicked component (deterministic for text,
    Gemma for the rest), build it (auto-revert on failure), restart the preview."""
    from app import editor
    # dev preview serves from source, so the studio just reloads the iframe - no rebuild/restart.
    return editor.edit_component(req.project_id, req.component_id, req.prompt, req.tag, req.text, req.class_name)


@app.post("/api/replace-image")
async def replace_image(req: ReplaceImageRequest):
    """Select-Element image modal: Option A upload (overwrite the asset, instant,
    no rebuild) or Option B AI-regenerate via Fooocus."""
    from app import editor
    return editor.replace_image(req.project_id, req.src, req.data_b64, req.prompt)


@app.post("/api/upload-image")
async def upload_image(req: SetImageRequest):
    """Image modal Option A: save the uploaded file to a fresh asset and surgically
    repoint the clicked component's src at it (deterministic, no LLM, atomic)."""
    from app import editor
    return editor.set_component_image(req.project_id, req.component_id, req.src, data_b64=req.data_b64)


@app.post("/api/generate-image")
async def generate_image(req: SetImageRequest):
    """Image modal Option B: Fooocus-generate from the prompt, save to a fresh asset
    and repoint the component's src. GPU is coordinated inside generate_one (_unload_llm)."""
    from app import editor
    return editor.set_component_image(req.project_id, req.component_id, req.src, prompt=req.prompt)


@app.post("/api/add-section")
async def add_section(req: AddSectionRequest):
    """Add a brand-new, prompt-described section to the page the user pointed at."""
    from app import editor
    return editor.add_section(req.project_id, req.component_id, req.prompt)


@app.get("/api/latest-code")
async def get_latest_code(project_id: str):
    files = load_local_files(project_id)
    if not files:
        raise HTTPException(status_code=404, detail="Project folder not found")
    return {"project_id": project_id, "files": files}

@app.get("/api/download")
async def download_project(project_id: str):
    project_dir = os.path.join("output", project_id)
    if not os.path.exists(project_dir):
        raise HTTPException(status_code=404, detail="Project folder not found")
        
    # Zip files in-memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _, filenames in os.walk(project_dir):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, project_dir)
                zip_file.write(full_path, arcname=rel_path)
                
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/x-zip-compressed",
        headers={
            "Content-Disposition": f"attachment; filename={project_id}.zip"
        }
    )
