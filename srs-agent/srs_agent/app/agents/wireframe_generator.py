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
import logging

from ..generators.page_context import page_context, product_context
from ..generators.wireframe_html import page_html
from ..generators.wireframes import KINDS, wireframes_for
from ..llm import get_llm

log = logging.getLogger("srs.wireframes")

# How many pages are drawn at once. Quality is the point here, so this is about
# not holding the model's whole queue rather than about finishing quickly.
LANES = 3

HTML_WIREFRAME_PROMPT = """You are drawing one screen of a classic Low-Fidelity / Mid-Fidelity wireframe
in Balsamiq / Figma blueprint style: outlined boxes, an X through every image,
realistic sample data, no colour.

The document, the browser chrome, the stylesheet and the legend are already
written and wrap what you return. Write ONLY the page's <section> elements, in
reading order. No <!DOCTYPE>, no <html>, <head>, <body> or <style>, no <script>,
and never an <svg> - there is no vector markup in this document at all.

Draw the page and nothing about the page. No annotation badges, no section
name tags, no grid or guide overlay, no "wireframe mode" bar: a reviewer opens
this to see the screen, not notes written over it.

THE DESIGN SYSTEM, already defined. Use these class names rather than restyling:
- .wf-box          a 2px black outlined white box. .wf-box-thin is the 1px one.
- .wf-fill         #F3F4F6 fill. .wf-fill-2 is #E5E7EB, for a heavier band.
- .wf-img          the image placeholder: a bordered box with a black X corner
                   to corner, drawn in CSS. Give it a size, e.g.
                   <div class="wf-img" style="height:320px"></div>, and put
                   <span class="wf-label">HERO IMAGE 16:9</span> inside it to
                   say what belongs there. Use it for every image, banner,
                   avatar, logo, thumbnail, map and chart.
- .wf-btn          a wireframe button. .wf-btn-fill is the one primary action,
                   .wf-btn-sm the small one.
- .wf-input        an outlined input. .wf-label-sm is the small caps label
                   above it.
- .sk              a grey bar standing in for a line of body copy; .sk-thin is
                   the secondary line. Set width inline: style="width:88%".
                   Use these for paragraphs - never Lorem Ipsum.
- .wf-tag          a small dashed badge for a status, a count or a pill on a
                   card - real content, never a label about the design.

Tailwind is loaded, so use its utilities for layout, spacing and type
(grid, flex, gap, px-8, py-12, text-2xl, font-bold). Never use a Tailwind colour
utility: the wireframe is black, white and grey by definition. Separate sections
with border-t-2 border-black.

SAMPLE DATA IS THE POINT. Every table gets real rows, every card a real title
and figure, every input a plausible typed value, every status one of the values
the specification listed for that column. A wireframe full of empty boxes tells
a reviewer nothing about whether the screen is right.

Draw the whole page - all of the sections listed for it, at the depth a real
screen has. Return the sections only, starting at <section."""

