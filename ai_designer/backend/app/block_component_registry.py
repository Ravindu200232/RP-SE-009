"""Unified facade for the professional block/component code library.

This is the single entry point the AI generator (eventually) talks to. It joins
the two halves — `professional_components.py` (1000+ reusable UI components) and
`professional_sections.py` (1000+ reusable page sections) — behind one stable
public API and a whole-library validator.

Public API
----------
    get_all_components()
    get_all_sections()
    get_component_by_id(component_id)
    get_section_by_id(section_id)
    search_components(prompt, max_results=50)
    search_sections(prompt, page_type=None, max_results=50)
    render_component(component_id, props)
    render_section(section_id, props)
    validate_professional_library()

Plus convenience helpers: get_components_by_type, get_sections_by_type,
compose_page, library_stats.

Nothing here is wired into the live generator yet — this module only creates and
validates the library.
"""
from __future__ import annotations

import copy

from app import professional_components as _pc
from app import professional_sections as _ps


# --------------------------------------------------------------------------- #
# Required public API — delegate to the two halves
# --------------------------------------------------------------------------- #

def get_all_components() -> list:
    return _pc.get_all_components()


def get_all_sections() -> list:
    return _ps.get_all_sections()


def get_component_by_id(component_id: str):
    return _pc.get_component_by_id(component_id)


def get_section_by_id(section_id: str):
    return _ps.get_section_by_id(section_id)


def search_components(prompt: str, max_results: int = 50) -> list:
    return _pc.search_components(prompt, max_results)


def search_sections(prompt: str, page_type: str = None, max_results: int = 50) -> list:
    return _ps.search_sections(prompt, page_type=page_type, max_results=max_results)


def render_component(component_id: str, props: dict = None) -> str:
    return _pc.render_component(component_id, props)


def render_section(section_id: str, props: dict = None) -> str:
    return _ps.render_section(section_id, props)


# --------------------------------------------------------------------------- #
# Convenience helpers
# --------------------------------------------------------------------------- #

def get_components_by_type(component_type: str, family: str = None, max_results: int = 50) -> list:
    return _pc.get_components_by_type(component_type, family=family, max_results=max_results)


def get_sections_by_type(section_type: str, family: str = None, max_results: int = 50) -> list:
    return _ps.get_sections_by_type(section_type, family=family, max_results=max_results)


def compose_page(section_ids, props: dict = None, wrap: bool = True) -> str:
    """Render an ordered list of section ids into one safe JSX page string.

    `props` is an optional {section_id: props} map. The result is build-safe even
    if an id is unknown (each section degrades to a small placeholder section).
    """
    props = props or {}
    parts = [render_section(sid, props.get(sid, {})) for sid in (section_ids or [])]
    inner = "".join(parts)
    return f'<main className="min-h-screen">{inner}</main>' if wrap else inner


def library_stats() -> dict:
    comp = _pc.summarize_components()
    sec = _ps.summarize_sections()
    domains = sorted(set(comp["domains"]) | set(sec["domains"]))
    families = sorted(set(comp["visual_families"]) | set(sec["visual_families"]))
    return {
        "component_count": comp["total"],
        "section_count": sec["total"],
        "component_types": comp["component_types"],
        "section_types": sec["section_types"],
        "domains": domains,
        "visual_families": families,
        "page_types": sec["page_types"],
        "component_type_count": len(comp["component_types"]),
        "section_type_count": len(sec["section_types"]),
        "domain_count": len(domains),
        "family_count": len(families),
    }


# --------------------------------------------------------------------------- #
# Whole-library validation
# --------------------------------------------------------------------------- #

# Minimum library guarantees promised by this module.
MINIMUMS = {
    "components": 1000,
    "sections": 1000,
    "domains": 15,
    "visual_families": 15,
    "section_types": 20,
    "component_types": 25,
}


def validate_professional_library() -> dict:
    """Validate the whole library: per-half schema/anti-copy/render checks plus
    cross-collection guarantees (counts, breadth, and globally-unique ids)."""
    comp = _pc.validate_components(MINIMUMS["components"])
    sec = _ps.validate_sections(MINIMUMS["sections"])

    errors = []
    errors.extend(f"component: {e}" for e in comp["errors"])
    errors.extend(f"section: {e}" for e in sec["errors"])

    all_ids = [c["component_id"] for c in _pc.COMPONENTS] + [s["section_id"] for s in _ps.SECTIONS]
    if len(set(all_ids)) != len(all_ids):
        errors.append("ids are not globally unique across components and sections")

    stats = library_stats()
    if stats["component_count"] < MINIMUMS["components"]:
        errors.append(f"component count {stats['component_count']} < {MINIMUMS['components']}")
    if stats["section_count"] < MINIMUMS["sections"]:
        errors.append(f"section count {stats['section_count']} < {MINIMUMS['sections']}")
    if stats["domain_count"] < MINIMUMS["domains"]:
        errors.append(f"domain count {stats['domain_count']} < {MINIMUMS['domains']}")
    if stats["family_count"] < MINIMUMS["visual_families"]:
        errors.append(f"visual family count {stats['family_count']} < {MINIMUMS['visual_families']}")
    if stats["section_type_count"] < MINIMUMS["section_types"]:
        errors.append(f"section type count {stats['section_type_count']} < {MINIMUMS['section_types']}")
    if stats["component_type_count"] < MINIMUMS["component_types"]:
        errors.append(f"component type count {stats['component_type_count']} < {MINIMUMS['component_types']}")

    return {
        "ok": comp["ok"] and sec["ok"] and not errors,
        "errors": errors,
        "components": comp,
        "sections": sec,
        "stats": stats,
    }


if __name__ == "__main__":  # pragma: no cover - manual inspection helper
    import json

    result = validate_professional_library()
    print(json.dumps({"ok": result["ok"], "stats": result["stats"],
                      "errors": result["errors"][:10]}, indent=2))
