"""SrsJsonGeneratorAgent — produce the SRS JSON.

Strategy (robust by construction):
  1. Build a deterministic, schema-valid skeleton. When the customer approved a
     plan, `plan_srs` composes it from that plan and nothing else — which is what
     stops a calculator being specified with five roles and an audit log. With no
     plan we fall back to the old domain-template composer.
  2. If Ollama is reachable, ask the model for a focused ENRICHMENT PACK and
     merge it in here. The plan-aware merge refuses anything outside the plan, so
     the model can sharpen wording but never widen scope.
  3. On any failure, keep the deterministic SRS (never a generic empty one).
  4. Attach the builder handoff — the plan restated in the app builder's own
     vocabulary, plus the prompt string it actually consumes.
"""
from __future__ import annotations

import re

from ..generators.builder_brief import attach_handoff
from ..knowledge.offline_srs import build_offline_srs, merge_pack
from ..knowledge.plan_srs import _auth_on, build_srs_from_plan, merge_pack_planned
from ..llm import LLMRepairFailed, LLMUnavailable, get_llm
from ..schemas.srs import summarize_srs, validate_srs
from ..generators.standards import apply_international_profile
from ..services.events import bus
from .state import AgentState

_SYS = (
    "You are a senior requirements engineer. Given a non-technical user's app "
    "idea and their answers, produce the DOMAIN-SPECIFIC content for a software "
    "requirements specification as STRICT JSON (no prose, no markdown). Tailor "
    "everything to THIS idea — real tables, real modules, real requirements. "
    "Return ONLY a JSON object with these keys:\n"
    "{\n"
    '  "system_category": str,\n'
    '  "app_summary": {"business_goal": str, "short_description": str, "target_users": [str]},\n'
    '  "roles": [{"role_key": snake_case, "role_name": str, "description": str}],\n'
    '  "main_modules": [str],\n'
    '  "pages": [{"route": str, "sections": [str], "functions": [str]}],\n'
    '  "tables": [{"table_name": snake_case, "description": str, "fields": ['
    '{"name": str, "type": "uuid|string|text|integer|decimal|boolean|date|datetime|enum|json|foreign_key", '
    '"primary_key": bool, "nullable": bool, "unique": bool, "references": "table.id", "values": [str], "default": any}]}],\n'
    '  "relationships": [{"from": "table.col", "to": "table.col", "type": "one_to_many|many_to_one|one_to_one|many_to_many", "description": str}],\n'
    '  "functional_requirements": [{"module": str, "requirement": "The system shall …", "priority": "high|medium|low"}],\n'
    '  "non_functional_requirements": [{"category": str, "requirement": str}],\n'
    '  "business_workflows": [{"workflow_name": str, "steps": [str]}],\n'
    '  "validation_rules": [{"field": str, "rule": str}],\n'
    '  "notification_rules": [{"event": str, "recipients": [str], "channels": [str]}],\n'
    '  "reporting_requirements": [{"report_name": str, "filters": [str], "exports": ["PDF","Excel"]}],\n'
    '  "integration_requirements": [{"name": str, "type": str, "description": str, "required": bool}],\n'
    '  "security_requirements": [str],\n'
    '  "risk_priority": [{"area": str, "risk": str, "severity": "High|Medium|Low", "reason": str, "mitigation": str}],\n'
    '  "ambiguities": [{"area": str, "description": str, "assumption_made": str, "needs_clarification": bool}]\n'
    "}\n"
    "Reference foreign keys with the exact 'table.id' form.\n"
    "\n"
    "`pages` is where a specification stops being a list of nouns and becomes "
    "something a developer can build from, so give it real weight. Write one "
    "entry per route the approved plan already has — never a new route — "
    "and for each of them:\n"
    "- `sections`: the blocks a visitor meets going down that page, in order, "
    "each named for what it holds. A landing page is a hero with its headline "
    "and its calls to action, then the browse-by-category strip, the featured "
    "items, the trust or testimonial block, the sign-up strip, the footer. A "
    "list page is its search box, its filters named field by field, its sort "
    "options, the result grid, and what that grid says when it is empty. A "
    "detail page is its image, its identity block, its full description, its "
    "specification table, its action row and its related items. Headings like "
    "'Main content' or 'Details section' are worth nothing to the person "
    "building it.\n"
    "- `functions`: every action a user can take on that page and what each "
    "one does, plus what a row or card in a list shows, field by field. "
    "'Manage products' is not a function. 'Search products by name', "
    "'Filter by category, brand and price', 'Sort by price or newest', and "
    "'Each card shows image, name, brand, price, discounted price when set, "
    "stock state and an Add to Cart action' are four. Name the empty state, "
    "the over-limit state, and the refusal message wherever a rule can reject "
    "the action.\n"
    "The builder reads this and nothing else when it lays out the screen. A "
    "page left with one line of functions and no sections is built as one line "
    "of functions and no sections, and the customer opens a heading over an "
    "empty box.\n"
    "\n"
    "THE APPROVED PLAN IS THE BOUNDARY. It is what the customer read and signed "
    "off on, and it is the whole of what you are specifying.\n"
    "- Do NOT introduce a record, role, screen or capability the plan does not "
    "contain. Detail and sharpen what is there; never widen it. Anything you add "
    "beyond the plan is discarded, so it only costs you attention.\n"
    "- Give NO minimum counts any thought. Three tables is the right answer when "
    "the plan has three records, and one is the right answer when it has one.\n"
    "- If the plan has no login, the app has no accounts. Do not mention users, "
    "roles, permissions, admins, sign-in or audit logs anywhere — not in a "
    "requirement, not in a table, not in a risk.\n"
    "- Each `table_name` is the PLAIN PLURAL of the thing it holds: books, "
    "students, loans, products, sales. Never pluralise a name that is already "
    "plural — `bookses`, `studentses`, `loanses`, `productses`, `customerses` "
    "are not words. Nothing downstream corrects this: the builder creates the "
    "collection under exactly the name you write, so `bookses` ships as a "
    "real collection in a real app. It has happened in 4 specifications."
)


