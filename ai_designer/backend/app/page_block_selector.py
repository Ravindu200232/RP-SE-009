"""Page block selector — choose professional section/component IDs per page.

Bridges the page plan (route blueprint + design genome) and the professional
block library (`block_component_registry`). It:

1. infers the page's professional visual family + primary domain from the genome,
2. builds a COMPACT metadata context (never full JSX code) for an LLM,
3. asks the LLM to choose section/component IDs (optional, defensive), and
4. always has a deterministic fallback that picks compatible, high-quality,
   varied blocks and avoids repeating the same block sequence across pages.

Selection output (the contract used by `page_assembler`):

    {
      "page_slug": "...",
      "page_purpose": "...",
      "selected_sections": [{"section_id", "reason", "props_needed", ...}],
      "selected_components": [{"component_id", "reason"}]
    }

The selector NEVER sends section/component JSX to the LLM — only metadata.
"""
from __future__ import annotations

import json
import re

from app import professional_components as pc
from app import professional_sections as ps
from app import block_component_registry as bcr
from app import route_block_rules as rbr


# --------------------------------------------------------------------------- #
# Genome family/domain -> professional family/domain
# --------------------------------------------------------------------------- #

# Genome `visual_family` (design_recipes) and `inspiration_family` (DNA library)
# slugs map onto the professional library's family slugs.
_DNA_TO_PRO_FAMILY = {
    "healthcare-clinical": "clinical-trust",
    "healthcare-trust-saas": "healthcare-saas",
    "trust-saas": "healthcare-saas",
    "service-trust": "healthcare-saas",
    "automotive-showroom": "premium-automotive",
    "product-commerce": "ecommerce-premium",
    "ecommerce-product": "ecommerce-premium",
    "developer-console": "devtool-console",
    "ai-devtools": "devtool-console",
    "learning-editorial": "education-editorial",
    "education-media": "education-editorial",
    "restaurant-reservation": "restaurant-editorial",
    "travel-destination": "travel-destination",
    "real-estate-listings": "real-estate-listing",
    "fitness-coaching": "fitness-coaching",
    "creative-portfolio": "agency-editorial",
    "creative-agency": "agency-editorial",
    "finance-trust": "fintech-trust",
    "fintech-trust": "fintech-trust",
    "operations-console": "dashboard-operations",
    "operational-business": "dashboard-operations",
    "saas-productivity": "saas-gradient",
}

_DNA_TO_DOMAIN = {
    "healthcare-clinical": "healthcare", "healthcare-trust-saas": "healthcare",
    "trust-saas": "saas", "service-trust": "saas",
    "automotive-showroom": "automotive",
    "product-commerce": "ecommerce", "ecommerce-product": "ecommerce",
    "developer-console": "ai-devtools", "ai-devtools": "ai-devtools",
    "learning-editorial": "education", "education-media": "education",
    "restaurant-reservation": "restaurant",
    "travel-destination": "travel",
    "real-estate-listings": "real-estate",
    "fitness-coaching": "fitness",
    "creative-portfolio": "agency", "creative-agency": "agency",
    "finance-trust": "fintech", "fintech-trust": "fintech",
    "operations-console": "business-ops", "operational-business": "business-ops",
    "saas-productivity": "saas",
}


# Each domain maps to a SET of compatible professional families (first = canonical).
# The genome rotates within the set, so two apps of the same domain can render in
# different palettes — coherent per app, varied app-to-app and run-to-run.
_DOMAIN_PRO_FAMILIES = {
    "healthcare": ["clinical-trust", "healthcare-saas", "fintech-trust"],
    "automotive": ["premium-automotive", "ecommerce-premium", "dashboard-operations"],
    "restaurant": ["restaurant-editorial", "travel-destination", "agency-editorial"],
    "real-estate": ["real-estate-listing", "ecommerce-premium", "fintech-trust"],
    "travel": ["travel-destination", "restaurant-editorial", "community-social"],
    "fitness": ["fitness-coaching", "community-social", "education-editorial"],
    "education": ["education-editorial", "community-social", "saas-gradient"],
    "ecommerce": ["ecommerce-premium", "premium-automotive", "restaurant-editorial"],
    "saas": ["saas-gradient", "dashboard-operations", "fintech-trust"],
    "ai-devtools": ["devtool-console", "saas-gradient", "dashboard-operations"],
    "business-ops": ["dashboard-operations", "fintech-trust", "saas-gradient"],
    "fintech": ["fintech-trust", "dashboard-operations", "saas-gradient"],
    "agency": ["agency-editorial", "community-social", "education-editorial"],
    "community": ["community-social", "agency-editorial", "fitness-coaching"],
    "media": ["education-editorial", "agency-editorial", "community-social"],
}


