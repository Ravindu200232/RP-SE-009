"""Stack adapters for the project runtime registry (shared server namespace)."""
from server_modules.services.preview_runtime import (RuntimeRegistry, project_host,
                                                     runtime_environment)
from server_modules.services.process_tree import spawn_owned, stop_owned


RUNTIMES = RuntimeRegistry(stop_process=stop_owned, emit=lambda event: emit(event), ui_port=UI_PORT)


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
           "NODE_ENV": "development", "BROWSER": "none", "FORCE_COLOR": "0", "NO_COLOR": "1"}
    if stack == "mern-microservices":
        argv = [NPM_BIN, "run", "dev"]
    else:
        binary = root / "node_modules" / "next" / "dist" / "bin" / "next"
        argv = ([NODE_BIN, str(binary), "dev"] if binary.is_file()
                else [NPM_BIN, "run", "dev", "--"])
        argv += [*_bundler_flag(root), "--port", str(runtime.port), "--hostname", "127.0.0.1"]
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
        urls += [f"http://127.0.0.1:{port}/health" for key, port in runtime.ports.items() if key != "PORT"]
    while time.monotonic() < deadline:
        if not RUNTIMES.current(runtime, generation) or not runtime.proc or runtime.proc.poll() is not None:
            return False
        pending = []
        for url in urls:
            try:
                # Next's first document request compiles the route. Keep the
                # readiness budget bounded, but don't repeatedly abort it.
                response = requests.get(url, timeout=(1, max(.01, min(30, deadline - time.monotonic()))))
                if response.status_code >= 400:
                    pending.append(url)
                response.close()
            except requests.RequestException:
                pending.append(url)
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
