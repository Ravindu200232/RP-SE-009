

# Ask for the rewrite; reject anything that overran and retry once.
def _element_write_round(arch, path, before, instruction, element, anchor,
                         removing, adding=False, retexting=False, attempts=2,
                         line=0, context=None, shared_routes=None):
    """Ask for the rewrite; reject anything that overran and retry once."""
    # From: agents/features/runtime/selection/selection_scope.py
    near = _neighbours(arch, path, before)
    # From: agents/features/runtime/selection/selection_scope.py
    span = _section_span(element)
    # From: agents/features/runtime/selection/selection_scope.py
    where = _where_in_file(before, element, line)
    ctx = context or {}
    proof = (f"## Analyzer change contract\nCurrent: {ctx.get('current') or '(not recorded)'}\n"
             f"Gap: {ctx.get('gap') or instruction}\nOwnership: {ctx.get('cause') or path}\n"
             f"Verify: {ctx.get('verify') or 'the exact selected change works without regressions'}\n"
             f"Shared route reach: {', '.join(shared_routes or []) or element.get('route', '/')}\n\n")
    # From: agents/features/runtime/selection/selection_repair.py
    # From: agents/features/selection_rules.py
    user = (proof + f"## The element the user clicked\n{describe(element)}\n\n"
            + (f"## Where it is\n{where}\n\n" if where else "")
            + (f"## The section they selected — it runs from the first of "
               f"these to the second\n{span}\n\n" if span else "")
            + f"Route: {element.get('route', '/')}\n\n"
            + f"## What they want\n{instruction}\n\n"
            + _edit_rules(adding)
            + f"## The complete current source of {path}\n{before}"
            + (f"\n\n## The files this one is joined to — what it "
               f"renders, and what renders it\n{near}" if near else ""))
    arch._workspace_tool_cache = {}
    convo = [{"role": "system", "content": ELEMENT_EDIT_SYSTEM + "\n\n" + TOOL_HELP},
             {"role": "user", "content": user}]

    for attempt in range(1, attempts + 1):
        got = {"writes": {}}

        # Captures write so the next step can work from real evidence.
        def capture_write(out_path, content):
            """Capture write so the next step can work from real evidence."""
            key = str(out_path or "").replace("\\", "/").lstrip("./")
            if key:
                got["writes"][key] = content

        # From: agents/planner/builder/write_stream.py
        parser = FileStreamParser(
            on_text=lambda t: None,
            on_file_start=lambda p: None,
            on_file_token=lambda t: None,
            on_file_end=capture_write)
        buf = []

        # Accepts another streamed model chunk and emit any complete file blocks.
        def feed(tok):
            """Accept another streamed model chunk and emit any complete file blocks."""
            buf.append(tok)
            # From: agents/planner/builder/write_stream.py
            parser.feed(tok)

        try:
            reply = ""
            seen_observations = set()
            while True:
                turn_buf = []
                # Sends one model turn, collect its streamed output, and pass each chunk to the active writer/parser.
                def feed_turn(tok):
                    """Prepare the feed turn value or state used by this focused pipeline step."""
                    turn_buf.append(tok)
                    feed(tok)
                # From: agents/planner/builder/builder_setup.py
                arch._stream(convo, feed_turn, temperature=0.3,
                             timeout=arch.EDIT_TIMEOUT)
                reply = "".join(turn_buf)
                convo.append({"role": "assistant", "content": reply})
                # From: agents/core/workspace/source_workspace.py
                observations, used = WorkspaceTools(arch).serve(reply)
                if used and not got["writes"]:
                    sig = observations.strip()
                    used_chars = sum(len(str(m.get("content", ""))) for m in convo)
                    try:
                        budget_chars = int(arch._budget_chars())
                    except Exception:
                        budget_chars = 0
                    if sig and sig not in seen_observations and (not budget_chars or used_chars < budget_chars * 0.82):
                        seen_observations.add(sig)
                        # From: agents/build/tester_common.py
                        elog("INFO", f"   🧰 section editor inspected {used} workspace tool(s)")
                        convo.append({"role": "user", "content":
                                      "Tool observations:\n\n" + observations +
                                      "\n\nContinue the same selected-element edit. Follow dependencies as far as needed; do not repeat a tool call."})
                        continue
                    if sig in seen_observations:
                        # From: agents/build/tester_common.py
                        elog("WARN", "   ↔ section editor repeated the same inspection — deciding with current evidence")
                break
        except Exception as e:
            eerr(f"The model failed: {e}")
            return False, ""
        # From: agents/planner/builder/write_stream.py
        parser.close()

        full_reply = "".join(buf)
        # From: agents/planner/builder/build_validation.py
        for out in arch.run_requested_commands(full_reply):
            # From: agents/build/tester_common.py
            elog("INFO", f"   📦 {out.splitlines()[0][:110]}")

        need = re.search(r"^\s*NEED\s+(\S+)\s*$", reply, re.M)
        if need and not got["writes"]:
            needed = need.group(1).strip('`')
            # From: agents/build/tester_common.py
            elog("INFO", f"   ↗ focused editor discovered dependency {needed} — escalating automatically")
            return False, "__AGENTFORGE_ESCALATE__:" + needed

        writes = got["writes"]
        body = writes.get(path, "")
        external = [rel for rel in writes if rel != path]
        if external:
            names = ",".join(external[:8])
            # From: agents/build/tester_common.py
            elog("INFO", "   ↗ focused editor emitted dependency write(s) — "
                         f"escalating transaction: {names}")
            return False, "__AGENTFORGE_ESCALATE__:" + names
        if writes and not body:
            only = ",".join(list(writes)[:8])
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ focused editor wrote {only}, not selected owner {path} — escalating")
            return False, "__AGENTFORGE_ESCALATE__:" + only
        if not body:

            head = " ".join(reply.split())[:300] or "(empty response)"

            if _DECLINED_RE.search(reply):
                # From: agents/build/tester_common.py
                elog("INFO", f"   ✅ Nothing to change — {head[:160]}")
                eerr("That element is not on this page — nothing was changed")
                return False, ""
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ no <write_file> block — model said: {head}")
            if attempt < attempts:
                convo.append({"role": "user", "content":
                    "That was not a file. Output the COMPLETE file inside "
                    f"one <write_file path=\"{path}\">…</write_file> block, "
                    "starting immediately with '<write_file'. No markdown "
                    "fences, no explanation, no summary."})
                continue

            # What it said, not only that it said nothing usable.
            eerr(f"The model returned no file after {attempts} attempts. "
                 f"It said: {head[:220]}")
            return False, ""

        why = None
        if not body.strip():
            why = "the rewrite is empty"
        else:
            if len(body) < 0.5 * len(before):
                # From: agents/build/tester_common.py
                elog("INFO", f"   ✂ the file goes from {len(before)} to "
                             f"{len(body)} characters — writing it as asked")
            return True, body

        # From: agents/build/tester_common.py
        elog("WARN", f"   ⛔ Rejected: {why[:110]}")
        if attempt == attempts:
            eerr("The edit changed far more than the element — nothing was "
                 "written")
            return False, ""
        convo.append({"role": "assistant", "content": reply[:2000]})
        convo.append({"role": "user", "content":
            f"That rewrite was rejected: {why}\n\nTry again. Output the "
            f"COMPLETE file, byte-identical to the original except for the "
            f"element described above."})
    return False, ""

