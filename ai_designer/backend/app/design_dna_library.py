"""Offline abstract Design DNA library.

This module intentionally stores pattern vocabulary only. It does not contain
real website references, brand names, URLs, image paths, source copy, logos, or
full templates. The records are generated from abstract combinations of design
families, page rhythms, hero styles, navigation styles, card treatments, image
strategies, color systems, typography systems, and section patterns.
"""
from __future__ import annotations

from collections import Counter
import copy
import re


REQUIRED_FIELDS = {
    "id",
    "name",
    "category",
    "domain_fit",
    "design_family",
    "hero_patterns",
    "nav_patterns",
    "section_patterns",
    "card_patterns",
    "CTA_patterns",
    "footer_patterns",
    "color_palette_family",
    "typography_style",
    "spacing_style",
    "image_strategy",
    "layout_rhythm",
    "best_for_domains",
    "complexity_level",
    "light_or_dark",
    "professional_quality_score",
}


CATEGORIES = [
    "SaaS / Productivity",
    "POS / ERP / Business Software",
    "Portfolio / Agency / Creative",
    "Ecommerce / Product",
    "Marketing / Landing / Brand",
    "Social / Community / Creator",
    "AI / Developer Tools",
    "Finance / FinTech",
    "Education / Media / Content",
    "Healthcare / Hospital / Clinic",
    "Vehicle Sales / Automotive",
    "Restaurant / Booking",
    "Real Estate",
    "Travel / Tourism",
    "Fitness / Wellness",
]


