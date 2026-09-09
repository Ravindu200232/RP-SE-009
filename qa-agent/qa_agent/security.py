"""A static security pass over the generated application.

Checks for exposed secrets, password storage, query injection and unsafe HTML.
Authentication requirements belong to the application's approved contracts and
their unit/E2E tests. A write method or a path called "dashboard" cannot decide
whether a product has accounts, private data or privileged operations.

Every finding names a file and a line, so it is verifiable rather than
advisory.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

CHECKS = {
    "EXPOSED_SECRET": "a NEXT_PUBLIC_ variable holding something secret",
    "FAKE_HASH": "passwords stored without hashing",
    "QUERY_INJECTION": "user input reaching a query unchecked",
    "UNSAFE_HTML": "dangerouslySetInnerHTML on something a user supplied",
}

SECRET_NAMES = re.compile(
    r"NEXT_PUBLIC_[A-Z0-9_]*(SECRET|KEY|TOKEN|PASSWORD|PRIVATE|CREDENTIAL)", re.I)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*(?:body|req|data|input|form)\b", re.I)
HASH_HINTS = re.compile(r"bcrypt|argon2|scrypt|pbkdf2|createHash|hashSync|hash\(", re.I)
UNSAFE_HTML = re.compile(r"dangerouslySetInnerHTML")
INJECTION = re.compile(r"\$where|\bnew\s+Function\b|eval\s*\(", re.I)

SKIP_DIRS = {"node_modules", ".next", ".git", "coverage", "test", "__pycache__",
             ".agentforge", ".agent"}


def ignored_dirs(root: Path | str) -> set[str]:
    """What this project says is not its source, read from its own .gitignore.

    Build output is not source, and a minified bundle contains every
    dangerous-looking string there is: four findings against one Vite bundle
    were enough to mark a clean build unverified. Where that output lands is
    the project's decision though - Next writes `.next`, Vite writes `dist`,
    the next stack will write somewhere else - so it is read from the project
    rather than listed here.

    Only plain entries are honoured. A pattern with no slash matches a
    directory of that name at any depth, which is what git does with it;
    globs, negations and rooted paths are left alone, because half-reading a
    pattern language is worse than not reading it.
    """
    names = set()
    try:
        lines = (Path(root) / ".gitignore").read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return names
    for line in lines:
        entry = line.strip().rstrip("/")
        if not entry or entry.startswith(("#", "!", "/")) or "/" in entry:
            continue
        if any(character in entry for character in "*?[]"):
            continue
        names.add(entry)
    return names


def _sources(root: Path, limit: int = 900):
    skip = SKIP_DIRS | ignored_dirs(root)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in (".js", ".jsx", ".ts", ".tsx", ".mjs"):
            continue
        if any(part in skip for part in path.parts):
            continue
        yield path
        limit -= 1
        if limit <= 0:
            return


def _finding(root: Path, path: Path, line: int, code: str, detail: str) -> dict:
    return {"code": code, "file": path.relative_to(root).as_posix(), "line": line,
            "what": CHECKS[code], "detail": detail[:240]}


def scan(root: Path | str) -> list[dict]:
    root = Path(root)
    findings = []
    for path in _sources(root):
        try:
            body = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = body.splitlines()

        for number, line in enumerate(lines, 1):
            if SECRET_NAMES.search(line):
                findings.append(_finding(root, path, number, "EXPOSED_SECRET", line.strip()))
            if UNSAFE_HTML.search(line):
                findings.append(_finding(root, path, number, "UNSAFE_HTML", line.strip()))
            if INJECTION.search(line):
                findings.append(_finding(root, path, number, "QUERY_INJECTION", line.strip()))
            if PASSWORD_ASSIGN.search(line) and not HASH_HINTS.search(body):
                findings.append(_finding(root, path, number, "FAKE_HASH",
                                         "password stored without a hashing call in this file"))
        if len(findings) > 200:
            break
    return findings[:200]


def audit(root: Path | str, run=None) -> dict:
    """Dependency advisories, by severity. Empty when npm cannot answer."""
    root = Path(root)
    try:
        if run is not None:
            result = run("npm audit --json")
            body = result.get("stdout") or ""
        else:
            completed = subprocess.run(["npm", "audit", "--json"], cwd=str(root),
                                       capture_output=True, text=True, timeout=180, check=False)
            body = completed.stdout
        data = json.loads(body or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}
    counts = ((data.get("metadata") or {}).get("vulnerabilities") or {})
    return {name: value for name, value in counts.items()
            if isinstance(value, int) and value and name != "total"}


def review(root: Path | str, run=None) -> dict:
    return {"findings": scan(root), "audit": audit(root, run)}