def _family_seed(genome):
    genome = genome or {}
    raw = "|".join([
        str(genome.get("app_seed", "")),
        ",".join(genome.get("dna_profile_ids") or []),
        str(genome.get("inspiration_family", "")),
        str((genome.get("hero_recipe") or {}).get("id", "")),
        str(genome.get("card_style", "")),
    ])
    return sum((i + 1) * ord(c) for i, c in enumerate(raw)) or 3


def resolve_family_and_domain(prompt: str, genome: dict) -> tuple:
    """Pick a professional (visual_family, domain) for this page. The domain is
    derived from the genome/prompt; the family is rotated within the domain's
    compatible set by a genome seed so apps of the same domain vary in palette."""
    genome = genome or {}
    vf = str(genome.get("visual_family") or "")
    inf = str(genome.get("inspiration_family") or "")
    dom = _DNA_TO_DOMAIN.get(vf) or _DNA_TO_DOMAIN.get(inf)
    if not dom:
        dom = next(iter(pc.prompt_domains(prompt)), None)
    if not dom:
        dom = "saas"

    fam_set = list(_DOMAIN_PRO_FAMILIES.get(dom) or [])
    primary = _DNA_TO_PRO_FAMILY.get(vf) or _DNA_TO_PRO_FAMILY.get(inf)
    if primary and primary in pc.VISUAL_FAMILIES:
        fam_set = [primary] + [f for f in fam_set if f != primary]
    if not fam_set:
        fam_set = [next((f for f in pc.VISUAL_FAMILIES if dom in pc._FAMILIES.get(f, {}).get("domains", [])),
                        "saas-gradient")]
    fam = fam_set[_family_seed(genome) % len(fam_set)]
    return fam, dom


# --------------------------------------------------------------------------- #
# Domain-aware section-type resolvers
# --------------------------------------------------------------------------- #

def _catalog_type(domain):
    return {
        "healthcare": "department grid", "ecommerce": "product showcase",
        "automotive": "vehicle inventory grid", "restaurant": "restaurant menu preview",
        "real-estate": "property listing grid", "travel": "itinerary cards",
        "fitness": "fitness program cards", "education": "course catalog",
        "ai-devtools": "feature grid", "fintech": "feature grid",
        "business-ops": "service grid", "agency": "service grid",
        "community": "team section", "media": "gallery", "saas": "feature grid",
    }.get(domain, "service grid")


def _grid_type(domain):
    return {
        "automotive": "vehicle inventory grid", "ecommerce": "product collection grid",
        "real-estate": "property listing grid", "restaurant": "restaurant menu preview",
        "travel": "itinerary cards", "fitness": "fitness program cards",
        "education": "course catalog",
    }.get(domain, "product showcase")


def _cta_type(domain):
    return {"healthcare": "appointment cta", "restaurant": "reservation section"}.get(domain, "cta banner")


def _booking_type(domain):
    return {"restaurant": "reservation section"}.get(domain, "booking flow")


def _portal_type(domain):
    return {
        "healthcare": "patient portal", "ai-devtools": "developer workflow section",
        "fintech": "fintech transaction preview",
    }.get(domain, "dashboard preview")


def _report_type(domain):
    return {
        "healthcare": "lab report preview", "fintech": "fintech transaction preview",
    }.get(domain, "report preview")


def _hero_type(domain):
    return "travel destination hero" if domain == "travel" else "hero"


