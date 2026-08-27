# AgentForge

AgentForge is an agentic full-stack application builder. A requirement moves through SRS planning, architecture, Next.js generation, automated QA, repair, preview and deployment while the Studio streams the work in a desktop UI.

## Pipeline

```text
Requirement
   │
   ▼
SRS interview + diagrams
   │
   ▼
Planner / architecture contract
   │
   ▼
Builder ──► generated Next.js + MongoDB app
   │
   ▼
QA: unit → runtime/API → E2E → security
   │                 │
   └──── repair ◄────┘
   │
   ▼
Preview → Vercel / AWS deployment
```

The builder is requirement-driven rather than CRUD-specific. Apps may be authenticated or public. When authentication exists, user-owned records such as carts, bookings and history are scoped from the server session rather than trusting client-supplied user IDs. Successful mutations must also update or revalidate visible state so users do not need a manual refresh.

## Main capabilities

- SRS interview, structured requirements and rich native diagrams.
- Plan-to-code preflight before E2E testing.
- Next.js application generation with MongoDB support.
- Vitest unit-test authoring and retained whole-suite reporting.
- Playwright E2E journeys with source/DOM grounding, console/page-error evidence and repair.
- Stage-level E2E scoring, for example `10/12 = 83%`, plus an aggregate score across final accepted journeys.
- Runtime, API, security and deployment verification.
- Vercel and AWS deployment onboarding.
- Electron shell that owns the Python backend and Studio processes.
- Live Builder and SRS/Planner activity feeds with paced, latest-five updates.

## Requirements

- Python 3.11+
- Node.js 20+
- npm
- Ollama or another configured model endpoint supported by the project
- MongoDB when the generated application requires it

Deployment additionally needs the provider tools/accounts selected in the Deploy screen. AWS sign-in uses the in-app SSO/device flow where available; npm-installed Windows CLI shims such as `vercel.cmd` are launched through `COMSPEC` instead of being executed as native binaries.

## Install

### Windows

Run the one-time Windows setup, which installs the root runtime plus the SRS/deployment agent requirements and both Node applications:

```text
setup.bat
start.bat
```

`start.bat` prepares Electron when needed and opens the desktop shell. The Electron splash then starts `server.py` and the Studio, so a slow first dependency install does not look like a frozen command window.

### macOS / Linux

```bash
./setup.sh
./start.command
```

For backend-only development:

```bash
python3 server.py
```

The Studio is served through Electron at `http://localhost:3000/__agentforge`; the backend owns ports `7824`, `7825`, `7826` and the deployment sidecar on `7834` when used.

## Source map

```text
agentforge/
├── server.py                    stable backend entrypoint
├── server_runtime.py            ordered server-runtime assembler
├── pipeline.py                  direct pipeline entrypoint
├── agents/
│   ├── planning/                requirements → architecture/build plan
│   ├── build/                   generation + browser/runtime validation
│   ├── analysis/                diagnosis and evidence-backed repairs
│   ├── features/                feature/edit/image selection helpers
│   ├── data/                    MongoDB lifecycle/data helpers
│   ├── core/                    shared model, command and workspace tools
│   └── server/                  server-side builder/edit orchestration
├── qa_agent/
│   ├── unit/                    Vitest authoring, harness and execution
│   ├── e2e/                     journeys, grounding, browser and repair evidence
│   ├── verification/            API, security and PDF reporting
│   ├── core/                    QA session state
│   └── server/                  server-side QA stages
├── server_modules/
│   ├── core/                    process/runtime lifecycle
│   ├── srs/                     SRS bridge/API
│   ├── deploy/                  deployment bridge/jobs
│   └── ui/                      backend HTTP routes
├── srs-agent/                   SRS service and diagram generation
├── deployment-agent/            deployment planning/execution service
├── studio/                      Next.js desktop UI
├── desktop/                     Electron shell
└── production-ready/            generated app output (gitignored)
```

There are intentionally no compatibility-only one-line wrappers for the old flat agent paths. Internal imports point directly to the implementation package that owns the behavior.

## QA model

### Unit tests

Targeted feature updates merge their latest Vitest result into the existing suite snapshot instead of replacing unrelated results. The Overview therefore represents the current whole suite rather than only the last touched feature.

### E2E tests

Before a browser journey begins, QA compares the approved plan/requirements with the generated source and repairs evidence-backed mismatches. Browser execution then records every declared stage as `pass`, `fail` or `not_reached`.

For a 12-stage journey where stage 11 fails:

```text
10 passed / 12 total = 83%
1 failed
1 not reached
```

Repair/re-author attempts are not counted as extra tests. Only the final accepted journey ledger contributes to the overall E2E percentage. Console errors and `pageerror` stacks are captured and, when they name a generated source location, become narrow repair evidence for that source instead of triggering a broad speculative rewrite.

## Generated-app data rules

For authenticated applications, the generated server code should:

1. derive identity from the authenticated server session;
2. normalize one canonical user/owner identifier type;
3. stamp that identifier on owned writes;
4. include it in owned reads, updates and deletes;
5. return the canonical mutation result; and
6. update client state/cache or trigger route revalidation after success.

For public applications the planner must not invent authentication just to satisfy this pattern.

## Development checks

Fast repository checks used before packaging include:

```bash
python -m compileall -q agents qa_agent server_modules server.py server_runtime.py pipeline.py srs-agent/srs_agent deployment-agent/deploy_agent
python studio/scripts/verify_ui_contract.py
node studio/scripts/verify_activity.mjs
node studio/scripts/verify_progress.mjs
node studio/scripts/verify_test_counts.mjs
node studio/scripts/verify_uploads.mjs
node --check desktop/main.js
node --check desktop/runtime.js
node --check desktop/preload.js
```

A full Studio production build additionally requires its npm dependencies:

```bash
npm --prefix studio ci --no-audit --no-fund
npm --prefix studio run build
```

## Repository hygiene

Generated projects, Node modules, Python caches, logs and packaging outputs are ignored. Note that `/build/` is root-anchored in `.gitignore`: `agents/build/` is application source and must be committed.

Keep implementation files focused and below 1000 lines where practical. New code belongs in the narrowest pipeline package and should use direct imports rather than compatibility façade modules.
