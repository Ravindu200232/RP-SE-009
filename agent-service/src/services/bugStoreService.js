const BugStore = require('../models/BugStore');

/**
 * BugStoreService — The brain of the self-improving bug prevention system.
 *
 * How it works:
 *  1. SEED: On startup, seeds 30+ known MERN bug patterns
 *  2. INJECT: Before code generation, top bugs → injected into developer prompts
 *  3. LEARN: When a bug is found (by analyzer OR runtime error) → upsert into DB
 *  4. PREVENT: Next generation automatically avoids recorded bugs
 *
 * This creates a system that improves with every generation run.
 */
class BugStoreService {
  /**
   * Get top N known bugs ordered by severity + frequency.
   * Used to inject into developer system prompts.
   */
  async getPreventionRules(limit = 30) {
    const bugs = await BugStore.find({ autoFixable: true })
      .sort({ severity: -1, occurrences: -1 })
      .limit(limit)
      .select('name preventionRule badCode goodCode category severity');
    return bugs;
  }

  /**
   * Build a "NEVER DO THIS" block for injection into developer prompts.
   */
  async buildPreventionPrompt() {
    const bugs = await this.getPreventionRules(25);
    if (bugs.length === 0) return '';

    const criticalAndHigh = bugs.filter(b => b.severity === 'critical' || b.severity === 'high');
    const medium = bugs.filter(b => b.severity === 'medium');

    let prompt = '\n\n=== KNOWN BUGS — NEVER GENERATE THESE PATTERNS ===\n';
    prompt += 'These bugs have been recorded from past generations. NEVER repeat them:\n\n';

    criticalAndHigh.forEach((bug, i) => {
      prompt += `[${bug.severity.toUpperCase()}] ${bug.name}:\n`;
      prompt += `  RULE: ${bug.preventionRule}\n`;
      if (bug.badCode) prompt += `  BAD:  ${bug.badCode.slice(0, 120)}\n`;
      if (bug.goodCode) prompt += `  GOOD: ${bug.goodCode.slice(0, 120)}\n`;
      prompt += '\n';
    });

    if (medium.length > 0) {
      prompt += 'ALSO AVOID:\n';
      medium.forEach(bug => { prompt += `  - ${bug.preventionRule}\n`; });
    }

    prompt += '=== END KNOWN BUGS ===\n';
    return prompt;
  }

  /**
   * Record a bug found during generation. Upserts by patternId.
   * If same pattern seen again, increments occurrence count.
   */
  async recordBug(bugData, jobId) {
    const patternId = this._makePatternId(bugData.name || bugData.description);

    try {
      await BugStore.findOneAndUpdate(
        { patternId },
        {
          $setOnInsert: {
            patternId,
            name: bugData.name || bugData.description.slice(0, 60),
            category: bugData.category || 'other',
            description: bugData.description,
            badCode: bugData.badCode || '',
            goodCode: bugData.goodCode || '',
            preventionRule: bugData.preventionRule || bugData.description,
            affectsServices: bugData.affectsServices || ['express'],
            severity: bugData.severity || 'high',
            autoFixable: bugData.autoFixable !== false
          },
          $inc: { occurrences: 1 },
          $set: { lastSeenJobId: jobId }
        },
        { upsert: true, new: true }
      );
    } catch (err) {
      // Don't crash generation on bug store failures
      console.error('[BugStore] Failed to record bug:', err.message);
    }
  }

  /**
   * Record multiple bugs at once (from analyzer output).
   */
  async recordBugs(bugs, jobId) {
    for (const bug of bugs) {
      await this.recordBug(bug, jobId);
    }
  }

  /**
   * Parse raw analyzer issues text and extract structured bugs.
   */
  parseAnalyzerIssues(issuesText, serviceName) {
    const bugs = [];
    const lines = issuesText.split('\n').filter(l => l.trim().startsWith('-') || l.trim().startsWith('•'));

    for (const line of lines) {
      const text = line.replace(/^[-•*]\s*/, '').trim();
      if (!text || text.toLowerCase() === 'none') continue;

      const bug = {
        name: text.slice(0, 80),
        description: text,
        affectsServices: [serviceName || 'express'],
        ...this._classifyBug(text)
      };
      bugs.push(bug);
    }
    return bugs;
  }

