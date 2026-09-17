"""Wireframes drawn for quality, one page at a time.

The rule-based projection in `generators/wireframes` is instant and always
available, which makes it the right thing to show the moment a specification
exists. It is not, however, a good wireframe: it knows a page lists something
but not what a row of it looks like, so every table came out as grey bars.

This pass asks the model to lay each page out properly and to fill it with
plausible sample data - the names, dates and amounts this product would really
hold - because a wireframe with "Lorem" in every cell tells a reviewer nothing
about whether the screen is right.

Per page rather than per document: a single call covering eleven pages spends
its output budget on the first four and truncates the rest, and one page failing
should cost that page, not the set. The rule-based layout stands in wherever a
page cannot be drawn.
"""
from __future__ import annotations

import asyncio
import json

from ..generators.wireframes import KINDS, wireframes_for
from ..llm import get_llm

# How many pages are drawn at once. Quality is the point here, so this is about
# not holding the model's whole queue rather than about finishing quickly.
LANES = 3

_SYS = (
    "You lay out application screens as black-and-white wireframes, in the "
    "classic style: outlined boxes, an X through every image placeholder, "
    "circles for icons, section rules with the section's name on them.\n"
    "Return JSON {\"canvas\": <height>, \"blocks\": [...]} only.\n\n"
    "THE CANVAS. x, y, w, h are whole numbers on a grid 100 units wide. "
    "\"canvas\" is how many units tall the page is: 100 is one screenful, and a "
    "landing or marketing page that scrolls should be 200-320. Use the height "
    "the page actually needs. Blocks must stay inside it (x+w <= 100, "
    "y+h <= canvas), must not overlap, and must leave a 4-unit margin left and "
    "right. Stack sections down the page in reading order.\n\n"
    f"KINDS: {', '.join(KINDS)}.\n"
    "- heading: a large bold headline. label is the text.\n"
    "- title: a smaller bold page or section title.\n"
    "- text: body copy. \"lines\": [strings].\n"
    "- image: a picture placeholder, drawn as a crossed box.\n"
    "- icon: a labelled circle. Put several in a row.\n"
    "- divider: a rule across the page with its name in a box on it. Use one "
    "between sections of a long page.\n"
    "- cards: a row of cards. \"items\": [{\"title\", \"meta\"}].\n"
    "- rating: five stars.\n"
    "- nav: the top bar. \"value\" is the logo text, \"label\" the links, "
    "comma separated. Use one only at the very top of a public page.\n"
    "- footer: the bottom bar. \"value\" is the logo text.\n"
    "- table: \"columns\": [names] and \"sample\": [[row values]].\n"
    "- field: one input. \"value\" is what is typed in it.\n"
    "- stat: a figure with a label. \"value\" is the figure.\n"
    "- button, tabs, chart, list: as their names suggest.\n"
    "- panel: an outline around a group, and nothing more. It draws no contents "
    "of its own, so every field, button and line of text inside it must be its "
    "own block positioned within the panel's box. A sign-in panel with no field "
    "blocks inside it renders as an empty rectangle.\n\n"
    "SAMPLE DATA. Fill every extra with realistic data for this product - real "
    "names, dates, amounts and statuses. Never Lorem Ipsum, never empty "
    "strings. Sample data is what makes a wireframe reviewable.\n"
    "NO COLOUR. The wireframe is black and white by definition, so never "
    "mention or set one."
)


