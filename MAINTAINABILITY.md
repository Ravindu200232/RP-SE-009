# RP-SE-009 maintenance map

The repository follows the actual pipeline so a maintainer can find behavior without chasing compatibility wrappers.

## Build pipeline

- `agents/planning/` — requirement interpretation, architecture and planning.
- `agents/build/` — project generation and baseline validation.
- `agents/analysis/` — analyzer, reproducer and evidence-backed repair.
- `agents/features/` — feature/edit/capture/image helpers.
- `agents/data/` — MongoDB lifecycle and data helpers.
- `agents/core/` — shared command, model, export and workspace tools.
- `agents/server/` — server-side build/edit orchestration.

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
- `pipeline.py` + `agents/server/pipeline/` — direct standalone pipeline entrypoint.

## Product surfaces

- `srs-agent/` — SRS interview, knowledge and diagrams.
- `deployment-agent/` — provider planning, onboarding and deployment.
- `studio/` — Next.js Studio.
- `desktop/` — Electron shell and process ownership.

## Rules

1. Put new code in the narrowest matching package.
2. Import the real implementation directly; do not add compatibility-only re-export files.
3. Keep source files below 1000 lines where practical.
4. Preserve the Builder contract during refactors.
5. Prefer deterministic/source/browser evidence over speculative LLM repair.
6. Keep retry attempts separate from final QA result accounting.
7. Validate import/runtime behavior after structural changes, not just syntax.
8. Root build outputs are ignored as `/build/`; `agents/build/` is source and must remain tracked.
