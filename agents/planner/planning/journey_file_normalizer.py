"""Journey File Normalizer.

One planning responsibility lives in this file so the flow is easy to follow.
"""
from __future__ import annotations

# Source: image_plan.py — imported helper(s) come from this file.
from agents.planner.planning.image_plan import _plan_images

# Source: planning_helpers.py — shared planning constants and small helper functions.
from agents.planner.planning.planning_helpers import (
    Any,
    _canonical_actor,
    _dict,
    _list,
    _records,
    _strings,
    _text,
)

class JourneyFileNormalizerMixin:
    """Keep journey file normalizer behavior together."""

    # Converts end-to-end in the format expected by the next pipeline steps.
    def _normalize_e2e(self, value: Any) -> dict:
        """Convert end-to-end in the standard shape used by the rest of the pipeline."""
        # From: agents/planner/planning/planning_helpers.py
        e2e = _dict(value)
        journeys = []
        # From: agents/planner/planning/planning_helpers.py
        for index, item in enumerate(_records(e2e.get("journeys")), 1):
            steps = []
            # From: agents/planner/planning/planning_helpers.py
            for step in _list(item.get("steps")):
                if isinstance(step, dict):
                    # From: agents/planner/planning/planning_helpers.py
                    steps.append({
                        "at": _text(step.get("at"), 180),
                        "action": _text(step.get("action"), 300),
                        "selector_hint": _text(step.get("selector_hint"), 240),
                        "input": _dict(step.get("input")),
                        "expect": _text(step.get("expect"), 400),
                    })
                # From: agents/planner/planning/planning_helpers.py
                elif _text(step):
                    # From: agents/planner/planning/planning_helpers.py
                    steps.append({"at": "", "action": _text(step), "selector_hint": "", "input": {}, "expect": ""})
            # From: agents/planner/planning/planning_helpers.py
            journeys.append({
                "id": _text(item.get("id") or f"E2E-{index:03d}").upper(),
                "name": _text(item.get("name") or f"Journey {index}", 120),
                "actor": _canonical_actor(item.get("actor") or item.get("who"), "visitor"),
                "start_path": _text(item.get("start_path") or "/", 180),
                "requirement_ids": _strings(item.get("requirement_ids"), 40),
                "capability_ids": _strings(item.get("capability_ids") or item.get("covers"), 40),
                "steps": steps,
                "database_assertions": _strings(item.get("database_assertions"), 400),
                "negative_cases": _strings(item.get("negative_cases"), 400),
                "final_assertion": _text(item.get("final_assertion"), 500),
            })
        # From: agents/planner/planning/planning_helpers.py
        return {
            "strategy": _text(e2e.get("strategy") or "Requirement-driven browser journeys", 500),
            "data_preconditions": _strings(e2e.get("data_preconditions"), 400),
            "journeys": journeys,
            "route_checks": _strings(e2e.get("route_checks"), 400),
            "responsive_checks": _strings(e2e.get("responsive_checks"), 400),
            "accessibility_checks": _strings(e2e.get("accessibility_checks"), 400),
            "failure_evidence": _strings(e2e.get("failure_evidence"), 400),
        }

    # Converts files in the format expected by the next pipeline steps.
    def _normalize_files(self, value: Any, routes: list[dict]) -> list[dict]:
        """Convert files in the standard shape used by the rest of the pipeline."""
        route_by_file = {item["file"]: item for item in routes}
        out, seen = [], set()
        # From: agents/planner/planning/planning_helpers.py
        source = _records(value)
        for item in source:
            # From: agents/planner/planning/planning_helpers.py
            path = _text(item.get("path")).replace("\\", "/").lstrip("./")
            if not path or path in seen:
                continue
            seen.add(path)
            route = route_by_file.get(path, {})
            # From: agents/planner/planning/planning_helpers.py
            kind = _text(item.get("kind") or route.get("kind") or "server").lower()
            if path.endswith("route.js"):
                kind = "route"
            # From: agents/planner/planning/planning_helpers.py
            out.append({
                "path": path, "kind": kind,
                "purpose": _text(item.get("purpose") or route.get("purpose"), 700),
                "requirements": _strings(item.get("requirements") or route.get("requirement_ids"), 40),
                "imports_from": _strings(item.get("imports_from"), 200),
                "exports": _strings(item.get("exports"), 160),
                "reads": _strings(item.get("reads") or route.get("reads"), 100),
                "writes": _strings(item.get("writes") or route.get("writes"), 100),
                "sections": _strings(item.get("sections") or route.get("sections"), 500),
                "actions": _strings(item.get("actions") or route.get("actions"), 500),
                "layout": _text(item.get("layout") or route.get("layout"), 700),
                "contracts": _strings(item.get("contracts"), 120),
                "done_when": _strings(item.get("done_when"), 500),
            })
        return out

    # Converts tasks in the format expected by the next pipeline steps.
    def _normalize_tasks(self, value: Any, files: list[dict]) -> list[dict]:
        """Convert tasks in the standard shape used by the rest of the pipeline."""
        files_by_path = {item["path"]: item for item in files}
        out, assigned = [], set()
        # From: agents/planner/planning/planning_helpers.py
        for index, item in enumerate(_records(value), 1):
            paths = []
            # From: agents/planner/planning/planning_helpers.py
            for file in _list(item.get("files")):
                path = file.get("path") if isinstance(file, dict) else file
                # From: agents/planner/planning/planning_helpers.py
                path = _text(path).replace("\\", "/").lstrip("./")
                if path and path not in paths:
                    paths.append(path)
                    assigned.add(path)
            if not paths:
                continue
            # From: agents/planner/planning/planning_helpers.py
            out.append({
                "id": item.get("id") or index, "actor": _canonical_actor(item.get("actor")),
                "title": _text(item.get("title") or f"Task {index}", 140),
                "goal": _text(item.get("goal"), 600),
                "requirement_ids": _strings(item.get("requirement_ids") or item.get("covers"), 40),
                "files": [files_by_path.get(path, {"path": path, "kind": "server", "purpose": ""}) for path in paths],
                "depends_on": _list(item.get("depends_on")),
                "done_when": _strings(item.get("done_when"), 500)
                             if isinstance(item.get("done_when"), list)
                             else [_text(item.get("done_when"), 500)] if item.get("done_when") else [],
            })
        return out

    # Converts dependencies in the format expected by the next pipeline steps.
    def _normalize_dependencies(self, value: Any) -> list[dict]:
        """Convert dependencies in the standard shape used by the rest of the pipeline."""
        out = []
        # From: agents/planner/planning/planning_helpers.py
        for item in _list(value):
            if isinstance(item, dict):
                # From: agents/planner/planning/planning_helpers.py
                name, reason = _text(item.get("name")), _text(item.get("reason"), 300)
            else:
                # From: agents/planner/planning/planning_helpers.py
                name, reason = _text(item), "Required by the approved plan"
            if name and name not in {entry["name"] for entry in out}:
                out.append({"name": name, "reason": reason})
        return out

    # Builds small backward-compatible plan views used by existing pipeline consumers.
    def _compatibility_views(self, plan: dict, source_input: str = "") -> None:
        """Build small backward-compatible plan views used by existing pipeline consumers."""
        access = plan["roles_and_access"]
        plan["signup_role"] = access.get("signup_role") or ""
        plan["demo_accounts"] = access.get("demo_accounts") or []
        plan["role_homes"] = {role["name"]: role["home"]
                              for role in access.get("roles") or []
                              if role.get("name") and role.get("home")}
        design = plan.get("design") or {}
        # From: agents/planner/planning/image_plan.py
        plan["images"] = _plan_images(plan, design, source_input)
        # From: agents/planner/planning/planning_helpers.py
        plan["look_and_feel"] = _text(design.get("direction") or design.get("mood"))
        plan["phases"] = []
        for task in plan.get("tasks") or []:
            plan["phases"].append({
                "id": task["id"], "title": task["title"], "goal": task["goal"],
                "done_when": "; ".join(task.get("done_when") or []),
                "covers": task.get("requirement_ids") or [],
                "files": task.get("files") or [],
            })
        plan["workflows"] = []
        for journey in plan["e2e_plan"].get("journeys") or []:
            steps = []
            for step in journey.get("steps") or []:
                text = " — ".join(x for x in [step.get("at"), step.get("action"), step.get("expect")] if x)
                if text:
                    steps.append(text)
            plan["workflows"].append({
                "name": journey["name"], "who": journey["actor"],
                "covers": journey.get("capability_ids") or [], "steps": steps,
            })
        plan["contracts"] = []
        for api in plan.get("api_contracts") or []:
            request = [str(row.get("field")) for row in api["request"] if row.get("field")]
            response = [str(row.get("field")) for row in api["response"] if row.get("field")]
            callers = api.get("called_from") or [""]
            for caller in callers:
                plan["contracts"].append({
                    "name": api["name"], "kind": "api", "from": caller,
                    "target": api["path"], "method": api["method"],
                    "request": request, "response": response,
                    "trigger": api["name"], "effect": api["success_effect"],
                })

        route_files = {route["path"]: route["file"] for route in plan.get("routes") or []
                       if route.get("path") and route.get("file")}
        for page in plan.get("site_map") or []:
            target = page.get("path") or ""
            parent = page.get("parent") or ""
            if not target or not parent or target == parent:
                continue
            trigger = "; ".join(page.get("reached_from") or []) or page.get("label") or "navigate"
            plan["contracts"].append({
                "name": f"Navigate to {page.get('label') or target}",
                "kind": "navigation", "from": route_files.get(parent, parent),
                "target": target, "method": "", "request": [], "response": [],
                "trigger": trigger, "effect": page.get("purpose") or f"Show {target}",
            })
