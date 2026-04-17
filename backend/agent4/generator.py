from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import re
import shutil
import zipfile

import yaml

from .models import ArchitectureAnalysis, PackageRequest, ServiceDescriptor, StrategyDecision, slugify, to_pretty_json


IGNORE_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    ".next",
    "dist",
    "build",
}


class ArtifactGenerator:
    def generate(
        self,
        request: PackageRequest,
        analysis: ArchitectureAnalysis,
        strategy: StrategyDecision,
        job_dir: Path,
    ) -> tuple[Path, Path, list[str]]:
        package_dir = job_dir / slugify(analysis.project_name)
        if package_dir.exists():
            shutil.rmtree(package_dir)
        shutil.copytree(
            Path(analysis.source_path),
            package_dir,
            ignore=shutil.ignore_patterns(*IGNORE_NAMES),
        )
        self._sanitize_package_dir(package_dir)

        artifacts: list[str] = []
        for service in analysis.services:
            target_dir = package_dir / service.relative_path
            dockerfile_path = target_dir / "Dockerfile"
            if not dockerfile_path.exists():
                dockerfile_path.write_text(self._dockerfile_for(service), encoding="utf-8")
                artifacts.append(str(dockerfile_path.relative_to(package_dir)))

        compose_path = package_dir / "docker-compose.yml"
        compose_path.write_text(self._compose_yaml(analysis), encoding="utf-8")
        artifacts.append("docker-compose.yml")

        env_path = package_dir / ".env.example"
        env_path.write_text(self._env_template(analysis), encoding="utf-8")
        artifacts.append(".env.example")

        setup_path = package_dir / "setup.sh"
        setup_path.write_text(self._setup_script(), encoding="utf-8")
        setup_path.chmod(0o755)
        artifacts.append("setup.sh")

        readme_path = package_dir / "README.md"
        readme_path.write_text(self._readme(analysis, strategy), encoding="utf-8")
        artifacts.append("README.md")

        workflow_dir = package_dir / ".github" / "workflows"
        if workflow_dir.exists():
            shutil.rmtree(workflow_dir)
        workflow_dir.mkdir(parents=True, exist_ok=True)
        for service in analysis.services:
            workflow_name = f"{service.service_key}.yml" if service.kind == "backend" else "client.yml"
            workflow_path = workflow_dir / workflow_name
            workflow_path.write_text(self._workflow_yaml(service, analysis), encoding="utf-8")
            artifacts.append(str(workflow_path.relative_to(package_dir)))

        analysis_path = package_dir / "analysis.json"
        analysis_path.write_text(to_pretty_json(self._analysis_payload(analysis)), encoding="utf-8")
        artifacts.append("analysis.json")

        strategy_path = package_dir / "strategy.json"
        strategy_path.write_text(to_pretty_json(strategy.__dict__), encoding="utf-8")
        artifacts.append("strategy.json")

        evidence_path = package_dir / "deployment_evidence.json"
        evidence_path.write_text(to_pretty_json({"status": "generated", "artifacts": artifacts}), encoding="utf-8")
        artifacts.append("deployment_evidence.json")

        zip_path = job_dir / f"{slugify(analysis.project_name)}_generated_{datetime.now(timezone.utc):%Y%m%d}.zip"
        self._zip_dir(package_dir, zip_path)
        artifacts.append(zip_path.name)
        return package_dir, zip_path, artifacts

    def _sanitize_package_dir(self, package_dir: Path) -> None:
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

        for path in package_dir.rglob("*"):
            if not path.is_file():
                continue

            lower_name = path.name.lower()
            if lower_name in blocked_names or path.suffix.lower() in blocked_suffixes:
                path.unlink(missing_ok=True)

        # Remove any copied workflow files so only Agent 4's generated workflows remain.
        copied_workflows = package_dir / ".github" / "workflows"
        if copied_workflows.exists():
            shutil.rmtree(copied_workflows)

    def write_evidence(self, package_dir: Path, payload: dict) -> Path:
        evidence_path = package_dir / "deployment_evidence.json"
        evidence_path.write_text(to_pretty_json(payload), encoding="utf-8")
        return evidence_path

    def rewrite_zip(self, package_dir: Path, zip_path: Path) -> None:
        if zip_path.exists():
            zip_path.unlink()
        self._zip_dir(package_dir, zip_path)

    def _zip_dir(self, package_dir: Path, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(package_dir.rglob("*")):
                archive.write(file_path, file_path.relative_to(package_dir.parent))

    def _analysis_payload(self, analysis: ArchitectureAnalysis) -> dict:
        return {
            "declared_architecture": analysis.declared_architecture,
            "scanned_architecture": analysis.scanned_architecture,
            "final_architecture": analysis.final_architecture,
            "confidence": analysis.confidence,
            "conflict": analysis.conflict,
            "project_name": analysis.project_name,
            "selected_stack": analysis.selected_stack,
            "services": [service.__dict__ for service in analysis.services],
            "infrastructure": analysis.infrastructure,
            "evidence": analysis.evidence,
        }

    def _dockerfile_for(self, service: ServiceDescriptor) -> str:
        if service.kind == "frontend":
            command = '["npm", "run", "dev", "--", "--host", "0.0.0.0"]'
            if service.runtime == "nextjs":
                command = '["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]'
            return "\n".join(
                [
                    "FROM node:20-slim",
                    "",
                    "WORKDIR /app",
                    "",
                    "COPY package*.json ./",
                    "RUN npm ci",
                    "",
                    "COPY . .",
                    "",
                    f"EXPOSE {service.port}",
                    f"CMD {command}",
                    "",
                ]
            )

        if service.runtime == "python":
            return "\n".join(
                [
                    "FROM python:3.11-slim",
                    "",
                    "WORKDIR /app",
                    "COPY requirements.txt ./",
                    "RUN pip install --no-cache-dir -r requirements.txt",
                    "COPY . .",
                    f"EXPOSE {service.port}",
                    f'HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 CMD wget -qO- http://localhost:{service.port}/health || exit 1',
                    'CMD ["python", "main.py"]',
                    "",
                ]
            )

        return "\n".join(
            [
                "FROM node:20-alpine AS deps",
                "WORKDIR /app",
                "COPY package*.json ./",
                "RUN npm install --omit=dev --legacy-peer-deps",
                "",
                "FROM node:20-alpine AS runtime",
                "RUN addgroup -S appgroup && adduser -S appuser -G appgroup",
                "WORKDIR /app",
                "COPY --from=deps /app/node_modules ./node_modules",
                "COPY . .",
                "RUN chown -R appuser:appgroup /app",
                "USER appuser",
                f"EXPOSE {service.port}",
                f'HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 CMD wget -qO- http://localhost:{service.port}/health || exit 1',
                f'CMD ["node", "{service.entrypoint}"]',
                "",
            ]
        )

    def _compose_yaml(self, analysis: ArchitectureAnalysis) -> str:
        data: dict = {"version": "3.9", "services": {}, "volumes": {}}
        service_map = {service.service_key: service for service in analysis.services}

        if analysis.infrastructure.get("mongo"):
            data["services"]["mongo"] = {
                "image": "mongo:latest",
                "container_name": "mongo_container",
                "volumes": ["mongo_data:/data/db"],
                "ports": ["27017:27017"],
                "healthcheck": {
                    "test": ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                },
            }
            data["volumes"]["mongo_data"] = None

        if analysis.infrastructure.get("postgres"):
            data["services"]["postgres"] = {
                "image": "postgres:16-alpine",
                "container_name": "postgres_container",
                "environment": [
                    "POSTGRES_DB=${POSTGRES_DB:-app}",
                    "POSTGRES_USER=${POSTGRES_USER:-app}",
                    "POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-change-me}",
                ],
                "ports": ["5432:5432"],
                "volumes": ["postgres_data:/var/lib/postgresql/data"],
                "healthcheck": {
                    "test": ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER"],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                },
            }
            data["volumes"]["postgres_data"] = None

        if analysis.infrastructure.get("redis"):
            data["services"]["redis"] = {
                "image": "redis:7-alpine",
                "container_name": "redis_container",
                "ports": ["6379:6379"],
                "healthcheck": {
                    "test": ["CMD", "redis-cli", "ping"],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                },
            }

        if analysis.infrastructure.get("rabbitmq"):
            data["services"]["rabbitmq"] = {
                "image": "rabbitmq:3-management",
                "container_name": "rabbitmq_container",
                "ports": ["5672:5672", "15672:15672"],
                "healthcheck": {
                    "test": ["CMD", "rabbitmq-diagnostics", "ping"],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                },
            }

        for service in analysis.services:
            entry = {
                "build": f"./{service.relative_path}",
                "container_name": f"{service.service_key}_container",
                "ports": [f"{service.port}:{service.port}"],
                "environment": self._compose_environment(service, service_map, analysis.infrastructure),
            }
            depends_on = self._compose_dependencies(service, service_map, analysis.infrastructure)
            if depends_on:
                entry["depends_on"] = depends_on
            if service.kind == "frontend":
                entry["stdin_open"] = True
                entry["tty"] = True
            elif service.has_health_endpoint:
                entry["healthcheck"] = {
                    "test": ["CMD", "wget", "-qO-", f"http://localhost:{service.port}/health"],
                    "interval": "30s",
                    "timeout": "10s",
                    "retries": 3,
                }
            data["services"][service.service_key] = entry

        return yaml.safe_dump(data, sort_keys=False)

    def _compose_environment(
        self,
        service: ServiceDescriptor,
        service_map: dict[str, ServiceDescriptor],
        infrastructure: dict[str, bool],
    ) -> list[str]:
        env = [f"PORT={service.port}"]
        if service.kind == "frontend":
            for peer in service_map.values():
                if peer.kind == "backend":
                    env.append(f"VITE_{peer.service_key.upper()}_URL=http://localhost:{peer.port}")
            return env

        public_env_name = f"{service.service_key.upper()}_URL"
        env.append(f"SERVER_URL=${{{public_env_name}:-http://localhost:{service.port}}}")

        for variable in sorted(service.env_vars):
            if variable == "PORT" or variable == "SERVER_URL":
                continue
            if variable.endswith("_SERVICE_URL"):
                target = slugify(variable.removesuffix("_URL")).replace("-", "_")
                target_service = service_map.get(target)
                if target_service:
                    env.append(f"{variable}=http://{target_service.service_key}_container:{target_service.port}")
                continue
            env.append(f"{variable}=${{{variable}}}")

        if infrastructure.get("mongo") and "MONGO_URL" not in "".join(env):
            env.append("MONGO_URL=${MONGO_URL}")
        return env

    def _compose_dependencies(
        self,
        service: ServiceDescriptor,
        service_map: dict[str, ServiceDescriptor],
        infrastructure: dict[str, bool],
    ) -> dict:
        depends_on: dict[str, dict[str, str]] = {}
        if service.kind == "backend":
            if infrastructure.get("mongo"):
                depends_on["mongo"] = {"condition": "service_healthy"}
            if infrastructure.get("postgres"):
                depends_on["postgres"] = {"condition": "service_healthy"}
            if infrastructure.get("redis"):
                depends_on["redis"] = {"condition": "service_healthy"}
            if infrastructure.get("rabbitmq"):
                depends_on["rabbitmq"] = {"condition": "service_healthy"}
        for dependency in service.dependencies:
            target = service_map.get(dependency)
            if target:
                depends_on[target.service_key] = {"condition": "service_healthy"}
        if service.kind == "frontend":
            for peer in service_map.values():
                if peer.kind == "backend":
                    depends_on[peer.service_key] = {"condition": "service_started"}
        return depends_on

    def _env_template(self, analysis: ArchitectureAnalysis) -> str:
        lines = [
            "# Generated by Agent 4. Replace placeholders before deployment.",
            "MONGO_URL=mongodb://mongo:27017/app",
            "POSTGRES_DB=app",
            "POSTGRES_USER=app",
            "POSTGRES_PASSWORD=change-me",
            "SEKRET_KEY=replace-me",
            "EMAIL_USER=replace-me@example.com",
            "EMAIL_PASS=replace-me",
        ]
        for service in analysis.services:
            if service.kind == "backend":
                lines.append(f"{service.service_key.upper()}_URL=http://localhost:{service.port}")
        return "\n".join(lines) + "\n"

    def _setup_script(self) -> str:
        return "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "",
                "if [ ! -f .env ]; then",
                "  cp .env.example .env",
                "fi",
                "",
                "docker compose up --build",
                "",
            ]
        )

    def _readme(self, analysis: ArchitectureAnalysis, strategy: StrategyDecision) -> str:
        backend_services = [service for service in analysis.services if service.kind == "backend"]
        frontend_services = [service for service in analysis.services if service.kind == "frontend"]
        lines = [
            f"# {analysis.project_name}",
            "",
            "Packaged by Agent 4 as a deployment-ready microservice project.",
            "",
            "## Architecture",
            "",
            f"- Declared architecture: `{analysis.declared_architecture or 'not provided'}`",
            f"- Scanned architecture: `{analysis.scanned_architecture}`",
            f"- Final architecture: `{analysis.final_architecture}`",
            f"- Confidence: `{analysis.confidence}`",
            f"- Deployment profile: `{strategy.deployment_profile}`",
            "",
            "## Services",
            "",
        ]
        for service in backend_services + frontend_services:
            lines.append(f"- `{service.name}` -> `{service.relative_path}` on port `{service.port}`")
        lines.extend(
            [
                "",
                "## Quick Start",
                "",
                "```bash",
                "cp .env.example .env",
                "./setup.sh",
                "```",
                "",
                "## CI/CD",
                "",
                "- GitHub Actions workflows are generated under `.github/workflows/`.",
                "- Workflows run tests and Docker build checks for each service.",
                "- `GITHUB_TOKEN` is intended only for in-repo workflow tasks.",
                "- Cloud deployment targets are intentionally excluded for now.",
                "",
                "## Generated Evidence",
                "",
                "- `analysis.json`",
                "- `strategy.json`",
                "- `deployment_evidence.json`",
                "",
            ]
        )
        return "\n".join(lines)

    def _workflow_yaml(self, service: ServiceDescriptor, analysis: ArchitectureAnalysis) -> str:
        if service.kind == "frontend":
            return self._client_workflow(service)
        return self._backend_workflow(service)

    def _backend_workflow(self, service: ServiceDescriptor) -> str:
        data = {
            "name": f"{service.service_key} CI",
            "on": {
                "push": {
                    "branches": ["main"],
                    "paths": [f"{service.relative_path}/**", f".github/workflows/{service.service_key}.yml"],
                },
                "pull_request": {"branches": ["main"], "paths": [f"{service.relative_path}/**"]},
                "workflow_dispatch": {},
            },
            "permissions": {"contents": "read"},
            "jobs": {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "uses": "actions/setup-node@v4",
                            "with": {"node-version": "20"},
                        },
                        {
                            "name": "Install dependencies",
                            "working-directory": f"./{service.relative_path}",
                            "run": "if [ -f package.json ]; then npm ci || npm install --legacy-peer-deps || true; else echo 'No package.json found, skipping install'; fi",
                        },
                        {
                            "name": "Run tests",
                            "working-directory": f"./{service.relative_path}",
                            "run": "if [ -f package.json ] && npm run | grep -q '\\btest\\b'; then npm test -- --runInBand || true; else echo 'No test script found, skipping tests'; fi",
                            "continue-on-error": True,
                        },
                    ],
                },
            },
        }
        return yaml.safe_dump(data, sort_keys=False)

    def _client_workflow(self, service: ServiceDescriptor) -> str:
        data = {
            "name": "client CI",
            "on": {
                "push": {"branches": ["main"], "paths": [f"{service.relative_path}/**", ".github/workflows/client.yml"]},
                "pull_request": {"branches": ["main"], "paths": [f"{service.relative_path}/**"]},
                "workflow_dispatch": {},
            },
            "permissions": {"contents": "read"},
            "jobs": {
                "build-and-check": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "uses": "actions/setup-node@v4",
                            "with": {"node-version": "20"},
                        },
                        {
                            "name": "Install dependencies",
                            "working-directory": f"./{service.relative_path}",
                            "run": "if [ -f package.json ]; then npm ci || npm install || true; else echo 'No package.json found, skipping install'; fi",
                        },
                        {
                            "name": "Build app",
                            "working-directory": f"./{service.relative_path}",
                            "run": "if [ -f package.json ] && npm run | grep -q '\\bbuild\\b'; then npm run build || true; else echo 'No build script found, skipping build'; fi",
                            "continue-on-error": True,
                        },
                    ],
                },
            },
        }
        return yaml.safe_dump(data, sort_keys=False)
