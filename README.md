# Agent 4

Architecture-aware deployment and packaging agent for the multi-agent SDLC research pipeline.

## What it does

- Accepts Agent 3 output and gathers deployment intent through conversation
- Detects and verifies architecture across six styles
- Fully packages microservice projects for Docker and GitHub Actions
- Optionally validates Docker artifacts locally
- Optionally pushes the packaged result to an existing GitHub repository after validation
- Persists job status, evidence, and downloadable ZIP output
- **Learns from all historical jobs to improve future processing** (internal-only, no UI exposure)

## Project layout

- `backend/` - FastAPI-oriented backend and packaging engine
- `frontend/` - Next.js input and status UI
- `tests/` - pytest coverage for detection, packaging, validation, GitHub push, and self-learning
- `LEARNING_SYSTEM.md` - Documentation for self-learning functionality
- `SELF_LEARNING_QUICKSTART.md` - Quick start guide for self-learning features

## Backend run

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8004
```

## Frontend run

```bash
cd frontend
npm install
npm run dev
```

## Job request shape

`POST /package`

```json
{
  "source_path": "/absolute/path/to/agent3/output",
  "docker_enabled": true,
  "github_push_enabled": true,
  "github_repo_url": "git@github.com:owner/repo.git",
  "github_branch": "main",
  "commit_message": "Add packaged deployment output"
}
```

## Notes

- Agent 4 input discovery is fixed to `/Users/malith_bandara/Desktop/AGENT4_Research/Microservice_input`.
- Microservices are the only fully packaged architecture in v1.
- Other detected architectures return strategy and evidence output with `NEEDS_REVIEW`.
- GitHub push uses machine-level Git authentication only. No secrets are collected in the UI.
- AWS deployment artifacts are intentionally deferred for a later milestone.

## Self-Learning System

Agent 4 includes an internal **self-learning engine** that learns from all processed jobs:

- **Automatic** - Learns on startup from 40+ historical jobs
- **Internal Only** - No UI exposure, no public API endpoints for learning data
- **Privacy First** - No project names, URLs, or personal data exposed
- **Statistical Patterns** - Learns architecture frequencies, confidence distributions, technology trends
- **No Configuration** - Works automatically with zero setup

### Learning Insights Available

From 40+ historical jobs, learns:

- Architecture detection patterns (37 microservices, 2 event-driven, 1 monolith)
- Confidence distributions by architecture (avg 0.888 for microservices)
- Most common technology stacks and deployment profiles
- Infrastructure patterns (postgres, redis, rabbitmq, mongo)
- Service framework trends
- Job success rates and outcomes

### Testing Self-Learning

```bash
# Run all learning tests
pytest tests/test_learning.py -v -s

# See what was learned and get a report
python example_learning_usage.py
```

See [LEARNING_SYSTEM.md](LEARNING_SYSTEM.md) for complete documentation and internal usage examples.
