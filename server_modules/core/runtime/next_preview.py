# Next Preview: one focused part of the development-server lifecycle.
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


# Purpose: Handle strip ansi for this focused step.
def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


# Purpose: Start the generated Next.js preview server.
def start_next(proj_dir: Path, port: int = DEV_PORT):
    """
    Start `next dev` on DEV_PORT.

    Note the dev server is started directly here: `--host` and `--strictPort`
    flags, and `next dev` exits immediately on unknown arguments. Next is
    launched directly through node rather than `npm run dev`, which removes a
    process layer and makes the tree far more reliable to kill.
    """
    _stop_dev_proc()
    _kill_project_next(proj_dir)
    _kill_port(port)
    active_vite["stderr_lines"] = []
    active_vite["ready"] = False
    active_vite["stack"] = "next"

    next_bin = proj_dir / "node_modules" / "next" / "dist" / "bin" / "next"
    flags = bundler_flag(proj_dir)
    if next_bin.exists():
        argv = [NODE_BIN, str(next_bin), "dev", *flags,
                "--port", str(port), "--hostname", "127.0.0.1"]
    else:
        argv = [NPM_BIN, "run", "dev", "--", *flags,
                "--port", str(port), "--hostname", "127.0.0.1"]

    env = {**os.environ,
           "NEXT_TELEMETRY_DISABLED": "1",
           "PORT": str(port),
           "NODE_ENV": "development",
           "BROWSER": "none",

           "FORCE_COLOR": "0", "NO_COLOR": "1"}

    kwargs = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
              if os.name == "nt" else {"start_new_session": True})

    # Purpose: Handle run for this focused step.
    def _run():
        try:
            p = subprocess.Popen(
                argv, cwd=proj_dir,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", env=env, **kwargs)
            active_vite["proc"] = p

            # Purpose: Handle pump for this focused step.
            def _pump(stream, is_err):
                for line in stream:
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
                        elog("WARN", f"   [next] {l[:140]}")
                    else:
                        elog("INFO", f"   [next] {l[:140]}")

            threading.Thread(target=_pump, args=(p.stderr, True), daemon=True).start()
            _pump(p.stdout, False)
        except Exception as e:
            elog("ERROR", f"   Next.js crashed: {e}")

    threading.Thread(target=_run, daemon=True).start()


# Purpose: Wait until the Next.js preview server can answer requests.
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


# Purpose: Compile errors from the Next dev server, for the LLM fix prompt.
def next_stderr() -> str:
    """Compile errors from the Next dev server, for the LLM fix prompt."""
    lines = active_vite.get("stderr_lines", [])
    keys = ("Failed to compile", "Module not found", "Can't resolve", "⨯",
            "Error:", "SyntaxError", "ReferenceError", "TypeError",
            "is not exported from", "is not defined",
            "MongoServerSelectionError", "MongoNetworkError", "ECONNREFUSED")
    return "\n".join([l for l in lines if any(k in l for k in keys)][-40:])


# Purpose: Absolute position of the next line the dev server will print.
def dev_log_mark() -> int:
    """Absolute position of the next line the dev server will print."""
    return (active_vite.get("dropped", 0)
            + len(active_vite.get("stderr_lines", [])))


_DEV_NOISE = re.compile(
    r"^\s*(?:[○✓⚡]|- Local:|- Network:|Ready in\b|Compiling\b|✓ Compiled\b"
    r"|GET .*\b[23]\d\d in\b|POST .*\b[23]\d\d in\b|Attention:|▲ Next\.js)")


# Purpose: Everything the dev server printed since `mark`.
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


# Purpose: Start the correct preview server for the generated project.
def start_dev_server(proj_dir: Path, stack: str = None):
    """Dispatch to the right dev server for the project's stack."""
    stack = stack or detect_stack(proj_dir)

    active_vite["dir"] = str(Path(proj_dir).resolve())
    start_next(proj_dir)


# Purpose: Is the dev server answering right now? Silent — no logs, no waiting.
def _dev_alive(timeout: float = 2.0) -> bool:
    """Is the dev server answering right now? Silent — no logs, no waiting."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{DEV_PORT}/",
                                    timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


# Purpose: Wait until the generated project preview is ready.
def wait_for_dev(stack: str = "next", timeout: int = None) -> bool:
    return wait_for_next(timeout or NEXT_READY_TIMEOUT)


# Purpose: Return useful development-server errors for repair.
def dev_stderr(stack: str = "next") -> str:
    return next_stderr()


