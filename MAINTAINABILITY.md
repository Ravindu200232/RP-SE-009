# AgentForge maintenance map

The repository follows the actual pipeline so a maintainer can find behaviour
without chasing compatibility wrappers.

## The four agents

Each agent is an ordinary importable Python package in its own directory. None
of them is executed into the server's shared namespace, so each one works from
the CLI, from a test, and from the other agents.

- `srs-agent/srs_agent/` — interview, requirements, diagrams, SRS documents.
- `builder-agent/builder_agent/` — the engine, and the builder agent that plans,
  designs, builds and verifies one application.
- `qa-agent/qa_agent/` — the QA agent: unit and end-to-end suites at the deep
  verification profile, plus the record the Studio renders.
- `deployment-agent/deploy_agent/` — provider planning, onboarding, deployment.

## The builder engine

`builder-agent/builder_agent/` is a ReAct loop with native tool calling — a
port of AgentX. There is no interaction mode and no approval gate: a studio
build is unattended, so the engine plans, designs, builds and verifies in one
pass, and `policy.py` still refuses destructive commands in every case.

- `loop.py` — the engine. Context frame, tool execution, repair guards, and the
  completion gate that refuses a final answer without evidence.
- `agent.py` — one build: plan → design → build → verify.
- `config.py` — the builder stacks, and the two quality profiles. Building runs
  at the default profile; the deep profile belongs to the unit and E2E suites.
- `evidence.py` — the verification ledger. Exit status and journey outcomes,
  never a model's claim that something passed.
- `memory.py` / `compactor.py` / `context.py` — conversation memory, eviction,
  checkpoints and the token budget.
- `llm.py` — the Ollama transport (local and cloud), plus the router the loop
  talks to.
- `prompts.py`, `skills.py`, `templates.py`, `design.py`, `knowledge.py` —
  what a build starts from: the contract, the guidance, the scaffold, the
  design system, and what earlier runs proved.
- `browser.py` / `journeys.py` — the isolated direct-CDP browser and the
  declarative journeys that produce E2E evidence.
- `tools/` — the tool set: files, search, terminal, verification, browser,
  skills, plan.
- `assets/skills/`, `assets/templates/` — the bundled skills and the verified
  starting points for each stack.
- `cli.py` — `builder-agent run | plan | review | chat | models`.

## The QA agent

- `harness.py` — makes the runner work before anything is authored.
- `unit.py` — authoring, running and repairing the unit suite; counts come from
  Vitest's own report.
- `e2e.py` — journeys, scored per stage, with unreached stages recorded as
  unreached rather than failed.
- `security.py` — six static checks a generator actually gets wrong.
- `report.py` — the record the Studio reads, and the printable PDF.

## Runtime

- `server.py` — stable backend entrypoint.
- `server_runtime.py` — ordered shared-runtime assembler.
- `server_modules/core/` — startup and process lifecycle.
- `server_modules/services/` — importable shared services: MongoDB,
  cancellation, images, and the pencil/select pickers.
- `server_modules/builder/` — the studio bridge: pipeline, point-and-edit,
  media, projects, QA read-back, and the event translator.
- `server_modules/srs/`, `server_modules/deploy/` — the other agents' bridges.
- `server_modules/ui/` — HTTP handlers.

## Product surfaces

- `studio/` — Next.js Studio. The chat stream beside the preview is
  `components/AgentChat.jsx`; the verification ledger is
  `components/testing/Evidence.jsx`.
- `desktop/` — Electron shell and process ownership.

## Rules

1. Put new code in the narrowest matching package.
2. Import the real implementation directly; do not add compatibility-only
   re-export files.
3. Keep source files below 1000 lines where practical.
4. Preserve the builder contract during refactors: the stack is product-owned,
   never a model decision.
5. Prefer deterministic source, command and browser evidence over speculative
   LLM repair.
6. Never let a model's claim close a verification gate. The ledger closes it.
7. An agent is a library; only the server's own glue belongs in
   `_RUNTIME_PARTS`.
8. Validate import and runtime behaviour after structural changes, not just
   syntax.
