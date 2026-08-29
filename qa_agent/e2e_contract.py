"""Machine-readable proof contract for each browser journey."""
from __future__ import annotations

import re


_MUTATION_WORDS = re.compile(
    r"\b(create|add|book|reserve|pay|update|save|cancel|delete|remove|approve|reject|submit|send|apply|change|mark)\b",
    re.I,
)


def _clean_list(values, cap=16):
    out = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= cap:
            break
    return out


def capability_contract(arch, journey: dict) -> dict:
    """Compile workflow/capability/contract facts into one proof ledger."""
    plan = getattr(arch, "plan", None) or {}
    covers = {str(x or "").upper() for x in (journey.get("covers") or []) if str(x or "").strip()}
    caps = [c for c in (plan.get("capabilities") or [])
            if isinstance(c, dict) and (not covers or str(c.get("id") or "").upper() in covers)]

    proofs, files, requirements = [], [], []
    for cap in caps:
        requirements.extend([cap.get("requirement")])
        proofs.extend([cap.get("proof")])
        files.extend(cap.get("files") or [])

    handoffs = []
    for item in (plan.get("contracts") or []):
        if not isinstance(item, dict):
            continue
        frm = str(item.get("from") or "").strip()
        target = str(item.get("target") or "").strip()
        if files and frm not in files and not any(f and f in target for f in files):
            continue
        effect = str(item.get("effect") or "").strip()
        trigger = str(item.get("trigger") or "").strip()
        if trigger or effect:
            handoffs.append({"from": frm, "target": target,
                             "trigger": trigger, "effect": effect})

    steps = _clean_list(journey.get("steps") or [], 20)
    text = " ".join(steps + _clean_list(requirements) + _clean_list(proofs))
    role = str(journey.get("role") or "").strip().lower()
    return {
        "title": str(journey.get("title") or "").strip(),
        "actor": role or "signed-out",
        "requires_session": bool(role and role not in {"visitor", "public", "anonymous", "signed out"}),
        "workflow_steps": steps,
        "requirements": _clean_list(requirements),
        "proofs": _clean_list(proofs),
        "source_files": _clean_list(files),
        "handoffs": handoffs[:10],
        "expects_mutation": bool(_MUTATION_WORDS.search(text)),
        "preserve_auth": not bool(re.search(r"\b(login|log in|sign in|authenticate|session|role)\b", text, re.I)),
    }


def scenario_contract_issue(contract: dict, scenario, is_business_step) -> str:
    """Reject a scenario that cannot prove the contract even if selectors parse."""
    if not contract:
        return ""
    expected_role = str(contract.get("actor") or "").strip().lower()
    actual_role = str(getattr(scenario, "role", "") or "signed-out").strip().lower()
    if expected_role and expected_role != "signed-out" and actual_role != expected_role:
        return f"scenario role {actual_role!r} does not match required actor {expected_role!r}"

    steps = list(getattr(scenario, "steps", []) or [])
    if not contract.get("expects_mutation"):
        return ""
    business = [i for i, step in enumerate(steps) if is_business_step(step)]
    if not business:
        return "the capability contract requires a business mutation, but the scenario never performs one"
    first = business[0]
    proof_verbs = {"EXPECT_TEXT", "EXPECT_URL", "EXPECT_VALUE", "WAIT_FOR", "EXPECT_NO_ERROR"}
    if not any(getattr(step, "verb", "") in proof_verbs for step in steps[first + 1:]):
        return "the scenario performs a business action but never proves its resulting state"
    return ""


def runtime_contract_issue(contract: dict, scenario, evidence: dict,
                           is_business_step) -> str:
    """Require an observed persisted effect for contracts that mutate data."""
    if not contract or not contract.get("expects_mutation"):
        return ""
    steps = list(getattr(scenario, "steps", []) or [])
    business = [i for i, step in enumerate(steps) if is_business_step(step)]
    if not business:
        return "the contract requires a mutation but the scenario has no business action"
    first = business[0]
    mutations = []
    for row in (evidence or {}).get("mutation_events") or []:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "")
        if "/api/auth/" in url:
            continue
        try:
            idx = int(row.get("step_index", -1))
        except Exception:
            idx = -1
        if idx >= first and int(row.get("status") or 0) < 300:
            mutations.append(row)
    if not mutations:
        return ("the capability contract requires a persisted business change, "
                "but the browser observed no successful non-auth mutation request")
    return ""
