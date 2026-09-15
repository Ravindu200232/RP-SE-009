# Project flow: validate ownership -> read or change -> notify the Studio.
SRC_ROOTS = ("app", "components", "lib", "src", "pages", "packages", "client", "server", "scripts", "services")
SKIP_DIRS = {"node_modules", ".next", ".git", "dist", "out", ".vite", ".turbo",
             ".agentforge", ".cache", "build", ".husky", ".idea", ".vscode", "coverage", ".output"}
SRC_EXT = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".css", ".scss", ".sass", ".less", ".html", ".htm",
    ".json", ".md", ".yaml", ".yml", ".sql", ".prisma",
    ".svg", ".env", ".toml"
}


def _iter_source(proj_dir: Path):
    """Every source file in a project, whatever layout it uses."""
    if not proj_dir.is_dir():
        return
    for root_str, dirnames, filenames in os.walk(proj_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not (d.startswith(".") and d != ".env")]
        root_path = Path(root_str)
        for fname in filenames:
            if fname.lower() in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
                continue
            if fname.startswith(".") and fname not in (".env", ".env.local", ".env.example"):
                continue
            fp = root_path / fname
            if fp.suffix.lower() in SRC_EXT or fname in (".env", ".env.local", ".env.example", "Dockerfile"):
                yield fp


def _owned_dir(root: Path, raw: str, label: str,
               missing_label: str) -> tuple:
    """Resolve one HTTP-supplied directory name inside its owned root."""
    name = str(raw or "").strip().replace("\\", "/")
    if not name or "/" in name or name in (".", "..") or name.startswith("."):
        return name, None, f"{raw!r} is not a {label}"
    try:
        resolved = (root / name).resolve()
        resolved.relative_to(root.resolve())
    except (ValueError, OSError):
        return name, None, f"{name} is outside {root.name}"
    if not resolved.is_dir():
        return name, None, f"no such {missing_label}: {name}"
    return name, resolved, ""


def _deploy_marker(project_dir: Path) -> dict | None:
    """Return cheap, disk-only deployment history for project listings."""
    agentforge = project_dir / ".agentforge"
    if (agentforge / "deploy-deleted.json").is_file():
        return {"state": "deleted", "target": ""}
    link = agentforge / "deploy" / "link.json"
    if not link.is_file():
        return None
    try:
        target = str(json.loads(link.read_text(encoding="utf-8")).get("target") or "")
    except Exception:
        target = ""
    return {"state": "deployed", "target": target}


def discard_srs(srs_id: str) -> dict:
    """Remove one staged specification without escaping its owned root."""
    sid, resolved, error = _owned_dir(
        PROD_DIR / ".srs", srs_id, "specification id", "specification")
    if error:
        if "outside" in error:
            error = f"{sid} is outside the specification store"
        return {"error": error}

    shutil.rmtree(resolved, ignore_errors=True)
    if resolved.exists():
        return {"error": f"{sid} could not be removed"}
    elog("INFO", f"   🗑 discarded the specification {sid}")
    return {"ok": True, "srs_id": sid}


def keep_srs(srs_id: str) -> dict:
    """Keep a specification as a project of its own, without building it.

    Approving a specification used to be the same act as starting a build, so
    there was no way to say "the spec is what I wanted, not yet the app": the
    interview stayed staged under a hidden folder with nothing listing it and
    no way back. This gives it a project directory, which is the only thing
    the studio lists.

    Nothing is scaffolded and no environment is written. The directory holds
    the specification and nothing else - and that absence is what identifies
    it later, so a build over the top of it needs no marker cleared.
    """
    sid, staging, error = _owned_dir(
        PROD_DIR / ".srs", srs_id, "specification id", "specification")
    if error:
        if "outside" in error:
            error = f"{sid} is outside the specification store"
        return {"error": error}

    name = project_name_for(_srs_app_name(sid) or sid)
    proj_dir = PROD_DIR / name
    try:
        proj_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"error": f"could not keep {sid}: {e}"}
    if not claim_project(name):
        return {"error": f"{name} was taken by someone else a moment ago - try again"}

    if not adopt_srs(sid, proj_dir):
        # An empty directory is worse than no directory: it lists as a project
        # that cannot open.
        shutil.rmtree(proj_dir, ignore_errors=True)
        return {"error": f"the specification {sid} could not be attached"}

    eproject(name)
    elog("INFO", f"   📄 kept the specification as {name} — nothing was built")
    return {"ok": True, "project": name, "srs_id": sid}


