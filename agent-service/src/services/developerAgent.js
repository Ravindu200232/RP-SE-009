const bugStoreService = require('./bugStoreService');
const patternLoader = require('./patternLoader');
const { OllamaTimeoutError } = require('./ollamaService');

/**
 * DeveloperAgent — Generates code following the established team template pattern.
 *
 * TEMPLATE PATTERN (from MICROSERVICE_PATTERN_README.md):
 *  Backend:  ES modules, Server.js, DbConnection.js, SEKRET_KEY, MONGO_URL, Swagger
 *  Frontend: Vite + React + Tailwind v3 PostCSS, BrowserRouter, route groups, localStorage JWT
 *
 * Phase 1: package.json ONLY → npm install with exact packages
 * Phase 2: All source files (Server.js, DbConnection.js, routes, models, controllers, .env)
 */

// ── System Prompts ─────────────────────────────────────────────────────────

const PACKAGE_JSON_SYSTEM = `You are a Node.js package expert. Generate ONLY a package.json file.
Respond with ONLY the raw JSON — no markdown, no explanation, no code blocks.
The JSON must be valid and parseable by JSON.parse().

REQUIRED PACKAGE.JSON STRUCTURE:
{
  "name": "service-name",
  "version": "1.0.0",
  "type": "module",
  "main": "Server.js",
  "scripts": {
    "start": "nodemon Server.js",
    "test": "jest",
    "test:coverage": "jest --coverage"
  },
  "dependencies": { ... all required packages ... },
  "devDependencies": { "nodemon": "^3.0.1" }
}

CRITICAL: "type": "module" is REQUIRED — this enables ES module import/export syntax.
CRITICAL: main must be "Server.js" — NOT index.js.
CRITICAL: start script must be "nodemon Server.js".

ABSOLUTELY FORBIDDEN — these will cause EJSONPARSE and break npm:
  ✗ HTML comments: <!-- anything -->
  ✗ XML tags: <tag>
  ✗ JS comments: // or /* */
  ✗ Markdown: ** or ##
  ✗ Trailing commas after last item
  ✗ Single quotes (use double quotes only)
  ✗ Unquoted keys

JSON ONLY. If in doubt, output nothing but valid JSON.`;

// ── Backend Template Pattern ──────────────────────────────────────────────

const EXPRESS_SOURCE_SYSTEM = `You are an expert Node.js/Express developer. You MUST follow this EXACT template pattern.

═══════════════════════════════════════════════
CRITICAL ARCHITECTURE RULES — NO EXCEPTIONS:
═══════════════════════════════════════════════

[1] ES MODULES ONLY — use import/export (NEVER require/module.exports)
    ✓ import express from "express"
    ✗ const express = require("express")

[2] ENTRY POINT: Server.js (NEVER index.js or src/index.js)
    ✓ File path: Server.js
    ✗ File path: src/index.js

[3] DB CONNECTION: DbConnection.js pattern
    ✓ import { connectToDatabase } from "./DbConnection.js"
    ✓ export function connectToDatabase() { mongoose.connect(process.env.MONGO_URL) }

[4] ENV VARIABLE NAMES (exact names required):
    ✓ MONGO_URL=mongodb://localhost:27017/dbname
    ✓ SEKRET_KEY=your_shared_secret
    ✗ MONGODB_URI (wrong name)
    ✗ JWT_SECRET (wrong name)

[5] SERVER.JS REQUIRED STRUCTURE (copy this order exactly):
    import express from "express"
    import bodyParser from "body-parser"
    import dotenv from "dotenv"
    import helmet from "helmet"
    import rateLimit from "express-rate-limit"
    import swaggerJsdoc from "swagger-jsdoc"
    import swaggerUi from "swagger-ui-express"
    import jwt from "jsonwebtoken"
    import cors from "cors"
    import { connectToDatabase } from "./DbConnection.js"
    --- all your route imports ---

    dotenv.config()
    const app = express()

    // Helmet (security headers)
    app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false, crossOriginOpenerPolicy: false, hsts: false }))

    // CORS
    app.use(cors())

    // Body parser
    app.use(bodyParser.json())

    // Rate limiter
    app.use(rateLimit({ windowMs: 15 * 60 * 1000, max: 100, standardHeaders: true, legacyHeaders: false }))

    // JWT decode middleware (non-blocking — never reject, just decode)
    app.use((req, res, next) => {
      let token = req.header("Authorization")
      if (token) {
        token = token.replace("Bearer ", "")
        jwt.verify(token, process.env.SEKRET_KEY, (err, decode) => {
          if (!err) req.user = decode
        })
      }
      next()
    })

    // Swagger
    const swaggerSpec = swaggerJsdoc({ definition: { openapi: "3.0.0", info: { title: "Service API", version: "1.0.0" }, servers: [{ url: process.env.SERVER_URL || \`http://localhost:\${process.env.PORT}\` }], components: { securitySchemes: { bearerAuth: { type: "http", scheme: "bearer", bearerFormat: "JWT" } } } }, apis: ["./routes/*.js"] })
    app.use("/api-docs", swaggerUi.serve, swaggerUi.setup(swaggerSpec))
    app.get("/api-docs.json", (req, res) => res.json(swaggerSpec))

    // Connect DB
    connectToDatabase()

    // Health check
    app.get("/health", (req, res) => res.json({ status: "healthy", service: "name", timestamp: new Date().toISOString() }))

    // Mount routes
    app.use("/api/v1/resource", resourceRouter)

    const PORT = process.env.PORT || 3001
    app.listen(PORT, () => console.log(\`Service running on port \${PORT}\`))

[6] DbConnection.js EXACT PATTERN:
    import mongoose from "mongoose"
    import dotenv from "dotenv"
    dotenv.config()

    export function connectToDatabase() {
      const mongoUrl = process.env.MONGO_URL
      mongoose.connect(mongoUrl)
      const connection = mongoose.connection
      connection.once("open", () => {
        console.log("MongoDB database connection established successfully")
      })
    }

[7] ROLE HELPERS — always create controllers/authController.js:
    export function checkHasAccount(req) { return !!req.user }
    export function checkAdmin(req) { return req.user?.role === "admin" }
    export function checkCustomer(req) { return req.user?.role === "customer" }
    export function checkRestaurant(req) { return req.user?.role === "restaurant" }
    export function checkDelivery(req) { return req.user?.role === "delivery" }

[8] CONTROLLER PATTERN (always with auth check + try/catch):
    import { checkHasAccount, checkAdmin } from "./authController.js"
    import Item from "../models/Item.js"

    export async function getItems(req, res) {
      try {
        if (!checkHasAccount(req)) return res.status(401).json({ message: "Please login" })
        const items = await Item.find()
        return res.json(items)
      } catch (error) {
        return res.status(500).json({ message: "Internal server error" })
      }
    }

[9] MONGOOSE MODEL PATTERN:
    import mongoose from "mongoose"
    const schema = new mongoose.Schema({ ... }, { timestamps: true })
    export default mongoose.model("Name", schema)

[10] ROUTE PATTERN:
    import express from "express"
    import { getItems, createItem } from "../controllers/itemController.js"
    const router = express.Router()
    router.get("/", getItems)
    router.post("/", createItem)
    export default router

[11] .env EXACT FORMAT:
    MONGO_URL=mongodb://localhost:27017/{projectname}
    SEKRET_KEY=shared_secret_key_change_in_production
    PORT={port}
    SERVER_URL=http://localhost:{port}
    NODE_ENV=development

[12] INTER-SERVICE CALLS use axios + env URL:
    const otherServiceUrl = process.env.OTHER_SERVICE_URL || "http://localhost:3002"
    await axios.put(\`\${otherServiceUrl}/api/v1/resource/\${id}\`, data)

[13] JWT LOGIN pattern (in user-service or driver-service):
    import jwt from "jsonwebtoken"
    const token = jwt.sign({ id: user._id, email: user.email, role: user.role }, process.env.SEKRET_KEY)
    return res.json({ token, user })

[14] FILE EXTENSION: Always include .js in all ES module imports
    ✓ import Item from "../models/Item.js"
    ✗ import Item from "../models/Item"

[15] PASSWORD HASHING — always use bcryptjs (NOT bcrypt):
    import bcryptjs from "bcryptjs"
    const hashed = await bcryptjs.hash(password, 10)
    const valid = await bcryptjs.compare(password, user.passwordHash)
    REASON: bcrypt requires native compilation and FAILS on Windows (ENOENT spawn npm)
    bcryptjs is pure JavaScript and works everywhere without compilation

FILE FORMAT — use EXACTLY for every file:
===FILE: relative/path/to/file.ext===
[COMPLETE file content — never truncate, never use // ... or placeholder comments]
===END===`;

