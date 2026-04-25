from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .graph import run_build
from .llm import DEFAULT_MODEL, OLLAMA_AVAILABLE
from .prompts import COMPONENT_SPECS, PAGE_TEMPLATES, STYLE_VARIANTS
from .sandbox import STORE as SANDBOX_STORE, plan_srs, refine_sandbox, repair_sandbox, run_generation

try:
    from langchain_core.prompts import ChatPromptTemplate
    LANGCHAIN_AVAILABLE = True
except Exception:
    ChatPromptTemplate = None
    LANGCHAIN_AVAILABLE = False

try:
    from langgraph.graph import StateGraph
    LANGGRAPH_AVAILABLE = True
except Exception:
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


class BuildRequest(BaseModel):
    srs_json: dict[str, Any]
    model: str | None = None


class SandboxGenerateRequest(BaseModel):
    srs_json: dict[str, Any]
    model: str | None = None


class SandboxRefineRequest(BaseModel):
    instruction: str


class SandboxRepairRequest(BaseModel):
    error_message: str
    error_stack: str | None = None


class SandboxPlanRequest(BaseModel):
    srs_json: dict[str, Any]
    model: str | None = None


app = FastAPI(title="Agent 2 Builder API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: dict[str, dict[str, Any]] = {}
RUN_LOCK = threading.Lock()
BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "runs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _start_background_build(run_id: str, srs_json: dict, model: str | None) -> None:
    run_dir = OUTPUT_DIR / run_id

    def append_log(message: str) -> None:
        with RUN_LOCK:
            RUNS[run_id]["logs"].append({"ts": time.time(), "message": message})

    def worker() -> None:
        try:
            state = run_build(
                srs_json=srs_json,
                output_dir=str(run_dir),
                model=model,
                on_log=append_log,
            )
            with RUN_LOCK:
                RUNS[run_id]["status"] = "completed"
                RUNS[run_id]["files"] = state.get("files", [])
                RUNS[run_id]["completed_at"] = time.time()
        except Exception as exc:
            append_log(f"[error] {exc}")
            with RUN_LOCK:
                RUNS[run_id]["status"] = "failed"
                RUNS[run_id]["error"] = str(exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "agent2-developer",
        "langchain": LANGCHAIN_AVAILABLE,
        "langgraph": LANGGRAPH_AVAILABLE,
        "ollama": OLLAMA_AVAILABLE,
        "default_model": DEFAULT_MODEL,
    }


@app.get("/api/v1/catalog")
def catalog() -> dict[str, Any]:
    return {
        "styles": STYLE_VARIANTS,
        "component_categories": [
            {"id": k, **v} for k, v in COMPONENT_SPECS.items()
        ],
        "page_templates": PAGE_TEMPLATES,
        "variants_per_category": len(STYLE_VARIANTS),
    }


@app.post("/api/v1/build/start")
def start_build(payload: BuildRequest) -> dict[str, Any]:
    run_id = str(uuid4())
    project_name = (
        payload.srs_json.get("project_name")
        or payload.srs_json.get("name")
        or (payload.srs_json.get("metadata") or {}).get("project")
        or "GeneratedApp"
    )
    with RUN_LOCK:
        RUNS[run_id] = {
            "started_at": time.time(),
            "project_name": project_name,
            "model": payload.model or DEFAULT_MODEL,
            "status": "running",
            "logs": [],
            "files": [],
        }
    _start_background_build(run_id, payload.srs_json, payload.model)
    return {"build_id": run_id, "model": payload.model or DEFAULT_MODEL}


@app.get("/api/v1/build/{build_id}")
def get_build(build_id: str) -> dict[str, Any]:
    with RUN_LOCK:
        run = RUNS.get(build_id)
        if not run:
            raise HTTPException(status_code=404, detail="build not found")
        snapshot = {
            "status": run["status"],
            "project_name": run["project_name"],
            "model": run["model"],
            "logs": [entry["message"] for entry in run["logs"]],
            "stats": {
                "files": len(run["files"]),
                "expected": len(STYLE_VARIANTS) * len(COMPONENT_SPECS) + len(STYLE_VARIANTS) * len(PAGE_TEMPLATES),
            },
            "files": [
                {"path": f["path"], "category": f.get("category"), "style": f.get("style")}
                for f in run["files"]
            ],
            "output_path": str(OUTPUT_DIR / build_id),
            "error": run.get("error"),
        }
    return snapshot


@app.get("/api/v1/build/{build_id}/file")
def get_build_file(build_id: str, path: str) -> dict[str, Any]:
    with RUN_LOCK:
        run = RUNS.get(build_id)
        if not run:
            raise HTTPException(status_code=404, detail="build not found")
    target = (OUTPUT_DIR / build_id / path).resolve()
    base = (OUTPUT_DIR / build_id).resolve()
    if not str(target).startswith(str(base)) or not target.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return {"path": path, "content": target.read_text(encoding="utf-8")}


def _sandbox_payload(record: dict[str, Any], include_html: bool = True) -> dict[str, Any]:
    return {
        "sandbox_id": record["sandbox_id"],
        "status": record.get("status"),
        "version": record.get("version", 0),
        "model": record.get("model"),
        "history": record.get("history", []),
        "error": record.get("error"),
        "html": record.get("html") if include_html else None,
        "code": record.get("code") if include_html else None,
    }


@app.post("/api/v1/sandbox/plan")
def sandbox_plan(payload: SandboxPlanRequest) -> dict[str, Any]:
    try:
        enriched = plan_srs(payload.srs_json, payload.model)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"plan failed: {exc}")
    return {"srs_json": enriched}


