# Final quality flow: security -> delivery stabilization -> performance -> verdict.
# Close the build with quality evidence and leave the preview available.
def finish_quality_and_serve(arch, proj_dir, qa, analyzer, *, pname, db_ok, build_ok,
                             flow_report, flow_clean, flow_conclusive, unit_out, e2e_out,
                             runtime_errors, runtime_report, api_report, runtime_clean, api_clean):
    """Close the build with quality evidence and leave the preview available."""
    # Stage 6: close with security and performance evidence.
    sec_findings, sec_audit, perf_scores = [], {}, {}
    sec_ran = False
    try:
        sec_findings, sec_audit = run_security_stage(arch, proj_dir, analyzer)
        sec_ran = True
    except Exception as e:
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ Security stage failed, so nothing is known "
                     f"about whether this app is safe: {e}")
        log.exception("security stage")

    # Tests are evidence, not the delivery boundary. Re-probe and repair the
    # exact served app so a red unit/E2E suite cannot hide a real 404, 500,
    # collection mismatch, broken relationship, or missing planned journey.
    delivery_written = 0
    try:
        build_ok, db_ok, final_report, delivery_clean, delivery_conclusive, delivery_written = (
            run_delivery_stabilization(arch, proj_dir, analyzer, db_ok=db_ok,
                                       build_ok=build_ok, rounds=3))
        flow_report = final_report
        flow_clean = runtime_clean = api_clean = delivery_clean
        flow_conclusive = delivery_conclusive
        runtime_errors = [] if delivery_clean else [
            f"{getattr(f, 'code', 'DELIVERY')}: {getattr(f, 'message', '')}"
            for f in _serious_findings(final_report)[:8]]
        if delivery_written:
            if unit_out:
                unit_out["stale_after_late_repair"] = True
            if e2e_out:
                e2e_out["stale_after_late_repair"] = True
            # Source: security.py — imported helper(s) come from this file.
            from qa_agent.verification.security import SecurityAgent
            # From: agents/pipeline/build/project_preview.py
            sec_findings, _ = SecurityAgent(
                proj_dir, callbacks=_analyzer_callbacks(),
                cmd=getattr(arch, "cmd", None)).run(audit=False)
    except Exception as e:
        delivery_clean = delivery_conclusive = False
        final_report = _merge_analyzer_reports(flow_report, runtime_report, api_report)
        # From: agents/analysis/analysis_shared.py
        final_report.findings.append(Finding(
            "blocker", "DELIVERY_STABILIZATION_FAILED",
            f"final self-healing failed: {e}"))
        flow_report = final_report
        flow_clean = runtime_clean = api_clean = False
        runtime_errors.append(f"final self-healing failed: {e}")
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ Final self-healing failed: {e}")
        log.exception("delivery stabilization")

    if _dev_alive():
        red = []
        if not build_ok:
            red.append("build")
        if not runtime_clean:
            red.append("runtime")
        if not api_clean:
            red.append("API")
        if (e2e_out or {}).get("failed"):
            red.append(f"{(e2e_out or {}).get('failed')} journey(s)")
        if not (e2e_out or {}).get("ran"):
            red.append("E2E did not run")
        if red:
            # From: agents/build/tester_common.py
            elog("INFO", f"   ⚡ measuring performance anyway — {', '.join(red)} "
                         f"still red; the numbers describe the page as served")
        try:
            perf_scores = run_perf_stage(proj_dir)
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ Performance stage failed: {e}")
            log.exception("perf stage")
    else:
        # From: agents/build/tester_common.py
        elog("INFO", "   ⚡ performance skipped — nothing is answering on "
                     f"port {DEV_PORT}, so there is no app to measure")

    # Stage 7: write one final verdict and keep the preview available.
    final_report = flow_report

    write_qa_report(proj_dir, qa, unit=unit_out, security=sec_findings,
                    audit=sec_audit, perf=perf_scores, e2e=e2e_out,
                    runtime=runtime_errors, security_ran=sec_ran,
                    flow_report=final_report, flow_clean=flow_clean,
                    flow_conclusive=flow_conclusive)

    security_clean = bool(sec_ran) and not any(
        getattr(f, "severity", "") in ("blocker", "major")
        for f in (sec_findings or []))
    e2e_clean = (bool((e2e_out or {}).get("ran"))
                 and not bool((e2e_out or {}).get("failed", 0))
                 and not bool((e2e_out or {}).get("unwritable", 0))
                 and (e2e_out or {}).get("build_after_fix", True) is not False
                 and not bool((e2e_out or {}).get("stale_after_late_repair")))
    unit_clean = (bool((unit_out or {}).get("ran"))
                  and bool((unit_out or {}).get("clean", False))
                  and not bool((unit_out or {}).get("stale_after_late_repair")))
    quality_clean = bool(build_ok and flow_clean and flow_conclusive
                         and runtime_clean and api_clean
                         and security_clean and e2e_clean and unit_clean
                         and not runtime_errors)
    emit({"type": "quality_summary",
          "clean": quality_clean, "build": bool(build_ok),
          "flow": bool(flow_clean), "flow_conclusive": bool(flow_conclusive),
          "runtime": bool(runtime_clean), "api": bool(api_clean),
          "security": bool(security_clean), "e2e": bool(e2e_clean),
          "unit": bool(unit_clean), "runtime_errors": len(runtime_errors),
          "delivery_clean": bool(delivery_clean),
          "delivery_repaired": int(delivery_written)})

    _write_final_flow_receipt(
        proj_dir, final_report, clean=delivery_clean,
        conclusive=bool(delivery_conclusive), db_ok=db_ok, build_ok=build_ok)

    url = f"http://localhost:{DEV_PORT}"

    serving = False
    try:
        with socket.create_connection(("127.0.0.1", DEV_PORT), timeout=2):
            serving = True
    except OSError:

        serving = wait_for_next(20)
    if serving:
        estep("serve", "done" if (quality_clean or delivery_clean) else "error")
        if quality_clean:
            eprog("Done — clean and connected", 100)
            # From: agents/build/tester_common.py
            elog("INFO", f"🎉 Clean app live at {url}")
        else:
            eprog("Built — unresolved quality gate", 100)
            # From: agents/build/tester_common.py
            elog("WARN", f"⚠ App is live at {url}, but it is NOT labelled "
                         "clean because the final quality gate did not pass. "
                         "See .agentforge/final-flow.json and the QA report.")
    else:
        estep("serve", "error")
        eprog("Built, but not serving", 100)
        # From: agents/build/tester_common.py
        elog("WARN", "   ⚠ The app was built and tested, but nothing is "
                     f"answering on port {DEV_PORT}. The files and the "
                     "test results are all on disk — use the reload button "
                     "on the preview to try serving it again.")
    edone(url, pname)
