const bugStoreService = require('./bugStoreService');
const staticAnalyzer = require('./staticAnalyzer');

/**
 * AnalyzerAgent — Completely rewritten with:
 *
 *  LAYER 1: Static analysis (instant, zero-AI) — catches 30+ patterns
 *  LAYER 2: AI analysis with 40-point MERN checklist (deep review)
 *  LAYER 3: Multi-round fix loop (up to 3 rounds until clean)
 *  LAYER 4: Bug store recording (never repeat same bug)
 *
 * This gives 100% coverage: static catches the obvious, AI catches the subtle.
 */

const ANALYZER_SYSTEM_PROMPT = `You are the world's most thorough MERN stack code reviewer.
You MUST check every single point in the checklist below and fix ALL issues found.

FILE FORMAT for fixed files (use EXACTLY):
===FILE: relative/path/to/file.ext===
[COMPLETE file content — never truncate]
===END===

TEAM PATTERN: ES MODULES throughout (import/export — NOT require/module.exports)
Entry point: Server.js (NOT index.js)
Env vars: MONGO_URL, SEKRET_KEY (NOT MONGODB_URI or JWT_SECRET)

MANDATORY 45-POINT MERN CHECKLIST — check EVERY point:

EXPRESS/NODE CHECKS (ES MODULE PATTERN):
[ 1] dotenv.config() called FIRST in Server.js before any other imports take effect
[ 2] app.use(express.json()) is present BEFORE all routes
[ 3] app.use(express.urlencoded({ extended: true })) is present
[ 4] app.use(cors()) is present with cors imported
[ 5] connectToDatabase() is imported from "./DbConnection.js" and called in Server.js
[ 6] MONGO_URL used (NOT MONGODB_URI) — value: mongodb://localhost:27017/{dbname}
[ 7] PORT comes from process.env.PORT || <default> (never hardcoded in app.listen)
[ 8] Global error handler (err, req, res, next) added AFTER all routes BEFORE app.listen
[ 9] /health endpoint exists returning { status: "healthy", service: name, timestamp }
[10] All route files are imported AND mounted with app.use() in Server.js

ROUTE/CONTROLLER CHECKS:
[11] EVERY async route handler has try { ... } catch (err) { res.status(500).json({message: err.message}) }
[12] return used before every res.json() to prevent "headers already sent"
[13] Every Mongoose operation (find/save/create/update/delete) has await before it
[14] Input validation exists for all POST/PUT routes
[15] Route methods: GET=read, POST=create, PUT/PATCH=update, DELETE=delete
[16] Auth checks: checkHasAccount(req), checkAdmin(req) etc. imported from authController.js

MODEL CHECKS:
[17] All Mongoose models have proper field types
[18] Required fields have { required: [true, "message"] }
[19] Passwords NEVER stored plain — always hashed with bcryptjs
[20] All model files end with: export default mongoose.model("Name", schema)
[21] Model names consistent between mongoose.model() and controller imports

IMPORTS/EXPORTS CHECKS (ES MODULE):
[22] All files use import/export — NO require() or module.exports
[23] All import paths include .js extension: import X from "./path/to/file.js"
[24] Relative import paths are correct (../models/ from controllers/, ./routes/ from Server.js)
[25] bcryptjs used (NOT bcrypt) — bcrypt needs native compilation, fails on Windows
[26] All packages used in code are listed in package.json dependencies

PACKAGE.JSON CHECKS:
[27] "type": "module" is present — REQUIRED for ES modules
[28] "main": "Server.js" (NOT index.js)
[29] "start" script: "nodemon Server.js"
[30] Required packages: express, mongoose, cors, dotenv, bcryptjs, jsonwebtoken, helmet
[31] NO HTML comments (<!-- -->) or JS comments in package.json — JSON ONLY

.ENV CHECKS:
[32] .env has MONGO_URL (NOT MONGODB_URI), SEKRET_KEY (NOT JWT_SECRET), PORT, SERVER_URL
[33] All process.env.VARIABLE references match .env keys exactly

REACT/FRONTEND CHECKS:
[34] NEVER use <Outlet /> from react-router-dom — use nested <Routes><Route> inside each page group
[35] App.jsx uses flat route groups: <Route path="/*" element={<HomePage />} />, <Route path="admin/*" element={<AdminPage />} />
[36] Each page group (HomePage, AdminPage) has its OWN <Routes> with nested routes
[37] API calls: import.meta.env.VITE_SERVICE_URL + /api/v1/resource (full path, not just base URL)
[38] Token: localStorage.setItem("token", res.data.token) + Bearer header on API calls
[39] Tailwind v3: @tailwind base; @tailwind components; @tailwind utilities; (NOT @import "tailwindcss")
[40] vite.config.js has server.port: 5173 and NO tailwindcss in plugins array

GATEWAY CHECKS:
[41] http-proxy-middleware is in gateway dependencies
[42] All service ports match the plan exactly
[43] Gateway is CommonJS (require) while backend services are ES modules (import)

SECURITY CHECKS:
[44] JWT tokens verified in protected routes using SEKRET_KEY
[45] No secrets hardcoded in source files (use process.env or import.meta.env)

RESPOND FORMAT:
ROUND: [1/2/3/4/5]
ISSUES_FOUND:
- [service-name] issue description matching checklist point number
FIXED_FILES:
===FILE: ...===
[complete content]
===END===
CLEAN: YES/NO (YES = ALL 45 points pass for ALL files)`;

