"""App Understanding Layer (Part A) + Design Genome (Part B).

Works for ANY prompt - not a fixed hospital/hotel/POS list. `infer_app_understanding`
classifies the prompt into a category + domain via keyword inference (falling back to
"custom" and inferring from the prompt). `make_genome` then produces a SEEDED, anti-
similarity-scored structural genome so the same prompt generated twice yields a
STRUCTURALLY different app (different layout family, navigation, dashboard, CRUD style,
section order) - not just different colours/content. The genome is stored in project
metadata so future generations can avoid repeating recent structures.
"""
import json
import os
import random

# ---- Part B option spaces (the structural axes) ----
LAYOUT_FAMILIES = ["portal-first", "dashboard-first", "marketing-first", "admin-first",
                   "workflow-first", "marketplace", "content-first", "mobile-first", "command-center"]
NAV_PATTERNS = ["topnav", "sidebar", "split-nav", "tabs", "command-palette", "stepper", "mobile-bottom-nav"]
PAGE_STRATEGIES = ["landing-heavy", "dashboard-heavy", "workflow-heavy", "data-heavy", "content-heavy", "booking-heavy"]
DASHBOARD_STYLES = ["kpi-cards", "table-first", "kanban", "calendar", "analytics", "activity-feed", "split-pane", "map-based"]
CRUD_STYLES = ["table-dense", "card-grid", "split-pane", "wizard", "kanban", "timeline", "calendar"]
SECTION_STRATEGIES = ["storytelling", "conversion", "operations", "directory", "analytics", "community", "productized-service"]
VISUAL_STYLES = ["clean", "bold", "premium-dark", "glass", "editorial", "playful", "enterprise", "minimal", "dense-admin"]
DENSITIES = ["compact", "balanced", "spacious"]
INTERACTION_STYLES = ["modal-heavy", "inline-edit", "wizard-flow", "bulk-actions", "command-actions"]
HERO_VARIANTS = ["split", "full-image", "dashboard-preview", "search-booking", "stats-first", "card-stack", "editorial"]
NAV_VARIANTS = ["centered topnav", "action topnav", "sidebar", "floating nav", "utility bar"]
SECTION_VARIANTS = ["feature cards", "icon grid", "split image/text", "stats band", "timeline", "portal preview", "gallery", "FAQ", "CTA"]
CARD_STYLES = ["flat", "bordered", "glass", "shadow", "image-card", "stat-card"]
LAYOUT_RHYTHMS = ["compact", "spacious", "editorial", "image-heavy", "data-heavy"]
IMAGE_STRATEGIES = ["hero image", "section images", "gallery", "dashboard mockup", "no-image fallback"]
CTA_PLACEMENTS = ["hero-primary", "hero-split", "floating", "after-stats", "section-end", "nav-cta"]

_AXES = ["layout_family", "navigation_pattern", "page_strategy", "dashboard_style",
         "crud_style", "section_strategy", "visual_style", "density", "interaction_style",
         "hero_variant", "nav_variant", "section_variant", "card_style",
         "layout_rhythm", "image_strategy", "cta_placement", "inspiration_family"]
_SIG_AXES = ["layout_family", "navigation_pattern", "page_strategy", "dashboard_style",
             "crud_style", "section_strategy", "hero_variant", "nav_variant",
             "section_variant", "card_style", "layout_rhythm", "image_strategy", "cta_placement",
             "inspiration_family"]

