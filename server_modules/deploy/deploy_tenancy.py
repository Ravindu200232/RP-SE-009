# Each person's deployments and deployment accounts (runtime part; see tenancy.py).
"""Deploying on a shared AgentForge: your GitHub, your AWS, your Vercel, your database.

The deployment agent was written for one person at one desk, so it signs in
with whatever that machine is signed in to: the `gh` login, the Vercel CLI's
login, every AWS profile in ~/.aws. With many people on one machine, that is
everyone deploying into the owner's accounts, and everyone able to pick anyone
else's AWS profile.

So each person's accounts are kept with their account (auth_db.py, the secrets
encrypted), a run is started with its owner named, and every request to the
agent is rewritten for the person making it: their AWS profiles are named for
them and they cannot name anyone else's, the machine-wide logins are refused,
and a status or a list shows only what is theirs. The agent itself looks the
owner's tokens up for each run (deployment_agent/owner_credentials.py) and
never falls back to the machine's.
"""
DEPLOY_JOB_OWNERS: dict = {}
_RUN_PROJECTS: dict = {}
# Logins that sign the whole machine in, and so sign everyone in.
MACHINE_LOGINS = {"github", "vercel", "ollama"}
GITHUB_TOKEN_SCOPES = "repo,workflow"


def _profile_prefix(user) -> str:
    return f"af-{str(user['id'])[-10:]}-"


def aws_profile_for(user, name: str) -> str:
    """The AWS CLI profile a name means for this person: theirs, never anyone else's."""
    prefix = _profile_prefix(user)
    base = re.sub(r"[^A-Za-z0-9_\-]", "-", str(name or "").strip()).strip("-") or "console"
    if base.startswith(prefix):
        return base
    # Someone else's namespaced name means nothing here; what is left of it does.
    return prefix + (re.sub(r"^af-[0-9a-f]{10}-", "", base) or "console")


def deploy_settings_for(user) -> dict:
    """What a deployment for this person uses, in the shape the old settings had."""
    saved = auth_db.user_settings(user["id"]) if user else {}
    return {**saved, "aws_region": saved.get("aws_region") or "ap-south-1"}


def deploy_summary_for(user) -> dict:
    """What this person has connected, and nothing that could be replayed."""
    if not user:
        return {}
    saved = auth_db.user_settings(user["id"])
    token = saved.get("vercel_token", "")
    mongo = _deploy_mongo_uri(saved)
    return {
        "vercel_cli_signed_in": False,
        "aws_profile": saved.get("aws_profile", ""),
        "aws_region": saved.get("aws_region", ""),
        "aws_start_url": saved.get("aws_start_url", ""),
        "aws_sso_region": saved.get("aws_sso_region", ""),
        "vercel_token_set": bool(token),
        "vercel_token_hint": (f"…{token[-4:]}" if token else ""),
        "mongodb_uri_set": bool(mongo),
        "mongodb_uri_hint": _redact_uri(mongo),
        "github_token_set": bool(saved.get("github_token")),
        "github_login": saved.get("github_login", ""),
        "github_client_id": saved.get("github_client_id", ""),
        "netlify_token_set": bool(saved.get("netlify_token")),
        "azure_credentials_set": bool(saved.get("azure_credentials")),
    }


