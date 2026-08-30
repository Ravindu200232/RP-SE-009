# Pencil flow: capture -> understand the mark -> scope -> apply -> verify.
# The model to send an image to. DEFAULT_BUILD (`qwen2.5-coder:14b`) has no vision capability, so this fires
# often. Borrowing one for a single call beats refusing the tool; returning "" means the caller degrades to
# text-only rather than failing.
def _vision_model(preferred: str) -> str:
    """
    The model to send an image to.

    DEFAULT_BUILD (`qwen2.5-coder:14b`) has no vision capability, so this fires
    often. Borrowing one for a single call beats refusing the tool; returning ""
    means the caller degrades to text-only rather than failing.
    """
    try:
        # From: agents/core/llm/model_catalog.py
        if ollama.supports_vision(preferred):
            return preferred
    except Exception:
        pass
    # From: agents/core/llm/llm_settings.py
    saved = str(load_settings().get("vision_model", "")).strip()
    if saved:
        return saved
    try:
        # From: agents/core/llm/model_catalog.py
        cat = ollama.catalog()
        pool = (cat.get("cloud") or []) + (cat.get("local") or [])
        for entry in pool:
            if entry.get("vision"):
                return entry["id"]
    except Exception as e:
        log.warning(f"could not find a vision model: {e}")
    return ""


# Runs one focused pencil-edit generation round and collect the proposed file changes.
def _pencil_write_round(arch, path, before, instruction, element, shot,
                        vis_model, payload, attempts=2, line=0, context=None,
                        shared_routes=None):
    """Prepare the pencil write round value or state used by this focused pipeline step."""
    vp = payload.get("viewport") or {}
    ctx = context or {}
    text = (f"## Analyzer change contract\nCurrent: {ctx.get('current') or '(not recorded)'}\n"
            f"Gap: {ctx.get('gap') or instruction}\nOwnership: {ctx.get('cause') or path}\n"
            f"Verify: {ctx.get('verify') or 'the marked redesign works without regressions'}\n"
            f"Shared route reach: {', '.join(shared_routes or []) or element.get('route') or payload.get('route') or '/'}\n\n"
            f"Route: {element.get('route') or payload.get('route') or '/'}   "
            f"Viewport: {vp.get('w', '?')}×{vp.get('h', '?')} "
            f"({vp.get('mode', 'desktop')})\n")
    # From: agents/features/pencil_capture.py
    if shot and shot.ok():
        c = shot.crop
        text += ("Image 1 is a close-up of the red freehand annotation. "
                 "Image 2 is the resized full page with the same mark for context.\n"
                 f"Marked region: x={c.get('x')} y={c.get('y')} "
                 f"{c.get('width')}×{c.get('height')}\n")
        if shot.logged_in:
            text += "The capture is of the signed-in view.\n"
    else:
        text += ("No screenshot is available. Redesign the element described "
                 "below.\n")
    if element:
        # From: agents/features/selection_rules.py
        text += f"\nElement under the drawing:\n{describe(element)}\n"
        # From: agents/features/runtime/selection/selection_scope.py
        where = _where_in_file(before, element, line)
        if where:
            text += f"\nWhere that is in the source:\n{where}\n"
    text += (f"\n## What the user asked for\n{instruction}\n\n"
             f"## The complete current source of {path}\n{before}")
    # From: agents/features/runtime/selection/selection_scope.py
    near = _neighbours(arch, path, before)
    if near:
        text += (f"\n\n## The files this one is joined to — what it renders, "
                 f"and what renders it\n{near}")

    msg = {"role": "user", "content": text}
    # From: agents/features/pencil_capture.py
    if shot and shot.ok():
        # From: agents/features/pencil_capture.py
        msg["images"] = shot.vision_images()

    convo = [{"role": "system", "content": PENCIL_SYSTEM + "\n\n" + TOOL_HELP}, msg]
    anchor = (element.get("text") or "").strip()[:60]

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

        raw = []

        # Accepts another streamed model chunk and emit any complete file blocks.
        def feed(token):
            """Accept another streamed model chunk and emit any complete file blocks."""
            raw.append(token)
            # From: agents/planner/builder/write_stream.py
            parser.feed(token)

        try:
            reply = ""
            seen_observations = set()
            while True:
                turn_raw = []

                # Sends one model turn, collect its streamed output, and pass each chunk to the active writer/parser.
                def feed_turn(token):
                    """Prepare the feed turn value or state used by this focused pipeline step."""
                    turn_raw.append(token)
                    feed(token)

                # From: agents/planner/builder/builder_setup.py
                arch._stream(convo, feed_turn, temperature=0.4,
                             model=vis_model, timeout=arch.EDIT_TIMEOUT)
                reply = "".join(turn_raw)
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
                    if sig and sig not in seen_observations and (
                            not budget_chars or used_chars < budget_chars * 0.82):
                        seen_observations.add(sig)
                        # From: agents/build/tester_common.py
                        elog("INFO", f"   🧰 pencil editor inspected {used} workspace tool(s)")
                        convo.append({"role": "user", "content":
                                      "Tool observations:\n\n" + observations +
                                      "\n\nContinue the SAME visual edit. Follow the source/import/caller evidence. "
                                      "If another file must change, do not hide that fact; emit the required write so the controller can escalate safely."})
                        continue
                    if sig in seen_observations:
                        # From: agents/build/tester_common.py
                        elog("WARN", "   ↔ pencil editor repeated the same inspection — deciding with current evidence")
                break
        except Exception as e:
            eerr(f"The model failed: {e}")
            return False, ""
        # From: agents/planner/builder/write_stream.py
        parser.close()
        full_reply = "".join(raw)
        writes = got["writes"]
        body = writes.get(path, "")
        external = [rel for rel in writes if rel != path]
        if external:
            names = ",".join(external[:8])
            # From: agents/build/tester_common.py
            elog("INFO", "   ↗ pencil editor emitted dependency write(s) — "
                         f"escalating transaction: {names}")
            return False, "__AGENTFORGE_ESCALATE__:" + names
        if writes and not body:
            only = ",".join(list(writes)[:8])
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ pencil editor wrote {only}, not selected owner {path} — escalating")
            return False, "__AGENTFORGE_ESCALATE__:" + only
        need = re.search(r"^\s*NEED\s+(\S+)\s*$", reply, re.M)
        if need and not body:
            needed = need.group(1).strip('`')
            # From: agents/build/tester_common.py
            elog("INFO", f"   ↗ pencil editor discovered dependency {needed} — escalating automatically")
            return False, "__AGENTFORGE_ESCALATE__:" + needed
        if not body:
            head = " ".join(reply.split())[:300] or "(empty response)"
            if _DECLINED_RE.search(reply):
                # From: agents/build/tester_common.py
                elog("INFO", f"   ✅ Nothing to change — {head[:160]}")
                eerr(f"That region was not found in {path}, so nothing was "
                     f"changed. {vis_model} said: {head[:200]}")
                return False, ""
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ no <write_file> block — {vis_model} said: {head}")

            if attempt < attempts:
                convo.append({"role": "assistant", "content": reply[:2000]})
                convo.append({"role": "user", "content":
                    "That was not a file. Output the COMPLETE file inside "
                    f"one <write_file path=\"{path}\">…</write_file> block, "
                    "starting immediately with '<write_file'. No markdown "
                    "fences, no description of the image, no explanation."})
                continue
            eerr(f"{vis_model} returned no file after {attempts} attempts. "
                 f"It said: {head[:220]}")
            return False, ""

        if body.strip():
            return True, body
        if attempt == attempts:
            eerr("The model returned an empty file — nothing was written")
            return False, ""
    return False, ""
