"""Design library — curated, self-contained page templates distilled from the
user's local template collections (`ai_designer/landing pages/*` for marketing,
`Downloads/Compressed/*` React admin templates for dashboard/CRUD).

Flow (user-specified): the library SAVES proven designs; for each user input we
MATCH the closest template, take a COPY, and hand it to the LLM to EDIT for the
requested app (rewrite copy/brand/data wiring, keep the structure and polish).
Editing a strong template is far more reliable for a small model than authoring
a page from scratch.

Templates are browser-global JSX in our runtime conventions (window.<Page>,
Tailwind CDN classes, Icon global, assets/*.jpg image slots) and use the word
`ACCENT` inside Tailwind classes (e.g. bg-ACCENT-600). `load_template`
deterministically replaces it with the theme's real accent family so recoloring
never depends on the LLM.
"""
import os
import random
import re

_LIB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library")

# kind -> list of {name, file, mode, tags}
REGISTRY = {
    "landing": [
        {"name": "creative-dark", "file": "landing_creative_dark.jsx", "mode": "dark",
         "tags": ["ai", "tech", "creative", "studio", "media", "gaming", "saas", "modern", "startup"]},
        {"name": "saas-light", "file": "landing_saas_light.jsx", "mode": "light",
         "tags": ["saas", "business", "management", "crm", "platform", "clean", "corporate", "health", "education"]},
        {"name": "editorial-photo", "file": "landing_editorial.jsx", "mode": "light",
         "tags": ["restaurant", "hotel", "travel", "fashion", "estate", "salon", "food", "boutique", "gallery", "premium"]},
    ],
    "dashboard": [
        {"name": "mantis-admin", "file": "dashboard_mantis.jsx", "mode": "any",
         "tags": ["admin", "analytics", "management", "corporate"]},
        {"name": "glass-band", "file": "dashboard_glass.jsx", "mode": "any",
         "tags": ["modern", "creative", "media", "startup"]},
    ],
    "list": [
        {"name": "pro-table", "file": "crud_list.jsx", "mode": "any", "tags": ["any"]},
    ],
}

# V2 (Next.js) templates - landings keep the SAME copy-slot anchors, so
# landing_copy.apply works unchanged; marketing pages share that copy JSON.
_NEXT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library_next")

NEXT_LANDINGS = [
    {"name": "creative-dark", "file": "landing_creative_dark.jsx",
     "tags": ["ai", "tech", "creative", "studio", "media", "gaming", "saas", "modern", "startup"]},
    {"name": "saas-light", "file": "landing_saas_light.jsx",
     "tags": ["saas", "business", "management", "crm", "platform", "clean", "corporate", "health", "education", "school", "hospital"]},
    {"name": "editorial-photo", "file": "landing_editorial.jsx",
     "tags": ["restaurant", "hotel", "travel", "fashion", "estate", "salon", "food", "boutique", "gallery", "premium", "gym", "fitness"]},
    # Remixed from the user's own projects (section bank): every pick composes
    # a DIFFERENT section combination, so this one never repeats itself.
    {"name": "remix-sections", "file": None, "compose": True,
     "tags": ["any", "management", "system", "app", "platform", "shop", "store"]},
]

NEXT_MARKETING = {"features": "page_features.jsx", "about": "page_about.jsx", "contact": "page_contact.jsx"}


def match_landing_next(prompt_text: str):
    text = (prompt_text or "").lower()
    def score(e):
        return sum(2 for t in e["tags"] if t in text) + random.random()
    return max(NEXT_LANDINGS, key=score)


# =========================================================================
# VARIETY ENGINE — no two consecutive generations share a design, even for
# the SAME prompt. Choices (landing template x accent palette x font pair =
# 3 x 10 x 14 = 420 base combinations) are persisted to _design_history.json
# and recent picks are heavily down-weighted / excluded.
# =========================================================================
FONT_PAIRS = [
    ("Sora", "Inter"), ("Poppins", "Inter"), ("Manrope", "Manrope"),
    ("Space Grotesk", "Inter"), ("Outfit", "Outfit"), ("Plus Jakarta Sans", "Inter"),
    ("Fraunces", "Inter"), ("Playfair Display", "Source Sans 3"), ("IBM Plex Sans", "IBM Plex Sans"),
    ("DM Sans", "DM Sans"), ("Rubik", "Karla"), ("Bricolage Grotesque", "Inter"),
    ("Lexend", "Lexend"), ("Quicksand", "Nunito"),
]

