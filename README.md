# RP-SE-009: Self-Optimizing AI-Agentic Full-Stack Development Application

An academic software engineering project developed at the **Sri Lanka Institute of Information Technology (SLIIT)**. RP-SE-009 provides an integrated workflow that turns a software requirement into a structured SRS, an implementation plan, a generated full-stack application, verified test evidence, repair iterations, and a deployment-ready release.

## Project scope

The Version 2 application integrates four specialist subsystems behind a shared desktop and backend runtime:

- **SRS Agent V2** — requirement intake, clarification, structured specifications, diagrams, and the approved builder handoff.
- **AI Code Developer Agent V2** — architecture planning, full-stack generation, feature updates, analysis, and evidence-scoped repair.
- **QA Agent Backend** — unit, runtime/API, end-to-end, security, and verification workflows.
- **Deployment Agent** — environment validation, provider onboarding, release generation, monitoring, and Vercel/AWS deployment support.

The application keeps each subsystem modular while using a single orchestration layer, shared project state, and one Studio interface.

## Architecture

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         Desktop Application                          │
│                 Electron Shell + Next.js Studio UI                  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTP / WebSocket events
┌───────────────────────────────▼──────────────────────────────────────┐
│                    Application Runtime and API                       │
│ server.py → server_runtime.py → server_modules/{core,srs,deploy,ui} │
└──────────────┬────────────────┬─────────────────┬────────────────────┘
               │                │                 │
┌──────────────▼───────┐ ┌──────▼──────────┐ ┌────▼───────────────────┐
│ SRS and Planning     │ │ Code Development │ │ Quality Assurance      │
│ requirement intake  │ │ architecture      │ │ unit/runtime/API tests │
│ clarification       │ │ code generation   │ │ E2E and security       │
│ diagrams and SRS    │ │ analysis + repair │ │ evidence and reports   │
└──────────────┬───────┘ └──────┬───────────┘ └────┬───────────────────┘
               └────────────────┴──────────────┬────┘
                                               │ accepted build
                                    ┌──────────▼───────────┐
                                    │ Deployment Agent     │
                                    │ validation, release, │
                                    │ Vercel/AWS, monitor  │
                                    └──────────────────────┘
```

### End-to-end workflow

```text
Requirement
   → SRS interview, analysis, diagrams, and approval
   → architecture and implementation contract
   → Next.js/MongoDB full-stack generation
   → unit → runtime/API → E2E → security verification
   → evidence-based repair loop when a gate fails
   → preview and accepted build
   → Vercel or AWS deployment and monitoring
