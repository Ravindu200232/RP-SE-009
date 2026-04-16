from __future__ import annotations

from pathlib import Path
import json
import shutil
import uuid
import zipfile

from agent4.models import PackageRequest, JobState
from agent4.service import Agent4Service


def make_workspace() -> Path:
    base = Path(__file__).resolve().parents[1] / ".pytest_tmp" / f"service-{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_packages_microservice_repo() -> None:
    workspace = make_workspace()
    try:
        source = workspace / "source"
        write(source / "server" / "user-service" / "package.json", json.dumps({"name": "user-service", "main": "Server.js", "scripts": {"test": "jest"}}))
        write(source / "server" / "user-service" / "Server.js", "const PORT = process.env.PORT || 3000; app.get('/health', () => {}); process.env.SEKRET_KEY; process.env.MONGO_URL;")
        write(source / "server" / "order-service" / "package.json", json.dumps({"name": "order-service", "main": "Server.js"}))
        write(source / "server" / "order-service" / "Server.js", "const PORT = process.env.PORT || 3001; app.get('/health', () => {}); process.env.USER_SERVICE_URL; process.env.MONGO_URL;")
        write(source / "client" / "package.json", json.dumps({"name": "frontend", "scripts": {"dev": "vite --host 0.0.0.0"}}))
        write(source / "client" / "src" / "main.js", "console.log('hello');")

        srs_path = workspace / "srs.json"
        srs_path.write_text(json.dumps({"projectName": "Food App", "architectureType": "microservices", "selectedStack": "React + Node.js + MongoDB"}), encoding="utf-8")
        review_path = workspace / "review.json"
        review_path.write_text(json.dumps({"overallScore": 92, "action_required": "APPROVE"}), encoding="utf-8")

        service = Agent4Service()
        result = service.process(
            PackageRequest(
                job_id="job-packaged",
                source_path=str(source),
                review_report_path=str(review_path),
                srs_path=str(srs_path),
                docker_enabled=False,
                github_push_enabled=False,
            )
        )

        assert result.state == JobState.PACKAGED
        assert Path(result.package_dir, "docker-compose.yml").exists()
        assert Path(result.package_dir, ".github", "workflows", "user_service.yml").exists()
        assert not Path(result.package_dir, "aws").exists()
        env_text = Path(result.package_dir, ".env.example").read_text(encoding="utf-8")
        assert "AWS_REGION" not in env_text
        zip_path = service.download_path("job-packaged")
        assert zip_path is not None
        with zipfile.ZipFile(zip_path) as archive:
            assert any(name.endswith("docker-compose.yml") for name in archive.namelist())
            assert not any("/aws/" in name or name.endswith("/aws") for name in archive.namelist())
    finally:
        shutil.rmtree(workspace)
