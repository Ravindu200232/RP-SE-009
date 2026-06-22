"""Generic route intelligence: page-intent detection + domain×intent section rules.

Nothing here is keyed on app names. A page's intent is inferred from its domain,
route slug, title, nav label, the user prompt, the app features, and the page
blueprint — using a synonym table so unseen routes ("areas", "districts",
"timetable", "advisors") resolve to the right intent. Each (domain, intent) rule
declares required / allowed / denied semantic groups, preferred section &
component types, min unique groups, max duplicate groups, and the hero visual
type. `enforce_route_rules` rewrites a section plan to satisfy the rule while
KEEPING each slot's legacy `data-page-section` marker (duplicate/denied markers
are replaced with an equivalent allowed section, never dropped).
"""
from __future__ import annotations

import re

from app.professional_sections import semantic_group_for


# --------------------------------------------------------------------------- #
# Page intent taxonomy + route synonyms
# --------------------------------------------------------------------------- #

PAGE_INTENTS = [
    "homepage", "listing_search", "neighborhood_discovery", "booking_flow",
    "profile_directory", "service_catalog", "dashboard_portal", "operations_management",
    "compliance_security", "reporting_analytics", "education_catalog", "schedule_calendar",
    "results_progress", "destination_discovery", "ecommerce_collection", "product_detail",
    "pricing_plans", "contact_support", "about_trust", "faq_help",
]

# (keywords, intent) — most specific first; matched against slug/title/nav/prompt.
_SYNONYMS = [
    (["neighborhood", "neighbourhood", "area", "district", "community", "places-to-live", "locality"], "neighborhood_discovery"),
    (["book-tour", "schedule-visit", "schedule-tour", "reserve", "reservation", "appointment", "test-drive", "plan-trip", "enroll-now", "book-now"], "booking_flow"),
    (["class-schedule", "timetable", "calendar", "schedule", "sessions", "session-times"], "schedule_calendar"),
    (["member-result", "progress", "outcome", "results", "transformation", "achievement"], "results_progress"),
    (["compliance", "security", "privacy", "audit", "encryption", "access-control", "governance"], "compliance_security"),
    (["provider-portal", "staff-portal", "patient-portal", "portal", "dashboard", "console", "workspace", "back-office"], "dashboard_portal"),
    (["operations", "clinic-management", "management", "resource", "staffing", "operations-management"], "operations_management"),
    (["report", "analytics", "reporting", "insight", "statement"], "reporting_analytics"),
    (["book-tour", "schedule-visit", "reserve", "reservation", "appointment", "book", "booking", "test-drive", "plan-trip", "enroll-now"], "booking_flow"),
    (["agent", "advisor", "expert", "coach", "trainer", "doctor", "physician", "instructor", "guide", "team", "staff-directory", "our-people"], "profile_directory"),
    (["destination", "tour", "trip", "getaway"], "destination_discovery"),
    (["course", "curriculum", "learning-path", "lesson", "module", "catalog-course"], "education_catalog"),
    (["pricing", "plans", "membership", "subscription", "packages-price"], "pricing_plans"),
    (["listing", "properties", "property-search", "inventory", "vehicles", "stock"], "listing_search"),
    (["products", "shop", "collection", "catalog", "store", "menu", "dishes"], "ecommerce_collection"),
    (["service", "patient-service", "department", "what-we-do", "offerings", "treatments"], "service_catalog"),
    (["contact", "support", "help", "get-in-touch"], "contact_support"),
    (["faq", "questions", "help-center"], "faq_help"),
    (["about", "story", "who-we-are", "mission"], "about_trust"),
]

# Domain hints that disambiguate "listing"-style routes.
_LISTING_AS_ECOMMERCE = {"ecommerce"}
_LISTING_AS_INVENTORY = {"vehicle", "pos-erp"}