```

The repair loop uses observed source, runtime, browser, and test evidence. A failed gate returns a narrow repair request to the owning stage; accepted results continue to the next gate. Test retries remain separate from the final accepted QA result.

## Repository structure

```text
RP-SE-009/
├── server.py                       stable backend entrypoint
├── server_runtime.py               ordered shared-runtime composition
├── agents/
│   ├── planner/                    request planning and application building
│   │   ├── planning/               requirement interpretation, routes, sitemap
│   │   ├── builder/                approved-plan generation and file writing
│   │   └── templates/              auth and runtime scaffolding defaults
│   ├── pipeline/                   standalone pipeline and feature safety
│   │   ├── build/                  fix loop, runtime/test gates, preview
│   │   └── bugs/                   bug request, workflow, and verification
│   ├── build/                      baseline route and browser validation
│   ├── analysis/                   diagnosis and repair
│   │   ├── checks/                 auth, code, data, and route scans
│   │   ├── repair/                 bug fixing, repair runner, semantic audit
│   │   └── runtime/                runtime probes and browser reproduction
│   ├── features/                   feature and edit workflows
│   │   ├── planning/               request and evidence scoping
│   │   └── runtime/                feature updates, images, pencil, selection
│   ├── data/                       database lifecycle and record helpers
│   ├── core/                       shared model, command, and workspace tools
│   │   ├── llm/                    client, settings, and model catalog
│   │   ├── workspace/              file, dependency, and source tools
│   │   ├── imports/                import reading and rule checks
│   │   ├── syntax/                 syntax and React DOM prop checks
│   │   ├── runtime/                command execution and cancellation
│   │   ├── nextjs/                 Next.js docs and dev tools
│   │   ├── docs/                   documentation index
│   │   └── learning/               build lessons
│   └── server/                     Studio project files and WebSocket jobs
├── srs-agent/                      SRS service, knowledge, and diagrams
├── qa_agent/
│   ├── unit/                       unit-test authoring and execution
│   ├── e2e/                        browser journeys and evidence
│   ├── verification/               API, security, and PDF reports
│   ├── core/                       QA session state
│   └── server/                     backend QA stages
├── deployment-agent/               deployment planning and execution
├── server_modules/
│   ├── core/                       process and job lifecycle
│   ├── srs/                        SRS runtime bridge and API
│   ├── deploy/                     deployment runtime bridge and jobs
│   └── ui/                         HTTP handlers
├── studio/                         Next.js user interface
├── desktop/                        Electron process and window lifecycle
├── test/                           unit and integration regression suite
├── document/                       system documentation artifacts
└── production-ready/               generated applications (gitignored)
```

The V2 layout uses direct imports to the package that owns each behavior. Old flat compatibility modules are not retained when the same implementation has moved into a focused package. Each agent area is split into subpackages so that a single concern stays readable in one file: every module under `agents/` is roughly 400 lines or fewer.

## Technology stack

- Python 3.11+ backend and agent services
- Next.js 16, React 19, and Tailwind CSS 4 Studio
- Electron desktop runtime
- MongoDB for generated applications that require persistence
- Vitest unit testing and Playwright end-to-end testing
- Ollama-compatible local or configured remote model endpoint
- Vercel and AWS deployment integrations

## Setup

### Windows

```text
setup.bat
start.bat
```

### macOS or Linux

```bash
chmod +x setup.sh start.command
./setup.sh
./start.command
```

For backend-only development:

```bash
python server.py
```

The Studio runs at `http://localhost:3000/__agentforge`. Backend services use ports `7824`, `7825`, and `7826`; the deployment sidecar uses `7834` when enabled.

## Development validation

Run the repository regression suite:

```bash
python test/run_suite.py
```

Check the SRS evaluation dataset and render its coverage report:

```bash
python -m test.eval.validate
python -m test.eval.report
```

The suite asserts that the code behaves; the dataset in [`test/eval/`](test/eval/)
asserts that the *document the SRS agent writes* holds the properties a customer
brief implies. It carries 471 briefs over 14 claims — intake guards, scope
discipline, a 57-cell domain x archetype matrix at four scales, and 13 output
languages from 6 input scripts. See
[`test/eval/README.md`](test/eval/README.md) and the generated
[`test/eval/results/coverage.md`](test/eval/results/coverage.md).

Run the main static and contract checks:

```bash
python -m compileall -q agents qa_agent server_modules server.py server_runtime.py srs-agent/srs_agent deployment-agent/deploy_agent
python studio/scripts/verify_ui_contract.py
node studio/scripts/verify_activity.mjs
node studio/scripts/verify_progress.mjs
node studio/scripts/verify_test_counts.mjs
node studio/scripts/verify_uploads.mjs
node --check desktop/main.js
node --check desktop/runtime.js
node --check desktop/preload.js
python deployment-agent/verify_aws_session_contract.py
```

For a production Studio build:

```bash
npm --prefix studio ci --no-audit --no-fund
npm --prefix studio run build
```

Interactive deployment sign-in and a complete generated-application browser run require the relevant local accounts, credentials, services, and database.

## Academic context

- **Project ID:** RP-SE-009
- **Project title:** Self-Optimizing AI-Agentic Full-Stack Development Application
- **Institution:** Sri Lanka Institute of Information Technology (SLIIT)

This repository is maintained as a campus software engineering project. See [LICENSE](LICENSE) for the permitted academic and non-commercial use terms.
