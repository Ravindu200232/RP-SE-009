"""Agent 3 Tester API - real unit-test generation + execution."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import generator, runner
from .graph import build_execution_graph, build_generation_graph, build_scan_graph
from .models import (
    DiscoveredFile,
    GenerateRequest,
    GeneratedTest,
    HealthResponse,
    RunRequest,
    RunStatus,
    ScanResult,
)

try:
    import langchain  # noqa: F401

    LANGCHAIN_AVAILABLE = True
except Exception:
    LANGCHAIN_AVAILABLE = False

try:
    import langgraph  # noqa: F401

    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False


app = FastAPI(title="Agent 3 Tester API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parents[1]
RUNS_DIR = BASE_DIR / "runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_sample_dir() -> Path:
    """Return the bundled sample-apps folder.

    We look for any sibling of /api that contains a workspace package.json.
    This way the user can rename the folder ("sample-apps", "food order backend",
    "my-mern-app", whatever) and the dropdown still works.
    Override via AGENT3_SAMPLE_DIR env var if you want to pin one location.
    """
    import os as _os

    pinned = _os.environ.get("AGENT3_SAMPLE_DIR")
    if pinned:
        p = Path(pinned).expanduser().resolve()
        if p.is_dir():
            return p

    parent = BASE_DIR.parent
    candidates = [parent / "sample-apps"]
    if parent.is_dir():
        for child in sorted(parent.iterdir()):
            if not child.is_dir():
                continue
            if child.name in {"api", "frontend", "runs", ".git"}:
                continue
            pkg = child / "package.json"
            if pkg.is_file():
                candidates.append(child)
    for c in candidates:
        if c.is_dir():
            return c
    return parent / "sample-apps"


SAMPLE_DIR = _resolve_sample_dir()

RUNS: dict[str, RunStatus] = {}
_lock = threading.Lock()

GEN_GRAPH = build_generation_graph()
SCAN_GRAPH = build_scan_graph()
RUN_GRAPH = build_execution_graph()


def _persist(run: RunStatus) -> None:
    out = RUNS_DIR / run.run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "status.json").write_text(run.model_dump_json(indent=2), encoding="utf-8")


def _set(run_id: str, **fields: Any) -> None:
    with _lock:
        run = RUNS[run_id]
        for key, value in fields.items():
            setattr(run, key, value)
        _persist(run)


# ── Routes ──────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        service="agent3-tester",
        langchain=LANGCHAIN_AVAILABLE,
        langgraph=LANGGRAPH_AVAILABLE,
        llm_provider=generator.llm_provider(),
        node_available=runner.node_available(),
    )


@app.get("/api/v1/sample-apps")
def list_sample_apps() -> dict[str, Any]:
    """Return sample apps that ship with this repo so the frontend can offer one-click selection."""
    if not SAMPLE_DIR.is_dir():
        return {"root": str(SAMPLE_DIR), "services": []}
    services = []
    for child in sorted(SAMPLE_DIR.iterdir()):
        if (child / "package.json").is_file():
            services.append({"name": child.name, "path": str(child)})
    return {"root": str(SAMPLE_DIR), "services": services}


@app.post("/api/v1/scan", response_model=ScanResult)
def scan(payload: GenerateRequest) -> ScanResult:
    """Read-only preview - discovers services and counts functions, no files written."""
    started = time.time()
    state = SCAN_GRAPH.invoke({"source_path": payload.source_path, "logs": []})
    if state.get("error"):
        raise HTTPException(status_code=400, detail=state["error"])
    return ScanResult(
        root=payload.source_path,
        services=state.get("service_infos", []),
        files=state.get("discovered", []),
        total_services=len(state.get("services", [])),
        total_files=len(state.get("discovered", [])),
        total_functions=sum(s.function_count for s in state.get("service_infos", [])),
        duration_ms=(time.time() - started) * 1000.0,
    )


@app.post("/api/v1/unit-test/generate")
def generate_tests(payload: GenerateRequest) -> dict[str, Any]:
    run_id = uuid4().hex[:12]
    run = RunStatus(
        run_id=run_id,
        phase="generate.discover",
        status="pending",
        logs=[f"received generate request for {payload.source_path}"],
        started_at=time.time(),
    )
    with _lock:
        RUNS[run_id] = run
        _persist(run)

    def worker() -> None:
        _set(run_id, status="running", phase="generate.discover")
        try:
            state = GEN_GRAPH.invoke(
                {
                    "source_path": payload.source_path,
                    "overwrite": payload.overwrite,
                    "logs": [],
                }
            )
        except Exception as exc:
            _set(run_id, status="failed", phase="generate.error", error=str(exc), finished_at=time.time())
            return

        logs = list(RUNS[run_id].logs) + state.get("logs", [])
        if state.get("error"):
            _set(
                run_id,
                status="failed",
                phase="generate.error",
                error=state["error"],
                logs=logs,
                discovered=state.get("discovered", []),
                generated=state.get("generated", []),
                used_llm=state.get("used_llm", False),
                finished_at=time.time(),
            )
            return

        _set(
            run_id,
            status="completed",
            phase="generate.done",
            logs=logs,
            discovered=state.get("discovered", []),
            generated=state.get("generated", []),
            used_llm=state.get("used_llm", False),
            finished_at=time.time(),
        )

    threading.Thread(target=worker, daemon=True).start()
    return {"run_id": run_id}


@app.post("/api/v1/unit-test/run")
def run_tests(payload: RunRequest) -> dict[str, Any]:
    if not runner.node_available():
        raise HTTPException(status_code=400, detail="node/npm not found on PATH on the API host")

    run_id = uuid4().hex[:12]
    run = RunStatus(
        run_id=run_id,
        phase="run.resolve",
        status="pending",
        logs=[f"received run request for {payload.source_path}"],
        started_at=time.time(),
    )
    with _lock:
        RUNS[run_id] = run
        _persist(run)

    def worker() -> None:
        _set(run_id, status="running", phase="run.installing")
        try:
            state = RUN_GRAPH.invoke(
                {
                    "source_path": payload.source_path,
                    "install": payload.install,
                    "logs": [],
                }
            )
        except Exception as exc:
            _set(run_id, status="failed", phase="run.error", error=str(exc), finished_at=time.time())
            return

        logs = list(RUNS[run_id].logs) + state.get("logs", [])
        if state.get("error"):
            _set(
                run_id,
                status="failed",
                phase="run.error",
                error=state["error"],
                logs=logs,
                summary=state.get("summary"),
                finished_at=time.time(),
            )
            return

        _set(
            run_id,
            status="completed",
            phase="run.done",
            logs=logs,
            summary=state.get("summary"),
            finished_at=time.time(),
        )

    threading.Thread(target=worker, daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/v1/runs/{run_id}", response_model=RunStatus)
def get_run(run_id: str) -> RunStatus:
    with _lock:
        run = RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/api/v1/runs")
def list_runs() -> dict[str, Any]:
    with _lock:
        return {
            "runs": [
                {
                    "run_id": r.run_id,
                    "phase": r.phase,
                    "status": r.status,
                    "started_at": r.started_at,
                    "finished_at": r.finished_at,
                }
                for r in RUNS.values()
            ]
        }


# ── Legacy endpoints (kept for compatibility with older orchestration code) ─
@app.post("/api/v1/tests/start")
def legacy_start(payload: dict[str, Any]) -> dict[str, Any]:
    source_path = payload.get("source_path", "")
    return generate_tests(GenerateRequest(source_path=source_path))


@app.get("/api/v1/tests/{run_id}")
def legacy_get(run_id: str) -> dict[str, Any]:
    run = RUNS.get(run_id)
    if not run:
        return {"status": "missing", "logs": []}
    return json.loads(run.model_dump_json())
