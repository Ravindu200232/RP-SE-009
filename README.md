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
- An agentic builder: a ReAct loop with native tool calling, which plans,
  chooses a design system, writes the application and proves it works. There is
  no approval gate and no hard-coded build pipeline; the destructive-command
  denylist still holds in every case.
- Two application stacks: Next.js + MongoDB, and MERN behind one API gateway.
- Verified starting points, so a build begins at the part that differs rather
  than at twenty boilerplate files written from memory.
- Vitest unit-test authoring, run for real and measured from the runner's own
  coverage report.
- End-to-end journeys in an isolated direct-CDP browser, scored per stage —
  for example `10/12 = 83%` — with unreached stages recorded as unreached.
- A verification ledger that refuses to let a run report completion on a claim
  rather than on evidence, surfaced in the Studio's Testing → Evidence view.
- Runtime, security and deployment verification.
- Point-and-edit: click an element or draw on the page and the agent edits the
  source that renders it.
- A chat stream beside the preview: the build as a conversation, and the place
  to ask for the next change.
- Vercel and AWS deployment onboarding.
- Electron shell that owns the Python backend and Studio processes.

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
├── builder-agent/builder_agent/
│   ├── loop.py                  the ReAct engine
│   ├── agent.py                 one build: plan -> design -> build -> verify
│   ├── evidence.py              the verification ledger
│   ├── browser.py, journeys.py  isolated direct-CDP browser and E2E journeys
│   ├── tools/                   files, search, terminal, verification, browser
│   ├── assets/                  bundled skills and verified stack templates
│   └── cli.py                   builder-agent run | plan | review | chat
├── qa-agent/qa_agent/
│   ├── harness.py               makes the runner work before authoring
│   ├── unit.py, e2e.py          the two suites, at the deep profile
│   ├── security.py              six static checks
│   └── report.py                the Studio record and the PDF
├── server_modules/
│   ├── core/                    process/runtime lifecycle
│   ├── services/                MongoDB, cancellation, images, pickers
│   ├── builder/                 studio bridge: pipeline, edits, media, QA
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

## Verification model

Building runs at one quality profile. The deep profile is spent where it pays:
the unit and end-to-end suites, which are the evidence anyone actually reads.

### The ledger

A run declares what it must prove before it writes tests, and the scope is
sealed so it cannot be narrowed once a flow turns out to be hard. Every suite
then names the requirement ids it covers. A final answer is refused while a
required layer has no current passing evidence: "I have finished" is a claim,
and only the ledger closes the gate. Anything genuinely unprovable is recorded
as a limitation, which is never a pass.

A pass taken before the last edit is marked *outdated* rather than discarded:
voiding everything on every keystroke is how a repair loop stops converging.
The finished article is re-verified once, at the revision it is finished at.

### Unit tests

Counts come from Vitest's own assertion rows, and coverage from the runner's
`coverage-summary.json`. A suite that exits 0 below the coverage floor is a
failure. Repair stops when the same failures repeat with nothing changed in
between.

### E2E tests

Journeys run in the engine's isolated direct-CDP browser: no test framework is
generated into the project in order to verify it. Every journey ends with a
diagnostics check, so a page that renders while throwing in the console or
answering 500 fails. Failures are classified by owner - a wrong locator, a
missing control, or broken production behaviour - which is what makes repair
converge. Browser execution records every declared stage as `pass`, `fail` or
`not_reached`.

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
python -m compileall -q builder-agent/builder_agent qa-agent/qa_agent server_modules server.py server_runtime.py srs-agent/srs_agent deployment-agent/deploy_agent
python test/run_suite.py
python studio/scripts/verify_ui_contract.py
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

Generated projects, Node modules, Python caches, logs and packaging outputs are ignored.

Keep implementation files focused and below 1000 lines where practical. New code belongs in the narrowest pipeline package and should use direct imports rather than compatibility façade modules.
