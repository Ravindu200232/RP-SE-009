"""A public address for one project's running app.

A preview is served on a host of its own - p-<hash>.localhost - because the
generated app asks for "/_next/...", "/api/..." and everything else from the
root, and a path prefix would send those to AgentForge instead. That host only
resolves on this machine, so a studio opened from a phone has nowhere to load
the app from: the frame stays empty while everything else works.

A link fixes that without touching the generated app: one `cloudflared` tunnel
per project, pointed at this server and told which preview host its requests
are for. What it publishes is the app, not AgentForge - this server answers
nothing but that project's preview on a preview host, and 404s the whole
AgentForge API there (preview_http.py).

The address is public to whoever holds it, the way any preview link is. It is
a random four-word name, it lives only while the link does, and closing the
link takes it away.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

ADDRESS = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
READY_SECONDS = 60


def cloudflared() -> str:
    """Where the tunnel program is, or "" when there is none."""
    named = os.environ.get("AGENTFORGE_CLOUDFLARED", "").strip()
    if named and Path(named).is_file():
        return named
    beside_settings = (Path.home() / ".agentforge"
                       / ("cloudflared.exe" if os.name == "nt" else "cloudflared"))
    if beside_settings.is_file():
        return str(beside_settings)
    return shutil.which("cloudflared") or ""


class PreviewLinks:
    """The public address of each preview that has one."""

    def __init__(self, *, port: int, spawn=None, ready_seconds: float = READY_SECONDS):
        self.port = port
        self.spawn = spawn or self._spawn
        self.ready_seconds = ready_seconds
        self._lock = threading.RLock()
        self._links: dict = {}

    def url(self, host: str) -> str:
        """This preview's public address, or "" - a dead tunnel has none."""
        with self._lock:
            link = self._links.get(host)
            if not link:
                return ""
            if link["proc"].poll() is not None:
                self._links.pop(host, None)
                return ""
            return link["url"]

    def open(self, host: str) -> str:
        """This preview's public address, published if it was not already.

        Raises ValueError when there is no way to publish one.
        """
        existing = self.url(host)
        if existing:
            return existing
        program = cloudflared()
        if not program:
            raise ValueError(
                "This app can only be opened on the machine AgentForge runs on: "
                "cloudflared is not installed. Put cloudflared in ~/.agentforge "
                "and try again.")
        proc = self.spawn(program, host)
        url = self._address_of(proc)
        if not url:
            self._end(proc)
            raise ValueError("The address could not be published - try again in a moment")
        with self._lock:
            # Another request may have published one while this was starting.
            already = self._links.get(host)
            if already and already["proc"].poll() is None:
                self._end(proc)
                return already["url"]
            self._links[host] = {"url": url, "proc": proc}
        return url

    def close(self, host: str) -> None:
        with self._lock:
            link = self._links.pop(host, None)
        if link:
            self._end(link["proc"])

    def close_all(self) -> None:
        with self._lock:
            links, self._links = list(self._links.values()), {}
        for link in links:
            self._end(link["proc"])

    def _spawn(self, program: str, host: str):
        return subprocess.Popen(
            [program, "tunnel", "--no-autoupdate",
             "--url", f"http://127.0.0.1:{self.port}", "--http-host-header", host],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def _address_of(self, proc) -> str:
        """The address the tunnel prints, waited for on a thread of its own.

        The thread keeps reading afterwards: a pipe nobody empties fills up,
        and then the tunnel stops answering.
        """
        found: dict = {}
        ready = threading.Event()

        def read():
            try:
                for line in proc.stdout or ():
                    if not ready.is_set():
                        match = ADDRESS.search(line or "")
                        if match:
                            found["url"] = match.group(0)
                            ready.set()
            except (OSError, ValueError):
                pass
            finally:
                ready.set()

        threading.Thread(target=read, daemon=True, name="preview-link").start()
        ready.wait(self.ready_seconds)
        return found.get("url", "")

    @staticmethod
    def _end(proc) -> None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:                                            # noqa: BLE001
            try:
                proc.kill()
            except Exception:                                        # noqa: BLE001
                pass
