# Drives the builder and QA agents for the studio.
"""What the studio's buttons actually do.

Deliberately thin. There is no stage machine here deciding which files to
write or which tests to run - that is the agent's job, and hard-coding it was
what made the previous version brittle. This resolves a project directory,
hands the agent a brief, and translates what comes back.

Four entry points, one shape: build, resume, feature, repair. Each one prepares
the workspace, runs Builder's code pass, brings the app up, then hands the
live preview to the independent QA pipeline.
"""

import re
import shutil
import threading
import time
import uuid
from pathlib import Path

_BUILDER_ROOT = str(BASE_DIR / "builder-agent")
_QA_ROOT = str(BASE_DIR / "qa-agent")
for _root in (_BUILDER_ROOT, _QA_ROOT):
    if _root not in sys.path:
        sys.path.insert(0, _root)

from builder_agent import BuilderAgent, Config, Events, detect_stack, stack_of  # noqa: E402
from builder_agent.templates import restore_styling  # noqa: E402
from builder_agent.designer import DesignerAgent
from builder_agent.sandbox import Sandbox
from server_modules.services.project_state import ProjectState, atomic_json

from server_modules.services.mongo_common import db_name_for  # noqa: E402

# StudioBridge, fill_missing_images, and emit helpers are injected into the shared runtime namespace.

BUILD_PHASES = ("build",)
EDIT_PHASES = ("build",)

# Files worth snapshotting before an edit so a single click can undo it.
UNDO_EXT = {".js", ".jsx", ".ts", ".tsx", ".css", ".json", ".md", ".html", ".svg"}
UNDO_SKIP = {"node_modules", ".next", ".git", ".agentforge", ".agent", "coverage"}
UNDO_KEEP = 12


# --------------------------------------------------------------------------
# Project naming and setup
# --------------------------------------------------------------------------
_STOPWORDS = {"a", "an", "the", "and", "for", "with", "build", "make", "create",
              "app", "application", "website", "site", "me", "my", "please",
              "generate", "using", "that", "this", "system", "simple", "full"}


def project_name_for(prompt: str) -> str:
    """A short, stable folder name taken from what the user asked for."""
    words = [w for w in re.findall(r"[a-z0-9]+", str(prompt or "").lower())
             if w not in _STOPWORDS and len(w) > 2]
    stem = "".join(words[:3])[:20] or "app"
    candidate, suffix = stem, 2
    while (PROD_DIR / candidate).exists():
        candidate = f"{stem}{suffix}"
        suffix += 1
    return candidate


def _write_env(proj_dir: Path) -> None:
    """Give the app its database connection and its plugins' settings.

    A generated app that has to invent its own connection string either
    hard-codes one or guesses a database name that collides with the last
    project's collections. Writing it here makes both impossible.

    The plugin settings arrive the same way and for the same reason. They
    belong to the person, not to this project, so they are kept once against
    their account and written in here every time the workspace is prepared -
    which means ticking Supabase on a project that already exists is enough,
    with no rebuild and nothing to paste again.
    """
    target = proj_dir / ".env.local"
    wanted = f"MONGODB_URI={MONGO.uri_for(proj_dir.name)}"
    try:
        existing = target.read_text("utf-8") if target.is_file() else ""
        if "MONGODB_URI=" not in existing:
            target.write_text((existing + "\n" if existing.strip() else "") + wanted + "\n",
                              encoding="utf-8")
    except OSError as error:
        elog("WARN", f"   ⚠ .env.local could not be written: {error}")
    _write_plugin_env(proj_dir)


def _adopt_plugins(proj_dir: Path, plugin_ids) -> None:
    """Record the build screen's picks on the new workspace, then fill its env."""
    try:
        from server_modules.builder.plugins import set_enabled
        chosen = set_enabled(proj_dir, list(plugin_ids))
        if chosen:
            elog("INFO", f"   plugins for this app: {', '.join(chosen)}")
        _write_plugin_env(proj_dir)
    except Exception as error:                                       # noqa: BLE001
        elog("WARN", f"   plugin choices were not applied: {error}")


def _write_plugin_env(proj_dir: Path) -> None:
    """Merge in whatever this project's ticked plugins contribute.

    Names only in the log. A value that reaches a log line reaches the saved
    stream and the transcript, which is every place a key must not be. The
    agent never sees one either: its file tools refuse every `.env*` path but
    `.env.example`, so the model reads them from `process.env` at run time.
    """
    try:
        from server_modules.builder.plugins import enabled_for, env_for
        if not enabled_for(proj_dir):
            return
        values = env_for((acting() or {}).get("id", ""), proj_dir)
        if not values:
            return
        from builder_agent.setup import merge_env
        merge_env(proj_dir / ".env.local", values)
        elog("INFO", f"   plugins configured: {', '.join(sorted(values))}")
    except Exception as error:                                       # noqa: BLE001
        elog("WARN", f"   plugin settings were not written: {error}")


