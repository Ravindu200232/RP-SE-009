"""Stops a build and removes its unfinished output safely."""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from pathlib import Path

__all__ = [
    "BuildCancelled", "begin", "note", "request", "check", "cancelled",
    "track", "finish", "cleanup", "state", "run",
]


class BuildCancelled(BaseException):
    """Stops the run without being caught as a normal build error."""


_lock = threading.RLock()
_flag = threading.Event()
_running = False
_project = ""
_srs_id = ""
_procs: set = set()

log = None  # The server provides logging without creating a circular import.


def _say(level: str, text: str) -> None:
    if log is not None:
        try:
            log(level, text)
        except Exception:
            pass



def begin() -> None:
    """Start tracking a new run."""
    global _running, _project, _srs_id
    with _lock:
        _flag.clear()
        _procs.clear()
        _running = True
        _project = ""
        _srs_id = ""


def note(project: str = "", srs_id: str = "") -> None:
    """Remember which output belongs to the current run."""
    global _project, _srs_id
    with _lock:
        if project:
            _project = str(project)
        if srs_id:
            _srs_id = str(srs_id)


def finish() -> None:
    """Stop tracking a completed run."""
    global _running
    with _lock:
        _running = False
        _flag.clear()
        _procs.clear()


def state() -> dict:
    with _lock:
        return {
            "running": _running,
            "cancelling": _flag.is_set(),
            "project": _project,
            "srs_id": _srs_id,
        }



def request() -> dict:
    """Ask the current run to stop and end its active child processes."""
    with _lock:
        if not _running:
            return {"ok": False, "error": "no build is running"}
        _flag.set()
        victims = list(_procs)
        who = {"project": _project, "srs_id": _srs_id}

    for p in victims:
        _kill(p)
    _say("WARN", f"   ⏹ cancel requested — stopping {len(victims)} child process(es)")
    return {"ok": True, **who}


def cancelled() -> bool:
    return _flag.is_set()


def check() -> None:
    """Stop at a safe point when cancellation is pending."""
    if _flag.is_set():
        raise BuildCancelled()



class track:
    """Track one child process so cancellation can stop it."""

    def __init__(self, proc):
        self.proc = proc

    def __enter__(self):
        if self.proc is not None:
            with _lock:
                _procs.add(self.proc)
            if _flag.is_set():
                _kill(self.proc)
        return self.proc

    def __exit__(self, *exc):
        with _lock:
            _procs.discard(self.proc)
        return False


def _kill(proc) -> None:
    """Stop a child process and anything it started."""
    try:
        if proc.poll() is not None:
            return
    except Exception:
        return

    try:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=15)
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
    except Exception as e:
        _say("WARN", f"   ⚠ could not stop pid {getattr(proc, 'pid', '?')}: {e}")



def cleanup(prod_dir: Path, delete_project=None) -> dict:
    """Remove the cancelled project's files and saved specification.

    The supplied project remover keeps all project cleanup rules in one place.
    """
    with _lock:
        project, srs_id = _project, _srs_id

    out = {"project": project, "srs_id": srs_id,
           "project_removed": False, "srs_removed": False}

    if project and delete_project is not None:
        try:
            res = delete_project(project)
            out["project_removed"] = not res.get("error")
            if res.get("error"):
                out["project_error"] = res["error"]
        except Exception as e:
            out["project_error"] = f"{type(e).__name__}: {e}"

    if srs_id:
        staged = Path(prod_dir) / ".srs" / str(srs_id)
        try:
            resolved = staged.resolve()
            resolved.relative_to((Path(prod_dir) / ".srs").resolve())
            if resolved.is_dir():
                shutil.rmtree(resolved, ignore_errors=True)
            out["srs_removed"] = not resolved.exists()
        except (ValueError, OSError) as e:
            out["srs_error"] = f"{type(e).__name__}: {e}"

    return out


def run(argv, *, timeout=None, capture_output=False, check=False, **kw):
    """Run a child process that can be stopped by a cancellation request."""
    if capture_output:
        kw.setdefault("stdout", subprocess.PIPE)
        kw.setdefault("stderr", subprocess.PIPE)

    proc = subprocess.Popen(argv, **kw)
    with track(proc):
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill(proc)
            try:
                proc.communicate(timeout=10)
            except Exception:
                pass
            raise

    done = subprocess.CompletedProcess(argv, proc.returncode, out, err)
    if check and done.returncode:
        raise subprocess.CalledProcessError(done.returncode, argv, out, err)
    return done