def _pages_to_cover(skeleton: dict) -> str:
    """Name every route the enrichment has to describe, and count them.

    "One entry per route the plan has" gets read as "the interesting ones": a
    courier spec came back with fifteen of seventeen, and the two it skipped
    were the driver screens, which shipped as a heading over nothing. A list
    with a number on it is much harder to come up short against.
    """
    doc = (skeleton or {}).get("srs_document") or {}
    routes = [str(p.get("route") or "").strip()
              for p in (doc.get("public_pages") or []) + (doc.get("protected_pages") or [])
              if isinstance(p, dict) and str(p.get("route") or "").strip()]
    if not routes:
        return ""
    listed = "\n".join(f"- {r}" for r in routes)
    return (f"THE {len(routes)} ROUTES YOUR `pages` MUST COVER, ALL OF THEM:\n"
            f"{listed}\n\nReturn exactly {len(routes)} entries in `pages`, "
            f"one per route above, each with its sections and its functions. A "
            f"route you leave out is built as an empty screen.\n\n")


def _answers_digest(questions: list[dict], answers: list[dict]) -> str:
    by_id = {q["id"]: q for q in questions}
    lines = []
    for a in answers:
        q = by_id.get(a.get("question_id"))
        if not q:
            continue
        val = a.get("raw_text") or a.get("value")
        if isinstance(val, list):
            val = ", ".join(str(x) for x in val)
        lines.append(f"- {q['question']} → {val}")
    return "\n".join(lines) or "(no explicit answers; use sensible defaults)"


def _validate_pack(d: dict) -> None:
    """Accept precise enrichment without forcing extra scope."""
    if not isinstance(d, dict):
        raise ValueError("pack must be a JSON object")
    tables = d.get("tables", [])
    if not isinstance(tables, list):
        raise ValueError("'tables' must be a list when supplied")
    unnamed = [t for t in tables if not isinstance(t, dict) or not t.get("table_name")]
    if unnamed:
        raise ValueError("every supplied table needs a table_name")
    frs = d.get("functional_requirements", [])
    if not isinstance(frs, list):
        raise ValueError("'functional_requirements' must be a list when supplied")
    malformed = [f for f in frs if not isinstance(f, dict) or not f.get("requirement")]
    if malformed:
        raise ValueError("every supplied functional requirement needs requirement text")


def _plan_scope_guard(plan: dict, auth: bool):
    """A validator that fails the pack for going outside the plan.

    The old gate demanded *at least* four tables and five requirements, which is
    exactly what made a calculator invent six. With a plan in hand the useful
    check is the opposite one: nothing new. Failing here re-prompts the model
    with the offending names, which is cheaper than silently dropping them.
    """
    allowed = {_norm(r.get("name", "")) for r in (plan.get("records") or [])}
    forbidden = ("login", "sign in", "sign-in", "password", "role", "permission",
                 "admin", "authenticat")

    def check(d: dict) -> None:
        if not isinstance(d, dict):
            raise ValueError("pack must be a JSON object")
        strays = sorted({
            str(t.get("table_name")) for t in (d.get("tables") or [])
            if isinstance(t, dict) and t.get("table_name")
            and _norm(t["table_name"]) not in allowed
        })
        if strays:
            raise ValueError(
                "these records are not in the approved plan and must be removed: "
                + ", ".join(strays)
                + ". The plan's records are: "
                + (", ".join(sorted(allowed)) or "(none)")
            )
        if not auth:
            blob = " ".join(
                str(f.get("requirement", "")) for f in (d.get("functional_requirements") or [])
                if isinstance(f, dict)
            ).lower()
            hits = sorted({w for w in forbidden if w in blob})
            if hits:
                raise ValueError(
                    "this app has no login, so no requirement may mention "
                    + ", ".join(hits) + ". Remove those requirements."
                )

    return check


