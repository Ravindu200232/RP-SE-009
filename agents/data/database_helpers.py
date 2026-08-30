"""
AgentForge-managed MongoDB.

Generated Next.js apps need a database, and AgentForge's promise is that nothing has
to be installed or signed up for. So AgentForge vendors ``mongod`` the same way it
already vendors Node: resolve an existing binary, otherwise fetch the official
archive from ``downloads.mongodb.org``, and run it on 127.0.0.1:27017.

**Only ``mongod`` is downloaded, not the archive.** The Windows ZIP is 923 MB,
of which 91% is debug symbols (`mongod.pdb` alone is 493 MB compressed). Since
`fastdl.mongodb.org` serves `Accept-Ranges: bytes`, we read the ZIP central
directory over HTTP ranges and inflate the single 32.5 MB member we need —
measured at 37.7 MB transferred instead of 922.6 MB. The macOS/Linux tarballs
are ~90 MB and cannot be seeked, so those stream and stop early.

Readiness needs no driver: mongod binds its port only after storage-engine
init, and it logs a "Waiting for connections" marker. Either signal will do, so
this module stays dependency-free — no pymongo, no motor.

Users who already run a server (local or Atlas) can set ``mongodb_uri`` in
``~/.agentforge/settings.json``; AgentForge then downloads and starts nothing. An
already-listening mongod on the port is *adopted*, never killed.
"""
import io
import json
import logging
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import threading
import time
import zipfile
from pathlib import Path

import requests

# Source: llm_client.py — imported helper(s) come from this file.
from agents.core.llm.llm_client import load_settings

log = logging.getLogger("mongo")

FEED_URL = "https://downloads.mongodb.org/current.json"
DEFAULT_PORT = 27017
HOME = Path.home() / ".agentforge" / "mongo"


FALLBACK_VERSION = "8.3.7"
FALLBACK_URLS = {
    ("windows", "x86_64"):
        f"https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-{FALLBACK_VERSION}.zip",
    ("macos", "arm64"):
        f"https://fastdl.mongodb.org/osx/mongodb-macos-arm64-{FALLBACK_VERSION}.tgz",
    ("macos", "x86_64"):
        f"https://fastdl.mongodb.org/osx/mongodb-macos-x86_64-{FALLBACK_VERSION}.tgz",
    ("ubuntu2204", "x86_64"):
        f"https://fastdl.mongodb.org/linux/mongodb-linux-x86_64-ubuntu2204-{FALLBACK_VERSION}.tgz",
}


BUDGET_S = 240


# Returns the current machine architecture in the naming format used by MongoDB downloads.
def _arch() -> str:
    """Return the current machine architecture in the naming format used by MongoDB downloads."""
    m = platform.machine().lower()
    return "arm64" if m in ("arm64", "aarch64") else "x86_64"


# MongoDB publishes per-distro Linux builds — there is no generic one.
def _linux_targets() -> list:
    """MongoDB publishes per-distro Linux builds — there is no generic one."""
    info = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                info[k] = v.strip().strip('"')
    except Exception:
        pass
    dist, ver = info.get("ID", ""), info.get("VERSION_ID", "")
    major = ver.split(".")[0] if ver else ""
    table = {
        ("ubuntu", "24"): "ubuntu2404", ("ubuntu", "22"): "ubuntu2204",
        ("ubuntu", "20"): "ubuntu2004", ("debian", "12"): "debian12",
        ("debian", "11"): "debian11", ("rhel", "9"): "rhel93",
        ("centos", "9"): "rhel93", ("rocky", "9"): "rhel93",
        ("almalinux", "9"): "rhel93", ("rhel", "8"): "rhel8",
        ("amzn", "2023"): "amazon2023",
    }
    picked = table.get((dist, major))

    return ([picked] if picked else []) + ["ubuntu2204", "ubuntu2404", "rhel93"]


# Returns the supported platform target names for this operating system.
def _targets() -> list:
    """Return the supported platform target names for this operating system."""
    if sys.platform.startswith("win"):
        return ["windows"]
    if sys.platform == "darwin":
        return ["macos"]
    return _linux_targets()


# Returns the platform-specific executable filename used to find MongoDB tools.
def _platform_executable(name: str) -> str:
    """Return the platform-specific executable filename used to find MongoDB tools."""
    return f"{name}.exe" if sys.platform.startswith("win") else name


# A user-supplied URI wins over anything AgentForge would manage.
def get_uri_override() -> str:
    """A user-supplied URI wins over anything AgentForge would manage."""
    # From: agents/core/llm/llm_client.py
    return (os.environ.get("MONGODB_URI", "").strip()
            or str(load_settings().get("mongodb_uri", "")).strip())


# Per-project database so generated apps never share collections.
def db_name_for(project: str) -> str:
    """Per-project database so generated apps never share collections."""
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", project or "").strip("_").lower()
    return f"agentforge_{slug[:48]}" if slug else "agentforge_app"


