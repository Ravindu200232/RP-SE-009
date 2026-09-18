"""Black-and-white wireframes, projected from the specification.

A wireframe is not a drawing decision, so nothing here asks a model for one.
Every page the specification already describes - its type, the functions listed
on it, the roles allowed, the tables it touches - determines a block layout by
rule, which is why a full set regenerates in milliseconds rather than minutes
and why it is always in step with the document it came from.

Blocks live on a 0-100 grid rather than in pixels, so a wireframe renders at any
size and so moving one is arithmetic. That is what lets the studio's editor
change a layout with tools instead of a model.

No navigation is drawn. A wireframe answers "what is on this page", and a navbar
repeated on eleven pages answers it eleven times without adding anything.
"""
from __future__ import annotations

import re

# The grid every block is placed on. Percentages of the frame, not pixels.
GRID = 100
GUTTER = 4
FULL = GRID - GUTTER * 2

KINDS = ("heading", "title", "text", "field", "button", "table", "cards",
         "list", "image", "icon", "divider", "rating", "stat", "panel",
         "tabs", "chart", "nav", "footer")


def _words(*parts) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _mentions(text: str, *needles: str) -> bool:
    return any(re.search(rf"\b{n}", text) for n in needles)


def _block(kind: str, x: int, y: int, w: int, h: int, label: str = "", **extra) -> dict:
    block = {"kind": kind, "x": x, "y": y, "w": w, "h": h, "label": label}
    block.update({k: v for k, v in extra.items() if v not in (None, "", [])})
    return block


def _auth_page(page: dict) -> list[dict]:
    """A sign-in or sign-up page: one narrow panel, centred, nothing else."""
    name = str(page.get("page_name") or "Sign in")
    signup = "up" in name.lower() or "register" in str(page.get("route") or "")
    fields = ["Full name", "Email address", "Password", "Confirm password"] if signup \
        else ["Email address", "Password"]
    blocks = [_block("panel", 28, 14, 44, 72, name)]
    y = 22
    blocks.append(_block("title", 34, y, 32, 7, name))
    y += 11
    for label in fields:
        blocks.append(_block("field", 34, y, 32, 7, label))
        y += 10
    blocks.append(_block("button", 34, y, 32, 8, "Create account" if signup else "Sign in"))
    blocks.append(_block("text", 34, y + 11, 32, 5,
                         "Already have an account?" if signup else "Create an account"))
    return blocks


def _entity_of(page: dict, tables: list[str], pairs=()) -> str:
    """Which stored thing this page is mostly about, for honest column labels.

    The page's own name and route decide it, and only then what it says it does:
    the booking page's function mentions patients, and reading the functions
    first labelled it "New patient" - a wireframe stating the wrong thing about
    the page, which is worse than a vague one.
    """
    title = _words(page.get("page_name"), page.get("route")).replace(" ", "")
    body = _words(*(page.get("functions") or [])).replace(" ", "")
    # A page whose own title names a stored thing is about that thing, full
    # stop. The verb-noun pairing below is for the other kind of page - one
    # named for an action, like "/book" or "Billing" - and letting it speak
    # here let a generic verb win an argument it should never have been in:
    # "Room Management" contains "manag", the workflows pair "manag" with
    # bookings, and the rooms page was drawn as a bookings page. "Billing
    # Management" went to patients the same way.
    spoken = any((stem := re.sub(r"[^a-z]+", "", str(t).lower()).rstrip("s")) and stem in title
                 for t in tables)
    best, best_score = "", 0
    for table in tables:
        stem = re.sub(r"[^a-z]+", "", str(table).lower()).rstrip("s")
        if not stem:
            continue
        # A longer stem is a more specific match, so "appointments" beats
        # "patients" on a page whose route is /book and whose title is Booking.
        score = (3 * len(stem) if stem in title else len(stem) if stem in body else 0)
        # A page named for a verb ("/book", "Billing") is about the thing that
        # verb acts on, and the specification's own workflows are where that
        # pairing is stated - not in a list of nouns written here, which could
        # only ever hold the vocabulary of one product.
        if not spoken:
            for verb, noun in pairs:
                if verb in title and noun in stem:
                    score = max(score, 3 * len(stem) + 1)
        if score > best_score:
            best, best_score = str(table), score
    return best or (tables[0] if tables else "records")