# category -> per-axis PREFERENCES (bias only; never the sole option, so apps still vary)
_BIAS = {
    "booking":     {"page_strategy": ["booking-heavy"], "dashboard_style": ["calendar"], "crud_style": ["calendar", "timeline"],
                    "hero_variant": ["search-booking", "card-stack"], "section_variant": ["timeline", "feature cards"],
                    "image_strategy": ["hero image", "section images"], "cta_placement": ["hero-primary", "floating"]},
    "marketplace": {"layout_family": ["marketplace"], "crud_style": ["card-grid"], "section_strategy": ["directory"], "page_strategy": ["content-heavy"],
                    "hero_variant": ["card-stack", "full-image"], "section_variant": ["gallery", "feature cards"],
                    "card_style": ["image-card", "shadow"], "image_strategy": ["gallery", "section images"]},
    "education":   {"page_strategy": ["workflow-heavy"], "dashboard_style": ["activity-feed", "kpi-cards"], "crud_style": ["card-grid", "timeline"],
                    "hero_variant": ["editorial", "dashboard-preview"], "section_variant": ["timeline", "portal preview"],
                    "layout_rhythm": ["editorial", "spacious"]},
    "healthcare":  {"layout_family": ["portal-first", "workflow-first"], "dashboard_style": ["activity-feed", "kpi-cards"], "crud_style": ["split-pane", "table-dense"],
                    "hero_variant": ["search-booking", "stats-first", "split"], "section_variant": ["portal preview", "stats band", "feature cards"],
                    "nav_variant": ["utility bar", "action topnav"], "image_strategy": ["hero image", "dashboard mockup", "section images"]},
    "finance":     {"page_strategy": ["data-heavy"], "dashboard_style": ["analytics", "kpi-cards"], "crud_style": ["table-dense"], "visual_style": ["enterprise", "premium-dark"],
                    "hero_variant": ["dashboard-preview", "stats-first"], "section_variant": ["stats band", "portal preview"],
                    "card_style": ["stat-card", "bordered"], "layout_rhythm": ["data-heavy", "compact"], "image_strategy": ["dashboard mockup"]},
    "inventory":   {"page_strategy": ["data-heavy"], "dashboard_style": ["table-first", "kpi-cards"], "crud_style": ["table-dense", "split-pane"], "density": ["compact"],
                    "hero_variant": ["dashboard-preview", "stats-first"], "section_variant": ["timeline", "stats band"],
                    "layout_rhythm": ["compact", "data-heavy"], "image_strategy": ["dashboard mockup", "no-image fallback"]},
    "content":     {"layout_family": ["content-first"], "page_strategy": ["content-heavy"], "section_strategy": ["storytelling"], "visual_style": ["editorial"],
                    "hero_variant": ["editorial", "full-image"], "section_variant": ["split image/text", "gallery"],
                    "layout_rhythm": ["editorial", "image-heavy"], "image_strategy": ["hero image", "section images"]},
    "social":      {"layout_family": ["mobile-first"], "dashboard_style": ["activity-feed"], "section_strategy": ["community"], "interaction_style": ["inline-edit"],
                    "hero_variant": ["card-stack", "full-image"], "section_variant": ["gallery", "feature cards"],
                    "card_style": ["glass", "shadow"]},
    "internal_tool": {"layout_family": ["admin-first", "command-center"], "navigation_pattern": ["sidebar", "command-palette"], "dashboard_style": ["table-first", "split-pane"], "visual_style": ["dense-admin", "enterprise"], "density": ["compact"],
                      "hero_variant": ["dashboard-preview", "stats-first"], "nav_variant": ["sidebar", "utility bar"],
                      "section_variant": ["portal preview", "stats band"], "layout_rhythm": ["compact", "data-heavy"], "image_strategy": ["dashboard mockup", "no-image fallback"]},
    "business":    {"layout_family": ["marketing-first", "dashboard-first"], "section_strategy": ["conversion", "productized-service"],
                    "hero_variant": ["split", "dashboard-preview", "card-stack"], "section_variant": ["feature cards", "portal preview"],
                    "nav_variant": ["action topnav", "floating nav"]},
    # ── Extended biases for new 14 categories ──
    "public_website":    {"layout_family": ["marketing-first", "content-first"], "section_strategy": ["storytelling", "conversion"], "visual_style": ["editorial", "clean"],
                          "hero_variant": ["full-image", "editorial", "split"], "section_variant": ["split image/text", "gallery", "feature cards"],
                          "layout_rhythm": ["editorial", "image-heavy", "spacious"], "image_strategy": ["hero image", "section images", "gallery"],
                          "cta_placement": ["hero-primary", "section-end"]},
    "ecommerce":         {"layout_family": ["marketplace", "marketing-first"], "crud_style": ["card-grid"], "section_strategy": ["directory", "conversion"],
                          "hero_variant": ["card-stack", "full-image"], "section_variant": ["gallery", "feature cards"],
                          "card_style": ["image-card", "shadow"], "image_strategy": ["gallery", "section images"],
                          "cta_placement": ["hero-primary", "floating", "after-stats"]},
    "business_erp":      {"layout_family": ["admin-first", "dashboard-first"], "navigation_pattern": ["sidebar", "topnav"], "dashboard_style": ["table-first", "kpi-cards"], "visual_style": ["enterprise", "clean"],
                          "crud_style": ["table-dense", "split-pane"], "hero_variant": ["dashboard-preview", "stats-first"],
                          "section_variant": ["stats band", "portal preview"], "layout_rhythm": ["compact", "data-heavy"],
                          "image_strategy": ["dashboard mockup", "no-image fallback"]},
    "admin_dashboard":   {"layout_family": ["admin-first", "command-center"], "navigation_pattern": ["sidebar"], "dashboard_style": ["table-first", "analytics", "kpi-cards"],
                          "visual_style": ["dense-admin", "enterprise"], "density": ["compact"],
                          "hero_variant": ["dashboard-preview", "stats-first"], "nav_variant": ["sidebar", "utility bar"],
                          "layout_rhythm": ["compact", "data-heavy"], "image_strategy": ["dashboard mockup"]},
    "content_management":{"layout_family": ["content-first"], "page_strategy": ["content-heavy"], "section_strategy": ["storytelling"], "visual_style": ["editorial"],
                          "hero_variant": ["editorial", "full-image"], "section_variant": ["split image/text", "gallery", "timeline"],
                          "layout_rhythm": ["editorial", "image-heavy"]},
    "service_marketplace":{"layout_family": ["marketplace"], "crud_style": ["card-grid"], "section_strategy": ["directory", "conversion"],
                           "hero_variant": ["search-booking", "card-stack"], "section_variant": ["gallery", "feature cards"],
                           "card_style": ["image-card", "shadow"], "image_strategy": ["gallery", "section images"]},
    "logistics":         {"layout_family": ["dashboard-first", "admin-first"], "dashboard_style": ["map-based", "table-first"], "visual_style": ["enterprise"],
                          "crud_style": ["table-dense", "split-pane"], "hero_variant": ["dashboard-preview", "stats-first"],
                          "section_variant": ["stats band", "portal preview"], "layout_rhythm": ["data-heavy", "compact"]},
    "real_estate":       {"layout_family": ["content-first", "marketplace"], "page_strategy": ["content-heavy"], "visual_style": ["editorial", "clean"],
                          "hero_variant": ["full-image", "search-booking"], "section_variant": ["gallery", "split image/text"],
                          "card_style": ["image-card", "shadow"], "image_strategy": ["gallery", "hero image", "section images"],
                          "layout_rhythm": ["image-heavy", "spacious"]},
    "government":        {"layout_family": ["portal-first", "marketing-first"], "visual_style": ["enterprise", "clean"],
                          "hero_variant": ["split", "stats-first"], "section_variant": ["feature cards", "stats band"],
                          "nav_variant": ["action topnav", "utility bar"], "layout_rhythm": ["spacious"]},
    "entertainment":     {"layout_family": ["content-first", "mobile-first"], "visual_style": ["premium-dark", "bold"], "page_strategy": ["content-heavy"],
                          "hero_variant": ["full-image", "card-stack"], "section_variant": ["gallery", "feature cards"],
                          "card_style": ["image-card", "glass"], "image_strategy": ["gallery", "hero image", "section images"]},
    "ai_automation":     {"layout_family": ["dashboard-first", "marketing-first"], "visual_style": ["premium-dark", "glass", "bold"],
                          "hero_variant": ["dashboard-preview", "card-stack"], "section_variant": ["feature cards", "portal preview"],
                          "nav_variant": ["floating nav", "action topnav"], "image_strategy": ["dashboard mockup", "no-image fallback"]},
    "security":          {"layout_family": ["admin-first", "portal-first"], "visual_style": ["enterprise", "premium-dark"],
                          "hero_variant": ["dashboard-preview", "stats-first"], "section_variant": ["stats band", "portal preview"],
                          "layout_rhythm": ["compact", "data-heavy"]},
    "internal_portal":   {"layout_family": ["portal-first", "dashboard-first"], "navigation_pattern": ["sidebar"], "visual_style": ["enterprise", "clean"],
                          "hero_variant": ["dashboard-preview"], "section_variant": ["portal preview", "stats band"],
                          "layout_rhythm": ["compact"]},
    "hybrid_app":        {"layout_family": ["marketing-first", "dashboard-first"], "section_strategy": ["conversion", "productized-service"],
                          "hero_variant": ["split", "dashboard-preview"], "section_variant": ["feature cards", "portal preview"]},
}

_CATEGORY_KEYWORDS = {
    # ── Original 10 categories ──
    "booking": ["book", "reservation", "appointment", "schedule", "availability", "rental", "salon", "hotel", "table", "slot", "coworking", "sports booking"],
    "marketplace": ["marketplace", "seller", "buyer", "listing", "vendor", "ecommerce", "classified", "auction", "storefront", "gig", "freelance marketplace"],
    "education": ["course", "student", "teacher", "school", "lms", "exam", "assignment", "lesson", "tutor", "learning", "quiz", "flashcard", "e-library"],
    "healthcare": ["patient", "hospital", "clinic", "medical", "doctor", "pharmacy", "lab", "health record", "telehealth", "dental", "veterinary", "telemedicine"],
    "finance": ["bank", "loan", "payment", "invoice", "budget", "accounting", "wallet", "trading", "fintech", "microloan", "insurance", "crypto", "tax"],
    "inventory": ["inventory", "stock", "warehouse", "supplier", "sku", "procurement", "logistics", "fulfilment", "shipment", "spare parts"],
    "content": ["blog", "cms", "article", "news", "magazine", "publishing", "portfolio", "newsletter", "podcast", "wiki", "knowledge base", "documentation"],
    "social": ["social", "community", "feed", "forum", "network", "follow", "messaging", "chat app", "dating", "alumni", "fan club", "review platform"],
    "internal_tool": ["internal", "admin panel", "crm", "erp", "back office", "ops dashboard", "staff portal", "ticketing", "admin dashboard", "intranet"],
    "business": ["business", "agency", "saas", "b2b", "platform", "service company", "startup", "corporate website", "company website"],
    # ── Extended — new 10 categories aligned to app_taxonomy ──
    "public_website": ["landing page", "company website", "portfolio website", "personal blog", "restaurant website", "hotel website", "law firm", "wedding website", "gym website", "event website", "non-profit", "ngo"],
    "ecommerce": ["online store", "fashion store", "electronics store", "grocery delivery", "food ordering", "pharmacy store", "book store", "dropshipping", "print-on-demand", "subscription box", "b2b wholesale"],
    "business_erp": ["erp system", "pos system", "hrm system", "payroll", "attendance system", "project management", "task management", "asset management", "document management", "expense management"],
    "admin_dashboard": ["admin dashboard", "super admin", "user management", "role permission", "api monitoring", "server monitoring", "business intelligence dashboard", "cms dashboard"],
    "content_management": ["content management", "blog management", "news publishing", "article publishing", "media library", "video upload", "podcast platform", "photo gallery", "digital magazine", "help center"],
    "service_marketplace": ["service marketplace", "home service", "tutor finder", "doctor finder", "lawyer finder", "cleaning service", "delivery service platform", "job marketplace", "consultant booking", "local business directory"],
    "logistics": ["delivery management", "courier tracking", "fleet management", "vehicle tracking", "taxi booking", "cargo management", "route planning", "driver management", "fuel management", "transport"],
    "real_estate": ["real estate", "property management", "rental management", "tenant portal", "land sales", "house rental", "property agent", "real estate marketplace", "construction project", "mortgage"],
    "government": ["citizen service", "government", "municipal", "public service", "complaint management", "permit application", "taxpayer portal", "police complaint", "court case", "land registry"],
    "entertainment": ["video streaming", "music streaming", "gaming community", "online radio", "podcast hosting", "live score", "entertainment", "anime", "sports news", "fan club"],
    "ai_automation": ["ai chatbot", "ai tool", "ai platform", "artificial intelligence", "machine learning", "generative ai", "llm", "gpt", "ai resume", "ai code", "ai image generator", "ai writing"],
    "security": ["rbac", "role-based access", "two-factor authentication", "audit log", "identity verification", "visitor management", "access control", "user permission"],
    "internal_portal": ["employee portal", "staff portal", "client portal", "vendor portal", "partner portal", "franchise portal", "intranet", "knowledge sharing portal", "internal helpdesk"],
    "hybrid_app": ["website with admin", "ecommerce with pos", "hospital with patient", "school with student", "restaurant with ordering", "saas with dashboard"],
}


