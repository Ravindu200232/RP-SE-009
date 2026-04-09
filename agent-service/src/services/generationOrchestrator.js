const path = require('path');
const fs = require('fs-extra');

const OllamaService = require('./ollamaService');
const PlannerAgent = require('./plannerAgent');
const DeveloperAgent = require('./developerAgent');
const AnalyzerAgent = require('./analyzerAgent');
const FileWriterService = require('./fileWriterService');
const AppRunnerService = require('./appRunnerService');
const bugStoreService = require('./bugStoreService');
const patternLoader = require('./patternLoader');
const staticAnalyzer = require('./staticAnalyzer');
const Generation = require('../models/Generation');

const GENERATED_APPS_BASE = path.resolve(
  process.env.GENERATED_APPS_DIR || path.join(__dirname, '../../../generated-apps')
);

// ── HARDCODED frontend template files (AI gets these wrong — always overwrite) ────────────────
//
// Team pattern: Tailwind v3 PostCSS (NOT @tailwindcss/vite v4)
// From MICROSERVICE_PATTERN_README.md section 12
//
// Frontend port: 5173 (Vite default dev server)

// vite.config.js — standard React, no Tailwind plugin (PostCSS handles it)
const CORRECT_VITE_CONFIG = `import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true
  }
})
`;

// tailwind.config.js — v3 content paths + team color palette
const CORRECT_TAILWIND_CONFIG = `/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#050818",
        secondary: "#ffffff",
        accent: "#7DC4FF",
      },
      fontFamily: {
        display: ["Cormorant Garamond", "serif"],
        sans: ["Outfit", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
}
`;

// postcss.config.js — v3 PostCSS plugin pattern
const CORRECT_POSTCSS_CONFIG = `export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
`;

// src/index.css — v3 directives (NOT @import "tailwindcss" — that's v4)
const CORRECT_INDEX_CSS = `@tailwind base;
@tailwind components;
@tailwind utilities;

/* Base styles */
*, *::before, *::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  font-family: 'Outfit', system-ui, -apple-system, sans-serif;
  background-color: #f3f4f6;
}
`;

class GenerationOrchestrator {
  constructor(io) {
    this.io = io;
    this.ollama = new OllamaService(io);
    this.planner = new PlannerAgent(this.ollama, io);
    this.developer = new DeveloperAgent(this.ollama, io);
    this.analyzer = new AnalyzerAgent(this.ollama, io);
    this.runner = new AppRunnerService(io);
  }