def detect_page_intent(domain="", slug="", title="", nav_label="", prompt="",
                       features=None, blueprint=None, position=None) -> str:
    """Infer the page intent from all available signals."""
    bp = blueprint or {}
    page_type = str(bp.get("page_type") or "").lower()
    if position == 0 or (slug in ("", "home", "index")) or page_type == "overview":
        return "homepage"

    hay = " ".join([
        str(slug), str(title), str(nav_label), " ".join(str(x) for x in (features or [])),
    ]).lower()
    hay = re.sub(r"[_/]+", "-", hay)

    for keywords, intent in _SYNONYMS:
        if any(kw in hay for kw in keywords):
            if intent == "listing_search" and domain in _LISTING_AS_ECOMMERCE:
                return "ecommerce_collection"
            return intent

    # Fall back to the route blueprint's page_type buckets.
    bucket = {
        "services": "service_catalog", "portal": "dashboard_portal",
        "management": "operations_management", "compliance": "compliance_security",
        "reports": "reporting_analytics", "booking": "booking_flow", "about": "about_trust",
    }.get(page_type)
    return bucket or "service_catalog"


# --------------------------------------------------------------------------- #
# Semantic group <-> section type
# --------------------------------------------------------------------------- #

GROUP_TO_TYPES = {
    "hero": ["hero", "travel destination hero"], "footer": ["footer"], "nav": ["navbar"],
    "property_listing": ["property listing grid", "property search"],
    "neighborhood_info": ["gallery", "service grid"], "map_location": ["gallery", "search panel"],
    "amenities": ["feature grid", "service grid"],
    "patient_services": ["department grid", "patient portal"], "doctor_search": ["doctor search"],
    "appointment_booking": ["appointment cta"], "booking": ["booking flow"],
    "reservation_booking": ["reservation section"], "restaurant_menu": ["restaurant menu preview"],
    "itinerary_packages": ["itinerary cards"], "travel_destinations": ["itinerary cards", "gallery"],
    "fitness_programs": ["fitness program cards"], "trainer_profiles": ["trainer profile section"],
    "member_results": ["fitness program cards", "stats strip"],
    "class_schedule": ["service grid", "timeline"],
    "education_courses": ["course catalog", "learning path section"],
    "ai_console": ["ai api panel", "developer workflow section"],
    "vehicle_inventory": ["vehicle inventory grid"],
    "ecommerce_collection": ["product showcase", "product collection grid"],
    "generic_pricing": ["pricing"], "invoice_reporting": ["report preview", "fintech transaction preview"],
    "dashboard_metrics": ["dashboard preview", "portal preview"],
    "provider_tools": ["patient portal", "portal preview"], "clinic_operations": ["service grid", "dashboard preview"],
    "generic_services": ["service grid"], "generic_features": ["feature grid"],
    # Part 5B: contextual groups so route blueprints can label generic blocks for
    # their route meaning (a gallery on a neighborhood page IS neighborhood_info).
    "neighborhood_info": ["gallery", "service grid"], "amenities": ["feature grid"],
    "commute_schools": ["service grid"], "local_highlights": ["gallery"],
    "featured_properties": ["property listing grid"], "specialties": ["feature grid"],
    "certifications": ["feature grid"], "availability": ["timeline", "service grid"],
    "member_reviews": ["testimonials"], "restaurant_menu": ["restaurant menu preview"],
    "stats": ["stats strip"], "trust": ["trust badges"], "compliance_security": ["trust badges"],
    "testimonials": ["testimonials"], "faq": ["faq"], "cta": ["cta banner", "appointment cta"],
    "gallery": ["gallery"], "search": ["search panel"], "profile_directory": ["team section"],
    "lab_report": ["lab report preview"], "process": ["timeline"], "app_preview": ["app preview"],
    "generic_content": ["feature grid"],
}


def section_type_for_group(group, domain=""):
    types = GROUP_TO_TYPES.get(group)
    if not types:
        return "feature grid"
    return types[0]


# --------------------------------------------------------------------------- #
# Intent rules (base) + domain overrides
# --------------------------------------------------------------------------- #