# Ordered keyword rules: (keywords, resolver). First match wins. CTA identities
# are resolved before booking/portal so "...-cta" never falls through to a flow.
_IDENTITY_RULES = [
    (("faq",), lambda d: "faq"),
    (("footer",), lambda d: "footer"),
    (("navbar",), lambda d: "navbar"),
    (("cta", "get-started", "enroll-now", "sign-up", "contact", "trade-in", "trade in", "provider-login", "login"),
     _cta_type),
    (("booking", "appointment", "availability", "reserve", "reservation", "confirmation", "visit-prep", "visit prep"),
     lambda d: _booking_type(d)),
    (("doctor", "find-a-doctor", "physician"), lambda d: "doctor search" if d == "healthcare" else "search panel"),
    (("search",), lambda d: "search panel"),
    (("portal", "dashboard", "console-preview", "developer-console-preview", "workspace"), _portal_type),
    (("lab", "report", "records", "record", "analytics", "trend", "export", "prescription", "insight"), _report_type),
    (("schedule", "queue", "staff", "resource", "operations", "workflow", "automation"),
     lambda d: _portal_type(d) if d in ("ai-devtools", "business-ops", "fintech", "saas") else "service grid"),
    (("api", "docs", "integration", "developer"), lambda d: "ai api panel" if d == "ai-devtools" else "feature grid"),
    # Compliance/security identities map to DISTINCT section types so a security
    # page reads as a varied layout (not four identical trust bands).
    (("audit", "log"), _report_type),
    (("access-control", "data-access", "access", "permission", "role-based"), lambda d: "feature grid"),
    (("encryption", "backup", "recovery"), lambda d: "service grid"),
    (("security", "compliance", "standard", "trust", "certif"), lambda d: "trust badges"),
    (("insurance", "payment", "pricing", "financing", "plans", "billing"), lambda d: "pricing"),
    (("menu", "chef", "food", "dining"), lambda d: "restaurant menu preview"),
    (("trainer", "coach"), lambda d: "trainer profile section" if d == "fitness" else "team section"),
    (("program", "class", "workout", "member", "transformation", "result"),
     lambda d: "fitness program cards" if d == "fitness" else _catalog_type(d)),
    (("inventory", "vehicle", "spotlight", "showroom", "collection", "product"), _grid_type),
    (("property", "listing", "neighborhood"), lambda d: "property listing grid"),
    (("destination", "itinerary", "trip", "tour", "guide", "package"), lambda d: "itinerary cards"),
    (("course", "learning", "instructor", "lesson", "media-library", "enrollment", "curriculum", "path"),
     lambda d: "learning path section" if d == "education" else _catalog_type(d)),
    (("department", "clinic", "catalog", "service", "specialt", "care-team", "care team", "team", "feature", "capabilit"),
     _catalog_type),
    (("gallery", "media", "showcase"), lambda d: "gallery" if d in ("media", "agency", "travel", "restaurant") else "product showcase"),
    (("testimonial", "review", "story", "community", "impact", "proof"), lambda d: "testimonials"),
    (("stat", "metric", "overview", "numbers"), lambda d: "stats strip"),
    (("emergency",), lambda d: "appointment cta" if d == "healthcare" else "cta banner"),
]


def map_identity_to_section_type(identity: str, domain: str, position: int = 1) -> str:
    """Map a legacy route-section identity (e.g. 'doctor-search-preview') to a
    professional section_type, domain-aware. Position 0 is treated as the hero."""
    s = str(identity or "").lower()
    if position == 0 or s.endswith("-hero") or s == "hero":
        return _hero_type(domain)
    for keys, resolver in _IDENTITY_RULES:
        if any(k in s for k in keys):
            return resolver(domain)
    return _catalog_type(domain)


# Generic plan (when a page has no explicit section identities).
def _generic_plan(domain, page_type):
    plan = [_hero_type(domain), _catalog_type(domain)]
    pt = str(page_type or "").lower()
    if pt in ("portal", "management", "reports", "app"):
        plan += [_portal_type(domain), _report_type(domain)]
    elif pt in ("compliance",):
        plan += ["trust badges", "feature grid"]
    elif pt in ("services", "booking"):
        plan += [_booking_type(domain), "faq"]
    else:
        plan += ["stats strip", "testimonials"]
    plan.append(_cta_type(domain))
    return plan


# --------------------------------------------------------------------------- #
# Deterministic selection
# --------------------------------------------------------------------------- #

def _seed(genome, slug):
    raw = str((genome or {}).get("app_seed", "")) + "|" + str(slug or "")
    return sum((i + 1) * ord(c) for i, c in enumerate(raw)) or 7


def _resolve_section_id(section_type, family, used_ids, salt):
    """Pick a concrete section_id for (type, family), rotating by salt for
    anti-repeat, preferring high quality and not-yet-used records."""
    pool = ps.get_sections_by_type(section_type, family=family) or ps.get_sections_by_type(section_type)
    if not pool:
        pool = ps.get_sections_by_type("feature grid", family=family) or ps.get_all_sections()[:1]
    fresh = [s for s in pool if s["section_id"] not in used_ids] or pool
    fresh = sorted(fresh, key=lambda s: (-s.get("quality_score", 0), s["section_id"]))
    return fresh[salt % len(fresh)]["section_id"]