def infer_app_understanding(prompt: str) -> dict:
    """Classify ANY prompt -> the App Understanding schema (Part A).

    Uses the full 24-category keyword map (10 original + 14 extended) for best
    coverage of the 300+ app types. Falls back to app_taxonomy.classify() for
    a more granular reading, then populates the standard schema fields.
    """
    p = " " + (prompt or "").lower() + " "

    # Score each category by keyword hits (weighted by length = specificity)
    best_cat, best_score = "custom", 0
    for cat_id, kws in _CATEGORY_KEYWORDS.items():
        score = sum(len(k) for k in kws if k in p)
        if score > best_score:
            best_score, best_cat = score, cat_id

    category = best_cat if best_score > 0 else "custom"

    # Use app_taxonomy for fine-grained classification if available
    try:
        from app import app_taxonomy as _tx
        cls = _tx.classify(prompt)
        # If taxonomy found a specific category, prefer it (it has better weights)
        if cls["category_id"] != "saas" or best_score == 0:
            category = cls["category_id"]
        design_family = cls["design_family"]
        app_type_label = cls["app_type"]
    except Exception:
        design_family = "saas"
        app_type_label = category

    words = [w for w in __import__("re").findall(r"[a-z]{3,}", p)
             if w not in ("the", "and", "for", "with", "app", "application", "build", "create", "make", "that", "this", "want")]
    domain = " ".join(words[:4]) if category == "custom" else category
    internal = any(k in p for k in ("internal", "admin", "staff", "back office", "ops", "employee", "dashboard only"))
    public = any(k in p for k in ("public", "marketing", "landing", "customers", "marketplace", "storefront", "website"))
    pvp = "internal" if internal and not public else ("public" if public and not internal else "hybrid")
    complexity = "advanced" if len(p) > 240 or p.count(",") >= 5 else ("simple" if len(p) < 60 else "medium")
    return {
        "app_category": category,
        "domain": domain.strip() or "custom",
        "primary_users": [], "user_roles": [], "core_workflows": [], "main_entities": [],
        "data_relationships": [], "required_pages": [], "dashboard_needs": [],
        "public_vs_private": pvp,
        "app_complexity": complexity,
        "business_goal": "", "design_tone": design_family, "unique_angle": app_type_label,
    }


def _pick(rng, axis, options, category):
    pref = _BIAS.get(category, {}).get(axis)
    if pref and rng.random() < 0.6:
        return rng.choice(pref)
    return rng.choice(options)


def _roll(rng, category) -> dict:
    return {
        "layout_family": _pick(rng, "layout_family", LAYOUT_FAMILIES, category),
        "navigation_pattern": _pick(rng, "navigation_pattern", NAV_PATTERNS, category),
        "page_strategy": _pick(rng, "page_strategy", PAGE_STRATEGIES, category),
        "dashboard_style": _pick(rng, "dashboard_style", DASHBOARD_STYLES, category),
        "crud_style": _pick(rng, "crud_style", CRUD_STYLES, category),
        "section_strategy": _pick(rng, "section_strategy", SECTION_STRATEGIES, category),
        "visual_style": _pick(rng, "visual_style", VISUAL_STYLES, category),
        "density": _pick(rng, "density", DENSITIES, category),
        "interaction_style": _pick(rng, "interaction_style", INTERACTION_STYLES, category),
        "hero_variant": _pick(rng, "hero_variant", HERO_VARIANTS, category),
        "nav_variant": _pick(rng, "nav_variant", NAV_VARIANTS, category),
        "section_variant": _pick(rng, "section_variant", SECTION_VARIANTS, category),
        "card_style": _pick(rng, "card_style", CARD_STYLES, category),
        "layout_rhythm": _pick(rng, "layout_rhythm", LAYOUT_RHYTHMS, category),
        "image_strategy": _pick(rng, "image_strategy", IMAGE_STRATEGIES, category),
        "cta_placement": _pick(rng, "cta_placement", CTA_PLACEMENTS, category),
    }


def _section_variant_sequence(genome: dict, rng) -> list:
    """A concrete section-component family sequence. This is intentionally
    separate from section_strategy: the strategy decides the story arc, while
    these families decide how each section is visually built."""
    primary = genome.get("section_variant", "feature cards")
    rhythm = genome.get("layout_rhythm", "spacious")
    image = genome.get("image_strategy", "hero image")
    pool = [primary]
    if image in ("gallery", "section images", "hero image"):
        pool += ["split image/text", "gallery"]
    if rhythm in ("data-heavy", "compact"):
        pool += ["stats band", "portal preview", "timeline"]
    if genome.get("section_strategy") in ("conversion", "productized-service"):
        pool += ["feature cards", "FAQ", "CTA"]
    if genome.get("section_strategy") in ("storytelling", "community"):
        pool += ["split image/text", "timeline", "gallery"]
    pool += ["feature cards", "icon grid", "stats band", "portal preview", "timeline", "FAQ"]
    dedup = list(dict.fromkeys(x for x in pool if x in SECTION_VARIANTS))
    rng.shuffle(dedup)
    if primary in dedup:
        dedup.remove(primary)
    return [primary] + dedup[:4]


def _dna_inspiration_family(record: dict) -> str:
    family = str((record or {}).get("design_family", "")).lower()
    category = str((record or {}).get("category", "")).lower()
    hay = family + " " + category
    if any(x in hay for x in ("healthcare", "clinical", "medical", "hospital", "patient")):
        return "healthcare-trust-saas"
    if any(x in hay for x in ("vehicle", "automotive", "commerce", "product", "marketplace", "catalog", "showroom")):
        return "ecommerce-product"
    if any(x in hay for x in ("ai", "developer", "technical", "code", "api")):
        return "ai-devtools"
    if any(x in hay for x in ("education", "course", "learning", "media")):
        return "education-media"
    if any(x in hay for x in ("finance", "fintech", "transaction", "ledger")):
        return "fintech-trust"
    if any(x in hay for x in ("pos", "erp", "business", "operations", "resource", "admin")):
        return "operational-business"
    if any(x in hay for x in ("portfolio", "agency", "creative", "studio", "editorial")):
        return "creative-agency"
    if any(x in hay for x in ("restaurant", "travel", "fitness", "wellness", "real-estate", "real estate", "property", "listing", "agent-trust", "destination")):
        return "ecommerce-product"
    return "healthcare-trust-saas"


