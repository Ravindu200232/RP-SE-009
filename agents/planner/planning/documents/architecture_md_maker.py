"""Write the architecture section used by architecture.md."""
from __future__ import annotations

# Source: planning_helpers.py — shared formatting helpers.
from agents.planner.planning.planning_helpers import _bullets, _dict, _md_cell, _records, _strings, _text

class ArchitectureMarkdownMixin:
    """Write the architecture section used by architecture.md."""

    # Builds architecture in the format expected by the next pipeline steps.
    def render_architecture(self, plan: dict) -> str:
        """Build architecture in the standard shape used by the rest of the pipeline."""
        arch = plan.get("architecture") or {}
        # From: agents/planner/planning/planning_helpers.py
        lines = [f"**Style:** {_text(arch.get('style')) or 'Modular application'}",
                 f"**Runtime:** {_text(arch.get('runtime'))}", "", "### Layers", ""]
        # From: agents/planner/planning/planning_helpers.py
        for layer in _records(arch.get("layers")):
            # From: agents/planner/planning/planning_helpers.py
            lines.append(f"- **{_text(layer.get('name'))}:** " + "; ".join(_strings(layer.get("responsibilities"))))
            if layer.get("files"):
                # From: agents/planner/planning/planning_helpers.py
                lines.append("  - Files: " + ", ".join(f"`{path}`" for path in _strings(layer.get("files"))))
        # From: agents/planner/planning/planning_helpers.py
        lines += ["", "### Component tree", "", *_bullets(arch.get("component_tree")),
                  "", "### Data flows", "", *_bullets(arch.get("data_flows")),
                  "", "### State strategy", "", *_bullets(arch.get("state_strategy")),
                  "", "### Cross-cutting behavior", "", *_bullets(arch.get("cross_cutting")),
                  "", "### Decisions", ""]
        # From: agents/planner/planning/planning_helpers.py
        for decision in _records(arch.get("decisions")):
            # From: agents/planner/planning/planning_helpers.py
            lines.append(f"- **{_text(decision.get('decision'))}:** {_text(decision.get('reason'))} Trade-off: {_text(decision.get('tradeoff'))}")
        return "\n".join(lines).strip()
