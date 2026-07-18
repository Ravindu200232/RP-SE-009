"""Canonical, lossless product context shared by every post-architecture agent."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agents import llm

CONTEXT_VERSION = "product-context/v1"
CONTEXT_FILE = ".locode/product-context.json"
OUTPUT_RESERVE_TOKENS = 4_096


class ProductContextError(RuntimeError):
    pass


def _stable(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def context_hash(value: dict) -> str:
    payload = {k: v for k, v in value.items() if k != "contextHash"}
    return hashlib.sha256(_stable(payload).encode("utf-8")).hexdigest()


def build_product_context(spec: dict, *, design_plan: dict | None = None,
                          quality_contract: dict | None = None,
                          component_inventory: list[str] | None = None) -> dict:
    """Create the complete product memory. No product field is summarized or sliced."""
    from agents import quality
    from agents.component_registry import component_export_map, installed_components
    from agents.design import planner as design_planner

    contract = quality_contract or quality.build_contract(spec)
    design = design_plan or design_planner.plan(spec)
    components = component_inventory
    if components is None:
        components = [str(c.get("name")) for c in (spec.get("component_contracts") or [])
                      if isinstance(c, dict) and c.get("name")]
    value = {
        "version": CONTEXT_VERSION,
        "rawInput": str(spec.get("_raw_idea") or spec.get("raw_input") or ""),
        "normalizedSpec": spec,
        "designPlan": design,
        "generationPlan": spec.get("generation_plan") or {"components": [], "dependencyWaves": []},
        "routeApiFieldContract": contract,
        "declaredComponents": components,
        "availableShadcnComponents": installed_components(),
        "uiExportMap": component_export_map(),
    }
    value["contextHash"] = context_hash(value)
    return value


def estimate_tokens(text: str) -> int:
    """Conservative preflight estimate for mixed JSON, prose, and source code."""
    return max(1, (len(text.encode("utf-8")) + 2) // 3)


def ensure_fits(text: str, *, output_tokens: int = OUTPUT_RESERVE_TOKENS,
                context_tokens: int | None = None, model_label: str = "Gemma") -> None:
    limit = int(context_tokens or llm.BASE_OPTS["num_ctx"])
    estimate = estimate_tokens(text)
    if estimate + int(output_tokens) > limit:
        raise ProductContextError(
            f"Full product context needs approximately {estimate:,} input tokens plus "
            f"{output_tokens:,} output tokens, exceeding {model_label}'s configured "
            f"{limit:,}-token window. "
            "Reduce the input/project inventory; Locode will not silently truncate product context."
        )


def prompt_block(context_or_spec: dict, *, output_tokens: int = OUTPUT_RESERVE_TOKENS) -> str:
    context = (context_or_spec if context_or_spec.get("version") == CONTEXT_VERSION
               else build_product_context(context_or_spec))
    text = json.dumps(context, ensure_ascii=False, indent=2, default=str)
    block = (
        "FULL PRODUCT CONTEXT — authoritative and lossless. Use exact routes, roles, fields, design, "
        "functions, and component names; never invent replacements.\n"
        f"<product_context version=\"{CONTEXT_VERSION}\" hash=\"{context['contextHash']}\">\n"
        f"{text}\n</product_context>\n\n"
    )
    ensure_fits(block, output_tokens=output_tokens)
    return block


def write_product_context(project_dir: str | Path, context: dict) -> Path:
    path = Path(project_dir) / CONTEXT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(context, ensure_ascii=False, indent=2, default=str) + "\n",
                    encoding="utf-8")
    return path


def load_product_context(project_dir: str | Path, *, required: bool = True) -> dict:
    path = Path(project_dir) / CONTEXT_FILE
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if required:
            raise ProductContextError(
                "This project predates product-context/v1. It remains runnable, but cannot be updated "
                "with Locode's full-context guarantee; regenerate it from the original input."
            ) from exc
        return {}
    if value.get("version") != CONTEXT_VERSION or value.get("contextHash") != context_hash(value):
        raise ProductContextError("The persisted product context is missing, unsupported, or corrupted")
    return value