def _spec_only(proj_dir: Path) -> bool:
    """Is this a specification that was kept rather than an app that was built?

    Read off the directory rather than a flag written into it. A marker has to
    be cleared by whoever builds the project later, and the build that forgets
    leaves a project the studio will only ever show a specification for. A
    manifest or a single source file is proof a build happened, and both appear
    long before it finishes.
    """
    if not (proj_dir / ".agentforge" / "srs").is_dir():
        return False
    if (proj_dir / "package.json").is_file():
        return False
    return not any(_iter_source(proj_dir))


def _prototype_only(proj_dir: Path) -> bool:
    """Is this an HTML prototype rather than an app that was built?"""
    if not (proj_dir / ".agentforge" / "prototype").is_dir():
        return False
    if (proj_dir / "package.json").is_file():
        return False
    return not any(_iter_source(proj_dir))


def build_available(proj_dir: Path) -> bool:
    if not (proj_dir / ".agentforge" / "srs").is_dir():
        return True
    designer = ProjectState(proj_dir).read().get("agents", {}).get("designer", {})
    return ((designer.get("status") == "completed" or bool(designer.get("completed_at"))) and
            (proj_dir / ".agentforge" / "prototype" / "index.html").is_file())


def delete_project(proj_name: str) -> dict:
    """Remove a fenced project, then its generated database, in background."""
    name, resolved, error = _owned_dir(
        PROD_DIR, proj_name, "project name", "project")
    if error:
        return {"error": error}
    # Nothing may keep talking about a project that is gone - and nothing may
    # keep writing one back. Disposing the session stops its dev servers; only
    # a cancellation stops the loop, which had carried on recreating a deleted
    # project file by file.
    forget_session(name)
    stopped = cancel.request(project=name)
    if stopped.get("ok"):
        elog("INFO", f"   ⏹ Stopped the run working on {name}")

    RUNTIMES.stop(runtime_for(name), "deleted", delete=True)
    # Its public address goes with it (preview_link.py).
    unpublish_preview(name)

    trash = PROD_DIR / f".trash-{name}-{int(time.time())}"
    try:
        resolved.rename(trash)
    except OSError as e:
        return {"error": f"could not delete {name}: {e}"}

    DEPLOY_RUNS.pop(name, None)
    release_project(name)

    def _finish():
        dropped, why = "", ""
        try:
            r = MONGO.reset_project_db(trash, node_bin=NODE_BIN)
            dropped = r.get("db", "") if r.get("ok") else ""
            why = "" if dropped else str(r.get("error", "") or "")
        except Exception as e:                                   # noqa: BLE001
            why = f"{type(e).__name__}: {e}"
        elog("INFO", f"   🗑 Deleted {name}"
                     + (f" and its database {dropped}" if dropped else
                        f" — its database was left ({why or 'no reason given'})"))
        try:
            shutil.rmtree(trash, ignore_errors=True)
        except Exception as e:                                   # noqa: BLE001
            log.debug(f"emptying {trash.name}: {e}")
        for old in PROD_DIR.glob(".trash-*"):
            if old != trash:
                shutil.rmtree(old, ignore_errors=True)

    threading.Thread(target=_finish, daemon=True).start()
    return {"ok": True, "project": name}


# What a drawing is allowed to be made of. It is opened in an iframe, so
# anything else it asks for is refused rather than guessed at.
# What a drawing is allowed to serve. `.js` belongs here: the whole point of
# demo.js is that the flow can be clicked through, and without it the preview
# refused the one file the skill requires - every drawing ever shown had its
# script 400 and none of the state, filters or sign-in worked. It got worse with
# motion, because content that starts at opacity 0 and waits for an observer
# stays invisible when the observer never loads.
PROTOTYPE_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                   ".js": "text/javascript; charset=utf-8",
                   ".mjs": "text/javascript; charset=utf-8",
                   ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg",
                   ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
                   ".ico": "image/x-icon", ".woff2": "font/woff2", ".woff": "font/woff"}