// ── Frontend Template Pattern ─────────────────────────────────────────────

const VITE_SOURCE_SYSTEM = `You are an expert React developer following the established frontend template pattern.

═══════════════════════════════════════════════
FRONTEND ARCHITECTURE RULES:
═══════════════════════════════════════════════

⚠️  ABSOLUTE PROHIBITIONS — THESE PATTERNS ARE BANNED:
    ✗ NEVER use <Outlet /> from react-router-dom — BANNED completely
    ✗ NEVER nest <Route> inside another <Route> with children (no nested route tree)
    ✗ NEVER import Outlet from react-router-dom
    ✗ NEVER use index.html — it's managed by Vite automatically
    ✗ NEVER use @import "tailwindcss" — that's v4 syntax, wrong for this project

✅ CORRECT ROUTE PATTERN — each page group owns its own <Routes>:
    // App.jsx — only top-level route groups, NO nesting
    <BrowserRouter>
      <Routes>
        <Route path="/*" element={<HomePage />} />
        <Route path="admin/*" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>

    // pages/home/HomePage.jsx — owns its own nested <Routes>
    import { Routes, Route } from "react-router-dom"
    <div>
      <Header />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
      </Routes>
    </div>

    // pages/admin/AdminPage.jsx — owns its own nested <Routes>
    import { Routes, Route, Navigate } from "react-router-dom"
    <div className="flex h-screen">
      <Sidebar />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
        </Routes>
      </main>
    </div>

[1] TAILWIND CSS v3 PostCSS (already installed by runner):
    - tailwind.config.js + postcss.config.js are already created
    - src/index.css uses: @tailwind base; @tailwind components; @tailwind utilities;
    - DO NOT write @import "tailwindcss" (that's v4 only)
    - DO NOT add tailwindcss to vite.config.js plugins (it's PostCSS, not Vite plugin)

[2] APP.JSX PATTERN — BrowserRouter wraps everything:
    import { BrowserRouter, Routes, Route } from "react-router-dom"
    import { Toaster } from "react-hot-toast"
    import HomePage from "./pages/home/HomePage"
    import AdminPage from "./pages/admin/AdminPage"

    function App() {
      return (
        <BrowserRouter>
          <Toaster position="top-right" />
          <Routes>
            <Route path="/*" element={<HomePage />} />
            <Route path="admin/*" element={<AdminPage />} />
          </Routes>
        </BrowserRouter>
      )
    }
    export default App

[3] ROUTE GROUP PATTERN — each group owns its nested routes:
    // pages/home/HomePage.jsx
    import { Routes, Route } from "react-router-dom"
    import Header from "../../components/header"
    function HomePage() {
      return (
        <>
          <Header />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/*" element={<NotFound />} />
          </Routes>
        </>
      )
    }
    export default HomePage

[4] AUTH STORAGE in localStorage:
    localStorage.setItem("token", res.data.token)
    localStorage.setItem("user", JSON.stringify(res.data.user))
    const token = localStorage.getItem("token")

[5] API CALL PATTERN — axios + env URL + JWT:
    const token = localStorage.getItem("token")
    const res = await axios.get(
      \`\${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users\`,
      { headers: { Authorization: \`Bearer \${token}\` } }
    )

[6] .ENV PATTERN — BASE URLs only (no path, no trailing slash):
    VITE_USER_SERVICE_URL=http://localhost:3001
    VITE_TASK_SERVICE_URL=http://localhost:3002
    ✗ WRONG: VITE_USER_SERVICE_URL=http://localhost:3001/api/v1/users
    ✓ RIGHT: VITE_USER_SERVICE_URL=http://localhost:3001
    Then in API calls: \`\${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users\`

[7] PROTECTED ROUTE PATTERN:
    const [token] = useState(localStorage.getItem("token"))
    if (!token) { window.location.href = "/login"; return null }

[8] UI DESIGN RULES:
    - Import Outfit + Cormorant Garamond fonts (Google Fonts in index.html)
    - Gold CTA buttons: className="bg-yellow-500 text-gray-900 font-semibold px-6 py-3 rounded-lg hover:bg-gray-900 hover:text-yellow-500 transition-all uppercase tracking-wide"
    - Blue CRUD buttons: className="bg-blue-500 text-white font-semibold py-2 px-4 rounded-lg hover:bg-blue-600 transition"
    - Red destructive: className="bg-red-500 text-white font-semibold py-2 px-4 rounded-lg hover:bg-red-600 transition"
    - White card: className="bg-white rounded-xl shadow-md p-5 border border-gray-200"
    - Dashboard background: className="bg-gray-100 min-h-screen"
    - Sidebar layout: className="flex h-screen overflow-hidden" > aside.w-64.bg-white.shadow-md + main.flex-1.overflow-y-auto

[9] SIDEBAR DASHBOARD PATTERN:
    <div className="flex h-screen overflow-hidden">
      <aside className="fixed md:static z-40 top-0 left-0 h-full w-64 bg-white shadow-md transform transition-transform">
        <div className="p-4 font-bold text-lg border-b">Admin Panel</div>
        <nav>...</nav>
        <button onClick={() => { localStorage.clear(); navigate("/login") }}>Logout</button>
      </aside>
      <main className="flex-1 p-4 bg-gray-100 overflow-y-auto">
        <Routes>...</Routes>
      </main>
    </div>

[10] FORM PAGE PATTERN:
    const [formData, setFormData] = useState({ field: "" })
    async function handleSubmit(e) {
      e.preventDefault()
      try {
        const token = localStorage.getItem("token")
        await axios.post(\`\${import.meta.env.VITE_SERVICE_URL}/api/v1/resource\`, formData, {
          headers: { Authorization: \`Bearer \${token}\` }
        })
        toast.success("Saved!")
        navigate(-1)
      } catch (err) {
        toast.error(err.response?.data?.message || "Error occurred")
      }
    }

[11] HERO SECTION (public pages) — elegant editorial style:
    Background image + dark overlay + Cormorant Garamond heading + gold CTA
    className for heading: "text-5xl md:text-7xl font-bold" style={{ fontFamily: "Cormorant Garamond, serif" }}
    Eyebrow text: className="uppercase tracking-widest text-yellow-500 text-sm font-medium mb-4"

FILE FORMAT — use EXACTLY for every file:
===FILE: relative/path/to/file.ext===
[COMPLETE file content — never truncate]
===END===`;

