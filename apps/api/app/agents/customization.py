"""CustomizationAgent — edit an existing SRS from a plain-English prompt.

LLM path: ask the model to apply the edit and return the full updated SRS +
a diff summary, validated through the repair loop. Deterministic fallback:
intent-detect common edits (add feature/requirement, rename module, stricter
performance, add language, add payment/approval) and mutate only the relevant
sections — unrelated content is preserved and version history is kept by the
caller.
"""
from __future__ import annotations

import copy
import json
import re

from ..llm import LLMRepairFailed, LLMUnavailable, get_llm
from ..schemas.srs import validate_srs
from ..services.events import bus
from .state import AgentState

_SYS = (
    "You edit an existing IEEE-830 SRS JSON based on a user's plain-English "
    "request. Apply ONLY what is asked; preserve everything else exactly. Keep "
    "the same JSON shape with root key 'srs_document'. Return ONLY JSON of the "
    'form {"srs_document": {...}, "diff_summary": ["short bullet", ...]}.'
)


def _next_id(items: list[dict], prefix: str) -> str:
    nums = [int(re.sub(r"\D", "", i.get("id", "")) or 0) for i in items]
    return f"{prefix}-{(max(nums) + 1) if nums else 1:03d}"


def apply_customization(srs: dict, prompt: str) -> tuple[dict, list[str]]:
    """Deterministic intent-based editor. Never deletes unrelated sections."""
    doc = copy.deepcopy(srs)["srs_document"]
    p = prompt.lower().strip()
    diff: list[str] = []

    # ── rename module / service ──────────────────────────────
    # Match on the ORIGINAL prompt so the new name keeps its casing.
    m = re.search(r"rename\s+([\w\- ]+?)\s+(?:to|->|→)\s+([\w\- ]+)", prompt, flags=re.IGNORECASE)
    if m:
        old, new = m.group(1).strip(), m.group(2).strip()
        blob = json.dumps(doc)
        # Replace case-insensitively across the whole document.
        new_blob = re.sub(re.escape(old), new, blob, flags=re.IGNORECASE)
        doc = json.loads(new_blob)
        diff.append(f"Renamed '{old}' → '{new}' across the SRS.")

    # ── stricter performance ─────────────────────────────────
    if ("performance" in p or "p95" in p or "faster" in p or "stricter" in p) and "rename" not in p:
        changed = False
        for nfr in doc.get("non_functional_requirements", []):
            if nfr.get("category", "").lower() == "performance":
                nfr["requirement"] = re.sub(r"\b3\s*seconds?\b", "1 second", nfr["requirement"], flags=re.IGNORECASE)
                if "P95" not in nfr["requirement"]:
                    nfr["requirement"] += " (P95 latency target tightened)."
                changed = True
        if changed:
            diff.append("Tightened performance NFR to a stricter P95 target.")

    # ── languages ────────────────────────────────────────────
    langs = re.findall(r"\b(sinhala|tamil|english|spanish|french|arabic|german|hindi)\b", p)
    if "language" in p or langs:
        names = sorted({l.capitalize() for l in langs}) or ["additional languages"]
        ui = doc.setdefault("ui_ux_requirements", {})
        ui["languages"] = sorted(set(ui.get("languages", []) + names))
        doc.setdefault("functional_requirements", []).append({
            "id": _next_id(doc.get("functional_requirements", []), "FR"),
            "module": "Localization",
            "requirement": f"The system shall support {', '.join(names)} as selectable display languages.",
            "priority": "medium",
        })
        diff.append(f"Added language support: {', '.join(names)}.")

    # ── payment / multi-currency ─────────────────────────────
    if "currency" in p or "multi-currency" in p or "multicurrency" in p:
        doc.setdefault("functional_requirements", []).append({
            "id": _next_id(doc.get("functional_requirements", []), "FR"),
            "module": "Payments",
            "requirement": "The system shall support multiple currencies with configurable exchange rates and per-transaction currency selection.",
            "priority": "high",
        })
        diff.append("Added multi-currency requirement.")
    elif "payment" in p or "payment gateway" in p or "stripe" in p or "checkout" in p:
        ints = doc.setdefault("integration_requirements", [])
        if not any(i.get("type") == "payment" for i in ints):
            ints.append({"name": "Payment Gateway", "type": "payment",
                         "description": "Online card payments via a hosted gateway.", "required": True})
        doc.setdefault("functional_requirements", []).append({
            "id": _next_id(doc.get("functional_requirements", []), "FR"),
            "module": "Payments",
            "requirement": "The system shall accept online payments through a secure hosted payment gateway.",
            "priority": "high",
        })
        diff.append("Added online payment gateway requirement.")

    # ── approval workflow ────────────────────────────────────
    m2 = re.search(r"add\s+(?:admin\s+)?approval\s+for\s+([\w\- ]+)", p)
    if m2:
        thing = m2.group(1).strip()
        doc.setdefault("business_workflows", []).append({
            "workflow_name": f"{thing.title()} Approval Workflow",
            "steps": [f"User requests {thing}", "Request enters 'pending approval' state",
                      "Admin reviews the request", "Admin approves or rejects",
                      f"On approval the {thing} is processed", "Requester is notified of the outcome"],
        })
        doc.setdefault("validation_rules", []).append(
            {"field": thing.replace(" ", "_"), "rule": f"A {thing} requires admin approval before it is finalised."})
        diff.append(f"Added admin approval workflow for {thing}.")

    # ── loyalty programme ────────────────────────────────────
    if "loyalty" in p or "rewards" in p or "points" in p:
        mods = doc.setdefault("main_modules", [])
        if "Loyalty & Rewards" not in mods:
            mods.append("Loyalty & Rewards")
        tables = doc.setdefault("database_design", {}).setdefault("tables", [])
        if not any(t["table_name"] == "loyalty_accounts" for t in tables):
            tables.append({
                "table_name": "loyalty_accounts", "description": "Customer loyalty points balance.",
                "fields": [
                    {"name": "id", "type": "uuid", "primary_key": True},
                    {"name": "user_id", "type": "foreign_key", "references": "users.id"},
                    {"name": "points_balance", "type": "integer", "default": 0},
                    {"name": "tier", "type": "enum", "values": ["bronze", "silver", "gold"], "default": "bronze"},
                ],
            })
        doc.setdefault("functional_requirements", []).append({
            "id": _next_id(doc.get("functional_requirements", []), "FR"),
            "module": "Loyalty & Rewards",
            "requirement": "The system shall award and redeem loyalty points and assign membership tiers.",
            "priority": "medium",
        })
        diff.append("Added loyalty programme (module, table, requirement).")

    # ── generic add feature/requirement/module ───────────────
    if not diff:
        m3 = re.search(r"add\s+(?:a\s+|an\s+)?(.+?)(?:\s+(?:feature|module|requirement|support))?$", p)
        label = (m3.group(1).strip() if m3 else prompt.strip())[:80]
        module = label.title()
        mods = doc.setdefault("main_modules", [])
        if module not in mods:
            mods.append(module)
        doc.setdefault("functional_requirements", []).append({
            "id": _next_id(doc.get("functional_requirements", []), "FR"),
            "module": module,
            "requirement": f"The system shall provide {label}.",
            "priority": "medium",
        })
        diff.append(f"Added requirement & module for: {label}.")

    return {"srs_document": doc}, diff


