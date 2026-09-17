"""LangGraph assembly."""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ..agents.coverage_auditor import audit_node
from ..agents.customization import customize_node
from ..agents.diagram_generator import diagram_node
from ..agents.domain_classifier import classify_node
from ..agents.english_plan import english_plan_node
from ..agents.intake import intake_node
from ..agents.pdf_generator import generate_pdf
from ..agents.reviewer import review_srs_node
from ..agents.srs_generator import generate_srs_node
from ..agents.state import AgentState
from ..services.events import bus

__all__ = ["run_analysis", "run_generation", "run_customization", "generate_pdf"]


async def clarify_node(state: AgentState) -> AgentState:
    await bus.emit(state["project_id"], "InterviewAgent",
                   "The idea was hard to read — starting from the app type.",
                   level="warn", progress=60)
    return {**state, "needs_clarification": True}


def _route_after_intake(state: AgentState) -> str:
    return "clarify" if state.get("is_nonsense") else "classify"


def _build_analysis():
    g = StateGraph(AgentState)
    g.add_node("intake", intake_node)
    g.add_node("classify", classify_node)
    g.add_node("clarify", clarify_node)
    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", _route_after_intake,
                            {"clarify": "clarify", "classify": "classify"})
    g.add_edge("classify", END)
    g.add_edge("clarify", END)
    return g.compile()


_analysis = None


async def run_analysis(state: AgentState) -> AgentState:
    global _analysis
    if _analysis is None:
        _analysis = _build_analysis()
    return await _analysis.ainvoke(state)


async def run_generation(state: AgentState) -> AgentState:
    return await _checkpointed(
        "generation", state,
        [audit_node, english_plan_node, generate_srs_node, review_srs_node, diagram_node])


async def run_customization(state: AgentState) -> AgentState:
    return await _checkpointed("customization", state, [customize_node, diagram_node])


async def _checkpointed(kind: str, state: AgentState, steps) -> AgentState:
    import hashlib
    import json
    from ..services import storage
    from ...jobs import CURRENT_JOB
    fingerprint = CURRENT_JOB.get() or hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    path = storage.project_dir(state["project_id"]) / f"{kind}-checkpoint.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    index = 0
    if saved.get("input") == fingerprint:
        state = saved["state"]
        index = saved["next"]
    # An index-driven walk rather than a for-range, so a step can ask to go back
    # to an earlier one by returning `_goto`. That is the whole of the reviewer's
    # enhance loop. The checkpoint format does not change - `next` was already an
    # index, it may simply now decrease - so a job interrupted mid-generation
    # still resumes where it stopped.
    #
    # The cap lives in the node that asks, not here: a loop that cannot run away
    # regardless of what a node returns is worth more than a second counter.
    names = [getattr(step, "__name__", str(position)) for position, step in enumerate(steps)]
    while index < len(steps):
        state = {**state, **await steps[index](state)}
        target = state.pop("_goto", None)
        index = names.index(target) if target in names else index + 1
        storage.write_json(path, {"input": fingerprint, "next": index, "state": state})
    return state
