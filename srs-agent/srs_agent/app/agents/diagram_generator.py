"""DiagramGeneratorAgent — build, LLM-improve, and render diagrams.

Pipeline:
  1. Build detailed deterministic Mermaid for all 7 diagram types (guaranteed).
  2. Ask the LLM to produce richer, idea-specific Mermaid; accept a diagram only
     if it passes a Mermaid header/sanity check, otherwise keep the template one
     (so output is always valid and renderable).
  3. Write .mmd and render .svg/.png (mmdc / npx) when available.
"""
from __future__ import annotations

import asyncio

from ..generators.diagrams import (
    DIAGRAM_KINDS,
    build_diagrams,
    mermaid_problems,
    render_diagrams,
    valid_mermaid,
)
from ..llm import LLMRepairFailed, LLMUnavailable, get_llm
from ..services.events import bus
from .customer_context import customer_context
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
    "table, role, module and workflow names provided.\n"
    "Structure is checked, not just the first line:\n"
    "- every subgraph must have a matching end\n"
    "- every node you declare must be connected by at least one arrow — a node "
    "nobody points at is a mistake\n"
    "- never reference a node id you did not declare\n"
    "- in a sequence diagram every activate needs its deactivate, and every "
    "participant must be declared before it is messaged\n"
    "- the use case diagram's bubbles are ACTIONS a person takes, in their own "
    "words. Never a page or a screen name, and never the same text twice."
)


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
    valid, faults = [], []
    for x in d["diagrams"]:
        if not isinstance(x, dict) or x.get("kind") not in DIAGRAM_KINDS:
            continue
        problems = mermaid_problems(x["kind"], x.get("source", ""))
        if problems:
            faults.append(f"{x['kind']}: {'; '.join(problems)}")
        else:
            valid.append(x)
    if len(valid) < 4:

        detail = (" Problems found — " + " | ".join(faults[:6])) if faults else ""
        raise ValueError("provide at least 4 structurally valid Mermaid diagrams." + detail)


async def _llm_diagrams(pid: str, srs: dict, context: str = "") -> dict[str, str]:
    doc = srs.get("srs_document", srs)
    llm = get_llm()
    user = (
        (f"{context}\n\n" if context else "")
        + _srs_context(doc)
        + "\nProduce the 7 Mermaid diagrams as specified. The ERD must include the "
        "tables and relationships above with PK/FK markers. The sequence and "
        "activity diagrams should follow the workflow steps. Label everything in "
        "the customer's own words, not in generic placeholders."
    )
    data = await llm.complete_json(
        system=_SYS, user=user, validator=_validate_diagram_pack,
        label="diagrams", trace_sink=lambda p: bus.trace(pid, p),
    )
    out: dict[str, str] = {}
    for x in data.get("diagrams", []):
        if isinstance(x, dict) and x.get("kind") in DIAGRAM_KINDS and valid_mermaid(x["kind"], x.get("source", "")):
            out[x["kind"]] = x["source"].strip()
    return out


async def diagram_node(state: AgentState) -> AgentState:
    pid = state["project_id"]
    srs = state.get("srs", {})
    await bus.log(pid, "DiagramGeneratorAgent", "Generating diagrams from the SRS…", progress=80)

    faults: list[str] = []
    diagrams = build_diagrams(srs, on_error=faults.append)
    for d in diagrams:
        d["generated_by"] = "template"
    for fault in faults:
        await bus.error(pid, "DiagramGeneratorAgent", f"Diagram template fault — {fault}")

    try:
        await bus.emit(pid, "DiagramGeneratorAgent", "Asking the LLM to enrich the diagrams…", progress=84)
        llm_map = await _llm_diagrams(
            pid, srs, customer_context(brief=state.get("brief", ""),
                                       session=state.get("session"),
                                       project=state.get("project")))
        improved = 0
        for d in diagrams:
            src = llm_map.get(d["kind"])
            if src and valid_mermaid(d["kind"], src):
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

    render_faults: list[str] = []

    diagrams = await asyncio.to_thread(render_diagrams, pid, diagrams,
                                       on_error=render_faults.append)
    srs.setdefault("srs_document", {})["diagrams"] = diagrams

    for fault in render_faults[:8]:
        await bus.error(pid, "DiagramGeneratorAgent", fault)

    rendered = sum(1 for d in diagrams if d.get("svg_path") or d.get("png_path"))
    await bus.emit(
        pid, "DiagramGeneratorAgent",
        f"Generated {len(diagrams)} diagrams"
        + (f", {rendered} rendered to image." if rendered
           else " (sources saved; see Errors for why no images were rendered)."),
        level="success", progress=95, data={"count": len(diagrams), "rendered": rendered},
    )
    return {**state, "srs": srs, "diagrams": diagrams}
