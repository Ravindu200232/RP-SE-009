from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from .models import GitHubPushResult


class GitHubPushClient:
    def push(self, package_dir: Path, repo_url: str, branch: str, commit_message: str) -> GitHubPushResult:
        remote_check = self._run_git(["git", "ls-remote", "--heads", repo_url, branch], cwd=package_dir)
        if remote_check.returncode != 0:
            stderr = (remote_check.stderr or "").lower()
            if any(token in stderr for token in ("permission denied", "authentication failed", "could not read username", "repository not found")):
                return GitHubPushResult(state="AUTH_REQUIRED", message=remote_check.stderr.strip(), branch=branch)
            return GitHubPushResult(state="ERROR", message=remote_check.stderr.strip() or remote_check.stdout.strip(), branch=branch)

        workspace = package_dir.parent / "_git_push_workspace"
        if workspace.exists():
            shutil.rmtree(workspace)

        clone = self._run_git(["git", "clone", "--depth", "1", repo_url, str(workspace)], cwd=package_dir.parent)
        if clone.returncode != 0:
            return GitHubPushResult(state="ERROR", message=clone.stderr.strip() or clone.stdout.strip(), branch=branch)

        checkout = self._run_git(["git", "checkout", "-B", branch], cwd=workspace)
        if checkout.returncode != 0:
            return GitHubPushResult(state="ERROR", message=checkout.stderr.strip() or checkout.stdout.strip(), branch=branch)

        self._sync_package(package_dir, workspace)
        self._run_git(["git", "add", "."], cwd=workspace)
        diff = self._run_git(["git", "diff", "--cached", "--quiet"], cwd=workspace)
        if diff.returncode == 0:
            return GitHubPushResult(state="PUSHED", message="No changes to push.", branch=branch)

        self._run_git(["git", "config", "user.name", "Agent 4"], cwd=workspace)
        self._run_git(["git", "config", "user.email", "agent4@example.local"], cwd=workspace)
        commit = self._run_git(["git", "commit", "-m", commit_message], cwd=workspace)
        if commit.returncode != 0:
            return GitHubPushResult(state="ERROR", message=commit.stderr.strip() or commit.stdout.strip(), branch=branch)

        push = self._run_git(["git", "push", "origin", f"HEAD:{branch}"], cwd=workspace)
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

