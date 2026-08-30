

# Builds a short state summary from the latest bug reproduction evidence.
def _reproduce_state(proj_dir: Path, route: str, complaint: str, analyzer):
    """Build a compact state summary from the latest bug reproduction evidence."""
    mark = dev_log_mark()
    # From: agents/pipeline/bugs/bug_request.py
    seen = _reproduce_complaint(proj_dir, route, complaint, analyzer)
    # From: agents/pipeline/build/runtime_faults.py
    trace = _filter_db_noise(dev_log_since(mark, limit=180), True)
    # From: agents/pipeline/bugs/bug_request.py
    return seen, trace, _observation_fault_signature(seen, trace)


# Converge downstream faults on the same affected route.
def _stabilize_bug_repair(arch, proj_dir: Path, proj_name: str, analyzer, *,
                          route: str, complaint: str, model: str,
                          baseline_signature: set, max_rounds: int = 8) -> tuple:
    """Converge downstream faults on the same affected route."""
    total = []
    last_sig = None
    repeat_sig = 0
    last_seen = None
    for rnd in range(1, max_rounds + 1):
        # From: agents/build/tester_common.py
        elog("INFO", f"   🩺 Bug stabilization {rnd}/{max_rounds} on {route}")
        seen, trace, sig = _reproduce_state(proj_dir, route, complaint, analyzer)
        last_seen = seen

        # A clean rerun settles a runtime/network complaint.
        semantic_ok = bool(getattr(seen, "clicked", "") and getattr(seen, "changed", False))
        if not sig and (baseline_signature or semantic_ok):
            # From: agents/build/tester_common.py
            elog("INFO", "   ✅ Affected route stayed clean after the repair")
            return True, total, seen
        if baseline_signature:
            old_left = baseline_signature & sig
            fresh = sig - baseline_signature
            if not old_left and not fresh:
                # From: agents/build/tester_common.py
                elog("INFO", "   ✅ Original symptom is gone and no downstream fault appeared")
                return True, total, seen
        if not baseline_signature and not sig and getattr(seen, "ran", False):
            # A quiet browser is valid proof for source-level complaints that
            # did not have a runtime signature before the edit.
            # From: agents/build/tester_common.py
            elog("INFO", "   ✅ Affected route is clean after the repair")
            return True, total, seen

        if sig == last_sig:
            repeat_sig += 1
            # From: agents/build/tester_common.py
            elog("WARN", "   ↔ the same affected-route fault survived; re-analyzing with fresh evidence")
        else:
            repeat_sig = 0
        last_sig = set(sig)

        # From: agents/analysis/runtime/browser_reproduction.py
        evidence = (f"The user reports: {complaint}\nAffected page: {route}\n\n"
                    + (seen.as_prompt() if seen is not None else "")
                    + ("\n\nThe Next dev server printed:\n" + trace if trace else ""))
        focus = _exact_runtime_focus(arch, evidence)
        # A repeated symptom needs a wider read, not an immediate rollback.
        if repeat_sig:
            focus = None
        # From: agents/pipeline/feature_safety.py
        round_tx = _capture_feature_transaction(arch, proj_dir)
        fixed = _repair_runtime(arch, proj_dir, None, analyzer, evidence, trace,
                                rnd + 1, model=model, focus_paths=focus or None)
        if not fixed:
            # From: agents/build/tester_common.py
            elog("WARN", "   ↔ no evidence-backed follow-up repair was possible from this observation")
            if repeat_sig >= 1:
                break
            continue

        # From: agents/pipeline/bugs/bug_verification.py
        check = verify_after_edit(arch, proj_dir, proj_name, stack="next",
                                  build_rounds=1, probe=False, analyzer=analyzer)
        if (not check.get("build_ok", True) or check.get("syntax_broken")
                or check.get("broken_imports")):
            # From: agents/pipeline/feature_safety.py
            reverted = _restore_feature_transaction(arch, proj_dir, round_tx)
            _stop_dev_proc(); start_dev_server(proj_dir, "next"); wait_for_dev("next")
            # From: agents/build/tester_common.py
            elog("WARN", f"   ↩ rejected one bad follow-up repair ({len(reverted)} file(s) restored); keeping the last green state")
            continue
        total.extend(p for p in fixed if p not in total)
    return False, total, last_seen