class _RangeReader(io.RawIOBase):
    """
    Random-access reader over an HTTP resource that supports byte ranges.

    Reads are served from a sliding buffer so zipfile's many small reads don't
    become thousands of requests.
    """
    CHUNK = 4 << 20

    # Prepares _RangeReader with the services and starting state it needs before it begins work.
    def __init__(self, url: str, session: requests.Session = None):
        """Prepare this helper with the state it needs."""
        self.url = url
        self.s = session or requests.Session()
        self.pos = 0
        self.buf = b""
        self.buf_start = -1
        self.transferred = 0

        head = self.s.head(url, timeout=30, allow_redirects=True)
        head.raise_for_status()
        if head.headers.get("Accept-Ranges") != "bytes":
            raise RuntimeError("server does not support range requests")
        self.size = int(head.headers["Content-Length"])

    # Checks whether this download stream supports seek operations required by zip readers.
    def seekable(self):
        """Return whether this download stream supports seek operations required by zip readers."""
        return True

    # Checks whether this download stream can be read by archive tools.
    def readable(self):
        """Return whether this download stream can be read by archive tools."""
        return True

    # Move the wrapped download stream to a requested byte position.
    def seek(self, off, whence=io.SEEK_SET):
        """Move the wrapped download stream to a requested byte position."""
        self.pos = (off if whence == io.SEEK_SET else
                    self.pos + off if whence == io.SEEK_CUR else self.size + off)
        return self.pos

    # Returns the current byte position of the wrapped download stream.
    def tell(self):
        """Return the current byte position of the wrapped download stream."""
        return self.pos

    # Download one remote file while reporting bounded progress.
    def _fetch(self, start: int, end: int) -> bytes:
        """Download one remote file while reporting bounded progress."""
        r = self.s.get(self.url, headers={"Range": f"bytes={start}-{end}"},
                       timeout=90)
        if r.status_code != 206:
            raise RuntimeError(f"range request returned {r.status_code}")
        self.transferred += len(r.content)
        return r.content

    # Read the requested data without changing it.
    def read(self, n=-1):
        """Read the requested data without changing it."""
        if n is None or n < 0:
            n = self.size - self.pos
        if n <= 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + n, self.size)
        cached = (self.buf_start >= 0 and self.buf_start <= self.pos
                  and end <= self.buf_start + len(self.buf))
        if not cached:
            want = max(n, self.CHUNK)
            self.buf = self._fetch(self.pos, min(self.pos + want, self.size) - 1)
            self.buf_start = self.pos
        off = self.pos - self.buf_start
        out = self.buf[off:off + (end - self.pos)]
        self.pos += len(out)
        return out




class MongoManagerBase:
    """Owns at most one `mongod` child. Every method is safe to call twice."""

    _RESET_SCRIPT = """\
import { MongoClient } from 'mongodb'
import { readFileSync } from 'fs'

const env = Object.fromEntries(
  readFileSync('.env.local', 'utf8')
    .split('\\n')
    .map(l => l.trim())
    .filter(l => l && !l.startsWith('#') && l.includes('='))
    .map(l => [l.slice(0, l.indexOf('=')).trim(),
               l.slice(l.indexOf('=') + 1).trim()]))

const uri = env.MONGODB_URI
const name = env.MONGODB_DB

// The guard that PERMITS a drop. Every database this app creates is
// `agentforge_`-prefixed, so anything else belongs to something that is not
// AgentForge and is refused rather than deleted.
if (!name.startsWith('agentforge_')) {
  console.log(JSON.stringify({ ok: false, error: 'refusing: ' + name }))
  process.exit(1)
}

const client = await new MongoClient(uri).connect()
const before = await client.db(name).listCollections().toArray()
await client.db(name).dropDatabase()
await client.close()
console.log(JSON.stringify({ ok: true, db: name, dropped: before.length }))
"""

    # Prepares MongoManagerBase with the services and starting state it needs before it begins work.
    def __init__(self, port: int = DEFAULT_PORT, home: Path = HOME,
                 callbacks: dict = None):
        """Prepare this helper with the state it needs."""
        self.port = port
        self.home = Path(home)
        self.cb = callbacks or {}
        self.proc = None
        self.binary = None
        self.version = None
        self.available = False

        self.adopted = False
        self.override = False
        self.reason = ""
        self._lock = threading.Lock()
        self._out_lines = []
        self._saw_ready = False

    # Returns the folder containing the managed MongoDB executables.
    @property
    def bin_dir(self) -> Path:
        """Return the folder containing the managed MongoDB executables."""
        return self.home / "bin"

    # Returns the folder containing the managed MongoDB database files.
    @property
    def data_dir(self) -> Path:
        """Return the folder containing the managed MongoDB database files."""
        return self.home / "data"

    # Returns the file used to remember the managed MongoDB process id.
    @property
    def pid_file(self) -> Path:
        """Return the file used to remember the managed MongoDB process id."""
        return self.home / "mongod.pid"

    # Register logging and progress callbacks used by the MongoDB manager.
    def set_callbacks(self, callbacks: dict):
        """Register logging and progress callbacks used by the MongoDB manager."""
        self.cb = callbacks or {}

    # Sends one progress event to the UI callback when a callback exists.
    def _fire(self, name, *a):
        """Send one progress event to the UI callback when a callback exists."""
        fn = self.cb.get(name)
        if fn:
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    # Writes one readable status message through the configured logger.
    def _log(self, lvl, txt):
        """Write one readable status message through the configured logger."""
        self._fire("on_log", lvl, txt)
        log.info(txt)

    # Sends one readable MongoDB status message through the registered callback.
    def _status(self, state, **extra):
        """Send one readable MongoDB status message through the registered callback."""
        self._fire("on_status", {"state": state, **extra})

    # Checks whether a TCP listener currently answers on the MongoDB port.
    def is_port_open(self) -> bool:
        """Return whether a TCP listener currently answers on the MongoDB port."""
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=1.0):
                return True
        except OSError:
            return False


__all__ = [name for name in globals() if not name.startswith("__")]
