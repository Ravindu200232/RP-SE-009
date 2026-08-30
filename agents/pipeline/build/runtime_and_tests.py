# Runtime/test flow: unit evidence -> smoke repair -> runtime/API -> E2E.
# Runs the served-app checks and return the evidence needed by final quality gates.
def run_runtime_and_qa(arch, proj_dir, qa, analyzer, *, db_ok, build_ok, drawing):
    """Run the served-app checks and return the evidence needed by final quality gates."""
    # Stage 5: run focused tests, then repair only observed failures.
    unit_out, e2e_out, runtime_errors = {}, {}, []
    # From: agents/analysis/analysis_shared.py
    runtime_report, api_report = AnalyzerReport(), AnalyzerReport()
    runtime_clean, api_clean = False, False
    try:
        unit = run_qa_unit_stage(arch, proj_dir, qa, build_ok=build_ok)
        unit_out = unit or {}
    except Exception as e:
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ Unit test stage failed: {e}")
        log.exception("qa unit stage")

    # Unit repair/revert can expose a shared Server/Client boundary late.
    # Batch every proven owner through Analyzer's full-file fixer before serve.
    try:
        for boundary_round in (1, 2):
            # From: agents/analysis/checks/code_checks.py
            boundary = analyzer.server_client_boundary_findings()
            if not boundary:
                break
            # From: agents/build/tester_common.py
            elog("INFO", f"   🧱 pre-runtime boundary repair {boundary_round}: "
                         f"{len(boundary)} proven source file(s)")
            # From: agents/analysis/analysis_shared.py
            # From: agents/analysis/repair/repair_runner.py
            if not analyzer.repair(AnalyzerReport(findings=boundary)):
                break
        # From: agents/analysis/checks/code_checks.py
        if analyzer.server_client_boundary_findings():
            # From: agents/build/tester_common.py
            elog("WARN", "   ⚠ Server/Client boundary blockers remain for runtime evidence")
    except Exception as e:
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ pre-runtime boundary scan failed: {e}")

    # Pictures keep drawing while the app is served and tested. Blocking here
    # cost the whole run the length of the image queue — one GPU image is
    # about a minute, so an eight-image plan stalled build, unit tests and
    # every browser check for eight minutes to avoid a placeholder in a
    # screenshot. A late picture is a cosmetic gap; a skipped test is not.
    if drawing.get("thread") and drawing["thread"].is_alive():
        # From: agents/build/tester_common.py
        elog("INFO", "   🖼 images keep drawing in the background — serving "
                     "and testing continue now")

    estep("serve", "active")
    eprog("Starting Next.js…", 90)
    # One last chance: a database that arrived late still counts.
    # From: agents/pipeline/build_pipeline.py
    db_ok = db_ok or database_ready()
    start_next(proj_dir)
    wait_for_next()
    # From: agents/pipeline/build_pipeline.py
    seed_error = seed_project(arch.plan) if db_ok else ""
    if not seed_error:
        # From: agents/pipeline/build_pipeline.py
        write_auth_details(proj_dir, arch.plan, verified=True, arch=arch)

    estep("test", "active")
    emit({"type": "test_start"})
    # From: agents/build/tester_browser.py
    tester = TesterAgent(proj_dir, DEV_PORT, stack="next", smoke_only=True)

    runtime_deadline = time.time() + RUNTIME_DEADLINE
    prev_evidence_sig = None
    previous_fixed = ()
    smoke_repaired = False

    for attempt in range(1, MAX_FIX + 2):
        emit({"type": "test_run", "attempt": attempt})

        mark = dev_log_mark()
        # From: agents/build/tester_common.py
        errors = tester.test()

        # From: agents/pipeline/build/runtime_faults.py
        faults = terminal_faults(_filter_db_noise(dev_log_since(mark), db_ok))
        for f in faults:
            if not any(f[:60] in e for e in errors):
                errors.append(f"Dev server error: {f}")
                emit({"type": "test_result", "status": "fail",
                      "msg": "Dev server error", "detail": f[:160]})
                # From: agents/build/tester_common.py
                elog("WARN", f"   ❌ terminal: {f[:110]}")

        # The database can die after Stage 2 said it was up. That is an
        # infrastructure fault, and handing it to the repair agent spends a
        # round rewriting application code that is not wrong. Restart the
        # server and re-read the app before anyone touches a file.
        # From: agents/pipeline/build/runtime_faults.py
        if db_ok and database_fault(errors):
            # From: agents/build/tester_common.py
            elog("WARN", "   🍃 the database stopped answering mid-run — "
                         "restarting it before blaming the app")
            # From: agents/pipeline/build/runtime_faults.py
            db_ok = recover_database()
            if db_ok:
                continue
            errors = [e for e in errors
                      if not any(m in e for m in _DB_ERROR_MARKERS)]

        if not db_ok:
            errors = [e for e in errors
                      if not any(m in e for m in _DB_ERROR_MARKERS)]

        if not errors and not seed_error:

            # From: agents/build/tester_common.py
            elog("INFO", "   🎉 Tests passed — no errors")
            estep("test", "done")
            break

        if time.time() > runtime_deadline:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ the {RUNTIME_DEADLINE}s runtime-repair "
                         f"budget is spent with {len(errors)} error(s) left")
            _report_unfixed(errors)
            estep("test", "done")
            break

        if attempt > MAX_FIX:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ Reached {MAX_FIX} fix attempts with "
                         f"{len(errors)} error(s) still unfixed")
            _report_unfixed(errors)
            estep("test", "done")
            break

        # From: agents/pipeline/build/runtime_faults.py
        dev_errors = _filter_db_noise(dev_log_since(mark), db_ok)
        if not dev_errors.strip():
            # From: agents/pipeline/build/runtime_faults.py
            dev_errors = _filter_db_noise(next_stderr(), db_ok)
        all_errors = "\n".join(errors[:8]) + "\n" + dev_errors
        if seed_error:
            all_errors += "\n\nSeed endpoint evidence:\n" + seed_error

        if getattr(tester, "mcp_report", ""):
            all_errors = tester.mcp_report + "\n\n" + all_errors

        guidance = nextdocs.guidance_for(all_errors)
        if guidance:
            all_errors += "\n" + guidance

        emit({"type": "test_fixing", "attempt": attempt, "errors": errors[:5]})
        # From: agents/build/tester_common.py
        elog("INFO", f"   🔧 Agent fixing (attempt {attempt}/{MAX_FIX})…")
        ephase({"phase": -2, "title": f"Fixing errors (try {attempt})",
                "status": "active"})

        runtime_focus = _exact_runtime_focus(arch, all_errors)
        if seed_error:
            seed_focus = [p for p in ("lib/seed.js", "lib/auth.js") if p in arch.files]
            runtime_focus = list(dict.fromkeys(runtime_focus + seed_focus))
        sig_rows = {e.splitlines()[0][:120] for e in errors}
        if seed_error:
            sig_rows.add(seed_error[:120])
        evidence_sig = (frozenset(sig_rows), tuple(runtime_focus), tuple(previous_fixed))
        if prev_evidence_sig == evidence_sig:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ attempt {attempt - 1} repeated the same errors, "
                         "source evidence and edited files — stopping true repetition")
            _report_unfixed(errors); estep("test", "done"); break
        prev_evidence_sig = evidence_sig
        _stop_dev_proc()
        if runtime_focus:
            # From: agents/build/tester_common.py
            elog("INFO", "   🎯 runtime evidence maps source: "
                         + ", ".join(runtime_focus[:3]))
        fixed_paths = _repair_runtime(arch, proj_dir, qa, analyzer, all_errors,
                                     dev_errors, attempt,
                                     focus_paths=runtime_focus or None,
                                     strict_scope=bool(runtime_focus),
                                     exact_scope=bool(runtime_focus))
        smoke_repaired = smoke_repaired or bool(fixed_paths)
        previous_fixed = tuple(sorted(fixed_paths or []))

        ephase({"phase": -2, "title": f"Fixing errors (try {attempt})",
                "status": "done"})
        ensure_node_deps(proj_dir)
        if fixed_paths:
            # From: agents/planner/builder/dependency_manager.py
            arch.repair_missing_imports()
            # From: agents/core/syntax/syntax_checker.py
            problems, _ = check_syntax(
                proj_dir, {p: arch.files.get(p, "") for p in fixed_paths})
            if problems:
                # From: agents/build/tester_common.py
                elog("WARN", "   ⚠ repaired source has syntax errors; the next pass will focus on them")
        start_next(proj_dir)
        wait_for_next()
        if db_ok:
            # From: agents/pipeline/build_pipeline.py
            seed_error = seed_project(arch.plan)

    if smoke_repaired:
        # From: agents/build/tester_common.py
        elog("INFO", "   🔨 runtime fixes settled — one production build")
        _stop_dev_proc()
        # From: agents/pipeline/build/build_fix_loop.py
        build_ok = bool(run_build_fix_loop(arch, proj_dir, db_ok, max_rounds=2))
        start_next(proj_dir)
        wait_for_next()

    runtime_errors = list(errors or [])
    try:
        runtime_report, runtime_clean, runtime_written = (
            run_runtime_verification_stage(
                arch, proj_dir, analyzer, db_ok=db_ok, build_ok=build_ok))
    except Exception as e:
        runtime_clean = False
        runtime_written = 0
        # From: agents/analysis/analysis_shared.py
        runtime_report = AnalyzerReport()
        # From: agents/analysis/analysis_shared.py
        runtime_report.findings.append(Finding(
            "blocker", "RUNTIME_STAGE_FAILED",
            f"runtime verification stage failed: {e}"))
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ Runtime verification stage failed: {e}")
        log.exception("runtime verification stage")

    try:
        api_report, api_clean, api_written = run_api_verification_stage(
            arch, proj_dir, analyzer, db_ok=db_ok, build_ok=build_ok)
    except Exception as e:
        api_clean = False
        api_written = 0
        # From: agents/analysis/analysis_shared.py
        api_report = AnalyzerReport()
        # From: agents/analysis/analysis_shared.py
        api_report.findings.append(Finding(
            "blocker", "API_STAGE_FAILED",
            f"API verification stage failed: {e}"))
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ API verification stage failed: {e}")
        log.exception("api verification stage")

    # Never serialize browser QA behind GPU work. Planned image paths get
    # instant PNG placeholders and the real files replace them in background.
    try:
        if drawing.get("thread") and drawing["thread"].is_alive():
            # From: agents/build/tester_common.py
            elog("INFO", "   🖼 images are still drawing — browser journeys continue immediately")
        else:
            threading.Thread(target=_fill_missing_images,
                             args=(arch, proj_dir, "the pages"),
                             daemon=True).start()
    except Exception as e:
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ Background image completion failed: {e}")

    e2e_blockers = _e2e_hard_upstream_blockers(runtime_report, api_report)

    # A journey needs a served app, not a green production build. `next
    # build` can exit non-zero on a crashed worker while every route still
    # answers 200 under `next dev`, and skipping the browser then throws
    # away the only evidence that would say what actually works.
    e2e_out = {}
    serving = _dev_alive()
    if serving and not e2e_blockers:
        if not build_ok:
            # From: agents/build/tester_common.py
            elog("WARN", "   ⚠ running the journeys against a served app "
                         "whose production build is red — a failure here "
                         "may be the build fault reappearing")
        try:
            e2e_out = run_qa_e2e_stage(arch, proj_dir, qa, analyzer,
                                       build_ok=build_ok, db_ok=db_ok) or {}
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ End-to-end stage failed: {e}")
            log.exception("qa e2e stage")
    else:
        reasons = []
        for stage, f in e2e_blockers[:6]:
            label = f"{stage}:{getattr(f, 'code', '')}"
            if label not in reasons:
                reasons.append(label)
        if not serving:
            reasons.insert(0, "app:not-serving")
        reason_text = ", ".join(reasons) or "upstream correctness gate"
        # From: agents/build/tester_common.py
        elog("WARN", "   ⛔ End-to-end journeys skipped — hard upstream "
                     "defects remain (" + reason_text + "). Fix the known "
                     "production fault before authoring browser journeys; "
                     "otherwise E2E only reports downstream symptoms.")
        e2e_out = {
            "ran": False, "flow": "", "passed": 0, "failed": 1,
            "fixed": 0, "unwritable": 0, "flows": [],
            "failures": [{"case": "upstream correctness gate",
                          "kind": "BLOCKED_UPSTREAM",
                          "message": reason_text}],
            "blocked_upstream": True,
        }

    if build_ok and int((e2e_out or {}).get("fixed") or 0) > 0:
        # From: agents/build/tester_common.py
        elog("INFO", "   🔁 confirming runtime/API health after E2E repairs")
        try:
            # From: agents/build/tester_browser.py
            fresh_tester = TesterAgent(proj_dir, DEV_PORT, stack="next", smoke_only=True)
            smoke_mark = dev_log_mark()
            # From: agents/build/tester_common.py
            fresh_errors = list(fresh_tester.test() or [])
            # From: agents/pipeline/build/runtime_faults.py
            for fault in terminal_faults(_filter_db_noise(dev_log_since(smoke_mark), db_ok)):
                if not any(fault[:60] in err for err in fresh_errors):
                    fresh_errors.append(f"Dev server error: {fault}")
            runtime_errors = fresh_errors
        except Exception as e:
            runtime_errors = [f"post-E2E smoke verification failed: {e}"]

        try:
            runtime_report, runtime_clean, _ = run_runtime_verification_stage(
                arch, proj_dir, analyzer, db_ok=db_ok, build_ok=build_ok,
                allow_repair=False)
        except Exception as e:
            runtime_clean = False
            # From: agents/analysis/analysis_shared.py
            runtime_report = AnalyzerReport()
            # From: agents/analysis/analysis_shared.py
            runtime_report.findings.append(Finding(
                "blocker", "RUNTIME_STAGE_FAILED",
                f"post-E2E runtime verification failed: {e}"))

        try:
            api_report, api_clean, _ = run_api_verification_stage(
                arch, proj_dir, analyzer, db_ok=db_ok, build_ok=build_ok,
                allow_repair=False)
        except Exception as e:
            api_clean = False
            # From: agents/analysis/analysis_shared.py
            api_report = AnalyzerReport()
            # From: agents/analysis/analysis_shared.py
            api_report.findings.append(Finding(
                "blocker", "API_STAGE_FAILED",
                f"post-E2E API verification failed: {e}"))


    return {
        "unit_out": unit_out, "e2e_out": e2e_out, "runtime_errors": runtime_errors,
        "runtime_report": runtime_report, "api_report": api_report,
        "runtime_clean": runtime_clean, "api_clean": api_clean,
        "db_ok": db_ok, "build_ok": build_ok,
    }
