# Feature flow: understand -> scope -> apply -> test -> refresh the preview.
def run_feature(proj_name: str, request: str, model: str, think: bool = None,
                qa_model: str = "", route: str = "", console: str = ""):
    """Apply, verify, stabilize, and test one dependency-aware change."""
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        elog("INFO", f"🧩 Feature — {request[:70]}")
        if arch.convo:
            elog("INFO", f"   🧠 Remembering the build ({len(arch.convo)} turns)")
        eprog("Planning…", 15)

        analyzer = _analyzer_for(arch, proj_dir)
        agent = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                              analyzer=analyzer, model=model)
        agent.route_hint = _infer_issue_route(route, request, "", "", arch, analyzer)
        if agent.route_hint and agent.route_hint != "/":
            elog("INFO", f"   🎯 Feature anchored to current route {agent.route_hint}")

        tx = _capture_feature_transaction(arch, proj_dir)
        before = dict(tx["files"])
        try:
            baseline_keys = _feature_baseline_keys(analyzer.scan())
        except Exception as e:
            log.debug(f"feature baseline scan: {e}")
            baseline_keys = set()

        eprog("Writing…", 40)
        spec = agent.run(request)
        if not spec.written:
            eerr("The feature agent changed nothing")
            return
        elog("INFO", f"   ✅ {len(spec.written)} file(s) written")
        if spec.rejected:
            elog("WARN", f"   ⛔ {len(spec.rejected)} unsafe/invalid write(s) were rejected")

        touched = [p for p in spec.written if p in before]
        undo_id = _snapshot(proj_name, touched, before) if touched else ""
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": touched})

        arch.save_convo()

        if console:
            _autofix_from_browser_console(
                arch, spec.written[0] if spec.written else "", console,
                proj_dir=proj_dir, analyzer=analyzer, model=model,
                route=getattr(agent, "route_hint", "") or route)

        if any(f.endswith("lib/seed.js") for f in spec.written) and db_ok():
            try:
                r = MONGO.reset_project_db(proj_dir, node_bin=NODE_BIN)
                if r.get("dropped"):
                    elog("INFO", f"   🧹 The seed changed — cleared {r['db']} "
                                 f"({r['dropped']} collection(s)) so it runs "
                                 f"again with the new shape")
            except Exception as e:
                elog("WARN", f"   ⚠ Could not re-seed after the seed changed: "
                             f"{e}. Records written before this feature will "
                             f"not have its new fields.")

        eprog("Verifying…", 65)
        image_request = feature_image_requested(request)
        if image_request:
            elog("INFO", "   🎨 feature requested visual media — using Fooocus for missing generated assets")
        _fill_missing_images(arch, proj_dir, "the requested feature",
                             explicit_request=image_request)
        res = verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                                probe=False, analyzer=analyzer)
        if res["routes_failed"]:
            elog("WARN", f"   ⚠ {len(res['routes_failed'])} route(s) still "
                         f"failing")

        hard_red = (not res["build_ok"] or bool(res.get("syntax_broken"))
                    or bool(res.get("broken_imports")))
        if hard_red:
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            elog("WARN", f"   ↩ Feature rolled back — verification stayed red "
                         f"({len(reverted)} file(s) restored)")
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            eerr("The feature introduced a compile/import regression, so it was rolled back automatically")
            return

        eprog("Watching the live app…", 78)
        stable, repaired, _live_report = _stabilize_feature_upgrade(
            arch, proj_dir, analyzer, baseline_keys=baseline_keys,
            before_files=before, db_ok=db_ok(), declared_routes=spec.routes,
            route_hint=getattr(agent, "route_hint", ""))
        if not stable:
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            try:
                arch.save_convo()
            except Exception:
                pass
            elog("WARN", f"   ↩ Feature rolled back after live regression "
                         f"({len(reverted)} file(s) restored)")
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            eerr("The feature caused live regressions that could not be stabilized, so the working app was restored")
            return

        if repaired:
            for path in sorted(_feature_changed_paths(before, arch)):
                if path.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")) and path not in spec.written:
                    spec.written.append(path)
            elog("INFO", f"   🛠 Live watch repaired {repaired} file write(s) before feature QA")

        eprog("Testing the feature…", 88)
        _feature_tests(arch, proj_dir, spec, model, qa_model,
                       build_ok=True)

        eprog("Final live watch…", 95)
        final_check = verify_after_edit(
            arch, proj_dir, proj_name, stack=stack, build_rounds=1,
            probe=False, analyzer=analyzer)
        final_red = (not final_check.get("build_ok", True)
                     or bool(final_check.get("syntax_broken"))
                     or bool(final_check.get("broken_imports")))
        if final_red:
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            elog("WARN", f"   ↩ Feature rolled back at final commit gate ({len(reverted)} file(s) restored)")
            eerr("The feature became red after QA, so the previous working app was restored")
            return

        final_stable, final_repairs, _ = _stabilize_feature_upgrade(
            arch, proj_dir, analyzer, baseline_keys=baseline_keys,
            before_files=before, db_ok=db_ok(), declared_routes=spec.routes,
            route_hint=getattr(agent, "route_hint", ""))
        if not final_stable:
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            try:
                arch.save_convo()
            except Exception:
                pass
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            elog("WARN", f"   ↩ Feature rolled back after final Next/browser watch ({len(reverted)} file(s) restored)")
            eerr("A live regression appeared after feature QA and could not be stabilized, so the feature was rolled back")
            return
        if final_repairs:
            elog("INFO", f"   🛠 Final live watch repaired {final_repairs} additional file write(s)")

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=getattr(agent, "route_hint", "") or "/")
    except Exception as e:
        eerr(f"Feature error: {e}")
        log.exception("run_feature")
    finally:
        stop_model(model)