def _prepare_workspace(prompt: str, project: str, srs_id: str) -> Path:
    if project:
        _, proj_dir, error = _owned_dir(PROD_DIR, project, "project name", "project")
        if error:
            raise ValueError(error)
        _write_env(proj_dir)
        if srs_id:
            if not adopt_srs(srs_id, proj_dir):
                raise RuntimeError("Could not load the approved specification")
            _adopt_customer_assets(srs_id, proj_dir)
        return proj_dir
    # Use the project name from the approved SRS rather than the design prompt.
    name = project_name_for(_srs_app_name(srs_id) or prompt)
    proj_dir = PROD_DIR / name
    proj_dir.mkdir(parents=True, exist_ok=True)
    # Its builder's from the moment it exists - decided here, by the server,
    # not by whichever studio happens to hear that it was made.
    if not claim_project(name):
        raise RuntimeError(f"{name} was taken by someone else a moment ago - start the build again")
    _write_env(proj_dir)
    eproject(name)
    if srs_id:
        if not adopt_srs(srs_id, proj_dir):
            raise RuntimeError("Could not load the approved specification")
        _adopt_customer_assets(srs_id, proj_dir)
    return proj_dir


def _adopt_customer_assets(srs_id: str, proj_dir: Path) -> None:
    """Pictures and page layouts chosen before this folder existed.

    Both are decided on screens that run between an approved specification and
    the first build, so they wait beside the specification until there is a
    project to belong to. Re-adopted on every run, not only the first: a
    wireframe edited after the build, or a picture added later, is otherwise
    invisible to every run but the one that created the folder.
    """
    adopt_site_images(srs_id, proj_dir)
    adopt_wireframes(srs_id, proj_dir)


def _brief(proj_dir: Path, prompt: str, model: str = "") -> str:
    """The request, plus whatever the approved specification already settled."""
    # Prioritize the customer's chosen SRS name when available.
    parts = [_srs_name_line(proj_dir) + prompt.strip()]
    try:
        spec = _srs_brief(proj_dir, model)
    except Exception:                                                # noqa: BLE001
        spec = ""
    if spec:
        parts += ["", "APPROVED SPECIFICATION (build to this):", spec]
    # Provide an isolated per-project database URI via environment variables.
    if getattr(RUN, "agent", "") != "designer" and not _prototype_only(proj_dir):
        parts += ["", f"This project's database is "
                      f"`{db_name_for(proj_dir.name)}`. Read the connection string from "
                      "MONGODB_URI in the environment; never hard-code one."]
    # Stage customer-supplied images into public assets before briefing the agent.
    try:
        publish_site_images(proj_dir)
        pictures = site_images_brief(proj_dir)
    except Exception:                                                # noqa: BLE001
        pictures = ""
    if pictures:
        parts += ["", pictures.strip()]
    # Provide the approved wireframe layout structure for the drawing pass.
    try:
        layouts = wireframe_brief(proj_dir)
    except Exception:                                                # noqa: BLE001
        layouts = ""
    if layouts:
        parts += ["", layouts.strip()]
    return "\n".join(parts)


# Timeout for awaiting user answers in the studio before continuing with defaults.
GATE_TIMEOUT = 600


# Build-time setup questions for skills requiring credentials once workspace exists.
BUILD_GATES = ("setup",)


def _config(proj_dir: Path, prompt: str, model: str, think, gates=BUILD_GATES,
            stack: str = "", prototype_only: bool = False) -> Config:
    # A stack chosen in the studio is a decision; reading it out of the wording
    # of the brief is a guess, and only the fallback.
    return Config(workspace=proj_dir, model=model or default_agent_model(),
                  host=ollama.host, stack=stack or detect_stack(prompt),
                  think=bool(think), prototype_only=bool(prototype_only),
                  extra={"gates": gates, "gate_timeout": GATE_TIMEOUT})


def _cancelled() -> bool:
    try:
        cancel.check()
        return False
    except cancel.BuildCancelled:
        return True


# --------------------------------------------------------------------------
# Answering a question the run asked
# --------------------------------------------------------------------------
# Track active agent runs so HTTP request handlers can route answers back to them.
_LIVE_APPROVALS = []
_APPROVALS_LOCK = threading.Lock()


def register_approvals(approvals) -> None:
    with _APPROVALS_LOCK:
        _LIVE_APPROVALS.append(approvals)


def forget_approvals(approvals) -> None:
    with _APPROVALS_LOCK:
        if approvals in _LIVE_APPROVALS:
            _LIVE_APPROVALS.remove(approvals)


def resolve_decision(decision_id: str, answer: dict) -> dict:
    """Hand one answer to whichever run is waiting for it."""
    with _APPROVALS_LOCK:
        registries = list(_LIVE_APPROVALS)
    for approvals in registries:
        if approvals.resolve(decision_id, answer):
            return {"ok": True}
    return {"error": "that question is no longer waiting for an answer"}


def pending_decisions() -> list:
    with _APPROVALS_LOCK:
        return [row for approvals in _LIVE_APPROVALS for row in approvals.list()]


