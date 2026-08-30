"""WebSocket messages translated into builder/update jobs."""

# Keep one Studio WebSocket connection open, decode each incoming action, and route it to the correct build or
# project-update job.
async def ws_handler(websocket, path=None):
    """Prepare the ws handler value or state used by this focused pipeline step."""
    clients.add(websocket)
    log.info(f"WS connected ({len(clients)})")
    try:
        await websocket.send(json.dumps({
            "type": "log", "level": "INFO",
            "text": "✅ AgentForge connected — enter a prompt and click Build"
        }))
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                job = _message_job(msg)
                if job:
                    threading.Thread(
                        target=job[0], args=job[1], daemon=True).start()
            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        log.info(f"WS disconnected ({len(clients)})")


# Translate one WebSocket action into its unchanged worker contract.
def _message_job(msg: dict):
    """Translate one WebSocket action into its unchanged worker contract."""
    kind = msg.get("type")
    prompt = str(msg.get("prompt") or "").strip()
    project = str(msg.get("project") or "").strip()

    known = {
        "agent_build", "agent_resume", "chat", "agent_update",
        "pencil_edit", "element_edit", "image_edit", "feature",
    }
    if kind not in known:
        return None
    model = msg.get("model") or default_agent_model()
    qa_model = str(msg.get("qa_model") or "").strip()
    route = str(msg.get("route") or "").strip()
    # From: agents/features/runtime/images/image_service.py
    think = _think_flag(msg)

    if kind == "agent_build" and prompt:
        return run_agent_pipeline, (
            prompt, model, think, qa_model, "",
            str(msg.get("logo") or "").strip(),
            str(msg.get("srs_id") or "").strip())
    if kind == "agent_resume" and project:
        return run_agent_pipeline, (
            "", model, think, qa_model, project)
    if kind in ("chat", "agent_update") and project and prompt:
        # From: agents/features/runtime/images/image_service.py
        return run_chat, (
            project, prompt, model, route, think, qa_model,
            _browser_console(msg))
    if kind == "pencil_edit" and project and prompt:
        return run_pencil_edit, (project, prompt, msg, model, think)
    if kind == "element_edit" and project and prompt:
        # From: agents/features/runtime/images/image_service.py
        return run_element_edit, (
            project, prompt, msg.get("element") or {}, model, think,
            _browser_console(msg))
    if kind == "image_edit" and project and prompt:
        return run_image_edit, (
            project, prompt, msg.get("element") or {}, model, think)
    if kind == "feature" and project and prompt:
        # From: agents/features/runtime/images/image_service.py
        return run_feature, (
            project, prompt, model, think, qa_model, route,
            _browser_console(msg))
    return None
