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

HTML_WIREFRAME_PROMPT = """Act as a Senior UI/UX Designer and Frontend Architect.
Generate a complete, self-contained, single-file HTML & Tailwind CSS layout representing a classic Low-Fidelity / Mid-Fidelity Wireframe (Balsamiq / Figma wireframe blueprint style) for:

STRICT WIREFRAME DESIGN SYSTEM & VISUAL RULES:
1. Palette: Strictly monochrome & grayscale (#FFFFFF background, #000000 borders and text, #F3F4F6 / #E5E7EB neutral fills). No brand colors, gradients, or accent fills.
2. Image Placeholders: Every single image, banner, avatar, or media container MUST use the authentic architectural wireframe box with an "X" (diagonal crossed lines from corner to corner). Use SVG crossed lines with vector-effect="non-scaling-stroke" and a centered label like "[ Image / Banner Placeholder ]".
3. Browser Chrome Wrapper: Wrap the entire wireframe inside a realistic browser window mockup (include window traffic light dots [o][o][o], URL address bar, and back/forward navigation arrows).
4. Typography & Styling:
- Clean, technical wireframe font (use Monospace or system-ui / Comic Neue / Balsamiq-like sketch style).
- Sharp corners or subtle 2px border radius, 1px or 2px solid black borders (`border-2 border-black` or `border border-zinc-900`).
- Buttons should look like wireframe button elements (pill/rectangle with 1.5px black borders, no drop shadows or color fills).
- Form inputs, dropdowns, and search bars should have clear wireframe outlines and simple placeholder text.
5. Interactive UX Features:
- Include a top floating utility bar with:
* Toggle "Grid / Blueprint Guides" (reveals a light gray 12-column alignment grid overlay).
* Toggle "UX Annotations / Labels" (shows/hides badges like [NAVBAR], [HERO], [CTA], [CARD-GRID], etc.).
6. Structure & Content:
- Provide complete, realistic structural layout with header, navigation, content blocks, cards, sidebar/filters (if applicable), and multi-column wireframe footer.
- Do NOT use external images (Unsplash/Lorem Picsum). Everything must be drawn using wireframe placeholders and SVG crossed boxes.

Ensure the output is production-ready HTML with CDN Tailwind CSS script included in the <head>.
"""