# --------------------------------------------------------------------------
# Undo
# --------------------------------------------------------------------------
def snapshot_project(proj_dir: Path, role: str = "developer") -> dict:
    """Copy the source files before an edit so one click can put them back."""
    snap_id = uuid.uuid4().hex[:10]
    store = proj_dir / ".agentforge" / "undo" / snap_id
    source = proj_dir / ".agentforge" / "prototype" if role == "designer" else proj_dir
    sandbox = Sandbox(proj_dir, role=role)
    files = []
    for path in sandbox.walk(source):
        if not path.is_file() or path.suffix not in UNDO_EXT:
            continue
        relative = path.relative_to(proj_dir)
        if any(part in UNDO_SKIP for part in path.relative_to(source).parts):
            continue
        try:
            sandbox.check_access(sandbox.resolve(str(path)), write=True)
        except Exception:
            continue
        target = store / "files" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, target)
            files.append(relative.as_posix())
        except OSError:
            continue
        if len(files) > 400:
            break
    atomic_json(store / "snapshot.json", {"agent": role, "files": files})
    _trim_undo(proj_dir)
    emit({"type": "undo_point", "id": snap_id, "files": files[:20], "agent": role})
    return {"id": snap_id, "files": files}


def _record_change(proj_dir: Path, snapshot_id: str, role: str) -> None:
    """Leave what this run changed on disk for the transaction that follows it.

    The snapshot taken before the edit is the only record of what the project
    looked like beforehand, and it is deleted twelve edits later, so the
    comparison is made here while both halves still exist.
    """
    try:
        from server_modules.services import change_set
        change_set.write(proj_dir, role,
                         change_set.capture(proj_dir, snapshot_id, role))
    except Exception as error:                                       # noqa: BLE001
        log.debug(f"change set for {role}: {error}")


def _trim_undo(proj_dir: Path) -> None:
    base = proj_dir / ".agentforge" / "undo"
    snaps = sorted((p for p in base.iterdir() if p.is_dir()),
                   key=lambda p: p.stat().st_mtime) if base.is_dir() else []
    for stale in snaps[:-UNDO_KEEP]:
        shutil.rmtree(stale, ignore_errors=True)


def restore_snapshot(project: str, snap_id: str) -> dict:
    # Undo writes files back, so it is told which project as strictly as a run.
    name, proj_dir, error = _owned_dir(PROD_DIR, project, "project name", "project")
    if error:
        return {"error": error}
    if not re.fullmatch(r"[a-f0-9]{10}", str(snap_id or "")):
        return {"error": "Invalid undo point"}
    store = proj_dir / ".agentforge" / "undo" / snap_id
    if not store.is_dir():
        return {"error": "that undo point is no longer available"}
    metadata = store / "snapshot.json"
    body = json.loads(metadata.read_text(encoding="utf-8")) if metadata.is_file() else {}
    role = body.get("agent", "developer")
    sandbox = Sandbox(proj_dir, role=role)
    restored = []
    source = store / "files" if metadata.is_file() else store
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        if path == metadata:
            continue
        relative = path.relative_to(source)
        target = sandbox.resolve(relative.as_posix())
        sandbox.check_access(target, write=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        restored.append(relative.as_posix())
        emit({"type": "file", "project": name, "agent": role, "name": relative.as_posix(),
              "size": target.stat().st_size, "content": target.read_text("utf-8", errors="replace")})
    return {"ok": True, "restored": restored}


# --------------------------------------------------------------------------
# The runs
# --------------------------------------------------------------------------
# Maintain one persistent agent instance per project across conversation turns.
_SESSIONS: dict[str, dict] = {}
_SESSIONS_LOCK = threading.Lock()


def _session_key(model: str, think, stack: str) -> tuple:
    """What makes a conversation a different one.

    Only the stack. Switching model or turning thinking on does not make what
    was already said untrue - the transcript, the evidence and the context
    belong to the project, and throwing them away because someone picked a
    different model is exactly the reset this was built to stop. Those two are
    applied to the conversation that is already running.
    """
    return (str(stack or ""),)


def forget_session(project: str, role: str = "") -> None:
    """Drop the conversation about a project that is closing or gone."""
    with _SESSIONS_LOCK:
        keys = [key for key in _SESSIONS if key == project or
                (isinstance(key, tuple) and key[0] == project and (not role or key[1] == role))]
        sessions = [_SESSIONS.pop(key) for key in keys]
    for session in sessions:
        try:
            if hasattr(session["agent"], "config"):
                save_conversation(PROD_DIR / project, session["agent"])
        except Exception as error:
            log.warning("Could not checkpoint session: %s", error)
        try:
            session["agent"].dispose()
        except Exception as error:                                   # noqa: BLE001
            log.debug(f"disposing the session for {project}: {error}")


# What one project's conversation cost, kept with the project rather than in
# the process that happened to run it.
STATS_FILE = ".agentforge/agents/developer/stats.json"
CONVERSATION_FILE = ".agentforge/agents/developer/conversation.json"


def project_stack(proj_dir: Path, fallback: str = "") -> str:
    detected = stack_of(proj_dir)
    if detected:
        return detected
    state = ProjectState(proj_dir).read()
    for role in ("developer", "designer"):
        selected = state.get("agents", {}).get(role, {}).get("request", {}).get("stack")
        if selected:
            return selected
    return fallback

# And what it said. A browser tab is not a record: reload it, or open the
# project tomorrow, and everything the run reported was gone.
STREAM_FILE = ".agentforge/stream.json"
STREAM_LOGS = 1500
STREAM_TURNS = 300


def read_stream(project: str) -> dict:
    """The account of what has happened to this project so far."""
    try:
        data = json.loads((PROD_DIR / str(project or "") / STREAM_FILE)
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {"logs": list(data.get("logs") or [])[-STREAM_LOGS:],
            "chat": list(data.get("chat") or [])[-STREAM_TURNS:]}


def write_stream(project: str, logs, chat) -> dict:
    """Keep the newest of it. A stream is a record, not an archive."""
    name, proj_dir, error = _owned_dir(PROD_DIR, project, "project name", "project")
    if error:
        return {"error": error}
    body = {"logs": list(logs or [])[-STREAM_LOGS:],
            "chat": list(chat or [])[-STREAM_TURNS:]}
    try:
        path = proj_dir / STREAM_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body), encoding="utf-8")
    except OSError as write_error:
        return {"error": str(write_error)}
    return {"ok": True, "logs": len(body["logs"]), "chat": len(body["chat"])}


