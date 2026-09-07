"""A machine snapshot of what the project actually is.

Given to the model before it plans, and refreshed whenever the tree changes.
It exists because of one recurring failure: a model that has not looked writes
an import against a directory that does not exist, gets a module-not-found
error, and then repairs the *import* rather than the layout. Twenty such errors
usually share one cause, and this is what makes that visible in one read.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .sandbox import IGNORED_DIRS

MAX_ENTRIES = 400
INTERESTING = ("package.json", "next.config.mjs", "next.config.js", "vite.config.js",
               "vitest.config.js", "vitest.workspace.js", "tsconfig.json", "jsconfig.json",
               "docker-compose.yml", "Dockerfile", ".env.example")


def _walk(root: Path, depth: int = 4) -> list[str]:
    out = []

    def visit(directory: Path, level: int, prefix: str) -> None:
        if level > depth or len(out) >= MAX_ENTRIES:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for entry in entries:
            if entry.name in IGNORED_DIRS or entry.name.startswith("."):
                continue
            if len(out) >= MAX_ENTRIES:
                out.append(f"{prefix}… (listing truncated)")
                return
            if entry.is_dir():
                out.append(f"{prefix}{entry.name}/")
                visit(entry, level + 1, prefix + "  ")
            else:
                out.append(f"{prefix}{entry.name}")

    visit(root, 1, "")
    return out


def _manifest(root: Path) -> dict:
    try:
        data = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _package_manager(root: Path) -> str:
    for lockfile, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
                           ("package-lock.json", "npm"), ("bun.lockb", "bun")):
        if (root / lockfile).is_file():
            return name
    return "npm"


def _routes(root: Path, limit: int = 60) -> list[str]:
    """Next.js App Router pages and route handlers, by file position."""
    found = []
    for base in (root / "app", root / "src" / "app"):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.name not in ("page.jsx", "page.js", "page.tsx", "route.js", "route.ts"):
                continue
            segments = path.parent.relative_to(base).as_posix()
            url = "/" + re.sub(r"\((?:[^)]*)\)/?", "", segments).strip("/")
            kind = "api" if path.name.startswith("route") else "page"
            found.append(f"{url or '/'} [{kind}] -> {path.relative_to(root).as_posix()}")
            if len(found) >= limit:
                return found
    return found


def _services(root: Path) -> list[str]:
    base = root / "packages"
    if not base.is_dir():
        return []
    return [entry.name for entry in sorted(base.iterdir())
            if entry.is_dir() and (entry / "package.json").is_file()]


def _models(root: Path, limit: int = 40) -> list[str]:
    found = []
    for base in root.rglob("models"):
        if any(part in IGNORED_DIRS for part in base.parts):
            continue
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.js")) + sorted(base.glob("*.jsx")):
            found.append(path.relative_to(root).as_posix())
            if len(found) >= limit:
                return found
    return found


def inspect_layout(root: Path | str) -> dict:
    root = Path(root)
    manifest = _manifest(root)
    layout = {
        "tree": _walk(root),
        "packageManager": _package_manager(root),
        "scripts": dict(list((manifest.get("scripts") or {}).items())[:20]),
        "dependencies": sorted(list((manifest.get("dependencies") or {}).keys()))[:40],
        "devDependencies": sorted(list((manifest.get("devDependencies") or {}).keys()))[:30],
        "routes": _routes(root),
        "services": _services(root),
        "models": _models(root),
        "config": [name for name in INTERESTING if (root / name).is_file()],
    }
    layout["signature"] = hashlib.sha256(
        json.dumps(layout, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return layout


def format_layout(layout: dict) -> str:
    parts = ["PROJECT LAYOUT (machine snapshot - trust this over memory)"]
    if layout["config"]:
        parts.append("Config present: " + ", ".join(layout["config"]))
    parts.append(f"Package manager: {layout['packageManager']}")
    if layout["scripts"]:
        parts.append("Scripts: " + ", ".join(f"{k}={v}" for k, v in layout["scripts"].items()))
    if layout["dependencies"]:
        parts.append("Dependencies: " + ", ".join(layout["dependencies"]))
    if layout["devDependencies"]:
        parts.append("Dev dependencies: " + ", ".join(layout["devDependencies"]))
    if layout["services"]:
        parts.append("Services: " + ", ".join(layout["services"]))
    if layout["routes"]:
        parts.append("Routes:\n" + "\n".join(f"  {row}" for row in layout["routes"]))
    if layout["models"]:
        parts.append("Models: " + ", ".join(layout["models"]))
    parts.append("Tree:\n" + "\n".join(f"  {row}" for row in layout["tree"]))
    return "\n".join(parts)