  async run(jobId, srs) {
    try {
      // ── STEP 0: Seed bug store ─────────────────────────────────────────────
      await bugStoreService.seed();
      await this._log(jobId, 'Orchestrator', 'Bug knowledge base ready (35+ known patterns including EJSONPARSE, Outlet, ES module, bcryptjs)', 'success');

      // ── STEP 0.5: Planning display (Codex-style thinking step) ───────────
      await this._log(jobId, 'Orchestrator', '📋 PLAN — Reading SRS and forming architecture...', 'info');
      this.io.to(jobId).emit('log', {
        level: 'thinking', agent: 'Orchestrator',
        message: '🧠 Thinking:\n  1. Identify microservices and their responsibilities\n  2. Define routes, models, and inter-service calls\n  3. Plan frontend route groups and pages\n  4. Generate code following team ES module pattern\n  5. Run static + AI analysis (up to 5 rounds each)\n  6. Start all services and verify\n  7. Generate SKILL.md, AGENTS.md, BUG.md',
        timestamp: new Date().toISOString()
      });

      // ── STEP 1: PLAN ───────────────────────────────────────────────────────
      await this._updateStatus(jobId, 'planning', 5, 'Planner');
      await this._log(jobId, 'Planner', 'Analyzing SRS and creating microservice architecture...', 'info');

      // Codex-style auto context compaction status
      const srsTokenEstimate = Math.ceil(JSON.stringify(srs).length / 4);
      this.io.to(jobId).emit('log', {
        level: 'info', agent: 'Planner',
        message: `📦 SRS context: ~${srsTokenEstimate} tokens → auto-compacting before AI call (Codex-style context compaction)`,
        timestamp: new Date().toISOString()
      });

      this.io.to(jobId).emit('log', {
        level: 'prompt', agent: 'AI Prompt',
        message: 'Sending SRS to AI → asking for microservice plan with services, routes, models...',
        timestamp: new Date().toISOString()
      });

      const plan = await this.planner.plan(jobId, srs, (token) => {
        this.io.to(jobId).emit('agent:stream', { agent: 'Planner', token });
      });

      await Generation.updateOne({ jobId }, {
        plan,
        services: plan.services.map(s => ({
          name: s.name, port: s.port, status: 'pending',
          routes: (s.routes || []).map(r => `${r.method} ${r.path}`)
        }))
      });
      const frontendPort = plan.frontend?.port || 5173;
      await this._log(jobId, 'Planner', `Plan: ${plan.services.map(s => `${s.name}:${s.port}`).join(', ')} + frontend:${frontendPort} + gateway:8080`, 'success');
      this.io.to(jobId).emit('plan:ready', { plan });

      // ── STEP 2: App directory ─────────────────────────────────────────────
      const appDir = path.join(GENERATED_APPS_BASE, jobId);
      await fs.ensureDir(appDir);
      const writer = new FileWriterService(appDir);
      await Generation.updateOne({ jobId }, { appDir });

      // allGeneratedFiles tracks EVERYTHING written (package.json + source files)
      const allGeneratedFiles = [];

      // ── STEP 3: Build each backend service ────────────────────────────────
      await this._updateStatus(jobId, 'generating', 10, 'Developer');

      for (let i = 0; i < plan.services.length; i++) {
        const service = plan.services[i];
        const progress = 10 + Math.round((i / plan.services.length) * 32);
        await this._updateProgress(jobId, progress);
        await this._log(jobId, 'Developer', `\n── Building ${service.name} (port ${service.port}) ──`, 'info');

        // 3a: AI → package.json only
        const pkgJson = await this.developer.generatePackageJson(jobId, service, plan, (t) => {
          this.io.to(jobId).emit('agent:stream', { agent: 'Developer', token: t });
        });
        const pkgContent = JSON.stringify(pkgJson, null, 2);
        await writer.writeFile(`${service.name}/package.json`, pkgContent);

        // ★ FIX: Track package.json in allGeneratedFiles
        allGeneratedFiles.push({ path: `${service.name}/package.json`, content: pkgContent, service: service.name });
        await this._log(jobId, 'Developer', `package.json created for ${service.name}`, 'success');

        // 3b: npm install with explicit package list
        const deps = Object.keys(pkgJson.dependencies || {});
        const svcDir = path.join(appDir, service.name);
        await this._log(jobId, 'Terminal', `Running: npm install ${deps.join(' ')}`, 'command');
        const installResult = await this.runner.npmInstall(svcDir, service.name, jobId, deps);
        await this._log(jobId, 'Runner',
          installResult.success ? `npm install complete for ${service.name}` : `npm install warning (continuing)`,
          installResult.success ? 'success' : 'warning'
        );

        // 3c: AI → all source files
        const srcFiles = await this.developer.generateSourceFiles(jobId, service, plan, (t) => {
          this.io.to(jobId).emit('agent:stream', { agent: 'Developer', token: t });
        });
        const prefixed = srcFiles.map(f => ({
          ...f,
          path: f.path.startsWith(service.name + '/') ? f.path : `${service.name}/${f.path}`
        }));
        await writer.writeFiles(prefixed);
        allGeneratedFiles.push(...prefixed);
        await this._log(jobId, 'Developer', `Generated ${srcFiles.length} source files for ${service.name}`, 'success');
        this.io.to(jobId).emit('files:generated', { service: service.name, files: prefixed.map(f => f.path) });
      }

      // ── STEP 4: Vite + React frontend ────────────────────────────────────
      await this._updateProgress(jobId, 45);
      await this._log(jobId, 'Developer', '\n── Building Frontend (Vite + React + Tailwind v3 PostCSS) ──', 'info');

      // 4a: npm create vite@latest frontend -- --template react
      const { appDir: frontendDir } = await this.runner.createViteApp(appDir, 'frontend', jobId);

      // 4b: npm install base dependencies
      await this.runner.npmInstall(frontendDir, 'frontend-base', jobId);

      // 4c: npm install -D tailwindcss@3 postcss autoprefixer (v3 PostCSS pattern — team template)
      await this.runner.installTailwindPostCSS(frontendDir, jobId);
      await this._log(jobId, 'Runner', 'Tailwind CSS v3 (PostCSS) installed', 'success');

      // 4d: npm install frontend libraries — react-router-dom, axios, react-hot-toast, etc.
      await this.runner.installFrontendLibs(frontendDir, jobId);
      await this._log(jobId, 'Runner', 'Frontend libraries installed (react-router-dom, axios, react-hot-toast, react-icons)', 'success');

      // 4e: AI → React source files
      const frontendFiles = await this.developer.generateViteFrontend(jobId, plan, (t) => {
        this.io.to(jobId).emit('agent:stream', { agent: 'Developer', token: t });
      });
      const prefixedFrontend = frontendFiles.map(f => ({
        ...f,
        service: 'frontend',
        path: f.path.startsWith('frontend/') ? f.path : `frontend/${f.path}`
      }));
      await writer.writeFiles(prefixedFrontend);
      allGeneratedFiles.push(...prefixedFrontend);

      // ★ ALWAYS overwrite these 4 config files with correct team template versions
      // AI often gets vite.config.js, tailwind.config.js, postcss.config.js, and index.css wrong.
      // These are hardcoded from the team pattern — never trust AI for config files.
      await this._log(jobId, 'Developer', 'Applying hardcoded template config files (vite + tailwind + postcss + index.css)', 'info');
      await writer.writeFile('frontend/vite.config.js', CORRECT_VITE_CONFIG);
      await writer.writeFile('frontend/tailwind.config.js', CORRECT_TAILWIND_CONFIG);
      await writer.writeFile('frontend/postcss.config.js', CORRECT_POSTCSS_CONFIG);
      await writer.writeFile('frontend/src/index.css', CORRECT_INDEX_CSS);

      // ★ Remove any @tailwindcss/vite traces (AI might generate v4 style — kill it)
      const vitePluginPkg = path.join(frontendDir, 'node_modules', '@tailwindcss', 'vite');
      // (don't remove node_modules — just ensure config files are correct above)

      // Update tracked files with correct versions
      const upsertFile = (filePath, content) => {
        const idx = allGeneratedFiles.findIndex(f => f.path === filePath);
        if (idx !== -1) allGeneratedFiles[idx].content = content;
        else allGeneratedFiles.push({ path: filePath, content, service: 'frontend' });
      };
      upsertFile('frontend/vite.config.js', CORRECT_VITE_CONFIG);
      upsertFile('frontend/tailwind.config.js', CORRECT_TAILWIND_CONFIG);
      upsertFile('frontend/postcss.config.js', CORRECT_POSTCSS_CONFIG);
      upsertFile('frontend/src/index.css', CORRECT_INDEX_CSS);

      await this._log(jobId, 'Developer', `Generated ${frontendFiles.length} frontend files`, 'success');
      this.io.to(jobId).emit('files:generated', { service: 'frontend', files: prefixedFrontend.map(f => f.path) });

      // ── STEP 5: Gateway ───────────────────────────────────────────────────
      const gatewayFiles = this.developer.generateGateway(plan);
      await writer.writeFiles(gatewayFiles);
      allGeneratedFiles.push(...gatewayFiles);
      await this._log(jobId, 'Developer', 'API Gateway generated', 'success');

      await Generation.updateOne({ jobId }, { generatedFiles: allGeneratedFiles });

      // ── STEP 6: Static analysis + auto-fix ───────────────────────────────
      await this._updateStatus(jobId, 'analyzing', 52, 'Analyzer');
      await this._log(jobId, 'Analyzer', '\n── Layer 1: Static Analysis (35 pattern checks) ──', 'info');

      const staticIssues = staticAnalyzer.analyzeFiles(allGeneratedFiles);
      const summary = staticAnalyzer.summarize(staticIssues);
      await this._log(jobId, 'Analyzer',
        `Found ${summary.total} issues: ${summary.critical} critical, ${summary.high} high, ${summary.other} other`,
        summary.critical > 0 ? 'warning' : 'success'
      );

      for (const issue of summary.topIssues) {
        await this._log(jobId, 'Analyzer',
          `  [${issue.severity.toUpperCase()}] ${issue.file}: ${issue.message}${issue.autoFixable ? ' (auto-fixing...)' : ''}`,
          issue.severity === 'critical' ? 'error' : 'warning'
        );
      }

      // Auto-fix
      for (let i = 0; i < allGeneratedFiles.length; i++) {
        const result = staticAnalyzer.autoFix(allGeneratedFiles[i], staticIssues);
        if (result.wasFixed) {
          allGeneratedFiles[i] = { ...allGeneratedFiles[i], content: result.content };
          await writer.writeFile(allGeneratedFiles[i].path, result.content);
          await this._log(jobId, 'Analyzer', `  Auto-fixed in ${allGeneratedFiles[i].path}: ${result.fixes.join(', ')}`, 'success');
        }
      }
      await bugStoreService.recordBugs(
        staticIssues.map(i => ({ name: i.name, description: i.message, category: i.category, severity: i.severity, preventionRule: i.message, affectsServices: ['express'] })),
        jobId
      );

      // ── STEP 7: AI multi-round analysis ──────────────────────────────────
      await this._updateProgress(jobId, 58);
      await this._log(jobId, 'Analyzer', '\n── Layer 2: AI 40-point Deep Review ──', 'info');
      this.io.to(jobId).emit('log', {
        level: 'prompt', agent: 'AI Prompt',
        message: 'Sending generated files to AI for 45-point MERN checklist review (up to 5 rounds)...',
        timestamp: new Date().toISOString()
      });

      const { issues, fixedFiles, totalRounds } = await this.analyzer.analyze(
        jobId, allGeneratedFiles, plan, (t) => {
          this.io.to(jobId).emit('agent:stream', { agent: 'Analyzer', token: t });
        }
      );

      if (fixedFiles.length > 0) {
        await writer.writeFiles(fixedFiles);
        for (const fix of fixedFiles) {
          const idx = allGeneratedFiles.findIndex(f => f.path === fix.path);
          if (idx !== -1) allGeneratedFiles[idx] = { ...allGeneratedFiles[idx], ...fix };
          else allGeneratedFiles.push(fix);
        }
        await Generation.updateOne({ jobId }, { generatedFiles: allGeneratedFiles });
        await this._log(jobId, 'Analyzer', `AI applied ${fixedFiles.length} fixes across ${totalRounds} rounds`, 'success');
      } else {
        await this._log(jobId, 'Analyzer', `Code review passed in ${totalRounds} round(s)`, 'success');
      }

      // ── STEP 8: Install gateway deps ──────────────────────────────────────
      await this._updateProgress(jobId, 68);
      const gatewayDir = path.join(appDir, 'gateway');
      await this._log(jobId, 'Terminal', 'Running: npm install (gateway)', 'command');
      await this.runner.npmInstall(gatewayDir, 'gateway', jobId);

      // ── STEP 9: Build frontend ────────────────────────────────────────────
      await this._updateProgress(jobId, 72);
      await this._log(jobId, 'Terminal', 'Running: npm run build (frontend)', 'command');
      const buildResult = await this.runner.npmBuild(frontendDir, 'frontend', jobId);

      if (!buildResult.success) {
        await this._log(jobId, 'Fixer', `Build failed: ${buildResult.error?.split('\n')[0]?.slice(0, 120)}`, 'error');

        // ★ TARGETED FIX for Tailwind config errors — re-apply all 4 hardcoded template files
        const isTailwindError = buildResult.error?.includes('tailwindcss') ||
          buildResult.error?.includes('PostCSS') || buildResult.error?.includes('postcss') ||
          buildResult.error?.includes('@tailwind') || buildResult.error?.includes('plugin');

        if (isTailwindError) {
          await this._log(jobId, 'Fixer', 'Known issue: Tailwind config error — re-applying template config files', 'info');
          await writer.writeFile('frontend/vite.config.js', CORRECT_VITE_CONFIG);
          await writer.writeFile('frontend/tailwind.config.js', CORRECT_TAILWIND_CONFIG);
          await writer.writeFile('frontend/postcss.config.js', CORRECT_POSTCSS_CONFIG);
          await writer.writeFile('frontend/src/index.css', CORRECT_INDEX_CSS);
          await this._log(jobId, 'Fixer', 'Re-applied all 4 template config files. Retrying build...', 'success');
        } else {
          // Send non-Tailwind errors to AI
          await this._log(jobId, 'Fixer', 'Sending build error to AI for fix...', 'info');
          this.io.to(jobId).emit('log', {
            level: 'prompt', agent: 'AI Prompt',
            message: `Sending build error to AI:\n${buildResult.error?.slice(0, 400)}`,
            timestamp: new Date().toISOString()
          });
          const frontendSrcFiles = await writer.readAllFiles('frontend');
          // Only send src/ and config files to AI — never send index.html
          const fixableFiles = frontendSrcFiles.filter(f =>
            !f.path.endsWith('index.html') &&
            (f.path.includes('/src/') || f.path.endsWith('.config.js') || f.path.endsWith('.css'))
          );
          const fixes = await this.analyzer.fixError(jobId, 'frontend', buildResult.error, fixableFiles.slice(0, 10), null);
          if (fixes.length > 0) {
            // Never write index.html from AI fixer output
            const safeFixes = fixes.filter(f => !f.path.endsWith('index.html'));
            const fixedWithPrefix = safeFixes.map(f => ({ ...f, path: f.path.startsWith('frontend/') ? f.path : `frontend/${f.path}` }));
            await writer.writeFiles(fixedWithPrefix);
          }
        }

        // Retry build
        const retryBuild = await this.runner.npmBuild(frontendDir, 'frontend', jobId);
        if (retryBuild.success) {
          await this._log(jobId, 'Runner', 'Frontend build successful on retry', 'success');
        } else {
          await this._log(jobId, 'Runner', 'Build still failing — starting dev server instead', 'warning');
        }
      } else {
        await this._log(jobId, 'Runner', 'Frontend build successful', 'success');
      }

      // ── STEP 10: Kill existing processes on service ports ─────────────────
      await this._updateStatus(jobId, 'running', 78, 'Runner');
      await this._log(jobId, 'Runner', '\n── Clearing ports and starting all services ──', 'info');

      // Kill any existing processes on all required ports before starting
      const allPorts = [...plan.services.map(s => s.port), frontendPort, 8080];
      for (const port of allPorts) {
        await this.runner.killPort(port, jobId);
      }
      await this._log(jobId, 'Runner', `Cleared ports: ${allPorts.join(', ')}`, 'success');

      // ── STEP 11: Start backend services ──────────────────────────────────
      const runningServices = [];
      const MAX_FIX_RETRIES = 4;  // 5 total attempts (1 initial + 4 retries)

      for (const svc of plan.services) {
        const svcDir = path.join(appDir, svc.name);
        if (!await fs.pathExists(path.join(svcDir, 'package.json'))) {
          await this._log(jobId, 'Runner', `Skipping ${svc.name} — no package.json found on disk`, 'warning');
          continue;
        }

        let started = false;
        for (let attempt = 0; attempt <= MAX_FIX_RETRIES && !started; attempt++) {
          if (attempt > 0) await this._log(jobId, 'Fixer', `Retry ${attempt}/${MAX_FIX_RETRIES} for ${svc.name}...`, 'info');

          const result = await this.runner.startService(svcDir, svc.name, svc.port, jobId);

          if (result.success) {
            started = true;
            runningServices.push({ name: svc.name, port: svc.port, url: result.url });
            await Generation.updateOne(
              { jobId, 'services.name': svc.name },
              { $set: { 'services.$.status': 'running', 'services.$.url': result.url, 'services.$.pid': result.pid } }
            );
            await this._log(jobId, 'Runner', `${svc.name} running at ${result.url}`, 'success');

          } else if (attempt < MAX_FIX_RETRIES) {
            const errorText = result.error || 'Unknown error';
            await this._log(jobId, 'Fixer', `${svc.name} crashed:\n${errorText.slice(0, 300)}`, 'error');

            this.io.to(jobId).emit('log', {
              level: 'prompt', agent: 'AI Prompt',
              message: `Sending crash error to AI:\n${errorText.slice(0, 300)}\n→ AI will read error, find the line, generate fix...`,
              timestamp: new Date().toISOString()
            });

            const svcFiles = await writer.readAllFiles(svc.name);
            const fixes = await this.analyzer.fixError(jobId, svc.name, errorText, svcFiles, null);

            if (fixes.length > 0) {
              await this._log(jobId, 'Fixer', `AI identified ${fixes.length} file(s) to fix:`, 'info');
              for (const fix of fixes) await this._log(jobId, 'Fixer', `  → ${fix.path}`, 'success');
              const fixedWithPrefix = fixes.map(f => ({
                ...f, path: f.path.startsWith(svc.name + '/') ? f.path : `${svc.name}/${f.path}`
              }));
              await writer.writeFiles(fixedWithPrefix);
              await this.runner.npmInstall(svcDir, svc.name, jobId);
            }
          } else {
            const errorText = result.error || 'Unknown error';
            await this._log(jobId, 'Runner', `${svc.name} failed after ${MAX_FIX_RETRIES + 1} attempts`, 'error');
            await Generation.updateOne(
              { jobId, 'services.name': svc.name },
              { $set: { 'services.$.status': 'error', 'services.$.error': errorText.slice(0, 500) } }
            );
            await bugStoreService.recordBug({
              name: `Startup failure: ${svc.name}`,
              description: errorText.slice(0, 300),
              category: 'other', severity: 'critical',
              preventionRule: `Fix: ${errorText.split('\n')[0].slice(0, 100)}`,
              affectsServices: [svc.name]
            }, jobId);
          }
        }
      }

      // ── STEP 12: Start frontend (Vite dev server) ─────────────────────────
      await this._updateProgress(jobId, 90);
      const feResult = await this.runner.startService(frontendDir, 'frontend', frontendPort, jobId, { useDevMode: true });
      if (feResult.success) {
        await this._log(jobId, 'Runner', `Frontend running at http://localhost:${frontendPort}`, 'success');
      } else {
        await this._log(jobId, 'Runner', `Frontend failed to start: ${feResult.error?.slice(0, 100)}`, 'error');
      }

      // ── STEP 13: Start gateway ────────────────────────────────────────────
      await this._updateProgress(jobId, 94);
      const gwResult = await this.runner.startService(gatewayDir, 'gateway', 8080, jobId);
      if (gwResult.success) {
        await this._log(jobId, 'Runner', 'Gateway running at http://localhost:8080', 'success');
      }

      // ── STEP 14: Auto-generate SKILL.md for the generated app ────────────
      await this._updateProgress(jobId, 95);
      try {
        const skillContent = patternLoader.generateSkillFile(plan, appDir, jobId);
        await fs.writeFile(path.join(appDir, 'SKILL.md'), skillContent, 'utf8');
        await this._log(jobId, 'Orchestrator', `SKILL.md generated — import in Claude Code with: @${appDir.replace(/\\/g, '/')}/SKILL.md`, 'success');
      } catch (err) {
        await this._log(jobId, 'Orchestrator', `SKILL.md generation skipped: ${err.message}`, 'warning');
      }

      // ── STEP 15: Auto-generate AGENTS.md (Codex-style project guide) ─────
      await this._updateProgress(jobId, 97);
      try {
        const agentsContent = this._generateAgentsMd(plan, appDir);
        await fs.writeFile(path.join(appDir, 'AGENTS.md'), agentsContent, 'utf8');
        await this._log(jobId, 'Orchestrator', 'AGENTS.md generated — project guidance file for AI agents', 'success');
      } catch (err) {
        await this._log(jobId, 'Orchestrator', `AGENTS.md generation skipped: ${err.message}`, 'warning');
      }

      // ── STEP 16: Auto-generate BUG.md (bug report for this generation) ───
      await this._updateProgress(jobId, 99);
      try {
        const bugContent = this._generateBugMd(plan, staticIssues, issues, jobId);
        await fs.writeFile(path.join(appDir, 'BUG.md'), bugContent, 'utf8');
        await this._log(jobId, 'Orchestrator', 'BUG.md generated — full bug report for this generation', 'success');
      } catch (err) {
        await this._log(jobId, 'Orchestrator', `BUG.md generation skipped: ${err.message}`, 'warning');
      }

      // ── COMPLETE ──────────────────────────────────────────────────────────
      const allUrls = {
        gateway: 'http://localhost:8080',
        frontend: `http://localhost:${frontendPort}`,
        services: runningServices.reduce((acc, s) => { acc[s.name] = s.url; return acc; }, {}),
        apiRoutes: plan.services.map(s => ({
          prefix: `/api/v1/${s.name.replace('-service', '')}`,
          target: `http://localhost:${s.port}`,
          viaGateway: `http://localhost:8080/api/v1/${s.name.replace('-service', '')}`
        }))
      };

      await Generation.updateOne({ jobId }, {
        status: 'complete', progress: 100,
        gatewayUrl: allUrls.gateway, frontendUrl: allUrls.frontend, allUrls
      });

      this.io.to(jobId).emit('generation:complete', { jobId, urls: allUrls });
      await this._log(jobId, 'Orchestrator', '\n✅ Done! Your app is ready:', 'success');
      await this._log(jobId, 'Orchestrator', `  🌐 Gateway (all services): http://localhost:8080`, 'success');
      await this._log(jobId, 'Orchestrator', `  🎨 Frontend (direct):      http://localhost:${frontendPort}`, 'success');
      for (const svc of runningServices) {
        await this._log(jobId, 'Orchestrator', `  ⚙️  ${svc.name}:   http://localhost:${svc.port}/api-docs`, 'success');
      }

      return await Generation.findOne({ jobId });

    } catch (err) {
      console.error('[Orchestrator] Fatal:', err);
      await this._log(jobId, 'Orchestrator', `Fatal error: ${err.message}`, 'error');
      await Generation.updateOne({ jobId }, { status: 'error', error: err.message });
      this.io.to(jobId).emit('generation:error', { jobId, error: err.message });
      throw err;
    }
  }