def github_login_for(token: str) -> str:
    """The GitHub account a token signs in as. Raises ValueError if GitHub refuses it."""
    try:
        answer = requests.get("https://api.github.com/user", timeout=15, headers={
            "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    except requests.RequestException as error:
        raise ValueError(f"GitHub could not be reached: {error}") from None
    if answer.status_code != 200:
        raise ValueError("GitHub did not accept that token")
    return str(answer.json().get("login") or "")


def save_deploy_settings(user, body: dict) -> dict:
    """Keep what this person typed in their own deployment accounts."""
    patch = {}
    # A public value, so it is kept beside the region rather than as a secret:
    # it identifies the OAuth app, it cannot act on its own, and the sign-in
    # that uses it happens on GitHub.
    if "github_client_id" in body:
        patch["github_client_id"] = str(body["github_client_id"]).strip()
    for key in ("aws_region", "aws_start_url", "aws_sso_region"):
        if key in body:
            patch[key] = str(body[key]).strip()
    if "aws_profile" in body:
        name = str(body["aws_profile"]).strip()
        patch["aws_profile"] = aws_profile_for(user, name) if name else ""
    for key in ("vercel_token", "netlify_token", "azure_credentials", "deploy_mongodb_uri"):
        if key in body:
            value = str(body[key]).strip()
            if key == "azure_credentials" and value and value != "-":
                from deployment_agent.hosted import validate_azure_credentials
                validate_azure_credentials(value)
            patch[key] = "" if value == "-" else value
    if "github_token" in body:
        value = str(body["github_token"]).strip()
        if value and value != "-":
            patch["github_login"] = github_login_for(value)
            patch["github_token"] = value
        else:
            patch["github_token"] = patch["github_login"] = ""
    if patch:
        auth_db.save_user_settings(user["id"], patch)
    return deploy_summary_for(user)


def deploy_request_for(user, method: str, path: str, body):
    """The request to send the agent on this person's behalf: (path, body, answer).

    `path` is the agent's own (with /api). When `answer` is not None the
    request is not sent at all and that is the reply. Raises ValueError for
    one this person may not make.
    """
    body = dict(body) if isinstance(body, dict) else {}
    route = path.split("?")[0]
    if method != "POST":
        return path, body, None
    if route == "/api/onboarding/login":
        tool = str(body.get("tool") or "")
        if tool in MACHINE_LOGINS:
            raise ValueError(
                "GitHub and Vercel are connected with a token in Deployment accounts - "
                "a sign-in here would sign this whole machine in, for everyone on it.")
        body["profile"] = aws_profile_for(user, body.get("profile") or "console")
    elif route in ("/api/aws/vercel/status", "/api/aws/netlify/status", "/api/aws/azure/status"):
        # Each hosted provider is checked the same way: this person's saved
        # credential unless the box in front of them holds a new one.
        provider = route.rsplit("/", 2)[1]
        saved_as = {"vercel": "vercel_token", "netlify": "netlify_token",
                    "azure": "azure_credentials"}[provider]
        token = str(body.get("token") or "").strip() or deploy_settings_for(user).get(saved_as, "")
        if not token:
            return path, body, {"connected": False,
                                "error": f"no {provider.title()} credentials saved"}
        body["token"] = token
    elif route.startswith("/api/aws/") or route.startswith("/api/runs/"):
        # Only this person's AWS sign-ins - and never none, which to boto3 means
        # this machine's own credentials. A vault reference is never taken from
        # a request: each profile already knows its own (aws_onboarding.py).
        body.pop("credential_reference", None)
        default = ("deployment-agent" if route == "/api/aws/sso/select"
                   else deploy_settings_for(user).get("aws_profile") or "console")
        for key in ("profile", "aws_profile"):
            body[key] = aws_profile_for(user, body.get(key) or default)
    if route.startswith("/api/runs/"):
        body["owner"] = user["id"]
    return path, body, None


def run_project(run_id: str) -> str:
    """The project a deployment run belongs to, or ""."""
    run_id = str(run_id or "")
    if run_id in _RUN_PROJECTS:
        return _RUN_PROJECTS[run_id]
    try:
        run = _deploy_call("GET", f"/api/runs/{run_id}", timeout=(2, 20))
    except Exception:                                                # noqa: BLE001
        return ""
    project = _project_of_path(str(run.get("project_path") or ""))
    if project:
        _RUN_PROJECTS[run_id] = project
    return project


def visible_onboarding(user, status: dict) -> dict:
    """The agent's view of the machine's accounts, cut down to this person's."""
    prefix = _profile_prefix(user)
    status = dict(status or {})
    status["aws_profiles"] = [p for p in status.get("aws_profiles") or []
                              if str(p).startswith(prefix)]
    status["aws_identities"] = {name: value for name, value in
                                (status.get("aws_identities") or {}).items()
                                if str(name).startswith(prefix)}
    status["aws_authenticated"] = bool(status["aws_identities"])
    saved = deploy_settings_for(user)
    status["github_authenticated"] = bool(saved.get("github_token"))
    status["github_account"] = saved.get("github_login", "")
    return status


def visible_runs(user, answer: dict) -> dict:
    runs = [run for run in (answer or {}).get("runs") or []
            if auth_db.owns(user, "project", _project_of_path(str(run.get("project_path") or "")))]
    return {**(answer or {}), "runs": runs}


def deploy_credentials_provider(owner: str) -> dict:
    """What the deployment agent asks for, for each run: its owner's tokens."""
    try:
        return auth_db.deploy_secrets(owner)
    except Exception as error:                                       # noqa: BLE001
        log.warning(f"deployment credentials for {owner}: {error}")
        return {}