def _feature_tests(arch, proj_dir: Path, spec, model: str, qa_model: str, *,
                   build_ok: bool):
    """Author and run scoped unit tests when build and cloud QA are ready."""
    qa_model = qa_model or model
    qa = QASession(proj_dir, callbacks=_qa_callbacks(), model=qa_model,
                   enabled=is_cloud_model(qa_model))
    if not qa.enabled:
        elog("WARN", "   ⚠ QA is cloud-only — the feature ships untested. "
                     "Pick a cloud QA model to have tests written for it.")
        return qa
    if not build_ok:
        elog("WARN", "   ⚠ Skipping the feature's tests — the build is not green")
        return qa
    qa.bind(arch)

    targets = select_targets(spec.written, qa.read_source,
                             already=len(qa.manifest))
    if not targets:
        elog("INFO", "   🧪 Nothing in this feature is worth a unit test")
    else:
        elog("INFO", f"   🧪 Writing tests for {len(targets)} new file(s)")
        author = UnitTestAuthor(arch, proj_dir, callbacks=_qa_callbacks(),
                                session=qa)
        written = author.write_for(targets)
        elog("INFO", f"   🧪 {len(written)} test file(s) written")

    if not qa.has_tests():
        return qa
    ephase({"phase": -15, "title": "Running unit tests", "status": "active"})
    harness = TestHarness(proj_dir, callbacks=_qa_callbacks(), cmd=qa.cmd)
    harness.materialise()
    if not harness.install():
        _qa_skip(qa, "the test runner could not be installed")
        ephase({"phase": -15, "title": "Running unit tests", "status": "done"})
        return qa
    try:
        run_qa_unit_stage(arch, proj_dir, qa, build_ok=True,
                          scope=spec.written)
    except Exception as e:
        elog("WARN", f"   ⚠ Unit test stage failed: {e}")
        log.exception("feature unit tests")
    ephase({"phase": -15, "title": "Running unit tests", "status": "done"})
    return qa


UNDO_DIR = LOGS_DIR / "undo"


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


def restore_snapshot(proj_name: str, stamp: str = "") -> dict:
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


