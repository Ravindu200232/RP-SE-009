from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from . import state
from .common import now_iso, resolve_existing, summarize_upload
from .config import DATASET_CANDIDATES, TEMPLATE_CANDIDATES, VOICE_NOTE_MARKER
from .orchestrator import build_agent_message, model_config, planner_name
from .question_maker import build_question_plan, missing_interview_questions
from .schemas import AnswersRequest, MessageRequest, SessionCreate
from .session_service import (
    create_session_state,
    finalize_session,
    persist_session,
    require_session,
    serialize_session,
    session_dir,
)
from .srs_generator import build_srs, build_stack


app = FastAPI(title="Agent 1 SRS API", version="0.4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "agent1-srs",
        "template_found": resolve_existing(TEMPLATE_CANDIDATES) is not None,
        "dataset_found": resolve_existing(DATASET_CANDIDATES) is not None,
        "planner": planner_name(),
        "models": model_config(),
    }


@app.post("/api/v1/sessions")
def create_session(payload: SessionCreate) -> dict[str, str]:
    session_id = str(uuid4())
    state.SESSIONS[session_id] = create_session_state(session_id, payload)
    persist_session(session_id, state.SESSIONS[session_id])
    return {"session_id": session_id, "project_name": state.SESSIONS[session_id]["project_name"]}


@app.get("/api/v1/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, object]:
    return serialize_session(session_id, require_session(session_id))


@app.post("/api/v1/sessions/{session_id}/intake")
async def intake(
    session_id: str,
    message: str = Form(""),
    browser_transcript: str = Form(""),
    files: list[UploadFile] = File(default=[]),
) -> dict[str, object]:
    session = require_session(session_id)
    combined = (message or "").strip()
    if browser_transcript.strip():
        combined = f"{combined}\n\n{VOICE_NOTE_MARKER}\n{browser_transcript.strip()}".strip()
    if not combined and not files:
        raise HTTPException(status_code=400, detail="Provide a text idea, a voice transcript, or at least one file.")

    for file in files:
        session["uploads"].append(summarize_upload(file, await file.read()))

    if combined:
        session["idea"] = session["idea"] or combined
        session["messages"].append({"role": "user", "content": combined, "created_at": now_iso()})

    session["question_plan"] = build_question_plan(session)
    session["analysis_summary"] = session["question_plan"]["summary"]
    session["recommended_stack"] = build_stack(session)
    session["draft_srs"] = build_srs(session, False)
    session["diagram_previews"] = session["draft_srs"].get("diagram_previews", [])
    session["status"] = "awaiting_answers"
    session["messages"].append({"role": "agent", "content": build_agent_message(session, "intake"), "created_at": now_iso()})
    persist_session(session_id, session)
    return {
        "reply": session["messages"][-1]["content"],
        "analysis_summary": session["analysis_summary"],
        "question_plan": session["question_plan"],
        "draft_srs": session["draft_srs"],
        "session": serialize_session(session_id, session),
    }


@app.post("/api/v1/sessions/{session_id}/message")
def send_message(session_id: str, payload: MessageRequest) -> dict[str, object]:
    session = require_session(session_id)
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    session["messages"].append({"role": "user", "content": message, "created_at": now_iso()})
    session["question_plan"] = build_question_plan(session)
    session["analysis_summary"] = session["question_plan"]["summary"]
    session["draft_srs"] = build_srs(session, False)
    session["messages"].append({"role": "agent", "content": build_agent_message(session, "update"), "created_at": now_iso()})
    persist_session(session_id, session)
    return {"reply": session["messages"][-1]["content"], "draft_srs": session["draft_srs"], "session": serialize_session(session_id, session)}


@app.post("/api/v1/sessions/{session_id}/answers")
def submit_answers(session_id: str, payload: AnswersRequest) -> dict[str, object]:
    session = require_session(session_id)
    if not payload.answers:
        raise HTTPException(status_code=400, detail="At least one answer is required")

    session["answers"].update(payload.answers)
    missing = missing_interview_questions(session)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Please answer the remaining {len(missing)} interview question(s) before building the final SRS.",
        )

    serialized = finalize_session(session_id, session)
    return {"reply": "The SRS has been generated and validated.", "srs": session["final_srs"], "validation": session["validation"], "session": serialized}


@app.post("/api/v1/sessions/{session_id}/generate-srs")
def generate_srs(session_id: str) -> dict[str, object]:
    session = require_session(session_id)
    missing = missing_interview_questions(session)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Please answer the remaining {len(missing)} interview question(s) before building the final SRS.",
        )
    serialized = finalize_session(session_id, session)
    return {"srs": session["final_srs"], "validation": session["validation"], "session": serialized}


@app.get("/api/v1/sessions/{session_id}/artifacts/{artifact_name}")
def download_artifact(session_id: str, artifact_name: str) -> Response:
    require_session(session_id)
    file_path = session_dir(session_id) / artifact_name.lower()
    if artifact_name.lower() not in {"srs.json", "srs.pdf"} or not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not ready yet")
    return Response(
        content=file_path.read_bytes(),
        media_type="application/pdf" if artifact_name.lower().endswith(".pdf") else "application/json",
        headers={"Content-Disposition": f'attachment; filename="{file_path.name}"'},
    )