def _find_html_root(proj_dir: Path) -> Path:
    """Find root directory containing index.html for preview."""
    proto = (proj_dir / ".agentforge" / "prototype").resolve()
    if (proto / "index.html").is_file():
        return proto
    for dist_rel in ("client/dist", "dist", "client/public", "public", "client"):
        candidate = (proj_dir / dist_rel).resolve()
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    if (proj_dir / "index.html").is_file():
        return proj_dir.resolve()
    return proto


def _find_html_info(proj_dir: Path) -> dict:
    """Check if the project has an HTML prototype or first-page HTML available."""
    proto = proj_dir / ".agentforge" / "prototype"
    if (proto / "index.html").is_file():
        return {
            "has_html": True,
            "html_url": f"/__agentforge/api/prototype/{proj_dir.name}/index.html",
        }
    for dist_rel in ("client/dist", "dist", "client/public", "public", "client", ""):
        candidate = proj_dir / dist_rel if dist_rel else proj_dir
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return {
                "has_html": True,
                "html_url": f"/__agentforge/api/prototype/{proj_dir.name}/index.html",
            }
    return {
        "has_html": False,
        "html_url": "",
    }


def read_prototype(proj_name: str, rel: str) -> tuple:
    """One file of a project's HTML drawing, for the review pane to show.

    Returns (bytes, content type). Raises FileNotFoundError when there is no
    such file, and ValueError when the path is not one this may serve - the
    name comes from a URL, so it is never trusted to stay inside the folder.
    """
    name, proj_dir, error = _owned_dir(PROD_DIR, proj_name, "project name", "project")
    if error:
        raise FileNotFoundError(error)

    root = _find_html_root(proj_dir)
    rel = str(rel or "index.html").replace("\\", "/").strip("/") or "index.html"
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"{rel} is outside the drawing") from None

    kind = PROTOTYPE_TYPES.get(target.suffix.lower())
    if kind is None:
        raise ValueError(f"a drawing does not serve {target.suffix or 'that'} files")
    if not target.is_file():
        if rel == "tailwind.js":
            base = globals().get("BASE_DIR")
            fallback = (Path(base) if base else Path(__file__).resolve().parent.parent.parent) / "builder-agent" / "builder_agent" / "assets" / "static" / "tailwind.js"
            if fallback.is_file():
                return fallback.read_bytes(), kind
        # Fallback check in prototype folder if root was dist or vice versa
        prototype_root = (proj_dir / ".agentforge" / "prototype").resolve()
        proto_alt = (prototype_root / rel).resolve()
        if not proto_alt.is_relative_to(prototype_root):
            raise ValueError(f"{rel} is outside the drawing")
        if proto_alt.is_file():
            content = proto_alt.read_bytes()
            if proto_alt.suffix.lower() == ".html":
                from server_modules.services.prototype_storage import isolate_storage
                content = isolate_storage(content, name)
            return content, kind
        raise FileNotFoundError(f"no {rel} in this drawing")
    content = target.read_bytes()
    if target.suffix.lower() == ".html":
        from server_modules.services.prototype_storage import isolate_storage
        content = isolate_storage(content, name)
    return content, kind


def list_projects() -> list:
    """Return all projects in production-ready/ with metadata."""
    projects = []
    if not PROD_DIR.exists():
        return projects
    for d in sorted(PROD_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):

        if not d.is_dir() or d.name.startswith("."):
            continue
        pkg = d / "package.json"
        title = d.name
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text())
                title = data.get("name", d.name)
            except: pass
        html_info = _find_html_info(d)
        projects.append({
            "name": d.name,
            "title": title,
            "mtime": int(d.stat().st_mtime),
            "file_count": sum(1 for _ in _iter_source(d)),
            "stack": detect_stack(d),

            "unfinished": _unfinished_count(d),

            "spec_only": _spec_only(d),
            "prototype_only": _prototype_only(d),
            "build_available": build_available(d),

            "has_html": html_info["has_html"],
            "html_url": html_info["html_url"],

            "deployed": _deploy_marker(d),
        })
    return projects


def _unfinished_count(proj_dir: Path) -> int:
    """Count planned files absent on disk without walking dependencies."""
    try:
        fp = proj_dir / ".agentforge" / "plan.json"
        if not fp.is_file():
            return 0
        plan = json.loads(fp.read_text(encoding="utf-8"))
        planned = [f.get("path", "") for ph in (plan.get("phases") or [])
                   for f in (ph.get("files") or []) if f.get("path")]
        missing = 0
        for rel in planned:
            rel = rel.lstrip("./")
            stem = re.sub(r"\.jsx?$", "", rel)
            if any((proj_dir / c).is_file()
                   for c in (rel, stem + ".js", stem + ".jsx")):
                continue
            missing += 1
        return missing
    except Exception as e:
        log.debug(f"unfinished count for {proj_dir.name}: {e}")
        return 0