_SYS = (
    "Act as a Senior UI/UX Designer and Frontend Architect. You lay out application "
    "screens as classic Low-Fidelity / Mid-Fidelity Wireframes in Balsamiq / Figma "
    "wireframe blueprint style: outlined boxes, an X through every image placeholder, "
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
    "- image: an architectural wireframe box with an \"X\" through it. label like \"[ Image / Banner Placeholder ]\".\n"
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
    "STRICT WIREFRAME DESIGN SYSTEM & VISUAL RULES:\n"
    "1. PALETTE & FIDELITY: Strictly monochrome & grayscale (#FFFFFF background, "
    "#000000 borders and text, #F3F4F6 / #E5E7EB neutral fills). No brand colors or accent fills.\n"
    "2. SAMPLE DATA: Fill every extra with realistic data for this product - real "
    "names, dates, amounts, tables, stats, and statuses. Never Lorem Ipsum, never empty "
    "strings. Sample data is what makes a wireframe reviewable.\n"
    "3. TYPOGRAPHY & HIERARCHY: Clean, technical monospace / system font hierarchy, "
    "crisp borders for structural zones, wireframe pill / rounded buttons, outline inputs.\n"
    "4. NO COLOUR: The wireframe is black and white by definition, so never mention or set one."
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


def _ask_for(page: dict, doc: dict, product: str) -> str:
    """The whole product, then this page, then the instruction.

    The product half is identical for every page of a run, which is what makes
    it worth building once and passing in: the pages of one specification are
    then drawn against the same facts and come out looking like one product.
    """
    return (
        f"{product}\n\n===\n\n{page_context(page, doc)}\n\n"
        "Lay this page out in full. Draw every section listed above, in that "
        "order, and fill every table, card, field and figure with the sample "
        "data this product would really hold."
    )


# Draws in flight, so one version is never drawn twice at once, and the tasks
# themselves, because asyncio keeps only a weak reference to a bare task and
# will collect one mid-flight.
_IN_FLIGHT: dict[tuple[str, str], object] = {}


def draw_later(project_id: str, doc: dict) -> None:
    """Replace the projection with a drawn set, without making anyone wait.

    The projection is what a document has the instant it is saved, and it is
    honest but thin: it knows a page lists rooms, so it draws a table with grey
    bars in it. Nobody reviewing a wireframe learns anything from grey bars,
    and the drawn set - real room numbers, real prices, the status column's own
    declared values - was reachable only by pressing a button most people never
    pressed. So the good set is what a saved specification gets, and the
    projection is what it shows in the seconds before that arrives.

    Scheduled rather than awaited: drawing costs a model call per page, and no
    save should block on it. If the process stops first the projection stands
    and the button still works, which is the same floor as before.
    """
    key = (str(project_id), str((doc or {}).get("version") or ""))
    if not doc or key in _IN_FLIGHT:
        return

    async def work() -> None:
        try:
            from ..services import storage
            storage.save_drawn_wireframes(project_id, doc, await draft_wireframes(doc))
        except Exception:  # noqa: BLE001 - the projection is already saved
            pass
        finally:
            _IN_FLIGHT.pop(key, None)

    try:
        _IN_FLIGHT[key] = asyncio.get_running_loop().create_task(work())
    except RuntimeError:  # no loop running - nothing to schedule onto
        _IN_FLIGHT.pop(key, None)


async def draft_page(page: dict, doc: dict, product: str) -> dict | None:
    """One page's layout and height from the model, or None to keep the derived one.

    Tried twice. The usual failure is `LLMRepairFailed` with nothing partial to
    show, which is the model having answered in prose instead of JSON - and it
    is intermittent, because this deployment ignores `format` entirely (the
    same prompt returns prose with `format: "json"`, with a full schema, and
    with no format at all, on cloud models and on a local one). JSON therefore
    comes back because the system prompt asks for it, which is a thing that
    works most of the time rather than always. Measured here, roughly one page
    in three came back unusable and silently reverted to the projection - the
    thin grey-bar layout - with nothing logged to say why.

    A second attempt is the honest fix available on this endpoint: it costs one
    call on the pages that need it and nothing on the pages that do not.
    """
    check = _validator(page)
    name = page.get("page_name") or page.get("route") or "a page"
    trouble = None
    for attempt in (1, 2):
        try:
            body = await get_llm().complete_json(
                system=_SYS, user=_ask_for(page, doc, product),
                validator=check, label="srs_wireframe")
            # `complete_json` returns what the model sent and uses the validator
            # only to decide whether to accept it, so the cleaning the validator
            # does - ids, clamped boxes, capped lists - has to be taken from a
            # second call. Without it the raw blocks are stored, unnumbered and
            # unclamped, and the editor cannot address them.
            return check(body)
        except Exception as exc:  # noqa: BLE001 - the projection is the floor
            trouble = exc
            log.info("wireframe for %s failed on attempt %d: %s: %s",
                     name, attempt, type(exc).__name__, str(exc)[:200])
    log.warning("keeping the derived layout for %s - the drawing pass failed "
                "twice (%s: %s)", name, type(trouble).__name__, str(trouble)[:200])
    return None


async def draft_wireframes(doc: dict, *, on_page=None) -> list[dict]:
    """Every page, drawn for quality, falling back to the projection per page.

    The derived layout is the starting point and the floor: a page the model
    declines to draw, or draws badly enough to fail validation, still has one.
    """
    frames = wireframes_for(doc)
    product = product_context(doc)
    by_route = {p.get("route"): p for p in
                ((doc.get("public_pages") or []) + (doc.get("protected_pages") or []))
                if isinstance(p, dict)}
    lanes = asyncio.Semaphore(LANES)

    async def one(frame: dict) -> None:
        page = by_route.get(frame["route"]) or {}
        async with lanes:
            drawn = await draft_page({**page, **frame}, doc, product)
        if drawn and drawn.get("blocks"):
            frame["blocks"] = drawn["blocks"]
            frame["canvas"] = drawn.get("canvas") or 100
            frame["drawn"] = True
        if on_page:
            on_page(frame)

    await asyncio.gather(*(one(frame) for frame in frames))
    return frames


def _fenced(reply) -> str:
    """The HTML out of a reply that may or may not have fenced it."""
    content = str(reply or "").strip()
    if "```html" in content:
        content = content.split("```html", 1)[1].split("```", 1)[0]
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0]
    return content.strip()


# A model told not to emit a whole document will occasionally emit one anyway.
# Keeping only what is between the body tags costs nothing and saves the page.
def _sections_only(html: str) -> str:
    if "<body" in html.lower():
        after = html[html.lower().index("<body"):]
        html = after[after.index(">") + 1:]
    if "</body>" in html.lower():
        html = html[:html.lower().index("</body>")]
    return html.strip()


async def draft_html_wireframe(page: dict, doc: dict, product: str = "") -> str:
    """One page as a finished HTML wireframe: our shell around the model's sections.

    The shell is not negotiable and the model never sees a reason to reproduce
    it, which is what makes `<svg>` impossible here rather than merely
    forbidden: there is no <style> and no <head> for the model to write into,
    and the crossed image box already exists as a class it is told to use.
    """
    body = _sections_only(_fenced(await get_llm().complete(
        f"{HTML_WIREFRAME_PROMPT}\n\n===\n\n"
        f"{product or product_context(doc)}\n\n===\n\n{page_context(page, doc)}")))
    if not body:
        raise ValueError(f"no sections returned for {page.get('page_name') or page.get('route')}")
    app = str((doc.get("app_summary") or {}).get("app_name") or doc.get("project_name") or "app")
    host = "".join(ch for ch in app.lower() if ch.isalnum()) or "app"
    return page_html(str(page.get("page_name") or "Page"),
                     f"https://{host}.example.com{page.get('route') or '/'}", body)


async def draft_html_wireframes(doc: dict, *, on_page=None) -> dict[str, str]:
    """Every page as HTML, keyed by route. A page that fails is simply absent."""
    product = product_context(doc)
    pages = [p for p in ((doc.get("public_pages") or []) + (doc.get("protected_pages") or []))
             if isinstance(p, dict)]
    lanes = asyncio.Semaphore(LANES)
    out: dict[str, str] = {}

    async def one(page: dict) -> None:
        route = str(page.get("route") or "/")
        try:
            async with lanes:
                html = await draft_html_wireframe(page, doc, product)
        except Exception:  # noqa: BLE001 - one page failing is not the set failing
            return
        out[route] = html
        if on_page:
            on_page(route, html)

    await asyncio.gather(*(one(page) for page in pages))
    return out
