"""
Test suite for self-learning functionality.
Demonstrates how the learning engine learns from historical jobs.
"""

from __future__ import annotations

import pytest
from pathlib import Path
import json

from backend.agent4.learning import LearningEngine, LearningInsight
from backend.agent4.service import Agent4Service
from backend.agent4.analytics import LearningAnalytics, LearningMonitor


DATA_ROOT = Path(__file__).resolve().parents[1] / ".pytest_tmp" / "learning-jobs"

SAMPLE_JOB = DATA_ROOT / "sample-job"
SAMPLE_JOB.mkdir(parents=True, exist_ok=True)

(SAMPLE_JOB / "result.json").write_text(
    json.dumps(
        {
            "architecture": "microservices",
            "confidence": 0.92,
            "state": "VALIDATED",
            "strategy": {
                "deployment_profile": "docker-compose"
            },
        }
    ),
    encoding="utf-8",
)

(SAMPLE_JOB / "analysis.json").write_text(
    json.dumps(
        {
            "services": [
                {
                    "name": "user-service",
                    "runtime": "node",
                },
                {
                    "name": "order-service",
                    "runtime": "node",
                },
            ],
            "infrastructure": {
                "mongodb": True,
                "redis": True,
            },
        }
    ),
    encoding="utf-8",
)


class TestLearningEngine:
    """Test the self-learning engine"""

    def test_learning_engine_initialization(self):
        """Test that learning engine can be initialized"""
        engine = LearningEngine(DATA_ROOT)
        assert engine is not None
        assert engine.data_root == DATA_ROOT

    def test_learn_from_historical_jobs(self):
        """Test learning from actual historical job data"""
        engine = LearningEngine(DATA_ROOT)
        insights = engine.learn()

        assert insights is not None
        assert insights.total_jobs_processed > 0
        print(f"\n✓ Learned from {insights.total_jobs_processed} historical jobs")

    def test_architecture_frequency_extraction(self):
        """Test that architecture frequencies are correctly extracted"""
        engine = LearningEngine(DATA_ROOT)
        insights = engine.learn()

        assert insights.architecture_frequency
        print(f"\n✓ Architecture frequency distribution:")
        for arch, count in sorted(
            insights.architecture_frequency.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {arch}: {count}")

    def test_confidence_distribution_by_architecture(self):
        """Test that confidence distributions are tracked"""
        engine = LearningEngine(DATA_ROOT)
        insights = engine.learn()

        assert insights.confidence_by_architecture
        print(f"\n✓ Confidence distributions by architecture:")
        for arch, confidences in insights.confidence_by_architecture.items():
            if confidences:
                avg_conf = sum(confidences) / len(confidences)
                print(
                    f"  {arch}: avg={avg_conf:.3f}, "
                    f"min={min(confidences):.3f}, max={max(confidences):.3f} "
                    f"({len(confidences)} samples)"
                )

    def test_technology_stack_learning(self):
        """Test that technology stacks are captured"""
        engine = LearningEngine(DATA_ROOT)
        insights = engine.learn()

        assert insights.tech_stack_frequency
        print(f"\n✓ Most common technology stacks:")
        for stack, count in sorted(
            insights.tech_stack_frequency.items(), key=lambda x: x[1], reverse=True
        )[:5]:
            print(f"  {stack}: {count}")

    def test_success_rate_tracking(self):
        """Test that success rates are tracked"""
        engine = LearningEngine(DATA_ROOT)
        insights = engine.learn()

        total = insights.total_jobs_processed
        success_rate = insights.successful_jobs / total if total > 0 else 0
        print(f"\n✓ Job outcomes:")
        print(f"  Total: {total}")
        print(f"  Successful: {insights.successful_jobs} ({success_rate:.1%})")
        print(f"  Failed: {insights.failed_jobs}")
        print(f"  Needs review: {insights.needs_review_jobs}")

    def test_learning_insights_export(self):
        """Test exporting learning insights to dict"""
        engine = LearningEngine(DATA_ROOT)
        insights = engine.learn()

        insights_dict = engine.to_dict()
        assert "metadata" in insights_dict
        assert "architectures" in insights_dict
        assert "technology_stacks" in insights_dict
        print(f"\n✓ Learning insights exported with {len(insights_dict)} sections")

    def test_learning_with_service_integration(self):
        """Test that learning engine integrates with Agent4Service"""
        service = Agent4Service()
        
        # Service should have initialized learning engine
        assert service.learning_engine is not None
        print(f"\n✓ Agent4Service initialized with learning engine")
        
        # Test getting learning summary
        summary = service.get_learning_summary()
        assert "metadata" in summary
        print(f"✓ Retrieved learning summary from service")

    def test_architecture_confidence_baseline(self):
        """Test getting confidence baseline for an architecture"""
        service = Agent4Service()
        
        # Test with microservices (most common in test data)
        baseline = service.get_architecture_confidence_baseline("microservices")
        
        if baseline.get("available"):
            print(f"\n✓ Microservices confidence baseline:")
            print(f"  Average: {baseline.get('avg', 0):.3f}")
            print(f"  Range: {baseline.get('min', 0):.3f} - {baseline.get('max', 0):.3f}")
            print(f"  Samples: {baseline.get('count', 0)}")

    def test_analytics_formatting(self):
        """Test analytics module formatting"""
        engine = LearningEngine(DATA_ROOT)
        insights = engine.learn()
        insights_dict = engine.to_dict()

        admin_view = LearningAnalytics.format_insights_for_admin(insights_dict)
        assert "overview" in admin_view
        assert "architectures" in admin_view
        assert "recommendations" in admin_view
        print(f"\n✓ Admin analytics view formatted with {len(admin_view)} sections")

    def test_learning_report_generation(self):
        """Test generating a learning report"""
        engine = LearningEngine(DATA_ROOT)
        insights = engine.learn()
        insights_dict = engine.to_dict()

        report = LearningAnalytics.generate_learning_report(insights_dict)
        assert "OVERVIEW" in report
        assert "DETECTED ARCHITECTURES" in report
        print(f"\n✓ Learning report generated ({len(report)} chars)")
        print(report)

    def test_learning_monitor_health_check(self):
        """Test learning monitor health checks"""
        service = Agent4Service()
        health = LearningMonitor.check_learning_health(service)

        assert "healthy" in health
        assert "total_jobs_analyzed" in health
        print(f"\n✓ Learning monitor health check:")
        print(f"  Status: {health.get('status')}")
        print(f"  Jobs analyzed: {health.get('total_jobs_analyzed')}")
        print(f"  Architectures learned: {health.get('architectures_learned')}")

    def test_learning_debug_export(self):
        """Test exporting learning insights to debug file"""
        engine = LearningEngine(DATA_ROOT)
        insights = engine.learn()

        # Export to a test file
        test_output = DATA_ROOT.parent / "learning_insights_test.json"
        export_path = engine.debug_export(test_output)

        assert export_path.exists()
        content = json.loads(export_path.read_text(encoding="utf-8"))
        assert "metadata" in content
        
        # Clean up
        export_path.unlink()
        print(f"\n✓ Learning debug export successful")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
