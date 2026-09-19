"""Which prototype file draws which route.

The two halves of a project name their pages differently and always have. The
specification says `/admin/bookings/:id`; the drawing calls that file
`admin-booking-detail.html`, because that is what a designer would call it.
Nothing wrote the correspondence down - the designer pass keeps a sitemap when
it runs the long way round, and an edit made through the studio does not - so
the wireframe for a route could not be told which page had just changed.

It is recovered here rather than demanded, from three things that are always
true of a real project: the route's own slug (`/admin/rooms` is very often
`admin-rooms.html`), the words in the file's name, and the page's `<title>`
against the name the specification gives it. A pairing that wins on none of
them is not guessed at; a page with no route simply has no wireframe, which is
the honest answer for a confirmation screen the specification never named.

Deterministic and cheap on purpose: this runs inside a change transaction, and
a model call to file some HTML would be a model call spent on filing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from server_modules.services.page_outline import title_of

# Words that appear in every name and so distinguish nothing.
NOISE = {"page", "screen", "view", "the", "a", "an", "of", "and", "my", "list", "html"}
EXACT_SLUG = 100.0
NAME_WEIGHT = 40.0
TITLE_WEIGHT = 40.0
ACCEPT = 45.0


def slug_for(route: str) -> str:
    """`/admin/rate-plans/:id` -> `admin-rate-plans-id.html`; `/` -> `index.html`."""
    parts = [p.strip("[]:") for p in str(route or "").strip("/").split("/") if p]
    stem = "-".join(re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-") for p in parts)
    return f"{stem or 'index'}.html"


def _tokens(text: str) -> set[str]:
    """The meaningful words in a name, singular, so `rooms` meets `room`."""
    words = set()
    for word in re.split(r"[^a-z0-9]+", str(text or "").lower()):
        if not word or word in NOISE:
            continue
        words.add(word[:-1] if len(word) > 3 and word.endswith("s") else word)
    return words


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _title_words(path: Path) -> set[str]:
    """The page's own title, minus the product name every title repeats."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return set()
    title = re.split(r"[—|·–-]", title_of(head), 1)[0]
    return _tokens(title)


def _from_sitemap(project_dir: Path) -> dict[str, str]:
    """The map the designer pass writes when it runs, if this project has one."""
    try:
        rows = json.loads((project_dir / ".agentforge" / "sitemap.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(row.get("file") or ""): str(row.get("route") or "")
            for row in (rows if isinstance(rows, list) else [])
            if isinstance(row, dict) and row.get("file") and row.get("route")}


def specified_pages(project_dir: Path | str) -> list[dict]:
    """Every page the adopted specification names, with the route it sits at."""
    try:
        saved = json.loads((Path(project_dir) / ".agentforge" / "wireframes" /
                            "wireframes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [page for page in (saved.get("pages") or [])
            if isinstance(page, dict) and page.get("route")]


def route_for_files(project_dir: Path | str, files) -> dict[str, str]:
    """Pair prototype files with routes. Returns filename -> route for `files`.

    Every prototype page is scored against every specified route and the
    strongest pairings are taken in turn, so `admin-rooms.html` claims
    `/admin/rooms` on its slug before `admin-room-edit.html` can claim it on a
    word they happen to share.

    Scored over the whole prototype rather than over the pages that changed,
    then narrowed. Otherwise the answer depends on what was asked about: a
    change to the confirmation screen alone, with `my-bookings.html` not in the
    question, let the confirmation screen take `/my-bookings` - and the
    wireframe for a page nobody had touched was redrawn from another page.
    """
    project_dir = Path(project_dir)
    wanted = {Path(str(name)).name for name in (files or [])
              if str(name).lower().endswith(".html")}
    pages = specified_pages(project_dir)
    if not wanted or not pages:
        return {}

    written = _from_sitemap(project_dir)
    routes = {str(page.get("route")): _tokens(page.get("page_name") or page.get("name") or "")
              for page in pages}
    folder = project_dir / ".agentforge" / "prototype"
    drawn = sorted(page.name for page in folder.glob("*.html")) if folder.is_dir() else []

    paired: dict[str, str] = {}
    scored: list[tuple[float, str, str]] = []
    for name in sorted(wanted | set(drawn)):
        if written.get(name) in routes:
            paired[name] = written[name]
            continue
        stem_words = _tokens(Path(name).stem)
        title_words = _title_words(folder / name)
        for route, name_words in routes.items():
            score = (EXACT_SLUG if slug_for(route) == name.lower() else 0.0)
            score += NAME_WEIGHT * _overlap(stem_words, _tokens(route))
            score += TITLE_WEIGHT * _overlap(title_words, name_words)
            if score >= ACCEPT:
                scored.append((score, name, route))

    taken = set(paired.values())
    for _score, name, route in sorted(scored, key=lambda row: (-row[0], row[1])):
        if name in paired or route in taken:
            continue
        paired[name] = route
        taken.add(route)
    return {name: route for name, route in paired.items() if name in wanted}
