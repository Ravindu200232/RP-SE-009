"""Serialize and validate the Architect's design plan without replacing it."""
from __future__ import annotations


def _section_labels(page: dict) -> list[str]:
    labels = []
    for section in page.get("sections") or []:
        name = section.get("section_name") if isinstance(section, dict) else section
        if name and str(name).strip():
            labels.append(str(name).strip())
    return labels


def design_brief(spec: dict) -> dict:
    design = spec.get("design") if isinstance(spec.get("design"), dict) else {}
    # Structured-SRS compatibility only. Free-text Architect specs always carry
    # the full canonical design object and never enter this branch.
    nav = design.get("navStyle")
    if nav not in ("sidebar", "topnav", "none"):
        nav = "sidebar" if bool((spec.get("auth") or {}).get("enabled")) else "none"
    return {
        "domain": spec.get("site_type") or "application",
        "preset": design.get("preset") or spec.get("style") or "custom",
        "mode": design.get("mode") or "dark",
        "navStyle": nav,
        "palette": design.get("palette") or {},
        "typography": design.get("typography") or {},
        "radius": design.get("radius") or "lg",
        "shadow": design.get("shadow") or "md",
        "spacing": design.get("spacing") or "normal",
        "motion": design.get("motion") or "subtle",
        "visualSignature": design.get("visualSignature") or "",
    }


def page_contracts(spec: dict) -> list[dict]:
    out = []
    for page in spec.get("pages") or []:
        functions = [str(fn) for fn in (page.get("functions") or [])]
        archetype = str(page.get("archetype") or page.get("kind") or "custom")
        layout = str(page.get("layout") or page.get("purpose") or "")
        out.append({
            "path": page.get("path"),
            "role": page.get("owner_role"),
            "title": page.get("title"),
            "archetype": archetype,
            "pattern": layout,
            "layout": layout,
            "userJob": page.get("userJob") or page.get("user_job") or page.get("purpose") or "",
            "purpose": page.get("purpose") or "",
            "primaryAction": page.get("primaryAction") or (functions[0] if functions else ""),
            "sections": _section_labels(page),
            "functions": functions,
            "visualSignature": page.get("visualSignature") or "",
        })
    return out


def plan(spec: dict) -> dict:
    contracts = page_contracts(spec)
    return {
        "brief": design_brief(spec),
        "pages": contracts,
        "by_path": {contract["path"]: contract for contract in contracts},
    }