def _map_dna_hero(patterns: list[str]) -> str:
    text = " ".join(patterns or []).lower()
    if any(x in text for x in ("search", "booking", "appointment", "reservation", "availability", "doctor", "property")):
        return "search-booking"
    if any(x in text for x in ("full-image", "immersive", "image hero", "destination", "showroom", "vehicle spotlight")):
        return "full-image"
    if any(x in text for x in ("dashboard", "portal", "console", "code workspace", "terminal", "workbench")):
        return "dashboard-preview"
    if any(x in text for x in ("metric", "stats", "security proof")):
        return "stats-first"
    if any(x in text for x in ("card stack", "community cards", "feed preview")):
        return "card-stack"
    if any(x in text for x in ("editorial", "story", "statement")):
        return "editorial"
    return "split"


def _map_dna_nav(patterns: list[str]) -> str:
    text = " ".join(patterns or []).lower()
    if "sidebar" in text:
        return "sidebar"
    if "utility" in text:
        return "utility bar"
    if "floating" in text:
        return "floating nav"
    if any(x in text for x in ("action", "commerce", "booking", "search", "inventory")):
        return "action topnav"
    return "centered topnav"


def _map_dna_card(patterns: list[str]) -> str:
    text = " ".join(patterns or []).lower()
    if "glass" in text:
        return "glass"
    if any(x in text for x in ("image", "product", "vehicle", "listing", "menu", "course", "trip", "program", "gallery")):
        return "image-card"
    if any(x in text for x in ("stat", "security", "transaction", "price", "metric")):
        return "stat-card"
    if "shadow" in text:
        return "shadow"
    if any(x in text for x in ("flat", "minimal", "table")):
        return "flat"
    return "bordered"


def _map_dna_cta(patterns: list[str]) -> str:
    text = " ".join(patterns or []).lower()
    if "nav" in text:
        return "nav-cta"
    if "floating" in text:
        return "floating"
    if "after" in text or "stats" in text:
        return "after-stats"
    if "split" in text:
        return "hero-split"
    if "section" in text:
        return "section-end"
    return "hero-primary"


def _map_dna_sections(patterns: list[str]) -> list[str]:
    out = []
    for pattern in patterns or []:
        p = str(pattern).lower()
        if "faq" in p:
            val = "FAQ"
        elif "cta" in p:
            val = "CTA"
        elif any(x in p for x in ("gallery", "listing", "inventory", "destination", "menu", "collection")):
            val = "gallery"
        elif any(x in p for x in ("timeline", "flow", "path", "schedule", "booking")):
            val = "timeline"
        elif any(x in p for x in ("stats", "metric", "progress", "proof", "band")):
            val = "stats band"
        elif any(x in p for x in ("portal", "dashboard", "preview", "api", "code", "console")):
            val = "portal preview"
        elif any(x in p for x in ("split", "image/text", "editorial")):
            val = "split image/text"
        elif "grid" in p and "icon" in p:
            val = "icon grid"
        else:
            val = "feature cards"
        if val not in out:
            out.append(val)
    return (out + ["feature cards", "stats band", "FAQ", "CTA"])[:5]


def _map_dna_visual_style(record: dict) -> str:
    hay = " ".join([
        str(record.get("category", "")),
        str(record.get("design_family", "")),
        str(record.get("color_palette_family", "")),
        str(record.get("layout_rhythm", "")),
        str(record.get("light_or_dark", "")),
    ]).lower()
    if "developer" in hay or "dark" in hay and "technical" in hay:
        return "premium-dark"
    if "creative" in hay or "editorial" in hay:
        return "editorial"
    if "business" in hay or "clinical" in hay or "finance" in hay or "healthcare" in hay:
        return "enterprise"
    if "restaurant" in hay or "fitness" in hay or "travel" in hay:
        return "playful"
    if "dark" in hay:
        return "premium-dark"
    return "clean"


def _map_dna_density(record: dict) -> str:
    hay = " ".join([str(record.get("spacing_style", "")), str(record.get("layout_rhythm", ""))]).lower()
    if "compact" in hay or "data-heavy" in hay:
        return "compact"
    if "spacious" in hay or "editorial" in hay or "image-heavy" in hay:
        return "spacious"
    return "balanced"


def _recent_primary_dna_families(history) -> list[str]:
    out = []
    for item in (history or [])[-3:]:
        families = item.get("dna_families") if isinstance(item, dict) else None
        if families:
            out.append(families[0])
    return out


def _select_design_dna(prompt: str, history=None, rng=None) -> tuple[list[dict], dict]:
    rng = rng or random.Random()
    try:
        from app import design_dna_library
        # Wider pool so diversity filters have more to work with
        candidates = design_dna_library.search_design_dna(prompt, max_results=30)
    except Exception:
        return [], {}
    if not candidates:
        return [], {}

    # Collect families used in the last 5 builds; deprioritize (don't exclude)
    # so we still fall back to them when no fresh candidates exist.
    recent_families = set()
    for item in (history or [])[-5:]:
        if isinstance(item, dict) and item.get("primary_dna_family"):
            recent_families.add(item["primary_dna_family"])

    fresh = [r for r in candidates if r.get("design_family") not in recent_families]
    stale = [r for r in candidates if r.get("design_family") in recent_families]
    # Use fresh first; fall back to stale only when fresh pool is too small
    ordered = (fresh + stale) if len(fresh) >= 2 else candidates

    top_span = min(len(ordered), 6)
    primary = ordered[rng.randrange(top_span)]
    selected = [primary]
    for record in ordered:
        if record["id"] == primary["id"]:
            continue
        if record.get("category") == primary.get("category") or len(selected) < 3:
            selected.append(record)
        if len(selected) >= 5:
            break
    try:
        summary = design_dna_library.summarize_design_dna(selected)
    except Exception:
        summary = {}
    return selected, summary


def _flatten_pattern(records: list[dict], field: str, limit: int = 8) -> list[str]:
    out = []
    for record in records or []:
        vals = record.get(field) or []
        if not isinstance(vals, list):
            vals = [vals]
        for val in vals:
            if val and val not in out:
                out.append(val)
            if len(out) >= limit:
                return out
    return out


