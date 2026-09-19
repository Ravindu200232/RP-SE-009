"""Signing in to Vercel, Netlify and Azure through their own command line tools.

GitHub has a device flow, so it is asked directly (`github_device.py`). These
three do not: Vercel and Netlify offer OAuth only to a registered application
with a redirect URL, and Azure's device flow hands back a user session rather
than the service principal a deployment needs. What all three do have is a
`login` command that opens a browser, completes the sign-in there, and writes a
credential to a known file.

So that is what this drives: run the command, show whatever it prints - Azure
prints a code to type, the other two open a tab - and when it finishes, read
the credential out of the tool's own store and keep it with the person's
account. Nobody pastes a token, and nothing here ever sees a password.

A tool that is not installed is not an error worth hiding. The provider says
which command installs it, and the studio shows that instead of failing.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

# How long a sign-in may stay open. The browser half is a person reading a
# page, so this is generous; the flow is dropped either way once it passes.
TTL_SECONDS = 600

HOME = Path.home()


def _first_file(*candidates: Path) -> Path | None:
    for path in candidates:
        if path and path.is_file():
            return path
    return None


def _where(name: str) -> str:
    """The tool's path, looking past whatever PATH this process inherited.

    `shutil.which` is right when the server was started from a shell the person
    also uses. It is wrong often enough not to rely on: a service, a launcher,
    or a desktop shell can start the server with a PATH that never had npm's
    global directory in it, and the studio would then say Vercel is not
    installed on a machine where `vercel` runs fine in a terminal.
    """
    found = shutil.which(name)
    if found:
        return found
    roots = []
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        roots.append(Path(appdata) / "npm")               # npm on Windows
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        roots.append(Path(local) / "Programs" / "nodejs")
    roots += [HOME / ".npm-global" / "bin", HOME / ".local" / "bin",
              Path("/usr/local/bin"), Path("/opt/homebrew/bin"),
              Path("/opt/az/bin"), Path("C:/Program Files/Microsoft SDKs/Azure/CLI2/wbin")]
    # Select Windows-compatible binary executable with file extension.
    suffixes = (os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") + [""]
                if os.name == "nt" else [""])
    for root in roots:
        for suffix in suffixes:
            candidate = root / f"{name}{suffix.lower()}"
            if candidate.is_file():
                return str(candidate)
    return ""


def _vercel_token() -> str:
    """The token `vercel login` wrote, wherever this platform keeps it."""
    appdata = os.environ.get("APPDATA", "")
    found = _first_file(
        Path(appdata) / "com.vercel.cli" / "auth.json" if appdata else None,
        HOME / ".local" / "share" / "com.vercel.cli" / "auth.json",
        HOME / "Library" / "Application Support" / "com.vercel.cli" / "auth.json",
        HOME / ".vercel" / "auth.json",
    )
    if not found:
        return ""
    try:
        return str(json.loads(found.read_text(encoding="utf-8")).get("token") or "")
    except (OSError, ValueError):
        return ""


def _netlify_token() -> str:
    """The token `netlify login` wrote, from whichever user it signed in as."""
    appdata = os.environ.get("APPDATA", "")
    found = _first_file(
        Path(appdata) / "netlify" / "Config" / "config.json" if appdata else None,
        HOME / ".config" / "netlify" / "config.json",
        HOME / "Library" / "Preferences" / "netlify" / "config.json",
        HOME / ".netlify" / "config.json",
    )
    if not found:
        return ""
    try:
        saved = json.loads(found.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    users = saved.get("users")
    if isinstance(users, dict):
        # The most recently used account, which is the one just signed in.
        for record in reversed(list(users.values())):
            token = (((record or {}).get("auth") or {}).get("token")) if isinstance(record, dict) else ""
            if token:
                return str(token)
    return str(saved.get("accessToken") or "")


def _azure_credentials() -> str:
    """A service principal for the signed-in subscription, as the field wants.

    `az login` produces a user session, and a deployment cannot run as a person
    - GitHub Actions needs a credential of its own. So the sign-in is followed
    by minting one, which is the same thing the Azure documentation tells you
    to do by hand.
    """
    made = _run([_where("az") or "az", "ad", "sp", "create-for-rbac", "--sdk-auth",
                 "--role", "contributor", "--name", "agentforge-deploy"], timeout=180)
    text = (made.stdout or "").strip()
    start = text.find("{")
    if start < 0:
        return ""
    try:
        json.loads(text[start:])
    except ValueError:
        return ""
    return text[start:]


@dataclass
class Provider:
    key: str
    title: str
    command: list
    setting: str
    install: str
    read: object
    # Azure prints a code to type; the others open a browser themselves.
    shows_code: bool = False


PROVIDERS = {
    "vercel": Provider(
        key="vercel", title="Vercel", command=["vercel", "login"],
        setting="vercel_token", install="npm i -g vercel", read=_vercel_token),
    "netlify": Provider(
        key="netlify", title="Netlify", command=["netlify", "login"],
        setting="netlify_token", install="npm i -g netlify-cli", read=_netlify_token),
    "azure": Provider(
        key="azure", title="Azure", command=["az", "login", "--use-device-code"],
        setting="azure_credentials", shows_code=True,
        install="winget install Microsoft.AzureCLI  (or: brew install azure-cli)",
        read=_azure_credentials),
}

# "To sign in, use a web browser to open the page https://microsoft.com/devicelogin
#  and enter the code ABCD1234 to authenticate."
_CODE = re.compile(r"enter the code\s+([A-Z0-9-]{6,})", re.I)
_URL = re.compile(r"https://\S+")


def _run(command: list, timeout: int = 60):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                          shell=os.name == "nt")


@dataclass
class Signin:
    flow_id: str
    provider: str
    process: object
    output: list = field(default_factory=list)
    user_code: str = ""
    verification_uri: str = ""
    started: float = field(default_factory=time.time)
    error: str = ""


class CliSignins:
    """Runs one `login` per person who asks, and reads the result back."""

    def __init__(self) -> None:
        self._flows: dict[str, Signin] = {}
        self._lock = threading.RLock()

    def available(self) -> dict:
        """Which of these can be signed into on this machine right now."""
        return {key: {"title": p.title, "installed": bool(_where(p.command[0])),
                      "install": p.install}
                for key, p in PROVIDERS.items()}

    def start(self, provider_key: str) -> dict:
        provider = PROVIDERS.get(str(provider_key or "").strip())
        if not provider:
            raise ValueError(f"There is no browser sign-in for {provider_key!r}.")
        tool = _where(provider.command[0])
        if not tool:
            raise ValueError(
                f"The {provider.title} command line tool is not installed on this "
                f"machine. Install it with `{provider.install}` and try again, or "
                f"paste a token instead.")
        try:
            process = subprocess.Popen(
                [tool, *provider.command[1:]],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, text=True, bufsize=1,
                shell=os.name == "nt")
        except OSError as exc:
            raise ValueError(f"{provider.title} could not be started: {exc}") from exc

        flow = Signin(flow_id="cli_" + secrets.token_urlsafe(14),
                      provider=provider.key, process=process)
        # Read on a thread: the tool prints as it goes and a blocking read here
        # would hold the request until the person finished in the browser.
        threading.Thread(target=self._drain, args=(flow,), daemon=True).start()
        with self._lock:
            self._prune()
            self._flows[flow.flow_id] = flow
        return {"flow_id": flow.flow_id, "provider": provider.key,
                "title": provider.title, "shows_code": provider.shows_code}

    def _drain(self, flow: Signin) -> None:
        try:
            for line in flow.process.stdout:
                line = line.strip()
                if not line:
                    continue
                flow.output.append(line)
                if not flow.user_code:
                    found = _CODE.search(line)
                    if found:
                        flow.user_code = found.group(1)
                        url = _URL.search(line)
                        flow.verification_uri = url.group(0).rstrip(".,") if url else ""
        except Exception as exc:  # noqa: BLE001 - the poll reports it
            flow.error = str(exc)[:300]

    def poll(self, flow_id: str) -> dict:
        with self._lock:
            self._prune()
            flow = self._flows.get(str(flow_id or ""))
        if not flow:
            raise ValueError("That sign-in is no longer running. Start it again.")
        provider = PROVIDERS[flow.provider]
        running = flow.process.poll() is None

        if running:
            return {"status": "pending", "user_code": flow.user_code,
                    "verification_uri": flow.verification_uri,
                    "shows_code": provider.shows_code}

        with self._lock:
            self._flows.pop(flow.flow_id, None)
        if flow.process.returncode not in (0, None):
            raise ValueError(self._why(provider, flow))
        value = provider.read()
        if not value:
            raise ValueError(
                f"{provider.title} reported a successful sign-in but left no "
                f"credential this could read. Paste a token instead.")
        return {"status": "ready", "setting": provider.setting, "value": value}

    def cancel(self, flow_id: str) -> dict:
        with self._lock:
            flow = self._flows.pop(str(flow_id or ""), None)
        if flow and flow.process.poll() is None:
            try:
                flow.process.terminate()
            except OSError:
                pass
        return {"status": "cancelled"}

    def _why(self, provider: Provider, flow: Signin) -> str:
        """The tool's last words, which are more use than its exit code."""
        said = " ".join(flow.output[-3:])[:400].strip()
        return said or f"{provider.title} sign-in did not complete."

    def _prune(self) -> None:
        now = time.time()
        for key in [k for k, f in self._flows.items() if now - f.started > TTL_SECONDS]:
            dead = self._flows.pop(key, None)
            if dead and dead.process.poll() is None:
                try:
                    dead.process.terminate()
                except OSError:
                    pass


SIGNINS = CliSignins()
