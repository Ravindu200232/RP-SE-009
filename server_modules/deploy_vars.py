"""What a deployment needs from the customer that is a secret or a value only they know."""
from __future__ import annotations

import re
import threading
import time
from typing import Any
from urllib.parse import unquote, urlparse, urlsplit, urlunsplit

from . import config

_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
# Names that would change how the agent's own tools run, not what the deployed application is told.
_RESERVED = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "HOME", "USERPROFILE", "TEMP", "TMP", "SHELL",
             "NODE_OPTIONS", "NODE_PATH", "PYTHONPATH", "PYTHONHOME", "LD_PRELOAD", "LD_LIBRARY_PATH",
             "NPM_CONFIG_USERCONFIG", "GIT_SSH_COMMAND", "GIT_ASKPASS", "VERCEL_TOKEN", "NETLIFY_AUTH_TOKEN",
             "GH_TOKEN", "GITHUB_TOKEN", "AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}
MAX_VARIABLES = 50
MAX_BYTES = 8192
_LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}


def valid_name(name: str) -> str:
    """The variable's name, or why it cannot be one."""
    name = str(name or "").strip()
    if not _NAME.match(name):
        raise ValueError("a variable name is capital letters, digits and underscores, starting with a letter "
                         "(for example ADMIN_EMAIL)")
    if name in _RESERVED or name.startswith("AGENTFORGE_"):
        raise ValueError(f"{name} is used by the machine itself and cannot be set here")
    return name


def names() -> list[dict[str, Any]]:
    """The saved variables as names and hints. Never the values."""
    saved = config.setting("deploy_env", {}) or {}
    return [{"name": name, "hint": str(value)[-4:] if len(str(value)) > 8 else ""}
            for name, value in sorted(saved.items())]


def save(name: str, value: str, secret: bool = True) -> list[dict[str, Any]]:
    """Save one variable; an empty value removes it. `secret` is whether it was asked for as one."""
    name = valid_name(name)
    value = str(value or "")
    if len(value.encode("utf-8")) > MAX_BYTES:
        raise ValueError(f"a value can be at most {MAX_BYTES} bytes")
    saved = dict(config.setting("deploy_env", {}) or {})
    kinds = dict(config.setting("deploy_env_secret", {}) or {})
    if not value.strip():
        saved.pop(name, None)
        kinds.pop(name, None)
    else:
        if name not in saved and len(saved) >= MAX_VARIABLES:
            raise ValueError(f"at most {MAX_VARIABLES} variables can be saved")
        saved[name], kinds[name] = value, bool(secret)
    config.save_settings({"deploy_env": saved, "deploy_env_secret": kinds})
    return names()


_SECRET_NAME = re.compile(r"PASS|SECRET|TOKEN|KEY|URI|CRED", re.IGNORECASE)


def secret_values() -> list[str]:
    """The saved values that are secrets, for hiding them wherever a tool might print one. A plain value (a name, an."""
    kinds = config.setting("deploy_env_secret", {}) or {}
    found = []
    for name, value in (config.setting("deploy_env", {}) or {}).items():
        secret = kinds.get(name)
        if secret is None:
            secret = bool(_SECRET_NAME.search(str(name)))
        if secret and isinstance(value, str) and len(value) >= 8:
            found.append(value)
    database = config.setting("deploy_mongodb_uri", "") or ""
    if not database:
        return found
    # The databases a build is handed are this string with another name in it, so the password is hidden on its own too.
    password = unquote(urlparse(database).password or "")
    return [*found, database, *(uri for uri in build_databases() if uri), *([password] if len(password) >= 8 else [])]


# What a question may ask the studio to try before it accepts a value.
CHECKS: tuple[str, ...] = ("mongodb",)


def accept(question: dict, value: str) -> str:
    """Take the value a question asked for: try it if the question says how, keep it by name. Returns why not, or ''."""
    try:
        name = valid_name(question.get("variable", ""))
    except ValueError as exc:
        return str(exc)
    value = str(value or "")
    if not value.strip():
        return "Type a value first."
    if question.get("check") == "mongodb":
        from . import mongo_check

        result = mongo_check.check(value)
        if not result.get("ok"):
            return str(result.get("message") or "That connection string could not be used.")
    try:
        save(name, value, secret=bool(question.get("secret", True)))
    except ValueError as exc:
        return str(exc)
    return ""


