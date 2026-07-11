"""LangGraph assembly.

Three compiled graphs compose the 8 agent nodes:

* analysis      : intake → (clarify | classify → plan)
* generation    : audit → generate_srs → diagrams
* customization : customize → diagrams

Each maps to a phase of the product flow that is separated by human input
(answering questions / approving), which keeps every graph a clean DAG.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ..agents.coverage_auditor import audit_node
from ..agents.customization import customize_node
from ..agents.diagram_generator import diagram_node
from ..agents.domain_classifier import classify_node
from ..agents.intake import intake_node
from ..agents.pdf_generator import generate_pdf  # re-exported for callers
from ..agents.question_planner import plan_questions_node
from ..agents.srs_generator import generate_srs_node
from ..agents.state import AgentState
from ..services.events import bus

__all__ = ["run_analysis", "run_generation", "run_customization", "generate_pdf"]


# ── clarify (nonsense input) ─────────────────────────────────
_CLARIFY_QUESTIONS = [
    {"id": "Q1", "question": "What kind of business or app do you want to build?",
     "why_needed": "We could not understand the idea; this anchors the domain.",
     "answer_type": "single_choice",
     "suggested_options": ["Hotel / Hospitality", "Online Store / E-commerce", "Healthcare / Clinic",
                           "Education / School", "Vehicle / Automotive", "Other"],
     "maps_to_srs_fields": ["system_category"], "coverage_areas": ["business_type"], "required": True},
    {"id": "Q2", "question": "In one sentence, what should it help people do?",
     "why_needed": "Defines the core goal.", "answer_type": "free_text", "suggested_options": [],
     "maps_to_srs_fields": ["app_summary.business_goal"], "coverage_areas": ["main_goal"], "required": True},
    {"id": "Q3", "question": "Who will use it? (e.g. admins, customers, staff)",
     "why_needed": "Defines the roles.", "answer_type": "free_text", "suggested_options": [],
     "maps_to_srs_fields": ["roles"], "coverage_areas": ["users_roles"], "required": True},
]


async def clarify_node(state: AgentState) -> AgentState:
    await bus.emit(state["project_id"], "QuestionPlannerAgent",
                   "Asking 3 basic questions to understand the idea.", level="warn", progress=60)
    return {**state, "questions": list(_CLARIFY_QUESTIONS), "needs_clarification": True}


def _route_after_intake(state: AgentState) -> str:
    return "clarify" if state.get("is_nonsense") else "classify"


# ── graph builders ───────────────────────────────────────────
def _build_analysis():
    g = StateGraph(AgentState)
    g.add_node("intake", intake_node)
    g.add_node("classify", classify_node)
    g.add_node("plan", plan_questions_node)
    g.add_node("clarify", clarify_node)
    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", _route_after_intake,
                            {"clarify": "clarify", "classify": "classify"})
    g.add_edge("classify", "plan")
    g.add_edge("plan", END)
    g.add_edge("clarify", END)
    return g.compile()


def _build_generation():
    g = StateGraph(AgentState)
    g.add_node("audit", audit_node)
    g.add_node("generate", generate_srs_node)
    g.add_node("render_diagrams", diagram_node)
    g.add_edge(START, "audit")
    g.add_edge("audit", "generate")
    g.add_edge("generate", "render_diagrams")
    g.add_edge("render_diagrams", END)
    return g.compile()


def _build_customization():
    g = StateGraph(AgentState)
    g.add_node("customize", customize_node)
    g.add_node("render_diagrams", diagram_node)
    g.add_edge(START, "customize")
    g.add_edge("customize", "render_diagrams")
    g.add_edge("render_diagrams", END)
    return g.compile()


_analysis = None
_generation = None
_customization = None


async def run_analysis(state: AgentState) -> AgentState:
    global _analysis
    if _analysis is None:
        _analysis = _build_analysis()
    return await _analysis.ainvoke(state)


async def run_generation(state: AgentState) -> AgentState:
    global _generation
    if _generation is None:
        _generation = _build_generation()
    return await _generation.ainvoke(state)


async def run_customization(state: AgentState) -> AgentState:
    global _customization
    if _customization is None:
        _customization = _build_customization()
    return await _customization.ainvoke(state)