  /**
   * Classify a bug description into a category + severity + prevention rule.
   */
  _classifyBug(description) {
    const d = description.toLowerCase();

    if (d.includes('await') && (d.includes('missing') || d.includes('without'))) {
      return { category: 'missing-await', severity: 'critical',
        preventionRule: 'Always use await before every mongoose/async operation' };
    }
    if (d.includes('cors')) {
      return { category: 'cors-error', severity: 'high',
        preventionRule: 'Add cors() middleware before all routes in Express' };
    }
    if (d.includes('dotenv') || d.includes('require(\'dotenv\')') || d.includes('.config()')) {
      return { category: 'env-not-used', severity: 'critical',
        preventionRule: 'require("dotenv").config() must be the FIRST line in index.js' };
    }
    if (d.includes('express.json') || d.includes('body parser') || d.includes('bodyparser')) {
      return { category: 'missing-middleware', severity: 'high',
        preventionRule: 'Always add app.use(express.json()) before routes' };
    }
    if (d.includes('try') && d.includes('catch') || d.includes('error handler')) {
      return { category: 'missing-error-handler', severity: 'high',
        preventionRule: 'Every route handler must have try/catch with res.status(500).json({error})' };
    }
    if (d.includes('import') || d.includes('require') || d.includes('path')) {
      return { category: 'wrong-import', severity: 'high',
        preventionRule: 'Verify all import/require paths match actual file locations' };
    }
    if (d.includes('port') && d.includes('hardcod')) {
      return { category: 'port-issue', severity: 'medium',
        preventionRule: 'Always use process.env.PORT || defaultPort, never hardcode port' };
    }
    if (d.includes('module.exports') || d.includes('export')) {
      return { category: 'missing-export', severity: 'high',
        preventionRule: 'Every module must end with module.exports = ...' };
    }
    if (d.includes('mongodb') || d.includes('mongoose.connect')) {
      return { category: 'mongodb-issue', severity: 'critical',
        preventionRule: 'Call mongoose.connect(process.env.MONGODB_URI) in db.js and import db.js in index.js' };
    }
    if (d.includes('start') && d.includes('script')) {
      return { category: 'start-script-missing', severity: 'critical',
        preventionRule: 'package.json must have "scripts": { "start": "node src/index.js" }' };
    }
    if (d.includes('jwt') || d.includes('token')) {
      return { category: 'jwt-error', severity: 'high',
        preventionRule: 'JWT_SECRET must be in .env and used via process.env.JWT_SECRET' };
    }
    if (d.includes('package.json') || d.includes('dependenc')) {
      return { category: 'dependency-missing', severity: 'high',
        preventionRule: 'All required npm packages must be listed in package.json dependencies' };
    }
    if (d.includes('use client') || d.includes('next.js') || d.includes('nextjs')) {
      return { category: 'nextjs-error', severity: 'high',
        preventionRule: 'Add "use client" directive to any Next.js component using hooks or browser APIs' };
    }
    if (d.includes('syntax') || d.includes('parse error') || d.includes('unexpected token')) {
      return { category: 'syntax-error', severity: 'critical',
        preventionRule: 'Ensure all JS/TS files have valid syntax — check brackets, commas, semicolons' };
    }

    return { category: 'other', severity: 'medium',
      preventionRule: description.slice(0, 100) };
  }

