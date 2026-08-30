"""Route Normalizer.

One planning responsibility lives in this file so the flow is easy to follow.
"""
from __future__ import annotations

# Source: image_plan.py — imported helper(s) come from this file.
from agents.planner.planning.image_plan import _runtime_path

# Source: planning_helpers.py — shared planning constants and small helper functions.
from agents.planner.planning.planning_helpers import (
    Any,
    _records,
    _strings,
    _text,
)

class RouteNormalizerMixin:
    """Keep route normalizer behavior together."""

    # Converts site map in the format expected by the next pipeline steps.
    def _normalize_site_map(self, value: Any) -> list[dict]:
        """Convert site map in the standard shape used by the rest of the pipeline."""
        out = []
        # From: agents/planner/planning/planning_helpers.py
        source = _records(value)
        for item in source:
            # From: agents/planner/planning/planning_helpers.py
            path = _text(item.get("path"))
            if not path:
                continue
            # From: agents/planner/planning/planning_helpers.py
            out.append({
                "path": path, "parent": _text(item.get("parent")),
                "label": _text(item.get("label") or item.get("purpose"), 120),
                "type": _text(item.get("type") or "page", 20),
                "audience": _text(item.get("audience") or "PUBLIC", 100),
                "purpose": _text(item.get("purpose"), 500),
                "reached_from": _strings(item.get("reached_from"), 300),
                "children": _strings(item.get("children"), 180),
            })
        return out

    # Converts routes in the format expected by the next pipeline steps.
    def _normalize_routes(self, value: Any) -> list[dict]:
        """Convert routes in the standard shape used by the rest of the pipeline."""
        out = []
        # From: agents/planner/planning/planning_helpers.py
        source = _records(value)
        for item in source:
            # From: agents/planner/planning/planning_helpers.py
            path = _text(item.get("path"))
            # From: agents/planner/planning/planning_helpers.py
            file = _text(item.get("file")).replace("\\", "/").lstrip("./")
            if not path and file:
                # From: agents/planner/planning/image_plan.py
                path = _runtime_path(file)
            if not path or not file:
                continue
            # From: agents/planner/planning/planning_helpers.py
            kind = _text(item.get("kind") or "server").lower()
            if file.endswith("route.js"):
                kind = "route"
            # From: agents/planner/planning/planning_helpers.py
            out.append({
                "path": path, "file": file,
                "kind": kind if kind in {"server", "client", "route"} else "server",
                "audience": _text(item.get("audience") or "PUBLIC", 100),
                "purpose": _text(item.get("purpose"), 600),
                "reads": _strings(item.get("reads"), 100),
                "writes": _strings(item.get("writes"), 100),
                "sections": _strings(item.get("sections"), 500),
                "actions": _strings(item.get("actions"), 500),
                "states": _strings(item.get("states"), 100),
                "layout": _text(item.get("layout"), 700),
                "requirement_ids": _strings(item.get("requirement_ids"), 40),
            })
        return out
