# Who may do what on a shared AgentForge (runtime part; see auth_db.py and access.py).
"""Accounts, wired into the rest of the server.

Every API request and every socket is signed in. The parts after this one ask
`may` before acting, start a run through `start_run`, and `emit` sends each
message only to `recipients`: the person whose project it is about, or whose
run or request is sending it.
"""
from http.cookies import CookieError, SimpleCookie

from server_modules.services import auth_db
from server_modules.services.access import rule as access_rule
from server_modules.services.run_queue import RunQueue

auth_db.projects_dir = PROD_DIR
RUN_QUEUE = RunQueue()
# The person signed in on each socket, and who started each SRS job.
WS_USERS: dict = {}
SRS_JOBS: dict = {}
SESSION_COOKIE = "af_session"
# Where the studio is served from, when it is served to the internet.
PUBLIC_ORIGIN = os.environ.get("AGENTFORGE_PUBLIC_ORIGIN", "").strip().rstrip("/")


def acting():
    """The person this request or run is for, on this thread."""
    return getattr(RUN, "user", None)


def act_as(user) -> None:
    RUN.user = user


def _cookie(header: str, name: str) -> str:
    try:
        jar = SimpleCookie()
        jar.load(str(header or ""))
    except CookieError:
        return ""
    morsel = jar.get(name)
    return morsel.value if morsel else ""


def session_token(headers) -> tuple:
    """(the sign-in token, whether it came from the cookie rather than a header)."""
    auth = str(headers.get("Authorization") or "")
    if auth.startswith("Bearer "):
        return auth[7:].strip(), False
    return _cookie(headers.get("Cookie") or "", SESSION_COOKIE), True


