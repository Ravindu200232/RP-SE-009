# AgentForge

A studio for taking a product from a sentence to a deployed application:
interview → plan → specification → design → prototype → build → test → deploy.

The interface is the AgentForge Studio, copied unchanged from `RP-SE-009`. The
engine underneath it is this repository's own Ollama terminal agent. Nothing in
between is hard-coded: every stage is a prompt pack on disk, and the only things
that say "no" to a model are the validation rules ported from `RP-SE-009`.

## Running it

```powershell
./studio.bat
```

That starts the backend and the studio together and prints where to open it. The
first run installs the studio's npm packages. To run beside another instance:

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

Requirements: Python 3.10+, Node 20+, and Ollama. Pick a model in the studio's
settings before starting a project — the backend does not choose one for you.

## One context, five agents

The five agents — **SRS**, **prototype**, **builder**, **QA** and **deploy** —
are not five conversations. They are five roles taking turns in one, against one
workspace, with one model:

```
workspaces/<project>/           the application being built
  .agentforge/
    context.json                THE conversation, all five agents share it
    events.jsonl                what the studio's chat stream replays
    interview.json  plan.json  design.json
    srs/        srs.json, SRS.md, diagrams/*.mmd, handoff/{app,builder}.md, handoff.json
    wireframe/  app/   a React app: src/pages/<page>.tsx for every screen, and bundle.html
    prototype/  app/   the wireframe app, edited into the prototype; routes.json, demo-accounts.json
    skills/     web-artifacts-builder   Anthropic's skill, staged for the agent to read
    build/      report.json
    qa/         report.json
    deploy/     run.json, events.jsonl
```

What the SRS agent learned in the interview is still in front of the builder;
what the builder did is still in front of the deployer. Agents do not re-read
their way back to a shared understanding — they never lost it. They read a file
when they need an exact value, not to re-learn something they were told.

`context.json` is written after every turn, so closing the app does not lose the
conversation. When the window fills, the engine summarises the oldest turns into
a running memory; if the model returns nothing for a summary, a mechanical
digest of the paths, commands and requests is kept instead. A thin memory is
survivable; losing the session is not.

Each stage runs **silent plan mode**: the agent plans the work and immediately
carries it out, because the studio approved the stage by starting it. What it
leaves behind is files. A message typed into the chat stream afterwards edits
those same files through `write_file` and `replace_text`.

## Wireframes and prototype: one React app, edited

Neither is hand-drawn HTML. Both are a small **React** app (TypeScript, Vite, Tailwind CSS, shadcn/ui, Lucide icons, Recharts) that
the project's agent writes with its own file tools, following Anthropic's official
[`web-artifacts-builder`](https://github.com/anthropics/skills/tree/main/skills/web-artifacts-builder) skill, which is kept unchanged in
`prompts/skills/web-artifacts-builder/` and staged where the agent can read it.

The handoff the agent works from is two files in `.agentforge/srs/handoff/`: a small **`app.md`**, which is what the customer asked
for in their own words, who uses it and the site map, with nothing technical in it; and the developer's **`builder.md`**, the full
specification, which the build, the tests and the deployment read.

- **Wireframes**: the agent reads the skill and `app.md` and writes `src/pages/<page>.tsx` for every screen of the site map, in
  low fidelity. The Studio only creates the app (the skill's first step: `server_modules/web_app.py`, from `server_modules/web_kit/`) and,
  when the agent is done, bundles it with Vite into one self-contained `bundle.html` (the skill's last step), which the Wireframe tab frames.
- **Prototype**: a new app is set up, and the agent reads the skill, the approved wireframes (every page and what it imports),
  `app.md` and the approved design, plans the prototype, and writes a high-fidelity, animated page for every screen. The wireframes stay
  as they were. When the product has sign-in, the prototype signs in with one fictitious account for each role (`src/demo.ts`), the same
  accounts the build is seeded with (`demo-accounts.json`). A screen with no page leaves the run resumable instead of handed over.
- The packages (about 180 MB) are installed once into `<state>/web-kit` and linked into every app as `node_modules`; Node.js is the only
  thing a computer needs. An app that does not bundle is given to the agent, with what the bundler said, to fix.

## Scaffold-first build and evidence

After prototype approval, the builder installs the selected stack's template —
Next.js, Vite or Remix on Supabase; Next.js, Vite, Remix or MERN on MongoDB alone (no Supabase
account needed); or those MongoDB stacks with a Supabase Storage bucket for uploaded files — from `builder-agent/builder_agent/assets/templates/` into an
empty project workspace.
It never overwrites an existing application. Before it plans, the builder's
model may ask the customer what it cannot settle itself - a decision with no safe
default, or a value only they have - in its own words and only when it is really
needed. Once the plan starts the build never stops to ask: it runs straight
through on the project's connected database and records whatever it could not
settle as a gap in the build report. The stack and testing guides in `_guides/` and the
authentication guide (`prompts/shared/authentication.md`) are staged under
`.agentforge/build/guides/` and passed into the build plan along with the SRS
handoff, approved design customization and prototype. The build records its
installed files in `.agentforge/build/scaffold.json`.

QA uses the copied Vitest, Playwright, axe and Lighthouse configuration and the
ZAP CI example. It saves runner JSON and actual screenshots under the project;
the Studio's **Testing → Scaffold QA** view reads those artifacts. Unavailable
tools, missing routes and incomplete requirements are reported as gaps, not
counted as passing tests.

## Everything is a prompt

`prompts/` holds every instruction this product gives a model. Changing how a
stage behaves is editing a file:

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
