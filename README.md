# Code Developer Agent

AI-powered MERN stack microservice generator using **Ollama + DeepSeek**.

Upload an SRS (Software Requirements Specification) JSON → AI agents plan, generate, analyze, fix, and run a complete MERN microservice application.

## Architecture

```
code-developer-agent/
├── agent-service/     ← Express + Socket.IO + MongoDB (port 5000)
│   └── src/
│       ├── services/
│       │   ├── ollamaService.js          # Ollama API + streaming + history
│       │   ├── plannerAgent.js           # SRS → project plan (JSON)
│       │   ├── developerAgent.js         # plan → MERN code
│       │   ├── analyzerAgent.js          # code review + auto-fix
│       │   ├── fileWriterService.js      # write files to disk
│       │   ├── appRunnerService.js       # npm install + npm start
│       │   └── generationOrchestrator.js # main pipeline
│       ├── models/
│       │   ├── Generation.js             # job state + files
│       │   └── Message.js                # AI conversation history
│       └── routes/
│           ├── generate.js               # POST /api/generate
│           └── history.js                # GET /api/history
├── frontend/          ← Next.js 14 UI (port 3000)
├── generated-apps/    ← Generated apps land here
├── start.bat          ← Windows start script
└── start.sh           ← Linux/Mac start script
```

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Node.js | >= 18 | https://nodejs.org |
| MongoDB | >= 6 | https://www.mongodb.com |
| Ollama | latest | https://ollama.ai |

## Quick Start (Windows)

```bat
# 1. Double-click start.bat  OR:
cd code-developer-agent
start.bat
```

## Quick Start (Linux/Mac)

```bash
chmod +x start.sh
./start.sh
```

## Manual Start

```bash
# Terminal 1 — Start Ollama
ollama serve

# Pull model (one time)
ollama pull deepseek-v3.1:671b-cloud

# Terminal 2 — Start MongoDB
mongod --dbpath /data/db

# Terminal 3 — Start Agent Service
cd agent-service
npm install
npm start

# Terminal 4 — Start Frontend
cd frontend
npm install
npm run build
npm start
```

## URLs

| Service | URL |
|---------|-----|
| UI (SRS upload) | http://localhost:3000 |
| Agent API | http://localhost:5000 |
| Generated App Gateway | http://localhost:8080 |
| Generated Frontend | http://localhost:3001 |

## SRS JSON Format

```json
{
  "projectName": "task-manager",
  "description": "A simple task management application",
  "features": [
    "User authentication (register/login)",
    "Create, read, update, delete tasks",
    "Task status tracking (todo, in-progress, done)",
    "Task priority levels"
  ],
  "techStack": "MERN Stack Microservices",
  "database": "MongoDB"
}
```

## How it Works

1. **Planner Agent** — Analyzes SRS → JSON plan with services, routes, models
2. **Developer Agent** — Generates complete code for each microservice + Next.js frontend + API Gateway
3. **File Writer** — Writes all files to `generated-apps/{jobId}/`
4. **Analyzer Agent** — Reviews all code for bugs, missing imports → applies fixes
5. **Runner** — `npm install` + `npm start` for each service
6. **Gateway** — Single URL (`:8080`) proxies all services and frontend
7. **History** — All AI conversations saved to MongoDB for error-fixing context

## API Endpoints

```
POST /api/generate              # Start generation (body: { srs: {...} })
GET  /api/generate/:jobId       # Get job status + URLs
GET  /api/generate/:jobId/files # List generated files
GET  /api/generate/:jobId/file  # Get file content (?filePath=...)
GET  /api/history               # List all past jobs
GET  /api/history/:jobId/messages # AI conversation history
GET  /api/history/:jobId/logs   # Execution logs
```

## Environment Variables (agent-service/.env)

```env
PORT=5000
MONGODB_URI=mongodb://localhost:27017/code-developer-agent
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-v3.1:671b-cloud
GENERATED_APPS_DIR=../generated-apps
GATEWAY_PORT=8080
BASE_SERVICE_PORT=8001
```
