# Visual image flow: prompt or upload -> replace source -> keep undo point.
# Returns the model's final unwrapped line of prose.
def _one_line(arch, system: str, ask: str, timeout: int = 120) -> str:
    """Return the model's final unwrapped line of prose."""
    # From: agents/core/llm/chat_requests.py
    r = ollama.chat(arch.model, [{"role": "system", "content": system},
                                 {"role": "user", "content": ask[:2400]}],
                    options={"temperature": 0.7}, timeout=timeout)
    text = ((r.get("message") or {}).get("content") or "").strip()
    return text.splitlines()[-1].strip().strip('"').strip("'") if text else ""


# Redraw a selected literal image reference and swap it in source.
def run_image_edit(proj_name: str, instruction: str, element: dict,
                   model: str, think: bool = None):
    """Redraw a selected literal image reference and swap it in source."""
    set_tester_emit(emit)
    try:
        # From: agents/pipeline/feature_safety.py
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

        # From: agents/features/runtime/images/image_service.py
        agent = image_agent()
        if not agent.enabled:
            eerr("Image generation is switched off — turn it on in Settings")
            return
        # From: agents/features/image_generator.py
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
        # From: agents/build/tester_common.py
        elog("INFO", f"   🎨 {prompt[:100]}")

        eprog("Drawing…", 45)
        # From: agents/features/image_generator.py
        name = agent.slug(prompt)
        out = proj_dir / "public" / "generated" / f"{name}.png"

        # From: agents/features/image_generator.py
        if not agent.generate(prompt, out, aspect="landscape", force=True):
            ephase({"phase": -21, "title": "Drawing the picture",
                    "status": "done", "written": 0})
            eerr("The picture could not be drawn")
            return
        new_ref = f"/generated/{name}.png"

        olds = {rel: arch.files[rel] for rel in holders}
        # From: agents/features/runtime/feature_update.py
        undo_id = _snapshot(proj_name, holders, olds)
        for rel in holders:
            # From: agents/planner/builder/file_writer.py
            arch.write_file(rel, olds[rel].replace(ref, new_ref))
            estream_start(rel)
            estream_end(rel, arch.files[rel])
            # From: agents/build/tester_common.py
            elog("INFO", f"   🖼 {rel} — {ref[:40]} → {new_ref}")
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": holders})
        ephase({"phase": -21, "title": "Drawing the picture",
                "status": "done", "written": len(holders)})
        # From: agents/planner/builder/project_memory.py
        arch.save_convo()

        eprog("Done!", 100)
        edone(f"http://localhost:{DEV_PORT}", proj_name,
              preview=_route_of(element))
    except Exception as e:
        eerr(f"Image edit error: {e}")
        log.exception("run_image_edit")
    finally:
        stop_model(model)


# Store the user's image and swap its selected literal source reference.
def run_image_swap(proj_name: str, data_b64: str, filename: str, element: dict):
    """Store the user's image and swap its selected literal source reference."""
    set_tester_emit(emit)
    try:
        # From: agents/pipeline/feature_safety.py
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

        # From: agents/features/runtime/images/image_service.py
        name = _safe_stem(filename, "uploaded")
        out = proj_dir / "public" / "generated" / f"{name}.png"
        # From: agents/features/runtime/images/image_service.py
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
            # From: agents/build/tester_common.py
            elog("INFO", f"   🖼 replaced {new_ref}")
            eprog("Done!", 100)
            edone(f"http://localhost:{DEV_PORT}", proj_name,
                  preview=_route_of(element))
            return

        eprog("Pointing the page at it…", 70)
        olds = {rel: arch.files[rel] for rel in holders}
        # From: agents/features/runtime/feature_update.py
        undo_id = _snapshot(proj_name, holders, olds)
        for rel in holders:
            # From: agents/planner/builder/file_writer.py
            arch.write_file(rel, olds[rel].replace(ref, new_ref))
            estream_start(rel)
            estream_end(rel, arch.files[rel])
            # From: agents/build/tester_common.py
            elog("INFO", f"   🖼 {rel} — {ref[:40]} → {new_ref}")
        if undo_id:
            emit({"type": "undo_point", "id": undo_id, "files": holders})
        ephase({"phase": -21, "title": "Placing your picture",
                "status": "done", "written": len(holders)})
        # From: agents/planner/builder/project_memory.py
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


# Clarify a short visual request without widening it; never raise.
def tune_instruction(instruction: str, element: dict, route: str,
                     model: str) -> str:
    """Clarify a short visual request without widening it; never raise."""
    text = (instruction or "").strip()
    if not text or len(text) > 400:
        return text
    try:
        # From: agents/features/selection_rules.py
        what = describe(element or {})
    except Exception:
        what = ""
    ask = (f"They typed: {text}\n\n"
           f"They were pointing at: {what or 'something on the page'}\n"
           f"On the page: {route or '/'}\n\n"
           f"Write the instruction.")
    try:
        # From: agents/core/llm/chat_requests.py
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


# Analyze visual-edit impact and auto-escalate genuine multi-file work.
def _visual_change_preflight(arch, analyzer, proj_dir, instruction: str,
                             element: dict, path: str, route: str, model: str):
    """Analyze visual-edit impact and auto-escalate genuine multi-file work."""
    try:
        # From: agents/features/feature_writer.py
        # From: agents/pipeline/build/project_preview.py
        agent = FeaturesAgent(arch, proj_dir, callbacks=_analyzer_callbacks(),
                              analyzer=analyzer, model=model)
        # From: agents/features/selection_rules.py
        selected = describe(element or {}) if element else ""
        # From: agents/features/planning/request_planning.py
        spec = agent.plan_change(
            instruction, selected_path=path, selected_route=route,
            selected_element=selected)
        if spec.files:
            # From: agents/features/planning/request_planning.py
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
            # From: agents/build/tester_common.py
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
        # From: agents/build/tester_common.py
        elog("WARN", f"   ⚠ change impact analysis unavailable ({str(e)[:90]}) — escalating to evidence-first change analysis")
        # From: agents/features/selection_rules.py
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
