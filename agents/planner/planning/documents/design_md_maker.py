"""Write the visual design section used by design.md."""
from __future__ import annotations

# Source: planning_helpers.py — shared formatting helpers.
from agents.planner.planning.planning_helpers import _bullets, _dict, _md_cell, _records, _strings, _text

class DesignMarkdownMixin:
    """Write the visual design section used by design.md."""

    # Builds design in the format expected by the next pipeline steps.
    def render_design(self, plan: dict) -> str:
        """Build design in the standard shape used by the rest of the pipeline."""
        design = plan.get("design") or {}
        # From: agents/planner/planning/planning_helpers.py
        lines = [f"**Direction:** {_text(design.get('direction'))}",
                 f"**Mood:** {_md_cell(design.get('mood'))}", ""]
        for title, key in (("Colors", "colors"), ("Typography", "typography"),
                           ("Layout", "layout"), ("Composition", "composition"),
                           ("Components", "components")):
            lines.append(f"### {title}")
            lines.append("")
            # From: agents/planner/planning/planning_helpers.py
            section = _dict(design.get(key))
            for name, value in section.items():
                # From: agents/planner/planning/planning_helpers.py
                lines.append(f"- **{str(name).replace('_', ' ').title()}:** {_md_cell(value)}")
            lines.append("")
        # From: agents/planner/planning/planning_helpers.py
        states = _dict(design.get("screen_states"))
        lines += ["### Screen states", ""]
        for name, value in states.items():
            # From: agents/planner/planning/planning_helpers.py
            lines.append(f"- **{name.title()}:** {_text(value)}")
        lines += ["", "### Responsive and accessibility", ""]
        # From: agents/planner/planning/planning_helpers.py
        lines += _bullets(design.get("responsive"), "Follow the route layouts")
        # From: agents/planner/planning/planning_helpers.py
        lines += _bullets(design.get("accessibility"), "Use semantic accessible controls")
        # From: agents/planner/planning/planning_helpers.py
        images = _records(plan.get("images"))
        if images:
            lines += ["", "### Images", ""]
            for item in images:
                # From: agents/planner/planning/planning_helpers.py
                lines.append(f"- `/generated/{item.get('key')}.png` "
                             f"({item.get('aspect') or 'landscape'}) — "
                             f"{_text(item.get('purpose'), 300)}")
        return "\n".join(lines).strip()
