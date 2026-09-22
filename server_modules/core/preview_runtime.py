"""Stack adapters for the project runtime registry (shared server namespace)."""
from server_modules.services.preview_runtime import (RuntimeRegistry, project_host,
                                                     runtime_environment)
from server_modules.services.preview_link import PreviewLinks
from server_modules.services.process_tree import spawn_owned, stop_owned


# A preview answers on p-<hash>.localhost, which is this machine's name for it.
# A studio opened from anywhere else needs an address of its own (preview_link.py).
PREVIEW_LINKS = PreviewLinks(port=UI_PORT)
# The addresses a studio was opened at, so a published preview knows which
# parent page may talk to it.
STUDIO_ORIGINS: set = set()

RUNTIMES = RuntimeRegistry(stop_process=stop_owned, emit=lambda event: emit(event),
                           ui_port=UI_PORT,
                           public_url=lambda project: PREVIEW_LINKS.url(project_host(project)))


def publish_preview(project: str, studio_origin: str = "") -> dict:
    """An address for this project's app that works away from this machine."""
    runtime = runtime_for(project)
    if studio_origin:
        STUDIO_ORIGINS.add(studio_origin)
    url = PREVIEW_LINKS.open(project_host(runtime.project))
    with runtime.lock:
        RUNTIMES.changed(runtime)          # the studio is watching for this
    return {"ok": True, "publicUrl": url, **RUNTIMES.snapshot(runtime)}


def unpublish_preview(project: str) -> dict:
    PREVIEW_LINKS.close(project_host(str(project or "")))
    return {"ok": True}


def runtime_for(project=None, *, stack=""):
    name = str(project or getattr(RUN, "project", "") or "")
    _, root, error = _owned_dir(PROD_DIR, name, "project name", "project")
    if error:
        raise ValueError(error)
    return RUNTIMES.get(root, stack)


def runtime_from_host(host):
    host = str(host).split(":", 1)[0].lower()
    if not re.fullmatch(r"p-[a-f0-9]{24}\.localhost", host):
        return None
    # Reconstruct stable addresses after a backend restart without persisting
    # stale PIDs or port allocations on disk.
    for directory in PROD_DIR.iterdir():
        if directory.is_dir() and not directory.name.startswith(".") and project_host(directory.name) == host:
            try:
                return runtime_for(directory.name)
            except ValueError:
                return None
    return None


def _runtime_env(runtime):
    ports = RUNTIMES.allocate(runtime, _declared_port_values(runtime.directory))
    return runtime_environment(_project_env(runtime.directory), ports)


def _spawn_preview(runtime, generation):
    root = runtime.directory
    stack = runtime.stack
    env = {**os.environ, **_runtime_env(runtime), "NEXT_TELEMETRY_DISABLED": "1",
           "NODE_ENV": "development", "BROWSER": "none", "FORCE_COLOR": "0", "NO_COLOR": "1",
           "HOST": "127.0.0.1"}
    if stack == "mern-microservices":
        argv = [NPM_BIN, "run", "dev"]
    elif stack == "remix-mongo":
        # Remix v2 runs on Vite, so the flags are Vite's: `--host`, not Next's
        # `--hostname`, and no bundler flag of any kind. Passing Next's spelling
        # here starts the server on a random port and the preview never finds it.
        argv = [NPM_BIN, "run", "dev", "--",
                "--port", str(runtime.port), "--host", "127.0.0.1"]
    else:
        binary = root / "node_modules" / "next" / "dist" / "bin" / "next"
        if binary.is_file():
            argv = [NODE_BIN, str(binary), "dev", *_bundler_flag(root),
                    "--port", str(runtime.port), "--hostname", "127.0.0.1"]
        else:
            argv = [NPM_BIN, "run", "dev", "--",
                    "--port", str(runtime.port), "--host", "127.0.0.1"]
    with runtime.lock:
        if not RUNTIMES.current(runtime, generation):
            return False
        RUNTIMES.release_reservations(runtime)
        proc = spawn_owned(argv, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="replace", env=env)
        runtime.proc = proc

    def pump(stream):
        for line in stream:
            line = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).strip()
            if not line:
                continue
            with runtime.lock:
                if runtime.proc is not proc or not RUNTIMES.current(runtime, generation):
                    break
                runtime.logs.append(line)
                if len(runtime.logs) > 400:
                    del runtime.logs[:200]
                    runtime.dropped += 200
            emit({"type": "log", "project": runtime.project,
                  "level": "WARN" if "error" in line.lower() else "INFO",
                  "text": f"[{runtime.project}] {line[:300]}"})
        stream.close()
    runtime.log_threads = [threading.Thread(target=pump, args=(stream,), daemon=True)
                           for stream in (proc.stdout, proc.stderr)]
    for thread in runtime.log_threads:
        thread.start()
    return True