def save_session_stats(proj_dir: Path, agent) -> None:
    """Write down what this run spent, so the project can say so later."""
    stats = _measure(agent)
    if not stats:
        return
    try:
        role = getattr(agent.config, "extra", {}).get("agent_role", "developer")
        path = Path(proj_dir) / ".agentforge" / "agents" / role / "stats.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    except OSError as error:
        log.debug(f"saving the session for {proj_dir.name}: {error}")


def save_conversation(proj_dir: Path, agent) -> None:
    """Persist the transcript itself, including its compacted memory."""
    role = agent.config.extra.get("agent_role", "developer")
    path = Path(proj_dir) / ".agentforge" / "agents" / role / "conversation.json"
    temporary = path.with_name(f"conversation-{uuid.uuid4().hex}.tmp")
    try:
        body = {"workspace": str(Path(proj_dir).resolve()), "stack": agent.config.stack,
                "memory": agent.memory.serialize(), "plan": agent.plan_text,
                "design": agent.design, "usage": dict(agent.router.usage), "agent": role}
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(path, body)
    except OSError as error:
        elog("WARN", f"Could not save the conversation for {proj_dir.name}: {error}")
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _prune_designer_memory(memory) -> None:
    """Evict zombie large file reads from previous designer sessions to save tokens and eliminate delay."""
    try:
        memory.strip_written_bodies()
        memory.evict_superseded()
        total = len(memory.messages)
        cutoff = max(0, total - 10)
        for msg in memory.messages[:cutoff]:
            meta = msg.get("meta", {})
            if meta.get("kind") == "tool-result" and meta.get("tool") in ("readFile", "grepSearch"):
                body = msg.get("content") or ""
                if len(body) > 300:
                    target = (meta.get("args") or {}).get("filePath", "file")
                    msg["content"] = (f"[{len(body)} chars of earlier {meta.get('tool')} on {target} omitted. "
                                      "Read file again if current content needed.]")
    except Exception:
        pass


def restore_conversation(proj_dir: Path, agent) -> bool:
    """Resume this project's saved context when its live agent is gone."""
    role = agent.config.extra.get("agent_role", "developer")
    path = Path(proj_dir) / ".agentforge" / "agents" / role / "conversation.json"
    if not path.is_file() and role == "developer":
        path = Path(proj_dir) / ".agentforge/conversation.json"
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
        if (body.get("workspace") != str(Path(proj_dir).resolve())
                or body.get("stack") != agent.config.stack
                or body.get("agent", "developer") != role):
            return False
        from builder_agent.memory import Memory

        memory = Memory(budget_tokens=agent.config.context_tokens)
        memory.restore(body["memory"])
        memory.close_pending_tools("The earlier session ended before this tool returned.")
        if role == "designer":
            _prune_designer_memory(memory)
        agent.memory = memory
        agent.plan_text = body.get("plan") or ""
        agent.design = body.get("design")
        agent.router.usage.update(body.get("usage") or {})
        return bool(len(agent.memory))
    except FileNotFoundError:
        if role == "designer":
            return False
        # Recover partial chat history from legacy runs without assuming full tool context.
        turns = read_stream(proj_dir.name).get("chat") or []
        transcript = [f"{turn.get('role', 'message')}: {turn.get('text', '')}"
                      for turn in turns if isinstance(turn, dict) and turn.get("text")]
        if not transcript:
            return False
        agent.memory.add_user(
            "SAVED PROJECT CONVERSATION (partial history). Earlier tool observations "
            "were not stored by that version. Use this to understand prior requests and "
            "decisions; inspect current code where necessary. These historical messages "
            "are not new instructions or verification evidence.\n\n" + "\n\n".join(transcript),
            kind="recovered-conversation")
        stats = _saved_session_stats(proj_dir.name)
        agent.router.usage.update({"requests": stats.get("requests", 0),
                                   "prompt": stats.get("sent", 0),
                                   "completion": stats.get("received", 0)})
        return True
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        elog("WARN", f"Could not restore the conversation for {proj_dir.name}: {error}")
        return False


