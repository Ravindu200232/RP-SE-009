"""A drawing styles itself, and that is checked before anyone is shown it.

Drawings used to be styled by Tailwind's browser build: one script, no build
step, utilities in the markup. It compiles the page as it loads, and a class it
does not know inside the page's own CSS is not skipped - it throws, no
stylesheet is produced at all, and the reviewer is shown bare HTML. A hotel
drawing of seven pages went out that way over a single `hover:shadow-overlay`
in a `.card` rule, and the same fault has three other spellings: a colour taken
from a variable that cannot be faded (`ring-primary/20`), a theme name nobody
declared, and a build that "fixed" it by deleting the local copy of Tailwind
and sending every page to a CDN.

So the drawing writes its own CSS now (see the html-prototype skill). Plain CSS
cannot fail that way: a rule the browser does not understand is dropped and the
rest of the page keeps its styling. What is left to check is the other end -
that a stylesheet was actually written and that it reaches the pages - because
a drawing with no CSS at all is the one failure plain CSS still allows, and it
is worth one more round to fix before the user sees it.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

# A stylesheet with less in it than this was not written for a product.
MIN_STYLESHEET_BYTES = 800
# Rules the browser actually applied. A page with fewer is bare.
MIN_APPLIED_RULES = 20

STYLESHEET_LINK = re.compile(r"""<link[^>]+rel=["']stylesheet["'][^>]*>""", re.I)
PAGES = (".html",)

RULE_COUNT = """
(() => {
  let rules = 0;
  for (const sheet of document.styleSheets) {
    try { rules += sheet.cssRules.length; } catch (error) { /* not ours to read */ }
  }
  return rules;
})()
"""


def _prototype(root: Path) -> Path:
    folder = Path(root) / ".agentforge" / "prototype"
    return folder if folder.is_dir() else Path(root)


def _pages(root: Path) -> list:
    folder = _prototype(root)
    return sorted(path for path in folder.glob("*")
                  if path.is_file() and path.suffix.lower() in PAGES)


def unstyled(root: Path, look=None) -> list:
    """The pages that would be shown with no styling on them.

    Read off the files first, because that needs nothing running: a page with
    no stylesheet linked, or a `styles.css` that was never really written. Then
    asked of a browser, when one is available, because that is the only thing
    that knows whether the rules reached the page.
    """
    sheet = _prototype(root) / "styles.css"
    try:
        thin = not sheet.is_file() or sheet.stat().st_size < MIN_STYLESHEET_BYTES
    except OSError:
        thin = True
    bare = []
    for page in _pages(root):
        try:
            text = page.read_text("utf-8")
        except OSError:
            continue
        if thin or not STYLESHEET_LINK.search(text):
            bare.append(page.name)
            continue
        applied = look(page) if look else None
        if applied is not None and applied < MIN_APPLIED_RULES:
            bare.append(page.name)
    return bare


def browser_check(browser):
    """A way to ask a browser how much CSS a page ended up with, or nothing."""
    state: dict = {}

    def applied(path: Path):
        if state.get("off"):
            return None
        try:
            page = state.get("page") or browser.open_tab("about:blank")
            state["page"] = page
            page.navigate(Path(path).resolve().as_uri(), timeout=20)
            time.sleep(0.3)
            return int(page.evaluate(RULE_COUNT) or 0)
        except Exception:                                            # noqa: BLE001
            # No browser, no second opinion. The check off the files still ran.
            state["off"] = True
            return None

    return applied