def _norm(name: str) -> str:
    """Loose key so `Sale`, `sales` and `sale_items`/`Sale Item` compare sanely."""
    key = re.sub(r"[^a-z0-9]", "", str(name or "").lower())
    if key.endswith("ies"):
        return key[:-3] + "y"
    if key.endswith("s") and not key.endswith("ss"):
        return key[:-1]
    return key


async def generate_srs_node(state: AgentState) -> AgentState:
    pid = state["project_id"]
    project = state.get("project", {})
    brief = state.get("brief", "")
    questions = state.get("questions", [])
    answers = state.get("answers", [])

    session = state.get("session") or {}
    plan = state.get("plan") or {}
    pack_profile = session.get("pack") or {}
    auth = _auth_on(pack_profile, plan) if plan else True

    if plan:
        await bus.log(pid, "SrsJsonGeneratorAgent",
                      "Composing the SRS from the approved plan…", progress=10)
        skeleton = build_srs_from_plan(project=project, plan=plan, pack=pack_profile,
                                       session=session, brief=brief)
        validator = _plan_scope_guard(plan, auth)
    else:
        await bus.log(pid, "SrsJsonGeneratorAgent",
                      "No approved plan — composing from the domain template…", progress=10)
        skeleton = build_offline_srs(project=project, answers=answers,
                                     session=session, brief=brief)
        validator = _validate_pack
    try:
        validate_srs(skeleton)
    except Exception as exc:  # noqa: BLE001 - should not happen; log if it does
        await bus.error(pid, "SrsJsonGeneratorAgent", f"Skeleton failed validation: {exc}")

    srs = skeleton
    try:
        llm = get_llm()
        await bus.emit(pid, "SrsJsonGeneratorAgent", "Asking the LLM for domain-specific content…", progress=35)
        digest = _answers_digest(questions, answers)
        plan_md = str(state.get("plan_markdown") or "").strip()
        user = (
            f"DETECTED DOMAIN: {state.get('classification', {}).get('detected_domain')}\n\n"
            f"USER IDEA / BRIEF:\n{brief[:3000]}\n\n"
            + (f"THE APPROVED PLAN — THIS IS THE BOUNDARY:\n{plan_md[:6000]}\n\n" if plan_md else "")
            + (("This app has NO login and NO user accounts. Say nothing about "
                "users, roles, permissions or admins.\n\n") if plan and not auth else "")
            + f"USER ANSWERS:\n{digest}\n\n"
            + _pages_to_cover(skeleton)
            + "Now produce the enrichment JSON described in the system message, "
            "tailored precisely to this idea."
        )
        pack = await llm.complete_json(
            system=_SYS, user=user, validator=validator,
            label="srs_enrich", trace_sink=lambda p: bus.trace(pid, p),
        )
        merged = (merge_pack_planned(skeleton, pack, plan) if plan
                  else merge_pack(skeleton, pack))
        validate_srs(merged)
        srs = merged
        doc = srs["srs_document"]
        await bus.emit(pid, "SrsJsonGeneratorAgent",
                       f"LLM enrichment merged: {len(doc['database_design']['tables'])} tables, "
                       f"{len(doc['functional_requirements'])} FR.", level="success", progress=60)
    except LLMUnavailable as exc:
        await bus.emit(pid, "SrsJsonGeneratorAgent",
                       f"LLM not used ({str(exc)[:140]}) — using the deterministic domain SRS.",
                       level="warn", progress=60)
    except LLMRepairFailed as exc:
        await bus.error(pid, "SrsJsonGeneratorAgent",
                        f"LLM enrichment didn't validate after retries; kept deterministic SRS. ({exc.label})",
                        data={"raw_preview": (exc.raw or "")[:500]})
    except Exception as exc:  # noqa: BLE001
        await bus.error(pid, "SrsJsonGeneratorAgent", f"SRS enrichment error: {exc}; kept deterministic SRS.")

    apply_international_profile(srs)

    if plan:
        srs["srs_document"]["approved_plan_markdown"] = str(state.get("plan_markdown") or "")
        # The customer's own words, kept whole. The seed sizes they wrote down
        # ("at least 6 rooms, at least 20 events") live nowhere else by this
        # point: the interview turns them into records and the counts are lost,
        # so the handoff asked for "realistic demo data" and the build shipped
        # two rooms and three events.
        srs["srs_document"]["customer_brief"] = str(brief or "")
        attach_handoff(srs, plan, pack_profile, auth=auth)
        handoff = srs["srs_document"]["builder_handoff"]
        await bus.emit(pid, "SrsJsonGeneratorAgent",
                       f"Builder handoff ready: {len(handoff['requirements'])} requirements, "
                       f"{len(handoff['prompt'].split())} words.",
                       level="success", progress=65)

    summary = summarize_srs(srs)
    await bus.emit(
        pid, "SrsJsonGeneratorAgent",
        f"SRS ready: {summary['functional']} FR, {summary['non_functional']} NFR, "
        f"{summary['tables']} tables, {summary['roles']} roles"
        + ("" if auth else ", no login") + ".",
        level="success", progress=70, data={"summary": summary},
    )
    return {**state, "srs": srs}