// ── DeveloperAgent Class ──────────────────────────────────────────────────

class DeveloperAgent {
  constructor(ollamaService, io) {
    this.ollama = ollamaService;
    this.io = io;
  }

  /**
   * PHASE 1: Generate package.json only for a backend service.
   * Returns parsed JSON object (ES module style).
   */
  async generatePackageJson(jobId, service, plan, onToken, context = {}) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Developer',
      message: `[AI] Generating package.json for ${service.name}...`
    });
    this.io.to(jobId).emit('log', {
      level: 'prompt',
      agent: 'AI Prompt',
      message: `Asking AI: Generate package.json for ${service.name}\n→ type: "module", main: "Server.js", start: "nodemon Server.js"\n→ deps: ${(service.dependencies || []).join(', ')}`,
      timestamp: new Date().toISOString()
    });

    const prompt = `Generate a package.json for a Node.js/Express microservice:

Name: ${service.name}
Port: ${service.port}
Required dependencies: ${(service.dependencies || [
  'express', 'mongoose', 'cors', 'dotenv', 'helmet',
  'express-rate-limit', 'body-parser', 'jsonwebtoken', 'bcrypt',
  'axios', 'swagger-jsdoc', 'swagger-ui-express', 'nodemon'
]).join(', ')}

Compacted project context:
${context.compactedContext?.developerPrompt || 'No additional compacted context.'}

CRITICAL REQUIREMENTS:
- "type": "module" (ES modules — REQUIRED)
- "main": "Server.js" (entry point — NOT index.js)
- scripts.start = "nodemon Server.js"
- scripts.dev = "nodemon Server.js"
- scripts.test = "jest"

Respond with ONLY valid JSON. No markdown. No explanation.`;

    const response = await this.ollama.generate(jobId, prompt, PACKAGE_JSON_SYSTEM, 'developer', `pkg_${service.name}`, onToken);

    try {
      // ★ CRITICAL FIX: Strip ALL non-JSON content before parsing.
      // AI sometimes injects <!-- HTML comments --> inside JSON strings which causes EJSONPARSE.
      let clean = response
        .replace(/```json\n?|```\n?/g, '')     // strip markdown fences
        .replace(/<!--[\s\S]*?-->/g, '')        // strip HTML comments (<!-- ... -->)
        .replace(/\/\/[^\n]*/g, '')             // strip JS single-line comments
        .replace(/\/\*[\s\S]*?\*\//g, '')       // strip JS multi-line comments
        .trim();
      const start = clean.indexOf('{');
      const end = clean.lastIndexOf('}') + 1;
      const parsed = JSON.parse(clean.slice(start, end));

      // Enforce the template pattern — no exceptions
      parsed.type = 'module';
      parsed.main = 'Server.js';
      parsed.scripts = parsed.scripts || {};
      parsed.scripts.start = 'nodemon Server.js';
      parsed.scripts.dev = 'nodemon Server.js';
      parsed.scripts.test = parsed.scripts.test || 'jest';

      // Enforce required deps — versions use "*" (npm install will pick latest)
      parsed.dependencies = parsed.dependencies || {};
      const required = [
        'express', 'mongoose', 'cors', 'dotenv', 'helmet',
        'express-rate-limit', 'body-parser', 'jsonwebtoken',
        'bcryptjs', 'axios', 'swagger-jsdoc', 'swagger-ui-express'
      ];
      for (const dep of required) {
        if (!parsed.dependencies[dep]) parsed.dependencies[dep] = '*';
      }
      // Always use bcryptjs (pure JS — bcrypt requires native compilation and breaks on Windows)
      delete parsed.dependencies.bcrypt;
      // nodemon goes in devDependencies
      parsed.devDependencies = parsed.devDependencies || {};
      if (!parsed.devDependencies.nodemon) parsed.devDependencies.nodemon = '*';

      return parsed;
    } catch (e) {
      // Fallback with all template deps — versions "*" so npm picks latest
      return {
        name: service.name,
        version: '1.0.0',
        type: 'module',
        main: 'Server.js',
        scripts: { start: 'nodemon Server.js', dev: 'nodemon Server.js', test: 'jest' },
        dependencies: {
          express: '*', mongoose: '*', cors: '*', dotenv: '*', helmet: '*',
          'express-rate-limit': '*', 'body-parser': '*', jsonwebtoken: '*',
          bcryptjs: '*', axios: '*', 'swagger-jsdoc': '*', 'swagger-ui-express': '*'
        },
        devDependencies: { nodemon: '*' }
      };
    }
  }

  /**
   * PHASE 2: Generate all source files for a backend service.
   * Returns [{path, content, service}] — ES module style, Server.js entry.
   */
  async generateSourceFiles(jobId, service, plan, onToken, context = {}) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Developer',
      message: `[AI] Generating source code for ${service.name}...`
    });

    const [preventionPrompt, backendPattern] = await Promise.all([
      bugStoreService.buildPreventionPrompt(),
      patternLoader.backendPatternPrompt()
    ]);
    const systemPrompt = EXPRESS_SOURCE_SYSTEM + backendPattern + preventionPrompt;

    const requiredFiles = Array.isArray(service.requiredFiles) && service.requiredFiles.length > 0
      ? service.requiredFiles
      : [
        'Server.js',
        'DbConnection.js',
        '.env.example',
        'controllers/authController.js'
      ];

    // Build inter-service env vars
    const interServiceEnv = (service.interServiceCalls || [])
      .map(dep => {
        const depSvc = plan.services.find(s => s.name === dep);
        if (!depSvc) return '';
        const envKey = dep.replace(/-service$/, '').replace(/-/g, '_').toUpperCase() + '_SERVICE_URL';
        return `${envKey}=http://localhost:${depSvc.port}`;
      })
      .filter(Boolean)
      .join('\n');

    this.io.to(jobId).emit('log', {
      level: 'prompt',
      agent: 'AI Prompt',
      message: `Asking AI: Generate complete ES module source for ${service.name}\n→ Entry: Server.js, DB: DbConnection.js\n→ ${service.routes?.length || 0} routes, ${service.models?.length || 0} models\n→ Auth: SEKRET_KEY, DB: MONGO_URL`,
      timestamp: new Date().toISOString()
    });

    const mongoUrl = plan.sharedEnv?.MONGO_URL || `mongodb://localhost:27017/${plan.projectName || 'myapp'}`;

    const prompt = `Generate ALL source files for this Express microservice using ES MODULE syntax.

Service: ${service.name}
Port: ${service.port}
Description: ${service.description}

Routes:
${(service.routes || []).map(r => `  ${r.method} ${r.path} — ${r.description}`).join('\n')}

MongoDB Models:
${JSON.stringify(service.models || [], null, 2)}

Inter-service dependencies: ${(service.interServiceCalls || []).join(', ') || 'none'}

Compacted project context:
${context.compactedContext?.developerPrompt || 'No additional compacted context.'}

CANONICAL FILE MANIFEST (generate EXACTLY these paths, do not invent alternate names):
${requiredFiles.map((file, index) => `${index + 1}. ${file}`).join('\n')}

RULES FOR THE FILE MANIFEST:
- Every file path above is mandatory.
- Use the exact file names from the manifest, including `.controller.js`, `.service.js`, `.model.js`, and `.routes.js`.
- If you want a second alias file, only add it after all manifest files are present.
- Never rename manifest files to Task.js, taskRoutes.js, userService.js, userController.js, or similar alternates unless the manifest explicitly says so.

REQUIRED CONTENT GUIDANCE:
- Server.js: Express server with helmet, cors, body-parser or express.json, rate-limit, JWT middleware, Swagger, routes mounted
- DbConnection.js: export function connectToDatabase() using MONGO_URL
- controllers/authController.js: checkHasAccount, checkAdmin, checkCustomer, checkRestaurant, checkDelivery helpers
- models/*.js: Mongoose models with ES module default export
- routes/*.js: route files with ES module default router
- controllers/*.js: business logic with try/catch + auth checks
- services/*.js: business logic layer importing models, not routes
- .env.example: MONGO_URL, SEKRET_KEY, PORT, SERVER_URL, NODE_ENV${interServiceEnv ? ', ' + interServiceEnv.split('\n').map(e => e.split('=')[0]).join(', ') : ''}

.env.example content:
MONGO_URL=${mongoUrl}
SEKRET_KEY=${plan.sharedEnv?.SEKRET_KEY || 'shared_secret_key_change_in_production'}
PORT=${service.port}
SERVER_URL=http://localhost:${service.port}
NODE_ENV=development${interServiceEnv ? '\n' + interServiceEnv : ''}

REMEMBER:
- import/export NOT require/module.exports
- Server.js NOT index.js
- MONGO_URL NOT MONGODB_URI
- SEKRET_KEY NOT JWT_SECRET
- All imports must include .js extension
- Route -> Controller -> Service -> Model

Use ===FILE: path === ===END=== format for EVERY file.`;

    let response;
    try {
      response = await this.ollama.generate(jobId, prompt, systemPrompt, 'developer', `src_${service.name}`, onToken);
    } catch (err) {
      if (err instanceof OllamaTimeoutError && err.partialResponse) {
        // ── Timeout continuation: save partial files, ask AI to continue ─────
        const partialFiles = this.extractFiles(err.partialResponse, service.name);

        this.io.to(jobId).emit('log', {
          level: 'warning',
          agent: 'Developer',
          message: `⚠️ Generation timed out for ${service.name} — saved ${partialFiles.length} partial files. Asking AI to continue...`,
          timestamp: new Date().toISOString()
        });

        if (partialFiles.length > 0) {
          const continuedFiles = await this._continueGeneration(
            jobId, service, plan, systemPrompt, partialFiles, onToken
          );
          // Merge: partial files + continuation (continuation wins on conflicts)
          return this._mergeFiles(partialFiles, continuedFiles);
        }
        throw err; // no partial files extracted at all — rethrow
      }
      throw err;
    }

    return this.extractFiles(response, service.name);
  }

  /**
   * Continuation prompt: given already-generated files, ask AI for the remaining ones.
   * This is the "save and continue" pattern for handling generation timeouts.
   */
  async _continueGeneration(jobId, service, plan, systemPrompt, alreadyGeneratedFiles, onToken) {
    const alreadyDone = alreadyGeneratedFiles.map(f => f.path).join('\n  ');

    // What files are we still missing?
    const requiredFiles = Array.isArray(service.requiredFiles) && service.requiredFiles.length > 0
      ? service.requiredFiles.filter(file => file !== 'package.json')
      : [
        'Server.js',
        'DbConnection.js',
        '.env.example',
        'controllers/authController.js'
      ];

    const missing = requiredFiles.filter(req => !alreadyGeneratedFiles.find(f =>
      f.path.endsWith(req) || f.path === req
    ));

    const continuationPrompt = `CONTINUATION — you were generating source files for ${service.name} but were cut off.

You already generated these files (do NOT regenerate them):
  ${alreadyDone}

Please generate ONLY the remaining files:
  ${missing.length > 0 ? missing.join('\n  ') : 'Any files not listed above'}

Service: ${service.name} (port ${service.port})
Routes: ${(service.routes || []).map(r => `${r.method} ${r.path}`).join(', ')}
Models: ${(service.models || []).map(m => m.name).join(', ')}

Use ===FILE: path=== [complete content] ===END=== for every file.
Respect these exact target file names:
  ${requiredFiles.join('\n  ')}
DO NOT repeat already-generated files. ONLY continue with the missing ones.`;

    this.io.to(jobId).emit('log', {
      level: 'info',
      agent: 'Developer',
      message: `Continuing generation for ${service.name}: requesting ${missing.length} remaining files...`,
      timestamp: new Date().toISOString()
    });

    try {
      const continuationResponse = await this.ollama.generate(
        jobId, continuationPrompt, systemPrompt, 'developer', `src_${service.name}_cont`, onToken
      );
      return this.extractFiles(continuationResponse, service.name);
    } catch (contErr) {
      if (contErr instanceof OllamaTimeoutError && contErr.partialResponse) {
        // Even the continuation timed out — extract whatever we got
        return this.extractFiles(contErr.partialResponse, service.name);
      }
      return []; // continuation failed — return empty, use only partial files
    }
  }

  /**
   * Merge two file arrays. newFiles wins on path conflicts.
   */
  _mergeFiles(existingFiles, newFiles) {
    const map = new Map(existingFiles.map(f => [f.path, f]));
    for (const f of newFiles) {
      if (f.path && f.content) map.set(f.path, f);
    }
    return Array.from(map.values());
  }

  /**
   * Generate Vite + React frontend files following the team frontend pattern.
   * Tailwind v3 PostCSS is already installed by runner before this is called.
   */
  async generateViteFrontend(jobId, plan, onToken) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Developer',
      message: '[AI] Generating React frontend source files...'
    });

    const [preventionPrompt, frontendPattern] = await Promise.all([
      bugStoreService.buildPreventionPrompt(),
      patternLoader.frontendPatternPrompt()
    ]);
    const systemPrompt = VITE_SOURCE_SYSTEM + frontendPattern + preventionPrompt;

    // Build service URL env vars — base URL only (no path suffix)
    // API calls in components will append /api/v1/{resource}
    const serviceEnvVars = (plan.services || [])
      .map(s => {
        const key = s.name.replace(/-service$/, '').replace(/-/g, '_').toUpperCase() + '_SERVICE_URL';
        return `VITE_${key}=http://localhost:${s.port}`;
      })
      .join('\n');

    // Determine route groups from pages
    const routeGroups = plan.frontend?.routeGroups || ['HomePage'];

    this.io.to(jobId).emit('log', {
      level: 'prompt',
      agent: 'AI Prompt',
      message: `Asking AI: Generate React+Vite frontend for "${plan.projectName}"\n→ Route groups: ${routeGroups.join(', ')}\n→ Pages: ${plan.frontend?.pages?.map(p => p.name).join(', ')}\n→ Tailwind v3 PostCSS pattern (NOT @tailwindcss/vite)`,
      timestamp: new Date().toISOString()
    });

    const prompt = `Generate a complete React + Vite frontend for:

Project: ${plan.projectName}
Description: ${plan.description}

Pages:
${(plan.frontend?.pages || []).map(p => `  [${p.group || 'HomePage'}] ${p.route} — ${p.name}: ${p.description}`).join('\n')}

Route Groups: ${routeGroups.join(', ')}
Components: ${(plan.frontend?.components || ['Header', 'Footer']).join(', ')}

Backend services:
${(plan.services || []).map(s => `  ${s.name}: http://localhost:${s.port} — ${s.description}`).join('\n')}

