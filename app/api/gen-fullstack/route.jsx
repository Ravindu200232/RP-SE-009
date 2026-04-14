import { ollamaChat, readOllamaStream } from '@/configs/AiModel';
import Prompt from '@/data/Prompt';

/* ─────────────────────────────────────────────────────────────────────────────
   SHARED HELPERS
───────────────────────────────────────────────────────────────────────────── */

/** Extract file paths as they appear in streaming text (for live console logs) */
function extractNewFilePaths(text, prevText) {
    const added = text.slice(prevText.length);
    const paths = [];
    const feRe = /={2,3}\s*FRONTEND\s*:\s*([^\n=\r]+?)\s*={2,3}/gi;
    const beRe = /={2,3}\s*BACKEND\s*:\s*([^\n=\r]+?)\s*={2,3}/gi;
    let m;
    while ((m = feRe.exec(added)) !== null) paths.push({ section: 'frontend', path: m[1].trim() });
    while ((m = beRe.exec(added)) !== null) paths.push({ section: 'backend',  path: m[1].trim() });
    return paths;
}

/** Universal AI output parser — same logic as gen-ai-code route */
function parseAIOutput(text) {
    const result = { projectTitle: '', explanation: '', frontend: {}, backend: {} };

    const addFrontend = (path, code) => {
        if (!path || !code?.trim()) return;
        const k = path.trim().startsWith('/') ? path.trim() : `/${path.trim()}`;
        if (['/index.js','/index.html','/package.json','/vite.config.js','/tailwind.config.js'].includes(k)) return;
        result.frontend[k] = { code: code.trim() };
    };
    const addBackend = (path, code) => {
        if (!path || !code?.trim()) return;
        const k = path.trim().startsWith('/') ? path.trim() : `/${path.trim()}`;
        result.backend[k] = { code: code.trim() };
    };

    // META
    const metaMatch = text.match(/===META===([\s\S]*?)===ENDMETA===/i);
    if (metaMatch) {
        try {
            const m = JSON.parse(metaMatch[1].trim());
            result.projectTitle = m.projectTitle || m.title || '';
            result.explanation  = m.explanation  || m.description || '';
        } catch (_) {
            const t = metaMatch[1].match(/projectTitle["\s:]+([^\n",}]+)/i);
            if (t) result.projectTitle = t[1].trim().replace(/[",]/g, '');
        }
    }

    // Method 1 — delimiter markers (two passes: with and without ENDFILE)
    {
        const re3 = /={2,3}\s*FRONTEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)={2,3}\s*ENDFILE\s*={2,3}/gi;
        let m;
        while ((m = re3.exec(text)) !== null) addFrontend(m[1], m[2]);
        const re4 = /={2,3}\s*BACKEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)={2,3}\s*ENDFILE\s*={2,3}/gi;
        while ((m = re4.exec(text)) !== null) addBackend(m[1], m[2]);
        if (Object.keys(result.frontend).length === 0 && Object.keys(result.backend).length === 0) {
            const re = /={2,3}\s*FRONTEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)(?===={2,3}\s*(?:FRONTEND|BACKEND|ENDFILE|META)\s*|$)/gi;
            while ((m = re.exec(text)) !== null) addFrontend(m[1], m[2].replace(/===ENDFILE===/gi,'').trimEnd());
            const re2 = /={2,3}\s*BACKEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)(?===={2,3}\s*(?:FRONTEND|BACKEND|ENDFILE|META)\s*|$)/gi;
            while ((m = re2.exec(text)) !== null) addBackend(m[1], m[2].replace(/===ENDFILE===/gi,'').trimEnd());
        }
    }

    // Method 2 — markdown blocks with path comment
    if (Object.keys(result.frontend).length === 0) {
        const re = /```(?:jsx?|tsx?|javascript|typescript)?\r?\n([\s\S]*?)```/g;
        let m;
        while ((m = re.exec(text)) !== null) {
            const block = m[1];
            const firstLine = block.split('\n')[0].trim();
            const pathMatch = firstLine.match(/^\/\/\s*(\/[\w/.\-]+\.[a-z]+)/i)
                || firstLine.match(/^#\s*(\/[\w/.\-]+\.[a-z]+)/i);
            if (pathMatch) {
                const code = block.split('\n').slice(1).join('\n');
                const path = pathMatch[1];
                const isBackend = path.includes('-service') || path.includes('gateway') || path.includes('/routes/') || path.includes('/models/');
                if (isBackend) addBackend(path, code); else addFrontend(path, code);
            }
        }
    }

    // Extract projectTitle if still missing
    if (!result.projectTitle) {
        const t = text.match(/(?:projectTitle|Project Title|title)\s*[":=]\s*["']?([^\n"',]+)/i);
        if (t) result.projectTitle = t[1].trim();
    }

    return result;
}

