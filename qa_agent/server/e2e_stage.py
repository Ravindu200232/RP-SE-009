# Evidence-first end-to-end checks and repairs.
from qa_agent.e2e.e2e_normalize import normalize_scenario_selectors
from qa_agent.e2e.e2e_contract import scenario_contract_issue, runtime_contract_issue
from qa_agent.e2e.e2e_invariants import validate_repair_invariants, repair_guard_feedback
from qa_agent.e2e.e2e_console import console_repair_batch
from qa_agent.e2e.e2e_preflight import run_plan_code_preflight
# e2e_final.py runs in this same namespace and calls stage_result directly.
from qa_agent.e2e.e2e_results import (aggregate_e2e, apply_stage_result,
                                      stage_result)

def _repair_after_stages(proj_dir: Path, qa, arch, runner, failures):
    """Re-align stale tests after proven late-stage application repairs."""
    for f in failures:
        try:
            f.stale = True
        except Exception:
            pass
    fixer = BugFixerAgent(arch, proj_dir, callbacks=_qa_callbacks(), session=qa,
                          model=QASession.model_for(qa, arch))
    for rnd in range(1, MAX_AFTER_FIX + 1):
        groups = _by_test_file(failures)
        ephase({"phase": -16, "title": "Re-aligning tests with the shipped code",
                "status": "active"})
        elog("INFO", f"   🔧 re-aligning {len(groups)} test file(s) with the "
                     f"code the later stages left behind (round {rnd}/"
                     f"{MAX_AFTER_FIX})")

        def repair(group):
            try:
                fixer.fix(group, build_ok=True, round_no=rnd, tier=0)
            except Exception as e:
                elog("WARN", f"   ⚠ re-alignment failed on "
                             f"{group[0].test_file}: {e}")
                log.exception("post-stage fix")

        with ThreadPoolExecutor(max_workers=QA_FIX_WORKERS) as pool:
            list(pool.map(repair, groups))
        ephase({"phase": -16, "title": "Re-aligning tests with the shipped code",
                "status": "done"})

        passed, failures, ok = runner.run()
        if not ok:
            elog("WARN", "   ⚠ the re-run produced no report — keeping the "
                         "last numbers that were measured")
            return passed, failures
        if not failures:
            elog("INFO", f"   ✅ {passed}/{passed} — the suite is green on the "
                         f"code that is shipping")
            return passed, failures
        elog("WARN", f"   ❌ {len(failures)} still failing after round {rnd}")
    _leave_unresolved(runner, failures,
                      "the code changed after these tests were written and "
                      "they could not be brought back into line")
    return passed, failures


def _e2e_detail(failures) -> list:
    """Serialize browser failures for the QA report."""
    out = []
    for f in failures or ():
        out.append({
            "case": getattr(f, "name", ""),
            "target": getattr(f, "target", ""),
            "kind": getattr(f, "kind", ""),
            "message": getattr(f, "message", ""),
            "stack": (getattr(f, "stack", "") or "")[:2000],
        })
    return out


def run_qa_e2e_stage(arch, proj_dir: Path, qa, analyzer, *, build_ok: bool,
                     db_ok: bool) -> dict:
    """Run real browser journeys after build and runtime gates settle."""
    out = {"ran": False, "flow": "", "passed": 0, "failed": 0, "fixed": 0,
           "unwritable": 0, "flows": [], "failures": [],
           "stage_total": 0, "stage_passed": 0, "stage_failed": 0,
           "stage_not_reached": 0, "stage_rate": 0,
           "global_integrity": {"ran": False, "passed": False, "failures": 0},
           "stale_after_late_repair": False}
    if not qa or not qa.enabled:
        return out
    if not build_ok:
        elog("WARN", "   ⚠ End-to-end flow skipped — the build is not green")
        return out
    if not db_ok:

        elog("WARN", "   ⚠ End-to-end flow skipped — no database")
        return out

    ephase({"phase": -17, "title": "End-to-end flow", "status": "active"})
    agent = E2EAgent(arch, proj_dir, callbacks=_qa_callbacks(), session=qa,
                     analyzer=analyzer, base_url=f"http://localhost:{DEV_PORT}")
    try:
        out.update(_e2e_rounds(agent, arch, proj_dir, qa, analyzer, out))
    except Exception as e:
        elog("WARN", f"   ⚠ End-to-end flow failed: {e}")
        log.exception("qa e2e")
    ephase({"phase": -17, "title": "End-to-end flow", "status": "done"})
    return out


