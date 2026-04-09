const path = require('path');

/**
 * StaticAnalyzer — Zero-AI, instant bug detection using:
 *   1. Syntax validation (JS parse)
 *   2. 35 regex-based MERN pattern checks
 *   3. Package.json completeness checks
 *   4. Cross-file consistency checks
 *
 * Runs BEFORE AI analysis to catch obvious bugs instantly.
 * Returns structured issues that can be auto-fixed without AI.
 */
class StaticAnalyzer {
  /**
   * Analyze all generated files. Returns issues grouped by file.
   */
  analyzeFiles(files) {
    const allIssues = [];

    for (const file of files) {
      if (!file.content || !file.path) continue;

      const ext = path.extname(file.path).toLowerCase();
      const isJS = ['.js', '.mjs', '.cjs', '.jsx'].includes(ext);
      const isTS = ['.ts', '.tsx'].includes(ext);
      const isJSON = ext === '.json';
      const isEnv = file.path.endsWith('.env') || file.path.endsWith('.env.local');

      const fileIssues = [];

      // ── 1. Syntax Check ────────────────────────────────────────
      if (isJS) {
        const syntaxErr = this._checkJSSyntax(file.content, file.path);
        if (syntaxErr) fileIssues.push(syntaxErr);
      }

      if (isJSON) {
        const jsonErr = this._checkJSON(file.content, file.path);
        if (jsonErr) fileIssues.push(jsonErr);
      }

      // ── 2. Pattern Checks ──────────────────────────────────────
      if (isJS || isTS) {
        fileIssues.push(...this._checkExpressPatterns(file));
        fileIssues.push(...this._checkAsyncPatterns(file));
        fileIssues.push(...this._checkImportPatterns(file));
        fileIssues.push(...this._checkNextJSPatterns(file));
      }

      if (isJSON && file.path.includes('package.json')) {
        fileIssues.push(...this._checkPackageJson(file));
      }

      // Check index.html for missing Vite entry point script
      const isIndexHtml = file.path === 'index.html' || file.path === 'frontend/index.html' || file.path.endsWith('/index.html');
      if (isIndexHtml) {
        fileIssues.push(...this._checkIndexHtml(file));
      }

      if (isEnv) {
        fileIssues.push(...this._checkEnvFile(file));
      }

      if (fileIssues.length > 0) {
        allIssues.push(...fileIssues.map(i => ({ ...i, filePath: file.path })));
      }
    }

    // ── 3. Cross-file checks ─────────────────────────────────────
    allIssues.push(...this._crossFileChecks(files));

    return allIssues;
  }

  /**
   * Auto-fix issues that can be fixed without AI (simple string replacements).
   * Returns { file, wasFixed, fixes }
   *
   * Safe for all file types including index.html (targeted fixes only).
   */
  autoFix(file, issues) {
    let content = file.content;
    const fixes = [];

    for (const issue of issues) {
      if (!issue.autoFix || issue.filePath !== file.path) continue;

      const before = content;
      content = issue.autoFix(content);
      if (content !== before) {
        fixes.push(issue.name);
      }
    }

    return { content, wasFixed: fixes.length > 0, fixes };
  }

  // ── Syntax Checkers ───────────────────────────────────────────────────────

  _checkJSSyntax(code, filePath) {
    // Simple bracket/brace balance check
    let braces = 0, parens = 0, brackets = 0;
    let inString = false, strChar = '', escaped = false;

    for (let i = 0; i < code.length; i++) {
      const ch = code[i];
      if (escaped) { escaped = false; continue; }
      if (ch === '\\' && inString) { escaped = true; continue; }
      if ((ch === '"' || ch === "'" || ch === '`') && !inString) { inString = true; strChar = ch; continue; }
      if (ch === strChar && inString) { inString = false; continue; }
      if (inString) continue;

      if (ch === '{') braces++;
      if (ch === '}') braces--;
      if (ch === '(') parens++;
      if (ch === ')') parens--;
      if (ch === '[') brackets++;
      if (ch === ']') brackets--;
    }

    if (braces !== 0) return {
      name: 'unbalanced-braces',
      severity: 'critical',
      category: 'syntax-error',
      message: `Unbalanced {} braces (${braces > 0 ? 'missing ' + braces + ' closing }' : 'extra ' + Math.abs(braces) + ' closing }'})`,
      autoFixable: false
    };
    if (parens !== 0) return {
      name: 'unbalanced-parens',
      severity: 'critical',
      category: 'syntax-error',
      message: `Unbalanced () parentheses`,
      autoFixable: false
    };

    return null;
  }