@app.post("/api/v1/sandbox/generate")
def sandbox_generate(payload: SandboxGenerateRequest) -> dict[str, Any]:
    record = SANDBOX_STORE.create(payload.srs_json, payload.model)
    sandbox_id = record["sandbox_id"]

    def worker() -> None:
        try:
            run_generation(sandbox_id)
        except Exception as exc:
            SANDBOX_STORE.update(sandbox_id, status="failed", error=str(exc))

    threading.Thread(target=worker, daemon=True).start()
    return {"sandbox_id": sandbox_id, "status": "generating"}


@app.get("/api/v1/sandbox/{sandbox_id}")
def sandbox_get(sandbox_id: str, include_html: bool = True) -> dict[str, Any]:
    record = SANDBOX_STORE.get(sandbox_id)
    if not record:
        raise HTTPException(status_code=404, detail="sandbox not found")
    return _sandbox_payload(record, include_html=include_html)


@app.get("/api/v1/sandbox/{sandbox_id}/preview", response_class=None)
def sandbox_preview(sandbox_id: str):
    from fastapi.responses import HTMLResponse, PlainTextResponse

    record = SANDBOX_STORE.get(sandbox_id)
    if not record:
        return PlainTextResponse("sandbox not found", status_code=404)
    if record.get("status") != "ready" or not record.get("html"):
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;padding:24px;color:#6b7280'>"
            f"Sandbox status: {record.get('status')}. {record.get('error') or 'Generating...'}</body></html>"
        )
    return HTMLResponse(record["html"])


@app.post("/api/v1/sandbox/{sandbox_id}/refine")
def sandbox_refine(sandbox_id: str, payload: SandboxRefineRequest) -> dict[str, Any]:
    instruction = (payload.instruction or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="instruction is required")
    record = SANDBOX_STORE.get(sandbox_id)
    if not record:
        raise HTTPException(status_code=404, detail="sandbox not found")
    SANDBOX_STORE.update(sandbox_id, status="refining")

    def worker() -> None:
        try:
            refine_sandbox(sandbox_id, instruction)
        except Exception as exc:
            SANDBOX_STORE.update(sandbox_id, status="failed", error=str(exc))

    threading.Thread(target=worker, daemon=True).start()
    return {"sandbox_id": sandbox_id, "status": "refining"}


@app.post("/api/v1/sandbox/{sandbox_id}/repair")
def sandbox_repair(sandbox_id: str, payload: SandboxRepairRequest) -> dict[str, Any]:
    error_message = (payload.error_message or "").strip()
    if not error_message:
        raise HTTPException(status_code=400, detail="error_message is required")
    record = SANDBOX_STORE.get(sandbox_id)
    if not record:
        raise HTTPException(status_code=404, detail="sandbox not found")
    SANDBOX_STORE.update(sandbox_id, status="repairing")

    def worker() -> None:
        try:
            repair_sandbox(sandbox_id, error_message, payload.error_stack or "")
        except Exception as exc:
            SANDBOX_STORE.update(sandbox_id, status="failed", error=str(exc))

    threading.Thread(target=worker, daemon=True).start()
    return {"sandbox_id": sandbox_id, "status": "repairing"}
