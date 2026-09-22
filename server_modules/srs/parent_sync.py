"""A durable, one-way change transaction: source -> SRS -> sibling -> SRS."""

def run_manual_prototype_change(project, summary):
    """Verify direct HTML edits before their existing durable SRS transaction."""
    from builder_agent.prototype_check import validate_all, repair_prompt
    from qa_agent.browser import Browser
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


MAX_REDRAWN_PAGES = 12


def _as_evidence(change):
    """A completed change as something to put in the next agent's brief.

    The sentence an agent writes about its own work is a summary of intent.
    The agent on the other side of the handoff has to reproduce that work, and
    for it the files are the request: which ones moved, and what in them. Both
    travel now, the sentence still first, because it is what says why.
    """
    from server_modules.services import change_set
    detail = change_set.brief(change)
    return ("\n\n" + detail) if detail else ""


def _changed_pages(directory, change):
    """The prototype pages this change rewrote, in the form a drawing reads.

    The wireframe for a screen and the prototype of that screen are the same
    screen twice, and until now only one of them ever heard about a change: the
    document was told a sentence, and the drawing was re-derived from the
    sentence. So a section moved by hand in the prototype left the wireframe
    showing the old arrangement, with nothing anywhere recording that the two
    had parted company.

    What travels is the page's structure rather than its markup - see
    `page_outline` for why - and only for pages the specification actually
    names. A confirmation screen the document never mentioned has no wireframe
    to update, and inventing a route for it would put one in the specification.
    """
    from server_modules.services import change_set, prototype_routes
    from server_modules.services.page_outline import outline
    names = [name for name in change_set.touched(change, under=".agentforge/prototype/")
             if name.lower().endswith(".html")]
    routes = prototype_routes.route_for_files(directory, names)
    pages, seen = [], set()
    for name in names:
        route = routes.get(name.rsplit("/", 1)[-1])
        if not route or route in seen:
            continue
        try:
            structure = outline((directory / name).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue                       # deleted by the same change; nothing to draw
        if not structure:
            continue
        seen.add(route)
        pages.append({"route": route, "outline": structure})
    return pages[:MAX_REDRAWN_PAGES]


# Next.js file-system routing patterns.
# `app/foo/page.jsx`          → /foo
# `app/foo/[id]/page.jsx`     → /foo/[id]
# `pages/foo.jsx`             → /foo
# `src/app/foo/page.jsx`      → /foo
_NEXTJS_PAGE_SUFFIXES = ("/page.jsx", "/page.tsx", "/page.js", "/page.ts")
_PAGES_DIR_EXT = {".jsx", ".tsx", ".js", ".ts"}

# JSX/TSX files that are obviously not page files.
_NON_PAGE_NAMES = {
    "layout", "loading", "error", "not-found", "template", "default",
    "_app", "_document", "_error", "middleware",
}


def _route_from_nextjs_path(rel: str) -> str | None:
    """Derive a URL route from a Next.js source file path.

    Handles both App Router (`app/.../page.jsx`) and Pages Router
    (`pages/foo.jsx` or `src/pages/foo.jsx`). Returns None for files that
    are clearly not page files (layouts, hooks, components, etc.).
    """
    import re as _re
    parts = rel.replace("\\", "/").split("/")
    # Must be inside app/ or pages/ (possibly under src/)
    try:
        if "src" in parts:
            parts = parts[parts.index("src") + 1:]
        root = parts[0] if parts else ""
    except (IndexError, ValueError):
        return None

    if root == "app":
        # App Router: last segment must be "page[.ext]"
        stem = parts[-1].rsplit(".", 1)[0].lower() if parts else ""
        if stem != "page":
            return None
        route_parts = parts[1:-1]  # strip "app" and "page.jsx"
        route_parts = [p for p in route_parts if not p.startswith("(")]  # strip route groups
        route = "/" + "/".join(route_parts) if route_parts else "/"
        return route

    if root == "pages":
        if len(parts) < 2:
            return None
        stem = parts[-1].rsplit(".", 1)[0].lower()
        suffix = parts[-1].rsplit(".", 1)[-1].lower()
        if suffix not in ("jsx", "tsx", "js", "ts"):
            return None
        if stem in _NON_PAGE_NAMES or stem.startswith("_"):
            return None
        if stem == "index":
            route_parts = parts[1:-1]
        else:
            route_parts = parts[1:-1] + [stem]
        route = "/" + "/".join(route_parts) if route_parts else "/"
        return route

    return None


def _changed_pages_from_build(directory, change) -> list[dict]:
    """The pages a developer (build) change rewrote, derived from JSX/TSX files.

    The prototype HTML pass covers `.html` prototype changes; this covers the
    React source files a build agent writes. Both return the same shape so the
    wireframe redraw call treats them identically.

    Route resolution uses Next.js file-system conventions first, then falls
    back to name-based matching against the pages the specification named.
    Pages that cannot be reliably matched are silently skipped — inventing a
    route is worse than leaving a wireframe unchanged.
    """
    from server_modules.services import change_set
    from server_modules.services.page_outline import outline_jsx, title_of_jsx
    from server_modules.services.prototype_routes import specified_pages

    # Only consider source-code files (not CSS, JSON, config)
    touched = change_set.touched(change)
    source_files = [
        name for name in touched
        if any(name.lower().endswith(ext) for ext in (".jsx", ".tsx"))
        and not any(seg.startswith(".") or seg in ("node_modules", ".next")
                    for seg in name.replace("\\", "/").split("/"))
    ]
    if not source_files:
        return []

    # Build a set of routes the specification knows about
    spec_pages = specified_pages(directory)
    if not spec_pages:
        return []
    spec_routes = {str(p.get("route")): p for p in spec_pages if p.get("route")}
    spec_page_names = {
        str(p.get("page_name") or p.get("name") or ""): str(p.get("route"))
        for p in spec_pages
        if (p.get("page_name") or p.get("name")) and p.get("route")
    }

    pages, seen = [], set()
    for rel in source_files:
        # --- 1. Next.js file-system route derivation ---
        route = _route_from_nextjs_path(rel)

        # --- 2. Name-based fallback against the specification ---
        if not route or route not in spec_routes:
            import re as _re
            stem = rel.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
            stem_lower = stem.lower()
            stem_words = set(_re.split(r"[^a-z0-9]+", stem_lower))
            stem_words -= {"page", "screen", "view", "index", "component"}
            best_route, best_score = None, 0
            for spec_route in spec_routes:
                route_words = set(_re.split(r"[^a-z0-9]+", spec_route.lower()))
                score = len(stem_words & route_words)
                if score > best_score:
                    best_score, best_route = score, spec_route
            route = best_route if best_score > 0 else None

        if not route or route in seen:
            continue

        # --- 3. Read the JSX file and extract its structural outline ---
        try:
            jsx_src = (directory / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        structure = outline_jsx(jsx_src)
        if not structure:
            continue

        seen.add(route)
        pages.append({"route": route, "outline": structure})

    return pages[:MAX_REDRAWN_PAGES]




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


def _drawings_settled(sid, seconds=900):
    """Wait for the SRS to finish drawing before taking a copy of its pages.

    A page is a model call and there are as many as the specification has
    pages, so a save schedules the drawing and returns long before it lands.
    Adopting at that moment copies the previous version's pages - every time,
    for as long as the project lives, because nothing adopts again afterwards.
    One project was found nine versions on with its wireframes still stamped
    1.8.0 while the specification's own copies said 1.9.0.

    Bounded and forgiving: an SRS that cannot answer is not a reason to fail a
    change, and the pages already on disk are what the studio would have shown
    anyway.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if SERVER_STOPPING:
            return
        try:
            response = requests.get(f"http://127.0.0.1:{SRS_PORT}/projects/{sid}/wireframes",
                                    timeout=30)
            response.raise_for_status()
            if not response.json().get("drawing"):
                return
        except (requests.RequestException, ValueError):
            return
        time.sleep(3)


def _adopt(sid, directory):
    """Pull the revised documents back into the project, quietly."""
    _drawings_settled(sid)
    RUN.document_sync = True
    try:
        if not adopt_srs(sid, directory):
            raise RuntimeError("The SRS updated, but its project documents could not be refreshed")
    finally:
        RUN.document_sync = False


def _sync_parent_documents(directory, request_path, request, label, role, summary, pages=()):
    sid = _srs_id_of(directory)
    checkpoint = request.setdefault("srs_jobs", {})
    job_id = checkpoint.get(label)
    if not job_id:
        body = {"change_id": f"{request_path.stem}-{label}", "source": role,
                "summary": summary[:12000]}
        if pages:
            body["pages"] = list(pages)
        response = requests.post(f"http://127.0.0.1:{SRS_PORT}/jobs", json={
            "path": f"/projects/{sid}/changes", "method": "POST", "body": body}, timeout=30)
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
    "handoff files and `.agentforge/design-spec.json` when it exists, then apply that "
    "revision to your own artifact. Preserve unrelated "
    "behavior. Update only your own files and verify the result.\n\n"
    "They asked for:\n{prompt}\n")


def run_spec_change(project, prompt, targets, change_request_id=""):
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
    if change_request_id:
        from server_modules.services.change_requests import update as update_change_request
        update_change_request(directory, change_request_id, status="running", started_at=time.time())
    try:
        _spec_change_stages(project, directory, request_path, prompt, targets)
    except Exception as error:                                   # noqa: BLE001
        if SERVER_STOPPING:
            return                  # a resumable transaction, not a failed one
        if change_request_id:
            from server_modules.services.change_requests import update as update_change_request
            update_change_request(directory, change_request_id, status="failed", error=str(error))
        # Record sync state and error markers for retry tracking in standalone transactions.
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["sync_error"] = str(error)
        atomic_json(request_path, request)
        failed = {"status": "failed", "error": str(error), "request_id": request_path.stem}
        ProjectState(directory).update(sync=failed)
        emit({"type": "sync_state", "project": project, **failed})
        raise
    if change_request_id:
        from server_modules.services.change_requests import update as update_change_request
        update_change_request(directory, change_request_id, status="completed", completed_at=time.time())


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
        if role == "developer":
            # The drawing went first, so the build is shown what it did rather
            # than left to infer it from the same sentence a second time.
            from server_modules.services import change_set
            brief += _as_evidence(change_set.read(directory, "designer"))
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

    from server_modules.services import change_set
    for role in ("designer", "developer"):
        change_set.clear(directory, role)
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
    from server_modules.services import change_set
    # What the run did, rather than what it said about itself. Kept until the
    # transaction completes, so a resumed one still has it.
    source_change = change_set.read(directory, source)

    def checkpoint(next_stage):
        nonlocal stage
        stage = request["stage"] = next_stage
        request.pop("sync_error", None)
        atomic_json(request_path, request)

    emit({"type": "sync_state", "project": directory.name, "status": "running", "source": source})
    state.update(sync={"status": "running", "source": source, "request_id": request_path.stem})
    if stage == "source_completed":
        # Designer changes: read prototype HTML outline
        # Developer changes: read JSX/TSX outline from built files
        if source == "designer":
            changed_pages = _changed_pages(directory, source_change)
        else:
            changed_pages = _changed_pages_from_build(directory, source_change)
        result = _sync_parent_documents(directory, request_path, request, "source", source, summary,
                                        changed_pages)
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
            + summary + _as_evidence(source_change))
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
        mirrored = change_set.read(directory, sibling)
        # When the sibling is designer (prototype), read HTML outline.
        # When the sibling is developer (build), read JSX outline.
        if sibling == "designer":
            sibling_pages = _changed_pages(directory, mirrored)
        else:
            sibling_pages = _changed_pages_from_build(directory, mirrored)
        result = _sync_parent_documents(directory, request_path, request, "mirror", sibling,
                                        request["sibling_summary"],
                                        sibling_pages)
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
    change_set.clear(directory, source)
    change_set.clear(directory, sibling)
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
