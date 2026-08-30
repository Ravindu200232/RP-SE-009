

# Redesign the region the user drew over. The image is captured server-side: a browser cannot rasterise an iframe
# from the parent document, so same-origin buys DOM access for the picker and nothing at all for pixels. `think`
# is a real parameter now. Both dispatchers have always passed five arguments and the body has always read
# `think`, so every pencil edit raised TypeError on the first line inside the `try` and surfaced as "Pencil edit
# error" — the tool has never once run. Defaulted so a four-argument caller keeps working.
def run_pencil_edit(proj_name: str, instruction: str, payload: dict,
                    model: str, think=None):
    """
    Redesign the region the user drew over.

    The image is captured server-side: a browser cannot rasterise an iframe from
    the parent document, so same-origin buys DOM access for the picker and
    nothing at all for pixels.

    `think` is a real parameter now. Both dispatchers have always passed five
    arguments and the body has always read `think`, so every pencil edit raised
    TypeError on the first line inside the `try` and surfaced as "Pencil edit
    error" — the tool has never once run. Defaulted so a four-argument caller
    keeps working.
    """
    set_tester_emit(emit)
    element = payload.get("element") or {}
    try:
        # From: agents/pipeline/feature_safety.py
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        # From: agents/pipeline/feature_safety.py
        analyzer = _analyzer_for(arch, proj_dir)
        # From: agents/features/element_selector.py
        resolver = ElementResolver(arch, analyzer)

        route = payload.get("route") or element.get("route") or "/"
        eprog("Finding the code…", 12)
        # From: agents/features/element_selector.py
        res = resolver.resolve({**element, "route": route})
        if not res.path:
            eerr(f"Could not find the code for that region — {res.reason}")
            return
        # From: agents/build/tester_common.py
        elog("INFO", f"   📍 {res.path}:{res.line or '?'}")
        # From: agents/features/runtime/selection/selection_scope.py
        shared = _shared_routes(arch, res.path)
        emit({"type": "element_picked", "file": res.path, "line": res.line,
              "score": res.score, "candidates": res.candidates[:6],
              "used_model": res.used_model, "shared_routes": shared[:12]})
        # From: agents/features/runtime/selection/selection_scope.py
        _log_reach(res.path, shared, route)

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
            arch, analyzer, proj_dir, instruction, element, res.path, route, model)
        if broaden:
            count = len(getattr(impact, "files", []) or [])
            # From: agents/build/tester_common.py
            elog("INFO", f"   ↗ pencil change spans {count} source file(s) — switching to full agentic change")
            # From: agents/features/runtime/feature_update.py
            return run_feature(proj_name, change_request, model, think, unit_tests=False)

        # From: agents/features/runtime/pencil/pencil_writer.py
        vis_model = _vision_model(model)
        shot = None
        if vis_model:
            eprog("Capturing the region…", 30)
            ephase({"phase": -12, "title": "Capturing the region",
                    "status": "active"})
            # From: agents/analysis/runtime/runtime_probe.py
            creds = analyzer.demo_credentials()
            # From: agents/analysis/runtime/runtime_probe.py
            # From: agents/features/pencil_capture.py
            shot = capture_region(
                route, viewport=payload.get("viewport") or {},
                scroll=payload.get("scroll") or {},
                strokes=payload.get("strokes") or [], port=DEV_PORT,
                login=(creds[0] if creds else None),
                login_endpoint=analyzer.find_login_endpoint())
            ephase({"phase": -12, "title": "Capturing the region",
                    "status": "done"})
            # From: agents/features/pencil_capture.py
            if not shot.ok():
                # From: agents/build/tester_common.py
                elog("WARN", f"   ⚠ Screenshot failed ({shot.error}) — using the "
                             f"element description instead")
                shot = None
            elif vis_model != model:
                # From: agents/build/tester_common.py
                elog("INFO", f"   👁 {model} has no vision — using {vis_model} "
                             f"for this one call")
        else:
            # From: agents/build/tester_common.py
            elog("WARN", "   ⚠ No vision-capable model is available — the "
                         "drawing is used only to locate the region")

        eprog("Redesigning…", 50)
        ephase({"phase": -13, "title": "Redesigning", "status": "active"})

        mark = dev_log_mark()
        # From: agents/features/runtime/pencil/pencil_writer.py
        ok, written = _pencil_write_round(arch, res.path, before, instruction,
                                          element, shot, vis_model or model,
                                          payload, line=res.line,
                                          context=getattr(impact, 'context', {}) or {},
                                          shared_routes=shared)
        ephase({"phase": -13, "title": "Redesigning", "status": "done",
                "written": 1 if ok else 0})
        if not ok:
            if isinstance(written, str) and written.startswith("__AGENTFORGE_ESCALATE__:"):
                needed = written.split(":", 1)[1]
                change_request = (
                    f"On route {route or '/'} the user drew over a region rendered by {res.path}. "
                    f"The visual editor discovered that {needed} is also required.\n\n"
                    f"Requested change:\n{instruction}\n\n"
                    "Implement the complete dependency-aware change across every necessary file, preserving unrelated behavior."
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

        # From: agents/features/runtime/selection/selection_workflow.py
        impact = _converge_visual_semantics(
            arch, analyzer, proj_dir, instruction, impact, res.path,
            route, element, model)
        touched = list(dict.fromkeys(getattr(impact, "written", []) or [res.path]))
        # From: agents/features/runtime/feature_update.py
        undo_id = _snapshot(proj_name, touched, before_project)
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": touched})

        eprog("Verifying…", 78)
        # From: agents/features/runtime/images/image_completion.py
        _fill_missing_images(arch, proj_dir)
        # From: agents/pipeline/bugs/bug_verification.py
        verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                          build_rounds=0, probe=False, analyzer=analyzer)
        # From: agents/features/runtime/images/image_service.py
        # From: agents/features/runtime/selection/selection_repair.py
        _autofix_from_browser_console(
            arch, res.path, _browser_console(payload), proj_dir=proj_dir,
            analyzer=analyzer, model=model, route=route)
        # From: agents/features/runtime/selection/selection_repair.py
        _autofix_from_terminal(arch, res.path, payload, mark,
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
            declared_routes=getattr(impact, "routes", []) or [], route_hint=route)
        if red or not stable:
            # From: agents/pipeline/feature_safety.py
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            # From: agents/build/tester_common.py
            elog("WARN", f"   ↩ Pencil edit rolled back after live verification ({len(reverted)} file(s))")
            eerr("The pencil redesign could not keep the app runtime-clean, so the previous working state was restored")
            return
        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(payload))
    except Exception as e:
        eerr(f"Pencil edit error: {e}")
        log.exception("run_pencil_edit")
    finally:
        stop_model(model)


