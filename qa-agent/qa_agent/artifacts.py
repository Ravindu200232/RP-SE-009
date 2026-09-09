"""Read saved testing artifacts without executing tests or inferring passes."""
from __future__ import annotations

import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path


def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def timestamp(path):
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def screenshot_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if (not path.is_relative_to(root) or path.suffix.lower() != ".png"
            or not any(path.is_relative_to((root / folder).resolve())
                       for folder in (".agent/screenshots", ".agentforge/screenshots"))):
        raise ValueError("Not a project screenshot")
    return path


def screenshots(root, visuals=()):
    rows = []
    for folder in (".agent/screenshots", ".agentforge/screenshots"):
        for candidate in sorted((root / folder).glob("*.png")):
            try:
                path = screenshot_path(root, candidate.relative_to(root))
                with path.open("rb") as stream:
                    header = stream.read(24)
                if header[:8] != b"\x89PNG\r\n\x1a\n":
                    continue
                width, height = struct.unpack(">II", header[16:24])
                relative = path.relative_to(root.resolve()).as_posix()
                review = next((v for v in visuals if str(v.get("filePath", "")).replace("\\", "/")
                               in (relative, path.as_posix())), {})
                rows.append({"path": relative, "name": candidate.stem,
                             "width": width, "height": height, "at": timestamp(path),
                             "status": review.get("status", "captured"),
                             "findings": review.get("findings", "No saved visual review.")})
            except (OSError, ValueError, struct.error):
                continue
    return rows


def saved_vitest(root):
    full = root / ".agentforge/qa/vitest.json"
    data = load(full)
    if isinstance(data, dict) and isinstance(data.get("testResults"), list):
        return {**data, "source": ".agentforge/qa/vitest.json", "recordedAt": timestamp(full)}
    cache = root / "node_modules/.vite/vitest/results.json"
    data = load(cache)
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return None
    rows = []
    for entry in data["results"]:
        if not isinstance(entry, list) or len(entry) != 2:
            continue
        name, result = entry
        if not isinstance(result, dict) or not isinstance(result.get("failed"), bool):
            continue
        rows.append({"file": str(name).lstrip(":"),
                     "status": "failed" if result["failed"] else "passed",
                     "duration": result.get("duration")})
    return {"source": "vitest-cache", "recordedAt": timestamp(cache), "fileResults": rows,
            "note": "Saved Vitest file outcomes. Individual test-case results were not saved; "
                    "these are historical results, not a new test run."} if rows else None


