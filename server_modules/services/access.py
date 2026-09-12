"""What a request needs before a shared AgentForge will answer it.

Every API route is one of: open to anyone signed in, about one project, about
one specification, about one deployment, about the run in progress, or for the
admin. The rule is read off the path and the body and nothing else, so it can
be checked before the handler does anything at all.

Default deny: a route not listed here is the admin's, so a route added later is
closed until someone decides who it is for.
"""
from __future__ import annotations

from urllib.parse import unquote

# Anyone who is signed in. The settings answer each person with their own.
USER_GET = {"/projects", "/models", "/srs-status", "/deploy-status", "/settings",
            "/image-check", "/mongo"}
USER_POST = {"/logo-prompt", "/tune", "/build-attach", "/upload-project", "/jobs",
             "/build/cancel", "/settings"}
# The run in progress, which is one person's at a time.
RUN_GET = {"/decisions"}
RUN_POST = {"/decision"}
# One project, named in the path.
PROJECT_GET = ("/runtime/", "/files/", "/stream/", "/session/", "/qa-screenshot/",
               "/prototype/", "/qa/", "/srs-results/", "/qa-pdf/", "/srs-pdf/",
               "/deploy-results/")
# One project, named in the body.
PROJECT_POST = {"/resume", "/delete-project", "/save-file", "/element-edit", "/feature",
                "/agent-update", "/stream", "/shot", "/undo", "/deploy-start",
                "/projects/assign", "/preview-link"}
# One project if the body names one, otherwise nobody's in particular.
MAYBE_PROJECT_POST = {"/attach", "/image", "/image-upload"}
# One specification, named in the body.
SRS_POST = {"/discard-srs", "/keep-srs"}


def rule(method: str, path: str, body: dict | None = None) -> tuple:
    """(what the request needs, the thing it is about) for one API request.

    `path` is the part after /__agentforge/api, without its query string.
    """
    body = body if isinstance(body, dict) else {}
    method = str(method or "GET").upper()
    path = str(path or "")
    if path.startswith("/srs/"):
        return _srs_rule(method, path[4:], body)
    if path.startswith("/deploy/"):
        return _deploy_rule(method, path[7:], body)
    if method == "GET":
        if path in USER_GET:
            return ("user", "")
        if path in RUN_GET:
            return ("run", "")
        if path.startswith("/jobs/"):
            return ("job", path[6:].strip("/"))
        for prefix in PROJECT_GET:
            if path.startswith(prefix):
                return ("project", unquote(path[len(prefix):]).strip("/").split("/", 1)[0])
        return ("admin", "")
    if path.startswith("/runtime/") and path.endswith("/activity"):
        return ("project", unquote(path[9:-9]).strip("/"))
    if path.startswith("/open/"):
        return ("project", unquote(path[6:]).strip("/"))
    if path in PROJECT_POST:
        return ("project", str(body.get("project") or "").strip())
    if path in MAYBE_PROJECT_POST:
        project = str(body.get("project") or "").strip()
        return ("project", project) if project else ("user", "")
    if path in SRS_POST:
        return ("srs", str(body.get("srs_id") or "").strip())
    if path == "/agent-build":
        srs = str(body.get("srs_id") or "").strip()
        return ("srs", srs) if srs else ("user", "")
    if path in RUN_POST:
        return ("run", "")
    if path in USER_POST:
        return ("user", "")
    return ("admin", "")


def _srs_rule(method: str, path: str, body: dict) -> tuple:
    """The SRS agent's routes. Each of its projects is one person's specification."""
    if path == "/jobs" and method == "POST":
        inner = str(body.get("path") or "").split("?")[0]
        if inner == "/projects":
            # A new one becomes its creator's; a list shows only their own.
            post = str(body.get("method") or "POST").upper() == "POST"
            return ("srs-create", "") if post else ("user", "")
        key = srs_project(inner)
        return ("srs", key) if key else ("admin", "")
    if path.startswith("/jobs/") and method == "GET":
        return ("srs-job", path[6:].strip("/"))
    if path == "/projects" and method == "GET":
        return ("user", "")
    key = srs_project(path)
    return ("srs", key) if key else ("admin", "")


def srs_project(path: str) -> str:
    """The specification a path on the SRS agent is about, or ""."""
    parts = [part for part in str(path or "").split("?")[0].split("/") if part]
    if len(parts) >= 2 and parts[0] == "projects":
        return unquote(parts[1])
    return ""


def _deploy_rule(method: str, path: str, body: dict) -> tuple:
    """The deployment agent's routes, as the studio names them (without /api).

    A run is one person's because its project is. The account routes are
    answered for the person asking and nobody else (deploy_tenancy.py).
    """
    parts = [part for part in str(path or "").split("?")[0].split("/") if part]
    if parts[:1] == ["jobs"]:
        if len(parts) == 1 and method == "POST":
            inner = str(body.get("path") or "")
            return _deploy_rule(str(body.get("method") or "POST").upper(), inner,
                                body.get("body") if isinstance(body.get("body"), dict) else {})
        if len(parts) == 2 and method == "GET":
            return ("deploy-job", parts[1])
        return ("admin", "")
    if parts[:1] == ["runs"]:
        if len(parts) == 1:
            return ("user", "")
        if parts[1] == "analyze":
            return ("project-path", str(body.get("path") or ""))
        return ("deploy-run", unquote(parts[1]))
    if parts[:1] in (["onboarding"], ["aws"], ["mongodb"], ["health"]):
        return ("user", "")
    return ("admin", "")