PAGE_UPDATE_SYSTEM = """\
You are rewriting ONE page of a Next.js 16 App Router app, in place.

You are given the complete current source of that page, the components it
renders, and what the user wants changed. Everything you need is here.

DO EVERYTHING THEY ASKED FOR. Rewrite the copy, change the animations,
restructure the layout, redesign the page end to end — if that is the request,
that is the job, and no change is too large.

THAT INCLUDES REMOVING THINGS. "Take the sidebar out", "drop the stats band",
"get rid of the hero" — do exactly that, and delete the markup properly rather
than hiding it behind a class. Removal is a normal request, not a special case.

WHAT MUST NOT HAPPEN is a part of the page disappearing that they never
mentioned. A request to tighten the spacing leaves every section still on the
page. A request to restyle the cards leaves the FAQ below them alone. One
question before you answer: is anything gone that they did not ask you to
remove? If so, put it back.

Do not invent content either. No placeholder addresses, phone numbers, social
links, testimonials or statistics that the app has no data for: an empty column
is better than a fabricated one.

WHAT IS NEVER YOURS TO CHANGE:
  • API routes — same paths, same methods, same request and response shapes.
  • Entities — the collections and the fields on them keep their names.
  • Functions — every one keeps its name, its parameters and what it does.
  • Exports — other files import them.
  • Props — a component called with `product={p}` is still called that way.
  • 'use client' stays exactly where it is, or stays absent. If something you
    add needs a hook or a handler and this file is a Server Component, put that
    piece in its own small 'use client' component and render it here.

IF YOU NEED A PACKAGE THAT IS NOT INSTALLED, ask for it BEFORE the file:

<run_command>npm install embla-carousel-react</run_command>

One package per command, real npm names, `npm install` only. Already there, so
never ask for: react, react-dom, next, mongodb, tailwindcss, lucide-react,
framer-motion, better-auth.

Output the COMPLETE file in exactly one <write_file path="…"> block. No
markdown fences, no explanation.
"""


# The page file a route renders, or '' when the route is unknown.
def _page_file_for(arch, analyzer, route: str) -> str:
    """The page file a route renders, or '' when the route is unknown."""
    route = (route or "/").split("?")[0].rstrip("/") or "/"
    try:
        # From: agents/analysis/checks/route_checks.py
        for url, meta in (analyzer.enumerate_routes() or {}).items():
            if meta.get("kind") == "page" and (url.rstrip("/") or "/") == route:
                return meta.get("file", "")
    except Exception as e:
        log.debug(f"page file for {route}: {e}")

    stem = "app" + ("" if route == "/" else route) + "/page"
    for ext in (".jsx", ".js"):
        if (stem + ext) in arch.files:
            return stem + ext
    return ""