def wait_for_dev(stack="next", timeout=None, *, runtime=None, generation=None):
    runtime = runtime or runtime_for()
    generation = runtime.generation if generation is None else generation
    deadline = time.monotonic() + (NEXT_READY_TIMEOUT if timeout is None else timeout)
    urls = [f"http://127.0.0.1:{runtime.port}/"]
    if stack == "mern-microservices":
        packages_dir = Path(runtime.directory) / "packages"
        if packages_dir.is_dir():
            existing = {p.name.replace("-", "_").upper() for p in packages_dir.iterdir()
                        if p.is_dir() and (p / "src" / "server.js").is_file()}
            for key, port in runtime.ports.items():
                if key == "PORT":
                    continue
                prefix = key.removesuffix("_PORT").upper()
                if not existing or prefix in existing or "SERVICE" in prefix:
                    urls.append(f"http://127.0.0.1:{port}/health")
        else:
            urls += [f"http://127.0.0.1:{port}/health" for key, port in runtime.ports.items() if key != "PORT"]
    while time.monotonic() < deadline:
        if not RUNTIMES.current(runtime, generation) or not runtime.proc or runtime.proc.poll() is not None:
            return False
        pending = []
        for url in urls:
            response = None
            try:
                # Next's first document request compiles the route. Keep the
                # readiness budget bounded, but don't repeatedly abort it.
                response = requests.get(url, timeout=(1, max(.01, min(30, deadline - time.monotonic()))))
            except requests.RequestException:
                alt = url.replace("://127.0.0.1:", "://localhost:") if "://127.0.0.1:" in url else ""
                if alt:
                    try:
                        response = requests.get(alt, timeout=(1, max(.01, min(30, deadline - time.monotonic()))))
                    except requests.RequestException:
                        pass
            if response is None:
                pending.append(url)
                continue
            if response.status_code >= 500:
                pending.append(url)
            elif response.status_code >= 400 and not (url.endswith("/health") and response.status_code == 404):
                pending.append(url)
            response.close()
        if not pending:
            return RUNTIMES.current(runtime, generation)
        time.sleep(min(.3, max(0, deadline - time.monotonic())))
    runtime.error = "Startup did not become ready: " + ", ".join(pending or urls)
    return False


def launch_runtime(runtime, generation):
    working_on(runtime.project)
    root = runtime.directory
    if not (root / "package.json").is_file():
        runtime.status = "stopped"
        runtime.error = "This app has not been built yet (no package.json)."
        return False
    runtime.stack = stack_of(root) or runtime.stack or "nextjs-mongo"
    MONGO.ensure_running()
    runner = lambda argv, **kwargs: run_runtime_command(runtime, generation, argv, **kwargs)
    if not ensure_node_deps(root, runner=runner):
        raise RuntimeError("The dependencies could not be installed")
    if not RUNTIMES.current(runtime, generation):
        return False
    if runtime.stack == "mern-microservices" and not _ensure_client_bundle(root, runner=runner):
        raise RuntimeError("The client bundle could not be built")
    for attempt in range(3):
        if not RUNTIMES.current(runtime, generation):
            return False
        if _spawn_preview(runtime, generation) and wait_for_dev(runtime.stack, runtime=runtime, generation=generation):
            return True
        # An immediately exiting Node process can be observed before its log
        # readers. Collect its bind error before choosing whether to retry.
        if runtime.proc and runtime.proc.poll() is not None:
            for thread in runtime.log_threads:
                thread.join(timeout=.5)
        with runtime.lock:
            if not RUNTIMES.current(runtime, generation):
                return False
            tail = "\n".join(runtime.logs[-30:])
            collision = "EADDRINUSE" in tail or "address already in use" in tail.lower()
            RUNTIMES._stop_process(runtime)
            RUNTIMES.release_ports(runtime)
            if not collision or attempt == 2:
                runtime.error = runtime.error or tail[-1500:] or "The app exited during startup"
                return False
            runtime.logs.clear()
            runtime.error = ""
    return False


def run_runtime_command(runtime, generation, argv, *, timeout=None, capture_output=False, **kwargs):
    """Startup installs/builds belong to this project, not global cancellation."""
    if capture_output:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with runtime.lock:
        if not RUNTIMES.current(runtime, generation):
            raise RuntimeError("Startup was superseded")
        proc = spawn_owned(argv, **kwargs)
        runtime.proc = proc
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(argv, proc.returncode, stdout, stderr)
    finally:
        with runtime.lock:
            if runtime.proc is proc:
                runtime.proc = None
            stop_owned(proc)


def agent_runtime_environment(runtime, agent, *, service=False):
    with runtime.lock:
        if runtime.deleted:
            raise RuntimeError("This project was deleted")
        # A build may reuse the existing preview for probes. Only launching a
        # replacement service transfers ownership away from that preview.
        if service and runtime.proc:
            RUNTIMES._stop_process(runtime)
            runtime.status, runtime.reason = "stopped", "build"
            RUNTIMES.changed(runtime)
        env = _runtime_env(runtime)
        RUNTIMES.release_reservations(runtime)
        return env


def agent_runtime_info(runtime):
    with runtime.lock:
        env = _runtime_env(runtime)
        return {"ports": dict(runtime.ports), "environment": {
            key: value for key, value in env.items() if key in runtime.ports or key == "PUBLIC_APP_URL"}}


def dev_stderr(stack="next", *, runtime=None):
    runtime = runtime or runtime_for()
    return "\n".join(runtime.logs[-40:])


def _open_project(proj_name, *, background=True):
    runtime = runtime_for(proj_name)
    if _spec_only(runtime.directory):
        return {**RUNTIMES.snapshot(runtime), "status": "specification"}
    if not (runtime.directory / "package.json").is_file():
        return {**RUNTIMES.snapshot(runtime), "status": "stopped", "error": "This app has not been built yet."}
    return RUNTIMES.open(runtime, launch_runtime, background=background)