# Domain headlines give each app's home hero a distinct, on-domain H1 instead of
# a single generic title repeated across every page.
_DOMAIN_HEADLINES = {
    "healthcare": "Compassionate care, organized around you",
    "automotive": "Find the vehicle that fits your life",
    "restaurant": "A table set for every occasion",
    "real-estate": "Find a place to call home",
    "travel": "Your next journey starts here",
    "fitness": "Train with a plan that actually works",
    "education": "Learn skills that move you forward",
    "ecommerce": "Products designed for everyday life",
    "saas": "The faster way to run your work",
    "ai-devtools": "Ship AI features with confidence",
    "business-ops": "Run operations without the chaos",
    "fintech": "Move money with clarity and trust",
    "agency": "Ideas, crafted into experiences",
    "community": "Where your people come together",
    "media": "Stories worth your attention",
}


# Domain-correct hero subtitles. Using these (instead of the route blueprint's
# page-type `purpose`, which is healthcare-defaulted) prevents cross-domain copy
# leaks like "Patient service catalog" appearing on a restaurant page.
_DOMAIN_SUBTITLES = {
    "healthcare": "Book care, find the right doctor, and manage records with ease.",
    "automotive": "Browse certified inventory, compare, and book a test drive.",
    "restaurant": "Reserve a table, browse the menu, and plan your visit.",
    "real-estate": "Search listings and book a tour with agents you can trust.",
    "travel": "Discover destinations and plan the perfect trip, end to end.",
    "fitness": "Find programs, meet trainers, and book your classes.",
    "education": "Explore courses and follow a clear path to mastery.",
    "ecommerce": "Discover products designed for everyday life.",
    "saas": "Plan, track, and ship your work in one calm place.",
    "ai-devtools": "Build, ship, and observe AI features with confidence.",
    "business-ops": "Run operations, track resources, and report with ease.",
    "fintech": "Move money, track spending, and stay in control.",
    "agency": "Strategy, design, and delivery under one roof.",
    "community": "Connect, share, and grow together with your people.",
    "media": "Discover stories and content worth your time.",
}


def _hero_title(domain, page_blueprint):
    """Home/overview pages get a domain headline; secondary pages use their own
    name so each page's hero is distinct."""
    pb = page_blueprint or {}
    name = str(pb.get("name") or "").strip()
    page_type = str(pb.get("page_type") or "").lower()
    if name and name.lower() not in ("home", "overview") and page_type not in ("overview",):
        return name[:60]
    return _DOMAIN_HEADLINES.get(domain, "Built for the work you do")


def _default_props(section_type, page_blueprint, prompt, domain="saas", app_name=""):
    """Minimal, safe, domain-flavored prop overrides. Defaults in the renderers
    already produce complete output, so we only override identity/brand/copy fields."""
    pb = page_blueprint or {}
    props = {}
    if section_type in ("hero", "travel destination hero"):
        props["title"] = _hero_title(domain, pb)
        props["subtitle"] = _DOMAIN_SUBTITLES.get(domain, "Everything you need, in one place.")
        props["domain"] = domain
        name = str(pb.get("name") or "").strip().lower()
        page_type = str(pb.get("page_type") or "").lower()
        props["hero_panel_variant"] = "primary" if (name in ("", "home", "overview") or page_type == "overview") else "secondary"
        if pb.get("name"):
            props["eyebrow"] = str(pb["name"])[:40]
    if section_type in ("navbar", "footer") and app_name:
        props["brand"] = app_name[:24]
    return props


def _select_components(selected_sections, family, domain, salt):
    """A few representative components for the page (for downstream tooling)."""
    types, seen = [], set()
    for s in selected_sections:
        for dep in ps.SECTION_DEPENDENCIES.get(s.get("section_type", ""), []):
            if dep not in seen:
                seen.add(dep)
                types.append(dep)
    out, used = [], set()
    for i, ctype in enumerate(types[:6]):
        pool = pc.get_components_by_type(ctype, family=family) or pc.get_components_by_type(ctype)
        if not pool:
            continue
        pick = pool[(salt + i) % len(pool)]
        if pick["component_id"] in used:
            continue
        used.add(pick["component_id"])
        out.append({"component_id": pick["component_id"],
                    "reason": f"{ctype} supports the {domain} page composition"})
    return out


