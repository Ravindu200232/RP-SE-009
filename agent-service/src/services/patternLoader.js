const fs = require('fs-extra');
const path = require('path');

const TEMPLATES_DIR = path.resolve(__dirname, '../../templates');

/**
 * PatternLoader — reads the 4 team template pattern files and injects
 * them into AI developer prompts so generated code always matches the
 * team's established MERN microservice pattern.
 *
 * Files read from agent-service/templates/:
 *   MICROSERVICE_PATTERN.md  — backend Server.js, DbConnection.js, routes, models
 *   FRONTEND_PATTERN.md      — App.jsx, BrowserRouter, route groups, localStorage JWT
 *   LOCAL_RUN_PATTERN.md     — ports, .env, startup order
 *   UI_DESIGN_PATTERN.md     — Tailwind colors, fonts, buttons, cards, hero, sidebar
 */
class PatternLoader {
  constructor() {
    this._cache = {};
  }

  /** Read a single pattern file (cached after first read). */
  async load(filename) {
    if (this._cache[filename]) return this._cache[filename];
    const filePath = path.join(TEMPLATES_DIR, filename);
    try {
      const content = await fs.readFile(filePath, 'utf8');
      this._cache[filename] = content;
      return content;
    } catch {
      console.warn(`[PatternLoader] Could not read ${filename}`);
      return '';
    }
  }

  /** Returns a concise backend injection block for developer prompts. */
  async backendPatternPrompt() {
    const raw = await this.load('MICROSERVICE_PATTERN.md');
    if (!raw) return '';

    // Extract only the critical sections (keep prompt size manageable)
    const sections = this._extractSections(raw, [
      '## 3. Backend Library Pattern',
      '## 4. Standard Backend Service Pattern',
      '## 5. Auth Helper Pattern',
      '## 6. JWT Token Pattern',
      '## 7. Controller Pattern',
      '## 8. Route Pattern',
      '## 9. MongoDB Model Pattern',
      '## 10. Inter-Service Communication Pattern',
      '## 16. Environment Variable Pattern',
      '## 19. AI Prompt You Can Reuse'
    ]);

    return `\n\n${'='.repeat(60)}\nTEAM TEMPLATE PATTERN — BACKEND (follow exactly)\n${'='.repeat(60)}\n${sections}\n${'='.repeat(60)}\n`;
  }

  /** Returns a concise frontend injection block for developer prompts. */
  async frontendPatternPrompt() {
    const [frontend, ui, local] = await Promise.all([
      this.load('FRONTEND_PATTERN.md'),
      this.load('UI_DESIGN_PATTERN.md'),
      this.load('LOCAL_RUN_PATTERN.md')
    ]);

    const frontendSections = this._extractSections(frontend, [
      '## 2. `main.jsx` Pattern',
      '## 3. `App.jsx` Pattern',
      '## 4. `BrowserRouter` Pattern',
      '## 5. Route Group Pattern',
      '## 6. Nested Routes Pattern',
      '## 9. Protected Layout Pattern',
      '## 10. API Call Pattern',
      '## 11. Form Page Pattern',
      '## 12. State And Storage Pattern',
      '## 15. Reusable Build Prompt For Another AI'
    ]);

    const uiSections = this._extractSections(ui, [
      '## 1. Core Visual Direction',
      '## 2. Color Pattern',
      '## 3. Typography Pattern',
      '## 6. Button Pattern',
      '## 7. Card / Box Pattern',
      '## 8. Table Pattern',
      '## 9. Sidebar Pattern',
      '## 10. Hero Section Pattern',
      '## 17. UI Prompt For Another AI'
    ]);

    const localSections = this._extractSections(local, [
      '## 2. Required Local Ports',
      '## 3. Local Environment Setup',
      '## 4. Client `.env` For Local Run'
    ]);

    return `\n\n${'='.repeat(60)}\nTEAM TEMPLATE PATTERN — FRONTEND (follow exactly)\n${'='.repeat(60)}\n${frontendSections}\n\n--- UI DESIGN ---\n${uiSections}\n\n--- PORTS & ENV ---\n${localSections}\n${'='.repeat(60)}\n`;
  }