# Selection apply flow: prove ownership -> edit -> verify -> rollback if needed.
# Re-read a focused edit and close only source-proven remaining gaps.
def _converge_visual_semantics(arch, analyzer, proj_dir, request: str,
                               spec, path: str, route: str, element: dict,
                               model: str):
    """Re-read a focused edit and close only source-proven remaining gaps."""
    # From: agents/features/feature_writer.py
    # From: agents/pipeline/build/project_preview.py
    agent = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                          analyzer=analyzer, model=model)
    if spec is None:
        # From: agents/features/feature_contract.py
        spec = FeatureSpec(summary=request, files=[{
            "path": path, "action": "edit", "kind": "",
            "why": "visual selection resolved to this source file",
        }], context={})
    spec.written = list(dict.fromkeys((getattr(spec, "written", []) or []) + [path]))
    ctx = spec.context or {}
    ctx.setdefault("current", "focused visual edit was applied to the resolved source owner")
    ctx.setdefault("gap", request)
    ctx.setdefault("cause", f"visual resolver and preflight identified {path} as the owner candidate")
    ctx.setdefault("evidence", [{"path": path,
                                  "fact": "selected region resolved to this current source file"}])
    ctx.setdefault("verify", "current source must implement the exact visual request without breaking its dependencies")
    ctx.setdefault("confidence", "medium")
    spec.context = ctx
    # From: agents/features/feature_checker.py
    # From: agents/features/selection_rules.py
    return agent.converge_semantics(
        request, spec, selected_path=path, selected_route=route,
        selected_element=describe(element or {}), rounds=2)

