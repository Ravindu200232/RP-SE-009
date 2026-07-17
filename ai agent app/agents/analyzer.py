"""agents/analyzer.py — the generator's compiler, as a Python client.

Wraps the long-lived `scripts/analyzer.mjs` process (a TypeScript LanguageService over stdio) so a
generation agent can ask "is this file correct?" BEFORE writing it. Measured on a real app: ~0.5-1.3s
per file, against 60-120s to generate one — the check is free, and it catches exactly the classes the
repair LLM could not fix (truncation, `</Alert}`, hallucinated icons, MUI v5 Grid).

Fails SOFT by design: if node or the app's typescript is missing, every call reports clean and
generation proceeds untouched. An analyzer that can't run must never be the reason an app doesn't get
built — the repair harness is still behind it.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path

_NODE = shutil.which("node") or "node"
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "analyzer.mjs"

# The first check pays for building the program (~2.5s); later ones are ~1s. A file that takes longer
# than this is not worth stalling a 10-minute generation over.
_BOOT_TIMEOUT = 90.0
_CALL_TIMEOUT = 60.0


class Analyzer:
    """One analyzer process per generated app. Use as a context manager, or call close()."""

    def __init__(self, project_dir, emit=None):
        # Absolute: the child resolves argv[2] against its own cwd, which IS this directory — a
        # relative path resolves to `<dir>/<dir>`, tsconfig.json is not found, and the analyzer then
        # runs with an empty config (no `jsx`, no `paths`) and reports confident nonsense.
        self.dir = Path(project_dir).resolve()
        self.emit = emit or (lambda *a, **k: None)
        self.proc: subprocess.Popen | None = None
        self.ok = False
        self.ts_version = ""
        self._id = 0
        self._lines: queue.Queue = queue.Queue()
        self._lock = threading.Lock()
        self._start()

    # ── lifecycle ────────────────────────────────────────────────────────────
    def _start(self):
        if not _SCRIPT.exists():
            self._log(f"analyzer disabled: {_SCRIPT.name} not found")
            return
        try:
            self.proc = subprocess.Popen(
                [_NODE, str(_SCRIPT), str(self.dir)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                cwd=str(self.dir),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
        except Exception as e:  # noqa: BLE001
            self._log(f"analyzer disabled: could not start node ({e})")
            return

        threading.Thread(target=self._reader, daemon=True).start()
        hello = self._read(_BOOT_TIMEOUT)
        if not hello or not hello.get("ok"):
            reason = (hello or {}).get("error") or (hello or {}).get("fatal") or "no response"
            self._log(f"analyzer disabled: {reason}")
            self.close()
            return
        self.ok = True
        self.ts_version = hello.get("ts", "?")
        self._log(f"analyzer ready (typescript {self.ts_version}) — checking files before they land")

    def _reader(self):
        try:
            for line in self.proc.stdout:  # type: ignore[union-attr]
                line = line.strip()
                if line:
                    self._lines.put(line)
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._lines.put(None)

    def _read(self, timeout: float):
        try:
            line = self._lines.get(timeout=timeout)
        except queue.Empty:
            return None
        if line is None:
            return None
        try:
            return json.loads(line)
        except Exception:  # noqa: BLE001
            return None

    def close(self):
        self.ok = False
        if self.proc:
            try:
                self.proc.stdin.close()  # type: ignore[union-attr]
                self.proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                try:
                    self.proc.kill()
                except Exception:  # noqa: BLE001
                    pass
            self.proc = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def _log(self, text: str):
        self.emit("log", {"text": text})

    # ── protocol ─────────────────────────────────────────────────────────────
    def _call(self, op: str, **kw) -> dict | None:
        if not self.ok or not self.proc:
            return None
        with self._lock:
            self._id += 1
            req = {"id": self._id, "op": op, **kw}
            try:
                self.proc.stdin.write(json.dumps(req) + "\n")  # type: ignore[union-attr]
                self.proc.stdin.flush()  # type: ignore[union-attr]
            except Exception as e:  # noqa: BLE001
                self._log(f"analyzer lost ({e}) — continuing without it")
                self.ok = False
                return None
            res = self._read(_CALL_TIMEOUT)
            if res is None:
                self._log("analyzer timed out — continuing without it")
                self.ok = False
                return None
            return res

    # ── ops ──────────────────────────────────────────────────────────────────
    def check(self, rel: str, source: str) -> list[dict]:
        """Diagnostics for `source` as if it were at `rel` — WITHOUT writing it.

        Returns [] when clean or when the analyzer is unavailable (fail-soft: an absent analyzer must
        not block generation). Each diagnostic: {line, column, code, message}."""
        res = self._call("check", path=rel.replace("\\", "/"), source=source)
        if not res or not res.get("ok"):
            return []
        return res.get("diagnostics") or []

    def release(self, rel: str):
        """Drop the in-memory candidate for `rel` (it is now on disk, or abandoned)."""
        self._call("release", path=rel.replace("\\", "/"))

    def interface(self, rel: str) -> dict:
        """{name, props} of the file's default export, read from the AST — the fact a consumer needs
        so it stops guessing (`<Body recipe={x} />` against a body that takes no props)."""
        res = self._call("interface", path=rel.replace("\\", "/"))
        if not res or not res.get("ok"):
            return {}
        return {"name": res.get("name"), "props": res.get("props"), "found": res.get("found")}

    def exports(self, module: str) -> dict:
        """{exists, names} for a module specifier — `@mui/icons-material/Heart` does not exist,
        `Favorite` does, and the model cannot tell without being shown."""
        res = self._call("exports", module=module)
        if not res or not res.get("ok"):
            return {"exists": True, "names": []}  # unknown → do not fabricate a failure
        return {"exists": res.get("exists"), "names": res.get("names") or [],
                "reason": res.get("reason")}


def format_diagnostics(diags: list[dict], limit: int = 6, width: int = 320) -> str:
    """The compiler's own words, for the prompt that regenerates the file.

    Messages are capped: an overload-resolution failure can run ~900 chars of type dumps, which buys
    the model nothing and crowds out the file it is meant to be rewriting."""
    lines = []
    for d in diags[:limit]:
        loc = f"line {d['line']}" if d.get("line") else "?"
        msg = " ".join(str(d.get("message", "")).split())
        if len(msg) > width:
            msg = msg[:width].rstrip() + " …"
        lines.append(f"- {loc}: {msg} (TS{d.get('code')})")
    if len(diags) > limit:
        lines.append(f"- …and {len(diags) - limit} more")
    return "\n".join(lines)
