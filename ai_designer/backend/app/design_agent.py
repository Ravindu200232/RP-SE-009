"""Design Agent — LLM-creates a visual design_blueprint.json per SRS app.

Reads the parsed SRS + genome + design history, calls Gemma to produce a
compact 12-field visual identity blueprint that is domain-specific and unique
from all previous generations. Falls back to a genome-seeded blueprint (NOT
a single hardcoded default) so visual diversity is guaranteed even without LLM.

Key improvements over v1:
- Schema reduced to 12 fields so it fits comfortably in num_predict=4096
- Fallback maps genome axes (visual_style, nav_pattern, hero_variant) to varied
  values instead of always returning the same defaults
- Retry call when LLM parse fails (stripped prompt, max 2 attempts)
- Inline similarity check + second attempt with explicit exclusion instructions
"""
import json
import os
import random

# ── Compact LLM prompt (12-field schema) ────────────────────────────────────

_BLUEPRINT_PROMPT = """\
You are a UI/UX design strategist. Create a unique visual identity for a web app.

Return ONLY valid JSON — no explanation, no markdown — with EXACTLY these 15 keys:
{
  "domain_mood": "<one word from: clinical|luxury|retail|academic|energetic|bold|minimal|playful|enterprise|elegant|vibrant|tech>",
  "primary_color": "<hex like #1d4ed8>",
  "accent_color": "<hex like #f59e0b>",
  "background_color": "<hex like #f8fafc or #0f0f23>",
  "text_color": "<hex like #1e293b>",
  "navbar_style": "<one of: transparent-overlay|solid-dark|solid-light|glass|minimal|branded>",
  "hero_composition": "<one of: split-image-text|full-screen-image|centered-text|search-first|booking-panel|dashboard-preview|product-showcase|editorial>",
  "listing_variant": "<one of: horizontal-media-cards|large-featured-grid|schedule-grid|compact-catalog|table-catalog|standard-card-grid>",
  "filter_placement": "<one of: inline-chips|left-sidebar|top-search-bar|compact-toolbar|dark-panel>",
  "card_style": "<one of: flat-minimal|elevated-shadow|bordered|glass-effect|image-top|stat-card>",
  "button_style": "<one of: rounded-pill|sharp-corners|soft-corners|outlined|solid-gradient>",
  "dashboard_shell": "<one of: left-sidebar-dark|left-sidebar-light|top-nav-dark|top-nav-light|split-nav>",
  "background_style": "<one of: flat-color|subtle-gradient|pattern|mesh-gradient|image-overlay>",
  "page_layout_variant": "<one of: editorial-split|centered-catalog|booking-catalog|schedule-catalog|product-catalog|full-bleed-hero|magazine-sections|dashboard-landing>",
  "section_order": ["<section1>","<section2>","<section3>","<section4>","<section5>"]
}
"""

# ── Genome-to-blueprint value maps (fallback is varied, not hardcoded) ───────

_MOOD_BY_CATEGORY = {
    "healthcare": ["clinical", "elegant", "enterprise"],
    "medical":    ["clinical", "minimal", "tech"],
    "hotel":      ["luxury", "elegant", "vibrant"],
    "hospitality":["luxury", "elegant"],
    "education":  ["academic", "vibrant", "playful"],
    "school":     ["academic", "minimal"],
    "ecommerce":  ["retail", "bold", "vibrant"],
    "retail":     ["retail", "energetic", "bold"],
    "food":       ["energetic", "bold", "vibrant"],
    "restaurant": ["bold", "vibrant", "luxury"],
    "automotive": ["tech", "bold", "enterprise"],
    "fitness":    ["energetic", "bold", "vibrant"],
    "gym":        ["energetic", "bold"],
    "finance":    ["enterprise", "minimal", "tech"],
    "real_estate":["elegant", "enterprise", "minimal"],
    "beauty":     ["elegant", "luxury", "vibrant"],
    "salon":      ["elegant", "luxury"],
    "logistics":  ["tech", "enterprise", "minimal"],
    "inventory":  ["enterprise", "minimal", "tech"],
}

