"""Stage-wise E2E result accounting.

The browser may retry a journey several times while repairing it.  QA reports must
never count those retries as extra tests.  This module turns the *latest accepted
scenario/run* into one stable stage ledger and aggregates those ledgers once.
"""
from __future__ import annotations


def _name(value) -> str:
    return str(value or "").strip()


def _failure_index(scenario, failures, evidence=None) -> int:
    evidence = evidence or {}
    try:
        idx = int(evidence.get("failed_index", -1))
        if 0 <= idx < len(getattr(scenario, "steps", []) or []):
            return idx
    except Exception:
        pass
    names = {_name(getattr(f, "name", "")) for f in (failures or [])}
    for i, step in enumerate(getattr(scenario, "steps", []) or []):
        if _name(step.describe()) in names:
            return i
    return -1


def stage_result(scenario, failures=None, evidence=None, *, authoring_failed=False) -> dict:
    """Return a deterministic status for every stage in one browser journey."""
    failures = list(failures or [])
    steps = list(getattr(scenario, "steps", []) or [])
    total = len(steps)
    evidence = evidence or {}

    if authoring_failed:
        rows = [{"index": i + 1, "label": step.describe(), "status": "not_reached"}
                for i, step in enumerate(steps)]
        return _summary(rows)

    if not failures:
        rows = [{"index": i + 1, "label": step.describe(), "status": "pass"}
                for i, step in enumerate(steps)]
        return _summary(rows)

    failed_at = _failure_index(scenario, failures, evidence)
    rows = []
    if failed_at >= 0:
        for i, step in enumerate(steps):
            status = "pass" if i < failed_at else "fail" if i == failed_at else "not_reached"
            rows.append({"index": i + 1, "label": step.describe(), "status": status})
    else:
        # The browser completed its scripted steps and a post-condition failed
        # (for example persisted side-effect proof). Keep the successful user
        # actions and expose that proof as its own real E2E stage.
        completed = bool(evidence.get("completed")) or bool(steps)
        for i, step in enumerate(steps):
            rows.append({"index": i + 1, "label": step.describe(),
                         "status": "pass" if completed else "not_reached"})
        first = failures[0] if failures else None
        rows.append({"index": len(rows) + 1,
                     "label": _name(getattr(first, "name", "")) or "Journey proof",
                     "status": "fail"})
    return _summary(rows)


def _summary(rows) -> dict:
    passed = sum(1 for row in rows if row.get("status") == "pass")
    failed = sum(1 for row in rows if row.get("status") == "fail")
    not_reached = sum(1 for row in rows if row.get("status") == "not_reached")
    total = len(rows)
    return {
        "stage_total": total,
        "stage_passed": passed,
        "stage_failed": failed,
        "stage_not_reached": not_reached,
        "stage_rate": round(passed * 100 / total) if total else 0,
        "stages": rows,
    }


def apply_stage_result(out: dict, scenario, failures=None, evidence=None, *, authoring_failed=False) -> dict:
    out.update(stage_result(scenario, failures, evidence, authoring_failed=authoring_failed))
    return out


def aggregate_e2e(out: dict) -> dict:
    """Aggregate final journey ledgers plus the one global integrity proof."""
    flows = list(out.get("flows") or [])
    passed = sum(int(f.get("stage_passed") or 0) for f in flows)
    total = sum(int(f.get("stage_total") or 0) for f in flows)
    failed = sum(int(f.get("stage_failed") or 0) for f in flows)
    not_reached = sum(int(f.get("stage_not_reached") or 0) for f in flows)

    global_proof = out.get("global_integrity") or {}
    if global_proof.get("ran"):
        total += 1
        if global_proof.get("passed"):
            passed += 1
        else:
            failed += 1

    out["stage_total"] = total
    out["stage_passed"] = passed
    out["stage_failed"] = failed
    out["stage_not_reached"] = not_reached
    out["stage_rate"] = round(passed * 100 / total) if total else 0
    return out
