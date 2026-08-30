"""Write plan.md from the normalized plan."""
from __future__ import annotations

# Source: planning_helpers.py — shared formatting helpers.
from agents.planner.planning.planning_helpers import _bullets, _dict, _md_cell, _records, _strings, _text

class PlanMarkdownMixin:
    """Write plan.md from the normalized plan."""

    # Builds markdown in the format expected by the next pipeline steps.
    def render_markdown(self, plan: dict) -> str:
        """Build markdown in the standard shape used by the rest of the pipeline."""
        project = plan["project"]
        lines = [f"# {project['title']}", "", "## Overview", "",
                 project["summary"], "", f"**Product type:** {project['product_type']}",
                 f"**Primary goal:** {project['primary_goal']}", "",
                 "**Target audiences:** " + (", ".join(project["target_audiences"]) or "Not specified"),
                 "", "## Source Requirement Ledger", ""]
        for req in plan["requirements"]:
            lines += [f"### {req['id']} — {req['behavior']}", "",
                      f"- Source: {req['source_text']}", f"- Actor: {req['actor']}",
                      f"- Business rule: {req['business_rule'] or 'None beyond the stated behavior'}",
                      "- Acceptance:"]
            lines += [f"  - {item}" for item in req["acceptance"]] or ["  - Observable implementation proof"]
            lines.append("")
        # From: agents/planner/planning/planning_helpers.py
        lines += ["## Assumptions", "", *_bullets(plan["assumptions"], "No additional assumptions"), "",
                  "## Core Capabilities", ""]
        for cap in plan["capabilities"]:
            proof = "; ".join(cap["proof_points"]) or "implementation and visible outcome"
            lines.append(f"- **{cap['id']}** ({cap['actor']}): {cap['behavior']} — proof: {proof}")
        # From: agents/planner/planning/documents/design_md_maker.py
        lines += ["", "## Design", "", self.render_design(plan), "", "## Information Architecture", ""]
        ia = plan["information_architecture"]
        # From: agents/planner/planning/planning_helpers.py
        lines += [f"**Navigation model:** {_text(ia.get('navigation_model')) or 'Defined by the site map'}", "",
                  "### Global navigation", ""]
        # From: agents/planner/planning/planning_helpers.py
        for nav in _records(ia.get("global_navigation")):
            # From: agents/planner/planning/planning_helpers.py
            lines.append(f"- {_text(nav.get('audience'))}: {_text(nav.get('label'))} → `{_text(nav.get('path'))}` (`{_text(nav.get('test_id'))}`)")
        lines += ["", "## Site Map", "", "| Path | Parent | Type | Audience | Purpose | Reached from |",
                  "|---|---|---|---|---|---|"]
        for row in plan["site_map"]:
            # From: agents/planner/planning/planning_helpers.py
            lines.append("| " + " | ".join(_md_cell(row[key]) for key in
                         ("path", "parent", "type", "audience", "purpose", "reached_from")) + " |")
        lines += ["", "## Routes", "", "| Path | File | Kind | Audience | Reads | Writes | Requirements |",
                  "|---|---|---|---|---|---|---|"]
        for row in plan["routes"]:
            # From: agents/planner/planning/planning_helpers.py
            lines.append("| " + " | ".join(_md_cell(row[key]) for key in
                         ("path", "file", "kind", "audience", "reads", "writes", "requirement_ids")) + " |")
            if row["sections"]:
                lines.append(f"\n**`{row['path']}` sections:** " + "; ".join(row["sections"]))
            if row["actions"]:
                lines.append(f"\n**`{row['path']}` actions:** " + "; ".join(row["actions"]))
            if row.get("layout"):
                lines.append(f"\n**`{row['path']}` layout:** " + row["layout"])
        lines += ["", "## Data Model", ""]
        for model in plan["data_model"]:
            lines += [f"### `{model['collection']}`", "", model["purpose"] or "Application data", ""]
            for field in model["fields"]:
                required = "required" if field["required"] else "optional"
                lines.append(f"- `{field['name']}`: {field['type']} ({required}) — {field['rules'] or 'no extra rule'}")
            seed = model.get("seed") or {}
            # From: agents/planner/planning/planning_helpers.py
            lines.append(f"- Seed: {_text(seed.get('count')) or '0'} using `{_text(seed.get('identity_field')) or 'stable identity'}`")
            lines.append("")
        lines += ["## Roles and Access", "", f"**Authentication required:** {str(plan['roles_and_access']['authentication_required']).lower()}",
                  f"**Sign-up:** {plan['roles_and_access']['signup']}", ""]
        for role in plan["roles_and_access"]["roles"]:
            lines.append(f"- **{role['name']}** → `{role['home']}` — " + "; ".join(role["permissions"]))
        accounts = plan["roles_and_access"]["demo_accounts"]
        if accounts:
            lines += ["", "### Demo Accounts", "", "| Email | Password | Role |",
                      "|---|---|---|"]
            for account in accounts:
                lines.append(f"| {account['email']} | {account['password']} | {account['role']} |")
        lines += ["", "## API Contracts", ""]
        for api in plan["api_contracts"]:
            lines += [f"### {api['method']} `{api['path']}` — {api['name']}", "",
                      f"- Handler: `{api['handler_file']}`", f"- Called from: {', '.join(api['called_from'])}",
                      f"- Audience: {api['audience']}", f"- Success: {api['success_effect']}", ""]
        # From: agents/planner/planning/documents/architecture_md_maker.py
        lines += ["## Architecture", "", self.render_architecture(plan), "", "## End-to-End Plan", "",
                  f"**Strategy:** {plan['e2e_plan']['strategy']}", ""]
        for journey in plan["e2e_plan"]["journeys"]:
            lines += [f"### {journey['id']} — {journey['name']} ({journey['actor']})", ""]
            for number, step in enumerate(journey["steps"], 1):
                lines.append(f"{number}. `{step['at'] or journey['start_path']}` — {step['action']} — expect {step['expect']}")
            lines.append(f"- Final assertion: {journey['final_assertion']}")
            lines.append("")
        lines += ["## File Plan", ""]
        for file in plan["file_plan"]:
            lines += [f"### `{file['path']}` ({file['kind']})", "", file["purpose"] or "Planned implementation file"]
            if file["sections"]:
                lines.append("- Sections: " + "; ".join(file["sections"]))
            if file["actions"]:
                lines.append("- Actions: " + "; ".join(file["actions"]))
            if file["done_when"]:
                lines.append("- Done when: " + "; ".join(file["done_when"]))
            lines.append("")
        lines += ["## Build Tasks", ""]
        for task in plan["tasks"]:
            lines += [f"### Task {task['id']} — {task['title']}", "", task["goal"],
                      "", "- Files: " + ", ".join(f"`{f['path']}`" for f in task["files"]),
                      "- Requirements: " + (", ".join(task["requirement_ids"]) or "supporting work"),
                      "- Done when: " + "; ".join(task["done_when"]), ""]
        # From: agents/planner/planning/planning_helpers.py
        lines += ["## Definition of Done", "", *_bullets(plan["definition_of_done"])]
        return "\n".join(lines).strip() + "\n"
