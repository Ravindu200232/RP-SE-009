from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import uuid


ARCHITECTURES = {
    "monolith",
    "modular_monolith",
    "layered",
    "microservices",
    "event_driven",
    "serverless",
}


class JobState:
    PACKAGED = "PACKAGED"
    VALIDATED = "VALIDATED"
    PUSHED = "PUSHED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    ERROR = "ERROR"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    return "-".join(part for part in cleaned.split("-") if part) or "agent4-package"


@dataclass
class PackageRequest:
    source_path: str
    review_report_path: str = ""
    srs_path: str = ""
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    docker_enabled: bool = False
    github_push_enabled: bool = False
    github_repo_url: str = ""
    github_branch: str = "main"
    commit_message: str = "Add packaged deployment output"
    architecture_manifest_path: str = ""
    target_profile: str = "docker-actions"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PackageRequest":
        request = cls(
            job_id=str(payload.get("job_id") or uuid.uuid4().hex),
            source_path=str(payload["source_path"]),
            review_report_path=str(payload.get("review_report_path", "")),
            srs_path=str(payload.get("srs_path", "")),
            docker_enabled=bool(payload.get("docker_enabled", False)),
            github_push_enabled=bool(payload.get("github_push_enabled", False)),
            github_repo_url=str(payload.get("github_repo_url", "")),
            github_branch=str(payload.get("github_branch", "main")),
            commit_message=str(payload.get("commit_message", "Add packaged deployment output")),
            architecture_manifest_path=str(payload.get("architecture_manifest_path", "")),
            target_profile=str(payload.get("target_profile", "docker-actions")),
        )
        return request


@dataclass
class ServiceDescriptor:
    name: str
    service_key: str
    relative_path: str
    runtime: str
    kind: str
    port: int
    has_health_endpoint: bool
    entrypoint: str
    dependencies: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    inferred_from: list[str] = field(default_factory=list)


@dataclass
class ArchitectureAnalysis:
    declared_architecture: str | None
    scanned_architecture: str
    final_architecture: str
    confidence: float
    conflict: bool
    project_name: str
    source_path: str
    selected_stack: str
    services: list[ServiceDescriptor] = field(default_factory=list)
    infrastructure: dict[str, bool] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)


@dataclass
class StrategyDecision:
    architecture: str
    deployment_profile: str
    packaging_supported: bool
    release_strategy: str
    monitoring: list[str]
    notes: list[str]


@dataclass
class ValidationCheck:
    name: str
    success: bool
    details: str


@dataclass
class ValidationReport:
    success: bool
    checks: list[ValidationCheck] = field(default_factory=list)


@dataclass
class GitHubPushResult:
    state: str
    message: str
    branch: str = ""
    commit_sha: str = ""


@dataclass
class JobResult:
    job_id: str
    state: str
    architecture: str
    confidence: float
    strategy: StrategyDecision
    validation: ValidationReport
    push_result: GitHubPushResult
    artifacts: list[str]
    download_path: str
    package_dir: str
    evidence_path: str
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=False)


def resolve_path(value: str) -> Path:
    return Path(value).expanduser().resolve()