def _apply_design_dna_to_genome(genome: dict, prompt: str, history=None, rng=None) -> dict:
    selected, summary = _select_design_dna(prompt, history=history, rng=rng)
    if not selected:
        return genome
    genome = dict(genome or {})
    primary = selected[0]
    hero_patterns = _flatten_pattern(selected, "hero_patterns")
    nav_patterns = _flatten_pattern(selected, "nav_patterns")
    section_patterns = _flatten_pattern(selected, "section_patterns", 10)
    card_patterns = _flatten_pattern(selected, "card_patterns")
    cta_patterns = _flatten_pattern(selected, "CTA_patterns")
    footer_patterns = _flatten_pattern(selected, "footer_patterns")
    families = list(dict.fromkeys(r.get("design_family", "") for r in selected if r.get("design_family")))

    genome["dna_profile_ids"] = [r["id"] for r in selected]
    genome["dna_families"] = families
    genome["primary_dna_family"] = primary.get("design_family", "")
    genome["selected_design_dna"] = selected
    genome["dna_summary"] = summary
    genome["hero_patterns"] = hero_patterns
    genome["nav_patterns"] = nav_patterns
    genome["section_patterns"] = section_patterns
    genome["card_patterns"] = card_patterns
    genome["CTA_patterns"] = cta_patterns
    genome["footer_patterns"] = footer_patterns

    genome["color_palette_family"] = primary.get("color_palette_family", genome.get("color_palette_family", ""))
    genome["typography_style"] = primary.get("typography_style", genome.get("typography_style", ""))
    genome["spacing_style"] = primary.get("spacing_style", genome.get("spacing_style", ""))
    genome["image_strategy"] = primary.get("image_strategy", genome.get("image_strategy", "hero image"))
    genome["layout_rhythm"] = primary.get("layout_rhythm", genome.get("layout_rhythm", "spacious"))
    genome["footer_style"] = (footer_patterns or [genome.get("footer_style", "product footer")])[0]
    genome["inspiration_family"] = _dna_inspiration_family(primary)
    genome["hero_variant"] = _map_dna_hero(hero_patterns)
    genome["nav_variant"] = _map_dna_nav(nav_patterns)
    genome["section_variants"] = _map_dna_sections(section_patterns)
    genome["section_variant"] = genome["section_variants"][0]
    genome["card_style"] = _map_dna_card(card_patterns)
    genome["cta_placement"] = _map_dna_cta(cta_patterns)
    genome["visual_style"] = _map_dna_visual_style(primary)
    genome["density"] = _map_dna_density(primary)
    if primary.get("complexity_level") in ("advanced", "enterprise"):
        genome["dashboard_style"] = "analytics" if genome.get("inspiration_family") in ("ai-devtools", "fintech-trust") else genome.get("dashboard_style", "kpi-cards")
    return genome


def _apply_visual_recipes_to_genome(genome: dict, rng=None) -> dict:
    """Attach concrete browser-visible recipe selections to the genome.

    Design DNA gives us abstract families/patterns. Recipes are the bridge to
    actual JSX/CSS branches: hero skeleton, nav shape, card treatment, section
    wrappers, CTA, and footer layout.
    """
    try:
        from app import design_recipes
        selected = design_recipes.select_visual_recipes(genome, rng=rng)
    except Exception as exc:
        genome = dict(genome or {})
        genome["visual_recipe_error"] = str(exc)[:120]
        return genome
    genome = dict(genome or {})
    genome.update(selected)
    nav_recipe = selected.get("nav_recipe") or {}
    hero_recipe = selected.get("hero_recipe") or {}
    if nav_recipe.get("variant"):
        genome["nav_variant"] = nav_recipe["variant"]
    if hero_recipe.get("variant"):
        genome["hero_variant"] = hero_recipe["variant"]
    return genome


def genome_signature(genome: dict) -> str:
    return "|".join(str(genome.get(a, "")) for a in _SIG_AXES)


def _sig_tuple(genome):
    return tuple(genome.get(a, "") for a in _SIG_AXES)


def make_genome(prompt: str, history=None, rng=None) -> dict:
    """Produce a Design Genome that is category-appropriate yet STRUCTURALLY distinct
    from `history` (a list of prior genomes). Uses fresh entropy each call, so the SAME
    prompt twice yields different genomes; anti-similarity picks the candidate that shares
    the FEWEST structural axes with any recent genome."""
    rng = rng or random.Random()                      # fresh OS entropy -> same prompt varies
    und = infer_app_understanding(prompt)
    cat = und["app_category"]
    hist_sigs = [_sig_tuple(h) for h in (history or [])]
    best, best_score = None, 99
    for _ in range(28):
        g = _roll(rng, cat)
        s = _sig_tuple(g)
        score = max((sum(1 for a, b in zip(s, hs) if a == b) for hs in hist_sigs), default=0)
        if score < best_score:
            best, best_score = g, score
        if best_score == 0:
            break
    best["app_seed"] = "%08x" % rng.getrandbits(32)
    best["app_category"] = cat
    best["domain"] = und["domain"]
    try:
        from app import inspiration_library
        inspiration = inspiration_library.select_inspiration(prompt, history=history, rng=rng)
        best = inspiration_library.apply_inspiration_to_genome(best, inspiration, rng=rng)
    except Exception as _insp:
        best["inspiration_family"] = "curated-fallback"
        best["inspiration_error"] = str(_insp)[:120]
    try:
        best = _apply_design_dna_to_genome(best, prompt, history=history, rng=rng)
    except Exception as _dna:
        best["design_dna_error"] = str(_dna)[:120]
    if not best.get("section_variants"):
        best["section_variants"] = _section_variant_sequence(best, rng)
    else:
        best["section_variants"] = [v for v in best["section_variants"] if v in SECTION_VARIANTS][:5] or _section_variant_sequence(best, rng)
        best["section_variant"] = best["section_variants"][0]
    try:
        best = _apply_visual_recipes_to_genome(best, rng=rng)
    except Exception as _recipe:
        best["visual_recipe_error"] = str(_recipe)[:120]
    try:
        from app import design_quality
        best = design_quality.polish_genome(best, prompt=prompt, rng=rng)
    except Exception as _quality:
        best["design_quality_error"] = str(_quality)[:120]
    best["first_screen_skeleton"] = first_screen_skeleton(best)
    return best


GENOME_FILE = "_design_genome.json"
HISTORY_FILE = "_genome_history.json"


def _hist_path(base_dir):
    return os.path.join(base_dir, HISTORY_FILE)


def load_history(base_dir: str, limit: int = 12) -> list:
    try:
        with open(_hist_path(base_dir), encoding="utf-8") as f:
            return json.load(f)[-limit:]
    except (OSError, ValueError):
        return []


def write_genome(out_dir: str, prompt: str, base_dir: str = "output", genome: dict = None) -> dict:
    """Persist a genome (made fresh if not supplied) that avoids recent structures, and
    append it to the shared history. Pass `genome` to persist the SAME genome that already
    drove this build (graph.py makes it early so it can shape the actual code, then stores it)."""
    history = load_history(base_dir)
    if genome is None:
        genome = make_genome(prompt, history=history)
    try:
        with open(os.path.join(out_dir, GENOME_FILE), "w", encoding="utf-8") as f:
            json.dump(genome, f, indent=2)
        history.append(genome)
        with open(_hist_path(base_dir), "w", encoding="utf-8") as f:
            json.dump(history[-24:], f, indent=2)
    except OSError:
        pass
    return genome


# ======================================================================
# GENOME -> BUILD MAPPING (Part 1): translate the abstract genome axes into the
# CONCRETE scaffold knobs that change real generated code. Every returned value
# is one the scaffold already supports (so `next build` stays green): site.styles
# (nav/dash/dashLayout/list/appNav) + per-entity crud_layout + marketing section
# order. This is what makes layout_family / navigation_pattern / dashboard_style /
# crud_style / section_strategy produce STRUCTURALLY different apps - not metadata.
# ======================================================================

# scaffold-supported values (mirror next_scaffold exactly - do NOT emit anything else)
NAV_PRESETS = ["solid", "blur", "pill", "dark", "minimal", "accent-top", "underline", "accent-solid", "floating", "tinted"]
DASH_PRESETS = ["classic", "band", "tinted", "glass", "outline", "bold", "gradient-cards", "flat", "ring", "mono"]
LIST_PRESETS = ["classic", "striped", "cards", "dense", "soft", "dark-head", "bordered", "pill-rows", "airy", "accent-edge"]
CRUD_LAYOUTS = ["table", "kanban", "split-pane", "spreadsheet", "timeline"]
DASH_LAYOUTS = ["kpi-cards", "analytics", "activity-feed", "table-first", "operations"]   # widget composition (scaffold)
APP_NAVS = ["sidebar", "topnav"]                                                          # app-shell orientation (scaffold)

_VISUAL_NAV = {"clean": "blur", "bold": "accent-top", "premium-dark": "dark", "glass": "floating",
               "editorial": "minimal", "playful": "pill", "enterprise": "solid", "minimal": "minimal", "dense-admin": "underline"}
