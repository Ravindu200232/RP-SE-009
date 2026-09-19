"""Netlify delivery and isolated Azure CLI identity for hosted targets."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import requests

from . import owner_credentials
from .security import redact_text
from .tools import run_command


def netlify_api(method: str, path: str, data=None):
    token = str(owner_credentials.current().get("netlify_token") or "")
    if not token:
        raise ValueError("Connect your Netlify access token in Deployment accounts")
    response = requests.request(method, f"https://api.netlify.com/api/v1/{path.lstrip('/')}",
                                headers={"Authorization": f"Bearer {token}"}, json=data, timeout=40)
    if not response.ok:
        raise RuntimeError(f"Netlify HTTP {response.status_code}: {redact_text(response.text[:1000])}")
    return response.json() if response.content else {}


NETLIFY_HINT = ("Create a personal access token at app.netlify.com, under "
                "User settings, Applications.")
AZURE_HINT = ("Paste the service principal JSON from "
              "`az ad sp create-for-rbac --sdk-auth`.")


def netlify_connection_status(supplied: str = "") -> dict:
    """Non-throwing summary for the dashboard, like Vercel's.

    Netlify had a paste box and nothing else: a token that was wrong was stored
    exactly as happily as one that worked, and the first anyone heard of it was
    a failed deployment. Asking Netlify who the token belongs to costs one
    request and turns the box into a sign-in.
    """
    token = str(supplied or "").strip() or str(owner_credentials.current().get("netlify_token") or "")
    if not token:
        return {"connected": False, "source": "", "message": NETLIFY_HINT}
    source = "pasted token" if supplied else "saved token"
    try:
        response = requests.get("https://api.netlify.com/api/v1/user",
                                headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if not response.ok:
            return {"connected": False, "source": source,
                    "message": f"Netlify HTTP {response.status_code}: "
                               f"{redact_text(response.text[:200])}"}
        user = response.json() or {}
    except Exception as error:  # noqa: BLE001 - a status check never raises
        return {"connected": False, "source": source, "message": str(error)[:200]}
    return {"connected": True, "source": source, "verified": True,
            "account": user.get("email") or user.get("slug") or "",
            "name": user.get("full_name") or ""}


def azure_connection_status(supplied: str = "") -> dict:
    """The same for Azure, and honest about which half it proved.

    The shape of the service principal JSON can be checked here; the sign-in
    itself needs the Azure CLI, which is on the CI runner and not necessarily on
    this machine. Saying "connected" for a well-formed blob nobody has ever
    signed in with would be the same false comfort the paste box gave, so the
    two are reported apart.
    """
    raw = str(supplied or "").strip() or str(owner_credentials.current().get("azure_credentials") or "")
    if not raw:
        return {"connected": False, "source": "", "message": AZURE_HINT}
    source = "pasted credentials" if supplied else "saved credentials"
    try:
        credentials = validate_azure_credentials(raw)
    except ValueError as error:
        return {"connected": False, "source": source, "message": str(error)}
    account = credentials["subscriptionId"]
    try:
        run_command(["az", "login", "--service-principal",
                     "--username", credentials["clientId"],
                     "--password", credentials["clientSecret"],
                     "--tenant", credentials["tenantId"], "--output", "none"],
                    env=owner_credentials.command_env(), timeout=90, check=True)
    except FileNotFoundError:
        return {"connected": True, "source": source, "verified": False, "account": account,
                "message": "The credentials are complete. The Azure CLI is not on this "
                           "machine, so the sign-in is proved on the CI runner instead."}
    except Exception as error:  # noqa: BLE001 - a status check never raises
        return {"connected": False, "source": source, "account": account,
                "message": redact_text(str(error))[:200]}
    return {"connected": True, "source": source, "verified": True, "account": account}


def validate_azure_credentials(value: str) -> dict:
    try:
        credentials = json.loads(value)
    except (ValueError, TypeError):
        raise ValueError("Azure credentials must be service principal JSON") from None
    keys = ("clientId", "clientSecret", "tenantId", "subscriptionId")
    if not isinstance(credentials, dict) or any(not isinstance(credentials.get(key), str) or not credentials[key].strip() for key in keys):
        raise ValueError("Azure credentials require clientId, clientSecret, tenantId and subscriptionId")
    return {key: credentials[key] for key in keys}


def azure_command(args: list[str], timeout=180, authenticate=False):
    credentials = validate_azure_credentials(owner_credentials.current().get("azure_credentials", ""))
    env = owner_credentials.command_env()
    if authenticate:
        run_command(["az", "login", "--service-principal", "--username", credentials["clientId"],
                     "--password", credentials["clientSecret"], "--tenant", credentials["tenantId"],
                     "--output", "none"], env=env, timeout=90, check=True)
    return run_command(["az", *args, "--subscription", credentials["subscriptionId"], "--only-show-errors"],
                       env=env, timeout=timeout, check=True)


def set_azure_environment(app: str, group: str, values: dict):
    # A temporary settings file keeps values out of CLI arguments and event logs.
    with tempfile.TemporaryDirectory(prefix="agentforge-azure-settings-") as folder:
        path = Path(folder) / "settings.json"
        path.write_text(json.dumps(values), encoding="utf-8")
        azure_command(["webapp", "config", "appsettings", "set", "--name", app, "--resource-group", group,
                       "--settings", f"@{path}", "--output", "none"])


def runtime_values(plan: dict, uri: str, url: str, previous: dict | None = None) -> dict:
    import secrets
    from .environment import DEPLOYER_INJECTED
    values = {"MONGODB_URI": uri} if uri else {}
    if uri:
        from urllib.parse import urlsplit
        values['MONGODB_DB'] = urlsplit(uri).path.lstrip('/') or plan.get('project_slug', 'app').replace('-', '_')
    for entry in (plan.get("environment") or {}).get("entries", []):
        name = entry["name"]
        if entry.get("resolution") == "auto_generate":
            values[name] = (previous or {}).get(name) or secrets.token_urlsafe(48)
        elif entry.get("resolution") == "user_required" and name not in values:
            if (previous or {}).get(name):
                values[name] = previous[name]
            elif entry.get("required"):
                raise ValueError(f"Required runtime setting {name} is missing; configure it before deployment")
    values.update({name: url.rstrip("/") for name in DEPLOYER_INJECTED})
    return values