_CATEGORY_PROFILES = [
    {
        "category": "SaaS / Productivity",
        "name_prefix": "Workflow System",
        "keywords": ["saas", "productivity", "crm", "project", "team", "workflow", "collaboration", "dashboard", "automation"],
        "domain_fit": ["team workspace", "workflow software", "productivity platform", "admin dashboard"],
        "design_families": ["saas-productivity", "workflow-saas", "collaboration-platform", "trust-saas"],
        "hero": ["split product story", "dashboard proof hero", "workflow preview hero", "metrics-led hero", "card stack hero"],
        "nav": ["centered topnav", "action topnav", "utility bar", "sidebar hybrid", "floating product nav"],
        "sections": ["feature cards", "portal preview", "stats band", "integration grid", "workflow timeline", "FAQ", "trust band"],
        "cards": ["bordered", "shadow", "stat-card", "soft panel", "workflow tile"],
        "ctas": ["hero-primary", "nav-cta", "floating trial CTA", "after-proof CTA", "section-end"],
        "footers": ["product footer", "utility footer", "trust footer", "compact resource footer"],
        "palettes": ["calm trust", "operational blue", "clean neutral", "soft indigo"],
        "typography": ["precise sans", "friendly sans", "dense sans", "technical sans"],
        "spacing": ["spacious", "balanced", "compact"],
        "images": ["dashboard mockup", "workflow diagram", "section images", "no-image fallback"],
        "rhythms": ["spacious", "data-heavy", "compact"],
    },
    {
        "category": "POS / ERP / Business Software",
        "name_prefix": "Operations Desk",
        "keywords": ["pos", "erp", "inventory", "order", "stock", "supplier", "warehouse", "operations", "booking", "payment", "pharmacy", "medicine", "prescription", "grn", "batch", "expiry", "dispensary", "pharmacist"],
        "domain_fit": ["retail operations", "ERP dashboard", "inventory control", "back-office workflow"],
        "design_families": ["operational-business", "dense-admin", "workflow-command", "resource-planning"],
        "hero": ["dashboard proof hero", "metrics-first hero", "operations board hero", "workflow preview hero"],
        "nav": ["sidebar", "utility bar", "action topnav", "compact app nav"],
        "sections": ["stats band", "portal preview", "timeline", "feature cards", "resource grid", "reports preview"],
        "cards": ["stat-card", "bordered", "flat", "dense table card", "alert tile"],
        "ctas": ["after-stats", "nav-cta", "hero-primary", "operations demo CTA"],
        "footers": ["enterprise footer", "utility footer", "support footer"],
        "palettes": ["operational blue", "clean neutral", "slate control", "data teal"],
        "typography": ["dense sans", "precise sans", "technical sans"],
        "spacing": ["compact", "balanced", "data-heavy"],
        "images": ["dashboard mockup", "operations board", "no-image fallback"],
        "rhythms": ["compact", "data-heavy", "balanced"],
    },
    {
        "category": "Portfolio / Agency / Creative",
        "name_prefix": "Creative Studio",
        "keywords": ["portfolio", "agency", "creative", "studio", "designer", "artist", "case", "brand", "work"],
        "domain_fit": ["creative portfolio", "agency showcase", "studio services", "case study archive"],
        "design_families": ["creative-agency", "editorial-studio", "gallery-led", "asymmetric-brand"],
        "hero": ["editorial lead hero", "immersive brand image hero", "card stack hero", "asymmetric statement hero"],
        "nav": ["floating nav", "centered topnav", "minimal topnav", "project index nav"],
        "sections": ["gallery", "split image/text", "timeline", "feature cards", "case study grid", "client proof"],
        "cards": ["image-card", "glass", "shadow", "minimal frame", "case tile"],
        "ctas": ["hero-split", "section-end", "floating brief CTA", "contact CTA"],
        "footers": ["minimal footer", "studio footer", "project archive footer"],
        "palettes": ["creative contrast", "gallery monochrome", "warm brand", "high contrast neutral"],
        "typography": ["editorial display", "premium sans", "friendly sans"],
        "spacing": ["editorial", "image-heavy", "spacious"],
        "images": ["gallery", "section images", "hero image"],
        "rhythms": ["editorial", "image-heavy", "spacious"],
    },
    {
        "category": "Ecommerce / Product",
        "name_prefix": "Product Commerce",
        "keywords": ["ecommerce", "product", "store", "shop", "marketplace", "retail", "catalog", "checkout", "sales", "vehicle"],
        "domain_fit": ["product commerce", "marketplace catalog", "retail landing", "collection browsing"],
        "design_families": ["ecommerce-product", "catalog-commerce", "premium-product", "marketplace-discovery"],
        "hero": ["product spotlight hero", "full-image hero", "card stack hero", "collection hero"],
        "nav": ["action topnav", "centered topnav", "floating nav", "commerce utility nav"],
        "sections": ["gallery", "feature cards", "split image/text", "collection grid", "trust proof", "CTA"],
        "cards": ["image-card", "shadow", "flat", "product tile", "price card"],
        "ctas": ["hero-primary", "nav-cta", "section-end", "shop CTA", "compare CTA"],
        "footers": ["commerce footer", "brand footer", "support footer"],
        "palettes": ["premium product", "clean neutral", "warm product", "gallery monochrome"],
        "typography": ["premium sans", "friendly sans", "precise sans"],
        "spacing": ["image-heavy", "spacious", "balanced"],
        "images": ["gallery", "hero image", "section images", "product preview"],
        "rhythms": ["image-heavy", "spacious", "editorial"],
    },
    {
        "category": "Marketing / Landing / Brand",
        "name_prefix": "Launch Story",
        "keywords": ["landing", "marketing", "brand", "campaign", "startup", "service", "conversion", "launch", "lead"],
        "domain_fit": ["conversion landing", "brand campaign", "service website", "launch page"],
        "design_families": ["marketing-brand", "conversion-story", "service-launch", "brand-system"],
        "hero": ["split product story", "card stack hero", "editorial lead hero", "benefit-led hero"],
        "nav": ["action topnav", "floating nav", "centered topnav", "minimal topnav"],
        "sections": ["feature cards", "timeline", "FAQ", "CTA", "proof band", "benefit grid"],
        "cards": ["shadow", "glass", "bordered", "benefit card", "testimonial tile"],
        "ctas": ["hero-primary", "floating", "section-end", "lead capture CTA"],
        "footers": ["brand footer", "newsletter footer", "minimal footer"],
        "palettes": ["warm brand", "calm trust", "creative contrast", "clean neutral"],
        "typography": ["friendly sans", "editorial display", "precise sans"],
        "spacing": ["spacious", "editorial", "balanced"],
        "images": ["section images", "hero image", "illustrated mockup", "no-image fallback"],
        "rhythms": ["spacious", "editorial", "compact"],
    },
    {
        "category": "Social / Community / Creator",
        "name_prefix": "Community Hub",
        "keywords": ["social", "community", "creator", "forum", "member", "network", "chat", "content", "feed"],
        "domain_fit": ["member community", "creator network", "content hub", "forum platform"],
        "design_families": ["social-community", "creator-network", "member-platform", "community-cards"],
        "hero": ["community cards hero", "card stack hero", "immersive brand image hero", "feed preview hero"],
        "nav": ["floating nav", "centered topnav", "utility bar", "member nav"],
        "sections": ["gallery", "feature cards", "timeline", "portal preview", "member proof", "feed preview"],
        "cards": ["glass", "shadow", "image-card", "profile card", "feed card"],
        "ctas": ["hero-split", "floating", "nav-cta", "join CTA"],
        "footers": ["community footer", "minimal footer", "resource footer"],
        "palettes": ["community bright", "warm brand", "soft indigo", "creative contrast"],
        "typography": ["friendly sans", "premium sans", "precise sans"],
        "spacing": ["spacious", "balanced", "image-heavy"],
        "images": ["gallery", "section images", "profile mosaic"],
        "rhythms": ["spacious", "image-heavy", "editorial"],
    },
    {
        "category": "AI / Developer Tools",
        "name_prefix": "Developer Intelligence",
        "keywords": ["ai", "developer", "devtool", "code", "api", "agent", "automation", "cloud", "docs", "model"],
        "domain_fit": ["AI developer tool", "API platform", "automation workspace", "technical docs"],
        "design_families": ["ai-devtools", "technical-platform", "developer-workbench", "code-console"],
        "hero": ["dashboard proof hero", "code workspace hero", "editorial lead hero", "terminal preview hero"],
        "nav": ["utility bar", "floating nav", "sidebar", "docs nav"],
        "sections": ["portal preview", "stats band", "timeline", "FAQ", "code panel", "API workflow"],
        "cards": ["glass", "bordered", "stat-card", "code card", "console tile"],
        "ctas": ["hero-split", "nav-cta", "after-stats", "docs CTA", "sandbox CTA"],
        "footers": ["developer footer", "docs footer", "security footer"],
        "palettes": ["developer dark", "clean technical", "slate control", "soft indigo"],
        "typography": ["technical sans", "dense sans", "precise sans"],
        "spacing": ["data-heavy", "compact", "balanced"],
        "images": ["dashboard mockup", "code panel", "no-image fallback", "workflow diagram"],
        "rhythms": ["data-heavy", "compact", "spacious"],
    },
    {
        "category": "Finance / FinTech",
        "name_prefix": "Trust Ledger",
        "keywords": ["finance", "fintech", "bank", "loan", "wallet", "invoice", "payment", "transaction", "security", "audit"],
        "domain_fit": ["financial dashboard", "payment workflow", "invoice platform", "trusted account portal"],
        "design_families": ["fintech-trust", "secure-finance", "metrics-led-finance", "transaction-platform"],
        "hero": ["metrics-first hero", "dashboard proof hero", "split product story", "security proof hero"],
        "nav": ["utility bar", "action topnav", "centered topnav", "secure app nav"],
        "sections": ["stats band", "portal preview", "feature cards", "FAQ", "security controls", "transaction preview"],
        "cards": ["stat-card", "bordered", "flat", "transaction card", "security card"],
        "ctas": ["after-stats", "hero-primary", "nav-cta", "trust CTA"],
        "footers": ["trust footer", "enterprise footer", "compliance footer"],
        "palettes": ["fintech trust", "clean neutral", "secure emerald", "data teal"],
        "typography": ["precise sans", "dense sans", "technical sans"],
        "spacing": ["data-heavy", "compact", "balanced"],
        "images": ["dashboard mockup", "chart preview", "no-image fallback"],
        "rhythms": ["data-heavy", "compact", "spacious"],
    },
    {
        "category": "Education / Media / Content",
        "name_prefix": "Learning Media",
        "keywords": ["education", "course", "learning", "student", "teacher", "lesson", "media", "content", "school", "catalog"],
        "domain_fit": ["course platform", "learning portal", "media library", "student dashboard"],
        "design_families": ["education-media", "course-catalog", "learning-path", "editorial-learning"],
        "hero": ["editorial lead hero", "course preview hero", "immersive learning hero", "catalog hero"],
        "nav": ["centered topnav", "action topnav", "floating nav", "course catalog nav"],
        "sections": ["split image/text", "gallery", "timeline", "feature cards", "course catalog", "learning path"],
        "cards": ["image-card", "bordered", "shadow", "course card", "lesson tile"],
        "ctas": ["hero-primary", "hero-split", "section-end", "enroll CTA"],
        "footers": ["content footer", "catalog footer", "resource footer"],
        "palettes": ["learning editorial", "warm academic", "clean neutral", "soft cyan"],
        "typography": ["readable editorial", "friendly sans", "editorial display"],
        "spacing": ["editorial", "spacious", "image-heavy"],
        "images": ["section images", "gallery", "course preview", "media grid"],
        "rhythms": ["editorial", "spacious", "image-heavy"],
    },
    {
        "category": "Healthcare / Hospital / Clinic",
        "name_prefix": "Clinical Trust",
        "keywords": ["hospital", "clinic", "healthcare", "patient", "doctor", "appointment", "lab", "emergency", "portal", "compliance"],
        "domain_fit": ["hospital website", "clinic management", "patient portal", "appointment booking", "lab report access"],
        "design_families": ["healthcare-trust-saas", "clinical-operations", "patient-care-platform", "medical-service"],
        "hero": ["trust overview hero", "appointment booking hero", "doctor search hero", "emergency contact hero", "patient portal preview hero"],
        "nav": ["utility bar", "action topnav", "centered topnav", "calm sidebar"],
        "sections": ["emergency contact band", "appointment CTA", "doctor search preview", "departments grid", "patient portal preview", "lab report access", "compliance cards"],
        "cards": ["soft trust card", "bordered clinical card", "stat-card", "portal tile", "care pathway card"],
        "ctas": ["book appointment CTA", "find doctor CTA", "patient portal CTA", "emergency CTA"],
        "footers": ["trust footer", "clinic support footer", "compliance footer"],
        "palettes": ["clinical blue white", "calm trust", "soft teal clinical", "clean neutral"],
        "typography": ["precise sans", "friendly sans", "readable sans"],
        "spacing": ["spacious", "balanced", "data-heavy"],
        "images": ["hero image", "doctor search mockup", "patient portal preview", "section images"],
        "rhythms": ["spacious", "data-heavy", "balanced"],
    },
    {
        "category": "Vehicle Sales / Automotive",
        "name_prefix": "Automotive Market",
        "keywords": ["vehicle", "automotive", "car", "dealer", "sales", "inventory", "financing", "test drive", "trade", "marketplace"],
        "domain_fit": ["vehicle sales website", "automotive marketplace", "dealer inventory", "test drive funnel"],
        "design_families": ["automotive-commerce", "vehicle-marketplace", "premium-product", "inventory-showroom"],
        "hero": ["vehicle spotlight hero", "inventory search hero", "full-image showroom hero", "financing offer hero"],
        "nav": ["action topnav", "floating nav", "inventory nav", "commerce utility nav"],
        "sections": ["inventory gallery", "financing options", "test drive flow", "vehicle comparison", "trust proof", "trade-in CTA"],
        "cards": ["image-card", "vehicle tile", "shadow", "price card", "spec card"],
        "ctas": ["schedule test drive CTA", "view inventory CTA", "financing CTA", "trade-in CTA"],
        "footers": ["commerce footer", "dealer support footer", "trust footer"],
        "palettes": ["premium product", "showroom neutral", "clean neutral", "high contrast neutral"],
        "typography": ["premium sans", "precise sans", "friendly sans"],
        "spacing": ["image-heavy", "spacious", "balanced"],
        "images": ["gallery", "hero image", "vehicle preview", "section images"],
        "rhythms": ["image-heavy", "spacious", "editorial"],
    },
    {
        "category": "Restaurant / Booking",
        "name_prefix": "Reservation Service",
        "keywords": ["restaurant", "booking", "reservation", "menu", "table", "food", "dining", "order", "delivery"],
        "domain_fit": ["restaurant booking", "dining website", "reservation workflow", "menu ordering"],
        "design_families": ["restaurant-booking", "hospitality-service", "menu-commerce", "local-service"],
        "hero": ["reservation hero", "menu spotlight hero", "immersive dining hero", "availability search hero"],
        "nav": ["action topnav", "centered topnav", "floating nav", "booking utility nav"],
        "sections": ["menu preview", "booking flow", "hours band", "location cards", "reviews proof", "private dining CTA"],
        "cards": ["menu card", "image-card", "shadow", "reservation card", "review tile"],
        "ctas": ["reserve table CTA", "view menu CTA", "order now CTA", "call CTA"],
        "footers": ["local service footer", "booking footer", "support footer"],
        "palettes": ["warm hospitality", "clean neutral", "rich dining", "fresh natural"],
        "typography": ["friendly sans", "editorial display", "premium sans"],
        "spacing": ["spacious", "image-heavy", "balanced"],
        "images": ["hero image", "gallery", "menu preview", "section images"],
        "rhythms": ["image-heavy", "spacious", "editorial"],
    },
    {
        "category": "Real Estate",
        "name_prefix": "Property Journey",
        "keywords": ["real estate", "property", "listing", "home", "agent", "rent", "buy", "neighborhood", "mortgage"],
        "domain_fit": ["property listings", "real estate agency", "rental marketplace", "neighborhood guide"],
        "design_families": ["real-estate-listings", "property-marketplace", "agent-trust", "neighborhood-editorial"],
        "hero": ["property search hero", "listing gallery hero", "agent trust hero", "neighborhood editorial hero"],
        "nav": ["search topnav", "action topnav", "floating nav", "listing nav"],
        "sections": ["listing grid", "neighborhood cards", "agent proof", "mortgage calculator preview", "tour booking flow", "market stats"],
        "cards": ["listing card", "image-card", "bordered", "stat-card", "agent card"],
        "ctas": ["book tour CTA", "view listings CTA", "contact agent CTA", "valuation CTA"],
        "footers": ["listing footer", "trust footer", "local guide footer"],
        "palettes": ["property neutral", "calm trust", "warm brand", "clean neutral"],
        "typography": ["premium sans", "precise sans", "readable editorial"],
        "spacing": ["spacious", "image-heavy", "balanced"],
        "images": ["gallery", "listing preview", "hero image", "section images"],
        "rhythms": ["image-heavy", "spacious", "editorial"],
    },
    {
        "category": "Travel / Tourism",
        "name_prefix": "Destination Booking",
        "keywords": ["travel", "tourism", "hotel", "tour", "destination", "booking", "trip", "itinerary", "guide"],
        "domain_fit": ["travel booking", "tour website", "destination guide", "itinerary planner"],
        "design_families": ["travel-tourism", "destination-editorial", "booking-marketplace", "experience-gallery"],
        "hero": ["destination image hero", "booking search hero", "itinerary preview hero", "experience story hero"],
        "nav": ["floating nav", "action topnav", "centered topnav", "booking nav"],
        "sections": ["destination gallery", "itinerary timeline", "booking flow", "experience cards", "review proof", "FAQ"],
        "cards": ["image-card", "trip card", "shadow", "experience tile", "price card"],
        "ctas": ["plan trip CTA", "book tour CTA", "explore destinations CTA", "talk to guide CTA"],
        "footers": ["travel footer", "booking footer", "guide footer"],
        "palettes": ["destination warm", "ocean calm", "clean neutral", "fresh natural"],
        "typography": ["friendly sans", "editorial display", "premium sans"],
        "spacing": ["image-heavy", "spacious", "editorial"],
        "images": ["hero image", "gallery", "destination preview", "section images"],
        "rhythms": ["image-heavy", "editorial", "spacious"],
    },
    {
        "category": "Fitness / Wellness",
        "name_prefix": "Wellness Coaching",
        "keywords": ["fitness", "wellness", "gym", "coach", "trainer", "health", "class", "habit", "nutrition", "booking"],
        "domain_fit": ["fitness studio", "wellness coaching", "class booking", "habit tracking"],
        "design_families": ["fitness-wellness", "coaching-platform", "class-booking", "health-lifestyle"],
        "hero": ["program transformation hero", "class booking hero", "coach trust hero", "habit dashboard hero"],
        "nav": ["action topnav", "centered topnav", "floating nav", "class schedule nav"],
        "sections": ["program cards", "class schedule", "coach profiles", "progress stats", "nutrition preview", "member proof"],
        "cards": ["program card", "image-card", "stat-card", "coach card", "class tile"],
        "ctas": ["book class CTA", "start plan CTA", "meet coach CTA", "join challenge CTA"],
        "footers": ["wellness footer", "class footer", "support footer"],
        "palettes": ["fresh natural", "warm wellness", "clean neutral", "soft teal clinical"],
        "typography": ["friendly sans", "premium sans", "precise sans"],
        "spacing": ["spacious", "image-heavy", "balanced"],
        "images": ["hero image", "section images", "program preview", "gallery"],
        "rhythms": ["spacious", "image-heavy", "data-heavy"],
    },
]


