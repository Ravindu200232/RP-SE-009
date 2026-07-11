"""DiagramGeneratorAgent — build, LLM-improve, and render diagrams.

Pipeline:
  1. Build detailed deterministic Mermaid for all 7 diagram types (guaranteed).
  2. Ask the LLM to produce richer, idea-specific Mermaid; accept a diagram only
     if it passes a Mermaid header/sanity check, otherwise keep the template one
     (so output is always valid and renderable).
  3. Write .mmd and render .svg/.png (mmdc / npx) when available.
"""
from __future__ import annotations

import json

from ..generators.diagrams import DIAGRAM_KINDS, build_diagrams, render_diagrams
from ..llm import LLMRepairFailed, LLMUnavailable, get_llm
from ..services.events import bus
from .state import AgentState

_SYS = (
    "You are a software architect who writes VALID Mermaid diagram code. "
    "Return ONLY JSON: {\"diagrams\":[{\"kind\":..., \"source\":\"<mermaid>\"}]} "
    "for these kinds: use_case, activity, sequence, erd, system_context, "
    "component, deployment. Rules: 'erd' MUST start with 'erDiagram'; 'sequence' "
    "MUST start with 'sequenceDiagram'; all others MUST start with 'flowchart TD' "
    "or 'flowchart LR'. Make each diagram DETAILED and specific to the system "
    "described. Do NOT put parentheses, quotes, or special characters inside node "
    "labels (use plain words). Keep node ids short and alphanumeric. Use the real "
    "table, role, module and workflow names provided."
)


def _valid_mermaid(kind: str, source: str) -> bool:
    src = (source or "").strip()
    if len(src) < 30:
        return False
    head = src.splitlines()[0].strip().lower()
    if kind == "erd":
        return head.startswith("erdiagram")
    if kind == "sequence":
        return head.startswith("sequencediagram")
    return head.startswith("flowchart") or head.startswith("graph")


def _srs_context(doc: dict) -> str:
    db = doc.get("database_design", {})
    tbls = []
    for t in db.get("tables", [])[:20]:
        fields = ", ".join(f.get("name", "") for f in (t.get("fields", []) or [])[:8])
        tbls.append(f"{t['table_name']}({fields})")
    rels = [f"{r.get('from')}->{r.get('to')} [{r.get('type')}]" for r in db.get("relationships", [])[:18]]
    roles = ", ".join(r.get("role_name", "") for r in doc.get("roles", []))
    mods = ", ".join(doc.get("main_modules", []))
    wfs = []
    for w in (doc.get("business_workflows", []) or [])[:2]:
        wfs.append(w.get("workflow_name", "") + ": " + " -> ".join(w.get("steps", [])[:8]))
    integ = ", ".join(i.get("name", "") for i in doc.get("integration_requirements", []))
    return (
        f"PROJECT: {doc.get('project_name')}\n"
        f"ROLES: {roles}\n"
        f"MODULES: {mods}\n"
        f"TABLES: {'; '.join(tbls)}\n"
        f"RELATIONSHIPS: {'; '.join(rels)}\n"
        f"WORKFLOWS: {' || '.join(wfs)}\n"
        f"INTEGRATIONS: {integ}\n"
    )


def _validate_diagram_pack(d: dict) -> None:
    if not isinstance(d, dict) or not isinstance(d.get("diagrams"), list):
        raise ValueError("return JSON {\"diagrams\":[{kind, source}]}")
    valid = [x for x in d["diagrams"]
             if isinstance(x, dict) and x.get("kind") in DIAGRAM_KINDS and _valid_mermaid(x["kind"], x.get("source", ""))]
    if len(valid) < 4:
        raise ValueError("provide at least 4 valid Mermaid diagrams (correct headers per kind)")


async def _llm_diagrams(pid: str, srs: dict) -> dict[str, str]:
    doc = srs.get("srs_document", srs)
    llm = get_llm()
    user = (
        _srs_context(doc)
        + "\nProduce the 7 Mermaid diagrams as specified. The ERD must include the "
        "tables and relationships above with PK/FK markers. The sequence and "
        "activity diagrams should follow the workflow steps."
    )
    data = await llm.complete_json(
        system=_SYS, user=user, validator=_validate_diagram_pack,
        label="diagrams", trace_sink=lambda p: bus.trace(pid, p),
    )
    out: dict[str, str] = {}
    for x in data.get("diagrams", []):
        if isinstance(x, dict) and x.get("kind") in DIAGRAM_KINDS and _valid_mermaid(x["kind"], x.get("source", "")):
            out[x["kind"]] = x["source"].strip()
    return out


async def diagram_node(state: AgentState) -> AgentState:
    pid = state["project_id"]
    srs = state.get("srs", {})
    await bus.log(pid, "DiagramGeneratorAgent", "Generating diagrams from the SRS…", progress=80)

    diagrams = build_diagrams(srs)  # detailed deterministic baseline (all 7)
    for d in diagrams:
        d["generated_by"] = "template"

    try:
        await bus.emit(pid, "DiagramGeneratorAgent", "Asking the LLM to enrich the diagrams…", progress=84)
        llm_map = await _llm_diagrams(pid, srs)
        improved = 0
        for d in diagrams:
            src = llm_map.get(d["kind"])
            if src and _valid_mermaid(d["kind"], src):
                d["source"] = src
                d["generated_by"] = "llm"
                improved += 1
        await bus.emit(pid, "DiagramGeneratorAgent",
                       f"LLM enriched {improved}/{len(diagrams)} diagrams (rest use detailed templates).",
                       level="success", progress=88)
    except LLMUnavailable as exc:
        await bus.emit(pid, "DiagramGeneratorAgent",
                       f"LLM not used ({str(exc)[:120]}) — using detailed template diagrams.",
                       level="warn", progress=88)
    except (LLMRepairFailed, ValueError) as exc:
        await bus.emit(pid, "DiagramGeneratorAgent",
                       f"LLM diagrams unusable ({exc}); using detailed template diagrams.",
                       level="warn", progress=88)
    except Exception as exc:  # noqa: BLE001
        await bus.error(pid, "DiagramGeneratorAgent", f"Diagram LLM step error: {exc}; using templates.")

    diagrams = render_diagrams(pid, diagrams)
    srs.setdefault("srs_document", {})["diagrams"] = diagrams

    rendered = sum(1 for d in diagrams if d.get("png_path"))
    await bus.emit(
        pid, "DiagramGeneratorAgent",
        f"Generated {len(diagrams)} diagrams"
        + (f", {rendered} rendered to image." if rendered else " (sources saved; install mermaid-cli to render images)."),
        level="success", progress=95, data={"count": len(diagrams), "rendered": rendered},
    )
    return {**state, "srs": srs, "diagrams": diagrams}
