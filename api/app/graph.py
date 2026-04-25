from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from .llm import build_llm, llm_invoke, strip_code_fence
from .prompts import (
    COMPONENT_SPECS,
    COMPONENT_SYSTEM_PROMPT,
    PAGE_SYSTEM_PROMPT,
    PAGE_TEMPLATES,
    STYLE_VARIANTS,
    component_user_prompt,
    page_user_prompt,
)


class BuildState(TypedDict, total=False):
    srs_json: dict[str, Any]
    srs_str: str
    project_name: str
    model: str
    output_dir: str
    files: list[dict[str, str]]
    logs: list[str]
    on_log: Any


def _log(state: BuildState, message: str) -> None:
    state.setdefault("logs", []).append(message)
    cb = state.get("on_log")
    if callable(cb):
        try:
            cb(message)
        except Exception:
            pass


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", value or "").strip().title().replace(" ", "")
    return cleaned or "App"


def node_ingest(state: BuildState) -> BuildState:
    srs = state.get("srs_json", {}) or {}
    project = (
        srs.get("project_name")
        or srs.get("name")
        or (srs.get("metadata") or {}).get("project")
        or "GeneratedApp"
    )
    state["project_name"] = _safe_name(str(project))
    state["srs_str"] = json.dumps(srs, indent=2, ensure_ascii=False)
    state.setdefault("files", [])
    _log(state, f"Ingested SRS for project '{state['project_name']}'.")
    return state


def node_plan(state: BuildState) -> BuildState:
    total = len(STYLE_VARIANTS) * len(COMPONENT_SPECS) + len(PAGE_TEMPLATES) * len(STYLE_VARIANTS)
    _log(state, f"Planned {total} generation tasks (4 categories × 5 styles + 5 pages × 5 styles).")
    return state


def _generate_component_category(category: str) -> Callable[[BuildState], BuildState]:
    def _node(state: BuildState) -> BuildState:
        spec = COMPONENT_SPECS[category]
        llm = build_llm(model=state.get("model"))
        for index, variant in enumerate(STYLE_VARIANTS, start=1):
            comp_name = f"{spec['label'].replace(' ', '')}{index}"
            prompt = component_user_prompt(category, variant, state["srs_str"], comp_name)
            try:
                raw = llm_invoke(
                    llm,
                    [
                        ("system", COMPONENT_SYSTEM_PROMPT),
                        ("human", prompt),
                    ],
                )
                code = strip_code_fence(raw)
            except Exception as exc:
                code = _fallback_component(comp_name, category, variant, state)
                _log(state, f"[warn] {comp_name}: LLM error ({exc}); used fallback.")
            file_path = f"frontend/components/{category}s/{comp_name}.jsx"
            state["files"].append({"path": file_path, "content": code, "category": category, "style": variant["id"]})
            _log(state, f"Generated {category} variant {index}/5 ({variant['label']}) → {file_path}")
        return state

    _node.__name__ = f"node_generate_{category}"
    return _node


def node_generate_pages(state: BuildState) -> BuildState:
    llm = build_llm(model=state.get("model"))
    for page in PAGE_TEMPLATES:
        for index, variant in enumerate(STYLE_VARIANTS, start=1):
            page_name = f"{page['name']}{index}"
            prompt = page_user_prompt({**page, "name": page_name}, variant, state["srs_str"])
            try:
                raw = llm_invoke(
                    llm,
                    [
                        ("system", PAGE_SYSTEM_PROMPT),
                        ("human", prompt),
                    ],
                )
                code = strip_code_fence(raw)
            except Exception as exc:
                code = _fallback_page(page_name, page, variant, state)
                _log(state, f"[warn] {page_name}: LLM error ({exc}); used fallback.")
            file_path = f"frontend/pages/{page['id']}/{page_name}.jsx"
            state["files"].append({"path": file_path, "content": code, "category": "page", "style": variant["id"]})
            _log(state, f"Generated page {page['name']} variant {index}/5 ({variant['label']}) → {file_path}")
    return state


def node_package(state: BuildState) -> BuildState:
    output_dir = Path(state["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    for file in state["files"]:
        target = output_dir / file["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file["content"], encoding="utf-8")
    manifest = {
        "project_name": state["project_name"],
        "model": state.get("model"),
        "files": [{"path": f["path"], "category": f.get("category"), "style": f.get("style")} for f in state["files"]],
        "logs": state.get("logs", []),
    }
    (output_dir / "build.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _log(state, f"Packaged {len(state['files'])} files at {output_dir}.")
    return state


def _fallback_component(name: str, category: str, variant: dict, state: BuildState) -> str:
    project = state.get("project_name", "GeneratedApp")
    label = COMPONENT_SPECS[category]["label"]
    return f"""import React from "react";

export default function {name}() {{
  return (
    <div className="p-4 border border-gray-200 rounded-lg bg-white">
      <p className="text-sm font-semibold text-gray-900">{project} {label} — {variant['label']}</p>
      <p className="text-xs text-gray-500 mt-1">Fallback render. LLM unavailable.</p>
    </div>
  );
}}
"""


def _fallback_page(name: str, page: dict, variant: dict, state: BuildState) -> str:
    project = state.get("project_name", "GeneratedApp")
    return f"""import React from "react";

export default function {name}() {{
  return (
    <main className="min-h-screen p-8 bg-gray-50">
      <h1 className="text-2xl font-bold text-gray-900">{project} — {page['name']}</h1>
      <p className="text-sm text-gray-600 mt-2">Style: {variant['label']}. Fallback render.</p>
    </main>
  );
}}
"""


def build_graph():
    graph = StateGraph(BuildState)
    graph.add_node("ingest", node_ingest)
    graph.add_node("plan", node_plan)
    graph.add_node("gen_header", _generate_component_category("header"))
    graph.add_node("gen_footer", _generate_component_category("footer"))
    graph.add_node("gen_nav", _generate_component_category("nav"))
    graph.add_node("gen_card", _generate_component_category("card"))
    graph.add_node("gen_pages", node_generate_pages)
    graph.add_node("package", node_package)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "plan")
    graph.add_edge("plan", "gen_header")
    graph.add_edge("gen_header", "gen_footer")
    graph.add_edge("gen_footer", "gen_nav")
    graph.add_edge("gen_nav", "gen_card")
    graph.add_edge("gen_card", "gen_pages")
    graph.add_edge("gen_pages", "package")
    graph.add_edge("package", END)
    return graph.compile()


def run_build(srs_json: dict, output_dir: str, model: str | None = None, on_log=None) -> BuildState:
    app = build_graph()
    initial: BuildState = {
        "srs_json": srs_json,
        "model": model,
        "output_dir": output_dir,
        "files": [],
        "logs": [],
        "on_log": on_log,
    }
    return app.invoke(initial)
