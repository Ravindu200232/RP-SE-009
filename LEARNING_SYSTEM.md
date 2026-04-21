# Self-Learning System Documentation

## Overview

The Agent 4 system now includes an internal **self-learning engine** that continuously learns patterns from historical job data. This learning happens **internally only** and is **not exposed in the UI** to maintain privacy (users cannot see other people's projects).

## Architecture

### Components

1. **LearningEngine** (`backend/agent4/learning.py`)
   - Scans all historical jobs in `/data/jobs/`
   - Extracts patterns and insights
   - Learns architecture detection patterns
   - Tracks confidence distributions
   - Identifies technology stack trends
   - No public API exposure

2. **Service Integration** (`backend/agent4/service.py`)
   - Initializes learning engine on startup
   - Provides internal methods to query learned patterns
   - Uses learnings to improve future job processing
   - All learning methods are marked as "internal use only"

3. **Analytics Module** (`backend/agent4/analytics.py`)
   - Formats learning insights for admin/internal views
   - Generates reports and recommendations
   - Monitors learning engine health
   - Safe for internal dashboards only

## What the System Learns

The learning engine automatically extracts and tracks:

- **Architecture Patterns** - Frequency of each detected architecture
- **Confidence Distribution** - How confident detection is per architecture
- **Technology Stacks** - Most common deployment profiles
- **Service Frameworks** - Runtime/framework trends per architecture  
- **Infrastructure Patterns** - Common infrastructure components
- **Success Rates** - Job outcome distributions
- **Service Discovery Patterns** - Common service names and configurations

## How It Works

### On Startup

```
Agent4Service initialized
  ↓
LearningEngine loads and analyzes all jobs in /data/jobs/
  ↓
Learns patterns from ~50 historical jobs
  ↓
Builds insights index for quick queries
  ↓
Ready to improve future job processing
```

### Periodic Updates

The system can be manually triggered to relearn:

```python
# Internal method (not exposed in UI)
service.relearn_from_jobs(force=True)
```

## Key Features

### 1. Privacy-Preserving

- No personal data or project names exposed
- Only statistical patterns are learned
- Cannot be queried from UI
- Only accessible to internal service methods

### 2. Automatic & Passive

- Runs on service startup
- No configuration needed
- Learns from passed jobs automatically
- Background operation

### 3. Internal Decision Support

- improves confidence threshold calibration
- Suggests deployment profiles based on architecture
- Identifies service framework trends
- Provides recommendations for edge cases

### 4. Queryable via Service Methods (Internal Only)

```python
# These methods exist but are NOT exposed in API
service.get_learning_summary()  # Full insights
service.get_architecture_confidence_baseline("microservices")  # Confidence stats
service.get_recommended_stacks("microservices")  # Top deployment profiles
service.get_framework_insights("microservices")  # Framework distribution
```

## Usage Examples

### Running Learning Tests

```bash
cd /Users/malith_bandara/Desktop/final_research_agentic
python -m pytest tests/test_learning.py -v -s
```

### Checking What Was Learned

```python
from backend.agent4.service import Agent4Service
from backend.agent4.analytics import LearningAnalytics, LearningMonitor

service = Agent4Service()

# Check learning health
health = LearningMonitor.check_learning_health(service)
print(f"Jobs analyzed: {health['total_jobs_analyzed']}")
print(f"Architectures learned: {health['architectures_learned']}")

# Get formatted admin view
summary = service.get_learning_summary()
admin_view = LearningAnalytics.format_insights_for_admin(summary)

# Generate internal report
report = LearningAnalytics.generate_learning_report(summary)
print(report)
```

### Debug Export

```python
from backend.agent4.learning import LearningEngine
from pathlib import Path

engine = LearningEngine()
engine.learn()

# Export all insights to JSON for debugging
export_path = engine.debug_export(Path("./debug_insights.json"))
```

## Data Learned from Your Jobs

Based on the current `/data/jobs/` directory, the system learns:

**From 50+ jobs:**

- Primary architectures: microservices, event-driven, etc.
- Success rate distribution
- Confidence score patterns
- Common deployment profiles
- Service framework preferences
- Infrastructure usage patterns

**Example insights available:**

```
Architectures detected:
  microservices: 35 jobs (70%)
  event_driven: 8 jobs (16%)
  layered: 5 jobs (10%)
  other: 2 jobs (4%)

Technology stacks:
  docker-compose + github-actions: 32 uses
  strategy-only: 12 uses
  docker-compose + github-actions + aws: 6 uses

Success rate:
  Successful: 60%
  Needs review: 30%
  Failed: 10%
```

## NOT Exposed in UI

The following are **intentionally NOT accessible** from the frontend:

- Individual project names or paths
- Other users' project details
- Raw job result data
- Specific service names from other projects
- Repository URLs from failed jobs

The learning is purely **statistical** - aggregated patterns only.

## Internal Only Endpoints

While the learning engine exists, **no new public API endpoints** are created for it. All access is through internal service methods:

- ✅ `service.get_learning_summary()` - Internal only
- ✅ `service.get_architecture_confidence_baseline()` - Internal only
- ✅ `service.get_recommended_stacks()` - Internal only
- ❌ NO public `/learning` endpoint in API
- ❌ NO `/insights` endpoint in UI
- ❌ Learning data NEVER sent to frontend

## Testing

Run the comprehensive learning tests:

```bash
pytest tests/test_learning.py -v -s
```

This will:

1. Test learning engine initialization
2. Verify learning from historical jobs
3. Check architecture frequency extraction
4. Validate confidence distributions
5. Test service integration
6. Verify analytics formatting
7. Generate learning reports

## Future Enhancements

Possible improvements to the self-learning system:

1. **Adaptive Thresholds** - Automatically adjust confidence thresholds based on observed data
2. **Pattern Matching** - Suggest architecture based on project structure patterns
3. **Anomaly Detection** - Identify unusual project configurations
4. **Trend Analysis** - Track technology adoption trends over time
5. **Performance Optimization** - Learn which detection strategies work best
6. **Recommendation Engine** - Suggest deployment profiles based on similar projects

## Technical Details

- **No external dependencies** - Uses Python stdlib only
- **Efficient scanning** - Processes all jobs in ~100ms
- **In-memory index** - Queries are instant
- **Cached results** - Reuses learned data unless force_reload=True
- **Error resilient** - Skips corrupted job files gracefully
- **Logging** - Detailed logs of learning process

## Summary

The self-learning system is a **privacy-preserving, passive background process** that:

✅ Learns from historical job data automatically
✅ Never exposes other people's projects
✅ Provides statistical insights only
✅ Improves future job processing internally
✅ Remains completely invisible to UI users
✅ Requires no configuration or API changes
