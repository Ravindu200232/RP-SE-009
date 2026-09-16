"""Draw the preview page for every design theme.

These pages are for looking at. They are what the grid and its popup show, and
nothing else ever reads them - a build is handed the theme's prompt file, not
this HTML. Deleting the whole design-previews folder costs a redraw and nothing
more.

    python scripts/draw_theme_previews.py              # draw what is missing
    python scripts/draw_theme_previews.py --redraw     # draw all of them again
    python scripts/draw_theme_previews.py bauhaus kinetic
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server_modules.builder.theme_preview import (  # noqa: E402
    CACHE, PREVIEW_MODEL, cached_path, render_preview, themes,
)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    redraw = "--redraw" in sys.argv
    wanted = args or themes()
    started = time.time()
    from server_modules.builder.theme_preview import _Budget
    print(f"model   {PREVIEW_MODEL}  (thinking {'on' if _Budget.think else 'off'})")
    print(f"cache   {CACHE}")
    print(f"themes  {len(wanted)}{'  (redrawing)' if redraw else '  (missing only)'}\n")

    drawn = failed = skipped = 0
    for index, slug in enumerate(wanted, 1):
        target = cached_path(slug)
        if target.is_file() and not redraw:
            skipped += 1
            print(f"[{index:2}/{len(wanted)}] {slug:16} kept     {target.stat().st_size:7,} bytes")
            continue
        for attempt in (1, 2):
            mark = time.time()
            try:
                path = render_preview(slug)
                drawn += 1
                print(f"[{index:2}/{len(wanted)}] {slug:16} drawn    {path.stat().st_size:7,} bytes"
                      f"  {time.time() - mark:5.0f}s")
                break
            except Exception as error:  # noqa: BLE001 - one theme must not end the run
                detail = f"{type(error).__name__}: {error}"
                if attempt == 1:
                    print(f"[{index:2}/{len(wanted)}] {slug:16} retry    {detail[:70]}")
                    continue
                failed += 1
                print(f"[{index:2}/{len(wanted)}] {slug:16} FAILED   {detail[:70]}")

    print(f"\ndrawn {drawn}   kept {skipped}   failed {failed}   "
          f"in {(time.time() - started) / 60:.1f} min")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
