"""Turns a user's request into one complete, normalized product plan."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from xml.sax.saxutils import escape, quoteattr

from agents.core.ollama_client import OllamaClient, max_context
from agents.features.source_guidance import feature_image_requested

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

# One account flow can be planned under any of these names. The planner must
# not append a second page for a flow the plan already serves, or the app ships
# duplicate half-built auth screens that compete for the same navigation.
SIGN_IN_PATHS = frozenset({"/sign-in", "/signin", "/login"})
SIGN_UP_PATHS = frozenset({"/sign-up", "/signup", "/register"})

# How many times the planner is asked to close its own gaps before the build
# proceeds with what it has.
GAP_ROUNDS = 3

_PLAN_VOLUME_KEYS = ("requirements", "routes", "file_plan", "site_map",
                     "capabilities", "tasks")

def _plan_volume(plan: dict) -> dict:
    return {key: len(_list(plan.get(key))) for key in _PLAN_VOLUME_KEYS}

def _plan_is_poorer(candidate: dict, current: dict) -> bool:
    """True when a replanned answer carries less of the product than we hold."""
    new, old = _plan_volume(candidate), _plan_volume(current)
    return any(new[key] < old[key] for key in _PLAN_VOLUME_KEYS)

def _plan_is_empty(plan: dict) -> bool:
    """A plan with nothing to build is a failed plan, not a small product."""
    volume = _plan_volume(plan)
    return not (volume["routes"] or volume["file_plan"])

@dataclass
class PlanBundle:
    data: dict
    markdown: str
    architecture_markdown: str
    design_markdown: str
    raw: str
    sitemap_xml: str = ""

def _text(value: Any, limit: int = 0) -> str:
    result = " ".join(str(value or "").split())
    return result[:limit] if limit else result

def _list(value: Any) -> list:
    return value if isinstance(value, list) else []

def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}

def _strings(value: Any, limit: int = 0) -> list[str]:
    # A model that answers `"exports": "ensureSeeded"` means the one-item list.
    # Dropping the scalar threw the answer away, so a gap round that asked for
    # exactly that value could report the same gap forever and never close it.
    items = _list(value) or ([value] if isinstance(value, (str, int, float)) else [])
    out = []
    for item in items:
        text = _text(item, limit)
        if text and text not in out:
            out.append(text)
    return out

def _records(value: Any) -> list[dict]:
    return [dict(item) for item in _list(value) if isinstance(item, dict)]

def _slug(value: str, fallback: str = "agentforge-app") -> str:
    result = re.sub(r"[^a-z0-9]+", "-", _text(value).lower()).strip("-")
    return result[:48].strip("-") or fallback

def _xml_attrs(**values) -> str:
    """Render only the attributes that carry a value."""
    return "".join(f' {name.replace("_", "-")}={quoteattr(_text(value))}'
                   for name, value in values.items() if _text(value))

def _xml_list(tag: str, item_tag: str, items: Any, indent: str = "    ") -> list[str]:
    """Render one child list, or nothing when the plan left it empty."""
    values = _strings(items, 500)
    if not values:
        return []
    return ([f"{indent}<{tag}>"]
            + [f"{indent}  <{item_tag}>{escape(value)}</{item_tag}>" for value in values]
            + [f"{indent}</{tag}>"])

def render_sitemap_xml(plan: dict) -> str:
    """One XML document joining every planned page, API and navigation link."""
    project = _dict(plan.get("project"))
    ia = _dict(plan.get("information_architecture"))
    access = _dict(plan.get("roles_and_access"))
    known = {_text(page.get("path")): page for page in _records(plan.get("site_map"))}
    pages = [route for route in _records(plan.get("routes"))
             if _text(route.get("kind")) != "route"]
    apis = _records(plan.get("api_contracts"))

    lines = ["<sitemap" + _xml_attrs(app=project.get("title"),
                                     pages=len(pages), apis=len(apis)) + ">",
             "  <navigation" + _xml_attrs(model=ia.get("navigation_model")) + ">"]
    for nav in _records(ia.get("global_navigation")):
        lines.append("    <link" + _xml_attrs(
            audience=nav.get("audience"), label=nav.get("label"),
            path=nav.get("path"), testid=nav.get("test_id")) + "/>")
    for role in _records(access.get("roles")):
        lines.append("    <home" + _xml_attrs(role=role.get("name"),
                                              path=role.get("home")) + "/>")
    lines.append("  </navigation>")

    for page in pages:
        meta = _dict(known.get(_text(page.get("path"))))
        lines.append("  <page" + _xml_attrs(
            path=page.get("path"), file=page.get("file"), kind=page.get("kind"),
            audience=page.get("audience") or meta.get("audience"),
            parent=meta.get("parent"), label=meta.get("label")) + ">")
        for tag, value in (("purpose", page.get("purpose") or meta.get("purpose")),
                           ("layout", page.get("layout"))):
            if _text(value):
                lines.append(f"    <{tag}>{escape(_text(value, 700))}</{tag}>")
        for tag, item_tag, items in (
                ("sections", "section", page.get("sections")),
                ("actions", "action", page.get("actions")),
                ("states", "state", page.get("states")),
                ("reads", "collection", page.get("reads")),
                ("writes", "collection", page.get("writes")),
                ("reached-from", "entry", meta.get("reached_from")),
                ("children", "child", meta.get("children")),
                ("requirements", "req", page.get("requirement_ids"))):
            lines += _xml_list(tag, item_tag, items)
        lines.append("  </page>")

    for api in apis:
        lines.append("  <api" + _xml_attrs(
            name=api.get("name"), method=api.get("method"), path=api.get("path"),
            file=api.get("handler_file"), audience=api.get("audience")) + ">")
        lines += _xml_list("called-from", "file", api.get("called_from"))
        if _text(api.get("success_effect")):
            lines.append("    <success>"
                         + escape(_text(api.get("success_effect"), 500))
                         + "</success>")
        lines.append("  </api>")

    lines.append("</sitemap>")
    return "\n".join(lines) + "\n"

DESIGN_ARCHETYPES = (
    "editorial magazine — type-led asymmetry, a large serif display face, hairline "
    "rules, captioned imagery, one restrained accent",
    "soft minimal — generous whitespace, rounded surfaces, a single muted accent, "
    "quiet type scale, shadow used sparingly",
    "dark technical — near-black canvas, one luminous accent, dense data surfaces, "
    "tabular numerals, precise 1px borders",
    "warm organic — earthy neutrals, humanist type, soft large radii, "
    "photography-first blocks, gentle grain",
    "high-contrast graphic — flat colour blocks, hard borders, oversized labels, "
    "no shadows, deliberate colour clashes",
    "vivid product — saturated duotone, bold geometric sans, layered cards, "
    "confident motion, bright empty states",
    "archival museum — paper-tone canvas, small caps, wide letter-spacing, "
    "framed imagery, ink-black text",
    "utility console — compact rows, monospace accents, muted greys with one "
    "signal colour, table-first composition",
)

def _design_archetype(seed: str) -> str:
    """A stable but per-app starting direction, so builds stop looking alike."""
    digest = hashlib.sha256(_text(seed).lower().encode("utf-8")).hexdigest()
    return DESIGN_ARCHETYPES[int(digest, 16) % len(DESIGN_ARCHETYPES)]

SHELL_FILES = (
    ("app/layout.jsx", "server",
     "Root shell: import ./globals.css, render <html>/<body>, and wrap "
     "{children} in the shared Navbar and Footer so every route has the "
     "same chrome"),
    ("components/Navbar.jsx", "client",
     "Global navigation for every route: brand, the planned destinations "
     "with an active state, a working mobile menu, and session-aware "
     "actions when the plan has accounts"),
    ("components/Footer.jsx", "server",
     "Global footer for every route: brand line, planned link groups and "
     "closing row"),
)

IMAGE_STYLE = ("photographic, believable materials, natural commercial lighting, "
               "clean composition, no watermark")
IMAGE_NO_TEXT = "no text, no lettering, no logos"
IMAGE_AD_STYLE = ("premium commercial advertising composition, strong visual hierarchy, "
                  "background scene with clear copy-safe space, polished campaign art")
IMAGE_FIELD_WORDS = ("image", "photo", "picture", "thumbnail", "cover",
                     "banner", "avatar", "poster")
AUTH_COLLECTIONS = {"user", "users", "session", "sessions", "account",
                    "accounts", "verification", "jwks"}
IMAGE_LIMIT = 12
SEED_IMAGE_LIMIT = 4

def _image_field(model: dict) -> str:
    """The field a seeded row already keeps its picture in, when it has one."""
    for field in _records(model.get("fields")):
        name = _text(field.get("name"), 100)
        if any(word in name.lower() for word in IMAGE_FIELD_WORDS):
            return name
    return ""

def _seed_count(model: dict) -> int:
    """How many seeded rows of this collection deserve their own picture."""
    digits = re.sub("[^0-9]", "", str(_dict(model.get("seed")).get("count") or ""))
    return min(int(digits or 0), SEED_IMAGE_LIMIT)

def _demo_accounts(accounts: list[dict], roles: list[dict]) -> list[dict]:
    """Keep every explicit identity; synthesize only roles still unrepresented."""
    out, taken_roles, taken_emails = [], set(), set()
    for account in accounts:
        role, email = _text(account["role"]).lower(), account["email"].lower()
        if email and email not in taken_emails:
            if role: taken_roles.add(role)
            taken_emails.add(email)
            out.append(account)
    for role in roles:
        name = _text(role.get("name"), 80)
        if not name or name.lower() in taken_roles:
            continue
        email = f"{_slug(name, 'demo')}@demo.local"
        if email in taken_emails:
            continue
        taken_roles.add(name.lower())
        taken_emails.add(email)
        out.append({"email": email, "password": "password123", "role": name,
                    "name": f"Demo {name.title()}"})
    return out

def _singular(word: str) -> str:
    """Name one row of a collection so its picture prompt reads naturally."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    return word[:-1] if word.endswith("s") else word

