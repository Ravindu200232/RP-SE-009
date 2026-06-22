"""Regression tests for the professional block/component code library.

Validates the 1000+ component and 1000+ section local code library exposed by
`app.block_component_registry` (backed by `professional_components` and
`professional_sections`): counts, schema, render quality, domain search, the
anti-copy guarantees, and a composed hospital homepage assembled from 6 sections.

Run:
    cd ai_designer/backend
    python _test_professional_block_library.py
"""
import json
import os
import random
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import block_component_registry as bcr
from app import professional_components as pc
from app import professional_sections as ps


RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

BANNED = [
    "stripe", "apple", "nike", "linear", "notion", "figma", "vercel", "webflow",
    "tesla", "amazon", "github", "openai", "coursera", "spotify", "shopify",
    "airbnb", "uber", "netflix", "zillow", "redfin", "doordash", "square",
]
URL_RE = re.compile(r"(https?://|www\.|[a-z0-9-]+\.(?:com|app|ai|io|co|net|org|tech|dev|xyz)\b)", re.I)
SAFE_IMG_RE = re.compile(r"^/generated/[a-z0-9][a-z0-9/_-]*\.(?:jpg|jpeg|png|webp)$")


def looks_like_jsx(s):
    if not isinstance(s, str):
        return False
    t = s.strip()
    if not t.startswith("<") or not t.endswith(">"):
        return False
    if "className=" not in t:
        return False
    if t.count("<") != t.count(">"):
        return False
    if t.count("{") != t.count("}"):
        return False
    if not any(x in t for x in ("sm:", "md:", "lg:")):
        return False
    if "None" in t or "[object" in t or "</br>" in t:
        return False
    return True


def banned_hits(text):
    low = str(text or "").lower()
    return [b for b in BANNED if re.search(rf"\b{re.escape(b)}\b", low)]


def render_broad_sample():
    """Render a wide spread of components and sections for anti-copy scans."""
    out = []
    for ct in pc.COMPONENT_TYPES:
        for fam in pc.VISUAL_FAMILIES[:4]:
            recs = bcr.get_components_by_type(ct, family=fam, max_results=1)
            if recs:
                out.append(bcr.render_component(recs[0]["component_id"], {}))
    for st in ps.SECTION_TYPES:
        for fam in pc.VISUAL_FAMILIES[:3]:
            recs = bcr.get_sections_by_type(st, family=fam, max_results=1)
            if recs:
                out.append(bcr.render_section(recs[0]["section_id"], {}))
    return out