_NAV_VARIANT_PRESET = {"centered topnav": "blur", "action topnav": "accent-solid", "sidebar": "tinted",
                       "floating nav": "floating", "utility bar": "accent-top"}
_VISUAL_DASH = {"clean": "classic", "bold": "bold", "premium-dark": "glass", "glass": "glass",
                "editorial": "mono", "playful": "gradient-cards", "enterprise": "outline", "minimal": "flat", "dense-admin": "ring"}
_DENSITY_LIST = {"compact": "dense", "spacious": "airy"}
_VISUAL_LIST = {"enterprise": "bordered", "editorial": "soft", "playful": "pill-rows", "premium-dark": "dark-head",
                "bold": "accent-edge", "glass": "striped", "minimal": "classic", "clean": "classic", "dense-admin": "dense"}
_DASHBOARD_LAYOUT = {"kpi-cards": "kpi-cards", "analytics": "analytics", "activity-feed": "activity-feed",
                     "table-first": "table-first", "split-pane": "table-first", "kanban": "operations",
                     "calendar": "analytics", "map-based": "analytics"}
_NAV_ORIENT = {"sidebar": "sidebar", "topnav": "topnav", "split-nav": "sidebar", "tabs": "topnav",
               "command-palette": "sidebar", "stepper": "topnav", "mobile-bottom-nav": "topnav"}
# crud_style -> (concrete scaffold crud_layout, the table list-preset to pair with it)
_CRUD_MAP = {"table-dense": ("table", "dense"), "card-grid": ("table", "cards"), "split-pane": ("split-pane", "classic"),
             "wizard": ("table", "soft"), "kanban": ("kanban", "classic"), "timeline": ("timeline", "classic"),
             "calendar": ("timeline", "striped"), "spreadsheet": ("spreadsheet", "classic")}
# complementary layouts so a multi-entity app mixes structure (not all-kanban)
_CRUD_COMPLEMENT = {"table": ["split-pane", "timeline"], "kanban": ["table", "timeline"],
                    "timeline": ["table", "split-pane"], "split-pane": ["table", "kanban"], "spreadsheet": ["table", "timeline"]}

# section_strategy -> ordered marketing section kinds (known to page_sections)
_SECTION_ORDER = {
    "storytelling": ["split", "testimonial", "features", "stats"],
    "conversion": ["features", "pricing", "stats", "faq"],
    "operations": ["steps", "features", "stats", "split"],
    "directory": ["gallery", "features", "terminology"],
    "analytics": ["stats", "features", "split"],
    "community": ["testimonial", "features", "gallery"],
    "productized-service": ["features", "pricing", "steps", "faq"],
}

_SECTION_KIND_BY_VARIANT = {
    "feature cards": "features",
    "icon grid": "features",
    "split image/text": "split",
    "stats band": "stats",
    "timeline": "steps",
    "portal preview": "split",
    "gallery": "gallery",
    "FAQ": "faq",
    "CTA": "cta",
}


def genome_to_crud_layout(crud_style: str) -> str:
    """The single concrete CRUD component a crud_style maps to (pure, testable)."""
    return _CRUD_MAP.get(crud_style, ("table", "classic"))[0]


def genome_crud_layouts(genome: dict, n: int) -> list:
    """A per-entity crud_layout list: entity 0 reflects the genome's crud_style; the rest
    rotate complementary layouts (seeded by app_seed) so a multi-entity app mixes structure."""
    primary = genome_to_crud_layout(genome.get("crud_style", "table-dense"))
    comp = _CRUD_COMPLEMENT.get(primary, ["table"])
    seed = int(str(genome.get("app_seed", "0") or "0"), 16) if str(genome.get("app_seed", "0")).strip("0123456789abcdef") == "" else hash(str(genome.get("app_seed")))
    rng = random.Random(seed)
    out = [primary]
    for i in range(1, max(0, n)):
        out.append(comp[(i - 1) % len(comp)] if rng.random() < 0.7 else primary)
    return out[:n]


def genome_to_styles(genome: dict) -> dict:
    """Translate the genome into the scaffold's site.styles knobs (all build-safe)."""
    vis = genome.get("visual_style", "clean")
    dens = genome.get("density", "balanced")
    nav_recipe = genome.get("nav_recipe") or {}
    nav_variant = nav_recipe.get("variant") or genome.get("nav_variant", "centered topnav")
    selected = genome.get("selected_inspirations") or []
    return {
        "nav": nav_recipe.get("preset") or _NAV_VARIANT_PRESET.get(nav_variant) or _VISUAL_NAV.get(vis, "blur"),
        "dash": _VISUAL_DASH.get(vis, "classic"),
        "dashLayout": _DASHBOARD_LAYOUT.get(genome.get("dashboard_style", "kpi-cards"), "kpi-cards"),
        "list": _DENSITY_LIST.get(dens) or _VISUAL_LIST.get(vis, "classic"),
        "appNav": _NAV_ORIENT.get(genome.get("navigation_pattern", "sidebar"), "sidebar"),
        "navVariant": nav_variant,
        "heroVariant": genome.get("hero_variant", "split"),
        "sectionVariants": list(genome.get("section_variants") or [genome.get("section_variant", "feature cards")]),
        "cardStyle": genome.get("card_style", "bordered"),
        "layoutRhythm": genome.get("layout_rhythm", "spacious"),
        "imageStrategy": genome.get("image_strategy", "hero image"),
        "ctaPlacement": genome.get("cta_placement", "hero-primary"),
        "inspirationFamily": genome.get("inspiration_family", ""),
        "inspirationCategories": list(dict.fromkeys(s.get("category", "") for s in selected if isinstance(s, dict)))[:6],
        "dnaProfileIds": list(genome.get("dna_profile_ids") or [])[:8],
        "dnaFamilies": list(genome.get("dna_families") or [])[:8],
        "primaryDnaFamily": genome.get("primary_dna_family", ""),
        "colorPaletteFamily": genome.get("color_palette_family", ""),
        "typographyStyle": genome.get("typography_style", ""),
        "spacingStyle": genome.get("spacing_style", ""),
        "footerStyle": genome.get("footer_style", ""),
        "visualFamily": genome.get("visual_family", ""),
        "heroRecipe": (genome.get("hero_recipe") or {}).get("id", ""),
        "navRecipe": (genome.get("nav_recipe") or {}).get("id", ""),
        "sectionRecipes": list(genome.get("section_recipe_ids") or []),
        "cardRecipe": (genome.get("card_recipe") or {}).get("id", ""),
        "ctaRecipe": (genome.get("cta_recipe") or {}).get("id", ""),
        "footerRecipe": (genome.get("footer_recipe") or {}).get("id", ""),
        "browserVisibleSignature": genome.get("browser_visible_signature", ""),
        "artDirectorEnabled": bool(genome.get("art_director_enabled")),
        "premiumPreset": genome.get("premium_preset_id", ""),
        "premiumPresetName": genome.get("premium_preset_name", ""),
        "designQualityBefore": genome.get("design_quality_before", {}),
        "designQualityAfter": genome.get("design_quality_after", {}),
        "imageRoles": dict(genome.get("image_roles") or {}),
        "imageReuseLimit": genome.get("image_reuse_limit", 2),
        "richComponentVariants": list(genome.get("rich_component_variants") or []),
    }


def genome_section_order(genome: dict, default_pack: list) -> list:
    """Reorder a marketing page's section pack per the genome's section_strategy."""
    variant_order = [_SECTION_KIND_BY_VARIANT.get(v) for v in (genome.get("section_variants") or [])]
    variant_order = [v for v in variant_order if v]
    order = variant_order or _SECTION_ORDER.get(genome.get("section_strategy", ""))
    return list(order) if order else list(default_pack or [])