def _one_line(arch, system: str, ask: str, timeout: int = 120) -> str:
    """Return the model's final unwrapped line of prose."""
    r = ollama.chat(arch.model, [{"role": "system", "content": system},
                                 {"role": "user", "content": ask[:2400]}],
                    options={"temperature": 0.7}, timeout=timeout)
    text = ((r.get("message") or {}).get("content") or "").strip()
    return text.splitlines()[-1].strip().strip('"').strip("'") if text else ""


def run_image_edit(proj_name: str, instruction: str, element: dict,
                   model: str, think: bool = None):
    """Redraw a selected literal image reference and swap it in source."""
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return

        old_src = (str(element.get("src") or "").strip()
                   or str(element.get("bg") or "").strip())
        alt = str((element.get("attrs") or {}).get("alt") or "").strip()
        if not old_src:
            eerr("That is not a picture — there is nothing to redraw")
            return

        ref = old_src
        for cut in (f"http://localhost:{DEV_PORT}", f"http://127.0.0.1:{DEV_PORT}"):
            if ref.startswith(cut):
                ref = ref[len(cut):]
        holders = [rel for rel, body in arch.files.items()
                   if ref and ref in body]
        if not holders:
            eerr(f"That picture's address ({ref[:70]}) is not written in any "
                 f"file — it probably comes from the database, so change it "
                 f"there or in the seed")
            return

        agent = image_agent()
        if not agent.enabled:
            eerr("Image generation is switched off — turn it on in Settings")
            return
        if not agent.available():
            eerr("No Fooocus is answering — start it, or set its address in "
                 "Settings")
            return

        ephase({"phase": -21, "title": "Drawing the picture", "status": "active"})
        eprog("Writing the image prompt…", 20)
        idea = (arch.plan or {}).get("description") or ""
        ask = (f"## The picture now\n{alt or ref}\n\n"
               f"## What they want instead\n{instruction}\n"
               + (f"\n## The app it is for\n{idea[:200]}\n" if idea else ""))
        try:
            prompt = _one_line(arch, IMAGE_PROMPT_SYSTEM, ask) or instruction
        except Exception as e:
            log.debug(f"image prompt: {e}")
            prompt = instruction
        elog("INFO", f"   🎨 {prompt[:100]}")

        eprog("Drawing…", 45)
        name = agent.slug(prompt)
        out = proj_dir / "public" / "generated" / f"{name}.png"

        if not agent.generate(prompt, out, aspect="landscape", force=True):
            ephase({"phase": -21, "title": "Drawing the picture",
                    "status": "done", "written": 0})
            eerr("The picture could not be drawn")
            return
        new_ref = f"/generated/{name}.png"

        olds = {rel: arch.files[rel] for rel in holders}
        undo_id = _snapshot(proj_name, holders, olds)
        for rel in holders:
            arch.write_file(rel, olds[rel].replace(ref, new_ref))
            estream_start(rel)
            estream_end(rel, arch.files[rel])
            elog("INFO", f"   🖼 {rel} — {ref[:40]} → {new_ref}")
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": holders})
        ephase({"phase": -21, "title": "Drawing the picture",
                "status": "done", "written": len(holders)})
        arch.save_convo()

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(element))
    except Exception as e:
        eerr(f"Image edit error: {e}")
        log.exception("run_image_edit")
    finally:
        stop_model(model)


