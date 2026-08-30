"""Render the planner route map as sitemap XML."""
from xml.sax.saxutils import escape, quoteattr
from typing import Any
# Source: planning_helpers.py — imported helper(s) come from this file.
from agents.planner.planning.planning_helpers import _dict, _records, _strings, _text

# Render only the attributes that carry a value.
def _xml_attrs(**values) -> str:
    """Render only the attributes that carry a value."""
    # From: agents/planner/planning/planning_helpers.py
    return "".join(f' {name.replace("_", "-")}={quoteattr(_text(value))}'
                   for name, value in values.items() if _text(value))

# Render one child list, or nothing when the plan left it empty.
def _xml_list(tag: str, item_tag: str, items: Any, indent: str = "    ") -> list[str]:
    """Render one child list, or nothing when the plan left it empty."""
    # From: agents/planner/planning/planning_helpers.py
    values = _strings(items, 500)
    if not values:
        return []
    return ([f"{indent}<{tag}>"]
            + [f"{indent}  <{item_tag}>{escape(value)}</{item_tag}>" for value in values]
            + [f"{indent}</{tag}>"])

# One XML document joining every planned page, API and navigation link.
def render_sitemap_xml(plan: dict) -> str:
    """One XML document joining every planned page, API and navigation link."""
    # From: agents/planner/planning/planning_helpers.py
    project = _dict(plan.get("project"))
    # From: agents/planner/planning/planning_helpers.py
    ia = _dict(plan.get("information_architecture"))
    # From: agents/planner/planning/planning_helpers.py
    access = _dict(plan.get("roles_and_access"))
    # From: agents/planner/planning/planning_helpers.py
    known = {_text(page.get("path")): page for page in _records(plan.get("site_map"))}
    # From: agents/planner/planning/planning_helpers.py
    pages = [route for route in _records(plan.get("routes"))
             if _text(route.get("kind")) != "route"]
    # From: agents/planner/planning/planning_helpers.py
    apis = _records(plan.get("api_contracts"))

    lines = ["<sitemap" + _xml_attrs(app=project.get("title"),
                                     pages=len(pages), apis=len(apis)) + ">",
             "  <navigation" + _xml_attrs(model=ia.get("navigation_model")) + ">"]
    # From: agents/planner/planning/planning_helpers.py
    for nav in _records(ia.get("global_navigation")):
        lines.append("    <link" + _xml_attrs(
            audience=nav.get("audience"), label=nav.get("label"),
            path=nav.get("path"), testid=nav.get("test_id")) + "/>")
    # From: agents/planner/planning/planning_helpers.py
    for role in _records(access.get("roles")):
        lines.append("    <home" + _xml_attrs(role=role.get("name"),
                                              path=role.get("home")) + "/>")
    lines.append("  </navigation>")

    for page in pages:
        # From: agents/planner/planning/planning_helpers.py
        meta = _dict(known.get(_text(page.get("path"))))
        lines.append("  <page" + _xml_attrs(
            path=page.get("path"), file=page.get("file"), kind=page.get("kind"),
            audience=page.get("audience") or meta.get("audience"),
            parent=meta.get("parent"), label=meta.get("label")) + ">")
        for tag, value in (("purpose", page.get("purpose") or meta.get("purpose")),
                           ("layout", page.get("layout"))):
            # From: agents/planner/planning/planning_helpers.py
            if _text(value):
                # From: agents/planner/planning/planning_helpers.py
                lines.append(f"    <{tag}>{escape(_text(value, 700))}</{tag}>")
        for tag, item_tag, items in (
                ("sections", "section", page.get("sections")),
                ("actions", "action", page.get("actions")),
                ("states", "state", page.get("states")),
                ("reads", "collection", page.get("reads")),
                ("writes", "collection", page.get("writes")),
                ("reached-from", "entry", meta.get("reached_from")),
                ("children", "child", meta.get("children")),
                ("requirements", "req", page.get("requirement_ids"))):
            lines += _xml_list(tag, item_tag, items)
        lines.append("  </page>")

    for api in apis:
        lines.append("  <api" + _xml_attrs(
            name=api.get("name"), method=api.get("method"), path=api.get("path"),
            file=api.get("handler_file"), audience=api.get("audience")) + ">")
        lines += _xml_list("called-from", "file", api.get("called_from"))
        # From: agents/planner/planning/planning_helpers.py
        if _text(api.get("success_effect")):
            # From: agents/planner/planning/planning_helpers.py
            lines.append("    <success>"
                         + escape(_text(api.get("success_effect"), 500))
                         + "</success>")
        lines.append("  </api>")

    lines.append("</sitemap>")
    return "\n".join(lines) + "\n"
