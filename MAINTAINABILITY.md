# AgentForge maintenance map

The repository follows the actual pipeline so a maintainer can find behavior without chasing compatibility wrappers.

## Build pipeline

Each area is split into subpackages so one concern stays in one readable file.

- `agents/planner/` — requirement interpretation, routes and sitemap (`planning/`), approved-plan generation and file writing (`builder/`), scaffolding defaults (`templates/`).
- `agents/pipeline/` — the standalone prepare → plan → build → verify → report → serve flow (`build_pipeline.py`), build gates and fix loop (`build/`), bug request/workflow/verification (`bugs/`), edit safety (`feature_safety.py`).
- `agents/build/` — baseline route and browser validation of a generated project.
- `agents/analysis/` — the analyzer plus source scans (`checks/`), evidence-backed repair (`repair/`), runtime probes and browser reproduction (`runtime/`).
- `agents/features/` — feature/edit/capture/image helpers, with request and evidence scoping (`planning/`) and applied updates (`runtime/`).
- `agents/data/` — database lifecycle, install and record helpers (`database_*.py`).
- `agents/core/` — shared LLM (`llm/`), workspace (`workspace/`), import (`imports/`), syntax (`syntax/`), command and cancellation (`runtime/`), Next.js (`nextjs/`), documentation index (`docs/`) and build lessons (`learning/`).
- `agents/server/` — Studio project file access and WebSocket build/update jobs (`projects/`).

## QA pipeline

- `qa_agent/unit/` — unit-test authoring, harness, execution and snapshots.
- `qa_agent/e2e/` — flow authoring, grounding, browser execution, console evidence and result ledgers.
- `qa_agent/verification/` — API/security/PDF reporting.
- `qa_agent/core/` — QA session state.
- `qa_agent/server/` — server-side QA stages.

## Runtime

- `server.py` — stable backend entrypoint.
- `server_runtime.py` — ordered shared-runtime assembler.
- `server_modules/core/` — startup/process lifecycle.
- `server_modules/srs/` — SRS bridge/API.
- `server_modules/deploy/` — deployment bridge/jobs.
- `server_modules/ui/` — HTTP handlers.
- `agents/pipeline/build_pipeline.py` — direct standalone pipeline entrypoint.

## Product surfaces

- `srs-agent/` — SRS interview, knowledge and diagrams.
- `deployment-agent/` — provider planning, onboarding and deployment.
- `studio/` — Next.js Studio.
- `desktop/` — Electron shell and process ownership.

## Rules

1. Put new code in the narrowest matching package.
2. Import the real implementation directly; do not add compatibility-only re-export files.
3. Keep one responsibility per module: `agents/` modules stay at or below roughly 400 lines, and no source file should pass 1000.
4. Preserve the Builder contract during refactors.
5. Prefer deterministic/source/browser evidence over speculative LLM repair.
6. Keep retry attempts separate from final QA result accounting.
7. Validate import/runtime behavior after structural changes, not just syntax.
8. Root build outputs are ignored as `/build/`; `agents/build/` is source and must remain tracked.
