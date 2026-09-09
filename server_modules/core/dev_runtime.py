# Development server lifecycle and shared runtime I/O.
def _route_of(payload: dict) -> str:
    """The page a picker-driven edit was made on, for the preview reload."""
    route = (payload or {}).get("route") or "/"
    route = str(route).strip()

    return route if route.startswith("/") and "//" not in route else "/"
def eerr(txt):

    log.error(txt)
    emit({"type": "error", "text": txt})


_STREAM_SEND_LOCK = threading.Lock()
_STREAM_SEND_FILE = ""
_STREAM_SEND_TEXT = ""
_STREAM_SEND_TIMER = None
_STREAM_SEND_DELAY = 0.03
_STREAM_SEND_MAX = 8192


def _take_stream_payload_locked():
    global _STREAM_SEND_FILE, _STREAM_SEND_TEXT, _STREAM_SEND_TIMER
    if not _STREAM_SEND_TEXT:
        _STREAM_SEND_TIMER = None
        return None
    payload = {"type": "stream", "file": _STREAM_SEND_FILE, "token": _STREAM_SEND_TEXT}
    _STREAM_SEND_FILE = ""
    _STREAM_SEND_TEXT = ""
    _STREAM_SEND_TIMER = None
    return payload


def _flush_stream_send():
    with _STREAM_SEND_LOCK:
        payload = _take_stream_payload_locked()
    if payload:
        emit(payload)


def _cancel_stream_timer_locked():
    global _STREAM_SEND_TIMER
    timer = _STREAM_SEND_TIMER
    _STREAM_SEND_TIMER = None
    if timer:
        timer.cancel()


def estream_start(fname):
    _flush_stream_send()
    emit({"type": "stream_start", "file": fname})


def estream(fname, tok):
    global _STREAM_SEND_FILE, _STREAM_SEND_TEXT, _STREAM_SEND_TIMER
    token = str(tok or "")
    if not token:
        return

    pending = None
    send_now = None
    timer_to_start = None
    with _STREAM_SEND_LOCK:
        if _STREAM_SEND_TEXT and _STREAM_SEND_FILE != fname:
            _cancel_stream_timer_locked()
            pending = _take_stream_payload_locked()

        _STREAM_SEND_FILE = fname
        _STREAM_SEND_TEXT += token
        if len(_STREAM_SEND_TEXT) >= _STREAM_SEND_MAX:
            _cancel_stream_timer_locked()
            send_now = _take_stream_payload_locked()
        elif _STREAM_SEND_TIMER is None:
            timer_to_start = threading.Timer(_STREAM_SEND_DELAY, _flush_stream_send)
            timer_to_start.daemon = True
            _STREAM_SEND_TIMER = timer_to_start

    if pending:
        emit(pending)
    if send_now:
        emit(send_now)
    if timer_to_start:
        timer_to_start.start()


def estream_end(f, c):
    _flush_stream_send()
    emit({"type": "stream_end", "file": f, "content": c})

def ephase(payload):      emit({**payload, "type":"phase"})
def echat(text):          emit({"type":"agent_msg",    "text":text})
def ememory(stats):       emit({"type":"memory",       **stats})
def emongo(payload):      emit({**payload, "type":"mongo"})
def ecommand(payload):    emit({**payload, "type":"command"})


def ecreds(accounts, source="plan", verified=None):
    """
    The generated app's demo accounts, for AgentForge's own UI.

    Generated apps used to print these on their own login page — a "Demo
    Accounts" card above the sign-in form listing five addresses and a shared
    password. The prompts now forbid that, so the accounts have to reach the
    developer some other way, and this is it.
    """
    emit({"type": "demo_accounts", "accounts": accounts,
          "source": source, "verified": verified})


_cur_stream = {"name": None, "buf": ""}

def on_token(token: str):
    if token.startswith("\x00START:"):
        fname = token[7:]
        _cur_stream["name"] = fname
        _cur_stream["buf"]  = ""
        estream_start(fname)
    elif token == "\x00END":
        fname = _cur_stream["name"]
        content = _cur_stream["buf"]
        estream_end(fname, content)
        _cur_stream["name"] = None
        _cur_stream["buf"]  = ""
    else:
        _cur_stream["buf"] += token
        estream(_cur_stream["name"] or "generating…", token)


