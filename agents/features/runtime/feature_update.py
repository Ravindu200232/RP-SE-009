# Feature flow: understand -> scope -> apply -> test -> refresh the preview.
# Apply, verify, stabilize, and test one dependency-aware change.
def run_feature(proj_name: str, request: str, model: str, think: bool = None,
                qa_model: str = "", route: str = "", console: str = "",
                unit_tests: bool = True):
    """Apply, verify, stabilize, and test one dependency-aware change."""
    set_tester_emit(emit)
    try:
        # From: agents/pipeline/feature_safety.py
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        # From: agents/build/tester_common.py
        elog("INFO", f"🧩 Feature — {request[:70]}")
        if arch.convo:
            # From: agents/build/tester_common.py
            elog("INFO", f"   🧠 Remembering the build ({len(arch.convo)} turns)")
        eprog("Planning…", 15)

        # From: agents/pipeline/feature_safety.py
        analyzer = _analyzer_for(arch, proj_dir)
        # From: agents/features/feature_writer.py
        # From: agents/pipeline/build/project_preview.py
        agent = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                              analyzer=analyzer, model=model)
        # From: agents/pipeline/bugs/bug_request.py
        agent.route_hint = _infer_issue_route(route, request, "", "", arch, analyzer)
        if agent.route_hint and agent.route_hint != "/":
            # From: agents/build/tester_common.py
            elog("INFO", f"   🎯 Feature anchored to current route {agent.route_hint}")

        # From: agents/pipeline/feature_safety.py
        tx = _capture_feature_transaction(arch, proj_dir)
        before = dict(tx["files"])
        try:
            # From: agents/analysis/checks/scan_state.py
            # From: agents/pipeline/feature_safety.py
            baseline_keys = _feature_baseline_keys(analyzer.scan())
        except Exception as e:
            log.debug(f"feature baseline scan: {e}")
            baseline_keys = set()

        eprog("Writing…", 40)
        spec = agent.run(request)
        if not spec.written:
            eerr("The feature agent changed nothing")
            return
        # From: agents/build/tester_common.py
        elog("INFO", f"   ✅ {len(spec.written)} file(s) written")
        if spec.rejected:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⛔ {len(spec.rejected)} unsafe/invalid write(s) were rejected")

        touched = [p for p in spec.written if p in before]
        undo_id = _snapshot(proj_name, touched, before) if touched else ""
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": touched})

        # From: agents/planner/builder/project_memory.py
        arch.save_convo()

        if console:
            # From: agents/features/runtime/selection/selection_repair.py
            _autofix_from_browser_console(
                arch, spec.written[0] if spec.written else "", console,
                proj_dir=proj_dir, analyzer=analyzer, model=model,
                route=getattr(agent, "route_hint", "") or route)

        # From: agents/pipeline/bugs/bug_request.py
        if any(f.endswith("lib/seed.js") for f in spec.written) and db_ok():
            try:
                # From: agents/data/database_records.py
                r = MONGO.reset_project_db(proj_dir, node_bin=NODE_BIN)
                if r.get("dropped"):
                    # From: agents/build/tester_common.py
                    elog("INFO", f"   🧹 The seed changed — cleared {r['db']} "
                                 f"({r['dropped']} collection(s)) so it runs "
                                 f"again with the new shape")
            except Exception as e:
                # From: agents/build/tester_common.py
                elog("WARN", f"   ⚠ Could not re-seed after the seed changed: "
                             f"{e}. Records written before this feature will "
                             f"not have its new fields.")

        eprog("Verifying…", 65)
        # From: agents/features/feature_prompts.py
        image_request = feature_image_requested(request)
        if image_request:
            # From: agents/build/tester_common.py
            elog("INFO", "   🎨 feature requested visual media — using Fooocus for missing generated assets")
        # From: agents/features/runtime/images/image_completion.py
        _fill_missing_images(arch, proj_dir, "the requested feature",
                             explicit_request=image_request)
        # From: agents/pipeline/bugs/bug_verification.py
        res = verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                                probe=False, analyzer=analyzer)
        if res["routes_failed"]:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ {len(res['routes_failed'])} route(s) still "
                         f"failing")

        hard_red = (not res["build_ok"] or bool(res.get("syntax_broken"))
                    or bool(res.get("broken_imports")))
        if hard_red:
            # From: agents/pipeline/feature_safety.py
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            # From: agents/build/tester_common.py
            elog("WARN", f"   ↩ Feature rolled back — verification stayed red "
                         f"({len(reverted)} file(s) restored)")
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            eerr("The feature introduced a compile/import regression, so it was rolled back automatically")
            return

        eprog("Watching the live app…", 78)
        # From: agents/pipeline/bugs/bug_request.py
        # From: agents/pipeline/feature_safety.py
        stable, repaired, _live_report = _stabilize_feature_upgrade(
            arch, proj_dir, analyzer, baseline_keys=baseline_keys,
            before_files=before, db_ok=db_ok(), declared_routes=spec.routes,
            route_hint=getattr(agent, "route_hint", ""))
        if not stable:
            # From: agents/pipeline/feature_safety.py
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            try:
                # From: agents/planner/builder/project_memory.py
                arch.save_convo()
            except Exception:
                pass
            # From: agents/build/tester_common.py
            elog("WARN", f"   ↩ Feature rolled back after live regression "
                         f"({len(reverted)} file(s) restored)")
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            eerr("The feature caused live regressions that could not be stabilized, so the working app was restored")
            return

        if repaired:
            # From: agents/pipeline/feature_safety.py
            for path in sorted(_feature_changed_paths(before, arch)):
                if path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")) and path not in spec.written:
                    spec.written.append(path)
            # From: agents/build/tester_common.py
            elog("INFO", f"   🛠 Live watch repaired {repaired} file write(s) before feature QA")

        eprog("Testing the feature…", 88)
        if unit_tests:
            _feature_tests(arch, proj_dir, spec, model, qa_model, build_ok=True)
        else:
            # From: agents/build/tester_common.py
            elog("INFO", "   🩺 Visual edit uses runtime verification only")

        eprog("Final live watch…", 95)
        # From: agents/pipeline/bugs/bug_verification.py
        final_check = verify_after_edit(
            arch, proj_dir, proj_name, stack=stack, build_rounds=1,
            probe=False, analyzer=analyzer)
        final_red = (not final_check.get("build_ok", True)
                     or bool(final_check.get("syntax_broken"))
                     or bool(final_check.get("broken_imports")))
        if final_red:
            # From: agents/pipeline/feature_safety.py
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            # From: agents/build/tester_common.py
            elog("WARN", f"   ↩ Feature rolled back at final commit gate ({len(reverted)} file(s) restored)")
            eerr("The feature became red after QA, so the previous working app was restored")
            return

        # From: agents/pipeline/bugs/bug_request.py
        # From: agents/pipeline/feature_safety.py
        final_stable, final_repairs, _ = _stabilize_feature_upgrade(
            arch, proj_dir, analyzer, baseline_keys=baseline_keys,
            before_files=before, db_ok=db_ok(), declared_routes=spec.routes,
            route_hint=getattr(agent, "route_hint", ""))
        if not final_stable:
            # From: agents/pipeline/feature_safety.py
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            try:
                # From: agents/planner/builder/project_memory.py
                arch.save_convo()
            except Exception:
                pass
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            # From: agents/build/tester_common.py
            elog("WARN", f"   ↩ Feature rolled back after final Next/browser watch ({len(reverted)} file(s) restored)")
            eerr("A live regression appeared after feature QA and could not be stabilized, so the feature was rolled back")
            return
        if final_repairs:
            # From: agents/build/tester_common.py
            elog("INFO", f"   🛠 Final live watch repaired {final_repairs} additional file write(s)")

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=getattr(agent, "route_hint", "") or "/")
    except Exception as e:
        eerr(f"Feature error: {e}")
        log.exception("run_feature")
    finally:
        stop_model(model)




