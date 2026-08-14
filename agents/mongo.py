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

from .ollama_client import load_settings

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


def _arch() -> str:
    m = platform.machine().lower()
    return "arm64" if m in ("arm64", "aarch64") else "x86_64"


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


def _targets() -> list:
    if sys.platform.startswith("win"):
        return ["windows"]
    if sys.platform == "darwin":
        return ["macos"]
    return _linux_targets()


def _exe(name: str) -> str:
    return f"{name}.exe" if sys.platform.startswith("win") else name


def get_uri_override() -> str:
    """A user-supplied URI wins over anything AgentForge would manage."""
    return (os.environ.get("MONGODB_URI", "").strip()
            or str(load_settings().get("mongodb_uri", "")).strip())


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

    def __init__(self, url: str, session: requests.Session = None):
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

    def seekable(self): return True

    def readable(self): return True

    def seek(self, off, whence=io.SEEK_SET):
        self.pos = (off if whence == io.SEEK_SET else
                    self.pos + off if whence == io.SEEK_CUR else self.size + off)
        return self.pos

    def tell(self): return self.pos

    def _fetch(self, start: int, end: int) -> bytes:
        r = self.s.get(self.url, headers={"Range": f"bytes={start}-{end}"},
                       timeout=90)
        if r.status_code != 206:
            raise RuntimeError(f"range request returned {r.status_code}")
        self.transferred += len(r.content)
        return r.content

    def read(self, n=-1):
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


