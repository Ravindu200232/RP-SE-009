# Drives the builder and QA agents for the studio.
"""What the studio's buttons actually do.

Deliberately thin. There is no stage machine here deciding which files to
write or which tests to run - that is the agent's job, and hard-coding it was
what made the previous version brittle. This resolves a project directory,
hands the agent a brief, and translates what comes back.

Four entry points, one shape: build, resume, feature, repair. Each one prepares
the workspace, runs the builder through its unit/E2E checks, brings the app up,
and publishes the evidence it already produced.
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

from builder_agent import BuilderAgent, Config, Events, detect_stack  # noqa: E402
from qa_agent import QAAgent  # noqa: E402
from qa_agent.agent import QAOutcome  # noqa: E402
from qa_agent import report as qa_report, security as qa_security  # noqa: E402

from server_modules.services.mongo_common import db_name_for  # noqa: E402

# `StudioBridge`, `fill_missing_images`, `cancel` and the emit helpers come from
# the runtime parts executed before this one, not from an import: these files
# are one program sharing one namespace.

BUILD_PHASES = ("plan", "design", "build", "unit", "e2e")
EDIT_PHASES = ("build", "unit", "e2e")

# Files worth snapshotting before an edit so a single click can undo it.
UNDO_EXT = {".js", ".jsx", ".ts", ".tsx", ".css", ".json", ".md"}
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
    """Give the app its database connection before it is asked to connect.

    A generated app that has to invent its own connection string either
    hard-codes one or guesses a database name that collides with the last
    project's collections. Writing it here makes both impossible.
    """
    target = proj_dir / ".env.local"
    wanted = f"MONGODB_URI={MONGO.uri_for(proj_dir.name)}"
    try:
        existing = target.read_text("utf-8") if target.is_file() else ""
        if "MONGODB_URI=" in existing:
            return
        target.write_text((existing + "\n" if existing.strip() else "") + wanted + "\n",
                          encoding="utf-8")
    except OSError as error:
        elog("WARN", f"   ⚠ .env.local could not be written: {error}")


def _prepare_workspace(prompt: str, project: str, srs_id: str) -> Path:
    if project:
        proj_dir = PROD_DIR / project
        proj_dir.mkdir(parents=True, exist_ok=True)
        _write_env(proj_dir)
        return proj_dir
    name = project_name_for(prompt)
    proj_dir = PROD_DIR / name
    proj_dir.mkdir(parents=True, exist_ok=True)
    _write_env(proj_dir)
    eproject(name)
    if srs_id:
        try:
            adopt_srs(srs_id, proj_dir)
        except Exception as error:                                   # noqa: BLE001
            elog("WARN", f"   ⚠ the specification could not be attached: {error}")
    return proj_dir


def _brief(proj_dir: Path, prompt: str) -> str:
    """The request, plus whatever the approved specification already settled."""
    parts = [prompt.strip()]
    try:
        spec = _srs_brief(proj_dir, "")
    except Exception:                                                # noqa: BLE001
        spec = ""
    if spec:
        parts += ["", "APPROVED SPECIFICATION (build to this):", spec]
    # The per-project database keeps generated apps out of each other's
    # collections, and the URI reaches the app through its environment so
    # nothing has to be hard-coded into the source.
    parts += ["", f"MongoDB is running and this project's database is "
                  f"`{db_name_for(proj_dir.name)}`. Read the connection string from "
                  f"MONGODB_URI in the environment (it is set to "
                  f"{MONGO.uri_for(proj_dir.name)}); never hard-code one."]
    return "\n".join(parts)


# How long a question waits for the studio before the build carries on with
# what it would have done anyway. Long enough to read a plan; short enough that
# a closed browser does not strand a run.
GATE_TIMEOUT = 600


def _config(proj_dir: Path, prompt: str, model: str, think, gates: bool = False,
            stack: str = "") -> Config:
    # A stack chosen in the studio is a decision; reading it out of the wording
    # of the brief is a guess, and only the fallback.
    return Config(workspace=proj_dir, model=model or default_agent_model(),
                  host=ollama.host, stack=stack or detect_stack(prompt),
                  think=bool(think),
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
# A run blocks on its own thread, so the HTTP handler needs a way to reach the
# registry it is waiting on. Runs are rare and short-lived, so a list of the
# live ones is simpler than a lookup table nothing else would use.
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
def snapshot_project(proj_dir: Path) -> dict:
    """Copy the source files before an edit so one click can put them back."""
    snap_id = uuid.uuid4().hex[:10]
    store = proj_dir / ".agentforge" / "undo" / snap_id
    files = []
    for path in proj_dir.rglob("*"):
        if not path.is_file() or path.suffix not in UNDO_EXT:
            continue
        relative = path.relative_to(proj_dir)
        if any(part in UNDO_SKIP for part in relative.parts):
            continue
        target = store / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, target)
            files.append(relative.as_posix())
        except OSError:
            continue
        if len(files) > 400:
            break
    _trim_undo(proj_dir)
    emit({"type": "undo_point", "id": snap_id, "files": files[:20]})
    return {"id": snap_id, "files": files}


def _trim_undo(proj_dir: Path) -> None:
    base = proj_dir / ".agentforge" / "undo"
    snaps = sorted((p for p in base.iterdir() if p.is_dir()),
                   key=lambda p: p.stat().st_mtime) if base.is_dir() else []
    for stale in snaps[:-UNDO_KEEP]:
        shutil.rmtree(stale, ignore_errors=True)


def restore_snapshot(project: str, snap_id: str) -> dict:
    proj_dir = PROD_DIR / str(project or "")
    store = proj_dir / ".agentforge" / "undo" / str(snap_id or "")
    if not store.is_dir():
        return {"error": "that undo point is no longer available"}
    restored = []
    for path in store.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(store)
        target = proj_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        restored.append(relative.as_posix())
        efile(relative.as_posix(), target.stat().st_size,
              target.read_text("utf-8", errors="replace"))
    return {"ok": True, "restored": restored}


# --------------------------------------------------------------------------
# The runs
# --------------------------------------------------------------------------
# One live agent per project, so the next thing said in the chat is the next
# thing said in the same conversation.
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


def forget_session(project: str) -> None:
    """Drop the conversation about a project that is closing or gone."""
    with _SESSIONS_LOCK:
        session = _SESSIONS.pop(str(project or ""), None)
    if session:
        try:
            session["agent"].dispose()
        except Exception as error:                                   # noqa: BLE001
            log.debug(f"disposing the session for {project}: {error}")


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
        others = [name for name in _SESSIONS if name != str(keep or "")]
    for name in others:
        forget_session(name)
    return others


def _agent_for(proj_dir: Path, brief: str, model: str, think, stack: str,
               *, kind: str, phases, plan: bool):
    """The agent already talking about this project, or a new one.

    A chat message is the next line of a conversation, not the first line of a
    new one. Keeping the agent alive between messages is what makes "no, the
    other button" mean anything: the transcript, the verification ledger and
    the context window all carry over, and the engine's own compaction is what
    keeps that affordable over a long session.

    A build starts a fresh conversation, since there is nothing before it. A
    change of model or of thinking does not: it is applied to the conversation
    already running, because what was said stays true whoever answers next.
    """
    name = proj_dir.name
    key = _session_key(model, think, stack)

    release_other_sessions(name)
    agent = None
    if not plan:
        with _SESSIONS_LOCK:
            session = _SESSIONS.get(name)
        if session and session["key"] == key and session.get("reusable"):
            agent = session["agent"]
            agent.retarget(model, think)
        elif session:
            forget_session(name)

    fresh = agent is None
    if fresh:
        forget_session(name)
        agent = BuilderAgent(
            _config(proj_dir, brief, model, think, gates=plan, stack=stack),
            events=Events(), cancel=_cancelled)
    else:
        # The bus is the agent's, but the listeners belong to one run: each has
        # its own phase list and its own report writer.
        agent.events.clear()

    StudioBridge(agent.events, kind=kind, phases=list(phases))
    agent.events.any(qa_report.LiveReport(
        proj_dir, agent.memory.evidence, emit,
        lambda error: elog("WARN", f"Could not save testing results: {error}")))
    # Registered whether or not it can be reused: a build never continues an
    # earlier conversation, but its services still have to be lettable-go of.
    with _SESSIONS_LOCK:
        _SESSIONS[name] = {"agent": agent, "key": key, "reusable": not plan}
    if not fresh:
        elog("INFO", f"   continuing the conversation ({len(agent.memory)} messages so far)")
    return agent


def _run_agent(proj_dir: Path, brief: str, model: str, think, *, phases, kind: str,
               plan: bool = True, stack: str = ""):
    """One builder-agent run, wired to the studio.

    A full build asks about its plan and its design, because the studio can
    answer. An edit does not: there is no plan to review, and the design was
    settled when the project was built.
    """
    agent = _agent_for(proj_dir, brief, model, think, stack,
                       kind=kind, phases=phases, plan=plan)
    register_approvals(agent.approvals)
    try:
        return agent, (agent.run(brief) if plan else agent.build(brief))
    finally:
        forget_approvals(agent.approvals)
        agent._finish()


def _verify(proj_dir: Path, project: str, model: str, think, qa_model: str, *, memory=None):
    """Run the QA agent over the finished project at the deep profile."""
    events = Events()
    StudioBridge(events, kind="test", phases=list(EDIT_PHASES))
    qa = QAAgent(project=project, project_dir=proj_dir,
                 model=(qa_model or model or default_agent_model()),
                 host=ollama.host, events=events, think=bool(think),
                 cancel=_cancelled, memory=memory)
    try:
        return qa.run()
    finally:
        qa.dispose()


def _serve(proj_dir: Path, agent=None) -> str:
    """Bring the app up so the preview and the journeys have something to hit.

    The run's own dev servers go first. A finished run leaves them up so the
    preview has something to show, but the preview is about to start its own
    copy of the same application, and on a multi-service stack the old ones are
    still holding the ports the new ones need - the gateway came up on the
    preview port while every service behind it died with EADDRINUSE.

    A Next app never noticed: it binds one port, and starting the dev server
    frees that port first. Nothing here needs to know which ports a stack uses,
    only that the processes holding them belong to the run that just ended.
    """
    estep("preview", "active")
    try:
        if agent is not None:
            agent.processes.stop_all()
        # Whatever this run owned is gone; anything still on the project's own
        # ports is an orphan from a run that ended badly, and it will stop the
        # preview just as effectively.
        freed = free_declared_ports(proj_dir)
        if freed:
            log.info(f"freed ports {', '.join(str(p) for p in freed)} before the preview")
        ensure_node_deps(proj_dir)
        start_dev_server(proj_dir, detect_stack(proj_dir))
        if wait_for_dev(detect_stack(proj_dir)):
            estep("preview", "done")
            return f"http://127.0.0.1:{DEV_PORT}"
        elog("WARN", "   ⚠ the dev server did not become ready in time")
    except Exception as error:                                       # noqa: BLE001
        elog("WARN", f"   ⚠ the preview could not be started: {error}")
    estep("preview", "error")
    return ""


def _record_verification(proj_dir: Path, project: str, agent, outcome):
    """Keep the builder's real results; E2E does not start another QA cycle."""
    evidence = agent.memory.evidence.summary()
    security = {"findings": qa_security.scan(proj_dir), "audit": {}}
    record = qa_report.from_evidence(
        project=project, project_dir=proj_dir, evidence=evidence, security=security,
        complete=outcome.status == "completed")
    path = qa_report.write(proj_dir, record)
    emit({"type": "test_report", "project": project,
          "stages": record["stages"], "complete": record["complete"]})
    ok = evidence.get("ready", False) and not security["findings"]
    reason = (f"{len(security['findings'])} security finding(s)" if security["findings"]
              else "" if ok else "Required verification has not passed.")
    return QAOutcome(project=project, ok=ok, record=record, path=str(path), reason=reason)


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
                       stack: str = "") -> None:
    """Build an application from a request, then prove it works."""
    started = time.time()
    cancel.begin()
    try:
        proj_dir = _prepare_workspace(prompt, project, srs_id)
        name = proj_dir.name
        cancel.note(project=name, srs_id=srs_id)
        resuming = bool(project)
        elog("INFO", f"🏗️  {'Resuming' if resuming else 'Building'} {name}")
        estep("plan", "active")

        MONGO.ensure_running()
        brief = _brief(proj_dir, prompt or
                       "Continue this project: finish whatever is incomplete and "
                       "make every verification pass.")
        if logo:
            brief += f"\n\nA logo has already been generated at {logo}; use it in the header."

        agent, outcome = _run_agent(proj_dir, brief, model, think,
                                    phases=BUILD_PHASES, kind="build", stack=stack)
        if outcome.status == "cancelled":
            return ecancel({"project": name})

        fill_missing_images(proj_dir, "the build")
        url = _serve(proj_dir, agent)
        qa_outcome = _record_verification(proj_dir, name, agent, outcome)
        if _finish(name, url, outcome, qa_outcome):
            elog("SUCCESS", f"✅ {name} finished in {int(time.time() - started)}s")
    except cancel.BuildCancelled:
        ecancel({"project": project})
    except Exception as error:                                       # noqa: BLE001
        log.exception("agent pipeline")
        eerr(f"{type(error).__name__}: {error}")
    finally:
        cancel.finish()