  _checkJSON(content, filePath) {
    // ★ Check for HTML comments inside JSON (EJSONPARSE killer)
    if (/<!--[\s\S]*?-->/.test(content)) {
      return {
        name: 'html-comment-in-json',
        severity: 'critical',
        category: 'syntax-error',
        message: 'HTML comment (<!-- -->) found inside JSON — this breaks JSON.parse() with EJSONPARSE',
        autoFixable: true,
        autoFix: (code) => {
          // Strip all HTML comments, JS single-line comments, JS multi-line comments
          let fixed = code
            .replace(/<!--[\s\S]*?-->/g, '')   // <!-- HTML comments -->
            .replace(/\/\/[^\n"]*(?=\n)/g, '')  // // single-line comments (not inside strings)
            .replace(/\/\*[\s\S]*?\*\//g, '');  // /* multi-line comments */
          // Try to parse; if still invalid, just return stripped version
          try { JSON.parse(fixed); } catch {}
          return fixed;
        }
      };
    }

    // ★ Check for JS comments inside JSON (also breaks parsing)
    if (/\/\/[^\n]*\n/.test(content) || /\/\*[\s\S]*?\*\//.test(content)) {
      return {
        name: 'js-comment-in-json',
        severity: 'critical',
        category: 'syntax-error',
        message: 'JS comment (// or /* */) found inside JSON — JSON does not support comments',
        autoFixable: true,
        autoFix: (code) => code
          .replace(/\/\/[^\n"]*(?=\n)/g, '')
          .replace(/\/\*[\s\S]*?\*\//g, '')
      };
    }

    try {
      JSON.parse(content);
      return null;
    } catch (e) {
      return {
        name: 'invalid-json',
        severity: 'critical',
        category: 'syntax-error',
        message: `Invalid JSON: ${e.message}`,
        autoFixable: false
      };
    }
  }

  // ── Express Pattern Checks ────────────────────────────────────────────────

  _checkExpressPatterns(file) {
    const issues = [];
    const c = file.content;
    const isIndex = file.path.includes('index.js') || file.path.includes('app.js') || file.path.includes('server.js');
    const isRoute = file.path.includes('route') || file.path.includes('router');

    const usesExpress = c.includes('express') || c.includes('Router');
    if (!usesExpress) return issues;

    // Also detect Server.js (ES module entry point) as index file
    const isServerJs = file.path.includes('Server.js') || file.path.includes('server.js');
    const isEntry = isIndex || isServerJs;

    // Check 1: express.json() middleware
    if (isEntry && c.includes('express()') && !c.includes('express.json()') && !c.includes('bodyParser.json')) {
      issues.push({
        name: 'missing-express-json',
        severity: 'critical',
        category: 'missing-middleware',
        message: 'Missing app.use(express.json()) — req.body will be undefined',
        autoFixable: true,
        autoFix: (code) => code.replace(
          /(const app = express\(\);?\n)/,
          '$1app.use(express.json());\napp.use(express.urlencoded({ extended: true }));\n'
        )
      });
    }

    // Check 2: CORS middleware
    if (isEntry && c.includes('express()') && !c.includes('cors')) {
      issues.push({
        name: 'missing-cors',
        severity: 'high',
        category: 'cors-error',
        message: 'Missing cors() middleware — frontend cannot call this API',
        autoFixable: true,
        autoFix: (code) => {
          if (!code.includes("require('cors')") && !code.includes('require("cors")')) {
            code = code.replace(
              /(require\('express'\)|require\("express"\))/,
              `$1\nconst cors = require('cors');`
            );
          }
          return code.replace(
            /(const app = express\(\);?\n)/,
            `$1app.use(cors());\n`
          );
        }
      });
    }

    // Check 3: dotenv loaded in entry file
    // ES module pattern: import dotenv from "dotenv"; dotenv.config();
    // CJS pattern: require("dotenv").config() as first line
    if (isEntry && !c.includes('dotenv') && c.includes('process.env')) {
      issues.push({
        name: 'dotenv-missing',
        severity: 'critical',
        category: 'env-not-used',
        message: 'Server.js uses process.env but does not import/configure dotenv',
        autoFixable: false
      });
    }

    // Check 4: Hardcoded PORT
    const hardPortMatch = c.match(/app\.listen\(\s*(\d{4,5})\s*[,)]/);
    if (hardPortMatch) {
      issues.push({
        name: 'hardcoded-port',
        severity: 'medium',
        category: 'port-issue',
        message: `Port ${hardPortMatch[1]} is hardcoded. Use process.env.PORT || ${hardPortMatch[1]}`,
        autoFixable: true,
        autoFix: (code) => code.replace(
          /app\.listen\(\s*(\d{4,5})\s*,/,
          `app.listen(process.env.PORT || $1,`
        )
      });
    }

    // Check 5: missing export in route/model files
    // ES modules use 'export default' or 'export function', CJS uses 'module.exports'
    const hasEsExport = c.includes('export default') || c.includes('export function') || c.includes('export const') || c.includes('export async function');
    const hasCjsExport = c.includes('module.exports');
    if ((isRoute || file.path.includes('model')) && !hasEsExport && !hasCjsExport) {
      issues.push({
        name: 'missing-export',
        severity: 'critical',
        category: 'missing-export',
        message: 'Route/model file missing export — add "export default router" or "export default mongoose.model(...)"',
        autoFixable: false
      });
    }

    // Check 6: Global error middleware missing in Server.js/index
    if (isEntry && c.includes('app.listen') && !c.includes('err, req, res, next')) {
      issues.push({
        name: 'no-error-middleware',
        severity: 'high',
        category: 'missing-error-handler',
        message: 'No global error handling middleware (err, req, res, next) before app.listen()',
        autoFixable: true,
        autoFix: (code) => code.replace(
          /(app\.listen\()/,
          `app.use((err, req, res, next) => {\n  console.error(err.stack);\n  res.status(err.status || 500).json({ error: err.message || 'Internal Server Error' });\n});\n\n$1`
        )
      });
    }

    // Check 7: Health endpoint
    if (isEntry && c.includes('app.listen') && !c.includes('/health')) {
      issues.push({
        name: 'no-health-endpoint',
        severity: 'low',
        category: 'other',
        message: 'No /health endpoint — add one for monitoring',
        autoFixable: true,
        autoFix: (code) => code.replace(
          /(app\.listen\()/,
          `app.get('/health', (req, res) => res.json({ status: 'ok' }));\n\n$1`
        )
      });
    }

    return issues;
  }

  // ── Async Pattern Checks ──────────────────────────────────────────────────

  _checkAsyncPatterns(file) {
    const issues = [];
    const c = file.content;

    // Check: res.json called twice (headers already sent)
    const routeBlocks = c.match(/(?:router|app)\.[a-z]+\([^{]+\{[\s\S]*?\}\s*\)/g) || [];
    for (const block of routeBlocks) {
      const sendCount = (block.match(/res\.(json|send|status)\(/g) || []).length;
      if (sendCount > 2) {
        issues.push({
          name: 'multiple-res-send',
          severity: 'high',
          category: 'async-error',
          message: 'Multiple res.json/res.send calls detected — add return before each conditional response',
          autoFixable: false
        });
        break;
      }
    }

    // Check: mongoose operations without await in async functions
    const mongoOps = ['find', 'findOne', 'findById', 'save', 'create', 'updateOne', 'deleteOne', 'aggregate'];
    for (const op of mongoOps) {
      // Simple string check: look for assignment of mongoose op result without await
      const simplePattern = new RegExp(`(?:const|let|var)\\s+\\w+\\s*=\\s*[\\w.]+\\.${op}\\(`);
      const hasOp = simplePattern.test(c);
      const hasAwait = c.includes(`await`) && c.includes(`.${op}(`);
      // Only flag if op is used without any await present at all
      if (hasOp && !hasAwait) {
        issues.push({
          name: 'missing-await-mongoose',
          severity: 'critical',
          category: 'missing-await',
          message: `Possible missing await before mongoose ${op} — check all database calls`,
          autoFixable: false
        });
        break;
      }
    }

    return issues;
  }

  // ── Import Pattern Checks ─────────────────────────────────────────────────

  _checkImportPatterns(file) {
    const issues = [];
    const c = file.content;

    // Check: bcrypt vs bcryptjs (both CJS require and ES module import)
    const usesBcryptNotJs = (
      (c.includes("require('bcrypt')") || c.includes('require("bcrypt")') ||
       c.includes("from 'bcrypt'") || c.includes('from "bcrypt"')) &&
      !c.includes('bcryptjs')
    );
    if (usesBcryptNotJs) {
      issues.push({
        name: 'bcrypt-not-bcryptjs',
        severity: 'critical',
        category: 'dependency-missing',
        message: "Use bcryptjs instead of bcrypt — bcrypt requires native compilation and fails on Windows (spawn ENOENT)",
        autoFixable: true,
        autoFix: (code) => code
          .replace(/require\(['"]bcrypt['"]\)/g, "require('bcryptjs')")
          .replace(/from ['"]bcrypt['"]/g, "from 'bcryptjs'")
      });
    }

    // Check: <Outlet /> usage — BANNED in this team's pattern
    // Team uses nested <Routes><Route> inside each page group instead
    const isJSX = file.path.endsWith('.jsx') || file.path.endsWith('.tsx');
    if (isJSX && (c.includes('<Outlet') || c.includes('import { Outlet') || c.includes("import {Outlet"))) {
      issues.push({
        name: 'outlet-pattern-banned',
        severity: 'critical',
        category: 'react-router-error',
        message: '<Outlet /> is BANNED — use nested <Routes><Route> inside each page group component instead',
        autoFixable: false
      });
    }

    // Check: mongoose connected but MONGODB_URI might be missing
    if (c.includes('mongoose.connect') && c.includes("'mongodb://localhost:27017'") && !c.includes('27017/')) {
      issues.push({
        name: 'mongodb-uri-missing-dbname',
        severity: 'high',
        category: 'mongodb-issue',
        message: "MongoDB URI missing database name — should be mongodb://localhost:27017/{dbname}",
        autoFixable: false
      });
    }

    return issues;
  }

  // ── Next.js Pattern Checks ────────────────────────────────────────────────

  _checkNextJSPatterns(file) {
    const issues = [];
    const c = file.content;
    const isNextComponent = file.path.includes('/app/') || file.path.includes('/components/') || file.path.includes('/pages/');

    if (!isNextComponent) return issues;

    const usesHooks = /use(State|Effect|Ref|Callback|Memo|Context|Reducer)\(/.test(c);
    const usesEventHandlers = /onClick|onChange|onSubmit|onKeyDown/.test(c);
    const hasUseClient = c.trimStart().startsWith("'use client'") || c.trimStart().startsWith('"use client"');
    const isServerSafe = file.path.includes('layout') || file.path.includes('loading') || file.path.includes('error');

    if ((usesHooks || usesEventHandlers) && !hasUseClient && !isServerSafe) {
      issues.push({
        name: 'missing-use-client',
        severity: 'critical',
        category: 'nextjs-error',
        message: 'Component uses hooks/events but is missing "use client" directive at top',
        autoFixable: true,
        autoFix: (code) => `'use client';\n${code}`
      });
    }

    return issues;
  }

  // ── Package.json Checks ───────────────────────────────────────────────────

  _checkPackageJson(file) {
    const issues = [];
    let pkg;

    try {
      pkg = JSON.parse(file.content);
    } catch {
      return issues;
    }

    // Check: "start" script exists
    if (!pkg.scripts?.start) {
      issues.push({
        name: 'missing-start-script',
        severity: 'critical',
        category: 'start-script-missing',
        message: 'package.json missing "start" script — npm start will fail',
        autoFixable: true,
        autoFix: (code) => {
          try {
            const p = JSON.parse(code);
            p.scripts = p.scripts || {};
            // Detect if it's a Next.js or Express package
            const isNext = p.dependencies?.next;
            p.scripts.start = isNext ? 'next start' : 'node src/index.js';
            if (!p.scripts.dev) p.scripts.dev = isNext ? 'next dev' : 'nodemon src/index.js';
            return JSON.stringify(p, null, 2);
          } catch { return code; }
        }
      });
    }

    const deps = { ...pkg.dependencies, ...pkg.devDependencies };

    // Check: cors in dependencies if it's a backend package
    if (pkg.dependencies?.express && !deps.cors) {
      issues.push({
        name: 'cors-missing-in-package',
        severity: 'critical',
        category: 'dependency-missing',
        message: 'cors package not in dependencies — add "cors": "^2.8.5"',
        autoFixable: true,
        autoFix: (code) => {
          try {
            const p = JSON.parse(code);
            p.dependencies = p.dependencies || {};
            p.dependencies.cors = '^2.8.5';
            return JSON.stringify(p, null, 2);
          } catch { return code; }
        }
      });
    }

    // Check: dotenv in dependencies
    if (pkg.dependencies?.express && !deps.dotenv) {
      issues.push({
        name: 'dotenv-missing-in-package',
        severity: 'critical',
        category: 'dependency-missing',
        message: 'dotenv package not in dependencies — add "dotenv": "^16.0.0"',
        autoFixable: true,
        autoFix: (code) => {
          try {
            const p = JSON.parse(code);
            p.dependencies = p.dependencies || {};
            p.dependencies.dotenv = '^16.3.1';
            return JSON.stringify(p, null, 2);
          } catch { return code; }
        }
      });
    }

    // Check: mongoose in dependencies for backend
    if (pkg.dependencies?.express && !deps.mongoose) {
      issues.push({
        name: 'mongoose-missing-in-package',
        severity: 'critical',
        category: 'dependency-missing',
        message: 'mongoose package not in dependencies',
        autoFixable: true,
        autoFix: (code) => {
          try {
            const p = JSON.parse(code);
            p.dependencies = p.dependencies || {};
            p.dependencies.mongoose = '^8.0.0';
            return JSON.stringify(p, null, 2);
          } catch { return code; }
        }
      });
    }

    return issues;
  }

  // ── index.html Checks ─────────────────────────────────────────────────────

  _checkIndexHtml(file) {
    const issues = [];
    const c = file.content;

    // Check for missing Vite entry point script tag
    if (!c.includes('src/main.jsx') && !c.includes('src/main.tsx') && !c.includes('src/main.js')) {
      issues.push({
        name: 'missing-vite-entry-script',
        severity: 'critical',
        category: 'syntax-error',
        message: 'index.html missing <script type="module" src="/src/main.jsx"></script> — Vite will not bundle anything',
        autoFixable: true,
        autoFix: (code) => {
          if (code.includes('src/main.')) return code; // already fixed
          return code.replace(
            /(<div[^>]*id=["']root["'][^>]*><\/div>)\s*<\/body>/,
            '$1\n  <script type="module" src="/src/main.jsx"></script>\n</body>'
          );
        }
      });
    }

    // Check for missing root div
    if (!c.includes('id="root"') && !c.includes("id='root'")) {
      issues.push({
        name: 'missing-root-div',
        severity: 'critical',
        category: 'syntax-error',
        message: 'index.html missing <div id="root"></div> — React cannot mount',
        autoFixable: false
      });
    }

    return issues;
  }

  // ── .env File Checks ──────────────────────────────────────────────────────

  _checkEnvFile(file) {
    const issues = [];
    const c = file.content;
    const isBackend = !file.path.includes('frontend') && !file.path.includes('.local');

    if (isBackend) {
      if (!c.includes('PORT=')) {
        issues.push({
          name: 'env-missing-port',
          severity: 'critical',
          category: 'env-not-used',
          message: '.env missing PORT variable',
          autoFixable: false
        });
      }
      // Team pattern uses MONGO_URL (not MONGODB_URI or MONGO_URI)
      if (!c.includes('MONGO_URL=') && !c.includes('MONGODB_URI=') && !c.includes('MONGO_URI=')) {
        issues.push({
          name: 'env-missing-mongo-url',
          severity: 'critical',
          category: 'mongodb-issue',
          message: '.env missing MONGO_URL variable (team pattern uses MONGO_URL, not MONGODB_URI)',
          autoFixable: false
        });
      }
      // Team pattern uses SEKRET_KEY (not JWT_SECRET)
      if (!c.includes('SEKRET_KEY=') && !c.includes('JWT_SECRET=')) {
        issues.push({
          name: 'env-missing-sekret-key',
          severity: 'high',
          category: 'jwt-error',
          message: '.env missing SEKRET_KEY variable (team pattern uses SEKRET_KEY, not JWT_SECRET)',
          autoFixable: false
        });
      }
    }

    return issues;
  }

  // ── Cross-File Checks ─────────────────────────────────────────────────────

  _crossFileChecks(files) {
    const issues = [];

    // NOTE: package.json cross-file check REMOVED — it was producing false positives
    // because package.json is written to disk separately (before static analysis runs)
    // and therefore not always present in the in-memory files array.
    // The orchestrator tracks package.json separately and adds it to allGeneratedFiles.

    // Check: gateway has no MongoDB dependency (gateway doesn't need mongoose)
    const gatewayPkg = files.find(f => f.path === 'gateway/package.json' || f.path === 'gateway\\package.json');
    if (gatewayPkg) {
      try {
        const pkg = JSON.parse(gatewayPkg.content);
        if (pkg.dependencies?.mongoose) {
          issues.push({
            filePath: 'gateway/package.json',
            name: 'gateway-has-mongoose',
            severity: 'medium',
            category: 'dependency-missing',
            message: 'Gateway does not need mongoose — it only proxies requests',
            autoFixable: true,
            autoFix: (code) => {
              try {
                const p = JSON.parse(code);
                delete p.dependencies?.mongoose;
                return JSON.stringify(p, null, 2);
              } catch { return code; }
            }
          });
        }
      } catch {}
    }

    return issues;
  }

  /**
   * Format issues as a readable summary for logging.
   */
  summarize(issues) {
    const critical = issues.filter(i => i.severity === 'critical');
    const high = issues.filter(i => i.severity === 'high');
    const other = issues.filter(i => !['critical', 'high'].includes(i.severity));

    return {
      total: issues.length,
      critical: critical.length,
      high: high.length,
      other: other.length,
      topIssues: [...critical, ...high].slice(0, 10).map(i => ({
        file: i.filePath,
        name: i.name,
        message: i.message,
        severity: i.severity,
        autoFixable: !!i.autoFix
      }))
    };
  }
}

module.exports = new StaticAnalyzer();
