"""A durable, one-way change transaction: source -> SRS -> sibling -> SRS."""

def run_manual_prototype_change(project, summary):
    """Verify direct HTML edits before their existing durable SRS transaction."""
    from builder_agent.prototype_check import validate_all, repair_prompt
    from builder_agent.browser import Browser
    from builder_agent.events import Events
    directory = PROD_DIR / project
    state = ProjectState(directory)
    state.agent('designer', status='running')
    browser = Browser(events=Events())
    try:
        findings = validate_all(directory, browser=browser)
        if any(row.get('kind') == 'browser unavailable' for row in findings):
            raise RuntimeError('Prototype browser validation was unavailable. The saved HTML remains available for retry.')
        errors = [row for row in findings if row.get('kind') != 'browser unavailable']
        if errors:
            _, result = _run_agent(directory, repair_prompt(errors), default_agent_model(), False,
                                phases=('prototype',), kind='edit', plan=False, prototype_only=True)
            if result.status != 'completed':
                raise RuntimeError('Direct HTML validation failed: ' + result.result[:500])
        state.agent('designer', status='completed', summary=summary, completed_at=time.time(), error='')
        emit({'type':'run_state','project':project,'agent':'designer','status':'completed'})
    except Exception as error:
        state.agent('designer', status='error', error=str(error))
        raise
    finally:
        browser.close()

def _srs_id_of(directory):
    link = json.loads((directory / ".agentforge" / "srs" / "link.json").read_text(encoding="utf-8"))
    return link["srs_id"]


def _await_srs_job(request_path, request, label, job_id):
    """Wait out one SRS job, or say why it cannot be waited for."""
    checkpoint = request.setdefault("srs_jobs", {})
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
        return job.get("result") or {}
    raise RuntimeError("SRS synchronization exceeded 30 minutes; its job remains available for retry")


def _adopt(sid, directory):
    """Pull the revised documents back into the project, quietly."""
    RUN.document_sync = True
    try:
        if not adopt_srs(sid, directory):
            raise RuntimeError("The SRS updated, but its project documents could not be refreshed")
    finally:
        RUN.document_sync = False


def _sync_parent_documents(directory, request_path, request, label, role, summary):
    sid = _srs_id_of(directory)
    checkpoint = request.setdefault("srs_jobs", {})
    job_id = checkpoint.get(label)
    if not job_id:
        response = requests.post(f"http://127.0.0.1:{SRS_PORT}/jobs", json={
            "path": f"/projects/{sid}/changes", "method": "POST",
            "body": {"change_id": f"{request_path.stem}-{label}", "source": role, "summary": summary[:12000]}}, timeout=30)
        response.raise_for_status()
        job_id = checkpoint[label] = response.json()["job_id"]
        atomic_json(request_path, request)
    result = _await_srs_job(request_path, request, label, job_id)
    _adopt(sid, directory)
    return result


def clear_qa_change(directory) -> None:
    """Consume the digest, so the next change cannot re-post this evidence."""
    try:
        from server_modules.srs.qa_change import clear_change
        clear_change(directory)
    except Exception:  # noqa: BLE001
        pass


def read_qa_change(directory) -> dict:
    """The verification digest this build left behind, if it ran tests at all."""
    try:
        from server_modules.srs.qa_change import read_change
        return read_change(directory)
    except Exception:  # noqa: BLE001 - never fail a sync over a missing note
        return {}


def _with_screen_inventory(directory, summary: str) -> str:
    """Name the pages that exist, rather than trusting prose to have named them.

    The drawing's screen list used to reach the SRS through a separate writer
    whose file `adopt_srs` overwrote after every sync - and which the
    `DesignerAgent` path, the one most prototype edits take, never called. A
    directory listing appended to the change the transaction already carries is
    both accurate and durable, and it costs no extra round trip.
    """
    proto = directory / ".agentforge" / "prototype"
    if not proto.is_dir():
        return summary
    pages = sorted(page.name for page in proto.glob("*.html"))
    if not pages:
        return summary
    return f"{summary}\n\nPrototype pages now present: {', '.join(pages)}."


def artifact_exists(directory, role, agents=None):
    """Is there something of this role's to update?

    The same two tests the sibling step uses, in one place now that three
    callers ask the question: the studio deciding what to offer, the route
    refusing what does not exist, and the transaction re-checking hours later.
    """
    if role == "designer":
        return (directory / ".agentforge" / "prototype" / "index.html").is_file()
    if agents is None:
        agents = ProjectState(directory).read().get("agents", {})
    built = agents.get("developer", {})
    return ((directory / "package.json").is_file()
            and bool(built.get("completed_at") or built.get("status") == "completed"))


def _adopt_revised_documents(directory):
    """Take the revision the studio already made and give it to the project.

    The revision itself is not made here. By the time this runs the composer has
    already posted it and been told the new version - that is what the studio
    shows before asking whether to carry it down. Applying it again here wrote
    the same change twice: two `Customized: …` rows, two version bumps, for one
    sentence. Measured, on the first live run.

    What is left is the part `/customize` does not do. It leaves the project
    "customized", and `adopt_srs` refuses any status but "approved", so the
    project's own copy of the document would otherwise stay as it was and the
    children would read a handoff that predates the change they are being asked
    to apply.
    """
    sid = _srs_id_of(directory)
    approved = requests.post(f"http://127.0.0.1:{SRS_PORT}/projects/{sid}/approve",
                             json={}, timeout=60)
    approved.raise_for_status()
    _adopt(sid, directory)
    detail = requests.get(f"http://127.0.0.1:{SRS_PORT}/projects/{sid}", timeout=30)
    detail.raise_for_status()
    body = detail.json()
    newest = (body.get("versions") or [{}])[-1]
    return {"version": (body.get("project") or {}).get("current_version") or newest.get("version"),
            "diff_summary": newest.get("diff_summary") or []}


