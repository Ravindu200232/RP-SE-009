"""Page quality gate.

Fails a page when it would look wrong for its route: denied sections present,
required semantic groups missing, duplicate sections/titles/groups, a large gray
hero placeholder, missing CTA or footer, or route identity not matching content
(e.g. generic pricing/reporting on a neighborhood or booking route).

Two entry points:
* `evaluate_selection(selection)` — checks a block selection (semantic groups vs
  the domain×intent route rule + duplicate + CTA/footer presence).
* `evaluate_page_jsx(jsx)` — checks rendered page markup (gray-hero placeholder,
  CTA, footer, duplicate section markers/titles).
"""
from __future__ import annotations

import re

from app import route_block_rules as rbr


_CTA_GROUPS = {"cta", "booking", "appointment_booking", "reservation_booking"}


def evaluate_selection(selection: dict, domain: str = None, intent: str = None) -> dict:
    sections = selection.get("selected_sections") or []
    domain = domain or selection.get("domain") or ""
    intent = intent or selection.get("intent") or "service_catalog"
    groups = [s.get("semantic_group") or "" for s in sections]
    types = [s.get("section_type") or "" for s in sections]

    rule = rbr.get_route_rule(domain, intent)
    rq = rbr.route_quality(groups, rule)
    issues = list(rq["issues"])

    if not (set(groups) & _CTA_GROUPS or "cta banner" in types or "appointment cta" in types):
        issues.append("no CTA section")
    if "footer" not in groups and "footer" not in types:
        issues.append("no footer section")

    ids = [s.get("section_id") for s in sections if s.get("section_id")]
    if len(set(ids)) != len(ids):
        issues.append("duplicate section_id present")

    # duplicate legacy markers (titles) — markers must be unique per page
    markers = [s.get("legacy_identity") for s in sections if s.get("legacy_identity")]
    if len(set(markers)) != len(markers):
        issues.append("duplicate page-section marker present")

    return {"ok": not issues, "issues": sorted(set(issues)), "route_quality": rq,
            "domain": domain, "intent": intent}


def evaluate_page_jsx(jsx: str, domain: str = None, intent: str = None) -> dict:
    issues = []
    src = str(jsx or "")

    # A large gray hero placeholder (the old image-panel hero caption) — replaced
    # by domain hero_visuals panels, so its presence means a gray box leaked back.
    if "See it in action" in src:
        issues.append("large gray hero placeholder present")

    # CTA present (premium-cta marker, a cta section, or a clear CTA control)
    if 'data-premium-cta="true"' not in src and 'data-section-type="cta banner"' not in src \
            and 'data-section-type="appointment cta"' not in src and ">Get started<" not in src:
        issues.append("CTA missing in rendered page")

    if "<footer" not in src and 'data-section-type="footer"' not in src and 'data-page-section="footer"' not in src:
        issues.append("footer missing in rendered page")

    # duplicate section markers in the rendered page
    markers = re.findall(r'data-page-section="([^"]+)"', src)
    if len(set(markers)) != len(markers):
        issues.append("duplicate data-page-section marker in rendered page")

    return {"ok": not issues, "issues": issues, "section_markers": markers}
