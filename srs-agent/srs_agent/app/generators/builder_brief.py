"""The handoff to the app builder.

The builder at `Ai-Website-Builder-main` does not read an SRS. Its whole input
contract is `POST /api/generate/<workspaceId>` with `{"prompt": "<string>"}`,
and that string goes to a model which turns it into
`{appType, requirements: [{id, text, kind, entity}]}` before anything is built.

So this module produces two things: that requirement list, pre-derived from the
approved plan so the builder's model has almost nothing to guess, and the prompt
string that carries it.

Three constraints come from the builder's own code, and all three are enforced
here rather than hoped for:

* Its blueprint reply is capped at 8192 output tokens and a truncated reply is a
  hard failure (`Blueprint was not valid JSON`), so the brief is capped.
* Its Ollama config never sets `num_ctx`, so anything past the default context
  is silently dropped from the *front* — the most important sentences go first.
* Its stack has a fixed package whitelist, and its own prompt says naming a
  library it does not have "produces a requirement that can never be satisfied".
  So we never name one.
"""
from __future__ import annotations

import re


KINDS = ("page", "create", "edit", "delete", "list", "feature")


ALLOWED_PACKAGES = (
    "react", "react-dom", "next", "mongoose", "lucide-react", "bcryptjs",
    "jose", "tailwind", "tailwindcss",
)


_FORBIDDEN = (
    "zod", "react-hook-form", "next-auth", "prisma", "postgres", "postgresql",
    "mysql", "sqlite", "redux", "zustand", "graphql", "trpc", "stripe",
    "firebase", "supabase", "express", "fastapi", "django", "material-ui",
    "mui", "chakra", "bootstrap", "styled-components", "axios", "sequelize",
    "typeorm", "socket.io", "auth0", "clerk",
)


MAX_WORDS = 1200
MAX_CHARS = 8000


def _strip_forbidden(text: str) -> str:
    """Drop a sentence that names a package the builder does not have."""
    keep = []
    for sentence in re.split(r"(?<=[.!?])\s+", str(text or "")):
        low = sentence.lower()
        if any(re.search(rf"\b{re.escape(p)}\b", low) for p in _FORBIDDEN):
            continue
        keep.append(sentence)
    return " ".join(keep).strip()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().rstrip(".")


def _entity(name: str) -> str:
    """`sale items` -> `SaleItem`. The builder names mongoose models this way."""
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", str(name or "")) if p]
    singular = []
    for p in parts:
        if p.lower().endswith("ies"):
            p = p[:-3] + "y"
        elif p.lower().endswith("es") and p.lower().endswith(("ches", "shes", "sses", "xes")):
            p = p[:-2]
        elif p.lower().endswith("s") and not p.lower().endswith("ss"):
            p = p[:-1]
        singular.append(p[:1].upper() + p[1:])
    return "".join(singular) or "Record"


_FIELD_TYPES = {
    "decimal": "Number", "integer": "Number", "boolean": "Boolean",
    "date": "Date", "datetime": "Date",
}


