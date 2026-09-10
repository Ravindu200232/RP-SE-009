"""Measure a drawing, so the wording that produces it can be changed against numbers.

The drawing pass writes pages that are three kilobytes when they should be
fifteen. Every attempt to fix that so far has been: change the skill, run a
whole build, look at the result, guess again. A build is half an hour and only
one of the three attempts landed.

This runs the drawing pass *only* - no planning, no build, no studio - against
a fixed brief and a fixed plan, and prints what came back beside what a page of
that kind should be. A round is a couple of minutes, so a candidate wording can
be tried, measured, and kept or thrown away on evidence.

    python test/manual/measure_drawing.py                     # draw, then measure
    python test/manual/measure_drawing.py --brief shop
    python test/manual/measure_drawing.py --only <dir>        # measure what is there
    python test/manual/measure_drawing.py --only <dir> --json out.json

`--only` measures any directory of HTML without calling a model, which is how
the reference and the existing drawings were measured to set the targets below.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "builder-agent"))


# ---------------------------------------------------------------------------
# What a page is made of
# ---------------------------------------------------------------------------
SCRIPT_OR_STYLE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")
COMMENT = re.compile(r"<!--.*?-->", re.S)

SECTION = re.compile(r"<(?:section|article)\b", re.I)
LANDMARK = re.compile(r"<(?:header|footer|main|nav|aside)\b", re.I)
IMAGE = re.compile(r"<img\b|<Image\b|<picture\b|background-image\s*:\s*url\(", re.I)
LINK = re.compile(r"<a\b[^>]*\bhref=|<Link\b[^>]*\bhref=", re.I)
ROW = re.compile(r"<tr\b", re.I)
FIELD = re.compile(r"<(?:input|select|textarea)\b", re.I)
HEADING = re.compile(r"<h[1-6]\b", re.I)

HEADER = re.compile(r"<header\b.*?</header>", re.S | re.I)
FOOTER = re.compile(r"<footer\b.*?</footer>", re.S | re.I)

# A container with an id and nothing inside it is only a problem when the script
# is what fills it: with demo.js deleted that is a blank rectangle, and none of
# the links that should have been inside it exist. A `<div id="preloader">` is
# not that, and the reference has one on every page.
HOLLOW = re.compile(
    r"<(div|ul|ol|tbody|section|main|table)\b[^>]*\bid\s*=\s*[\"']([^\"']+)[\"'][^>]*>\s*</\1>",
    re.I)

# Anything that tells the reader they are looking at a toy. The drawing is the
# product as it will be; the only thing it cannot do is store data, and that is
# invisible.
DISCLAIMER = re.compile(
    r"\b(?:prototype|mock[- ]?up|mockup|wireframe|demo only|for demo|"
    r"coming soon|not implemented|sample data only|this is a demo|"
    r"no backend|not functional|for illustration)\b", re.I)

# Filler is a different fault from a disclaimer: it does not tell the reader the
# product is fake, it just says nothing. Reported separately.
FILLER = re.compile(r"\b(?:lorem ipsum|dolor sit amet|placeholder text|your text here)\b", re.I)


def measure(html: str) -> dict:
    """Count what is actually on the page, ignoring the script and the styles."""
    body = COMMENT.sub("", html)
    visible = SCRIPT_OR_STYLE.sub("", body)
    text = TAG.sub(" ", visible)
    words = [w for w in text.split() if any(c.isalnum() for c in w)]

    header = HEADER.search(body)
    footer = FOOTER.search(body)
    shell = sum(len(LINK.findall(m.group(0))) for m in (header, footer) if m)

    return {
        "bytes": len(html.encode("utf-8")),
        "sections": len(SECTION.findall(body)) + len(LANDMARK.findall(body)),
        "images": len(IMAGE.findall(body)),
        "links": len(LINK.findall(body)),
        "shell": shell,
        "words": len(words),
        "headings": len(HEADING.findall(body)),
        "rows": len(ROW.findall(body)),
        "fields": len(FIELD.findall(body)),
        "hollow_ids": [m.group(2) for m in HOLLOW.finditer(body)],
        "disclaimers": sorted({m.group(0).lower() for m in DISCLAIMER.finditer(text)}),
        "filler": sorted({m.group(0).lower() for m in FILLER.finditer(text)}),
    }


# ---------------------------------------------------------------------------
# What a page of each kind should be
# ---------------------------------------------------------------------------
# Measured off every page of Mentor-1.0.0, not off its best one. What that
# reference holds constant across all nine pages is the shell and the section
# count - every page has at least 6 sections and at least 39 links, of which
# ~37 come from the header nav and the footer sitemap. That is the density the
# drawing is missing: ours has 11 links on the whole page.
#
# What varies by page is the content: images, words and rows belong to what the
# page is for, so they are judged per kind and the floors are the reference's
# own minimums.
EVERY_PAGE = {"bytes": 9000, "sections": 6, "links": 35, "shell": 30}

TARGETS = {
    "landing": {**EVERY_PAGE, "bytes": 15000, "images": 8, "words": 400},
    "detail":  {**EVERY_PAGE, "bytes": 12000, "images": 4, "words": 300},
    "list":    {**EVERY_PAGE, "images": 6, "words": 200},
    "admin":   {**EVERY_PAGE, "words": 180, "rows": 8},
    "form":    {**EVERY_PAGE, "words": 150, "fields": 3},
}

# The name is the only thing available before the page is read, and it is
# enough: a file called login.html is a form whatever it contains.
KINDS = (
    ("form", ("login", "signin", "sign-in", "signup", "register", "contact",
              "checkout", "book", "new", "edit", "settings", "profile")),
    ("admin", ("admin", "dashboard", "console", "manage", "orders", "reports")),
    ("detail", ("-id", "[id]", "detail", "item", "product", "room", "post")),
    ("landing", ("index", "home", "landing", "about", "pricing")),
)


def kind_of(name: str) -> str:
    stem = Path(name).stem.lower()
    for kind, terms in KINDS:
        if any(term in stem for term in terms):
            return kind
    return "list"


def judge(name: str, got: dict) -> tuple[str, list[str]]:
    kind = kind_of(name)
    short = [f"{key} {got.get(key, 0)}/{want}"
             for key, want in TARGETS[kind].items() if got.get(key, 0) < want]
    return kind, short


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def report(directory: Path, label: str = "") -> dict:
    pages = sorted(directory.glob("*.html"))
    if not pages:
        print(f"No pages in {directory}")
        return {}

    script = directory / "demo.js"
    demo = script.read_text(encoding="utf-8", errors="replace") if script.is_file() else ""

    print(f"\n{label or directory}")
    print(f"{'page':<20}{'kind':<9}{'bytes':>7}{'sect':>6}{'img':>5}"
          f"{'link':>6}{'shell':>7}{'word':>6}{'row':>5}{'fld':>5}")
    print("-" * 78)

    results, met = {}, 0
    for page in pages:
        got = measure(page.read_text(encoding="utf-8", errors="replace"))
        kind, short = judge(page.name, got)
        # A hollow container only matters if the script is what fills it.
        got["hollow"] = [i for i in got.pop("hollow_ids") if _filled_by(demo, i)]
        results[page.name] = {**got, "kind": kind, "short": short}
        met += not short
        print(f"{page.name:<20}{kind:<9}{got['bytes']:>7}{got['sections']:>6}"
              f"{got['images']:>5}{got['links']:>6}{got['shell']:>7}{got['words']:>6}"
              f"{got['rows']:>5}{got['fields']:>5}"
              f"{'' if not short else '  <- ' + ', '.join(short)}")

    total = sum(r["bytes"] for r in results.values())
    shells = [r["shell"] for r in results.values()]
    print("-" * 78)
    print(f"{len(pages)} pages, {total:,} bytes total, "
          f"{total // max(len(pages), 1):,} average, "
          f"shell {min(shells)}-{max(shells)} links. "
          f"{met}/{len(pages)} pages meet their target.")

    for name, row in results.items():
        if row["hollow"]:
            print(f"  {name}: the script fills {', '.join(row['hollow'])} - "
                  f"with demo.js deleted that content is gone")
        if row["disclaimers"]:
            print(f"  {name} tells the reader it is not real: "
                  f"{', '.join(row['disclaimers'])}")
        if row["filler"]:
            print(f"  {name} has filler text: {', '.join(row['filler'])}")

    if demo:
        print(f"  demo.js {len(demo.encode('utf-8')):,} bytes; state "
              f"{'persists under ' + _storage_key(demo) if _storage_key(demo) else 'is NOT persisted'}")
    else:
        print("  no demo.js - nothing on these pages runs")

    return results


def _storage_key(demo: str) -> str:
    """The localStorage key the script uses, whether written inline or as a const.

    Worth naming: the first version of this looked only for a quoted literal
    inside setItem, reported "state is NOT persisted" for three runs that were
    all persisting correctly under `setItem(KEY, …)`, and nearly sent a real
    piece of guidance back to be rewritten for a fault that did not exist.
    """
    call = re.search(r"localStorage\.(?:get|set)Item\(\s*([A-Za-z_$][\w$]*|[\"'][^\"']+[\"'])", demo)
    if not call:
        return ""
    name = call.group(1)
    if name[0] in "\"'":
        return name.strip("\"'")
    declared = re.search(
        r"\b(?:const|let|var)\s+" + re.escape(name) + r"\s*=\s*[\"']([^\"']+)[\"']", demo)
    return declared.group(1) if declared else f"{name} (a constant)"


def report_app(root: Path) -> dict:
    """The same measurement, on a built Next.js application.

    The question is the same one - is this screen a page or a paragraph - and
    the answer has been the same in both places. What differs is where the
    shell lives: a drawing repeats the header and footer into every file, while
    a built app has them once, in the layout and its components, and every page
    inherits them. So the shell is measured once and shown against every page.
    """
    pages = sorted(p for p in root.glob("app/**/page.*")
                   if "node_modules" not in p.parts)
    if not pages:
        print(f"No app/**/page.* under {root}")
        return {}

    shell_files = [p for p in list(root.glob("app/layout.*")) +
                   list(root.glob("components/**/*.jsx")) +
                   list(root.glob("components/**/*.js"))
                   if "node_modules" not in p.parts
                   and re.search(r"layout|header|footer|nav|shell|sidebar", p.name, re.I)]
    shell = sum(len(LINK.findall(p.read_text(encoding="utf-8", errors="replace")))
                for p in shell_files)

    print(f"\n{root}")
    print(f"{'page':<34}{'kind':<9}{'bytes':>7}{'sect':>6}{'img':>5}"
          f"{'link':>6}{'word':>6}{'row':>5}{'fld':>5}")
    print("-" * 84)

    results, met = {}, 0
    for page in pages:
        rel = str(page.parent.relative_to(root / "app")).replace("\\", "/")
        route = "/" if rel == "." else "/" + rel
        got = measure(page.read_text(encoding="utf-8", errors="replace"))
        # A drawing repeats the shell into every file, so its links land in the
        # page's own count. A built app has the shell once, in the layout, so
        # the page file legitimately carries only its own links - judging it on
        # the drawing's total would count the same nav twice and fail a page
        # that is fine.
        got["shell"] = shell
        got["links"] += shell
        kind, short = judge("index" if route == "/" else route, got)
        got["links"] -= shell
        got.pop("hollow_ids", None)
        results[route] = {**got, "kind": kind, "short": short}
        met += not short
        print(f"{route[:33]:<34}{kind:<9}{got['bytes']:>7}{got['sections']:>6}"
              f"{got['images']:>5}{got['links']:>6}{got['words']:>6}"
              f"{got['rows']:>5}{got['fields']:>5}"
              f"{'' if not short else '  <- ' + ', '.join(short)}")

    total = sum(r["bytes"] for r in results.values())
    print("-" * 84)
    print(f"{len(pages)} pages, {total:,} bytes total, "
          f"{total // len(pages):,} average. {met}/{len(pages)} meet their target.")
    print(f"  shell: {shell} links across "
          f"{', '.join(p.name for p in shell_files) or 'nothing that looks like a shell'}")
    for route, row in results.items():
        if row["disclaimers"]:
            print(f"  {route} tells the reader it is not real: {', '.join(row['disclaimers'])}")
        if row["filler"]:
            print(f"  {route} has filler text: {', '.join(row['filler'])}")
    return results


def _filled_by(demo: str, element_id: str) -> bool:
    """Does the script put content into this element?"""
    if not demo:
        return False
    handle = re.search(
        r"(?:getElementById\(\s*[\"']" + re.escape(element_id) + r"[\"']|"
        r"querySelector\(\s*[\"']#" + re.escape(element_id) + r"[\"'])", demo)
    if not handle:
        return False
    # Crude but sufficient: the script mentions it, and it writes content
    # somewhere. A page that has the element only to read a value is fine.
    return bool(re.search(r"innerHTML|append(?:Child)?|insertAdjacentHTML|"
                          r"createElement|\.textContent\s*=", demo))


# ---------------------------------------------------------------------------
# Running one drawing
# ---------------------------------------------------------------------------
BRIEFS = {
    "hotel": (
        "A boutique hotel's website where guests browse rooms, check availability "
        "for their dates, book a room, and read about the dining, the spa and the "
        "weddings the hotel hosts. Staff sign in to a small admin area to see "
        "today's arrivals and mark a booking as checked in.",
        """## Screens
