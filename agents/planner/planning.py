"""LLM-first product planning for AgentForge.

The user's text enters once and leaves as one normalized plan that owns the
design, site map, routes, data, architecture, file graph, and E2E journeys.
There are no heuristic replanning loops: the planning prompt asks the model to
perform its completeness pass before returning the first answer.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agents.core.ollama_client import OllamaClient, max_context


log = logging.getLogger("planner")
PROMPT_PATH = Path(__file__).with_name("planning_prompt.md")

NEXT_STACK = """\
FIXED IMPLEMENTATION STACK
- Next.js 16 App Router, React 19, JavaScript only; no TypeScript.
- Tailwind utilities for styling; lucide-react icons; framer-motion only when motion helps.
- MongoDB official driver through the generated @/lib/mongodb module.
- Files live under app/, components/, and lib/. Pages use .jsx, route/lib modules use .js.
- Filesystem routing; no react-router-dom, Pages Router, Mongoose, Prisma, or external APIs.
- Better Auth is generated only when the product genuinely needs authentication.
- AgentForge already owns package/config/Mongo/auth defaults. Never put those in file_plan/tasks.
- Every product page, component, seed module, API route, loading/error/empty behavior, and E2E journey must be planned.
"""

VITE_STACK = """\
FIXED IMPLEMENTATION STACK
- React 18 + Vite, JavaScript .jsx only; no TypeScript.
- Tailwind utilities, react-router-dom v6, lucide-react, framer-motion.
- Browser state plus localStorage only. No server, database, private API, or server authentication.
- Files live under src/. AgentForge owns package/config/index/main/style defaults.
- Every product screen, component, state transition, persistence behavior, and E2E journey must be planned.
"""


@dataclass
class PlanBundle:
    data: dict
    markdown: str
    architecture_markdown: str
    design_markdown: str
    raw: str


def _text(value: Any, limit: int = 0) -> str:
    result = " ".join(str(value or "").split())
    return result[:limit] if limit else result


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _strings(value: Any, limit: int = 0) -> list[str]:
    out = []
    for item in _list(value):
        text = _text(item, limit)
        if text and text not in out:
            out.append(text)
    return out


def _records(value: Any) -> list[dict]:
    return [dict(item) for item in _list(value) if isinstance(item, dict)]


def _slug(value: str, fallback: str = "agentforge-app") -> str:
    result = re.sub(r"[^a-z0-9]+", "-", _text(value).lower()).strip("-")
    return result[:48].strip("-") or fallback


def _runtime_path(file_path: str) -> str:
    rel = _text(file_path).replace("\\", "/")
    if not rel.startswith("app/"):
        return ""
    parts = rel.split("/")
    if not parts[-1].startswith(("page.", "route.")):
        return ""
    segments = [part for part in parts[1:-1]
                if not (part.startswith("(") and part.endswith(")"))]
    return "/" + "/".join(segments) if segments else "/"


def _app_file(route_path: str, leaf: str = "page.jsx") -> str:
    route = _text(route_path).split("?", 1)[0].split("#", 1)[0].strip()
    if not route.startswith("/"):
        return ""
    segments = [part for part in route.strip("/").split("/") if part]
    if any(part in {".", ".."} for part in segments):
        return ""
    return "app/" + ("/".join(segments) + "/" if segments else "") + leaf


def _canonical_actor(value: Any, fallback: str = "") -> str:
    """Turn access prose such as ``ROLE admin`` into an exact role value."""
    actor = _text(value, 80)
    actor = re.sub(r"^(?:as\s+)?role\s*[:=-]?\s+", "", actor,
                   flags=re.I).strip()
    return actor or fallback


def _json_object(raw: str) -> dict:
    """Read the first complete JSON object from a model response."""
    source = str(raw or "").strip()
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", source,
                        flags=re.I | re.S)
    candidates = list(reversed(fenced))
    candidates.append(source)
    decoder = json.JSONDecoder()
    for candidate in candidates:
        for match in re.finditer(r"\{", candidate):
            try:
                value, _ = decoder.raw_decode(candidate[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
    return {}


def _md_cell(value: Any) -> str:
    if isinstance(value, list):
        value = ", ".join(_text(item) for item in value)
    return _text(value).replace("|", "\\|").replace("\n", " ") or "—"


def _bullets(items: Any, empty: str = "None") -> list[str]:
    values = _list(items)
    if not values:
        return [f"- {empty}"]
    lines = []
    for item in values:
        if isinstance(item, dict):
            label = item.get("text") or item.get("name") or item.get("decision")
            tail = item.get("reason") or item.get("purpose") or item.get("tradeoff")
            line = _text(label)
            if tail:
                line += " — " + _text(tail)
        else:
            line = _text(item)
        if line:
            lines.append("- " + line)
    return lines or [f"- {empty}"]


class PlannerAgent:
    """Produce and normalize the one plan used by every downstream stage."""

    def __init__(self, client: OllamaClient, model: str, *, stack: str = "next",
                 callbacks: dict | None = None, think: bool | None = None,
                 stream: Callable | None = None):
        self.client = client
        self.model = model
        self.stack = "vite" if stack == "vite" else "next"
        self.cb = callbacks or {}
        self.think = think
        self.stream = stream
        self.tokens_in = 0
        self.tokens_out = 0

    def _fire(self, name: str, *args) -> None:
        callback = self.cb.get(name)
        if callable(callback):
            try:
                callback(*args)
            except Exception as exc:  # callbacks must not stop planning
                log.warning("planner callback %s failed: %s", name, exc)

    def _log(self, level: str, message: str) -> None:
        callback = self.cb.get("on_log")
        if callable(callback):
            self._fire("on_log", level, message)
        else:
            log.info(message)

    def _system_prompt(self) -> str:
        body = PROMPT_PATH.read_text(encoding="utf-8")
        stack = VITE_STACK if self.stack == "vite" else NEXT_STACK
        return body + "\n\n" + stack

    def _call(self, messages: list[dict], on_delta: Callable[[str], None]) -> None:
        if self.stream:
            self.stream(messages, on_delta, temperature=0.25, timeout=900)
            return
        options = {"temperature": 0.25, "top_p": 0.9,
                   "num_ctx": max_context(self.model)}
        for chunk in self.client.chat_stream(
                self.model, messages, options=options, keep_alive="10m",
                think=self.think, timeout=900):
            message = chunk.get("message") or {}
            delta = message.get("content") or ""
            if delta:
                on_delta(delta)
            if chunk.get("done"):
                self.tokens_in += chunk.get("prompt_eval_count", 0) or 0
                self.tokens_out += chunk.get("eval_count", 0) or 0

    def create(self, user_input: str, requirement_source: str = "") -> PlanBundle | None:
        requirements = str(requirement_source or user_input or "").strip()
        context = str(user_input or "").strip()
        if not requirements:
            self._log("ERROR", "   ❌ Planning needs non-empty user input")
            return None
        user = (
            "AUTHORITATIVE USER INPUT\n\n" + requirements +
            ("\n\nBUILD CONTEXT (implementation resources/constraints, not extra product requirements)\n\n"
             + context if context and context != requirements else "") +
            "\n\nCreate the complete JSON plan now. Preserve every stated detail."
        )
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": user},
        ]
        chunks = []
        self._fire("on_file_start", "plan.md")

        def receive(delta: str) -> None:
            chunks.append(delta)
            self._fire("on_file_token", "plan.md", delta)

        try:
            self._call(messages, receive)
        except Exception as exc:
            self._log("ERROR", f"   ❌ Planner failed: {exc}")
            return None
        raw = "".join(chunks)
        parsed = _json_object(raw)
        if not parsed:
            self._log("ERROR", "   ❌ Planner returned no JSON object")
            return None
        plan = self.normalize(parsed, requirements)
        markdown = self.render_markdown(plan)
        architecture = "# Architecture\n\n" + self.render_architecture(plan)
        design = "# Product Design\n\n" + self.render_design(plan)
        self._fire("on_file_end", "plan.md", markdown)
        return PlanBundle(plan, markdown, architecture, design, raw)

    def normalize(self, raw: dict, source_input: str = "") -> dict:
        """Canonicalize names without changing or rejecting model decisions."""
        plan = dict(raw)
        project = _dict(plan.get("project"))
        if not project:
            project = {
                "name": plan.get("project_name"),
                "title": plan.get("title"),
                "summary": plan.get("description"),
            }
        project["name"] = _slug(project.get("name") or project.get("title"))
        project["title"] = _text(project.get("title") or project["name"].replace("-", " ").title())
        project["summary"] = _text(project.get("summary") or plan.get("source_input_summary") or source_input, 600)
        project["product_type"] = _text(project.get("product_type") or "web application")
        project["primary_goal"] = _text(project.get("primary_goal") or project["summary"], 500)
        project["target_audiences"] = _strings(project.get("target_audiences"), 120)
        project["success_metrics"] = _strings(project.get("success_metrics"), 300)
        plan["project"] = project
        plan["project_name"] = project["name"]
        plan["title"] = project["title"]
        plan["description"] = project["summary"]
        plan["source_input_summary"] = _text(plan.get("source_input_summary") or source_input, 2000)

        requirements = []
        for index, item in enumerate(_records(plan.get("requirements")), 1):
            rid = _text(item.get("id") or f"REQ-{index:03d}").upper()
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
        plan["assumptions"] = _records(plan.get("assumptions"))
        plan["design"] = _dict(plan.get("design"))
        plan["information_architecture"] = _dict(plan.get("information_architecture"))
        plan["roles_and_access"] = self._normalize_access(plan.get("roles_and_access"))
        plan["site_map"] = self._normalize_site_map(
            plan.get("site_map"), plan["information_architecture"],
            plan["roles_and_access"])
        plan["api_contracts"] = self._normalize_apis(plan.get("api_contracts"))
        plan["routes"] = self._normalize_routes(
            plan.get("routes"), plan["site_map"], plan["api_contracts"])
        plan["data_model"] = self._normalize_data(plan.get("data_model"))
        plan["capabilities"] = self._normalize_capabilities(plan.get("capabilities"))
        plan["architecture"] = _dict(plan.get("architecture"))
        plan["e2e_plan"] = self._normalize_e2e(plan.get("e2e_plan"))
        plan["file_plan"] = self._normalize_files(
            plan.get("file_plan"), plan["routes"], plan["api_contracts"],
            plan["capabilities"], plan["roles_and_access"])
        plan["tasks"] = self._normalize_tasks(plan.get("tasks"), plan["file_plan"])
        plan["dependencies"] = self._normalize_dependencies(plan.get("dependencies"))
        plan["definition_of_done"] = _strings(plan.get("definition_of_done"), 500)
        self._compatibility_views(plan)
        return plan

    def _normalize_site_map(self, value: Any,
                            information_architecture: dict | None = None,
                            access: dict | None = None) -> list[dict]:
        out = []
        source = _records(value)
        known = {_text(item.get("path")) for item in source}
        for path, required in (
            ("/sign-in", bool((access or {}).get("authentication_required"))),
            ("/sign-up", _text((access or {}).get("signup")).lower() == "open"),
        ):
            if required and path not in known:
                label = path[1:].replace("-", " ").title()
                source.append({"path": path, "parent": "/", "label": label,
                               "type": "page", "audience": "PUBLIC",
                               "purpose": f"Serve the {label} account flow"})
                known.add(path)
        for nav in _records((information_architecture or {}).get("global_navigation")):
            path = _text(nav.get("path"))
            if path.startswith("/") and not path.startswith("/api/") and path not in known:
                source.append({
                    "path": path, "parent": "/" if path != "/" else "",
                    "label": nav.get("label"), "type": "page",
                    "audience": nav.get("audience"),
                    "purpose": f"Serve the {nav.get('label') or path} navigation destination",
                    "reached_from": [f"global navigation {nav.get('label') or path}"],
                })
                known.add(path)
        for item in source:
            path = _text(item.get("path"))
            if not path:
                continue
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

    def _normalize_routes(self, value: Any,
                          site_map: list[dict] | None = None,
                          apis: list[dict] | None = None) -> list[dict]:
        out = []
        source = _records(value)
        known_files = {_text(item.get("file")).replace("\\", "/")
                       for item in source}
        for api in apis or []:
            file = api.get("handler_file") or ""
            if file and file not in known_files:
                source.append({
                    **api, "file": file, "kind": "route", "purpose": api["name"],
                })
                known_files.add(file)
        for item in source:
            path = _text(item.get("path"))
            file = _text(item.get("file")).replace("\\", "/").lstrip("./")
            if not path and file:
                path = _runtime_path(file)
            if not path or not file:
                continue
            kind = _text(item.get("kind") or "server").lower()
            if file.endswith("route.js"):
                kind = "route"
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
                "requirement_ids": _strings(item.get("requirement_ids"), 40),
            })

        known_paths = {item["path"] for item in out}
        for page in site_map or []:
            path = _text(page.get("path"))
            kind = _text(page.get("type") or "page").lower()
            file = _app_file(path)
            if kind != "page" or not file or path in known_paths:
                continue
            out.append({
                "path": path, "file": file, "kind": "server",
                "audience": _text(page.get("audience") or "PUBLIC", 100),
                "purpose": _text(page.get("purpose") or page.get("label"), 600),
                "reads": [], "writes": [],
                "sections": [page.get("label")] if page.get("label") else [],
                "actions": [], "states": [], "requirement_ids": [],
            })
            known_paths.add(path)
        return out

    def _normalize_data(self, value: Any) -> list[dict]:
        out = []
        for item in _records(value):
            collection = _text(item.get("collection"), 100)
            if not collection:
                continue
            fields = []
            for field in _records(item.get("fields")):
                if field.get("name"):
                    fields.append({
                        "name": _text(field.get("name"), 100),
                        "type": _text(field.get("type") or "string", 50),
                        "required": bool(field.get("required")),
                        "rules": _text(field.get("rules"), 400),
                    })
            out.append({
                "collection": collection, "purpose": _text(item.get("purpose"), 500),
                "fields": fields, "indexes": _strings(item.get("indexes"), 200),
                "seed": _dict(item.get("seed")),
                "relationships": _strings(item.get("relationships"), 240),
            })
        return out

    def _normalize_access(self, value: Any) -> dict:
        access = _dict(value)
        roles = []
        for role in _records(access.get("roles")):
            name = _text(role.get("name"), 80)
            if name:
                roles.append({
                    "name": _canonical_actor(name, name), "home": _text(role.get("home"), 180),
                    "permissions": _strings(role.get("permissions"), 300),
                    "restrictions": _strings(role.get("restrictions"), 300),
                })
        accounts = []
        for account in _records(access.get("demo_accounts")):
            if account.get("email") and account.get("password"):
                accounts.append({
                    "email": _text(account.get("email"), 160),
                    "password": str(account.get("password")),
                    "role": _canonical_actor(account.get("role"), "user"),
                    "name": _text(account.get("name") or "Demo User", 120),
                })
        return {
            "authentication_required": bool(access.get("authentication_required")),
            "signup": _text(access.get("signup") or "not-applicable", 30),
            "signup_role": _text(access.get("signup_role"), 80),
            "roles": roles, "demo_accounts": accounts,
        }

    def _normalize_apis(self, value: Any) -> list[dict]:
        out = []
        for item in _records(value):
            path = _text(item.get("path"))
            if not path:
                continue
            handler = (_text(item.get("handler_file")).replace("\\", "/")
                       or _app_file(path, "route.js"))
            out.append({
                "name": _text(item.get("name") or f"api-{len(out)+1}", 120),
                "method": _text(item.get("method") or "GET", 10).upper(), "path": path,
                "handler_file": handler, "called_from": _strings(item.get("called_from"), 200),
                "audience": _text(item.get("audience") or "PUBLIC", 100),
                "request": _records(item.get("request")),
                "response": _records(item.get("response")), "errors": _records(item.get("errors")),
                "side_effects": _strings(item.get("side_effects"), 400),
                "success_effect": _text(item.get("success_effect"), 500),
                "requirement_ids": _strings(item.get("requirement_ids"), 40),
            })
        return out

    def _normalize_capabilities(self, value: Any) -> list[dict]:
        out = []
        for index, item in enumerate(_records(value), 1):
            behavior = _text(item.get("behavior") or item.get("requirement"), 700)
            if not behavior:
                continue
            actor = _canonical_actor(item.get("actor") or item.get("who"), "user")
            proof_points = (_strings(item.get("proof"), 500)
                            if isinstance(item.get("proof"), list)
                            else [_text(item.get("proof"), 500)] if item.get("proof") else [])
            out.append({
                "id": _text(item.get("id") or f"CAP-{index:03d}").upper(),
                "requirement_ids": _strings(item.get("requirement_ids"), 40),
                "actor": actor, "who": actor,
                "behavior": behavior, "requirement": behavior,
                "proof": "; ".join(proof_points), "proof_points": proof_points,
                "files": _strings(item.get("files"), 200),
                "route": _text(item.get("route"), 180), "e2e": bool(item.get("e2e", True)),
            })
        return out

    def _normalize_e2e(self, value: Any) -> dict:
        e2e = _dict(value)
        journeys = []
        for index, item in enumerate(_records(e2e.get("journeys")), 1):
            steps = []
            for step in _list(item.get("steps")):
                if isinstance(step, dict):
                    steps.append({
                        "at": _text(step.get("at"), 180),
                        "action": _text(step.get("action"), 300),
                        "selector_hint": _text(step.get("selector_hint"), 240),
                        "input": _dict(step.get("input")),
                        "expect": _text(step.get("expect"), 400),
                    })
                elif _text(step):
                    steps.append({"at": "", "action": _text(step), "selector_hint": "", "input": {}, "expect": ""})
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
        return {
            "strategy": _text(e2e.get("strategy") or "Requirement-driven browser journeys", 500),
            "data_preconditions": _strings(e2e.get("data_preconditions"), 400),
            "journeys": journeys,
            "route_checks": _strings(e2e.get("route_checks"), 400),
            "responsive_checks": _strings(e2e.get("responsive_checks"), 400),
            "accessibility_checks": _strings(e2e.get("accessibility_checks"), 400),
            "failure_evidence": _strings(e2e.get("failure_evidence"), 400),
        }

    def _normalize_files(self, value: Any, routes: list[dict],
                         apis: list[dict], capabilities: list[dict],
                         access: dict | None = None) -> list[dict]:
        route_by_file = {item["file"]: item for item in routes}
        out, seen = [], set()
        source = _records(value)
        for route in routes:
            if route["file"] not in {str(item.get("path") or "") for item in source}:
                source.append({**route, "path": route["file"]})
        known = {str(item.get("path") or "") for item in source}
        for api in apis:
            path = api.get("handler_file") or ""
            if path and path not in known:
                source.append({
                    "path": path, "kind": "route", "purpose": api.get("name"),
                    "requirements": api.get("requirement_ids"),
                    "contracts": [api.get("name")],
                    "done_when": [api.get("success_effect")],
                })
                known.add(path)
        for capability in capabilities:
            for path in capability.get("files") or []:
                if path and path not in known:
                    source.append({
                        "path": path, "kind": "client" if path.endswith(".jsx") else "server",
                        "purpose": capability.get("behavior"),
                        "requirements": capability.get("requirement_ids"),
                        "done_when": capability.get("proof_points"),
                    })
                    known.add(path)
        if (access or {}).get("demo_accounts") and "lib/seed.js" not in known:
            source.append({
                "path": "lib/seed.js", "kind": "server",
                "purpose": "Idempotently create all planned data and Better Auth demo credential accounts",
                "contracts": ["Export ensureSeeded; await ensureDemoAccounts before first data read"],
                "done_when": ["Every demo signs in with its exact role; seeded data is queryable"],
            })
            known.add("lib/seed.js")
        for item in source:
            path = _text(item.get("path")).replace("\\", "/").lstrip("./")
            if not path or path in seen:
                continue
            seen.add(path)
            route = route_by_file.get(path, {})
            kind = _text(item.get("kind") or route.get("kind") or "server").lower()
            if path.endswith("route.js"):
                kind = "route"
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
                "contracts": _strings(item.get("contracts"), 120),
                "done_when": _strings(item.get("done_when"), 500),
            })
        return out

    def _normalize_tasks(self, value: Any, files: list[dict]) -> list[dict]:
        files_by_path = {item["path"]: item for item in files}
        out, assigned = [], set()
        for index, item in enumerate(_records(value), 1):
            paths = []
            for file in _list(item.get("files")):
                path = file.get("path") if isinstance(file, dict) else file
                path = _text(path).replace("\\", "/").lstrip("./")
                if path and path not in paths:
                    paths.append(path)
                    assigned.add(path)
            if not paths:
                continue
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
        loose = [item for item in files if item["path"] not in assigned]
        if loose:
            out.append({
                "id": len(out) + 1, "title": "Complete remaining planned files",
                "goal": "Implement every file in the approved file graph.",
                "requirement_ids": sorted({rid for item in loose for rid in item.get("requirements", [])}),
                "files": loose,
                "depends_on": [out[-1]["id"]] if out else [],
                "done_when": ["Every listed file fulfills its plan contract."],
            })
        return out

    def _normalize_dependencies(self, value: Any) -> list[dict]:
        out = []
        for item in _list(value):
            if isinstance(item, dict):
                name, reason = _text(item.get("name")), _text(item.get("reason"), 300)
            else:
                name, reason = _text(item), "Required by the approved plan"
            if name and name not in {entry["name"] for entry in out}:
                out.append({"name": name, "reason": reason})
        return out

    def _compatibility_views(self, plan: dict) -> None:
        access = plan["roles_and_access"]
        plan["signup_role"] = access.get("signup_role") or ""
        plan["demo_accounts"] = access.get("demo_accounts") or []
        plan["role_homes"] = {role["name"]: role["home"]
                              for role in access.get("roles") or []
                              if role.get("name") and role.get("home")}
        design = plan.get("design") or {}
        plan["images"] = _records(design.get("images"))
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

    def render_markdown(self, plan: dict) -> str:
        project = plan["project"]
        lines = [f"# {project['title']}", "", "## Overview", "",
                 project["summary"], "", f"**Product type:** {project['product_type']}",
                 f"**Primary goal:** {project['primary_goal']}", "",
                 "**Target audiences:** " + (", ".join(project["target_audiences"]) or "Not specified"),
                 "", "## Source Requirement Ledger", ""]
        for req in plan["requirements"]:
            lines += [f"### {req['id']} — {req['behavior']}", "",
                      f"- Source: {req['source_text']}", f"- Actor: {req['actor']}",
                      f"- Business rule: {req['business_rule'] or 'None beyond the stated behavior'}",
                      "- Acceptance:"]
            lines += [f"  - {item}" for item in req["acceptance"]] or ["  - Observable implementation proof"]
            lines.append("")
        lines += ["## Assumptions", "", *_bullets(plan["assumptions"], "No additional assumptions"), "",
                  "## Core Capabilities", ""]
        for cap in plan["capabilities"]:
            proof = "; ".join(cap["proof_points"]) or "implementation and visible outcome"
            lines.append(f"- **{cap['id']}** ({cap['actor']}): {cap['behavior']} — proof: {proof}")
        lines += ["", "## Design", "", self.render_design(plan), "", "## Information Architecture", ""]
        ia = plan["information_architecture"]
        lines += [f"**Navigation model:** {_text(ia.get('navigation_model')) or 'Defined by the site map'}", "",
                  "### Global navigation", ""]
        for nav in _records(ia.get("global_navigation")):
            lines.append(f"- {_text(nav.get('audience'))}: {_text(nav.get('label'))} → `{_text(nav.get('path'))}` (`{_text(nav.get('test_id'))}`)")
        lines += ["", "## Site Map", "", "| Path | Parent | Type | Audience | Purpose | Reached from |",
                  "|---|---|---|---|---|---|"]
        for row in plan["site_map"]:
            lines.append("| " + " | ".join(_md_cell(row[key]) for key in
                         ("path", "parent", "type", "audience", "purpose", "reached_from")) + " |")
        lines += ["", "## Routes", "", "| Path | File | Kind | Audience | Reads | Writes | Requirements |",
                  "|---|---|---|---|---|---|---|"]
        for row in plan["routes"]:
            lines.append("| " + " | ".join(_md_cell(row[key]) for key in
                         ("path", "file", "kind", "audience", "reads", "writes", "requirement_ids")) + " |")
            if row["sections"]:
                lines.append(f"\n**`{row['path']}` sections:** " + "; ".join(row["sections"]))
            if row["actions"]:
                lines.append(f"\n**`{row['path']}` actions:** " + "; ".join(row["actions"]))
        lines += ["", "## Data Model", ""]
        for model in plan["data_model"]:
            lines += [f"### `{model['collection']}`", "", model["purpose"] or "Application data", ""]
            for field in model["fields"]:
                required = "required" if field["required"] else "optional"
                lines.append(f"- `{field['name']}`: {field['type']} ({required}) — {field['rules'] or 'no extra rule'}")
            seed = model.get("seed") or {}
            lines.append(f"- Seed: {_text(seed.get('count')) or '0'} using `{_text(seed.get('identity_field')) or 'stable identity'}`")
            lines.append("")
        lines += ["## Roles and Access", "", f"**Authentication required:** {str(plan['roles_and_access']['authentication_required']).lower()}",
                  f"**Sign-up:** {plan['roles_and_access']['signup']}", ""]
        for role in plan["roles_and_access"]["roles"]:
            lines.append(f"- **{role['name']}** → `{role['home']}` — " + "; ".join(role["permissions"]))
        lines += ["", "## API Contracts", ""]
        for api in plan["api_contracts"]:
            lines += [f"### {api['method']} `{api['path']}` — {api['name']}", "",
                      f"- Handler: `{api['handler_file']}`", f"- Called from: {', '.join(api['called_from'])}",
                      f"- Audience: {api['audience']}", f"- Success: {api['success_effect']}", ""]
        lines += ["## Architecture", "", self.render_architecture(plan), "", "## End-to-End Plan", "",
                  f"**Strategy:** {plan['e2e_plan']['strategy']}", ""]
        for journey in plan["e2e_plan"]["journeys"]:
            lines += [f"### {journey['id']} — {journey['name']} ({journey['actor']})", ""]
            for number, step in enumerate(journey["steps"], 1):
                lines.append(f"{number}. `{step['at'] or journey['start_path']}` — {step['action']} — expect {step['expect']}")
            lines.append(f"- Final assertion: {journey['final_assertion']}")
            lines.append("")
        lines += ["## File Plan", ""]
        for file in plan["file_plan"]:
            lines += [f"### `{file['path']}` ({file['kind']})", "", file["purpose"] or "Planned implementation file"]
            if file["sections"]:
                lines.append("- Sections: " + "; ".join(file["sections"]))
            if file["actions"]:
                lines.append("- Actions: " + "; ".join(file["actions"]))
            if file["done_when"]:
                lines.append("- Done when: " + "; ".join(file["done_when"]))
            lines.append("")
        lines += ["## Build Tasks", ""]
        for task in plan["tasks"]:
            lines += [f"### Task {task['id']} — {task['title']}", "", task["goal"],
                      "", "- Files: " + ", ".join(f"`{f['path']}`" for f in task["files"]),
                      "- Requirements: " + (", ".join(task["requirement_ids"]) or "supporting work"),
                      "- Done when: " + "; ".join(task["done_when"]), ""]
        lines += ["## Definition of Done", "", *_bullets(plan["definition_of_done"])]
        return "\n".join(lines).strip() + "\n"

    def render_design(self, plan: dict) -> str:
        design = plan.get("design") or {}
        lines = [f"**Direction:** {_text(design.get('direction'))}",
                 f"**Mood:** {_md_cell(design.get('mood'))}", ""]
        for title, key in (("Colors", "colors"), ("Typography", "typography"),
                           ("Layout", "layout"), ("Composition", "composition"),
                           ("Components", "components")):
            lines.append(f"### {title}")
            lines.append("")
            section = _dict(design.get(key))
            for name, value in section.items():
                lines.append(f"- **{str(name).replace('_', ' ').title()}:** {_md_cell(value)}")
            lines.append("")
        states = _dict(design.get("screen_states"))
        lines += ["### Screen states", ""]
        for name, value in states.items():
            lines.append(f"- **{name.title()}:** {_text(value)}")
        lines += ["", "### Responsive and accessibility", ""]
        lines += _bullets(design.get("responsive"), "Follow the route layouts")
        lines += _bullets(design.get("accessibility"), "Use semantic accessible controls")
        return "\n".join(lines).strip()

    def render_architecture(self, plan: dict) -> str:
        arch = plan.get("architecture") or {}
        lines = [f"**Style:** {_text(arch.get('style')) or 'Modular application'}",
                 f"**Runtime:** {_text(arch.get('runtime'))}", "", "### Layers", ""]
        for layer in _records(arch.get("layers")):
            lines.append(f"- **{_text(layer.get('name'))}:** " + "; ".join(_strings(layer.get("responsibilities"))))
            if layer.get("files"):
                lines.append("  - Files: " + ", ".join(f"`{path}`" for path in _strings(layer.get("files"))))
        lines += ["", "### Component tree", "", *_bullets(arch.get("component_tree")),
                  "", "### Data flows", "", *_bullets(arch.get("data_flows")),
                  "", "### State strategy", "", *_bullets(arch.get("state_strategy")),
                  "", "### Cross-cutting behavior", "", *_bullets(arch.get("cross_cutting")),
                  "", "### Decisions", ""]
        for decision in _records(arch.get("decisions")):
            lines.append(f"- **{_text(decision.get('decision'))}:** {_text(decision.get('reason'))} Trade-off: {_text(decision.get('tradeoff'))}")
        return "\n".join(lines).strip()


class RefinerAgent:
    """Compatibility adapter for the original Vite refine/build pipeline."""

    def __init__(self, ollama_url: str, model: str):
        self.client = OllamaClient(ollama_url)
        self.model = model

    def refine(self, raw_idea: str) -> str:
        planner = PlannerAgent(self.client, self.model, stack="vite")
        bundle = planner.create(raw_idea)
        if not bundle:
            return ""
        plan = bundle.data
        project = plan["project"]
        design = plan.get("design") or {}
        features = [cap["behavior"] for cap in plan.get("capabilities") or []]
        routes = [route["path"] for route in plan.get("routes") or []]
        spec = {
            "project_name": project["name"],
            "site_type": project.get("product_type") or "app",
            "strategy": "react-app" if len(routes) <= 1 else "react-sections",
            "title": project["title"],
            "tagline": _dict(design.get("brand")).get("tagline") or project["primary_goal"],
            "description": project["summary"],
            "color_scheme": json.dumps(design.get("colors") or {}, ensure_ascii=False),
            "style": design.get("direction") or design.get("mood") or "modern",
            "brand_name": _dict(design.get("brand")).get("name") or project["title"],
            "target_audience": ", ".join(project.get("target_audiences") or []),
            "key_features": features,
            "component_details": "\n".join(plan.get("architecture", {}).get("component_tree") or []),
            "special_instructions": bundle.markdown,
            "sections": [entry.get("label") for entry in plan.get("site_map") or [] if entry.get("type") == "page"],
            "design": design,
            "features": features,
            "plan": plan,
            "_raw_idea": raw_idea,
        }
        return json.dumps(spec, indent=2, ensure_ascii=False)


__all__ = ["PlanBundle", "PlannerAgent", "RefinerAgent", "PROMPT_PATH"]
