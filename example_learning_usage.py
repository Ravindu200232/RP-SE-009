#!/usr/bin/env python3
"""
Example: Using the Self-Learning System

This script demonstrates how the self-learning system works internally
and how to query learned patterns from the backend.

Note: These methods are internal-only and NOT exposed in the public API or UI.
"""

from backend.agent4.service import Agent4Service
from backend.agent4.analytics import LearningAnalytics, LearningMonitor
from backend.agent4.learning import LearningEngine
from pathlib import Path


def main():
    print("=" * 60)
    print("AGENT 4 - SELF-LEARNING SYSTEM DEMONSTRATION")
    print("=" * 60)
    
    # Initialize the service (learning engine starts automatically)
    service = Agent4Service()
    print("\n✓ Service initialized with self-learning engine")
    
    # 1. Check learning engine health
    print("\n" + "-" * 60)
    print("1. LEARNING ENGINE HEALTH CHECK")
    print("-" * 60)
    health = LearningMonitor.check_learning_health(service)
    print(f"Status: {health.get('status')}")
    print(f"Jobs analyzed: {health.get('total_jobs_analyzed')}")
    print(f"Architectures learned: {health.get('architectures_learned')}")
    
    # 2. Get learning summary
    print("\n" + "-" * 60)
    print("2. LEARNING SUMMARY")
    print("-" * 60)
    summary = service.get_learning_summary()
    
    print(f"\nJobs processed: {summary['metadata']['total_jobs_processed']}")
    print(f"Success rate: {summary['metadata']['success_rate']:.1%}")
    print(f"Successful: {summary['metadata']['successful_jobs']}")
    print(f"Failed: {summary['metadata']['failed_jobs']}")
    print(f"Needs review: {summary['metadata']['needs_review_jobs']}")
    
    # 3. Architecture insights
    print("\n" + "-" * 60)
    print("3. ARCHITECTURE INTELLIGENCE")
    print("-" * 60)
    
    architectures = summary['architectures']['frequency']
    print(f"\nDetected architectures ({len(architectures)}):")
    for arch, count in sorted(architectures.items(), key=lambda x: x[1], reverse=True):
        pct = (count / summary['metadata']['total_jobs_processed']) * 100
        confidence = summary['architectures']['confidence_distribution'].get(arch, {})
        avg_conf = confidence.get('avg', 0)
        print(f"  • {arch:20} {count:3} jobs ({pct:5.1f}%) - avg confidence: {avg_conf:.3f}")
    
    # 4. Technology trends
    print("\n" + "-" * 60)
    print("4. TECHNOLOGY STACK TRENDS")
    print("-" * 60)
    stacks = summary['technology_stacks']
    print(f"\nMost common deployment profiles:")
    for stack, count in sorted(stacks.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  • {stack}: {count}")
    
    # 5. Infrastructure patterns
    print("\n" + "-" * 60)
    print("5. INFRASTRUCTURE PATTERNS LEARNED")
    print("-" * 60)
    infra = summary['infrastructure_patterns']
    print(f"\nDetected infrastructure components ({len(infra)}):")
    for component, count in sorted(infra.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {component}: {count}")
    
    # 6. Service runtime/framework insights
    print("\n" + "-" * 60)
    print("6. SERVICE FRAMEWORK TRENDS")
    print("-" * 60)
    frameworks = summary['service_frameworks']
    for arch, runtime_dist in frameworks.items():
        if runtime_dist:
            print(f"\n  {arch}:")
            for runtime, count in sorted(runtime_dist.items(), key=lambda x: x[1], reverse=True)[:3]:
                print(f"    • {runtime}: {count}")
    
    # 7. Microservices confidence analysis
    print("\n" + "-" * 60)
    print("7. MICROSERVICES DETECTION CONFIDENCE")
    print("-" * 60)
    baseline = service.get_architecture_confidence_baseline("microservices")
    if baseline.get("available"):
        print(f"  Average confidence: {baseline.get('avg', 0):.3f}")
        print(f"  Min confidence: {baseline.get('min', 0):.3f}")
        print(f"  Max confidence: {baseline.get('max', 0):.3f}")
        print(f"  Samples: {baseline.get('count', 0)}")
    
    # 8. Recommended stacks for microservices
    print("\n" + "-" * 60)
    print("8. RECOMMENDED DEPLOYMENT PROFILES")
    print("-" * 60)
    stacks = service.get_recommended_stacks("microservices", limit=3)
    print(f"\nFor microservices architecture:")
    for stack, count in stacks:
        print(f"  • {stack}: {count} uses")
    
    # 9. Generate admin report
    print("\n" + "-" * 60)
    print("9. ADMIN ANALYTICS REPORT")
    print("-" * 60)
    admin_view = LearningAnalytics.format_insights_for_admin(summary)
    print(f"\nAdmin insights available for {len(admin_view)} areas:")
    for section in admin_view.keys():
        print(f"  ✓ {section}")
    
    recommendations = admin_view.get('recommendations', [])
    if recommendations:
        print(f"\nGenerated recommendations ({len(recommendations)}):")
        for rec in recommendations:
            print(f"  → {rec}")
    
    # 10. Generate detailed report
    print("\n" + "-" * 60)
    print("10. DETAILED LEARNING REPORT")
    print("-" * 60)
    report = LearningAnalytics.generate_learning_report(summary)
    print(report)
    
    # 11. Internal methods available
    print("\n" + "-" * 60)
    print("11. AVAILABLE INTERNAL METHODS (Backend Only)")
    print("-" * 60)
    print("""
    These methods exist in Agent4Service but are NOT exposed in API:
    
    service.get_learning_summary()
      → Full learning insights from all historical jobs
    
    service.get_architecture_confidence_baseline(architecture)
      → Confidence distribution for a specific architecture
    
    service.get_recommended_stacks(architecture, limit=3)
      → Most common deployment profiles for architecture
    
    service.get_framework_insights(architecture)
      → Framework/runtime distribution for services
    
    service.relearn_from_jobs(force=True)
      → Force re-analysis of all historical jobs
    
    LearningMonitor.check_learning_health(service)
      → Health status of learning engine
    
    LearningAnalytics.format_insights_for_admin(summary)
      → Format for internal admin dashboards
    
    LearningAnalytics.generate_learning_report(summary)
      → Generate text report for documentation
    """)
    
    # 12. Privacy guarantee
    print("\n" + "-" * 60)
    print("12. PRIVACY GUARANTEES")
    print("-" * 60)
    print("""
    ✓ No project names exposed
    ✓ No repository URLs exposed
    ✓ No personal data collected
    ✓ No UI access to learning data
    ✓ No public API endpoints for learning
    ✓ Statistical patterns only
    ✓ Users cannot see other users' projects
    ✓ Learning data stays internal
    """)
    
    print("=" * 60)
    print("SELF-LEARNING SYSTEM STATUS: ✓ ACTIVE AND FUNCTIONAL")
    print("=" * 60)


if __name__ == "__main__":
    main()
