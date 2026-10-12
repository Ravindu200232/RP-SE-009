"""Small, defensive readers for model-authored QA reports."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _count(value: Any) -> int:
    """Return a non-negative integer where the report supplied one."""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def summary_counts(report: Mapping[str, Any] | Any) -> dict[str, int]:
    """Return display/gate counts from either supported QA report shape."""
    if not isinstance(report, Mapping):
        return {"pass": 0, "fail": 0, "warn": 0}

    summary = report.get("summary")
    if isinstance(summary, Mapping):
        return {
            "pass": _count(summary.get("pass", summary.get("passed"))),
            "fail": _count(summary.get("fail", summary.get("failed"))),
            "warn": _count(summary.get("warn", summary.get("warning", summary.get("warnings")))),
        }

    counts = {"pass": 0, "fail": 0, "warn": 0}
    layers = report.get("layers")
    if not isinstance(layers, list):
        return counts
    for layer in layers:
        if not isinstance(layer, Mapping):
            continue
        status = str(layer.get("status") or "").strip().lower()
        if status in {"pass", "passed", "complete", "completed"}:
            counts["pass"] += 1
        elif status in {"fail", "failed", "error"}:
            counts["fail"] += 1
        elif status in {"warn", "warning", "partial", "recorded"}:
            counts["warn"] += 1
    return counts
