from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os

from .architecture import ArchitectureDetector
from .generator import ArtifactGenerator
from .github_push import GitHubPushClient
from .jobs import JobStore
from .models import (
    GitHubPushResult,
    JobResult,
    JobState,
    PackageRequest,
    StrategyDecision,
    ValidationReport,
)
from .strategy import StrategySelector
from .validators import Validator


AGENT4_FIXED_INPUT_ROOT = Path("/Users/malith_bandara/Desktop/AGENT4_Research/Microservice_input")


class Agent4Service:
    def __init__(
        self,
        store: JobStore | None = None,
        detector: ArchitectureDetector | None = None,
        selector: StrategySelector | None = None,
        generator: ArtifactGenerator | None = None,
        validator: Validator | None = None,
        github_push_client: GitHubPushClient | None = None,
    ) -> None:
        self.store = store or JobStore()
        self.detector = detector or ArchitectureDetector()
        self.selector = selector or StrategySelector()
        self.generator = generator or ArtifactGenerator()
        self.validator = validator or Validator()
        self.github_push_client = github_push_client or GitHubPushClient()

    def process(self, request: PackageRequest) -> JobResult:
        job_dir = self.store.job_dir(request.job_id)
        review_gate_message = self._review_gate(request.review_report_path) if request.review_report_path else ""
        analysis = self.detector.analyze(request.source_path, request.srs_path, request.architecture_manifest_path)
        strategy = self.selector.select(analysis)

        empty_validation = ValidationReport(success=False, checks=[])
        empty_push = GitHubPushResult(state="SKIPPED", message="GitHub push not requested.")
        base_result = JobResult(
            job_id=request.job_id,
            state=JobState.NEEDS_REVIEW,
            architecture=analysis.final_architecture,
            confidence=analysis.confidence,
            strategy=strategy,
            validation=empty_validation,
            push_result=empty_push,
            artifacts=[],
            download_path="",
            package_dir="",
            evidence_path="",
            message="",
        )

        if review_gate_message:
            base_result.message = review_gate_message
            self.store.save(base_result)
            return base_result

        if analysis.conflict or analysis.confidence < 0.80:
            analysis_path = job_dir / "analysis.json"
            strategy_path = job_dir / "strategy.json"
            analysis_path.write_text(json.dumps(self.generator._analysis_payload(analysis), indent=2), encoding="utf-8")
            strategy_path.write_text(json.dumps(strategy.__dict__, indent=2), encoding="utf-8")
            base_result.artifacts = [analysis_path.name, strategy_path.name]
            base_result.package_dir = str(job_dir)
            base_result.evidence_path = str(analysis_path)
            base_result.message = "Architecture metadata and repository scan did not align strongly enough for automatic packaging."
            self.store.save(base_result)
            return base_result

        if not strategy.packaging_supported:
            analysis_path = job_dir / "analysis.json"
            strategy_path = job_dir / "strategy.json"
            analysis_path.write_text(json.dumps(self.generator._analysis_payload(analysis), indent=2), encoding="utf-8")
            strategy_path.write_text(json.dumps(strategy.__dict__, indent=2), encoding="utf-8")
            base_result.artifacts = [analysis_path.name, strategy_path.name]
            base_result.package_dir = str(job_dir)
            base_result.evidence_path = str(strategy_path)
            base_result.message = "Architecture detected successfully, but full packaging is not implemented for this style in v1."
            self.store.save(base_result)
            return base_result

        package_dir, zip_path, artifacts, commit_preview = self.generator.generate(request, analysis, strategy, job_dir)
        validation = self.validator.validate(package_dir, analysis, request.docker_enabled)
        state = JobState.PACKAGED if not request.docker_enabled else JobState.VALIDATED if validation.success else JobState.VALIDATION_FAILED
        push_result = GitHubPushResult(state="SKIPPED", message="GitHub push not requested.")

        if request.github_push_enabled and validation.success:
            push_result = self.github_push_client.push(
                package_dir=package_dir,
                repo_url=request.github_repo_url,
                branch=request.github_branch,
                commit_message=request.commit_message,
            )
            if push_result.state == JobState.AUTH_REQUIRED:
                state = JobState.AUTH_REQUIRED
            elif push_result.state == JobState.PUSHED:
                state = JobState.PUSHED
        elif request.github_push_enabled and not validation.success:
            push_result = GitHubPushResult(state="SKIPPED", message="GitHub push skipped because validation failed.")

        evidence_payload = {
            "job_id": request.job_id,
            "architecture": analysis.final_architecture,
            "confidence": analysis.confidence,
            "strategy": strategy.__dict__,
            "validation": {"success": validation.success, "checks": [check.__dict__ for check in validation.checks]},
            "push_result": push_result.__dict__,
            "artifacts": artifacts,
            "commit_preview": commit_preview,
        }
        evidence_path = self.generator.write_evidence(package_dir, evidence_payload)
        self.generator.rewrite_zip(package_dir, zip_path)

        result = JobResult(
            job_id=request.job_id,
            state=state,
            architecture=analysis.final_architecture,
            confidence=analysis.confidence,
            strategy=strategy,
            validation=validation,
            push_result=push_result,
            artifacts=artifacts,
            commit_preview=commit_preview,
            download_path=f"/download/{request.job_id}",
            package_dir=str(package_dir),
            evidence_path=str(evidence_path),
            message="Packaging completed." if validation.success or not request.docker_enabled else "Packaging completed but validation failed.",
        )
        self.store.save(result)
        return result

    def get_job(self, job_id: str) -> dict | None:
        return self.store.load(job_id)

    def download_path(self, job_id: str) -> Path | None:
        result = self.store.load(job_id)
        if not result:
            return None
        job_dir = self.store.job_dir(job_id)
        for child in job_dir.iterdir():
            if child.suffix == ".zip":
                return child
        return None

    def list_input_candidates(self) -> dict:
        root = self._input_root()
        candidates: list[dict] = []

        if not root.exists() or not root.is_dir():
            return {"root": str(root), "items": []}

        # If the configured input root is itself an application package,
        # use it as the only candidate input for Agent 4.
        if self._looks_like_source_dir(root):
            candidate = self._build_candidate(root, root)
            if candidate:
                candidates.append(candidate)
            return {"root": str(root), "items": candidates}

        for job_dir in sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name.lower()):
            scan_targets = [job_dir]
            scan_targets.extend(path for path in job_dir.iterdir() if path.is_dir())

            for target in scan_targets:
                candidate = self._build_candidate(job_dir, target)
                if candidate:
                    candidates.append(candidate)

        candidates.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return {"root": str(root), "items": candidates}

    def _review_gate(self, review_report_path: str) -> str:
        path = Path(review_report_path)
        if not path.exists():
            return "Review report path does not exist."
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return ""

        if payload.get("action_required") == "REWORK":
            return "Agent 3 marked the package for rework, so Agent 4 will not deploy it."
        if payload.get("passStatus") is False:
            return "Agent 3 did not approve the package for deployment."
        if payload.get("overallScore") is not None and float(payload["overallScore"]) < 85:
            return "Review score is below the deployment threshold."
        return ""

    def _input_root(self) -> Path:
        return AGENT4_FIXED_INPUT_ROOT.expanduser().resolve()

    def _build_candidate(self, job_dir: Path, target: Path) -> dict | None:
        if not self._looks_like_source_dir(target):
            return None

        return {
            "id": f"{job_dir.name}:{target.name}",
            "job_folder": job_dir.name,
            "name": target.name,
            "display_name": f"{job_dir.name} / {target.name}",
            "source_path": str(target),
            "ready": True,
            "missing": [],
            "updated_at": self._iso_mtime(target),
        }

    def _looks_like_source_dir(self, path: Path) -> bool:
        markers = [
            path / "server",
            path / "client",
            path / "frontend",
            path / "docker-compose.yml",
            path / "analysis.json",
            path / "package.json",
            path / "pyproject.toml",
            path / "requirements.txt",
            path / "pom.xml",
        ]
        return any(marker.exists() for marker in markers)

    def _first_existing_file(self, roots: list[Path], patterns: list[str]) -> Path | None:
        seen: set[Path] = set()
        for root in roots:
            if root in seen or not root.exists() or not root.is_dir():
                continue
            seen.add(root)

            for pattern in patterns:
                matches = sorted(path for path in root.glob(pattern) if path.is_file())
                if matches:
                    return matches[0]
        return None

    def _iso_mtime(self, path: Path) -> str:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()

