"""Project-owned local runtimes. HTTP and agents share this lifecycle.

The registry never discovers processes by port: only handles it owns may be
stopped. Socket reservations protect allocation inside this backend; a bind
race with another program is handled by the launcher's bounded retry.
"""
from __future__ import annotations

import hashlib
import re
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path


IDLE_SECONDS = 600
SHARED_PORT_KEYS = {"MONGO_PORT", "MONGODB_PORT", "DB_PORT", "DATABASE_PORT",
                    "REDIS_PORT", "POSTGRES_PORT", "MYSQL_PORT", "SMTP_PORT"}


def project_host(project: str) -> str:
    return "p-" + hashlib.sha256(project.encode()).hexdigest()[:24] + ".localhost"


@dataclass(eq=False)
class Runtime:
    directory: Path
    stack: str = ""
    runtime_id: str = ""
    request_id: str = ""
    generation: int = 0
    revision: int = 0
    status: str = "stopped"
    reason: str = ""
    error: str = ""
    proc: object = None
    ports: dict = field(default_factory=dict)
    reservations: list = field(default_factory=list)
    logs: list = field(default_factory=list)
    log_threads: list = field(default_factory=list)
    dropped: int = 0
    last_activity: float = 0
    leases: int = 0
    deleted: bool = False
    lock: object = field(default_factory=threading.RLock)

    @property
    def project(self):
        return self.directory.name

    @property
    def port(self):
        return self.ports.get("PORT", 0)