def first_screen_skeleton(genome: dict) -> str:
    recipe_first = genome.get("first_screen_skeleton") if genome.get("hero_recipe") else ""
    if recipe_first:
        return str(recipe_first)
    return "|".join([
        str(genome.get("nav_variant", "centered topnav")),
        str(genome.get("hero_variant", "split")),
        str(genome.get("image_strategy", "hero image")),
        str(genome.get("cta_placement", "hero-primary")),
    ])


def genome_visual_composition(genome: dict) -> dict:
    return {
        "hero_variant": genome.get("hero_variant", "split"),
        "nav_variant": genome.get("nav_variant", "centered topnav"),
        "section_variants": list(genome.get("section_variants") or [genome.get("section_variant", "feature cards")]),
        "section_variant": genome.get("section_variant", "feature cards"),
        "card_style": genome.get("card_style", "bordered"),
        "layout_rhythm": genome.get("layout_rhythm", "spacious"),
        "image_strategy": genome.get("image_strategy", "hero image"),
        "cta_placement": genome.get("cta_placement", "hero-primary"),
        "first_screen_skeleton": genome.get("first_screen_skeleton") or first_screen_skeleton(genome),
        "inspiration_family": genome.get("inspiration_family", ""),
        "visual_family": genome.get("visual_family", ""),
        "hero_recipe": dict(genome.get("hero_recipe") or {}),
        "nav_recipe": dict(genome.get("nav_recipe") or {}),
        "section_recipes": list(genome.get("section_recipes") or []),
        "section_recipe_ids": list(genome.get("section_recipe_ids") or []),
        "card_recipe": dict(genome.get("card_recipe") or {}),
        "cta_recipe": dict(genome.get("cta_recipe") or {}),
        "footer_recipe": dict(genome.get("footer_recipe") or {}),
        "browser_visible_signature": genome.get("browser_visible_signature", ""),
        "inspiration_dna": dict(genome.get("inspiration_dna") or {}),
        "dna_profile_ids": list(genome.get("dna_profile_ids") or []),
        "dna_families": list(genome.get("dna_families") or []),
        "selected_design_dna": list(genome.get("selected_design_dna") or []),
        "dna_summary": dict(genome.get("dna_summary") or {}),
        "hero_patterns": list(genome.get("hero_patterns") or []),
        "nav_patterns": list(genome.get("nav_patterns") or []),
        "section_patterns": list(genome.get("section_patterns") or []),
        "card_patterns": list(genome.get("card_patterns") or []),
        "CTA_patterns": list(genome.get("CTA_patterns") or []),
        "footer_patterns": list(genome.get("footer_patterns") or []),
        "color_palette_family": genome.get("color_palette_family", ""),
        "typography_style": genome.get("typography_style", ""),
        "spacing_style": genome.get("spacing_style", ""),
        "footer_style": genome.get("footer_style", ""),
        "art_director_enabled": bool(genome.get("art_director_enabled")),
        "premium_preset": dict(genome.get("premium_preset") or {}),
        "premium_preset_id": genome.get("premium_preset_id", ""),
        "premium_preset_name": genome.get("premium_preset_name", ""),
        "design_quality_before": dict(genome.get("design_quality_before") or {}),
        "design_quality_after": dict(genome.get("design_quality_after") or {}),
        "image_roles": dict(genome.get("image_roles") or {}),
        "image_reuse_limit": genome.get("image_reuse_limit", 2),
        "rich_component_variants": list(genome.get("rich_component_variants") or []),
        "recipe_source_mode": genome.get("recipe_source_mode", "handcrafted"),
        "extracted_design_recipes": list(genome.get("extracted_design_recipes") or []),
        "extracted_recipe_ids": list(genome.get("extracted_recipe_ids") or []),
        "extracted_recipe_families": list(genome.get("extracted_recipe_families") or []),
        "github_recipe_influence": dict(genome.get("github_recipe_influence") or {}),
    }


def visual_structure_signature(genome: dict, styles: dict = None, crud_layouts=None) -> str:
    styles = styles or genome_to_styles(genome)
    sections = ">".join(genome.get("section_variants") or [genome.get("section_variant", "")])
    layouts = "+".join(sorted(crud_layouts or [])) or "table"
    dna_families = ">".join(genome.get("dna_families") or [genome.get("primary_dna_family", "")])
    hero_patterns = ">".join((genome.get("hero_patterns") or [])[:3])
    nav_patterns = ">".join((genome.get("nav_patterns") or [])[:2])
    card_patterns = ">".join((genome.get("card_patterns") or [])[:3])
    section_recipes = ">".join(genome.get("section_recipe_ids") or [])
    extracted_recipes = ">".join(genome.get("extracted_recipe_ids") or [])
    return "|".join([
        str(genome.get("inspiration_family", "")),
        str(genome.get("visual_family", "")),
        str(dna_families),
        str(hero_patterns),
        str(genome.get("hero_variant", "")),
        str((genome.get("hero_recipe") or {}).get("id", "")),
        str(nav_patterns),
        str(styles.get("navVariant") or genome.get("nav_variant", "")),
        str((genome.get("nav_recipe") or {}).get("id", "")),
        sections,
        section_recipes,
        str(card_patterns),
        str(genome.get("card_style", "")),
        str((genome.get("card_recipe") or {}).get("id", "")),
        str(genome.get("spacing_style", "")),
        str(genome.get("image_strategy", "")),
        str(genome.get("color_palette_family", "")),
        str(genome.get("typography_style", "")),
        str((genome.get("cta_recipe") or {}).get("id", "")),
        str((genome.get("footer_recipe") or {}).get("id", "")),
        str(genome.get("premium_preset_id", "")),
        str(genome.get("art_director_enabled", "")),
        str(styles.get("dashLayout", "")),
        layouts,
        first_screen_skeleton(genome),
        str(genome.get("browser_visible_signature", "")),
        str(genome.get("recipe_source_mode", "")),
        extracted_recipes,
    ])


def structure_signature(genome: dict, styles: dict, crud_layouts) -> str:
    """A signature of the REAL generated structure (not just genome metadata): app-shell
    orientation + dashboard composition + nav/list preset + the multiset of CRUD layouts +
    section strategy. Two apps with the same signature look structurally identical."""
    layouts = "+".join(sorted(crud_layouts or [])) or "table"
    return "|".join([
        genome.get("inspiration_family", ""), genome.get("visual_family", ""), genome.get("primary_dna_family", ""), genome.get("layout_family", ""), styles.get("appNav", ""), styles.get("dashLayout", ""),
        styles.get("nav", ""), styles.get("list", ""), layouts, genome.get("section_strategy", ""),
        genome.get("hero_variant", ""), (genome.get("hero_recipe") or {}).get("id", ""),
        genome.get("card_style", ""), (genome.get("card_recipe") or {}).get("id", ""), genome.get("image_strategy", ""),
    ])


