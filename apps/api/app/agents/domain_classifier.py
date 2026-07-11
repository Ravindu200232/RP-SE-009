"""DomainClassifierAgent — detect domain, app type, and confidence.

Uses the deterministic keyword classifier as a prior and (when Ollama is up)
asks the model to refine the label, app type, and confidence. Also derives the
complexity estimate and suggested stack shown in the analyzer inspector.
"""
from __future__ import annotations

import json

from ..knowledge.domains import DOMAIN_LIBRARY, classify_domain, get_domain
from ..llm import LLMUnavailable, get_llm
from ..services.events import bus
from .state import AgentState

_SYS = (
    "You are a software domain classifier. Given a product idea, identify the "
    "business domain and application type. Respond with ONLY JSON: "
    '{"domain_key": one of %s, "detected_domain": short label, '
    '"app_type": e.g. "SPA"|"POS"|"admin dashboard"|"customer portal"|"PWA"|"hybrid", '
    '"confidence": 0..1, "reasoning": one sentence}.'
)


def _complexity(domain_key: str, brief: str) -> dict:
    dom = get_domain(domain_key)
    n_tables = len(dom["tables"])
    n_modules = len(dom["modules"])
    score = n_tables + n_modules + len(brief) // 400
    if score >= 18:
        overall, backend = "High", "High"
    elif score >= 12:
        overall, backend = "Medium-High", "High"
    else:
        overall, backend = "Medium", "Medium"
    return {"overall": overall, "backend": backend, "frontend": "Medium"}


def _stack(domain_key: str) -> dict:
    arch = "Microservices" if domain_key in ("retail", "vehicle", "hotel") else "Modular Monolith"
    return {
        "frontend": "React + Tailwind",
        "backend": "Express / Node",
        "database": "MongoDB",
        "architecture": arch,
        "locked": True,
    }


async def classify_node(state: AgentState) -> AgentState:
    pid = state["project_id"]
    brief = state.get("brief", "")
    await bus.log(pid, "DomainClassifierAgent", "Identifying domain patterns…", progress=40)

    key, conf, label = classify_domain(brief)
    classification = {
        "domain_key": key,
        "detected_domain": label,
        "app_type": get_domain(key)["app_type_primary"],
        "confidence": conf,
        "similar_patterns": sum(1 for d in DOMAIN_LIBRARY if d == key) + (2 if key != "custom" else 0),
        "reasoning": f"Matched {label} by keyword evidence in the brief.",
    }

    # Refine with the LLM when available (non-fatal).
    try:
        llm = get_llm()
        data = await llm.complete_json(
            system=_SYS % json.dumps(list(DOMAIN_LIBRARY.keys()) + ["custom"]),
            user=f"Product idea:\n{brief[:2500]}",
            label="domain_classify",
            trace_sink=lambda p: bus.trace(pid, p),
        )
        dk = data.get("domain_key")
        if dk in DOMAIN_LIBRARY or dk == "custom":
            classification["domain_key"] = dk
            classification["detected_domain"] = data.get("detected_domain") or DOMAIN_LIBRARY.get(dk, {}).get("label", label)
            classification["app_type"] = data.get("app_type") or classification["app_type"]
            classification["confidence"] = float(data.get("confidence", conf))
            classification["reasoning"] = data.get("reasoning") or classification["reasoning"]
            await bus.emit(pid, "DomainClassifierAgent", f"LLM refined domain → {classification['detected_domain']}", progress=55)
    except LLMUnavailable:
        await bus.emit(pid, "DomainClassifierAgent", "Ollama offline; using deterministic classification.", level="warn", progress=55)
    except Exception as exc:  # noqa: BLE001
        await bus.emit(pid, "DomainClassifierAgent", f"Classifier refine skipped: {exc}", level="warn")

    key = classification["domain_key"]
    await bus.emit(
        pid, "DomainClassifierAgent",
        f"Detected {classification['detected_domain']} (confidence {classification['confidence']:.0%})",
        level="success", progress=60, data={"classification": classification},
    )

    return {
        **state,
        "classification": classification,
        "project": {
            **state.get("project", {}),
            "complexity": _complexity(key, brief),
            "suggested_stack": _stack(key),
        },
    }