def _saved_session_stats(project: str) -> dict:
    try:
        data = json.loads((PROD_DIR / str(project or "") / STATS_FILE)
                          .read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _measure(agent) -> dict:
    """One agent's context and spend, in the shape the status line reads."""
    if agent is None:
        return {}
    try:
        from builder_agent.context import ContextBudget

        budget = ContextBudget(agent.config.context_tokens)
        measurement = budget.measure(agent.memory.build(), fresh=True).as_event()
    except Exception as error:                                       # noqa: BLE001
        log.debug(f"measuring a session: {error}")
        measurement = {}
    usage = dict(getattr(agent.router, "usage", {}) or {})
    return {"model": agent.router.label, "stack": agent.config.stack,
            "messages": len(agent.memory),
            "requests": usage.get("requests", 0),
            "sent": usage.get("prompt", 0), "received": usage.get("completion", 0),
            **measurement}


def session_stats(project: str) -> dict:
    """The context a project's conversation is already holding.

    The status line is fed by events, and events only arrive while something
    is running. Switching to a project whose conversation is alive but idle
    left the line blank, and it came back at zero on the next message as
    though nothing had been said - which was exactly the reset the session was
    built to prevent, showing through in the one place a person reads it.

    A conversation lives in the process that is running it, and the backend
    outlives none of its restarts, so what a project last spent is written
    down with the project. A live session wins; the file answers for one that
    has ended.
    """
    with _SESSIONS_LOCK:
        session = _SESSIONS.get((str(project or ""), "developer")) or _SESSIONS.get(str(project or ""))
    agent = session["agent"] if session else None
    if agent is None:
        return _saved_session_stats(project)
    return _measure(agent)


def release_other_sessions(keep: str) -> list:
    """Let go of every project except this one, and say which were let go.

    A finished run leaves its dev services up so the preview keeps working,
    and only one project is previewed at a time - so every other project's
    services are leftovers holding ports this one is about to want. A Next app
    never noticed, because the single port it uses is freed before it starts.
    A second microservices app found 4101-4103 still taken, every service it
    owned died on startup, and the preview served a gateway with nothing
    behind it.
    """
    with _SESSIONS_LOCK:
        active = (RUN_QUEUE.active() or {}).get("project")
        others = list({name[0] if isinstance(name, tuple) else name for name in _SESSIONS
                       if (name[0] if isinstance(name, tuple) else name) not in (keep, active)})
    for name in others:
        forget_session(name)
    return others


def _agent_for(proj_dir: Path, brief: str, model: str, think, stack: str,
               *, kind: str, phases, plan: bool, prototype_only: bool = False):
    """The agent already talking about this project, or a new one.

    A chat message is the next line of a conversation, not the first line of a
    new one. Keeping the agent alive between messages is what makes "no, the
    other button" mean anything: the transcript, the verification ledger and
    the context window all carry over, and the engine's own compaction is what
    keeps that affordable over a long session.

    An explicitly requested full build starts a fresh conversation. Its first
    follow-up feature continues that build's transcript. A
    change of model or of thinking does not: it is applied to the conversation
    already running, because what was said stays true whoever answers next.
    """
    role = "designer" if prototype_only else "developer"
    name = (proj_dir.name, role)
    key = _session_key(model, think, stack)

    agent = None
    if not plan:
        with _SESSIONS_LOCK:
            session = _SESSIONS.get(name)
        if session and session["key"] == key and session.get("reusable"):
            agent = session["agent"]
            agent.retarget(model, think)
        elif session:
            forget_session(proj_dir.name, role)

    fresh = agent is None
    restored = False
    if fresh:
        forget_session(proj_dir.name, role)
        config = _config(proj_dir, brief, model, think, stack=stack, prototype_only=prototype_only)
        config.extra["agent_role"] = role
        agent = (DesignerAgent if role == "designer" else BuilderAgent)(config, events=Events(), cancel=_cancelled)
        agent.sandbox = Sandbox(proj_dir, role=role)
        if not plan:
            restored = restore_conversation(proj_dir, agent)
    else:
        # The bus is the agent's, but the listeners belong to one run: each has
        # its own phase list and its own report writer.
        agent.events.clear()

    # Allow interactive questions during edits as well as builds.
    agent.approvals.enabled = True
    agent.plan_approval = False
    agent.design_approval = False
    agent.prototype_approval = False

    StudioBridge(agent.events, kind=kind, phases=list(phases),
                 think=bool(getattr(agent.config, "think", False)))
    agent.events.on("checkpoint", lambda _: save_conversation(proj_dir, agent))
    agent.events.on("agent:start", lambda _: save_conversation(proj_dir, agent))
    agent.events.on("agent:done", lambda _: save_conversation(proj_dir, agent))
    # Both a build and an edit leave context for the next chat request.
    with _SESSIONS_LOCK:
        _SESSIONS[name] = {"agent": agent, "key": key, "reusable": True}
    if not fresh or restored:
        elog("INFO", f"   continuing the conversation ({len(agent.memory)} messages so far)")
    runtime = RUNTIMES.get(proj_dir, stack)
    agent.processes.env_provider = lambda service=False: agent_runtime_environment(runtime, agent, service=service)
    agent.processes.spawn_process = spawn_owned
    agent.processes.stop_process = stop_owned
    agent.processes.runtime_info = lambda: agent_runtime_info(runtime)
    return agent


def _run_agent(proj_dir: Path, brief: str, model: str, think, *, phases, kind: str,
               plan: bool = True, stack: str = "", prototype_only: bool = False,
               no_tests: bool = False):
    """One builder-agent run, wired to the studio.

    A full build asks about its plan and its design, because the studio can
    answer. An edit does not: there is no plan to review, and the design was
    settled when the project was built.
    """
    role = "designer" if prototype_only or no_tests else "developer"
    RUN.project = proj_dir.name
    RUN.agent = role
    state = ProjectState(proj_dir)
    RUN.run_id = state.start(role, {"prompt": brief, "model": model, "think": think,
                                   "stack": stack, "prototype_only": role == "designer"},
                             (acting() or {}).get("id", ""))
    agent = _agent_for(proj_dir, brief, model, think, stack,
                       kind=kind, phases=phases, plan=plan,
                       prototype_only=(prototype_only or no_tests))
    if prototype_only:
        agent.config.prototype_only = True
    if no_tests:
        agent.config.unit_tests = False
        agent.config.e2e_tests = False
    register_approvals(agent.approvals)
    emit({"type": "run_state", "project": proj_dir.name, "status": "running"})
    def phase_checkpoint(payload):
        state.agent(role, phase=payload.get("phase", ""))
        save_conversation(proj_dir, agent)
    agent.events.on("phase", phase_checkpoint)
    outcome = None
    try:
        if role == "developer":
            agent.prototype_dir = proj_dir / ".agentforge" / "prototype"
        outcome = agent.run(brief) if role == "designer" or plan else agent.build(brief)
        if outcome.status != "cancelled" and outcome.result:
            echat(outcome.result)
        return agent, outcome
    finally:
        state.agent(role, summary=str(getattr(outcome, "result", ""))[:8000],
                    status="finishing" if outcome and outcome.status == "completed" else
                    "paused" if outcome and outcome.status == "cancelled" else "failed",
                    error="" if outcome and outcome.status == "completed" else str(getattr(outcome, "result", "Run interrupted")))
        forget_approvals(agent.approvals)
        agent._finish()
        save_conversation(proj_dir, agent)
        save_session_stats(proj_dir, agent)


def _workspace(project: str):
    """The project a run may touch, or nothing at all.

    `PROD_DIR / ""` is the directory every project lives in, and it is a
    directory, so the check that a workspace exists passed for a run that had
    been given no project at all. One did: it read the store's git history,
    listed the other projects, and started writing an application into the
    middle of them. A name has to name a project.
    """
    name, resolved, error = _owned_dir(PROD_DIR, project, "project name", "project")
    if error:
        eerr(error)
        return None
    return resolved


def _serve(proj_dir: Path, agent=None) -> str:
    """Transfer this build's processes to its project-owned final preview."""
    estep("preview", "active")
    if agent is not None:
        agent.processes.stop_all()
    stack = stack_of(proj_dir)
    put_back = restore_styling(proj_dir, stack)
    if put_back:
        elog("WARN", f"Restored styling: {', '.join(put_back)}")
        cache = proj_dir / ".next"
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
    runtime = RUNTIMES.get(proj_dir, stack)
    result = RUNTIMES.restart_for_work(runtime, launch_runtime)
    if result["status"] == "running":
        estep("preview", "done")
        return result["previewUrl"]
    estep("preview", "error")
    return ""


def _finish(project: str, url: str, outcome, qa_outcome=None) -> bool:
    if outcome.status != "completed":
        eerr(f"Build {outcome.status}: {outcome.result}")
        return False
    if qa_outcome is not None and not qa_outcome.ok:
        eerr(f"Verification incomplete: {qa_outcome.reason}")
        return False
    if not url:
        eerr("The preview did not become ready. Check the runtime logs.")
        return False
    eprog("Done", 100)
    edone(url, project)
    return True


def run_agent_pipeline(prompt: str, model: str, think=None, qa_model: str = "",
                       project: str = "", logo: str = "", srs_id: str = "",
                       stack: str = "", attachments: str = "",
                       prototype_only: bool = False, plugins=()) -> None:
    """Build an application from a request, then prove it works."""
    started = time.time()
    runtime = None
    cancel.begin()
    try:
        proj_dir = _prepare_workspace(prompt, project, srs_id)
        # Applies build-configured plugins to newly prepared workspaces.
        if plugins:
            _adopt_plugins(proj_dir, plugins)
        name = proj_dir.name
        working_on(name)
        RUN.agent = "designer" if prototype_only else "developer"
        stack = project_stack(proj_dir, stack) or stack
        if not prototype_only and not build_available(proj_dir):
            raise ValueError("Complete the prototype before starting the build")
        if not prototype_only:
            runtime = RUNTIMES.get(proj_dir, stack)
            RUNTIMES.begin_work(runtime)
        cancel.note(project=name, srs_id=srs_id)
        # Treat empty kept projects as initial builds rather than resumptions.
        first = not prompt and (_spec_only(proj_dir) or _prototype_only(proj_dir))
        resuming = bool(project) and not first
        elog("INFO", f"🏗️  {'Resuming' if resuming else 'Building'} {name}")
        estep("prototype" if prototype_only else "build", "active")

        if not prototype_only:
            MONGO.ensure_running()
        saved = ProjectState(proj_dir).read().get("agents", {}).get(RUN.agent, {})
        request = saved.get("request", {}) if not prompt and saved.get("status") in ("interrupted", "paused", "failed") else {}
        brief = request.get("prompt")
        if brief and "APPROVED SPECIFICATION (build to this):" in brief:
            fresh_spec = _srs_brief(proj_dir, model)
            if fresh_spec and len(fresh_spec) > 5000 and len(brief) < len(fresh_spec):
                brief = ""
        if not brief:
            brief = _brief(proj_dir, prompt or (
                "Build this application from the approved prototype and specification below. "
                "Nothing has been written yet." if first else
                "Continue this project: finish whatever is incomplete and "
                "make every verification pass."), model=model)
        if logo:
            brief += f"\n\nA logo has already been generated at {logo}; use it in the header."
        if attachments:
            brief += read_staged_attachments(attachments, proj_dir)
        if not request:
            brief = ("Read the shared .agentforge/handoff/app.md, sitemap.md, prototype.md and builder.md. "
                     "The approved specification is the implementation brief. Do not generate another plan.\n\n" + brief)

        agent, outcome = _run_agent(proj_dir, brief, model, think,
                                    phases=("prototype",) if prototype_only else BUILD_PHASES,
                                    kind="build", stack=stack, plan=False, prototype_only=prototype_only)
        if outcome.status == "cancelled":
            return ecancel({"project": name})

        if prototype_only:
            if outcome.status != "completed":
                return eerr(outcome.result)
            edone(f"/api/prototype/{name}/index.html", name)
            elog("SUCCESS", f"✅ {name} HTML prototype finished in {int(time.time() - started)}s")
            return

        fill_missing_images(proj_dir, "the build")
        # Re-copy public assets now that the application scaffold directory exists.
        publish_site_images(proj_dir)
        url = _serve(proj_dir, agent)
        qa_outcome = run_qa_verification(
            proj_dir=proj_dir, project=name, model=model, qa_model=qa_model,
            think=think, host=ollama.host, cancel=_cancelled,
            memory=agent.memory, preview_url=url)
        if _finish(name, url, outcome, qa_outcome):
            elog("SUCCESS", f"✅ {name} finished in {int(time.time() - started)}s")
    except cancel.BuildCancelled:
        ecancel({"project": project})
    except Exception as error:                                       # noqa: BLE001
        log.exception("agent pipeline")
        eerr(f"{type(error).__name__}: {error}")
    finally:
        if runtime is not None:
            with _SESSIONS_LOCK:
                session = _SESSIONS.get((runtime.project, "developer"))
            if session:
                session["agent"].processes.stop_all()
            RUNTIMES.end_work(runtime)
        cancel.finish()


def _is_html_modification(proj_dir: Path, prompt: str, route: str = "", elements=None, brief: str = "") -> bool:
    """Determine if an edit targets HTML prototypes or static HTML rather than full app code."""
    if route == "/__builder":
        return False
    if _prototype_only(proj_dir):
        return True
    route_str = str(route or "").lower()
    if "/api/prototype" in route_str or route_str.startswith("/prototype") or route_str.endswith(".html"):
        return True
    if elements:
        elems = elements if isinstance(elements, list) else [elements]
        for elem in elems:
            if isinstance(elem, dict):
                r = str(elem.get("route") or "").lower()
                if "/api/prototype" in r or "/prototype" in r or r.endswith(".html"):
                    return True
                f = str(elem.get("file") or "").lower()
                if ".agentforge/prototype" in f or f.endswith(".html"):
                    return True
    combined_text = f"{prompt} {brief}".lower()
    if (proj_dir / ".agentforge" / "prototype").is_dir():
        if re.search(r"\b(prototype|html\s*prototype|drawing|\.html)\b", combined_text):
            return True
        if ".agentforge/prototype" in combined_text:
            return True
    if not (proj_dir / "package.json").is_file() and (proj_dir / ".agentforge" / "prototype").is_dir():
        return True
    return False


def run_feature(project: str, prompt: str, model: str, think=None, qa_model: str = "",
                route: str = "", console: str = "") -> None:
    """Add something to an application that already exists."""
    _edit_run(project, prompt, model, think, qa_model, console,
              kind="feature",
              route=route,
              brief=(f"Add this to the existing application:\n\n{prompt}\n\n"
                     + (f"The user was on the route {route} when they asked.\n" if route else "")
                     + "Read the code that already exists before changing anything, follow the "
                       "conventions it uses, and keep every current behaviour working. Prove "
                       "the new behaviour with tests and a browser journey."))


def run_chat(project: str, prompt: str, model: str, route: str = "", think=None,
             qa_model: str = "", console: str = "", agent_role: str = "") -> None:
    """Carry out a chat request against the existing application."""
    _edit_run(project, prompt, model, think, qa_model, console,
              kind="edit",
              route="/prototype" if agent_role == "designer" else "/__builder" if agent_role == "developer" else route,
              brief=(f"The user's next request in this project conversation:\n\n{prompt}\n\n"
                     + (f"They were on the route {route}.\n" if route else "")
                     + "Continue from the conversation and project memory already available. "
                       "Resolve references to earlier work from that history, and inspect current "
                       "code where needed for this request. Follow the user's intent, whether "
                       "it is a new feature, a design change, or a fix. Keep unrelated behaviour "
                       "working. For a reported bug, reproduce it and fix its cause. Verify "
                       "the requested behaviour with appropriate checks and report what changed."))


def _edit_run(project: str, prompt: str, model, think, qa_model: str, console: str,
              *, kind: str, brief: str, route: str = "", elements=None) -> None:
    runtime = None
    cancel.begin()
    cancel.note(project=project)
    try:
        proj_dir = _workspace(project)
        if proj_dir is None:
            return
        working_on(proj_dir.name)
        elog("INFO", f"✏️  {prompt[:160]}")
        estep("build", "active")

        is_html_mod = _is_html_modification(proj_dir, prompt, route=route, elements=elements, brief=brief)
        if not is_html_mod and not build_available(proj_dir):
            raise ValueError("Complete the prototype before updating the build")
        RUN.agent = "designer" if is_html_mod else "developer"
        if not is_html_mod:
            runtime = RUNTIMES.get(proj_dir)
            RUNTIMES.begin_work(runtime)
        if not is_html_mod:
            MONGO.ensure_running()
        snapshot = snapshot_project(proj_dir, RUN.agent)

        full = brief
        if is_html_mod:
            full = (
                "DIRECT HTML/PROTOTYPE UPDATE: Update HTML, CSS, or prototype files directly "
                "in .agentforge/prototype/ (or workspace HTML files). Do NOT run unit tests, do NOT run E2E journeys, "
                "and do NOT start background servers. Make the requested visual or content edits directly.\n\n"
            ) + full
        if console:
            full += ("\n\nThe browser had already logged this before they asked:\n"
                     + console[:6000])
        # The project is already built, so it knows its own stack far better
        # than the sentence asking for a change does.
        phases = ("build",) if is_html_mod else EDIT_PHASES
        agent, outcome = _run_agent(proj_dir, _brief(proj_dir, full, model=model), model, think,
                                    phases=phases, kind=kind, plan=False,
                                    stack=project_stack(proj_dir), no_tests=is_html_mod)
        if outcome.status == "cancelled":
            return ecancel({"project": proj_dir.name})
        if outcome.status != "completed":
            return eerr(outcome.result)
        _record_change(proj_dir, snapshot.get("id", ""), RUN.agent)

        if is_html_mod:
            proto_root = proj_dir / ".agentforge" / "prototype"
            target_url = f"/api/prototype/{proj_dir.name}/index.html"
            if proto_root.is_dir():
                from builder_agent.agent import _title_of
                on_disk = {p.name for p in proto_root.glob("*.html")}
                pages = []
                for p_name in sorted(on_disk):
                    pages.append({"file": p_name, "route": "", "label": _title_of(p_name), "what": ""})
                emit({"type": "prototype", "project": proj_dir.name, "pages": pages, "path": str(proto_root)})
                if route and ".html" in route:
                    html_file = route.split("/")[-1].split("?")[0]
                    if (proto_root / html_file).is_file():
                        target_url = f"/api/prototype/{proj_dir.name}/{html_file}"
            eprog("Done", 100)
            estep("build", "done")
            edone(target_url, proj_dir.name)
            return

        fill_missing_images(proj_dir, "the edit")
        url = _serve(proj_dir, agent)
        qa_outcome = run_qa_verification(
            proj_dir=proj_dir, project=proj_dir.name, model=model, think=think,
            host=ollama.host, cancel=_cancelled, memory=agent.memory,
            preview_url=url)
        _finish(proj_dir.name, url, outcome, qa_outcome)
    except cancel.BuildCancelled:
        ecancel({"project": project})
    except Exception as error:                                       # noqa: BLE001
        log.exception(kind)
        eerr(f"{type(error).__name__}: {error}")
    finally:
        if runtime is not None:
            with _SESSIONS_LOCK:
                session = _SESSIONS.get((runtime.project, "developer"))
            if session:
                session["agent"].processes.stop_all()
            RUNTIMES.end_work(runtime)
        cancel.finish()
