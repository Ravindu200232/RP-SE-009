/**
 * PlannerAgent — Analyzes the SRS JSON and creates a structured MERN microservice plan.
 *
 * Codex-style auto context compaction (srsCompactor):
 *  Layer 1 — DIRECT EXTRACTION: SRS has services[].endpoints defined → plan built in ~0ms, no Ollama call
 *  Layer 2 — COMPACT TEXT: ~600 char summary sent to Ollama (instead of 6000+ char raw JSON)
 *  Layer 3 — ULTRA-COMPACT RETRY: If Ollama still times out, retry with ~150 char summary
 *
 * Template pattern:
 *  - Backend services: ES modules, Server.js, DbConnection.js, ports 3001+
 *  - Frontend: Vite + React + Tailwind v3 PostCSS, port 5173
 *  - Gateway: port 8080
 *  - Auth: SEKRET_KEY (shared across all services)
 *  - DB: MONGO_URL (mongodb://localhost:27017/{project})
 */

const srsCompactor = require('./srsCompactor');

const SYSTEM_PROMPT = `You are an expert software architect specializing in MERN stack microservices.
Analyze an SRS document and produce a detailed project plan following THIS EXACT template pattern.

ALWAYS respond with ONLY valid JSON. No markdown, no explanation outside the JSON.

ARCHITECTURE RULES (MUST FOLLOW):
- Backend: ES modules ("type": "module"), entry Server.js, DB in DbConnection.js
- Auth env var: SEKRET_KEY (NOT JWT_SECRET)
- DB env var: MONGO_URL (NOT MONGODB_URI)
- Packages: express, mongoose, cors, dotenv, helmet, express-rate-limit, body-parser, jsonwebtoken, bcryptjs, axios, swagger-jsdoc, swagger-ui-express, nodemon
- Services start at port 3001 (NOT 8001), increment by 1 per service
- Frontend: Vite + React + Tailwind v3 PostCSS at port 5173
- Gateway: port 8080

Your response must match this schema exactly:
{
  "projectName": "string",
  "description": "string",
  "services": [
    {
      "name": "user-service",
      "description": "string",
      "port": 3001,
      "routes": [
        { "method": "POST", "path": "/api/v1/users/register", "description": "Register user" },
        { "method": "POST", "path": "/api/v1/users/login", "description": "Login, returns JWT" },
        { "method": "GET", "path": "/api/v1/users/profile", "description": "Get profile (protected)" }
      ],
      "models": [
        {
          "name": "User",
          "fields": [
            { "name": "firstName", "type": "String", "required": true },
            { "name": "lastName", "type": "String", "required": true },
            { "name": "email", "type": "String", "required": true, "unique": true },
            { "name": "password", "type": "String", "required": true },
            { "name": "role", "type": "String", "enum": ["admin", "customer"], "default": "customer" }
          ]
        }
      ],
      "dependencies": ["express", "mongoose", "cors", "dotenv", "helmet", "express-rate-limit", "body-parser", "jsonwebtoken", "bcryptjs", "axios", "swagger-jsdoc", "swagger-ui-express"],
      "interServiceCalls": []
    }
  ],
  "frontend": {
    "port": 5173,
    "pages": [
      { "name": "Home", "route": "/", "description": "Landing page", "group": "HomePage" },
      { "name": "Login", "route": "/login", "description": "Login form", "group": "HomePage" },
      { "name": "Register", "route": "/register", "description": "Register form", "group": "HomePage" },
      { "name": "AdminDashboard", "route": "/admin/dashboard", "description": "Admin panel", "group": "AdminPage" }
    ],
    "routeGroups": ["HomePage", "AdminPage"],
    "components": ["Header", "Footer", "Sidebar"],
    "serviceUrls": [
      "VITE_USER_SERVICE_URL=http://localhost:3001"
    ]
  },
  "gateway": {
    "port": 8080,
    "routes": [
      { "prefix": "/api/v1/users", "target": "http://localhost:3001", "service": "user-service" }
    ]
  },
  "sharedEnv": {
    "SEKRET_KEY": "shared_jwt_secret_key_change_me",
    "MONGO_URL": "mongodb://localhost:27017/{projectName}"
  }
}`;

class PlannerAgent {
  constructor(ollamaService, io) {
    this.ollama = ollamaService;
    this.io = io;
  }