# Mapping from home-page section_catalog family names to professional section_types.
# When a home page uses stats_band, sub-pages skip "stats strip" to avoid repeats.
_FAMILY_TO_SECTION_TYPE: dict[str, str] = {
    "stats_band":       "stats strip",   "metrics_cards":    "stats strip",
    "testimonials_grid":"testimonials",  "testimonial_big":  "testimonials",
    "review_wall":      "testimonials",
    "pricing":          "pricing",       "pricing_plans":    "pricing",
    "faq":              "faq",
    "gallery":          "gallery",       "product_showcase": "product showcase",
    "features_grid":    "feature grid",  "bento":            "feature grid",
    "value_props":      "service grid",
    "team":             "team section",
    "newsletter":       "newsletter",
    "contact_split":    "contact form",
    "logos_strip":      "trust badges",
    "cta_band":         "cta banner",    "banner_announce":  "cta banner",
    "timeline":         "timeline",
    "steps":            "process steps",
    "comparison":       "pricing",
    "integrations_grid":"feature grid",
}


def deterministic_select_blocks_for_page(prompt: str, page_blueprint: dict, genome: dict) -> dict:
    """Pick compatible, varied, high-quality blocks with no LLM, enforcing the
    domain×page-intent route rule (required/denied/duplicate semantic groups)."""
    pb = page_blueprint or {}
    family, domain = resolve_family_and_domain(prompt, genome)
    slug = pb.get("slug") or "page"
    purpose = pb.get("purpose") or f"{pb.get('name', 'Page')} for {domain}"
    page_type = pb.get("page_type") or ""
    identities = [i for i in (pb.get("sections") or []) if str(i).strip()]
    features = pb.get("features") or pb.get("key_features") or []
    salt = _seed(genome, slug)

    # Build excluded section types from cross-page family tracking (home page → sub-pages).
    _excl_fams = list((genome or {}).get("exclude_families") or [])
    exclude_section_types: set[str] = {
        _FAMILY_TO_SECTION_TYPE[f] for f in _excl_fams if f in _FAMILY_TO_SECTION_TYPE
    }

    intent = rbr.detect_page_intent(
        domain=domain, slug=slug, title=pb.get("name", ""), nav_label=pb.get("nav_label", ""),
        prompt=prompt, features=features, blueprint=pb,
    )

    # Build the per-slot plan (hero first), tag semantic groups, enforce route rules.
    # Home pages + healthcare already use domain-specific blueprints (no healthcare
    # leak there); only non-healthcare SECONDARY routes need the blueprint override.
    if identities and (domain == "healthcare" or intent == "homepage"):
        plan = []
        for i, ident in enumerate(identities):
            st = map_identity_to_section_type(ident, domain, i)
            plan.append({"legacy_identity": ident, "section_type": st,
                         "semantic_group": ps.semantic_group_for(st)})
    else:
        # Every other route uses a domain + intent BLUEPRINT, so its markers,
        # groups, and section types are domain-specific (no healthcare leak) and
        # route-correct (e.g. a Neighborhoods page gets neighborhood/map/amenities).
        slots = rbr.route_blueprint(domain, intent)
        plan = [{"legacy_identity": s["marker"], "section_type": s["section_type"],
                 "semantic_group": s["group"]} for s in slots]
    for slot in plan:
        slot.setdefault("semantic_group", ps.semantic_group_for(slot["section_type"]))
    plan, route_report = rbr.enforce_route_rules(plan, domain, intent)

    selected, used = [], set()
    for i, slot in enumerate(plan):
        stype = slot["section_type"]
        # Skip section types that were already used on the home page.
        if stype in exclude_section_types and stype not in ("hero", "navbar", "footer", "cta banner"):
            continue
        sid = _resolve_section_id(stype, family, used, salt + i * 7)
        used.add(sid)
        selected.append({
            "section_id": sid,
            "section_type": stype,
            "semantic_group": slot["semantic_group"],
            "visual_family": family,
            "legacy_identity": slot["legacy_identity"],
            "reason": f"{stype} fits the {domain} {intent} page ({slot['legacy_identity'] or 'generic slot'})",
            "props_needed": _default_props(stype, pb, prompt, domain=domain),
        })

    if not any(s["section_type"] == "footer" for s in selected):
        sid = _resolve_section_id("footer", family, used, salt + 991)
        selected.append({"section_id": sid, "section_type": "footer", "semantic_group": "footer",
                         "visual_family": family, "legacy_identity": None,
                         "reason": "site footer", "props_needed": {}})

    components = _select_components(selected, family, domain, salt)
    return {
        "page_slug": slug,
        "page_purpose": purpose,
        "selected_sections": selected,
        "selected_components": components,
        "visual_family": family,
        "domain": domain,
        "intent": intent,
        "route_report": route_report,
        "source": "deterministic",
    }