_COMPLEXITY_LEVELS = ["simple", "standard", "advanced", "enterprise"]
_LIGHT_DARK = ["light", "light", "light", "mixed", "dark"]

_BANNED_SITE_NAMES = {
    "stripe", "apple", "nike", "linear", "notion", "figma", "vercel", "framer", "webflow",
    "slack", "dropbox", "airtable", "miro", "asana", "monday", "clickup", "calendly",
    "square", "shopify", "toast", "lightspeed", "clover", "revel", "odoo", "zoho",
    "quickbooks", "xero", "tesla", "ikea", "amazon", "etsy", "glossier", "patagonia",
    "gymshark", "mailchimp", "hubspot", "intercom", "typeform", "canva", "headspace",
    "duolingo", "grammarly", "ahrefs", "discord", "reddit", "github", "linkedin",
    "pinterest", "openai", "anthropic", "perplexity", "cursor", "replit", "gitlab",
    "supabase", "railway", "cloudflare", "gitbook", "wise", "revolut", "monzo",
    "mercury", "ramp", "brex", "paypal", "coinbase", "robinhood", "coursera", "edx",
    "udemy", "ted", "spotify", "masterclass", "warby parker", "best buy", "product hunt",
    "stack overflow", "bruno simon", "brittany chiang", "tobias van schneider",
    "adham dannaway", "active theory", "work and co", "the new york times",
    "national geographic",
}