- `/` - Home: the hotel, its rooms, its dining and what makes it worth staying at.
- `/rooms` - Rooms: every room type with photographs, size, occupancy and price.
- `/rooms/[id]` - Room detail: one room in full, with the booking panel.
- `/dining` - Dining: the restaurants, the menus and the times.
- `/experiences` - Experiences: the spa, the excursions and what is included.
- `/gallery` - Gallery: photographs of the property.
- `/about` - About: the story of the hotel and how to find it.
- `/contact` - Contact: the enquiry form, the address and the map.
- `/admin` - Admin: today's arrivals and departures, and marking a guest in.
- `/login` - Sign in: staff sign in to reach the admin area.

## Requirements
1. A guest browses room types with photographs and prices.
2. A guest checks availability for a date range and books a room.
3. A guest reads about dining, the spa and weddings.
4. Staff sign in and see today's arrivals.
5. Staff mark a booking as checked in.
6. Every screen works on a phone.
""",
    ),
    "shop": (
        "An online shop for a small roastery: customers browse coffees, read about "
        "each one, add to a basket and check out. The owner signs in to see orders "
        "and mark one as shipped.",
        """## Screens
- `/` - Home: this month's coffees and what the roastery is.
- `/shop` - Shop: every coffee, filterable by roast and origin.
- `/shop/[id]` - Coffee detail: one coffee, its notes, its origin and the buy panel.
- `/basket` - Basket: what is in the basket and what it costs.
- `/checkout` - Checkout: delivery details and payment.
- `/about` - About: the roastery, the people and the sourcing.
- `/admin/orders` - Orders: every order, and marking one shipped.
- `/login` - Sign in: the owner signs in.

