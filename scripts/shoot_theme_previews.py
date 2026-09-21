"""Photograph each theme's own preview page for the picker grid.

The grid used to show a screenshot that shipped with the theme registry - a
picture of somebody else's product in that style. Clicking the card opened the
page we drew from the theme's design system, so the thumbnail and the preview
were two different pages and the grid was, at best, a hint.

This takes the picture from the page the popup actually shows, so the card and
the preview are the same thing. It also covers the themes the registry shipped
no screenshot for at all.

    python scripts/shoot_theme_previews.py              # shoot what is missing
    python scripts/shoot_theme_previews.py --redo       # shoot all of them again
    python scripts/shoot_theme_previews.py bauhaus      # just these
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "builder-agent"))

from server_modules.builder.theme_preview import CACHE, themes  # noqa: E402

GRID = ROOT / "studio" / "public" / "design-themes"
CATALOGUE = GRID / "themes.json"
WIDTH, HEIGHT = 1280, 800


def main() -> int:
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")] or themes()
    redo = "--redo" in sys.argv
    GRID.mkdir(parents=True, exist_ok=True)

    from qa_agent.browser import Browser
    from builder_agent.events import Events

    catalogue = json.loads(CATALOGUE.read_text(encoding="utf-8")) if CATALOGUE.is_file() else {}
    browser = Browser(events=Events())
    shot = skipped = missing = failed = 0
    started = time.time()
    try:
        page = browser.page()
        for index, slug in enumerate(wanted, 1):
            source = CACHE / f"{slug}.html"
            target = GRID / f"{slug}.png"
            if not source.is_file():
                missing += 1
                print(f"[{index:2}/{len(wanted)}] {slug:16} no drawn page - run draw_theme_previews.py")
                continue
            if target.is_file() and not redo:
                skipped += 1
                continue
            try:
                page.navigate(source.resolve().as_uri(), timeout=30)
                # The page is static; a beat lets webfonts and CSS settle so the
                # thumbnail shows the type the theme actually asked for.
                time.sleep(1.2)
                page.screenshot(target, width=WIDTH, height=HEIGHT)
                if slug in catalogue:
                    catalogue[slug]["hasPreview"] = True
                shot += 1
                print(f"[{index:2}/{len(wanted)}] {slug:16} {target.stat().st_size:8,} bytes")
            except Exception as error:  # noqa: BLE001 - one bad theme is not the run
                failed += 1
                print(f"[{index:2}/{len(wanted)}] {slug:16} failed: {error}")
    finally:
        browser.close()

    if catalogue:
        CATALOGUE.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nshot {shot}, kept {skipped}, not drawn {missing}, failed {failed} "
          f"in {time.time() - started:.0f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