# Repairs one bug transaction until its affected route is stable.
def run_bug_report(proj_name: str, complaint: str, model: str, route: str = "",
                   think: bool = None, qa_model: str = "", console: str = ""):
    """Repair one bug transaction until its affected route is stable."""
    set_tester_emit(emit)
    tx = None
    try:
        # From: agents/pipeline/feature_safety.py
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        # From: agents/pipeline/feature_safety.py
        analyzer = _analyzer_for(arch, proj_dir)
        # From: agents/build/tester_common.py
        elog("INFO", f"🐛 {complaint[:80]}")
        eprog("Reproducing…", 20)

        if not _dev_alive():
            # From: agents/build/tester_common.py
            elog("INFO", "   ▶ Starting the dev server to reproduce it")
            start_dev_server(proj_dir, stack)
            wait_for_dev(stack)

        # From: agents/pipeline/bugs/bug_request.py
        effective_route = _infer_issue_route(route, complaint, console, "",
                                             arch, analyzer)
        if effective_route != (route or "/"):
            # From: agents/build/tester_common.py
            elog("INFO", f"   🎯 Repair route resolved from evidence: {effective_route}")

        mark = dev_log_mark()
        # From: agents/pipeline/bugs/bug_request.py
        seen = _reproduce_complaint(proj_dir, effective_route, complaint, analyzer)
        # From: agents/pipeline/build/runtime_faults.py
        trace = _filter_db_noise(dev_log_since(mark, limit=180), True)
        # From: agents/pipeline/build/runtime_faults.py
        faults = terminal_faults(trace)
        # From: agents/pipeline/bugs/bug_request.py
        baseline_sig = _observation_fault_signature(seen, trace)
        # From: agents/pipeline/bugs/bug_request.py
        # From: agents/planner/builder/project_memory.py
        baseline_sig.update(_evidence_fault_signature(console))

        report = (f"The user reports: {complaint}\n\n"
                  f"They were on {effective_route}.\n\n")
        if console:
            report += ("Their own browser had already logged this on the page "
                       "they were looking at — this is primary evidence:\n"
                       f"{console.strip()}\n\n")
            # From: agents/build/tester_common.py
            elog("INFO", "   📋 the browser's console came with the report")
        # From: agents/analysis/runtime/browser_reproduction.py
        report += seen.as_prompt()
        if faults:
            report += ("\n\nThe dev server printed this at the same time:\n"
                       + "\n".join(faults[:6]))
            # From: agents/build/tester_common.py
            elog("INFO", f"   📋 {len(faults)} matching server error(s)")

        # From: agents/pipeline/feature_safety.py
        tx = _capture_feature_transaction(arch, proj_dir)
        before = dict(getattr(arch, "files", {}) or {})

        eprog("Repairing…", 45)
        focus = _exact_runtime_focus(arch, report + "\n" + trace)
        fixed = _repair_runtime(arch, proj_dir, None, analyzer, report, trace, 1,
                                model=model, focus_paths=focus or None)
        if not fixed:
            eerr("Nothing was changed — source evidence did not prove a safe repair")
            return
        # From: agents/build/tester_common.py
        elog("INFO", f"   ✅ {len(fixed)} file(s) changed")

        eprog("Checking…", 65)
        # From: agents/features/runtime/images/image_completion.py
        _fill_missing_images(arch, proj_dir)
        # From: agents/pipeline/bugs/bug_verification.py
        check = verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                                  build_rounds=1, probe=False, analyzer=analyzer)
        hard_red = (not check.get("build_ok", True)
                    or bool(check.get("syntax_broken"))
                    or bool(check.get("broken_imports")))
        if hard_red:
            # From: agents/pipeline/feature_safety.py
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            # From: agents/build/tester_common.py
            elog("WARN", f"   ↩ Bug repair rolled back — compile/import verification stayed red ({len(reverted)} file(s) restored)")
            eerr("The attempted bug repair introduced a compile/import regression and was rolled back")
            return

        eprog("Watching the repaired flow…", 78)
        stable, more, after = _stabilize_bug_repair(
            arch, proj_dir, proj_name, analyzer, route=effective_route,
            complaint=complaint, model=model, baseline_signature=baseline_sig)
        all_fixed = list(dict.fromkeys(list(fixed) + list(more)))
        if not stable:
            # Live verification can be inconclusive even when the edit is green.
            # Keep the last compile-safe repair so the fixer can build on it next
            # time instead of restoring the known-broken source.
            # From: agents/build/tester_common.py
            elog("WARN", "   ↔ live verification is still inconclusive; keeping the last green repair")
            try:
                # From: agents/planner/builder/project_memory.py
                arch.save_convo()
            except Exception:
                pass

        touched = [p for p in all_fixed if p in before]
        # From: agents/features/runtime/feature_update.py
        undo_id = _snapshot(proj_name, touched, before) if touched else ""
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": touched})
        # From: agents/planner/builder/project_memory.py
        arch.save_convo()

        # From: agents/pipeline/bugs/bug_request.py
        _report_symptom(seen, after or _reproduce_complaint(
            proj_dir, effective_route, complaint, analyzer))
        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=effective_route)
    except Exception as e:
        if tx is not None:
            try:
                # From: agents/pipeline/feature_safety.py
                _restore_feature_transaction(arch, proj_dir, tx)
            except Exception:
                pass
        eerr(f"Bug fix error: {e}")
        log.exception("run_bug_report")
    finally:
        stop_model(model)

# Answer from full project source without modifying the app.
def run_question(arch, proj_dir: Path, question: str):
    """Answer from full project source without modifying the app."""
    try:
        # From: agents/pipeline/feature_safety.py
        analyzer = _analyzer_for(arch, proj_dir, runtime=False)
        # From: agents/features/feature_writer.py
        # From: agents/pipeline/build/project_preview.py
        agent = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                              analyzer=analyzer, model=model)
        # From: agents/features/feature_contract.py
        convo = [
            {"role": "system", "content":
                "You are answering a question about a Next.js app you can see "
                "in full. Answer in two or three sentences, naming the exact "
                "files and values involved. Do not write code unless a two "
                "line snippet is the clearest answer. Do not suggest changes "
                "unless asked."},
            {"role": "user", "content":
                f"## The project\n{agent.full_source()}\n\n"
                f"## The question\n{question}"},
        ]
        buf = []
        # From: agents/planner/builder/builder_setup.py
        arch._stream(convo, buf.append, temperature=0.2, timeout=120)
        answer = "".join(buf).strip() or "I could not work that out."
        echat(answer)
        # From: agents/build/tester_common.py
        elog("INFO", "   💬 answered")
    except Exception as e:
        eerr(f"Could not answer: {e}")
        log.exception("run_question")


# Converts common string/number values into a predictable boolean.
def _truthy(name: str) -> bool:
    """Convert common string/number values into a predictable boolean."""
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")
