"""The design system a build commits to before it writes a component.

The engine used to stop and ask: a form of palettes, fonts and spacing, waiting
on a human. In a studio build nobody is sitting on that form, so it is now
decided automatically from the request itself and written straight to disk.

It is written as a project skill rather than injected into every prompt for the
same reason every other skill is: it is read once, on demand, it stays visible
in the workspace, it survives the run, and the user can edit it by hand.

Automatic does not mean identical. A hospital app and a street-food marketplace
must not come out the same colour, so the domain in the request picks the
palette, the type and the tone. "Do not reuse one hard-coded theme" is a rule
the engine has to keep, not just tell the model to keep.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


SKILL_NAME = "design-system"

NEUTRALS = {
    "slate": {"name": "Slate",
              "light": {"background": "#F8FAFC", "surface": "#FFFFFF", "surfaceAlt": "#F1F5F9",
                        "border": "#E2E8F0", "text": "#0F172A", "textMuted": "#64748B"},
              "dark": {"background": "#020617", "surface": "#0F172A", "surfaceAlt": "#1E293B",
                       "border": "#334155", "text": "#F8FAFC", "textMuted": "#94A3B8"}},
    "zinc": {"name": "Zinc",
             "light": {"background": "#FAFAFA", "surface": "#FFFFFF", "surfaceAlt": "#F4F4F5",
                       "border": "#E4E4E7", "text": "#09090B", "textMuted": "#71717A"},
             "dark": {"background": "#09090B", "surface": "#18181B", "surfaceAlt": "#27272A",
                      "border": "#3F3F46", "text": "#FAFAFA", "textMuted": "#A1A1AA"}},
    "stone": {"name": "Stone (warm)",
              "light": {"background": "#FAFAF9", "surface": "#FFFFFF", "surfaceAlt": "#F5F5F4",
                        "border": "#E7E5E4", "text": "#1C1917", "textMuted": "#78716C"},
              "dark": {"background": "#0C0A09", "surface": "#1C1917", "surfaceAlt": "#292524",
                       "border": "#44403C", "text": "#FAFAF9", "textMuted": "#A8A29E"}},
    "sand": {"name": "Sand (cream)",
             "light": {"background": "#FBF7F0", "surface": "#FFFDF9", "surfaceAlt": "#F3EDE2",
                       "border": "#E5DCCB", "text": "#211B14", "textMuted": "#7A6A56"},
             "dark": {"background": "#14100B", "surface": "#1F1913", "surfaceAlt": "#2C241B",
                      "border": "#463A2C", "text": "#FBF7F0", "textMuted": "#B9A88E"}},
    "navy": {"name": "Navy (cool deep)",
             "light": {"background": "#F5F8FC", "surface": "#FFFFFF", "surfaceAlt": "#EAF0F8",
                       "border": "#D5DFEC", "text": "#0A1428", "textMuted": "#5D7291"},
             "dark": {"background": "#060D1B", "surface": "#0D1728", "surfaceAlt": "#152238",
                      "border": "#22334F", "text": "#F5F8FC", "textMuted": "#8AA0BE"}},
}

STATUS = {
    "light": {"success": "#059669", "warning": "#D97706", "danger": "#E11D48", "info": "#0284C7"},
    "dark": {"success": "#34D399", "warning": "#FBBF24", "danger": "#FB7185", "info": "#38BDF8"},
}

# Each palette carries the domains it belongs to, so the request picks it.
PALETTES = [
    {"id": "midnight-indigo", "name": "Midnight Indigo", "neutral": "slate",
     "mood": "Focused, technical, product-led. Dashboards and SaaS.",
     "domains": ("dashboard", "admin", "saas", "analytics", "crm", "erp", "inventory",
                 "management", "portal", "tracker", "task", "project"),
     "light": {"primary": "#4F46E5", "primaryHover": "#4338CA", "accent": "#8B5CF6"},
     "dark": {"primary": "#818CF8", "primaryHover": "#A5B4FC", "accent": "#A78BFA"}},
    {"id": "ocean-slate", "name": "Ocean Slate", "neutral": "navy",
     "mood": "Calm, trustworthy, institutional. Finance, health, government.",
     "domains": ("hospital", "clinic", "health", "medical", "patient", "doctor", "pharmacy",
                 "bank", "finance", "insurance", "loan", "payment", "government", "school",
                 "university", "student", "library"),
     "light": {"primary": "#0369A1", "primaryHover": "#075985", "accent": "#06B6D4"},
     "dark": {"primary": "#38BDF8", "primaryHover": "#7DD3FC", "accent": "#22D3EE"}},
    {"id": "forest-sage", "name": "Forest Sage", "neutral": "stone",
     "mood": "Grounded, sustainable, calm. Wellness, farming, education, climate.",
     "domains": ("farm", "agri", "garden", "gardening", "nursery", "plant", "plants",
                 "seed", "florist", "eco", "green", "climate", "wellness", "yoga",
                 "fitness", "gym", "nature", "recycle", "environment", "organic"),
     "light": {"primary": "#15803D", "primaryHover": "#166534", "accent": "#84CC16"},
     "dark": {"primary": "#4ADE80", "primaryHover": "#86EFAC", "accent": "#A3E635"}},
    {"id": "sunset-ember", "name": "Sunset Ember", "neutral": "stone",
     "mood": "Warm, energetic, consumer. Marketplaces, food, travel, community.",
     "domains": ("restaurant", "food", "cafe", "menu", "delivery", "recipe", "kitchen",
                 "travel", "tour", "hotel", "booking", "resort", "event", "ticket",
                 "marketplace", "shop", "store", "ecommerce", "cart"),
     "light": {"primary": "#EA580C", "primaryHover": "#C2410C", "accent": "#F59E0B"},
     "dark": {"primary": "#FB923C", "primaryHover": "#FDBA74", "accent": "#FBBF24"}},
    {"id": "royal-violet", "name": "Royal Violet", "neutral": "zinc",
     "mood": "Creative, premium, expressive. Design tools, media, AI products.",
     "domains": ("music", "media", "video", "stream", "photo", "gallery", "art", "design",
                 "creative", "studio", "ai", "chat", "social", "game"),
     "light": {"primary": "#7C3AED", "primaryHover": "#6D28D9", "accent": "#D946EF"},
     "dark": {"primary": "#A78BFA", "primaryHover": "#C4B5FD", "accent": "#E879F9"}},
    {"id": "rose-clay", "name": "Rose Clay", "neutral": "sand",
     "mood": "Soft, human, editorial. Portfolios, lifestyle, boutique commerce.",
     "domains": ("portfolio", "blog", "wedding", "beauty", "salon", "fashion", "boutique",
                 "lifestyle", "bakery", "craft"),
     "light": {"primary": "#BE4A5C", "primaryHover": "#9F3A4B", "accent": "#D97757"},
     "dark": {"primary": "#F19AA6", "primaryHover": "#F7BFC6", "accent": "#E79479"}},
    {"id": "cyber-teal", "name": "Cyber Teal", "neutral": "navy",
     "mood": "Sharp, modern, technical. Developer tools, data, logistics.",
     "domains": ("developer", "api", "devops", "monitor", "log", "data", "iot", "sensor",
                 "fleet", "logistics", "warehouse", "shipping", "transport", "parking"),
     "light": {"primary": "#0D9488", "primaryHover": "#0F766E", "accent": "#65A30D"},
     "dark": {"primary": "#2DD4BF", "primaryHover": "#5EEAD4", "accent": "#A3E635"}},
    {"id": "mono-contrast", "name": "Mono Contrast", "neutral": "zinc",
     "mood": "Editorial, minimal, typography-first. Docs, agencies, news.",
     "domains": ("news", "magazine", "docs", "documentation", "agency", "journal", "notes",
                 "wiki", "reading"),
     "light": {"primary": "#111111", "primaryHover": "#2E2E2E", "accent": "#2563EB"},
     "dark": {"primary": "#FAFAFA", "primaryHover": "#E4E4E7", "accent": "#60A5FA"}},
]

FONTS = [
    {"id": "inter-neue", "name": "Inter Neue",
     "heading": 'Inter,"Segoe UI Variable Display","Segoe UI",system-ui,sans-serif',
     "body": 'Inter,"Segoe UI",system-ui,-apple-system,sans-serif',
     "mono": '"JetBrains Mono","Cascadia Mono",Consolas,ui-monospace,monospace'},
    {"id": "georgia-editorial", "name": "Georgia Editorial",
     "heading": 'Georgia,"Iowan Old Style","Times New Roman",serif',
     "body": '"Segoe UI",system-ui,-apple-system,"Helvetica Neue",sans-serif',
     "mono": 'Consolas,"SF Mono",ui-monospace,monospace'},
    {"id": "cambria-classic", "name": "Cambria Classic",
     "heading": 'Cambria,Constantia,"Palatino Linotype",Georgia,serif',
     "body": 'Calibri,Candara,"Segoe UI",system-ui,sans-serif',
     "mono": "Consolas,ui-monospace,monospace"},
    {"id": "grotesk-sharp", "name": "Grotesk Sharp",
     "heading": 'Archivo,"Helvetica Neue","Arial Black",Arial,sans-serif',
     "body": '"Helvetica Neue",Helvetica,Arial,"Segoe UI",sans-serif',
     "mono": '"Roboto Mono",Consolas,ui-monospace,monospace'},
    {"id": "garamond-luxe", "name": "Garamond Luxe",
     "heading": '"EB Garamond",Garamond,"Palatino Linotype",Palatino,Georgia,serif',
     "body": 'Optima,Candara,Corbel,"Segoe UI",sans-serif',
     "mono": '"Courier New",Courier,ui-monospace,monospace'},
    {"id": "corbel-humanist", "name": "Corbel Humanist",
     "heading": 'Corbel,Candara,"Segoe UI",system-ui,sans-serif',
     "body": 'Candara,Corbel,"Segoe UI",system-ui,sans-serif',
     "mono": "Consolas,ui-monospace,monospace"},
    {"id": "console-tech", "name": "Console Tech",
     "heading": '"Cascadia Mono","JetBrains Mono",Consolas,ui-monospace,monospace',
     "body": '"Segoe UI",system-ui,-apple-system,sans-serif',
     "mono": '"Cascadia Mono",Consolas,ui-monospace,monospace'},
]

# Which font suits which palette's mood. Typography is not independent of colour.
FONT_FOR_PALETTE = {
    "midnight-indigo": "inter-neue", "ocean-slate": "inter-neue",
    "forest-sage": "corbel-humanist", "sunset-ember": "grotesk-sharp",
    "royal-violet": "grotesk-sharp", "rose-clay": "garamond-luxe",
    "cyber-teal": "console-tech", "mono-contrast": "georgia-editorial",
}

TYPE_SCALES = {"compact": (1.2, 14), "balanced": (1.25, 15),
               "comfortable": (1.333, 16), "dramatic": (1.5, 17)}
RADII = {"square": "0px", "subtle": "4px", "rounded": "8px", "soft": "14px", "pillowy": "22px"}
DENSITIES = {"compact": (4, 32), "cozy": (4, 40), "comfortable": (8, 48)}

BORDERS = {
    "hairline": ("1px", "One thin rule. Separation comes mostly from spacing."),
    "defined": ("1.5px", "Visible structure without weight. Good on dense screens."),
    "bold": ("2px", "Strong outlines. Editorial and high-contrast."),
}
ELEVATION = {
    "flat": "No shadows. Separation comes from borders alone.",
    "subtle": "A hairline shadow on raised surfaces only.",
    "layered": "A clear three-step scale: card, popover, modal.",
    "dramatic": "Deep, tinted shadows. Marketing pages.",
}
MOTION = {
    "none": "No transitions. Instant, and maximally accessible.",
    "subtle": "120-180ms fades and 2px shifts.",
    "expressive": "200-320ms springs, slide-ins, staggered lists.",
}
THEME_MODES = {
    "light": "One light theme. Fastest to build and verify.",
    "dark": "One dark theme.",
    "both": "Both token sets, a working toggle, and the choice remembered.",
}
TONES = {
    "professional": "Precise, calm, no exclamation marks.",
    "friendly": "Warm and plain-spoken. Contractions welcome.",
    "playful": "Light humour, personality in empty states.",
    "bold": "Short, confident, declarative.",
    "minimal": "Say the least that works. Labels over sentences.",
    "luxury": "Restrained, spacious, understated.",
}
CONTRAST = {
    "aa": "WCAG AA: 4.5:1 body text, 3:1 large text and UI. The baseline.",
    "aaa": "WCAG AAA: 7:1 body text. Stricter, and it constrains muted greys.",
}
CONTAINERS = {
    "1120": "Focused app content.",
    "1280": "The common default.",
    "1440": "Wide dashboards and tables.",
    "full": "Edge to edge, with page gutters.",
}

# A route the plan wrote as code or in quotes: `/menu`, "/admin/orders".
# This is how a plan names a route, and it is what separates one from the
# prose around it - measured on a real plan, reading every slash-word instead
# found thirty-eight "screens" in a five-screen application, among them /127
# out of an IP address, /db out of "test/db", and /vitest out of
# "jest-dom/vitest".
QUOTED_ROUTE = re.compile(r"[`\"'](/(?:[a-z0-9][a-z0-9\-/\[\]:_]*)?)[`\"']")

# The fallback, for a plan that quotes nothing. It has to stand on its own:
# preceded by a space or a bracket, never by a letter, a digit or a dot, so
# the tail of `MongoDB/Mongoose` and of `127.0.0.1` cannot become a page.
BARE_ROUTE = re.compile(
    r"(?:^|(?<=[\s(\[]))(/(?:[a-z0-9][a-z0-9\-/\[\]:_]*)?)(?=[\s,.;:)\]]|$)")

# Routes that are not screens. An API handler has no design.
NOT_A_SCREEN = ("/api/", "/_next", "/static/", "/assets/", "/public/")

# The same, as the first segment, so `/api` itself goes as well as what is under
# it. A MERN plan names its gateway's `/api` and `/ready` beside the screens,
# and both were offered as pages to draw.
NOT_A_SCREEN_ROOT = {"api", "_next", "static", "assets", "public"}

# What a platform polls to ask whether the app is up. Only the bare route: a
# screen at /orders/ready or /ready-meals is still a screen.
HEALTH_ROUTES = {"health", "healthz", "ready", "readyz", "livez", "metrics"}

# The last segment of a file path, not of a route: `app/menu/page.jsx` is how
# the screen at /menu is built, and is not a second screen called /menu/page.
NOT_A_SEGMENT = ("page", "route", "layout", "index", "middleware")


def _is_screen(route: str) -> bool:
    if any(skip in route for skip in NOT_A_SCREEN):
        return False
    if route.count("/") > 4 or "." in route:
        return False
    parts = [part for part in route.strip("/").split("/") if part]
    if parts and (parts[0] in NOT_A_SCREEN_ROOT or parts == parts[:1] and parts[0] in HEALTH_ROUTES):
        return False
    if parts and parts[-1] in NOT_A_SEGMENT:
        return False
    # A number is a port, a status code or an octet - never a page.
    return not any(part.isdigit() for part in parts)


def _screen_label(route: str) -> str:
    """`/recipes/[slug]` -> `Recipe detail`; `/` -> `Home`."""
    parts = [part for part in route.strip("/").split("/") if part]
    if not parts:
        return "Home"
    dynamic = [part for part in parts if part.startswith(("[", ":"))]
    words = [part for part in parts if not part.startswith(("[", ":"))]
    name = " ".join(word.replace("-", " ").replace("_", " ") for word in words) or "Item"
    label = name[:1].upper() + name[1:]
    return f"{label.rstrip('s')} detail" if dynamic else label


# A heading that introduces the screens, and a list item under it. Reading the
# section the plan wrote is still reading the plan; it is not a list of screens
# in general.
SCREEN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*(?:[0-9.]+\s*)?(?:the\s+)?"
                            r"(screens?|pages?|routes?|views?)\b", re.I)
ANY_HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
LIST_ITEM = re.compile(r"^\s{0,6}(?:[-*+]|\d+[.)])\s+(.*)$")

# "A rooms page", "the settings screen", "an orders view" - a plan that names
# its screens in prose rather than by path.
NAMES_A_SCREEN = re.compile(
    r"\b(?:an?|the)\s+([a-z][a-z0-9]*(?:[ '\-][a-z0-9]+){0,3})\s+(?:page|screen|view)\b",
    re.I)

# Words that describe a screen rather than name one.
NOT_A_NAME = {"new", "the", "this", "that", "each", "every", "one", "same",
              "single", "first", "last", "next", "other", "another", "only",
              "whole", "full", "real", "own", "second"}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")


def _named_screens(body: str) -> list[dict]:
    """Screens the plan names without giving them a path.

    A plan is prose, and a planner that writes "a rooms page: the inventory
    grid with filters" has named a screen just as surely as one that writes
    `/rooms`. Reading only the paths showed a six-screen product as one screen,
    and the design step then offered the user a single page to think about.

    No route is invented for these. The plan did not state one, so the studio
    shows the name and leaves the path blank rather than claiming a path that
    may turn out to be wrong.
    """
    found: dict[str, dict] = {}

    def keep(name: str, said: str) -> None:
        name = " ".join(str(name or "").split())[:40]
        slug = _slug(name)
        if not slug or name.lower() in NOT_A_NAME or slug in found:
            return
        found[slug] = {"id": slug, "route": "", "label": name[:1].upper() + name[1:],
                       "what": said[:160]}

    # The section the plan wrote for them, when it wrote one.
    inside = False
    for line in body.splitlines():
        if ANY_HEADING.match(line):
            inside = bool(SCREEN_HEADING.match(line))
            continue
        if not inside:
            continue
        item = LIST_ITEM.match(line)
        if not item:
            continue
        said = item.group(1).strip()
        # "Dashboard — KPIs and recent bookings" / "Rooms: the inventory grid".
        # The name is what comes before the dash; what follows is what it does.
        parts = re.split(r"\s*[-–—:|]\s+", said, maxsplit=1)
        name = re.sub(r"[`*]", "", parts[0])
        keep(name, parts[1].strip() if len(parts) > 1 else said)

    if found:
        return list(found.values())

    # Otherwise, anywhere the plan calls something a page, a screen or a view.
    for line in body.splitlines():
        for match in NAMES_A_SCREEN.finditer(line):
            said = re.sub(r"^[\s\-*#>|0-9.)]+", "", line).strip()
            keep(match.group(1), said)
    return list(found.values())


def pages_from_plan(text: str) -> list[dict]:
    """The screens this plan actually names, with what each one is for.

    The alternative is a list of screens in general - landing, login, profile,
    settings - offered to every product whether or not it has them. A plan
    that has been approved already says which screens exist; asking about any
    others is asking the user to design a different application.
    """
    body = str(text or "")
    # A plan that writes one route as code writes all of them that way, so the
    # quoted ones are the whole inventory and the loose scan is only for a plan
    # that quotes nothing at all.
    pattern = QUOTED_ROUTE if QUOTED_ROUTE.search(body) else BARE_ROUTE

    found: dict[str, dict] = {}
    for line in body.splitlines():
        # A line naming one route is describing it. A line naming four is
        # listing them - "compiles cleanly with all routes (/menu, /checkout,
        # /admin/login)" - and describes none of them.
        listed = len(pattern.findall(line)) > 1
        for match in pattern.finditer(line):
            route = match.group(1).rstrip(".,;:)")
            if not _is_screen(route):
                continue
            key = route.rstrip("/") or "/"
            # What the plan says about it, without repeating the route back.
            said = re.sub(r"^[\s\-*#>|0-9.)]+", "", line).strip()
            said = said.replace(f"`{route}`", "").replace(route, "", 1)
            said = re.sub(r"^[\s`\-–—:.,]+", "", said)
            said = re.sub(r"\s+", " ", said).strip()

            # A plan mentions a route several times and describes it once. The
            # line that describes it names it early - "- `/menu` — today's
            # soups" - where a passing mention buries it in a sentence about
            # something else. Taking the first occurrence gave the home page a
            # description about confirmation emails.
            rank = (listed, match.start(), len(line))
            if key in found and found[key]["rank"] <= rank:
                continue
            found[key] = {
                "id": key, "route": key, "label": _screen_label(key),
                # A line that only listed this route alongside others says
                # nothing about it, and an empty description is better than a
                # confident sentence about something else.
                "what": "" if listed else said[:160], "rank": rank,
            }
    for page in found.values():
        page.pop("rank", None)
    if len(found) > 1:
        return sorted(found.values(), key=lambda page: (page["route"] != "/", page["route"]))

    # One route, or none, in a plan that plainly describes an application: the
    # planner named its screens in prose instead of by path. Read those, and
    # keep whichever route it did write.
    named = _named_screens(body)
    if len(named) > len(found):
        by_id = {page["id"]: page for page in named}
        by_id.update({page["id"]: page for page in found.values()})
        return sorted(by_id.values(), key=lambda page: (page["route"] != "/", page["label"]))
    return sorted(found.values(), key=lambda page: (page["route"] != "/", page["route"]))


PAGES = [
    ("landing", "Landing / home", False), ("login", "Login", False),
    ("register", "Register", False), ("dashboard", "Dashboard", False),
    ("list", "List / index", False), ("detail", "Detail view", False),
    ("create-edit", "Create / edit form", False), ("search", "Search results", False),
    ("profile", "Profile / account", False), ("settings", "Settings", False),
    ("checkout", "Cart / checkout", False), ("admin", "Admin console", False),
    ("not-found", "404 / error", False),
]

# Data-dense products get tighter defaults; consumer products get roomier ones.
SHAPE_FOR_PALETTE = {
    "midnight-indigo": ("balanced", "rounded", "cozy"),
    "ocean-slate": ("balanced", "subtle", "compact"),
    "forest-sage": ("comfortable", "soft", "comfortable"),
    "sunset-ember": ("comfortable", "soft", "comfortable"),
    "royal-violet": ("comfortable", "soft", "cozy"),
    "rose-clay": ("dramatic", "rounded", "comfortable"),
    "cyber-teal": ("compact", "subtle", "compact"),
    "mono-contrast": ("dramatic", "square", "cozy"),
}

# Words that describe the shape of an app rather than its subject. A hospital
# dashboard is a hospital product; "dashboard" must not outvote "hospital".
GENERIC_DOMAINS = frozenset({
    "dashboard", "admin", "portal", "management", "tracker", "task", "project",
    "shop", "store", "booking", "event", "chat", "social", "data", "monitor",
})

# How a palette's mood reads in words, so the copy matches the colours.
TONE_FOR_PALETTE = {
    "midnight-indigo": "professional", "ocean-slate": "professional",
    "forest-sage": "friendly", "sunset-ember": "friendly",
    "royal-violet": "bold", "rose-clay": "luxury",
    "cyber-teal": "minimal", "mono-contrast": "minimal",
}

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _luminance(hex_value: str) -> float:
    def channel(offset: int) -> float:
        value = int(hex_value[offset:offset + 2], 16) / 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)


def contrast_ratio(a: str, b: str) -> float | None:
    """WCAG contrast, 1-21. Used to check the contract, not to guess at it."""
    if not (_HEX.match(a or "") and _HEX.match(b or "")):
        return None
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return round((high + 0.05) / (low + 0.05), 2)


def _on_color(fill: str) -> str:
    """The legible foreground for a fill, rather than assuming white."""
    return "#FFFFFF" if (contrast_ratio("#FFFFFF", fill) or 1) >= (contrast_ratio("#0B0B0F", fill) or 1) \
        else "#0B0B0F"


def tokens(palette_id: str, mode: str) -> dict:
    palette = next(p for p in PALETTES if p["id"] == palette_id)
    neutral = NEUTRALS[palette["neutral"]][mode]
    brand = palette[mode]
    return {**neutral, **brand, "onPrimary": _on_color(brand["primary"]), **STATUS[mode]}


def choose(task: str) -> dict:
    """Pick the design from the request. Deterministic, and never one theme.

    Scored rather than first-match: "hotel booking dashboard" mentions three
    domains, and the one it mentions most is the one the product actually is.
    """
    text = re.sub(r"[^a-z0-9 ]+", " ", str(task or "").lower())
    words = text.split()
    corpus = f" {' '.join(words)} "

    best, best_score = PALETTES[0], 0
    for palette in PALETTES:
        score = 0
        for domain in palette["domains"]:
            if f" {domain} " not in corpus and domain not in text:
                continue
            weight = 1 if domain in GENERIC_DOMAINS else 3
            score += weight if f" {domain} " in corpus else weight - 1
        if score > best_score:
            best, best_score = palette, score

    if best_score == 0:
        # Nothing in the request named a domain this knows, and most real
        # requests name none: "Wayfarer Books, an online bookshop" matches no
        # keyword in any list. Falling through to the first palette made every
        # one of those products the same colour - the exact thing the top of
        # this file says the engine has to prevent, and not something a longer
        # keyword list would ever finish fixing.
        #
        # So the request picks it anyway, by its own digest. Two different
        # products differ, and the same request still gives the same answer
        # every time.
        digest = hashlib.sha256(" ".join(words).encode("utf-8")).digest()
        best = PALETTES[digest[0] % len(PALETTES)]

    scale, radius, density = SHAPE_FOR_PALETTE[best["id"]]
    dark_first = any(word in corpus for word in
                     (" dark ", " night ", " terminal ", " console ", " developer "))
    return {
        "palette": best["id"], "paletteName": best["name"], "mood": best["mood"],
        "font": FONT_FOR_PALETTE[best["id"]],
        "typeScale": scale, "radius": radius, "density": density,
        "themeMode": "dark" if dark_first else "light",
        "border": "bold" if best["id"] == "mono-contrast" else "hairline",
        "elevation": "flat" if best["id"] == "mono-contrast" else "subtle",
        "motion": "subtle",
        "tone": TONE_FOR_PALETTE.get(best["id"], "professional"),
        "contrast": "aa",
        "container": "1440" if density == "compact" else "1280",
        "pages": [],
        "matched": best_score > 0,
    }


def form_payload(task: str, plan: str = "") -> dict:
    """Everything a design form needs to render, plus what was chosen for it.

    Pure data, so the studio, the CLI and a test all render the same catalogue
    and there is no second list to keep in step.
    """
    chosen = choose(task)
    # Every screen the plan names starts selected: the user removes what they
    # do not want rather than assembling the list themselves.
    screens = pages_from_plan(plan or task)
    chosen["pages"] = [page["id"] for page in screens]
    return {
        "chosen": chosen,
        "planned": bool(screens),
        "palettes": [{
            "id": p["id"], "name": p["name"], "mood": p["mood"],
            "light": tokens(p["id"], "light"), "dark": tokens(p["id"], "dark"),
        } for p in PALETTES],
        "fonts": [{"id": f["id"], "name": f["name"], "heading": f["heading"],
                   "body": f["body"]} for f in FONTS],
        "typeScales": [{"id": name, "base": base, "ratio": ratio}
                       for name, (ratio, base) in TYPE_SCALES.items()],
        "radii": [{"id": name, "value": value} for name, value in RADII.items()],
        "densities": [{"id": name, "unit": unit, "control": control}
                      for name, (unit, control) in DENSITIES.items()],
        "borders": [{"id": name, "value": value, "hint": hint}
                    for name, (value, hint) in BORDERS.items()],
        "elevations": [{"id": name, "hint": hint} for name, hint in ELEVATION.items()],
        "motions": [{"id": name, "hint": hint} for name, hint in MOTION.items()],
        "themeModes": [{"id": name, "hint": hint} for name, hint in THEME_MODES.items()],
        "tones": [{"id": name, "hint": hint} for name, hint in TONES.items()],
        "contrasts": [{"id": name, "hint": hint} for name, hint in CONTRAST.items()],
        "containers": [{"id": name, "hint": hint} for name, hint in CONTAINERS.items()],
        "pages": screens or [{"id": page, "label": label, "route": "", "what": "",
                              "core": core} for page, label, core in PAGES],
    }


def apply_answer(chosen: dict, answer: dict | None) -> dict:
    """Fold a form answer onto the chosen defaults, ignoring anything unknown.

    The answer arrives over HTTP, so nothing here trusts its shape: an
    unrecognised id keeps the default rather than failing the build at the one
    step that was meant to be optional.
    """
    if not isinstance(answer, dict):
        return chosen
    allowed = {
        "palette": {p["id"] for p in PALETTES},
        "font": {f["id"] for f in FONTS},
        "typeScale": set(TYPE_SCALES),
        "radius": set(RADII),
        "density": set(DENSITIES),
        "themeMode": set(THEME_MODES),
        "border": set(BORDERS),
        "elevation": set(ELEVATION),
        "motion": set(MOTION),
        "tone": set(TONES),
        "contrast": set(CONTRAST),
        "container": set(CONTAINERS),
    }
    picked = dict(chosen)
    for field, valid in allowed.items():
        value = answer.get(field)
        if isinstance(value, str) and value in valid:
            picked[field] = value
    wanted_pages = answer.get("pages")
    if isinstance(wanted_pages, list) and picked.get("pages"):
        # The offered screens came from the plan, so they are the known set.
        known = set(picked["pages"])
        picked["pages"] = [page for page in wanted_pages if page in known]
    elif isinstance(wanted_pages, list):
        known = {page for page, _, _ in PAGES}
        picked["pages"] = sorted({p for p in wanted_pages if p in known})
    if picked["palette"] != chosen["palette"]:
        palette = next(p for p in PALETTES if p["id"] == picked["palette"])
        picked["paletteName"], picked["mood"] = palette["name"], palette["mood"]
    picked["matched"] = True
    return picked



def _theme_note(mode: str) -> str:
    """How the chosen theme is actually switched on.

    "One dark theme" used to be followed by "the dark tokens go under
    [data-theme=dark]" and nothing else, which says where to put them and never
    says to turn them on. Twenty drawn pages opened `<html lang="en">`, the dark
    block sat there unused, and a site chosen dark came out white.
    """
    if mode == "dark":
        return (" The page is dark by default: the dark values are the ones in `:root`, "
                "so nothing has to be toggled for it to look right.")
    if mode == "both":
        return (' Light is `:root` and dark goes under `[data-theme="dark"]`, set on '
                "`<html>` by the toggle and remembered.")
    return ""


def render_tokens_css(selection: dict) -> str:
    """The contract as CSS custom properties, both modes."""
    scale, base = TYPE_SCALES[selection["typeScale"]]
    unit, control = DENSITIES[selection["density"]]
    # Which set the page wears when nothing has been toggled. This used to be
    # the light one whatever had been chosen, so picking "one dark theme" wrote
    # the dark values under `[data-theme="dark"]`, left `:root` light, and shipped
    # twenty pages of `<html lang="en">` with nothing to turn it on. The dark
    # tokens were there and dead, and the site was white.
    default = selection.get("themeMode") if selection.get("themeMode") in ("light", "dark") else "light"
    other = "dark" if default == "light" else "light"

    lines = [":root {"]
    for role, value in tokens(selection["palette"], default).items():
        lines.append(f"  --{_kebab(role)}: {value};")
    font = next(f for f in FONTS if f["id"] == selection["font"])
    lines += [f"  --font-heading: {font['heading']};",
              f"  --font-body: {font['body']};",
              f"  --font-mono: {font['mono']};",
              f"  --font-size-base: {base}px;",
              f"  --type-scale: {scale};",
              f"  --radius: {RADII[selection['radius']]};",
              f"  --space-unit: {unit}px;",
              f"  --control-height: {control}px;",
              "}", "", f'[data-theme="{other}"] {{']
    for role, value in tokens(selection["palette"], other).items():
        lines.append(f"  --{_kebab(role)}: {value};")
    lines.append("}")
    return "\n".join(lines)


def _kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def render_skill(selection: dict, goal: str = "") -> str:
    light, dark = tokens(selection["palette"], "light"), tokens(selection["palette"], "dark")
    ratio = contrast_ratio(light["text"], light["background"])
    font = next(f for f in FONTS if f["id"] == selection["font"])
    return "\n".join([
        "---", f"name: {SKILL_NAME}",
        "description: The design contract for this application. Colours, type, shape and "
        "spacing are decided; follow them exactly rather than inventing your own.",
        "---", "",
        "# Design system", "",
        f"Chosen for this product: **{selection['paletteName']}** - {selection['mood']}",
        (f"\nGoal: {goal[:300]}" if goal else ""), "",
        "This is the contract, not a suggestion. Where this file and your own taste disagree, "
        "this file wins. Do not introduce another palette, another font stack or another radius "
        "scale anywhere in the application.", "",
        "## Tokens", "",
        "Put these in the global stylesheet and reference them everywhere. Never hard-code a "
        "hex value in a component.", "",
        "```css", render_tokens_css(selection), "```", "",
        "## Typography", "",
        f"- Headings: `{font['heading']}`",
        f"- Body: `{font['body']}`",
        f"- Monospace: `{font['mono']}`",
        f"- Base size {TYPE_SCALES[selection['typeScale']][1]}px, "
        f"scale ratio {TYPE_SCALES[selection['typeScale']][0]}.", "",
        "## Shape and spacing", "",
        f"- Corner radius: {RADII[selection['radius']]} on cards, inputs and buttons.",
        f"- Spacing unit: {DENSITIES[selection['density']][0]}px; every gap is a multiple of it.",
        f"- Control height: {DENSITIES[selection['density']][1]}px for buttons and inputs.",
        f"- Borders: {BORDERS[selection.get('border', 'hairline')][0]}. "
        f"{BORDERS[selection.get('border', 'hairline')][1]}",
        f"- Elevation: {ELEVATION[selection.get('elevation', 'subtle')]}",
        f"- Motion: {MOTION[selection.get('motion', 'subtle')]}",
        f"- Content width: {selection.get('container', '1280')}"
        + ("px" if str(selection.get("container", "1280")).isdigit() else "") + ". "
        + CONTAINERS[selection.get("container", "1280")],
        f"- Theme: {THEME_MODES[selection.get('themeMode', 'light')]}"
        + _theme_note(selection.get("themeMode", "light")), "",
        "## Voice", "",
        f"- {selection.get('tone', 'professional').title()}: "
        f"{TONES[selection.get('tone', 'professional')]}",
        f"- Contrast: {CONTRAST[selection.get('contrast', 'aa')]}", "",
        "## Styling", "",
        "Tailwind is installed and configured in the scaffold, and its theme reads the tokens "
        "above. Compose the interface from Tailwind utilities and your own components; do not "
        "install a component library on top of it, and do not hand-write a second colour or "
        "spacing scale beside the tokens.", "",
        "## Screens this product needs", "",
        "Implement the screens and routes in the approved plan. Apply this design to those "
        "screens without adding routes based on domain words or generic UI examples. "
        "The following are additions explicitly selected in the design form; an empty list "
        "keeps the approved plan's scope unchanged.", "",
        *[f"- {label}" for page, label, _ in PAGES if page in (selection.get("pages") or [])],
        "",
        "## Rules", "",
        "- Body text on the page background is "
        f"{ratio}:1 - keep every text/background pair at 4.5:1 or better.",
        "- `accent` is for highlights and badges. The primary call to action always uses "
        "`primary`.",
        "- Every interactive element needs a visible focus ring using `primary`.",
        "- Finish the loading, empty, error and success state of every screen. A screen that "
        "only has its happy path is not done.",
        "- Layout must work at 360px and at 1280px. Test both.", "",
        "## Palette reference", "",
        "| role | light | dark |", "| --- | --- | --- |",
        *[f"| {role} | `{light[role]}` | `{dark[role]}` |" for role in light],
    ])


def write_design_skill(workspace: Path | str, selection: dict, goal: str = "",
                       stack: str = "nextjs-mongo") -> dict:
    """Write the contract into the project as a skill and return where it went."""
    target = Path(workspace) / ".agents" / "skills" / SKILL_NAME
    target.mkdir(parents=True, exist_ok=True)
    (target / "SKILL.md").write_text(render_skill(selection, goal), encoding="utf-8")
    css = target / "tokens.css"
    css.write_text(render_tokens_css(selection), encoding="utf-8")
    return {"skill": SKILL_NAME,
            "path": f".agents/skills/{SKILL_NAME}/SKILL.md",
            "tokens": f".agents/skills/{SKILL_NAME}/tokens.css",
            "selection": selection}


def design_contract_message(selection: dict) -> str:
    return "\n".join([
        "DESIGN CONTRACT (already decided; do not re-open it):",
        f"- Palette: {selection['paletteName']} - {selection['mood']}",
        f"- Default theme: {selection['themeMode']}; both modes must work.",
        f"- Type: {selection['font']}, {selection['typeScale']} scale.",
        f"- Shape: {selection['radius']} radius, {selection['density']} density.",
        f"Read `.agents/skills/{SKILL_NAME}/SKILL.md` in full before writing any UI, and copy "
        "its token block into the application's global stylesheet. Do not invent a second "
        "palette, and do not hard-code hex values in components.",
    ])