_THEME_BY_PALETTE = {
    "calm trust": {"accent": "blue", "theme_style": "minimal"},
    "operational blue": {"accent": "indigo", "theme_style": "minimal"},
    "creative contrast": {"accent": "fuchsia", "theme_style": "glassmorphism"},
    "premium product": {"accent": "slate", "theme_style": "minimal"},
    "warm brand": {"accent": "amber", "theme_style": "neo-brutalism"},
    "community bright": {"accent": "violet", "theme_style": "glassmorphism"},
    "developer dark": {"accent": "violet", "theme_style": "cyberpunk"},
    "fintech trust": {"accent": "emerald", "theme_style": "minimal"},
    "learning editorial": {"accent": "cyan", "theme_style": "minimal"},
    "clean neutral": {"accent": "slate", "theme_style": "minimal"},
    "soft indigo": {"accent": "indigo", "theme_style": "minimal"},
    "slate control": {"accent": "slate", "theme_style": "minimal"},
    "data teal": {"accent": "teal", "theme_style": "minimal"},
    "gallery monochrome": {"accent": "slate", "theme_style": "minimal"},
    "high contrast neutral": {"accent": "slate", "theme_style": "minimal"},
    "clean technical": {"accent": "violet", "theme_style": "minimal"},
    "secure emerald": {"accent": "emerald", "theme_style": "minimal"},
    "soft cyan": {"accent": "cyan", "theme_style": "minimal"},
    "clinical blue white": {"accent": "blue", "theme_style": "minimal"},
    "soft teal clinical": {"accent": "teal", "theme_style": "minimal"},
    "showroom neutral": {"accent": "slate", "theme_style": "minimal"},
    "warm hospitality": {"accent": "amber", "theme_style": "minimal"},
    "rich dining": {"accent": "rose", "theme_style": "minimal"},
    "fresh natural": {"accent": "emerald", "theme_style": "minimal"},
    "property neutral": {"accent": "slate", "theme_style": "minimal"},
    "destination warm": {"accent": "amber", "theme_style": "minimal"},
    "ocean calm": {"accent": "cyan", "theme_style": "minimal"},
    "warm wellness": {"accent": "emerald", "theme_style": "minimal"},
    "warm academic": {"accent": "amber", "theme_style": "minimal"},
}

_FONT_BY_TYPOGRAPHY = {
    "precise sans": ("Sora", "Inter"),
    "dense sans": ("IBM Plex Sans", "IBM Plex Sans"),
    "editorial display": ("Fraunces", "Inter"),
    "premium sans": ("Manrope", "Manrope"),
    "friendly sans": ("DM Sans", "DM Sans"),
    "technical sans": ("Space Grotesk", "Inter"),
    "readable editorial": ("Playfair Display", "Source Sans 3"),
    "readable sans": ("Source Sans 3", "Inter"),
}


def inspiration_theme(genome: dict) -> dict:
    """Map abstract inspiration DNA to existing safe theme knobs."""
    genome = genome or {}
    out = dict(_THEME_BY_PALETTE.get(genome.get("color_palette_family", ""), {}))
    fonts = _FONT_BY_TYPOGRAPHY.get(genome.get("typography_style", ""))
    if fonts:
        out["font_display"], out["font_body"] = fonts
    return out


# ======================================================================
# UNIVERSAL DOMAIN MODELER (Part 2): infer entities/fields/workflows/roles/pages for
# ANY prompt - including unknown/custom ones - from its nouns, verbs, business goal and
# category. Used as a FALLBACK when research/planner produced nothing, so a generated app
# always has a meaningful, domain-shaped data model (never an empty "Item" stub).
# ======================================================================
import re as _re

_DM_STOP = {"the", "and", "for", "with", "app", "application", "build", "create", "make", "that", "this",
            "want", "need", "system", "platform", "website", "site", "online", "web", "tool", "manage",
            "management", "track", "tracking", "simple", "small", "let", "lets", "allow", "allows", "users",
            "user", "can", "where", "which", "their", "your", "our", "have", "has", "from", "into", "about"}
_DM_VERBS = {"book": "Booking", "order": "Ordering", "approve": "Approvals", "ship": "Shipping",
             "enroll": "Enrollment", "schedule": "Scheduling", "pay": "Payments", "invoice": "Invoicing",
             "review": "Reviews", "track": "Tracking", "assign": "Assignments", "report": "Reporting",
             "rent": "Rentals", "deliver": "Deliveries", "register": "Registration", "submit": "Submissions",
             "publish": "Publishing", "checkout": "Checkout", "subscribe": "Subscriptions"}
_DM_ROLE_WORDS = {"admin": "Admin", "manager": "Manager", "staff": "Staff", "customer": "Customer",
                  "client": "Client", "student": "Student", "teacher": "Teacher", "patient": "Patient",
                  "doctor": "Doctor", "seller": "Seller", "buyer": "Buyer", "member": "Member",
                  "owner": "Owner", "employee": "Employee", "vendor": "Vendor", "guest": "Guest",
                  "agent": "Agent", "host": "Host", "driver": "Driver", "tenant": "Tenant"}
# per-category SEED entities so a recognised domain always models its core records
_CATEGORY_ENTITIES = {
    "booking": ["Booking", "Customer", "Service", "Staff"],
    "marketplace": ["Listing", "Order", "Seller", "Review"],
    "education": ["Course", "Student", "Assignment", "Enrollment"],
    "healthcare": ["Patient", "Appointment", "Doctor", "Record"],
    "finance": ["Account", "Transaction", "Invoice", "Client"],
    "inventory": ["Product", "Supplier", "Order", "Shipment"],
    "content": ["Article", "Author", "Category", "Comment"],
    "social": ["Post", "Member", "Comment", "Group"],
    "internal_tool": ["Ticket", "Team", "Task", "Report"],
    "business": ["Lead", "Deal", "Client", "Task"],
}
_FIELD_BANK = ["name", "status", "email", "phone", "date", "amount", "category", "notes", "owner", "priority"]


def _field(name: str) -> dict:
    n = name.lower()
    t = "text"
    if n in ("status", "priority", "category", "stage"): t = "select"
    elif n in ("date", "due_date", "created_at"): t = "date"
    elif n in ("amount", "price", "total", "quantity", "count"): t = "number"
    elif n == "email": t = "email"
    elif n in ("notes", "description", "details"): t = "textarea"
    out = {"name": name, "label": name.replace("_", " ").title(), "type": t}
    if t == "select":
        out["options"] = ["Active", "Pending", "Completed", "Cancelled"]
    return out


def infer_domain_model(prompt: str, understanding: dict = None) -> dict:
    """Return {entities, roles, workflows, pages, public_vs_private} inferred from the
    prompt. Works for unknown domains by pulling salient nouns/verbs out of the text."""
    u = understanding or infer_app_understanding(prompt)
    cat = u.get("app_category", "custom")
    p = " " + (prompt or "").lower() + " "
    words = [w for w in _re.findall(r"[a-z]{3,}", p) if w not in _DM_STOP]

    roles = [lab for key, lab in _DM_ROLE_WORDS.items() if key in p] or ["Admin", "User"]
    workflows = [lab for vb, lab in _DM_VERBS.items() if _re.search(r"\b" + vb, p)]

    names = list(dict.fromkeys(_CATEGORY_ENTITIES.get(cat, [])))            # category seeds first
    if cat == "custom":
        # singularise + Title-case salient nouns from the prompt as candidate entities
        for w in words:
            cand = (w[:-1] if w.endswith("s") and len(w) > 4 else w).title()
            if cand not in names and cand.lower() not in _DM_ROLE_WORDS:
                names.append(cand)
    names = names[:4] or ["Record"]

    entities = []
    for i, nm in enumerate(names):
        fields = ["name", "status", "notes"] + (["amount"] if cat in ("finance", "marketplace", "inventory") else ["date"])
        entities.append({
            "name": nm, "label": nm + ("s" if not nm.endswith("s") else ""),
            "storage_key": nm, "fields": [_field(f) for f in dict.fromkeys(fields)],
            "crud_layout": "table",
        })
    pages = [w.title() for w in ("features", "about", "contact")] if u.get("public_vs_private") != "internal" else []
    return {"entities": entities, "roles": roles[:3],
            "workflows": workflows or ["Records", "Reporting"], "pages": pages,
            "public_vs_private": u.get("public_vs_private", "hybrid")}


def load_genome(out_dir: str):
    try:
        with open(os.path.join(out_dir, GENOME_FILE), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