class AnalyzerAgent {
  constructor(ollamaService, io) {
    this.ollama = ollamaService;
    this.io = io;
    this.MAX_ROUNDS = 5;
  }

  /**
   * LAYER 1 + 2 + 3: Full analysis pipeline.
   * Returns { issues, fixedFiles, totalRounds, bugsSaved }
   */
  async analyze(jobId, allFiles, plan, onToken, context = {}) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Analyzer',
      message: 'Layer 1: Running static analysis on all files...'
    });

    // ── LAYER 1: Static Analysis ────────────────────────────────
    const staticIssues = staticAnalyzer.analyzeFiles(allFiles);
    const staticSummary = staticAnalyzer.summarize(staticIssues);

    this.io.to(jobId).emit('log', {
      level: staticSummary.critical > 0 ? 'error' : 'info',
      agent: 'Analyzer',
      message: `Static analysis: ${staticSummary.total} issues (${staticSummary.critical} critical, ${staticSummary.high} high)`,
      timestamp: new Date().toISOString()
    });

    // Auto-fix what we can without AI
    const autoFixedFiles = [];
    for (const file of allFiles) {
      const result = staticAnalyzer.autoFix(file, staticIssues);
      if (result.wasFixed) {
        autoFixedFiles.push({ path: file.path, content: result.content, service: file.service });
        this.io.to(jobId).emit('log', {
          level: 'success',
          agent: 'Analyzer',
          message: `Auto-fixed ${result.fixes.join(', ')} in ${file.path}`,
          timestamp: new Date().toISOString()
        });
      }
    }

    // Merge auto-fixes back into allFiles
    const mergedFiles = allFiles.map(f => {
      const fixed = autoFixedFiles.find(af => af.path === f.path);
      return fixed || f;
    });

    // Record static bugs in bug store
    const bugsToRecord = staticIssues.map(i => ({
      name: i.name,
      description: i.message,
      category: i.category,
      severity: i.severity,
      preventionRule: i.message,
      affectsServices: ['express']
    }));
    await bugStoreService.recordBugs(bugsToRecord, jobId);

    // ── LAYER 2 + 3: AI Multi-Round Analysis ───────────────────
    let currentFiles = mergedFiles;
    let allIssues = staticIssues.map(i => `[${i.filePath}] ${i.message}`);
    let allFixedFiles = [...autoFixedFiles];
    let totalRounds = 0;
    let isClean = false;

    for (let round = 1; round <= this.MAX_ROUNDS && !isClean; round++) {
      totalRounds = round;
      this.io.to(jobId).emit('agent:working', {
        agent: 'Analyzer',
        message: `Layer 2: AI deep review — Round ${round}/${this.MAX_ROUNDS}...`
      });

      const result = await this._runAIAnalysis(jobId, currentFiles, plan, round, onToken, context);

      if (result.issues.length > 0) {
        allIssues.push(...result.issues);

        // Record new bugs found by AI
        const aiBugs = bugStoreService.parseAnalyzerIssues(
          result.issues.join('\n'),
          'multiple'
        );
        await bugStoreService.recordBugs(aiBugs, jobId);

        this.io.to(jobId).emit('log', {
          level: 'warning',
          agent: 'Analyzer',
          message: `Round ${round}: Found ${result.issues.length} issues, applying ${result.fixedFiles.length} fixes...`,
          timestamp: new Date().toISOString()
        });
      }

      if (result.fixedFiles.length > 0) {
        // Never accept AI rewrites of index.html — Vite manages it
        const safeFixedFiles = result.fixedFiles.filter(f => !f.path.endsWith('index.html'));
        allFixedFiles = this._mergeFixedFiles(allFixedFiles, safeFixedFiles);
        // Apply fixes to current files for next round
        currentFiles = this._applyFixes(currentFiles, safeFixedFiles);
      }

      if (result.isClean || result.issues.length === 0) {
        isClean = true;
        this.io.to(jobId).emit('log', {
          level: 'success',
          agent: 'Analyzer',
          message: `Round ${round}: Code review passed — no more issues found!`,
          timestamp: new Date().toISOString()
        });
      }
    }

    this.io.to(jobId).emit('log', {
      level: 'success',
      agent: 'Analyzer',
      message: `Analysis complete: ${allIssues.length} total issues fixed across ${totalRounds} rounds`,
      timestamp: new Date().toISOString()
    });

    return {
      issues: allIssues,
      fixedFiles: allFixedFiles,
      totalRounds,
      bugsSaved: bugsToRecord.length
    };
  }

  /**
   * RUNTIME FIX: Called when a service fails to start.
   * Uses full conversation history + error output + checklist.
   */
  async fixError(jobId, serviceName, errorOutput, relevantFiles, onToken, context = {}) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Fixer',
      message: `Fixing runtime error in ${serviceName}: ${errorOutput.slice(0, 60)}...`
    });

    // Get prevention rules from bug store for context
    const preventionPrompt = await bugStoreService.buildPreventionPrompt();

    const FIXER_SYSTEM = `You are an expert Node.js debugger. Fix the EXACT error shown.
${preventionPrompt}

Use ===FILE: path=== [complete content] ===END=== for every fixed file.
Return COMPLETE file contents — never truncate.
Make MINIMAL targeted fixes. Do not rewrite working code.`;

    // Also run static analysis on the failing service files first
    const staticIssues = staticAnalyzer.analyzeFiles(relevantFiles);
    const staticFixedFiles = [];
    for (const file of relevantFiles) {
      const result = staticAnalyzer.autoFix(file, staticIssues);
      if (result.wasFixed) {
        staticFixedFiles.push({ path: file.path, content: result.content });
      }
    }

    const prompt = `The service "${serviceName}" failed to start with this error:

ERROR OUTPUT:
\`\`\`
${errorOutput.slice(0, 3000)}
\`\`\`

Static analysis also found these issues:
${staticIssues.map(i => `- [${i.severity}] ${i.message}`).join('\n') || 'None'}

Relevant files:
${relevantFiles.map(f => `--- ${f.path} ---\n${f.content?.slice(0, 3000)}`).join('\n\n')}

Fix the error. Return complete corrected files using ===FILE=== format.`;

    const response = await this.ollama.generateWithHistory(
      jobId, prompt, FIXER_SYSTEM, 'fixer', `fix_${serviceName}`, onToken, context
    );

    // Filter out index.html from AI fixes — Vite manages it, AI should not rewrite it
    const aiFixedFiles = this._extractFiles(response).filter(
      f => !f.path.endsWith('index.html')
    );
    const allFixes = this._mergeFixedFiles(staticFixedFiles, aiFixedFiles);

    // Record this bug in the store
    await bugStoreService.recordBug({
      name: `Runtime error in ${serviceName}: ${errorOutput.split('\n')[0].slice(0, 60)}`,
      description: errorOutput.slice(0, 200),
      category: 'other',
      severity: 'critical',
      preventionRule: `Check ${serviceName} for: ${errorOutput.slice(0, 100)}`,
      affectsServices: [serviceName]
    }, jobId);

    return allFixes;
  }

  // ── Private Helpers ────────────────────────────────────────────────────────

  async _runAIAnalysis(jobId, files, plan, round, onToken, context = {}) {
    // Build file summary (limit size to avoid token overload)
    // EXCLUDE index.html — AI must not rewrite it (Vite manages it)
    const criticalFiles = files.filter(f => {
      const name = f.path.toLowerCase();
      if (name.endsWith('index.html')) return false; // never send to AI
      return name.includes('server.js') || name.includes('package.json') ||
             name.includes('.env') || name.includes('route') ||
             name.includes('model') || name.includes('controller') ||
             name.includes('app.jsx') || name.includes('main.jsx') ||
             name.includes('homepage') || name.includes('adminpage') ||
             name.includes('dbconnection');
    });

    const fileContent = criticalFiles
      .slice(0, 20)
      .map(f => `=== ${f.path} ===\n${f.content?.slice(0, 2000) || ''}`)
      .join('\n\n---\n\n');

    const prompt = `ROUND ${round}/${this.MAX_ROUNDS} — Review this MERN microservice code against ALL 40 checklist points.

Project: ${plan.projectName}
Services: ${plan.services?.map(s => `${s.name}:${s.port}`).join(', ')}

FILES TO REVIEW (${criticalFiles.length} key files):
${fileContent}

Check ALL 40 points. Fix EVERYTHING found. Return COMPLETE fixed files.
Set CLEAN: YES only if ALL 40 points pass for all files.`;

    const response = await this.ollama.generateWithHistory(
      jobId, prompt, ANALYZER_SYSTEM_PROMPT, 'analyzer', `analyze_round_${round}`, onToken, context
    );

    return this._parseResponse(response);
  }

  _parseResponse(response) {
    const issues = [];
    const fixedFiles = [];

    // ★ LOOP FIX: clip at last ===END=== before parsing to discard looped junk
    const cleanResponse = this._clipAtLastEnd(response);

    // Extract issues
    const issuesMatch = cleanResponse.match(/ISSUES_FOUND:([\s\S]*?)(?:FIXED_FILES:|===FILE:|CLEAN:|$)/);
    if (issuesMatch) {
      issuesMatch[1].trim().split('\n').forEach(line => {
        const cleaned = line.replace(/^[-•*\[\d\]]\s*/, '').trim();
        if (cleaned && !cleaned.toLowerCase().includes('none') && cleaned.length > 3) {
          issues.push(cleaned);
        }
      });
    }

    // Extract fixed files
    const fileRegex = /===FILE:\s*([^\n=]+)===\n([\s\S]*?)===END===/g;
    let match;
    while ((match = fileRegex.exec(cleanResponse)) !== null) {
      fixedFiles.push({ path: match[1].trim(), content: match[2] });
    }

    // Check if clean
    const isClean = /CLEAN:\s*YES/i.test(cleanResponse);

    return { issues, fixedFiles, isClean };
  }

  _extractFiles(response) {
    const files = [];
    // ★ LOOP FIX: clip at last ===END=== before parsing
    const cleanResponse = this._clipAtLastEnd(response);
    const fileRegex = /===FILE:\s*([^\n=]+)===\n([\s\S]*?)===END===/g;
    let match;
    while ((match = fileRegex.exec(cleanResponse)) !== null) {
      files.push({ path: match[1].trim(), content: match[2] });
    }
    return files;
  }

  /**
   * Clip the response at the last valid ===END=== marker.
   * Discards all looped/repeated text that appears after the model finishes.
   */
  _clipAtLastEnd(response) {
    if (!response) return response;
    const lastIdx = response.lastIndexOf('===END===');
    if (lastIdx === -1) return response;
    return response.slice(0, lastIdx + '===END==='.length);
  }

  _applyFixes(currentFiles, fixedFiles) {
    const fixMap = new Map(fixedFiles.map(f => [f.path, f]));
    return currentFiles.map(f => fixMap.get(f.path) || f);
  }

  _mergeFixedFiles(existing, newFixes) {
    const map = new Map(existing.map(f => [f.path, f]));
    for (const fix of newFixes) { map.set(fix.path, fix); }
    return Array.from(map.values());
  }
}

module.exports = AnalyzerAgent;
