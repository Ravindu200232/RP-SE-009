"""SrsReviewerAgent — read the draft back and say what is wrong with it.

Until this node existed the first draft was the final draft. The only quality
pass was `generators/standards._quality_flags`, a regex that records "possibly
vague" against a requirement and never acts on it.

The reviewer audits the draft against the same skills the generator wrote it
from — `functional-requirements`, `non-functional-quality`,
`security-architecture` — and either accepts it or sends it back with findings
the generator can act on. What it cannot do is widen scope: the generator
rebuilds its skeleton from the approved plan on every pass and
`_plan_scope_guard` refuses anything the plan does not contain. So a round can
sharpen a requirement, add a missing threshold, or raise an ambiguity, and it
structurally cannot invent a feature.

Three things decide when to stop, and none of them is the model:

  * the configured iteration cap;
  * no progress - a round that did not reduce the blocking findings will not
    reduce them next time either;
  * anything going wrong with the LLM, which accepts the draft. A reviewer that
    can block SRS generation is worse than no reviewer, because the
    deterministic SRS is always worth shipping.
"""
from __future__ import annotations

from ..config import settings
from ..llm import LLMRepairFailed, LLMUnavailable, get_llm
from ..services import storage
from ..services.events import bus
from ..skills import get_active_skills_guidance
from .state import AgentState

AUDIT_SKILLS = ("functional-requirements", "non-functional-quality", "security-architecture")
SEVERITIES = ("blocker", "major", "minor")
SCORES = ("functional", "non_functional", "security", "ambiguity", "traceability")
# A score below this is a blocking judgement even when no single requirement was
# named - "the security section is thin" is a real finding without a culprit.
FLOOR = 3

_SYS = (
    "You review a software requirements specification against the engineering "
    "standards you are given, and you report. You do not rewrite the document.\n\n"
    "Return JSON only, in exactly this shape:\n"
    '{"verdict": "accept" | "revise",\n'
    ' "scores": {"functional": 0-5, "non_functional": 0-5, "security": 0-5, '
    '"ambiguity": 0-5, "traceability": 0-5},\n'
    ' "findings": [{"requirement_id": "<an id that exists in the document>", '
    '"skill": "<which standard it breaks>", "rule": "<the rule, quoted briefly>", '
    '"severity": "blocker" | "major" | "minor", "problem": "<what is wrong>", '
    '"suggested_rewrite": "<the requirement, rewritten>"}],\n'
    ' "missing_requirements": [{"kind": "non_functional" | "security", '
    '"topic": "<what is absent>", "why": "<why the standard requires it>"}],\n'
    ' "ambiguities": [{"area": "...", "description": "<what is unclear>", '
    '"assumption_made": "<what a reader would have to assume>", '
    '"needs_clarification": true}]}\n\n'
    "Rules:\n"
    "- Every `requirement_id` must be an id that appears in the document. Do not "
    "invent one. If a problem has no single owner, report it through `scores` and "
    "`missing_requirements` instead.\n"
    "- `blocker` means the requirement cannot be built or tested as written. Use "
    "it sparingly and never more than five times.\n"
    "- Do not propose new features, screens, roles or tables. The product scope is "
    "settled; you are judging how it is written down.\n"
    "- An empty `findings` list is the right answer for a specification that "
    "meets the standards."
)


def _ids(doc: dict) -> set[str]:
    out = set()
    for key in ("functional_requirements", "non_functional_requirements"):
        for item in (doc.get(key) or []):
            if isinstance(item, dict) and item.get("id"):
                out.add(str(item["id"]))
    return out


def _validator(doc: dict):
    """Reject a verdict that is not actionable.

    A finding against a requirement that does not exist cannot be fixed, and a
    round spent on one is a round the cap has already spent. Better to fail the
    response and let the repair loop ask again.
    """
    known = _ids(doc)

    def check(body: dict) -> dict:
        if not isinstance(body, dict):
            raise ValueError("The review must be a JSON object.")
        scores = body.get("scores") or {}
        if not isinstance(scores, dict):
            raise ValueError("`scores` must be an object.")
        for key in SCORES:
            value = scores.get(key)
            if not isinstance(value, (int, float)) or not 0 <= float(value) <= 5:
                raise ValueError(f"`scores.{key}` must be a number from 0 to 5.")
        findings = body.get("findings") or []
        if not isinstance(findings, list):
            raise ValueError("`findings` must be a list.")
        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError("Each finding must be an object.")
            if str(finding.get("severity", "")).lower() not in SEVERITIES:
                raise ValueError(f"`severity` must be one of {', '.join(SEVERITIES)}.")
            rid = str(finding.get("requirement_id") or "").strip()
            if rid and known and rid not in known:
                raise ValueError(
                    f"`requirement_id` {rid!r} is not in the document. "
                    f"Use one of: {', '.join(sorted(known)[:12])}.")
            if not str(finding.get("problem") or "").strip():
                raise ValueError("Each finding needs a `problem`.")
        return body

    return check


def _blockers(verdict: dict) -> list[dict]:
    return [f for f in (verdict.get("findings") or [])
            if str(f.get("severity", "")).lower() == "blocker"]