def ensure_model(model: str) -> bool:
    """Check Ollama tags; pull model if missing. Returns True if ready."""

    if is_cloud_model(model):

        # No weights to fetch, but the daemon only proxies a cloud model it
        # has been asked for, so an unregistered one is registered first. With
        # an API key has_model() is already true and nothing is pulled.
        if not ollama.has_model(model):
            elog("INFO", f"   ☁️  Registering cloud model {model} "
                         f"(no download — cloud models carry no weights)…")
            if ollama.pull(model):
                elog("INFO", f"   ✅ {model} registered")
            else:
                elog("WARN", f"   ⚠️  Could not register {model} with "
                             f"Ollama — trying the call anyway")

        via = "API key" if ollama.api_key else \
              "signed-in Ollama" if ollama.signed_in() else None
        if via:
            elog("INFO", f"   ☁️  Cloud model ready: {model} via {via} "
                         f"(ctx {max_context(model):,})")
        else:

            elog("WARN", f"   ☁️  {model}: no API key and Ollama isn't signed "
                         f"in — trying anyway")
        return True

    if ollama.has_model(model):
        elog("INFO", f"   ✅ Model ready: {model}")
        return True

    elog("INFO", f"   📥 Pulling {model} from Ollama (first time only)…")
    ok = ollama.pull(model, on_progress=lambda p: elog("INFO", f"   📥 {model}: {p}%"))
    if ok:
        elog("INFO", f"   ✅ {model} pulled!")
    else:
        elog("ERROR", f"   ❌ Pull failed: {model}")
    return ok

def stop_model(model: str):
    """Unload model from VRAM immediately after use."""
    if is_cloud_model(model):
        return
    ollama.unload(model)
    elog("INFO", f"   🗑️  Unloaded {model}")

def _deps_ready(proj_dir: Path) -> bool:
    """
    Are node_modules already correct for this package.json?

    Stack-agnostic by construction: instead of probing for a specific binary
    (the old code looked for `vite`, which never exists under Next and so made
    `npm install` re-run on every call), check that every dependency
    package.json declares is physically installed.

    That single test also covers the case this needs to catch — when
    `sync_dependencies()` adds a package, its folder is absent and an install
    is triggered — while still recognising installs done by older versions of
    AgentForge, so existing projects are not needlessly reinstalled.
    """
    nm = proj_dir / "node_modules"
    if not nm.is_dir():
        return False
    try:
        pkg = json.loads((proj_dir / "package.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    manifests = [(proj_dir, pkg)]
    workspaces = pkg.get("workspaces") or []
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages") or []
    try:
        for pattern in workspaces:
            for directory in proj_dir.glob(pattern):
                manifest = directory / "package.json"
                if manifest.is_file():
                    manifests.append((directory, json.loads(manifest.read_text(encoding="utf-8"))))
    except (OSError, ValueError):
        return False

    for directory, manifest in manifests:
        deps = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
        # Node resolves from the package outward; npm workspaces commonly hoist
        # to the root while version conflicts remain inside a workspace.
        locations = []
        current = directory
        while True:
            locations.append(current / "node_modules")
            if current == proj_dir:
                break
            if not current.is_relative_to(proj_dir):
                return False
            current = current.parent
        if any(not any((location / name / "package.json").is_file() for location in locations)
               for name in deps):
            return False
    return True


def ensure_node_deps(proj_dir: Path) -> bool:
    if _deps_ready(proj_dir):
        return True

    first = not (proj_dir / "node_modules").is_dir()
    elog("INFO", "📦 Installing dependencies (npm install)…")

    from server_modules.services import NPM_LOCK
    with NPM_LOCK:
        try:
            r = cancel.run(
                [NPM_BIN, "install", "--no-audit", "--no-fund",
                 "--prefer-offline", "--loglevel=error"],
                cwd=proj_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900 if first else 300,
            )
            if r.returncode == 0:
                elog("INFO", "   ✅ npm install complete")
                return True
            elog("ERROR", f"   ❌ npm install failed:\n{(r.stderr or '')[:300]}")
            return False
        except subprocess.TimeoutExpired:
            elog("ERROR", "   ❌ npm install timed out")
            return False
        except Exception as e:
            elog("ERROR", f"   ❌ npm install crashed: {e}")
            return False


def _next_major(proj_dir: Path) -> int:
    """The installed Next.js major version, or 0 when it cannot be read."""
    try:
        manifest = proj_dir / "node_modules" / "next" / "package.json"
        if manifest.is_file():
            version = json.loads(manifest.read_text(encoding="utf-8")).get("version", "")
        else:
            version = (json.loads((proj_dir / "package.json").read_text(encoding="utf-8"))
                       .get("dependencies", {}).get("next", ""))
        found = re.search(r"(\d+)", version or "")
        return int(found.group(1)) if found else 0
    except Exception:                                                # noqa: BLE001
        return 0


def _bundler_flag(proj_dir: Path) -> list:
    """Keep Next 16 on Webpack, where its diagnostics still name real files.

    Turbopack reports the same failures in a different vocabulary, and the
    repair loop reads those messages to find the file at fault.
    """
    return ["--webpack"] if _next_major(proj_dir) >= 16 else []


def detect_stack(proj_dir: Path) -> str:
    """Which framework a generated project uses. AgentForge only builds Next."""
    return "next"


def _kill_proc_tree(proc):
    """Kill a dev server *and its children* — npm/next spawn workers."""
    if proc is None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=15)
            return

        try:
            pgid = os.getpgid(proc.pid)
            own_group = pgid != os.getpgid(0)
        except Exception:
            pgid, own_group = None, False

        if own_group:
            try:
                os.killpg(pgid, signal.SIGTERM)
                proc.wait(timeout=4)
            except Exception:
                pass
            try:
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                pass
            return

        try:
            proc.terminate()
            proc.wait(timeout=4)
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass
    except Exception:
        pass


# `PORT=4000`, `AUTH_PORT=4101`. Values only, so a URL is not mistaken for one.
_PORT_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z0-9_]*PORT)\s*=\s*(\d{2,5})\s*$", re.M)


