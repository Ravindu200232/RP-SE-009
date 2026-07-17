"""agents/tools/fingerprint.py — ProjectFingerprint (P1).

Detects the workspace shape ONCE before any repair: package manager, lockfile, Next/React/TypeScript
versions, tsconfig path aliases, App-Router layout, DB + auth implementation, scripts, test frameworks,
and the PROTECTED files the repair loop must never modify (the fixed core: DB/auth/session/middleware
and the pinned UI primitives).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# The fixed permanent core — repairs must never touch these (regenerating auth/db/ui breaks everything).
_PROTECTED = (
    "lib/mongodb.ts", "lib/api.ts", "lib/auth.ts", "lib/session.ts", "lib/seed.ts",
    "middleware.ts", "app/layout.tsx", "next.config.mjs", "tsconfig.json", "package.json",
)
_PROTECTED_DIRS = ("components/ui", "types")


def _read_json_lenient(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"(?m)//[^\n]*$", "", text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        return json.loads(text)
    except Exception:
        return {}


def fingerprint(project_dir) -> dict:
    d = Path(project_dir)
    pkg = _read_json_lenient(d / "package.json")
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    lock = ("pnpm" if (d / "pnpm-lock.yaml").exists()
            else "yarn" if (d / "yarn.lock").exists()
            else "bun" if (d / "bun.lockb").exists()
            else "npm")
    tsconfig = _read_json_lenient(d / "tsconfig.json")
    aliases = ((tsconfig.get("compilerOptions") or {}).get("paths") or {})
    protected = [p for p in _PROTECTED if (d / p).exists()]
    for pd in _PROTECTED_DIRS:
        if (d / pd).exists():
            protected.append(pd + "/**")
    return {
        "packageManager": lock,
        "versions": {"next": deps.get("next"), "react": deps.get("react"),
                     "typescript": deps.get("typescript"), "mongoose": deps.get("mongoose")},
        "dependencies": sorted(deps),
        "scripts": pkg.get("scripts") or {},
        "pathAliases": aliases or {"@/*": ["./*"]},
        "appRouter": (d / "app").exists(),
        "srcLayout": (d / "src" / "app").exists(),
        "db": "mongoose" if "mongoose" in deps else None,
        "auth": "jose+bcrypt" if ("jose" in deps or "bcryptjs" in deps) else None,
        "testFrameworks": [x for x in ("jest", "vitest", "@playwright/test", "playwright") if x in deps],
        "protectedFiles": protected,
    }


def is_protected(rel: str, fp: dict) -> bool:
    """True if `rel` is a protected file/dir the repair loop must not modify."""
    rel = str(rel).replace("\\", "/")
    for p in fp.get("protectedFiles") or []:
        if p.endswith("/**"):
            if rel.startswith(p[:-3]):
                return True
        elif rel == p:
            return True
    return False
