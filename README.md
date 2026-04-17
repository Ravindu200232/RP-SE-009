# Agent 4

Architecture-aware deployment and packaging agent for the multi-agent SDLC research pipeline.

## What it does

- Accepts Agent 3 output and gathers deployment intent through conversation
- Detects and verifies architecture across six styles
- Fully packages microservice projects for Docker and GitHub Actions
- Optionally validates Docker artifacts locally
- Optionally pushes the packaged result to an existing GitHub repository after validation
- Persists job status, evidence, and downloadable ZIP output

## Project layout

- `backend/` - FastAPI-oriented backend and packaging engine
- `frontend/` - Next.js input and status UI
- `tests/` - pytest coverage for detection, packaging, validation, and GitHub push behavior

## Backend run

```bash
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