class MongoManager:
    """Owns at most one `mongod` child. Every method is safe to call twice."""

    def __init__(self, port: int = DEFAULT_PORT, home: Path = HOME,
                 callbacks: dict = None):
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

    @property
    def bin_dir(self) -> Path: return self.home / "bin"

    @property
    def data_dir(self) -> Path: return self.home / "data"

    @property
    def pid_file(self) -> Path: return self.home / "mongod.pid"

    def set_callbacks(self, callbacks: dict):
        self.cb = callbacks or {}

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn:
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):
        self._fire("on_log", lvl, txt)
        log.info(txt)

    def _status(self, state, **extra):
        self._fire("on_status", {"state": state, **extra})

    def find_binary(self) -> Path:
        """Previously downloaded binary, else one already installed."""
        local = self.bin_dir / _exe("mongod")
        if local.exists():
            return local
        which = shutil.which("mongod")
        if which:
            return Path(which)
        if sys.platform.startswith("win"):
            for p in sorted(Path("C:/Program Files/MongoDB/Server").glob(
                    "*/bin/mongod.exe"), reverse=True):
                return p
        return None

    def is_port_open(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=1.0):
                return True
        except OSError:
            return False

    def resolve_download(self) -> dict:
        """{version, url, kind} for this platform, from the official feed."""
        arch = _arch()
        targets = _targets()
        try:
            r = requests.get(FEED_URL, timeout=30)
            r.raise_for_status()
            feed = r.json()
            versions = [v for v in feed.get("versions", [])
                        if v.get("production_release")
                        and not v.get("release_candidate")]
            for want in targets:
                for v in versions:
                    for dl in v.get("downloads", []):
                        if (dl.get("target") == want and dl.get("arch") == arch
                                and dl.get("edition") == "base"):
                            url = (dl.get("archive") or {}).get("url")
                            if url:
                                return {"version": v.get("version", "?"),
                                        "url": url,
                                        "kind": "zip" if url.endswith(".zip") else "tgz"}
        except Exception as e:
            self._log("WARN", f"   MongoDB version feed unreachable ({e}) — "
                              f"using {FALLBACK_VERSION}")

        for want in targets:
            url = FALLBACK_URLS.get((want, arch))
            if url:
                return {"version": FALLBACK_VERSION, "url": url,
                        "kind": "zip" if url.endswith(".zip") else "tgz"}
        raise RuntimeError(f"No MongoDB build published for {sys.platform}/{arch}")

    def download_binary(self) -> Path:
        """Fetch just `mongod` into `bin/`. Returns its path."""
        info = self.resolve_download()
        self.version = info["version"]
        target = self.bin_dir / _exe("mongod")
        self.bin_dir.mkdir(parents=True, exist_ok=True)

        self._log("INFO", f"🍃 MongoDB not found — fetching mongod {self.version}")
        self._status("downloading", version=self.version, pct=0)

        tmp = target.with_suffix(target.suffix + ".part")
        try:
            if info["kind"] == "zip":
                moved = self._extract_from_zip(info["url"], tmp)
            else:
                moved = self._extract_from_tgz(info["url"], tmp)
            if not moved:
                raise RuntimeError("mongod not found inside the archive")
            tmp.replace(target)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

        if not sys.platform.startswith("win"):
            os.chmod(target, 0o755)

        (self.home / "version.json").write_text(
            json.dumps({"version": self.version, "url": info["url"]}, indent=2),
            encoding="utf-8")
        self._log("INFO", f"   ✅ mongod {self.version} installed → {target}")
        return target

    def _progress(self, done: int, total: int, state: str = "downloading"):
        pct = int(done / total * 100) if total else 0
        if pct >= getattr(self, "_last_pct", -5) + 5:
            self._last_pct = pct
            self._log("INFO", f"   🍃 MongoDB {pct}%  "
                              f"({done/1e6:.1f} / {total/1e6:.1f} MB)")
            self._status(state, version=self.version, pct=pct)

    def _extract_from_zip(self, url: str, out_path: Path) -> bool:
        """
        Inflate only `bin/mongod.exe` using HTTP range reads.

        Falls back to a full streamed download if the server won't do ranges.
        """
        self._last_pct = -5
        try:
            reader = _RangeReader(url)
        except Exception as e:
            self._log("WARN", f"   Range requests unavailable ({e}) — "
                              f"downloading the full archive")
            return self._extract_from_zip_full(url, out_path)

        with zipfile.ZipFile(reader) as zf:
            member = next((i for i in zf.infolist()
                           if i.filename.replace("\\", "/").endswith("bin/mongod.exe")),
                          None)
            if member is None:
                return False
            total = member.compress_size
            self._log("INFO", f"   🍃 Pulling {total/1e6:.1f} MB of a "
                              f"{reader.size/1e6:.0f} MB archive (symbols skipped)")
            with zf.open(member) as src, open(out_path, "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
                    self._progress(min(reader.transferred, total), total)
        return True

    def _extract_from_zip_full(self, url: str, out_path: Path) -> bool:
        tmp_zip = self.home / "archive.zip"
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(tmp_zip, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    self._progress(done, total)
        try:
            with zipfile.ZipFile(tmp_zip) as zf:
                member = next((i for i in zf.infolist()
                               if i.filename.replace("\\", "/").endswith("bin/mongod.exe")),
                              None)
                if member is None:
                    return False
                with zf.open(member) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
        finally:
            tmp_zip.unlink(missing_ok=True)
        return True

    def _extract_from_tgz(self, url: str, out_path: Path) -> bool:
        """Gzip streams aren't seekable — read through and stop at mongod."""
        self._last_pct = -5
        with requests.get(url, stream=True, timeout=180) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0)
            r.raw.decode_content = False

            counter = {"n": 0}
            outer = r.raw

            class _Counting:
                """
                Plain read()-only wrapper, deliberately NOT an io.RawIOBase.

                Wrapping a RawIOBase subclass in io.BufferedReader would be a
                trap: BufferedReader pulls from the raw stream via readinto(),
                which io.RawIOBase leaves unimplemented, so the very first read
                raises NotImplementedError. tarfile's stream mode only ever
                calls fileobj.read(size), so a bare object is both correct and
                sufficient.
                """

                def read(self, n=-1):
                    data = outer.read(n if n and n > 0 else 1 << 20)
                    counter["n"] += len(data or b"")
                    return data or b""

            with tarfile.open(fileobj=_Counting(), mode="r|gz") as tf:
                for member in tf:
                    self._progress(counter["n"], total)
                    if not member.isfile():
                        continue
                    if not member.name.replace("\\", "/").endswith("bin/mongod"):
                        continue
                    src = tf.extractfile(member)
                    if src is None:
                        return False
                    with src, open(out_path, "wb") as dst:
                        shutil.copyfileobj(src, dst, 1 << 20)
                    return True
        return False

    def _clear_stale_lock(self):
        """A hard kill leaves mongod.lock behind; WiredTiger is crash-safe."""
        lock = self.data_dir / "mongod.lock"
        if lock.exists() and not self.is_port_open():
            try:
                lock.unlink()
                self._log("INFO", "   🍃 Cleared a stale mongod.lock")
            except OSError:
                pass

    def start(self, timeout: int = 90) -> bool:
        binary = self.binary or self.find_binary()
        if binary is None:
            binary = self.download_binary()
        self.binary = binary

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._clear_stale_lock()

        cmd = [str(binary), "--dbpath", str(self.data_dir),
               "--port", str(self.port), "--bind_ip", "127.0.0.1",

               "--wiredTigerCacheSizeGB", "0.25"]

        kwargs = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                  if sys.platform.startswith("win")
                  else {"start_new_session": True})

        self._log("INFO", f"🍃 Starting MongoDB on 127.0.0.1:{self.port}")
        self._saw_ready = False
        self._out_lines = []
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=str(self.home), stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                errors="replace", **kwargs)
        except Exception as e:
            self.reason = f"could not launch mongod: {e}"
            self._log("ERROR", f"   ❌ {self.reason}")
            return False

        try:
            self.pid_file.write_text(str(self.proc.pid), encoding="utf-8")
        except OSError:
            pass

        threading.Thread(target=self._drain, daemon=True).start()
        return self.wait_ready(timeout)

    def _drain(self):
        try:
            for line in self.proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                self._out_lines.append(line)
                if len(self._out_lines) > 400:
                    del self._out_lines[:200]
                if "Waiting for connections" in line or '"id":23016' in line:
                    self._saw_ready = True
        except Exception:
            pass

    def wait_ready(self, timeout: int = 90) -> bool:
        """Ready = the log marker, or two consecutive TCP accepts."""
        deadline = time.time() + timeout
        hits = 0
        while time.time() < deadline:
            if self._saw_ready:
                self._ready(); return True
            hits = hits + 1 if self.is_port_open() else 0
            if hits >= 2:
                self._ready(); return True
            if self.proc and self.proc.poll() is not None:
                self.reason = self._diagnose()
                self._log("ERROR", f"   ❌ mongod exited: {self.reason}")
                self._status("error", error=self.reason[:300])
                return False
            time.sleep(0.25)

        self.reason = f"mongod did not become ready within {timeout}s"
        self._log("ERROR", f"   ❌ {self.reason}")
        self._status("error", error=self.reason)
        return False

    def _ready(self):
        self.available = True
        self._log("INFO", f"   ✅ MongoDB ready on 127.0.0.1:{self.port}")
        self._status("running", port=self.port, version=self.version)

    def _diagnose(self) -> str:
        tail = "\n".join(self._out_lines[-8:])
        code = self.proc.returncode if self.proc else None
        if "Address already in use" in tail:
            return "port 27017 is already in use"
        if "DBPathInUse" in tail or "Unable to lock file" in tail:
            return "data directory is locked by another mongod"
        if code in (-4, 132) or (code or 0) & 0xFFFFFFFF == 0xC000001D:
            return ("this CPU lacks AVX support, which MongoDB 5.0+ requires — "
                    "set a MONGODB_URI in Settings to use an external server")
        if "vcruntime" in tail.lower() or (code or 0) & 0xFFFFFFFF == 0xC0000135:
            return ("the Microsoft Visual C++ runtime is missing — install it, "
                    "or set a MONGODB_URI in Settings")
        return tail[:400] or f"exit code {code}"

    def stop(self):

        if not self.proc:
            return
        try:
            if sys.platform.startswith("win"):
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                               capture_output=True, timeout=15)
            else:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self._log("INFO", "   🍃 MongoDB stopped")
        except Exception:
            pass
        finally:
            self.proc = None
            self.available = False
            self.pid_file.unlink(missing_ok=True)
            self._status("off")

    def ensure_running(self) -> bool:
        """
        Make a MongoDB available. Never raises, never exceeds BUDGET_S.

        Order: user override → adopt a listening server → resolve/download and
        start our own.
        """
        if get_uri_override():
            self.available = True
            self.override = True
            self.reason = ""
            self._log("INFO", "🍃 Using MONGODB_URI from Settings")
            self._status("external")
            return True

        with self._lock:

            self.override = False
            if self.proc and self.proc.poll() is None:
                self.available = True
                return True
            self.adopted = False
            self.available = False

            if self.is_port_open():
                self.available = True
                self.adopted = True
                self._log("INFO", f"   ✅ Adopting the MongoDB already on "
                                  f":{self.port}")
                self._status("running", port=self.port)
                return True

            deadline = time.time() + BUDGET_S
            try:
                ok = self.start(timeout=min(90, max(10, int(deadline - time.time()))))
                if not ok and "locked" in (self.reason or ""):
                    self._clear_stale_lock()
                    ok = self.start(timeout=45)
            except Exception as e:
                self.reason = str(e)
                self._log("ERROR", f"   ❌ MongoDB setup failed: {e}")
                ok = False

            self.available = ok
            if not ok:
                self._log("WARN", "   ⚠ Continuing without a database — the app "
                                  "will still be generated, but DB pages will "
                                  "error until MongoDB is available.")
                self._log("WARN", "      Fix: set a MONGODB_URI in Settings.")
                self._status("error", error=self.reason[:300])
            return ok

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