UNDO_DIR = LOGS_DIR / "undo"


# Copy rewritten files to the external undo store.
def _snapshot(proj_name: str, paths, files: dict) -> str:
    """Copy rewritten files to the external undo store."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = UNDO_DIR / proj_name / stamp
    saved = 0
    for rel in paths:
        body = files.get(rel)
        if body is None:
            continue
        fp = base / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(body, encoding="utf-8")
        saved += 1
    return stamp if saved else ""


# Restore snapshot.
def restore_snapshot(proj_name: str, stamp: str = "") -> dict:
    """Restore snapshot safely without changing unrelated project behavior."""
    base = UNDO_DIR / proj_name
    if not base.is_dir():
        return {"ok": False, "error": "nothing to undo"}
    if not stamp:
        stamps = sorted(p.name for p in base.iterdir() if p.is_dir())
        if not stamps:
            return {"ok": False, "error": "nothing to undo"}
        stamp = stamps[-1]
    src = base / stamp
    if not src.is_dir():
        return {"ok": False, "error": f"no snapshot {stamp}"}
    proj_dir = PROD_DIR / proj_name
    restored = []
    for fp in src.rglob("*"):
        if not fp.is_file():
            continue
        rel = fp.relative_to(src).as_posix()
        dest = proj_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(fp.read_text(encoding="utf-8"), encoding="utf-8")
        restored.append(rel)
    return {"ok": True, "restored": restored, "id": stamp}
