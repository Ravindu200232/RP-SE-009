

MAX_ELEMENT_AUTOFIX = 2


# Repairs a visual edit from runtime evidence and its dependency graph.
def _autofix_from_terminal(arch, path, element, mark, rounds=MAX_ELEMENT_AUTOFIX,
                           proj_dir: Path = None, analyzer=None, model: str = None):
    """Repair a visual edit from runtime evidence and its dependency graph."""
    import urllib.error
    import urllib.request

    route = _route_of(element)
    if proj_dir is None:
        rounds = 0

    for rnd in range(0, max(0, rounds) + 1):
        status = None
        try:
            with urllib.request.urlopen(
                    f"http://localhost:{DEV_PORT}{route}", timeout=60) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as e:
            log.debug(f"autofix probe {route}: {e}")

        # From: agents/pipeline/build/runtime_faults.py
        faults = terminal_faults(_filter_db_noise(dev_log_since(mark), True))
        if not faults and (status is None or status < 400):
            if rnd:
                # From: agents/build/tester_common.py
                elog("INFO", f"   ✅ {route} is clean after the evidence repair")
            return True
        if rnd >= rounds or proj_dir is None:
            break

        detail = "\n".join(faults[:6]) or f"{route} returned HTTP {status}"
        exact = _exact_runtime_focus(arch, detail)
        focus = exact or [path]
        try:
            # From: agents/core/workspace/source_workspace.py
            graph = WorkspaceTools(arch).dependency_paths(
                [p for p in focus if p in arch.files], max_depth=4, cap=40)
            focus = list(dict.fromkeys(focus + graph))
        except Exception as e:
            log.debug(f"visual repair dependency graph: {e}")
        # From: agents/build/tester_common.py
        elog("WARN", f"   🐞 {route} broke — evidence repair ({rnd + 1}/{rounds}): "
                     f"{detail.splitlines()[0][:100]}")
        if len(focus) > 1:
            # From: agents/build/tester_common.py
            elog("INFO", f"   🔗 reading {len(focus)} connected source file(s) around the runtime fault")
        ephase({"phase": -20, "title": f"Diagnosing the edit (round {rnd + 1})",
                "status": "active"})
        try:
            # From: agents/pipeline/feature_safety.py
            helper = analyzer or _analyzer_for(arch, proj_dir)
            written = _repair_runtime(
                arch, proj_dir, None, helper, detail, detail, rnd + 1, model,
                focus_paths=focus, strict_scope=True)
            ephase({"phase": -20, "title": f"Diagnosing the edit (round {rnd + 1})",
                    "status": "done", "written": len(written or [])})
            if not written:
                # From: agents/build/tester_common.py
                elog("WARN", "   ⚠ evidence planner could not prove a safe visual-edit repair")
                break
            # From: agents/build/tester_common.py
            elog("INFO", f"   🐞 evidence repair rewrote {len(written)} file(s): "
                         + ", ".join(written[:8]))
            mark = dev_log_mark()
        except Exception as e:
            ephase({"phase": -20, "title": f"Diagnosing the edit (round {rnd + 1})",
                    "status": "done"})
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ evidence repair failed: {e}")
            log.exception("autofix: runtime repair")
            break

    # From: agents/build/tester_common.py
    elog("WARN", f"   ⚠ {route} is still reporting errors — leaving the fault explicit")
    return False