FILE_PRIORITY = [
    "app/page.js", "app/page.jsx", "app/layout.js", "lib/mongodb.js",
    "app/globals.css", "next.config.mjs", "jsconfig.json",
    "package.json", "tailwind.config.js", "plan.md",
]
MAX_LISTED_FILES = 500
MAX_FILE_BYTES = 256_000
MAX_PROTOTYPE_CHARACTERS = 4_000_000


def save_project_file(proj_name: str, rel: str, content: str, *, change_summary: str = "") -> dict:
    """Write one manually edited file, fenced inside its project."""
    proj_dir = PROD_DIR / _safe_stem(proj_name, "")
    if not proj_dir.is_dir():
        return {"error": f"no such project: {proj_name}"}

    rel = str(rel or "").replace("\\", "/").strip().lstrip("/")
    if not rel:
        return {"error": "no path given"}
    try:
        target = (proj_dir / rel).resolve()
        target.relative_to(proj_dir.resolve())
    except (ValueError, OSError):
        return {"error": f"{rel} is outside the project"}

    if target.suffix not in SRC_EXT | {".json", ".md", ".mjs", ".cjs", ".txt"}:
        return {"error": f"{target.suffix or 'that kind of file'} is not editable here"}
    prototype_edit = rel.startswith('.agentforge/prototype/') and target.suffix == '.html'
    limit = MAX_PROTOTYPE_CHARACTERS if prototype_edit else MAX_FILE_BYTES
    if len(content) > limit:
        return {"error": f"{len(content):,} characters is past the "
                         f"{limit:,} limit"}

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="")
    except OSError as e:
        return {"error": f"could not write {rel}: {e}"}

    size = (f"{len(content)/1024:.1f}KB" if len(content) >= 1024
            else f"{len(content)}B")
    elog("INFO", f"   💾 {rel} saved by hand ({size})")

    emit({'type': 'file', 'project': proj_name, 'agent': 'designer' if prototype_edit else 'developer',
          'name': rel, 'size': size, 'content': content, 'note': 'written'})
    if change_summary and rel.startswith('.agentforge/prototype/') and target.suffix == '.html':
        summary = re.sub(r"(?:mongodb(?:\+srv)?://|https?://[^/\s:@]+:[^/\s@]+@)[^\s'\"<>]+",
                         '[redacted connection]', str(change_summary))[:6000]
        start_run(run_manual_prototype_change, (proj_name, summary), project=proj_name)
    return {"ok": True, "path": rel, "size": size}


def get_project_files(proj_name: str, role: str = "developer") -> dict:
    """Read all source files from a project directory, return as {path: content}."""
    _, proj_dir, error = _owned_dir(PROD_DIR, proj_name, "project name", "project")
    if error:
        return {}

    def add(files: dict, rel: str, fp: Path):
        if fp.name.startswith(".env") and fp.name != ".env.example":
            return
        try:
            if fp.stat().st_size > MAX_FILE_BYTES:
                return
            content = fp.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return
        sz = (f"{len(content)/1024:.1f}KB" if len(content) >= 1024
              else f"{len(content)}B")
        files[rel] = {"content": content, "size": sz}

    files = {}
    if role == "designer":
        sandbox = Sandbox(proj_dir, role="designer")
        for fp in sandbox.walk(proj_dir / ".agentforge" / "prototype", limit=MAX_LISTED_FILES):
            if fp.suffix in SRC_EXT:
                add(files, fp.relative_to(proj_dir).as_posix(), fp)
        return files
    for rel in FILE_PRIORITY:
        fp = proj_dir / rel
        if fp.exists() and rel not in files:
            add(files, rel, fp)

    for fp in sorted(_iter_source(proj_dir)):
        if len(files) >= MAX_LISTED_FILES:
            break
        rel = str(fp.relative_to(proj_dir)).replace("\\", "/")
        if rel not in files:
            add(files, rel, fp)

    for sub in ("tests/unit", "tests/e2e"):
        base = proj_dir / sub
        if not base.is_dir():
            continue
        for fp in sorted(base.rglob("*")):
            if len(files) >= MAX_LISTED_FILES:
                break
            if fp.is_file() and fp.suffix in SRC_EXT:
                rel = str(fp.relative_to(proj_dir)).replace("\\", "/")
                if rel not in files:
                    add(files, rel, fp)
    return files