def _plan_images(plan: dict, design: dict, source_input: str) -> list[dict]:
    """Plan pictures only when asked: banner, poster, auth pages, seeded rows."""
    if not feature_image_requested(source_input or plan.get("source_input_summary")):
        return []
    title = plan["project"]["title"]
    out, taken = [], set()

    def add(key: str, purpose: str, subject: str, aspect: str) -> None:
        key = _slug(key, "")
        if not key or key in taken or len(out) >= IMAGE_LIMIT:
            return
        taken.add(key)
        out.append({"key": key, "purpose": _text(purpose, 300),
                    "prompt": _text(subject, 650), "aspect": aspect})

    context = _text(plan["project"].get("summary") or plan.get("description"), 180)
    add("banner", "Hero banner across the top of the public landing page",
        f'wide premium advertisement for {title}; visually represent {context}; '
        f'background-led campaign scene, include the exact readable brand name "{title}" '
        f'as the main headline, one short relevant promotional line, {IMAGE_AD_STYLE}, {IMAGE_STYLE}',
        "banner")
    add("poster", "Promotional poster panel on the public landing page",
        f'promotional retail advertisement for {title}; visually represent {context}; '
        f'include the exact readable brand name "{title}" with one concise offer-style headline, '
        f'product/subject as the visual focus, {IMAGE_AD_STYLE}, {IMAGE_STYLE}', "poster")
    access = _dict(plan.get("roles_and_access"))
    if access.get("authentication_required"):
        add("login", "Backdrop beside the /sign-in form",
            f'calm, premium sign-in background for {title}; visually match {context}; '
            f'leave quiet negative space for the form UI, {IMAGE_STYLE}, {IMAGE_NO_TEXT}', "portrait")
        if _text(access.get("signup")).lower() == "open":
            add("signup", "Backdrop beside the /sign-up form",
                f'welcoming sign-up background for {title}; visually match {context}; '
                f'warm aspirational scene with quiet negative space for the form UI, '
                f'{IMAGE_STYLE}, {IMAGE_NO_TEXT}', "portrait")

    models = [model for model in _records(plan.get("data_model"))
              if _text(model.get("collection")).lower() not in AUTH_COLLECTIONS
              and _seed_count(model)]
    seeded = [(model, _image_field(model)) for model in models]
    seeded = [(model, field) for model, field in seeded if field]
    if models and not seeded:
        models[0]["fields"].append({
            "name": "image", "type": "string", "required": False,
            "rules": "Path of this row's generated picture under /generated"})
        seeded = [(models[0], "image")]
    for model, field in seeded:
        collection = _text(model.get("collection"), 100)
        one = _singular(collection)
        for number in range(1, _seed_count(model) + 1):
            key = _slug(collection + "-" + str(number), "")
            add(key, "Seeded `" + collection + "` row " + str(number) +
                ": set its `" + field + "` to /generated/" + key + ".png",
                one + " for " + title + ", " + _text(model.get("purpose"), 100) +
                f", authentic domain-specific subject, premium e-commerce/catalog photography, "
                f"single clear focal subject, uncluttered background, {IMAGE_STYLE}, {IMAGE_NO_TEXT}",
                "square")

    for extra in _records(design.get("images")):
        purpose = _text(extra.get("purpose"), 300)
        extra_prompt = _text(extra.get("prompt"), 420) or purpose
        add(extra.get("key"), purpose,
            f"{extra_prompt}; visually consistent with {title} and its real domain; "
            f"{IMAGE_STYLE}, {IMAGE_NO_TEXT}", _text(extra.get("aspect"), 20) or "wide")
    return out

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
    """Match an access description to an exact role name."""
    actor = _text(value, 80)
    actor = re.sub(r"^(?:as\s+)?role\s*[:=-]?\s+", "", actor,
                   flags=re.I).strip()
    return actor or fallback

