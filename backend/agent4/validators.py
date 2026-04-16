from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess

import yaml

from .models import ArchitectureAnalysis, ValidationCheck, ValidationReport


class Validator:
    def validate(self, package_dir: Path, analysis: ArchitectureAnalysis, docker_enabled: bool) -> ValidationReport:
        checks: list[ValidationCheck] = []

        compose_path = package_dir / "docker-compose.yml"
        checks.append(self._file_check(compose_path, "docker-compose.yml exists"))
        if compose_path.exists():
            try:
                yaml.safe_load(compose_path.read_text(encoding="utf-8"))
                checks.append(ValidationCheck("docker-compose.yml parses", True, "YAML parsed successfully."))
            except yaml.YAMLError as exc:
                checks.append(ValidationCheck("docker-compose.yml parses", False, str(exc)))

        workflow_dir = package_dir / ".github" / "workflows"
        for workflow_path in sorted(workflow_dir.glob("*.yml")):
            try:
                yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
                checks.append(ValidationCheck(f"{workflow_path.name} parses", True, "Workflow YAML parsed successfully."))
            except yaml.YAMLError as exc:
                checks.append(ValidationCheck(f"{workflow_path.name} parses", False, str(exc)))

        if docker_enabled:
            checks.extend(self._docker_checks(package_dir, analysis))

        success = all(check.success for check in checks)
        return ValidationReport(success=success, checks=checks)

    def _file_check(self, path: Path, name: str) -> ValidationCheck:
        return ValidationCheck(name, path.exists(), f"{path} {'exists' if path.exists() else 'is missing'}.")

    def _docker_checks(self, package_dir: Path, analysis: ArchitectureAnalysis) -> list[ValidationCheck]:
        checks: list[ValidationCheck] = []
        docker = shutil.which("docker")
        if not docker:
            checks.append(ValidationCheck("docker availability", False, "Docker is not installed or not on PATH."))
            return checks

        compose_cmd = [docker, "compose", "config"]
        compose_result = subprocess.run(
            compose_cmd,
            cwd=package_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        checks.append(
            ValidationCheck(
                "docker compose config",
                compose_result.returncode == 0,
                compose_result.stdout.strip() or compose_result.stderr.strip(),
            )
        )

        if os.getenv("AGENT4_SKIP_DOCKER_BUILD") == "1":
            checks.append(ValidationCheck("docker build smoke", True, "Skipped because AGENT4_SKIP_DOCKER_BUILD=1."))
            return checks

        for service in analysis.services:
            dockerfile_path = package_dir / service.relative_path / "Dockerfile"
            if not dockerfile_path.exists():
                checks.append(ValidationCheck(f"{service.name} dockerfile", False, "Dockerfile missing."))
                continue
            # Let the local Docker CLI choose its default pull behavior. Newer
            # buildx-backed installs reject the legacy "--pull=never" form.
            build_result = subprocess.run(
                [
                    docker,
                    "build",
                    "-f",
                    str(dockerfile_path),
                    str((package_dir / service.relative_path)),
                ],
                cwd=package_dir,
                capture_output=True,
                text=True,
                check=False,
            )
            checks.append(
                ValidationCheck(
                    f"{service.name} docker build",
                    build_result.returncode == 0,
                    build_result.stdout.strip() or build_result.stderr.strip(),
                )
            )
        return checks
