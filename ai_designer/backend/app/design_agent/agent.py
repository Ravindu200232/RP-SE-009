"""Part of the `design_agent` package (auto-split, verbatim). See design_agent/__init__.py."""
import json
import os
import random
from ._derive import _derive_page_designs, _derive_tw
from ._fallback import _derive_full_palette, _varied_fallback
from ._history import _history_exclusions, _load_design_history, _save_to_history
from ._maps import _BLUEPRINT_PROMPT, _FILTER_BY_CATEGORY, _HERO_BY_CATEGORY, _LAYOUT_BY_CATEGORY, _LISTING_BY_CATEGORY

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