def _e2e_rounds(agent, arch, proj_dir, qa, analyzer, out):
    """Every journey in the plan, walked one after another.

    Used to be one flow — `agent.author()` was asked for "the most important
    journey", which on a shop was always the customer buying something, and
    the manager's half shipped with nothing having ever clicked through it.
    Now the plan's workflows are the list, one browser run each, and each
    flow keeps its own re-author and repair loop. A crash found by flow two
    is repaired before flow three runs.

    Repairs are validated per round with a syntax check (the flow runs on the
    dev server, which compiles routes on demand), and the production build
    runs ONCE here, after every journey, only if any repair touched a file.
    Six flows × an adaptive E2E repair budget used to mean a full `next build`
    per round; now it is one build for the whole stage. A repair that only
    `next build` rejects is still caught — and, if it cannot be repaired in
    that build's own fix loop, reverted — before the app is served.
    """
    journeys = agent.journeys()
    total = len(journeys)
    stage_source_paths = [p for p in arch.files
                          if p.startswith(("app/", "components/", "lib/"))]
    stage_source_set = set(stage_source_paths)
    stage_baseline = FileSnapshot(proj_dir)
    stage_baseline.capture(stage_source_paths)

    preflight_fixed = run_plan_code_preflight(
        analyzer, repairable_major=REPAIRABLE_MAJOR, elog=elog, log=log)
    out["fixed"] += int(preflight_fixed or 0)

    if total > 1:
        elog("INFO", f"   🎭 {total} journeys to walk: "
                     + " · ".join(j["title"] for j in journeys))

    flows, all_fail = [], []
    blocked_retry = []
    agent._journey_outcomes = {}
    for n, journey in enumerate(journeys, start=1):
        if total > 1:
            elog("INFO", f"   🎭 journey {n}/{total} — {journey['title']}"
                         + (f" (as {journey['role']})" if journey.get("role") else ""))

        if not _dev_alive(2.0):
            elog("WARN", "   ↻ the dev server is not answering — starting it "
                         "again before walking this journey")
            start_next(proj_dir)
            if not wait_for_next():
                elog("WARN", "   ⚠ it did not come back; this journey will "
                             "report what it finds")
        one = {"ran": False, "flow": "", "passed": 0, "failed": 0, "fixed": 0,
               "unwritable": 0, "failures": []}
        try:
            one = _e2e_one_flow(agent, arch, proj_dir, qa, analyzer, one, journey)
        except Exception as e:
            elog("WARN", f"   ⚠ journey '{journey['title']}' could not run: {e}")
            log.exception("qa e2e flow")
        flows.append({"title": journey["title"], "role": journey.get("role", ""),
                      **{k: one.get(k) for k in ("ran", "flow", "passed", "failed",
                                                 "fixed", "unwritable", "stage_total",
                                                 "stage_passed", "stage_failed",
                                                 "stage_not_reached", "stage_rate", "stages")},
                      "blocked_upstream": bool(one.get("blocked_upstream"))})
        agent._journey_outcomes[journey["title"]] = {
            "role": journey.get("role", ""),
            "status": ("blocked_upstream" if one.get("blocked_upstream") else
                       "pass" if one.get("ran") and not one.get("failed") else "fail"),
            "reason": one.get("blocked_reason", ""),
        }
        if one.get("blocked_upstream"):
            blocked_retry.append((len(flows) - 1, journey))
        else:
            all_fail.extend(one.get("failures") or [])
        out["ran"] = out["ran"] or bool(one.get("ran"))
        out["fixed"] += int(one.get("fixed") or 0)
        out["failed"] += int(one.get("failed") or 0)
        out["passed"] += 1 if (one.get("ran") and not one.get("failed")) else 0
        out["unwritable"] = out.get("unwritable", 0) + int(one.get("unwritable") or 0)

    if blocked_retry and not E2E_RETRY_BLOCKED:
        elog("INFO", f"   ⏭ {len(blocked_retry)} dependency-blocked journey(s) "
                     "will not be replayed; fast E2E mode records them and moves on")

    for flow_index, journey in (blocked_retry if E2E_RETRY_BLOCKED else []):
        elog("INFO", f"   🔁 retrying dependency-blocked journey — {journey['title']}")
        one = {"ran": False, "flow": "", "passed": 0, "failed": 0, "fixed": 0,
               "unwritable": 0, "failures": []}
        try:
            one = _e2e_one_flow(agent, arch, proj_dir, qa, analyzer, one, journey)
        except Exception as e:
            elog("WARN", f"   ⚠ dependency retry '{journey['title']}' could not run: {e}")
            log.exception("qa e2e dependency retry")
        old = flows[flow_index]
        # Remove the first-pass counters before replacing its result.
        out["fixed"] -= int(old.get("fixed") or 0)
        out["failed"] -= int(old.get("failed") or 0)
        out["passed"] -= 1 if (old.get("ran") and not old.get("failed")) else 0
        out["unwritable"] -= int(old.get("unwritable") or 0)
        flows[flow_index] = {"title": journey["title"], "role": journey.get("role", ""),
                             **{k: one.get(k) for k in ("ran", "flow", "passed", "failed",
                                                        "fixed", "unwritable", "stage_total",
                                                        "stage_passed", "stage_failed",
                                                        "stage_not_reached", "stage_rate", "stages")},
                             "blocked_upstream": bool(one.get("blocked_upstream"))}
        out["fixed"] += int(one.get("fixed") or 0)
        out["failed"] += int(one.get("failed") or 0)
        out["passed"] += 1 if (one.get("ran") and not one.get("failed")) else 0
        out["unwritable"] += int(one.get("unwritable") or 0)
        all_fail.extend(one.get("failures") or [])
        agent._journey_outcomes[journey["title"]] = {
            "role": journey.get("role", ""),
            "status": ("blocked_upstream" if one.get("blocked_upstream") else
                       "pass" if one.get("ran") and not one.get("failed") else "fail"),
            "reason": one.get("blocked_reason", ""),
        }

    global_failures = []
    global_mark = dev_log_mark()
    try:
        elog("INFO", "   🔐 one role-separation integrity sweep")
        global_failures = agent.global_integrity()
        for fault in terminal_faults(dev_log_since(global_mark)):
            rel_m = re.search(r"((?:app|components|lib)[\\/][A-Za-z0-9_./\\\[\]-]+\.(?:jsx?|mjs))", fault)
            rel = rel_m.group(1).replace("\\", "/") if rel_m else ""
            if not any(str(getattr(f, "message", ""))[:100] in fault for f in global_failures):
                global_failures.append(TestFailure(
                    test_file="tests/e2e/__global-integrity__.spec.js",
                    target=rel, name="Next runtime error during global integrity",
                    message=fault[:700], stack=fault[:3000], kind="CRASH"))
    except Exception as e:
        elog("WARN", f"   ⚠ global E2E integrity could not run: {e}")
        log.exception("qa e2e global integrity")

    for grnd in range(1, E2E_GLOBAL_REPAIR_ATTEMPTS + 1):
        if not global_failures:
            break
        targets = []
        for f in global_failures[:6]:
            rel = str(getattr(f, "target", "") or "").strip()
            if rel and rel not in targets:
                targets.append(rel)
        report = "\n\n".join(
            f"[{getattr(f, 'kind', 'E2E')}] {f.name}\n{f.message}\n{f.stack[:1000]}"
            for f in global_failures[:6])
        snap = FileSnapshot(proj_dir)
        snap.capture([p for p in arch.files
                      if p.startswith(("app/", "components/", "lib/"))])
        fixed = _repair_runtime(
            arch, proj_dir, qa, analyzer, report, "", 100 + grnd,
            model=QASession.model_for(qa, arch), focus_paths=targets,
            strict_scope=True)
        if not fixed:
            break
        problems, _ = check_syntax(
            proj_dir, {p: arch.files.get(p, "") for p in fixed})
        if problems:
            snap.restore(fixed)
            elog("WARN", "   ↩ global E2E repair did not parse — reverted")
            break
        out["fixed"] += len(fixed)
        try:
            agent.invalidate_runtime_evidence()
        except Exception:
            pass
        rerun_mark = dev_log_mark()
        global_failures = agent.global_integrity()
        for fault in terminal_faults(dev_log_since(rerun_mark)):
            rel_m = re.search(r"((?:app|components|lib)[\\/][A-Za-z0-9_./\\\[\]-]+\.(?:jsx?|mjs))", fault)
            rel = rel_m.group(1).replace("\\", "/") if rel_m else ""
            global_failures.append(TestFailure(
                test_file="tests/e2e/__global-integrity__.spec.js", target=rel,
                name="Next runtime error during global integrity", message=fault[:700],
                stack=fault[:3000], kind="CRASH"))

    if global_failures:
        out["failed"] += len(global_failures)
        all_fail.extend(_e2e_detail(global_failures))
        out["global_integrity"] = {"ran": True, "passed": False,
                                   "failures": len(global_failures)}
        elog("WARN", f"   ⚠ global E2E integrity still has "
                     f"{len(global_failures)} failure(s)")
    else:
        out["global_integrity"] = {"ran": True, "passed": True, "failures": 0}
        elog("INFO", "   ✅ global E2E route/role integrity is clean")

    out["flows"] = flows
    out["failures"] = all_fail
    out["flow"] = (flows[0]["flow"] if flows and len(flows) == 1
                   else f"{out['passed']} of {total} journeys pass")
    if total > 1:
        elog("INFO" if out["passed"] == total else "WARN",
             f"   🎭 {out['passed']} of {total} journeys pass end to end")

    if out["fixed"]:
        elog("INFO", f"   🔨 {out['fixed']} file(s) repaired during end-to-end "
                     f"— one production build to confirm they compile")
        _stop_dev_proc()
        built = run_build_fix_loop(arch, proj_dir, True, max_rounds=1)
        out["build_after_fix"] = bool(built)
        if not built:
            elog("WARN", "   ↩ E2E repair transaction failed the production build — restoring the pre-E2E source")
            stage_baseline.restore()
            for rel in list(arch.files):
                if (rel.startswith(("app/", "components/", "lib/"))
                        and rel not in stage_source_set):
                    try:
                        (proj_dir / rel).unlink(missing_ok=True)
                    except Exception:
                        pass
            try:
                arch.load_existing()
            except Exception:
                pass
            errors, conclusive = _npm_build_errors(proj_dir, "next")
            if conclusive and not errors:
                elog("INFO", "   ✅ pre-E2E source restored and build is clean")
            out["fixed"] = 0
            out["failed"] += 1
            out["failures"].append({
                "case": "E2E repair transaction", "target": "", "kind": "BUILD",
                "message": "E2E candidate repairs were rolled back because the production build was not green",
                "stack": "",
            })
        start_next(proj_dir)
        wait_for_next()

    aggregate_e2e(out)
    _e2e_final_clean_room(agent, arch, proj_dir, qa, analyzer,
                          journeys, flows, out)
    aggregate_e2e(out)
    return out