def build_handoff(*, plan: dict, srs_document: dict, pack: dict | None = None,
                  auth: bool = False) -> dict:
    """The plan in the builder's own vocabulary."""
    plan = plan or {}
    pack = pack or {}
    doc = srs_document or {}

    requirements: list[dict] = []
    seen: set[str] = set()

    def add(text: str, kind: str, entity: str | None) -> None:
        text = _clean(_strip_forbidden(text))
        if not text or text.lower() in seen or kind not in KINDS:
            return
        seen.add(text.lower())
        requirements.append({"id": f"R{len(requirements) + 1}", "text": text,
                             "kind": kind, "entity": entity})

    srs_pages = [p for p in ((doc.get("public_pages") or [])
                             + (doc.get("protected_pages") or []))
                 if isinstance(p, dict) and _clean(p.get("page_name", ""))]

    pages: list[dict] = []
    if srs_pages:
        for page in srs_pages:
            name = _clean(page.get("page_name", ""))
            route = _clean(page.get("route", "")) or (
                "/" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"))
            pages.append({"route": route, "name": name, "primary": True})
            fns = [_clean(f) for f in (page.get("functions") or []) if _clean(f)]
            purpose = fns[0] if fns else ""
            article = "An" if name[:1].upper() in "AEIOU" else "A"
            add(f"{article} {name} page: {purpose[:1].lower()}{purpose[1:]}"
                if purpose else f"{article} {name} page", "page", None)
    else:
        for i, screen in enumerate(plan.get("screens") or []):
            name = _clean(screen.get("name", ""))
            if not name:
                continue
            route = "/" if i == 0 else "/" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            pages.append({"route": route, "name": name, "primary": True})
            purpose = _clean(screen.get("purpose", ""))
            article = "An" if name[:1].upper() in "AEIOU" else "A"

            add(f"{article} {name} page: {purpose[:1].lower()}{purpose[1:]}" if purpose
                else f"{article} {name} page", "page", None)

    models: list[dict] = []
    archetype = str(pack.get("archetype") or "fullstack-crud")

    if auth:

        models.append({"name": "User",
                       "fields": {"name": "String", "email": "String",
                                  "password": "String", "role": "String"},
                       "readOnly": False})

    for table in (doc.get("database_design", {}) or {}).get("tables", []):
        tname = table.get("table_name", "")
        if tname in ("users", "roles"):
            continue
        entity = _entity(tname)
        fields = {}
        for f in table.get("fields", []):
            fname = f.get("name")
            if not fname or fname in ("id", "created_at"):
                continue
            fields[fname] = _FIELD_TYPES.get(str(f.get("type")), "String")
        models.append({"name": entity, "fields": fields, "readOnly": False})

        if archetype != "fullstack-crud":
            continue
        label = tname.replace("_", " ")
        singular = label[:-1] if label.endswith("s") else label
        add(f"Users can add a new {singular}", "create", entity)
        add(f"Users can see a list of {label}", "list", entity)
        add(f"Users can edit an existing {singular}", "edit", entity)
        add(f"Users can delete a {singular}", "delete", entity)

    for user in plan.get("users") or []:
        role = _clean(user.get("role", ""))
        for duty in user.get("can_do") or []:
            duty = _clean(duty)
            if duty and role:
                add(f"{role}s can {duty[:1].lower()}{duty[1:]}", "feature", None)

    for feature in plan.get("features") or []:
        add(_clean(feature), "feature", None)

    if auth:
        add("Users can register an account with an email address and password", "feature", "User")
        add("Users can sign in and sign out", "feature", "User")
        add("Signed-out visitors are redirected away from protected pages", "feature", None)

    handoff = {
        "appType": _clean(pack.get("app_label") or doc.get("system_category") or "Web application"),
        "requirements": requirements,
        "models": models,
        "pages": pages,
    }
    handoff["prompt"] = render_prompt(handoff, plan, auth=auth)
    return handoff


def render_prompt(handoff: dict, plan: dict, *, auth: bool = False) -> str:
    """The string to paste into the builder.

    Ordered by what matters most, because an over-long prompt loses its front
    to the context window, not its tail.
    """
    plan = plan or {}
    kind = handoff["appType"]
    article = "An" if kind[:1].upper() in "AEIOU" else "A"

    lines: list[str] = [
        f"{article} {kind} web application.",
        "",
        _clean(_strip_forbidden(plan.get("product_intent", ""))) + ".",
        "",
    ]

    if handoff["pages"]:
        lines.append("PAGES: " + ", ".join(p["name"] for p in handoff["pages"]) + ".")
    if handoff["models"]:
        model_bits = []
        for m in handoff["models"]:
            fields = ", ".join(list(m["fields"])[:8]) or "name"
            model_bits.append(f"{m['name']} ({fields})")
        lines.append("DATA: " + "; ".join(model_bits) + ".")
    if not auth:

        lines.append("There are no user accounts and no login. "
                     "Every page is public. Do not add authentication, "
                     "roles, permissions or an admin area.")
    lines.append("")

    lines.append("WHAT IT MUST DO:")
    for r in handoff["requirements"]:
        lines.append(f"{r['id']}. {r['text']}.")

    look = _clean(_strip_forbidden(plan.get("look_and_feel", "")))
    if look:
        lines += ["", f"LOOK AND FEEL: {look}."]

    text = "\n".join(lines).strip() + "\n"
    return _cap(text)


def _cap(text: str) -> str:
    """Trim from the end — the requirement list degrades better than the intro."""
    words = text.split()
    if len(words) > MAX_WORDS:
        text = " ".join(words[:MAX_WORDS])
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]

    if not text.endswith("\n"):
        cut = text.rfind("\n")
        if cut > MAX_CHARS // 2:
            text = text[:cut]
        text += "\n"
    return text


def attach_handoff(srs: dict, plan: dict, pack: dict | None = None,
                   auth: bool = False) -> dict:
    """Put the handoff onto the SRS document, in place."""
    doc = srs.get("srs_document") or {}
    doc["builder_handoff"] = build_handoff(plan=plan, srs_document=doc,
                                           pack=pack, auth=auth)
    return srs


__all__ = ["build_handoff", "render_prompt", "attach_handoff",
           "KINDS", "ALLOWED_PACKAGES", "MAX_WORDS", "MAX_CHARS"]