ACCENT_FAMILIES = ["cyan", "blue", "indigo", "violet", "fuchsia", "rose", "emerald", "lime", "amber", "slate"]

_HISTORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_design_history.json")


def _load_history():
    try:
        import json
        with open(_HISTORY, encoding="utf-8") as f:
            return json.load(f)[-6:]
    except Exception:
        return []


def _save_history(hist):
    try:
        import json
        with open(_HISTORY, "w", encoding="utf-8") as f:
            json.dump(hist[-6:], f)
    except OSError:
        pass


def pick_design(prompt_text: str) -> dict:
    """Pick {landing, accent, font_display, font_body} - domain tags still bias
    the landing choice, but anything used in the last two runs is avoided."""
    hist = _load_history()
    recent_landings = [h.get("landing") for h in hist[-2:]]
    recent_accents = [h.get("accent") for h in hist[-2:]]
    recent_fonts = [h.get("font_display") for h in hist[-2:]]
    text = (prompt_text or "").lower()

    def weight(e):
        w = 1.0 + 1.5 * sum(1 for t in e["tags"] if t in text)
        if e["name"] in recent_landings:
            w *= 0.12
        return w

    weights = [weight(e) for e in NEXT_LANDINGS]
    landing = random.choices(NEXT_LANDINGS, weights=weights, k=1)[0]
    if hist and landing["name"] == hist[-1].get("landing") and len(NEXT_LANDINGS) > 1:
        others = [e for e in NEXT_LANDINGS if e["name"] != landing["name"]]
        landing = random.choices(others, weights=[weight(e) for e in others], k=1)[0]

    accents = [a for a in ACCENT_FAMILIES if a not in recent_accents] or ACCENT_FAMILIES
    accent = random.choice(accents)
    pairs = [p for p in FONT_PAIRS if p[0] not in recent_fonts] or FONT_PAIRS
    font_display, font_body = random.choice(pairs)

    hist.append({"landing": landing["name"], "accent": accent, "font_display": font_display})
    _save_history(hist)
    return {"landing": landing, "accent": accent, "font_display": font_display, "font_body": font_body}


def load_next(filename: str, theme: dict) -> str:
    with open(os.path.join(_NEXT_DIR, filename), encoding="utf-8") as f:
        src = f.read()
    return src.replace("ACCENT", accent_family(theme))


def load_landing(entry: dict, theme: dict, hero_file: str | None = None,
                  prompt_text: str = "", design_plane: dict | None = None,
                  category_id: str = "") -> tuple[str, str]:
    """Return (detail, source) for a landing entry - file-based or composed.

    When `design_plane` is provided (from the new classification pipeline), the
    compose path uses the plane's world-class section sequence (12-16 sections)
    instead of random 4-6 sections. `category_id` enables domain-specific
    heading substitution so section copy matches the app type.
    """
    if entry.get("compose"):
        from app import section_bank
        desc, src, used_families = section_bank.compose_landing(
            hero_file=hero_file,
            prompt_text=prompt_text,
            design_plane=design_plane,
            category_id=category_id,
        )
        return desc, src.replace("ACCENT", accent_family(theme)), used_families
    return entry["name"], load_next(entry["file"], theme), set()


_FAMILY = re.compile(r"(?:text|bg|from|to|ring|border)-([a-z]+)-\d")


def accent_family(theme: dict) -> str:
    """'text-cyan-400' -> 'cyan'; falls back to indigo."""
    m = _FAMILY.search(theme.get("accent", "") or "")
    return m.group(1) if m else "indigo"


def match_template(kind: str, prompt_text: str, theme: dict):
    """Pick the library entry closest to the user's input (tag hits + theme-mode
    affinity, random tie-break for variety). None when the kind has no library."""
    entries = REGISTRY.get(kind) or []
    if not entries:
        return None
    text = (prompt_text or "").lower()
    mode = theme.get("mode", "light")

    def score(e):
        s = sum(2 for t in e["tags"] if t in text)
        if e["mode"] in (mode, "any"):
            s += 1
        return s + random.random()  # tie-break -> variety across runs

    return max(entries, key=score)


def load_template(entry: dict, theme: dict) -> str:
    """Read a template copy and recolor ACCENT -> the theme's accent family."""
    path = os.path.join(_LIB_DIR, entry["file"])
    with open(path, encoding="utf-8") as f:
        src = f.read()
    return src.replace("ACCENT", accent_family(theme))
