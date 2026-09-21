"""Read every page, not only the ones a journey happened to open.

The usability check already existed and ran in exactly one place: the
`navigate` branch of a journey step. So a page reached by clicking was never
read, and a page no journey visits - a register form, an admin list, a
dashboard behind a role nobody automated - was never read at all. On a
thirteen-page specification that is most of the application.

This walks the pages the specification declares, opens each one against the
runtime that is already up, and runs the same two functions the journey uses,
so a finding here reads identically to a finding there. It asks no model,
asserts nothing and fails nothing: a sweep is a reading, and a reading that
could fail a build would be a reason not to take it.

A parameterised route is skipped rather than guessed at. `/rooms/[id]` with an
invented id is a 404 dressed up as a page, and "no h1 heading" about a 404 is
worse than no reading at all.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "builder-agent") not in sys.path:
    sys.path.insert(0, str(_ROOT / "builder-agent"))

from .journeys import capture_ui_quality, ui_quality_note  # noqa: E402

# Enough to cover an application, few enough that the sweep stays a footnote in
# the run rather than a stage of it.
MAX_PAGES = 30
OPEN_TIMEOUT = 20
# `/rooms/[id]`, `/rooms/:id`, `/rooms/{id}` - a route that needs a real record
# to mean anything.
PARAMETERISED = re.compile(r"\[|\]|:\w|\{")


def _spec(project_dir: Path) -> dict:
    for relative in (Path(".agentforge") / "srs" / "srs_latest.json",):
        try:
            body = json.loads((project_dir / relative).read_text(encoding="utf-8"))
            return body.get("srs_document") or body or {}
        except (OSError, ValueError):
            continue
    return {}


def routes_for(project_dir: Path | str) -> list[dict]:
    """Every page the specification names, or the sitemap if there is no spec."""
    project_dir = Path(project_dir)
    doc = _spec(project_dir)
    pages, seen = [], set()
    for page in ((doc.get("public_pages") or []) + (doc.get("protected_pages") or [])):
        if not isinstance(page, dict):
            continue
        route = str(page.get("route") or "").strip()
        if not route or route in seen or PARAMETERISED.search(route):
            continue
        seen.add(route)
        pages.append({"route": route,
                      "page": str(page.get("page_name") or route),
                      "login_required": bool(page.get("login_required")
                                              or page.get("allowed_roles"))})
    if pages:
        return pages[:MAX_PAGES]

    # A project built straight from a prompt has no specification, but the
    # builder wrote a sitemap for its own use.
    try:
        from builder_agent import sitemap
        for entry in sitemap.load(project_dir):
            route = str((entry or {}).get("route") or "").strip()
            if route and route not in seen and not PARAMETERISED.search(route):
                seen.add(route)
                pages.append({"route": route, "page": str(entry.get("title") or route),
                              "login_required": False})
    except Exception:  # noqa: BLE001 - no sitemap is a normal case
        pass
    return pages[:MAX_PAGES]


def sweep(browser, base_url: str, pages: list[dict], shots_dir: Path | str | None = None,
          events=None) -> list[dict]:
    """Open each page and read it. Returns one row per page, findings or not."""
    base = str(base_url or "").rstrip("/")
    if not base or not pages:
        return []
    rows = []
    try:
        page = browser.page()
    except Exception as error:  # noqa: BLE001 - no browser is not a failed build
        return [{"page": "", "route": "", "note": "",
                 "error": f"the browser was not available: {error}"}]

    for entry in pages:
        route = entry["route"] if entry["route"].startswith("/") else "/" + entry["route"]
        row = {"page": entry["page"], "route": route, "note": "", "shot": ""}
        try:
            page.navigate(base + route, timeout=OPEN_TIMEOUT)
            row["note"] = ui_quality_note(capture_ui_quality(page))
            if shots_dir:
                name = re.sub(r"[^a-z0-9]+", "-", f"page{route}".lower()).strip("-")
                target = Path(shots_dir) / f"{name or 'index'}.jpg"
                page.frame(target)
                row["shot"] = target.name
        except Exception as error:  # noqa: BLE001 - one bad page is one bad row
            row["error"] = str(error)[:300]
        rows.append(row)
        if events:
            events.emit("test", state="result", kind="ui", suite=route,
                        status="failed" if row.get("error") else "passed",
                        detail=row.get("error") or row["note"] or "read")
    return rows


def summarise(rows: list[dict]) -> str:
    """One line for the log, naming the pages with something to fix."""
    if not rows:
        return ""
    flagged = [r for r in rows if r.get("error") or (r["note"] and r["note"] != "clean")]
    if not flagged:
        return f"{len(rows)} page(s) read, all clean"
    named = ", ".join(r["route"] for r in flagged[:6])
    return (f"{len(rows)} page(s) read, {len(flagged)} with findings: {named}"
            + (" and more" if len(flagged) > 6 else ""))
