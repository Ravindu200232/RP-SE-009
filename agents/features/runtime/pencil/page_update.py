

# Rewrite the page the user is looking at, and nothing else. The general update path hands the model an 18-file
# snapshot and lets it choose what to touch. When the user is looking at one page and describing what they want it
# to look like, that is both slower and less accurate than handing over that page in full — and it is the
# difference between "change the layout of this page" and an edit that lands in a shared component and changes
# four other screens. Behaviour is fenced off in the prompt rather than by scope: the file may change as much as
# the request needs, but the routes, entities, functions, exports and props it defines may not.
def run_page_update(proj_name: str, instruction: str, model: str, route: str,
                    think: bool = None):
    """
    Rewrite the page the user is looking at, and nothing else.

    The general update path hands the model an 18-file snapshot and lets it
    choose what to touch. When the user is looking at one page and describing
    what they want it to look like, that is both slower and less accurate than
    handing over that page in full — and it is the difference between "change
    the layout of this page" and an edit that lands in a shared component and
    changes four other screens.

    Behaviour is fenced off in the prompt rather than by scope: the file may
    change as much as the request needs, but the routes, entities, functions,
    exports and props it defines may not.
    """
    set_tester_emit(emit)
    try:
        # From: agents/pipeline/feature_safety.py
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        # From: agents/pipeline/feature_safety.py
        analyzer = _analyzer_for(arch, proj_dir)
        # From: agents/features/runtime/pencil/pencil_workflow.py
        path = _page_file_for(arch, analyzer, route)
        if not path or path not in arch.files:
            # From: agents/build/tester_common.py
            elog("INFO", f"   ↪ {route or '/'} is not one page — planning it "
                         f"as a change instead")
            # From: agents/features/runtime/feature_update.py
            return run_feature(proj_name, instruction, model, think)

        before = arch.files[path]
        # From: agents/build/tester_common.py
        elog("INFO", f"📄 Page update — {route or '/'} → {path}")
        eprog("Rewriting the page…", 35)
        ephase({"phase": -20, "title": f"Rewriting {route or '/'}",
                "status": "active"})

        # From: agents/features/runtime/selection/selection_scope.py
        near = _neighbours(arch, path, before)
        # From: agents/features/runtime/selection/selection_scope.py
        chain = _layout_chain(arch, path)

        # From: agents/features/runtime/selection/selection_scope.py
        chrome = "\n\n".join(f"--- {p} ({_reach_label(arch, p, route)}) ---\n{b}"
                             for p, b in chain)
        # From: agents/features/runtime/selection/selection_scope.py
        pmap = _project_map(arch)
        user = ((f"{pmap}\n\n" if pmap else "")
                + f"## The page\nRoute: {route or '/'}\nFile: {path}\n\n"
                f"## What the user wants\n{instruction}\n\n"
                f"DO NOT CHANGE: api routes, entities, functions. The routes "
                f"stay at the same paths with the same methods and the same "
                f"request and response shapes. The data entities keep their "
                f"fields and their names. Every function keeps its name, its "
                f"parameters and what it does.\n\n"
                f"Everything else on this page is yours: the layout, the copy, "
                f"the animation, the whole design if that is what they asked "
                f"for — including removing a section if they asked for that. "
                f"Only what they did not mention stays exactly as it is.\n\n"
                f"## The COMPLETE current source of {path}\n{before}"
                + (f"\n\n## The components it renders, so you can match "
                   f"them\n{near}" if near else "")
                + (f"\n\n## The layout wrapping this route, and what it renders"
                   f"\nThe navbar, header, footer and page shell live HERE, not "
                   f"in the page — Next composes the layout around it, so the "
                   f"page's own source will not mention them. If what was asked "
                   f"for is one of those, rewrite the file below that actually "
                   f"contains it and leave the page alone.\n\n"
                   f"A layout wraps EVERY route beneath it. Removing a navbar "
                   f"from the root layout removes it from the whole site, which "
                   f"is almost never what one page's request meant. Each file "
                   f"below says how many routes it is on — read that before "
                   f"you touch it.\n\n"
                   f"### Taking chrome off THIS route only\n"
                   f"A nested layout does NOT do it. `app/…/layout.jsx` renders "
                   f"INSIDE the root layout, so anything the root renders is "
                   f"still there — this was the advice here before and it "
                   f"cannot work. What works:\n"
                   f"  1. Move the markup into a small component under "
                   f"`components/` with `'use client'` on line 1.\n"
                   f"  2. In it, `const pathname = usePathname()` from "
                   f"`next/navigation`, and `return null` for the routes it "
                   f"should not appear on.\n"
                   f"  3. Render that component from the layout in place of "
                   f"the markup you moved.\n"
                   f"Do NOT put `'use client'` on the root layout — it exports "
                   f"`metadata` and owns `<html>`/`<body>`, and both stop "
                   f"working in a client component. A nested layout is still "
                   f"the right answer for ADDING chrome to one route.\n\n"
                   f"{chrome}"
                   if chrome else ""))
        arch._workspace_tool_cache = {}
        convo = [{"role": "system", "content": PAGE_UPDATE_SYSTEM + "\n\n" + TOOL_HELP},
                 {"role": "user", "content": user}]

        mark = dev_log_mark()

        writable = {path} | {p for p, _ in chain}
        writable.add("/".join(path.split("/")[:-1]) + "/layout.jsx")
        got, raw = {}, []

        # Measure and return how long the current pencil/page-update operation has taken.
        def took(pth, content):

            """Prepare the took value or state used by this focused pipeline step."""
            key = (pth or "").strip().lstrip("./").replace("\\", "/")

            fresh = (key.startswith("components/")
                     and key.endswith((".jsx", ".js"))
                     and key not in arch.files)
            if key not in writable and not fresh:
                # From: agents/build/tester_common.py
                elog("WARN", f"   ⛔ ignored a write to {key} — this edit may "
                             f"only touch {', '.join(sorted(writable))}, or a "
                             f"new file under components/")
                return
            if fresh:
                # From: agents/build/tester_common.py
                elog("INFO", f"   ➕ {key} — new component for this route's "
                             f"chrome")
            got[key] = content

        # From: agents/planner/builder/write_stream.py
        parser = FileStreamParser(
            on_text=lambda t: None, on_file_start=lambda pth: None,
            on_file_token=lambda t: None,
            on_file_end=took)

        # Accepts another streamed model chunk and emit any complete file blocks.
        def feed(tok):
            """Accept another streamed model chunk and emit any complete file blocks."""
            raw.append(tok)
            # From: agents/planner/builder/write_stream.py
            parser.feed(tok)

        t0 = time.time()
        try:
            for tool_turn in range(3):
                turn_raw = []
                # Sends one model turn, collect its streamed output, and pass each chunk to the active writer/parser.
                def feed_turn(tok):
                    """Prepare the feed turn value or state used by this focused pipeline step."""
                    turn_raw.append(tok)
                    feed(tok)
                # From: agents/planner/builder/builder_setup.py
                arch._stream(convo, feed_turn, temperature=0.3, timeout=arch.EDIT_TIMEOUT)
                reply = "".join(turn_raw)
                convo.append({"role": "assistant", "content": reply})
                # From: agents/core/workspace/source_workspace.py
                observations, used = WorkspaceTools(arch).serve(reply)
                if used and not got and tool_turn < 2:
                    # From: agents/build/tester_common.py
                    elog("INFO", f"   🧰 page editor inspected {used} workspace tool(s)")
                    convo.append({"role": "user", "content":
                                  "Tool observations:\n\n" + observations +
                                  "\n\nContinue the same page edit and write the minimum complete file set."})
                    continue
                break
        except Exception as e:
            eerr(f"The model failed: {e}")
            return
        # From: agents/planner/builder/write_stream.py
        parser.close()
        # From: agents/build/tester_common.py
        elog("INFO", f"   ⏱ model {time.time() - t0:.1f}s")

        # From: agents/planner/builder/build_validation.py
        for out in arch.run_requested_commands("".join(raw)):
            # From: agents/build/tester_common.py
            elog("INFO", f"   📦 {out.splitlines()[0][:110]}")

        if not got:
            head = " ".join("".join(raw).split())[:300] or "(empty response)"
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ no <write_file> block — model said: {head}")
            if _DECLINED_RE.search("".join(raw)):
                eerr(f"Nothing was changed — the model said: {head[:220]}")
                return False, ""
            eerr(f"The model returned no file. It said: {head[:220]}")
            return

        olds, keep = {}, {}
        for key, content in got.items():
            was = arch.files.get(key, "")
            # From: agents/features/selection_rules.py
            why = guard_scope(was, content, designing=True) if was else ""
            if why:
                # From: agents/build/tester_common.py
                elog("WARN", f"   ⛔ Rejected {key}: {why[:120]}")
                continue
            olds[key] = was
            keep[key] = content
        if not keep:
            eerr("The rewrite was rejected — nothing was written")
            return

        # From: agents/features/runtime/feature_update.py
        undo_id = _snapshot(proj_name, list(keep), olds)
        for key, content in keep.items():
            # From: agents/planner/builder/file_writer.py
            arch.write_file(key, content)
            estream_start(key)
            estream_end(key, content)
            if key != path:
                # From: agents/build/tester_common.py
                elog("INFO", f"   📐 {key} — the chrome lives here, not in "
                             f"{path}")
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": list(keep)})
        ephase({"phase": -20, "title": f"Rewriting {route or '/'}",
                "status": "done", "written": len(keep)})
        # From: agents/planner/builder/project_memory.py
        arch.save_convo()

        eprog("Checking the page…", 75)
        t1 = time.time()
        # From: agents/features/runtime/images/image_completion.py
        _fill_missing_images(arch, proj_dir)
        # From: agents/pipeline/bugs/bug_verification.py
        verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                          build_rounds=0, probe=False, analyzer=analyzer)
        # From: agents/features/runtime/selection/selection_repair.py
        _autofix_from_terminal(arch, path, {"route": route}, mark,
                               proj_dir=proj_dir, analyzer=analyzer, model=model)
        # From: agents/build/tester_common.py
        elog("INFO", f"   ⏱ verify {time.time() - t1:.1f}s")

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of({"route": route}))
    except Exception as e:
        eerr(f"Page update error: {e}")
        log.exception("run_page_update")
    finally:
        stop_model(model)