def session_cookie(token: str, *, secure: bool) -> str:
    """Set-Cookie for a sign-in - or, with no token, its removal.

    A frame, an image and a socket cannot carry the studio's header, so the
    session also travels as a cookie the page's script cannot read.
    """
    age = auth_db.SESSION_DAYS * 86400 if token else 0
    parts = [f"{SESSION_COOKIE}={token}", "Path=/", "HttpOnly", "SameSite=Lax", f"Max-Age={age}"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def request_user(headers):
    token, _ = session_token(headers)
    return auth_db.get_user_by_token(token)


def _hostname(value: str) -> str:
    text = str(value or "").lower()
    if "://" in text:
        text = urlsplit(text).netloc
    return text.rsplit("@", 1)[-1].split(":", 1)[0]


def studio_host(headers) -> str:
    """The address the studio was opened at, as this request reaches us.

    The studio proxies to this server, so `Host` here is the proxy's own end;
    the address the browser actually used is the forwarded one.
    """
    value = str(headers.get("X-Forwarded-Host") or headers.get("Host") or "")
    return value.split(",")[0].strip()


def same_origin(origin: str, host: str) -> bool:
    """Is a request carrying this Origin from the studio's own page?"""
    if not origin:
        return True          # not a browser, so not riding on anyone's cookie
    if PUBLIC_ORIGIN and origin.rstrip("/") == PUBLIC_ORIGIN:
        return True
    return _hostname(origin) == _hostname(host)


def trusted(headers) -> bool:
    """Did the studio's own page send this, and not a page that only shares its cookie?

    A generated app previews on another host and runs code its author wrote.
    Without this, a preview could build, edit or delete in the name of
    whoever opened it, riding on their session cookie.
    """
    site = str(headers.get("Sec-Fetch-Site") or "").lower()
    if site and site not in ("same-origin", "none"):
        return False
    return same_origin(str(headers.get("Origin") or ""), studio_host(headers))


def _project_of_path(path: str) -> str:
    try:
        relative = Path(path).resolve().relative_to(Path(PROD_DIR).resolve())
    except (ValueError, OSError):
        return ""
    return relative.parts[0] if relative.parts else ""


def may(user, kind: str, key: str = "") -> bool:
    """May this person make a request that needs `kind` of `key`? See access.py."""
    if not user:
        return False
    if kind in ("user", "srs-create"):
        return True
    if kind == "admin":
        return bool(user.get("admin"))
    if kind in ("project", "srs"):
        return bool(key) and auth_db.owns(user, kind, key)
    if kind == "project-path":
        name = _project_of_path(key)
        return bool(name) and auth_db.owns(user, "project", name)
    if kind == "run":
        active = RUN_QUEUE.active()
        return bool(active) and active["user"] == user["id"]
    if kind == "srs-job":
        return (srs_job_metadata(key) or {}).get("user") == user["id"]
    if kind == "job":
        return (_JOBS.get(key) or {}).get("user") == user["id"]
    if kind == "deploy-job":
        return DEPLOY_JOB_OWNERS.get(key) == user["id"]
    if kind == "deploy-run":
        project = run_project(key)
        return bool(project) and auth_db.owns(user, "project", project)
    return False


def recipients(msg: dict) -> list:
    """The sockets one message may go to: its project's owner's, or its sender's.

    A message about a project goes only to whoever owns it. One about no
    project goes to the person the run or request sending it is for; with
    neither, it is the server talking about itself and is for everyone.
    """
    sockets = list(clients)
    project = str(msg.get("project") or "")
    try:
        owner = auth_db.owner_of("project", project) if project else (acting() or {}).get("id")
    except Exception as error:                                       # noqa: BLE001
        log.debug(f"message owner: {error}")
        return []
    if owner:
        return [ws for ws in sockets if (WS_USERS.get(ws) or {}).get("id") == owner]
    if project:
        return [ws for ws in sockets if (WS_USERS.get(ws) or {}).get("admin")]
    return sockets


def _project_of(target, args) -> str:
    if getattr(target, "__name__", "") == "run_agent_pipeline":
        return str(args[4]) if len(args) > 4 else ""
    return str(args[0]) if args else ""


_REQUEST_LOCK = threading.RLock()
_DURABLE_TARGETS = {"run_agent_pipeline", "run_chat", "run_feature", "run_element_edit",
                    "run_manual_prototype_change", "run_spec_change"}

# Run kinds originating from SRS changes that manage their own transaction lifecycle.
_OWN_TRANSACTION = {"run_spec_change"}
SERVER_STOPPING = False


def start_run(target, args, *, project=None, user=None, replay_path=None) -> None:
    """Start one pipeline run on its own thread, in line behind any other.

    One build at a time: the pipeline keeps one run's state (what to cancel,
    which project its output belongs to), and two builds at once would also run
    each other out of memory. Everyone waiting is told how many are ahead.
    """
    user = user or acting()
    project = _project_of(target, args) if project is None else project

    def turn():
        nonlocal project, args
        act_as(user)
        kind = getattr(target, "__name__", "")
        role = "designer" if (kind == "run_manual_prototype_change" or (kind == "run_agent_pipeline" and len(args) > 9 and args[9]) or
              (kind == "run_chat" and len(args) > 7 and args[7] == "designer") or
              # Attribute drawing-only changes to the designer role.
              (kind == "run_spec_change" and len(args) > 2 and "developer" not in set(args[2] or ())) or
              (kind == "run_element_edit" and len(args) > 7 and str(args[7]).startswith("/prototype"))) else "developer"
        RUN.agent = role
        request_path = replay_path
        journal = None
        started = False
        try:
            if kind in _DURABLE_TARGETS:
                from server_modules.services.project_state import ProjectState, atomic_json
                with _REQUEST_LOCK:
                    if not project and kind == "run_agent_pipeline":
                        project = project_name_for(args[0])
                        (PROD_DIR / project).mkdir(parents=True, exist_ok=False)
                        if not claim_project(project):
                            raise ValueError("Project ownership could not be recorded")
                        args = tuple(list(args[:4]) + [project] + list(args[5:]))
                        eproject(project)
                    RUN.project = project
                    _, directory, error = _owned_dir(PROD_DIR, project, "project name", "project")
                    if error:
                        raise ValueError(error)
                    request_path = request_path or directory / ".agentforge" / "requests" / f"{time.time_ns()}.json"
                    if not replay_path:
                        journal = {"target": kind, "args": list(args), "project": project, "agent": role,
                                   "owner": (user or {}).get("id", ""), "started": True}
                    state = ProjectState(directory)
                    current = state.read().get("agents", {}).get(role, {})
                    if not replay_path and current.get("status") not in ("running", "finishing"):
                        state.agent(role, status="queued")
                        emit({"type": "run_state", "project": project, "agent": role, "status": "queued"})
                    if not replay_path:
                        prompt = '' if kind == 'run_manual_prototype_change' else args[0] if kind == "run_agent_pipeline" else args[1]
                        if prompt:
                            emit({"type": "user_msg", "project": project, "agent": role, "text": prompt})

            def work():
                nonlocal started
                started = True
                if journal is not None:
                    # Save journal checkpoints only once active execution starts.
                    atomic_json(request_path, journal)
                if kind in _OWN_TRANSACTION:
                    # Stage machine manages checkpoints and failure handling directly in this journal.
                    RUN.request_path = request_path
                    return target(*args)
                request = json.loads(request_path.read_text(encoding="utf-8")) if request_path else {}
                if not request.get("stage"):
                    target(*args)
                    if request_path and ProjectState(PROD_DIR / project).read().get("agents", {}).get(role, {}).get("status") == "completed":
                        request["stage"] = "source_completed"
                        atomic_json(request_path, request)
                if request_path and request.get("stage"):
                    try:
                        synchronize_completed_change(PROD_DIR / project, request_path, request)
                    except Exception as error:
                        if SERVER_STOPPING:
                            # Preserve a resumable transaction, not a failed-sync marker.
                            return
                        request["sync_error"] = str(error)
                        atomic_json(request_path, request)
                        state = {"status": "failed", "error": str(error), "request_id": request_path.stem}
                        ProjectState(PROD_DIR / project).update(sync=state)
                        emit({"type": "sync_state", "project": project, **state})

            def told(ahead):
                emit({"type": "log", "level": "INFO", **({"project": project} if project else {}),
                      "text": f"Queued: {ahead} run(s) ahead on this server."})

            RUN_QUEUE.run(work, user=(user or {}).get("id", ""), project=project, kind=kind, agent=role, on_wait=told)
            if not started and request_path:
                emit({"type": "cancelled", "project": project, "agent": role})
        except Exception as error:
            emit({"type": "error", "project": project, "agent": role, "text": str(error)})
        finally:
            # A killed process never reaches here, leaving the request for recovery.
            if request_path and request_path.is_file() and not SERVER_STOPPING:
                saved = json.loads(request_path.read_text(encoding="utf-8"))
                if not saved.get("sync_error"):
                    request_path.unlink(missing_ok=True)

    threading.Thread(target=turn, daemon=True).start()


def run_thread(target, args=(), daemon=True):
    """`threading.Thread(...)` for a pipeline run: it waits its turn, as its starter."""
    user = acting()

    class _Run:
        def start(self):
            start_run(target, tuple(args), user=user)
    return _Run()


def cancel_mine(project: str = "", agent: str = "") -> tuple:
    """Stop this person's run, or take theirs out of the line. (answer, status)"""
    user = acting() or {}
    left = RUN_QUEUE.leave(user.get("id", ""), project, agent)
    active = RUN_QUEUE.active()
    if (active and active["user"] == user.get("id") and
            (not project or active["project"] == project) and (not agent or active.get("agent") == agent)):
        out = cancel.request(project)
        return out, (200 if out.get("ok") else 409)
    if left:
        return {"ok": True, "left": left}, 200
    return {"ok": False, "error": "no build of yours is running"}, 409


def claim_project(name: str) -> bool:
    """Record that whoever this request or run is for owns a new project."""
    user = acting()
    if not user:
        return True
    return auth_db.claim("project", name, user["id"])


def release_project(name: str) -> None:
    try:
        auth_db.release("project", name)
    except Exception as error:                                       # noqa: BLE001
        log.debug(f"release {name}: {error}")


def visible_project(name: str, user=None) -> bool:
    return auth_db.owns(user or acting(), "project", name)


def shared_settings(answer: dict) -> dict:
    """The settings panel: each person's own accounts, and AgentForge's only to its admin."""
    user = acting() or {}
    mine = {**answer, "admin": bool(user.get("admin")), "deploy": deploy_summary_for(user)}
    if user.get("admin"):
        return mine
    return {**mine, "api_key_hint": "", "mongodb_uri_hint": "", "mongodb_uri_set": False}


def socket_user(websocket):
    """The person signed in on a socket, or None - checked once, when it opens."""
    request = getattr(websocket, "request", None)
    headers = (getattr(request, "headers", None)
               or getattr(websocket, "request_headers", None) or {})
    if not same_origin(str(headers.get("Origin") or ""), studio_host(headers)):
        return None
    return auth_db.get_user_by_token(_cookie(headers.get("Cookie") or "", SESSION_COOKIE))


def job_denied(msg: dict, user) -> str:
    """Why this person may not start the run a socket message asks for, or ""."""
    project = str(msg.get("project") or "").strip()
    srs_id = str(msg.get("srs_id") or "").strip()
    if project and not may(user, "project", project):
        return "that project is not one of yours"
    if msg.get("type") == "agent_build" and srs_id and not may(user, "srs", srs_id):
        return "that specification is not one of yours"
    return ""


def srs_job_metadata(job_id: str) -> dict:
    if not re.fullmatch(r"job_[a-f0-9]+", str(job_id)):
        return SRS_JOBS.get(job_id, {})
    if job_id not in SRS_JOBS:
        from server_modules.services.project_state import read_json
        SRS_JOBS[job_id] = read_json(PROD_DIR / ".srs" / ".job-owners" / f"{job_id}.json")
    return SRS_JOBS[job_id]


def srs_job_started(job_id: str, user, create: bool = False, listing: bool = False) -> None:
    if job_id and user:
        SRS_JOBS[job_id] = {"user": user["id"], "create": bool(create), "listing": bool(listing)}
        from server_modules.services.project_state import atomic_json
        atomic_json(PROD_DIR / ".srs" / ".job-owners" / f"{job_id}.json", SRS_JOBS[job_id])
        # The agent forgets a job fifteen minutes after it ends; so can this.
        if len(SRS_JOBS) > 2000:
            for old in list(SRS_JOBS)[:500]:
                SRS_JOBS.pop(old, None)


def srs_job_answered(job_id: str, answer, user) -> dict:
    """What a poll of an SRS job may show its starter.

    A list is cut down to their own specifications, and a finished job that
    created one makes it theirs.
    """
    job = srs_job_metadata(job_id)
    answer = answer if isinstance(answer, dict) else {}
    if job.get("listing") and answer.get("result") is not None:
        return {**answer, "result": visible_srs_list(answer["result"], user)}
    if job.get("create") and answer.get("status") == "done":
        created = (((answer.get("result") or {}).get("project")) or {}).get("id")
        if created:
            auth_db.claim("srs", str(created), job["user"])
    return answer


def visible_srs_list(answer, user):
    """The SRS agent's own list, cut down to this person's specifications."""
    def mine(items):
        return [p for p in items or []
                if isinstance(p, dict) and auth_db.owns(user, "srs", str(p.get("id") or ""))]
    if isinstance(answer, list):
        return mine(answer)
    answer = answer if isinstance(answer, dict) else {}
    return {**answer, "projects": mine(answer.get("projects"))}
