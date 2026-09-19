from __future__ import annotations

import os
import json
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

from . import owner_credentials
from .config import OLLAMA_MODEL, OLLAMA_URL
from .security import redact_text
from .local_execution import assert_no_local_docker, docker_block_environment


TOOL_COMMANDS = {
    "git": ["git", "--version"],
    "gh": ["gh", "--version"],
    "aws": ["aws", "--version"],
    "node": ["node", "--version"],
    "vercel": ["vercel", "--version"],
    "netlify": ["netlify", "--version"],
    "az": ["az", "--version"],
    "ollama": ["ollama", "--version"],
}


def _windows_tool_directories() -> list[str]:
    """Return common per-machine CLI install directories."""
    if os.name != "nt":
        return []
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    local_app_data = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    return [
        str(program_files / "Git" / "cmd"),
        str(program_files / "GitHub CLI"),
        str(program_files / "Amazon" / "AWSCLIV2"),
        str(program_files / "nodejs"),
        str(local_app_data / "Programs" / "Ollama"),
        str(local_app_data / "Programs" / "nodejs"),
        str(local_app_data / "GitHubDesktop" / "bin"),

        str(Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / "npm"),

        str(program_files / "nodejs" / "bin"),
        str(program_files / "Microsoft SDKs" / "Azure" / "CLI2" / "wbin"),
    ]


def _runtime_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    merged = os.environ.copy()
    if owner_credentials.active():
        for key in ("GH_TOKEN", "GITHUB_TOKEN", "VERCEL_TOKEN", "NETLIFY_AUTH_TOKEN", "AZURE_CONFIG_DIR"):
            merged.pop(key, None)
    if extra:
        merged.update(extra)
    current = merged.get("PATH", "")
    additions = [path for path in _windows_tool_directories() if Path(path).is_dir()]
    if additions:
        merged["PATH"] = os.pathsep.join(additions + ([current] if current else []))
    return merged


def resolve_command(name: str) -> str | None:
    return shutil.which(name, path=_runtime_environment().get("PATH"))


def run_command(
    args: list[str],
    cwd: Path | str | None = None,
    timeout: int = 30,
    env: dict[str, str] | None = None,
    check: bool = False,
    input: str | None = None,
    authenticated: bool = True,
) -> subprocess.CompletedProcess[str]:
    # A command run for a person signs in as them (owner_credentials.py).
    assert_no_local_docker(args, cwd)
    account_env = owner_credentials.command_env()
    if not authenticated:
        account_env = {key: value for key, value in account_env.items() if key in {"GH_CONFIG_DIR", "AZURE_CONFIG_DIR"}}
        account_env.update({key: "" for key in ("GH_TOKEN", "GITHUB_TOKEN", "VERCEL_TOKEN", "NETLIFY_AUTH_TOKEN", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN")})
    merged_env = _runtime_environment({**account_env, **(env or {})})
    blocker = docker_block_environment()
    merged_env['PATH'] = blocker['PATH'] + os.pathsep + merged_env.get('PATH', '')
    merged_env['DOCKER_HOST'] = blocker['DOCKER_HOST']
    merged_env['DOCKER_CONTEXT'] = blocker['DOCKER_CONTEXT']
    resolved_args = list(args)
    resolved_args[0] = resolve_command(resolved_args[0]) or resolved_args[0]

    if cwd and Path(resolved_args[0]).name.lower() in {"git", "git.exe"}:
        safe_directory = str(Path(cwd).resolve())
        resolved_args[1:1] = ["-c", f"safe.directory={safe_directory}"]
    private = [value for value in owner_credentials.current().values() if isinstance(value, str) and len(value) > 8]
    private.extend(value for key, value in (env or {}).items() if any(word in key.upper() for word in ("SECRET", "TOKEN", "PASSWORD", "URI")) and len(value) > 8)
    try:
        azure = json.loads(owner_credentials.current().get("azure_credentials", "{}"))
        private.append(azure.get("clientSecret", ""))
    except (ValueError, TypeError):
        pass
    def sanitized(output):
        for secret in private:
            if secret:
                output = output.replace(secret, "***REDACTED***")
        return redact_text(output)
    try:
        result = subprocess.run(resolved_args, cwd=str(cwd) if cwd else None, env=merged_env,
                                input=input, capture_output=True, text=True, timeout=timeout, shell=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(sanitized(str(exc))) from None
    for attribute in ("stdout", "stderr"):
        output = getattr(result, attribute) or ""
        setattr(result, attribute, sanitized(output))
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"Command failed: {args[0]}")
    return result


def command_exists(name: str) -> bool:
    return resolve_command(name) is not None


def tool_status() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, command in TOOL_COMMANDS.items():
        path = resolve_command(command[0])
        item: dict[str, Any] = {"installed": bool(path), "path": path or "", "version": ""}
        if path:
            try:
                proc = run_command(command, timeout=8)
                item["version"] = (proc.stdout or proc.stderr).strip().splitlines()[0][:160]
                if name == "node":
                    item["ready"] = proc.returncode == 0
            except Exception as exc:
                item["error"] = str(exc)
        result[name] = item

    try:
        from deploy_agent.bridge import ollama_probe
        result["ollama"].update(ollama_probe())
    except Exception:                                           # noqa: BLE001
        try:
            import requests

            response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
            response.raise_for_status()
            names = [model.get("name", "") for model in response.json().get("models", [])]
            result["ollama"]["ready"] = True
            result["ollama"]["model_ready"] = OLLAMA_MODEL in names
        except Exception as exc:
            result["ollama"]["ready"] = False
            result["ollama"]["model_ready"] = False
            result["ollama"]["error"] = str(exc)

    result["ports"] = {"7834_available": _port_available(7834)}
    return result


def _port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def login_command(tool: str, profile: str = "", region: str = "") -> list[str]:
    if tool == "aws-configure":
        args = ["aws", "configure", "sso"]
        if profile:
            args.extend(["--profile", profile])
    elif tool == "aws-console-login":
        args = [
            "aws",
            "login",
            "--profile",
            profile or "agentforge-console",
            "--region",
            region or "ap-south-1",
            "--no-cli-pager",
        ]
    elif tool == "aws-login":
        args = ["aws", "sso", "login"]
        if profile:
            args.extend(["--profile", profile])
    elif tool == "vercel":
        args = ["vercel", "login"]
    elif tool == "github":
        args = [
            "gh",
            "auth",
            "login",
            "--hostname",
            "github.com",
            "--web",
            "--clipboard",
            "--git-protocol",
            "https",
        ]
    elif tool == "ollama":
        args = ["ollama", "signin"]
    else:
        raise ValueError("Unsupported login tool")
    return args


def start_login(tool: str, profile: str = "", region: str = "") -> subprocess.Popen[str]:
    args = login_command(tool, profile, region)
    args[0] = resolve_command(args[0]) or args[0]
    return subprocess.Popen(
        args,
        env=_runtime_environment(),
        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
    )
