"""agents/repair/diagnose.py — the single diagnosis pass + root-cause ordering (P1).

Runs ALL static checks ONCE (module gate → contract scan → `tsc --noEmit`), normalizes every failure
to a common shape, groups them by file, and orders the files **producers-first** (models/types/lib →
api routes → shared components → page bodies → pages) so a producer error is repaired before the
consumer errors it causes. This replaces the "one `next build` per compiler error" loop, which is why
the harness converges in 1–2 rounds instead of dozens.
"""
from __future__ import annotations

import re

from agents import module_gate
from agents.repair import contract_scan

# tsc --noEmit --pretty false → `path(line,col): error TS####: message`
_TSC = re.compile(r"^(.+?\.(?:tsx?|jsx?))\((\d+),(\d+)\):\s*error\s+(TS\d+):\s*(.*)$", re.MULTILINE)

# Producers before consumers. Lower index = fix earlier.
_PRIORITY = (
    "models/", "types/", "lib/", "app/api/",
    "components/features/", "components/layouts/", "components/pages/",
)


def _priority(rel: str) -> int:
    r = rel.replace("\\", "/")
    for i, pat in enumerate(_PRIORITY):
        if r.startswith(pat):
            return i
    if r.startswith("app/") and r.endswith("page.tsx"):
        return len(_PRIORITY)          # route wrappers last
    return len(_PRIORITY) + 1


def _norm(file: str, line: int, code: str, source: str, message: str) -> dict:
    return {"file": file.replace("\\", "/").lstrip("./"), "line": line,
            "code": code, "source": source, "message": message.strip()[:400]}


def diagnose(project_dir, runner, registry: dict | None = None, *, run_tsc: bool = True) -> dict:
    """One pass over every static gate. Returns
    {clusters: [{file, priority, errors:[…]}], counts, blockers}. `clusters` is ordered producers-first."""
    findings: list[dict] = []

    # 1. module resolution (producers of a whole cascade of downstream errors → highest priority)
    for rel, bad in module_gate.scan_project(project_dir).items():
        for b in bad:
            findings.append(_norm(rel, 0, "MODULE", "module", f"Unresolved import '{b['spec']}'"))

    # 2. contract/field drift
    if registry:
        for rel, fs in contract_scan.scan_project(project_dir, registry).items():
            for f in fs:
                findings.append(_norm(rel, f["line"], "CONTRACT", "contract",
                                      f"Unknown field '{f['field']}' for entity {f['entity']}"))

    # 3. tsc — ALL type/syntax errors at once
    tsc_res = None
    if run_tsc:
        tsc_res = runner.run("tsc")
        for m in _TSC.finditer(tsc_res.output):
            findings.append(_norm(m.group(1), int(m.group(2)), m.group(4), "tsc", m.group(5)))

    # group by file, order producers-first (stable by line within a file)
    by_file: dict[str, list[dict]] = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)
    clusters = [
        {"file": rel, "priority": _priority(rel),
         "errors": sorted(errs, key=lambda e: (e["line"], e["code"]))}
        for rel, errs in by_file.items()
    ]
    clusters.sort(key=lambda c: (c["priority"], c["file"]))

    counts = {
        "module": sum(1 for f in findings if f["source"] == "module"),
        "contract": sum(1 for f in findings if f["source"] == "contract"),
        "tsc": sum(1 for f in findings if f["source"] == "tsc"),
    }
    return {
        "clusters": clusters,
        "counts": counts,
        "blockers": len(findings),
        "files": len(clusters),
        "tsc_timed_out": bool(tsc_res and tsc_res.timed_out),
    }