SPEC_CHILD_BRIEF = (
    "The parent SRS has been revised at the customer's request. Read the current "
    "handoff files and apply that revision to your own artifact. Preserve unrelated "
    "behavior. Update only your own files and verify the result.\n\n"
    "They asked for:\n{prompt}\n")


def run_spec_change(project, prompt, targets):
    """A change that starts at the specification and is pushed down into the app.

    The mirror image of `synchronize_completed_change`, and deliberately not its
    reflection in one respect: nothing the children do is reported back up. In
    the other direction the document has to learn what an agent did; here the
    document is where the change came from, so posting the children's summaries
    back would merge the same change a second time and bump the version again
    for nothing.
    """
    request_path = getattr(RUN, "request_path", None)
    if request_path is None:
        raise RuntimeError("A specification change must be started through the run queue")
    directory = PROD_DIR / project
    try:
        _spec_change_stages(project, directory, request_path, prompt, targets)
    except Exception as error:                                   # noqa: BLE001
        if SERVER_STOPPING:
            return                  # a resumable transaction, not a failed one
        # Record sync state and error markers for retry tracking in standalone transactions.
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["sync_error"] = str(error)
        atomic_json(request_path, request)
        failed = {"status": "failed", "error": str(error), "request_id": request_path.stem}
        ProjectState(directory).update(sync=failed)
        emit({"type": "sync_state", "project": project, **failed})
        raise


def _spec_change_stages(project, directory, request_path, prompt, targets):
    """The stages themselves, so the wrapper above owns every failure."""
    if not (directory / ".agentforge" / "srs" / "link.json").is_file():
        raise ValueError("This project has no linked specification to revise")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    state = ProjectState(directory)
    stage = request.get("stage", "spec_requested")
    wanted = [role for role in ("designer", "developer") if role in set(targets or ())]

    def checkpoint(next_stage):
        nonlocal stage
        stage = request["stage"] = next_stage
        request.pop("sync_error", None)
        atomic_json(request_path, request)

    emit({"type": "sync_state", "project": project, "status": "running", "source": "srs"})
    state.update(sync={"status": "running", "source": "srs", "request_id": request_path.stem})

    if stage == "spec_requested":
        result = _adopt_revised_documents(directory)
        request["srs_version"] = result.get("version")
        request["spec_diff"] = result.get("diff_summary") or []
        checkpoint("srs_updated")

    # The drawing first, always: the build reads the prototype, so it must be
    # looking at the revised one.
    for role, ready, done_stage in (("designer", "srs_updated", "designer_updated"),
                                    ("developer", "designer_updated", "developer_updated")):
        if stage != ready:
            continue
        agents = state.read().get("agents", {})
        if role not in wanted or not artifact_exists(directory, role, agents):
            checkpoint(done_stage)
            continue
        options = agents.get(role, {}).get("request", {})
        brief = SPEC_CHILD_BRIEF.format(prompt=prompt)
        said = request.get("spec_diff") or []
        if said:
            brief += "\nWhat the specification now says changed:\n" + "\n".join(f"- {line}" for line in said)
        # Share current queue slot with sibling task to prevent deadlocks and loopbacks.
        RUN_QUEUE.set_agent(role)
        run_chat(directory.name, brief, options.get("model") or default_agent_model(),
                 "/prototype" if role == "designer" else "/__builder",
                 options.get("think", True), "", "", role)
        finished = state.read().get("agents", {}).get(role, {})
        if finished.get("status") != "completed":
            raise RuntimeError(f"{role.title()} update did not complete: "
                               f"{finished.get('error') or 'continue the saved run'}. "
                               "The specification already carries the change.")
        checkpoint(done_stage)

    if stage == "developer_updated":
        checkpoint("qa_pending")
    # Verification is the one thing the children know that the document does
    # not, so it alone travels back up.
    if stage == "qa_pending":
        digest = read_qa_change(directory)
        if digest.get("summary_text"):
            result = _sync_parent_documents(directory, request_path, request,
                                            "qa", "qa", digest["summary_text"])
            request["srs_version"] = result.get("version")
            clear_qa_change(directory)
        checkpoint("complete")

    state.update(sync={"status": "completed", "version": request.get("srs_version"), "source": "srs"})
    emit({"type": "sync_state", "project": project, "status": "completed",
          "version": request.get("srs_version")})


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
    if source == "designer":
        summary = _with_screen_inventory(directory, summary)
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
        checkpoint("qa_pending")
    if stage == "sibling_completed":
        result = _sync_parent_documents(directory, request_path, request, "mirror", sibling, request["sibling_summary"])
        request["srs_version"] = result.get("version")
        checkpoint("qa_pending")
    # Record QA verification only after tested code revisions are committed to document.
    if stage == "qa_pending":
        digest = read_qa_change(directory)
        if digest.get("summary_text"):
            result = _sync_parent_documents(directory, request_path, request,
                                            "qa", "qa", digest["summary_text"])
            request["srs_version"] = result.get("version")
            clear_qa_change(directory)
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