# Edit selected UI locally or escalate when dependencies require it.
def run_element_edit(proj_name: str, instruction: str, element: dict,
                     model: str, think: bool = None, console: str = ""):
    """Edit selected UI locally or escalate when dependencies require it."""
    set_tester_emit(emit)
    try:
        # From: agents/pipeline/feature_safety.py
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        # From: agents/pipeline/feature_safety.py
        analyzer = _analyzer_for(arch, proj_dir)
        # From: agents/features/element_selector.py
        resolver = ElementResolver(arch, analyzer)

        # From: agents/build/tester_common.py
        # From: agents/features/selection_rules.py
        elog("INFO", f"🎯 {describe(element).splitlines()[0][:90]}")
        eprog("Finding the code…", 15)
        t_resolve = time.time()
        # From: agents/features/element_selector.py
        res = resolver.resolve(element)
        # From: agents/build/tester_common.py
        elog("INFO", f"   ⏱ resolve {time.time() - t_resolve:.1f}s")
        if not res.path:
            eerr(f"Could not find the code for that element — {res.reason}")
            return
        # From: agents/build/tester_common.py
        elog("INFO", f"   📍 {res.path}:{res.line or '?'} "
                     f"({'model chose' if res.used_model else 'unambiguous'})")
        # From: agents/features/runtime/selection/selection_scope.py
        shared = _shared_routes(arch, res.path)
        emit({"type": "element_picked", "file": res.path, "line": res.line,
              "score": res.score, "candidates": res.candidates[:6],
              "used_model": res.used_model, "shared_routes": shared[:12]})
        page_route = _route_of(element)

        # From: agents/features/runtime/selection/selection_scope.py
        _log_reach(res.path, shared, page_route)

        before = arch.files.get(res.path, "")
        if not before:
            eerr(f"{res.path} is empty or unreadable")
            return
        before_project = dict(arch.files)
        # From: agents/pipeline/feature_safety.py
        tx = _capture_feature_transaction(arch, proj_dir)
        try:
            # From: agents/analysis/checks/scan_state.py
            # From: agents/pipeline/feature_safety.py
            baseline_keys = _feature_baseline_keys(analyzer.scan())
        except Exception:
            baseline_keys = set()

        # From: agents/features/runtime/image_edit.py
        broaden, change_request, impact = _visual_change_preflight(
            arch, analyzer, proj_dir, instruction, element, res.path,
            page_route, model)
        if broaden:
            count = len(getattr(impact, "files", []) or [])
            # From: agents/build/tester_common.py
            elog("INFO", f"   ↗ selected-region change spans {count} source file(s) — switching to full agentic change")
            # From: agents/features/runtime/feature_update.py
            return run_feature(proj_name, change_request, model, think, unit_tests=False)

        anchor = (element.get("text") or "").strip()[:60]
        # From: agents/features/selection_rules.py
        removing = looks_like_removal(instruction)
        # From: agents/features/selection_rules.py
        adding = looks_like_addition(instruction)
        # From: agents/features/selection_rules.py
        retexting = looks_like_retext(instruction)

        eprog("Editing…", 40)
        ephase({"phase": -11, "title": "Editing the element", "status": "active"})

        mark = dev_log_mark()
        t_write = time.time()
        ok, written = _element_write_round(arch, res.path, before, instruction,
                                           element, anchor, removing, adding,
                                           retexting, line=res.line,
                                           context=getattr(impact, 'context', {}) or {},
                                           shared_routes=shared)
        # From: agents/build/tester_common.py
        elog("INFO", f"   ⏱ model {time.time() - t_write:.1f}s")
        if not ok:
            ephase({"phase": -11, "title": "Editing the element", "status": "done"})
            if isinstance(written, str) and written.startswith("__AGENTFORGE_ESCALATE__:"):
                needed = written.split(":", 1)[1]
                change_request = (
                    f"On route {page_route or '/'} the user selected UI rendered by {res.path}. "
                    f"Source inspection showed that {needed} is also required.\n\n"
                    f"Requested change:\n{instruction}\n\n"
                    "Implement the complete dependency-aware change across every necessary file, then verify it."
                )
                # From: agents/features/runtime/feature_update.py
                return run_feature(proj_name, change_request, model, think, unit_tests=False)
            return

        # From: agents/planner/builder/file_writer.py
        if not arch.write_file(res.path, written):
            eerr(f"Could not write {res.path}")
            return
        estream_start(res.path)
        estream_end(res.path, written)

        impact = _converge_visual_semantics(
            arch, analyzer, proj_dir, instruction, impact, res.path,
            page_route, element, model)
        touched = list(dict.fromkeys(getattr(impact, "written", []) or [res.path]))
        # From: agents/features/runtime/feature_update.py
        undo_id = _snapshot(proj_name, touched, before_project)
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": touched})
        ephase({"phase": -11, "title": "Editing the element", "status": "done",
                "written": len(touched)})

        eprog("Verifying…", 75)
        t_verify = time.time()

        # From: agents/features/runtime/images/image_completion.py
        _fill_missing_images(arch, proj_dir)
        # From: agents/pipeline/bugs/bug_verification.py
        verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                          build_rounds=0, probe=False, analyzer=analyzer)
        # From: agents/features/runtime/selection/selection_repair.py
        _autofix_from_browser_console(
            arch, res.path, console, proj_dir=proj_dir, analyzer=analyzer,
            model=model, route=page_route)
        # From: agents/features/runtime/selection/selection_repair.py
        _autofix_from_terminal(arch, res.path, element, mark,
                               proj_dir=proj_dir, analyzer=analyzer, model=model)
        # From: agents/pipeline/bugs/bug_verification.py
        final = verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                                  build_rounds=1, probe=False, analyzer=analyzer)
        red = (not final.get("build_ok", True) or bool(final.get("syntax_broken"))
               or bool(final.get("broken_imports")))
        # From: agents/pipeline/bugs/bug_request.py
        # From: agents/pipeline/feature_safety.py
        stable, _, _ = _stabilize_feature_upgrade(
            arch, proj_dir, analyzer, baseline_keys=baseline_keys,
            before_files=tx["files"], db_ok=db_ok(),
            declared_routes=getattr(impact, "routes", []) or [], route_hint=page_route)
        if red or not stable:
            # From: agents/pipeline/feature_safety.py
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            # From: agents/build/tester_common.py
            elog("WARN", f"   ↩ Selection rolled back after live verification ({len(reverted)} file(s))")
            eerr("The selected edit could not keep the app runtime-clean, so the previous working state was restored")
            return
        # From: agents/build/tester_common.py
        elog("INFO", f"   ⏱ verify {time.time() - t_verify:.1f}s")
        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(element))
    except Exception as e:
        eerr(f"Element edit error: {e}")
        log.exception("run_element_edit")
    finally:
        stop_model(model)
