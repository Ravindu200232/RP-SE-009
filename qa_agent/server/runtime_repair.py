# Runtime QA repair helpers.


def _emit_qa_results(passed, failures, rnd):
    """One event per case, capped, so the counter in the UI is truthful."""
    if passed:
        emit({"type": "test_result", "status": "pass",
              "msg": f"{passed} unit test(s) passed",
              "detail": f"round {rnd}"})
    for f in failures[:40]:
        emit({"type": "test_result", "status": "fail",
              "msg": f"{f.name}",
              "detail": f"{f.test_file} — {f.message[:200]}"})


def _exact_runtime_focus(arch, text: str) -> list[str]:
    """Stack locations plus the source graph needed to explain them."""
    blob = str(text or "").replace("\\", "/")
    exact = []
    for rel in (getattr(arch, "files", None) or {}):
        rel = str(rel or "").replace("\\", "/").lstrip("./")
        if not rel.startswith(("app/", "components/", "lib/", "src/", "hooks/", "utils/", "services/", "store/", "stores/")):
            continue
        if not re.search(re.escape(rel) + r"(?::\d+)(?::\d+)?", blob, re.I):
            continue
        if rel not in exact:
            exact.append(rel)
    if not exact:
        return []
    try:
        graph = WorkspaceTools(arch).dependency_paths(exact, max_depth=4, cap=40)
    except Exception as e:
        log.debug(f"runtime dependency graph: {e}")
        graph = []
    return list(dict.fromkeys(exact + graph))[:40]


def _repair_runtime(arch, proj_dir: Path, qa, analyzer, all_errors: str,
                    dev_errors: str, attempt: int, model: str = None,
                    focus_paths=None, strict_scope: bool = False,
                    privileged_paths=None, exact_scope: bool = False) -> list:
    """Repair runtime/E2E failures through evidence-first diagnosis.

    Browser page/network/DOM evidence seeds a focused source neighborhood, but
    it never doubles as a write allowlist or as proof of root cause.  The repair
    planner must establish CURRENT/GAP/CAUSE/EVIDENCE before the fixer writes;
    proven dependencies may expand beyond the initial failing page.
    """
    planner = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                            analyzer=analyzer, model=model)
    fixer = BugFixerAgent(arch, proj_dir, callbacks=_qa_callbacks(), session=qa,
                          model=model)

    evidence = "\n".join([all_errors or "", dev_errors or ""])
    exact_evidence_paths = []
    if focus_paths and exact_scope:
        focus = []
        for rel in focus_paths:
            rel = str(rel or "").strip().replace("\\", "/").lstrip("./")
            if rel and rel in arch.files and rel not in focus:
                focus.append(rel)
        exact_evidence_paths = list(focus)
        try:
            graph = WorkspaceTools(arch).dependency_paths(
                focus, max_depth=4, cap=44)
            focus = list(dict.fromkeys(focus + graph))
        except Exception as e:
            log.debug(f"exact repair dependency graph: {e}")
    else:
        focus = planner.repair_focus_paths(focus_paths, evidence) if focus_paths else []

    def run_fixer(spec):
        if not spec or spec.is_empty():
            return []
        elog("INFO", f"   🧭 {spec.summary or 'Repair planned'} "
                     f"— {len(spec.files)} file(s)")
        for pkg in spec.packages:
            elog("INFO", f"   📦 npm install {pkg}")
            try:
                arch.cmd.run(f"npm install {pkg}")
            except Exception as e:
                elog("WARN", f"   ⚠ npm install {pkg} failed: {e}")
        try:
            return fixer.fix_runtime(all_errors, spec, server_log=dev_errors,
                                     round_no=attempt,
                                     privileged_paths=privileged_paths)
        except Exception as e:
            elog("WARN", f"   ⚠ Runtime repair failed: {e}")
            log.exception("runtime repair: fix")
            return []

    spec = None
    try:
        spec = planner.plan_repair(all_errors, server_log=dev_errors,
                                   focus_paths=focus or focus_paths)
    except Exception as e:
        elog("WARN", f"   ⚠ Repair planning failed: {e}")
        log.exception("runtime repair: plan")

    if spec and not spec.is_empty():
        ctx = getattr(spec, "context", {}) or {}
        elog("INFO", f"   🧠 repair root cause — {str(ctx.get('cause') or spec.summary)[:180]}")
        evidence_paths = [str(e.get('path') or '') for e in (ctx.get('evidence') or [])
                          if isinstance(e, dict) and e.get('path')]
        if evidence_paths:
            elog("INFO", "   🔎 repair evidence — " + ", ".join(evidence_paths[:8]))

    written = run_fixer(spec)
    if written:
        elog("INFO", f"   ✅ Repaired {len(written)} file(s): "
                     f"{', '.join(written)}")
        return written

    # Browser console/pageerror stacks are themselves concrete source evidence.
    # If the planner failed to emit its textual EVIDENCE lines but the runtime
    # mapped the failure to exact project files, do not throw that proof away.
    # Build a deterministic repair spec over only those named files; the caller
    # still applies syntax + invariant guards before accepting any write.
    if strict_scope and exact_scope and exact_evidence_paths:
        exact = []
        for rel in exact_evidence_paths:
            rel = str(rel or "").strip().replace("\\", "/").lstrip("./")
            if rel in arch.files and rel not in exact:
                exact.append(rel)
        if exact:
            elog("INFO", "   🧯 exact browser stack is the repair evidence — "
                         "using a deterministic source-scoped fixer")
            direct = FeatureSpec(
                summary="Repair the browser runtime error at its exact mapped source locations",
                files=[{
                    "action": "edit", "path": rel, "kind": "client",
                    "why": "browser console/pageerror stack directly maps this project source",
                } for rel in exact[:16]],
                context={
                    "current": "the browser reaches this source and emits a runtime console/page error",
                    "gap": "the page must render and execute without that runtime error",
                    "cause": "runtime evidence directly maps the failure to the scoped source files",
                    "evidence": [{
                        "path": rel,
                        "fact": "browser stack/console mapping names this source during the failing action",
                    } for rel in exact[:16]],
                    "verify": "repeat the same browser action with no console.error/pageerror and preserve the journey behavior",
                    "confidence": "high",
                },
            )
            written = run_fixer(direct)
            if written:
                elog("INFO", f"   ✅ Exact-stack repair wrote {len(written)} file(s): "
                             f"{', '.join(written)}")
                return written

    if strict_scope:
        elog("WARN", "   ⚠ Evidence-first E2E repair could not prove a safe change — no speculative fallback")
        return []

    if focus:
        elog("INFO", "   🔭 focused repair was inconclusive — broadening source analysis")
        try:
            broad = planner.plan_repair(all_errors, server_log=dev_errors,
                                        focus_paths=None)
        except Exception as e:
            elog("WARN", f"   ⚠ Broad repair analysis failed: {e}")
            broad = None
        written = run_fixer(broad)
        if written:
            elog("INFO", f"   ✅ Broad evidence repair wrote {len(written)} file(s): "
                         f"{', '.join(written)}")
            return written

    elog("WARN", "   ⚠ Runtime repair remains unresolved — root cause was not proven, so no code was guessed")
    return []