## Requirements
1. A customer browses coffees with photographs and prices.
2. A customer filters by roast and by origin.
3. A customer adds a coffee to the basket and the basket count updates.
4. A customer checks out with delivery details.
5. The owner signs in and marks an order shipped.
6. Every screen works on a phone.
""",
    ),
}


def draw(brief: str, model: str, keep: bool) -> Path:
    from builder_agent.agent import BuilderAgent
    from builder_agent.config import Config
    from builder_agent.events import Events

    task, plan = BRIEFS[brief]
    workspace = Path(tempfile.mkdtemp(prefix=f"drawing-{brief}-"))
    print(f"workspace {workspace}")

    events = Events()
    seen = {"round": 0}

    # A wildcard listener is called as fn(event, payload), and Events swallows
    # anything this raises - so it stays boring on purpose.
    def watch(name, payload):
        if name == "notice":
            print(f"  [{payload.get('level', 'info')}] {str(payload.get('message'))[:160]}")
        elif name == "phase":
            print(f"  [phase] {payload.get('title')} {payload.get('status')}")
        elif name == "prototype":
            seen["round"] = payload.get("round", 0)
            print(f"  [drawn] round {payload.get('round')}: "
                  f"{len(payload.get('pages') or [])} pages")
        elif name == "tool":
            call = payload.get("tool") or payload.get("name")
            if call in ("writeFile", "readSkill"):
                print(f"  [{call}] {payload.get('path') or payload.get('skill') or ''}")

    events.any(watch)

    # gates off: every approval resolves to its default at once, so the pass
    # runs start to finish with nobody answering.
    config = Config(workspace=workspace, model=model, extra={"gates": False})
    agent = BuilderAgent(config, events=events)
    print(f"model {agent.config.model}")

    agent.plan_text = plan
    agent.apply_design(task, plan=plan)
    if not agent.screens:
        raise SystemExit("The design pass named no screens; the plan's ## Screens "
                         "section did not parse.")
    print(f"screens {len(agent.screens)}: "
          f"{', '.join(s.get('route', '?') for s in agent.screens)}")

    agent.prototype(task, plan=plan)
    directory = workspace / ".agentforge" / "prototype"
    if keep:
        print(f"kept at {directory}")
    return directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", default="hotel", choices=sorted(BRIEFS))
    parser.add_argument("--model", default="", help="defaults to the saved agent model")
    parser.add_argument("--only", default="", metavar="DIR",
                        help="measure a directory of HTML and do not call a model")
    parser.add_argument("--app", default="", metavar="DIR",
                        help="measure a built Next.js application's pages instead")
    parser.add_argument("--json", default="", metavar="FILE",
                        help="also write the measurements as JSON")
    parser.add_argument("--keep", action="store_true", default=True)
    args = parser.parse_args()

    if args.app:
        root = Path(args.app)
        if not root.is_dir():
            raise SystemExit(f"Not a directory: {root}")
        results = report_app(root)
    elif args.only:
        directory = Path(args.only)
        if not directory.is_dir():
            raise SystemExit(f"Not a directory: {directory}")
        results = report(directory)
    else:
        model = args.model
        if not model:
            sys.path.insert(0, str(ROOT))
            from server_modules.core.bootstrap import default_agent_model
            model = default_agent_model()
        results = report(draw(args.brief, model, args.keep), label=f"drawing: {args.brief}")

    if args.json and results:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
