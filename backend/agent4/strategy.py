from __future__ import annotations

from .models import ArchitectureAnalysis, StrategyDecision


class StrategySelector:
    def select(self, analysis: ArchitectureAnalysis) -> StrategyDecision:
        architecture = analysis.final_architecture
        if architecture == "microservices":
            return StrategyDecision(
                architecture=architecture,
                deployment_profile="docker-compose + github-actions",
                packaging_supported=True,
                release_strategy="manual-promote",
                monitoring=["/health endpoints", "container health checks", "GitHub Actions run status"],
                notes=[
                    "Generate Dockerfiles, docker-compose, GitHub Actions workflows, and deployment evidence.",
                    "Cloud deployment targets are intentionally deferred until a later milestone.",
                ],
            )

        guidance = {
            "monolith": "Prefer a single-container deployment path with simpler CI/CD and hosting.",
            "modular_monolith": "Prefer a single deployable image with module-aware environment configuration.",
            "layered": "Prefer a single service deployment with layered health and API checks.",
            "event_driven": "Prefer queue-aware deployment with broker provisioning and consumer health checks.",
            "serverless": "Prefer function packaging with managed identity and event source mapping.",
        }
        return StrategyDecision(
            architecture=architecture,
            deployment_profile="strategy-only",
            packaging_supported=False,
            release_strategy="manual-review",
            monitoring=["deployment evidence only"],
            notes=[guidance.get(architecture, "Architecture-specific packaging is not implemented in v1.")],
        )