_URL_RE = re.compile(r"(https?://|www\.|[a-z0-9-]+\.(com|app|ai|io|co|net|org|tech)\b)", re.I)
_IMAGE_PATH_RE = re.compile(r"(/assets/|/generated/|\\assets\\|\\generated\\|[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp|svg|gif)\b)", re.I)


def _window(values: list[str], start: int, count: int) -> list[str]:
    if not values:
        return []
    out = []
    for i in range(count):
        value = values[(start + i) % len(values)]
        if value not in out:
            out.append(value)
    return out


def _dedupe(values) -> list[str]:
    out = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _make_record(profile: dict, serial: int, local_index: int) -> dict:
    quality = min(99, 82 + ((serial + local_index) % 16))
    domain_fit = _window(profile["domain_fit"], local_index, 3)
    sections = _dedupe(_window(profile["sections"], local_index, 5) + _window(profile["sections"], local_index + 5, 1))
    return {
        "id": f"dna-{serial:04d}",
        "name": f"{profile['name_prefix']} DNA {local_index + 1:03d}",
        "category": profile["category"],
        "domain_fit": domain_fit,
        "design_family": profile["design_families"][local_index % len(profile["design_families"])],
        "hero_patterns": _window(profile["hero"], local_index, 3),
        "nav_patterns": _window(profile["nav"], local_index // 2, 2),
        "section_patterns": sections,
        "card_patterns": _window(profile["cards"], local_index, 3),
        "CTA_patterns": _window(profile["ctas"], local_index, 2),
        "footer_patterns": _window(profile["footers"], local_index, 2),
        "color_palette_family": profile["palettes"][local_index % len(profile["palettes"])],
        "typography_style": profile["typography"][local_index % len(profile["typography"])],
        "spacing_style": profile["spacing"][local_index % len(profile["spacing"])],
        "image_strategy": profile["images"][local_index % len(profile["images"])],
        "layout_rhythm": profile["rhythms"][local_index % len(profile["rhythms"])],
        "best_for_domains": _dedupe(profile["keywords"] + [x.replace(" ", "-") for x in domain_fit])[:14],
        "complexity_level": _COMPLEXITY_LEVELS[(serial + local_index) % len(_COMPLEXITY_LEVELS)],
        "light_or_dark": _LIGHT_DARK[(serial + local_index) % len(_LIGHT_DARK)],
        "professional_quality_score": quality,
    }


def _build_library() -> list[dict]:
    records = []
    serial = 1
    for category_index, profile in enumerate(_CATEGORY_PROFILES):
        target = 67 if category_index < 10 else 66
        for local_index in range(target):
            records.append(_make_record(profile, serial, local_index))
            serial += 1
    return records


DESIGN_DNA_LIBRARY = _build_library()


def get_all_design_dna() -> list[dict]:
    """Return a defensive copy of every local abstract DNA record."""
    return copy.deepcopy(DESIGN_DNA_LIBRARY)


def get_design_dna_by_category(category: str) -> list[dict]:
    """Return all records whose category matches exactly or by case-insensitive text."""
    needle = str(category or "").strip().lower()
    if not needle:
        return []
    records = [
        r for r in DESIGN_DNA_LIBRARY
        if r["category"].lower() == needle or needle in r["category"].lower()
    ]
    return copy.deepcopy(records)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _record_search_blob(record: dict) -> str:
    parts = []
    for key, value in record.items():
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        else:
            parts.append(str(value))
    return " ".join(parts).lower()


def _domain_boost(record: dict, prompt: str, words: set[str]) -> int:
    category = record.get("category", "")
    profile = next((p for p in _CATEGORY_PROFILES if p["category"] == category), None)
    if not profile:
        return 0
    boost = 0
    hay = prompt.lower()
    for keyword in profile["keywords"]:
        key_words = _tokens(keyword)
        if keyword in hay or key_words.intersection(words):
            boost += 8
    if category == "Healthcare / Hospital / Clinic" and {"hospital", "clinic", "patient", "doctor", "appointment", "lab", "emergency", "portal"}.intersection(words):
        boost += 35
    if category == "Vehicle Sales / Automotive" and {"vehicle", "automotive", "car", "dealer", "financing", "inventory", "drive"}.intersection(words):
        boost += 35
    if category == "AI / Developer Tools" and {"ai", "api", "developer", "devtool", "code", "agent", "automation"}.intersection(words):
        boost += 35
    if category == "Education / Media / Content" and {"course", "education", "learning", "student", "teacher", "lesson", "catalog"}.intersection(words):
        boost += 35
    if category == "Ecommerce / Product" and {"product", "shop", "store", "marketplace", "sales", "catalog"}.intersection(words):
        boost += 12
    if category == "SaaS / Productivity" and {"dashboard", "portal", "workflow", "management", "software"}.intersection(words):
        boost += 10
    return boost


def search_design_dna(prompt: str, max_results: int = 12) -> list[dict]:
    """Search the offline DNA library using domain and pattern keywords.

    For large SRS JSON inputs the token set can be thousands of items, making
    per-record regex searches very slow. Truncate the prompt to 600 characters
    before tokenising so the search stays fast regardless of input size."""
    prompt = str(prompt or "")
    # For large SRS JSON inputs the token set can be enormous. Limit to the first
    # 1500 chars (always contains the project_name/system_category/app_summary)
    # + a snippet from later to catch any domain keywords buried deeper.
    if len(prompt) > 1500:
        search_text = prompt[:1200] + " " + prompt[len(prompt)//4:len(prompt)//4 + 300]
    else:
        search_text = prompt
    words = _tokens(search_text)
    max_results = max(1, int(max_results or 12))
    scored = []
    for record in DESIGN_DNA_LIBRARY:
        blob = _record_search_blob(record)
        lexical = sum(1 for w in words if len(w) > 1 and re.search(rf"\b{re.escape(w)}\b", blob))
        phrase_hits = sum(4 for fit in record.get("domain_fit", []) if str(fit).lower() in search_text.lower())
        score = lexical + phrase_hits + _domain_boost(record, search_text, words)
        if score:
            scored.append((score, record["professional_quality_score"], record["id"], record))
    if not scored:
        scored = [
            (record["professional_quality_score"], record["professional_quality_score"], record["id"], record)
            for record in DESIGN_DNA_LIBRARY
        ]
    scored.sort(key=lambda row: (-row[0], -row[1], row[2]))

    selected = []
    category_counts = Counter()
    for _score, _quality, _id, record in scored:
        if len(selected) >= max_results:
            break
        limit = max(3, max_results // 2)
        if category_counts[record["category"]] >= limit and len(category_counts) < 3:
            continue
        selected.append(record)
        category_counts[record["category"]] += 1
    return copy.deepcopy(selected[:max_results])


def summarize_design_dna(records: list[dict]) -> dict:
    """Summarize categories, families, visual systems, and dominant patterns."""
    records = list(records or [])
    category_counts = Counter(r.get("category", "") for r in records)
    family_counts = Counter(r.get("design_family", "") for r in records)
    palette_counts = Counter(r.get("color_palette_family", "") for r in records)
    light_counts = Counter(r.get("light_or_dark", "") for r in records)
    hero_counts = Counter()
    section_counts = Counter()
    for record in records:
        hero_counts.update(record.get("hero_patterns") or [])
        section_counts.update(record.get("section_patterns") or [])
    return {
        "total": len(records),
        "categories": sorted(k for k in category_counts if k),
        "category_counts": dict(category_counts),
        "top_design_families": [x for x, _n in family_counts.most_common(8)],
        "top_hero_patterns": [x for x, _n in hero_counts.most_common(8)],
        "top_section_patterns": [x for x, _n in section_counts.most_common(10)],
        "palette_families": [x for x, _n in palette_counts.most_common(8)],
        "light_or_dark": dict(light_counts),
    }


def _flatten_strings(value) -> list[str]:
    if isinstance(value, dict):
        out = []
        for v in value.values():
            out.extend(_flatten_strings(v))
        return out
    if isinstance(value, list):
        out = []
        for v in value:
            out.extend(_flatten_strings(v))
        return out
    if isinstance(value, str):
        return [value]
    return []


def _contains_banned_name(text: str) -> str:
    lower = text.lower()
    for banned in sorted(_BANNED_SITE_NAMES, key=len, reverse=True):
        if " " in banned:
            if banned in lower:
                return banned
        elif re.search(rf"\b{re.escape(banned)}\b", lower):
            return banned
    return ""


def validate_design_dna_library() -> dict:
    """Validate size, schema, uniqueness, category breadth, and anti-copy rules."""
    errors = []
    records = DESIGN_DNA_LIBRARY
    if len(records) != 1000:
        errors.append(f"expected 1000 records, found {len(records)}")

    ids = [r.get("id") for r in records]
    if len(set(ids)) != len(ids):
        errors.append("record ids are not unique")

    categories = {r.get("category") for r in records}
    if len(categories) < 15:
        errors.append(f"expected at least 15 categories, found {len(categories)}")

    for idx, record in enumerate(records):
        missing = REQUIRED_FIELDS - set(record)
        if missing:
            errors.append(f"{record.get('id', idx)} missing fields: {sorted(missing)}")
        for field in ("hero_patterns", "nav_patterns", "section_patterns", "card_patterns", "CTA_patterns", "footer_patterns", "domain_fit", "best_for_domains"):
            if not isinstance(record.get(field), list) or not record.get(field):
                errors.append(f"{record.get('id', idx)} field {field} must be a non-empty list")
        if not isinstance(record.get("professional_quality_score"), (int, float)):
            errors.append(f"{record.get('id', idx)} professional_quality_score must be numeric")
        for text in _flatten_strings(record):
            if _URL_RE.search(text):
                errors.append(f"{record.get('id', idx)} contains URL-like text: {text}")
            if _IMAGE_PATH_RE.search(text):
                errors.append(f"{record.get('id', idx)} contains image-path-like text: {text}")
            banned = _contains_banned_name(text)
            if banned:
                errors.append(f"{record.get('id', idx)} contains banned site name: {banned}")
    return {
        "ok": not errors,
        "errors": errors,
        "record_count": len(records),
        "category_count": len(categories),
    }