def _repair_contract_backed_selector_failure(agent, arch, proj_dir, analyzer,
                                             failures) -> tuple:
    """Repair a soft E2E miss only when independent architecture evidence says app bug.

    A missing selector or guessed copy normally means the generated scenario
    described the UI badly and must NOT rewrite application code. The exception
    is when the deterministic analyzer independently reports a flow/capability
    defect on the exact page where the scenario missed: a broken contract, an
    inert promised control, missing planned data, a role redirect, or an
    unbuilt promise. Example:
    a promised action id is absent on a detail page *and* the plan contract
    says that page must reach the create flow. That is no longer a test guess;
    two independent witnesses point at the same disconnected feature.

    Returns (written_count, changed_paths).  A syntax-breaking repair is rolled
    back immediately and reported as no change.
    """
    targets = {str(getattr(f, "target", "") or "").strip()
               for f in (failures or [])}
    targets.discard("")
    if not targets:
        return 0, []

    try:
        scanned = analyzer.scan()
    except Exception as e:
        log.debug(f"selector arbitration scan: {e}")
        return 0, []

    relevant = []
    flow_codes = {
        "BROKEN_CONTRACT", "NO_WAY_THERE", "UNBUILT_PROMISE",
        "MISSING_PLANNED_DATA", "INERT_CONTROL", "ROLE_REDIRECT",
        "MONGO_ID_TYPE", "DYNAMIC_ROUTE_ERROR",
    }
    for finding in (getattr(scanned, "findings", None) or []):
        if getattr(finding, "code", "") not in flow_codes:
            continue
        paths = {str(getattr(finding, "path", "") or "").strip()}
        paths |= {str(x or "").strip() for x in
                  (getattr(finding, "extra", None) or [])}
        paths.discard("")
        if targets & paths:
            relevant.append(finding)

    if not relevant:
        try:
            semantic = analyzer.unbuilt_promises(max_reads=4)
        except Exception as e:
            log.debug(f"selector arbitration semantic audit: {e}")
            semantic = []
        for finding in semantic or []:
            if getattr(finding, "code", "") != "UNBUILT_PROMISE":
                continue
            paths = {str(getattr(finding, "path", "") or "").strip()}
            paths |= {str(x or "").strip() for x in
                      (getattr(finding, "extra", None) or [])}
            paths.discard("")
            if targets & paths:
                relevant.append(finding)

    if not relevant:
        return 0, []

    elog("INFO", "   🔗 E2E miss matches independent capability/flow evidence "
                 "— repairing the app, not the test")
    for f in relevant[:4]:
        elog("WARN", f"      [{getattr(f, 'code', '')}] "
                     f"{getattr(f, 'message', '')[:140]}")

    snap = FileSnapshot(proj_dir)
    capture_paths = {rel for rel in arch.files
                     if rel.startswith(("app/", "components/", "lib/"))}
    for finding in relevant:
        for rel in [getattr(finding, "path", "")] + list(
                getattr(finding, "extra", None) or []):
            rel = str(rel or "").strip().lstrip("./").replace("\\", "/")
            if rel.startswith(("app/", "components/", "lib/")):
                capture_paths.add(rel)
    snap.capture(sorted(capture_paths))

    report = AnalyzerReport()
    report.findings = relevant
    report.missing = []
    try:
        analyzer.repair(report)
    except Exception as e:
        elog("WARN", f"   ⚠ contract-backed selector repair failed: {e}")
        log.exception("e2e selector contract repair")
        return 0, []

    try:
        arch.repair_missing_imports()
    except Exception:
        pass

    changed = snap.changed()
    if not changed:
        return 0, []

    problems, _ = check_syntax(
        proj_dir, {rel: arch.files.get(rel, "") for rel in changed})
    if problems:
        elog("WARN", "   ↩ contract-backed selector repair does not parse — "
                     "reverting it")
        snap.restore()
        try:
            arch.load_existing()
        except Exception:
            pass
        return 0, []

    return len(changed), changed