def declared_ports(proj_dir: Path) -> list[int]:
    """Every port this project's own configuration says it will bind.

    A multi-service app binds one port per service, and only the project knows
    how many or which: the gateway takes `PORT`, each service takes its own
    `<NAME>_PORT`. Reading them here means nothing has to be written down that
    would go stale the moment a stack adds a service - and the alternative was
    a run whose gateway came up while every service behind it died on a port
    an earlier run had never let go of.
    """
    return list(dict.fromkeys(_declared_port_values(proj_dir).values()))


def _declared_port_values(proj_dir: Path) -> dict:
    ports = {}
    for name in (".env.local", ".env", ".env.example"):
        try:
            body = (Path(proj_dir) / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for key, value in _PORT_LINE.findall(body):
            port = int(value)
            if 1024 <= port <= 65535:
                ports.setdefault(key, port)
    return ports


def free_declared_ports(proj_dir: Path) -> list[int]:
    """Take back every port this project is about to bind."""
    freed = [port for port in declared_ports(proj_dir) if port != DEV_PORT]
    for port in freed:
        _kill_port(port)
    return freed


def _kill_port(port: int):
    """Force-kill whatever holds a port, on Windows as well as POSIX."""
    if os.name == "nt":
        try:
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                                 capture_output=True, text=True,
                                 timeout=10).stdout
            pids = set()
            for line in out.splitlines():
                parts = line.split()

                if (len(parts) >= 5 and parts[3] == "LISTENING"
                        and parts[1].rsplit(":", 1)[-1] == str(port)):
                    pids.add(parts[-1])
            for pid in pids - {"0", "4"}:
                subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                               capture_output=True, timeout=10)
            if pids:
                time.sleep(0.5)
        except Exception:
            pass
        return

    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5
        )
        pids = [p.strip() for p in result.stdout.strip().split() if p.strip()]
        for pid in pids:
            try: subprocess.run(["kill", "-9", pid], timeout=3, capture_output=True)
            except: pass
        if pids:
            time.sleep(0.5)
    except Exception:
        pass


def _stop_dev_proc():
    """Terminate the tracked dev server, whatever stack it is."""
    if active_vite.get("proc"):
        _kill_proc_tree(active_vite["proc"])
        active_vite["proc"] = None





