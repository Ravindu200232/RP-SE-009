"""Build the canonical task DAG and human-readable TASKS.md for every app."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PLANNER_VERSION = 1


def _safe(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-") or "item"


def _page_dir(path: str) -> str:
    clean = str(path or "/").strip("/")
    return f"app/{clean}" if clean else "app"


def _component_target(page: dict, component: str, contract: dict) -> str:
    feature = _safe((contract.get("allowed_resources") or [page.get("owner_role") or "shared"])[0])
    return f"components/features/{feature}/{component}.tsx"


def build_plan(spec: dict) -> dict:
    component_by_name = {c["name"]: c for c in spec.get("component_contracts") or []}
    tasks: list[dict] = []

    def add(task_id: str, kind: str, title: str, target: str = "", depends=None,
            requirement=None, test_id: str = ""):
        tasks.append({
            "id": task_id,
            "kind": kind,
            "title": title,
            "target": target,
            "depends_on": list(depends or []),
            "requirement": requirement or {},
            "test_id": test_id or f"test:{task_id}",
            "status": "planned",
            "evidence": [],
        })

    for role in spec.get("roles") or []:
        role_id = f"role:{role['name']}:layout"
        add(role_id, "layout", f"Generate {role['label']} layout and navigation",
            "components/layouts/RoleWorkspace.tsx", requirement={"role": role["name"]})

    for page in spec.get("pages") or []:
        pid = _safe(page["id"])
        page_task = f"page:{pid}"
        role_dep = f"role:{page.get('owner_role')}:layout"
        add(page_task, "page", f"Create page {page['path']}", f"{_page_dir(page['path'])}/page.tsx",
            [role_dep], {"page": page["path"], "role": page.get("owner_role")})
        auth_task = f"{page_task}:auth"
        add(auth_task, "page-logic", "Add route authentication and role checks",
            f"{_page_dir(page['path'])}/page.tsx", [page_task],
            {"access": page.get("access")})
        data_task = f"{page_task}:data"
        add(data_task, "page-logic", "Add page data loading, validation and orchestration",
            f"{_page_dir(page['path'])}/page.tsx", [auth_task],
            {"resources": page.get("resources") or []})

        section_tasks = []
        for section in page.get("sections") or []:
            sid = f"{page_task}:section:{_safe(section['section_name'])}"
            component_tasks = []
            for component in section.get("components") or []:
                contract = component_by_name.get(component, {"name": component, "usages": []})
                cid = f"{sid}:component:{_safe(component)}"
                target = _component_target(page, component, contract)
                add(cid, "component", f"Generate {component}", target, [data_task], {
                    "component": component,
                    "section": section["section_name"],
                    "allowed_resources": contract.get("allowed_resources") or [],
                    "allowed_fields": contract.get("allowed_fields") or [],
                })
                component_tasks.append(cid)
            add(sid, "section", f"Compose {section['section_name']} section",
                f"{_page_dir(page['path'])}/_components/{''.join(x.title() for x in _safe(section['section_name']).split('-'))}Section.tsx",
                component_tasks or [data_task],
                {"section": section["section_name"], "components": section.get("components") or []})
            section_tasks.append(sid)

        action_tasks = []
        action_by_id = {a["id"]: a for a in spec.get("actions") or []}
        for action_id in page.get("action_ids") or []:
            action = action_by_id.get(action_id, {})
            aid = f"{page_task}:action:{_safe(action.get('label') or action_id)}"
            add(aid, "action", f"Connect {action.get('label') or action_id}",
                f"{_page_dir(page['path'])}/page.tsx", section_tasks or [data_task], action)
            action_tasks.append(aid)
        compose = f"{page_task}:compose"
        add(compose, "composition", "Import components and complete the page",
            f"{_page_dir(page['path'])}/page.tsx", section_tasks + action_tasks or [data_task],
            {"page": page["path"]})
        test = f"{page_task}:verify"
        add(test, "verification", "Run route, role, component and interaction checks",
            "verification/report.json", [compose], {"page": page["path"]})
        add(f"{page_task}:screenshots", "screenshot", "Capture desktop and mobile screenshots",
            "verification/screenshots", [test], {"page": page["path"]})

    planned_component_names = {
        t.get("requirement", {}).get("component") for t in tasks if t.get("kind") == "component"
    }
    for contract in spec.get("component_contracts") or []:
        if contract.get("name") in planned_component_names:
            continue
        pseudo_page = {"owner_role": (contract.get("roles") or ["shared"])[0]}
        add(f"component:{_safe(contract.get('name'))}", "component",
            f"Generate shared {contract.get('name')}",
            _component_target(pseudo_page, contract.get("name"), contract),
            requirement={"component": contract.get("name"), "roles": contract.get("roles") or []})

    for resource in spec.get("resources") or []:
        rid = f"resource:{_safe(resource['table'])}"
        add(rid, "resource", f"Generate and verify {resource['table']} persistence",
            f"models/{resource['name']}.ts" if resource["name"] != "User" else "models/User.ts",
            requirement={"resource": resource["name"], "fields": resource.get("fields") or []})
    for relation in spec.get("relationships") or []:
        add(f"relationship:{_safe(relation['id'])}", "relationship",
            f"Verify relationship {relation['from']} -> {relation['to']}",
            "verification/report.json", requirement=relation)

    return {
        "version": PLANNER_VERSION,
        "input_hash": spec.get("input_hash"),
        "project": spec.get("project_name"),
        "tasks": tasks,
        "summary": {
            "total": len(tasks),
            "planned": len(tasks),
            "complete": 0,
        },
    }


def _coverage(spec: dict, plan: dict) -> dict:
    expected = {
        "roles": len(spec.get("roles") or []),
        "routes": len(spec.get("pages") or []),
        "pages": len(spec.get("pages") or []),
        "sections": sum(len(p.get("sections") or []) for p in spec.get("pages") or []),
        "components": len(spec.get("component_contracts") or []),
        "functions": len(spec.get("actions") or []),
        "tables": len(spec.get("resources") or []),
        "relationships": len(spec.get("relationships") or []),
    }
    planned = {
        "roles": len(spec.get("roles") or []),
        "routes": len(spec.get("pages") or []),
        "pages": len({t["requirement"].get("page") for t in plan["tasks"] if t["kind"] == "page"}),
        "sections": sum(1 for t in plan["tasks"] if t["kind"] == "section"),
        "components": len({t["requirement"].get("component") for t in plan["tasks"] if t["kind"] == "component"}),
        "functions": len(spec.get("actions") or []),
        "tables": sum(1 for t in plan["tasks"] if t["kind"] == "resource"),
        "relationships": sum(1 for t in plan["tasks"] if t["kind"] == "relationship"),
    }
    dimensions = {}
    for key, total in expected.items():
        covered = planned.get(key, 0)
        dimensions[key] = {
            "expected": total,
            "planned": covered,
            "percent": 100.0 if total == 0 else round(100 * min(covered, total) / total, 2),
        }
    return {
        "strict": True,
        "complete": all(x["percent"] == 100.0 for x in dimensions.values()),
        "dimensions": dimensions,
    }


def _tasks_markdown(spec: dict, plan: dict) -> str:
    task_by_requirement: dict[tuple[str, str], list[dict]] = {}
    for task in plan["tasks"]:
        req = task.get("requirement") or {}
        page = str(req.get("page") or "")
        role = str(req.get("role") or "")
        if page:
            task_by_requirement.setdefault((role, page), []).append(task)
    lines = [f"# {spec.get('title', 'App')} — Component-wise Build Tasks", "",
             f"Input hash: `{spec.get('input_hash', '')}`", ""]
    for role in spec.get("roles") or []:
        lines.extend([f"## Role: {role['label']}", ""])
        for page in [p for p in spec.get("pages") or [] if p.get("owner_role") == role["name"]]:
            lines.extend([f"### Page: `{page['path']}` — {page['title']}", ""])
            lines.append("- [ ] Create and orchestrate `page.tsx`")
            lines.append("- [ ] Add route auth, data loading, validation and page logic")
            for section in page.get("sections") or []:
                lines.append(f"- [ ] Section: {section['section_name']}")
                for component in section.get("components") or []:
                    lines.append(f"  - [ ] Component: `{component}`")
            for function in page.get("functions") or []:
                lines.append(f"- [ ] Function: {function}")
            lines.extend([
                "- [ ] Import all declared components",
                "- [ ] Run route, role, API and interaction tests",
                "- [ ] Capture desktop and mobile screenshots",
                "",
            ])
    lines.extend(["## Data and Relationships", ""])
    for resource in spec.get("resources") or []:
        lines.append(f"- [ ] `{resource['table']}` schema, validation, API and persistence")
    for relation in spec.get("relationships") or []:
        lines.append(f"- [ ] `{relation['from']}` → `{relation['to']}` ({relation['type']})")
    return "\n".join(lines).rstrip() + "\n"


def _json(path: Path, value: Any):
    path.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")


def write_artifacts(project_dir: Path, spec: dict, contract: dict, generated_files=None) -> dict:
    out = Path(project_dir) / ".locode"
    out.mkdir(parents=True, exist_ok=True)
    plan = build_plan(spec)
    if generated_files is not None:
        known = set(generated_files)
        for task in plan["tasks"]:
            target = task.get("target") or ""
            if target and (target in known or (Path(project_dir) / target).exists()):
                task["status"] = "complete"
                task["evidence"] = [target]
        plan["summary"]["complete"] = sum(t["status"] == "complete" for t in plan["tasks"])
    coverage = _coverage(spec, plan)
    analysis = {
        **(spec.get("analysis") or {}),
        "planner_version": PLANNER_VERSION,
        "coverage_complete": coverage["complete"],
    }
    _json(out / "normalized-spec.json", spec.get("canonical_ir") or spec)
    _json(out / "analysis.json", analysis)
    _json(out / "plan.json", plan)
    (out / "TASKS.md").write_text(_tasks_markdown(spec, plan), encoding="utf-8")
    _json(out / "contract.json", contract)
    _json(out / "coverage.json", coverage)
    return {"plan": plan, "coverage": coverage, "analysis": analysis}