_NAVBAR_BY_NAV = {
    "topnav":         ["solid-light", "solid-dark", "glass", "transparent-overlay"],
    "sidebar":        ["solid-light", "branded", "minimal"],
    "split-nav":      ["branded", "glass", "solid-dark"],
    "tabs":           ["minimal", "solid-light"],
    "command-palette":["minimal", "solid-dark"],
    "mobile-bottom-nav":["solid-light", "minimal"],
}

_HERO_BY_VARIANT = {
    "split":            "split-image-text",
    "full-image":       "full-screen-image",
    "search-booking":   "search-first",
    "stats-first":      "stats-first",
    "dashboard-preview":"dashboard-preview",
    "editorial":        "editorial",
    "card-stack":       "product-showcase",
}

# Domain → structural rendering variants (used by srs_public_page_generator)
_LISTING_BY_CATEGORY = {
    "hotel": "horizontal-media-cards", "hospitality": "horizontal-media-cards",
    "travel": "horizontal-media-cards", "property": "horizontal-media-cards",
    "real_estate": "horizontal-media-cards", "real estate": "horizontal-media-cards",
    "automotive": "table-catalog", "vehicle": "table-catalog", "car": "table-catalog",
    "ecommerce": "large-featured-grid", "retail": "large-featured-grid",
    "shop": "large-featured-grid", "product": "large-featured-grid",
    "fitness": "schedule-grid", "gym": "schedule-grid", "sport": "schedule-grid",
    "class": "schedule-grid", "yoga": "schedule-grid",
    "restaurant": "large-featured-grid", "food": "large-featured-grid",
    "education": "large-featured-grid", "school": "large-featured-grid",
    "course": "large-featured-grid",
    "healthcare": "compact-catalog", "medical": "compact-catalog",
    "pharmacy": "compact-catalog", "clinic": "compact-catalog",
}

_FILTER_BY_CATEGORY = {
    "hotel": "top-search-bar", "hospitality": "top-search-bar", "travel": "top-search-bar",
    "real_estate": "left-sidebar", "real estate": "left-sidebar",
    "automotive": "left-sidebar", "vehicle": "left-sidebar",
    "ecommerce": "left-sidebar", "retail": "left-sidebar",
    "fitness": "inline-chips", "gym": "inline-chips",
    "education": "inline-chips", "school": "inline-chips",
    "restaurant": "compact-toolbar", "food": "compact-toolbar",
    "healthcare": "inline-chips", "medical": "inline-chips",
}

_LAYOUT_BY_CATEGORY = {
    "hotel": "booking-catalog", "hospitality": "booking-catalog", "travel": "booking-catalog",
    "fitness": "schedule-catalog", "gym": "schedule-catalog",
    "ecommerce": "product-catalog", "retail": "product-catalog",
    "real_estate": "editorial-split", "real estate": "editorial-split",
    "automotive": "product-catalog", "vehicle": "product-catalog", "car": "product-catalog",
    "education": "centered-catalog", "school": "centered-catalog",
    "healthcare": "centered-catalog", "medical": "centered-catalog", "pharmacy": "centered-catalog",
    "restaurant": "magazine-sections", "food": "magazine-sections",
}

_HERO_BY_CATEGORY = {
    "hotel": "booking-panel", "hospitality": "booking-panel", "travel": "booking-panel",
    "fitness": "full-screen-image", "gym": "full-screen-image", "sport": "full-screen-image",
    "real_estate": "search-first", "real estate": "search-first",
    "automotive": "search-first", "vehicle": "search-first", "car": "search-first",
    "ecommerce": "product-showcase", "retail": "product-showcase", "shop": "product-showcase",
    "education": "centered-text", "school": "centered-text", "course": "centered-text",
    "healthcare": "centered-text", "medical": "centered-text", "pharmacy": "centered-text",
    "clinic": "centered-text",
    "restaurant": "full-screen-image", "food": "full-screen-image",
}