_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_PREVIEW_LOCK = threading.RLock()


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def start_next(proj_dir: Path, port: int = DEV_PORT, stack: str = "next"):
    """
    Start `next dev` on DEV_PORT.

    Note the dev server is started directly here: `--host` and `--strictPort`
    flags, and `next dev` exits immediately on unknown arguments. Next is
    launched directly through node rather than `npm run dev`, which removes a
    process layer and makes the tree far more reliable to kill.
    """
    _stop_dev_proc()
    _kill_port(port)
    active_vite["stderr_lines"] = []
    active_vite["ready"] = False
    active_vite["stack"] = stack
    label = "MERN" if stack == "mern-microservices" else "Next.js"

    next_bin = proj_dir / "node_modules" / "next" / "dist" / "bin" / "next"
    flags = _bundler_flag(proj_dir) if stack != "mern-microservices" else []
    if stack == "mern-microservices":
        # The project's supervisor starts its workspaces and the public client.
        argv = [NPM_BIN, "run", "dev"]
    elif next_bin.exists():
        argv = [NODE_BIN, str(next_bin), "dev", *flags,
                "--port", str(port), "--hostname", "127.0.0.1"]
    else:
        argv = [NPM_BIN, "run", "dev", "--", *flags,
                "--port", str(port), "--hostname", "127.0.0.1"]

    env = {**os.environ, **_project_env(proj_dir),
           "NEXT_TELEMETRY_DISABLED": "1",
           "PORT": str(port),
           "NODE_ENV": "development",
           "BROWSER": "none",

           "FORCE_COLOR": "0", "NO_COLOR": "1"}

    kwargs = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
              if os.name == "nt" else {"start_new_session": True})

    try:
        p = subprocess.Popen(
            argv, cwd=proj_dir,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=env, **kwargs)
        active_vite["proc"] = p
    except Exception as error:
        elog("ERROR", f"   {label} could not start: {error}")
        return False

    def _run():
        try:
            def _pump(stream, is_err):
                for line in stream:
                    if active_vite.get("proc") is not p:
                        return
                    l = _strip_ansi(line).strip()
                    if not l:
                        continue
                    active_vite["stderr_lines"].append(l)
                    if len(active_vite["stderr_lines"]) > 400:
                        del active_vite["stderr_lines"][:200]

                        active_vite["dropped"] = active_vite.get("dropped", 0) + 200
                    if any(k in l for k in ("Ready in", "✓ Ready", "- Local:")):
                        active_vite["ready"] = True
                    if is_err or any(k in l for k in
                                     ("Error", "error", "Failed to compile")):
                        elog("WARN", f"   [{label}] {l[:140]}")
                    else:
                        elog("INFO", f"   [{label}] {l[:140]}")

            threading.Thread(target=_pump, args=(p.stderr, True), daemon=True).start()
            _pump(p.stdout, False)
        except Exception as e:
            elog("ERROR", f"   {label} log stream ended: {e}")

    threading.Thread(target=_run, daemon=True).start()
    return True


def _project_env(proj_dir: Path) -> dict:
    values = {}
    for name in (".env", ".env.local"):
        path = Path(proj_dir) / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.strip().removeprefix("export ").partition("=")
            if separator and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key.strip()):
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                values[key.strip()] = value
    return values


def _ensure_client_bundle(proj_dir: Path) -> bool:
    """Build a static workspace client only when its sources are newer."""
    client = Path(proj_dir) / "client"
    if not (client / "package.json").is_file():
        return True
    manifest = json.loads((Path(proj_dir) / "package.json").read_text(encoding="utf-8"))
    if not manifest.get("scripts", {}).get("build"):
        return True
    index = client / "dist" / "index.html"
    built = index.stat().st_mtime if index.is_file() else 0
    changed = not built
    for directory, folders, files in os.walk(client):
        folders[:] = [name for name in folders if name not in {"node_modules", "dist", ".git", "coverage"}]
        if any((Path(directory) / name).stat().st_mtime > built for name in files):
            changed = True
            break
    if not changed:
        return True
    elog("INFO", "   Building the updated client bundle…")
    result = cancel.run([NPM_BIN, "run", "build"], cwd=proj_dir,
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=NEXT_READY_TIMEOUT)
    if result.returncode:
        elog("ERROR", f"Client build failed: {(result.stderr or result.stdout or '')[-1600:]}")
        return False
    return True


def wait_for_next(timeout: int = NEXT_READY_TIMEOUT, port: int = DEV_PORT) -> bool:
    """
    Wait for `next dev` to serve the index route.

    Readiness and compilation are separate: the server accepts connections
    quickly but then blocks while compiling `/`. So poll cheaply for liveness,
    then spend one long request warming the route — which also means Playwright
    never pays for the cold compile. A 500 counts as ready: the server is up
    and a page is throwing, which is exactly what the tester needs to see.
    """
    import urllib.request, urllib.error

    deadline = time.time() + timeout
    live = False
    while time.time() < deadline:
        if active_vite.get("ready"):
            live = True
            break
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                live = True
                break
        except OSError:
            pass
        proc = active_vite.get("proc")
        if proc is not None and proc.poll() is not None:
            elog("ERROR", "   ❌ Next.js dev server exited during startup")
            return False
        time.sleep(0.3)

    if not live:
        elog("ERROR", f"   ❌ Next.js did not start within {timeout}s")
        return False

    remaining = max(30, int(deadline - time.time()))
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=remaining)
        elog("INFO", "   ✅ Next.js compiled and serving")
        return True
    except urllib.error.HTTPError as e:

        elog("WARN", f"   ⚠ Next.js served HTTP {e.code} on /")
        return True
    except Exception as e:
        elog("WARN", f"   ⚠ Next.js warm-up request failed: {e}")
        return True


