"""Commands the run starts, and the ones it has to keep alive.

Three shapes of work, one manager:

* **Finite** - an install, a build, a test suite. Runs to an exit code, which
  the loop reads. Long ones hand back a process id while still running so the
  model can do something useful instead of blocking on npm install.
* **Service** - a dev server or watcher. Never exits by design; readiness is
  proved by reaching its URL, not by waiting for it. Services survive a
  successful run so the preview stays up afterwards.
* **Abandoned** - anything still running when the run ends. Killed, including
  its children: an orphaned dev server holding port 3000 breaks the next run.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

IS_WINDOWS = os.name == "nt"
TAIL_LIMIT = 24_000       # per stream, kept in memory for the model to read
YIELD_AFTER = 25          # seconds before a finite command hands back an id


@dataclass
class Job:
    id: str
    command: str
    cwd: str
    service: bool
    popen: subprocess.Popen
    started: float = field(default_factory=time.time)
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    timed_out: bool = False
    released: bool = False   # a service the run deliberately left running
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def running(self) -> bool:
        return self.popen.poll() is None

    def summary(self) -> dict:
        return {"processId": self.id, "command": self.command[:300],
                "service": self.service, "running": self.running,
                "exitCode": self.exit_code, "elapsed": round(time.time() - self.started, 1)}


def shell_info() -> dict:
    return {"platform": sys.platform,
            "shell": os.environ.get("COMSPEC", "cmd.exe") if IS_WINDOWS else "/bin/sh"}


class Processes:
    """Owns every child process a run starts."""

    def __init__(self, events=None, env: dict | None = None) -> None:
        self.events = events
        self.env = env
        self.env_provider = None
        self.spawn_process = None
        self.stop_process = None
        self.runtime_info = None
        self.jobs: dict[str, Job] = {}

    # -- lifecycle -------------------------------------------------------
    def begin_run(self) -> None:
        """Keep managed services across turns; forget finished jobs."""
        self.jobs = {jid: job for jid, job in self.jobs.items()
                     if job.service and job.running}

    def list(self) -> list[Job]:
        return list(self.jobs.values())

    def services(self) -> list[Job]:
        return [j for j in self.jobs.values() if j.service and j.running]

    def active(self) -> list[Job]:
        return [j for j in self.jobs.values() if j.running]

    def release_services(self) -> None:
        """Hand running services to the caller so a finished build stays live."""
        for job in self.services():
            job.released = True

    # -- running ---------------------------------------------------------
    def start(self, command: str, cwd: str | Path, service: bool = False,
              env: dict | None = None) -> Job:
        runtime_env = self.env_provider(service=service) if self.env_provider else {}
        merged = {**os.environ, **(self.env or {}), **(env or {}), **runtime_env}
        merged.setdefault("CI", "1")
        merged.setdefault("FORCE_COLOR", "0")
        merged.setdefault("NO_COLOR", "1")
        spawn = self.spawn_process or subprocess.Popen
        group = ({} if self.spawn_process else
                 {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if IS_WINDOWS
                 else {"start_new_session": True})
        popen = spawn(
            command, shell=True, cwd=str(cwd), env=merged,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
            **group)
        job = Job(id=uuid.uuid4().hex[:12], command=command, cwd=str(cwd),
                  service=service, popen=popen)
        self.jobs[job.id] = job
        for stream, name in ((popen.stdout, "stdout"), (popen.stderr, "stderr")):
            threading.Thread(target=self._pump, args=(job, stream, name), daemon=True).start()
        return job

    def _pump(self, job: Job, stream, name: str) -> None:
        if stream is None:
            return
        try:
            for line in iter(stream.readline, ""):
                with job.lock:
                    text = getattr(job, name) + line
                    setattr(job, name, text[-TAIL_LIMIT:])
                if self.events:
                    self.events.emit("process", processId=job.id, stream=name, line=line.rstrip())
        except (ValueError, OSError):
            pass
        finally:
            try:
                stream.close()
            except OSError:
                pass

    def wait(self, job: Job, timeout: float) -> dict:
        """Wait for a job, or report it as still running when the budget runs out."""
        deadline = time.time() + max(0.0, timeout)
        while time.time() < deadline:
            if not job.running:
                job.exit_code = job.popen.returncode
                return self.result(job)
            time.sleep(0.15)
        return self.result(job, pending=True)

    def result(self, job: Job, pending: bool = False) -> dict:
        with job.lock:
            out, err = job.stdout, job.stderr
        return {"processId": job.id, "command": job.command, "service": job.service,
                "pending": pending or job.running, "exitCode": job.exit_code,
                "timedOut": job.timed_out, "stdout": out[-TAIL_LIMIT:], "stderr": err[-TAIL_LIMIT:],
                "elapsed": round(time.time() - job.started, 1)}

    def run(self, command: str, cwd: str | Path, timeout: float,
            service: bool = False, yield_after: float = YIELD_AFTER) -> dict:
        """Start a command and either finish it or hand back its id."""
        job = self.start(command, cwd, service=service)
        if service:
            # A service is not supposed to exit. Give it a moment to fail loudly
            # (a port clash, a syntax error) and otherwise report it as up.
            time.sleep(min(3.0, timeout))
            if not job.running:
                job.exit_code = job.popen.returncode
                return {**self.result(job), "startupFailed": True}
            return self.result(job, pending=True)

        outcome = self.wait(job, min(timeout, yield_after))
        if not outcome["pending"]:
            return outcome
        if timeout <= yield_after:
            job.timed_out = True
            self.stop(job.id)
            return {**self.result(job), "timedOut": True}
        return outcome  # still running; the model gets an id and can wait later

    # -- stopping --------------------------------------------------------
    def stop(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job or (not job.running and not getattr(job.popen, "_preview_job", None)):
            return False
        (self.stop_process or self._kill_tree)(job.popen)
        job.exit_code = job.popen.poll()
        return True

    def stop_all(self, keep_services: bool = False) -> None:
        for job in list(self.jobs.values()):
            if keep_services and job.service and job.released:
                continue
            if job.running or getattr(job.popen, "_preview_job", None):
                (self.stop_process or self._kill_tree)(job.popen)
                job.exit_code = job.popen.poll()

    @staticmethod
    def _kill_tree(popen: subprocess.Popen) -> None:
        """Kill the process and its children.

        `npm run dev` is a shell that spawns node; terminating the shell alone
        leaves node holding the port, and the next run then fails to bind with
        an error that has nothing to do with the code.
        """
        try:
            if IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(popen.pid)],
                               capture_output=True, timeout=20, check=False)
            else:
                os.killpg(os.getpgid(popen.pid), signal.SIGTERM)
                try:
                    popen.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(popen.pid), signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            try:
                popen.kill()
            except OSError:
                pass