def _rule(required, denied=None, allowed=None, hero="primary", min_unique=3, max_dup=2,
          max_counts=None, sections=None, components=None):
    return {
        "required_groups": list(required),
        "allowed_groups": list(allowed or []),
        "denied_groups": list(denied or []),
        "preferred_section_types": list(sections or []),
        "preferred_component_types": list(components or []),
        "min_unique_groups": min_unique,
        "max_duplicate_groups": max_dup,
        "max_group_counts": dict(max_counts or {}),
        "hero_visual": hero,
    }


_NO_SALES = ["generic_pricing", "invoice_reporting"]

_BASE_RULES = {
    "homepage": _rule(["hero"], hero="primary", min_unique=4),
    "listing_search": _rule(["property_listing", "vehicle_inventory", "ecommerce_collection", "search"],
                            denied=["generic_pricing", "invoice_reporting"], hero="search",
                            sections=["search panel", "property listing grid"]),
    "neighborhood_discovery": _rule(["neighborhood_info", "map_location", "gallery", "property_listing"],
                                    denied=_NO_SALES, hero="map",
                                    sections=["gallery", "property listing grid", "trust badges"]),
    "booking_flow": _rule(["booking", "appointment_booking", "reservation_booking"],
                          denied=["invoice_reporting", "generic_pricing"], hero="booking",
                          max_counts={"booking": 1, "appointment_booking": 1, "reservation_booking": 1},
                          sections=["booking flow", "appointment cta"]),
    "profile_directory": _rule(["profile_directory", "trainer_profiles", "doctor_search"],
                               denied=_NO_SALES, hero="profiles",
                               sections=["team section", "trainer profile section", "testimonials"]),
    "service_catalog": _rule(["generic_services", "patient_services", "education_courses", "fitness_programs"],
                             denied=["generic_pricing"], hero="services",
                             sections=["service grid", "department grid"]),
    "dashboard_portal": _rule(["dashboard_metrics", "provider_tools", "app_preview"],
                              hero="dashboard", max_counts={"lab_report": 1, "invoice_reporting": 1},
                              sections=["dashboard preview", "portal preview"]),
    "operations_management": _rule(["dashboard_metrics", "provider_tools", "generic_services", "process"],
                                   hero="operations", max_counts={"generic_services": 1, "patient_services": 1},
                                   sections=["dashboard preview", "service grid", "timeline"]),
    "compliance_security": _rule(["compliance_security", "trust", "generic_features", "invoice_reporting"],
                                 denied=["generic_pricing"], hero="security",
                                 sections=["trust badges", "feature grid", "report preview"]),
    "reporting_analytics": _rule(["invoice_reporting", "dashboard_metrics", "stats"],
                                 hero="dashboard", sections=["report preview", "dashboard preview"]),
    "education_catalog": _rule(["education_courses"], denied=["invoice_reporting"], hero="catalog",
                               sections=["course catalog", "learning path section"]),
    "schedule_calendar": _rule(["class_schedule", "process", "dashboard_metrics", "generic_services"],
                               denied=["invoice_reporting"], hero="schedule",
                               max_counts={"booking": 1, "appointment_booking": 1},
                               sections=["timeline", "service grid"]),
    "results_progress": _rule(["member_results", "fitness_programs", "stats", "dashboard_metrics"],
                              denied=_NO_SALES, hero="results",
                              sections=["fitness program cards", "stats strip"]),
    "destination_discovery": _rule(["travel_destinations", "itinerary_packages", "gallery", "search"],
                                   denied=["invoice_reporting"], hero="destination",
                                   sections=["itinerary cards", "gallery", "search panel"]),
    "ecommerce_collection": _rule(["ecommerce_collection"], hero="collection",
                                  sections=["product collection grid", "product showcase"]),
    "product_detail": _rule(["ecommerce_collection", "gallery"], hero="product",
                            sections=["product showcase", "gallery"]),
    "pricing_plans": _rule(["generic_pricing"], hero="pricing", sections=["pricing"]),
    "contact_support": _rule(["faq", "cta", "search"], hero="contact", sections=["faq", "cta banner"]),
    "about_trust": _rule(["trust", "testimonials", "stats", "profile_directory"], hero="about",
                         sections=["trust badges", "testimonials", "team section"]),
    "faq_help": _rule(["faq"], hero="faq", sections=["faq"]),
}