def _json_object(raw: str) -> dict:
    """Read the first complete JSON object in a model response."""
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
    """Create the shared plan used by every later stage."""

    def __init__(self, client: OllamaClient, model: str, *, stack: str = "next",
                 callbacks: dict | None = None, think: bool | None = None,
                 stream: Callable | None = None):
        self.client = client
        self.model = model
        self.stack = "next"
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
            except Exception as exc:  # A callback failure must not stop planning.
                log.warning("planner callback %s failed: %s", name, exc)

    def _log(self, level: str, message: str) -> None:
        callback = self.cb.get("on_log")
        if callable(callback):
            self._fire("on_log", level, message)
        else:
            log.info(message)

    def _system_prompt(self) -> str:
        return PROMPT_PATH.read_text(encoding="utf-8") + "\n\n" + NEXT_STACK

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
            "\n\nSTARTING ART DIRECTION for this app: " +
            _design_archetype(requirements) +
            ". Interpret it for this domain and audience — derive the palette, "
            "type, spacing and composition from it. Do not fall back to a "
            "generic gold-and-serif luxury look, and do not reuse a direction "
            "from another product."
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
        plan, raw = self._close_gaps(messages, plan, raw, requirements)
        if _plan_is_empty(plan):
            # Every later stage reads this plan. An empty one builds nothing,
            # leaves the scaffold placeholder serving, and still passes a
            # journey that only opens "/" — a green result for no product.
            self._log("ERROR", "   ❌ The planner produced no routes and no "
                               "files. Refusing to build from an empty plan — "
                               "the model's answer was probably truncated.")
            return None
        markdown = self.render_markdown(plan)
        architecture = "# Architecture\n\n" + self.render_architecture(plan)
        design = "# Product Design\n\n" + self.render_design(plan)
        self._fire("on_file_end", "plan.md", markdown)
        return PlanBundle(plan, markdown, architecture, design, raw,
                          render_sitemap_xml(plan))

    def normalize(self, raw: dict, source_input: str = "") -> dict:
        """Make plan names consistent without changing its decisions."""
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
        plan["site_map"] = self._normalize_site_map(plan.get("site_map"))
        plan["api_contracts"] = self._normalize_apis(plan.get("api_contracts"))
        plan["routes"] = self._normalize_routes(plan.get("routes"))
        plan["data_model"] = self._normalize_data(plan.get("data_model"))
        plan["capabilities"] = self._normalize_capabilities(plan.get("capabilities"))
        plan["architecture"] = _dict(plan.get("architecture"))
        plan["e2e_plan"] = self._normalize_e2e(plan.get("e2e_plan"))
        plan["file_plan"] = self._normalize_files(
            plan.get("file_plan"), plan["routes"])
        plan["tasks"] = self._normalize_tasks(plan.get("tasks"), plan["file_plan"])
        plan["dependencies"] = self._normalize_dependencies(plan.get("dependencies"))
        plan["definition_of_done"] = _strings(plan.get("definition_of_done"), 500)
        if plan["roles_and_access"]["authentication_required"]:
            aliases = {"users": "user", "accounts": "account", "sessions": "session", "verifications": "verification"}
            for model in plan["data_model"]:
                model["collection"] = aliases.get(model["collection"].lower(), model["collection"])
                model["relationships"] = [re.sub(r"\b(users|accounts|sessions|verifications)\b", lambda m: aliases[m.group(1).lower()], rel, flags=re.I) for rel in model["relationships"]]
            for route in plan["routes"]:
                route["reads"] = [aliases.get(x.lower(), x) for x in route["reads"]]
                route["writes"] = [aliases.get(x.lower(), x) for x in route["writes"]]
        self._compatibility_views(plan, source_input)
        return plan

    def _close_gaps(self, messages: list[dict], plan: dict, raw: str,
                    requirements: str) -> tuple[dict, str]:
        """Send the planner its own holes until it reports a complete plan.

        Only the planner writes plan content, so an incomplete first answer is
        answered by asking again rather than by filling the hole in Python.
        """
        for attempt in range(1, GAP_ROUNDS + 1):
            gaps = self.plan_gaps(plan)
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
                self._call(messages, chunks.append)
            except Exception as exc:
                self._log("WARN", f"   ⚠ Gap round failed: {exc}")
                return plan, raw
            reply = "".join(chunks)
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

    def plan_gaps(self, plan: dict) -> list[str]:
        """Every hole the planner left, phrased so the planner can close it.

        This only reads the plan against itself. Nothing here writes a page,
        route, file or task: a gap goes back to the planner, because a page
        invented in Python arrives with no purpose, sections, requirements or
        E2E coverage and quietly competes with the one the planner meant.
        """
        gaps = []
        access = _dict(plan.get("roles_and_access"))
        pages = [item for item in plan.get("site_map") or []
                 if _text(item.get("type") or "page").lower() == "page"]
        page_paths = {_text(item.get("path")) for item in pages}
        route_paths = {_text(item.get("path")) for item in plan.get("routes") or []}
        route_files = {_text(item.get("file")) for item in plan.get("routes") or []}
        planned_files = {_text(item.get("path")) for item in plan.get("file_plan") or []}
        assigned = {_text(file.get("path"))
                    for task in plan.get("tasks") or []
                    for file in task.get("files") or []}

        for label, aliases, required in (
            ("sign-in", SIGN_IN_PATHS, bool(access.get("authentication_required"))),
            ("sign-up", SIGN_UP_PATHS,
             _text(access.get("signup")).lower() == "open"),
        ):
            if required and not (page_paths & aliases):
                gaps.append(
                    f"roles_and_access needs a {label} flow, but no site_map "
                    f"page serves one. Add the page you intend (for example "
                    f"/{label}) with its route, file and journey.")

        for nav in _records(_dict(plan.get("information_architecture"))
                            .get("global_navigation")):
            path = _text(nav.get("path"))
            if (path.startswith("/") and not path.startswith("/api/")
                    and path not in page_paths):
                gaps.append(
                    f"global_navigation links to {path}, but no site_map page "
                    f"serves it. Add that page or drop the link.")

        for item in pages:
            path = _text(item.get("path"))
            if path and path not in route_paths:
                gaps.append(f"site_map page {path} has no routes entry naming "
                            f"its file.")

        for api in plan.get("api_contracts") or []:
            handler = _text(api.get("handler_file"))
            if handler and handler not in route_files:
                gaps.append(
                    f"api_contracts {_text(api.get('method'))} "
                    f"{_text(api.get('path'))} has no routes entry for "
                    f"{handler}.")

        for item in plan.get("routes") or []:
            file = _text(item.get("file"))
            if file and file not in planned_files:
                gaps.append(f"routes entry {_text(item.get('path'))} owns "
                            f"{file}, but file_plan does not plan it.")

        for capability in plan.get("capabilities") or []:
            for file in capability.get("files") or []:
                if _text(file) and _text(file) not in planned_files:
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
                        gaps.append(f"route {_text(route.get('path'))} names collection {name}, but data_model does not define it.")
        for model in plan.get("data_model") or []:
            collection = str(model.get("collection") or "")
            for rel in model.get("relationships") or []:
                m = re.match(r"\s*([A-Za-z_]\w*)\s*->\s*([A-Za-z_]\w*)\._id\s*$", str(rel))
                if m and m.group(1) not in models.get(collection, set()):
                    gaps.append(f"relationship {collection}.{m.group(1)} is missing that source field from data_model.")
                if m and m.group(2) not in models:
                    gaps.append(f"relationship {rel} targets collection {m.group(2)}, but data_model does not define it.")
            if collection and collection not in used_models:
                gaps.append(f"data_model collection {collection} is never read or written by a planned route; connect it to the user flow or remove it.")

        seeds = bool(access.get("demo_accounts")) or any(
            _seed_count(model) for model in plan.get("data_model") or [])
        if seeds:
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

    def _normalize_site_map(self, value: Any) -> list[dict]:
        out = []
        source = _records(value)
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

    def _normalize_routes(self, value: Any) -> list[dict]:
        out = []
        source = _records(value)
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
                "layout": _text(item.get("layout"), 700),
                "requirement_ids": _strings(item.get("requirement_ids"), 40),
            })
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
        required = bool(access.get("authentication_required"))
        return {
            "authentication_required": required,
            "signup": _text(access.get("signup") or "not-applicable", 30),
            "signup_role": _text(access.get("signup_role"), 80),
            "roles": roles,
            "demo_accounts": _demo_accounts(accounts, roles) if required else accounts,
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

    def _normalize_files(self, value: Any, routes: list[dict]) -> list[dict]:
        route_by_file = {item["file"]: item for item in routes}
        out, seen = [], set()
        source = _records(value)
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
                "layout": _text(item.get("layout") or route.get("layout"), 700),
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

    def _compatibility_views(self, plan: dict, source_input: str = "") -> None:
        access = plan["roles_and_access"]
        plan["signup_role"] = access.get("signup_role") or ""
        plan["demo_accounts"] = access.get("demo_accounts") or []
        plan["role_homes"] = {role["name"]: role["home"]
                              for role in access.get("roles") or []
                              if role.get("name") and role.get("home")}
        design = plan.get("design") or {}
        plan["images"] = _plan_images(plan, design, source_input)
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
            if row.get("layout"):
                lines.append(f"\n**`{row['path']}` layout:** " + row["layout"])
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
        accounts = plan["roles_and_access"]["demo_accounts"]
        if accounts:
            lines += ["", "### Demo Accounts", "", "| Email | Password | Role |",
                      "|---|---|---|"]
            for account in accounts:
                lines.append(f"| {account['email']} | {account['password']} | {account['role']} |")
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
        images = _records(plan.get("images"))
        if images:
            lines += ["", "### Images", ""]
            for item in images:
                lines.append(f"- `/generated/{item.get('key')}.png` "
                             f"({item.get('aspect') or 'landscape'}) — "
                             f"{_text(item.get('purpose'), 300)}")
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

__all__ = ["PlanBundle", "PlannerAgent", "PROMPT_PATH"]