# Repairs a visual-edit browser fault with its whole dependency slice.
def _autofix_from_browser_console(arch, path: str, console: str, *,
                                  proj_dir: Path, analyzer, model: str,
                                  route: str = "") -> list:
    """Repair a visual-edit browser fault with its whole dependency slice."""
    console = str(console or "").strip()
    if not console:
        return []
    exact = _exact_runtime_focus(arch, console)
    if not exact:
        return []
    try:
        # From: agents/core/workspace/source_workspace.py
        focus = WorkspaceTools(arch).dependency_paths(exact, max_depth=4, cap=44)
    except Exception:
        focus = exact
    focus = list(dict.fromkeys(exact + focus))
    # From: agents/build/tester_common.py
    elog("WARN", f"   🧯 browser console points to {len(exact)} source location(s); "
                 f"reading {len(focus)} connected file(s) first")
    report = (
        f"A visual/feature edit on route {route or '/'} has browser runtime errors.\n"
        "Fix every independent runtime error proven by this console batch before "
        "changing selectors or guessing at the selected element. Follow callers, "
        "imports, API handlers and shared data dependencies around each stack file.\n\n"
        f"Browser console:\n{console[:6000]}"
    )
    written = _repair_runtime(
        arch, proj_dir, None, analyzer, report, "", 1, model,
        focus_paths=focus, strict_scope=True, exact_scope=True)
    if written:
        # From: agents/build/tester_common.py
        elog("INFO", f"   ✅ console dependency repair wrote {len(written)} file(s): "
                     + ", ".join(written[:10]))
    return written or []


PICTURES_RULE = (
    "PICTURES ARE FREE — ASK FOR ONE AND IT IS DRAWN. When the request wants "
    "an image, a photo, a picture, an icon, a logo or a background, write an "
    "ordinary tag pointing into /generated/ and describe the picture in the "
    "alt text:\n"
    "    <img src=\"/generated/sourdough-loaf.png\" "
    "alt=\"a rustic sourdough loaf on a wooden board, warm morning light\" "
    "className=\"...\" />\n"
    "The file does not exist yet and that is fine — the alt text is the "
    "prompt, and every picture referenced this way is generated and written "
    "to disk the moment your edit lands. Use a short kebab-case filename and "
    "write the alt text the way you would describe the shot to a "
    "photographer: subject, setting, style, light.\n"
    "Never use a stock photo URL, never link to an external host, and never "
    "leave a placeholder box where a picture was asked for.\n"
    "PUT IT WHERE IT CAN BE SEEN. A picture that was asked for is the point of "
    "the change, so it goes in the flow of the section at full strength — no "
    "`opacity-20`, no `mix-blend-multiply`, and no gradient laid over it. This "
    "is the shape that keeps coming back and it renders as nothing at all:\n"
    "    <div className=\"absolute inset-0 z-0 opacity-20\">\n"
    "      <img … className=\"… mix-blend-multiply\" />\n"
    "      <div className=\"absolute inset-0 bg-gradient-to-b from-white "
    "to-white\" />\n"
    "    </div>\n"
    "Twenty per cent opacity under a white gradient on a white section is an "
    "invisible picture, and the person who asked for it sees no change. Only "
    "make one a faint background when the request actually said watermark, "
    "texture, or subtle background — and even then keep it above `opacity-60`. "
    "Otherwise give it real size: a hero band, a card image, a figure beside "
    "the text, something with width and height that a reader would notice.\n\n")


# Returns contract-preserving rules for add or update picker edits.
def _edit_rules(adding: bool) -> str:
    """Return contract-preserving rules for add or update picker edits."""
    shared = ("DO NOT CHANGE: api routes, entities, functions. The routes stay "
              "at the same paths with the same methods and the same request "
              "and response shapes. The data entities keep their fields and "
              "their names. Every function keeps its name, its parameters and "
              "what it does.\n\n"
              + PICTURES_RULE)
    if adding:
        return shared + (
            "ADD THE REQUESTED SECTION WHERE THEY POINTED. Preserve existing "
            "sections unless the new section genuinely needs a local import or "
            "small wiring change. Do not perform unrelated cleanup or redesign. "
            "The new section may be as large or complex as the request needs.\n\n")
    return shared + (
        "CHANGE THE SELECTED REGION COMPLETELY AS REQUESTED. Preserve unrelated "
        "sections and public contracts, but imports/helpers used by this region "
        "may change when necessary. Do not reject a correct edit because it "
        "changes many lines; verification decides correctness.\n\n")
