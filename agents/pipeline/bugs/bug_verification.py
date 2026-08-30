

# Check syntax, imports, build, dev startup, and optional routes.
def verify_after_edit(arch, proj_dir: Path, proj_name: str, *,
                      stack: str = "next", build_rounds: int = 2,
                      probe: bool = True, analyzer=None) -> dict:
    """Check syntax, imports, build, dev startup, and optional routes."""
    out = {"build_ok": True, "routes_failed": [], "broken_imports": 0,
           "syntax_broken": []}
    # From: agents/pipeline/feature_safety.py
    analyzer = analyzer or _analyzer_for(arch, proj_dir)

    # From: agents/pipeline/bugs/bug_workflow.py
    compiling = bool(build_rounds) and not _truthy("AGENTFORGE_SKIP_BUILD_CHECK")

    if compiling:

        _stop_dev_proc()

    ensure_node_deps(proj_dir)

    # From: agents/core/syntax/syntax_checker.py
    problems, why_not = check_syntax(proj_dir, arch.files)
    if why_not:

        # From: agents/build/tester_common.py
        elog("INFO", f"   ⚠ Syntax not checked — {why_not}")
    elif problems:
        # From: agents/build/tester_common.py
        elog("WARN", f"🧩 {len(problems)} file(s) do not parse — repairing")
        ephase({"phase": -6, "title": "Fixing broken syntax", "status": "active"})
        # From: agents/analysis/analysis_shared.py
        report = AnalyzerReport()
        # From: agents/analysis/analysis_shared.py
        # From: agents/core/syntax/syntax_checker.py
        report.findings = [
            Finding(severity="blocker", code="SYNTAX_ERROR", path=p["path"],
                    message=msg)
            for p, msg in zip(problems, syntax_messages(problems))
        ]
        # From: agents/core/syntax/syntax_checker.py
        for line in syntax_messages(problems):
            # From: agents/build/tester_common.py
            elog("WARN", f"   ✗ {line}")
        try:
            # From: agents/analysis/repair/repair_runner.py
            analyzer.repair(report)
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ Syntax repair failed: {e}")
            log.exception("verify_after_edit: syntax repair")
        # From: agents/core/syntax/syntax_checker.py
        still, _ = check_syntax(proj_dir, arch.files)
        # From: agents/build/tester_common.py
        elog("INFO" if not still else "WARN",
             "   ✅ Every file parses" if not still
             else f"   ⚠ {len(still)} still unparseable")
        out["syntax_broken"] = [p["path"] for p in still]
        ephase({"phase": -6, "title": "Fixing broken syntax", "status": "done"})

    # From: agents/core/imports/import_checker.py
    broken = check_named_imports(arch.files)
    out["broken_imports"] = len(broken)
    if broken:
        # From: agents/build/tester_common.py
        elog("WARN", f"🔗 {len(broken)} import(s) name something the target "
                     f"module does not export")
        ephase({"phase": -7, "title": "Fixing broken imports", "status": "active"})
        # From: agents/analysis/analysis_shared.py
        report = AnalyzerReport()
        # From: agents/analysis/checks/code_checks.py
        report.findings = analyzer.broken_imports()
        try:
            # From: agents/analysis/repair/repair_runner.py
            analyzer.repair(report)
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ Import repair failed: {e}")
            log.exception("verify_after_edit: import repair")
        # From: agents/core/imports/import_checker.py
        still = check_named_imports(arch.files)
        out["broken_imports"] = len(still)
        # From: agents/build/tester_common.py
        elog("INFO" if not still else "WARN",
             "   ✅ Every import resolves" if not still
             else f"   ⚠ {len(still)} still unresolved")
        ephase({"phase": -7, "title": "Fixing broken imports", "status": "done"})

    if compiling:
        # From: agents/pipeline/build/build_fix_loop.py
        out["build_ok"] = run_build_fix_loop(arch, proj_dir, MONGO.available,
                                             max_rounds=build_rounds)
        if not out["build_ok"]:
            estep("build", "error")
        start_dev_server(proj_dir, stack)
    elif not _dev_alive():

        start_dev_server(proj_dir, stack)

    if not wait_for_dev(stack):
        # From: agents/build/tester_common.py
        elog("WARN", "   ⚠ Dev server did not come up — skipping the route probe")
        return out

    if probe:
        # From: agents/analysis/checks/scan_state.py
        report = analyzer.scan()
        mark = dev_log_mark()
        # From: agents/analysis/runtime/runtime_probe.py
        analyzer.probe_routes(report)

        others = [f for f in report.findings if f.code != "ROUTE_ERROR"]
        blockers = [f for f in others if f.severity == "blocker"]
        if blockers:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ {len(blockers)} blocker(s) the edit leaves behind:")
            for f in blockers[:5]:
                # From: agents/analysis/analysis_shared.py
                # From: agents/build/tester_common.py
                elog("WARN", f"      {f.line()[:150]}")
        elif others:
            # From: agents/build/tester_common.py
            elog("INFO", f"   · {len(others)} smaller finding(s) — see the "
                         f"Testing tab")

        failed = [f for f in report.findings if f.code == "ROUTE_ERROR"]
        if failed:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ❌ {len(failed)} route(s) failing — repairing")
            ephase({"phase": -8, "title": "Fixing failing routes", "status": "active"})
            report.findings = failed
            report.missing = []

            # From: agents/pipeline/build/runtime_faults.py
            trace = _filter_db_noise(dev_log_since(mark), True)
            try:
                # From: agents/analysis/repair/repair_runner.py
                analyzer.repair(report, server_log=trace)
            except Exception as e:
                # From: agents/build/tester_common.py
                elog("WARN", f"   ⚠ Route repair failed: {e}")
                log.exception("verify_after_edit: route repair")
            ephase({"phase": -8, "title": "Fixing failing routes", "status": "done"})

            _stop_dev_proc()
            ensure_node_deps(proj_dir)
            start_dev_server(proj_dir, stack)
            if wait_for_dev(stack):
                # From: agents/analysis/checks/scan_state.py
                again = analyzer.scan()
                # From: agents/analysis/runtime/runtime_probe.py
                analyzer.probe_routes(again)
                failed = [f for f in again.findings if f.code == "ROUTE_ERROR"]
        out["routes_failed"] = [f.message for f in failed]

    return out