# (domain, intent) -> partial override (merged onto base).
_DOMAIN_OVERRIDES = {
    ("healthcare", "service_catalog"): {"required_groups": ["patient_services", "appointment_booking", "generic_services"],
                                        "denied_groups": ["generic_pricing", "invoice_reporting"]},
    ("healthcare", "dashboard_portal"): {"required_groups": ["provider_tools", "dashboard_metrics"],
                                         "max_group_counts": {"lab_report": 1, "patient_services": 1}},
    ("healthcare", "operations_management"): {"required_groups": ["clinic_operations", "dashboard_metrics", "generic_services"],
                                              "max_group_counts": {"generic_services": 1, "patient_services": 1}},
    ("real-estate", "neighborhood_discovery"): {"required_groups": ["neighborhood_info", "map_location", "gallery"],
                                                "denied_groups": _NO_SALES},
    ("real-estate", "booking_flow"): {"required_groups": ["booking", "appointment_booking"],
                                      "denied_groups": ["invoice_reporting", "generic_pricing"]},
    ("real-estate", "listing_search"): {"required_groups": ["property_listing", "search"]},
    ("fitness", "profile_directory"): {"required_groups": ["trainer_profiles"], "denied_groups": _NO_SALES,
                                       "preferred_section_types": ["trainer profile section", "team section", "testimonials"]},
    ("healthcare", "profile_directory"): {"required_groups": ["doctor_search"], "denied_groups": _NO_SALES,
                                          "preferred_section_types": ["doctor search", "team section", "trust badges"]},
    ("real-estate", "profile_directory"): {"required_groups": ["profile_directory"], "denied_groups": _NO_SALES,
                                           "preferred_section_types": ["team section", "testimonials", "trust badges"]},
    ("fitness", "schedule_calendar"): {"required_groups": ["class_schedule", "generic_services", "process"],
                                       "max_group_counts": {"booking": 1}, "denied_groups": ["invoice_reporting"]},
    ("fitness", "results_progress"): {"required_groups": ["member_results", "fitness_programs", "stats"],
                                      "denied_groups": _NO_SALES},
    ("vehicle", "listing_search"): {"required_groups": ["vehicle_inventory", "search"]},
    ("ecommerce", "listing_search"): {"required_groups": ["ecommerce_collection"]},
}


def get_route_rule(domain: str, intent: str) -> dict:
    base = dict(_BASE_RULES.get(intent, _BASE_RULES["service_catalog"]))
    base = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
            for k, v in base.items()}
    override = _DOMAIN_OVERRIDES.get((domain, intent))
    if override:
        for k, v in override.items():
            base[k] = v
    base["domain"] = domain
    base["intent"] = intent
    return base


# --------------------------------------------------------------------------- #
# Evaluation + enforcement
# --------------------------------------------------------------------------- #

_PROTECTED = {"hero", "footer", "nav"}
_SAFE_FILLERS = ["generic_features", "trust", "testimonials", "stats", "faq", "cta", "generic_services"]


def route_quality(groups, rule) -> dict:
    """Evaluate a list of semantic groups against a route rule -> {ok, issues}."""
    issues = []
    present = list(groups)
    counts = {}
    for g in present:
        counts[g] = counts.get(g, 0) + 1
    denied = set(rule.get("denied_groups", []))
    for g in present:
        if g in denied:
            issues.append(f"denied group present: {g}")
    if rule.get("required_groups") and not any(g in rule["required_groups"] for g in present):
        issues.append(f"missing required group (any of {rule['required_groups']})")
    max_counts = rule.get("max_group_counts", {})
    default_max = rule.get("max_duplicate_groups", 2)
    for g, c in counts.items():
        cap = max_counts.get(g, default_max)
        if g not in _PROTECTED and c > cap:
            issues.append(f"duplicate group over limit: {g} x{c} (max {cap})")
    unique = len([g for g in set(present) if g not in _PROTECTED])
    if unique < rule.get("min_unique_groups", 3):
        issues.append(f"too few unique groups: {unique} < {rule.get('min_unique_groups', 3)}")
    # de-dup issue strings
    return {"ok": not issues, "issues": sorted(set(issues)), "counts": counts}