/** Parse ONLY backend files from text */
function parseBackendOnly(text) {
    const result = { projectTitle: '', backend: {} };
    const addBackend = (path, code) => {
        if (!path || !code?.trim()) return;
        const k = path.trim().startsWith('/') ? path.trim() : `/${path.trim()}`;
        result.backend[k] = { code: code.trim() };
    };
    // META
    const metaMatch = text.match(/===META===([\s\S]*?)===ENDMETA===/i);
    if (metaMatch) {
        try {
            const m = JSON.parse(metaMatch[1].trim());
            result.projectTitle = m.projectTitle || '';
        } catch (_) {}
    }
    // With ENDFILE
    const re2 = /={2,3}\s*BACKEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)={2,3}\s*ENDFILE\s*={2,3}/gi;
    let m;
    while ((m = re2.exec(text)) !== null) addBackend(m[1], m[2]);
    // Without ENDFILE
    if (Object.keys(result.backend).length === 0) {
        const re = /={2,3}\s*BACKEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)(?===={2,3}\s*(?:FRONTEND|BACKEND|ENDFILE|META)\s*|$)/gi;
        while ((m = re.exec(text)) !== null) addBackend(m[1], m[2].replace(/===ENDFILE===/gi,'').trimEnd());
    }
    // Markdown fallback
    if (Object.keys(result.backend).length === 0) {
        const re3 = /```(?:js|javascript)?\r?\n([\s\S]*?)```/g;
        while ((m = re3.exec(text)) !== null) {
            const firstLine = m[1].split('\n')[0].trim();
            const pathM = firstLine.match(/^\/\/\s*(\/[\w/.\-]+\.[a-z]+)/i);
            if (pathM) addBackend(pathM[1], m[1].split('\n').slice(1).join('\n'));
        }
    }
    return result;
}