  /**
   * Generate the SKILL.md file content for a completed generation.
   * This is written to the generated app root as a Claude Code importable skill.
   *
   * @param {Object} plan       — the planner output (services, frontend, etc.)
   * @param {string} appDir     — absolute path to the generated app
   * @param {string} jobId      — generation job ID
   * @returns {string}          — markdown content for SKILL.md
   */
  generateSkillFile(plan, appDir, jobId) {
    const services = plan.services || [];
    const frontendPort = plan.frontend?.port || 5173;
    const projectName = plan.projectName || 'my-app';
    const description = plan.description || '';
    const sharedSecret = plan.sharedEnv?.SEKRET_KEY || 'shared_secret_key_change_in_production';
    const mongoUrl = plan.sharedEnv?.MONGO_URL || `mongodb://localhost:27017/${projectName}`;

    const serviceEnvVars = services
      .map(s => {
        const key = s.name.replace(/-service$/, '').replace(/-/g, '_').toUpperCase();
        return `VITE_${key}_SERVICE_URL=http://localhost:${s.port}`;
      })
      .join('\n');

    const runSection = services
      .map((s, i) => `### Terminal ${i + 1} — ${s.name} (port ${s.port})\n\`\`\`bash\ncd ${s.name}\nnpm start\n\`\`\``)
      .join('\n\n') +
      `\n\n### Terminal ${services.length + 1} — Frontend (port ${frontendPort})\n\`\`\`bash\ncd frontend\nnpm run dev\n\`\`\``;

    const routesSection = services.map(s => {
      const routes = (s.routes || []).map(r => `| \`${r.method}\` | \`${r.path}\` | ${r.description || ''} |`).join('\n');
      return `### ${s.name} — http://localhost:${s.port}\n\n| Method | Path | Description |\n|--------|------|-------------|\n${routes || '| GET | /health | Health check |'}`;
    }).join('\n\n');

    const envSection = services.map(s => {
      const extra = (s.interServiceCalls || []).map(dep => {
        const depSvc = services.find(sv => sv.name === dep);
        if (!depSvc) return '';
        const key = dep.replace(/-service$/, '').replace(/-/g, '_').toUpperCase();
        return `${key}_SERVICE_URL=http://localhost:${depSvc.port}`;
      }).filter(Boolean).join('\n');

      return `### ${s.name}/.env\n\`\`\`env\nMONGO_URL=${mongoUrl}\nSEKRET_KEY=${sharedSecret}\nPORT=${s.port}\nSERVER_URL=http://localhost:${s.port}\nNODE_ENV=development${extra ? '\n' + extra : ''}\n\`\`\``;
    }).join('\n\n');

    return `# ${projectName} — Generated App Skill

> **Job ID**: \`${jobId}\`
> **App directory**: \`${appDir}\`
> **Generated**: ${new Date().toISOString().split('T')[0]}

## Overview

${description}

**Stack**: Node.js + Express (ES Modules) | MongoDB + Mongoose | React + Vite + Tailwind CSS v3

## Architecture

\`\`\`
${projectName}/
${services.map(s => `├── ${s.name}/          # port ${s.port}`).join('\n')}
├── frontend/           # port ${frontendPort} (Vite dev)
└── gateway/            # port 8080 (API gateway)
\`\`\`

## Services & API Routes

${routesSection}

## How to Run

> All services use ES Modules (\`type: "module"\`). Entry point is \`Server.js\`, not \`index.js\`.

${runSection}

### Terminal ${services.length + 2} — API Gateway (port 8080)
\`\`\`bash
cd gateway
npm start
\`\`\`

## Environment Variables

> **All services share the same \`SEKRET_KEY\`** — JWT tokens issued by one service work in all others.

${envSection}

### frontend/.env
\`\`\`env
${serviceEnvVars}
\`\`\`

## Auth Pattern

1. Login via \`POST /api/v1/users/login\` → receive \`token\`
2. Store: \`localStorage.setItem("token", token)\`
3. Send to every protected request:
   \`\`\`
   Authorization: Bearer <token>
   \`\`\`

All services verify using the shared \`SEKRET_KEY\`. Role is embedded in the JWT:
- \`req.user.role\` → \`"admin"\` | \`"customer"\` | \`"restaurant"\` | \`"delivery"\`

Role helpers in every service (\`controllers/authController.js\`):
\`\`\`js
checkHasAccount(req)   // any logged-in user
checkAdmin(req)        // role === "admin"
checkCustomer(req)     // role === "customer"
checkRestaurant(req)   // role === "restaurant"
checkDelivery(req)     // role === "delivery"
\`\`\`

## Swagger API Docs (running locally)

${services.map(s => `- **${s.name}**: http://localhost:${s.port}/api-docs`).join('\n')}

## Health Checks

${services.map(s => `- http://localhost:${s.port}/health`).join('\n')}
- http://localhost:8080/health (gateway)

## How to Add a New Route

1. Create controller function in \`{service}/controllers/{name}Controller.js\`
2. Create route file in \`{service}/routes/{name}Routes.js\`
3. Mount in \`{service}/Server.js\`: \`app.use("/api/v1/{resource}", {name}Router)\`
4. Add Swagger JSDoc comment above the route

## How to Add a New Frontend Page

1. Decide the page group: **HomePage** (public), **AdminPage**, or role-specific page
2. Create file: \`frontend/src/pages/{group}/{PageName}.jsx\`
3. Add route inside that group component's \`<Routes>\` block
4. Add nav \`<Link>\` in the appropriate header or sidebar

## Template Pattern

This app was generated using the team MERN template pattern:
- **Backend**: \`MICROSERVICE_PATTERN.md\`
- **Frontend**: \`FRONTEND_PATTERN.md\` + \`UI_DESIGN_PATTERN.md\`
- **Local run**: \`LOCAL_RUN_PATTERN.md\`

Import this skill in Claude Code to get full context:
\`\`\`
@${appDir.replace(/\\/g, '/')}/SKILL.md
\`\`\`
`;
  }

  /**
   * Extract specific sections from a markdown file by heading.
   * Keeps only the requested headings and their content.
   */
  _extractSections(markdown, headings) {
    if (!markdown) return '';
    const lines = markdown.split('\n');
    const result = [];
    let capturing = false;
    let currentDepth = 0;

    for (const line of lines) {
      const isHeading = headings.some(h => line.startsWith(h) || line.trim() === h.trim());

      if (isHeading) {
        capturing = true;
        currentDepth = (line.match(/^#+/) || [''])[0].length;
        result.push(line);
        continue;
      }

      if (capturing) {
        const lineDepth = (line.match(/^#+/) || [''])[0].length;
        // Stop capturing when we hit a same-or-higher level heading not in our list
        if (lineDepth > 0 && lineDepth <= currentDepth && !headings.some(h => line.startsWith(h))) {
          capturing = false;
          continue;
        }
        result.push(line);
      }
    }

    return result.join('\n').trim();
  }
}

module.exports = new PatternLoader();