# Agentic edit of an existing project — same write_file loop.
def run_agent_update(proj_name: str, instruction: str, model: str,
                     think: bool = None):
    """Agentic edit of an existing project — same write_file loop."""
    set_tester_emit(emit)
    try:
        # From: agents/pipeline/feature_safety.py
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        # From: agents/build/tester_common.py
        elog("INFO", f"✏️  Agent update ({stack}) — {instruction[:70]}")
        eprog("Reading project…", 10)

        eprog("Applying changes…", 35)
        # From: agents/planner/builder/project_memory.py
        n = arch.update(instruction)
        if not n:
            eerr("Agent made no changes")
            return
        # From: agents/build/tester_common.py
        elog("INFO", f"   ✅ {n} file(s) updated")

        # From: agents/planner/builder/project_memory.py
        arch.save_convo()

        eprog("Verifying…", 80)
        # From: agents/features/runtime/images/image_completion.py
        _fill_missing_images(arch, proj_dir)
        # From: agents/pipeline/bugs/bug_verification.py
        res = verify_after_edit(arch, proj_dir, proj_name, stack=stack)
        if res["routes_failed"]:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ {len(res['routes_failed'])} route(s) still "
                         f"failing: {'; '.join(res['routes_failed'][:3])}")

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name)
    except Exception as e:
        eerr(f"Agent update error: {e}")
        log.exception("Agent update error")
    finally:
        stop_model(model)