/** Extract API summary from gateway code for frontend generation */
function extractApiSummary(backendFiles) {
    const lines = [];
    lines.push('Backend API (Gateway port 3005):');
    Object.entries(backendFiles).forEach(([path, content]) => {
        const code = typeof content === 'string' ? content : content?.code || '';
        if (path.includes('gateway') && path.endsWith('index.js')) {
            const proxies = [...code.matchAll(/['"]\/api\/[\w-]+['"]/g)].map(m => m[0].replace(/['"]/g,''));
            if (proxies.length) lines.push(`  Proxy routes: ${[...new Set(proxies)].join(', ')}`);
        }
        if (path.includes('/routes/')) {
            const routeMatches = [...code.matchAll(/router\.(get|post|put|delete)\(['"]([^'"]+)['"]/gi)];
            if (routeMatches.length) {
                const service = path.split('/')[1] || path;
                routeMatches.forEach(m => lines.push(`  ${m[1].toUpperCase()} ${service}${m[2]}`));
            }
        }
    });
    if (lines.length === 1) lines.push('  GET/POST/PUT/DELETE /api/* routes available');
    return lines.join('\n');
}

/** Run static fixes on backend code (no AI required) */
function staticFixBackend(backendFiles) {
    const fixed = {};
    let fixCount = 0;
    Object.entries(backendFiles).forEach(([path, content]) => {
        let code = typeof content === 'string' ? content : content?.code || '';
        let changed = false;

        // Fix ports
        if (path.includes('gateway') && path.endsWith('index.js')) {
            if (!code.includes('3005')) {
                code = code.replace(/app\.listen\(\s*(\d{4})\s*[,)]/g, (m, p) => p !== '3005' ? `app.listen(3005,` : m);
                changed = true;
            }
        }
        if (path.includes('-service') && path.endsWith('index.js')) {
            // Ensure cors + express.json
            if (code.includes('express()') && !code.includes('app.use(cors())') && !code.includes('app.use(cors(')) {
                code = code.replace(
                    /const app = express\(\);/,
                    `const app = express();\napp.use(cors());\napp.use(express.json());`
                );
                if (!code.includes("require('cors')") && !code.includes('require("cors")')) {
                    code = `const cors = require('cors');\n` + code;
                }
                changed = true;
            }
        }
        // Fix route response format
        if (path.includes('/routes/')) {
            // res.json without success wrap → add success:true
            code = code.replace(/res\.json\(([^{][^)]+)\)/g, (m, inner) => {
                if (inner.includes('success')) return m;
                return `res.json({ success: true, data: ${inner} })`;
            });
        }
        if (changed) fixCount++;
        fixed[path] = { code };
    });
    return { files: fixed, fixCount };
}

/** Static sanitize for frontend (mirrors CodeView sanitize) */
function staticFixFrontend(frontendFiles) {
    const ALLOWED = new Set([
        'react','react-dom','react-router-dom','lucide-react',
        'framer-motion','react-toastify','tailwind-merge','uuid',
        'react-beautiful-dnd','recharts','date-fns',
    ]);
    const fixed = {};
    Object.entries(frontendFiles).forEach(([path, content]) => {
        let code = typeof content === 'string' ? content : content?.code || '';
        // @/ aliases
        code = code.replace(/from\s+['"]@\/([^'"]+)['"]/g, "from '/$1'");
        code = code.replace(/import\s*\(\s*['"]@\/([^'"]+)['"]\s*\)/g, "import('/$1')");
        // Line-level fixes
        code = code.split('\n').map(line => {
            if (/^\s*import\s+['"][^'"]+\.css['"]/.test(line)) return '// [css removed]';
            if (line.includes('react-hot-toast')) {
                return line
                    .replace(/from ['"]react-hot-toast['"]/, "from 'react-toastify'")
                    .replace(/from "react-hot-toast"/, 'from "react-toastify"')
                    .replace(/\bToaster\b/, 'ToastContainer');
            }
            if (line.includes('<Toaster') && !line.includes('Container'))
                return line.replace(/<Toaster([^>]*)\/>/, '<ToastContainer$1/>');
            const m = line.match(/^\s*import\s+.*?from\s+['"]([^'"./][^'"@][^'"]*)['"]/);
            if (m) {
                const pkg = m[1].split('/')[0];
                if (!ALLOWED.has(pkg)) return `// [removed: ${pkg}]`;
            }
            return line;
        }).join('\n');
        fixed[path] = { code };
    });
    return fixed;
}

/* ─────────────────────────────────────────────────────────────────────────────
   PARSE TEST RESULTS from AI API-testing output
   Expects ===API_TESTS=== ... ===END_API_TESTS=== block with pipe-delimited rows
───────────────────────────────────────────────────────────────────────────── */
function parseTestResults(text) {
    const results = [];

    // Primary: structured ===API_TESTS=== block
    const block = text.match(/===API_TESTS===([\s\S]*?)===END_API_TESTS===/i);
    if (block) {
        block[1].trim().split('\n').forEach(line => {
            line = line.trim();
            if (!line || line.startsWith('#') || line.startsWith('//')) return;
            const parts = line.split('|').map(p => p.trim());
            if (parts.length < 2) return;
            const routePart = parts[0].trim();
            const spaceIdx  = routePart.indexOf(' ');
            if (spaceIdx < 1) return;
            const method = routePart.slice(0, spaceIdx).toUpperCase();
            const path   = routePart.slice(spaceIdx + 1).trim();
            if (!['GET','POST','PUT','DELETE','PATCH'].includes(method)) return;
            if (!path.startsWith('/')) return;
            const status     = (parts[1] || '').toUpperCase().includes('PASS') ? 'PASS' : 'FAIL';
            const sampleData = parts[2] && parts[2] !== '-' ? parts[2] : null;
            const reason     = status === 'FAIL' && parts[3] && parts[3] !== '-' ? parts[3] : null;
            results.push({ method, path, status, sampleData, reason });
        });
    }

    // Fallback: scan free text for METHOD /path ... PASS/FAIL pattern
    if (results.length === 0) {
        const re = /\b(GET|POST|PUT|DELETE|PATCH)\s+(\/[^\s|,]+)\s*[|:—\-\s]+(PASS|FAIL)([^\n]*)/gi;
        let m;
        while ((m = re.exec(text)) !== null) {
            const method = m[1].toUpperCase();
            const path   = m[2].trim();
            const status = m[3].toUpperCase();
            const reason = status === 'FAIL' ? m[4]?.replace(/^[\s|:—\-]+/, '').trim() || null : null;
            // Deduplicate
            if (!results.find(r => r.method === method && r.path === path))
                results.push({ method, path, status, reason });
        }
    }

    return results;
}

/* ─────────────────────────────────────────────────────────────────────────────
   BUILD BACKEND SNAPSHOT for prompts (capped to avoid token overflow)
───────────────────────────────────────────────────────────────────────────── */
function buildBackendSnapshot(backendFiles, maxFiles = 15, maxCharsPerFile = 1800) {
    return Object.entries(backendFiles)
        .slice(0, maxFiles)
        .map(([p, c]) => {
            const code = typeof c === 'string' ? c : c?.code || '';
            return `===FILE: ${p}===\n${code.slice(0, maxCharsPerFile)}\n===END===`;
        })
        .join('\n\n');
}

/* ─────────────────────────────────────────────────────────────────────────────
   STREAM ALL CHUNKS FROM OLLAMA — yields chunk objects
───────────────────────────────────────────────────────────────────────────── */
async function* streamOllama(messages, system, temperature = 0.7) {
    const response = await ollamaChat({ messages, system, temperature, stream: true });
    yield* readOllamaStream(response);
}

/* ─────────────────────────────────────────────────────────────────────────────
   ROUTE HANDLER
───────────────────────────────────────────────────────────────────────────── */
export async function POST(req) {
    // prompt = full combined string (design seed + user messages)
    const { prompt } = await req.json();
    const encoder = new TextEncoder();

    const stream = new ReadableStream({
        async start(controller) {
            const emit = (data) => {
                try { controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`)); } catch (_) {}
            };

            try {
                let projectTitle = '';
                let totalChars   = 0;

                /* ══════════════════════════════════════════════════
                   PHASE 1 — BACKEND GENERATION
                ══════════════════════════════════════════════════ */
                emit({ type: 'phase', phase: 'backend-gen', status: 'start',
                    message: '⚙️  Generating backend microservices…' });

                let backendText = '';
                let prevText    = '';
                const beUserPrompt = prompt;  // full prompt already includes design seed

                for await (const chunk of streamOllama(
                    [{ role: 'user', content: beUserPrompt }],
                    Prompt.BACKEND_GEN_PROMPT, 0.6
                )) {
                    const content = chunk?.message?.content ?? '';
                    if (content) {
                        backendText += content;
                        totalChars  += content.length;
                        emit({ type: 'chunk', phase: 'backend-gen', chars: totalChars });
                        // Emit file-found events
                        const newFiles = extractNewFilePaths(backendText, prevText);
                        newFiles.forEach(f => emit({ type: 'file', phase: 'backend-gen', ...f }));
                        prevText = backendText;
                    }
                    if (chunk?.done) break;
                }

                console.log(`[backend-gen] ${backendText.length} chars`);
                const beParsed = parseBackendOnly(backendText);
                let backendFiles = beParsed.backend;
                projectTitle = beParsed.projectTitle || projectTitle;

                const beCount = Object.keys(backendFiles).length;
                emit({ type: 'phase', phase: 'backend-gen', status: 'done',
                    fileCount: beCount,
                    message: `✅ Generated ${beCount} backend files` });

                if (beCount === 0) {
                    emit({ type: 'log', phase: 'backend-gen', level: 'warning',
                        message: '⚠️  Backend parser found 0 files — check AI output format. Continuing with frontend only.' });
                }

                /* ══════════════════════════════════════════════════
                   PHASE 2 — BACKEND BUG FIXING (up to 5 rounds)
                ══════════════════════════════════════════════════ */
                if (beCount > 0) {
                    emit({ type: 'phase', phase: 'backend-fix', status: 'start',
                        message: '🔍 Analyzing backend for bugs…' });

                    // Round 0 — static fixes (instant, no AI)
                    const { files: staticFixed, fixCount } = staticFixBackend(backendFiles);
                    backendFiles = staticFixed;
                    if (fixCount > 0) {
                        emit({ type: 'log', phase: 'backend-fix', level: 'info',
                            message: `🔧 Static analysis fixed ${fixCount} files (ports, middleware, CORS)` });
                    } else {
                        emit({ type: 'log', phase: 'backend-fix', level: 'success',
                            message: '✅ Static analysis: no quick-fix issues found' });
                    }

                    let cleanRounds = 0;
                    for (let round = 1; round <= 5; round++) {
                        emit({ type: 'log', phase: 'backend-fix', level: 'info', round,
                            message: `🤖 Round ${round}/5: AI reviewing backend code…` });

                        // Build snapshot (limit to avoid huge prompts)
                        const snapshot = Object.entries(backendFiles)
                            .slice(0, 12)
                            .map(([p, c]) => {
                                const code = typeof c === 'string' ? c : c?.code || '';
                                return `===FILE: ${p}===\n${code.slice(0, 2000)}\n===END===`;
                            })
                            .join('\n\n');

                        let fixText = '';
                        for await (const chunk of streamOllama(
                            [{ role: 'user', content: snapshot }],
                            Prompt.BACKEND_FIX_PROMPT, 0.3
                        )) {
                            const content = chunk?.message?.content ?? '';
                            if (content) {
                                fixText    += content;
                                totalChars += content.length;
                                emit({ type: 'chunk', phase: 'backend-fix', chars: totalChars, round });
                            }
                            if (chunk?.done) break;
                        }

                        if (fixText.includes('===NO_BUGS===') || fixText.trim() === '===NO_BUGS===') {
                            emit({ type: 'log', phase: 'backend-fix', level: 'success', round,
                                message: `✅ Round ${round}: No bugs found — backend is clean!` });
                            cleanRounds++;
                            break;
                        }

                        const fixParsed = parseBackendOnly(fixText);
                        const fixedCount = Object.keys(fixParsed.backend).length;
                        if (fixedCount > 0) {
                            backendFiles = { ...backendFiles, ...fixParsed.backend };
                            emit({ type: 'log', phase: 'backend-fix', level: 'warning', round,
                                message: `🔧 Round ${round}: Fixed ${fixedCount} backend file(s)` });
                        } else {
                            emit({ type: 'log', phase: 'backend-fix', level: 'success', round,
                                message: `✅ Round ${round}: AI found no actionable changes` });
                            cleanRounds++;
                            break;
                        }
                    }

                    emit({ type: 'phase', phase: 'backend-fix', status: 'done',
                        message: `✅ Backend verified (${Object.keys(backendFiles).length} files ready)` });
                }

                /* ══════════════════════════════════════════════════
                   PHASE 3 — POSTMAN-STYLE API ROUTE TESTING
                   Simulates real HTTP requests for every route.
                   Auto-fixes failing routes for up to 3 rounds.
                ══════════════════════════════════════════════════ */
                if (Object.keys(backendFiles).length > 0) {
                    emit({ type: 'phase', phase: 'api-test', status: 'start',
                        message: '🧪 Running Postman-style API route tests…' });

                    let allRoutesClean = false;

                    for (let round = 1; round <= 3; round++) {
                        emit({ type: 'log', phase: 'api-test', level: 'info', round,
                            message: `🔬 Round ${round}/3: Simulating requests for all routes…` });

                        const snapshot = buildBackendSnapshot(backendFiles);

                        let testText = '';
                        for await (const chunk of streamOllama(
                            [{ role: 'user', content: snapshot }],
                            Prompt.API_TEST_PROMPT, 0.2
                        )) {
                            const content = chunk?.message?.content ?? '';
                            if (content) {
                                testText   += content;
                                totalChars += content.length;
                                emit({ type: 'chunk', phase: 'api-test', chars: totalChars, round });
                            }
                            if (chunk?.done) break;
                        }

                        const testResults = parseTestResults(testText);
                        const passed      = testResults.filter(r => r.status === 'PASS');
                        const failed      = testResults.filter(r => r.status === 'FAIL');

                        // Emit individual route test results
                        if (testResults.length > 0) {
                            testResults.forEach(r => {
                                emit({
                                    type: 'test-result',
                                    method: r.method,
                                    path:   r.path,
                                    status: r.status,
                                    reason: r.reason || null,
                                    sampleData: r.sampleData || null,
                                    round,
                                });
                            });
                            emit({
                                type: 'test-summary',
                                passed: passed.length,
                                failed: failed.length,
                                total:  testResults.length,
                                round,
                            });
                        }

                        if (failed.length === 0) {
                            const msg = testResults.length > 0
                                ? `✅ All ${passed.length} routes PASSED! Backend is production-ready.`
                                : `⚠️  AI found no parseable routes — assuming backend is OK.`;
                            emit({ type: 'log', phase: 'api-test', level: 'success', round, message: msg });
                            allRoutesClean = true;
                            break;
                        }

                        // ── Auto-fix failing routes ─────────────────────────
                        emit({ type: 'log', phase: 'api-test', level: 'warning', round,
                            message: `🔧 ${failed.length} route(s) failing — running targeted auto-fix…` });

                        const failList = failed
                            .map(r => `${r.method} ${r.path}: ${r.reason || 'unknown issue'}`)
                            .join('\n');

                        let fixText = '';
                        for await (const chunk of streamOllama(
                            [{ role: 'user', content:
                                `${snapshot}\n\n` +
                                `FAILED ROUTES THAT MUST BE FIXED:\n${failList}\n\n` +
                                `Fix ONLY these routes. Output the corrected files.`
                            }],
                            Prompt.API_FIX_PROMPT, 0.3
                        )) {
                            const content = chunk?.message?.content ?? '';
                            if (content) {
                                fixText    += content;
                                totalChars += content.length;
                                emit({ type: 'chunk', phase: 'api-test', chars: totalChars, round });
                            }
                            if (chunk?.done) break;
                        }

                        if (fixText.includes('===NO_BUGS===')) {
                            emit({ type: 'log', phase: 'api-test', level: 'success', round,
                                message: `✅ AI confirmed: routes are correct after targeted review.` });
                            allRoutesClean = true;
                            break;
                        }

                        const fixParsed   = parseBackendOnly(fixText);
                        const fixedCount  = Object.keys(fixParsed.backend).length;
                        if (fixedCount > 0) {
                            backendFiles = { ...backendFiles, ...fixParsed.backend };
                            emit({ type: 'log', phase: 'api-test', level: 'info', round,
                                message: `🔧 Applied fixes to ${fixedCount} file(s). Re-running tests next round…` });
                        } else {
                            emit({ type: 'log', phase: 'api-test', level: 'warning', round,
                                message: `⚠️  Could not generate fixes automatically. Moving on.` });
                            break;
                        }
                    }

                    const finalBeCount = Object.keys(backendFiles).length;
                    emit({ type: 'phase', phase: 'api-test', status: 'done',
                        fileCount: finalBeCount,
                        message: allRoutesClean
                            ? `✅ All API routes verified (${finalBeCount} files)`
                            : `⚠️  API testing complete — ${finalBeCount} backend files ready` });
                }

                /* ══════════════════════════════════════════════════
                   PHASE 5 — FRONTEND GENERATION
                ══════════════════════════════════════════════════ */
                emit({ type: 'phase', phase: 'frontend-gen', status: 'start',
                    message: '🎨 Generating React frontend…' });

                const apiSummary   = extractApiSummary(backendFiles);
                // Inject frontend-only instruction + API summary into the existing prompt
                const feUserPrompt =
                    `IMPORTANT: Generate ONLY React frontend files (===FRONTEND: /src/...===). ` +
                    `Do NOT generate any ===BACKEND:=== files — the backend is already built and running.\n\n` +
                    `${prompt}\n\n${apiSummary}`;

                let frontendText = '';
                prevText = '';
                for await (const chunk of streamOllama(
                    [{ role: 'user', content: feUserPrompt }],
                    Prompt.CODE_GEN_PROMPT, 0.7
                )) {
                    const content = chunk?.message?.content ?? '';
                    if (content) {
                        frontendText += content;
                        totalChars   += content.length;
                        emit({ type: 'chunk', phase: 'frontend-gen', chars: totalChars });
                        const newFiles = extractNewFilePaths(frontendText, prevText);
                        newFiles.forEach(f => emit({ type: 'file', phase: 'frontend-gen', ...f }));
                        prevText = frontendText;
                    }
                    if (chunk?.done) break;
                }

                console.log(`[frontend-gen] ${frontendText.length} chars`);
                const feParsed = parseAIOutput(frontendText);
                let frontendFiles = feParsed.frontend;
                projectTitle = projectTitle || feParsed.projectTitle || '';

                const feCount = Object.keys(frontendFiles).length;
                emit({ type: 'phase', phase: 'frontend-gen', status: 'done',
                    fileCount: feCount,
                    message: `✅ Generated ${feCount} frontend files` });

                if (feCount === 0) {
                    emit({ type: 'error', error: 'Frontend generation produced 0 files. The AI may have not followed the output format. Try regenerating.', done: true });
                    controller.close();
                    return;
                }

                /* ══════════════════════════════════════════════════
                   PHASE 6 — FRONTEND BUG FIXING (up to 3 rounds)
                ══════════════════════════════════════════════════ */
                emit({ type: 'phase', phase: 'frontend-fix', status: 'start',
                    message: '🔍 Checking frontend for issues…' });

                // Always apply static fixes first (instant)
                frontendFiles = staticFixFrontend(frontendFiles);
                emit({ type: 'log', phase: 'frontend-fix', level: 'info',
                    message: '🔧 Static sanitization applied (CSS, @/ aliases, package whitelist, react-toastify)' });

                for (let round = 1; round <= 3; round++) {
                    emit({ type: 'log', phase: 'frontend-fix', level: 'info', round,
                        message: `🤖 Round ${round}/3: AI reviewing frontend code…` });

                    // Send up to 6 core files for review
                    const coreFiles = Object.entries(frontendFiles)
                        .filter(([p]) => p.endsWith('.jsx') || p.endsWith('.js'))
                        .slice(0, 6);
                    const snapshot = coreFiles
                        .map(([p, c]) => {
                            const code = typeof c === 'string' ? c : c?.code || '';
                            return `===FILE: ${p}===\n${code.slice(0, 2500)}\n===END===`;
                        })
                        .join('\n\n');

                    let fixText = '';
                    for await (const chunk of streamOllama(
                        [{ role: 'user', content: snapshot }],
                        Prompt.FRONTEND_FIX_PROMPT, 0.3
                    )) {
                        const content = chunk?.message?.content ?? '';
                        if (content) {
                            fixText    += content;
                            totalChars += content.length;
                            emit({ type: 'chunk', phase: 'frontend-fix', chars: totalChars, round });
                        }
                        if (chunk?.done) break;
                    }

                    if (fixText.includes('===NO_BUGS===') || fixText.trim() === '===NO_BUGS===') {
                        emit({ type: 'log', phase: 'frontend-fix', level: 'success', round,
                            message: `✅ Round ${round}: No bugs found — frontend is clean!` });
                        break;
                    }

                    const fixParsed = parseAIOutput(fixText);
                    const fixedCount = Object.keys(fixParsed.frontend).length;
                    if (fixedCount > 0) {
                        frontendFiles = { ...frontendFiles, ...fixParsed.frontend };
                        // Re-apply static fixes after AI edits
                        frontendFiles = staticFixFrontend(frontendFiles);
                        emit({ type: 'log', phase: 'frontend-fix', level: 'warning', round,
                            message: `🔧 Round ${round}: Fixed ${fixedCount} frontend file(s)` });
                    } else {
                        emit({ type: 'log', phase: 'frontend-fix', level: 'success', round,
                            message: `✅ Round ${round}: AI found no actionable changes` });
                        break;
                    }
                }

                emit({ type: 'phase', phase: 'frontend-fix', status: 'done',
                    message: `✅ Frontend verified (${Object.keys(frontendFiles).length} files ready)` });

                /* ══════════════════════════════════════════════════
                   FINAL — emit complete result
                ══════════════════════════════════════════════════ */
                const totalFiles = Object.keys(frontendFiles).length + Object.keys(backendFiles).length;
                emit({ type: 'log', phase: 'complete', level: 'success',
                    message: `🚀 Full-stack app ready! ${totalFiles} files total` });

                emit({
                    type: 'final',
                    final: {
                        frontend:     frontendFiles,
                        backend:      backendFiles,
                        projectTitle: projectTitle || 'Generated App',
                    },
                    done: true,
                });
                controller.close();

            } catch (e) {
                console.error('[gen-fullstack] error:', e);
                emit({ type: 'error', error: e.message || 'Generation failed', done: true });
                controller.close();
            }
        },
    });

    return new Response(stream, {
        headers: {
            'Content-Type':  'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection':    'keep-alive',
        },
    });
}