def _replacement_group(rule, counts, used_targets, domain):
    """Choose an allowed, under-capacity group to replace a denied/duplicate slot."""
    max_counts = rule.get("max_group_counts", {})
    default_max = rule.get("max_duplicate_groups", 2)
    denied = set(rule.get("denied_groups", []))
    pool = list(rule.get("required_groups", [])) + _SAFE_FILLERS
    for g in pool:
        if g in denied or g in _PROTECTED:
            continue
        if counts.get(g, 0) >= max_counts.get(g, default_max):
            continue
        if g in used_targets:
            continue
        return g
    return None


def enforce_route_rules(plan, domain, intent):
    """Rewrite a section plan (list of slot dicts with section_type + legacy_identity)
    so it satisfies the route rule, KEEPING every legacy `data-page-section` marker.

    Each slot is updated in place: `section_type` + `semantic_group` may change to
    an equivalent allowed section; the marker (`legacy_identity`) is preserved.
    Returns (plan, report)."""
    rule = get_route_rule(domain, intent)
    denied = set(rule.get("denied_groups", []))
    max_counts = rule.get("max_group_counts", {})
    default_max = rule.get("max_duplicate_groups", 2)
    report = {"domain": domain, "intent": intent, "replacements": [], "injected_required": []}

    for slot in plan:
        slot.setdefault("semantic_group", semantic_group_for(slot.get("section_type", "")))

    # Pass 1: replace denied / over-duplicate slots (never the hero/footer).
    counts = {}
    used_targets = set()
    for slot in plan:
        g = slot["semantic_group"]
        is_protected = g in _PROTECTED
        over = counts.get(g, 0) >= max_counts.get(g, default_max)
        if not is_protected and (g in denied or over):
            newg = _replacement_group(rule, counts, used_targets, domain)
            if newg:
                nt = section_type_for_group(newg, domain)
                report["replacements"].append({
                    "identity": slot.get("legacy_identity"), "from": slot["section_type"],
                    "to": nt, "reason": "denied" if g in denied else "duplicate", "group": g,
                })
                slot["section_type"] = nt
                slot["semantic_group"] = newg
                g = newg
                used_targets.add(newg)
        counts[g] = counts.get(g, 0) + 1

    # Pass 2: ensure at least one required group is present.
    required = rule.get("required_groups", [])
    if required and not any(slot["semantic_group"] in required for slot in plan):
        target_group = next((g for g in required if g not in denied), required[0])
        nt = section_type_for_group(target_group, domain)
        filler = _pick_filler_slot(plan, counts)
        if filler is not None:
            report["injected_required"].append({
                "identity": filler.get("legacy_identity"), "from": filler["section_type"],
                "to": nt, "group": target_group,
            })
            counts[filler["semantic_group"]] = max(0, counts.get(filler["semantic_group"], 1) - 1)
            filler["section_type"] = nt
            filler["semantic_group"] = target_group
            counts[target_group] = counts.get(target_group, 0) + 1

    report["final_groups"] = [slot["semantic_group"] for slot in plan]
    report["quality"] = route_quality(report["final_groups"], rule)
    return plan, report


def _pick_filler_slot(plan, counts):
    """Pick a non-hero/footer slot whose group is generic or over-represented."""
    for slot in plan:
        g = slot["semantic_group"]
        if g in _PROTECTED:
            continue
        if g in ("generic_features", "generic_services", "generic_content", "stats", "trust") or counts.get(g, 0) > 1:
            return slot
    # else any middle slot
    middles = [s for s in plan if s["semantic_group"] not in _PROTECTED]
    return middles[-1] if middles else None


# --------------------------------------------------------------------------- #
# Route blueprints (Part 5B): domain + intent specific data-page-section markers
# --------------------------------------------------------------------------- #
# Each slot = (marker, semantic_group, section_type). The marker is the
# data-page-section identity — domain/intent specific so non-healthcare routes
# NEVER inherit healthcare-default markers. Healthcare keeps its existing
# blueprint identities (handled on the legacy identity path) for continuity.

