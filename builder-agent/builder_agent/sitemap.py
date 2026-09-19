"""The screens, and how they reach each other.

The plan names the screens in prose and the drawing turns them into files that
link to one another. Neither is a map: the plan does not say what links to what,
and the drawing says it only by being read, twelve files at a time. Between the
two passes that knowledge was being re-derived from scratch, and a screen the
plan named could go missing without anything noticing that it had.

So it is written down once, kept in the project, and handed to both passes.

It is never shown to the user. They approved a plan and they will look at a
drawing; a routing table between the two is bookkeeping, and asking them to
confirm it would be asking them to do the agent's filing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

RELATIVE_HREF = re.compile(r'href\s*=\s*"([^"#?:]+\.html)(?:[#?][^"]*)?"', re.I)
TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)

PATH = Path(".agentforge") / "sitemap.json"


def _file_for(route: str) -> str:
    """`/admin/orders` -> `admin-orders.html`; `/` -> `index.html`."""
    parts = [p.strip("[]:") for p in str(route or "").strip("/").split("/") if p]
    stem = "-".join(re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-") for p in parts)
    return f"{stem or 'index'}.html"


def from_screens(screens) -> list[dict]:
    """The map as the plan leaves it: every screen, no links yet."""
    entries, seen = [], set()
    for screen in screens or []:
        route = str(screen.get("route") or "")
        name = _file_for(route)
        if name in seen:
            continue
        seen.add(name)
        entries.append({"file": name, "route": route,
                        "label": str(screen.get("label") or "").strip(),
                        "what": str(screen.get("what") or "").strip(),
                        "drawn": False, "links": []})
    return entries


def from_drawing(directory, entries=None) -> list[dict]:
    """Fold what was actually drawn onto the map.

    A page the drawing added is added here; a page the plan named and the
    drawing has not written yet stays, marked undrawn, because that is exactly
    the thing worth knowing before the build starts.
    """
    root = Path(directory)
    merged = {entry["file"]: dict(entry) for entry in (entries or [])}
    if not root.is_dir():
        return list(merged.values())

    for page in sorted(root.glob("*.html")):
        html = page.read_text(encoding="utf-8", errors="replace")
        title = TITLE.search(html)
        entry = merged.setdefault(page.name, {
            "file": page.name, "route": "", "label": "", "what": "", "links": []})
        entry["drawn"] = True
        if not entry.get("label") and title:
            entry["label"] = re.sub(r"\s*[|\-–—]\s*.*$", "", title.group(1).strip())[:80]
        # Where this page can actually take somebody, deduplicated and in the
        # order the markup has them.
        seen, links = set(), []
        for href in RELATIVE_HREF.findall(html):
            target = href.rsplit("/", 1)[-1]
            if target != page.name and target not in seen:
                seen.add(target)
                links.append(target)
        entry["links"] = links
    return list(merged.values())


def unreachable(entries) -> list[str]:
    """Pages nothing links to. `index.html` is the way in, so never counted."""
    linked = {target for entry in entries for target in entry.get("links") or []}
    return sorted(entry["file"] for entry in entries
                  if entry["file"] != "index.html" and entry["file"] not in linked)


def dangling(entries) -> list[str]:
    """Addresses the pages link to that no page answers.

    The other half of a whole application, and the half nothing was reporting:
    a bakery linked four pages at `rooms.html` and never wrote it, so every one
    of those was a dead end the moment anybody clicked. Orphans are pages
    nobody can reach; these are journeys that stop.
    """
    have = {entry["file"] for entry in entries}
    missing = {target for entry in entries for target in entry.get("links") or []
               if target not in have}
    return sorted(missing)


def render(entries, *, drawn: bool = False) -> str:
    """The map as a prompt block, or "" when there is nothing worth saying."""
    if not entries:
        return ""
    lines = ["THE SITE MAP - every screen this product has, and what reaches what:"]
    for entry in sorted(entries, key=lambda e: (e["file"] != "index.html", e["file"])):
        bits = [f"- {entry['file']}"]
        if entry.get("route"):
            bits.append(f"({entry['route']})")
        if entry.get("label"):
            bits.append(f"— {entry['label']}")
        if entry.get("what"):
            bits.append(f": {entry['what'][:120]}")
        if drawn and entry.get("links"):
            bits.append(f"  -> {', '.join(entry['links'][:12])}")
        if drawn and not entry.get("drawn"):
            bits.append("  [NOT DRAWN YET]")
        lines.append(" ".join(bits))

    orphans = unreachable(entries)
    if orphans:
        lines.append(f"Nothing links to: {', '.join(orphans)}. Every screen has to be "
                     "reachable from the navigation, so put them in it.")
    dead = dangling(entries)
    if dead:
        lines.append(f"Linked but missing: {', '.join(dead)}. Every one of those is a "
                     "dead end the moment somebody clicks it - write the page, or stop "
                     "linking to it.")
    if not orphans and not dead:
        lines.append("Every screen is reachable and every link lands. Keep it that way.")
    return "\n".join(lines)


def save(workspace, entries) -> Path:
    path = Path(workspace) / PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=1), encoding="utf-8")
    return path


def load(workspace) -> list[dict]:
    path = Path(workspace) / PATH
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, list) else []
    except (OSError, ValueError):
        return []
