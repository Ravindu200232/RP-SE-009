"""Shared contracts and context helpers for dependency-aware feature changes."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from agents.planner.architecture import FileStreamParser
from agents.core.workspace import WorkspaceTools, TOOL_HELP
from agents.features.source_guidance import feature_prompt


LOCAL_IMPORT_RE = re.compile(
    r"""from\s+['"]@/(components/[\w./-]+)['"]""")

log = logging.getLogger("features")

# Legacy public names kept for compatibility.
MAX_FILES = None
MAX_PACKAGES = None
MAX_READS = None
NO_PACKAGE = frozenset({"", "none", "null", "n/a", "n-a", "no package",
                        "no-package", "(none)"})

# These are path-safety boundaries, not complexity limits.
CHANGE_DIRS = ("app/", "components/", "lib/", "styles/", "src/")
CHANGE_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".css")
CHANGE_ROOT_FILES = {
    "middleware.js", "middleware.jsx", "middleware.ts", "middleware.tsx",
    "instrumentation.js", "instrumentation.ts",
    "next.config.js", "next.config.mjs", "next.config.ts",
    "tailwind.config.js", "tailwind.config.mjs", "postcss.config.js",
}

def normalise_change_path(path: str) -> str:
    raw = str(path or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        return ""
    parts = raw.split("/")
    if ".." in parts:
        return ""
    while raw.startswith("./"):
        raw = raw[2:]
    return raw


def safe_change_path(path: str) -> bool:
    rel = normalise_change_path(path)
    if not rel:
        return False
    if rel.startswith(("node_modules/", ".git/", ".next/", ".agentforge/")):
        return False
    if rel in CHANGE_ROOT_FILES:
        return True
    return rel.startswith(CHANGE_DIRS) and rel.endswith(CHANGE_EXTS)


def package_requested(name: str) -> bool:
    return " ".join(str(name or "").strip().lower().split()) not in NO_PACKAGE

def protocol_lines(text: str):
    """Yield normalized ``KIND, payload`` pairs from a line protocol."""
    for raw in str(text or "").splitlines():
        head, sep, rest = raw.strip().partition("::")
        if sep:
            yield head.strip().upper(), rest.strip().strip("`")


def change_entry(text: str) -> dict | None:
    """Parse and safety-check one FILE payload."""
    parts = [part.strip().strip("`") for part in text.split("::")]
    if len(parts) < 2:
        return None
    action, path = parts[0].lower(), normalise_change_path(parts[1])
    if action not in ("new", "edit") or not safe_change_path(path):
        return None
    return {
        "path": path,
        "action": action,
        "kind": parts[2].lower() if len(parts) > 2 else "",
        "why": parts[3] if len(parts) > 3 else "",
    }


def unique_paths(items: list) -> list:
    seen, unique = set(), []
    for item in items:
        if item.get("path") not in seen:
            seen.add(item.get("path"))
            unique.append(item)
    return unique


@dataclass
class FeatureSpec:
    summary: str = ""
    files: list = field(default_factory=list)
    packages: list = field(default_factory=list)
    routes: list = field(default_factory=list)
    written: list = field(default_factory=list)
    rejected: list = field(default_factory=list)

    context: dict = field(default_factory=dict)

    def paths(self) -> set:
        return {f["path"] for f in self.files}

    def is_empty(self) -> bool:
        return not self.files


PLAN_SYSTEM = feature_prompt("PLAN", foundation=True)
REPAIR_SYSTEM = feature_prompt("REPAIR", foundation=True)




class FeaturesAgentBase:
    """Composition over ArchitectAgent, exactly like AnalyzerAgent."""

    COVER_SYSTEM = feature_prompt("COVER")

    MEMORY_TURNS = 8

    MEMORY_CHARS = 14_000

    def __init__(self, arch, project_dir=None, *, callbacks=None, analyzer=None,
                 model=None):
        self.arch = arch
        self.project_dir = project_dir or arch.project_dir
        self.cb = callbacks or {}

        self.model = model or None
        if analyzer is None:
            from agents.analysis.analyzer import AnalyzerAgent
            analyzer = AnalyzerAgent(arch, self.project_dir, callbacks=self.cb)
        self.az = analyzer

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn and callable(fn):
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):
        self._fire("on_log", lvl, txt)
        log.info(txt)

    def _budget_chars(self) -> int:
        return self.az._budget_chars()

    def full_source(self, budget: int = 0) -> str:
        """Return prioritized complete source blocks within the model budget."""
        files = self.az.source_files()
        budget = budget or int(self._budget_chars() * 0.55)

        def rank(rel):
            if rel.startswith("lib/"):
                return 0
            if rel.endswith(("layout.jsx", "layout.js")):
                return 1
            if "/api/" in rel:
                return 2
            if rel.startswith("app/"):
                return 3
            return 4

        out, used = [], 0
        for rel in sorted(files, key=lambda r: (rank(r), r)):
            body = files[rel]
            block = f"--- {rel} ---\n{body}\n"
            if used + len(block) > budget:
                out.append(f"--- {rel} ---\n(omitted — the context budget "
                           f"ran out here)\n")
                continue
            out.append(block)
            used += len(block)
        return "\n".join(out)

    def feature_focus_paths(self, request: str, limit: int | None = None) -> list[str]:
        """Rank likely owners before workspace tools trace dependencies."""
        files = self.az.source_files()
        words = {w for w in re.findall(r"[a-z0-9_]+", str(request or "").lower())
                 if len(w) >= 4 and w not in {"this","that","with","from","page","make","add","update","change","feature"}}
        scored = []
        for rel, body in files.items():
            hay_path = rel.lower()
            hay = str(body or "").lower()[:16000]
            score = sum((8 if w in hay_path else 0) + min(hay.count(w), 4) for w in words)
            if score:
                scored.append((-score, rel))
        ordered = [rel for _, rel in sorted(scored)]
        chosen = ordered if not limit else ordered[:limit]
        for shared in ("app/layout.jsx", "app/layout.js", "components/Navbar.jsx",
                       "components/Navbar.js", "lib/seed.js"):
            if shared in files and shared not in chosen:
                chosen.append(shared)
        return chosen if not limit else chosen[:limit]

    def _focused_source(self, paths: list[str], budget: int) -> str:
        chunks, used = [], 0
        files = self.az.source_files()
        live = getattr(self.arch, "files", {}) or {}
        for rel in paths:
            body = str(live.get(rel, files.get(rel, "")) or "")
            if not body:
                continue
            block = f"\n### {rel}\n```\n{body}\n```\n"
            if used + len(block) > budget and chunks:
                break
            chunks.append(block)
            used += len(block)
        return "".join(chunks)

    def _memory(self) -> list:
        """Replay compact plan/recent reasoning under the current system prompt."""
        convo = getattr(self.arch, "convo", None) or []
        if len(convo) < 3:
            return []
        body = [m for m in convo if m.get("role") in ("user", "assistant")]
        if not body:
            return []

        head, tail = body[:1], body[1:][-self.MEMORY_TURNS:]
        kept, total = [], 0
        for m in reversed(head + tail):
            c = (m.get("content") or "")[:2200]
            if total + len(c) > self.MEMORY_CHARS:
                break
            kept.append({"role": m["role"], "content": c})
            total += len(c)
        kept.reverse()
        if not kept:
            return []
        return ([{"role": "user", "content":
                  "Compact historical receipts from earlier work follow. "
                  "They are context only: CURRENT SOURCE, routes and package.json "
                  "are authoritative when history disagrees."}]
                + kept
                + [{"role": "assistant", "content":
                    "Understood. I remember this project and the choices we "
                    "made in it."}])


__all__ = [name for name in globals() if not name.startswith("__")]
