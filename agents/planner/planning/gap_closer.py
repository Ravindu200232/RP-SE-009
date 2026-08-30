"""Gap Closer.

One planning responsibility lives in this file so the flow is easy to follow.
"""
from __future__ import annotations

# Source: image_plan.py — imported helper(s) come from this file.
from agents.planner.planning.image_plan import SHELL_FILES, _seed_count

# Source: planning_helpers.py — shared planning constants and small helper functions.
from agents.planner.planning.planning_helpers import (
    AUTH_OWNED_COLLECTIONS,
    GAP_ROUNDS,
    SIGN_IN_PATHS,
    SIGN_UP_PATHS,
    _dict,
    _json_object,
    _plan_is_poorer,
    _promised_routes,
    _records,
    _slug,
    _strings,
    _text,
    _unplanned_routes,
    _url_shape,
    re,
)

class GapCloserMixin:
    """Keep gap closer behavior together."""

    # make tha plan standerd shema
    def normalize(self, raw: dict, source_input: str = "") -> dict:
        """Make plan names consistent without changing its decisions."""
        plan = dict(raw)
        # From: agents/planner/planning/planning_helpers.py
        project = _dict(plan.get("project"))
        if not project:
            project = {
                "name": plan.get("project_name"),
                "title": plan.get("title"),
                "summary": plan.get("description"),
            }
        # From: agents/planner/planning/planning_helpers.py
        project["name"] = _slug(project.get("name") or project.get("title"))
        # From: agents/planner/planning/planning_helpers.py
        project["title"] = _text(project.get("title") or project["name"].replace("-", " ").title())
        # From: agents/planner/planning/planning_helpers.py
        project["summary"] = _text(project.get("summary") or plan.get("source_input_summary") or source_input, 600)
        # From: agents/planner/planning/planning_helpers.py
        project["product_type"] = _text(project.get("product_type") or "web application")
        # From: agents/planner/planning/planning_helpers.py
        project["primary_goal"] = _text(project.get("primary_goal") or project["summary"], 500)
        # From: agents/planner/planning/planning_helpers.py
        project["target_audiences"] = _strings(project.get("target_audiences"), 120)
        # From: agents/planner/planning/planning_helpers.py
        project["success_metrics"] = _strings(project.get("success_metrics"), 300)
        plan["project"] = project
        plan["project_name"] = project["name"]
        plan["title"] = project["title"]
        plan["description"] = project["summary"]
        # From: agents/planner/planning/planning_helpers.py
        plan["source_input_summary"] = _text(plan.get("source_input_summary") or source_input, 2000)

        requirements = []
        # From: agents/planner/planning/planning_helpers.py
        for index, item in enumerate(_records(plan.get("requirements")), 1):
            # From: agents/planner/planning/planning_helpers.py
            rid = _text(item.get("id") or f"REQ-{index:03d}").upper()
            # From: agents/planner/planning/planning_helpers.py
            requirements.append({
                "id": rid, "actor": _text(item.get("actor") or "user", 80),
                "source_text": _text(item.get("source_text") or item.get("behavior"), 700),
                "behavior": _text(item.get("behavior") or item.get("source_text"), 700),
                "business_rule": _text(item.get("business_rule"), 800),
                "acceptance": _strings(item.get("acceptance"), 500),
                "priority": _text(item.get("priority") or "must", 30),
            })
        plan["requirements"] = requirements
        plan["source_requirements"] = [r["source_text"] for r in requirements]
        # From: agents/planner/planning/planning_helpers.py
        plan["assumptions"] = _records(plan.get("assumptions"))
        # From: agents/planner/planning/planning_helpers.py
        plan["design"] = _dict(plan.get("design"))
        # From: agents/planner/planning/planning_helpers.py
        plan["information_architecture"] = _dict(plan.get("information_architecture"))
        # From: agents/planner/planning/data_access_normalizer.py
        plan["roles_and_access"] = self._normalize_access(plan.get("roles_and_access"))
        # From: agents/planner/planning/route_normalizer.py
        plan["site_map"] = self._normalize_site_map(plan.get("site_map"))
        # From: agents/planner/planning/data_access_normalizer.py
        plan["api_contracts"] = self._normalize_apis(plan.get("api_contracts"))
        # From: agents/planner/planning/route_normalizer.py
        plan["routes"] = self._normalize_routes(plan.get("routes"))
        # From: agents/planner/planning/data_access_normalizer.py
        plan["data_model"] = self._normalize_data(plan.get("data_model"))
        # From: agents/planner/planning/data_access_normalizer.py
        plan["capabilities"] = self._normalize_capabilities(plan.get("capabilities"))
        # From: agents/planner/planning/planning_helpers.py
        plan["architecture"] = _dict(plan.get("architecture"))
        # From: agents/planner/planning/journey_file_normalizer.py
        plan["e2e_plan"] = self._normalize_e2e(plan.get("e2e_plan"))
        # From: agents/planner/planning/journey_file_normalizer.py
        plan["file_plan"] = self._normalize_files(
            plan.get("file_plan"), plan["routes"])
        # From: agents/planner/planning/journey_file_normalizer.py
        plan["tasks"] = self._normalize_tasks(plan.get("tasks"), plan["file_plan"])
        # From: agents/planner/planning/journey_file_normalizer.py
        plan["dependencies"] = self._normalize_dependencies(plan.get("dependencies"))
        # From: agents/planner/planning/planning_helpers.py
        plan["definition_of_done"] = _strings(plan.get("definition_of_done"), 500)
        if plan["roles_and_access"]["authentication_required"]:
            aliases = {"users": "user", "accounts": "account", "sessions": "session", "verifications": "verification"}
            for model in plan["data_model"]:
                model["collection"] = aliases.get(model["collection"].lower(), model["collection"])
                # From: agents/planner/planning/planning_helpers.py
                model["relationships"] = [re.sub(r"\b(users|accounts|sessions|verifications)\b", lambda m: aliases[m.group(1).lower()], rel, flags=re.I) for rel in model["relationships"]]
            for route in plan["routes"]:
                route["reads"] = [aliases.get(x.lower(), x) for x in route["reads"]]
                route["writes"] = [aliases.get(x.lower(), x) for x in route["writes"]]
        # From: agents/planner/planning/journey_file_normalizer.py
        self._compatibility_views(plan, source_input)
        return plan

    # Sends the planner its own holes until it reports a complete plan. Only the planner writes plan content, so an
    # incomplete first answer is answered by asking again rather than by filling the hole in Python.
    def _close_gaps(self, messages: list[dict], plan: dict, raw: str,
                    requirements: str) -> tuple[dict, str]:
        """Send the planner its own holes until it reports a complete plan.

        Only the planner writes plan content, so an incomplete first answer is
        answered by asking again rather than by filling the hole in Python.
        """
        # From: agents/planner/planning/planning_helpers.py
        promised = _promised_routes(requirements)
        for attempt in range(1, GAP_ROUNDS + 1):
            # From: agents/planner/planning/planning_helpers.py
            gaps = self.plan_gaps(plan) + _unplanned_routes(plan, promised)
            if not gaps:
                if attempt > 1:
                    self._log("INFO", "   ✅ Planner closed every gap")
                return plan, raw
            self._log("WARN", f"   🧩 {len(gaps)} gap(s) in the plan — asking "
                              f"the planner to complete it "
                              f"({attempt}/{GAP_ROUNDS})")
            for gap in gaps[:8]:
                self._log("WARN", f"      • {gap}")

            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content":
                    "That plan is incomplete. Every item below is a hole in "
                    "your own plan, not a new requirement:\n\n"
                    + "\n".join(f"- {gap}" for gap in gaps)
                    + "\n\nKeep every decision you already made. Add exactly "
                      "what is missing, with the same quality as the rest: real "
                      "purpose, sections, actions, states, requirement links and "
                      "journey coverage — never a placeholder. Return the "
                      "COMPLETE JSON plan again as one raw JSON object."},
            ]
            chunks = []
            try:
                # From: agents/planner/planning/request_planner.py
                self._call(messages, chunks.append)
            except Exception as exc:
                self._log("WARN", f"   ⚠ Gap round failed: {exc}")
                return plan, raw
            reply = "".join(chunks)
            # From: agents/planner/planning/planning_helpers.py
            parsed = _json_object(reply)
            if not parsed:
                self._log("WARN", "   ⚠ Gap round returned no JSON object")
                return plan, raw

            # A retry answers with the WHOLE plan, so a truncated or partial
            # reply parses into a smaller plan than the one already in hand.
            # Accepting it silently trades a real plan for an empty one and
            # every later stage then builds nothing, so only an answer that is
            # genuinely more complete replaces what we have.
            candidate = self.normalize(parsed, requirements)
            # From: agents/planner/planning/planning_helpers.py
            if _plan_is_poorer(candidate, plan):
                self._log("WARN", "   ⚠ the gap round came back smaller than "
                                  "the plan it was fixing — keeping the fuller "
                                  "plan and stopping here")
                return plan, raw
            plan, raw = candidate, reply

        left = self.plan_gaps(plan)
        if left:
            self._log("WARN", f"   ⚠ {len(left)} gap(s) survived "
                              f"{GAP_ROUNDS} planning rounds")
        return plan, raw

    # Every hole the planner left, phrased so the planner can close it. This only reads the plan against itself.
    # Nothing here writes a page, route, file or task: a gap goes back to the planner, because a page invented in
    # Python arrives with no purpose, sections, requirements or E2E coverage and quietly competes with the one the
    # planner meant.
    def plan_gaps(self, plan: dict) -> list[str]:
        """Every hole the planner left, phrased so the planner can close it.

        This only reads the plan against itself. Nothing here writes a page,
        route, file or task: a gap goes back to the planner, because a page
        invented in Python arrives with no purpose, sections, requirements or
        E2E coverage and quietly competes with the one the planner meant.
        """
        gaps = []
        # From: agents/planner/planning/planning_helpers.py
        access = _dict(plan.get("roles_and_access"))
        # From: agents/planner/planning/planning_helpers.py
        pages = [item for item in plan.get("site_map") or []
                 if _text(item.get("type") or "page").lower() == "page"]
        # From: agents/planner/planning/planning_helpers.py
        page_paths = {_url_shape(item.get("path")) for item in pages}
        # From: agents/planner/planning/planning_helpers.py
        route_paths = {_url_shape(item.get("path")) for item in plan.get("routes") or []}
        # From: agents/planner/planning/planning_helpers.py
        route_files = {_text(item.get("file")) for item in plan.get("routes") or []}
        # From: agents/planner/planning/planning_helpers.py
        planned_files = {_text(item.get("path")) for item in plan.get("file_plan") or []}
        # From: agents/planner/planning/planning_helpers.py
        assigned = {_text(file.get("path"))
                    for task in plan.get("tasks") or []
                    for file in task.get("files") or []}

        # From: agents/planner/planning/planning_helpers.py
        for label, aliases, required in (
            ("sign-in", SIGN_IN_PATHS, bool(access.get("authentication_required"))),
            ("sign-up", SIGN_UP_PATHS,
             _text(access.get("signup")).lower() == "open"),
        ):
            # From: agents/planner/planning/planning_helpers.py
            if required and not (page_paths & {_url_shape(a) for a in aliases}):
                gaps.append(
                    f"roles_and_access needs a {label} flow, but no site_map "
                    f"page serves one. Add the page you intend (for example "
                    f"/{label}) with its route, file and journey.")

        # From: agents/planner/planning/planning_helpers.py
        for nav in _records(_dict(plan.get("information_architecture"))
                            .get("global_navigation")):
            # From: agents/planner/planning/planning_helpers.py
            path = _text(nav.get("path"))
            # From: agents/planner/planning/planning_helpers.py
            if (path.startswith("/") and not path.startswith("/api/")
                    and _url_shape(path) not in page_paths):
                gaps.append(
                    f"global_navigation links to {path}, but no site_map page "
                    f"serves it. Add that page or drop the link.")

        for item in pages:
            # From: agents/planner/planning/planning_helpers.py
            path = _text(item.get("path"))
            # From: agents/planner/planning/planning_helpers.py
            if path and _url_shape(path) not in route_paths:
                gaps.append(f"site_map page {path} has no routes entry naming "
                            f"its file.")

        for api in plan.get("api_contracts") or []:
            # From: agents/planner/planning/planning_helpers.py
            handler = _text(api.get("handler_file"))
            if handler and handler not in route_files:
                # From: agents/planner/planning/planning_helpers.py
                gaps.append(
                    f"api_contracts {_text(api.get('method'))} "
                    f"{_text(api.get('path'))} has no routes entry for "
                    f"{handler}.")

        for item in plan.get("routes") or []:
            # From: agents/planner/planning/planning_helpers.py
            file = _text(item.get("file"))
            if file and file not in planned_files:
                # From: agents/planner/planning/planning_helpers.py
                gaps.append(f"routes entry {_text(item.get('path'))} owns "
                            f"{file}, but file_plan does not plan it.")

        for capability in plan.get("capabilities") or []:
            for file in capability.get("files") or []:
                # From: agents/planner/planning/planning_helpers.py
                if _text(file) and _text(file) not in planned_files:
                    # From: agents/planner/planning/planning_helpers.py
                    gaps.append(
                        f"capability {_text(capability.get('id'))} names "
                        f"{_text(file)}, but file_plan does not plan it.")

        for path, _kind, purpose in SHELL_FILES:
            if path not in planned_files:
                gaps.append(f"file_plan has no {path}. {purpose}.")

        models = {str(m.get("collection") or ""): {str(f.get("name") or "") for f in m.get("fields") or []}
                  for m in plan.get("data_model") or [] if m.get("collection")}
        used_models = set()
        for route in plan.get("routes") or []:
            for name in list(route.get("reads") or []) + list(route.get("writes") or []):
                name = str(name or "").strip()
                if name:
                    used_models.add(name)
                    if name not in models:
                        # From: agents/planner/planning/planning_helpers.py
                        gaps.append(f"route {_text(route.get('path'))} names collection {name}, but data_model does not define it.")
        for model in plan.get("data_model") or []:
            collection = str(model.get("collection") or "")
            for rel in model.get("relationships") or []:
                # From: agents/planner/planning/planning_helpers.py
                m = re.match(r"\s*([A-Za-z_]\w*)\s*->\s*([A-Za-z_]\w*)\._id\s*$", str(rel))
                if m and m.group(1) not in models.get(collection, set()):
                    gaps.append(f"relationship {collection}.{m.group(1)} is missing that source field from data_model.")
                if m and m.group(2) not in models:
                    gaps.append(f"relationship {rel} targets collection {m.group(2)}, but data_model does not define it.")
            if (collection and collection not in used_models
                    and collection not in AUTH_OWNED_COLLECTIONS):
                gaps.append(f"data_model collection {collection} is never read or written by a planned route; connect it to the user flow or remove it.")

        # From: agents/planner/planning/image_plan.py
        seeds = bool(access.get("demo_accounts")) or any(
            _seed_count(model) for model in plan.get("data_model") or [])
        if seeds:
            # From: agents/planner/planning/planning_helpers.py
            seed = next((item for item in plan.get("file_plan") or []
                         if _text(item.get("path")) == "lib/seed.js"), None)
            if seed is None:
                gaps.append(
                    "the plan seeds demo accounts or rows, but file_plan has "
                    "no lib/seed.js. AgentForge calls its ensureSeeded export, "
                    "so plan that file exporting ensureSeeded.")
            elif "ensureSeeded" not in (seed.get("exports") or []):
                gaps.append(
                    'the file_plan entry whose path is "lib/seed.js" needs '
                    '"exports": ["ensureSeeded"] — a JSON array on that entry, '
                    "not prose in its purpose or contracts. AgentForge calls "
                    "that exact name through /api/seed.")

        for path in sorted(planned_files - assigned):
            if path:
                gaps.append(f"file_plan plans {path}, but no task builds it.")

        return gaps