def _s(marker, group, section_type):
    return {"marker": marker, "group": group, "section_type": section_type}


ROUTE_BLUEPRINTS = {
    ("real-estate", "neighborhood_discovery"): [
        _s("neighborhood-hero", "hero", "hero"),
        _s("neighborhood-info", "neighborhood_info", "gallery"),
        _s("neighborhood-map", "map_location", "gallery"),
        _s("amenities-schools", "amenities", "feature grid"),
        _s("commute-highlights", "commute_schools", "service grid"),
        _s("featured-properties", "featured_properties", "property listing grid"),
        _s("agent-area-cta", "cta", "cta banner"),
    ],
    ("real-estate", "listing_search"): [
        _s("listings-hero", "hero", "hero"),
        _s("property-search", "property_listing", "property search"),
        _s("featured-properties", "featured_properties", "property listing grid"),
        _s("listing-highlights", "amenities", "feature grid"),
        _s("agent-trust", "trust", "trust badges"),
        _s("browse-cta", "cta", "cta banner"),
    ],
    ("real-estate", "profile_directory"): [
        _s("agents-hero", "hero", "hero"),
        _s("agent-profiles", "profile_directory", "team section"),
        _s("agent-specialties", "specialties", "feature grid"),
        _s("agent-reviews", "member_reviews", "testimonials"),
        _s("contact-agent-cta", "cta", "cta banner"),
    ],
    ("real-estate", "booking_flow"): [
        _s("tour-hero", "hero", "hero"),
        _s("tour-availability", "booking", "booking flow"),
        _s("schedule-tour", "appointment_booking", "appointment cta"),
        _s("tour-prep", "process", "timeline"),
        _s("agent-confirm-cta", "cta", "cta banner"),
    ],
    ("fitness", "profile_directory"): [
        _s("trainer-hero", "hero", "hero"),
        _s("trainer-profiles", "trainer_profiles", "trainer profile section"),
        _s("specialties-certifications", "specialties", "feature grid"),
        _s("availability-schedule", "availability", "timeline"),
        _s("member-reviews", "member_reviews", "testimonials"),
        _s("booking-cta", "cta", "cta banner"),
    ],
    ("fitness", "schedule_calendar"): [
        _s("schedule-hero", "hero", "hero"),
        _s("weekly-schedule", "class_schedule", "timeline"),
        _s("class-types", "generic_services", "service grid"),
        _s("trainer-availability", "availability", "feature grid"),
        _s("book-class-cta", "cta", "cta banner"),
    ],
    ("fitness", "results_progress"): [
        _s("results-hero", "hero", "hero"),
        _s("member-progress", "member_results", "stats strip"),
        _s("transformation-stories", "member_reviews", "testimonials"),
        _s("program-outcomes", "fitness_programs", "fitness program cards"),
        _s("start-plan-cta", "cta", "cta banner"),
    ],
    ("fitness", "service_catalog"): [
        _s("programs-hero", "hero", "hero"),
        _s("program-cards", "fitness_programs", "fitness program cards"),
        _s("program-levels", "generic_features", "feature grid"),
        _s("trainer-trust", "trust", "trust badges"),
        _s("join-cta", "cta", "cta banner"),
    ],
    ("restaurant", "ecommerce_collection"): [
        _s("menu-hero", "hero", "hero"),
        _s("menu-categories", "restaurant_menu", "restaurant menu preview"),
        _s("chef-specials", "generic_features", "feature grid"),
        _s("dietary-info", "trust", "trust badges"),
        _s("order-cta", "cta", "cta banner"),
    ],
    ("restaurant", "booking_flow"): [
        _s("reserve-hero", "hero", "hero"),
        _s("reservation-form", "reservation_booking", "reservation section"),
        _s("opening-hours", "generic_services", "service grid"),
        _s("private-dining", "generic_features", "feature grid"),
        _s("reserve-cta", "cta", "reservation section"),
    ],
    ("restaurant", "service_catalog"): [
        _s("location-hero", "hero", "hero"),
        _s("hours-location", "generic_services", "service grid"),
        _s("dining-gallery", "gallery", "gallery"),
        _s("contact-info", "trust", "trust badges"),
        _s("visit-cta", "cta", "reservation section"),
    ],
    ("travel", "destination_discovery"): [
        _s("destination-hero", "hero", "travel destination hero"),
        _s("destination-search", "search", "search panel"),
        _s("featured-destinations", "travel_destinations", "itinerary cards"),
        _s("destination-gallery", "gallery", "gallery"),
        _s("plan-trip-cta", "cta", "cta banner"),
    ],
    ("travel", "booking_flow"): [
        _s("trip-hero", "hero", "travel destination hero"),
        _s("trip-packages", "itinerary_packages", "itinerary cards"),
        _s("trip-booking", "booking", "booking flow"),
        _s("trip-highlights", "generic_features", "feature grid"),
        _s("book-trip-cta", "cta", "cta banner"),
    ],
    ("travel", "profile_directory"): [
        _s("guides-hero", "hero", "hero"),
        _s("guide-profiles", "profile_directory", "team section"),
        _s("guide-specialties", "specialties", "feature grid"),
        _s("guide-reviews", "member_reviews", "testimonials"),
        _s("contact-guide-cta", "cta", "cta banner"),
    ],
    ("business-ops", "listing_search"): [
        _s("inventory-hero", "hero", "hero"),
        _s("product-search", "search", "search panel"),
        _s("product-collection", "ecommerce_collection", "product collection grid"),
        _s("stock-highlights", "dashboard_metrics", "dashboard preview"),
        _s("manage-cta", "cta", "cta banner"),
    ],
    ("business-ops", "reporting_analytics"): [
        _s("reports-hero", "hero", "hero"),
        _s("reports-overview", "invoice_reporting", "report preview"),
        _s("kpi-board", "dashboard_metrics", "dashboard preview"),
        _s("trend-insights", "stats", "stats strip"),
        _s("export-cta", "cta", "cta banner"),
    ],
    ("business-ops", "operations_management"): [
        _s("ops-hero", "hero", "hero"),
        _s("ops-board", "dashboard_metrics", "dashboard preview"),
        _s("resource-grid", "generic_services", "service grid"),
        _s("process-timeline", "process", "timeline"),
        _s("manage-cta", "cta", "cta banner"),
    ],
}