# --------------------------------------------------------------------------- #
# Compact LLM context (metadata only — never JSX)
# --------------------------------------------------------------------------- #

# The ONLY section fields ever exposed to the LLM.
_LLM_SECTION_FIELDS = (
    "section_id", "section_type", "domain_fit", "visual_family",
    "quality_score", "required_props", "preview_description", "selection_summary",
)
_LLM_COMPONENT_FIELDS = (
    "component_id", "component_type", "domain_fit", "visual_family", "quality_score", "selection_summary",
)


def build_block_selection_context(prompt: str, page_blueprint: dict, genome: dict) -> dict:
    """Compact, code-free metadata context for the LLM selector.

    Contains candidate section/component METADATA only (the exact fields the spec
    allows) plus page info. It never contains render functions or JSX code.
    """
    pb = page_blueprint or {}
    family, domain = resolve_family_and_domain(prompt, genome)
    query = " ".join([
        str(prompt or ""), str(pb.get("purpose", "")), str(pb.get("name", "")),
        " ".join(str(s) for s in (pb.get("sections") or [])),
    ]).strip()

    sec_cands = bcr.search_sections(query or domain, max_results=40)
    focused = [s for s in sec_cands if s["visual_family"] == family or domain in s.get("domain_fit", [])]
    sec_cands = (focused or sec_cands)[:24]
    comp_cands = bcr.search_components(query or domain, max_results=18)
    comp_focused = [c for c in comp_cands if c["visual_family"] == family or domain in c.get("domain_fit", [])]
    comp_cands = (comp_focused or comp_cands)[:14]

    return {
        "page": {
            "slug": pb.get("slug"), "name": pb.get("name"),
            "purpose": pb.get("purpose"), "page_type": pb.get("page_type"),
            "section_identities": list(pb.get("sections") or []),
        },
        "domain": domain,
        "visual_family": family,
        "candidate_sections": [{k: s.get(k) for k in _LLM_SECTION_FIELDS} for s in sec_cands],
        "candidate_components": [{k: c.get(k) for k in _LLM_COMPONENT_FIELDS} for c in comp_cands],
    }


_LLM_SYSTEM = (
    "You are a senior web designer assembling ONE page from a library of pre-built, "
    "production-ready sections. You are given page info and CANDIDATE section/component "
    "METADATA only (never code). Choose 4-7 sections that best fit the page purpose and "
    "domain, in a sensible order (start with a hero, end with a footer or strong CTA). "
    "You MUST only use section_id / component_id values that appear in the candidates. "
    "Respond with STRICT JSON and nothing else, in this shape:\n"
    '{"page_slug": "...", "page_purpose": "...", '
    '"selected_sections": [{"section_id": "...", "reason": "...", "props_needed": {}}], '
    '"selected_components": [{"component_id": "...", "reason": "..."}]}'
)


def _llm_select(context: dict):
    """Call the LLM with compact metadata; return parsed JSON or raise."""
    from app.agents import get_llm, ensure_ollama, extract_json  # lazy: keep import optional
    from langchain_core.prompts import ChatPromptTemplate

    if not ensure_ollama():
        raise RuntimeError("LLM runtime unavailable")
    chain = ChatPromptTemplate.from_messages([
        ("system", _LLM_SYSTEM),
        ("user", "PAGE + CANDIDATES (metadata only):\n{ctx}\n\nReturn the JSON selection now."),
    ]) | get_llm(temperature=0.2, num_predict=1200)
    raw = chain.invoke({"ctx": json.dumps(context, ensure_ascii=True)}).content
    return extract_json(raw)