_SYS = (
    "Act as a Senior UI/UX Designer and Frontend Architect. You lay out application "
    "screens as classic Low-Fidelity / Mid-Fidelity Wireframes in Balsamiq / Figma "
    "wireframe blueprint style: outlined boxes, an X through every image placeholder, "
    "circles for icons, section rules with the section's name on them.\n"
    "Return JSON {\"canvas\": <height>, \"blocks\": [...]} only.\n\n"
    "EVERY BLOCK HAS THIS SHAPE. The key naming the kind is \"kind\" - not "
    "\"type\", not \"component\":\n"
    "  {\"kind\": \"table\", \"label\": \"Reservations\", \"x\": 4, \"y\": 40, "
    "\"w\": 92, \"h\": 30,\n"
    "   \"columns\": [\"Tool\", \"Member\", \"Status\"],\n"
    "   \"sample\": [[\"Cordless Drill\", \"A. Rivera\", \"Confirmed\"]]}\n\n"
    "THE CANVAS. x, y, w, h are whole numbers on a grid 100 units wide. "
    "\"canvas\" is how many units tall the page is: 100 is one screenful, and a "
    "landing or marketing page that scrolls should be 200-320. Use the height "
    "the page actually needs. Blocks must stay inside it (x+w <= 100, "
    "y+h <= canvas), must not overlap, and must leave a 4-unit margin left and "
    "right. Stack sections down the page in reading order.\n\n"
    f"KINDS: {', '.join(KINDS)}.\n"
    "- heading: a large bold headline. label is the text.\n"
    "- title: a smaller bold page or section title.\n"
    "- text: body copy. \"lines\" is required and holds 2-4 written-out "
    "sentences - the paragraph this page would really carry, about this "
    "product. Placeholder prose is the point: a reviewer needs to see how much "
    "copy fits and what it says. Never an empty list, and give the block enough "
    "height for the lines you wrote (roughly 4 units per line).\n"
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
    "names, dates, amounts, tables, stats, and statuses. Never empty strings. "
    "Sample data is what makes a wireframe reviewable.\n"
    "3. WRITE THE WORDS OUT. Placeholder copy stands in for the real thing, the "
    "way Lorem Ipsum does, but written about this product so it reads as the "
    "page it will become: every text block carries whole sentences, every "
    "heading its actual headline, every button its actual verb, every field a "
    "plausible typed value, every card a title and a line under it. Nothing is "
    "left as a grey bar for someone to imagine.\n"
    "4. DEPTH. Draw the page a real product would ship, not a sketch of one. "
    "Every section the page is said to have, and inside each one the parts it "
    "needs: a list has its search, its filters, its column headers, its rows, "
    "its pagination and its empty-state note; a form has its label, its input "
    "and its helper text per field, and its submit and cancel; a detail page "
    "has its heading, its image, its facts, its description and its actions. "
    "20-35 blocks is the usual shape of a page drawn this way - use as many as "
    "the page needs, and prefer more detail over less.\n"
    "5. TYPOGRAPHY & HIERARCHY: Clean, technical monospace / system font hierarchy, "
    "crisp borders for structural zones, wireframe pill / rounded buttons, outline inputs.\n"
    "6. NO COLOUR: The wireframe is black and white by definition, so never mention or set one."
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
        if not isinstance(blocks, list) or not 2 <= len(blocks) <= 60:
            raise ValueError(f"{name} needs between 2 and 60 blocks; got "
                             f"{len(blocks) if isinstance(blocks, list) else 'none'}.")
        out = []
        for i, raw in enumerate(blocks):
            if not isinstance(raw, dict):
                raise ValueError(f"block {i + 1} is not an object")
            # "type" is what the model reaches for when the prompt grows and
            # the one example drifts out of its attention - measured at every
            # page of a fourteen-page document failing on it, twice each, for a
            # key name. The word it chose is not ambiguous; refusing it only
            # loses the page. The prompt states "kind" plainly; this accepts
            # the near miss rather than spending two model calls rejecting it.
            kind = str(raw.get("kind") or raw.get("type") or "").strip().lower()
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
            # A text block with no lines renders as three grey bars, which is
            # the thing a reviewer learns nothing from. Asking for the words in
            # the prompt was not enough on its own - the model dropped them on
            # the pages it was least sure about, which are the pages that most
            # needed them - so the same rule that guards an empty table guards
            # an empty paragraph.
            if kind == "text" and not block.get("lines"):
                raise ValueError(
                    f"the text block {block['label'] or ''!r} at y={box['y']} has no "
                    "\"lines\"; write the 2-4 sentences this paragraph would really "
                    "carry, about this product")
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


def handoff_context(project_id: str) -> str:
    """The documents the prototype is built from, verbatim.

    `app.md`, `sitemap.md` and `prototype.md` are what the specification already
    wrote for the agents that draw and build this product: what it is, which
    pages exist and what belongs on each. Passing them as they are means the
    wireframe reads the same source the prototype does, and means this module
    holds no rules about what a page contains - the specification says it, in
    its own words, for whatever product this happens to be.

    `builder.md` is deliberately left out: it is the implementation contract,
    ten times the size of the rest, and none of it changes how a page looks.
    """
    from ..services.storage import project_dir
    folder = project_dir(project_id) / "handoff"
    parts = []
    for name in ("app.md", "sitemap.md", "prototype.md"):
        try:
            text = (folder / name).read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            parts.append(f"===== {name} =====\n{text}")
    return "\n\n".join(parts)


async def draft_html_wireframe(page: dict, doc: dict, context: str = "") -> str:
    """One page as a complete, self-contained HTML wireframe document."""
    name = str(page.get("page_name") or page.get("route") or "the page")
    html = _fenced(await get_llm().complete_text(
        system="You return one complete HTML document and nothing else.",
        user=(f"{HTML_WIREFRAME_PROMPT}\n\n"
              f"THE PAGE TO DRAW: {name} at {page.get('route') or '/'}\n\n"
              "Draw this one page of the product described below. Everything you "
              "need is in these documents; follow them and invent nothing they "
              "do not say.\n\n"
              f"{context}"),
        label="srs_wireframe_html"))
    if "<" not in html:
        raise ValueError(f"no HTML returned for {name}")
    return html


async def draft_html_wireframes(doc: dict, *, project_id: str = "",
                                on_page=None) -> dict[str, str]:
    """Every page as HTML, keyed by route. A page that fails is simply absent."""
    context = handoff_context(project_id) if project_id else ""
    pages = [p for p in ((doc.get("public_pages") or []) + (doc.get("protected_pages") or []))
             if isinstance(p, dict)]
    lanes = asyncio.Semaphore(LANES)
    out: dict[str, str] = {}

    async def one(page: dict) -> None:
        route = str(page.get("route") or "/")
        try:
            async with lanes:
                html = await draft_html_wireframe(page, doc, context)
        except Exception as exc:  # noqa: BLE001 - one page is not the set
            log.warning("no HTML wireframe for %s: %s", route, str(exc)[:200])
            return
        out[route] = html
        if on_page:
            on_page(route, html)

    await asyncio.gather(*(one(page) for page in pages))
    return out
