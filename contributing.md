# Contributing to AgentForge

AgentForge is easiest to maintain when each change stays inside the pipeline stage that owns it and the repair system keeps evidence stronger than guesses.

## Development setup

Requirements: Python 3.11+, Node.js 20+, npm and a configured Ollama/model runtime.

```bash
./setup.sh
./start.command          # macOS/Linux
# or start.bat on Windows
```

Backend-only development can use `python3 server.py`.

## Codebase map

| Area | Location | Responsibility |
|---|---|---|
| Planning | `agents/planner/` | Requirements, design, site map and architecture (`planning/`), generation (`builder/`), scaffolding (`templates/`) |
| Pipeline | `agents/pipeline/` | Standalone prepare → build → verify flow, build gates (`build/`), bug workflow (`bugs/`) |
| Build | `agents/build/` | Baseline runtime/browser and route checks |
| Analysis/repair | `agents/analysis/` | Diagnosis (`checks/`), fixes (`repair/`), reproduction (`runtime/`) |
| Feature/edit tools | `agents/features/` | Selection, capture, image/source guidance (`planning/`, `runtime/`) |
| Data | `agents/data/` | Database lifecycle, install and record helpers |
| Builder server | `agents/server/` | Studio project files and WebSocket build/update jobs |
| Unit QA | `qa_agent/unit/` | Vitest authoring, harness and runner |
| E2E QA | `qa_agent/e2e/` | Journey authoring, grounding, execution and results |
| Verification | `qa_agent/verification/` | API/security/PDF reporting |
| QA server | `qa_agent/server/` | QA pipeline stages exposed by the backend |
| Shared server | `server_modules/` | Core, SRS, deployment and HTTP runtime fragments |
| Studio | `studio/` | Next.js UI |
| Desktop | `desktop/` | Electron lifecycle and splash |

Do not add a tiny file whose only job is to re-export a moved class. Update internal callers to the real module instead.

## Change rules

- Keep Builder behavior backward-compatible unless the task explicitly changes it.
- Keep source files below 1000 lines, and keep new or refactored `agents/` modules at or below roughly 400; split by responsibility, not arbitrary line count.
- Use server-session identity for authenticated user-owned records; never trust a client-provided owner ID.
- Do not add auth to an app whose requirements do not need auth.
- A successful mutation must make the new data visible without a manual browser refresh.
- E2E actions must come from requirements plus current source/DOM evidence. Do not invent magic promo codes, role credentials, test IDs or redirect targets.
- Browser console/page errors are evidence. Prefer the exact source location from the stack over a broad repair scope.
- Test retries do not inflate coverage. Stage scores describe the final accepted E2E journey.
- Never turn a failing generated test into a skip just to make the suite green.

## Validation before a pull request

Run at least:

```bash
python -m compileall -q agents qa_agent server_modules server.py server_runtime.py srs-agent/srs_agent deployment-agent/deploy_agent
python studio/scripts/verify_ui_contract.py
node studio/scripts/verify_activity.mjs
node studio/scripts/verify_progress.mjs
node studio/scripts/verify_test_counts.mjs
node studio/scripts/verify_uploads.mjs
node --check desktop/main.js desktop/runtime.js desktop/preload.js
python deployment-agent/verify_aws_session_contract.py
```

When npm dependencies are available, also run:

```bash
npm --prefix studio ci --no-audit --no-fund
npm --prefix studio run build
```

For behavioral changes, run a generated application through its relevant unit, runtime/API and E2E flow rather than relying only on repository syntax checks.

## Pull requests

Keep one coherent change per PR. Explain the observed failure/evidence, the source files changed, and which validation was run. UI changes should include a screenshot. Do not commit `node_modules`, `.next`, `production-ready`, caches, logs or local secrets.