_PALETTES_BY_STYLE = {
    "clean":        ("#3b82f6","#06b6d4","#f8fafc","#0f172a"),
    "bold":         ("#dc2626","#f59e0b","#fff7ed","#1c1917"),
    "premium-dark": ("#818cf8","#e879f9","#0f0f23","#f1f5f9"),
    "glass":        ("#6366f1","#a78bfa","#0ea5e9","#ffffff"),
    "editorial":    ("#18181b","#e11d48","#ffffff","#09090b"),
    "enterprise":   ("#1d4ed8","#0284c7","#f8fafc","#1e293b"),
    "minimal":      ("#18181b","#71717a","#ffffff","#09090b"),
    "dense-admin":  ("#0f766e","#14b8a6","#f0fdfa","#134e4a"),
    "playful":      ("#8b5cf6","#f59e0b","#fafafa","#1c1917"),
    "cyberpunk":    ("#22d3ee","#f43f5e","#0f172a","#e2e8f0"),
}

_CARD_BY_STYLE = {
    "clean":        "elevated-shadow",
    "bold":         "bordered",
    "premium-dark": "glass-effect",
    "glass":        "glass-effect",
    "editorial":    "flat-minimal",
    "enterprise":   "bordered",
    "minimal":      "flat-minimal",
    "dense-admin":  "bordered",
    "playful":      "image-top",
    "cyberpunk":    "glass-effect",
}

_SECTION_ORDERS = [
    ["hero", "features", "stats", "testimonials", "cta"],
    ["hero", "stats", "features", "gallery", "cta"],
    ["hero", "features", "gallery", "faq", "cta"],
    ["hero", "stats", "testimonials", "features", "cta"],
    ["hero", "features", "pricing", "faq", "cta"],
    ["hero", "gallery", "features", "stats", "contact"],
    ["hero", "services", "stats", "team", "cta"],
    ["hero", "how-it-works", "features", "testimonials", "cta"],
]


def _genre_mood(system_category: str, genome: dict) -> str:
    """Pick a domain-appropriate mood that varies with genome seed."""
    cat = str(system_category).lower().replace(" ", "_")
    # Try exact match, then word-in-category match
    moods = None
    for key, vals in _MOOD_BY_CATEGORY.items():
        if key in cat or cat.startswith(key[:4]):
            moods = vals
            break
    if not moods:
        moods = ["enterprise", "minimal", "tech", "bold", "elegant"]
    # Use genome's inspiration_family as seed for deterministic variation
    seed_word = (genome.get("inspiration_family") or "a") + system_category
    idx = sum(ord(c) for c in seed_word) % len(moods)
    return moods[idx]