def run_image_swap(proj_name: str, data_b64: str, filename: str, element: dict):
    """Store the user's image and swap its selected literal source reference."""
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, "", None)
        if arch is None:
            return

        old_src = (str(element.get("src") or "").strip()
                   or str(element.get("bg") or "").strip())
        if not old_src:
            eerr("That is not a picture — there is nothing to replace")
            return

        ref = old_src
        for cut in (f"http://localhost:{DEV_PORT}", f"http://127.0.0.1:{DEV_PORT}"):
            if ref.startswith(cut):
                ref = ref[len(cut):]
        holders = [rel for rel, body in arch.files.items() if ref and ref in body]
        if not holders:
            eerr(f"That picture's address ({ref[:70]}) is not written in any "
                 f"file — it probably comes from the database, so change it "
                 f"there or in the seed")
            return

        ephase({"phase": -21, "title": "Placing your picture", "status": "active"})
        eprog("Reading the file…", 30)

        name = _safe_stem(filename, "uploaded")
        out = proj_dir / "public" / "generated" / f"{name}.png"
        why = save_uploaded_image(data_b64, out)
        if why:
            ephase({"phase": -21, "title": "Placing your picture",
                    "status": "done", "written": 0})
            eerr(why)
            return

        new_ref = f"/generated/{name}.png"
        if new_ref == ref:
            ephase({"phase": -21, "title": "Placing your picture",
                    "status": "done", "written": 0})
            elog("INFO", f"   🖼 replaced {new_ref}")
            eprog("Done!", 100)
            edone(f"http://localhost:{DEV_PORT}", proj_name,
                  preview=_route_of(element))
            return

        eprog("Pointing the page at it…", 70)
        olds = {rel: arch.files[rel] for rel in holders}
        undo_id = _snapshot(proj_name, holders, olds)
        for rel in holders:
            arch.write_file(rel, olds[rel].replace(ref, new_ref))
            estream_start(rel)
            estream_end(rel, arch.files[rel])
            elog("INFO", f"   🖼 {rel} — {ref[:40]} → {new_ref}")
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": holders})
        ephase({"phase": -21, "title": "Placing your picture",
                "status": "done", "written": len(holders)})
        arch.save_convo()

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(element))
    except Exception as e:
        eerr(f"Image swap error: {e}")
        log.exception("run_image_swap")


TUNE_SYSTEM = """\
You rewrite one short request into one precise instruction for the model that \
is about to change a web page. You are given what the person typed and what \
they were pointing at when they typed it.

Their words are the whole brief. They are usually four or five words, often \
mistyped, and they are standing in front of the thing they mean — so the words \
leave out everything the picture already told them. Your job is to put that \
back, and NOTHING else.

RULES, all binding:
- Keep their intent exactly. Never add a second change, a colour, an \
animation, a layout idea or a "while you're there". If they asked for one \
thing, the instruction asks for one thing.
- Fix the typing. "blackground" is background, "centre it" is center it.
- Say WHAT and WHERE. If an element is provided, use its tag/text/role. If no \
element is provided, treat this as a project feature or bug report and name the \
current route plus the exact behavior that should change.
- For a bug report preserve the symptom and state the visible proof that it is fixed. \
For a feature request state the new behavior and the visible proof that it exists. \
Do not widen the scope.
- Say what must LOOK different when it is done, in one clause. That is the \
line that stops a change from landing invisibly.
- If they asked for a picture, say plainly that it must be clearly visible at \
full strength — not a faint wash, not behind an overlay, not under a tint.
- Never invent content: no product names, no copy, no numbers they did not \
give you.
- If their request is already precise, return it as it stands.

Reply with the instruction and nothing else. No preamble, no quotes, no \
explanation, no markdown. One sentence, two at most, under 60 words.\
"""


def tune_instruction(instruction: str, element: dict, route: str,
                     model: str) -> str:
    """Clarify a short visual request without widening it; never raise."""
    text = (instruction or "").strip()
    if not text or len(text) > 400:
        return text
    try:
        what = describe(element or {})
    except Exception:
        what = ""
    ask = (f"They typed: {text}\n\n"
           f"They were pointing at: {what or 'something on the page'}\n"
           f"On the page: {route or '/'}\n\n"
           f"Write the instruction.")
    try:
        r = ollama.chat(model, [{"role": "system", "content": TUNE_SYSTEM},
                                {"role": "user", "content": ask}],
                        options={"temperature": 0.3}, think=False, timeout=90)
        out = ((r.get("message") or {}).get("content") or "").strip()
    except Exception as e:
        log.debug(f"tune: {e}")
        return text
    out = re.sub(r"^```[a-z]*\s*|\s*```$", "", out).strip().strip('"“”')
    out = " ".join(out.split())
    # A tuner that refuses, explains itself, or writes an essay.
    if (not out or len(out) > 500 or len(out.split()) > 90
            or out.lower().startswith(("i ", "sure", "here", "certainly",
                                       "as an", "sorry"))):
        return text
    return out


