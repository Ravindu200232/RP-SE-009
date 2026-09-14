"""A durable, one-way change transaction: source -> SRS -> sibling -> SRS."""

def _sync_parent_documents(directory, request_path, request, label, role, summary):
    link = json.loads((directory / ".agentforge" / "srs" / "link.json").read_text(encoding="utf-8"))
    sid = link["srs_id"]
    checkpoint = request.setdefault("srs_jobs", {})
    job_id = checkpoint.get(label)
    if not job_id:
        response = requests.post(f"http://127.0.0.1:{SRS_PORT}/jobs", json={
            "path": f"/projects/{sid}/changes", "method": "POST",
            "body": {"change_id": f"{request_path.stem}-{label}", "source": role, "summary": summary[:12000]}}, timeout=30)
        response.raise_for_status()
        job_id = checkpoint[label] = response.json()["job_id"]
        atomic_json(request_path, request)
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        if SERVER_STOPPING:
            raise RuntimeError("Document synchronization paused for shutdown")
        response = requests.get(f"http://127.0.0.1:{SRS_PORT}/jobs/{job_id}", timeout=30)
        if response.status_code == 404:
            # Receipt IDs make a later retry idempotent even after a job expires.
            checkpoint.pop(label, None)
            atomic_json(request_path, request)
            raise RuntimeError("The document job expired. Retry synchronization to restore it.")
        response.raise_for_status()
        job = response.json()
        if job.get("status") == "running":
            time.sleep(2)
            continue
        if job.get("status") == "error" or (job.get("http_status") or 200) >= 400:
            checkpoint.pop(label, None)
            atomic_json(request_path, request)
            raise RuntimeError(str(job.get("error") or (job.get("result") or {}).get("detail") or "SRS synchronization failed"))
        RUN.document_sync = True
        try:
            if not adopt_srs(sid, directory):
                raise RuntimeError("The SRS updated, but its project documents could not be refreshed")
        finally:
            RUN.document_sync = False
        return job.get("result") or {}
    raise RuntimeError("SRS synchronization exceeded 30 minutes; its job remains available for retry")


def synchronize_completed_change(directory, request_path, request):
    """Run after completion only. Sibling runs never enqueue another change transaction."""
    if not (directory / ".agentforge" / "srs" / "link.json").is_file():
        return
    source = request["agent"]
    sibling = "developer" if source == "designer" else "designer"
    state = ProjectState(directory)
    stage = request.get("stage", "source_completed")
    agents = state.read().get("agents", {})
    summary = request.get("change_summary") or agents.get(source, {}).get("summary") or "Completed the requested project update."
    request["change_summary"] = summary

    def checkpoint(next_stage):
        nonlocal stage
        stage = request["stage"] = next_stage
        request.pop("sync_error", None)
        atomic_json(request_path, request)

    emit({"type": "sync_state", "project": directory.name, "status": "running", "source": source})
    state.update(sync={"status": "running", "source": source, "request_id": request_path.stem})
    if stage == "source_completed":
        result = _sync_parent_documents(directory, request_path, request, "source", source, summary)
        request["srs_version"] = result.get("version")
        checkpoint("srs_updated")
    # A completed prototype may update an existing build, never start the first build.
    sibling_exists = ((directory / "package.json").is_file() and
                      (agents.get("developer", {}).get("completed_at") or agents.get("developer", {}).get("status") == "completed")) if sibling == "developer" else (directory / ".agentforge" / "prototype" / "index.html").is_file()
    if stage == "srs_updated" and sibling_exists:
        options = agents.get(sibling, {}).get("request", {})
        instruction = (
            "The parent SRS has been updated after a completed change in the other agent. "
            "Read the current handoff files and apply this change to your own artifact. "
            "Preserve unrelated behavior. Update only your own files and verify the result.\n\n"
            + summary)
        # This direct run shares the transaction's queue slot. It has an independent
        # context, and its completion cannot create another sibling transaction.
        RUN_QUEUE.set_agent(sibling)
        run_chat(directory.name, instruction, options.get("model") or default_agent_model(),
                 "/prototype" if sibling == "designer" else "/__builder", options.get("think", True),
                 "", "", sibling)
        completed = state.read().get("agents", {}).get(sibling, {})
        if completed.get("status") != "completed":
            raise RuntimeError(f"{sibling.title()} update did not complete: {completed.get('error') or 'continue the saved run'}")
        request["sibling_summary"] = completed.get("summary") or summary
        checkpoint("sibling_completed")
    elif stage == "srs_updated":
        checkpoint("complete")
    if stage == "sibling_completed":
        result = _sync_parent_documents(directory, request_path, request, "mirror", sibling, request["sibling_summary"])
        request["srs_version"] = result.get("version")
        checkpoint("complete")
    state.update(sync={"status": "completed", "version": request.get("srs_version"), "source": source})
    emit({"type": "sync_state", "project": directory.name, "status": "completed", "version": request.get("srs_version")})


def retry_project_sync(project):
    _, directory, error = _owned_dir(PROD_DIR, project, "project name", "project")
    if error:
        return {"error": error}
    with _REQUEST_LOCK:
        for path in sorted((directory / ".agentforge" / "requests").glob("*.json")):
            request = json.loads(path.read_text(encoding="utf-8"))
            if not request.get("sync_error"):
                continue
            request.pop("sync_error")
            atomic_json(path, request)
            start_run(globals()[request["target"]], tuple(request["args"]), project=project, replay_path=path)
    return {"ok": True}
