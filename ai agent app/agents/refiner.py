"""
agents/refiner.py — Architect agent.

Classifies the user's idea and produces a detailed build spec that now includes,
in addition to the visual brief:
  • data_model  — MongoDB collections with typed fields (drives the scaffold)
  • sections    — an ordered list of 6-10 rich sections for one long, beautiful page

Everything downstream (schema, API, frontend) is derived from this spec, so the
Architect is the single source of truth for what gets built.
"""
import json
import logging
import re

from agents import llm
from agents.scaffold import pascal

log = logging.getLogger("refiner")

# ── Site-type keyword detection (kept from the original) ──────────────────────
SITE_TYPES = {
    "ecommerce":  ["online shop", "online store", "e-commerce", "ecommerce", "marketplace",
                   "product listing", "buy online", "sell online", "shopping cart", "retail store"],
    "portfolio":  ["portfolio", "my work", "showcase my work", "personal website", "resume site",
                   "cv site", "my projects", "show my skills"],
    "saas":       ["saas", "b2b platform", "subscription service", "crm tool", "analytics platform",
                   "team dashboard", "business software"],
    "blog":       ["blog", "article site", "news site", "magazine", "journal", "writing platform",
                   "content site", "editorial"],
    "restaurant": ["restaurant website", "cafe website", "menu website", "food menu",
                   "bistro", "dine-in", "reservations page", "restaurant landing"],
    "dashboard":  ["dashboard", "admin panel", "analytics dashboard", "stats dashboard",
                   "metrics", "data visualization", "monitoring panel", "reporting tool"],
    "social":     ["social network", "community platform", "forum", "chat app", "messaging app",
                   "profile page", "user feed", "social media"],
    "app":        ["todo app", "task manager", "habit tracker", "note taking", "notes app",
                   "expense tracker", "budget tracker", "workout tracker", "fitness tracker",
                   "mood tracker", "journal app", "reading list", "bookmark manager",
                   "recipe app", "meal planner", "study planner", "flashcard app",
                   "inventory", "crm", "booking", "appointment", "project tracker", "kanban"],
    "tool":       ["calculator", "converter", "unit converter", "currency converter",
                   "timer", "stopwatch", "clock", "countdown", "weather app", "word counter",
                   "password generator", "qr generator", "color picker"],
    "general":    [],
}

KEYWORD_WEIGHTS = {"app": 3, "dashboard": 3, "ecommerce": 2, "blog": 2,
                   "social": 2, "restaurant": 2, "tool": 1}

# Section blueprints per type — one long, multi-section page. Data-driven sections
# (List/Grid/Add/Manage) are wired to the API contract by the frontend agent.
SECTION_MAP = {
    "app":        ["Hero", "QuickAdd", "ItemList", "Stats", "Features", "CTA"],
    "ecommerce":  ["Hero", "FeaturedProducts", "ProductGrid", "Categories", "Testimonials", "Newsletter"],
    "blog":       ["Hero", "FeaturedPosts", "PostList", "Categories", "Newsletter"],
    "dashboard":  ["Hero", "Overview", "DataPanel", "Insights", "Activity"],
    "social":     ["Hero", "Composer", "Feed", "Trending", "CTA"],
    "saas":       ["Hero", "Features", "HowItWorks", "LiveDemo", "Pricing", "CTA"],
    "restaurant": ["Hero", "Menu", "Reservations", "Gallery", "About", "Contact"],
    "portfolio":  ["Hero", "About", "Projects", "Skills", "Contact"],
    "tool":       ["Hero", "Tool", "Features", "HowItWorks", "CTA"],
    "general":    ["Hero", "Features", "Showcase", "About", "CTA"],
}

