"""The page list and the journeys, projected from the specification.

Neither asks a model for anything: the pages are the ones the document already
names, and a journey is its own workflow with each step attached to the page it
happens on. Both regenerate in milliseconds on every save, so neither can fall
out of step with the document.

The drawing of a page is not here - that is one HTML document per page, made by
`agents/wireframe_generator`. This file decides only which pages exist and in
what order they are walked.
"""
from __future__ import annotations

import re

# The grid every block is placed on. Percentages of the frame, not pixels.
GRID = 100
GUTTER = 4
FULL = GRID - GUTTER * 2

def _words(*parts) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _mentions(text: str, *needles: str) -> bool:
    return any(re.search(rf"\b{n}", text) for n in needles)


def _label_of(column) -> str:
    """"scheduled_at" -> "Scheduled at". The customer's own word, tidied."""
    name = column.get("name") if isinstance(column, dict) else column
    words = re.sub(r"[_\-]+", " ", str(name or "")).strip()
    return (words[:1].upper() + words[1:]) if words else ""


def _verb_noun_pairs(doc: dict, tables: list[str]) -> list[tuple]:
    """Which word a product uses for acting on which of its stored things.

    Read from the specification's own workflows: a workflow called "Booking a
    Visit" whose steps mention appointments states that pairing, in that
    product's vocabulary. A list written here could only hold one product's.
    """
    stems = {re.sub(r"[^a-z]+", "", t.lower()).rstrip("s"): t for t in tables}
    # A word that names one of the stored things is a noun, whatever else is in
    # the workflow's title. Taking every word as a verb produced ("room",
    # "booking") from a workflow like "Room Booking", and `_entity_of` then read
    # the page literally called "Room List" as being about bookings - it drew a
    # New booking form and a Bookings table on the rooms page. The pairing is
    # only meaningful for a word that is not already the name of a table.
    nouns = {stem for stem in stems if stem}
    nouns |= {stem[:5] for stem in nouns}
    pairs = set()
    for flow in (doc.get("business_workflows") or []):
        if not isinstance(flow, dict):
            continue
        verbs = {w[:5] for w in re.findall(r"[a-z]{4,}", str(flow.get("workflow_name") or "").lower())}
        verbs -= nouns
        said = _words(*(flow.get("steps") or [])).replace(" ", "")
        for stem in stems:
            if stem and stem in said:
                pairs |= {(verb, stem) for verb in verbs}
    return sorted(pairs)


def wireframes_for(doc: dict) -> list[dict]:
    """Every page in the specification, as a placed block layout."""
    rows = [t for t in ((doc.get("database_design") or {}).get("tables") or [])
            if isinstance(t, dict)]
    tables = [str(t.get("table_name") or t.get("name") or "") for t in rows]
    tables = [t for t in tables if t]
    pairs = _verb_noun_pairs(doc, tables)
    out = []
    for page in (doc.get("public_pages") or []) + (doc.get("protected_pages") or []):
        if not isinstance(page, dict):
            continue
        route = str(page.get("route") or "").strip() or "/"
        out.append({
            "route": route,
            "page_name": str(page.get("page_name") or route),
            "page_type": str(page.get("page_type") or "page"),
            "login_required": bool(page.get("login_required")),
            "roles": [str(r) for r in (page.get("allowed_roles") or [])],
            "functions": [str(f) for f in (page.get("functions") or [])],
        })
    return out


# Words that appear in every other sentence and so identify no page at all.
_THIN = {"page", "list", "view", "system", "user", "data", "form", "table",
         "centre", "center", "manager", "management", "dashboard", "portal"}


def _route_for_step(step: str, pages: list[dict], actors: set[str]) -> str:
    """Which screen a workflow step happens on, or "" when none clearly does.

    Scored rather than matched whole: requiring every word of "Doctor's Day
    List" to appear left seven of nine steps pointing nowhere, and a journey
    whose steps lead to no screen is a paragraph, not a path.

    Role names are excluded, because every step names the person taking it:
    matching on them sent "Patient selects Doctor and time slot" to the Patient
    Portal instead of the Booking Page. Scoring is by matched length, so a page
    identified by one specific word beats one identified by a vague one, and a
    step that names no page keeps "" - the system validating something is not a
    screen, and inventing one for it would be worse than leaving it blank.
    """
    low = step.lower()
    best, best_score = "", 0
    for page in pages:
        words = {w for w in re.findall(r"[a-z]{4,}", page["page_name"].lower())}
        words |= {w for w in re.sub(r"[^a-z]+", " ", page["route"].lower()).split()
                  if len(w) > 3}
        words -= _THIN | actors
        # A stem opens the word in the step, so "booking" matches "book" and
        # "schedule" matches "scheduled".
        score = sum(len(w) for w in words if re.search(rf"\b{re.escape(w[:5])}", low))
        if score > best_score:
            best, best_score = page["route"], score
    return best if best_score else ""


def user_journeys_for(doc: dict) -> list[dict]:
    """The workflows as journeys, each step tied to the page it happens on.

    The steps are the specification's own; what is added is which screen each
    one lands on, so a journey reads as a path through the wireframes rather
    than as a paragraph beside them.
    """
    pages = [{"route": str(p.get("route") or ""), "page_name": str(p.get("page_name") or "")}
             for p in ((doc.get("public_pages") or []) + (doc.get("protected_pages") or []))
             if isinstance(p, dict)]
    actors = set()
    for role in (doc.get("roles") or []):
        if isinstance(role, dict):
            for value in (role.get("role_key"), role.get("role_name"), role.get("name")):
                actors |= {w for w in re.findall(r"[a-z]{4,}", str(value or "").lower())}
    out = []
    for flow in (doc.get("business_workflows") or []):
        if not isinstance(flow, dict):
            continue
        steps = [{"step": str(step), "route": _route_for_step(str(step), pages, actors),
                  "named": True} for step in (flow.get("steps") or [])]
        _carry_routes(steps)
        out.append({"workflow_name": str(flow.get("workflow_name") or "Workflow"),
                    "who": str(flow.get("who") or "") or None,
                    "steps": steps})
    return out


def _carry_routes(steps: list[dict]) -> None:
    """A step that names no screen happens on the one before it.

    Workflow steps are sequential and a person stays where they are until
    something moves them, so "System validates no double-booking" happens on the
    page the booking was made from. Carried rather than guessed, and marked
    `named: False` so the studio can show an inherited route as the weaker claim
    it is.
    """
    for i, step in enumerate(steps):
        if step["route"]:
            continue
        step["named"] = False
        backward = next((s["route"] for s in reversed(steps[:i]) if s["route"]), "")
        forward = next((s["route"] for s in steps[i + 1:] if s["route"]), "")
        step["route"] = backward or forward
