"""
Internal analytics module for self-learning insights.
Provides tools for monitoring and debugging learned patterns.
Not exposed in user UI - internal use only (can be used in admin dashboards).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class LearningAnalytics:
    """
    Analytics view of learned patterns for internal use.
    Safe to expose to internal/admin endpoints only.
    """

    @staticmethod
    def format_insights_for_admin(insights: dict) -> dict[str, Any]:
        """
        Format learning insights for internal admin/debug views.
        Returns human-readable analysis of patterns.
        """
        return {
            "overview": {
                "total_jobs": insights.get("metadata", {}).get("total_jobs_processed", 0),
                "success_rate": f"{insights.get('metadata', {}).get('success_rate', 0):.1%}",
                "successful": insights.get("metadata", {}).get("successful_jobs", 0),
                "failed": insights.get("metadata", {}).get("failed_jobs", 0),
                "needs_review": insights.get("metadata", {}).get("needs_review_jobs", 0),
            },
            "architectures": {
                "detected": list(insights.get("architectures", {}).get("frequency", {}).keys()),
                "frequency": insights.get("architectures", {}).get("frequency", {}),
                "confidence": {
                    arch: {
                        "avg": conf.get("avg", 0),
                        "min": conf.get("min", 0),
                        "max": conf.get("max", 0),
                    }
                    for arch, conf in insights.get("architectures", {}).get("confidence_distribution", {}).items()
                },
            },
            "technology_trends": {
                "most_common_stacks": LearningAnalytics._get_top_n_items(
                    insights.get("technology_stacks", {}), 5
                ),
                "stack_distribution": insights.get("technology_stacks", {}),
            },
            "infrastructure": {
                "detected_patterns": insights.get("infrastructure_patterns", {}),
            },
            "service_runtimes": {
                arch: LearningAnalytics._get_top_n_items(frameworks, 3)
                for arch, frameworks in insights.get("service_frameworks", {}).items()
            },
            "recommendations": LearningAnalytics._generate_recommendations(insights),
        }

    @staticmethod
    def _get_top_n_items(items: dict, n: int = 5) -> list[tuple[str, int]]:
        """Get top N items from a frequency dict"""
        return sorted(items.items(), key=lambda x: x[1], reverse=True)[:n]

    @staticmethod
    def _generate_recommendations(insights: dict) -> list[str]:
        """Generate internal recommendations based on learned patterns"""
        recommendations = []
        
        metadata = insights.get("metadata", {})
        success_rate = metadata.get("success_rate", 0)
        
        if success_rate < 0.50:
            recommendations.append(
                "Low success rate detected. Review detection or packaging logic for improvements."
            )
        
        if metadata.get("needs_review_jobs", 0) > metadata.get("successful_jobs", 0):
            recommendations.append(
                "More jobs need review than succeed. Consider adjusting confidence thresholds."
            )
        
        architectures = insights.get("architectures", {}).get("frequency", {})
        if len(architectures) > 1:
            arch_confidence = insights.get("architectures", {}).get("confidence_distribution", {})
            for arch, conf in arch_confidence.items():
                if conf.get("avg", 0) < 0.70:
                    recommendations.append(
                        f"Architecture '{arch}' has low average confidence ({conf.get('avg')}). "
                        f"May need better detection heuristics."
                    )
        
        return recommendations

    @staticmethod
    def generate_learning_report(insights: dict) -> str:
        """
        Generate a text report of learned patterns for internal documentation.
        """
        lines = [
            "=== SELF-LEARNING ENGINE ANALYTICS ===",
            "",
            "OVERVIEW",
            f"Total jobs processed: {insights.get('metadata', {}).get('total_jobs_processed', 0)}",
            f"Success rate: {insights.get('metadata', {}).get('success_rate', 0):.1%}",
            f"Successful: {insights.get('metadata', {}).get('successful_jobs', 0)}",
            f"Failed: {insights.get('metadata', {}).get('failed_jobs', 0)}",
            f"Needs review: {insights.get('metadata', {}).get('needs_review_jobs', 0)}",
            "",
            "DETECTED ARCHITECTURES",
        ]
        
        arch_freq = insights.get("architectures", {}).get("frequency", {})
        for arch, count in sorted(arch_freq.items(), key=lambda x: x[1], reverse=True):
            pct = (count / insights.get('metadata', {}).get('total_jobs_processed', 1)) * 100
            lines.append(f"  {arch}: {count} jobs ({pct:.1f}%)")
        
        lines.extend([
            "",
            "TECHNOLOGY STACKS",
        ])
        
        for stack, count in sorted(
            insights.get("technology_stacks", {}).items(), key=lambda x: x[1], reverse=True
        )[:10]:
            lines.append(f"  {stack}: {count}")
        
        lines.extend([
            "",
            "INFRASTRUCTURE PATTERNS",
        ])
        
        for pattern, count in sorted(
            insights.get("infrastructure_patterns", {}).items(), key=lambda x: x[1], reverse=True
        ):
            lines.append(f"  {pattern}: {count}")
        
        return "\n".join(lines)


class LearningMonitor:
    """
    Monitor learning engine health and trigger updates.
    Internal use only - not exposed in public API.
    """

    @staticmethod
    def check_learning_health(service) -> dict[str, Any]:
        """
        Check if learning engine is working properly and report issues.
        """
        try:
            insights = service.get_learning_summary()
            total_jobs = insights.get("metadata", {}).get("total_jobs_processed", 0)

            return {
                "healthy": total_jobs > 0,
                "total_jobs_analyzed": total_jobs,
                "architectures_learned": len(insights.get("architectures", {}).get("frequency", {})),
                "status": "Learning engine is active" if total_jobs > 0 else "No jobs found to learn from",
            }
        except Exception as e:
            logger.error(f"Learning health check failed: {e}")
            return {
                "healthy": False,
                "status": f"Learning engine error: {str(e)}",
            }

    @staticmethod
    def trigger_learning_update(service) -> dict[str, Any]:
        """
        Manually trigger a re-learn cycle (useful after bulk job uploads).
        """
        try:
            result = service.relearn_from_jobs(force=True)
            insights = result.get("insights", {})
            
            return {
                "success": True,
                "message": "Learning engine successfully relearned from all jobs",
                "total_jobs": insights.get("metadata", {}).get("total_jobs_processed", 0),
                "architectures": list(
                    insights.get("architectures", {}).get("frequency", {}).keys()
                ),
            }
        except Exception as e:
            logger.error(f"Learning update failed: {e}")
            return {
                "success": False,
                "message": f"Failed to trigger learning update: {str(e)}",
            }
