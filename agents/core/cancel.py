"""
Stopping a build, at any point, and leaving nothing behind.

A run spends almost all of its wall-clock inside two things: a model that is
streaming tokens, and a child process — `npm install`, `npm run build`, a
Playwright journey — that can hold the thread for minutes. A flag alone
therefore cannot stop a build "at any time": between two checks of a flag
there can be four minutes of webpack. So this keeps a registry of the child
processes a run has started, and cancelling kills them; the thread they were
blocking then returns, sees the flag, and unwinds.

What cancelling means here is a decision the user made explicitly: the build
stops AND the half-built project goes, along with the specification it was
built from. A cancelled run leaves no project in the list to wonder about and
no spec that describes something that was never finished.

The names to remove arrive over the life of the run rather than at its start —
the project directory is not known until a slug has been derived, and the SRS
id only when one was used — so `note()` is called as they become known and
`begin()` starts from nothing.
"""

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
    """
    Raised at the next checkpoint after a cancel was asked for.

    From BaseException and not Exception, for the same reason KeyboardInterrupt
    is: the build is wrapped in `except Exception` at dozens of places that are
    there to keep one flaky step from ending a run, and every one of them would
    swallow this and carry on building the project the user just asked to
    throw away. Only the two handlers that name it get to catch it, and
    `finally` blocks still run, so nothing leaks.
    """


_lock = threading.RLock()
_flag = threading.Event()
_running = False
_project = ""
_srs_id = ""
_procs: set = set()

log = None  # set by the server so this module never imports it back


def _say(level: str, text: str) -> None:
    if log is not None:
        try:
            log(level, text)
        except Exception:
            pass



def begin() -> None:
    """A new run starts: no cancel pending, nothing yet to remove."""
    global _running, _project, _srs_id
    with _lock:
        _flag.clear()
        _procs.clear()
        _running = True
        _project = ""
        _srs_id = ""


def note(project: str = "", srs_id: str = "") -> None:
    """Record what this run would have to remove if it were cancelled."""
    global _project, _srs_id
    with _lock:
        if project:
            _project = str(project)
        if srs_id:
            _srs_id = str(srs_id)


def finish() -> None:
    """The run ended on its own terms. Nothing is pending any more."""
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
    """
    Ask the running build to stop, and make the ask land immediately.

    Killing the children is the part that makes this work while a build is
    inside webpack rather than between stages. The flag on its own would be
    honoured only at the next checkpoint, which can be several minutes away.
    """
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
    """Raise if a cancel is pending. Called wherever a run can safely unwind."""
    if _flag.is_set():
        raise BuildCancelled()



class track:
    """
    Context manager that makes one child process killable by `request()`.

        with cancel.track(proc):
            proc.wait()

    A process that has already exited is dropped on the way out, so the
    registry never grows over a long run.
    """

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
    """
    Kill a child and everything it started.

    `npm` and `py` are launchers: they spawn the process that does the work and
    wait on it. Killing the launcher alone leaves node or python running, still
    holding the port and the project directory, and the delete that follows
    then fails on Windows with the files locked open.
    """
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
    """
    Remove what the cancelled run produced: the project, and its spec.

    `delete_project` is passed in rather than imported because it lives in the
    server module and already carries the fencing this must not duplicate — it
    refuses names that escape `production-ready`, stops the dev server holding
    `.next/` open, and drops the project's database. Passing it keeps one
    implementation of a destructive operation instead of two.

    Both halves are best effort and reported separately. A spec that will not
    delete is worth saying out loud, but it is not a reason to leave a
    half-built project in the list.
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
    """
    `subprocess.run`, but the child can be killed from another thread.

    The signature is deliberately the same for the arguments the build uses,
    so a call site becomes killable by changing `subprocess.run` to
    `cancel.run` and nothing else. What it does not carry over is `input=` and
    `check=` semantics beyond the return code, because nothing here needs them.

    A child killed by `request()` comes back with a non-zero return code, and
    the caller treats it as a failed step — which then reaches the next
    checkpoint and unwinds. That ordering matters: the run must not report the
    failure to the user as a build error, and it does not, because the
    checkpoint raises before any of those paths finish reporting.
    """
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
