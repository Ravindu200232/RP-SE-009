# AgentForge Studio — Agentic SRS Generator

Turn a raw, non-technical software idea into a **complete IEEE-830 Software
Requirements Specification** — structured JSON, a professional PDF report,
rendered diagrams, functional/non-functional requirements, ambiguities, risk &
priority, and a full traceability matrix — and then **edit it by prompt**
("add a payment gateway", "make performance stricter", "rename booking-service
to reservation-service").

Built with **Next.js 15 + TypeScript + Tailwind** (web), **FastAPI + LangGraph**
(API), **MongoDB** (persistence), and **Ollama** (local LLM, `nemotron-3-super:cloud`).

> **Runs even with nothing installed but Python + Node.** If Ollama or MongoDB
> aren't reachable, the app automatically falls back to a deterministic,
> domain-aware generator and an in-memory store, so you always get a valid,
> domain-specific SRS. Wire up Ollama + Mongo for full LLM enrichment and
> persistence.

---

## Table of contents
1. [Architecture](#architecture)
2. [What it produces](#what-it-produces)
3. [Prerequisites](#prerequisites)
4. [Pull the Ollama models](#pull-the-ollama-models)
5. [Quick start (local, no Docker)](#quick-start-local-no-docker)
6. [Run with Docker Compose](#run-with-docker-compose)
7. [Using the app](#using-the-app)
8. [API reference](#api-reference)
9. [Tests](#tests)
10. [Optional dependencies](#optional-dependencies)
11. [Troubleshooting](#troubleshooting)
12. [Project layout](#project-layout)
13. [Samples are templates only](#samples-are-templates-only)

---

## Architecture

```
apps/
  web/        Next.js 15 App Router UI (intake → analyzing → questions → analyzer)
  api/        FastAPI + LangGraph agents, Ollama adapter, Mongo, PDF/diagram generators
packages/
  shared/     TypeScript types/contracts shared by the web app
samples/      Example SRS files (used as few-shot quality references only)
generated/    Per-project artifacts: srs JSON, diagrams (.mmd/.svg/.png), PDF
```

**Agentic workflow (LangGraph)** — eight agent nodes across three graphs:

| Agent | Role |
|-------|------|
| IntakeExtractorAgent | Normalises idea + PDF/OCR/voice text, detects language, **guards against nonsense input** |
| DomainClassifierAgent | Detects domain (hotel/retail/school/clinic/vehicle/…), app type, confidence; estimates complexity & stack |
| QuestionPlannerAgent | Generates 5–20 plain-language questions based on missing coverage |
| CoverageAuditorAgent | Scores SRS coverage, asks follow-ups only for missing critical areas |
| SrsJsonGeneratorAgent | Builds a domain-specific SRS; LLM-enriches it through a **schema-validated JSON repair loop** |
| DiagramGeneratorAgent | Builds Mermaid sources for 7 diagram types and renders SVG/PNG |
| SrsPdfGeneratorAgent | Renders the professional IEEE-830 PDF (cover, TOC, sections 1–9, embedded diagrams) |
| CustomizationAgent | Applies prompt edits, preserves unrelated sections, keeps version history |

The **Ollama adapter** tries the primary model, then the fallback model, validates
output against the Pydantic SRS schema, and on validation errors feeds them back
to the model and retries (up to 3×). If the server is unreachable, agents fall
back to the deterministic generator.

---

## What it produces

For each project, under `generated/{projectId}/`:

- `srs_v1.0.0.json`, `srs_latest.json` — the full SRS JSON (root key `srs_document`).
- `diagrams/*.mmd` + `*.svg` + `*.png` — Use Case, Activity, Sequence, ERD,
  System Context, Component, Deployment.
- `SRS_v1.0.0.pdf` — the IEEE-830 report (StayEase-style).

---

## Prerequisites

- **Python 3.11+** (3.13 tested)
- **Node.js 18.18+** (20+ recommended)
- *Optional:* **Ollama** (local LLM), **MongoDB** (persistence),
  **mermaid-cli** (`mmdc`) for SVG/PNG diagram rendering, **Docker** (compose).

---

## Configure the LLM (Ollama)

The LLM is used to **generate the requirement questions, the domain-specific
SRS content, and the diagrams**. Default configuration (`.env`):

```
OLLAMA_PRIMARY_MODEL=nemotron-3-super:cloud
OLLAMA_FALLBACK_MODEL=nemotron-3-super:cloud
```

```bash
ollama pull nemotron-3-super:cloud
ollama serve                      # usually already running on :11434
```

You can point these at any model you have (`ollama list`), local or a cloud
`*:cloud` model after `ollama signin`.

> ⚠️ **Name gotcha:** the model is **gemma** (e) not **gamma** (a). Run
> `ollama list` and set `OLLAMA_PRIMARY_MODEL` to a tag you actually have. A
> one-letter mismatch silently falls back to the deterministic generator.

The adapter tries the **primary** model, then the **fallback** model, validating
output against the schema and retrying with the validation errors (≤3×). If
neither model is reachable, agents fall back to the deterministic generator, so
**the app always works** — wire up the LLM for unique questions and richer,
idea-specific SRS + diagrams.

---

## Quick start (local, no Docker)

```bash
cp .env.example .env            # adjust model names if needed

# 1) Backend
cd apps/api
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
pip install -r requirements-extract.txt   # optional: PDF/OCR/voice extraction
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs  (interactive API)  ·  /health (status)

# 2) Frontend (new terminal, from repo root)
npm install
npm run dev --workspace apps/web
# → http://localhost:3000
```

The web app proxies `/api/*` to the backend (see `apps/web/next.config.mjs`), so
no CORS setup is needed for local dev.

---

## Run with Docker Compose

```bash
cp .env.example .env
docker compose up --build
# web → http://localhost:3000   api → http://localhost:8000   mongo → :27017
```

The API container reaches a **host-installed Ollama** at
`host.docker.internal:11434` (configurable via `OLLAMA_BASE_URL`).

---

## Using the app

1. **New Project** — describe your idea (e.g. *"A hotel booking platform…"*).
   Optionally attach a **PDF/image** or record **voice**.
2. **Analyzing** — Agent 1 reads the idea, detects the domain, and plans questions.
   Nonsense input (e.g. `asdasdas`) is caught and you're asked basic questions
   instead of getting a fake SRS.
3. **Requirement Gathering** — answer simple multiple-choice / free-text questions.
4. **Analyzer dashboard** — tabs for **SRS Document, Functional Req., JSON Output,
   Diagrams, Ambiguities, Risk & Priority**; a right **inspector** with counts,
   complexity, stack, domain; a bottom **console** (Live Logs / Agent Events /
   Terminal / Prompt Trace / Errors).
5. **Customize via prompt** — type edits in the left sidebar (or click a
   suggestion). The SRS, diagrams, RTM, and version bump regenerate; previous
   versions are preserved.
6. **Download** — JSON or the generated **SRS PDF**; **Approve** to lock it.

### Uploading the provided sample SRS files
The samples in `samples/` are **few-shot quality references** for the generator,
not data to import. To *see one rendered*, you can paste its idea or upload the
StayEase PDF on the intake screen — the PDF text is extracted and merged into the
brief.

### Generating the SRS PDF
Click **Download SRS PDF** (top bar or inspector), or
`GET /projects/{id}/download/pdf`. Diagrams embed as images when `mmdc` is
installed; otherwise the Mermaid source is included and the UI renders diagrams
live in the browser.

---

## API reference

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/projects` | Create a project from an idea |
| GET | `/projects` | List projects |
| GET | `/projects/{id}` | Project detail + latest SRS + versions |
| POST | `/projects/{id}/inputs` | Add text / **PDF / image / voice** (multipart) |
| POST | `/projects/{id}/analyze` | Run intake + domain + question planning |
| GET | `/projects/{id}/questions` | Current question set |
| POST | `/projects/{id}/answers` | Submit answers (updates coverage) |
| POST | `/projects/{id}/generate-srs` | Generate SRS + diagrams (v1.0.0) |
| GET | `/projects/{id}/srs-json` | Full SRS JSON |
| GET | `/projects/{id}/requirements` | FRs + NFRs |
| GET | `/projects/{id}/diagrams` | Diagram artifacts (Mermaid source) |
| GET | `/projects/{id}/ambiguities` | Ambiguities + assumptions |
| GET | `/projects/{id}/risks` | Risk & priority |
| POST | `/projects/{id}/customize` | Prompt-based edit (bumps version) |
| POST | `/projects/{id}/approve` | Mark approved |
| GET | `/projects/{id}/download/json` | Download SRS JSON |
| GET | `/projects/{id}/download/pdf` | Download SRS PDF |
| GET | `/projects/{id}/events` · `/events/stream` | Event history · **SSE live logs** |

---

## Tests

```bash
cd apps/api
.venv/Scripts/activate
pip install -r requirements.txt -r requirements-extract.txt
pytest -q
```

Covers: text idea → project; **nonsense → clarification (no fake SRS)**; dynamic
question count; coverage updates; **schema-valid SRS**; **hotel→rooms/bookings,
retail→products/inventory/POS, school→students/fees/transport, clinic→patients**;
**customize preserves data + version history**; stricter-performance & rename
edits; 7 diagrams generated; **PDF built**; inspector summary matches counts; and
the full HTTP flow via `TestClient`.

---

## Optional dependencies

| Feature | Install | Without it |
|---------|---------|------------|
| PDF text extraction | `pip install pdfplumber pypdf` | Upload returns a setup note |
| Image OCR | `pip install pytesseract pillow` + Tesseract binary (or `easyocr`) | OCR returns a setup note |
| Voice transcription | `pip install faster-whisper` | Audio stored; warning shown (no fake transcript) |
| Diagram SVG/PNG render | `npm i -g @mermaid-js/mermaid-cli` | `.mmd` saved; UI renders Mermaid live; PDF embeds source |
| Persistence | Run MongoDB | In-memory store (data lost on restart) |
| LLM enrichment | Run Ollama + pull models | Deterministic domain generator |

---

## Troubleshooting

- **`/health` shows `ollama.available: false`** — Ollama isn't running or the
  model name is wrong. Run `ollama list` and set `OLLAMA_PRIMARY_MODEL` to a tag
  you actually have. The app keeps working offline regardless.
- **Diagrams show source text instead of images in the PDF** — install
  `@mermaid-js/mermaid-cli` (`mmdc`) and regenerate. The web UI always renders
  diagrams live.
- **Mongo errors on startup** — ignored by default (`MONGODB_ALLOW_MEMORY_FALLBACK=true`).
  Set it to `false` to require Mongo.
- **LLM returns invalid JSON** — the repair loop retries 3× with the validation
  errors; if it still fails, the deterministic SRS is kept and the issue is
  logged to the **Errors** console tab.
- **Voice upload "not configured"** — install a local speech model
  (`pip install faster-whisper`); the `FasterWhisperAdapter` activates automatically.
- **Windows + WeasyPrint** — not used; the PDF engine is **ReportLab** (pure
  Python), so no GTK/Cairo system libraries are required.

---

## Project layout

```
apps/api/app/
  agents/        intake, domain_classifier, question_planner, coverage_auditor,
                 srs_generator, diagram_generator, pdf_generator, customization
  graph/         LangGraph assembly (analysis / generation / customization)
  knowledge/     domain library + deterministic offline SRS composer
  llm/           Ollama adapter + JSON repair
  extraction/    pdf / ocr / speech / brief
  generators/    diagrams (Mermaid) + pdf (ReportLab)
  routers/       FastAPI endpoints
  services/      orchestrator, event bus (SSE), storage
  schemas/       Pydantic SRS / project / question models
apps/web/
  app/           intake (/), projects, analyzing, questions, analyzer
  components/    header, ui/*, analyzer/* (sidebar, inspector, console-bar, tabs)
  lib/           api client, SSE hook, utils
```

---

## Samples are templates only

The files in `samples/` (AutoHub, EduSphere, GrandVista, MegaMart, StayEase) are
used **only** as structural/quality references and as the basis of the domain
knowledge library's depth. **No hotel/retail/school/vehicle data is hard-coded
into the generated output.** The domain is detected per-idea, and the generated
tables, modules, roles, workflows, and requirements are composed from the
detected domain + your answers + (optionally) the LLM. Change the idea and the
entire SRS changes accordingly.