  /**
   * Seed the bug store with known common MERN bugs on first run.
   */
  async seed() {
    // Always upsert all known patterns — new ones get inserted, existing ones are skipped
    const knownBugs = [
      {
        patternId: 'missing-await-mongoose',
        name: 'Missing await on Mongoose operations',
        category: 'missing-await',
        severity: 'critical',
        description: 'Mongoose operations like find/save/create not awaited',
        badCode: 'const users = User.find({}); // returns Promise, not data',
        goodCode: 'const users = await User.find({});',
        preventionRule: 'ALWAYS use await before: .find() .findOne() .findById() .save() .create() .updateOne() .deleteOne() .aggregate()',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'dotenv-not-first',
        name: 'dotenv.config() not first line',
        category: 'env-not-used',
        severity: 'critical',
        description: 'require("dotenv").config() must be called BEFORE any other require that uses process.env',
        badCode: 'const mongoose = require("mongoose");\nrequire("dotenv").config(); // TOO LATE',
        goodCode: 'require("dotenv").config(); // FIRST LINE\nconst mongoose = require("mongoose");',
        preventionRule: 'require("dotenv").config() MUST be the absolute first line in index.js before any other require',
        affectsServices: ['express', 'nextjs'],
        occurrences: 1
      },
      {
        patternId: 'missing-express-json',
        name: 'Missing express.json() middleware',
        category: 'missing-middleware',
        severity: 'critical',
        description: 'Without express.json(), req.body is always undefined',
        badCode: 'const app = express();\napp.use("/api", router); // body will be undefined',
        goodCode: 'const app = express();\napp.use(express.json());\napp.use("/api", router);',
        preventionRule: 'Always add app.use(express.json()) AND app.use(express.urlencoded({extended:true})) before routes',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'missing-cors',
        name: 'Missing CORS middleware',
        category: 'cors-error',
        severity: 'high',
        description: 'Without cors(), frontend cannot call the API',
        badCode: 'const app = express();\napp.use("/api", router);',
        goodCode: 'const cors = require("cors");\napp.use(cors({ origin: "*" }));\napp.use("/api", router);',
        preventionRule: 'Always add app.use(cors()) before any routes. Install cors: "cors" in package.json',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'no-try-catch-route',
        name: 'Route handler without try/catch',
        category: 'missing-error-handler',
        severity: 'high',
        description: 'Unhandled promise rejections crash Express route handlers',
        badCode: 'router.get("/users", async (req, res) => {\n  const users = await User.find({});\n  res.json(users);\n});',
        goodCode: 'router.get("/users", async (req, res) => {\n  try {\n    const users = await User.find({});\n    res.json(users);\n  } catch (err) {\n    res.status(500).json({ error: err.message });\n  }\n});',
        preventionRule: 'Every async route handler MUST have try/catch. Never leave async routes without error handling',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'hardcoded-port',
        name: 'Hardcoded port number',
        category: 'port-issue',
        severity: 'medium',
        description: 'Port number hardcoded instead of from environment',
        badCode: 'app.listen(3000, () => console.log("Server running"));',
        goodCode: 'const PORT = process.env.PORT || 3000;\napp.listen(PORT, () => console.log(`Server on ${PORT}`));',
        preventionRule: 'Always use: const PORT = process.env.PORT || <default>; Never hardcode port',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'mongoose-connect-missing',
        name: 'mongoose.connect() never called',
        category: 'mongodb-issue',
        severity: 'critical',
        description: 'db.js created but never imported in index.js',
        badCode: '// index.js — missing: require("./config/db")()',
        goodCode: 'require("dotenv").config();\nconst connectDB = require("./config/db");\nconnectDB(); // Must call this!',
        preventionRule: 'index.js MUST import and CALL connectDB() before starting the server',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'wrong-mongodb-uri',
        name: 'Wrong MongoDB URI format or variable name',
        category: 'mongodb-issue',
        severity: 'critical',
        description: 'MongoDB URI is wrong or using wrong env var name. Team uses MONGO_URL not MONGODB_URI.',
        badCode: 'mongoose.connect("localhost:27017") // wrong format\nmongoose.connect(process.env.MONGODB_URI) // wrong var name',
        goodCode: 'mongoose.connect(process.env.MONGO_URL) // uses MONGO_URL with full URI including dbname',
        preventionRule: 'Use process.env.MONGO_URL (team convention). URI must be: mongodb://localhost:27017/{dbname}',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'missing-export-es-module',
        name: 'Missing ES module export (export default)',
        category: 'missing-export',
        severity: 'critical',
        description: 'ES module file missing export default or named exports. Team uses ES modules (import/export), not CJS (require/module.exports).',
        badCode: 'const router = express.Router();\n// forgot export default router',
        goodCode: 'const router = express.Router();\nrouter.get(...);\nexport default router; // ES module export',
        preventionRule: 'Team uses ES modules. Every route/model/controller MUST use export default or named exports. NEVER use module.exports.',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'start-script-missing',
        name: 'Missing "start" script in package.json',
        category: 'start-script-missing',
        severity: 'critical',
        description: 'npm start fails because "start" script is missing',
        badCode: '{ "scripts": { "test": "jest" } }',
        goodCode: '{ "type": "module", "main": "Server.js", "scripts": { "start": "nodemon Server.js", "dev": "nodemon Server.js" } }',
        preventionRule: 'package.json MUST have "type":"module", "main":"Server.js", and "scripts":{"start":"nodemon Server.js"}',
        affectsServices: ['express', 'gateway'],
        occurrences: 1
      },
      {
        patternId: 'route-not-mounted',
        name: 'Route file created but not mounted in Server.js',
        category: 'route-not-mounted',
        severity: 'critical',
        description: 'Routes defined in router file but not attached to Express app in Server.js',
        badCode: '// routes/user.js exists but Server.js does not import or use it',
        goodCode: 'import userRouter from "./routes/userRoutes.js";\napp.use("/api/v1/users", userRouter);',
        preventionRule: 'Every route file MUST be imported and mounted with app.use("/api/v1/resource", router) in Server.js',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'jwt-secret-wrong-var',
        name: 'JWT uses wrong env var name (JWT_SECRET instead of SEKRET_KEY)',
        category: 'jwt-error',
        severity: 'critical',
        description: 'Team uses SEKRET_KEY for JWT. Using JWT_SECRET will cause token verification to fail between services.',
        badCode: 'jwt.sign(payload, process.env.JWT_SECRET) // WRONG — undefined, tokens wont verify',
        goodCode: 'jwt.sign(payload, process.env.SEKRET_KEY) // CORRECT — all services share same SEKRET_KEY',
        preventionRule: 'ALWAYS use process.env.SEKRET_KEY (not JWT_SECRET) for JWT operations. All services must share the same SEKRET_KEY.',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'missing-env-file',
        name: 'Missing .env file or incomplete .env',
        category: 'env-not-used',
        severity: 'critical',
        description: '.env file missing required variables',
        badCode: '// .env is empty or missing PORT, MONGO_URL, SEKRET_KEY',
        goodCode: 'MONGO_URL=mongodb://localhost:27017/myapp\nSEKRET_KEY=shared_secret\nPORT=3001\nSERVER_URL=http://localhost:3001\nNODE_ENV=development',
        preventionRule: 'Every service .env MUST have: MONGO_URL, SEKRET_KEY, PORT, SERVER_URL, NODE_ENV',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'use-client-missing-nextjs',
        name: 'Missing "use client" in Next.js component',
        category: 'nextjs-error',
        severity: 'critical',
        description: 'Next.js 14 requires "use client" for components using useState/useEffect/onClick',
        badCode: '// No directive at top\nimport { useState } from "react"; // ERROR in App Router',
        goodCode: '"use client";\nimport { useState } from "react"; // Works correctly',
        preventionRule: 'Any Next.js component using useState, useEffect, useRef, onClick, or browser APIs MUST start with "use client"',
        affectsServices: ['nextjs'],
        occurrences: 1
      },
      {
        patternId: 'frontend-wrong-api-url',
        name: 'Frontend hardcodes API URL instead of using import.meta.env',
        category: 'frontend-api-error',
        severity: 'high',
        description: 'Vite frontend must use import.meta.env.VITE_SERVICE_URL for API calls, with full /api/v1/resource path',
        badCode: 'fetch("http://localhost:3001/api/users") // hardcoded, breaks in different env',
        goodCode: 'await axios.get(`${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users`, { headers: { Authorization: `Bearer ${token}` } })',
        preventionRule: 'Vite frontend MUST use import.meta.env.VITE_SERVICE_URL (not process.env). Include full /api/v1/resource path in each call.',
        affectsServices: ['vite', 'react', 'frontend'],
        occurrences: 1
      },
      {
        patternId: 'async-not-awaited-controller',
        name: 'Async controller function result not awaited',
        category: 'async-error',
        severity: 'critical',
        description: 'Controller calls async function without await causing silent failures',
        badCode: 'const getUser = async (req, res) => { const u = User.findById(id); res.json(u); }',
        goodCode: 'const getUser = async (req, res) => { const u = await User.findById(id); res.json(u); }',
        preventionRule: 'In every controller, await ALL async operations. Missing await = gets Promise object not data',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'cors-dependency-missing',
        name: 'cors package used but not in package.json',
        category: 'dependency-missing',
        severity: 'critical',
        description: 'Code requires("cors") but package.json does not list it',
        badCode: '{ "dependencies": { "express": "^4.18.0" } } // missing cors',
        goodCode: '{ "dependencies": { "express": "^4.18.0", "cors": "^2.8.5" } }',
        preventionRule: 'Every package used with require() MUST be in package.json dependencies',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'no-error-middleware',
        name: 'No global error handling middleware',
        category: 'missing-error-handler',
        severity: 'high',
        description: 'Express app has no error handling middleware — unhandled errors return empty responses',
        badCode: '// index.js ends with app.listen() — no error handler',
        goodCode: 'app.use((err, req, res, next) => {\n  res.status(err.status || 500).json({ error: err.message });\n});',
        preventionRule: 'Add error handling middleware (4 params: err,req,res,next) AFTER all routes in index.js',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'mongoose-model-not-required',
        name: 'Mongoose model file not required in controller',
        category: 'model-error',
        severity: 'critical',
        description: 'Controller uses a model without importing it',
        badCode: '// controllers/user.js — uses User but never requires it\nconst users = await User.find({});',
        goodCode: 'const User = require("../models/User");\nconst users = await User.find({});',
        preventionRule: 'Every controller/route MUST require() the Mongoose models it uses at the top of the file',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'bcrypt-wrong-package',
        name: 'bcrypt vs bcryptjs confusion',
        category: 'dependency-missing',
        severity: 'high',
        description: 'Code requires bcryptjs but package.json has bcrypt (or vice versa)',
        badCode: 'const bcrypt = require("bcrypt"); // needs native binding, often fails',
        goodCode: 'const bcrypt = require("bcryptjs"); // pure JS, always works',
        preventionRule: 'Always use bcryptjs (not bcrypt) — it is pure JavaScript and does not require native compilation',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'next-config-wrong',
        name: 'next.config.js syntax error or wrong format',
        category: 'nextjs-error',
        severity: 'high',
        description: 'next.config.js using wrong export syntax',
        badCode: 'export default { ... } // Wrong for Next.js config',
        goodCode: '/** @type {import("next").NextConfig} */\nconst nextConfig = { ... };\nmodule.exports = nextConfig;',
        preventionRule: 'next.config.js MUST use module.exports = nextConfig syntax, NOT ES module export default',
        affectsServices: ['nextjs'],
        occurrences: 1
      },
      {
        patternId: 'tailwind-not-configured',
        name: 'Tailwind classes not working — missing config',
        category: 'nextjs-error',
        severity: 'medium',
        description: 'tailwind.config.js content array does not include all component files',
        badCode: 'content: ["./pages/**/*.{js,ts,jsx,tsx}"] // misses app dir',
        goodCode: 'content: ["./src/**/*.{js,ts,jsx,tsx,mdx}", "./app/**/*.{js,ts,jsx,tsx,mdx}"]',
        preventionRule: 'tailwind.config.js content must cover ALL file locations: ./src/**/*.{js,ts,jsx,tsx,mdx}',
        affectsServices: ['nextjs'],
        occurrences: 1
      },
      {
        patternId: 'mongoose-schema-validation',
        name: 'Mongoose model missing required field validation',
        category: 'model-error',
        severity: 'medium',
        description: 'Schema fields missing required:true and validation',
        badCode: 'email: String // no validation',
        goodCode: 'email: { type: String, required: [true, "Email required"], unique: true, lowercase: true }',
        preventionRule: 'All important Mongoose schema fields must have: type, required, and appropriate validators',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'password-not-hashed',
        name: 'Password stored without hashing',
        category: 'validation-error',
        severity: 'critical',
        description: 'User password saved to DB in plain text',
        badCode: 'user.password = req.body.password; await user.save();',
        goodCode: 'const salt = await bcrypt.genSalt(10);\nuser.password = await bcrypt.hash(req.body.password, salt);\nawait user.save();',
        preventionRule: 'NEVER store plain text passwords. Always hash with bcryptjs before saving to DB',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'res-after-send',
        name: 'Response sent multiple times in same handler',
        category: 'async-error',
        severity: 'high',
        description: 'Multiple res.json() or res.send() calls in same route causing "headers already sent" error',
        badCode: 'if (!user) { res.status(404).json({error:"not found"}); }\nres.json(user); // ERROR: headers already sent',
        goodCode: 'if (!user) { return res.status(404).json({error:"not found"}); } // note: return\nres.json(user);',
        preventionRule: 'After every res.json/res.send call that is conditional, add return to prevent further execution',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'wrong-relative-path',
        name: 'Wrong relative import path (../  vs ./)',
        category: 'wrong-import',
        severity: 'critical',
        description: 'require("./models/User") from inside controllers/ should be require("../models/User")',
        badCode: '// In src/controllers/user.js:\nconst User = require("./models/User"); // WRONG: one level up needed',
        goodCode: '// In src/controllers/user.js:\nconst User = require("../models/User"); // CORRECT',
        preventionRule: 'Always count folder levels: controllers/ needs ../models/, routes/ needs ../models/, etc.',
        affectsServices: ['express'],
        occurrences: 1
      },
      {
        patternId: 'tailwind-v3-postcss-pattern',
        name: 'Tailwind v3 PostCSS correct team pattern',
        category: 'vite-config-error',
        severity: 'critical',
        description: 'Team uses Tailwind v3 PostCSS (NOT @tailwindcss/vite v4). postcss.config.js with tailwindcss + autoprefixer. src/index.css uses @tailwind directives.',
        badCode: '// WRONG: @import "tailwindcss" in index.css (v4 syntax)\n// WRONG: tailwindcss() in vite.config.js plugins',
        goodCode: '// postcss.config.js: export default { plugins: { tailwindcss: {}, autoprefixer: {} } }\n// index.css: @tailwind base; @tailwind components; @tailwind utilities;\n// vite.config.js: plugins: [react()] — NO tailwindcss plugin',
        preventionRule: 'Team uses Tailwind v3 PostCSS: postcss.config.js handles tailwindcss. NEVER use @import "tailwindcss" (v4) or @tailwindcss/vite plugin.',
        affectsServices: ['vite', 'react', 'frontend'],
        occurrences: 3
      },
      {
        patternId: 'vite-index-html-missing-script',
        name: 'index.html missing Vite entry script tag',
        category: 'vite-config-error',
        severity: 'critical',
        description: 'index.html must contain <script type="module" src="/src/main.jsx"></script> or Vite builds nothing',
        badCode: '<div id="root"></div>\n</body> <!-- missing script tag — Vite bundles nothing -->',
        goodCode: '<div id="root"></div>\n<script type="module" src="/src/main.jsx"></script>\n</body>',
        preventionRule: 'index.html MUST have <script type="module" src="/src/main.jsx"></script> before </body>. Without it, nothing gets bundled.',
        affectsServices: ['vite', 'react', 'frontend'],
        occurrences: 2
      },
      {
        patternId: 'vite-server-port-5173',
        name: 'Vite dev server must run on port 5173',
        category: 'vite-config-error',
        severity: 'medium',
        description: 'vite.config.js must set server.port: 5173 explicitly so frontend always starts on correct port',
        badCode: 'export default defineConfig({ plugins: [react()] }) // random port',
        goodCode: 'export default defineConfig({ plugins: [react()], server: { port: 5173, host: true } })',
        preventionRule: 'Always set server.port: 5173 in vite.config.js. Frontend must run on 5173 consistently.',
        affectsServices: ['vite', 'react', 'frontend'],
        occurrences: 1
      },
      {
        patternId: 'outlet-pattern-banned',
        name: '<Outlet /> from react-router-dom is BANNED',
        category: 'react-router-error',
        severity: 'critical',
        description: 'Team pattern does NOT use <Outlet />. Each page group owns its own <Routes><Route> block.',
        badCode: '// WRONG: App.jsx nests routes\n<Route path="/" element={<HomePage />}>\n  <Route index element={<Home />} />\n</Route>\n// WRONG: HomePage.jsx renders <Outlet />',
        goodCode: '// CORRECT: App.jsx uses flat groups\n<Route path="/*" element={<HomePage />} />\n// CORRECT: HomePage.jsx has its own <Routes>\n<Routes><Route path="/" element={<Home />} /></Routes>',
        preventionRule: 'NEVER use <Outlet /> or nested <Route> children in App.jsx. Each page group component has its own <Routes><Route> block.',
        affectsServices: ['react', 'frontend'],
        occurrences: 2
      },
      {
        patternId: 'html-comment-in-json',
        name: 'HTML comment inside package.json (EJSONPARSE)',
        category: 'syntax-error',
        severity: 'critical',
        description: 'AI adds <!-- --> HTML comments inside JSON which breaks JSON.parse() with EJSONPARSE. This cascades to spawn npm ENOENT because npm cannot read package.json.',
        badCode: '"dependencies": {\n  "express": "^4.18.2",\n  <!-- Added bcryptjs -->\n  "bcryptjs": "^2.4.3"\n}',
        goodCode: '"dependencies": {\n  "express": "^4.18.2",\n  "bcryptjs": "^2.4.3"\n}',
        preventionRule: 'NEVER add HTML comments (<!-- -->), JS comments (// or /* */), or ANY non-JSON syntax inside package.json. JSON only.',
        affectsServices: ['express', 'frontend', 'gateway'],
        occurrences: 5
      },
      {
        patternId: 'es-module-wrong-import-path',
        name: 'ES module import missing .js extension',
        category: 'wrong-import',
        severity: 'critical',
        description: 'ES module imports require .js extension on relative paths. Without it, Node.js throws ERR_MODULE_NOT_FOUND.',
        badCode: 'import User from "../models/User" // ERR_MODULE_NOT_FOUND',
        goodCode: 'import User from "../models/User.js" // correct',
        preventionRule: 'ALL ES module relative imports MUST include .js extension: import X from "./path/to/file.js"',
        affectsServices: ['express'],
        occurrences: 3
      },
      {
        patternId: 'wrong-env-var-names',
        name: 'Wrong environment variable names (MONGODB_URI or JWT_SECRET)',
        category: 'env-not-used',
        severity: 'critical',
        description: 'Team uses MONGO_URL and SEKRET_KEY. Using MONGODB_URI or JWT_SECRET will break all services.',
        badCode: 'MONGODB_URI=mongodb://localhost\nJWT_SECRET=secret // WRONG names',
        goodCode: 'MONGO_URL=mongodb://localhost:27017/myapp\nSEKRET_KEY=shared_secret // CORRECT names',
        preventionRule: 'Team env var convention: MONGO_URL (not MONGODB_URI), SEKRET_KEY (not JWT_SECRET). ALL services use the same SEKRET_KEY.',
        affectsServices: ['express'],
        occurrences: 4
      }
    ];

    try {
      // Use bulkWrite with upsert to add new patterns without touching existing ones
      const ops = knownBugs.map(bug => ({
        updateOne: {
          filter: { patternId: bug.patternId },
          update: { $setOnInsert: bug },
          upsert: true
        }
      }));
      const result = await BugStore.bulkWrite(ops, { ordered: false });
      const inserted = result.upsertedCount || 0;
      const total = await BugStore.countDocuments();
      if (inserted > 0) {
        console.log(`[BugStore] Added ${inserted} new bug patterns (total: ${total})`);
      } else {
        console.log(`[BugStore] Bug store up to date (${total} patterns)`);
      }
    } catch (err) {
      console.error('[BugStore] Seed error:', err.message);
    }
  }

  _makePatternId(text) {
    return text.toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .slice(0, 60);
  }
}

module.exports = new BugStoreService();
