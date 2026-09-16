"""A live page for one design theme, drawn on request.

The registry themes ship with a screenshot, so the grid needs nothing from here.
The ones imported from a prompt file do not, and a screenshot is a picture of a
different product anyway - what a person choosing a theme wants to see is this
theme's own type, colour and spacing on a real page they can scroll and hover.

Rendering all seventy up front would be seventy model calls for sixty-nine pages
nobody opens, so a page is drawn the first time someone asks for that theme and
kept afterwards. scripts/draw_theme_previews.py draws the whole set.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "builder-agent"
if str(BUILDER) not in sys.path:
    sys.path.insert(0, str(BUILDER))

CACHE = ROOT / "design-previews"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
# No truncation. The window is a million tokens and the longest theme prompt is
# 25KB; cutting it removed the component and motion rules, which are most of
# what makes one theme look different from another.
MAX_PROMPT = 1_000_000
# Flash, not pro: drawing a page from a design system that is already written is
# transcription, and pro costs more for it. The ":cloud" suffix is not optional,
# and /api/tags does not prove a tag exists either way - only a request does.
# The configured model is a fallback for a host without this one.
PREVIEW_MODEL = "deepseek-v4-flash:cloud"

# Asking for "no frameworks, no external JavaScript" produced a thin page: these
# design systems are written in Tailwind classes, so denying Tailwind made the
# model translate every rule by hand and run out of room before the markup.
BRIEF = """html page create

Build one complete, self-contained landing page that shows this design system in
use: navigation, hero, stats, features, process, benefits, testimonials, pricing,
FAQ and footer.

- A single HTML file. Tailwind via CDN, Google Fonts and Lucide icons are all
  fine - use whatever the design system's own rules are written against.
- No photographs. Build imagery from CSS shapes, gradients or inline SVG.
- Follow every mandatory choice the design system names. If it says corners are
  sharp, no corner is rounded. If it names a font, load that font. If it lists
  sections that must be colour-blocked, colour-block them.
- Responsive from 400px up.

Return only the HTML, starting at <!DOCTYPE html>.
"""


class _Budget:
    """What Router.ask reads off a config.

    Thinking is off. Measured on deepseek-v4-flash, the same brief takes 25-27s
    without it and 123-133s with - five times the wait. Page size did not track
    the setting: a thinking-off page came out at 43KB and thinking-on pages at
    20KB and 23KB, so what varies is the design system's own length, not the
    reasoning. There is little here to reason about anyway - the design system
    is written out in full and the task is to render it.

    The truncation guard stays regardless, because a reply with no closing
    </html> must never reach the cache: on deepseek-v4-pro this brief once spent
    its whole budget reasoning, 125KB of it, and returned an empty page.
    """
    temperature = 0.4
    think = False
    max_response_tokens = 65_536
    context_tokens = 1_048_576
    response_timeout = 1_200
    stream_stall_timeout = 240


def _theme_root() -> Path:
    from builder_agent.design import THEME_ROOT
    return THEME_ROOT


def _slug_ok(slug: str) -> str:
    slug = str(slug or "").strip().lower()
    if not SLUG.match(slug):
        raise ValueError(f"Not a design theme: {slug!r}")
    return slug


def cached_path(slug: str) -> Path:
    return CACHE / f"{_slug_ok(slug)}.html"


def read_preview(slug: str) -> bytes:
    """The stored page, or FileNotFoundError when it has not been drawn yet."""
    return cached_path(slug).read_bytes()


def _extract_html(text: str) -> str:
    """The page out of a reply that may have arrived wrapped in a code fence."""
    body = str(text or "").strip()
    if not body:
        raise ValueError("The model returned nothing to draw. Try again.")
    fence = re.search(r"```(?:html)?\s*(.+?)```", body, re.S | re.I)
    if fence:
        body = fence.group(1).strip()
    start = body.lower().find("<!doctype")
    if start < 0:
        start = body.lower().find("<html")
    if start > 0:
        body = body[start:]
    low = body.lower()
    if "<html" not in low:
        raise ValueError("The model did not return an HTML page.")
    # A page that never closes is a page that was cut off, and an iframe shows
    # the half of it that arrived as though that were the design.
    if "</html>" not in low:
        raise ValueError("The model stopped before finishing the page. Try drawing it again.")
    return body


def render_preview(slug: str, model: str = "") -> Path:
    """Draw the page for one theme and keep it. Returns the file it wrote."""
    slug = _slug_ok(slug)
    prompt_file = _theme_root() / slug / "SKILL.md"
    if not prompt_file.is_file():
        raise FileNotFoundError(f"No design theme named {slug}.")

    from builder_agent.llm import Router, _default_client, load_settings

    chosen = str(model or "").strip() or PREVIEW_MODEL
    if not chosen:
        settings = load_settings() or {}
        chosen = str(settings.get("model") or settings.get("agent_model") or "").strip()
    if not chosen:
        raise ValueError("No model is configured to draw the preview.")

    system = prompt_file.read_text(encoding="utf-8", errors="replace")[:MAX_PROMPT]
    router = Router(_default_client(), chosen, config=_Budget())
    reply = router.ask([{"role": "system", "content": system},
                        {"role": "user", "content": BRIEF}],
                       stream=False, think=False, temperature=0.4, timeout=1_200)
    html = _extract_html(reply.content)

    CACHE.mkdir(parents=True, exist_ok=True)
    target = cached_path(slug)
    target.write_text(html, encoding="utf-8")
    return target


def themes() -> list[str]:
    """Every theme that has a prompt to draw from."""
    root = _theme_root()
    return sorted(d.name for d in root.iterdir() if d.is_dir() and (d / "SKILL.md").is_file())