GENERATE ALL FILES — DO NOT generate index.html (Vite manages it automatically):

1. src/App.jsx — BrowserRouter + flat route groups (${routeGroups.map(g => `<Route path="${g === 'HomePage' ? '/*' : g.replace('Page', '').toLowerCase() + '/*'}" element={<${g} />} />`).join(', ')})
   ⚠️ NEVER nest <Route> inside another <Route> in App.jsx — NO OUTLET PATTERN
2. src/main.jsx — mount App into #root with ReactDOM.createRoot
3. src/index.css — ONLY: @tailwind base; @tailwind components; @tailwind utilities;
   DO NOT use @import "tailwindcss" — that is v4 syntax, wrong for this project
4. .env — service URLs:
${serviceEnvVars}
5. src/pages/home/HomePage.jsx — public route group: <Header /> + own <Routes><Route path="/" /><Route path="/login" /><Route path="/register" /></Routes>
   NO <Outlet /> — use its OWN <Routes> block
${routeGroups.filter(g => g !== 'HomePage').map(g => `6. src/pages/${g.replace('Page', '').toLowerCase()}/${g}.jsx — ${g} dashboard: <Sidebar /> + own <Routes><Route path="/" element={<Navigate to="dashboard" />} /><Route path="dashboard" element={<Dashboard />} /></Routes>\n   NO <Outlet /> — use its OWN <Routes> block`).join('\n')}
7. src/pages/home/*.jsx — all public pages (Home, Login, Register, etc.)
${routeGroups.filter(g => g !== 'HomePage').map(g => `8. src/pages/${g.replace('Page', '').toLowerCase()}/*.jsx — all ${g} sub-pages`).join('\n')}
9. src/components/header.jsx — fixed header, transparent→solid on scroll, mobile drawer
10. src/components/footer.jsx — dark footer, multi-column layout
11. src/utils/api.js — axios instance with localStorage token + interceptors

DESIGN RULES:
- Public pages: editorial, elegant, Cormorant Garamond headings, gold CTAs
- Dashboards: sidebar + white cards on gray-100 background
- All API calls use env vars: import.meta.env.VITE_SERVICE_URL
- Store token: localStorage.setItem("token", token)

Use ===FILE: relative/path === ===END=== for every file.`;

    let response;
    try {
      response = await this.ollama.generate(jobId, prompt, systemPrompt, 'developer', 'src_frontend', onToken);
    } catch (err) {
      if (err instanceof OllamaTimeoutError && err.partialResponse) {
        const partialFiles = this.extractFiles(err.partialResponse, 'frontend');

        this.io.to(jobId).emit('log', {
          level: 'warning',
          agent: 'Developer',
          message: `⚠️ Frontend generation timed out — saved ${partialFiles.length} partial files. Asking AI to continue...`,
          timestamp: new Date().toISOString()
        });

        if (partialFiles.length > 0) {
          const alreadyDone = partialFiles.map(f => f.path).join('\n  ');
          const continuationPrompt = `CONTINUATION — you were generating React frontend files but were cut off.

You already generated these files (do NOT regenerate them):
  ${alreadyDone}

Please generate ONLY the remaining frontend files for project: ${plan.projectName}
Route groups: ${(plan.frontend?.routeGroups || ['HomePage']).join(', ')}
Pages still needed: ${(plan.frontend?.pages || [])
  .filter(p => !partialFiles.find(f => f.path.includes(p.name)))
  .map(p => `${p.name} (${p.route})`)
  .join(', ')}

Use ===FILE: relative/path=== [complete content] ===END=== for every file.
DO NOT repeat already-generated files. ONLY generate missing ones.`;

          this.io.to(jobId).emit('log', {
            level: 'info',
            agent: 'Developer',
            message: `Continuing frontend generation — requesting remaining pages/components...`,
            timestamp: new Date().toISOString()
          });

          try {
            const continuationResponse = await this.ollama.generate(
              jobId, continuationPrompt, systemPrompt, 'developer', 'src_frontend_cont', onToken
            );
            const continuedFiles = this.extractFiles(continuationResponse, 'frontend');
            return this._mergeFiles(partialFiles, continuedFiles);
          } catch (contErr) {
            if (contErr instanceof OllamaTimeoutError && contErr.partialResponse) {
              const moreFiles = this.extractFiles(contErr.partialResponse, 'frontend');
              return this._mergeFiles(partialFiles, moreFiles);
            }
            return partialFiles; // return what we have
          }
        }
        throw err;
      }
      throw err;
    }

    return this.extractFiles(response, 'frontend');
  }

  /**
   * Generate the API Gateway (programmatically — no AI needed).
   * CommonJS gateway (gateway doesn't use ES modules for simplicity).
   */
  generateGateway(plan) {
    const seen = new Set();
    const routes = [];

    for (const svc of plan.services) {
      for (const route of (svc.routes || [])) {
        // Extract the API prefix (e.g., /api/v1/users)
        const parts = route.path.split('/').filter(Boolean);
        const prefix = parts.length >= 3
          ? '/' + parts.slice(0, 3).join('/')  // /api/v1/resource
          : '/' + parts.slice(0, 2).join('/'); // /api/resource
        if (!seen.has(prefix)) {
          seen.add(prefix);
          routes.push({ prefix, target: `http://localhost:${svc.port}`, service: svc.name });
        }
      }
      // Fallback prefix
      const fallback = `/api/v1/${svc.name.replace('-service', '')}`;
      if (!seen.has(fallback)) {
        seen.add(fallback);
        routes.push({ prefix: fallback, target: `http://localhost:${svc.port}`, service: svc.name });
      }
    }

    const frontendPort = plan.frontend?.port || 5173;

    const gatewayIndex = `require('dotenv').config();
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const cors = require('cors');

const app = express();
app.use(cors());

app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    gateway: true,
    routes: ${JSON.stringify(routes.map(r => ({ prefix: r.prefix, service: r.service, target: r.target })))}
  });
});

// ── Service Proxies ──────────────────────────────────────────
${routes.map(r => `
// ${r.service}
app.use('${r.prefix}', createProxyMiddleware({
  target: '${r.target}',
  changeOrigin: true,
  on: {
    error: (err, req, res) => {
      console.error('[Gateway] ${r.service} unreachable:', err.message);
      if (!res.headersSent) res.status(502).json({ error: 'Service unavailable: ${r.service}' });
    }
  }
}));`).join('\n')}

// ── Frontend Proxy ───────────────────────────────────────────
app.use('/', createProxyMiddleware({
  target: 'http://localhost:${frontendPort}',
  changeOrigin: true,
  ws: true,
  on: {
    error: (err, req, res) => {
      if (!res.headersSent) res.status(502).json({ error: 'Frontend not ready. Run: npm run dev in frontend/' });
    }
  }
}));

const PORT = process.env.GATEWAY_PORT || 8080;
app.listen(PORT, () => {
  console.log(\`Gateway running at http://localhost:\${PORT}\`);
  console.log('Proxying:');
${routes.map(r => `  console.log('  ${r.prefix} → ${r.target} (${r.service})');`).join('\n')}
  console.log(\`  / → http://localhost:${frontendPort} (frontend)\`);
});
`;

    const gatewayPkg = JSON.stringify({
      name: 'api-gateway',
      version: '1.0.0',
      scripts: { start: 'node index.js', dev: 'nodemon index.js' },
      dependencies: {
        express: '^4.18.2',
        cors: '^2.8.5',
        dotenv: '^16.3.1',
        'http-proxy-middleware': '^3.0.0',
        nodemon: '^3.0.1'
      }
    }, null, 2);

    const gatewayEnv = `GATEWAY_PORT=8080\nNODE_ENV=production\n`;

    return [
      { path: 'gateway/index.js', content: gatewayIndex, service: 'gateway' },
      { path: 'gateway/package.json', content: gatewayPkg, service: 'gateway' },
      { path: 'gateway/.env', content: gatewayEnv, service: 'gateway' }
    ];
  }

  /**
   * Parse ===FILE: path===content===END=== blocks from AI response.
   *
   * ★ ROOT CAUSE FIX for file_0.js, file_1.js naming bug:
   *   The AI sometimes uses the right format but provides meaningless names.
   *   This parser:
   *   1. Rejects paths like file_0.js, file_1.js, generated_0.js
   *   2. Infers proper paths from file content when names are bad
   *   3. Validates paths are real relative file paths
   */
  extractFiles(response, serviceName) {
    const files = [];

    // ★ LOOP FIX: Truncate response at the last clean ===END=== before parsing.
    // When the AI enters a repetition loop, it generates junk after the real files.
    // Examples of junk:
    //   "Would Would you you like like to to add add more more features..."
    //   "=== ===ENDEND======"
    // Clip at the last valid ===END=== so none of this enters extractFiles.
    let cleanResponse = response;
    const lastEnd = response.lastIndexOf('===END===');
    if (lastEnd !== -1) {
      cleanResponse = response.slice(0, lastEnd + '===END==='.length);
    }

    // Also handle malformed doubled markers like "=== ===ENDEND======"
    // Normalize them to "===END==="
    cleanResponse = cleanResponse.replace(/={3}\s*={3}ENDEND={3,}/g, '===END===');

    const pattern = /={3}FILE:\s*([^\n=]+?)\s*={3}([\s\S]*?)={3}END={3}/g;
    let match;

    while ((match = pattern.exec(cleanResponse)) !== null) {
      const rawPath = match[1].trim();
      const content = match[2].trim();
      if (!rawPath || !content) continue;

      // Reject meaningless names like file_0.js, generated_1.jsx, block_2.js
      const isBadName = /^(?:file_\d+|generated_\d+|block_\d+|code_\d+|snippet_\d+)\.[a-z]+$/i.test(
        rawPath.split('/').pop()
      );

      if (isBadName) {
        // Infer real path from file content
        const inferredPath = this._inferFilePath(content, serviceName);
        if (inferredPath) {
          files.push({ path: inferredPath, content, service: serviceName });
        }
        // Skip bad-named files if can't infer
        continue;
      }

      files.push({ path: rawPath, content, service: serviceName });
    }

    // Fallback: parse markdown code blocks and infer paths from content
    if (files.length === 0) {
      const blockPattern = /```(?:js|jsx|ts|tsx|json|css|html|env)?\n([\s\S]*?)```/g;
      let blockMatch;
      while ((blockMatch = blockPattern.exec(cleanResponse)) !== null) {
        const content = blockMatch[1].trim();
        if (content.length < 20) continue;
        const inferredPath = this._inferFilePath(content, serviceName);
        if (inferredPath && !files.find(f => f.path === inferredPath)) {
          files.push({ path: inferredPath, content, service: serviceName });
        }
      }
    }

    return files;
  }

  /**
   * Infer the correct file path from file content patterns.
   * Used when AI generates bad file names.
   */
  _inferFilePath(content, serviceName) {
    const c = content.trim();
    const isBackend = !['frontend', 'client'].includes(serviceName);

    // ── Backend patterns ──────────────────────────────────────────────────
    if (isBackend) {
      // Server.js — has express listen or import express + dotenv.config
      if ((c.includes('app.listen') || c.includes('connectToDatabase')) && c.includes('express')) {
        return 'Server.js';
      }
      // DbConnection.js
      if (c.includes('connectToDatabase') && c.includes('mongoose.connect')) {
        return 'DbConnection.js';
      }
      // authController.js helpers
      if (c.includes('checkAdmin') || c.includes('checkHasAccount')) {
        return 'controllers/authController.js';
      }
      // .env file
      if (c.includes('MONGO_URL=') || c.includes('SEKRET_KEY=') || c.includes('MONGODB_URI=')) {
        return '.env';
      }
      // package.json
      if (c.includes('"scripts"') && c.includes('"dependencies"') && c.startsWith('{')) {
        return 'package.json';
      }
      // Model files — detect by schema pattern
      const modelMatch = c.match(/mongoose\.model\(['"](\w+)['"]/);
      if (modelMatch) {
        return `models/${modelMatch[1]}.js`;
      }
      // Router files — detect by express.Router + route method
      if (c.includes('express.Router()') && (c.includes('router.get') || c.includes('router.post'))) {
        const exportMatch = c.match(/export\s+default\s+(\w+)|module\.exports\s*=\s*(\w+)/);
        if (exportMatch) {
          const routerName = (exportMatch[1] || exportMatch[2]).toLowerCase().replace('router', '');
          return `routes/${routerName}Routes.js`;
        }
        return 'routes/index.js';
      }
      // Controller files
      if (c.includes('export async function') || (c.includes('async function') && c.includes('req, res'))) {
        return 'controllers/controller.js';
      }
    }

    // ── Frontend patterns ─────────────────────────────────────────────────
    if (!isBackend) {
      // vite.config.js
      if (c.includes('defineConfig') && c.includes('vite')) {
        return 'vite.config.js';
      }
      // tailwind.config.js
      if (c.includes('tailwindcss') && c.includes('content:')) {
        return 'tailwind.config.js';
      }
      // postcss.config.js
      if (c.includes('tailwindcss') && c.includes('autoprefixer') && !c.includes('defineConfig')) {
        return 'postcss.config.js';
      }
      // index.css
      if (c.includes('@tailwind') || c.includes('@import "tailwindcss"')) {
        return 'src/index.css';
      }
      // .env
      if (c.includes('VITE_') && c.includes('=')) {
        return '.env';
      }
      // index.html
      if (c.includes('<!DOCTYPE') || c.includes('<html')) {
        return 'index.html';
      }
      // main.jsx
      if (c.includes('createRoot') || c.includes("getElementById('root')")) {
        return 'src/main.jsx';
      }
      // App.jsx
      if (c.includes('BrowserRouter') || (c.includes('function App') && c.includes('return'))) {
        return 'src/App.jsx';
      }
      // Services/api.js
      if (c.includes('axios') && c.includes('import.meta.env') && !c.includes('useState')) {
        return 'src/services/api.js';
      }
      // Components — detect by export default + component name
      const componentMatch = c.match(/(?:function|const)\s+(\w+)\s*[=(]/) ;
      if (componentMatch) {
        const name = componentMatch[1];
        if (c.includes('return (') || c.includes('return(')) {
          if (name.includes('Page') || name.includes('View')) return `src/pages/${name}.jsx`;
          if (name === 'App') return 'src/App.jsx';
          if (name === 'Main') return 'src/main.jsx';
          return `src/components/${name}.jsx`;
        }
      }
    }

    return null; // Can't infer — skip
  }
}

module.exports = DeveloperAgent;