def _e2e_scenario_issue(agent, sc, journey=None) -> str:
    """Authoring defects that should be rewritten before opening a browser."""
    notes = normalize_scenario_selectors(sc)
    for note in notes[:3]:
        elog("INFO", f"   ↪ normalized scenario locator grammar — {note}")
    try:
        temporal = agent.normalize_temporal_values(sc, journey)
    except Exception as e:
        log.debug(f"e2e temporal normalization: {e}")
        temporal = []
    for note in temporal[:4]:
        elog("INFO", f"   📅 normalized decaying scenario data — {note}")
    why = sc.is_runnable()
    if why:
        return why
    contract = (journey or {}).get("contract") or {}
    why = scenario_contract_issue(contract, sc, agent._is_business_step)
    if why:
        return why
    executable = re.compile(
        r"^(?:GOTO|FILL|SELECT|CLICK|WAIT_FOR|EXPECT_TEXT|EXPECT_URL|"
        r"EXPECT_VALUE|EXPECT_MUTATION|EXPECT_NO_ERROR)\b", re.I)
    dropped = [(line, reason) for _, line, reason in (getattr(sc, "dropped", None) or [])
               if executable.search(str(line or ""))]
    if dropped:
        sample = "; ".join(f"{line} ({reason})" for line, reason in dropped[:3])
        return f"{len(dropped)} executable step(s) were dropped: {sample}"
    try:
        grounded = agent.grounding_issue(sc, journey)
    except Exception as e:
        log.debug(f"e2e grounding preflight: {e}")
        grounded = ""
    return grounded or ""