def run_feature(project: str, prompt: str, model: str, think=None, qa_model: str = "",
                route: str = "", console: str = "") -> None:
    """Add something to an application that already exists."""
    _edit_run(project, prompt, model, think, qa_model, console,
              kind="feature",
              brief=(f"Add this to the existing application:\n\n{prompt}\n\n"
                     + (f"The user was on the route {route} when they asked.\n" if route else "")
                     + "Read the code that already exists before changing anything, follow the "
                       "conventions it uses, and keep every current behaviour working. Prove "
                       "the new behaviour with tests and a browser journey."))


def run_chat(project: str, prompt: str, model: str, route: str = "", think=None,
             qa_model: str = "", console: str = "") -> None:
    """Carry out a chat request against the existing application."""
    _edit_run(project, prompt, model, think, qa_model, console,
              kind="edit",
              brief=(f"The user requests this change to the existing application:\n\n{prompt}\n\n"
                     + (f"They were on the route {route}.\n" if route else "")
                     + "Read the relevant existing code and follow the user's intent, whether "
                       "it is a new feature, a design change, or a fix. Keep unrelated behaviour "
                       "working. For a reported bug, reproduce it and fix its cause. Verify "
                       "the requested behaviour with appropriate checks and report what changed."))


def _edit_run(project: str, prompt: str, model, think, qa_model: str, console: str,
              *, kind: str, brief: str) -> None:
    cancel.begin()
    cancel.note(project=project)
    try:
        proj_dir = PROD_DIR / str(project or "")
        if not proj_dir.is_dir():
            return eerr(f"there is no project called {project}")
        elog("INFO", f"✏️  {prompt[:160]}")
        estep("build", "active")
        MONGO.ensure_running()
        snapshot_project(proj_dir)

        full = brief
        if console:
            full += ("\n\nThe browser had already logged this before they asked:\n"
                     + console[:6000])
        agent, outcome = _run_agent(proj_dir, _brief(proj_dir, full), model, think,
                                    phases=EDIT_PHASES, kind=kind, plan=False)
        if outcome.status == "cancelled":
            return ecancel({"project": proj_dir.name})

        fill_missing_images(proj_dir, "the edit")
        url = _serve(proj_dir, agent)
        qa_outcome = _record_verification(proj_dir, proj_dir.name, agent, outcome)
        _finish(proj_dir.name, url, outcome, qa_outcome)
    except cancel.BuildCancelled:
        ecancel({"project": project})
    except Exception as error:                                       # noqa: BLE001
        log.exception(kind)
        eerr(f"{type(error).__name__}: {error}")
    finally:
        cancel.finish()