  // ── AGENTS.md Generator ───────────────────────────────────────────────────
  _generateAgentsMd(plan, appDir) {
    const services = plan.services || [];
    const frontendPort = plan.frontend?.port || 5173;
    const projectName = plan.projectName || 'generated-app';

    const serviceList = services.map(s =>
      `- **${s.name}** (port ${s.port}): ${s.description || ''}`
    ).join('\n');

    const envList = services.map(s => {
      const key = s.name.replace(/-service$/, '').replace(/-/g, '_').toUpperCase();
      return `- \`${s.name}/.env\` — MONGO_URL, SEKRET_KEY, PORT=${s.port}, SERVER_URL=http://localhost:${s.port}`;
    }).join('\n');

    const startOrder = services.map((s, i) =>
      `${i + 1}. \`cd ${s.name} && npm start\` (port ${s.port})`
    ).concat([
      `${services.length + 1}. \`cd frontend && npm run dev\` (port ${frontendPort})`,
      `${services.length + 2}. \`cd gateway && npm start\` (port 8080)`
    ]).join('\n');

    return `# AGENTS.md — Project Guidance for AI Agents

> This file tells AI agents (Claude Code, Codex, Copilot, etc.) how to work with this project.
> Generated by the MERN Code Developer Agent on ${new Date().toISOString().split('T')[0]}.

## Project Overview

**Name**: ${projectName}
**Description**: ${plan.description || ''}
**Stack**: Node.js + Express (ES Modules) | MongoDB + Mongoose | React + Vite + Tailwind CSS v3

## Architecture

\`\`\`
${projectName}/
${services.map(s => `├── ${s.name}/          # port ${s.port}`).join('\n')}
├── frontend/           # port ${frontendPort} (Vite React)
└── gateway/            # port 8080 (API proxy)
\`\`\`

## Services

${serviceList}
- **frontend** (port ${frontendPort}): React + Vite + Tailwind CSS v3
- **gateway** (port 8080): http-proxy-middleware reverse proxy

## Critical Rules for AI Agents

### Backend (Node.js/Express)
- **ES Modules ONLY** — use \`import/export\`, NEVER \`require/module.exports\`
- **Entry point**: \`Server.js\` (not \`index.js\` or \`src/index.js\`)
- **DB connection**: \`import { connectToDatabase } from "./DbConnection.js"\`
- **Env vars**: \`MONGO_URL\` (not MONGODB_URI), \`SEKRET_KEY\` (not JWT_SECRET)
- **All imports** must include \`.js\` extension: \`import X from "./models/X.js"\`
- **Auth helpers**: \`checkHasAccount(req)\`, \`checkAdmin(req)\` in \`controllers/authController.js\`

### Frontend (React/Vite)
- **NEVER use** \`<Outlet />\` from react-router-dom
- **Route pattern**: App.jsx uses flat groups (\`<Route path="/*" element={<HomePage />} />\`)
- Each page group (HomePage, AdminPage) owns its own \`<Routes>\` with nested \`<Route>\`
- **Tailwind v3** PostCSS — do NOT use \`@import "tailwindcss"\` (v4 syntax)
- **API calls**: \`import.meta.env.VITE_SERVICE_URL\` + full path e.g. \`/api/v1/tasks\`
- **Token**: \`localStorage.setItem("token", token)\` then \`Authorization: Bearer <token>\`

### Shared
- All services share the same \`SEKRET_KEY\` — JWT tokens work across all services
- API prefix: \`/api/v1/{resource}\`
- Swagger docs: \`http://localhost:{port}/api-docs\`
- Health check: \`http://localhost:{port}/health\`

## Environment Variables

${envList}
- \`frontend/.env\` — VITE_SERVICE_URL per service

## How to Start (in order)

${startOrder}

## How to Modify This Project

### Add a new API route (backend)
1. Create controller: \`{service}/controllers/{name}Controller.js\`
2. Create route: \`{service}/routes/{name}Routes.js\`
3. Mount in Server.js: \`import {name}Router from "./routes/{name}Routes.js"\` + \`app.use("/api/v1/{resource}", {name}Router)\`
4. Add Swagger JSDoc above the route handler

### Add a new frontend page
1. Decide route group: **HomePage** (public) or **AdminPage** (protected)
2. Create: \`frontend/src/pages/{group}/{PageName}.jsx\`
3. Add \`<Route path="/{page}" element={<PageName />} />\` inside that group's \`<Routes>\`
4. Add nav link in the appropriate header or sidebar component

## Do NOT modify
- \`frontend/vite.config.js\` — hardcoded by team template (port 5173, no Tailwind plugin)
- \`frontend/tailwind.config.js\` — hardcoded team color palette
- \`frontend/postcss.config.js\` — Tailwind v3 PostCSS config
- \`gateway/index.js\` — auto-generated proxy config

## Import This in Claude Code

\`\`\`
@${appDir.replace(/\\/g, '/')}/AGENTS.md
\`\`\`
`;
  }

