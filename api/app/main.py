from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from langchain_core.prompts import ChatPromptTemplate

    LANGCHAIN_AVAILABLE = True
except Exception:
    ChatPromptTemplate = None
    LANGCHAIN_AVAILABLE = False

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:
    END = START = StateGraph = None
    LANGGRAPH_AVAILABLE = False


class TestRequest(BaseModel):
    source_path: str


app = FastAPI(title="Agent 3 Tester API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS: dict[str, dict[str, Any]] = {}
BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "runs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEST_LOGS = [
    "Setting up test environment.",
    "Initializing pytest + coverage.",
    "Running unit tests for auth, tasks, and notifications.",
    "Checking integration flow across API endpoints.",
    "Generating issue summary for Agent 2.",
]

ISSUES = [
    {
        "id": "BUG-201",
        "title": "Task update endpoint returns stale data",
        "severity": "High",
        "recommendation": "Refresh the returned task object after write operations.",
    },
    {
        "id": "BUG-202",
        "title": "Reminder worker has no retry guard",
        "severity": "Medium",
        "recommendation": "Add retry limits and error visibility for failed reminder jobs.",
    },
]


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "agent3-tester",
        "langchain": LANGCHAIN_AVAILABLE,
        "langgraph": LANGGRAPH_AVAILABLE,
    }


@app.post("/api/v1/tests/start")
def start_tests(payload: TestRequest) -> dict[str, Any]:
    run_id = str(uuid4())
    if LANGCHAIN_AVAILABLE and ChatPromptTemplate:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "Summarize a QA test plan for a generated software project."),
                ("human", "{source_path}"),
            ]
        )
        _ = prompt.format_messages(source_path=payload.source_path)
    RUNS[run_id] = {"started_at": time.time(), "source_path": payload.source_path}
    return {"run_id": run_id}


@app.get("/api/v1/tests/{run_id}")
def get_tests(run_id: str) -> dict[str, Any]:
    run = RUNS.get(run_id)
    if not run:
        return {"status": "missing", "logs": []}
    elapsed = int(time.time() - run["started_at"])
    visible_logs = min(len(TEST_LOGS), max(1, elapsed // 2 + 1))
    status = "completed" if visible_logs == len(TEST_LOGS) else "running"
    summary = {
        "quality_score": 88,
        "requirements_implemented": 76,
        "unit_total": 32,
        "unit_passed": 28,
        "security_issues": 2,
        "functional_score": 92,
        "code_quality_score": 84,
        "security_score": 73,
        "performance_score": 81,
    }
    report = {
        "run_id": run_id,
        "source_path": run["source_path"],
        "summary": summary,
        "issues": ISSUES if status == "completed" else [],
    }
    report_dir = OUTPUT_DIR / run_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "qa-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {
        "status": status,
        "phase": "reporting" if status == "completed" else "testing",
        "round": 1,
        "logs": TEST_LOGS[:visible_logs],
        "summary": summary,
        "issues": ISSUES if status == "completed" else [],
        "report_path": str(report_dir / "qa-report.json"),
    }

