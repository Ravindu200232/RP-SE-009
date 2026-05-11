"""LangGraph workflows for Agent 3.

Three graphs:
 - scan_graph        : discover → analyze (read-only preview, no files written)
 - generation_graph  : discover → analyze → generate (writes Jest tests)
 - execution_graph   : install → run → aggregate (runs Jest)

State is a plain dict so the FastAPI layer can persist it directly.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from . import analyzer, generator, runner
from .models import (
    DiscoveredFile,
    FileResult,
    GeneratedTest,
    JestSummary,
    ServiceInfo,
)


# ── Generation / Scan state ─────────────────────────────────────────────────
class GenState(TypedDict, total=False):
    source_path: str
    overwrite: bool
    services: list[Path]
    service_kinds: dict[str, str]      # service path -> "cjs"/"esm"
    discovered: list[DiscoveredFile]
    parsed: list[dict[str, Any]]       # service_root, source_path, functions, source_text, kind
    service_infos: list[ServiceInfo]
    generated: list[GeneratedTest]
    logs: list[str]
    used_llm: bool
    error: str


# ── Generation nodes ────────────────────────────────────────────────────────
def n_discover(state: GenState) -> GenState:
    logs = state.get("logs", [])
    root = Path(state["source_path"]).expanduser().resolve()
    if not root.exists():
        return {**state, "error": f"path does not exist: {root}", "logs": logs + [f"path missing: {root}"]}

    services = analyzer.discover_services(root)
    if not services:
        return {
            **state,
            "error": "no Node services found (no package.json with source code)",
            "services": [],
            "logs": logs + ["no node services found - did you point at a folder with source?"],
        }

    service_kinds: dict[str, str] = {}
    discovered: list[DiscoveredFile] = []
    for svc in services:
        kind = analyzer.classify_service(svc)
        service_kinds[str(svc)] = kind
        files = analyzer.discover_source_files(svc)
        discovered.extend(files)
        logs.append(f"discovered {len(files)} {kind.upper()} source file(s) in {svc.name}")

    return {**state, "services": services, "service_kinds": service_kinds, "discovered": discovered, "logs": logs}


def n_analyze(state: GenState) -> GenState:
    if state.get("error"):
        return state
    logs = state.get("logs", [])
    parsed: list[dict[str, Any]] = []
    services_by_path = {str(s): s for s in state.get("services", [])}
    service_kinds = state.get("service_kinds", {})

    # group functions by service for stats
    functions_per_service: dict[str, int] = {}
    for df in state.get("discovered", []):
        try:
            text = Path(df.path).read_text(encoding="utf-8")
        except OSError as exc:
            logs.append(f"could not read {df.relative}: {exc}")
            continue
        # find which service owns this file
        owner = None
        for svc_path, svc in services_by_path.items():
            try:
                Path(df.path).relative_to(svc)
                owner = svc
                break
            except ValueError:
                continue
        if owner is None:
            continue
        kind = service_kinds.get(str(owner), "cjs")
        functions = analyzer.parse_functions(text, kind=kind)
        functions_per_service[owner.name] = functions_per_service.get(owner.name, 0) + len(functions)
        parsed.append(
            {
                "service": owner,
                "source_path": Path(df.path),
                "functions": functions,
                "source_text": text,
                "relative": df.relative,
                "kind": kind,
            }
        )

    # Build ServiceInfo summary list for the scan response
    service_infos: list[ServiceInfo] = []
    for svc in state.get("services", []):
        files_in_svc = [df for df in state.get("discovered", []) if df.service == svc.name]
        kind = service_kinds.get(str(svc), "cjs")
        pkg = analyzer._read_pkg(svc)
        deps = pkg.get("dependencies", {}) if isinstance(pkg, dict) else {}
        framework_hint = None
        for cand in ("express", "fastify", "@nestjs/core", "koa", "@hapi/hapi"):
            if cand in deps:
                framework_hint = cand
                break
        service_infos.append(
            ServiceInfo(
                name=svc.name,
                path=str(svc),
                module_kind=kind,
                file_count=len(files_in_svc),
                function_count=functions_per_service.get(svc.name, 0),
                has_dependencies=(svc / "node_modules").is_dir(),
                framework_hint=framework_hint,
            )
        )

    total_fns = sum(s.function_count for s in service_infos)
    logs.append(f"analyzed {len(parsed)} files; total exported functions = {total_fns}")
    return {**state, "parsed": parsed, "service_infos": service_infos, "logs": logs}


def n_generate(state: GenState) -> GenState:
    if state.get("error"):
        return state
    logs = state.get("logs", [])
    overwrite = state.get("overwrite", False)
    generated: list[GeneratedTest] = []
    used_llm_overall = False

    for entry in state.get("parsed", []):
        service: Path = entry["service"]
        source_path: Path = entry["source_path"]
        functions = entry["functions"]
        source_text = entry["source_text"]
        kind = entry.get("kind", "cjs")
        if not functions:
            continue

        code, used_llm = generator.generate_test_for_module(
            source_path=source_path,
            service_root=service,
            functions=functions,
            source=source_text,
            module_kind=kind,
        )
        used_llm_overall = used_llm_overall or used_llm

        tests_dir = service / "__tests__"
        tests_dir.mkdir(parents=True, exist_ok=True)
        suffix = ".test.mjs" if kind == "esm" else ".test.js"
        test_file = tests_dir / f"{source_path.stem}{suffix}"

        if test_file.exists() and not overwrite:
            backup = test_file.with_suffix(".prev.js")
            try:
                backup.write_text(test_file.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass
        test_file.write_text(code, encoding="utf-8")

        test_count = code.count("it(") + code.count("test(")
        generated.append(
            GeneratedTest(
                source_file=str(source_path),
                test_file=str(test_file),
                function_count=len(functions),
                test_count=test_count,
                used_llm=used_llm,
                preview="\n".join(code.splitlines()[:25]),
            )
        )
        logs.append(
            f"wrote {test_file.relative_to(service.parent)} "
            f"({test_count} tests, llm={used_llm})"
        )
    return {**state, "generated": generated, "logs": logs, "used_llm": used_llm_overall}


def build_generation_graph():
    g = StateGraph(GenState)
    g.add_node("discover", n_discover)
    g.add_node("analyze", n_analyze)
    g.add_node("generate", n_generate)
    g.add_edge(START, "discover")
    g.add_edge("discover", "analyze")
    g.add_edge("analyze", "generate")
    g.add_edge("generate", END)
    return g.compile()


def build_scan_graph():
    """Discovery + analysis only, no file writes - used to power the Scan preview."""
    g = StateGraph(GenState)
    g.add_node("discover", n_discover)
    g.add_node("analyze", n_analyze)
    g.add_edge(START, "discover")
    g.add_edge("discover", "analyze")
    g.add_edge("analyze", END)
    return g.compile()


# ── Execution state ─────────────────────────────────────────────────────────
class RunState(TypedDict, total=False):
    source_path: str
    install: bool
    services: list[Path]
    service_kinds: dict[str, str]
    file_results: dict[str, list[FileResult]]
    summary: JestSummary
    logs: list[str]
    started: float
    error: str


def n_run_resolve(state: RunState) -> RunState:
    logs = state.get("logs", [])
    root = Path(state["source_path"]).expanduser().resolve()
    if not root.exists():
        return {**state, "error": f"path does not exist: {root}", "logs": logs + [f"path missing: {root}"]}
    services = analyzer.discover_services(root)
    if not services:
        return {**state, "error": "no Node services found", "services": [], "logs": logs + ["no node services found"]}
    kinds = {str(s): analyzer.classify_service(s) for s in services}
    logs.append(f"resolved {len(services)} service(s) to test")
    return {**state, "services": services, "service_kinds": kinds, "logs": logs, "started": time.time()}


def n_install_and_run(state: RunState) -> RunState:
    if state.get("error"):
        return state
    logs = state.get("logs", [])
    install = state.get("install", True)
    file_results: dict[str, list[FileResult]] = {}
    kinds = state.get("service_kinds", {})

    for svc in state.get("services", []):
        ok = runner.ensure_dependencies(svc, install=install, log=logs)
        if not ok:
            file_results[svc.name] = []
            continue
        kind = kinds.get(str(svc), "cjs")
        _, files, _payload = runner.run_jest(svc, log=logs, module_kind=kind)
        file_results[svc.name] = files

    return {**state, "file_results": file_results, "logs": logs}


def n_aggregate(state: RunState) -> RunState:
    if state.get("error"):
        return state
    duration = (time.time() - state.get("started", time.time())) * 1000.0
    summary = runner.aggregate(state.get("file_results", {}), duration)
    return {**state, "summary": summary}


def build_execution_graph():
    g = StateGraph(RunState)
    g.add_node("resolve", n_run_resolve)
    g.add_node("install_and_run", n_install_and_run)
    g.add_node("aggregate", n_aggregate)
    g.add_edge(START, "resolve")
    g.add_edge("resolve", "install_and_run")
    g.add_edge("install_and_run", "aggregate")
    g.add_edge("aggregate", END)
    return g.compile()