def _validator(page: dict):
    """Accept only a layout that fits the frame and says something."""
    name = str(page.get("page_name") or page.get("route") or "the page")

    def check(body: dict) -> dict:
        canvas = body.get("canvas")
        try:
            canvas = max(100, min(400, int(round(float(canvas)))))
        except (TypeError, ValueError):
            canvas = 100
        blocks = body.get("blocks")
        if not isinstance(blocks, list) or not 2 <= len(blocks) <= 40:
            raise ValueError(f"{name} needs between 2 and 40 blocks; got "
                             f"{len(blocks) if isinstance(blocks, list) else 'none'}.")
        out = []
        for i, raw in enumerate(blocks):
            if not isinstance(raw, dict):
                raise ValueError(f"block {i + 1} is not an object")
            kind = str(raw.get("kind") or "").strip().lower()
            if kind not in KINDS:
                raise ValueError(f"block {i + 1} has kind {kind!r}; use one of {', '.join(KINDS)}")
            box = {}
            for key in ("x", "y", "w", "h"):
                try:
                    box[key] = int(round(float(raw.get(key))))
                except (TypeError, ValueError):
                    raise ValueError(f"block {i + 1} is missing a numeric {key}") from None
            if box["w"] < 4 or box["h"] < 3:
                raise ValueError(f"block {i + 1} is too small to see ({box['w']}x{box['h']})")
            if (box["x"] < 0 or box["y"] < 0 or box["x"] + box["w"] > 100
                    or box["y"] + box["h"] > canvas):
                raise ValueError(f"block {i + 1} falls outside the {canvas}-unit page")
            block = {"id": f"b{i + 1}", "kind": kind,
                     "label": str(raw.get("label") or "")[:120], **box}
            for key in ("value", "rows"):
                if raw.get(key) not in (None, ""):
                    block[key] = raw[key]
            for key in ("columns", "sample", "items", "lines"):
                if isinstance(raw.get(key), list) and raw[key]:
                    block[key] = raw[key][:12]
            if kind == "table" and not block.get("sample"):
                raise ValueError(f"the {block['label'] or 'table'} needs \"sample\" rows; "
                                 "an empty table is not reviewable")
            out.append(block)
        return {"canvas": canvas, "blocks": out}

    return check


def _ask_for(page: dict, doc: dict, tables: list[dict]) -> str:
    named = ", ".join(str(t.get("table_name") or t.get("name") or "") for t in tables[:10])
    fields = []
    for table in tables[:6]:
        columns = [str(c.get("name") or c) for c in (table.get("columns") or [])][:8]
        if columns:
            fields.append(f"{table.get('table_name') or table.get('name')}: {', '.join(columns)}")
    return (
        f"PRODUCT: {str((doc.get('app_summary') or {}).get('app_name') or '')} — "
        f"{str((doc.get('app_summary') or {}).get('short_description') or '')[:400]}\n\n"
        f"PAGE: {page.get('page_name')} at {page.get('route')}\n"
        f"Seen by: {', '.join(page.get('allowed_roles') or []) or 'anyone, signed out'}\n"
        f"This page must let someone:\n"
        + "\n".join(f"- {f}" for f in (page.get("functions") or ["use the product"]))
        + (f"\n\nStored data available: {named}\n" if named else "\n")
        + ("\n".join(fields) + "\n" if fields else "")
        + "\nLay this page out. Put the sample data in that this product would really hold."
    )


async def draft_page(page: dict, doc: dict, tables: list[dict]) -> dict | None:
    """One page's layout and height from the model, or None to keep the derived one."""
    check = _validator(page)
    try:
        body = await get_llm().complete_json(
            system=_SYS, user=_ask_for(page, doc, tables),
            validator=check, label="srs_wireframe")
        # `complete_json` returns what the model sent and uses the validator
        # only to decide whether to accept it, so the cleaning the validator
        # does - ids, clamped boxes, capped lists - has to be taken from a
        # second call. Without it the raw blocks are stored, unnumbered and
        # unclamped, and the editor cannot address them.
        return check(body)
    except Exception:  # noqa: BLE001 - a page that cannot be drawn keeps its projection
        return None


async def draft_wireframes(doc: dict, *, on_page=None) -> list[dict]:
    """Every page, drawn for quality, falling back to the projection per page.

    The derived layout is the starting point and the floor: a page the model
    declines to draw, or draws badly enough to fail validation, still has one.
    """
    frames = wireframes_for(doc)
    tables = [t for t in ((doc.get("database_design") or {}).get("tables") or [])
              if isinstance(t, dict)]
    by_route = {p.get("route"): p for p in
                ((doc.get("public_pages") or []) + (doc.get("protected_pages") or []))
                if isinstance(p, dict)}
    lanes = asyncio.Semaphore(LANES)

    async def one(frame: dict) -> None:
        page = by_route.get(frame["route"]) or {}
        async with lanes:
            drawn = await draft_page({**page, **frame}, doc, tables)
        if drawn and drawn.get("blocks"):
            frame["blocks"] = drawn["blocks"]
            frame["canvas"] = drawn.get("canvas") or 100
            frame["drawn"] = True
        if on_page:
            on_page(frame)

    await asyncio.gather(*(one(frame) for frame in frames))
    return frames