def check_database_uri(uri: str, allow_local: bool = False) -> str:
    """The production database connection string, or why it cannot be one (a hosted app cannot reach this computer)."""
    uri = str(uri or "").strip()
    if not uri:
        return ""
    parsed = urlparse(uri)
    if parsed.scheme not in ("mongodb", "mongodb+srv"):
        raise ValueError("a MongoDB connection string starts with mongodb:// or mongodb+srv://")
    if allow_local:
        return uri
    hosts = (parsed.netloc.rsplit("@", 1)[-1]).split(",")
    for host in hosts:
        name = host.strip("[]").rsplit(":", 1)[0].strip("[]").lower() if not host.startswith("[") else host.strip("[]").lower()
        if not name or name in _LOOPBACK or name.endswith((".local", ".localhost")):
            raise ValueError("that address points at this computer: a deployed application cannot reach it. "
                             "Use a database that is reachable from the internet (for example MongoDB Atlas), "
                             "never a local MongoDB.")
    return uri


# --- the database connection is the studio's to provide, never a question ---------------------------------------------------

_DATABASE_VARIABLE = re.compile(r"^(MONGO\w*|DATABASE_URL|DB_URI|DB_URL)$")
_DATABASE_WORDS = re.compile(r"mongo\w*\W+(?:\w+\W+){0,2}(?:connection|uri|url|string)|connection\s+(?:string|uri|url)|\bMONGODB_URI\b",
                             re.IGNORECASE)


# What a question is about when it is not the database: a sign-in, a command-line tool, an account, a token, a name.
_OTHER_SUBJECT = re.compile(r"\b(sign(?:ed|s)?[ -]?(?:in|out)|log(?:ged|s)?[ -]?(?:in|out)|login|authenticat\w*|cli|token|"
                            r"account|team|site name|subdomain|domain|address is (?:taken|used))\b", re.IGNORECASE)


def asks_for_database(question: dict) -> bool:
    """Whether a question asks the customer for the database connection: a MongoDB connection string, an address, a variable."""
    if _DATABASE_VARIABLE.match(str(question.get("variable") or "").strip().upper()) or str(question.get("check") or "") == "mongodb":
        return True
    asked, why = str(question.get("question") or ""), str(question.get("why") or "")
    if _DATABASE_WORDS.search(asked):
        return True
    if _OTHER_SUBJECT.search(asked):
        return False
    return bool(_DATABASE_WORDS.search(why))


def database_state() -> dict[str, bool]:
    """Where the database connection stands: `saved` (a connection string, or MONGODB_URI saved by name) and `atlas` (an Atlas."""
    from . import mongo_connect

    saved = bool(config.setting("deploy_mongodb_uri", "") or "MONGODB_URI" in (config.setting("deploy_env", {}) or {}))
    return {"saved": saved, "atlas": bool(mongo_connect.credentials_saved() or mongo_connect.cli_account())}


def provided(question: dict, always: bool = False) -> str:
    """The reason a question about the database connection is not asked, or "" when it is the customer's to answer."""
    from . import prompts

    if not asks_for_database(question):
        return ""
    if not always:
        state = database_state()
        if not (state["saved"] or state["atlas"]):
            return ""
    return prompts.load("changes/database-provided").strip()


# --- the database a build runs on ---------------------------------------------------------------------------------------

BUILD_CHECK_SECONDS = 120          # how long "the connected cluster answers" (or does not) is remembered
NOTE_SECONDS = 600                 # how often the customer is told, per project, that it does not
_checked: dict[str, tuple[float, bool, str]] = {}
_noted: dict[str, float] = {}
_stages: dict[str, str] = {}              # how far the last look at each string got (`mongo_check` stage)
_check_lock = threading.Lock()


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")[:30]