def _coerce_llm_selection(llm_sel, context, fallback):
    """Keep only valid candidate IDs; fill page_slug/purpose; backfill from fallback."""
    valid_secs = {s["section_id"] for s in context.get("candidate_sections", [])}
    valid_comps = {c["component_id"] for c in context.get("candidate_components", [])}
    by_id = {s["section_id"]: s for s in ps.get_all_sections()}
    out_secs, seen = [], set()
    for item in (llm_sel.get("selected_sections") or []):
        sid = (item or {}).get("section_id")
        if sid in valid_secs and sid not in seen and sid in by_id:
            seen.add(sid)
            rec = by_id[sid]
            out_secs.append({
                "section_id": sid,
                "section_type": rec["section_type"],
                "visual_family": rec["visual_family"],
                "legacy_identity": None,
                "reason": str((item or {}).get("reason", ""))[:160] or "LLM selection",
                "props_needed": (item or {}).get("props_needed") if isinstance((item or {}).get("props_needed"), dict) else {},
            })
    if len(out_secs) < 3:  # too sparse to trust — use deterministic plan
        return fallback
    if not any(s["section_type"] == "footer" for s in out_secs):
        out_secs.append(next(s for s in fallback["selected_sections"] if s["section_type"] == "footer"))
    out_comps = []
    for item in (llm_sel.get("selected_components") or []):
        cid = (item or {}).get("component_id")
        if cid in valid_comps:
            out_comps.append({"component_id": cid, "reason": str((item or {}).get("reason", ""))[:160] or "LLM selection"})
    return {
        "page_slug": llm_sel.get("page_slug") or fallback["page_slug"],
        "page_purpose": llm_sel.get("page_purpose") or fallback["page_purpose"],
        "selected_sections": out_secs,
        "selected_components": out_comps or fallback["selected_components"],
        "visual_family": fallback["visual_family"],
        "domain": fallback["domain"],
        "source": "llm",
    }


def select_blocks_for_page(prompt: str, page_blueprint: dict, genome: dict, use_llm: bool = True) -> dict:
    """Select blocks for a page. Tries the LLM (compact metadata only) when
    enabled and available; always falls back to deterministic selection on any
    failure, timeout, or invalid output."""
    fallback = deterministic_select_blocks_for_page(prompt, page_blueprint, genome)
    if not use_llm:
        return fallback
    try:
        context = build_block_selection_context(prompt, page_blueprint, genome)
        llm_sel = _llm_select(context)
        if not isinstance(llm_sel, dict):
            return fallback
        coerced = _coerce_llm_selection(llm_sel, context, fallback)
        verdict = validate_block_selection(coerced)
        return coerced if verdict["ok"] else fallback
    except Exception:
        return fallback


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def validate_block_selection(selection: dict) -> dict:
    """Validate selection structure + that every ID exists in the library and no
    raw JSX leaked in."""
    issues = []
    if not isinstance(selection, dict):
        return {"ok": False, "issues": ["selection is not a dict"]}
    if not str(selection.get("page_slug") or "").strip():
        issues.append("missing page_slug")
    sections = selection.get("selected_sections")
    if not isinstance(sections, list) or not sections:
        issues.append("selected_sections must be a non-empty list")
        sections = []
    seen = set()
    for item in sections:
        if not isinstance(item, dict):
            issues.append("section entry is not a dict")
            continue
        sid = item.get("section_id")
        if not sid or not ps.get_section_by_id(sid):
            issues.append(f"invalid section_id: {sid}")
        elif sid in seen:
            issues.append(f"duplicate section_id: {sid}")
        seen.add(sid)
        if "props_needed" in item and not isinstance(item["props_needed"], dict):
            issues.append(f"props_needed must be a dict for {sid}")
    for item in (selection.get("selected_components") or []):
        cid = (item or {}).get("component_id")
        if not cid or not pc.get_component_by_id(cid):
            issues.append(f"invalid component_id: {cid}")
    blob = json.dumps(selection, ensure_ascii=True)
    if "className=" in blob or "<section" in blob or "render_function" in blob:
        issues.append("selection unexpectedly contains JSX/code")
    return {"ok": not issues, "issues": issues}


def context_is_code_free(context: dict) -> bool:
    """True if the LLM context carries metadata only (no JSX / render code)."""
    blob = json.dumps(context, ensure_ascii=True)
    markers = ("className=", "<section", "<div", "render_function", "import ", "=>", "function(")
    return not any(m in blob for m in markers)
