from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
import time

from .models import GitHubPushResult


class GitHubPushClient:
    def push(self, package_dir: Path, repo_url: str, branch: str, commit_message: str) -> GitHubPushResult:
        repo_error = self._validate_repo_url(repo_url)
        if repo_error:
            return GitHubPushResult(state="ERROR", message=repo_error, branch=branch)

        remote_check = self._run_git_with_retry(["git", "ls-remote", "--heads", repo_url, branch], cwd=package_dir)
        if remote_check.returncode != 0:
            stderr = (remote_check.stderr or "").lower()
            if any(token in stderr for token in ("permission denied", "authentication failed", "could not read username", "repository not found")):
                return GitHubPushResult(state="AUTH_REQUIRED", message=remote_check.stderr.strip(), branch=branch)
            return GitHubPushResult(state="ERROR", message=remote_check.stderr.strip() or remote_check.stdout.strip(), branch=branch)

        workspace = package_dir.parent / "_git_push_workspace"
        if workspace.exists():
            shutil.rmtree(workspace)

        clone = self._run_git_with_retry(["git", "clone", "--depth", "1", repo_url, str(workspace)], cwd=package_dir.parent)
        if clone.returncode != 0:
            return GitHubPushResult(state="ERROR", message=clone.stderr.strip() or clone.stdout.strip(), branch=branch)

        checkout = self._run_git(["git", "checkout", "-B", branch], cwd=workspace)
        if checkout.returncode != 0:
            return GitHubPushResult(state="ERROR", message=checkout.stderr.strip() or checkout.stdout.strip(), branch=branch)

        self._sync_package(package_dir, workspace)
        self._sanitize_workspace_for_push(workspace)
        findings = self._find_blocked_secrets(workspace)
        if findings:
            preview = "\n".join(findings[:6])
            suffix = "\n..." if len(findings) > 6 else ""
            return GitHubPushResult(
                state="ERROR",
                message=(
                    "Push blocked: sensitive token patterns are still present after sanitization. "
                    "Rotate/revoke the leaked keys and remove them from source before pushing.\n"
                    f"{preview}{suffix}"
                ),
                branch=branch,
            )
        self._run_git(["git", "add", "."], cwd=workspace)
        diff = self._run_git(["git", "diff", "--cached", "--quiet"], cwd=workspace)
        if diff.returncode == 0:
            return GitHubPushResult(state="PUSHED", message="No changes to push.", branch=branch)

        self._run_git(["git", "config", "user.name", "Agent 4"], cwd=workspace)
        self._run_git(["git", "config", "user.email", "agent4@example.local"], cwd=workspace)
        commit = self._run_git(["git", "commit", "-m", commit_message], cwd=workspace)
        if commit.returncode != 0:
            return GitHubPushResult(state="ERROR", message=commit.stderr.strip() or commit.stdout.strip(), branch=branch)

        push = self._run_git_with_retry(
            [
                "git",
                "-c",
                "http.version=HTTP/1.1",
                "-c",
                "http.postBuffer=524288000",
                "-c",
                "http.lowSpeedLimit=1000",
                "-c",
                "http.lowSpeedTime=60",
                "push",
                "origin",
                f"HEAD:{branch}",
            ],
            cwd=workspace,
            attempts=3,
        )
        if push.returncode != 0:
            stderr = (push.stderr or "").lower()
            if any(token in stderr for token in ("permission denied", "authentication failed", "could not read username")):
                return GitHubPushResult(state="AUTH_REQUIRED", message=push.stderr.strip(), branch=branch)
            return GitHubPushResult(state="ERROR", message=push.stderr.strip() or push.stdout.strip(), branch=branch)

        sha = self._run_git(["git", "rev-parse", "HEAD"], cwd=workspace)
        return GitHubPushResult(state="PUSHED", message="Packaged output pushed successfully.", branch=branch, commit_sha=sha.stdout.strip())

    def _sync_package(self, package_dir: Path, workspace: Path) -> None:
        for child in workspace.iterdir():
            if child.name == ".git":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

        for child in package_dir.iterdir():
            if child.name.endswith(".zip"):
                continue
            destination = workspace / child.name
            if child.is_dir():
                shutil.copytree(child, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(child, destination)

    def _run_git(self, command: list[str], cwd: Path):
        return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)

    def _sanitize_workspace_for_push(self, workspace: Path) -> None:
        # Remove high-risk files that commonly contain secrets.
        blocked_names = {
            "superbase.txt",
            ".env",
            ".env.local",
            ".env.development",
            ".env.production",
            "id_rsa",
            "id_dsa",
        }
        blocked_suffixes = {".pem", ".key", ".p12", ".pfx"}

        for path in workspace.rglob("*"):
            if not path.is_file():
                continue

            lower_name = path.name.lower()
            if lower_name in blocked_names or path.suffix.lower() in blocked_suffixes:
                path.unlink(missing_ok=True)
                continue

            # Redact common credential patterns in text files.
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            redacted, changed = self._redact_sensitive_content(content)
            if changed:
                path.write_text(redacted, encoding="utf-8")

    def _redact_sensitive_content(self, content: str) -> tuple[str, bool]:
        redacted = content

        patterns = [
            # Google API key format (e.g. AIza...).
            (re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"), "<REDACTED_GOOGLE_API_KEY>"),
            # Google Maps script URL query key.
            (re.compile(r"(?i)([?&]key=)AIza[0-9A-Za-z\-_]{20,}"), r"\1<REDACTED_GOOGLE_API_KEY>"),
            # Google OAuth client ID.
            (re.compile(r"\b[0-9]{8,}-[a-z0-9\-]+\.apps\.googleusercontent\.com\b", re.IGNORECASE), "<REDACTED_GOOGLE_OAUTH_CLIENT_ID>"),
            # Google OAuth client secret token format.
            (re.compile(r"\bGOCSPX-[A-Za-z0-9_-]+\b"), "<REDACTED_GOOGLE_OAUTH_CLIENT_SECRET>"),
            # Generic key/value style secrets.
            (re.compile(r"(?im)^(\s*(?:google_)?client[_-]?secret\s*[=:]\s*)(.+)$"), r"\1<REDACTED_SECRET>"),
            (re.compile(r"(?im)^(\s*(?:api[_-]?key|token|access[_-]?token|refresh[_-]?token|password)\s*[=:]\s*)(.+)$"), r"\1<REDACTED_SECRET>"),
        ]

        for pattern, replacement in patterns:
            redacted = pattern.sub(replacement, redacted)

        return redacted, redacted != content

    def _run_git_with_retry(self, command: list[str], cwd: Path, attempts: int = 2):
        last_result = None
        for attempt in range(1, attempts + 1):
            result = self._run_git(command, cwd)
            last_result = result
            if result.returncode == 0:
                return result

            stderr = (result.stderr or "").lower()
            stdout = (result.stdout or "").lower()
            output = f"{stderr}\n{stdout}"
            if not self._is_transient_network_error(output):
                return result

            if attempt < attempts:
                time.sleep(attempt)

        return last_result

    def _is_transient_network_error(self, output: str) -> bool:
        tokens = (
            "http 408",
            "requested url returned error: 408",
            "rpc failed",
            "remote end hung up unexpectedly",
            "unexpected disconnect",
            "operation timed out",
            "connection timed out",
            "the requested url returned error: 5",
            "http 5",
            "ssl_read",
            "http2 stream",
        )
        return any(token in output for token in tokens)

    def _find_blocked_secrets(self, workspace: Path) -> list[str]:
        patterns: list[tuple[str, re.Pattern[str]]] = [
            ("Google API key", re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b")),
            ("Google OAuth client secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_-]+\b")),
            (
                "Google OAuth client id",
                re.compile(r"\b[0-9]{8,}-[a-z0-9\-]+\.apps\.googleusercontent\.com\b", re.IGNORECASE),
            ),
        ]

        findings: list[str] = []
        for path in workspace.rglob("*"):
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            for label, pattern in patterns:
                for match in pattern.finditer(content):
                    line_no = content.count("\n", 0, match.start()) + 1
                    findings.append(f"{label}: {path.relative_to(workspace)}:{line_no}")
                    if len(findings) >= 25:
                        return findings
        return findings

    def _validate_repo_url(self, repo_url: str) -> str:
        value = (repo_url or "").strip()
        if not value:
            return "GitHub push is enabled, but repository URL is empty. Provide a valid GitHub repository URL."

        # Accept common remote formats.
        if value.startswith("git@") or value.startswith("https://") or value.startswith("ssh://"):
            return ""

        # If a local path is supplied, make the failure message explicit.
        if value.startswith("/") or value.startswith("./") or value.startswith("../") or value.startswith("~"):
            local_path = Path(value).expanduser().resolve()
            if (local_path / ".git").exists():
                return (
                    "GitHub repository URL appears to be a local repository path. "
                    "Use a remote URL like git@github.com:owner/repo.git or https://github.com/owner/repo.git."
                )
            return (
                f"'{local_path}' is a local folder, not a GitHub remote URL. "
                "Use a remote URL like git@github.com:owner/repo.git or https://github.com/owner/repo.git."
            )

        return (
            "Unsupported repository URL format. "
            "Use git@github.com:owner/repo.git or https://github.com/owner/repo.git."
        )