def _generic_blueprint(domain, intent):
    """Build a domain/intent blueprint from the route rule when no curated one
    exists (so unseen domains still get domain-specific, route-correct markers)."""
    rule = get_route_rule(domain, intent)
    hero_type = "travel destination hero" if domain == "travel" else "hero"
    i = intent.replace("_", "-")
    content_groups = [g for g in (rule.get("required_groups") or []) if g not in _PROTECTED]
    # Backfill from preferred section types, then safe defaults, so a page is never
    # just hero + CTA.
    if len(content_groups) < 2:
        for st in (rule.get("preferred_section_types") or []):
            g = semantic_group_for(st)
            if g not in content_groups and g not in _PROTECTED:
                content_groups.append(g)
    for fallback in ("generic_features", "trust", "stats"):
        if len(content_groups) >= 2:
            break
        if fallback not in content_groups:
            content_groups.append(fallback)

    slots = [_s(f"{i}-hero", "hero", hero_type)]
    seen = set()
    for g in content_groups[:4]:
        if g in seen:
            continue
        seen.add(g)
        slots.append(_s(g.replace("_", "-"), g, section_type_for_group(g, domain)))
    cta_type = {"healthcare": "appointment cta", "restaurant": "reservation section"}.get(domain, "cta banner")
    slots.append(_s(f"{i}-cta", "cta", cta_type))
    return slots


def route_blueprint(domain, intent):
    """Domain + intent specific section blueprint (markers + groups + types).
    Always returns a non-empty list (curated if available, else generic)."""
    return ROUTE_BLUEPRINTS.get((domain, intent)) or _generic_blueprint(domain, intent)