def next_stderr() -> str:
    """Compile errors from the Next dev server, for the LLM fix prompt."""
    lines = active_vite.get("stderr_lines", [])
    keys = ("Failed to compile", "Module not found", "Can't resolve", "⨯",
            "Error:", "SyntaxError", "ReferenceError", "TypeError",
            "is not exported from", "is not defined",
            "MongoServerSelectionError", "MongoNetworkError", "ECONNREFUSED")
    return "\n".join([l for l in lines if any(k in l for k in keys)][-40:])


def dev_log_mark() -> int:
    """Absolute position of the next line the dev server will print."""
    return (active_vite.get("dropped", 0)
            + len(active_vite.get("stderr_lines", [])))


_DEV_NOISE = re.compile(
    r"^\s*(?:[○✓⚡]|- Local:|- Network:|Ready in\b|Compiling\b|✓ Compiled\b"
    r"|GET .*\b[23]\d\d in\b|POST .*\b[23]\d\d in\b|Attention:|▲ Next\.js)")


def dev_log_since(mark: int, limit: int = 60) -> str:
    """
    Everything the dev server printed since `mark`.

    This exists because `next_stderr()` decides what matters by keyword, and a
    plain `TypeError: Cannot read properties of undefined … at Inventory
    (app/inventory/page.js:86:48)` — the shape of every 500 seen in this
    project — has its *useful* half on continuation lines that no keyword
    matches. Windowing the buffer around the request instead is exact: whatever
    the server printed while we were probing is, by construction, about that
    probe.

    Pairs with `logging.browserToTerminal`, which puts client-side errors into
    the same stream with a `[browser] … (file:line)` prefix.
    """
    lines = active_vite.get("stderr_lines", [])
    start = max(0, mark - active_vite.get("dropped", 0))
    fresh = [l for l in lines[start:] if not _DEV_NOISE.match(l)]
    return "\n".join(fresh[-limit:])


def start_dev_server(proj_dir: Path, stack: str = None, *, request=None):
    """Dispatch to the right dev server for the project's stack."""
    stack = stack_of(proj_dir) or stack
    if stack == "mern-microservices" and not _ensure_client_bundle(proj_dir):
        return False
    with _PREVIEW_LOCK:
        if request is not None and active_vite.get("request") != request:
            return False
        _stop_dev_proc()
        active_vite["dir"] = str(Path(proj_dir).resolve())
        return start_next(proj_dir, stack=stack)


def _dev_alive(timeout: float = 2.0) -> bool:
    """Is the dev server answering right now? Silent — no logs, no waiting."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{DEV_PORT}/",
                                    timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


def wait_for_dev(stack: str = "next", timeout: int = None) -> bool:
    owner = active_vite.get("proc")
    directory = active_vite.get("dir")

    def still_current():
        return active_vite.get("proc") is owner and active_vite.get("dir") == directory

    if stack == "mern-microservices":
        import urllib.request

        root = Path(active_vite["dir"])
        urls = [f"http://127.0.0.1:{DEV_PORT}/"]
        urls += [f"http://127.0.0.1:{port}/health"
                 for name, port in _declared_port_values(root).items()
                 if name != "PORT" and port != DEV_PORT]
        deadline = time.monotonic() + (timeout or NEXT_READY_TIMEOUT)
        pending = urls
        while time.monotonic() < deadline:
            if not still_current():
                return False
            proc = active_vite.get("proc")
            if proc is not None and proc.poll() is not None:
                elog("ERROR", "   MERN supervisor exited during startup")
                return False
            pending = []
            for url in urls:
                try:
                    with urllib.request.urlopen(url, timeout=max(.01, min(2, deadline - time.monotonic()))) as response:
                        if response.status >= 400:
                            pending.append(url)
                except Exception:
                    pending.append(url)
            if not still_current():
                return False
            if not pending:
                elog("INFO", "   ✅ Client and all configured services are ready")
                return True
            time.sleep(min(.3, max(0, deadline - time.monotonic())))
        elog("ERROR", f"   Startup did not become ready: {', '.join(pending)}")
        return False
    ready = wait_for_next(timeout or NEXT_READY_TIMEOUT)
    return ready and still_current()


def dev_stderr(stack: str = "next") -> str:
    return next_stderr()