def _e2e_agentic_diagnosis(agent, arch, analyzer, failures, journey, dev_trace,
                           model=None, debugger=None, scenario=None) -> dict:
    """Claude/Codex-style tool loop: inspect first, decide second, edit later."""
    debugger = debugger or AgenticE2EDebugger(
        agent, arch, analyzer=analyzer, model=model,
        notebook=DebugNotebook(goal=str((journey or {}).get("title") or "")))
    elog("INFO", "   🧠 Agentic debugger — inspect → hypothesis → tool → verdict")
    diag = debugger.investigate(
        failures, journey=journey, scenario=scenario, dev_trace=dev_trace)

    auth_priv = {"lib/auth.js", "lib/auth-client.js",
                 "app/api/auth/[...all]/route.js"}
    files = [str(x or "").strip() for x in (diag.get("files") or [])]

    try:
        sites = agent.console_bug_sites() or []
    except Exception as e:
        log.debug(f"console bug sites: {e}")
        sites = []
    if sites:
        named = []
        for rel, line, _why in sites[:12]:
            if rel and rel not in named:
                named.append(rel)
        files = named + [f for f in files if f not in named]
        elog("INFO", "   \U0001f4cd the browser's stack names: "
                     + ", ".join(f"{r}:{ln}" if ln else r
                                 for r, ln, _ in sites[:8]))
    if diag.get("verdict") == "AUTH_FIX":
        diag["privileged"] = [x for x in files if x in auth_priv]
    else:
        diag["privileged"] = []
        diag["files"] = [x for x in files if x not in auth_priv]

    elog("INFO", f"   🤖 E2E diagnosis — {diag.get('verdict', 'UNKNOWN')}: "
                 f"{str(diag.get('root') or 'no root text')[:180]}")
    if diag.get("files"):
        elog("INFO", "      evidence-scoped files: "
                     + ", ".join(diag.get("files")[:4]))
    if diag.get("hypothesis"):
        elog("INFO", "      hypothesis: " + str(diag.get("hypothesis"))[:180])
    return diag


def _runtime_contract_failure(agent, sc, journey):
    why = runtime_contract_issue((journey or {}).get("contract") or {}, sc,
                                 getattr(agent, "_last_run_evidence", {}) or {},
                                 agent._is_business_step)
    if not why:
        return []
    ev = getattr(agent, "_last_run_evidence", {}) or {}
    return [TestFailure(test_file=sc.spec_path(), target=str(ev.get("target") or ""),
                        name="capability side-effect proof", message=why,
                        stack=str(ev.get("api_network") or "")[:3000], kind="BEHAVIOR")]


