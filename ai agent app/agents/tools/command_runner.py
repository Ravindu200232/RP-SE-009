"""agents/tools/command_runner.py — the controlled CommandRunner (P1).

The ONLY way the repair harness runs workspace commands. The model never executes a raw shell string;
it selects an approved **command ID** (`build`, `tsc`, `lint`, `install`, `search`, `deps`, `unit`,
`e2e`) and the runner builds the argv. Every run captures exit code, stdout, stderr, duration, timeout
status, and the set of source files that changed during the command.

Wraps the same subprocess/env conventions already used by `agents/bugfix_agent.build` and `tester.py`.
"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

NPM = os.environ.get("NPM_BIN", r"C:\Program Files\nodejs\npm.CMD")
_BUILD_ENV = {"CI": "true", "MONGODB_URI": "", "NEXT_TELEMETRY_DISABLED": "1"}
_SRC_DIRS = ("app", "components", "lib", "models", "hooks", "types", "features")


@dataclass
class CommandResult:
    id: str
    exit_code: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool
    changed_files: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        return (self.stdout or "") + "\n" + (self.stderr or "")


class CommandRunner:
    """Fixed registry of approved commands. `run(command_id, **args)` is the single entry point."""

    def __init__(self, project_dir, emit=None):
        # Absolute, so a project-local binary path (node_modules/.bin/*.cmd) resolves regardless of cwd.
        self.dir = Path(project_dir).resolve()
        self.emit = emit or (lambda *a, **k: None)

    # ── internals ──────────────────────────────────────────────────────────────
    def _bin(self, name: str) -> str:
        p = self.dir / "node_modules" / ".bin" / (name + (".cmd" if os.name == "nt" else ""))
        return str(p) if p.exists() else name

    def _snapshot(self) -> dict[str, float]:
        snap: dict[str, float] = {}
        for base in _SRC_DIRS:
            root = self.dir / base
            if not root.exists():
                continue
            for fp in root.rglob("*"):
                if fp.suffix in (".ts", ".tsx", ".js", ".jsx", ".json", ".css"):
                    try:
                        snap[fp.as_posix()] = fp.stat().st_mtime
                    except OSError:
                        pass
        return snap

    def _changed(self, before: dict[str, float]) -> list[str]:
        after = self._snapshot()
        changed = [p for p, m in after.items() if before.get(p) != m]
        return sorted(str(Path(p).relative_to(self.dir).as_posix()) for p in changed)

    def _exec(self, cid: str, argv: list[str], timeout: int, env: dict | None = None,
              track_changes: bool = False) -> CommandResult:
        e = {**os.environ, **_BUILD_ENV, **(env or {})}
        before = self._snapshot() if track_changes else {}
        t0 = time.time()
        try:
            r = subprocess.run(argv, cwd=str(self.dir), capture_output=True, text=True,
                               timeout=timeout, env=e)
            code, out, err, timed = r.returncode, r.stdout or "", r.stderr or "", False
        except subprocess.TimeoutExpired as ex:
            code, out, err, timed = -1, (ex.stdout or "") if isinstance(ex.stdout, str) else "", "TIMEOUT", True
        except FileNotFoundError as ex:
            code, out, err, timed = 127, "", f"command not found: {ex}", False
        dur = round(time.time() - t0, 2)
        changed = self._changed(before) if track_changes else []
        return CommandResult(cid, code, out, err, dur, timed, changed)

    # ── approved commands ──────────────────────────────────────────────────────
    _COMMANDS = {"build", "tsc", "lint", "install", "search", "deps"}

    def run(self, command_id: str, **args) -> CommandResult:
        if command_id not in self._COMMANDS:
            raise ValueError(f"unapproved command: {command_id!r} (allowed: {sorted(self._COMMANDS)})")
        return getattr(self, command_id)(**args)

    def build(self) -> CommandResult:
        """`next build` — production build (stops at first hard error)."""
        return self._exec("build", [NPM, "run", "build"], timeout=420)

    def tsc(self) -> CommandResult:
        """`tsc --noEmit` — ALL type/syntax errors at once (the single-diagnosis workhorse)."""
        return self._exec("tsc", [self._bin("tsc"), "--noEmit", "--pretty", "false"], timeout=300)

    def lint(self) -> CommandResult:
        return self._exec("lint", [NPM, "run", "lint", "--", "--format", "compact"], timeout=180)

    def install(self) -> CommandResult:
        return self._exec("install", [NPM, "install"], timeout=600, track_changes=False)

    def deps(self) -> CommandResult:
        """Read package.json (approved-dependency inspection)."""
        pkg = self.dir / "package.json"
        text = pkg.read_text(encoding="utf-8") if pkg.exists() else "{}"
        return CommandResult("deps", 0, text, "", 0.0, False)

    def search(self, pattern: str = "", glob: str = "*.tsx") -> CommandResult:
        """Bounded ripgrep over the workspace (read-only)."""
        rg = self._bin("rg")
        return self._exec("search", [rg, "-n", "--glob", glob, pattern, "."], timeout=60)