class RuntimeRegistry:
    def __init__(self, *, stop_process, emit=lambda event: None, ui_port=7824,
                 clock=time.monotonic, idle_seconds=IDLE_SECONDS):
        self.stop_process = stop_process
        self.emit = emit
        self.ui_port = ui_port
        self.clock = clock
        self.idle_seconds = idle_seconds
        self.records = {}
        self.lock = threading.RLock()
        self.port_lock = threading.RLock()
        self.closed = threading.Event()
        self.watcher = None
        self.server_id = uuid.uuid4().hex

    def get(self, directory, stack=""):
        directory = Path(directory).resolve()
        with self.lock:
            runtime = self.records.get(directory)
            if runtime is None or (runtime.deleted and not runtime.leases and directory.is_dir()):
                runtime = self.records[directory] = Runtime(directory, stack)
            if stack:
                runtime.stack = stack
            return runtime

    def all(self):
        with self.lock:
            return list(self.records.values())

    def snapshot(self, runtime):
        with runtime.lock:
            return {"project": runtime.project, "serverId": self.server_id, "requestId": runtime.request_id,
                    "runtimeId": runtime.runtime_id, "revision": runtime.revision,
                    "status": runtime.status, "reason": runtime.reason,
                    "error": runtime.error, "working": bool(runtime.leases),
                    "previewUrl": f"http://{project_host(runtime.project)}:{self.ui_port}/",
                    "idleSeconds": self.idle_seconds}

    def changed(self, runtime):
        # Call while holding runtime.lock. Revision orders HTTP replies and WS
        # notifications, even when a very fast startup completes before POST.
        runtime.revision += 1
        self.emit({"type": "runtime_state", **self.snapshot(runtime)})

    def current(self, runtime, generation):
        return (not runtime.deleted and runtime.generation == generation
                and not self.closed.is_set())

    def open(self, runtime, launch, *, background=True):
        with runtime.lock:
            if runtime.deleted or self.closed.is_set():
                return self.snapshot(runtime)
            if runtime.status == "running" and runtime.proc and runtime.proc.poll() is None:
                runtime.last_activity = self.clock()
                return self.snapshot(runtime)
            if runtime.status == "starting" or runtime.leases:
                return self.snapshot(runtime)
            self._new_start(runtime)
            generation = runtime.generation
            reply = self.snapshot(runtime)
        if background:
            threading.Thread(target=self._launch, args=(runtime, generation, launch),
                             daemon=True, name=f"preview-{runtime.project}").start()
            return reply
        self._launch(runtime, generation, launch)
        return self.snapshot(runtime)

    def _new_start(self, runtime):
        self._stop_process(runtime)
        self.release_ports(runtime)
        runtime.generation += 1
        runtime.runtime_id = uuid.uuid4().hex
        runtime.request_id = uuid.uuid4().hex
        runtime.status, runtime.reason, runtime.error = "starting", "", ""
        runtime.logs, runtime.dropped = [], 0
        self.changed(runtime)

    def restart_for_work(self, runtime, launch):
        """A build hands its temporary servers to one final preview startup."""
        with runtime.lock:
            if runtime.deleted or self.closed.is_set():
                return self.snapshot(runtime)
            self._new_start(runtime)
            generation = runtime.generation
        self._launch(runtime, generation, launch)
        return self.snapshot(runtime)

    def _launch(self, runtime, generation, launch):
        try:
            ready = launch(runtime, generation)
            with runtime.lock:
                if not self.current(runtime, generation):
                    return
                if not ready:
                    raise RuntimeError(runtime.error or "The app did not become ready")
                runtime.status = "running"
                runtime.last_activity = self.clock()
                self.changed(runtime)
        except Exception as error:
            with runtime.lock:
                if self.current(runtime, generation):
                    self._stop_process(runtime)
                    self.release_ports(runtime)
                    runtime.status, runtime.error = "failed", str(error)[:2000]
                    self.changed(runtime)

    def begin_work(self, runtime):
        with runtime.lock:
            # Invalidate an in-flight project-open before the builder starts.
            if runtime.status == "starting" and not runtime.leases:
                self.stop(runtime, reason="build")
            runtime.leases += 1
            runtime.last_activity = self.clock()
            self.changed(runtime)

    def end_work(self, runtime):
        with runtime.lock:
            runtime.leases = max(0, runtime.leases - 1)
            runtime.last_activity = self.clock()
            if not runtime.leases and runtime.proc is None:
                self.release_ports(runtime)
                if runtime.status != "failed":
                    runtime.status, runtime.reason = "stopped", "build-ended"
            self.changed(runtime)

    def activity(self, runtime, runtime_id):
        with runtime.lock:
            if runtime.status != "running" or runtime.runtime_id != runtime_id:
                return False
            runtime.last_activity = self.clock()
            return True

    def _stop_process(self, runtime):
        proc, runtime.proc = runtime.proc, None
        if proc is not None:
            self.stop_process(proc)

    def stop(self, runtime, reason="stopped", *, delete=False):
        with runtime.lock:
            runtime.generation += 1
            runtime.deleted = runtime.deleted or delete
            self._stop_process(runtime)
            self.release_ports(runtime)
            runtime.status, runtime.reason = "stopped", reason
            self.changed(runtime)

    def reap(self):
        for runtime in self.all():
            with runtime.lock:
                if runtime.status != "running" or runtime.leases:
                    continue
                if runtime.proc is None or runtime.proc.poll() is not None:
                    self.stop(runtime, "exited")
                elif self.clock() - runtime.last_activity >= self.idle_seconds:
                    self.stop(runtime, "idle")

    def start_watcher(self):
        if self.watcher is not None:
            return
        def watch():
            while not self.closed.wait(1):
                self.reap()
        self.watcher = threading.Thread(target=watch, daemon=True, name="preview-idle")
        self.watcher.start()

    def close(self):
        self.closed.set()
        for runtime in self.all():
            self.stop(runtime, "shutdown")

    def allocate(self, runtime, declared, *, fresh=False):
        """Reserve all project ports together, excluding shared dependencies."""
        with runtime.lock, self.port_lock:
            if fresh:
                self.release_ports(runtime)
            wanted = {"PORT": declared.get("PORT", 5173),
                      **{key: value for key, value in declared.items()
                         if key.endswith("_PORT") and key not in SHARED_PORT_KEYS}}
            used = {port for other in self.all() for port in other.ports.values()}
            try:
                for key, preferred in wanted.items():
                    if key in runtime.ports:
                        continue
                    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                    try:
                        listener.bind(("127.0.0.1", int(preferred) if int(preferred) not in used else 0))
                    except OSError:
                        listener.bind(("127.0.0.1", 0))
                    port = listener.getsockname()[1]
                    runtime.ports[key] = port
                    runtime.reservations.append(listener)
                    used.add(port)
            except Exception:
                self.release_ports(runtime)
                raise
            return dict(runtime.ports)

    def release_reservations(self, runtime):
        with runtime.lock, self.port_lock:
            for listener in runtime.reservations:
                listener.close()
            runtime.reservations.clear()

    def release_ports(self, runtime):
        with runtime.lock, self.port_lock:
            self.release_reservations(runtime)
            runtime.ports.clear()


def runtime_environment(base, ports):
    """Override bind ports and only corresponding local upstream addresses."""
    env = {**base, **{key: str(value) for key, value in ports.items()}}
    for key, port in ports.items():
        if key == "PORT":
            continue
        url_key = key.removesuffix("_PORT") + "_URL"
        old = env.get(url_key, "")
        if not old:
            env[url_key] = f"http://127.0.0.1:{port}"
        elif re.match(r"^https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?:/|$)", old):
            env[url_key] = re.sub(r"^(https?://)(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?",
                                 rf"\g<1>127.0.0.1:{port}", old)
    env["PUBLIC_APP_URL"] = f"http://127.0.0.1:{ports['PORT']}"
    return env
