# AI Web Builder

A **local, no-cloud** AI app builder. Describe an app in plain language and it
generates a complete **Next.js 15 + MongoDB** project — powered entirely by a
local **Ollama + Gemma** model. No Claude/OpenAI keys, nothing leaves your machine
except the database calls to your own MongoDB Atlas cluster.

> Inspired by tools like bolt.diy, but built from scratch, local-first, and
> focused on one stack: Next.js App Router + Mongoose.

## Features

- 💬 Streaming chat with a local **gemma4:12b** model via Ollama.
- 🏗️ Generates a full, runnable Next.js + TypeScript + Tailwind + MongoDB project.
- 📁 Live file tree + code viewer as the app is built.
- 💾 Chat history & projects persisted in MongoDB.
- 📦 One-click **Export ZIP** (with a ready `.env.local`) or run straight from `workspace/<id>`.

## Prerequisites

1. **Node.js 18.18+** (you have v24).
2. **Ollama** running locally with the model pulled:
   ```bash
   ollama pull gemma4:12b
   ollama serve   # usually already running on http://127.0.0.1:11434
   ```
3. A **MongoDB** connection string (Atlas or local).

## Setup

```bash
pnpm install
# configure .env.local (already created for you):
#   MONGODB_URI, MONGODB_URI_TEMPLATE, OLLAMA_BASE_URL, OLLAMA_MODEL
pnpm dev
```

Open http://localhost:3000

## Configuration (`.env.local`)

| Variable                | Purpose                                                        |
| ----------------------- | -------------------------------------------------------------- |
| `MONGODB_URI`           | The builder's own DB (chat history + project metadata).        |
| `MONGODB_URI_TEMPLATE`  | Injected into every generated app. `{{DB_NAME}}` is replaced.  |
| `OLLAMA_BASE_URL`       | Ollama server (use `127.0.0.1`, not `localhost`, on Windows).  |
| `OLLAMA_MODEL`          | Model tag, e.g. `gemma4:12b`.                                   |
| `OLLAMA_NUM_CTX`        | Context window for generation.                                 |
| `WORKSPACE_DIR`         | Where generated projects are written (default `./workspace`).  |

## How a generated app uses MongoDB

The model is instructed to read `process.env.MONGODB_URI` only. At generation
time a `.env.local` is written into `workspace/<id>/` (and into the exported ZIP)
pointing at your cluster with a per-app database name. So:

```bash
cd workspace/<project-id>
npm install
npm run dev
```

…just works, with the database live.

> The in-app preview shows the generated **code**. To see the running app with a
> live database, run it locally as above (a normal Node process can open the
> MongoDB TCP connection that a browser sandbox cannot).

## Project layout

```
app/            builder UI (page) + API routes (chat, projects, status, export)
components/     chat panel, workbench (file tree + code viewer)
lib/llm/        Ollama streaming client + the code-generation system prompt
lib/artifact/   parser that turns model output into files
lib/workspace/  writes generated projects to disk + env injection
lib/db/         Mongoose connection + Project/Message models
workspace/      generated projects (git-ignored)
```