# Fallback data models per type when the LLM omits or botches data_model.
DEFAULT_MODELS = {
    "app":       [{"name": "Item", "fields": [
                    {"name": "title", "type": "String", "required": True},
                    {"name": "notes", "type": "String"},
                    {"name": "done", "type": "Boolean", "default": False},
                    {"name": "priority", "type": "Number", "default": 1}]}],
    "ecommerce": [{"name": "Product", "fields": [
                    {"name": "name", "type": "String", "required": True},
                    {"name": "price", "type": "Number", "default": 0},
                    {"name": "description", "type": "String"},
                    {"name": "image", "type": "String"},
                    {"name": "category", "type": "String"}]}],
    "blog":      [{"name": "Post", "fields": [
                    {"name": "title", "type": "String", "required": True},
                    {"name": "body", "type": "String"},
                    {"name": "author", "type": "String"},
                    {"name": "tags", "type": "[String]"}]}],
    "dashboard": [{"name": "Entry", "fields": [
                    {"name": "label", "type": "String", "required": True},
                    {"name": "value", "type": "Number", "default": 0},
                    {"name": "category", "type": "String"}]}],
    "social":    [{"name": "Post", "fields": [
                    {"name": "author", "type": "String", "required": True},
                    {"name": "content", "type": "String", "required": True},
                    {"name": "likes", "type": "Number", "default": 0}]}],
    "general":   [{"name": "Entry", "fields": [
                    {"name": "title", "type": "String", "required": True},
                    {"name": "description", "type": "String"}]}],
}

VALID_TYPES = {"String", "Number", "Boolean", "Date", "ObjectId", "Mixed", "Array"}

# ── Multi-page / auth / role detection ────────────────────────────────────────
MULTIPAGE_KEYWORDS = [
    "login", "log in", "sign up", "signup", "sign in", "signin", "auth", "account",
    "register", "role", "roles", "admin", "dashboard", "manage", "owner", "seller",
    "vendor", "agent", "multi page", "multi-page", "multipage", "multiple pages",
    "marketplace", "users", "staff", "permission", "moderat", "author", "tenant",
    "portal", "crm", "booking", "reservation", "hotel", "hostel", "rental",
]
# Default role sets per domain (most-privileged first). Refiner-derived when the LLM
# doesn't supply a `roles` list.
ROLE_PRESETS = {
    "ecommerce":  ["admin", "seller", "customer"],
    "marketplace": ["admin", "seller", "customer"],
    "blog":       ["admin", "author", "reader"],
    "social":     ["admin", "moderator", "member"],
    "saas":       ["admin", "manager", "member"],
    "dashboard":  ["admin", "manager", "member"],
    "restaurant": ["admin", "manager", "staff"],
    "portfolio":  ["admin", "user"],
    "tool":       ["admin", "user"],
    "app":        ["admin", "user"],
    "general":    ["admin", "user"],
}
# Roles that only consume (browse/buy/read), never create the owned resource.
CONSUMER_NAMES = {"customer", "reader", "guest", "buyer", "client", "shopper", "viewer"}

# An idea that RULES OUT accounts still mentions them ("no login, no accounts, no roles"), and a bare
# keyword scan reads those denials as demands — that is how a "single-page journal, no login" became a
# 10-page app with user+admin roles. Strip each negated phrase before scanning, so only what the idea
# actually ASKS for can trigger multipage/auth. Span-level (not whole-idea) stripping keeps mixed ideas
# working: "no login for visitors, but admins manage stock" still detects the admin side.
_NEGATED_FEATURE = re.compile(
    # The filler quantifier stays GREEDY so "no user accounts" is consumed whole; lazy matching
    # stops at "no user" and leaves "accounts" behind to trigger the very scan this prevents.
    r"\b(?:no|without|not|never|zero|non|excluding)\s+(?:\w+\s+){0,2}"
    r"(?:log\s?ins?|sign[\s-]?ups?|sign[\s-]?ins?|signups?|signins?|logins?|auth\w*|"
    r"accounts?|users?|roles?|admins?|registrations?|registering|register|passwords?|"
    r"permissions?|dashboards?|profiles?)\b",
    re.I,
)

def _clean_json(frag: str) -> str:
    """Strip the JSON mistakes small models make most: // comments, trailing commas."""
    frag = re.sub(r"(?m)//[^\n]*", "", frag)          # line comments
    frag = re.sub(r",(\s*[}\]])", r"\1", frag)        # trailing commas
    return frag


