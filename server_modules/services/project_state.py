"""Durable, bounded project/agent state. No browser is required to retain a run."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

SERVER_ID = uuid.uuid4().hex
ROLES = ("designer", "developer")
_LOCK = threading.RLock()
MAX_EVENTS = 1200


def atomic_json(path: Path, body) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(body, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {} if default is None else default


class ProjectState:
    def __init__(self, project: Path):
        self.project = Path(project).resolve()
        self.directory = self.project / ".agentforge"
        self.path = self.directory / "workflow.json"

    def read(self) -> dict:
        with _LOCK:
            state = read_json(self.path)
            state.setdefault("project", self.project.name)
            state.setdefault("agents", {})
            for agent in state["agents"].values():
                if agent.get("status") in ("running", "queued", "finishing") and agent.get("server_id") != SERVER_ID:
                    agent["status"] = "interrupted"
            return state

    def update(self, **patch) -> dict:
        with _LOCK:
            state = self.read()
            state.update(patch, updated_at=time.time())
            atomic_json(self.path, state)
            return state

    def agent(self, role: str, **patch) -> dict:
        if role not in ROLES:
            raise ValueError("Unknown agent role")
        if patch.get("status") in ("running", "queued", "finishing"):
            patch.setdefault("server_id", SERVER_ID)
        with _LOCK:
            state = self.read()
            prior = state["agents"].get(role, {})
            state["agents"][role] = {**prior, **patch, "updated_at": time.time()}
            return self.update(**state)

    def start(self, role: str, request: dict, owner: str = "") -> str:
        run_id = uuid.uuid4().hex
        self.agent(role, status="running", run_id=run_id, request=request,
                   owner=owner, server_id=SERVER_ID, error="")
        return run_id

    def record(self, message: dict) -> dict:
        """Append meaningful stream events; never persist image frames or token fragments."""
        role = message.get("agent", "developer")
        if role not in ROLES or message.get("type") in ("stream", "browser_frame", "runtime_state"):
            return message
        with _LOCK:
            path = self.directory / "agents" / role / "events.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            event = {**message, "event_id": uuid.uuid4().hex, "at": time.time() * 1000}
            # Source is read from the project; duplicating it in the journal wastes memory.
            event.pop("content", None)
            with path.open("a", encoding="utf-8") as stream:
                stream.write("\n" + json.dumps(event, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            if path.stat().st_size > 2_000_000:
                events = self.events(role)
                temporary = path.with_suffix(".tmp")
                temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in events), encoding="utf-8")
                temporary.replace(path)
            return {**message, "event_id": event["event_id"], "at": event["at"]}

    def events(self, role: str) -> list:
        if role not in ROLES:
            raise ValueError("Unknown agent role")
        from collections import deque
        path = self.directory / "agents" / role / "events.jsonl"
        with _LOCK:
            try:
                with path.open(encoding="utf-8") as stream:
                    lines = deque((line for line in stream if line.strip()), maxlen=MAX_EVENTS)
            except FileNotFoundError:
                return []
            events = []
            for line in lines:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    # A hard shutdown may leave one incomplete append at the end.
                    continue
            return events

    def snapshot(self) -> dict:
        with _LOCK:
            return {**self.read(), "events": {role: self.events(role) for role in ROLES}, "updated_at": time.time()}
