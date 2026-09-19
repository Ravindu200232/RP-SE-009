"""The wireframe for one page, as a complete HTML document.

Drawn from the specification's own handoff documents - app.md, sitemap.md and
prototype.md, passed verbatim - so this module holds no rules about what a page
contains. The specification says it, in its own words, for whatever product it
happens to describe.

Per page rather than per document: a single call covering fourteen pages spends
its output budget on the first few and truncates the rest, and one page failing
should cost that page rather than the set.
"""
from __future__ import annotations

import asyncio
import logging

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

# Retain strong references to background drawing tasks to prevent premature garbage collection.
_IN_FLIGHT: dict[tuple[str, str], object] = {}


def drawing(project_id: str) -> bool:
    """Is a drawing running for this project right now?

    A page is a model call and there are as many as the specification has
    pages, so the gap between "the specification is ready" and "the pages are
    drawn" is real - tens of seconds, sometimes more. Without this the studio
    could not tell that gap from a project whose pages simply failed, and it
    showed "not drawn yet" on every card as though nothing were happening.
    """
    wanted = str(project_id)
    return any(project == wanted and not getattr(task, "done", bool)()
               for (project, _version), task in list(_IN_FLIGHT.items()))


def draw_later(project_id: str, doc: dict) -> None:
    """Draw the pages properly once a version is saved, without anyone waiting.

    What is drawn is the HTML page, because that is the wireframe. The blocks
    are a projection of the specification onto a 0-100 grid: instant, always
    available, and thin enough that every table is a grid of grey bars. They
    are the right thing to show in the seconds before the real drawing lands
    and the wrong thing to leave behind as the finished article.

    Scheduled rather than awaited: a page is a model call and no save should
    block on one. If the process stops first the projection stands and the
    page can be drawn from the editor, which is the same floor as before.
    """
    key = (str(project_id), str((doc or {}).get("version") or ""))
    if not doc or key in _IN_FLIGHT:
        return

    async def work() -> None:
        try:
            from ..services import storage
            version = str((doc or {}).get("version") or "")
            drawn = await draft_html_wireframes(doc, project_id=project_id)
            for route, html in drawn.items():
                storage.save_page_html(project_id, route, html, version)
            log.info("drew %d page(s) of %s in full", len(drawn), project_id)
        except Exception as exc:  # noqa: BLE001 - the projection is already saved
            log.warning("the full drawing failed for %s: %s", project_id, str(exc)[:200])
        finally:
            _IN_FLIGHT.pop(key, None)

    try:
        _IN_FLIGHT[key] = asyncio.get_running_loop().create_task(work())
    except RuntimeError:  # no loop running - nothing to schedule onto
        _IN_FLIGHT.pop(key, None)


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