async def ws_handler(websocket, path=None):
    # Signed in once, when the socket opens: every run it starts is theirs,
    # and it hears only about what is theirs.
    user = await asyncio.get_running_loop().run_in_executor(None, socket_user, websocket)
    if user is None:
        await websocket.close(code=4401, reason="sign in")
        return
    WS_USERS[websocket] = user
    clients.add(websocket)
    log.info(f"WS connected ({len(clients)})")
    try:
        await websocket.send(json.dumps({
            "type": "log", "level": "INFO",
            "text": "✅ AgentForge connected — enter a prompt and click Build"
        }))
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    # Traffic, so that a quiet socket is not mistaken for a
                    # dead one by whatever sits between here and the studio.
                    await websocket.send(json.dumps({"type": "pong"}))
                    continue
                job = _message_job(msg)
                if job:
                    denied = job_denied(msg, user)
                    if denied:
                        await websocket.send(json.dumps({"type": "error", "text": denied}))
                        continue
                    start_run(job[0], job[1], user=user)
            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        WS_USERS.pop(websocket, None)
        log.info(f"WS disconnected ({len(clients)})")


def _message_job(msg: dict):
    """Translate one WebSocket action into its unchanged worker contract."""
    kind = msg.get("type")
    prompt = str(msg.get("prompt") or "").strip()
    project = str(msg.get("project") or "").strip()

    known = {
        "agent_build", "agent_resume", "chat", "agent_update",
        "element_edit", "feature",
    }
    if kind not in known:
        return None
    model = msg.get("model") or default_agent_model()
    qa_model = str(msg.get("qa_model") or "").strip()
    route = str(msg.get("route") or "").strip()
    think = _think_flag(msg)

    if kind == "agent_build" and (prompt or project):
        model = msg.get("design_model") or model if msg.get("prototype_only") else msg.get("builder_model") or model
        args = (
            prompt, model, think, qa_model, project,
            str(msg.get("logo") or "").strip(),
            str(msg.get("srs_id") or "").strip(),
            str(msg.get("stack") or "").strip(),
            # Only the token: the files themselves came over HTTP, because this
            # message travels on a socket that refuses a frame their size.
            str(msg.get("attachments") or "").strip(),
        )
        if bool(msg.get("prototype_only")):
            args += (True,)
        return run_agent_pipeline, args
    if kind == "agent_resume" and project:
        if msg.get("agent") == "designer":
            return run_agent_pipeline, ("", msg.get("design_model") or model, think, qa_model, project, "", "", "", "", True)
        return run_agent_pipeline, (
            "", model, think, qa_model, project)
    if kind in ("chat", "agent_update") and project and prompt:
        return run_chat, (
            project, prompt, model, route, think, qa_model,
            _browser_console(msg)) + ((str(msg["agent"]),) if msg.get("agent") else ())
    if kind == "element_edit" and project and prompt:
        return run_element_edit, (
            project, prompt, msg.get("elements") or msg.get("element") or {},
            model, think, _browser_console(msg), msg.get("shots") or [], route)
    if kind == "feature" and project and prompt:
        return run_feature, (
            project, prompt, model, think, qa_model, route,
            _browser_console(msg))
    return None


# --------------------------------------------------------------------------
# Opening a project, and the small helpers the HTTP layer needs
# --------------------------------------------------------------------------
def bind_host() -> str:
    """Bind to loopback unless LAN access was explicitly enabled."""
    return "0.0.0.0" if load_settings().get("lan_access") else "127.0.0.1"


def _redact_uri(uri: str) -> str:
    """`mongodb+srv://user:pass@host/db` -> `mongodb+srv://user:***@host`.

    Shown in Settings, so the user can confirm which cluster is configured
    without the password being on screen.
    """
    if not uri:
        return ""
    shown = re.sub(r"://([^:/@]+):[^@]*@", r"://\1:***@", uri)
    return shown[:60] + ("…" if len(shown) > 60 else "")