def _satisfied(verdict: dict) -> bool:
    """Python decides, not the model.

    The model's own `verdict` string is kept for the record but not obeyed: a
    reviewer asked to judge its own judgement tends to accept.
    """
    if _blockers(verdict):
        return False
    scores = verdict.get("scores") or {}
    return all(float(scores.get(key, 0)) >= FLOOR for key in SCORES)


def _digest(doc: dict) -> str:
    """The parts of the document a reviewer needs, without the parts it does not."""
    import json
    keep = ("project_name", "app_summary", "functional_requirements",
            "non_functional_requirements", "security_requirements", "roles",
            "business_workflows", "acceptance_criteria", "ambiguities",
            "requirement_traceability_matrix", "validation_rules")
    return json.dumps({k: doc.get(k) for k in keep if doc.get(k)},
                      ensure_ascii=False)[:24000]


def _record(state: AgentState, round_no: int, payload: dict) -> None:
    try:
        storage.save_review_round(state["project_id"], round_no, payload)
    except Exception:  # noqa: BLE001 - a lost note must not fail the run
        pass


def _accept(state: AgentState, status: str, detail: str = "", verdict: dict | None = None) -> AgentState:
    """Finish reviewing and stamp the outcome on the document."""
    srs = state.get("srs") or {}
    doc = srs.get("srs_document") if isinstance(srs, dict) else None
    if isinstance(doc, dict):
        # Nested inside a field the handoff already knows about. A new top-level
        # key would become a new "## ..." section in app.md, silently changing
        # the contract the builder reads.
        review = doc.setdefault("requirements_quality_review", {})
        if isinstance(review, dict):
            review["reviewer"] = {
                "status": status,
                "iterations_used": int(state.get("review_round") or 0),
                "stopped_because": detail,
                "final_scores": (verdict or {}).get("scores") or {},
                "unresolved_findings": (verdict or {}).get("findings") or [],
            }
    return {**state, "review_feedback": None, "review_done": True}


async def review_srs_node(state: AgentState) -> AgentState:
    pid = state["project_id"]
    srs = state.get("srs") or {}
    doc = (srs.get("srs_document") if isinstance(srs, dict) else None) or {}
    if not doc.get("functional_requirements"):
        return _accept(state, "skipped", "there was nothing to review")

    round_no = int(state.get("review_round") or 0)
    cap = max(0, int(getattr(settings, "srs_review_max_iterations", 2)))
    previous_blockers = state.get("review_blockers")

    await bus.log(pid, "SrsReviewerAgent",
                  f"Reviewing the draft against the requirements standards (round {round_no + 1})…",
                  progress=66)

    guidance = get_active_skills_guidance(only=AUDIT_SKILLS, budget=5000)
    user = (
        f"THE STANDARDS YOU ARE AUDITING AGAINST:\n{guidance}\n\n"
        f"THE SPECIFICATION:\n{_digest(doc)}\n\n"
        "Report against the standards above. Judge how the requirements are "
        "written, not what the product does."
    )

    try:
        verdict = await get_llm().complete_json(
            system=_SYS, user=user, validator=_validator(doc),
            label="srs_review", trace_sink=lambda p: bus.trace(pid, p))
    except LLMUnavailable as exc:
        await bus.emit(pid, "SrsReviewerAgent",
                       f"Review skipped ({str(exc)[:120]}) — keeping the draft as written.",
                       level="warn", progress=68)
        return _accept(state, "skipped", "the model was unavailable")
    except LLMRepairFailed as exc:
        await bus.error(pid, "SrsReviewerAgent",
                        f"The review did not validate after retries; keeping the draft. ({exc.label})",
                        data={"raw_preview": (exc.raw or "")[:400]})
        return _accept(state, "skipped", "the review did not validate")
    except Exception as exc:  # noqa: BLE001 - never block generation on the critic
        await bus.error(pid, "SrsReviewerAgent", f"Review error: {exc}; keeping the draft.")
        return _accept(state, "skipped", "the review failed")

    blockers = _blockers(verdict)
    findings = verdict.get("findings") or []
    _record(state, round_no + 1, {"round": round_no + 1, "verdict": verdict,
                                  "blockers": len(blockers), "findings": len(findings)})

    if _satisfied(verdict):
        await bus.emit(pid, "SrsReviewerAgent",
                       f"Accepted after {round_no + 1} round(s): {len(findings)} note(s), no blocking findings.",
                       level="success", progress=70)
        return _accept(state, "accepted", "the draft met the standards", verdict)

    if round_no >= cap:
        await bus.emit(pid, "SrsReviewerAgent",
                       f"Review limit reached with {len(blockers)} blocking finding(s) left; "
                       "they are recorded on the document.",
                       level="warn", progress=70)
        return _accept(state, "capped", f"the {cap}-round review limit was reached", verdict)

    if previous_blockers is not None and len(blockers) >= int(previous_blockers):
        await bus.emit(pid, "SrsReviewerAgent",
                       f"The last round did not reduce the {len(blockers)} blocking finding(s); stopping.",
                       level="warn", progress=70)
        return _accept(state, "stalled", "a round made no progress", verdict)

    await bus.emit(pid, "SrsReviewerAgent",
                   f"{len(blockers)} blocking finding(s) — sending the draft back to be rewritten.",
                   level="warn", progress=68)
    return {**state,
            "_goto": "generate_srs_node",
            "review_round": round_no + 1,
            "review_blockers": len(blockers),
            "review_feedback": verdict}