def _page_blocks(page: dict, tables: list[str], rows: list = (), pairs=()) -> list[dict]:
    """One page's layout, decided by what the specification says it does."""
    if str(page.get("page_type") or "").strip().lower() == "auth":
        return _auth_page(page)

    functions = [str(f) for f in (page.get("functions") or [])]
    text = _words(page.get("page_name"), page.get("route"), *functions)
    entity = _entity_of(page, tables, pairs)

    # Verbs, and words any product uses about its own screens. Nothing here
    # names a thing one kind of product stores: "invoice" sat in the export
    # list, which is a billing product's noun deciding the layout of every
    # other product's pages.
    listing = _mentions(text, "list", "view", "see", "history", "table", "search",
                        "browse", "manage", "schedule", "day", "portal", "records")
    entry = _mentions(text, "book", "create", "add", "enter", "write", "submit",
                      "pick", "register", "note", "pay", "confirm")
    summary = _mentions(text, "dashboard", "summary", "overview", "kpi", "chart",
                        "trend", "report", "metric")
    export = _mentions(text, "download", "export", "csv", "pdf")

    blocks = [_block("title", GUTTER, 5, 52, 8, str(page.get("page_name") or "Page"))]
    if export:
        blocks.append(_block("button", 70, 5, 26, 8, "Download / export"))
    y = 17

    if summary:
        width = (FULL - 3 * 3) // 4
        for i, label in enumerate(("Total", "Today", "Pending", "Completed")):
            blocks.append(_block("stat", GUTTER + i * (width + 3), y, width, 14, label))
        y += 19

    if summary and not listing:
        blocks.append(_block("chart", GUTTER, y, FULL, 34, "Trend over time"))
        y += 38

    if entry and listing:
        # Both: the form is the sidebar and the list is the page.
        form_w = 34
        blocks.append(_block("panel", GUTTER, y, form_w, GRID - y - 6, "New " + entity.rstrip("s")))
        inner = y + 6
        for label in _fields_for(entity, rows)[:4]:
            blocks.append(_block("field", GUTTER + 3, inner, form_w - 6, 7, label))
            inner += 10
        blocks.append(_block("button", GUTTER + 3, inner, form_w - 6, 8, "Save"))
        blocks.append(_block("table", GUTTER + form_w + 4, y, FULL - form_w - 4,
                             GRID - y - 6, entity.title(), rows=6,
                             columns=_columns_for(entity, rows)))
    elif entry:
        blocks.append(_block("panel", 22, y, 56, GRID - y - 6, "New " + entity.rstrip("s")))
        inner = y + 6
        for label in _fields_for(entity, rows)[:5]:
            blocks.append(_block("field", 26, inner, 48, 7, label))
            inner += 10
        blocks.append(_block("button", 26, inner, 48, 8, "Save"))
    elif listing:
        blocks.append(_block("field", GUTTER, y, 40, 7, "Search"))
        blocks.append(_block("button", 70, y, 26, 7, "Filter"))
        y += 11
        blocks.append(_block("table", GUTTER, y, FULL, GRID - y - 6, entity.title(),
                             rows=7, columns=_columns_for(entity, rows)))
    else:
        blocks.append(_block("cards", GUTTER, y, FULL, 36, entity.title(), rows=2))
        y += 40
        blocks.append(_block("text", GUTTER, y, FULL, 10,
                             functions[0] if functions else "Page content"))
    return blocks


# Columns every stored thing tends to carry that say nothing about it on a
# form: an identifier, a timestamp, a soft-delete flag. Named by shape, not by
# any one product's vocabulary.
_PLUMBING = re.compile(r"^(id|_id|uuid|created_at|updated_at|deleted_at|"
                       r"created|updated|.*_id|.*_hash|password.*|.*_token|"
                       r"salt|is_deleted|version)$", re.I)


def _label_of(column) -> str:
    """"scheduled_at" -> "Scheduled at". The customer's own word, tidied."""
    name = column.get("name") if isinstance(column, dict) else column
    words = re.sub(r"[_\-]+", " ", str(name or "")).strip()
    return (words[:1].upper() + words[1:]) if words else ""


def _fields_for(entity: str, tables: list) -> list[str]:
    """Field labels read off the entity's own columns.

    Taken from the specification rather than guessed from a list of words. A
    hardcoded list can only know the vocabulary of whatever product it was
    written against, and it labelled every form in every product with that
    one's nouns.
    """
    stem = re.sub(r"[^a-z]+", "", str(entity).lower()).rstrip("s")
    for table in tables:
        if not isinstance(table, dict):
            continue
        name = re.sub(r"[^a-z]+", "", str(table.get("table_name")
                                          or table.get("name") or "").lower()).rstrip("s")
        if name != stem:
            continue
        # The schema calls them `fields`; `columns` is accepted too so a
        # differently shaped document still yields real labels.
        out = [_label_of(c) for c in (table.get("fields") or table.get("columns") or [])]
        out = [c for c in out if c and not _PLUMBING.match(c.replace(" ", "_"))]
        if out:
            return out
    return ["Name", "Details"]


def _columns_for(entity: str, tables: list) -> list[str]:
    fields = _fields_for(entity, tables)
    columns = [entity.rstrip("s").title()] + [f for f in fields if f.lower() != "name"][:3]
    return (columns + ["Status"])[:5] if "Status" not in columns else columns[:5]


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
            "blocks": [{**b, "id": f"b{i + 1}"} for i, b in
                       enumerate(_page_blocks(page, tables, rows, pairs))],
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
