from __future__ import annotations

from pathlib import Path
import json
import shutil
import uuid
from types import SimpleNamespace

import agent4.validators as validators_module
from agent4.models import ArchitectureAnalysis, PackageRequest, ServiceDescriptor
from agent4.service import Agent4Service
from agent4.validators import Validator


def make_workspace() -> Path:
    base = Path(__file__).resolve().parents[1] / ".pytest_tmp" / f"validator-{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_validator_checks_generated_files() -> None:
    workspace = make_workspace()
    try:
        source = workspace / "source"
        write(source / "server" / "user-service" / "package.json", json.dumps({"name": "user-service", "main": "Server.js"}))
        write(source / "server" / "user-service" / "Server.js", "const PORT = process.env.PORT || 3000; app.get('/health', () => {});")
        write(source / "server" / "order-service" / "package.json", json.dumps({"name": "order-service", "main": "Server.js"}))
        write(source / "server" / "order-service" / "Server.js", "const PORT = process.env.PORT || 3001; app.get('/health', () => {}); process.env.USER_SERVICE_URL;")
        srs_path = workspace / "srs.json"
        srs_path.write_text(json.dumps({"projectName": "Validator App", "architectureType": "microservices"}), encoding="utf-8")
        review_path = workspace / "review.json"
        review_path.write_text(json.dumps({"overallScore": 91}), encoding="utf-8")

        service = Agent4Service()
        result = service.process(
            PackageRequest(
                job_id="job-validator",
                source_path=str(source),
                review_report_path=str(review_path),
                srs_path=str(srs_path),
                docker_enabled=False,
            )
        )

        report = Validator().validate(Path(result.package_dir), service.detector.analyze(str(source), str(srs_path)), docker_enabled=False)
        assert report.success is True
        assert any(check.name == "docker-compose.yml exists" and check.success for check in report.checks)
    finally:
        shutil.rmtree(workspace)


def test_docker_build_validation_uses_buildx_compatible_arguments(tmp_path, monkeypatch) -> None:
    package_dir = tmp_path / "package"
    service_dir = package_dir / "server" / "user-service"
    service_dir.mkdir(parents=True, exist_ok=True)
    write(service_dir / "Dockerfile", "FROM node:20-alpine\n")
    write(package_dir / "docker-compose.yml", "services: {}\n")

    analysis = ArchitectureAnalysis(
        declared_architecture="microservices",
        scanned_architecture="microservices",
        final_architecture="microservices",
        confidence=0.95,
        conflict=False,
        project_name="Validator App",
        source_path=str(package_dir),
        selected_stack="Node.js",
        services=[
            ServiceDescriptor(
                name="user-service",
                service_key="user_service",
                relative_path="server/user-service",
                runtime="node",
                kind="backend",
                port=3000,
                has_health_endpoint=True,
                entrypoint="Server.js",
            )
        ],
        infrastructure={},
        evidence=[],
    )

    commands: list[list[str]] = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(validators_module.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None)
    monkeypatch.setattr(validators_module.subprocess, "run", fake_run)

    report = Validator().validate(package_dir, analysis, docker_enabled=True)

    assert report.success is True
    assert any(check.name == "docker compose config" and check.success for check in report.checks)
    assert any(check.name == "user-service docker build" and check.success for check in report.checks)
    assert len(commands) == 2
    assert commands[1][:2] == ["/usr/bin/docker", "build"]
    assert "--pull=never" not in commands[1]
