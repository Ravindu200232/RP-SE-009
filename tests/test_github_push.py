from __future__ import annotations

from pathlib import Path
import json
import shutil
import subprocess
import uuid

from agent4.github_push import GitHubPushClient
from agent4.models import GitHubPushResult, JobState, PackageRequest
from agent4.service import Agent4Service


def make_workspace() -> Path:
    base = Path(__file__).resolve().parents[1] / ".pytest_tmp" / f"github-{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_pushes_packaged_output_to_existing_repo() -> None:
    workspace = make_workspace()
    try:
        remote = workspace / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)

        package_dir = workspace / "package"
        package_dir.mkdir(parents=True, exist_ok=True)
        write(package_dir / "README.md", "# packaged output\n")

        result = GitHubPushClient().push(package_dir, str(remote), "main", "Add package")

        assert result.state == JobState.PUSHED
        assert result.branch == "main"
    finally:
        shutil.rmtree(workspace)


def test_auth_required_state_bubbles_up() -> None:
    workspace = make_workspace()
    try:
        source = workspace / "source"
        write(source / "server" / "user-service" / "package.json", json.dumps({"name": "user-service", "main": "Server.js"}))
        write(source / "server" / "user-service" / "Server.js", "const PORT = process.env.PORT || 3000; app.get('/health', () => {});")
        write(source / "server" / "order-service" / "package.json", json.dumps({"name": "order-service", "main": "Server.js"}))
        write(source / "server" / "order-service" / "Server.js", "const PORT = process.env.PORT || 3001; app.get('/health', () => {}); process.env.USER_SERVICE_URL;")
        srs_path = workspace / "srs.json"
        srs_path.write_text(json.dumps({"projectName": "Push App", "architectureType": "microservices"}), encoding="utf-8")
        review_path = workspace / "review.json"
        review_path.write_text(json.dumps({"overallScore": 90}), encoding="utf-8")

        service = Agent4Service()
        service.github_push_client.push = lambda **_: GitHubPushResult(state="AUTH_REQUIRED", message="Login required.", branch="main")

        result = service.process(
            PackageRequest(
                job_id="job-auth-required",
                source_path=str(source),
                review_report_path=str(review_path),
                srs_path=str(srs_path),
                docker_enabled=False,
                github_push_enabled=True,
                github_repo_url="git@github.com:owner/repo.git",
            )
        )

        assert result.state == JobState.AUTH_REQUIRED
        assert result.push_result.message == "Login required."
    finally:
        shutil.rmtree(workspace)