async def customize_node(state: AgentState) -> AgentState:
    pid = state["project_id"]
    prompt = state.get("customization_prompt", "")
    srs = state.get("srs", {})
    await bus.log(pid, "CustomizationAgent", f"Applying edit: “{prompt}”", progress=15)

    new_srs, diff = None, []
    try:
        llm = get_llm()
        data = await llm.complete_json(
            system=_SYS,
            user=f"CURRENT SRS:\n{json.dumps(srs)[:9000]}\n\nUSER EDIT REQUEST:\n{prompt}",
            validator=lambda d: validate_srs({"srs_document": d.get("srs_document", {})}),
            label="srs_customize", trace_sink=lambda pl: bus.trace(pid, pl),
        )
        new_srs = {"srs_document": data["srs_document"]}
        diff = data.get("diff_summary") or ["Applied requested edit via LLM."]
        new_srs["srs_document"].setdefault("diagrams", srs.get("srs_document", {}).get("diagrams", []))
        await bus.emit(pid, "CustomizationAgent", "LLM applied edit and validated.", level="success", progress=45)
    except (LLMUnavailable, LLMRepairFailed) as exc:
        await bus.emit(pid, "CustomizationAgent",
                       "Using deterministic customizer." if isinstance(exc, LLMUnavailable)
                       else "LLM edit failed validation; using deterministic customizer.",
                       level="warn", progress=45)
        new_srs, diff = apply_customization(srs, prompt)
    except Exception as exc:  # noqa: BLE001
        await bus.error(pid, "CustomizationAgent", f"Customization error: {exc}; using deterministic editor.")
        new_srs, diff = apply_customization(srs, prompt)

    await bus.emit(pid, "CustomizationAgent", f"Edit applied: {len(diff)} change(s).",
                   level="success", progress=55, data={"diff": diff})
    return {**state, "srs": new_srs, "diff_summary": diff}