def _parse_json_lenient(text: str) -> dict:
    """Parse the first JSON object in text; salvage a truncated one if needed."""
    s = text.find("{")
    if s == -1:
        return {}
    frag = text[s:]
    # 1) strict parse of the (cleaned) full object
    end = frag.rfind("}")
    if end != -1:
        for candidate in (frag[:end + 1], _clean_json(frag[:end + 1])):
            try:
                return json.loads(candidate)
            except Exception:
                pass
    frag = _clean_json(frag)
    # 2) salvage: cut at the last shallow comma and close open brackets
    depth, in_str, esc, last_comma, stack = 0, False, False, None, []
    for i, ch in enumerate(frag):
        if in_str:
            if esc:            esc = False
            elif ch == "\\":   esc = True
            elif ch == '"':    in_str = False
            continue
        if ch == '"':          in_str = True
        elif ch in "{[":       stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack: stack.pop()
        elif ch == "," and len(stack) <= 2:
            last_comma = i
    if last_comma:
        candidate = frag[:last_comma] + "".join(reversed(stack))
        try:
            return json.loads(candidate)
        except Exception:
            pass
    return {}


SYSTEM_PROMPT = """\
You are a senior full-stack architect. Analyze the user's idea and produce a DETAILED \
JSON build spec for a Next.js + MongoDB app.

CRITICAL RULES:
1. Output ONLY a raw JSON object — no markdown, no prose, no code fences.
2. site_type must match the idea: tool, app, dashboard, ecommerce, blog, social, saas, \
restaurant, portfolio, or general.
3. data_model = the MongoDB collections the app persists (the app's OWN entities). Each \
collection has a PascalCase singular name and a list of fields. Field types MUST be one of: \
String, Number, Boolean, Date, ObjectId, [String]. Mark required/default where sensible. \
Keep it to 1-2 collections with only the fields the app actually needs. \
NAME EACH COLLECTION AFTER THE REAL DOMAIN NOUN IT STORES and give it DOMAIN-SPECIFIC fields — \
e.g. a pharmacy → Medicine (name, dosage, stock, price, expiryDate); an alarm app → Alarm \
(label, time, days, enabled); a recipe app → Recipe (title, ingredients, steps, minutes). \
NEVER use a generic placeholder name like Entry, Item, Record, Data, Thing, Element, or a vague \
Calculation with label/value/category — those are WRONG; pick the concrete entity the idea is about. \
NEVER include a User/Account/Auth collection — authentication and user accounts are added \
automatically. If the app truly stores nothing, use an empty array [].
4. sections = an ordered list of 6-10 PascalCase section names for ONE long, beautiful \
scrolling landing/app page. Include a "Hero" first, data sections that create and list \
the main entity (e.g. QuickAdd, ItemList, ProductGrid), and marketing sections (Features, \
CTA). Section names become React components.
5. description = 3-5 specific sentences about exactly what the app does.
6. app_kind: "multipage-app" if the app needs login/accounts, different user roles \
(admin/seller/customer, or manager/staff/guest, …), an admin area, or multiple pages; \
otherwise "single-page". OBEY THE IDEA'S OWN WORDS: if it says "single-page", "one page", \
"no login", "no accounts", "no roles" or "no admin", app_kind IS "single-page" with "roles": [] \
— a denial is NOT a request for that feature. Only choose "multipage-app" when the idea actually \
ASKS for accounts, roles or an admin area.
7. roles (only when app_kind is "multipage-app"): 2-4 lowercase role names for the kinds of \
users, most-privileged first, always starting with "admin" (e.g. ["admin","seller","customer"] \
or ["admin","manager","receptionist","guest"]). Omit for single-page apps.
8. theme = TWO hex colors (`accent`, `accent2`) that this app's whole UI is built from. CHOOSE them \
for THIS domain and mood — they must differ from app to app: pharmacy → clinical teal #14b8a6 / \
mint #5eead4; gratitude journal → warm amber #f59e0b / rose #fb7185; finance → emerald #10b981 / \
lime #84cc16; alarm app → sunrise orange #fb923c / gold #fbbf24; recipe app → tomato #ef4444 / \
basil #22c55e. `accent2` is a neighbouring or complementary hue, never the same as `accent`. \
NEVER fall back to indigo #6366f1 / blue / cyan out of habit — pick the color the IDEA suggests, \
and let `color_scheme` describe it in words.

Output JSON with EXACTLY these keys:
{
  "project_name": "kebab-case-name",
  "site_type": "app",
  "app_kind": "single-page",
  "roles": [],
  "title": "App Title",
  "tagline": "One compelling sentence",
  "description": "3-5 specific sentences",
  "color_scheme": "e.g. deep navy #0f172a with emerald #10b981 accents",
  "theme": { "accent": "#10b981", "accent2": "#34d399" },
  "style": "modern|minimal|bold|playful|luxury",
  "brand_name": "Brand Name",
  "target_audience": "Specific users",
  "key_features": ["feature 1", "feature 2", "feature 3", "feature 4"],
  "data_model": [
    { "name": "Task", "fields": [
      { "name": "title", "type": "String", "required": true },
      { "name": "done", "type": "Boolean", "default": false }
    ]}
  ],
  "sections": ["Hero", "QuickAdd", "ItemList", "Stats", "Features", "CTA"],
  "special_instructions": "Detailed notes: interactions, data flow, visual style"
}"""

