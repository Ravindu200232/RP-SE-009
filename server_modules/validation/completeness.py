"""Does the specification actually cover the plan it came from?"""
from __future__ import annotations

import re
from typing import Any

def _dig(doc: dict, path: str) -> list:
    node: Any = doc
    for part in path.split("."):
        node = (node or {}).get(part) if isinstance(node, dict) else None
    return node if isinstance(node, list) else []


def _words(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", str(text).lower()) if len(w) > 3}


def _singular_word(word: str) -> str:
    """Normalize ordinary English plurals used in plan record labels."""
    if len(word) < 4:
        return word
    if word.endswith("statuses"):
        return word[:-2]
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("sses", "xes", "ches", "shes")):
        return word[:-2]
    if word.endswith(("ss", "us", "is")):
        return word
    if word.endswith("s"):
        return word[:-1]
    return word


def _entity_words(text: str) -> tuple[str, ...]:
    return tuple(_singular_word(word) for word in
                 re.split(r"[^a-z0-9]+", str(text).lower()) if word)


def _covered(needle: str, haystacks: list[str]) -> bool:
    """Whether some requirement plausibly speaks to this plan item."""
    wanted = _words(needle)
    if not wanted:
        return True
    for text in haystacks:
        shared = wanted & _words(text)
        if len(shared) >= max(1, min(2, len(wanted))):
            return True
    return False


def requirement_coverage(doc: dict, plan: dict) -> list[str]:
    """Plan items with no requirement that mentions them."""
    requirements = [str(f.get("requirement", "")) for f in _dig(doc, "functional_requirements")]
    requirements += [str(w.get("workflow_name", "")) + " " + " ".join(w.get("steps") or [])
                     for w in _dig(doc, "business_workflows")]
    if not requirements:
        return ["the specification has no functional requirements at all"]

    gaps: list[str] = []
    for feature in [str(f) for f in (plan.get("features") or []) if str(f).strip()]:
        if not _covered(feature, requirements):
            gaps.append(f"no functional requirement covers the plan feature: {feature!r}")
    for flow in (plan.get("workflows") or []):
        name = str(flow.get("name") or "")
        if name and not _covered(name, requirements):
            gaps.append(f"no functional requirement or workflow covers the plan journey: {name!r}")
    for user in (plan.get("users") or []):
        role = str(user.get("role") or "")
        for action in (user.get("can_do") or []):
            if role and not _covered(f"{role} {action}", requirements):
                gaps.append(f"no functional requirement covers what {role} can do: {action!r}")
                break
    return gaps


def page_coverage(doc: dict, plan: dict) -> list[str]:
    """Screens the plan promised that the specification does not have."""
    routes = {str(p.get("route") or "").rstrip("/") or "/"
              for p in _dig(doc, "public_pages") + _dig(doc, "protected_pages")}
    names = {str(p.get("page_name") or "").lower()
             for p in _dig(doc, "public_pages") + _dig(doc, "protected_pages")}
    gaps = []
    for screen in (plan.get("screens") or []):
        route = str(screen.get("route") or "").rstrip("/") or "/"
        name = str(screen.get("name") or "")
        if route not in routes and name.lower() not in names:
            gaps.append(f"the plan's screen {name!r} ({route}) is not in the specification's pages")
    return gaps


def table_coverage(doc: dict, plan: dict) -> list[str]:
    """Records the plan promised that the database design does not have."""
    tables = {_entity_words(str(t.get("table_name") or ""))
              for t in _dig(doc, "database_design.tables")}
    gaps = []
    for record in (plan.get("records") or []):
        name = _entity_words(str(record.get("name") or ""))
        if not name:
            continue
        if name not in tables:
            gaps.append(f"the plan's record {record.get('name')!r} has no table in database_design")
    return gaps

# Optional-in-the-schema sections a well-formed SRS is still expected to carry.
STRUCTURAL_SECTIONS = (
    ("security_requirements", "security requirements"),
    ("acceptance_criteria", "acceptance criteria"),
    ("validation_rules", "field validation rules"),
    ("risk_priority", "risk and priority ranking"),
    ("assumptions", "assumptions"),
    ("constraints", "constraints"),
    ("role_access_matrix", "role access matrix"),
    ("api_design", "API design"),
)


def section_completeness(doc: dict) -> dict:
    """Which structurally-expected sections carry real content."""
    populated = [label for key, label in STRUCTURAL_SECTIONS if _dig(doc, key)]
    empty = [label for key, label in STRUCTURAL_SECTIONS if not _dig(doc, key)]
    return {"populated": populated, "empty": empty,
            "ratio": round(len(populated) / len(STRUCTURAL_SECTIONS), 2)}


def ambiguity_resolution(doc: dict) -> dict:
    """How many identified ambiguities are still open."""
    ambiguities = _dig(doc, "ambiguities")
    if not ambiguities:
        return {"total": 0, "resolved": 0, "rate": 1.0}
    resolved = sum(1 for a in ambiguities if not a.get("needs_clarification"))
    return {"total": len(ambiguities), "resolved": resolved,
            "rate": round(resolved / len(ambiguities), 2)}


def traceability_coverage(doc: dict) -> list[str]:
    """Requirements that trace to nothing."""
    traced = {str(row.get("requirement_id")) for row in
              _dig(doc, "requirement_traceability_matrix")}
    missing = [str(f.get("id")) for f in _dig(doc, "functional_requirements")
               if str(f.get("id")) not in traced]
    if missing:
        return [f"these requirements are in no traceability row: {', '.join(missing[:8])}"]
    return []


def check_document(doc: dict, plan: dict) -> list[str]:
    """Plan coverage and traceability, before any diagrams or pages are drawn."""
    gaps: list[str] = []
    gaps += page_coverage(doc, plan)
    gaps += table_coverage(doc, plan)
    gaps += requirement_coverage(doc, plan)
    gaps += traceability_coverage(doc)
    return gaps


def as_instructions(gaps: list[str]) -> str:
    return "\n".join(f"- {gap}" for gap in gaps)