_WATCHED_PKGS = ("agents", "qa_agent")


# Returns AgentForge source files watched while validating a self-repair.
def _own_sources():
    """Return AgentForge source files watched while validating a self-repair."""
    for pkg in _WATCHED_PKGS:
        for p in (BASE_DIR / pkg).glob("*.py"):
            if p.is_file():
                yield f"{pkg}/{p.name}", p


_AGENT_MTIMES = {rel: p.stat().st_mtime for rel, p in _own_sources()}


# Warn when loaded agent sources changed; never hot-swap modules.
def warn_if_agents_stale():
    """Warn when loaded agent sources changed; never hot-swap modules."""
    stale = []
    for rel, p in _own_sources():
        try:
            if p.stat().st_mtime > _AGENT_MTIMES.get(rel, 0) + 1:
                stale.append(rel)
        except OSError:
            continue
    if stale:
        # From: agents/build/tester_common.py
        elog("WARN", f"⚠ {', '.join(sorted(stale))} changed since this server "
                     f"started — restart AgentForge for it to take effect")
    return stale


RUN_INTENT = ".agentforge/intent.json"


# Persist the original request before planning makes resume metadata.
def save_run_intent(proj_dir: Path, **kw) -> None:
    """Persist the original request before planning makes resume metadata."""
    try:
        out = proj_dir / RUN_INTENT
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.is_file():
            return
        out.write_text(json.dumps(
            {k: v for k, v in kw.items() if v not in (None, "")},
            indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        log.debug(f"intent for {proj_dir.name}: {e}")


# Loads the saved run intent used when resuming a project repair.
def load_run_intent(proj_dir: Path) -> dict:
    """Load the saved run intent used when resuming a project repair."""
    try:
        return json.loads((proj_dir / RUN_INTENT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
