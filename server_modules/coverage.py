"""The interview's requirement-coverage taxonomy."""
from __future__ import annotations

from typing import Any

from . import prompts

STATUSES = ("KNOWN", "PARTIAL", "UNKNOWN", "NOT_APPLICABLE")


def categories() -> dict[str, dict[str, Any]]:
    try:
        return prompts.data("interview/categories").get("categories") or {}
    except prompts.MissingPrompt:
        return {}


def blank_coverage() -> dict[str, dict[str, Any]]:
    """One entry per category, seeded UNKNOWN — except a category marked."""
    out: dict[str, dict[str, Any]] = {}
    for key, entry in categories().items():
        status = "NOT_APPLICABLE" if entry.get("auto") == "not_applicable" else "UNKNOWN"
        out[key] = {"status": status, "confidence": "low", "facts": [],
                    "source": "", "updated_at": 0.0}
    return out