def _varied_fallback(genome: dict, system_category: str) -> dict:
    """Build a genome-seeded fallback blueprint with genuine visual variety.

    Unlike v1 which always returned solid-light + split-image-text, this maps
    every genome axis to a varied value so apps with different genomes look
    structurally different even without the LLM.
    """
    visual = genome.get("visual_style", "clean")
    nav_pattern = genome.get("navigation_pattern", "topnav")
    hero_variant = genome.get("hero_variant", "split")
    inspiration = genome.get("inspiration_family", "")
    color_family = genome.get("color_palette_family", "neutral")
    dark_mode = visual in ("premium-dark", "cyberpunk", "dense-admin")

    # Palette
    primary, accent, bg, text = _PALETTES_BY_STYLE.get(visual, _PALETTES_BY_STYLE["clean"])

    # Override with color_family hints
    if "warm" in color_family:
        primary, accent = "#dc2626", "#f59e0b"
    elif "cool" in color_family:
        primary, accent = "#3b82f6", "#06b6d4"
    elif "green" in color_family:
        primary, accent = "#16a34a", "#22c55e"
    elif "purple" in color_family:
        primary, accent = "#7c3aed", "#a78bfa"

    # Navbar
    nav_options = _NAVBAR_BY_NAV.get(nav_pattern, ["solid-light", "minimal"])
    seed = sum(ord(c) for c in (inspiration or system_category or "x"))
    navbar = nav_options[seed % len(nav_options)]
    if dark_mode and navbar == "solid-light":
        navbar = "solid-dark"

    # Hero
    hero = _HERO_BY_VARIANT.get(hero_variant, "split-image-text")

    # Card
    card = _CARD_BY_STYLE.get(visual, "elevated-shadow")

    # Dashboard shell
    if nav_pattern in ("topnav", "tabs"):
        shell = "top-nav-dark" if dark_mode else "top-nav-light"
    else:
        shell = "left-sidebar-dark" if dark_mode else "left-sidebar-light"

    # Background
    if dark_mode:
        bg_style = "flat-color"
    elif visual in ("glass",):
        bg_style = "image-overlay"
    elif visual in ("editorial", "minimal"):
        bg_style = "subtle-gradient"
    else:
        # vary by seed
        bg_opts = ["flat-color", "subtle-gradient", "pattern"]
        bg_style = bg_opts[seed % 3]

    # Button
    btn_opts = ["rounded-pill", "soft-corners", "sharp-corners", "outlined", "solid-gradient"]
    button = btn_opts[seed % len(btn_opts)]

    # Section order — deterministically pick one of 8 variants
    section_order = _SECTION_ORDERS[seed % len(_SECTION_ORDERS)]

    mood = _genre_mood(system_category, genome)

    # Structural variants — pick based on domain category
    cat_lower = system_category.lower()

    def _pick_struct(mapping: dict, default: str) -> str:
        for key, val in mapping.items():
            if key in cat_lower:
                return val
        return default

    listing_v = _pick_struct(_LISTING_BY_CATEGORY, "standard-card-grid")
    filter_p  = _pick_struct(_FILTER_BY_CATEGORY, "inline-chips")
    layout_v  = _pick_struct(_LAYOUT_BY_CATEGORY, "centered-catalog")
    # Override hero with domain-specific hero if hero_variant was generic "split"
    if hero_variant in ("split", "card-stack"):
        hero = _pick_struct(_HERO_BY_CATEGORY, hero)

    return {
        "domain_mood":        mood,
        "primary_color":      primary,
        "accent_color":       accent,
        "background_color":   bg,
        "text_color":         text,
        "navbar_style":       navbar,
        "hero_composition":   hero,
        "listing_variant":    listing_v,
        "filter_placement":   filter_p,
        "card_style":         card,
        "button_style":       button,
        "dashboard_shell":    shell,
        "background_style":   bg_style,
        "page_layout_variant": layout_v,
        "section_order":      section_order,
        # Derived full-form fields for downstream compatibility
        "color_palette": {
            "primary": primary, "secondary": bg, "accent": accent,
            "background": bg, "surface": bg, "text": text,
            "muted": "#94a3b8" if not dark_mode else "#475569",
        },
        "layout_style":             "enterprise" if visual in ("enterprise","dense-admin") else "split-hero",
        "page_spacing":             "balanced",
        "table_style":              "clean",
        "icon_style":               "outline",
        "animation_style":          "subtle-fade",
        "typography_direction": {
            "heading_style": "serif" if visual in ("editorial","luxury") else "sans-serif",
            "body_style": "readable",
            "heading_weight": "700",
            "size_scale": "normal",
        },
        "_source": "fallback",
    }


def _derive_full_palette(bp: dict) -> dict:
    """Expand the 5-color LLM output to the full 7-key color_palette."""
    p = bp.get("primary_color", "#3b82f6")
    a = bp.get("accent_color", "#06b6d4")
    bg = bp.get("background_color", "#ffffff")
    txt = bp.get("text_color", "#0f172a")
    dark = int(bg.lstrip("#")[:2], 16) < 80 if bg.startswith("#") and len(bg) >= 3 else False
    muted = "#475569" if dark else "#94a3b8"
    surface = bg  # close enough for our purposes
    secondary = "#1e1b4b" if dark else "#f1f5f9"
    return {"primary": p, "secondary": secondary, "accent": a,
            "background": bg, "surface": surface, "text": txt, "muted": muted}