def with_database(uri: str, database: str) -> str:
    """`uri` pointed at `database` on the same cluster, its credentials and options as they were."""
    parts = urlsplit(uri)
    return urlunsplit((parts.scheme, parts.netloc, "/" + database, parts.query, ""))


def build_databases(project: str = "") -> tuple[str, str]:
    """The connected cluster's databases for a build, (the app's, the tests'), or ("", "") when no cluster is connected."""
    uri = str(config.setting("deploy_mongodb_uri", "") or "")
    if not uri:
        return "", ""
    base = _slug(unquote(urlsplit(uri).path.strip("/")))
    if project and (not base or base in GENERIC_DATABASES):
        base = _project_database(project, base)
    base = base or "app"
    return with_database(uri, f"{base}_build"), with_database(uri, f"{base}_test")


# The database a string names when the studio made it before strings named none: every project built then shares it.
GENERIC_DATABASES = {"app"}


def _project_database(project: str, shared: str) -> str:
    """The name a project's databases are built from when the saved string names none of its own (or only the shared `app`)."""
    from . import store

    record = store.get(project) or {}
    pinned = str(record.get("mongo_database") or "")
    if pinned:
        return pinned
    built = bool(shared) and (config.record_dir(project) / "build" / "report.json").is_file()
    chosen = shared if built else (_slug(record.get("name")) or _slug(project) or shared)
    if record.get("id") == project and chosen:
        try:
            store.update(project, mongo_database=chosen)
        except Exception:  # noqa: BLE001 - not pinned this time is only asked again next time
            pass
    return chosen


def cluster_answers(uri: str) -> tuple[bool, str]:
    """Whether the connected cluster answers right now, and if not what it said (a paused cluster has no address, a wrong."""
    with _check_lock:
        seen = _checked.get(uri)
        if seen and time.time() - seen[0] < BUILD_CHECK_SECONDS:
            return seen[1], seen[2]
        from . import mongo_check

        try:
            result = mongo_check.check(uri)
            answer = (bool(result.get("ok")), str(result.get("message") or ""))
            _stages[uri] = str(result.get("stage") or "")
        except Exception as exc:  # noqa: BLE001 - a check that cannot run is not an answer from the cluster either way
            answer = (False, f"it could not be checked ({str(exc)[:120]})")
            _stages[uri] = "error"
        _checked[uri] = (time.time(), *answer)
        return answer


def forget_check(uri: str) -> None:
    """Ask the cluster again next time instead of using the remembered answer (after the customer said to try again)."""
    with _check_lock:
        _checked.pop(uri, None)


def refused_login(uri: str) -> bool:
    """Whether the last look at this connection string found that Atlas answers but refuses its username or password."""
    seen = _checked.get(uri)
    return bool(seen and not seen[1] and _stages.get(uri) == "auth")


def tell_unreachable(project: str, why: str) -> None:
    """Say, once in a while, that the connected cluster cannot be used and what the build is doing instead."""
    if not project or time.time() - _noted.get(project, 0) < NOTE_SECONDS:
        return
    _noted[project] = time.time()
    from . import bus

    text = (f"The MongoDB cluster you connected could not be reached ({why or 'no answer'}), so this build's database commands "
            "use a MongoDB on this computer (localhost:27017), which may not be running. If the cluster is paused, resume it in "
            "MongoDB Atlas: the next command uses it again.")
    bus.log(project, "WARN", text)
    bus.agent_msg(project, text, title="MongoDB cluster not reachable", kind="narration")


def environment(build: bool = False, project: str = "") -> dict[str, str]:
    """What a deployment run's commands are given, beyond its project's own Supabase connection."""
    env = {str(name): str(value) for name, value in (config.setting("deploy_env", {}) or {}).items()}
    database = str(config.setting("deploy_mongodb_uri", "") or "")
    if not database:
        return env
    if not build:
        env.setdefault("MONGODB_URI", build_databases(project)[0])
        return env
    answers, why = cluster_answers(database)
    if answers:
        app, tests = build_databases(project)
        env.setdefault("MONGODB_URI", app)
        env.setdefault("TEST_MONGODB_URI", tests)
    else:
        tell_unreachable(project, why)
    return env
