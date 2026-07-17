"""agents/repair/checkpoint.py — green checkpoints + rollback (P1).

An in-memory snapshot of every generated source file. The harness snapshots a KNOWN-GOOD state (fewer
blockers than before, or fully green) and, when a repair attempt makes things worse (more blockers, new
blockers, a passing check regressed), restores it — so the build never continues from a broken state.
In-memory (not a disk copy) because generated source is small text and restores must be instant.
"""
from __future__ import annotations

import time
from pathlib import Path

_SRC_DIRS = ("app", "components", "lib", "models", "hooks", "types", "features")
_SRC_EXT = (".ts", ".tsx", ".js", ".jsx", ".css", ".json")


class Checkpoint:
    def __init__(self, project_dir):
        self.dir = Path(project_dir)
        self._files: dict[str, str] = {}
        self.meta: dict = {}

    def snapshot(self, label: str, meta: dict | None = None) -> int:
        """Capture the current source tree. Returns the number of files snapshotted."""
        files: dict[str, str] = {}
        for base in _SRC_DIRS:
            root = self.dir / base
            if not root.exists():
                continue
            for fp in root.rglob("*"):
                if fp.suffix in _SRC_EXT:
                    try:
                        files[fp.relative_to(self.dir).as_posix()] = fp.read_text(encoding="utf-8")
                    except Exception:
                        pass
        self._files = files
        self.meta = {"label": label, "ts": time.time(), **(meta or {})}
        return len(files)

    def has(self) -> bool:
        return bool(self._files)

    def restore(self, only: set[str] | None = None) -> list[str]:
        """Rewrite snapshotted files that currently differ (optionally limited to `only`).
        Returns the list of files actually restored. Files created after the snapshot are left as-is."""
        restored: list[str] = []
        for rel, content in self._files.items():
            if only is not None and rel not in only:
                continue
            fp = self.dir / rel
            try:
                current = fp.read_text(encoding="utf-8") if fp.exists() else None
            except Exception:
                current = None
            if current != content:
                fp.parent.mkdir(parents=True, exist_ok=True)
                fp.write_text(content, encoding="utf-8")
                restored.append(rel)
        return restored

    def content_of(self, rel: str) -> str | None:
        return self._files.get(rel.replace("\\", "/"))