QUALITY_PROMPT_APPEND = """

STRICT QUALITY CONTRACT:
- Entities and their fields must be DOMAIN-SPECIFIC to the idea. A generic Entry/Item/Record/Data
  collection, or fields like label/value/category standing in for the real ones, is INVALID.
- Define only routes, API fields, roles, metrics, and actions represented in this JSON.
- Never invent links, redirects, endpoints, fields, or placeholder buttons.
- Authentication, ownership, validation, totals, and workflow transitions are server-owned.
- Persisted records use `_id`; do not introduce a second `id` identifier.
- Every collection needs a usable required display field and valid enum/default values.
- Functional pages must specify their resource mapping and testable API actions.
"""


class RefinerAgent:
    def __init__(self, ollama_url=None, model=None):
        self.model = model or llm.GEN_MODEL

    # ── Public ────────────────────────────────────────────────────────────────
    def refine(self, raw_idea: str):
        log.info("Architect: refining idea with %s", self.model)
        kw_type = self._detect_type(raw_idea)
        log.info("   Keyword-detected type: %s", kw_type)

        data = self._llm_refine(raw_idea, kw_type)
        spec = self._build_spec(raw_idea, kw_type, data)

        log.info("   Final: '%s' | type=%s | kind=%s | %d collection(s) | roles=%s | %d page(s)",
                 spec["title"], spec["site_type"], spec["app_kind"], len(spec["data_model"]),
                 [r["name"] for r in spec.get("roles", [])], len(spec.get("pages", [])))
        return json.dumps(spec, indent=2)

    # ── Type detection ──────────────────────────────────────────────────────────
    def _detect_type(self, idea: str) -> str:
        il = idea.lower()
        scores = {}
        for st, kws in SITE_TYPES.items():
            if not kws:
                continue
            matches = sum(1 for k in kws if k in il)
            if matches:
                scores[st] = matches * KEYWORD_WEIGHTS.get(st, 1)
        if not scores:
            return "general"
        return max(scores, key=lambda k: scores[k])

    # ── LLM call ────────────────────────────────────────────────────────────────
    def _llm_refine(self, raw_idea: str, kw_type: str) -> dict:
        hint = (f"\nThe keyword analysis suggests site_type='{kw_type}'. "
                f"Override only if the idea clearly implies something else."
                if kw_type != "general" else "")
        base_msg = (f"User idea: {raw_idea}\n{hint}\n\n"
                    f"Produce the detailed JSON spec. Be specific. Output JSON only:")
        # A refiner JSON parse failure silently drops the app into the generic-placeholder DEFAULT_MODELS
        # (the 'Entry'/'Item' bug). Retry once with a stricter reminder before giving up — the whole
        # downstream build hinges on this spec being domain-specific.
        for attempt in range(2):
            user_msg = base_msg if attempt == 0 else (
                base_msg + "\n\nYour previous reply was not valid JSON. Reply with a SINGLE raw JSON "
                "object ONLY — no markdown, no code fences, no commentary before or after — and give "
                "the app's REAL domain entities (never a generic Entry/Item/Record).")
            try:
                content = llm.chat(
                    [{"role": "user", "content": user_msg}],
                    # Indented JSON is very token-heavy; give ample headroom so the spec
                    # is never truncated. Very low temperature = consistent, valid JSON.
                    model=self.model, system=SYSTEM_PROMPT + QUALITY_PROMPT_APPEND,
                    num_predict=3072, timeout=200, extra_opts={"temperature": 0.05},
                    # think=False, explicitly: `llm.chat` defaults to THINK ("low"), and gemma4:12b
                    # then burns the whole budget thinking and returns an empty string. THAT is what
                    # "Architect JSON unparseable → using defaults" always was — not a prompt problem
                    # — and it is why a pharmacy app came out with a generic `Entry` collection. With
                    # thinking off the same prompt returns valid JSON naming Medicine/Supplier/Sale.
                    think=False,
                )
                if "```" in content:
                    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
                    content = m.group(1) if m else content
                parsed = _parse_json_lenient(content)
                if parsed:
                    log.info("   LLM type: %s | collections: %s", parsed.get("site_type"),
                             [m.get("name") for m in parsed.get("data_model", []) if isinstance(m, dict)])
                    return parsed
                log.warning("Architect JSON unparseable (attempt %d/2)", attempt + 1)
            except Exception as ex:
                log.warning("Architect LLM failed (%s) (attempt %d/2)", ex, attempt + 1)
        log.warning("Architect could not produce valid JSON — using defaults")
        return {}

    # ── Spec assembly + validation ──────────────────────────────────────────────
    def _build_spec(self, raw_idea: str, kw_type: str, data: dict) -> dict:
        llm_type = str(data.get("site_type", "")).lower().strip()
        high_conf = kw_type in ("app", "dashboard", "ecommerce")
        if llm_type in SECTION_MAP and not (high_conf and llm_type != kw_type):
            site_type = llm_type
        elif kw_type in SECTION_MAP:
            site_type = kw_type
        else:
            site_type = "general"

        brand = data.get("brand_name") or data.get("title") or self._extract_name(raw_idea)
        project_name = re.sub(r"[^a-z0-9]+", "-", brand.lower())[:30].strip("-") or "app"

        data_model = self._validate_data_model(data.get("data_model"), site_type)
        # Defensive: the User model is added deterministically by the auth scaffold —
        # never let the LLM's data_model include a User/Account/Auth collection.
        data_model = [m for m in data_model
                      if pascal(m.get("name", "")) not in ("User", "Account", "Auth", "Session")]
        if not data_model:
            data_model = [dict(m) for m in DEFAULT_MODELS.get(site_type, DEFAULT_MODELS["general"])]
        sections = self._validate_sections(data.get("sections"), site_type)

        features = data.get("key_features", [])
        features = [str(f) for f in features if f][:8] if isinstance(features, list) else []

        instructions = data.get("special_instructions", "") or data.get("description", "") or raw_idea
        if len(instructions.strip()) < 50:
            instructions = f"{raw_idea}\n\n{instructions}".strip()

        # ── Multi-page / auth / roles ─────────────────────────────────────────
        app_kind = self._detect_app_kind(raw_idea, data)
        roles: list = []
        pages: list = []
        auth = {"enabled": False, "roles": []}
        if app_kind == "multipage-app":
            roles = self._build_roles(data, site_type)
            for m in data_model:              # in a multi-role app, records belong to a user
                m["ownedBy"] = "User"
            pages = self._build_pages(roles, data_model)
            auth = {"enabled": True, "roles": [r["name"] for r in roles]}

        return {
            "project_name":         project_name,
            "site_type":            site_type,
            "app_kind":             app_kind,
            "strategy":             "fullstack-next",
            "title":                data.get("title", brand),
            "tagline":              data.get("tagline", f"Welcome to {brand}"),
            "description":          data.get("description") or raw_idea[:400],
            # No fixed fallback text: "deep navy…" matched the colour-keyword scan and painted EVERY
            # app that omitted a scheme the same navy/indigo. Empty text falls through to the
            # per-title hue in `scaffold._palette`, so apps stay visually distinct.
            "color_scheme":         data.get("color_scheme") or "",
            "theme":                self._theme(data),
            "style":                data.get("style", "modern"),
            "brand_name":           brand,
            "target_audience":      data.get("target_audience", "Everyone"),
            "key_features":         features,
            "data_model":           data_model,
            "sections":             sections,
            "auth":                 auth,
            "roles":                roles,
            "pages":                pages,
            "special_instructions": instructions,
            "_raw_idea":            raw_idea,
        }

    @staticmethod
    def _theme(data: dict) -> dict:
        """The model's two accent hexes, validated. `scaffold._palette` prefers these over everything
        else, so this is what actually colours the MUI theme; junk or missing values fall through to
        the colour-scheme keywords and then the per-title hue."""
        raw = data.get("theme")
        if not isinstance(raw, dict):
            return {}
        out = {}
        for key in ("accent", "accent2"):
            v = str(raw.get(key) or "").strip().lstrip("#")
            if re.fullmatch(r"[0-9a-fA-F]{6}", v):
                out[key] = "#" + v.lower()
        return out if out.get("accent") else {}

    # ── Multi-page / role derivation ────────────────────────────────────────────
    def _detect_app_kind(self, raw_idea: str, data: dict) -> str:
        il = raw_idea.lower()
        asked = _NEGATED_FEATURE.sub(" ", il)          # what the idea actually asks for
        denied = asked != il                            # it explicitly ruled something out
        wants_multipage = any(k in asked for k in MULTIPAGE_KEYWORDS)

        # An explicit denial with nothing positive left outranks the model's guess: it routinely
        # answers "multipage-app" for an idea whose every account word is a refusal.
        if denied and not wants_multipage:
            return "single-page"
        if str(data.get("app_kind", "")).replace("_", "-").strip() == "multipage-app":
            return "multipage-app"
        r = data.get("roles")
        if isinstance(r, list) and len([x for x in r if x]) >= 2:
            return "multipage-app"
        if wants_multipage:
            return "multipage-app"
        return "single-page"

    def _build_roles(self, data: dict, site_type: str) -> list:
        raw = data.get("roles")
        names = None
        if isinstance(raw, list):
            names = [re.sub(r"[^a-z0-9_]", "", str(n).lower()) for n in raw]
            names = [n for n in names if n]
        if not names:
            names = list(ROLE_PRESETS.get(site_type, ROLE_PRESETS["general"]))
        if "admin" not in names:
            names = ["admin"] + names
        seen, ordered = set(), []
        for n in names:
            if n not in seen:
                seen.add(n)
                ordered.append(n)
        ordered = ordered[:4]  # cap at 4 roles
        roles = []
        for i, n in enumerate(ordered):
            is_admin = n == "admin"
            roles.append({
                "name": n,
                "label": n.replace("_", " ").title(),
                "rank": 100 if is_admin else max(10, 90 - i * 10),
                "selfSignup": not is_admin,
                "home": "/admin" if is_admin else f"/{n}",
                "canCreate": (not is_admin) and (n not in CONSUMER_NAMES),
            })
        roles.sort(key=lambda r: r["rank"])
        return roles

    def _build_pages(self, roles: list, data_model: list) -> list:
        from agents.scaffold import route_name  # lazy import (avoids a cycle)
        def plural(nm: str) -> str:
            return route_name(nm).title()  # "Property" -> "Properties", "Category" -> "Categories"
        owned = list(data_model)
        pages = [{"path": "/", "title": "Home", "kind": "landing", "access": "public"}]
        for m in owned:
            nm = pascal(m.get("name", "Item"))
            seg = route_name(nm)
            pages.append({"path": f"/{seg}", "title": plural(nm), "kind": "list",
                          "access": "public", "resource": nm})
            pages.append({"path": f"/{seg}/[id]", "title": nm, "kind": "detail",
                          "access": "public", "resource": nm})
        pages.append({"path": "/login", "title": "Login", "kind": "auth", "access": "public"})
        pages.append({"path": "/signup", "title": "Sign up", "kind": "auth", "access": "public"})
        for r in roles:
            home, acc = r["home"], f"role:{r['name']}"
            pages.append({"path": home, "title": "Overview", "kind": "dashboard", "access": acc})
            if r["name"] == "admin":
                for m in owned:
                    nm = pascal(m.get("name", "Item"))
                    pages.append({"path": f"{home}/{route_name(nm)}", "title": f"Manage {plural(nm)}",
                                  "kind": "admin", "access": acc, "resource": nm})
                pages.append({"path": f"{home}/users", "title": "Manage Users",
                              "kind": "manage-users", "access": acc})
            elif r["canCreate"]:
                for m in owned:
                    nm = pascal(m.get("name", "Item"))
                    seg = route_name(nm)
                    pages.append({"path": f"{home}/{seg}", "title": f"My {plural(nm)}",
                                  "kind": "dashboard-list", "access": acc, "resource": nm})
                    pages.append({"path": f"{home}/{seg}/new", "title": f"New {nm}",
                                  "kind": "form", "access": acc, "resource": nm})
                    pages.append({"path": f"{home}/{seg}/[id]/edit", "title": f"Edit {nm}",
                                  "kind": "form", "access": acc, "resource": nm})
        return pages

    def _validate_data_model(self, raw, site_type: str) -> list:
        """Coerce the LLM's data_model into clean, safe collections. Fall back per type."""
        if not isinstance(raw, list):
            return [dict(m) for m in DEFAULT_MODELS.get(site_type, DEFAULT_MODELS["general"])]
        cleaned = []
        seen = set()
        for m in raw:
            if not isinstance(m, dict):
                continue
            name = pascal(m.get("name", ""))
            if not name or name in seen:
                continue
            fields = []
            for f in (m.get("fields") or []):
                if not isinstance(f, dict) or not f.get("name"):
                    continue
                fname = re.sub(r"[^A-Za-z0-9_]", "", str(f["name"]))
                if not fname:
                    continue
                ftype = str(f.get("type", "String")).strip()
                base = ftype[1:-1] if ftype.startswith("[") and ftype.endswith("]") else ftype
                if base not in VALID_TYPES and base.capitalize() not in VALID_TYPES:
                    ftype = "String"
                nf = {"name": fname, "type": ftype}
                for k in ("required", "unique", "default", "ref", "enum", "items"):
                    if k in f and f[k] is not None:
                        nf[k] = f[k]
                fields.append(nf)
            if not fields:
                fields = [{"name": "title", "type": "String", "required": True}]
            cleaned.append({"name": name, "fields": fields})
            seen.add(name)
            if len(cleaned) >= 3:
                break
        if not cleaned:
            return [dict(m) for m in DEFAULT_MODELS.get(site_type, DEFAULT_MODELS["general"])]
        return cleaned

    def _validate_sections(self, raw, site_type: str) -> list:
        default = SECTION_MAP.get(site_type, SECTION_MAP["general"])
        if not isinstance(raw, list):
            return default
        secs = []
        for s in raw:
            name = pascal(s) if isinstance(s, str) else ""
            if name and name not in secs and name != "Navbar":
                secs.append(name)
        if len(secs) < 4:
            return default
        if secs[0] != "Hero":
            secs = ["Hero"] + [s for s in secs if s != "Hero"]
        return secs[:10]

    def _extract_name(self, idea: str) -> str:
        stop = {"a", "an", "the", "build", "create", "make", "i", "want", "need", "please",
                "with", "for", "and", "or", "of", "website", "site", "page", "web", "app",
                "simple", "basic", "nice", "cool", "good", "great", "some", "just", "like"}
        words = [w.strip(".,!?\"'") for w in idea.split()
                 if w.lower().strip(".,!?\"'") not in stop]
        return " ".join(words[:3]).title() if words else "My App"
