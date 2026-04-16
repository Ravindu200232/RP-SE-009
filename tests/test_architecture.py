from __future__ import annotations

from pathlib import Path
import json
import shutil
import uuid

from agent4.architecture import ArchitectureDetector


def make_workspace() -> Path:
    base = Path(__file__).resolve().parents[1] / ".pytest_tmp" / f"case-{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_detects_microservices_from_repo_shape() -> None:
    workspace = make_workspace()
    try:
        source = workspace / "source"
        write(
            source / "server" / "user-service" / "package.json",
            json.dumps({"name": "user-service", "main": "Server.js", "scripts": {"test": "jest"}}),
        )
        write(source / "server" / "user-service" / "Server.js", "const PORT = process.env.PORT || 3000; app.get('/health', () => {});")
        write(
            source / "server" / "order-service" / "package.json",
            json.dumps({"name": "order-service", "main": "Server.js"}),
        )
        write(source / "server" / "order-service" / "Server.js", "const PORT = process.env.PORT || 3001; process.env.USER_SERVICE_URL;")
        write(
            source / "client" / "package.json",
            json.dumps({"name": "frontend", "scripts": {"dev": "vite --host 0.0.0.0"}}),
        )
        srs_path = workspace / "srs.json"
        srs_path.write_text(json.dumps({"projectName": "Food App", "architectureType": "microservices"}), encoding="utf-8")

        analysis = ArchitectureDetector().analyze(str(source), str(srs_path))

        assert analysis.final_architecture == "microservices"
        assert analysis.confidence >= 0.88
        assert len(analysis.services) == 3
        assert analysis.conflict is False
    finally:
        shutil.rmtree(workspace)


def test_flags_architecture_conflict() -> None:
    workspace = make_workspace()
    try:
        source = workspace / "source"
        write(source / "package.json", json.dumps({"name": "single-app", "scripts": {"dev": "next dev"}}))
        write(source / "server.js", "const PORT = process.env.PORT || 3000;")
        srs_path = workspace / "srs.json"
        srs_path.write_text(json.dumps({"projectName": "Blog", "architectureType": "microservices"}), encoding="utf-8")

        analysis = ArchitectureDetector().analyze(str(source), str(srs_path))

        assert analysis.conflict is True
        assert analysis.final_architecture == "microservices"
        assert analysis.scanned_architecture == "monolith"
    finally:
        shutil.rmtree(workspace)

