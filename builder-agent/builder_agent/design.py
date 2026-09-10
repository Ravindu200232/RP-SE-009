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

# Optional additions. The approved plan owns the actual route inventory.
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


def form_payload(task: str) -> dict:
    """Everything a design form needs to render, plus what was chosen for it.

    Pure data, so the studio, the CLI and a test all render the same catalogue
    and there is no second list to keep in step.
    """
    chosen = choose(task)
    return {
        "chosen": chosen,
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
        "pages": [{"id": page, "label": label, "core": core} for page, label, core in PAGES],
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
    if isinstance(wanted_pages, list):
        known = {page for page, _, _ in PAGES}
        picked["pages"] = sorted({p for p in wanted_pages if p in known})
    if picked["palette"] != chosen["palette"]:
        palette = next(p for p in PALETTES if p["id"] == picked["palette"])
        picked["paletteName"], picked["mood"] = palette["name"], palette["mood"]
    picked["matched"] = True
    return picked


def render_tokens_css(selection: dict) -> str:
    """The contract as CSS custom properties, both modes."""
    scale, base = TYPE_SCALES[selection["typeScale"]]
    unit, control = DENSITIES[selection["density"]]
    lines = [":root {"]
    for role, value in tokens(selection["palette"], "light").items():
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
              "}", "", '[data-theme="dark"] {']
    for role, value in tokens(selection["palette"], "dark").items():
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
        + (' The dark tokens go under `[data-theme="dark"]`.'
           if selection.get("themeMode") != "light" else ""), "",
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
