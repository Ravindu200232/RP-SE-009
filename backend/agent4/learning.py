"""
Self-learning module that analyzes historical job data internally.
Learns patterns from processed jobs and improves detection/strategy selection.
This is kept internal and not exposed via API.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict, field
from pathlib import Path
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LearningInsight:
    """Internal learning metrics from historical jobs"""
    
    architecture_frequency: dict[str, int] = field(default_factory=dict)
    confidence_by_architecture: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    tech_stack_frequency: dict[str, int] = field(default_factory=dict)
    success_rate_by_architecture: dict[str, float] = field(default_factory=dict)
    common_services_per_architecture: dict[str, dict[str, int]] = field(default_factory=dict)
    infrastructure_patterns: dict[str, int] = field(default_factory=dict)
    service_framework_mapping: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    avg_services_per_architecture: dict[str, float] = field(default_factory=dict)
    total_jobs_processed: int = 0
    successful_jobs: int = 0
    failed_jobs: int = 0
    needs_review_jobs: int = 0


class LearningEngine:
    """
    Internal learning engine that builds insights from historical job data.
    Runs on startup and periodically to extract patterns without exposing data.
    """

    def __init__(self, data_root: Path | None = None):
        self.data_root = data_root or Path("/Users/malith_bandara/Desktop/final_research_agentic/data/jobs")
        self.insights: LearningInsight | None = None
        self._last_loaded_count = 0

    def learn(self, force_reload: bool = False) -> LearningInsight:
        """
        Analyze all historical jobs and build learning insights.
        Returns cached insights unless force_reload=True.
        """
        if self.insights is not None and not force_reload:
            return self.insights

        self.insights = self._analyze_all_jobs()
        logger.info(
            f"Learning engine processed {self.insights.total_jobs_processed} jobs. "
            f"Success rate: {self._get_success_rate():.1%}"
        )
        return self.insights

    def _analyze_all_jobs(self) -> LearningInsight:
        """Scan all job directories and extract patterns"""
        insights = LearningInsight()

        if not self.data_root.exists():
            logger.warning(f"Data root does not exist: {self.data_root}")
            return insights

        for job_dir in self.data_root.iterdir():
            if not job_dir.is_dir():
                continue

            result = self._load_job_result(job_dir)
            if not result:
                continue

            insights.total_jobs_processed += 1
            self._process_job_result(result, insights, job_dir)

        # Calculate derived metrics
        self._compute_derived_metrics(insights)

        return insights

    def _load_job_result(self, job_dir: Path) -> dict[str, Any] | None:
        """Load result.json from a job directory"""
        result_file = job_dir / "result.json"
        if not result_file.exists():
            return None

        try:
            return json.loads(result_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError) as e:
            logger.debug(f"Failed to load job result from {result_file}: {e}")
            return None

    def _process_job_result(self, result: dict[str, Any], insights: LearningInsight, job_dir: Path) -> None:
        """Extract learning metrics from a single job result"""
        # Track architecture frequency and confidence
        architecture = result.get("architecture", "unknown")
        confidence = result.get("confidence", 0.0)
        state = result.get("state", "UNKNOWN")

        insights.architecture_frequency[architecture] = insights.architecture_frequency.get(architecture, 0) + 1
        insights.confidence_by_architecture[architecture].append(confidence)

        # Track job states
        if state == "PUSHED" or state == "VALIDATED":
            insights.successful_jobs += 1
        elif state == "VALIDATION_FAILED" or state == "ERROR":
            insights.failed_jobs += 1
        elif state == "NEEDS_REVIEW":
            insights.needs_review_jobs += 1

        # Extract tech stack from selected_stack in strategy
        strategy = result.get("strategy", {})
        selected_stack = strategy.get("deployment_profile", "unknown")
        insights.tech_stack_frequency[selected_stack] = insights.tech_stack_frequency.get(selected_stack, 0) + 1

        # Track services if available
        analysis_file = job_dir / "analysis.json"
        if analysis_file.exists():
            try:
                analysis = json.loads(analysis_file.read_text(encoding="utf-8"))
                self._extract_service_patterns(analysis, insights, architecture)
                self._extract_infrastructure_patterns(analysis, insights)
            except (json.JSONDecodeError, IOError):
                pass

    def _extract_service_patterns(self, analysis: dict[str, Any], insights: LearningInsight, architecture: str) -> None:
        """Learn patterns about service discovery and frameworks"""
        services = analysis.get("services", [])

        if architecture not in insights.common_services_per_architecture:
            insights.common_services_per_architecture[architecture] = {}

        service_names = Counter()
        for service in services:
            name = service.get("name", "unknown")
            runtime = service.get("runtime", "unknown")
            service_names[name] += 1

            # Track framework usage per architecture
            insights.service_framework_mapping[architecture][runtime] += 1

        # Track service count stats
        insights.common_services_per_architecture[architecture].update(service_names)

    def _extract_infrastructure_patterns(self, analysis: dict[str, Any], insights: LearningInsight) -> None:
        """Learn patterns about infrastructure detection"""
        infrastructure = analysis.get("infrastructure", {})

        for infra_type, present in infrastructure.items():
            if present:
                insights.infrastructure_patterns[infra_type] = insights.infrastructure_patterns.get(infra_type, 0) + 1

    def _compute_derived_metrics(self, insights: LearningInsight) -> None:
        """Compute aggregate metrics from collected data"""
        if insights.total_jobs_processed == 0:
            return

        # Average confidence per architecture
        for arch, confidences in insights.confidence_by_architecture.items():
            if confidences:
                avg_confidence = sum(confidences) / len(confidences)
                insights.success_rate_by_architecture[arch] = round(avg_confidence, 3)

        # Average services per architecture
        for arch, service_count in insights.common_services_per_architecture.items():
            if service_count:
                total_services = sum(service_count.values())
                avg = total_services / len(service_count)
                insights.avg_services_per_architecture[arch] = round(avg, 2)

    def get_best_confidence_for_architecture(self, architecture: str) -> dict[str, Any]:
        """
        Internal method: Get confidence distribution for an architecture
        Used to calibrate detection thresholds
        """
        if not self.insights:
            self.learn()

        confidences = self.insights.confidence_by_architecture.get(architecture, [])
        if not confidences:
            return {"available": False}

        return {
            "available": True,
            "min": round(min(confidences), 3),
            "max": round(max(confidences), 3),
            "avg": round(sum(confidences) / len(confidences), 3),
            "count": len(confidences),
        }

    def get_common_stacks_for_architecture(self, architecture: str, limit: int = 3) -> list[tuple[str, int]]:
        """Internal method: Get most common deployment profiles for an architecture"""
        if not self.insights:
            self.learn()

        # This would require tracking stacks per architecture in the learning process
        # For now, return all stacks sorted by frequency
        items = self.insights.tech_stack_frequency.items()
        return sorted(items, key=lambda x: x[1], reverse=True)[:limit]

    def get_service_frameworks_for_architecture(self, architecture: str) -> dict[str, int]:
        """Internal method: Get framework distribution for services in this architecture"""
        if not self.insights:
            self.learn()

        frameworks = self.insights.service_framework_mapping.get(architecture, {})
        return dict(frameworks.most_common(5))

    def to_dict(self) -> dict[str, Any]:
        """Convert insights to dictionary for internal logging/debugging"""
        if not self.insights:
            return {}

        return {
            "metadata": {
                "total_jobs_processed": self.insights.total_jobs_processed,
                "successful_jobs": self.insights.successful_jobs,
                "failed_jobs": self.insights.failed_jobs,
                "needs_review_jobs": self.insights.needs_review_jobs,
                "success_rate": self._get_success_rate(),
            },
            "architectures": {
                "frequency": self.insights.architecture_frequency,
                "confidence_distribution": {
                    arch: {
                        "avg": round(sum(conf) / len(conf), 3) if conf else 0,
                        "min": round(min(conf), 3) if conf else 0,
                        "max": round(max(conf), 3) if conf else 0,
                        "count": len(conf),
                    }
                    for arch, conf in self.insights.confidence_by_architecture.items()
                },
            },
            "technology_stacks": self.insights.tech_stack_frequency,
            "infrastructure_patterns": self.insights.infrastructure_patterns,
            "service_frameworks": {
                arch: dict(frameworks.most_common(10))
                for arch, frameworks in self.insights.service_framework_mapping.items()
            },
        }

    def _get_success_rate(self) -> float:
        """Calculate overall success rate"""
        if self.insights and self.insights.total_jobs_processed > 0:
            return self.insights.successful_jobs / self.insights.total_jobs_processed
        return 0.0

    def debug_export(self, output_path: Path | None = None) -> Path:
        """
        Export detailed learning metrics to a JSON file for debugging.
        This is an internal debugging tool, not exposed via API.
        """
        output_path = output_path or self.data_root.parent / "learning_insights.json"

        insights_dict = self.to_dict()
        output_path.write_text(json.dumps(insights_dict, indent=2), encoding="utf-8")
        logger.info(f"Learning insights exported to {output_path}")

        return output_path
