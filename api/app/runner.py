"""Run Jest in a Node service and parse the JSON output."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .models import FileResult, JestSummary, TestResult


def node_available() -> bool:
    return shutil.which("node") is not None and shutil.which("npm") is not None


def _find_jest(service_root: Path) -> Path | None:
    """Walk up looking for a node_modules/jest install (supports npm workspaces)."""
    cursor = service_root
    for _ in range(6):
        candidate = cursor / "node_modules" / "jest"
        if candidate.is_dir():
            return candidate
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    return None


def _install_dir(service_root: Path) -> Path:
    """Choose where to run npm install. Prefer a parent that declares workspaces."""
    cursor = service_root.parent
    for _ in range(4):
        pkg = cursor / "package.json"
        if pkg.is_file():
            try:
                import json as _json

                data = _json.loads(pkg.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            if "workspaces" in data:
                return cursor
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    return service_root


def ensure_dependencies(service_root: Path, *, install: bool, log: list[str]) -> bool:
    if _find_jest(service_root) is not None:
        log.append(f"[{service_root.name}] dependencies already installed")
        return True
    if not install:
        log.append(f"[{service_root.name}] node_modules missing and install=False")
        return False

    install_dir = _install_dir(service_root)
    log.append(f"[{service_root.name}] installing dependencies (npm install in {install_dir.name})…")
    try:
        result = subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
            cwd=str(install_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            shell=True,
        )
    except subprocess.TimeoutExpired:
        log.append(f"[{service_root.name}] npm install timed out")
        return False
    if result.returncode != 0:
        log.append(f"[{service_root.name}] npm install failed (exit {result.returncode})")
        if result.stderr:
            log.append(result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "")
        return False
    log.append(f"[{service_root.name}] dependencies ready")
    return True


def run_jest(
    service_root: Path,
    *,
    log: list[str],
    module_kind: str = "cjs",
) -> tuple[FileResult | None, list[FileResult], dict]:
    """Run Jest and return parsed results.

    Returns (overall, per-file results, raw_summary).
    """
    log.append(f"[{service_root.name}] running jest ({module_kind})…")
    jest_dir = _find_jest(service_root)
    if jest_dir is None:
        log.append(f"[{service_root.name}] could not locate jest install")
        return None, [], {}
    jest_bin = jest_dir / "bin" / "jest.js"

    cmd = ["node"]
    env = os.environ.copy()
    if module_kind == "esm":
        # Jest's experimental ESM mode requires this flag - we set it on node and
        # also via NODE_OPTIONS for any child workers Jest spawns.
        cmd.append("--experimental-vm-modules")
        prev = env.get("NODE_OPTIONS", "")
        env["NODE_OPTIONS"] = (prev + " --experimental-vm-modules").strip()

    cmd += [str(jest_bin), "--json", "--testLocationInResults"]

    if module_kind == "esm":
        # Make sure jest discovers .mjs test files even when the project doesn't
        # configure it (most don't).
        cmd += [
            "--testMatch", "**/__tests__/**/*.test.?(m|c)js",
            "--testMatch", "**/?(*.)+(spec|test).?(m|c)js",
        ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(service_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            shell=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        log.append(f"[{service_root.name}] jest timed out")
        return None, [], {}

    payload = _extract_json(result.stdout) or _extract_json(result.stderr)
    if not payload:
        log.append(f"[{service_root.name}] could not parse jest output")
        if result.stderr:
            tail = result.stderr.strip().splitlines()[-3:]
            for line in tail:
                log.append(line)
        return None, [], {}

    file_results: list[FileResult] = []
    for tr in payload.get("testResults", []):
        path = Path(tr.get("name", "")).name
        tests: list[TestResult] = []
        passed = failed = 0
        for assertion in tr.get("assertionResults", []):
            status = assertion.get("status", "pending")
            if status == "passed":
                passed += 1
            elif status == "failed":
                failed += 1
            tests.append(
                TestResult(
                    name=assertion.get("fullName") or assertion.get("title", ""),
                    status=status if status in {"passed", "failed", "skipped", "pending"} else "pending",
                    duration_ms=float(assertion.get("duration") or 0),
                    failure_message=(assertion.get("failureMessages") or [None])[0],
                )
            )
        file_results.append(
            FileResult(
                file=path,
                passed=passed,
                failed=failed,
                total=passed + failed,
                tests=tests,
            )
        )
    log.append(
        f"[{service_root.name}] jest done: "
        f"{payload.get('numPassedTests', 0)} passed, "
        f"{payload.get('numFailedTests', 0)} failed"
    )
    return None, file_results, payload


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    stripped = text.strip()
    # Fast path: jest --json prints a single JSON object on stdout.
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Fallback: scan for a balanced {...} block, respecting JSON strings/escapes.
    start = stripped.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : idx + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def aggregate(file_results_per_service: dict[str, list[FileResult]], duration_ms: float) -> JestSummary:
    summary = JestSummary(duration_ms=duration_ms)
    for service, files in file_results_per_service.items():
        summary.services_tested.append(service)
        for fr in files:
            summary.files.append(fr)
            summary.total_tests += fr.total
            summary.total_passed += fr.passed
            summary.total_failed += fr.failed
    return summary