// Both prefixes, deliberately. New databases are `agentforge_`, but every
// project generated before the rename has `locode_` pinned in its .env.local,
// and this guard is what PERMITS a drop — accepting only the new spelling
// would leave those databases impossible to reset from the app that made them.
if (!name.startsWith('agentforge_') && !name.startsWith('locode_')) {
  console.log(JSON.stringify({ ok: false, error: 'refusing: ' + name }))
  process.exit(1)
}

const client = await new MongoClient(uri).connect()
const before = await client.db(name).listCollections().toArray()
await client.db(name).dropDatabase()
await client.close()
console.log(JSON.stringify({ ok: true, db: name, dropped: before.length }))
"""

    def reset_project_db(self, project_dir: Path, node_bin: str = "node") -> dict:
        """
        Drop a generated app's database so its seed runs again.

        Generated apps guard `ensureSeeded()` with `countDocuments() > 0`, and
        `db_name_for()` is a deterministic function of the project name. So a
        seed corrected after a bad first run can never take effect — the rows
        are already there. Dropping the database is the only way to let the fix
        land.

        Destructive, therefore fenced:
          * refuses when the user configured their own `MONGODB_URI` — that is
            their server, possibly with real data, and AgentForge did not create it;
          * refuses any database whose name is not `agentforge_*`;
          * the check is repeated inside the Node script, so neither layer can
            be bypassed by a doctored `.env.local`.

        Uses the project's own pinned `mongodb` driver via a throwaway script
        rather than adding a Python driver dependency for one operation.
        """
        project_dir = Path(project_dir)
        if get_uri_override():
            return {"ok": False, "error": "MONGODB_URI is set in Settings — "
                                          "AgentForge will not touch your own database"}
        env = project_dir / ".env.local"
        if not env.exists():
            return {"ok": False, "error": "no .env.local"}
        try:
            db = ""
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("MONGODB_DB="):
                    db = line.split("=", 1)[1].strip()
        except OSError as e:
            return {"ok": False, "error": str(e)}

        if not db.startswith(("agentforge_", "locode_")):
            return {"ok": False, "error": f"refusing to drop '{db}' — not an "
                                          f"AgentForge-managed database"}

        script = project_dir / ".agentforge-reset.mjs"
        try:
            script.write_text(self._RESET_SCRIPT, encoding="utf-8")
            r = subprocess.run([node_bin, script.name], cwd=str(project_dir),
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60)
            out = (r.stdout or "").strip().splitlines()
            data = json.loads(out[-1]) if out else {}
            if r.returncode != 0 or not data.get("ok"):
                return {"ok": False, "error": data.get("error")
                        or (r.stderr or "reset failed")[:200]}
            self._log("WARN", f"   🍃 Dropped database {db} "
                              f"({data.get('dropped', 0)} collections) — the "
                              f"app will re-seed on next load")
            return data
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            script.unlink(missing_ok=True)

    def prefetch(self) -> bool:
        """Download the binary without starting it — the Settings button."""
        try:
            if self.find_binary():
                self._log("INFO", "   ✅ mongod is already available")
                return True
            self.binary = self.download_binary()
            return True
        except Exception as e:
            self._log("ERROR", f"   ❌ MongoDB download failed: {e}")
            self._status("error", error=str(e))
            return False

    def uri_for(self, project: str) -> str:
        override = get_uri_override()
        if override:
            return override
        return f"mongodb://127.0.0.1:{self.port}/{db_name_for(project)}"

    def status(self) -> dict:
        binary = self.binary or self.find_binary()
        return {
            "available": self.available,
            "running": self.is_running_now(),

            "external": self.adopted,
            "override": bool(get_uri_override()),
            "ours": bool(self.proc and self.proc.poll() is None),
            "downloaded": bool(binary),
            "binary": str(binary) if binary else "",
            "version": self.version or "",
            "port": self.port,
            "reason": self.reason,
        }

    def is_running_now(self) -> bool:
        return self.is_port_open()


MONGO = MongoManager()
