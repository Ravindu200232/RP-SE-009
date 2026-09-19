"""Long POSTs, made short."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextvars import ContextVar
from weakref import WeakValueDictionary

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("srs.jobs")

router = APIRouter(prefix="/jobs", tags=["agentforge"])


_JOBS: dict[str, dict] = {}


_KEEP_FINISHED_S = 900
_MAX_JOBS = 200

_app = None
_TASKS = {}
CURRENT_JOB = ContextVar("srs_job", default="")
_PROJECT_LOCKS = WeakValueDictionary()


def _job_path(job_id):
    from .app.config import settings
    return settings.storage_path / ".jobs" / f"{job_id}.json"


def _save(job_id):
    from .app.services.storage import write_json
    write_json(_job_path(job_id), _JOBS[job_id])


async def recover():
    import json
    from .app.config import settings
    root = settings.storage_path / ".jobs"
    for path in root.glob("job_*.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
            if job.get("finished") and time.time() - job["finished"] > _KEEP_FINISHED_S:
                path.unlink()
                continue
            _JOBS[path.stem] = job
            if job.get("status") == "running" and job.get("request"):
                _TASKS[path.stem] = asyncio.create_task(_run(path.stem, JobRequest(**job["request"])))
        except (OSError, ValueError) as error:
            log.warning("Could not recover job %s: %s", path.name, error)


class JobRequest(BaseModel):
    path: str
    method: str = "POST"
    body: dict | None = None


def attach(app) -> None:
    """Mount the job routes onto the SRS app and remember it for replay."""
    global _app
    _app = app
    app.include_router(router)


def _reap() -> None:
    done = [(j["finished"], jid) for jid, j in _JOBS.items() if j.get("finished")]
    now = time.time()
    for finished, jid in done:
        if now - finished > _KEEP_FINISHED_S:
            _JOBS.pop(jid, None)
            _job_path(jid).unlink(missing_ok=True)
    if len(_JOBS) > _MAX_JOBS:
        for _, jid in sorted(done)[:len(_JOBS) - _MAX_JOBS]:
            _JOBS.pop(jid, None)
            _job_path(jid).unlink(missing_ok=True)


async def _run(job_id: str, req: JobRequest) -> None:
    import httpx

    job = _JOBS[job_id]
    token = CURRENT_JOB.set(job_id)
    try:
        key = "/".join(req.path.split("/")[:3])
        lock = _PROJECT_LOCKS.setdefault(key, asyncio.Lock())
        transport = httpx.ASGITransport(app=_app)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://srs",
                                     timeout=None) as client:
            async with lock:
                r = await client.request(req.method, req.path, json=req.body or {})
        job["http_status"] = r.status_code
        try:
            job["result"] = r.json()
        except Exception:
            job["result"] = {"text": r.text}

        job["status"] = "done"
    except asyncio.CancelledError:
        # Shutdown is a checkpoint, not a completed request. Replay on startup.
        job["status"] = "running"
        raise
    except Exception as e:                                  # noqa: BLE001
        job["status"] = "error"
        job["error"] = f"{type(e).__name__}: {e}"
        log.warning(f"job {job_id} ({req.path}) failed: {job['error']}")
    finally:
        if job["status"] != "running":
            job["finished"] = time.time()
            job.pop("request", None)
        _save(job_id)
        _TASKS.pop(job_id, None)
        CURRENT_JOB.reset(token)


@router.post("")
async def start_job(req: JobRequest):
    """Begin the work and answer immediately."""
    if _app is None:
        raise HTTPException(503, "job runner is not attached")
    if not req.path.startswith("/"):
        raise HTTPException(400, "path must be absolute")

    if req.path.startswith("/jobs"):
        raise HTTPException(400, "jobs cannot run jobs")
    if req.path.endswith("/integrations"):
        raise HTTPException(400, "Submit credentials directly to the integrations endpoint")

    _reap()
    request = req.model_dump()
    for job_id, job in _JOBS.items():
        if job.get("status") == "running" and job.get("request") == request:
            return {"job_id": job_id, "status": "running", "path": req.path}
    if sum(job.get("status") == "running" for job in _JOBS.values()) >= _MAX_JOBS:
        raise HTTPException(429, "Too many pending jobs. Wait for an existing job to finish.")
    job_id = "job_" + uuid.uuid4().hex[:20]
    _JOBS[job_id] = {"status": "running", "path": req.path,
                     "started": time.time(), "finished": None,
                     "http_status": None, "result": None, "error": "", "request": request}
    _save(job_id)
    _TASKS[job_id] = asyncio.create_task(_run(job_id, req))
    return {"job_id": job_id, "status": "running", "path": req.path}


@router.get("/{job_id}")
async def poll_job(job_id: str):
    job = _JOBS.get(job_id)
    if job is None:

        raise HTTPException(404, "no such job (it may have expired)")
    elapsed = (job.get("finished") or time.time()) - job["started"]
    return {"job_id": job_id, **{k: v for k, v in job.items() if k != "request"}, "elapsed": round(elapsed, 1)}