  // ── BUG.md Generator ──────────────────────────────────────────────────────
  _generateBugMd(plan, staticIssues, aiIssues, jobId) {
    const date = new Date().toISOString().split('T')[0];
    const totalBugs = (staticIssues || []).length + (aiIssues || []).length;

    const staticSection = (staticIssues || []).length > 0
      ? (staticIssues || []).map((i, n) =>
          `### Bug ${n + 1}: ${i.name || 'Unknown'}\n- **File**: \`${i.filePath || 'unknown'}\`\n- **Severity**: ${i.severity || 'unknown'}\n- **Category**: ${i.category || 'unknown'}\n- **Description**: ${i.message || ''}\n- **Auto-fixed**: ${i.autoFix ? '✅ Yes' : '❌ No (manual fix needed)'}`
        ).join('\n\n')
      : '*No static analysis bugs found.*';

    const aiSection = (aiIssues || []).length > 0
      ? (aiIssues || []).slice(0, 20).map((issue, n) =>
          `### AI Bug ${n + 1}\n- **Description**: ${issue}`
        ).join('\n\n')
      : '*No additional bugs found by AI review.*';

    return `# BUG.md — Generation Bug Report

> **Job ID**: \`${jobId}\`
> **Project**: ${plan.projectName || 'unknown'}
> **Generated**: ${date}
> **Total bugs found**: ${totalBugs}

This file lists all bugs detected during code generation and the fixes applied.
It is generated automatically by the MERN Code Developer Agent.

## Summary

| Category | Count |
|----------|-------|
| Static analysis bugs | ${(staticIssues || []).length} |
| AI review bugs | ${(aiIssues || []).length} |
| **Total** | **${totalBugs}** |

---

## Static Analysis Bugs (Layer 1)

${staticSection}

---

## AI Review Bugs (Layer 2 — ${(aiIssues || []).length > 0 ? 'up to 5 rounds' : '0 rounds needed'})

${aiSection}

---

## Common Bug Prevention Rules

Based on bugs found in this generation:

1. **ES Module imports** — always include \`.js\` extension
2. **bcryptjs not bcrypt** — bcrypt needs native compilation, breaks on Windows
3. **MONGO_URL not MONGODB_URI** — team env var naming convention
4. **SEKRET_KEY not JWT_SECRET** — team env var naming convention
5. **No \`<Outlet />\`** — use nested \`<Routes><Route>\` inside each page group
6. **package.json JSON only** — no HTML comments, no JS comments, no markdown
7. **Server.js not index.js** — ES module entry point convention

---

*Report generated by MERN Code Developer Agent — ${date}*
`;
  }

  async _updateStatus(jobId, status, progress, agent) {
    await Generation.updateOne({ jobId }, { status, progress, currentAgent: agent });
    this.io.to(jobId).emit('status:update', { status, progress, agent });
  }

  async _updateProgress(jobId, progress) {
    await Generation.updateOne({ jobId }, { progress });
    this.io.to(jobId).emit('progress:update', { progress });
  }

  async _log(jobId, agent, message, type = 'info') {
    console.log(`[${agent}] ${message}`);
    this.io.to(jobId).emit('log', { level: type, agent, message, timestamp: new Date().toISOString() });
    await Generation.updateOne(
      { jobId },
      { $push: { logs: { agent, message, type, timestamp: new Date() } } }
    );
  }
}

module.exports = GenerationOrchestrator;