def assemble_hospital_homepage():
    """Pick 6 varied sections for a hospital homepage and return (ids, records)."""
    plan = [
        ("hero", "clinical-trust"),
        ("department grid", "healthcare-saas"),
        ("patient portal", "dashboard-operations"),
        ("trust badges", "fintech-trust"),
        ("appointment cta", "clinical-trust"),
        ("footer", "healthcare-saas"),
    ]
    ids, records = [], []
    for stype, fam in plan:
        found = bcr.get_sections_by_type(stype, family=fam, max_results=1)
        if not found:  # fall back to any family for that type
            found = bcr.get_sections_by_type(stype, max_results=1)
        records.append(found[0])
        ids.append(found[0]["section_id"])
    return ids, records


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def main():
    print("=" * 72)
    print("PROFESSIONAL BLOCK / COMPONENT LIBRARY")
    print("=" * 72)

    components = bcr.get_all_components()
    sections = bcr.get_all_sections()
    stats = bcr.library_stats()
    validation = bcr.validate_professional_library()

    # 1. component count >= 1000
    rec("1. component count >= 1000", len(components) >= 1000, len(components))

    # 2. section count >= 1000
    rec("2. section count >= 1000", len(sections) >= 1000, len(sections))

    # 3. all IDs unique (per collection and globally)
    comp_ids = [c["component_id"] for c in components]
    sec_ids = [s["section_id"] for s in sections]
    all_ids = comp_ids + sec_ids
    rec("3. all IDs unique (components, sections, and globally)",
        len(set(comp_ids)) == len(comp_ids)
        and len(set(sec_ids)) == len(sec_ids)
        and len(set(all_ids)) == len(all_ids),
        {"components": len(comp_ids), "sections": len(sec_ids), "unique": len(set(all_ids))})

    # 4. all required fields exist
    comp_missing = [c.get("component_id") for c in components if pc.COMPONENT_REQUIRED_FIELDS - set(c)]
    sec_missing = [s.get("section_id") for s in sections if ps.SECTION_REQUIRED_FIELDS - set(s)]
    rec("4. all required metadata fields exist on every record",
        not comp_missing and not sec_missing,
        {"components_missing": comp_missing[:3], "sections_missing": sec_missing[:3]})

    # 5. render_component returns valid JSX-like string (every type + random sample)
    comp_targets = []
    for ct in pc.COMPONENT_TYPES:
        comp_targets.append(next(c for c in components if c["component_type"] == ct)["component_id"])
    rng = random.Random(7)
    comp_targets += [c["component_id"] for c in rng.sample(components, 60)]
    comp_bad = [cid for cid in comp_targets if not looks_like_jsx(bcr.render_component(cid, {}))]
    rec("5. render_component returns valid JSX-like strings",
        not comp_bad, {"checked": len(comp_targets), "bad": comp_bad[:4]})

    # 6. render_section returns valid JSX-like string (every type + random sample)
    sec_targets = []
    for st in ps.SECTION_TYPES:
        sec_targets.append(next(s for s in sections if s["section_type"] == st)["section_id"])
    sec_targets += [s["section_id"] for s in rng.sample(sections, 40)]
    sec_bad = [sid for sid in sec_targets if not looks_like_jsx(bcr.render_section(sid, {}))]
    rec("6. render_section returns valid JSX-like strings",
        not sec_bad, {"checked": len(sec_targets), "bad": sec_bad[:4]})

    # 7-14. domain-aware search
    def check_domain(num, label, prompt, primary_domain, comp_types, sec_types):
        comps = bcr.search_components(prompt, max_results=12)
        secs = bcr.search_sections(prompt, max_results=12)
        ctypes_found = {r["component_type"] for r in comps}
        stypes_found = {r["section_type"] for r in secs}
        # The #1 ranked hit must be on-domain (right type or carries the domain),
        # and the expected domain-specific types must surface in the results.
        top_comp, top_sec = comps[0], secs[0]
        comp_top_ok = top_comp["component_type"] in comp_types or primary_domain in top_comp["domain_fit"]
        sec_top_ok = top_sec["section_type"] in sec_types or primary_domain in top_sec["domain_fit"]
        ok = (
            comp_top_ok and sec_top_ok
            and bool(comp_types & ctypes_found) and bool(sec_types & stypes_found)
        )
        rec(f"{num}. {label} search returns {primary_domain} sections/components", ok,
            {"top_comp": top_comp["component_type"], "top_sec": top_sec["section_type"],
             "comp_types": sorted(ctypes_found & comp_types), "sec_types": sorted(stypes_found & sec_types)})

    check_domain(7, "hospital",
                 "Hospital website with appointment booking, doctor search, patient portal, lab reports, and emergency department.",
                 "healthcare", {"doctor card", "service card"},
                 {"department grid", "doctor search", "patient portal", "appointment cta", "lab report preview", "portal preview"})
    check_domain(8, "vehicle",
                 "Vehicle dealership website with searchable car inventory, financing, and test drive booking.",
                 "automotive", {"vehicle card", "product card"},
                 {"vehicle inventory grid", "product showcase", "product collection grid", "search panel"})
    check_domain(9, "restaurant",
                 "Restaurant website with menu preview, table reservation booking, and chef specials.",
                 "restaurant", {"restaurant menu card"},
                 {"restaurant menu preview", "reservation section", "booking flow"})
    check_domain(10, "real estate",
                 "Real estate website with property search, listing cards, agents, and neighborhood highlights.",
                 "real-estate", {"property card"},
                 {"property listing grid", "property search", "search panel"})
    check_domain(11, "travel",
                 "Travel agency website with destinations, itinerary planning, tour packages, and trip booking.",
                 "travel", {"travel package card"},
                 {"travel destination hero", "itinerary cards", "search panel"})
    check_domain(12, "fitness",
                 "Fitness coaching website with program cards, trainer profiles, class schedule, and workouts.",
                 "fitness", {"trainer card", "service card"},
                 {"fitness program cards", "trainer profile section"})
    check_domain(13, "AI tool",
                 "AI developer tool landing page for API workflows, automation, code, and SDK integrations.",
                 "ai-devtools", {"feature card"},
                 {"ai api panel", "developer workflow section", "feature grid", "app preview"})
    check_domain(14, "course",
                 "Online course platform with catalog, learning paths, lessons, instructors, and student progress.",
                 "education", {"course card"},
                 {"course catalog", "learning path section"})

    # Shared corpus for anti-copy scans (metadata + a broad rendered sample).
    metadata_blob = json.dumps(components + sections, ensure_ascii=True).lower()
    sample_jsx = render_broad_sample()
    sample_blob = "\n".join(sample_jsx)

    # 15. no real brand names appear
    meta_brands = banned_hits(metadata_blob)
    jsx_brands = banned_hits(sample_blob)
    rec("15. no real brand names appear (metadata or rendered JSX)",
        not meta_brands and not jsx_brands, {"metadata": meta_brands[:5], "jsx": jsx_brands[:5]})

    # 16. no URLs appear
    meta_urls = URL_RE.findall(metadata_blob)
    jsx_urls = URL_RE.findall(sample_blob)
    rec("16. no URLs appear (metadata or rendered JSX)",
        not meta_urls and not jsx_urls, {"metadata": meta_urls[:3], "jsx": jsx_urls[:3]})

    # 17. no copied asset paths appear (every rendered image src is a safe local slot)
    srcs = re.findall(r'src="([^"]*)"', sample_blob)
    bad_srcs = [s for s in srcs if not SAFE_IMG_RE.match(s.lower())]
    meta_paths = re.findall(r"/assets/|/generated/|[a-z0-9_-]+\.(?:jpg|jpeg|png|webp|svg|gif)\b",
                            metadata_blob.replace("professional_components.py", "").replace("professional_sections.py", ""))
    rec("17. no copied asset paths appear (only safe /generated/* image slots)",
        not bad_srcs and not meta_paths and len(srcs) > 0,
        {"sample_srcs": sorted(set(srcs))[:4], "bad": bad_srcs[:3], "meta_paths": meta_paths[:3]})

    # 18. no section has quality_score below 80
    low_secs = [s["section_id"] for s in sections if s.get("quality_score", 0) < 80]
    low_comps = [c["component_id"] for c in components if c.get("quality_score", 0) < 80]
    rec("18. no section (or component) has quality_score below 80",
        not low_secs and not low_comps,
        {"low_sections": low_secs[:3], "low_components": low_comps[:3]})

    # 20 (data): assemble hospital homepage from 6 sections
    page_ids, page_recs = assemble_hospital_homepage()
    page_families = [r["visual_family"] for r in page_recs]
    page_types = [r["section_type"] for r in page_recs]

    # 19. selected sections have varied visual_family
    rec("19. selected hospital sections have varied visual_family",
        len(set(page_families)) >= 3 and len(set(page_types)) == 6,
        {"families": page_families, "types": page_types})

    # 20. sample generated page composed from 6 sections builds JSX safely
    page_jsx = bcr.compose_page(page_ids)
    has_hero = 'data-section-type="hero"' in page_jsx
    has_cta = 'data-section-type="appointment cta"' in page_jsx
    has_service = 'data-section-type="department grid"' in page_jsx
    has_trust = 'data-section-type="trust badges"' in page_jsx
    has_portal = 'data-section-type="patient portal"' in page_jsx or 'data-section-type="lab report preview"' in page_jsx
    has_footer = 'data-section-type="footer"' in page_jsx
    distinct_section_markers = len(set(re.findall(r'data-section-type="([^"]+)"', page_jsx)))
    not_repeated = distinct_section_markers == 6 and len(set(page_families)) >= 3
    page_ok = (
        looks_like_jsx(page_jsx) and has_hero and has_cta and has_service
        and has_trust and has_portal and has_footer and not_repeated
        and not banned_hits(page_jsx) and not URL_RE.findall(page_jsx)
    )
    rec("20. composed 6-section hospital page builds safe, varied JSX",
        page_ok,
        {"hero": has_hero, "cta": has_cta, "service/department": has_service, "trust": has_trust,
         "portal/report": has_portal, "footer": has_footer, "distinct_sections": distinct_section_markers,
         "len": len(page_jsx)})

    # Library-wide validation must be green.
    rec("library validator (validate_professional_library) is green",
        validation["ok"], validation["errors"][:4])
    rec("library breadth: 15+ domains, 15+ families, 20+ section types, 25+ component types",
        stats["domain_count"] >= 15 and stats["family_count"] >= 15
        and stats["section_type_count"] >= 20 and stats["component_type_count"] >= 25,
        {k: stats[k] for k in ("domain_count", "family_count", "section_type_count", "component_type_count")})

    # ---- informational output for the report ----
    print("-" * 72)
    print("Sample component IDs:", ", ".join(comp_ids[:10]))
    print("Sample section IDs:  ", ", ".join(sec_ids[:10]))
    print("Domains covered:     ", ", ".join(stats["domains"]))
    print("Visual families:     ", ", ".join(stats["visual_families"]))
    print("Hospital page plan:")
    for r in page_recs:
        print(f"   - {r['section_id']}  {r['section_type']:24s} [{r['visual_family']}]")

    print("=" * 72)
    ok = all(RESULTS)
    print(f"PROFESSIONAL BLOCK LIBRARY GREEN ({sum(RESULTS)}/{len(RESULTS)})" if ok
          else f"FAILURES ({sum(RESULTS)}/{len(RESULTS)} passed)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