  async plan(jobId, srs, onToken) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Planner',
      message: 'Analyzing SRS and creating microservice architecture plan...'
    });

    // ── Codex-style Auto Context Compaction ──────────────────────────────────
    const compacted = srsCompactor.compact(srs);

    this.io.to(jobId).emit('log', {
      level: 'info',
      agent: 'Planner',
      message: `SRS compacted: ${compacted.tokenEstimate} tokens (was ~${Math.ceil(JSON.stringify(srs).length / 4)} tokens)`,
      timestamp: new Date().toISOString()
    });

    // ── Layer 1: Direct extraction — no AI needed ────────────────────────────
    if (compacted.canSkipAI && compacted.directPlan) {
      this.io.to(jobId).emit('log', {
        level: 'success',
        agent: 'Planner',
        message: `✅ SRS has full service definitions — plan built directly (no AI call, no timeout possible)`,
        timestamp: new Date().toISOString()
      });
      return this._postProcess(compacted.directPlan);
    }

    // ── Layer 2: Compact text → Ollama ──────────────────────────────────────
    this.io.to(jobId).emit('log', {
      level: 'info',
      agent: 'Planner',
      message: `Sending compacted SRS (~${compacted.compact.length} chars) to AI planner...`,
      timestamp: new Date().toISOString()
    });

    try {
      const plan = await this._callOllama(jobId, compacted.compact, onToken);
      return plan;
    } catch (err) {
      const isTimeout = err.message?.includes('timeout') || err.code === 'ECONNABORTED';

      if (!isTimeout) throw err;

      // ── Layer 3: Ultra-compact retry on timeout ──────────────────────────
      this.io.to(jobId).emit('log', {
        level: 'warning',
        agent: 'Planner',
        message: `⚠️ AI planning timed out — retrying with ultra-compact SRS (~150 chars)...`,
        timestamp: new Date().toISOString()
      });

      const ultraCompact = srsCompactor.ultraCompact(srs);
      return await this._callOllama(jobId, ultraCompact, onToken);
    }
  }

  // ── Private: Call Ollama with a compact SRS string ─────────────────────────

  async _callOllama(jobId, compactSrs, onToken) {
    const prompt = `Analyze this SRS summary and create a detailed MERN microservice plan:

${compactSrs}

STRICT REQUIREMENTS:
- Each service handles ONE business domain
- user-service (or auth-service) handles auth (JWT login, register) — always include it
- Services start at port 3001, each increments by 1
- Frontend (Vite+React) at port 5173
- Gateway at port 8080
- Use SEKRET_KEY for JWT (shared across all services)
- Use MONGO_URL for MongoDB connection
- Include inter-service communication where needed (e.g., payment notifies order)
- Route paths use /api/v1/resource pattern
- All services need Swagger docs endpoint /api-docs

Respond with ONLY valid JSON. No markdown.`;

    const response = await this.ollama.generate(jobId, prompt, SYSTEM_PROMPT, 'planner', 'plan', onToken);
    return this._parsePlanResponse(response);
  }

  // ── Private: Parse and validate the AI plan JSON ───────────────────────────

  _parsePlanResponse(response) {
    try {
      const jsonMatch = response.match(/```json\s*([\s\S]*?)\s*```/) ||
                        response.match(/```\s*([\s\S]*?)\s*```/) ||
                        [null, response];
      const cleaned = (jsonMatch[1] || response).trim();
      const plan = JSON.parse(cleaned);
      return this._postProcess(plan);
    } catch {
      // Fallback: find the outermost { ... }
      const start = response.indexOf('{');
      const end = response.lastIndexOf('}') + 1;
      if (start !== -1 && end > start) {
        const plan = JSON.parse(response.slice(start, end));
        return this._postProcess(plan);
      }
      throw new Error('Planner returned invalid JSON. Response: ' + response.slice(0, 200));
    }
  }

  /**
   * Post-process the plan: enforce frontend port, resolve {projectName} placeholder,
   * ensure bcryptjs (not bcrypt) in all service dependencies.
   */
  _postProcess(plan) {
    // Always enforce frontend port 5173
    if (plan.frontend) plan.frontend.port = 5173;

    // Resolve {projectName} placeholder in MONGO_URL
    if (plan.sharedEnv?.MONGO_URL) {
      plan.sharedEnv.MONGO_URL = plan.sharedEnv.MONGO_URL
        .replace('{projectName}', plan.projectName || 'myapp')
        .replace('{project}', plan.projectName || 'myapp');
    }

    // Ensure bcryptjs (not bcrypt) in all service deps
    if (Array.isArray(plan.services)) {
      for (const svc of plan.services) {
        if (Array.isArray(svc.dependencies)) {
          const idx = svc.dependencies.indexOf('bcrypt');
          if (idx !== -1) svc.dependencies[idx] = 'bcryptjs';
          if (!svc.dependencies.includes('bcryptjs')) svc.dependencies.push('bcryptjs');
        }
      }
    }

    return plan;
  }
}

module.exports = PlannerAgent;