def _e2e_one_flow(agent, arch, proj_dir, qa, analyzer, out, journey=None):
    """Walk one journey with a Claude/Codex-style autonomous debug loop."""
    mark = dev_log_mark()
    notebook = DebugNotebook(goal=str((journey or {}).get("title") or ""))
    debugger = AgenticE2EDebugger(
        agent, arch, analyzer=analyzer, model=QASession.model_for(qa, arch),
        notebook=notebook)

    sc = agent.author(journey=journey)
    why = _e2e_scenario_issue(agent, sc, journey)
    for attempt in range(1, E2E_AUTHOR_REWRITE_ATTEMPTS + 1):
        if not why:
            break
        elog("WARN", f"   ⚠ the flow was not usable — {why}; one bounded rewrite "
                     f"({attempt}/{E2E_AUTHOR_REWRITE_ATTEMPTS})")
        sc = agent.author(previous=sc, why=why, journey=journey)
        why = _e2e_scenario_issue(agent, sc, journey)
    if why:
        title = str((journey or {}).get("title") or getattr(sc, "title", "") or "required journey")
        failure = TestFailure(
            test_file=getattr(sc, "spec_path", lambda: "tests/e2e/__authoring__.spec.js")(),
            target="", name=f"{title} scenario could not be grounded",
            message=str(why), stack="", kind="ASSERTION")
        out["flow"] = title
        out["failed"] = 1
        out["failures"] = _e2e_detail([failure])
        apply_stage_result(out, sc, [failure], {}, authoring_failed=True)
        elog("WARN", f"   ⚠ End-to-end flow could not be grounded — {why}")
        emit({"type": "test_result", "status": "fail",
              "msg": f"End-to-end authoring: {title}", "detail": str(why)[:200]})
        return out

    out["flow"] = sc.title
    elog("INFO", f"   🎭 {sc.title}  ({len(sc.steps)} steps)")
    try:
        # Bind locators to what the DOM really has before spending a run.
        bound = agent.preground(sc, journey)
        if bound:
            elog("INFO", f"   🧲 {bound} selector(s) bound to the live DOM "
                         "before the first run")
    except Exception as e:
        log.debug(f"preground: {e}")
    agent.write_spec(sc)
    failures = agent.run(sc, journey=journey)
    if not failures:
        failures = _runtime_contract_failure(agent, sc, journey)
    out["ran"] = True
    if not failures:
        agent.remember_scenario(journey, sc)
        apply_stage_result(out, sc, [], getattr(agent, "_last_run_evidence", {}) or {})
        elog("INFO", "   ✅ the end-to-end flow passed")
        emit({"type": "test_result", "status": "pass",
              "msg": f"End-to-end: {sc.title}",
              "detail": f"{len(sc.steps)} steps"})
        return out

    out["failed"] = len(failures)
    out["failures"] = _e2e_detail(failures)
    apply_stage_result(out, sc, failures, getattr(agent, "_last_run_evidence", {}) or {})
    for f in failures[:5]:
        emit({"type": "test_result", "status": "fail",
              "msg": f"End-to-end: {f.name}", "detail": f.message[:200]})

    round_budget = max(E2E_BASE_FIX, E2E_MIN_FIX)
    rnd = 0
    no_progress = 0
    seen_signatures = {_e2e_failure_signature(failures)}

    while failures and rnd < round_budget and rnd < E2E_HARD_FIX:
        rnd += 1
        real = list(failures)
        ephase({"phase": -18, "title": f"Agentic E2E debug (round {rnd})",
                "status": "active"})
        elog("INFO", f"   🧠 Agentic E2E round {rnd}/{round_budget}"
                     + (f" (hard cap {E2E_HARD_FIX})"
                        if round_budget < E2E_HARD_FIX else "")
                     + f" — {len(real)} failure(s)")

        try:
            before_step = int((getattr(agent, "_last_run_evidence", {}) or {}).get("failed_index", -1))
        except Exception:
            before_step = -1
        trace = _filter_db_noise(dev_log_since(mark), True)

        # Production console faults outrank selector or workflow guesses.
        console_batch = console_repair_batch(agent, real)
        if console_batch:
            events = console_batch.get("events") or []
            sites = console_batch.get("sites") or []
            targets = console_batch.get("files") or []
            elog("WARN", f"   🧯 console-first repair — {len(events)} browser runtime error(s)")
            if sites:
                elog("INFO", "   📍 browser locations — " + ", ".join(
                    f"{rel}:{line}" if line else rel for rel, line, _ in sites[:8]))
            snap = FileSnapshot(proj_dir)
            snap.capture([p for p in arch.files if p.startswith(("app/", "components/", "lib/"))])
            before_sources = {p: str(arch.files.get(p, "") or "") for p in arch.files
                              if p.startswith(("app/", "components/", "lib/"))}
            fixed = _repair_runtime(
                arch, proj_dir, qa, analyzer, console_batch.get("report") or "", trace, rnd,
                model=QASession.model_for(qa, arch), focus_paths=targets,
                strict_scope=True, exact_scope=bool(sites))
            if fixed:
                console_diag = {"verdict": "APP_FIX",
                                "root": "browser console runtime failure",
                                "files": list(targets), "locations": [
                                    {"path": r, "line": ln, "column": 0, "signal": "console.error"}
                                    for r, ln, _ in sites]}
                violations = validate_repair_invariants(
                    before_sources, arch.files, fixed, "APP_FIX", console_diag,
                    failure=real[0], journey=journey)
                if violations:
                    elog("WARN", "   ↩ console repair crossed the evidence boundary — reverting")
                    snap.restore(fixed)
                    try:
                        arch.load_existing()
                    except Exception:
                        pass
                    fixed = []
            if fixed:
                problems, _ = check_syntax(proj_dir, {p: arch.files.get(p, "") for p in fixed})
                if problems:
                    elog("WARN", "   ↩ console repair does not parse — reverting")
                    snap.restore(fixed)
                    try:
                        arch.load_existing()
                    except Exception:
                        pass
                else:
                    out["fixed"] += len(fixed)
                    elog("INFO", f"   ✅ console batch repaired {len(fixed)} file(s); re-checking the same action")
                    try:
                        agent.invalidate_runtime_evidence()
                    except Exception:
                        pass
                    failures = agent.run_resume(sc, journey=journey, failure=real[0])
                    if not failures:
                        failures = _runtime_contract_failure(agent, sc, journey)
                    if not failures:
                        agent.remember_scenario(journey, sc)
                        elog("INFO", f"   ✅ the end-to-end flow passes after console-first repair in round {rnd}")
                        emit({"type": "test_result", "status": "pass",
                              "msg": f"End-to-end: {sc.title}",
                              "detail": f"console-first repair in {rnd} round(s)"})
                        out["failed"] = 0
                        out["failures"] = []
                        break
                    # A new obstruction is handled on the next round with fresh evidence.
                    before = real
                    out["failed"] = len(failures)
                    out["failures"] = _e2e_detail(failures)
                    try:
                        after_step = int((getattr(agent, "_last_run_evidence", {}) or {}).get("failed_index", -1))
                    except Exception:
                        after_step = -1
                    progressed, reason = _e2e_progress(
                        before, failures, seen_signatures,
                        before_step=before_step, after_step=after_step)
                    if progressed:
                        no_progress = 0
                        new_sig = _e2e_failure_signature(failures)
                        if new_sig:
                            seen_signatures.add(new_sig)
                        round_budget = _e2e_extend_budget(
                            rnd, round_budget, E2E_HARD_FIX, E2E_PROGRESS_BONUS, True)
                        elog("INFO", f"   ↗ console-first progress — {reason}")
                    else:
                        no_progress += 1
                    mark = dev_log_mark()
                    continue
            else:
                elog("WARN", "   ⚠ console errors were captured, but no safe batch repair was proven")

        diag = _e2e_agentic_diagnosis(
            agent, arch, analyzer, real, journey, trace,
            model=QASession.model_for(qa, arch), debugger=debugger, scenario=sc)
        verdict = diag.get("verdict") or "UNKNOWN"
        old_failure = real[0]
        before = failures
        mark = dev_log_mark()

        if verdict == "TEST_FIX":
            patched = agent.patch_scenario_step(
                sc, old_failure, diag.get("test_patch") or "")
            if not patched:
                exact_patch = debugger.propose_test_patch(old_failure, sc)
                patched = agent.patch_scenario_step(sc, old_failure, exact_patch)
            if patched:
                elog("INFO", "   🧪 TEST_FIX — patched exactly one failing scenario step")
                agent.write_spec(sc)
                failures = agent.run_resume(sc, journey=journey,
                                            failure=old_failure)
            else:
                nfix, changed = _repair_contract_backed_selector_failure(
                    agent, arch, proj_dir, analyzer, real)
                if changed:
                    elog("INFO", "   🔗 TEST_FIX escalation found an app-side contract defect")
                    out["fixed"] += nfix
                    try:
                        agent.invalidate_runtime_evidence()
                    except Exception:
                        pass
                    failures = agent.run_resume(sc, journey=journey,
                                                failure=old_failure)
                else:
                    elog("WARN", "   ⚠ TEST_FIX had no DOM-grounded patch and no independent app defect — preserving the scenario")
                    failures = before

        elif verdict == "DATA_PREREQUISITE":
            instruction = (diag.get("next") or diag.get("root") or
                           "establish the required record/state through an existing user workflow before asserting it")
            elog("INFO", "   🌱 DATA_PREREQUISITE — fixing journey setup, not inventing UI/data")
            sc2 = agent.author(
                previous=sc,
                why="Add the real prerequisite setup using existing routes/controls. " + instruction,
                page=old_failure.target, journey=journey)
            unusable = _e2e_scenario_issue(agent, sc2, journey)
            if unusable:
                failures = before
            else:
                sc = sc2
                agent.write_spec(sc)
                failures = agent.run(sc, journey=journey)

        elif verdict == "BLOCKED_UPSTREAM":
            out["blocked_upstream"] = True
            out["blocked_reason"] = (diag.get("root") or diag.get("next") or
                                     "upstream journey failed")
            elog("WARN", "   ⛓ E2E journey appears blocked by an upstream business outcome — "
                         + str(out["blocked_reason"])[:220])
            failures = before

        elif verdict == "RETRY_TRANSIENT":
            elog("INFO", "   ♻ transient incident — retrying from the last browser checkpoint")
            failures = agent.run_resume(sc, journey=journey,
                                        failure=old_failure)

        elif verdict == "UNKNOWN":
            nfix, changed = _repair_contract_backed_selector_failure(
                agent, arch, proj_dir, analyzer, real)
            if changed:
                elog("INFO", "   🧭 UNKNOWN rescued by independent capability/flow evidence")
                out["fixed"] += nfix
                try:
                    agent.invalidate_runtime_evidence()
                except Exception:
                    pass
                failures = agent.run_resume(sc, journey=journey, failure=old_failure)
            else:
                elog("WARN", "   ⚠ debugger could not establish a safe root cause — preserving the app and trying a different hypothesis")
                failures = before

        else:  # APP_FIX / AUTH_FIX / ROUTE_FIX
            targets = []
            for rel in (diag.get("files") or []):
                rel = str(rel or "").strip()
                if rel and rel not in targets:
                    targets.append(rel)
            for f in real:
                rel = str(getattr(f, "target", "") or "").strip()
                if rel and rel not in targets:
                    targets.append(rel)

            report = "\n\n".join(
                f"[{getattr(f, 'kind', 'E2E')}] {f.name}\n{f.message}\n{f.stack[:1800]}"
                for f in real[:5])
            report += (
                "\n\nAGENTIC ROOT CAUSE\n" + str(diag.get("root") or "")
                + "\nHYPOTHESIS\n" + str(diag.get("hypothesis") or "")
                + "\nNEXT\n" + str(diag.get("next") or "")
            )
            if diag.get("locations"):
                report += "\nRUNTIME SOURCE LOCATIONS (highest-priority evidence)\n"
                for loc in (diag.get("locations") or [])[:6]:
                    if not isinstance(loc, dict):
                        continue
                    report += (f"- {loc.get('path')}:{loc.get('line')}:{loc.get('column', 0)} "
                               f"[{loc.get('signal', 'runtime')}]\n")

            snap = FileSnapshot(proj_dir)
            snap.capture([p for p in arch.files
                          if p.startswith(("app/", "components/", "lib/"))])
            exact_runtime_scope = bool(diag.get("locations"))
            if exact_runtime_scope:
                exact = []
                for loc in (diag.get("locations") or []):
                    rel = str((loc or {}).get("path") or "").strip() if isinstance(loc, dict) else ""
                    if rel and rel in arch.files and rel not in exact:
                        exact.append(rel)
                if exact:
                    targets = exact
            before_sources = {p: str(arch.files.get(p, "") or "")
                              for p in arch.files
                              if p.startswith(("app/", "components/", "lib/"))}
            fixed = _repair_runtime(
                arch, proj_dir, qa, analyzer, report, trace, rnd,
                model=QASession.model_for(qa, arch), focus_paths=targets,
                strict_scope=True,
                privileged_paths=diag.get("privileged") or [],
                exact_scope=exact_runtime_scope)

            if fixed:
                violations = validate_repair_invariants(
                    before_sources, arch.files, fixed, verdict, diag,
                    failure=old_failure, journey=journey)
                if violations:
                    elog("WARN", "   ↩ repair invariant guard rejected the candidate patch")
                    for item in violations[:4]:
                        elog("WARN", f"      • {item}")
                    snap.restore(fixed)
                    try:
                        arch.load_existing()
                    except Exception:
                        pass
                    guarded_report = report + repair_guard_feedback(
                        violations, diag, failure=old_failure)
                    fixed = _repair_runtime(
                        arch, proj_dir, qa, analyzer, guarded_report, trace, rnd,
                        model=QASession.model_for(qa, arch), focus_paths=targets,
                        strict_scope=True,
                        privileged_paths=diag.get("privileged") or [],
                        exact_scope=exact_runtime_scope)
                    if fixed:
                        violations = validate_repair_invariants(
                            before_sources, arch.files, fixed, verdict, diag,
                            failure=old_failure, journey=journey)
                        if violations:
                            elog("WARN", "   ↩ corrected repair still crossed the evidence boundary — reverted")
                            snap.restore(fixed)
                            try:
                                arch.load_existing()
                            except Exception:
                                pass
                            fixed = []

            ephase({"phase": -18, "title": f"Agentic E2E debug (round {rnd})",
                    "status": "done", "written": len(fixed)})
            if not fixed:
                elog("WARN", "   ⚠ evidence-scoped fixer changed nothing safe")
                failures = before
            else:
                problems, _ = check_syntax(
                    proj_dir, {p: arch.files.get(p, "") for p in fixed})
                if problems:
                    elog("WARN", f"   ↩ E2E fix does not parse ({syntax_messages(problems)[0][:90]}) — reverting")
                    snap.restore(fixed)
                    try:
                        arch.load_existing()
                    except Exception:
                        pass
                    failures = before
                else:
                    out["fixed"] += len(fixed)
                    try:
                        agent.invalidate_runtime_evidence()
                    except Exception:
                        pass
                    time.sleep(0.15)
                    failures = agent.run_resume(sc, journey=journey,
                                                failure=old_failure)

        if not failures:
            failures = _runtime_contract_failure(agent, sc, journey)
        out["failed"] = len(failures)
        out["failures"] = _e2e_detail(failures)
        if not failures:
            out["blocked_upstream"] = False
            out["blocked_reason"] = ""
            agent.remember_scenario(journey, sc)
            debugger.notebook.record_outcome(diag, progressed=True)
            elog("INFO", f"   ✅ the end-to-end flow passes after agentic round {rnd}")
            emit({"type": "test_result", "status": "pass",
                  "msg": f"End-to-end: {sc.title}",
                  "detail": f"agentic repair in {rnd} round(s)"})
            break

        try:
            after_step = int((getattr(agent, "_last_run_evidence", {}) or {}).get("failed_index", -1))
        except Exception:
            after_step = -1
        progressed, reason = _e2e_progress(
            before, failures, seen_signatures,
            before_step=before_step, after_step=after_step)
        debugger.notebook.record_outcome(diag, progressed=progressed)
        new_sig = _e2e_failure_signature(failures)
        if progressed:
            no_progress = 0
            if new_sig:
                seen_signatures.add(new_sig)
            elog("INFO", f"   ↗ agentic E2E progress — {reason}")
            old_budget = round_budget
            round_budget = _e2e_extend_budget(
                rnd, round_budget, E2E_HARD_FIX, E2E_PROGRESS_BONUS, True)
            if round_budget > old_budget:
                elog("INFO", f"   ➕ progress earned {round_budget - old_budget} more E2E repair round(s) "
                             f"— budget {old_budget}→{round_budget}, hard cap {E2E_HARD_FIX}")
        else:
            no_progress += 1
            if new_sig:
                seen_signatures.add(new_sig)
            if rnd < E2E_MIN_FIX:
                elog("WARN", f"   ↔ no progress in round {rnd}; trying another hypothesis — minimum {E2E_MIN_FIX} rounds")
            else:
                elog("WARN", f"   ↔ no progress after required round {rnd}")
            exhausted = bool(diag.get("exhausted"))
            if _e2e_stop_no_progress(
                    rnd, progressed, E2E_MIN_FIX, exhausted=exhausted):
                if exhausted:
                    elog("WARN", f"   ⏹ round {rnd} could only repeat a hypothesis the browser "
                                 "already rejected — evidence is exhausted, so no guess/retry is allowed")
                else:
                    elog("WARN", f"   ⏹ no journey progress after round {rnd}; stopping this obstruction")
                break

        elog("WARN", f"   ⚠ still failing after agentic round {rnd}: "
                     f"{failures[0].message[:110]}")

    apply_stage_result(out, sc, failures, getattr(agent, "_last_run_evidence", {}) or {})
    if failures:
        if E2E_HARD_FIX and rnd >= E2E_HARD_FIX:
            elog("WARN", f"   ⏹ E2E repair reached hard cap {E2E_HARD_FIX} — recording the failure "
                         "and moving to the next journey")
        elif E2E_HARD_FIX and rnd >= round_budget:
            elog("WARN", f"   ⏹ E2E repair used its current {round_budget}-round budget without "
                         "further journey progress — recording the failure")
        elif not E2E_HARD_FIX:
            elog("WARN", "   ⏹ E2E auto-repair is disabled — recording the failure")
    return out


def _by_test_file(failures):
    """Group failures by test file — one model call per file, not per case."""
    groups = {}
    for f in failures:
        groups.setdefault(f.test_file, []).append(f)
    return [groups[k] for k in sorted(groups)]