def _visual_change_preflight(arch, analyzer, proj_dir, instruction: str,
                             element: dict, path: str, route: str, model: str):
    """Analyze visual-edit impact and auto-escalate genuine multi-file work."""
    try:
        agent = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                              analyzer=analyzer, model=model)
        selected = describe(element or {}) if element else ""
        spec = agent.plan_change(
            instruction, selected_path=path, selected_route=route,
            selected_element=selected)
        if spec.files:
            spec = agent.cover_whole_request(instruction, spec)
        paths = {f.get("path", "") for f in spec.files if f.get("path")}
        ctx = getattr(spec, "context", {}) or {}
        evidence_paths = {str(e.get("path", "")) for e in (ctx.get("evidence") or [])
                          if isinstance(e, dict)}
        proven = bool(paths and path in evidence_paths and
                      ctx.get("cause") and ctx.get("gap") and ctx.get("verify") and
                      str(ctx.get("confidence") or "").lower() in ("high", "medium"))
        broader = (not proven or bool(spec.packages or spec.routes or
                       any(p != path for p in paths) or len(paths) > 1))
        if not broader:
            elog("INFO", f"   🔎 focused ownership proved in {path}: "
                         f"{str(ctx.get('cause') or '')[:150]}")
            return False, "", spec
        details = "\n".join(
            f"- {f.get('action','edit')} {f.get('path','')} — {f.get('why','')}"
            for f in spec.files)
        enriched = (
            f"The user made this request from the visual editor on route {route or '/'}; "
            f"the selected region is rendered by {path}.\n"
            f"Selected UI: {selected or '(region selected visually)'}\n\n"
            f"Requested change:\n{instruction}\n\n"
            f"Initial dependency analysis found this impact set:\n{details or '(re-analyze from source)'}\n"
            "Re-analyze from the current project and implement the whole change. "
            "Do not limit it to the selected file; preserve unrelated behavior."
        )
        return True, enriched, spec
    except Exception as e:
        elog("WARN", f"   ⚠ change impact analysis unavailable ({str(e)[:90]}) — escalating to evidence-first change analysis")
        selected = describe(element or {}) if element else ""
        enriched = (
            f"The user made this request from the visual editor on route {route or '/'}; "
            f"the selected region was resolved to {path}.\n"
            f"Selected UI: {selected or '(region selected visually)'}\n\n"
            f"Requested change:\n{instruction}\n\n"
            "The focused impact analysis was inconclusive. Inspect the current source, "
            "its imports/callers/API/data boundaries, establish the real owner/root cause, "
            "then implement only the evidence-backed complete change."
        )
        return True, enriched, None



def _converge_visual_semantics(arch, analyzer, proj_dir, request: str,
                               spec, path: str, route: str, element: dict,
                               model: str):
    """Re-read a focused edit and close only source-proven remaining gaps."""
    agent = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                          analyzer=analyzer, model=model)
    if spec is None:
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
    return agent.converge_semantics(
        request, spec, selected_path=path, selected_route=route,
        selected_element=describe(element or {}), rounds=2)