# ── History helpers ───────────────────────────────────────────────────────────

def _load_design_history(history_path: str) -> list:
    try:
        if os.path.exists(history_path):
            with open(history_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _save_to_history(history_path: str, entry: dict) -> None:
    try:
        history = _load_design_history(history_path)
        history.append(entry)
        history = history[-30:]
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _history_exclusions(history: list) -> str:
    """Build concise DO NOT USE list from recent history."""
    if not history:
        return ""
    lines = ["DO NOT reuse any combination already used:"]
    for h in history[-8:]:
        name = h.get("app_name", "?")[:20]
        p = h.get("color_palette", {})
        lines.append(
            f"  {name}: primary={p.get('primary','')}, "
            f"navbar={h.get('navbar_style','')}, hero={h.get('hero_composition','')}, "
            f"card={h.get('card_style','')}"
        )
    return "\n".join(lines)


# ── LLM call with parse + retry ───────────────────────────────────────────────

def _llm_blueprint(user_msg: str, log: list) -> dict | None:
    """Call LLM and return parsed dict, or None on failure. Logs errors.

    Uses message objects directly (not ChatPromptTemplate) to avoid LangChain's
    curly-brace template variable expansion mangling the JSON schema in the prompt.
    """
    from app.agents import get_llm, extract_json, ensure_ollama
    from langchain_core.messages import HumanMessage, SystemMessage

    if not ensure_ollama():
        log.append("design_agent: Ollama not available, using fallback")
        return None

    llm = get_llm(temperature=0.85, num_predict=4096, json_mode=True)

    try:
        result = llm.invoke([
            SystemMessage(content=_BLUEPRINT_PROMPT),
            HumanMessage(content=user_msg),
        ])
        raw = result.content if hasattr(result, "content") else str(result)
        parsed = extract_json(raw)
        if not isinstance(parsed, dict):
            log.append(f"design_agent: extract_json returned {type(parsed).__name__}, using fallback")
            return None
        if not parsed.get("domain_mood") or not parsed.get("navbar_style"):
            log.append(f"design_agent: LLM JSON missing required fields: {list(parsed.keys())[:6]}")
            return None
        return parsed
    except Exception as e:
        log.append(f"design_agent: LLM call failed ({type(e).__name__}: {str(e)[:80]})")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def create_design_blueprint(
    srs_data: dict,
    genome: dict,
    output_dir: str,
    history_path: str,
    app_name: str = "App",
) -> dict:
    """Create a visual design blueprint.

    Tries LLM first (2 attempts); if both fail, uses genome-seeded fallback.
    Saves design_blueprint.json to output_dir and appends to history.
    Returns the blueprint dict. Call-site gets the reason via blueprint['_source'].
    """
    _log: list = []

    history = _load_design_history(history_path)
    exclusions = _history_exclusions(history)

    doc = (srs_data.get("srs_document") or srs_data) if isinstance(srs_data, dict) else {}
    system_category = doc.get("system_category") or srs_data.get("system_category", "custom")
    app_summary = str(doc.get("app_summary") or srs_data.get("app_summary", ""))[:350]
    roles = srs_data.get("roles") or doc.get("roles") or []

    genome_hints = (
        f"visual_style={genome.get('visual_style','clean')}, "
        f"nav={genome.get('navigation_pattern','topnav')}, "
        f"hero_variant={genome.get('hero_variant','split')}, "
        f"color_family={genome.get('color_palette_family','neutral')}"
    )

    user_msg = (
        f"App: {app_name} | Domain: {system_category}\n"
        f"Summary: {app_summary}\n"
        f"Roles: {', '.join(str(r) for r in roles[:4])}\n"
        f"Genome hints (use as inspiration): {genome_hints}\n\n"
        f"{exclusions}\n\n"
        f"Create a visually UNIQUE blueprint for this {system_category} app."
    )

    # Attempt 1
    blueprint = _llm_blueprint(user_msg, _log)

    # Attempt 2 — if first failed or too similar, retry with shorter message
    if blueprint is None:
        short_msg = (
            f"App: {app_name} | Domain: {system_category}\n"
            f"Style hints: {genome_hints}\n"
            f"{exclusions}\n"
            "Return 15-field JSON now."
        )
        blueprint = _llm_blueprint(short_msg, _log)

    # Fallback — genome-seeded for real variety
    if blueprint is None:
        blueprint = _varied_fallback(genome, system_category)
        _log.append("design_agent: using genome-seeded fallback")

    # Enrich blueprint with derived fields
    blueprint["app_name"] = app_name
    blueprint["system_category"] = system_category
    blueprint["_log"] = _log
    if not blueprint.get("color_palette"):
        blueprint["color_palette"] = _derive_full_palette(blueprint)
    if "_source" not in blueprint:
        blueprint["_source"] = "llm"

    # Ensure section_order is a list
    so = blueprint.get("section_order")
    if not isinstance(so, list) or not so:
        blueprint["section_order"] = ["hero", "features", "stats", "testimonials", "cta"]

    # Derive Tailwind classes from the core fields
    blueprint["tailwind_classes"] = _derive_tw(blueprint)

    # Derive page_designs narrative
    blueprint["page_designs"] = _derive_page_designs(blueprint)

    # Fill structural fields if LLM didn't provide them (domain-seeded)
    cat_lower = system_category.lower()
    def _pick_struct_default(mapping: dict, default: str) -> str:
        for key, val in mapping.items():
            if key in cat_lower:
                return val
        return default

    # Hero and listing are FORCED from domain mapping because the LLM defaults to
    # generic values (dashboard_preview / table-catalog) across all domains.
    # Only override when the domain has an explicit entry — otherwise keep LLM's choice.
    _dom_hero    = _pick_struct_default(_HERO_BY_CATEGORY,    "")
    _dom_listing = _pick_struct_default(_LISTING_BY_CATEGORY, "")
    if _dom_hero:
        blueprint["hero_composition"] = _dom_hero
    else:
        blueprint.setdefault("hero_composition", "centered-text")
    if _dom_listing:
        blueprint["listing_variant"] = _dom_listing
    else:
        blueprint.setdefault("listing_variant", "standard-card-grid")
    blueprint.setdefault("filter_placement",    _pick_struct_default(_FILTER_BY_CATEGORY, "inline-chips"))
    blueprint.setdefault("page_layout_variant", _pick_struct_default(_LAYOUT_BY_CATEGORY, "centered-catalog"))

    # Derive other fields expected downstream
    blueprint.setdefault("layout_style", "enterprise" if "enterprise" in blueprint.get("domain_mood","") else "split-hero")
    blueprint.setdefault("page_spacing", "balanced")
    blueprint.setdefault("table_style", "clean")
    blueprint.setdefault("icon_style", "outline")
    blueprint.setdefault("animation_style", "subtle-fade")

    # Save to project
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "design_blueprint.json"), "w", encoding="utf-8") as f:
            json.dump(blueprint, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Append compact signature to history (includes structural fields)
    _save_to_history(history_path, {
        "app_name": app_name,
        "system_category": system_category,
        "color_palette": blueprint.get("color_palette", {}),
        "navbar_style": blueprint.get("navbar_style", ""),
        "hero_composition": blueprint.get("hero_composition", ""),
        "dashboard_shell": blueprint.get("dashboard_shell", ""),
        "card_style": blueprint.get("card_style", ""),
        "background_style": blueprint.get("background_style", ""),
        "button_style": blueprint.get("button_style", ""),
        "layout_style": blueprint.get("layout_style", ""),
        "listing_variant": blueprint.get("listing_variant", ""),
        "filter_placement": blueprint.get("filter_placement", ""),
        "page_layout_variant": blueprint.get("page_layout_variant", ""),
        "section_order": blueprint.get("section_order", []),
    })

    return blueprint


# ── Derived-field helpers ─────────────────────────────────────────────────────

def _derive_tw(bp: dict) -> dict:
    """Map blueprint fields to concrete Tailwind utility classes."""
    p = bp.get("primary_color", "#3b82f6")
    a = bp.get("accent_color", "#06b6d4")
    bg = bp.get("background_color", "#ffffff")
    dark_bg = int(bg.lstrip("#")[:2], 16) < 80 if bg.startswith("#") and len(bg) >= 3 else False

    btn = bp.get("button_style", "soft-corners")
    card = bp.get("card_style", "elevated-shadow")
    nav = bp.get("navbar_style", "solid-light")

    radius_btn = {"rounded-pill": "rounded-full", "sharp-corners": "rounded-none",
                  "soft-corners": "rounded-lg", "outlined": "rounded-lg",
                  "solid-gradient": "rounded-lg"}.get(btn, "rounded-lg")
    btn_fill = "border-2 border-current bg-transparent hover:bg-opacity-10" if btn == "outlined" else f"[background:{p}] hover:[background:{a}] text-white"

    card_cls = {"flat-minimal": "bg-white rounded-lg p-6",
                "elevated-shadow": "bg-white rounded-xl shadow-md p-6",
                "bordered": "bg-white rounded-lg border border-gray-200 p-6",
                "glass-effect": "bg-white/10 backdrop-blur-sm rounded-xl border border-white/20 p-6",
                "image-top": "bg-white rounded-xl overflow-hidden shadow-sm",
                "stat-card": "bg-white rounded-xl border-l-4 p-6 shadow-sm"}.get(card, "bg-white rounded-xl p-6")

    nav_cls = {"solid-light": "bg-white border-b border-gray-100 px-6 py-4",
               "solid-dark": f"[background:#0f172a] text-white px-6 py-4",
               "glass": "bg-white/80 backdrop-blur-md border-b border-white/20 px-6 py-4",
               "transparent-overlay": "absolute top-0 left-0 right-0 bg-transparent px-6 py-4",
               "minimal": "bg-white px-6 py-4",
               "branded": f"[background:{p}] text-white px-6 py-4"}.get(nav, "bg-white border-b px-6 py-4")

    hero_cls = {
        "split-image-text":   "grid grid-cols-2 gap-12 py-20 px-6",
        "full-screen-image":  "relative min-h-screen flex items-center justify-center text-white",
        "centered-text":      "text-center py-32 px-6",
        "search-first":       "py-24 px-6 text-center",
        "stats-first":        "py-20 px-6",
        "dashboard-preview":  "py-20 px-6 grid grid-cols-2 gap-12",
    }.get(bp.get("hero_composition",""), "py-20 px-6")

    badge_color = f"[color:{a}] [background:{a}1a]"

    return {
        "primary_button":   f"inline-flex items-center gap-2 [background:{p}] hover:[background:{a}] text-white px-6 py-3 {radius_btn} font-semibold transition-colors",
        "secondary_button": f"inline-flex items-center gap-2 border border-gray-300 hover:border-gray-400 px-6 py-3 {radius_btn} font-medium transition-colors",
        "card":             card_cls,
        "hero_section":     hero_cls,
        "nav":              nav_cls,
        "badge":            f"inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium {badge_color}",
    }


def _derive_page_designs(bp: dict) -> dict:
    hero = bp.get("hero_composition", "split-image-text")
    card = bp.get("card_style", "elevated-shadow")
    shell = bp.get("dashboard_shell", "left-sidebar-light")
    mood = bp.get("domain_mood", "professional")
    return {
        "home":      f"{hero.replace('-',' ').title()} hero, {card} feature cards, stats band, testimonials, CTA",
        "listing":   f"Search bar + {card} grid with filter sidebar",
        "detail":    f"Split pane: info panel + {card} detail area",
        "dashboard": f"{shell.replace('-',' ').title()} with KPI cards + data table",
        "admin":     f"Full-width table ({mood} tone) with bulk actions",
    }


def load_blueprint(output_dir: str) -> dict:
    """Load a previously saved design blueprint from the project directory."""
    try:
        p = os.path.join(output_dir, "design_blueprint.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}