# `router.get('/:slug', ...)` or `app.post('/orders', ...)`. Route modules are
# found by the shape of what they declare, not by where a particular framework
# happens to put them.
_DECLARED_ROUTE = re.compile(
    r"\b(?:router|app)\.(get|post|put|patch|delete|head|options)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.I)


def _linked_tests(root, tests, outcomes, path):
    """The test files that import this handler."""
    linked = []
    for name, source in tests.items():
        for spec in re.findall(r"(?:from\s*|import\s*\(|require\s*\()\s*['\"]([^'\"]+)", source):
            resolved = root / spec[2:] if spec.startswith("@/") else (root / name).parent / spec
            try:
                same = resolved.resolve().with_suffix("") == path.resolve().with_suffix("")
            except OSError:                       # a path that cannot be resolved is not a match
                continue
            if same:
                linked.append({"file": name, "status": outcomes.get(name, "unverified")})
                break
    return linked


def _declared_routes(root, tests, outcomes):
    """Express-style handlers, wherever the project keeps its services.

    The App Router branch below reads a framework convention: a file called
    `route.js` under `app/api` is a route because Next says so. A service
    written on Express says so in its own code instead, and looking only for
    the convention left every microservice project with no route record at all.
    """
    from .harness import ENGINE_DIRS, GUARDED
    from .security import ignored_dirs

    skip = ENGINE_DIRS | ignored_dirs(root)
    rows = []
    for path in sorted(root.rglob("*.js")):
        relative = path.relative_to(root)
        if path.name.endswith(GUARDED) or any(part in skip for part in relative.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        declared = _DECLARED_ROUTE.findall(text)
        if not declared:
            continue
        linked = _linked_tests(root, tests, outcomes, path)
        by_route = {}
        for method, route in declared:
            by_route.setdefault(route, set()).add(method.upper())
        for route, methods in by_route.items():
            rows.append({"route": route, "handler": relative.as_posix(),
                         "methods": sorted(methods), "tests": linked})
    return rows


def contracts(root, tests, vitest):
    """Source inventory and linked test outcomes; not an HTTP contract verdict."""
    outcomes = {r["file"]: r["status"] for r in (vitest or {}).get("fileResults", [])}
    for suite in (vitest or {}).get("testResults", []):
        name = str(suite.get("name", "")).replace("\\", "/")
        for test in tests:
            if name == test or name.endswith("/" + test):
                cases = suite.get("assertionResults") or []
                outcomes[test] = ("failed" if any(c.get("status") == "failed" for c in cases)
                                  else "passed" if cases and all(c.get("status") == "passed" for c in cases)
                                  else "unverified")
    rows = []
    for base in (root / "app/api", root / "src/app/api"):
        for path in sorted(base.rglob("route.*")):
            if path.suffix not in (".js", ".jsx", ".ts", ".tsx") or not path.resolve().is_relative_to(root.resolve()):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            target = path.relative_to(root).as_posix()
            linked = []
            for name, source in tests.items():
                for spec in re.findall(r"(?:from\s*|import\s*\(|require\s*\()\s*['\"]([^'\"]+)", source):
                    resolved = root / spec[2:] if spec.startswith("@/") else (root / name).parent / spec
                    if resolved.resolve().with_suffix("") == path.resolve().with_suffix(""):
                        linked.append({"file": name, "status": outcomes.get(name, "unverified")})
                        break
            rows.append({"route": "/api/" + path.parent.relative_to(base).as_posix().strip("."),
                         "handler": target,
                         "methods": sorted(set(re.findall(r"\bexport\s+(?:async\s+)?(?:function|const|let)\s+(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b", text))),
                         "tests": linked})
    return rows or _declared_routes(root, tests, outcomes)


def enrich(root, data):
    from .harness import collect_test_sources

    root = Path(root)
    tests = collect_test_sources(root)
    data["tests"] = {**(data.get("tests") or {}), **tests}
    data["screenshots"] = screenshots(root, (data.get("report", {}).get("evidence") or {}).get("visuals", []))
    data["contracts"] = contracts(root, data["tests"], data.get("vitest"))
    lessons = load(root / ".agent/knowledge.json")
    data["resolvedBugs"] = [r for r in lessons if isinstance(r, dict) and r.get("verification")] if isinstance(lessons, list) else []
    return data


def recover(root, project):
    from .report import assemble
    from .unit import UnitResult, failures_of
    from .e2e import E2EResult
    from .harness import read_coverage

    root = Path(root)
    vitest = saved_vitest(root)
    unit = UnitResult(ran=bool(vitest), report=vitest, coverage=read_coverage(root))
    unit.unresolved = [{"case": r["file"], "file": r["file"], "diagnosis": "saved file failure",
                        "message": "Vitest saved a failed file outcome; no assertion details were saved."}
                       for r in (vitest or {}).get("fileResults", []) if r["status"] == "failed"]
    unit.unresolved += failures_of(vitest)
    data = assemble(project=project, project_dir=root, unit=unit, e2e=E2EResult(),
                    security=None, evidence={}, runtime=[], manifest={}, tests={}, history=[],
                    stages=("unit",) if vitest else (), complete=False)
    data["recovered"] = True
    data["provenance"] = "Recovered saved artifacts. No tests were rerun. Missing stage details are unverified."
    enrich(root, data)
    recorded = [{"suite": r.get("problem"), "status": "recorded pass", "at": r.get("at"),
                 "detail": r["verification"], "source": ".agent/knowledge.json"}
                for r in data["resolvedBugs"] if r.get("category") == "E2E"
                and "passed" in str(r["verification"]).lower()]
    data["report"]["e2e"]["recordedOutcomes"] = recorded
    data["timeline"] = ([{"kind": "unit", "suite": "Saved Vitest results", "status": "recorded",
                          "at": vitest["recordedAt"], "source": vitest["source"]}] if vitest else [])
    data["timeline"] += [{**r, "kind": "e2e"} for r in recorded]
    data["timeline"] += [{"kind": "screenshot", "suite": r["name"], "status": "captured", "at": r["at"],
                          "source": r["path"]} for r in data["screenshots"]]
    data["timeline"].sort(key=lambda r: r.get("at") or "")
    if not (vitest or data["tests"] or data["screenshots"] or data["contracts"] or data["resolvedBugs"]):
        return {"error": "no test results for this project", "project": project}
    return data
