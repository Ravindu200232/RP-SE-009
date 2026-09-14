"""Compare completed child-agent changes with the parent SRS exactly once."""
from __future__ import annotations

import copy
import json

from ...jobs import CURRENT_JOB
from ..agents.customization import _editable_view, merge_edit
from ..agents.diagram_generator import diagram_node
from ..agents.pdf_generator import generate_pdf
from ..generators.agent_handoff import write_handoff
from ..generators.builder_brief import attach_handoff
from ..knowledge.plan_srs import effective_plan
from ..llm import get_llm
from ..models import repositories as repo
from ..schemas.srs import validate_srs
from . import storage
from .orchestrator import _bump_minor, now_iso, summarize_srs


async def synchronize(project_id: str, change_id: str, source: str, summary: str) -> dict:
    project = await repo.get_project(project_id)
    latest = await repo.latest_version(project_id)
    if not project or not latest:
        raise ValueError("A generated parent SRS is required")
    receipt = storage.project_dir(project_id) / "changes" / f"{change_id}.json"
    if receipt.is_file():
        return json.loads(receipt.read_text(encoding="utf-8"))
    checkpoint = receipt.with_suffix(".pending.json")
    if checkpoint.is_file():
        pending = json.loads(checkpoint.read_text(encoding="utf-8"))
        srs, diff, version = pending["srs"], pending["diff"], pending["version"]
    else:
        srs = copy.deepcopy(latest["srs"])
        prompt = (
            f"Completed change reported by {source}:\n{summary}\n\n"
            "Compare this with the current SRS. Reflect only the completed change in every affected "
            "section: UI/design, screens and routes, behavior, data, integrations, access rules, "
            "acceptance criteria and traceability. Preserve unrelated requirements. "
            "A design-only change must not invent backend features. If already represented, return "
            "an empty srs_document patch and an empty diff_summary. Never turn this report into a new "
            "feature merely because it mentions verification or generation."
        )
        result = await get_llm().complete_json(
            system='You maintain the authoritative parent SRS. Return JSON {"srs_document": {changed complete sections only}, "diff_summary": [short changes]}. No new product plan.',
            user=f"CURRENT SRS:\n{json.dumps(_editable_view(srs), ensure_ascii=False)}\n\n{prompt}",
            validator=lambda body: validate_srs(merge_edit(srs, body.get("srs_document"), summary)),
            label="srs_parent_compare")
        updated = merge_edit(srs, result.get("srs_document"), summary)
        diff = result.get("diff_summary") or []
        changed = _editable_view(updated) != _editable_view(srs)
        if not changed:
            diff = []
        srs = updated
        version = _bump_minor(latest["version"]) if changed else latest["version"]
        doc = srs["srs_document"]
        doc["version"] = version
        # The effective plan is a projection of the revised SRS, not another plan pass.
        plan = effective_plan(doc)
        doc["effective_plan"] = plan
        doc["approved_plan"] = plan
        from ..agents.plan_generator import render_plan_markdown
        doc["approved_plan_markdown"] = render_plan_markdown(plan, app_name=plan.get("app_name") or project.get("title", ""))
        attach_handoff(srs, plan, {}, auth=bool(doc.get("protected_pages")))
        storage.write_json(checkpoint, {"srs": srs, "diff": diff if changed else [], "version": version})

    if latest.get("operation_id") != change_id and version != latest["version"]:
        token = CURRENT_JOB.set(change_id)
        try:
            from ..graph.workflow import _checkpointed
            result = await _checkpointed("parent-diagrams", {"project_id": project_id, "srs": srs, "project": project}, [diagram_node])
            srs = result["srs"]
        finally:
            CURRENT_JOB.reset(token)
        storage.save_srs_json(project_id, srs, version)
        await repo.save_version({"id": repo.new_id("ver_"), "project_id": project_id,
            "version": version, "operation_id": change_id, "label": f"{source} update",
            "srs": srs, "diff_summary": diff, "created_at": now_iso()})
    elif latest.get("operation_id") == change_id:
        srs = latest["srs"]
    elif srs != latest["srs"]:
        await repo.update_version_document(latest["id"], srs)

    storage.save_srs_json(project_id, srs, version)
    await repo.save_diagrams(project_id, srs["srs_document"].get("diagrams", []))
    write_handoff(storage.project_dir(project_id) / "handoff", srs, project.get("stack", ""))
    await generate_pdf(project_id, srs, status="Approved", version=version)
    await repo.update_project(project_id, {"status": "approved", "current_version": version})
    result = {"change_id": change_id, "version": version, "diff_summary": diff,
              "summary": summarize_srs(srs), "status": "completed"}
    storage.write_json(receipt, result)
    checkpoint.unlink(missing_ok=True)
    return result