def run_element_edit(proj_name: str, instruction: str, element: dict,
                     model: str, think: bool = None, console: str = ""):
    """Edit selected UI locally or escalate when dependencies require it."""
    set_tester_emit(emit)
    try:
        proj_dir, arch, stack = _open_for_edit(proj_name, model, think)
        if arch is None:
            return
        analyzer = _analyzer_for(arch, proj_dir)
        resolver = ElementResolver(arch, analyzer)

        elog("INFO", f"🎯 {describe(element).splitlines()[0][:90]}")
        eprog("Finding the code…", 15)
        t_resolve = time.time()
        res = resolver.resolve(element)
        elog("INFO", f"   ⏱ resolve {time.time() - t_resolve:.1f}s")
        if not res.path:
            eerr(f"Could not find the code for that element — {res.reason}")
            return
        elog("INFO", f"   📍 {res.path}:{res.line or '?'} "
                     f"({'model chose' if res.used_model else 'unambiguous'})")
        shared = _shared_routes(arch, res.path)
        emit({"type": "element_picked", "file": res.path, "line": res.line,
              "score": res.score, "candidates": res.candidates[:6],
              "used_model": res.used_model, "shared_routes": shared[:12]})
        page_route = _route_of(element)

        _log_reach(res.path, shared, page_route)

        before = arch.files.get(res.path, "")
        if not before:
            eerr(f"{res.path} is empty or unreadable")
            return
        before_project = dict(arch.files)
        tx = _capture_feature_transaction(arch, proj_dir)
        try:
            baseline_keys = _feature_baseline_keys(analyzer.scan())
        except Exception:
            baseline_keys = set()

        broaden, change_request, impact = _visual_change_preflight(
            arch, analyzer, proj_dir, instruction, element, res.path,
            page_route, model)
        if broaden:
            count = len(getattr(impact, "files", []) or [])
            elog("INFO", f"   ↗ selected-region change spans {count} source file(s) — switching to full agentic change")
            return run_feature(proj_name, change_request, model, think)

        anchor = (element.get("text") or "").strip()[:60]
        removing = looks_like_removal(instruction)
        adding = looks_like_addition(instruction)
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
                return run_feature(proj_name, change_request, model, think)
            return

        if not arch.write_file(res.path, written):
            eerr(f"Could not write {res.path}")
            return
        estream_start(res.path)
        estream_end(res.path, written)

        impact = _converge_visual_semantics(
            arch, analyzer, proj_dir, instruction, impact, res.path,
            page_route, element, model)
        touched = list(dict.fromkeys(getattr(impact, "written", []) or [res.path]))
        undo_id = _snapshot(proj_name, touched, before_project)
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": touched})
        ephase({"phase": -11, "title": "Editing the element", "status": "done",
                "written": len(touched)})

        eprog("Verifying…", 75)
        t_verify = time.time()

        _fill_missing_images(arch, proj_dir)
        verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                          build_rounds=0, probe=False, analyzer=analyzer)
        _autofix_from_browser_console(
            arch, res.path, console, proj_dir=proj_dir, analyzer=analyzer,
            model=model, route=page_route)
        _autofix_from_terminal(arch, res.path, element, mark,
                               proj_dir=proj_dir, analyzer=analyzer, model=model)
        final = verify_after_edit(arch, proj_dir, proj_name, stack=stack,
                                  build_rounds=1, probe=False, analyzer=analyzer)
        red = (not final.get("build_ok", True) or bool(final.get("syntax_broken"))
               or bool(final.get("broken_imports")))
        stable, _, _ = _stabilize_feature_upgrade(
            arch, proj_dir, analyzer, baseline_keys=baseline_keys,
            before_files=tx["files"], db_ok=db_ok(),
            declared_routes=getattr(impact, "routes", []) or [], route_hint=page_route)
        if red or not stable:
            reverted = _restore_feature_transaction(arch, proj_dir, tx)
            _stop_dev_proc(); start_dev_server(proj_dir, stack); wait_for_dev(stack)
            elog("WARN", f"   ↩ Selection rolled back after live verification ({len(reverted)} file(s))")
            eerr("The selected edit could not keep the app runtime-clean, so the previous working state was restored")
            return
        elog("INFO", f"   ⏱ verify {time.time() - t_verify:.1f}s")
        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(element))
    except Exception as e:
        eerr(f"Element edit error: {e}")
        log.exception("run_element_edit")
    finally:
        stop_model(model)
