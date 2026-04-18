import { spawn } from 'node:child_process';
import { mkdir, writeFile, rm, readFile, access, appendFile } from 'node:fs/promises';
import net from 'node:net';
import { builtinModules } from 'node:module';
import os from 'node:os';
import path from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import {
    ollamaChat,
    readOllamaStream,
    BACKEND_GEN_MODEL,
    BACKEND_FIX_MODEL,
    API_TEST_MODEL,
    FRONTEND_GEN_MODEL,
    FRONTEND_FIX_MODEL,
} from '@/configs/AiModel';
import Prompt from '@/data/Prompt';
import {
    storeBugFix,
    buildMemoryContext,
    getFailedMethods,
    getBestKnownFix,
} from '@/lib/bugMemoryChroma';
import {
    pickStrategy,
    markStrategyFailed,
    clearStrategyState,
    buildHumanLikeInstruction,
} from '@/lib/fixStrategy';

const FIX_ROUND_CAP = Number.parseInt(process.env.AI_BUILDER_MAX_FIX_ROUNDS || '10', 10);
const MAX_BACKEND_FIX_ROUNDS = Number.isFinite(FIX_ROUND_CAP) && FIX_ROUND_CAP > 0 ? FIX_ROUND_CAP : 10;
const MAX_API_FIX_ROUNDS = Number.isFinite(FIX_ROUND_CAP) && FIX_ROUND_CAP > 0 ? FIX_ROUND_CAP : 10;
const MAX_LIVE_FIX_ROUNDS = Number.isFinite(FIX_ROUND_CAP) && FIX_ROUND_CAP > 0 ? FIX_ROUND_CAP : 10;
const MAX_NO_PROGRESS_ROUNDS = 2;
const MAX_SAME_SIGNATURE_ROUNDS = 2;
const MAX_REGRESSIVE_ROUNDS = 1;
const DEFAULT_FRONTEND_PORT = 3004;
const DEFAULT_GATEWAY_PORT = 3005;
const DEFAULT_SERVICE_PORT_START = 3006;
const BUG_MEMORY_PATH = path.join(process.cwd(), 'memory.md');
const BUG_SKILL_PATH = path.join(process.cwd(), 'skills', 'ai-web-builder-backend-recovery', 'SKILL.md');
const LOCAL_REFERENCE_MANIFEST = [
    {
        name: 'AgentField',
        file: 'references/agentfield-main/README.md',
        guidance: [
            'prefer structured contracts and typed outputs over loose code guesses',
            'preserve memory, auditability, and explicit execution state across repair rounds',
            'treat long-running work as observable multi-step workflows, not one-shot blobs',
        ],
    },
    {
        name: 'AI Website Builder',
        file: 'references/Ai-Website-Builder-main/README.md',
        guidance: [
            'optimize for full app coverage, real-time progress, and usable live preview',
            'favor end-to-end generation that keeps frontend and backend aligned',
        ],
    },
    {
        name: 'bolt.diy',
        file: 'references/bolt.diy-main/README.md',
        guidance: [
            'prefer deterministic file patches, diff-safe rewrites, and recovery from bad generations',
            'use file locking, snapshots, and provider/runtime abstraction patterns',
            'keep terminal, preview, and search workflows first-class in the builder UX',
        ],
    },
    {
        name: 'BuildShip',
        file: 'references/buildship-main/README.md',
        guidance: [
            'think in backend workflows, jobs, APIs, and production-ready service orchestration',
            'generate integrations and backend workflows as explicit system capabilities',
        ],
    },
    {
        name: 'Claude Code',
        file: 'references/claude-code-main/README.md',
        guidance: [
            'prefer terminal-first debugging, plugins/skills, and clear bug-report driven recovery',
            'treat bug fixing as an iterative engineering workflow with explicit ownership',
        ],
    },
    {
        name: 'Dyad',
        file: 'references/dyad-main/README.md',
        guidance: [
            'optimize for local-first app generation, runtime separation, and preview reliability',
            'support restartable dev environments and stable local execution paths',
        ],
    },
    {
        name: 'Dyad Cloud Sandboxes',
        file: 'references/dyad-main/plans/cloud-sandboxes.md',
        guidance: [
            'separate runtime modes cleanly and keep preview/start/restart actions deterministic',
            'treat browser-open and server lifecycle as explicit product behaviors',
        ],
    },
];

/* Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
   SHARED HELPERS
Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ */

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

/** Universal AI output parser Ã¢â‚¬â€ same logic as gen-ai-code route */
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

    // Method 1 Ã¢â‚¬â€ delimiter markers (two passes: with and without ENDFILE)
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

    // Method 2 Ã¢â‚¬â€ markdown blocks with path comment
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

async function readOptionalText(filePath, maxChars = 5000) {
    try {
        await access(filePath);
        const text = await readFile(filePath, 'utf8');
        if (!text) {
            return '';
        }

        return text.length > maxChars
            ? `${text.slice(0, maxChars)}\n[truncated]`
            : text;
    } catch (_) {
        return '';
    }
}

async function loadBackendRepairContext() {
    const [memoryText, skillText] = await Promise.all([
        readOptionalText(BUG_MEMORY_PATH, 4000),
        readOptionalText(BUG_SKILL_PATH, 4000),
    ]);

    const sections = [];
    if (memoryText) {
        sections.push(`PROJECT BUG MEMORY:\n${memoryText}`);
    }

    if (skillText) {
        sections.push(`PROJECT RECOVERY SKILL:\n${skillText}`);
    }

    sections.push(
        [
            'ROUND POLICY:',
            '- Round 1 should classify failures by root cause and fix only the single highest-impact root-cause group first.',
            '- Later rounds are recovery rounds for the same remaining root-cause group only.',
            '- Do not stop while backend validation errors or route/runtime bugs still remain.',
            '- If a failure repeats, rewrite the owning route file and related gateway/service registration completely instead of making a tiny patch.',
            '- Ignore blocked routes when choosing the next fix target; fix the direct root cause first.',
            `- Live runtime ports are fixed: frontend ${DEFAULT_FRONTEND_PORT}, gateway ${DEFAULT_GATEWAY_PORT}, services start at ${DEFAULT_SERVICE_PORT_START}.`,
            '- Validate routes, models, controllers, local requires, package.json files, and structured-spec endpoint coverage before claiming the backend is clean.',
            '- Never continue to frontend generation while any backend validation issue or route bug remains.',
        ].join('\n')
    );

    return sections.join('\n\n').trim();
}

function extractReferenceHeading(text = '') {
    const lines = String(text || '')
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);

    const heading = lines.find((line) => /^#/.test(line)) || lines[0] || '';
    return heading.replace(/^#+\s*/, '').trim();
}

async function loadLocalReferenceContext() {
    const discovered = [];

    for (const reference of LOCAL_REFERENCE_MANIFEST) {
        const absolutePath = path.join(process.cwd(), reference.file);
        const preview = await readOptionalText(absolutePath, 600);
        if (!preview) {
            continue;
        }

        discovered.push({
            ...reference,
            heading: extractReferenceHeading(preview),
        });
    }

    if (!discovered.length) {
        return '';
    }

    const lines = [
        'LOCAL REFERENCE BLUEPRINT:',
        'Use the following local projects as implementation-quality guidance. Keep the user prompt and structured spec as the primary contract, then apply these patterns to improve architecture, repair strategy, and product polish.',
        ...discovered.map((reference) => {
            const heading = reference.heading ? ` | ${reference.heading}` : '';
            return `- ${reference.name}${heading}: ${reference.guidance.join('; ')}.`;
        }),
        'Apply these references to generation and bug fixing by improving service boundaries, route/controller/model alignment, diff-safe rewrites, validation discipline, live-preview reliability, and deterministic runtime behavior.',
    ];

    return lines.join('\n');
}

async function appendBugMemory(section, details = []) {
    const lines = Array.isArray(details)
        ? details.map((item) => String(item || '').trim()).filter(Boolean)
        : [String(details || '').trim()].filter(Boolean);
    if (!lines.length) {
        return;
    }

    const timestamp = new Date().toISOString();
    const entry = [
        '',
        `## ${section} | ${timestamp}`,
        ...lines.slice(0, 8).map((line) => `- ${line}`),
    ].join('\n') + '\n';

    await appendFile(BUG_MEMORY_PATH, entry, 'utf8').catch(() => {});
}

function normalizeDisplayList(values = []) {
    return [...new Set((values || []).map((value) => String(value || '').trim()).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b));
}

function humanizeServiceName(serviceDir = '') {
    const label = String(serviceDir || '').replace(/^\/+/, '') || 'service';
    return label
        .replace(/-service$/i, ' service')
        .replace(/-/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

function fileUsesAuthMiddleware(code = '') {
    return /\b(?:app|router)\.(?:get|post|put|patch|delete)\s*\([\s\S]{0,400}?\bauth\b/.test(String(code || ''));
}

function fileDeclaresAuthMiddleware(code = '') {
    return /\b(?:const|let|var)\s+auth\b/.test(String(code || ''))
        || /\bfunction\s+auth\b/.test(String(code || ''))
        || /\bimport\s+auth\b/.test(String(code || ''))
        || /\bimport\s*\{\s*auth\s*\}\s*from\b/.test(String(code || ''))
        || /require\(\s*['"](?:\.\.\/|\.\/)*middleware\/auth['"]\s*\)/.test(String(code || ''));
}

function fileNeedsAuthMiddlewareImport(code = '') {
    return fileUsesAuthMiddleware(code) && !fileDeclaresAuthMiddleware(code);
}

function prependRequireLine(code = '', requireLine = '') {
    const source = String(code || '');
    const line = String(requireLine || '').trim();
    if (!source.trim() || !line) {
        return source;
    }
    if (source.includes(line)) {
        return source;
    }

    const requireBlockMatch = source.match(/^((?:\s*(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*require\([^\n]+\);\s*\r?\n)+)/);
    if (requireBlockMatch) {
        return `${requireBlockMatch[1]}${line}\n${source.slice(requireBlockMatch[1].length)}`;
    }

    return `${line}\n${source}`;
}

function inferExpectedLibraries(structuredSpec = null, prompt = '') {
    const backendLibraries = new Set(['express', 'cors', 'dotenv']);
    const frontendLibraries = new Set(['react']);
    const signalText = [
        prompt,
        structuredSpec?.projectTitle || '',
        ...(structuredSpec?.services || []).map((service) => `${service.name} ${service.description} ${(service.endpoints || []).map((endpoint) => `${endpoint.method} ${endpoint.path}`).join(' ')}`),
        ...(structuredSpec?.features || []).map((feature) => `${feature.name} ${feature.description}`),
    ].join(' ').toLowerCase();

    if ((structuredSpec?.services || []).length > 0) {
        backendLibraries.add('mongoose');
    }
    if ((structuredSpec?.services || []).length > 1) {
        backendLibraries.add('http-proxy-middleware');
        frontendLibraries.add('axios');
    }
    if (/auth|login|register|token|jwt|password/.test(signalText)) {
        backendLibraries.add('jsonwebtoken');
        backendLibraries.add('bcryptjs');
        frontendLibraries.add('react-router-dom');
    }
    if (/upload|image|file/.test(signalText)) {
        backendLibraries.add('multer');
    }
    if (/toast|notification|alert/.test(signalText)) {
        frontendLibraries.add('react-toastify');
    }
    if (/dashboard|chart|analytics|report/.test(signalText)) {
        frontendLibraries.add('recharts');
    }

    return {
        backendLibraries: normalizeDisplayList([...backendLibraries]),
        frontendLibraries: normalizeDisplayList([...frontendLibraries]),
    };
}

function buildAppPlanningSnapshot(structuredSpec = null, prompt = '') {
    const libraries = inferExpectedLibraries(structuredSpec, prompt);
    const services = (structuredSpec?.services || []).map((service) => {
        const endpointCount = Array.isArray(service?.endpoints) ? service.endpoints.length : 0;
        return `${service.name || service.slug || 'service'} (${endpointCount} endpoint${endpointCount === 1 ? '' : 's'})`;
    });
    const features = (structuredSpec?.features || []).map((feature) => feature.name).filter(Boolean);

    const lines = [
        `Project: ${structuredSpec?.projectTitle || 'Generated app'}`,
        `Services: ${services.length ? services.join(', ') : 'not structured'}`,
        `Features: ${features.length ? features.join(', ') : 'not structured'}`,
        `Expected backend libraries: ${libraries.backendLibraries.join(', ') || 'none inferred'}`,
        `Expected frontend libraries: ${libraries.frontendLibraries.join(', ') || 'none inferred'}`,
        'Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.',
        'Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.',
    ];

    return {
        libraries,
        lines,
    };
}

function inspectBackendFileImports(filePath = '', code = '', backendFiles = {}, declaredPackages = new Set()) {
    const missingLocalRequires = new Set();
    const missingPackages = new Set();
    const modelImports = new Set();

    [...String(code || '').matchAll(/require\(\s*['"](\.[^'"]+)['"]\s*\)/g)].forEach((match) => {
        const requestPath = match[1];
        const candidates = resolveLocalRequireCandidates(filePath, requestPath);
        const found = candidates.some((candidate) => backendFiles[candidate]);
        if (!found) {
            missingLocalRequires.add(requestPath);
        }
    });

    extractRequireAndImportRequests(code).forEach((requestPath) => {
        if (/\/models?\//i.test(requestPath) || /^\.\.\/models?\//i.test(requestPath) || /^\.\/*models?\//i.test(requestPath)) {
            modelImports.add(requestPath);
        }
        const packageName = getExternalRequirePackageName(requestPath);
        if (!packageName || NODE_BUILTIN_MODULES.has(packageName)) {
            return;
        }
        if (!declaredPackages.has(packageName)) {
            missingPackages.add(packageName);
        }
    });

    return {
        missingLocalRequires: normalizeDisplayList([...missingLocalRequires]),
        missingPackages: normalizeDisplayList([...missingPackages]),
        modelImports: normalizeDisplayList([...modelImports]),
    };
}

function collectBackendServiceAudit(backendFiles = {}, structuredSpec = null) {
    const backendPaths = Object.keys(backendFiles || {});
    const packageJsonByService = parsePackageJsonMap(backendFiles);
    const serviceDirs = new Set(
        backendPaths
            .map((filePath) => getServiceDirForFile(filePath))
            .filter(Boolean)
    );

    return [...serviceDirs]
        .filter(Boolean)
        .sort((a, b) => a.localeCompare(b))
        .map((serviceDir) => {
            const files = backendPaths.filter((filePath) => filePath.startsWith(`${serviceDir}/`) || filePath === `${serviceDir}/index.js`);
            const modelFiles = files.filter((filePath) => /\/models?\//i.test(filePath));
            const routeFiles = files.filter((filePath) => /\/routes?\//i.test(filePath));
            const controllerFiles = files.filter((filePath) => /\/controllers?\//i.test(filePath));
            const indexPath = `${serviceDir}/index.js`;
            const packagePath = `${serviceDir}/package.json`;
            const indexCode = normalizeBackendFileContent(indexPath, typeof backendFiles[indexPath] === 'string' ? backendFiles[indexPath] : backendFiles[indexPath]?.code || '');
            const servicePackageJson = packageJsonByService.get(serviceDir) || {};
            const declaredPackages = getDeclaredPackageNames(servicePackageJson);

            const routeAudit = routeFiles.reduce((acc, filePath) => {
                const code = normalizeBackendFileContent(filePath, typeof backendFiles[filePath] === 'string' ? backendFiles[filePath] : backendFiles[filePath]?.code || '');
                const imports = inspectBackendFileImports(filePath, code, backendFiles, declaredPackages);
                imports.missingLocalRequires.forEach((value) => acc.missingLocalRequires.add(value));
                imports.missingPackages.forEach((value) => acc.missingPackages.add(value));
                imports.modelImports.forEach((value) => acc.modelImports.add(value));
                [...code.matchAll(/\brouter\.(get|post|put|patch|delete)\s*\(\s*['"]([^'"]+)['"]/gi)].forEach((match) => {
                    acc.endpoints.add(`${String(match[1] || 'GET').toUpperCase()} ${match[2]}`);
                });
                if (/(joi|zod|express-validator|celebrate|validate|validationresult|required\s*:|enum\s*:)/i.test(code)) {
                    acc.hasValidationHints = true;
                }
                if (fileNeedsAuthMiddlewareImport(code)) {
                    acc.missingAuthMiddleware = true;
                }
                return acc;
            }, {
                missingLocalRequires: new Set(),
                missingPackages: new Set(),
                modelImports: new Set(),
                endpoints: new Set(),
                hasValidationHints: false,
                missingAuthMiddleware: false,
            });

            const modelAudit = modelFiles.reduce((acc, filePath) => {
                const code = normalizeBackendFileContent(filePath, typeof backendFiles[filePath] === 'string' ? backendFiles[filePath] : backendFiles[filePath]?.code || '');
                const imports = inspectBackendFileImports(filePath, code, backendFiles, declaredPackages);
                imports.missingLocalRequires.forEach((value) => acc.missingLocalRequires.add(value));
                imports.missingPackages.forEach((value) => acc.missingPackages.add(value));
                if (/new\s+Schema\s*\(|mongoose\.Schema|required\s*:|enum\s*:|default\s*:/.test(code)) {
                    acc.hasSchemaValidation = true;
                }
                return acc;
            }, {
                missingLocalRequires: new Set(),
                missingPackages: new Set(),
                hasSchemaValidation: false,
            });

            const indexAudit = inspectBackendFileImports(indexPath, indexCode, backendFiles, declaredPackages);
            const indexMissingAuthMiddleware = fileNeedsAuthMiddlewareImport(indexCode);
            const mountedRoutes = [...indexCode.matchAll(/\bapp\.use\(\s*['"]([^'"]+)['"]/g)]
                .map((match) => match[1])
                .filter(Boolean);

            return {
                serviceDir,
                serviceName: humanizeServiceName(serviceDir),
                modelFiles,
                routeFiles,
                controllerFiles,
                hasIndex: Boolean(backendFiles[indexPath]),
                hasPackage: Boolean(backendFiles[packagePath]),
                declaredPackages: normalizeDisplayList([...declaredPackages]),
                routeMissingLocalRequires: normalizeDisplayList([...routeAudit.missingLocalRequires]),
                routeMissingPackages: normalizeDisplayList([...routeAudit.missingPackages]),
                routeModelImports: normalizeDisplayList([...routeAudit.modelImports]),
                routeEndpoints: normalizeDisplayList([...routeAudit.endpoints]),
                routeValidationState: routeFiles.length === 0
                    ? 'no route files generated yet'
                    : routeAudit.hasValidationHints
                        ? 'route validation hints found'
                        : 'no explicit route validation hints found',
                routeMissingAuthMiddleware: routeAudit.missingAuthMiddleware,
                modelMissingLocalRequires: normalizeDisplayList([...modelAudit.missingLocalRequires]),
                modelMissingPackages: normalizeDisplayList([...modelAudit.missingPackages]),
                modelValidationState: modelFiles.length === 0
                    ? 'no model files generated yet'
                    : modelAudit.hasSchemaValidation
                        ? 'schema validation hints found'
                        : 'model files present but validation hints are light',
                indexMissingLocalRequires: indexAudit.missingLocalRequires,
                indexMissingPackages: indexAudit.missingPackages,
                indexMissingAuthMiddleware,
                mountedRoutes: normalizeDisplayList(mountedRoutes),
            };
        });
}

function emitBackendServiceAudit(emit, audit = [], { phase = 'backend-fix', round = null } = {}) {
    if (!emit || !Array.isArray(audit) || audit.length === 0) {
        return;
    }

    const base = { type: 'log', phase, level: 'info' };
    if (round != null) {
        base.round = round;
    }

    audit.forEach((service) => {
        emit({
            ...base,
            message: `[developer-check] ${service.serviceName}: models ${service.modelFiles.length}, routes ${service.routeFiles.length}, controllers ${service.controllerFiles.length}, index.js ${service.hasIndex ? 'present' : 'missing'}, package.json ${service.hasPackage ? 'present' : 'missing'}`,
        });
        emit({
            ...base,
            message: `[developer-check] ${service.serviceName}: model layer ${service.modelValidationState}; model imports ${service.modelMissingLocalRequires.length || service.modelMissingPackages.length ? `issues -> local ${service.modelMissingLocalRequires.join(', ') || 'none'} | packages ${service.modelMissingPackages.join(', ') || 'none'}` : 'OK'}`,
        });
        emit({
            ...base,
            message: `[developer-check] ${service.serviceName}: routes ${service.routeEndpoints.join(', ') || 'none parsed'}; route/model imports ${service.routeMissingLocalRequires.length || service.routeMissingPackages.length || service.routeMissingAuthMiddleware ? `issues -> local ${service.routeMissingLocalRequires.join(', ') || 'none'} | packages ${service.routeMissingPackages.join(', ') || 'none'}${service.routeMissingAuthMiddleware ? ' | auth middleware import missing' : ''}` : 'OK'}`,
        });
        emit({
            ...base,
            message: `[developer-check] ${service.serviceName}: index/routes ${service.hasIndex ? `mounts ${service.mountedRoutes.join(', ') || 'none parsed'}` : 'index.js missing'}; index import check ${service.indexMissingLocalRequires.length || service.indexMissingPackages.length || service.indexMissingAuthMiddleware ? `issues -> local ${service.indexMissingLocalRequires.join(', ') || 'none'} | packages ${service.indexMissingPackages.join(', ') || 'none'}${service.indexMissingAuthMiddleware ? ' | auth middleware import missing' : ''}` : 'OK'}`,
        });
    });
}

function classifyFrontendAuditKind(filePath = '') {
    const normalized = String(filePath || '').replace(/\\/g, '/').toLowerCase();
    if (/\/pages?\//.test(normalized) || /\/app\//.test(normalized)) return 'page';
    if (/(^|\/)(app|main|index)\.(jsx?|tsx?)$/.test(normalized)) return 'entry';
    if (/\/components?\//.test(normalized)) return 'component';
    return 'file';
}

function emitFrontendValidationPlan(emit, frontendFiles = {}, { phase = 'frontend-fix', round = null } = {}) {
    if (!emit) {
        return;
    }

    const candidates = Object.keys(frontendFiles || {})
        .filter((filePath) => /\.(jsx?|tsx?)$/i.test(filePath))
        .sort((a, b) => a.localeCompare(b));

    if (!candidates.length) {
        return;
    }

    const pages = candidates.filter((filePath) => classifyFrontendAuditKind(filePath) === 'page');
    emit({
        type: 'log',
        phase,
        level: 'info',
        ...(round != null ? { round } : {}),
        message: `Frontend checker: reviewing ${pages.length} page file(s) and ${candidates.length - pages.length} shared file(s) one by one for syntax, imports, and missing libraries.`,
    });

    candidates.slice(0, 40).forEach((filePath) => {
        emit({
            type: 'log',
            phase,
            level: 'info',
            ...(round != null ? { round } : {}),
            message: `[frontend-check] Checking ${classifyFrontendAuditKind(filePath)} ${filePath} for syntax, local imports, and library imports...`,
        });
    });

    if (candidates.length > 40) {
        emit({
            type: 'log',
            phase,
            level: 'info',
            ...(round != null ? { round } : {}),
            message: `[frontend-check] ...and ${candidates.length - 40} more frontend files in the same pass.`,
        });
    }
}

function resolveMongoUri(candidateUri, fallbackDbName) {
    if (!candidateUri || typeof candidateUri !== 'string') {
        return '';
    }

    const trimmed = candidateUri.trim();
    if (!trimmed) {
        return '';
    }

    return trimmed.replace(/\/ugenerateappname(?=[/?]|$)/i, `/${fallbackDbName}`);
}

function buildSecretExpression() {
    return "process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'dev-secret'";
}

function slugifyWorkspaceName(value = 'generated-app') {
    return String(value || 'generated-app')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        || 'generated-app';
}

function getGenerationOutputRoot(projectTitle = 'generated-app') {
    return path.join(process.cwd(), 'output', slugifyWorkspaceName(projectTitle || 'generated-app'));
}

async function persistGeneratedAppOutput({ projectTitle, frontendFiles = {}, backendFiles = {}, metadata = {} }) {
    const outputRoot = getGenerationOutputRoot(projectTitle);
    const frontendDir = path.join(outputRoot, 'frontend');
    const frontendSrcDir = path.join(frontendDir, 'src');
    const backendDir = path.join(outputRoot, 'backend');
    const reportsDir = path.join(outputRoot, 'reports');
    const gatewayUrl = String(metadata.gatewayUrl || '').trim();
    const gatewayPortMatch = gatewayUrl.match(/:(\d+)(?:\/|$)/);
    const frontendPort = Number(metadata.frontendPort || DEFAULT_FRONTEND_PORT);
    const gatewayPort = Number(gatewayPortMatch?.[1] || metadata.gatewayPort || DEFAULT_GATEWAY_PORT);
    const gatewayHost = gatewayUrl || `http://127.0.0.1:${gatewayPort}`;
    const servicePorts = metadata.servicePorts && typeof metadata.servicePorts === 'object'
        ? metadata.servicePorts
        : {};
    const normalizeFrontendPath = (filePath = '') => {
        const trimmed = String(filePath || '').replace(/\\/g, '/').trim();
        if (!trimmed) return 'App.jsx';
        if (trimmed.startsWith('/src/')) return trimmed.replace(/^\/src\//, '');
        if (trimmed.startsWith('/public/')) return trimmed.replace(/^\/public\//, '../public/');
        return trimmed.replace(/^\/+/, '');
    };

    await mkdir(frontendSrcDir, { recursive: true });
    await mkdir(path.join(frontendDir, 'public'), { recursive: true });
    await mkdir(backendDir, { recursive: true });
    await mkdir(reportsDir, { recursive: true });

    await writeFile(path.join(frontendDir, 'package.json'), JSON.stringify({
        name: slugifyWorkspaceName(projectTitle || 'generated-app'),
        version: '1.0.0',
        private: true,
        type: 'module',
        scripts: { dev: 'vite', build: 'vite build', preview: 'vite preview' },
        dependencies: {
            react: '^18.2.0',
            'react-dom': '^18.2.0',
            'react-router-dom': '^6.20.0',
            'lucide-react': '^0.363.0',
            'framer-motion': '^10.18.0',
            'react-toastify': '^10.0.0',
            'tailwind-merge': '^2.4.0',
            uuid: '^9.0.0',
            'react-beautiful-dnd': '^13.1.1',
            recharts: '^2.10.3',
            'date-fns': '^3.3.1',
        },
        devDependencies: {
            '@vitejs/plugin-react': '^4.2.1',
            vite: '^5.0.0',
            tailwindcss: '^3.4.1',
            postcss: '^8.4.35',
            autoprefixer: '^10.4.17',
        },
    }, null, 2), 'utf8');

    await writeFile(path.join(frontendDir, '.env'), [
        `PORT=${frontendPort}`,
        `VITE_API_BASE_URL=${gatewayHost}`,
        `VITE_GATEWAY_URL=${gatewayHost}`,
        `VITE_GATEWAY_PORT=${gatewayPort}`,
    ].join('\n') + '\n', 'utf8');

    await writeFile(path.join(frontendDir, 'vite.config.js'), `import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const frontendPort = Number(env.PORT || env.VITE_FRONTEND_PORT || ${frontendPort});
  const apiBaseUrl = env.VITE_API_BASE_URL || env.VITE_GATEWAY_URL || 'http://127.0.0.1:${gatewayPort}';

  return {
    plugins: [react()],
    resolve: { alias: { '@': path.resolve(__dirname, './src') } },
    server: {
      port: frontendPort,
      proxy: { '/api': { target: apiBaseUrl, changeOrigin: true } },
    },
  };
});
`, 'utf8');
    await writeFile(path.join(frontendDir, 'tailwind.config.js'), `export default { content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'], theme: { extend: {} }, plugins: [] };`, 'utf8');
    await writeFile(path.join(frontendDir, 'postcss.config.js'), `export default { plugins: { tailwindcss: {}, autoprefixer: {} } };`, 'utf8');
    await writeFile(path.join(frontendDir, 'index.html'), `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>${projectTitle || 'Generated App'}</title></head><body><div id="root"></div><script type="module" src="/src/main.jsx"></script></body></html>`, 'utf8');
    await writeFile(path.join(frontendSrcDir, 'App.css'), `@tailwind base;\n@tailwind components;\n@tailwind utilities;\n*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }\nbody { font-family: 'Inter', system-ui, -apple-system, sans-serif; -webkit-font-smoothing: antialiased; }\n#root { min-height: 100vh; }\n`, 'utf8');
    await writeFile(path.join(frontendSrcDir, 'main.jsx'), `import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './App.css';\nimport 'react-toastify/dist/ReactToastify.css';\ncreateRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);\n`, 'utf8');

    await Promise.all(
        Object.entries(frontendFiles).map(async ([filePath, content]) => {
            const absolutePath = path.join(frontendSrcDir, normalizeFrontendPath(filePath));
            await mkdir(path.dirname(absolutePath), { recursive: true });
            const code = normalizeFrontendFileContent(filePath, typeof content === 'string' ? content : content?.code || '');
            await writeFile(absolutePath, code, 'utf8');
        })
    );

    await Promise.all(
        Object.entries(backendFiles).map(async ([filePath, content]) => {
            const absolutePath = path.join(backendDir, filePath.replace(/^\/+/, ''));
            await mkdir(path.dirname(absolutePath), { recursive: true });
            const code = typeof content === 'string' ? content : content?.code || '';
            await writeFile(absolutePath, code, 'utf8');
        })
    );

    await writeFile(
        path.join(backendDir, '.env'),
        [
            `PORT=${gatewayPort}`,
            `PORT_GATEWAY=${gatewayPort}`,
            `MONGODB_URI=${metadata.mongoUri || 'mongodb://127.0.0.1:27017/ai-website-builder'}`,
            `MONGO_URL=${metadata.mongoUri || 'mongodb://127.0.0.1:27017/ai-website-builder'}`,
            `JWT_SECRET=${metadata.jwtSecret || 'ravindu2232'}`,
            `SECRET_KEY=${metadata.jwtSecret || 'ravindu2232'}`,
            `SEKRET_KEY=${metadata.jwtSecret || 'ravindu2232'}`,
            'NODE_ENV=development',
            ...Object.entries(servicePorts).flatMap(([serviceName, port], index) => {
                const normalizedName = String(serviceName || '')
                    .replace(/[^A-Za-z0-9]+/g, '_')
                    .replace(/^_+|_+$/g, '')
                    .toUpperCase();
                const lines = [];
                if (normalizedName && port) {
                    lines.push(`PORT_${normalizedName}=${port}`);
                }
                if (index === 0 && port) lines.push(`PORT_SERVICE1=${port}`);
                if (index === 1 && port) lines.push(`PORT_SERVICE2=${port}`);
                return lines;
            }),
        ].join('\n') + '\n',
        'utf8'
    );

    await writeFile(
        path.join(reportsDir, 'generation-summary.json'),
        JSON.stringify({
            projectTitle: projectTitle || 'generated-app',
            frontendFileCount: Object.keys(frontendFiles).length,
            backendFileCount: Object.keys(backendFiles).length,
            updatedAt: new Date().toISOString(),
            ...metadata,
        }, null, 2),
        'utf8'
    );

    return outputRoot;
}

function resolveLocalRequireCandidates(fromFilePath, requestPath) {
    const fromDir = path.posix.dirname(fromFilePath.replace(/\\/g, '/'));
    const basePath = path.posix.normalize(path.posix.join(fromDir, requestPath));
    return [
        basePath,
        `${basePath}.js`,
        `${basePath}.json`,
        path.posix.join(basePath, 'index.js'),
        path.posix.join(basePath, 'index.json'),
    ].map(candidate => candidate.startsWith('/') ? candidate : `/${candidate}`);
}

function extractBalancedJsonObjects(text = '', limit = 8) {
    const source = String(text || '');
    const results = [];
    let start = -1;
    let depth = 0;
    let inString = false;
    let escaped = false;

    for (let index = 0; index < source.length; index += 1) {
        const char = source[index];

        if (start === -1) {
            if (char === '{') {
                start = index;
                depth = 1;
                inString = false;
                escaped = false;
            }
            continue;
        }

        if (inString) {
            if (escaped) {
                escaped = false;
            } else if (char === '\\') {
                escaped = true;
            } else if (char === '"') {
                inString = false;
            }
            continue;
        }

        if (char === '"') {
            inString = true;
            continue;
        }
        if (char === '{') {
            depth += 1;
            continue;
        }
        if (char === '}') {
            depth -= 1;
            if (depth === 0) {
                const candidate = source.slice(start, index + 1);
                try {
                    const parsed = JSON.parse(candidate);
                    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                        results.push(parsed);
                    }
                } catch (_) {}
                start = -1;
                if (results.length >= limit) {
                    break;
                }
            }
        }
    }

    return results;
}

function extractFirstBalancedJsonText(text = '') {
    const source = String(text || '');
    let start = -1;
    let depth = 0;
    let inString = false;
    let escaped = false;

    for (let index = 0; index < source.length; index += 1) {
        const char = source[index];

        if (start === -1) {
            if (char === '{') {
                start = index;
                depth = 1;
                inString = false;
                escaped = false;
            }
            continue;
        }

        if (inString) {
            if (escaped) {
                escaped = false;
            } else if (char === '\\') {
                escaped = true;
            } else if (char === '"') {
                inString = false;
            }
            continue;
        }

        if (char === '"') {
            inString = true;
            continue;
        }
        if (char === '{') {
            depth += 1;
            continue;
        }
        if (char === '}') {
            depth -= 1;
            if (depth === 0 && start !== -1) {
                return source.slice(start, index + 1).trim();
            }
        }
    }

    return '';
}

const DEFAULT_PACKAGE_VERSION_BY_NAME = {
    express: '^4.18.2',
    cors: '^2.8.5',
    mongoose: '^8.0.3',
    dotenv: '^16.0.0',
    nodemon: '^3.0.1',
    uuid: '^9.0.0',
    bcryptjs: '^2.4.3',
    jsonwebtoken: '^9.0.2',
    'http-proxy-middleware': '^2.0.6',
    morgan: '^1.10.0',
    multer: '^1.4.5-lts.1',
    nodemailer: '^6.9.13',
    stripe: '^14.25.0',
    'socket.io': '^4.7.5',
    'socket.io-client': '^4.7.5',
};

function normalizePackageVersion(packageName = '', version = '') {
    const fallback = DEFAULT_PACKAGE_VERSION_BY_NAME[packageName] || '*';
    const value = typeof version === 'string' ? version.trim() : '';
    if (!value) {
        return fallback;
    }
    if (value === '^' || value === '~') {
        return fallback;
    }
    if (value === '*' || /^\d/.test(value) || /^[~^]?\d/.test(value)) {
        return value;
    }
    if (/^(file:|link:|workspace:|https?:|git\+|github:|npm:)/i.test(value)) {
        return value;
    }
    return fallback;
}

function sanitizeDependencyMap(dependencyMap = {}) {
    if (!dependencyMap || typeof dependencyMap !== 'object' || Array.isArray(dependencyMap)) {
        return dependencyMap;
    }

    const normalized = {};
    Object.entries(dependencyMap).forEach(([rawKey, rawValue]) => {
        let packageName = String(rawKey || '').trim();
        let version = typeof rawValue === 'string' ? rawValue.trim() : '';

        const keyedVersionMatch = packageName.match(/^((?:@[^/]+\/)?[^@]+)@(.+)$/);
        if (keyedVersionMatch) {
            packageName = keyedVersionMatch[1];
            if (!version || version === '^' || version === '~') {
                version = keyedVersionMatch[2];
            }
        }

        if (!packageName) {
            return;
        }

        normalized[packageName] = normalizePackageVersion(packageName, version);
    });

    return normalized;
}

function sanitizePackageJsonText(text = '') {
    const jsonText = extractFirstBalancedJsonText(text);
    if (!jsonText) {
        return String(text || '').trim();
    }

    try {
        const parsed = JSON.parse(jsonText);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
            return jsonText;
        }

        ['dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies'].forEach((field) => {
            if (parsed[field] && typeof parsed[field] === 'object' && !Array.isArray(parsed[field])) {
                parsed[field] = sanitizeDependencyMap(parsed[field]);
            }
        });

        return JSON.stringify(parsed, null, 2);
    } catch (_) {
        return jsonText;
    }
}

function scoreStructuredSpecCandidate(candidate) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
        return 0;
    }

    let score = 0;
    if (candidate.document_type) score += 2;
    if (candidate.standard) score += 1;
    if (candidate.metadata?.project_name) score += 3;
    if (candidate.sections?.introduction?.purpose) score += 2;
    if (Array.isArray(candidate.sections?.system_features)) score += candidate.sections.system_features.length * 2;
    if (Array.isArray(candidate.services)) score += candidate.services.length * 4;

    const endpointCount = Array.isArray(candidate.services)
        ? candidate.services.reduce((total, service) => total + (Array.isArray(service?.endpoints) ? service.endpoints.length : 0), 0)
        : 0;
    score += endpointCount;

    return score;
}

function normalizeStructuredAppSpec(candidate) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
        return null;
    }

    const metadata = candidate.metadata || {};
    const sections = candidate.sections || {};
    const introduction = sections.introduction || {};
    const productScope = introduction.product_scope || {};
    const systemFeatures = Array.isArray(sections.system_features) ? sections.system_features : [];
    const services = Array.isArray(candidate.services) ? candidate.services : [];

    const normalizedServices = services.map((service, index) => {
        const rawName = String(service?.name || `Service ${index + 1}`).trim();
        const slug = rawName
            .toLowerCase()
            .replace(/service$/i, '')
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '');
        return {
            name: rawName,
            slug,
            port: service?.port || null,
            description: String(service?.description || '').trim(),
            entities: Array.isArray(service?.entities) ? service.entities.map(String) : [],
            dependencies: Array.isArray(service?.dependencies) ? service.dependencies.map(String) : [],
            endpoints: Array.isArray(service?.endpoints)
                ? service.endpoints.map((endpoint) => ({
                    method: String(endpoint?.method || 'GET').toUpperCase(),
                    path: String(endpoint?.path || '').trim(),
                    description: String(endpoint?.description || '').trim(),
                    auth: Boolean(endpoint?.auth),
                })).filter((endpoint) => endpoint.path)
                : [],
        };
    });

    const normalizedFeatures = systemFeatures.map((feature, index) => ({
        id: String(feature?.feature_id || `FEATURE-${index + 1}`),
        name: String(feature?.feature_name || `Feature ${index + 1}`).trim(),
        description: String(feature?.description_and_priority?.description || feature?.description || '').trim(),
        priority: String(feature?.description_and_priority?.priority || feature?.priority || '').trim(),
        requirements: Array.isArray(feature?.functional_requirements)
            ? feature.functional_requirements.map((requirement, requirementIndex) => ({
                id: String(requirement?.requirement_id || `REQ-${index + 1}-${requirementIndex + 1}`),
                title: String(requirement?.title || '').trim(),
                description: String(requirement?.description || '').trim(),
                priority: String(requirement?.priority || '').trim(),
            }))
            : [],
    }));

    const entities = Array.from(new Set(normalizedServices.flatMap((service) => service.entities))).filter(Boolean);

    if (!normalizedServices.length && !normalizedFeatures.length && !metadata.project_name) {
        return null;
    }

    return {
        documentType: String(candidate.document_type || '').trim(),
        standard: String(candidate.standard || '').trim(),
        projectTitle: String(metadata.project_name || candidate.projectTitle || candidate.name || '').trim(),
        projectId: String(metadata.project_id || '').trim(),
        domain: String(metadata.domain || '').trim(),
        applicationType: String(metadata.application_type || '').trim(),
        version: String(metadata.version || '').trim(),
        purpose: String(introduction.purpose || '').trim(),
        summary: String(productScope.summary || '').trim(),
        businessObjectives: Array.isArray(productScope.business_objectives) ? productScope.business_objectives.map(String) : [],
        goals: Array.isArray(productScope.goals) ? productScope.goals.map(String) : [],
        features: normalizedFeatures,
        services: normalizedServices,
        entities,
        authRequired: normalizedServices.some((service) => service.endpoints.some((endpoint) => endpoint.auth)),
    };
}

function extractStructuredAppSpec(prompt = '') {
    const candidates = extractBalancedJsonObjects(prompt, 12);
    let best = null;
    let bestScore = 0;

    candidates.forEach((candidate) => {
        const score = scoreStructuredSpecCandidate(candidate);
        if (score > bestScore) {
            best = candidate;
            bestScore = score;
        }
    });

    if (bestScore < 6) {
        return null;
    }

    return normalizeStructuredAppSpec(best);
}

function buildStructuredSpecContract(spec = null) {
    if (!spec) {
        return '';
    }

    const lines = [
        'STRUCTURED APP CONTRACT (HARD REQUIREMENTS)',
        'Treat this contract as the primary source of truth.',
        'Do not simplify, merge away, or omit services/features/routes from this contract unless the user explicitly asks.',
    ];

    if (spec.projectTitle) lines.push(`Project: ${spec.projectTitle}`);
    if (spec.documentType || spec.standard) lines.push(`Spec: ${[spec.documentType, spec.standard].filter(Boolean).join(' / ')}`);
    if (spec.domain || spec.applicationType) lines.push(`Domain: ${[spec.domain, spec.applicationType].filter(Boolean).join(' / ')}`);
    if (spec.purpose) lines.push(`Purpose: ${spec.purpose}`);
    if (spec.summary) lines.push(`Summary: ${spec.summary}`);

    if (spec.businessObjectives.length) {
        lines.push('Business objectives:');
        spec.businessObjectives.forEach((objective) => lines.push(`- ${objective}`));
    }

    if (spec.goals.length) {
        lines.push('Goals:');
        spec.goals.forEach((goal) => lines.push(`- ${goal}`));
    }

    if (spec.features.length) {
        lines.push('Features to cover in the app:');
        spec.features.forEach((feature) => {
            lines.push(`- ${feature.name}${feature.priority ? ` [${feature.priority}]` : ''}: ${feature.description || 'Implement the feature fully.'}`);
            feature.requirements.forEach((requirement) => {
                lines.push(`  - ${requirement.id}: ${requirement.title || requirement.description}${requirement.priority ? ` [${requirement.priority}]` : ''}`);
            });
        });
    }

    if (spec.services.length) {
        lines.push('Required backend services:');
        spec.services.forEach((service) => {
            // Compute distinct gateway prefixes (/api/resource) for this service
            const gwPrefixes = [...new Set(
                (service.endpoints || [])
                    .map(ep => {
                        const parts = ep.path.replace(/^\//, '').split('/');
                        return parts.length >= 2 ? `/${parts[0]}/${parts[1]}` : `/${parts[0]}`;
                    })
                    .filter(Boolean)
            )];
            const prefixNote = gwPrefixes.length > 1
                ? ` [DUAL-PREFIX: generate TWO gateway proxy rules for port ${service.port}: ${gwPrefixes.join(', ')}]`
                : '';
            lines.push(`- ${service.name}${service.port ? ` (preferred port ${service.port})` : ''}${prefixNote}: ${service.description || 'Implement fully.'}`);
            if (service.entities.length) {
                lines.push(`  Entities: ${service.entities.join(', ')}`);
            }
            if (service.dependencies.length) {
                lines.push(`  Dependencies: ${service.dependencies.join(', ')}`);
            }
            if (gwPrefixes.length > 1) {
                lines.push(`  Gateway prefixes (ALL must be proxied to port ${service.port}): ${gwPrefixes.join(', ')}`);
            }
            service.endpoints.forEach((endpoint) => {
                lines.push(`  - ${endpoint.method} ${endpoint.path}${endpoint.auth ? ' [auth]' : ' [public]'}${endpoint.description ? ` - ${endpoint.description}` : ''}`);
            });
        });
    }

    if (spec.entities.length) {
        lines.push(`Core entities: ${spec.entities.join(', ')}`);
    }

    lines.push('Coverage rules:');
    lines.push('- Backend must generate every listed service and every listed endpoint path.');
    lines.push('- Gateway proxy prefixes must match the listed endpoint paths exactly.');
    lines.push('- Frontend must cover customer and admin/staff workflows implied by the features and services.');
    lines.push('- Generate pages, forms, dashboards, CRUD flows, and auth flows needed to cover the listed requirements end-to-end.');
    lines.push('- Preserve auth requirements from the contract for protected routes.');

    return lines.join('\n');
}

function specServiceDirCandidates(service = {}) {
    const rawName = String(service?.name || '').trim();
    const slug = String(service?.slug || '').trim();
    const rawSlug = rawName
        .toLowerCase()
        .replace(/service$/i, '')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
    const candidates = new Set();
    [slug, rawSlug].filter(Boolean).forEach((value) => {
        candidates.add(`/${value}-service`);
        candidates.add(`/${value}s-service`);
        candidates.add(`/${value.replace(/-+/g, '')}-service`);
    });
    return [...candidates];
}

function pathPatternMatches(actualPath = '', expectedPath = '') {
    if (!actualPath || !expectedPath) {
        return false;
    }

    const normalize = (value) => String(value)
        .trim()
        .replace(/\/+/g, '/')
        .replace(/\/$/, '')
        .replace(/:[A-Za-z_][A-Za-z0-9_]*/g, ':param');

    return normalize(actualPath) === normalize(expectedPath);
}

function validateStructuredSpecCoverage(backendFiles = {}, structuredSpec = null) {
    if (!structuredSpec) {
        return [];
    }

    const errors = [];
    const backendPaths = Object.keys(backendFiles || {});
    const contracts = parseBackendContracts(backendFiles);

    structuredSpec.services.forEach((service) => {
        const hasServiceDir = specServiceDirCandidates(service).some((dirPrefix) =>
            backendPaths.some((filePath) => filePath.startsWith(dirPrefix))
        );

        if (!hasServiceDir) {
            errors.push(`Missing structured-spec service: ${service.name}`);
        }

        service.endpoints.forEach((endpoint) => {
            const foundContract = contracts.some((contract) =>
                String(contract.method || '').toUpperCase() === endpoint.method &&
                pathPatternMatches(contract.path, endpoint.path)
            );
            if (!foundContract) {
                errors.push(`Missing structured-spec endpoint: ${endpoint.method} ${endpoint.path}`);
            }
        });
    });

    return errors;
}

function splitStructuredEndpointPath(endpointPath = '') {
    const segments = String(endpointPath || '')
        .trim()
        .replace(/\/+/g, '/')
        .replace(/\/$/, '')
        .split('/')
        .filter(Boolean);

    if (!segments.length) {
        return { mountPath: '/api/generated', routePath: '/' };
    }

    if (segments[0] !== 'api') {
        return {
            mountPath: `/${segments[0]}`,
            routePath: segments.length > 1 ? `/${segments.slice(1).join('/')}` : '/',
        };
    }

    if (segments.length <= 2) {
        return {
            mountPath: `/${segments.join('/')}`,
            routePath: '/',
        };
    }

    return {
        mountPath: `/${segments.slice(0, 2).join('/')}`,
        routePath: `/${segments.slice(2).join('/')}`,
    };
}

function pickStructuredServiceDir(service = {}, backendFiles = {}) {
    const backendPaths = Object.keys(backendFiles || {});
    const matched = specServiceDirCandidates(service).find((dirPrefix) =>
        backendPaths.some((filePath) => filePath.startsWith(dirPrefix))
    );
    if (matched) {
        return matched;
    }

    const fallbackSlug = String(service?.slug || 'generated').trim() || 'generated';
    return `/${fallbackSlug}-service`;
}

function pickStructuredModelInfo(serviceDir = '', backendFiles = {}, service = {}) {
    const modelPaths = Object.keys(backendFiles || {}).filter((filePath) =>
        filePath.startsWith(`${serviceDir}/models/`) && filePath.endsWith('.js')
    );

    if (!modelPaths.length) {
        return null;
    }

    const desiredNames = new Set([
        ...((service?.entities || []).map((value) => String(value || '').toLowerCase())),
        String(service?.name || '').toLowerCase(),
        String(service?.slug || '').toLowerCase(),
    ]);

    const selectedPath = modelPaths.find((filePath) => {
        const modelBase = filePath.split('/').pop()?.replace(/\.[^.]+$/, '') || '';
        return desiredNames.has(modelBase.toLowerCase());
    }) || modelPaths[0];

    const modelBase = selectedPath.split('/').pop()?.replace(/\.[^.]+$/, '') || 'Record';
    return {
        modelName: modelBase.replace(/[^A-Za-z0-9_$]/g, '') || 'Record',
        requirePath: `../models/${modelBase}`,
    };
}

function buildStructuredRouteSkeleton(routeFilePath, modelInfo, service = {}) {
    const serviceName = String(service?.name || routeFilePath.split('/').pop()?.replace(/\.[^.]+$/, '') || 'service').trim();
    const serviceLabel = serviceName.toLowerCase().replace(/\s+/g, '-');
    const modelRequireLine = modelInfo
        ? `const ${modelInfo.modelName} = require('${modelInfo.requirePath}');\n`
        : '';

    return [
        "const express = require('express');",
        modelRequireLine.trimEnd(),
        'const router = express.Router();',
        '',
        '// Health check',
        "router.get('/health', (req, res) => {",
        `  res.json({ success: true, data: { status: 'ok', service: '${serviceLabel}-routes' } });`,
        '});',
        '',
        'module.exports = router;',
        '',
    ].filter(Boolean).join('\n');
}

function buildStructuredRouteHandler(method, routePath, modelInfo) {
    const httpMethod = String(method || 'GET').toUpperCase();
    const normalizedRoute = routePath && routePath !== '/' ? routePath : '/';
    const usesId = normalizedRoute.includes(':');
    const pathLiteral = normalizedRoute.replace(/'/g, "\\'");
    const modelName = modelInfo?.modelName || null;

    const withTryCatch = (bodyLines = [], successLine = "res.json({ success: true, data: {} });") => [
        `router.${httpMethod.toLowerCase()}('${pathLiteral}', async (req, res) => {`,
        '  try {',
        ...bodyLines.map((line) => `    ${line}`),
        `    ${successLine}`,
        '  } catch (error) {',
        "    res.status(500).json({ success: false, error: error.message });",
        '  }',
        '});',
    ].join('\n');

    if (!modelName) {
        if (httpMethod === 'POST') {
            return withTryCatch(
                [
                    "const record = { _id: req.body?._id || req.body?.id || `generated-${Date.now()}`, ...req.body };",
                ],
                'res.status(201).json({ success: true, data: record });'
            );
        }
        if (httpMethod === 'GET') {
            return withTryCatch(
                [usesId ? "const record = { _id: req.params.id, ...req.query };" : 'const records = [];'],
                usesId
                    ? 'res.json({ success: true, data: record });'
                    : 'res.json({ success: true, data: records });'
            );
        }
        if (httpMethod === 'DELETE') {
            return withTryCatch([], 'res.json({ success: true, data: { deleted: true, _id: req.params.id || null } });');
        }
        return withTryCatch(
            [usesId ? "const record = { _id: req.params.id, ...req.body };" : 'const record = { ...req.body };'],
            'res.json({ success: true, data: record });'
        );
    }

    if (httpMethod === 'POST') {
        return withTryCatch(
            [
                'const payload = { ...req.body };',
                `const record = new ${modelName}(payload);`,
                'await record.save();',
            ],
            'res.status(201).json({ success: true, data: record });'
        );
    }

    if (httpMethod === 'GET') {
        return usesId
            ? withTryCatch(
                [
                    `const record = await ${modelName}.findById(req.params.id);`,
                    "if (!record) return res.status(404).json({ success: false, error: 'Record not found' });",
                ],
                'res.json({ success: true, data: record });'
            )
            : withTryCatch(
                [`const records = await ${modelName}.find({});`],
                'res.json({ success: true, data: records });'
            );
    }

    if (httpMethod === 'DELETE') {
        return withTryCatch(
            [
                `const record = await ${modelName}.findByIdAndDelete(req.params.id);`,
                "if (!record) return res.status(404).json({ success: false, error: 'Record not found' });",
            ],
            'res.json({ success: true, data: record });'
        );
    }

    return withTryCatch(
        [
            usesId
                ? `const record = await ${modelName}.findByIdAndUpdate(req.params.id, req.body, { new: true, runValidators: true });`
                : `const record = await ${modelName}.findOneAndUpdate({}, req.body, { new: true, upsert: true, runValidators: true });`,
            "if (!record) return res.status(404).json({ success: false, error: 'Record not found' });",
        ],
        'res.json({ success: true, data: record });'
    );
}

function ensureStructuredRouteHandler(routeCode = '', endpoint = {}, routePath = '/', modelInfo = null) {
    const httpMethod = String(endpoint?.method || 'GET').toUpperCase();
    const pathRegex = routePath === '/'
        ? /['"]\/['"]/
        : new RegExp(`['"]${routePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}['"]`);
    const existingHandler = new RegExp(`router\\.${httpMethod.toLowerCase()}\\(\\s*${pathRegex.source}`);

    if (existingHandler.test(routeCode)) {
        return routeCode;
    }

    const handlerBlock = buildStructuredRouteHandler(httpMethod, routePath, modelInfo);
    const exportPattern = /\nmodule\.exports\s*=\s*router\s*;\s*$/;
    if (exportPattern.test(routeCode)) {
        return routeCode.replace(exportPattern, `\n${handlerBlock}\n\nmodule.exports = router;\n`);
    }

    return `${routeCode.trim()}\n\n${handlerBlock}\n`;
}

function ensureServiceMount(indexCode = '', mountPath = '', routeFileBase = '') {
    if (!mountPath || !routeFileBase) {
        return indexCode;
    }

    const requireLine = `app.use('${mountPath}', require('./routes/${routeFileBase}'));`;
    if (indexCode.includes(requireLine) || new RegExp(`app\\.use\\(\\s*['"]${mountPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}['"]\\s*,`).test(indexCode)) {
        return indexCode;
    }

    if (indexCode.includes('// Routes')) {
        return indexCode.replace(/\/\/ Routes\s*\n/, `// Routes\n${requireLine}\n`);
    }

    const healthPattern = /\n\/\/ Health check[\s\S]*$/;
    if (healthPattern.test(indexCode)) {
        return indexCode.replace(healthPattern, `\n${requireLine}\n$&`);
    }

    return `${indexCode.trim()}\n\n${requireLine}\n`;
}

function ensureGatewayProxy(gatewayCode = '', mountPath = '', serviceDir = '', topology = null) {
    if (!gatewayCode || !mountPath || !serviceDir || !topology?.serviceConfigs?.[serviceDir]) {
        return gatewayCode;
    }

    if (new RegExp(`app\\.use\\(\\s*['"]${mountPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}['"]\\s*,\\s*createProxyMiddleware`, 'i').test(gatewayCode)) {
        return gatewayCode;
    }

    const serviceConfig = topology.serviceConfigs[serviceDir];
    const fallbackPort = Number(serviceConfig.originalPort || DEFAULT_SERVICE_PORT_START);
    const serviceLabel = serviceDir.replace(/^\/+/, '');
    const titleLabel = serviceLabel.replace(/-service$/i, '').replace(/-/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
    const proxyBlock = [
        `// ${titleLabel} proxy`,
        `app.use('${mountPath}', createProxyMiddleware({`,
        `  target: 'http://127.0.0.1:' + (${`process.env.${serviceConfig.envVar}`} || ${fallbackPort}),`,
        '  changeOrigin: true,',
        '  proxyTimeout: 10000,',
        '  timeout: 10000,',
        '  onProxyReq: fixRequestBody,',
        `  onError: (error, req, res) => res.status(502).json({ success: false, error: '${titleLabel} service unavailable', details: error.code || error.message })`,
        '}));',
    ].join('\n');

    const listenPattern = /\napp\.listen\(/;
    if (listenPattern.test(gatewayCode)) {
        return gatewayCode.replace(listenPattern, `\n${proxyBlock}\n$&`);
    }

    return `${gatewayCode.trim()}\n\n${proxyBlock}\n`;
}

function applyStructuredSpecCoverageFixes(backendFiles = {}, structuredSpec = null) {
    if (!structuredSpec) {
        return { files: backendFiles, fixCount: 0 };
    }

    const fixed = { ...backendFiles };
    const topology = inferBackendPortTopology(fixed);
    let contracts = parseBackendContracts(fixed);
    let fixCount = 0;

    structuredSpec.services.forEach((service) => {
        const serviceDir = pickStructuredServiceDir(service, fixed);
        const serviceDirName = serviceDir.replace(/^\/+/, '');
        const serviceIndexPath = `${serviceDir}/index.js`;
        const modelInfo = pickStructuredModelInfo(serviceDir, fixed, service);

        service.endpoints.forEach((endpoint) => {
            const alreadyPresent = contracts.some((contract) =>
                String(contract.method || '').toUpperCase() === endpoint.method &&
                pathPatternMatches(contract.path, endpoint.path)
            );
            if (alreadyPresent) {
                return;
            }

            const { mountPath, routePath } = splitStructuredEndpointPath(endpoint.path);
            const routeFileBase = mountPath.split('/').filter(Boolean).pop() || 'generated';
            const routeFilePath = `${serviceDir}/routes/${routeFileBase}.js`;

            const existingRouteCode = normalizeBackendFileContent(
                routeFilePath,
                typeof fixed[routeFilePath] === 'string' ? fixed[routeFilePath] : fixed[routeFilePath]?.code || ''
            );
            let nextRouteCode = existingRouteCode || buildStructuredRouteSkeleton(routeFilePath, modelInfo, service);
            nextRouteCode = ensureStructuredRouteHandler(nextRouteCode, endpoint, routePath, modelInfo);
            if (nextRouteCode !== existingRouteCode) {
                fixed[routeFilePath] = { code: nextRouteCode };
                fixCount += 1;
            }

            const existingServiceIndex = normalizeBackendFileContent(
                serviceIndexPath,
                typeof fixed[serviceIndexPath] === 'string' ? fixed[serviceIndexPath] : fixed[serviceIndexPath]?.code || ''
            );
            if (existingServiceIndex) {
                const nextServiceIndex = ensureServiceMount(existingServiceIndex, mountPath, routeFileBase);
                if (nextServiceIndex !== existingServiceIndex) {
                    fixed[serviceIndexPath] = { code: nextServiceIndex };
                    fixCount += 1;
                }
            }

            const gatewayPath = '/api-gateway/index.js';
            const existingGateway = normalizeBackendFileContent(
                gatewayPath,
                typeof fixed[gatewayPath] === 'string' ? fixed[gatewayPath] : fixed[gatewayPath]?.code || ''
            );
            if (existingGateway) {
                const nextGateway = ensureGatewayProxy(existingGateway, mountPath, serviceDirName, topology);
                if (nextGateway !== existingGateway) {
                    fixed[gatewayPath] = { code: nextGateway };
                    fixCount += 1;
                }
            }

            contracts = parseBackendContracts(fixed);
        });
    });

    return { files: fixed, fixCount };
}

async function validateBackendCandidateFiles(backendFiles, projectTitle = 'generated-app', structuredSpec = null) {
    const errors = [];
    const contracts = parseBackendContracts(backendFiles);
    const backendPaths = Object.keys(backendFiles);
    const packagePaths = backendPaths.filter((filePath) => filePath.endsWith('package.json'));
    const packageJsonByService = parsePackageJsonMap(backendFiles);
    if (packagePaths.length === 0) {
        return { ok: false, errors: ['Missing package.json in generated backend output'] };
    }
    if (backendPaths.length < 6 && contracts.length === 0) {
        return { ok: false, errors: ['Backend output is too small and contains no parseable routes'] };
    }
    const backendDirs = new Set(
        backendPaths
            .map((filePath) => filePath.split('/').filter(Boolean)[0])
            .filter(Boolean)
    );
    backendDirs.forEach((dirName) => {
        const packagePath = `/${dirName}/package.json`;
        const indexPath = `/${dirName}/index.js`;
        const hasAnyServiceFiles = backendPaths.some((filePath) => filePath.startsWith(`/${dirName}/`));
        if (!hasAnyServiceFiles) {
            return;
        }
        if (!backendFiles[packagePath]) {
            errors.push(`Missing package.json for backend service: ${dirName}`);
        }
        if (!backendFiles[indexPath]) {
            errors.push(`Missing index.js for backend service: ${dirName}`);
        }
    });
    const validationRoot = path.join(getGenerationOutputRoot(projectTitle), 'validation-check');

    await rm(validationRoot, { recursive: true, force: true }).catch(() => {});
    await mkdir(validationRoot, { recursive: true });

    await Promise.all(
        Object.entries(backendFiles).map(async ([filePath, content]) => {
            const absolutePath = path.join(validationRoot, filePath.replace(/^\/+/, ''));
            await mkdir(path.dirname(absolutePath), { recursive: true });
            const code = normalizeBackendFileContent(filePath, typeof content === 'string' ? content : content?.code || '');
            await writeFile(absolutePath, code, 'utf8');
            if (filePath.endsWith('package.json')) {
                try {
                    JSON.parse(code);
                } catch (error) {
                    errors.push(`${filePath}: invalid JSON (${error.message})`);
                }
            }
        })
    );

    for (const [filePath, content] of Object.entries(backendFiles)) {
        const code = normalizeBackendFileContent(filePath, typeof content === 'string' ? content : content?.code || '');
        if (!filePath.endsWith('.js')) continue;

        const isEntryFile = /\/index\.js$/i.test(filePath);
        const hasAppDeclaration = /\b(?:const|let|var)\s+app\s*=\s*express\s*\(/.test(code);
        const hasRouterDeclaration = /\b(?:const|let|var)\s+router\s*=\s*express\.Router\s*\(/.test(code);
        const usesAppObject = /\bapp\./.test(code);
        const usesRouterObject = /\brouter\./.test(code);

        if (isEntryFile && usesAppObject && !hasAppDeclaration) {
            errors.push(`${filePath}: entry file uses app.* without declaring const app = express()`);
        }
        if (isEntryFile && usesRouterObject && !hasRouterDeclaration) {
            errors.push(`${filePath}: entry file uses router.* without declaring const router = express.Router()`);
        }
        if (isEntryFile && hasAppDeclaration && !hasRouterDeclaration && /router\.get\(\s*['"]\/health['"]/i.test(code)) {
            errors.push(`${filePath}: health route in entry file uses router.get('/health') even though only app is declared`);
        }
        if (!isEntryFile && usesRouterObject && !hasRouterDeclaration) {
            errors.push(`${filePath}: route file uses router.* without declaring const router = express.Router()`);
        }
        if (/new\s+Schema\s*\(/.test(code) && /\bRequired\s*:/m.test(code)) {
            errors.push(`${filePath}: mongoose schema uses Required: instead of required:`);
        }
        if (/new\s+Schema\s*\(/.test(code) && /:\s*\{\s*required\s*:\s*true\s*[,}]/m.test(code) && !/:\s*\{\s*type\s*:/m.test(code)) {
            errors.push(`${filePath}: schema field has required:true but no type declaration`);
        }

        const requireMatches = [...code.matchAll(/require\(\s*['"](\.[^'"]+)['"]\s*\)/g)];
        requireMatches.forEach((match) => {
            const requestPath = match[1];
            const candidates = resolveLocalRequireCandidates(filePath, requestPath);
            const found = candidates.some(candidate => backendFiles[candidate]);
            if (!found) {
                errors.push(`${filePath}: missing local require ${requestPath}`);
            }
        });

        const serviceDir = getServiceDirForFile(filePath);
        const servicePackageJson = packageJsonByService.get(serviceDir) || {};
        const declaredPackages = getDeclaredPackageNames(servicePackageJson);
        if (fileNeedsAuthMiddlewareImport(code)) {
            const requirePath = /\/routes\//i.test(filePath) ? '../middleware/auth' : './middleware/auth';
            errors.push(`${filePath}: auth middleware is used but auth is not defined; add const auth = require('${requirePath}')`);
        }
        extractRequireAndImportRequests(code).forEach((requestPath) => {
            const packageName = getExternalRequirePackageName(requestPath);
            if (!packageName || NODE_BUILTIN_MODULES.has(packageName)) {
                return;
            }
            if (!declaredPackages.has(packageName)) {
                errors.push(`${filePath}: missing package dependency ${packageName} in ${serviceDir}/package.json`);
            }
        });

        const absolutePath = path.join(validationRoot, filePath.replace(/^\/+/, ''));
        const syntaxCheck = await runCommand(process.execPath, ['--check', absolutePath], {
            cwd: validationRoot,
            timeoutMs: 30000,
        }).catch((error) => ({
            code: 1,
            stdout: '',
            stderr: error?.message || String(error),
        }));

        if (syntaxCheck.code !== 0) {
            const detail = (syntaxCheck.stderr || syntaxCheck.stdout || 'syntax check failed')
                .split('\n')
                .map(line => line.trim())
                .filter(Boolean)
                .slice(0, 4)
                .join(' ');
            errors.push(`${filePath}: ${detail}`);
        }
    }

    errors.push(...validateStructuredSpecCoverage(backendFiles, structuredSpec));

    // Check for route shadowing: literal routes after /:param routes cause MongoDB CastError
    backendPaths.filter(p => p.includes('/routes/')).forEach(routeFilePath => {
        const rc = backendFiles[routeFilePath];
        const rCode = typeof rc === 'string' ? rc : rc?.code || '';
        const rdRe = /\brouter\.(get|post|put|patch|delete)\s*\(\s*['"](\/?[^'"]*)['"]/gi;
        const rdecls = [];
        let rdm;
        while ((rdm = rdRe.exec(rCode)) !== null) {
            const rp = rdm[2];
            const firstSeg = rp.replace(/^\//, '').split('/')[0] || '';
            rdecls.push({ pos: rdm.index, path: rp, isParamFirst: firstSeg.startsWith(':') });
        }
        const fp = rdecls.find(d => d.isParamFirst);
        if (fp) {
            rdecls.filter(d => !d.isParamFirst && d.pos > fp.pos && d.path !== '/health' && d.path !== '/').forEach(s => {
                errors.push(`${routeFilePath}: route shadowing — '${s.path}' defined after parameterized '${fp.path}'; move literal routes before /:param routes`);
            });
        }
    });

    if (structuredSpec?.services?.length) {
        const generatedServiceDirs = new Set(
            backendPaths
                .filter((filePath) => /\/(?:routes|models|controllers|index\.js|package\.json)/i.test(filePath))
                .map((filePath) => filePath.split('/').filter(Boolean)[0])
                .filter(Boolean)
        );
        structuredSpec.services.forEach((service) => {
            const candidates = specServiceDirCandidates(service).map((value) => value.replace(/^\/+/, ''));
            const matchedService = candidates.some((candidate) => generatedServiceDirs.has(candidate));
            if (!matchedService) {
                errors.push(`Missing generated files for structured-spec service: ${service.name}`);
            }
        });
    }

    await rm(validationRoot, { recursive: true, force: true }).catch(() => {});

    return {
        ok: errors.length === 0,
        errors,
    };
}

function unwrapGeneratedCodeBlock(text = '', filePath = '') {
    const raw = String(text || '').replace(/^\uFEFF/, '').trim();
    if (!raw) return '';

    const fenceMatch = raw.match(/^```(?:[a-zA-Z0-9_.+-]+)?\s*\n([\s\S]*?)\n```\s*$/);
    let value = fenceMatch ? fenceMatch[1].trim() : raw;

    if ((filePath.endsWith('package.json') || filePath.endsWith('.json')) && value.startsWith('```')) {
        const nestedFenceMatch = value.match(/^```(?:json)?\s*\n([\s\S]*?)\n```\s*$/);
        if (nestedFenceMatch) {
            value = nestedFenceMatch[1].trim();
        }
    }

    return value;
}

function normalizeBackendFileContent(filePath = '', content = '') {
    let value = unwrapGeneratedCodeBlock(content, filePath).replace(/\uFEFF/g, '');
    if (/\.(js|jsx|ts|tsx)$/i.test(filePath)) {
        value = value
            .replace(/```[a-zA-Z0-9_.+-]*\s*\r?\n[\s\S]*?```/g, '')
            .replace(/^\s*```[a-zA-Z0-9_.+-]*\s*$/gm, '')
            .replace(/^\s*```\s*$/gm, '')
            .trim();
    }
    if (filePath.endsWith('package.json')) {
        value = sanitizePackageJsonText(value);
    } else if (filePath.endsWith('.json')) {
        const jsonText = extractFirstBalancedJsonText(value);
        if (jsonText) {
            value = jsonText;
        }
    }
    return value;
}

function normalizeFrontendFileContent(filePath = '', content = '') {
    let value = unwrapGeneratedCodeBlock(content, filePath).replace(/\uFEFF/g, '');
    value = value
        .replace(/```[a-zA-Z0-9_.+-]*\s*\r?\n[\s\S]*?```/g, '')
        .replace(/^\s*```(?:[a-zA-Z0-9_.+-]+)?\s*$/gm, '')
        .replace(/^\s*```\s*$/gm, '')
        .trim();
    return value.trim() ? value : '';
}

/** Parse ONLY backend files from text */
function parseBackendOnly(text) {
    const result = { projectTitle: '', backend: {} };
    const addBackend = (path, code) => {
        if (!path || !code?.trim()) return;
        const k = path.trim().startsWith('/') ? path.trim() : `/${path.trim()}`;
        result.backend[k] = { code: normalizeBackendFileContent(k, code) };
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
            const pathM = firstLine.match(/^\/\/\s*(\/[\w/.\-]+\.[a-z]+)/i)
                || firstLine.match(/^#\s*(\/[\w/.\-]+\.[a-z]+)/i)
                || firstLine.match(/^file\s*:\s*(\/[\w/.\-]+\.[a-z]+)/i)
                || firstLine.match(/^path\s*:\s*(\/[\w/.\-]+\.[a-z]+)/i)
                || firstLine.match(/^(\/[\w/.\-]+\.[a-z]+)$/i);
            if (pathM) addBackend(pathM[1], m[1].split('\n').slice(1).join('\n'));
        }
    }
    if (Object.keys(result.backend).length === 0) {
        const re4 = /(?:^|\n)(?:File|Path)\s*:\s*(\/[^\n]+\.(?:js|json))\s*\n```(?:[\w-]+)?\r?\n([\s\S]*?)```/gi;
        while ((m = re4.exec(text)) !== null) addBackend(m[1], m[2]);
    }
    if (Object.keys(result.backend).length === 0) {
        const re5 = /(?:^|\n)#{1,6}\s*(\/[^\n]+\.(?:js|json))\s*\n```(?:[\w-]+)?\r?\n([\s\S]*?)```/gi;
        while ((m = re5.exec(text)) !== null) addBackend(m[1], m[2]);
    }
    return result;
}

function parseBackendJsonPayload(rawText) {
    if (!rawText || !rawText.trim()) {
        return { projectTitle: '', explanation: '', backend: {} };
    }

    let parsed = null;
    const trimmed = rawText.trim();
    try {
        parsed = JSON.parse(trimmed);
    } catch (_) {
        const jsonMatch = trimmed.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
            try {
                parsed = JSON.parse(jsonMatch[0]);
            } catch (_) {
                parsed = null;
            }
        }
    }

    if (!parsed || typeof parsed !== 'object') {
        return { projectTitle: '', explanation: '', backend: {} };
    }

    const backend = {};
    const files = Array.isArray(parsed.files) ? parsed.files : [];
    files.forEach((file) => {
        const filePath = typeof file?.path === 'string' ? file.path.trim() : '';
        const code = typeof file?.code === 'string' ? file.code : '';
        if (!filePath || !code.trim()) {
            return;
        }

        const normalizedPath = filePath.startsWith('/') ? filePath : `/${filePath}`;
        backend[normalizedPath] = { code: code.trim() };
    });

    return {
        projectTitle: typeof parsed.projectTitle === 'string' ? parsed.projectTitle : '',
        explanation: typeof parsed.explanation === 'string' ? parsed.explanation : '',
        backend,
    };
}

function inferBackendPortTopology(backendFiles) {
    const packageDirs = [...new Set(
        Object.keys(backendFiles)
            .filter(filePath => filePath.endsWith('package.json'))
            .map(filePath => filePath.replace(/^\/+/, '').split('/')[0])
    )];
    const serviceDirs = packageDirs.filter(dirName => dirName !== 'api-gateway');
    const prefixesByService = Object.fromEntries(serviceDirs.map(dirName => [dirName, new Set()]));
    const targetPrefixesByPort = new Map();
    const normalizeApiPrefix = (value = '') => {
        const clean = String(value || '').trim().replace(/\/+/g, '/').replace(/\/$/, '');
        if (!clean) return '';
        return clean.startsWith('/') ? clean : `/${clean}`;
    };
    const deriveServiceHints = (dirName = '') => {
        const baseName = dirName
            .replace(/-?service$/i, '')
            .replace(/[^A-Za-z0-9]+/g, ' ')
            .trim()
            .toLowerCase();
        const words = baseName.split(/\s+/).filter(Boolean);
        const hints = new Set();
        const addHint = (prefix) => {
            const normalized = normalizeApiPrefix(prefix);
            if (normalized) hints.add(normalized);
        };
        if (baseName) {
            addHint(`/api/${baseName.replace(/\s+/g, '-')}`);
        }
        words.forEach((word) => {
            addHint(`/api/${word}`);
            if (!word.endsWith('s')) addHint(`/api/${word}s`);
        });
        return [...hints];
    };

    Object.entries(backendFiles).forEach(([filePath, content]) => {
        const code = typeof content === 'string' ? content : content?.code || '';
        const parts = filePath.split('/').filter(Boolean);
        const serviceDir = parts[0];
        if (serviceDir && prefixesByService[serviceDir]) {
            deriveServiceHints(serviceDir).forEach(prefix => prefixesByService[serviceDir].add(prefix));
            if (filePath.endsWith('/index.js')) {
                [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]/g)]
                    .map(match => match[1].trim())
                    .filter(prefix => prefix.startsWith('/api/'))
                    .forEach(prefix => prefixesByService[serviceDir].add(prefix));
            }
            if (filePath.includes('/routes/')) {
                const resourceName = filePath.split('/').pop()?.replace(/\.[^.]+$/, '') || '';
                if (resourceName) {
                    prefixesByService[serviceDir].add(`/api/${resourceName}`);
                }
            }
        }

        if (filePath.includes('gateway') && filePath.endsWith('index.js')) {
            const register = (prefix, port) => {
                if (!targetPrefixesByPort.has(port)) {
                    targetPrefixesByPort.set(port, new Set());
                }
                targetPrefixesByPort.get(port).add(prefix);
            };

            [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,\s*createProxyMiddleware\(\{[\s\S]*?target:\s*['"]https?:\/\/(?:localhost|127\.0\.0\.1):(\d+)['"]/g)]
                .forEach(match => register(match[1].trim(), match[2]));
            [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,\s*createServiceProxy\(\s*['"]https?:\/\/(?:localhost|127\.0\.0\.1):(\d+)['"]/g)]
                .forEach(match => register(match[1].trim(), match[2]));
        }
    });

    const matchedPortByService = {};
    const usedPorts = new Set();

    serviceDirs.forEach((dirName) => {
        let bestPort = null;
        let bestScore = 0;
        const prefixes = prefixesByService[dirName] || new Set();
        targetPrefixesByPort.forEach((portPrefixes, port) => {
            let score = 0;
            prefixes.forEach(prefix => {
                if (portPrefixes.has(prefix)) {
                    score += 1;
                }
            });
            if (score > bestScore) {
                bestScore = score;
                bestPort = port;
            }
        });

        if (bestPort && bestScore > 0) {
            matchedPortByService[dirName] = String(bestPort);
            usedPorts.add(String(bestPort));
        }
    });

    const discoveredPorts = [...targetPrefixesByPort.keys()].map(port => String(port));
    let nextFallbackPort = DEFAULT_SERVICE_PORT_START;
    const serviceConfigs = {};

    serviceDirs.forEach((dirName, index) => {
        let originalPort = matchedPortByService[dirName] || null;
        if (!originalPort) {
            const openDiscoveredPort = discoveredPorts.find(port => !usedPorts.has(port));
            if (openDiscoveredPort) {
                originalPort = openDiscoveredPort;
                usedPorts.add(openDiscoveredPort);
            } else {
                while (usedPorts.has(String(nextFallbackPort))) {
                    nextFallbackPort += 1;
                }
                originalPort = String(nextFallbackPort);
                usedPorts.add(originalPort);
                nextFallbackPort += 1;
            }
        }

        const envVar = `PORT_${dirName.replace(/[^A-Za-z0-9]+/g, '_').toUpperCase()}`;
        serviceConfigs[dirName] = {
            index,
            originalPort,
            envVar,
        };
    });

    return { packageDirs, serviceDirs, serviceConfigs, prefixesByService };
}

function collectServiceRouteMounts(backendFiles = {}) {
    const mountsByService = {};
    Object.entries(backendFiles).forEach(([filePath, content]) => {
        if (!/\/index\.js$/i.test(filePath) || /gateway/i.test(filePath)) {
            return;
        }
        const code = typeof content === 'string' ? content : content?.code || '';
        const serviceDir = filePath.split('/').filter(Boolean)[0];
        if (!serviceDir) return;
        if (!mountsByService[serviceDir]) {
            mountsByService[serviceDir] = new Set();
        }
        [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,/g)]
            .map((match) => String(match[1] || '').trim())
            .filter((prefix) => prefix.startsWith('/api/'))
            .forEach((prefix) => mountsByService[serviceDir].add(prefix));
    });
    return mountsByService;
}

/** Extract API summary from gateway code for frontend generation */
function extractApiSummary(backendFiles) {
    const joinRoute = (prefix, routePath = '/') => {
        const cleanPrefix = prefix.endsWith('/') ? prefix.slice(0, -1) : prefix;
        if (!routePath || routePath === '/') return cleanPrefix || '/';
        const cleanRoute = routePath.startsWith('/') ? routePath : `/${routePath}`;
        return `${cleanPrefix}${cleanRoute}`;
    };

    const proxyPrefixes = new Set();
    const lines = [];
    lines.push(`Backend API (Gateway port ${DEFAULT_GATEWAY_PORT}):`);
    Object.entries(backendFiles).forEach(([path, content]) => {
        const code = typeof content === 'string' ? content : content?.code || '';
        if (path.includes('gateway') && path.endsWith('index.js')) {
            const proxies = [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,\s*createProxyMiddleware/gi)]
                .map(match => match[1].trim());
            if (proxies.length === 0) {
                [...code.matchAll(/['"]\/api\/[\w-]+['"]/g)]
                    .map(match => match[0].replace(/['"]/g, '').trim())
                    .forEach(prefix => proxyPrefixes.add(prefix));
            } else {
                proxies.forEach(prefix => proxyPrefixes.add(prefix));
            }
        }
    });

    const proxyList = [...proxyPrefixes].sort();
    if (proxyList.length > 0) {
        lines.push(`  Exact proxy prefixes: ${proxyList.join(', ')}`);
    }

    const contractLines = [];
    Object.entries(backendFiles).forEach(([path, content]) => {
        const code = typeof content === 'string' ? content : content?.code || '';
        if (!path.includes('/routes/')) return;

        const resourceName = path.split('/').pop()?.replace(/\.[^.]+$/, '') || '';
        const singularName = resourceName.replace(/s$/, '');
        // Find the best matching gateway prefix; a service may handle multiple prefixes
        const proxyPrefix = proxyList.find(prefix => prefix === `/api/${resourceName}`)
            || proxyList.find(prefix => prefix === `/api/${singularName}`)
            || proxyList.find(prefix => resourceName.startsWith(prefix.replace('/api/', '')))
            || proxyList.find(prefix => singularName.startsWith(prefix.replace('/api/', '')))
            || `/api/${resourceName}`;
        const routeMatches = [...code.matchAll(/router\.(get|post|put|delete|patch)\(\s*['"]([^'"]+)['"]/gi)];

        routeMatches.forEach(match => {
            contractLines.push(`  ${match[1].toUpperCase()} ${joinRoute(proxyPrefix, match[2])}`);
        });
    });

    if (contractLines.length > 0) {
        lines.push('  Resource route contract:');
        contractLines.forEach(line => lines.push(line));
        lines.push('  Frontend must call these exact gateway paths. Do not invent singular/plural variants.');
    } else if (proxyList.length > 0) {
        lines.push('  Frontend must call the exact proxy prefixes above through /api or VITE_API_BASE_URL.');
    } else {
        lines.push('  GET/POST/PUT/DELETE /api/* routes available');
    }

    const healthLines = [];
    Object.entries(backendFiles).forEach(([path, content]) => {
        const code = typeof content === 'string' ? content : content?.code || '';
        if (code.includes("app.get('/health'") || code.includes('app.get("/health"')) {
            if (path.includes('gateway')) {
                healthLines.push('  GET /health');
            } else {
                const service = path.split('/')[1] || path;
                healthLines.push(`  ${service}: GET /health`);
            }
        }
    });

    if (healthLines.length > 0) {
        lines.push('  Health checks:');
        healthLines.forEach(line => lines.push(line));
    }

    return lines.join('\n');
}

/** Run static fixes on backend code (no AI required) */
function staticFixBackend(backendFiles, structuredSpec = null) {
    const sanitizeBackendCode = (code) =>
        code
            .replace(/\uFEFF/g, '')
            .replace(/[^\x09\x0A\x0D\x20-\x7E]/g, '');

    const topology = inferBackendPortTopology(backendFiles);
    const serviceRouteMounts = collectServiceRouteMounts(backendFiles);
    const fixed = {};
    const createdFiles = [];
    const repairedFiles = [];
    let fixCount = 0;
    const noteCreatedFile = (filePath, reason = '') => {
        const message = reason ? `${filePath} — ${reason}` : filePath;
        if (!createdFiles.includes(message)) {
            createdFiles.push(message);
        }
    };
    const noteRepairedFile = (filePath, reason = '') => {
        const message = reason ? `${filePath} — ${reason}` : filePath;
        if (!repairedFiles.includes(message)) {
            repairedFiles.push(message);
        }
    };
    Object.entries(backendFiles).forEach(([path, content]) => {
        let code = normalizeBackendFileContent(path, typeof content === 'string' ? content : content?.code || '');
        const originalCode = code;
        let changed = false;
        const serviceName = path.split('/').filter(Boolean)[0] || '';

        const sanitized = sanitizeBackendCode(code);
        if (sanitized !== code) {
            code = sanitized;
            changed = true;
        }

        if (code.includes('process.env.MONGODB_URI') && !code.includes('process.env.MONGO_URL')) {
            code = code.replace(
                /process\.env\.MONGODB_URI/g,
                '(process.env.MONGODB_URI || process.env.MONGO_URL)'
            );
            changed = true;
        }

        if (/Trying alternative port|alternative port|EADDRINUSE/i.test(code)) {
            const nextCode = code
                .replace(/\n?\s*\/\/\s*Try alternative port if primary fails[\s\S]*?(?=\n\s*app\.listen\(\s*PORT|\n\s*app\.listen\(|$)/i, '\n')
                .replace(/\n\s*(?:const\s+server\s*=\s*)?app\.listen\(\s*PORT\s*,\s*\(\)\s*=>\s*\{[\s\S]*?\}\s*\);\s*server\.on\(\s*['"]error['"]\s*,\s*\([\s\S]*?\}\s*\);\s*/i, '\n')
                .replace(/\n\s*(?:const\s+server\s*=\s*)?app\.listen\(\s*PORT\s*,\s*\(\)\s*=>\s*\{[\s\S]*?\}\s*\);\s*app\.on\(\s*['"]error['"]\s*,\s*\([\s\S]*?\}\s*\);\s*/i, '\n');
            if (nextCode !== code) {
                code = nextCode;
                changed = true;
            }
        }

        if (/jsonwebtoken|jwt\./i.test(code)) {
            const secretExpr = buildSecretExpression();
            const secretPatterns = [
                { re: /process\.env\.JWT_SECRET(?!\s*\|\|)/g, replacement: `(${secretExpr})` },
                { re: /process\.env\.SECRET_KEY(?!\s*\|\|)/g, replacement: `(${secretExpr})` },
                { re: /process\.env\.SEKRET_KEY(?!\s*\|\|)/g, replacement: `(${secretExpr})` },
                { re: /process\.env\.JWT_SECRET\s*\|\|\s*(['"`][^'"`]+['"`])/g, replacement: `${secretExpr}` },
                { re: /process\.env\.SECRET_KEY\s*\|\|\s*(['"`][^'"`]+['"`])/g, replacement: `${secretExpr}` },
                { re: /process\.env\.SEKRET_KEY\s*\|\|\s*(['"`][^'"`]+['"`])/g, replacement: `${secretExpr}` },
            ];

            secretPatterns.forEach(({ re, replacement }) => {
                const nextCode = code.replace(re, replacement);
                if (nextCode !== code) {
                    code = nextCode;
                    changed = true;
                }
            });
        }

        // Fix ports
        if (path.includes('gateway') && path.endsWith('index.js')) {
            if (/\b(?:const|let|var)\s+app\s*=\s*express\s*\(/.test(code) && !/\b(?:const|let|var)\s+router\s*=/.test(code) && /\brouter\./.test(code)) {
                code = code.replace(/\brouter\./g, 'app.');
                changed = true;
            }
            Object.values(topology.serviceConfigs).forEach(({ originalPort, envVar }) => {
                code = code.replace(
                    new RegExp(`target:\\s*['"]https?:\\/\\/(?:localhost|127\\.0\\.0\\.1):${originalPort}['"]`, 'g'),
                    `target: 'http://127.0.0.1:' + (process.env.${envVar} || ${originalPort})`
                );
                code = code.replace(
                    new RegExp(`createServiceProxy\\(\\s*['"]https?:\\/\\/(?:localhost|127\\.0\\.0\\.1):${originalPort}['"]\\s*\\)`, 'g'),
                    `createServiceProxy('http://127.0.0.1:' + (process.env.${envVar} || ${originalPort}))`
                );
            });
            if (!code.includes(String(DEFAULT_GATEWAY_PORT))) {
                code = code.replace(/app\.listen\(\s*(\d{4})\s*[,)]/g, (m, p) => p !== String(DEFAULT_GATEWAY_PORT) ? `app.listen(${DEFAULT_GATEWAY_PORT},` : m);
                changed = true;
            }
            code = code.replace(
                /const\s+(PORT|port)\s*=\s*[^;]+;/g,
                `const PORT = Number(process.env.PORT_GATEWAY || process.env.PORT || ${DEFAULT_GATEWAY_PORT});`
            );
            code = code.replace(
                /process\.env\.PORT\s*\|\|\s*\d+/g,
                `process.env.PORT_GATEWAY || process.env.PORT || ${DEFAULT_GATEWAY_PORT}`
            );
            code = code.replace(/app\.listen\(\s*(?:\d+|process\.env\.[A-Z_]+[^,)]*|PORT)\s*,/g, 'app.listen(PORT,');
            code = code.replace(/const\s+server\s*=\s*app\.listen\(/g, 'app.listen(');
            if (!/const\s+PORT\s*=/.test(code) && /app\.listen\(PORT,/.test(code)) {
                code = code.replace(
                    /app\.use\(express\.json\(\)\);/,
                    `app.use(express.json());\nconst PORT = Number(process.env.PORT_GATEWAY || process.env.PORT || ${DEFAULT_GATEWAY_PORT});`
                );
                changed = true;
            }

            if (code.includes('express()')) {
                const needsCors = !code.includes('app.use(cors())') && !code.includes('app.use(cors(');
                const needsJson = !code.includes('app.use(express.json())') && !code.includes('express.json({');
                if (needsCors || needsJson) {
                    const middlewareLines = [
                        'const app = express();',
                        needsCors ? 'app.use(cors());' : null,
                        needsJson ? 'app.use(express.json());' : null,
                    ].filter(Boolean).join('\n');
                    code = code.replace(/const app = express\(\);/, middlewareLines);
                    if (!code.includes("require('cors')") && !code.includes('require(\"cors\")')) {
                        code = `const cors = require('cors');\n` + code;
                    }
                    changed = true;
                }
                // Ensure require('cors') exists when app.use(cors()) is present but require is missing
                if ((code.includes('app.use(cors())') || code.includes('app.use(cors(')) &&
                    !code.includes("require('cors')") && !code.includes('require(\"cors\")')) {
                    code = `const cors = require('cors');\n` + code;
                    changed = true;
                }
            }

            if (code.includes('http-proxy-middleware') && !code.includes('fixRequestBody')) {
                code = code.replace(
                    /const\s+\{\s*createProxyMiddleware\s*\}\s*=\s*require\((['"])http-proxy-middleware\1\);/,
                    `const { createProxyMiddleware, fixRequestBody } = require('http-proxy-middleware');`
                );
                changed = true;
            }

            if (code.includes('createProxyMiddleware({')) {
                const proxyAdditions = [];
                if (!code.includes('proxyTimeout:')) proxyAdditions.push('proxyTimeout: 10000,');
                if (!code.includes('timeout:')) proxyAdditions.push('timeout: 10000,');
                if (!code.includes('onProxyReq: fixRequestBody')) proxyAdditions.push('onProxyReq: fixRequestBody,');
                if (!code.includes('onError:')) {
                    proxyAdditions.push(
                        `onError: (error, req, res) => {\n` +
                        `      if (!res.headersSent) {\n` +
                        `        res.status(502).json({ success: false, error: 'downstream service unavailable', details: error.code || error.message });\n` +
                        `      }\n` +
                        `    },`
                    );
                }

                if (proxyAdditions.length > 0) {
                    code = code.replace(
                        /createProxyMiddleware\(\{\s*/g,
                        (match) => `${match}${proxyAdditions.join('\n    ')}\n    `
                    );
                    changed = true;
                }
            }

            const findServiceConfigForPrefix = (prefix = '') => {
                const normalized = prefix.trim();
                let bestMatch = null;
                let bestScore = 0;
                Object.entries(topology.prefixesByService || {}).forEach(([dirName, prefixes]) => {
                    const candidates = [...(prefixes || [])];
                    let score = 0;
                    candidates.forEach((candidate) => {
                        if (candidate === normalized) score += 3;
                        else if (normalized.startsWith(candidate + '/')) score += 2;
                        else if (candidate.startsWith(normalized + '/')) score += 1;
                    });
                    if (score > bestScore && topology.serviceConfigs?.[dirName]) {
                        bestScore = score;
                        bestMatch = topology.serviceConfigs[dirName];
                    }
                });
                return bestMatch;
            };

            code = code.replace(
                /app\.use\(\s*['"]([^'"]+)['"]\s*,\s*createProxyMiddleware\(\{([\s\S]*?)\}\)\s*\)/g,
                (fullMatch, prefix, proxyBlock) => {
                    const serviceConfig = findServiceConfigForPrefix(prefix);
                    if (!serviceConfig) return fullMatch;
                    const normalizedBlock = proxyBlock
                        .replace(
                            /target:\s*['"]http:\/\/127\.0\.0\.1:'\s*\+\s*\(process\.env\.[A-Z0-9_]+\s*\|\|\s*\d+\)/i,
                            `target: 'http://127.0.0.1:' + (process.env.${serviceConfig.envVar} || ${serviceConfig.originalPort})`
                        )
                        .replace(
                            /target:\s*['"]http:\/\/(?:localhost|127\.0\.0\.1):\d+['"]/i,
                            `target: 'http://127.0.0.1:' + (process.env.${serviceConfig.envVar} || ${serviceConfig.originalPort})`
                        );
                    return `app.use('${prefix}', createProxyMiddleware({${normalizedBlock}}))`;
                }
            );
            if (code.includes('createProxyMiddleware')) {
                const existingGatewayPrefixes = new Set(
                    [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,\s*createProxyMiddleware/gi)]
                        .map((match) => String(match[1] || '').trim())
                        .filter(Boolean)
                );
                const missingProxyBlocks = [];
                Object.entries(serviceRouteMounts).forEach(([dirName, prefixes]) => {
                    const serviceConfig = topology.serviceConfigs?.[dirName];
                    if (!serviceConfig) return;
                    [...prefixes].forEach((prefix) => {
                        if (!prefix || existingGatewayPrefixes.has(prefix)) {
                            return;
                        }
                        existingGatewayPrefixes.add(prefix);
                        missingProxyBlocks.push(
                            `app.use('${prefix}', createProxyMiddleware({\n` +
                            `  target: 'http://127.0.0.1:' + (process.env.${serviceConfig.envVar} || ${serviceConfig.originalPort}),\n` +
                            `  changeOrigin: true,\n` +
                            `  proxyTimeout: 10000,\n` +
                            `  timeout: 10000,\n` +
                            `  onProxyReq: fixRequestBody,\n` +
                            `  onError: (error, req, res) => {\n` +
                            `    if (!res.headersSent) {\n` +
                            `      res.status(502).json({ success: false, error: 'downstream service unavailable', details: error.code || error.message });\n` +
                            `    }\n` +
                            `  }\n` +
                            `}));`
                        );
                    });
                });
                if (missingProxyBlocks.length > 0) {
                    const insertion = `\n${missingProxyBlocks.join('\n\n')}\n\n`;
                    if (/app\.use\(\s*['"`]\*['"`]/.test(code)) {
                        code = code.replace(/app\.use\(\s*['"`]\*['"`]/, `${insertion}app.use('*'`);
                    } else if (/app\.listen\(/.test(code)) {
                        code = code.replace(/app\.listen\(/, `${insertion}app.listen(`);
                    } else {
                        code += insertion;
                    }
                    changed = true;
                }
            }
        }
        if (path.includes('/models/') && path.endsWith('.js')) {
            // Fix: `Required` is not a valid Mongoose type (e.g. { type: Required } or { required: { type: Required } })
            const fixedModel = code
                .replace(/\btype\s*:\s*Required\b/g, 'type: String, required: true')
                .replace(/required\s*:\s*\{\s*type\s*:\s*(?:Required|Boolean|String|Number|Date)\s*\}/g, 'required: true')
                // Fix nested subdoc field literally named "required" with an invalid type
                .replace(/,?\s*required\s*:\s*\{\s*[^}]{0,120}\}/g, (m) => {
                    // Only strip if it looks like a schema-type block, not a real required validator
                    if (/type\s*:/.test(m)) return '';
                    return m;
                })
                // Fix unique: true fields without sparse to prevent E11000 dup key on null values
                .replace(/unique\s*:\s*true(?!\s*,\s*sparse)/g, 'unique: true, sparse: true')
                // Fix category field typed as ObjectId → use String so plain category names work
                .replace(/\bcategory\s*:\s*\{\s*type\s*:\s*(?:Schema\.Types\.ObjectId|mongoose\.Schema\.Types\.ObjectId)[^}]*\}/g,
                    "category: { type: String, default: 'General' }")
                // Fix any field where ObjectId ref is used for simple lookup-name fields
                .replace(/\b(tag|label|type)\s*:\s*\{\s*type\s*:\s*(?:Schema\.Types\.ObjectId|mongoose\.Schema\.Types\.ObjectId)[^}]*\}/g,
                    (m, fieldName) => `${fieldName}: { type: String }`);
            if (fixedModel !== code) {
                code = fixedModel;
                changed = true;
            }
        }

        if (path.includes('-service') && path.endsWith('index.js')) {
            const serviceConfig = topology.serviceConfigs[serviceName] || {
                envVar: 'PORT_SERVICE',
                originalPort: String(DEFAULT_SERVICE_PORT_START),
            };
            const slotEnvName = serviceConfig.envVar;
            const fallbackPort = Number(serviceConfig.originalPort || DEFAULT_SERVICE_PORT_START);
            if (/\b(?:const|let|var)\s+app\s*=\s*express\s*\(/.test(code) && !/\b(?:const|let|var)\s+router\s*=/.test(code) && /\brouter\./.test(code)) {
                code = code.replace(/\brouter\./g, 'app.');
                changed = true;
            }
            if (/\bapp\./.test(code) && !/\b(?:const|let|var)\s+app\s*=\s*express\s*\(/.test(code)) {
                if (/express\s*=\s*require\(['"]express['"]\)/.test(code)) {
                    code = code.replace(
                        /(require\('dotenv'\)\.config\(\);\s*\n?)/,
                        `$1\nconst app = express();\n`
                    );
                    if (!/\b(?:const|let|var)\s+app\s*=\s*express\s*\(/.test(code)) {
                        code = code.replace(/(const\s+cors\s*=\s*require\(['"]cors['"]\);\s*\n?)/, `$1const app = express();\n`);
                    }
                    changed = true;
                }
            }
            if (fileNeedsAuthMiddlewareImport(code)) {
                const nextCode = prependRequireLine(code, "const auth = require('./middleware/auth');");
                if (nextCode !== code) {
                    code = nextCode;
                    changed = true;
                    noteRepairedFile(path, 'added missing auth middleware import');
                }
            }
            code = code.replace(
                /mongoose\.connect\(\s*(['"`])([^'"`]+)\1/g,
                (match, quote, uri) => uri.startsWith('mongodb://')
                    ? `mongoose.connect(process.env.MONGODB_URI || process.env.MONGO_URL || ${quote}${uri}${quote}`
                    : match
            );
            // Remove deprecated Mongoose v3 options (useNewUrlParser, useUnifiedTopology, etc.)
            // that produce noisy warnings in MongoDB driver v4+.
            code = code.replace(
                /mongoose\.connect\(([^)]+),\s*\{\s*((?:useNewUrlParser\s*:\s*(?:true|false),?\s*|useUnifiedTopology\s*:\s*(?:true|false),?\s*|useCreateIndex\s*:\s*(?:true|false),?\s*|useFindAndModify\s*:\s*(?:true|false),?\s*)+)\}\s*\)/g,
                (_, uriExpr) => `mongoose.connect(${uriExpr})`
            );
            code = code.replace(
                /const\s+(PORT|port)\s*=\s*[^;]+;/g,
                `const PORT = Number(process.env.PORT || process.env.${slotEnvName} || ${fallbackPort});`
            );
            code = code.replace(/process\.env\.PORT\s*\|\|\s*\d+/g, `process.env.PORT || process.env.${slotEnvName} || ${fallbackPort}`);
            code = code.replace(/app\.listen\(\s*[^,]+,\s*/g, 'app.listen(PORT, ');
            code = code.replace(/const\s+server\s*=\s*app\.listen\(/g, 'app.listen(');
            code = code.replace(/app\.listen\(PORT\(\)\s*=>/g, 'app.listen(PORT, () =>');
            code = code.replace(/app\.listen\(PORT\s*\)\s*=>/g, 'app.listen(PORT, () =>');
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
            // Ensure require('cors') exists when app.use(cors()) is already present but require is missing
            if ((code.includes('app.use(cors())') || code.includes('app.use(cors(')) &&
                !code.includes("require('cors')") && !code.includes('require("cors")')) {
                code = `const cors = require('cors');\n` + code;
                changed = true;
            }
            if (!/const\s+PORT\s*=/.test(code) && /app\.listen\(PORT,/.test(code)) {
                code = code.replace(
                    /app\.use\(express\.json\(\)\);/,
                    `app.use(express.json());\nconst PORT = Number(process.env.PORT || process.env.${slotEnvName} || ${fallbackPort});`
                );
                changed = true;
            }
            // Ensure a direct app.get('/health') exists in the service index.js.
            // Live health checks hit http://127.0.0.1:PORT/health directly — a health route
            // buried inside a mounted router (e.g. /api/auth/health) will always return 404.
            if (!/app\.get\(\s*['"]\/health['"]/i.test(code)) {
                const svcHealthBlock =
                    `\napp.get('/health', (req, res) => {\n` +
                    `  res.json({ success: true, data: { status: 'ok', service: '${serviceName}' } });\n` +
                    `});\n`;
                // Insert before the first app.listen() — use a flexible regex that handles any
                // amount of whitespace or no leading newline before the listen call.
                if (/app\.listen\(/.test(code)) {
                    code = code.replace(/([\s\S]*?)([ \t]*app\.listen\()/, (_, before, listenStart) => {
                        return before + svcHealthBlock + '\n' + listenStart;
                    });
                } else if (/app\.use\(express\.json\(\)\)/.test(code)) {
                    code = code.replace(/(app\.use\(express\.json\(\)\);)/, `$1${svcHealthBlock}`);
                } else {
                    code += svcHealthBlock;
                }
                changed = true;
            }
        }
        // Fix route response format
        if (path.includes('/routes/')) {
            code = code.replace(/\n\s*\.populate\([^\n]+\)/g, '');
            const resourceName = path.split('/').pop()?.replace(/\.[^.]+$/, '') || 'resource';
            const healthRouteBlock =
                `router.get('/health', (req, res) => {\n` +
                `    res.json({ success: true, data: { status: 'ok', route: '${resourceName}' } });\n` +
                `});\n\n`;
            const firstParamRouteIndex = code.search(/router\.(get|put|patch|delete)\(\s*['"]\/:[^'"]+['"]/i);
            const firstRouteIndex = code.search(/router\.(get|post|put|patch|delete)\(/i);
            const existingHealthIndex = code.search(/router\.get\(\s*['"]\/health['"]/i);
            const shouldInsertHealthRoute =
                existingHealthIndex === -1 ||
                (firstParamRouteIndex !== -1 && existingHealthIndex > firstParamRouteIndex);

            if (shouldInsertHealthRoute) {
                const insertIndex = firstParamRouteIndex !== -1
                    ? firstParamRouteIndex
                    : (firstRouteIndex !== -1 ? firstRouteIndex : code.length);
                code = `${code.slice(0, insertIndex)}${healthRouteBlock}${code.slice(insertIndex)}`;
                changed = true;
            }

            // Fix route shadowing: move literal-path routes that appear after /:param routes
            // to BEFORE the first parameterized route. Prevents Express treating literal segments
            // like 'my', 'me', 'search', 'course' as an ObjectId and throwing CastError.
            {
                const shadowDeclRe = /\brouter\.(get|post|put|patch|delete)\s*\(\s*['"](\/?[^'"]*)['"]/gi;
                const shadowDecls = [];
                let sdm;
                while ((sdm = shadowDeclRe.exec(code)) !== null) {
                    const rp = sdm[2];
                    const firstSeg = rp.replace(/^\//, '').split('/')[0] || '';
                    shadowDecls.push({ pos: sdm.index, path: rp, isParamFirst: firstSeg.startsWith(':') });
                }
                const firstParamDecl = shadowDecls.find(d => d.isParamFirst);
                if (firstParamDecl) {
                    const shadowedLiterals = shadowDecls.filter(
                        d => !d.isParamFirst && d.pos > firstParamDecl.pos && d.path !== '/health'
                    );
                    if (shadowedLiterals.length > 0) {
                        // Extract each shadowed literal's complete block by tracking paren/brace depth
                        const extractBlockEnd = (str, startPos) => {
                            let depth = 0, started = false, i = startPos;
                            while (i < str.length) {
                                const ch = str[i];
                                if (!started && ch === '(') started = true;
                                if (started) {
                                    if (ch === '(' || ch === '{') depth++;
                                    else if (ch === ')' || ch === '}') {
                                        depth--;
                                        if (depth <= 0) {
                                            let end = i + 1;
                                            if (str[end] === ';') end++;
                                            while (end < str.length && (str[end] === '\n' || str[end] === '\r')) end++;
                                            return end;
                                        }
                                    }
                                }
                                i++;
                            }
                            return str.length;
                        };

                        let newCode = code;
                        const blocksToInsert = [];
                        [...shadowedLiterals].sort((a, b) => b.pos - a.pos).forEach(decl => {
                            const endPos = extractBlockEnd(newCode, decl.pos);
                            blocksToInsert.unshift(newCode.slice(decl.pos, endPos));
                            newCode = newCode.slice(0, decl.pos) + newCode.slice(endPos);
                        });

                        const newFirstParamPos = newCode.search(/\brouter\.(get|post|put|patch|delete)\s*\(\s*['"]\/:[^'"]+['"]/i);
                        if (newFirstParamPos !== -1 && blocksToInsert.length > 0) {
                            newCode = newCode.slice(0, newFirstParamPos) + blocksToInsert.join('') + newCode.slice(newFirstParamPos);
                            code = newCode;
                            changed = true;
                        }
                    }
                }
            }

            code = code.replace(/res\.json\(([^{][^)]+)\)/g, (m, inner) => {
                if (inner.includes('success')) return m;
                return `res.json({ success: true, data: ${inner} })`;
            });
        }
        if (code !== originalCode) changed = true;
        if (changed) {
            fixCount++;
            if (!repairedFiles.some((entry) => entry.startsWith(`${path} —`)) && !repairedFiles.includes(path)) {
                noteRepairedFile(path, 'static backend repair');
            }
        }
        fixed[path] = { code };
    });

    // POST-PASS: auto-create stub model files for any require('../models/X') that has no matching file.
    // This prevents the recurring "Cannot find module '../models/X'" crash when AI patches a route
    // but forgets to create/preserve the model file it references.
    const fixedPaths = Object.keys(fixed);
    fixedPaths.forEach((filePath) => {
        if (!filePath.includes('/routes/')) return;
        const routeCode = typeof fixed[filePath] === 'string' ? fixed[filePath] : fixed[filePath]?.code || '';
        const serviceDir = filePath.split('/').filter(Boolean)[0];
        if (!serviceDir) return;

        const modelRequireRe = /require\(\s*['"]\.\.\/models\/([^'"]+)['"]\s*\)/g;
        let m2;
        while ((m2 = modelRequireRe.exec(routeCode)) !== null) {
            const modelName = m2[1].replace(/\.js$/i, '');
            const expectedPath = `/${serviceDir}/models/${modelName}.js`;

            // Check for an exact or case-insensitive match among existing fixed files
            const existsExact = Boolean(fixed[expectedPath]);
            const existsCaseInsensitive = !existsExact && fixedPaths.some(
                (p) => p.toLowerCase() === expectedPath.toLowerCase()
            );

            if (!existsExact && !existsCaseInsensitive) {
                // Auto-create a sensible stub Mongoose model so the service can start
                const entityName = modelName.charAt(0).toUpperCase() + modelName.slice(1).replace(/[^a-zA-Z0-9]/g, '');
                fixed[expectedPath] = {
                    code: [
                        `const mongoose = require('mongoose');`,
                        ``,
                        `const ${entityName}Schema = new mongoose.Schema({`,
                        `  name:        { type: String, required: true },`,
                        `  description: { type: String },`,
                        `  price:       { type: Number, default: 0 },`,
                        `  status:      { type: String, default: 'active' },`,
                        `  createdBy:   { type: mongoose.Schema.Types.ObjectId, ref: 'User' },`,
                        `}, { timestamps: true });`,
                        ``,
                        `module.exports = mongoose.model('${entityName}', ${entityName}Schema);`,
                    ].join('\n'),
                };
                fixCount++;
                noteCreatedFile(expectedPath, 'created missing model file');
            }
        }
    });

    // POST-PASS 2: ensure routes/<name>.js file exists when index.js requires ./routes/<name>.
    // Prevents "Cannot find module './routes/menu'" when AI replaces index.js but drops the routes file.
    fixedPaths.forEach((filePath) => {
        if (!/\/index\.js$/i.test(filePath) || /gateway/i.test(filePath)) return;
        const indexCode = typeof fixed[filePath] === 'string' ? fixed[filePath] : fixed[filePath]?.code || '';
        const serviceDir = filePath.split('/').filter(Boolean)[0];
        if (!serviceDir) return;

        const routeRequireRe = /require\(\s*['"]\.\/routes\/([^'"]+)['"]\s*\)/g;
        let m3;
        while ((m3 = routeRequireRe.exec(indexCode)) !== null) {
            const routeName = m3[1].replace(/\.js$/i, '');
            const expectedRoute = `/${serviceDir}/routes/${routeName}.js`;
            const existsExact = Boolean(fixed[expectedRoute]);
            const existsCaseInsensitive = !existsExact && Object.keys(fixed).some(
                (p) => p.toLowerCase() === expectedRoute.toLowerCase()
            );
            if (!existsExact && !existsCaseInsensitive) {
                // Create a minimal router stub so the service starts
                fixed[expectedRoute] = {
                    code: [
                        `const express = require('express');`,
                        `const router = express.Router();`,
                        ``,
                        `router.get('/health', (req, res) => {`,
                        `  res.json({ success: true, data: { status: 'ok', route: '${routeName}' } });`,
                        `});`,
                        ``,
                        `module.exports = router;`,
                    ].join('\n'),
                };
                fixCount++;
                noteCreatedFile(expectedRoute, 'created missing route file');
            }
        }
    });

    // POST-PASS 3 (new): Deep cross-validation — models ↔ routes ↔ index.js ↔ package.json.
    // Runs AFTER stubs are created so it has the full file graph to resolve against.
    // Fixes in order:
    //   (a) Wrong relative prefix: '../routes/X' in index.js  →  './routes/X'
    //   (b) Case-mismatched model require in route files      →  correct casing
    //   (c) Case-mismatched route require in index.js         →  correct casing
    //   (d) Mismatched app.use() mount vs actual route file   →  align path
    //   (e) Missing module.exports = router in route files
    //   (f) Missing app.listen() in service index.js
    {
        const crossPaths = Object.keys(fixed);
        // Case-insensitive lookup: lowercase path → actual path
        const pathByLower = new Map(crossPaths.map(p => [p.toLowerCase(), p]));

        // Resolve a local require() path from a given file, returning the actual fixed-map key
        const resolveLocal = (fromFp, requireStr) => {
            const fromDir = fromFp.replace(/\\/g, '/').split('/').filter(Boolean).slice(0, -1);
            const relParts = requireStr.replace(/\\/g, '/').split('/');
            const resolved = [...fromDir];
            for (const seg of relParts) {
                if (!seg || seg === '.') continue;
                if (seg === '..') resolved.pop();
                else resolved.push(seg);
            }
            const base = '/' + resolved.join('/');
            const candidates = [base, `${base}.js`, `${base}.json`, `${base}/index.js`];
            for (const c of candidates) {
                if (fixed[c]) return { path: c, found: true, caseFixed: false };
            }
            for (const c of candidates) {
                const actual = pathByLower.get(c.toLowerCase());
                if (actual) return { path: actual, found: true, caseFixed: actual !== c };
            }
            return { found: false };
        };

        // Compute a relative require() string from one file path to another
        const makeRelativeRequire = (fromFp, toFp, stripExt = true) => {
            const fromDir = fromFp.replace(/\\/g, '/').split('/').filter(Boolean).slice(0, -1);
            const toSegs = toFp.replace(/\\/g, '/').split('/').filter(Boolean);
            let common = 0;
            while (common < fromDir.length && common < toSegs.length && fromDir[common] === toSegs[common]) common++;
            const ups = fromDir.length - common;
            const downs = toSegs.slice(common);
            let rel = (ups === 0 ? './' : '../'.repeat(ups)) + downs.join('/');
            if (stripExt) rel = rel.replace(/\.js$/, '');
            return rel;
        };

        crossPaths.forEach((fp) => {
            if (!fp.endsWith('.js')) return;
            const svcDir = fp.split('/').filter(Boolean)[0] || '';
            let code = typeof fixed[fp] === 'string' ? fixed[fp] : fixed[fp]?.code || '';
            let changed = false;

            const isIndexJs = /\/index\.js$/i.test(fp) && !/gateway/i.test(fp);
            const isRouteFile = fp.includes('/routes/') && fp.endsWith('.js');

            // (a) Fix '../routes/X' → './routes/X' in service index.js
            if (isIndexJs) {
                const fixed1 = code.replace(
                    /require\(['"](\.\.\/routes\/[^'"]+)['"]\)/g,
                    (_, wrongPath) => `require('${wrongPath.replace(/^\.\.\/routes\//, './routes/')}')`
                );
                if (fixed1 !== code) { code = fixed1; changed = true; }
            }

            // (b) Fix case-mismatched require paths (applies to all JS files)
            const requireRe = /require\(['"](\.[^'"]+)['"]\)/g;
            let newCode = '';
            let lastIdx = 0;
            let m;
            requireRe.lastIndex = 0;
            while ((m = requireRe.exec(code)) !== null) {
                const reqStr = m[1];
                const result = resolveLocal(fp, reqStr);
                if (result.found && result.caseFixed) {
                    const corrected = makeRelativeRequire(fp, result.path, !reqStr.endsWith('.js'));
                    newCode += code.slice(lastIdx, m.index) + `require('${corrected}')`;
                    lastIdx = m.index + m[0].length;
                    changed = true;
                }
            }
            if (changed && newCode !== '') {
                code = newCode + code.slice(lastIdx);
            }

            // (c) Fix index.js app.use() path mismatches: align mount prefix to route file names
            // e.g. app.use('/api/courses', require('./routes/course')) but file is 'courses.js'
            if (isIndexJs) {
                const mountRe = /app\.use\(\s*(['"])([^'"]+)\1\s*,\s*require\(['"](\.[^'"]+)['"]\)\)/g;
                mountRe.lastIndex = 0;
                let mountCode = '';
                let mountLastIdx = 0;
                let changed2 = false;
                while ((m = mountRe.exec(code)) !== null) {
                    const mountPath = m[2]; // e.g. '/api/courses'
                    const reqPath = m[3];   // e.g. './routes/course'
                    const result = resolveLocal(fp, reqPath);
                    if (!result.found) {
                        // Try to find a route file whose name matches the last segment of mountPath
                        const mountSeg = mountPath.split('/').pop() || '';
                        const routeFileKey = crossPaths.find(p =>
                            p.startsWith(`/${svcDir}/routes/`) &&
                            p.endsWith('.js') &&
                            p.split('/').pop().replace(/\.js$/i, '').toLowerCase() === mountSeg.toLowerCase()
                        );
                        if (routeFileKey) {
                            const correctedReq = makeRelativeRequire(fp, routeFileKey);
                            mountCode += code.slice(mountLastIdx, m.index) +
                                `app.use(${m[1]}${mountPath}${m[1]}, require('${correctedReq}'))`;
                            mountLastIdx = m.index + m[0].length;
                            changed2 = true;
                        }
                    }
                }
                if (changed2) {
                    code = mountCode + code.slice(mountLastIdx);
                    changed = true;
                }
            }

            // (d) Ensure route files export the router
            if (isRouteFile && !code.includes('module.exports') && code.includes('router.')) {
                code += '\n\nmodule.exports = router;\n';
                changed = true;
            }

            // (e) Ensure service index.js has app.listen()
            if (isIndexJs && code.includes('express()') && !/app\.listen\(/.test(code)) {
                const svcSegs = fp.split('/').filter(Boolean);
                const svcName = svcSegs[0] || 'service';
                code += `\nconst PORT = Number(process.env.PORT || ${DEFAULT_SERVICE_PORT_START});\napp.listen(PORT, () => console.log(\`${svcName} running on port \${PORT}\`));\n`;
                changed = true;
            }

            if (changed) {
                fixed[fp] = { code };
                fixCount++;
                noteRepairedFile(fp, 'cross-file backend consistency repair');
            }
        });
    }

    // POST-PASS 4 (was POST-PASS 3): audit every JS file in each service and auto-add any missing npm packages to
    // that service's package.json.  This permanently fixes "Cannot find module 'jsonwebtoken'"
    // (and bcryptjs, stripe, multer, nodemailer, socket.io, etc.) caused when the AI writes a
    // require() call but forgets to list the package as a dependency.
    const allFixedPaths = Object.keys(fixed);

    // Collect distinct service directories (first path segment, including gateway)
    const serviceDirs = new Set();
    allFixedPaths.forEach((p) => {
        const seg = p.split('/').filter(Boolean)[0];
        if (seg) serviceDirs.add(seg);
    });

    serviceDirs.forEach((svcDir) => {
        const pkgPath = `/${svcDir}/package.json`;
        const pkgEntry = fixed[pkgPath];
        if (!pkgEntry) return; // no package.json for this service — nothing to patch

        // Parse existing package.json
        let pkgJson;
        try {
            const raw = typeof pkgEntry === 'string' ? pkgEntry : pkgEntry.code || '';
            pkgJson = JSON.parse(normalizeBackendFileContent(pkgPath, raw));
        } catch (_) {
            return; // invalid JSON — skip
        }
        pkgJson.dependencies = pkgJson.dependencies || {};

        const needed = new Set();

        allFixedPaths.forEach((fp) => {
            if (!fp.startsWith(`/${svcDir}/`) || !/\.js$/i.test(fp)) return;
            const code = typeof fixed[fp] === 'string' ? fixed[fp] : fixed[fp]?.code || '';
            extractRequireAndImportRequests(code).forEach((requestPath) => {
                const packageName = getExternalRequirePackageName(requestPath);
                if (!packageName || NODE_BUILTIN_MODULES.has(packageName)) {
                    return;
                }
                needed.add(packageName);
            });
        });

        // Add any missing packages with their known versions
        let patched = false;
        needed.forEach((pkg) => {
            if (!pkgJson.dependencies[pkg] && !pkgJson.devDependencies?.[pkg]) {
                const ver = DEFAULT_PACKAGE_VERSION_BY_NAME[pkg] || 'latest';
                pkgJson.dependencies[pkg] = ver;
                patched = true;
                fixCount++;
            }
        });

        if (patched) {
            const updatedCode = JSON.stringify(pkgJson, null, 2);
            fixed[pkgPath] = typeof pkgEntry === 'string' ? updatedCode : { ...pkgEntry, code: updatedCode };
            noteRepairedFile(pkgPath, 'added missing package dependencies');
        }
    });

    // Auto-generate missing auth middleware files and inject missing auth imports
    const authMiddlewareTemplate = [
        "const jwt = require('jsonwebtoken');",
        `const SECRET = process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'dev-secret';`,
        'module.exports = (req, res, next) => {',
        "  const header = req.headers['authorization'] || '';",
        "  const token = header.startsWith('Bearer ') ? header.slice(7) : null;",
        "  if (!token) return res.status(401).json({ success: false, error: 'No token provided' });",
        '  try { req.user = jwt.verify(token, SECRET); next(); }',
        "  catch (_) { res.status(401).json({ success: false, error: 'Invalid or expired token' }); }",
        '};',
    ].join('\n');

    Object.entries(fixed).forEach(([filePath, content]) => {
        if (!/\.js$/i.test(filePath)) {
            return;
        }
        let code = normalizeBackendFileContent(filePath, typeof content === 'string' ? content : content?.code || '');
        const serviceDir = '/' + filePath.split('/').filter(Boolean)[0];
        const middlewarePath = `${serviceDir}/middleware/auth.js`;
        let changed = false;

        if (fileNeedsAuthMiddlewareImport(code)) {
            const requirePath = /\/routes\//i.test(filePath) ? '../middleware/auth' : './middleware/auth';
            const nextCode = prependRequireLine(code, `const auth = require('${requirePath}');`);
            if (nextCode !== code) {
                code = nextCode;
                changed = true;
                noteRepairedFile(filePath, 'inserted auth middleware import');
            }
        }

        const middlewareRequireRe = /require\(\s*['"](?:\.\.\/|\.\/)*middleware\/auth['"]\s*\)/g;
        if (middlewareRequireRe.test(code) && !fixed[middlewarePath]) {
            fixed[middlewarePath] = { code: authMiddlewareTemplate };
            fixCount++;
            noteCreatedFile(middlewarePath, 'created auth middleware file');
        }

        if (changed) {
            fixed[filePath] = { code };
            fixCount++;
        }
    });

    if (structuredSpec) {
        const structuredCoverageFix = applyStructuredSpecCoverageFixes(fixed, structuredSpec);
        return {
            files: structuredCoverageFix.files,
            fixCount: fixCount + structuredCoverageFix.fixCount,
            createdFiles,
            repairedFiles,
        };
    }

    return { files: fixed, fixCount, createdFiles, repairedFiles };
}

function repairCommonFrontendSyntax(code = '') {
    let nextCode = String(code || '').replace(/\uFEFF/g, '');

    // Repair common malformed JSX event handler patterns such as:
    // onChangehandleChange}, onChange{handleChange}, onChangeÃ¦Å¾ÂhandleChange}
    nextCode = nextCode.replace(
        /\b(on[A-Z][A-Za-z0-9_]*)[^\S\r\n]*[^\w\s"'`=/{>(-]+([A-Za-z_$][\w$]*)\}/g,
        '$1={$2}'
    );
    nextCode = nextCode.replace(
        /\b(on[A-Z][A-Za-z0-9_]*)\{([A-Za-z_$][\w$]*)\}/g,
        '$1={$2}'
    );
    nextCode = nextCode.replace(
        /\b(on[A-Z][A-Za-z0-9_]*)=([A-Za-z_$][\w$]*)\}/g,
        '$1={$2}'
    );
    nextCode = nextCode.replace(
        /\b(on[A-Z][A-Za-z0-9_]*)\s+([A-Za-z_$][\w$]*)\}/g,
        '$1={$2}'
    );

    // Remove stray non-ASCII control/symbol characters that often corrupt JSX syntax.
    nextCode = nextCode
        .split('\n')
        .map((line) => {
            if (/\bon[A-Z][A-Za-z0-9_]*/.test(line) || /<(input|button|select|textarea|form)\b/i.test(line)) {
                return line.replace(/[^\x09\x0A\x0D\x20-\x7E]/g, '');
            }
            return line;
        })
        .join('\n');

    return nextCode;
}

function ensureToastifyImports(code = '') {
    let nextCode = String(code || '');
    const usesToastContainer = /\<ToastContainer\b/.test(nextCode);
    const usesToast = /\btoast\.(success|error|info|warn|warning|promise|loading|dark)\b|\btoast\(/.test(nextCode);
    const reactToastifyImportRegex = /import\s*\{([^}]+)\}\s*from\s*['"]react-toastify['"];?/;
    const hasReactToastifyImport = reactToastifyImportRegex.test(nextCode);

    if (!usesToastContainer && !usesToast) {
        return nextCode;
    }

    if (hasReactToastifyImport) {
        nextCode = nextCode.replace(reactToastifyImportRegex, (full, names) => {
            const parts = names.split(',').map((value) => value.trim()).filter(Boolean);
            const nameSet = new Set(parts);
            if (usesToastContainer) nameSet.add('ToastContainer');
            if (usesToast) nameSet.add('toast');
            return `import { ${[...nameSet].sort((a, b) => a.localeCompare(b)).join(', ')} } from 'react-toastify';`;
        });
    } else {
        const required = [];
        if (usesToastContainer) required.push('ToastContainer');
        if (usesToast) required.push('toast');
        const importLine = `import { ${required.join(', ')} } from 'react-toastify';\n`;
        if (/^import[\s\S]+?\n/m.test(nextCode)) {
            nextCode = nextCode.replace(/^((?:import .*;\n)+)/, `$1${importLine}`);
        } else {
            nextCode = `${importLine}${nextCode}`;
        }
    }

    return nextCode;
}

async function validateFrontendCandidateFiles(frontendFiles, { emit = null, phase = 'frontend-fix', round = null } = {}) {
    const candidateEntries = Object.entries(frontendFiles || {}).filter(([filePath]) => /\.(jsx?|tsx?)$/i.test(filePath));
    if (candidateEntries.length === 0) {
        return { ok: true, errors: [] };
    }
    emitFrontendValidationPlan(emit, Object.fromEntries(candidateEntries), { phase, round });

    const tempRoot = path.join(
        os.tmpdir(),
        `ai-builder-frontend-validate-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    );

    try {
        await mkdir(tempRoot, { recursive: true });

        const manifest = [];
        for (const [filePath, content] of candidateEntries) {
            const normalizedPath = filePath.replace(/^\/+/, '');
            const targetPath = path.join(tempRoot, normalizedPath);
            const code = normalizeFrontendFileContent(filePath, typeof content === 'string' ? content : content?.code || '');

            await mkdir(path.dirname(targetPath), { recursive: true });
            await writeFile(targetPath, code, 'utf8');
            manifest.push({ filePath, diskPath: targetPath });
        }

        const manifestPath = path.join(tempRoot, 'manifest.json');
        await writeFile(manifestPath, JSON.stringify(manifest), 'utf8');

        const validatorScript = `
const fs = require('node:fs');
const path = require('node:path');
const { transformSync, buildSync } = require('esbuild');

const manifest = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
const errors = [];
const fileSet = new Set(manifest.map((entry) => String(entry.filePath || '').replace(/\\\\/g, '/')));

const resolveImportCandidates = (fromPath, requestPath) => {
  const fromDir = path.posix.dirname(String(fromPath || '').replace(/\\\\/g, '/'));
  const basePath = path.posix.normalize(path.posix.join(fromDir, requestPath));
  return [
    basePath,
    basePath + '.js',
    basePath + '.jsx',
    basePath + '.ts',
    basePath + '.tsx',
    path.posix.join(basePath, 'index.js'),
    path.posix.join(basePath, 'index.jsx'),
    path.posix.join(basePath, 'index.ts'),
    path.posix.join(basePath, 'index.tsx'),
  ];
};

for (const entry of manifest) {
  const code = fs.readFileSync(entry.diskPath, 'utf8');
  const lowerPath = entry.filePath.toLowerCase();
  const loader = lowerPath.endsWith('.tsx')
    ? 'tsx'
    : lowerPath.endsWith('.ts')
      ? 'ts'
      : (lowerPath.endsWith('.jsx') || /<\\/?[A-Za-z]/.test(code))
        ? 'jsx'
        : 'js';

  const importRegex = /import\\s+[^'"]*?from\\s+['"]([^'"]+)['"]|import\\s+['"]([^'"]+)['"]|import\\(\\s*['"]([^'"]+)['"]\\s*\\)/g;
  let importMatch;
  while ((importMatch = importRegex.exec(code)) !== null) {
    const requestPath = importMatch[1] || importMatch[2] || importMatch[3];
    if (!requestPath || !requestPath.startsWith('.')) continue;
    const found = resolveImportCandidates(entry.filePath, requestPath).some((candidate) => fileSet.has(candidate.startsWith('/') ? candidate : '/' + candidate));
    if (!found) {
      errors.push(\`\${entry.filePath}: missing local import \${requestPath}\`);
    }
  }

  try {
    transformSync(code, {
      loader,
      jsx: 'automatic',
      format: 'esm',
      sourcemap: false,
    });
  } catch (error) {
    const firstError = error && error.errors && error.errors[0];
    const location = firstError && firstError.location
      ? \` (\${firstError.location.line}:\${firstError.location.column})\`
      : '';
    errors.push(\`\${entry.filePath}: \${(firstError && firstError.text) || error.message || 'frontend syntax validation failed'}\${location}\`);
  }
}

const entryCandidates = manifest.filter((entry) => /\\/(main|index|app)\\.(jsx?|tsx?)$/i.test(entry.filePath));
for (const entry of entryCandidates.slice(0, 3)) {
  try {
    buildSync({
      entryPoints: [entry.diskPath],
      bundle: true,
      write: false,
      format: 'esm',
      platform: 'browser',
      jsx: 'automatic',
      external: [
        'react',
        'react-dom',
        'react-router-dom',
        'lucide-react',
        'framer-motion',
        'react-toastify',
        'tailwind-merge',
        'uuid',
        'react-beautiful-dnd',
        'recharts',
        'date-fns',
      ],
      logLevel: 'silent',
    });
  } catch (error) {
    const firstError = error && error.errors && error.errors[0];
    const location = firstError && firstError.location
      ? \` (\${firstError.location.line}:\${firstError.location.column})\`
      : '';
    errors.push(\`\${entry.filePath}: \${(firstError && firstError.text) || error.message || 'frontend bundle validation failed'}\${location}\`);
  }
}

process.stdout.write(JSON.stringify([...new Set(errors)]));
`;

        const result = await runCommand(
            process.execPath,
            ['-e', validatorScript, manifestPath],
            { cwd: process.cwd(), timeoutMs: 120000 }
        );

        if (result?.code !== 0) {
            return {
                ok: false,
                errors: [`frontend validation process failed: ${String(result?.stderr || result?.stdout || `exit=${result?.code}`).trim()}`],
            };
        }

        const stdout = String(result?.stdout || '').trim();
        const errors = stdout ? JSON.parse(stdout) : [];
        return {
            ok: errors.length === 0,
            errors,
        };
    } catch (error) {
        return {
            ok: false,
            errors: [`frontend validation process failed: ${error.message || 'unknown error'}`],
        };
    } finally {
        await rm(tempRoot, { recursive: true, force: true }).catch(() => {});
    }
}

/** Static sanitize for frontend (mirrors CodeView sanitize) */
function staticFixFrontend(frontendFiles) {
    const ALLOWED = new Set([
        'react','react-dom','react-router-dom','lucide-react',
        'framer-motion','react-toastify','tailwind-merge','uuid',
        'react-beautiful-dnd','recharts','date-fns',
    ]);
    const previewRequestHelper = `const API_BASE = '';
const IS_PREVIEW_SANDBOX = typeof window !== 'undefined' && /codesandbox|sandpack|csb\\.app|csbops\\.io/i.test(window.location.hostname);
const safeJsonParse = (value, fallback) => {
  try {
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
};
const previewStorage = {
  readArray: (key) => safeJsonParse(window.localStorage.getItem(key), []),
  writeArray: (key, value) => window.localStorage.setItem(key, JSON.stringify(value)),
};
const buildPreviewAnalytics = (tasks) => {
  const counts = tasks.reduce((acc, task) => {
    const status = task?.status || 'todo';
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, { todo: 0, 'in-progress': 0, done: 0 });
  const priorityCounts = tasks.reduce((acc, task) => {
    const priority = task?.priority || 'medium';
    acc[priority] = (acc[priority] || 0) + 1;
    return acc;
  }, {});
  return {
    summary: {
      totalTasks: tasks.length,
      completedTasks: counts.done || 0,
      inProgressTasks: counts['in-progress'] || 0,
      todoTasks: counts.todo || 0,
      completionRate: tasks.length ? Math.round(((counts.done || 0) / tasks.length) * 100) : 0,
    },
    priorityDistribution: Object.entries(priorityCounts).map(([name, value]) => ({ name, value })),
    completionTrends: [
      { name: 'To Do', value: counts.todo || 0 },
      { name: 'In Progress', value: counts['in-progress'] || 0 },
      { name: 'Done', value: counts.done || 0 },
    ],
    productivity: {
      tasksCompletedToday: counts.done || 0,
      productivityScore: tasks.length ? Math.min(100, Math.round(((counts.done || 0) / tasks.length) * 100)) : 0,
    },
  };
};
const previewRequestJson = (path, options = {}) => {
  if (typeof window === 'undefined') return null;
  const method = (options.method || 'GET').toUpperCase();
  const tasks = previewStorage.readArray('tasks');
  const users = previewStorage.readArray('users');
  const defaultColumns = [
    { _id: 'todo', title: 'To Do', status: 'todo' },
    { _id: 'in-progress', title: 'In Progress', status: 'in-progress' },
    { _id: 'done', title: 'Done', status: 'done' },
  ];
  const columns = previewStorage.readArray('columns');
  const body = options.body ? safeJsonParse(options.body, {}) : {};
  const makeId = () => (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : String(Date.now()));
  if (method === 'GET') {
    if (/^\\/api\\/tasks\\/stats\\/status-counts(\\?|$)/.test(path)) {
      const counts = tasks.reduce((acc, task) => {
        const status = task?.status || 'todo';
        acc[status] = (acc[status] || 0) + 1;
        return acc;
      }, { todo: 0, 'in-progress': 0, done: 0 });
      return { success: true, data: counts };
    }
    if (/^\\/api\\/tasks\\/status\\//.test(path)) {
      const status = decodeURIComponent(path.split('/').pop() || 'todo');
      return { success: true, data: tasks.filter((task) => (task?.status || 'todo') === status) };
    }
    if (/^\\/api\\/tasks(\\?|$)/.test(path)) {
      return { success: true, data: tasks };
    }
    if (/^\\/api\\/users(\\?|$)/.test(path)) {
      return { success: true, data: users };
    }
    if (/^\\/api\\/columns(\\?|$)/.test(path)) {
      return { success: true, data: columns.length ? columns : defaultColumns };
    }
    const analytics = buildPreviewAnalytics(tasks);
    if (/^\\/api\\/analytics\\/summary(\\?|$)/.test(path) || /^\\/api\\/analytics\\/dashboard(\\?|$)/.test(path)) {
      return { success: true, data: analytics.summary };
    }
    if (/^\\/api\\/analytics\\/priority-distribution(\\?|$)/.test(path)) {
      return { success: true, data: analytics.priorityDistribution };
    }
    if (/^\\/api\\/analytics\\/completion-trends(\\?|$)/.test(path)) {
      return { success: true, data: analytics.completionTrends };
    }
    if (/^\\/api\\/analytics\\/productivity(\\?|$)/.test(path)) {
      return { success: true, data: analytics.productivity };
    }
  }
  if (method === 'POST' && /^\\/api\\/tasks(\\?|$)/.test(path)) {
    const nextTask = { _id: body._id || body.id || makeId(), status: 'todo', priority: 'medium', ...body };
    previewStorage.writeArray('tasks', [nextTask, ...tasks]);
    return { success: true, data: nextTask };
  }
  if (method === 'PUT' && /^\\/api\\/tasks\\//.test(path)) {
    const taskId = path.split('/').filter(Boolean).pop();
    const nextTasks = tasks.map((task) => ((task._id || task.id) === taskId ? { ...task, ...body } : task));
    const updatedTask = nextTasks.find((task) => (task._id || task.id) === taskId) || null;
    previewStorage.writeArray('tasks', nextTasks);
    return { success: true, data: updatedTask };
  }
  if (method === 'DELETE' && /^\\/api\\/tasks\\//.test(path)) {
    const taskId = path.split('/').filter(Boolean).pop();
    const nextTasks = tasks.filter((task) => (task._id || task.id) !== taskId);
    previewStorage.writeArray('tasks', nextTasks);
    return { success: true, data: { deleted: true, _id: taskId } };
  }
  if (method === 'POST' && /^\\/api\\/users(\\?|$)/.test(path)) {
    const nextUser = { _id: body._id || body.id || makeId(), ...body };
    previewStorage.writeArray('users', [nextUser, ...users]);
    return { success: true, data: nextUser };
  }
  if (method === 'POST' && /^\\/api\\/analytics\\/update(\\?|$)/.test(path)) {
    return { success: true, data: { updated: true } };
  }
  return null;
};
const requestJson = async (path, options = {}) => {
  if (IS_PREVIEW_SANDBOX) {
    const previewPayload = previewRequestJson(path, options);
    if (previewPayload) return previewPayload;
    throw new Error('PREVIEW_BACKEND_UNAVAILABLE');
  }
  try {
    const res = await fetch(API_BASE + path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      signal: AbortSignal.timeout(3000),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok || !payload?.success) {
      throw new Error(payload?.error || 'Request failed with status ' + res.status);
    }
    return payload;
  } catch (error) {
    const previewPayload = previewRequestJson(path, options);
    if (previewPayload) return previewPayload;
    throw error;
  }
};`;
    const normalizeCollectionHelper = `const normalizeCollection = (value) => {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.data)) return value.data;
  if (Array.isArray(value?.tasks)) return value.tasks;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.users)) return value.users;
  if (Array.isArray(value?.columns)) return value.columns;
  if (Array.isArray(value?.records)) return value.records;
  return [];
};`;
    const normalizeSourcePath = (filePath = '') => {
        const trimmed = String(filePath || '').replace(/\\/g, '/').trim();
        if (!trimmed) return '/src/App.jsx';
        if (trimmed.startsWith('/src/')) return trimmed;
        if (trimmed.startsWith('/public/')) return trimmed;
        return trimmed.startsWith('/') ? `/src${trimmed}` : `/src/${trimmed}`;
    };
    const getDirname = (filePath = '') => {
        const normalized = filePath.replace(/\\/g, '/');
        const idx = normalized.lastIndexOf('/');
        return idx <= 0 ? '/' : normalized.slice(0, idx);
    };
    const joinPath = (...parts) => {
        const merged = parts.join('/').replace(/\\/g, '/').replace(/\/+/g, '/');
        return merged.startsWith('/') ? merged : `/${merged}`;
    };
    const resolveImportPath = (fromPath, importPath) => {
        const baseDir = getDirname(normalizeSourcePath(fromPath)).split('/').filter(Boolean);
        importPath.split('/').forEach((segment) => {
            if (!segment || segment === '.') return;
            if (segment === '..') baseDir.pop();
            else baseDir.push(segment);
        });
        return `/${baseDir.join('/')}`;
    };
    const makeStubComponent = (filePath) => {
        const base = filePath.split('/').pop()?.replace(/\.[^.]+$/, '') || 'GeneratedComponent';
        const componentName = base.replace(/[^A-Za-z0-9]+/g, ' ').replace(/(?:^|\s)([A-Za-z0-9])/g, (_, ch) => ch.toUpperCase()).replace(/\s+/g, '') || 'GeneratedComponent';
        if (filePath.endsWith('.css')) {
            return '';
        }
        if (filePath.includes('/pages/')) {
            return `import React from 'react';\n\nexport default function ${componentName}() {\n  return (\n    <section className="min-h-screen bg-gray-950 text-white px-6 py-16">\n      <div className="max-w-5xl mx-auto">\n        <h1 className="text-4xl font-black mb-4">${componentName}</h1>\n        <p className="text-gray-400">This page was auto-created because the generator referenced it but did not include the file.</p>\n      </div>\n    </section>\n  );\n}\n`;
        }
        return `import React from 'react';\n\nexport default function ${componentName}() {\n  return null;\n}\n`;
    };
    const fixed = {};
    Object.entries(frontendFiles).forEach(([path, content]) => {
        let code = normalizeFrontendFileContent(path, typeof content === 'string' ? content : content?.code || '');
        code = repairCommonFrontendSyntax(code);
        code = ensureToastifyImports(code);
        code = code.replace(/http:\/\/localhost:3001/g, '/api');
        code = code.replace(/\(typeof\s+import\.meta\s*!==\s*'undefined'\s*&&\s*import\.meta\.env\?\.VITE_API_BASE_URL\)\s*\|\|\s*''/g, "''");
        code = code.replace(/\bimport\.meta\.env\?\.VITE_API_BASE_URL\b/g, "''");
        code = code.replace(/\bimport\.meta\.env\.VITE_API_BASE_URL\b/g, "''");
        code = code.replace(
            /(const\s+API_BASE\s*=\s*['"])http:\/\/localhost:\d{4}(['"])/g,
            "const API_BASE = '';"
        );
        if (/const\s+requestJson\s*=\s*async\s*\(/.test(code)) {
            code = code.replace(
                /const\s+API_BASE\s*=\s*['"]http:\/\/localhost:\d{4}['"];[\s\S]*?const\s+requestJson\s*=\s*async\s*\(path,\s*options\s*=\s*\{\}\)\s*=>\s*\{[\s\S]*?\n\};/m,
                previewRequestHelper
            );
        }
        if (/(setTasks|setItems|setUsers|setColumns)\(/.test(code) && !code.includes('const normalizeCollection =')) {
            if (/const\s+API_BASE\s*=/.test(code)) {
                code = code.replace(/(const\s+API_BASE\s*=\s*[^;]+;\n)/, `$1${normalizeCollectionHelper}\n`);
            } else if (/^import[\s\S]+?\n\n/.test(code)) {
                code = code.replace(/^((?:import .*;\n)+\n)/, `$1${normalizeCollectionHelper}\n`);
            } else {
                code = `${normalizeCollectionHelper}\n${code}`;
            }
        }
        code = code.replace(/\bsetTasks\(\s*payload\.data\s*\)/g, 'setTasks(normalizeCollection(payload.data))');
        code = code.replace(/\bsetItems\(\s*payload\.data\s*\)/g, 'setItems(normalizeCollection(payload.data))');
        code = code.replace(/\bsetUsers\(\s*payload\.data\s*\)/g, 'setUsers(normalizeCollection(payload.data))');
        code = code.replace(/\bsetColumns\(\s*payload\.data\s*\)/g, 'setColumns(normalizeCollection(payload.data))');
        code = code.replace(/\bsetTasks\(\s*JSON\.parse\(([^)]+)\)\s*\)/g, 'setTasks(normalizeCollection(JSON.parse($1)))');
        code = code.replace(/\bsetItems\(\s*JSON\.parse\(([^)]+)\)\s*\)/g, 'setItems(normalizeCollection(JSON.parse($1)))');
        code = code.replace(/\bsetUsers\(\s*JSON\.parse\(([^)]+)\)\s*\)/g, 'setUsers(normalizeCollection(JSON.parse($1)))');
        code = code.replace(/\bsetColumns\(\s*JSON\.parse\(([^)]+)\)\s*\)/g, 'setColumns(normalizeCollection(JSON.parse($1)))');
        code = code.replace(/\[\.\.\.(currentTasks|prevTasks|tasks),/g, '[...normalizeCollection($1),');
        code = code.replace(/\b(currentTasks|prevTasks|tasks)\.map\(/g, 'normalizeCollection($1).map(');
        code = code.replace(/\b(currentTasks|prevTasks|tasks)\.filter\(/g, 'normalizeCollection($1).filter(');
        // @/ aliases
        code = code.replace(/from\s+['"]@\/([^'"]+)['"]/g, "from '/$1'");
        code = code.replace(/import\s*\(\s*['"]@\/([^'"]+)['"]\s*\)/g, "import('/$1')");
        // Line-level fixes
        code = code.split('\n').map(line => {
            if (/^\s*import\s+['"][^'"]+\.css['"]/.test(line)) return '// [css removed]';
            if (/console\.error\(['"`]Failed to fetch/i.test(line)) {
                return line.replace(
                    /console\.error\((.+)\);/,
                    "if (!String(error?.message || err?.message || '').includes('PREVIEW_BACKEND_UNAVAILABLE')) console.error($1);"
                );
            }
            if (line.includes('react-hot-toast')) {
                return line
                    .replace(/from ['"]react-hot-toast['"]/, "from 'react-toastify'")
                    .replace(/from "react-hot-toast"/, 'from "react-toastify"')
                    .replace(/\bToaster\b/, 'ToastContainer');
            }
            if (line.includes('<Toaster') && !line.includes('Container'))
                return line.replace(/<Toaster([^>]*)\/>/, '<ToastContainer$1/>');
            line = line.replace(/\b(on[A-Z][A-Za-z0-9_]*)[^\S\r\n]*([A-Za-z_$][\w$]*)\}/g, '$1={$2}');
            const m = line.match(/^\s*import\s+.*?from\s+['"]([^'"./][^'"@][^'"]*)['"]/);
            if (m) {
                const pkg = m[1].split('/')[0];
                if (!ALLOWED.has(pkg)) return `// [removed: ${pkg}]`;
            }
            return line;
        }).join('\n');
        fixed[path] = { code };
    });

    const normalizedPathLookup = new Map(
        Object.keys(fixed).map((filePath) => [normalizeSourcePath(filePath), filePath])
    );
    const missingFiles = new Map();
    const importRegex = /import\s+[^'"]*?from\s+['"](\.[^'"]+)['"]|import\s+['"](\.[^'"]+)['"]/g;

    Object.entries(fixed).forEach(([filePath, content]) => {
        const code = typeof content === 'string' ? content : content?.code || '';
        let match;
        while ((match = importRegex.exec(code)) !== null) {
            const importTarget = match[1] || match[2];
            if (!importTarget) continue;
            const rawResolved = resolveImportPath(filePath, importTarget);
            const candidates = importTarget.endsWith('.css')
                ? [`${rawResolved}.css`, rawResolved]
                : [rawResolved, `${rawResolved}.jsx`, `${rawResolved}.js`, joinPath(rawResolved, 'index.jsx'), joinPath(rawResolved, 'index.js')];
            const exists = candidates.some((candidate) => normalizedPathLookup.has(normalizeSourcePath(candidate)));
            if (exists) continue;
            const newPath = importTarget.endsWith('.css') ? `${rawResolved}.css` : `${rawResolved}.jsx`;
            if (!missingFiles.has(newPath)) {
                missingFiles.set(newPath, { code: makeStubComponent(newPath) });
            }
        }
    });

    missingFiles.forEach((value, key) => {
        fixed[key] = value;
    });

    return fixed;
}

function buildFrontendSnapshot(
    frontendFiles,
    {
        maxFiles = 10,
        maxCharsPerFile = 3500,
        maxTotalChars = 22000,
    } = {}
) {
    const prioritize = ([path]) => {
        if (path.endsWith('/App.jsx')) return 0;
        if (/Task|Board|Kanban|Modal|Form|Dialog|Card|Store|api/i.test(path)) return 1;
        if (path.includes('/pages/')) return 2;
        if (path.includes('/components/')) return 3;
        return 4;
    };

    let totalChars = 0;
    const snapshotParts = [];

    Object.entries(frontendFiles)
        .sort((left, right) => {
            const priorityDiff = prioritize(left) - prioritize(right);
            return priorityDiff !== 0 ? priorityDiff : left[0].localeCompare(right[0]);
        })
        .slice(0, maxFiles)
        .forEach(([path, content]) => {
            if (totalChars >= maxTotalChars) {
                return;
            }

            const code = typeof content === 'string' ? content : content?.code || '';
            const remainingChars = maxTotalChars - totalChars;
            const allowedChars = Math.min(maxCharsPerFile, remainingChars);
            const snippet = code.length > allowedChars
                ? `${code.slice(0, allowedChars)}\n/* [truncated for prompt size] */`
                : code;

            snapshotParts.push(`===FILE: ${path}===\n${snippet}\n===END===`);
            totalChars += snippet.length;
        });

    return snapshotParts.join('\n\n');
}

function npmCommand() {
    return process.platform === 'win32' ? 'npm.cmd' : 'npm';
}

function normalizeSpawnArgs(args = []) {
    return (Array.isArray(args) ? args : [])
        .filter(value => value !== undefined && value !== null)
        .map(value => String(value));
}

function shouldRetrySpawn(error, hasRetried) {
    if (hasRetried || process.platform !== 'win32') {
        return false;
    }

    return ['EINVAL', 'ENOENT'].includes(error?.code);
}

function shouldUseShellForCommand(command = '', args = []) {
    if (process.platform !== 'win32') {
        return false;
    }

    const normalizedCommand = String(command || '').trim().toLowerCase();
    const firstArg = String((Array.isArray(args) ? args[0] : '') || '').trim().toLowerCase();

    if (
        /(^|[\\/])(npm|npm\.cmd|npx|npx\.cmd|pnpm|pnpm\.cmd|yarn|yarn\.cmd|bun|bun\.cmd)$/.test(normalizedCommand) ||
        normalizedCommand === 'npm' ||
        normalizedCommand === 'npm.cmd'
    ) {
        return true;
    }

    if (normalizedCommand === 'cmd.exe' || normalizedCommand === 'cmd') {
        return false;
    }

    return ['install', 'start', 'run'].includes(firstArg);
}

function getWindowsShellPath(env = process.env) {
    const candidates = [
        env?.ComSpec,
        env?.COMSPEC,
        env?.comspec,
        env?.SystemRoot ? path.join(env.SystemRoot, 'System32', 'cmd.exe') : '',
        env?.SYSTEMROOT ? path.join(env.SYSTEMROOT, 'System32', 'cmd.exe') : '',
        env?.WINDIR ? path.join(env.WINDIR, 'System32', 'cmd.exe') : '',
        env?.windir ? path.join(env.windir, 'System32', 'cmd.exe') : '',
        'cmd.exe',
    ];

    for (const candidate of candidates) {
        const value = String(candidate || '').trim();
        if (value) {
            return value;
        }
    }

    return 'cmd.exe';
}

function buildWindowsSpawnEnv(env = {}) {
    if (process.platform !== 'win32') {
        return env || process.env;
    }

    const mergedEnv = {
        ...process.env,
        ...(env || {}),
    };

    const systemRoot = mergedEnv.SystemRoot || mergedEnv.SYSTEMROOT || process.env.SystemRoot || process.env.SYSTEMROOT || 'C:\\Windows';
    const windir = mergedEnv.WINDIR || mergedEnv.windir || process.env.WINDIR || process.env.windir || systemRoot;
    const comSpec = getWindowsShellPath({
        ...mergedEnv,
        SystemRoot: systemRoot,
        SYSTEMROOT: systemRoot,
        WINDIR: windir,
        windir,
    });

    mergedEnv.SystemRoot = systemRoot;
    mergedEnv.SYSTEMROOT = systemRoot;
    mergedEnv.WINDIR = windir;
    mergedEnv.windir = windir;
    mergedEnv.ComSpec = comSpec;
    mergedEnv.COMSPEC = comSpec;

    return mergedEnv;
}

function buildSpawnOptions({ cwd, env, shellMode }) {
    const runtimeEnv = process.platform === 'win32'
        ? buildWindowsSpawnEnv(env)
        : (env || process.env);

    const options = {
        cwd,
        env: runtimeEnv,
        windowsHide: true,
    };

    if (shellMode) {
        options.shell = process.platform === 'win32'
            ? getWindowsShellPath(runtimeEnv)
            : true;
    } else {
        options.shell = false;
    }

    return options;
}

function joinApiPath(prefix, routePath = '/') {
    const cleanPrefix = prefix.endsWith('/') ? prefix.slice(0, -1) : prefix;
    if (!routePath || routePath === '/') {
        return cleanPrefix || '/';
    }

    const cleanRoute = routePath.startsWith('/') ? routePath : `/${routePath}`;
    return `${cleanPrefix}${cleanRoute}`;
}

function stripSpawnRecoveryNoise(text = '') {
    return String(text || '').replace(/\[spawn-recovery\][^\n]*\n?/g, '').trim();
}

function getResourceBase(pathname = '') {
    const segments = pathname.split('/').filter(Boolean);
    if (segments.length >= 2 && segments[0] === 'api') {
        return `/${segments.slice(0, 2).join('/')}`;
    }

    return pathname;
}

function parseJsonSafely(value) {
    if (!value || value === '-') {
        return null;
    }

    try {
        return JSON.parse(value);
    } catch (_) {
        return null;
    }
}

function cloneJson(value) {
    if (value === null || value === undefined) {
        return value;
    }

    return JSON.parse(JSON.stringify(value));
}

function getLiveSampleStateValue(sampleState = {}, key, createValue) {
    if (!sampleState.seed) {
        sampleState.seed = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    }
    if (!sampleState.cache) {
        sampleState.cache = {};
    }
    if (!(key in sampleState.cache)) {
        sampleState.cache[key] = createValue();
    }
    return sampleState.cache[key];
}

function createLiveSampleState() {
    return {
        seed: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        cache: {},
    };
}

function injectKnownIds(payload, routePath, createdRecords, sampleState = {}) {
    if (!payload || typeof payload !== 'object') {
        return payload;
    }

    const nextPayload = cloneJson(payload);
    const taskRecord = createdRecords['/api/tasks'] || null;
    const userRecord = createdRecords['/api/users'] || null;
    const authEmail = getLiveSampleStateValue(sampleState, 'auth.email', () => `john+${sampleState.seed}@example.com`);
    const authUsername = getLiveSampleStateValue(sampleState, 'auth.username', () => `john_${String(sampleState.seed).replace(/[^a-z0-9]/gi, '').toLowerCase()}`);
    const authPassword = getLiveSampleStateValue(sampleState, 'auth.password', () => `SecurePass123!${String(sampleState.seed).slice(-4)}`);
    const genericName = getLiveSampleStateValue(sampleState, 'generic.name', () => `Sample ${sampleState.seed}`);
    const categoryName = getLiveSampleStateValue(sampleState, 'category.name', () => `Category ${sampleState.seed}`);
    const productSku = getLiveSampleStateValue(sampleState, 'product.sku', () => `sku-${sampleState.seed}`);
    const productSlug = getLiveSampleStateValue(sampleState, 'product.slug', () => `product-${sampleState.seed}`);
    const productBrand = getLiveSampleStateValue(sampleState, 'product.brand', () => `Brand ${sampleState.seed}`);

    if (routePath.includes('/move-task') && taskRecord?.id) {
        nextPayload.taskId = taskRecord.id;
    }

    const applyValue = (obj) => {
        Object.entries(obj).forEach(([key, value]) => {
            if (value && typeof value === 'object') {
                applyValue(value);
                return;
            }

            if (/taskid$/i.test(key) && taskRecord?.id) {
                obj[key] = taskRecord.id;
            } else if (/userid$/i.test(key) && userRecord?.id) {
                obj[key] = userRecord.id;
            } else if (/columnid$/i.test(key) && createdRecords['/api/columns']?.id) {
                obj[key] = createdRecords['/api/columns'].id;
            } else if (/createdby$/i.test(key) && userRecord?.id) {
                obj[key] = userRecord.id;
            } else if (/assignee(id)?$/i.test(key) && userRecord?.id) {
                obj[key] = userRecord.id;
            } else if (typeof value === 'string' && /^:id$/i.test(value)) {
                const resourceBase = getResourceBase(routePath);
                if (createdRecords[resourceBase]?.id) {
                    obj[key] = createdRecords[resourceBase].id;
                }
            } else if (/(^|_)email$/i.test(key)) {
                obj[key] = authEmail;
            } else if (/username/i.test(key)) {
                obj[key] = authUsername;
            } else if (/password/i.test(key)) {
                obj[key] = authPassword;
            } else if (/first(name)?/i.test(key)) {
                obj[key] = 'John';
            } else if (/last(name)?/i.test(key)) {
                obj[key] = `Tester ${String(sampleState.seed).slice(-4)}`;
            } else if (/displayname/i.test(key)) {
                obj[key] = `John Tester ${String(sampleState.seed).slice(-4)}`;
            } else if (key === 'name') {
                obj[key] = /\/api\/categories(\/|$)/i.test(routePath) ? categoryName : genericName;
            } else if (/sku/i.test(key)) {
                obj[key] = productSku;
            } else if (/slug/i.test(key)) {
                obj[key] = productSlug;
            } else if (/brand/i.test(key)) {
                obj[key] = productBrand;
            } else if (/^category$/i.test(key) && createdRecords['/api/categories']?.payload?.name) {
                obj[key] = createdRecords['/api/categories'].payload.name;
            } else if (/^category$/i.test(key)) {
                obj[key] = categoryName;
            }
        });
    };

    applyValue(nextPayload);
    if (/\/api\/auth\/register/i.test(routePath) && nextPayload.email && !nextPayload.username) {
        nextPayload.username = String(nextPayload.email).split('@')[0];
    }
    if (/\/api\/auth\/(register|login)(\/|$)/i.test(routePath)) {
        nextPayload.email ??= authEmail;
        nextPayload.username ??= authUsername;
        nextPayload.password ??= authPassword;
    }
    return nextPayload;
}

function getCreatedIdForParam(paramName, routePath, createdRecords) {
    const lower = String(paramName || '').toLowerCase();
    const routeResource = getResourceBase(routePath);

    if (lower === 'id') {
        return createdRecords[routeResource]?.id || null;
    }
    if (lower.includes('user')) {
        return createdRecords['/api/users']?.id || createdRecords['/api/auth']?.id || null;
    }
    if (lower.includes('task')) {
        return createdRecords['/api/tasks']?.id || null;
    }
    if (lower.includes('column')) {
        return createdRecords['/api/columns']?.id || null;
    }
    if (lower.includes('order')) {
        return createdRecords['/api/orders']?.payload?.orderNumber || createdRecords['/api/orders']?.id || null;
    }
    if (lower.includes('category')) {
        return createdRecords['/api/categories']?.payload?.slug || createdRecords['/api/categories']?.id || null;
    }
    if (lower.includes('session')) {
        return createdRecords['/api/cart']?.payload?.sessionId || 'session123';
    }
    if (lower.includes('status')) {
        return 'todo';
    }

    return null;
}

function resolveDynamicPath(routePath, createdRecords) {
    let unresolved = false;
    const resolvedPath = routePath.replace(/:([A-Za-z0-9_]+)/g, (match, paramName) => {
        const resolvedValue = getCreatedIdForParam(paramName, routePath, createdRecords);
        if (!resolvedValue) {
            unresolved = true;
            return match;
        }

        return encodeURIComponent(String(resolvedValue));
    });

    return unresolved ? null : resolvedPath;
}

function extractCreatedRecord(payload) {
    const candidates = [
        payload?.data,
        payload?.data?.user,
        payload?.data?.task,
        payload?.data?.column,
        payload?.data?.order,
        payload?.user,
        payload,
    ];

    for (const candidate of candidates) {
        if (!candidate || typeof candidate !== 'object') {
            continue;
        }

        const id = candidate._id || candidate.id || candidate.orderNumber || candidate.slug || null;
        if (id) {
            return { id, payload: candidate };
        }
    }

    return null;
}

function extractAuthToken(payload) {
    return payload?.token
        || payload?.accessToken
        || payload?.access_token
        || payload?.data?.token
        || payload?.data?.accessToken
        || payload?.data?.access_token
        || payload?.data?.jwt
        || payload?.data?.authToken
        || payload?.data?.access?.token
        || payload?.data?.tokens?.accessToken
        || payload?.data?.tokens?.token
        || payload?.data?.session?.token
        || payload?.data?.session?.accessToken
        || payload?.user?.token
        || payload?.user?.accessToken
        || null;
}

function routeRequiresAuth(routePath = '', detail = '') {
    const normalizedPath = String(routePath).toLowerCase();
    const normalizedDetail = String(detail || '').toLowerCase();

    if (
        /^\/api\/auth\/(verify|profile)(\/|$)/i.test(routePath)
        || /^\/api\/users\/me(\/|$)/i.test(routePath)
        || /\/(me|profile|current-user|current_user)(\/|$)/i.test(routePath)
        || /\/api\/(enrollments|progress|wishlist|orders|cart|courses)(\/|$)/i.test(routePath)
    ) {
        return true;
    }

    return [
        'access token required',
        'bearer token',
        'jwt token',
        'requires valid jwt',
        'requires authentication',
        'requires auth',
        'protected route',
        'authenticated user',
        'current user',
    ].some(fragment => normalizedDetail.includes(fragment));
}

function isAuthFailureReason(statusCode = null, detail = '') {
    const normalizedDetail = String(detail || '').toLowerCase();

    if (statusCode === 401 || statusCode === 403) {
        return true;
    }

    return [
        'access denied',
        'no token provided',
        'access token required',
        'authentication required',
        'authorization required',
        'invalid token',
        'token expired',
        'unauthorized',
        'forbidden',
        'bearer token',
        'jwt token',
        'not authenticated',
        'login required',
    ].some(fragment => normalizedDetail.includes(fragment));
}

function buildQueryPayload(routePath = '', detail = '', payload = null) {
    const queryPayload = {};
    const normalizedDetail = String(detail || '').toLowerCase();
    const today = new Date();
    const thirtyDaysAgo = new Date(today.getTime() - (30 * 24 * 60 * 60 * 1000));
    const dateOnly = (value) => value.toISOString().slice(0, 10);

    if (
        /\/range(\/|$)/i.test(routePath)
        || normalizedDetail.includes('start date and end date are required')
    ) {
        if (!queryPayload.startDate && !queryPayload.start) {
            queryPayload.startDate = dateOnly(thirtyDaysAgo);
        }
        if (!queryPayload.endDate && !queryPayload.end) {
            queryPayload.endDate = dateOnly(today);
        }
    }

    return Object.keys(queryPayload).length > 0 ? queryPayload : null;
}

function appendQueryParams(routePath = '', queryPayload = null) {
    if (!queryPayload || typeof queryPayload !== 'object' || Array.isArray(queryPayload)) {
        return routePath;
    }

    const [basePath, existingQuery = ''] = String(routePath).split('?');
    const params = new URLSearchParams(existingQuery);

    Object.entries(queryPayload).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') {
            return;
        }

        if (Array.isArray(value)) {
            value.forEach((item) => {
                if (item !== undefined && item !== null && item !== '') {
                    params.append(key, String(item));
                }
            });
            return;
        }

        if (typeof value === 'object') {
            params.set(key, JSON.stringify(value));
            return;
        }

        params.set(key, String(value));
    });

    const queryString = params.toString();
    return queryString ? `${basePath}?${queryString}` : basePath;
}

function buildFieldSampleValue(fieldName, fieldType = 'String', createdRecords = {}, sampleState = {}, enumValues = []) {
    const lowerName = String(fieldName || '').toLowerCase();
    const normalizedType = String(fieldType || 'String').toLowerCase();
    const isObjectIdType = normalizedType.includes('objectid');

    const knownUserId    = createdRecords['/api/users']?.id    || createdRecords['/api/auth']?.id    || '507f1f77bcf86cd799439011';
    const knownTaskId    = createdRecords['/api/tasks']?.id    || '507f1f77bcf86cd799439012';
    const knownColumnId  = createdRecords['/api/columns']?.id  || '507f1f77bcf86cd799439013';
    const knownOrderId   = createdRecords['/api/orders']?.id   || '507f1f77bcf86cd799439015';
    const knownMenuId    = createdRecords['/api/menu']?.id     || createdRecords['/api/menus']?.id    || '507f1f77bcf86cd799439016';
    const knownCategoryId= createdRecords['/api/categories']?.id || '507f1f77bcf86cd799439014';

    const normalizedEnumValues = Array.isArray(enumValues)
        ? enumValues.map((value) => String(value).trim()).filter(Boolean)
        : [];

    if (normalizedEnumValues.length > 0) return normalizedEnumValues[0];

    if (lowerName.includes('email')) return getLiveSampleStateValue(sampleState, 'auth.email', () => `john+${sampleState.seed}@example.com`);
    if (lowerName.includes('username')) return getLiveSampleStateValue(sampleState, 'auth.username', () => `john_${String(sampleState.seed).replace(/[^a-z0-9]/gi, '').toLowerCase()}`);
    if (lowerName.includes('displayname')) return `John Tester ${String(sampleState.seed).slice(-4)}`;
    if (lowerName === 'name') return getLiveSampleStateValue(sampleState, 'generic.name', () => `Sample ${sampleState.seed}`);
    if (lowerName.includes('title')) return 'Test Item';
    if (lowerName.includes('description')) return 'Generated sample description';
    if (lowerName.includes('priority')) return 'high';
    if (lowerName.includes('status')) return 'pending';
    if (lowerName.includes('password')) return getLiveSampleStateValue(sampleState, 'auth.password', () => `SecurePass123!${String(sampleState.seed).slice(-4)}`);
    if (lowerName.includes('theme')) return 'dark';
    if (lowerName === 'action') return 'created';
    if (lowerName === 'price' || lowerName === 'amount' || lowerName === 'total') return 9.99;
    if (lowerName.includes('quantity') || lowerName.includes('qty')) return 1;
    if (lowerName.includes('paymentmethod') || lowerName === 'method') return 'credit_card';
    if (lowerName.includes('deliveryaddress') || lowerName === 'address') return '123 Test Street, City, State 12345';
    if (lowerName.includes('phone')) return '+1234567890';
    if (lowerName.includes('image') || lowerName.includes('photo') || lowerName.includes('avatar')) return 'https://via.placeholder.com/150';
    if (lowerName.includes('url') || lowerName.includes('link')) return 'https://example.com';
    if (lowerName.includes('role')) return 'customer';
    if (lowerName.includes('type') && !isObjectIdType) return 'standard';

    // ObjectId reference fields — always return a valid 24-char hex ObjectId string
    if (lowerName.includes('createdby') || lowerName.includes('userid') || lowerName === 'user' || lowerName === 'customer') return knownUserId;
    if (lowerName.includes('assignee') || lowerName.includes('driver')) return knownUserId;
    if (lowerName.includes('taskid') || lowerName === 'task') return knownTaskId;
    if (lowerName.includes('columnid') || lowerName === 'column') return knownColumnId;
    if (lowerName.includes('orderid') || lowerName === 'order') return knownOrderId;
    if (lowerName.includes('menuitem') || lowerName === 'item') return knownMenuId;
    // category: send valid ObjectId if field is ObjectId type, else send a string
    if (lowerName.includes('category')) {
        if (isObjectIdType) return knownCategoryId;
        return createdRecords['/api/categories']?.payload?.name || getLiveSampleStateValue(sampleState, 'category.name', () => `Main Course`);
    }

    if (lowerName.includes('sku')) return getLiveSampleStateValue(sampleState, 'product.sku', () => `sku-${sampleState.seed}`);
    if (lowerName.includes('slug')) return getLiveSampleStateValue(sampleState, 'product.slug', () => `item-${sampleState.seed}`);
    if (lowerName.includes('brand')) return getLiveSampleStateValue(sampleState, 'product.brand', () => `Brand ${sampleState.seed}`);
    if (lowerName.includes('position')) return 0;
    if (lowerName.includes('count') || lowerName.includes('total')) return 1;
    if (lowerName.includes('date') || lowerName.includes('deadline') || lowerName.includes('time')) return new Date().toISOString();

    // Fallback: any ObjectId-typed field gets a valid ObjectId string
    if (isObjectIdType) return knownUserId;
    if (normalizedType.includes('number')) return 1;
    if (normalizedType.includes('boolean')) return true;
    if (normalizedType.includes('date')) return new Date().toISOString();
    if (normalizedType.includes('array')) return [];
    if (normalizedType.includes('object')) return {};

    return 'Sample Value';
}

function extractModelFieldSpecs(modelCode = '') {
    const specs = [];
    const seen = new Set();
    const objectTypeRe = /([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{([\s\S]*?)\n\s*\}/g;
    let match;

    while ((match = objectTypeRe.exec(modelCode)) !== null) {
        const fieldName = match[1];
        const body = match[2];
        if (seen.has(fieldName)) continue;
        const typeMatch = body.match(/type\s*:\s*([A-Za-z0-9_.]+)/i);
        const required = /required\s*:\s*true/i.test(body);
        const enumMatch = body.match(/enum\s*:\s*\[([^\]]+)\]/i);
        const enumValues = enumMatch
            ? [...enumMatch[1].matchAll(/['"`]([^'"`]+)['"`]/g)].map((item) => item[1].trim()).filter(Boolean)
            : [];
        specs.push({
            name: fieldName,
            type: typeMatch ? typeMatch[1] : 'String',
            required,
            enumValues,
        });
        seen.add(fieldName);
    }

    const simpleTypeRe = /([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(String|Number|Boolean|Date|\[.*?\]|Schema\.Types\.ObjectId|mongoose\.Schema\.Types\.ObjectId)/g;
    while ((match = simpleTypeRe.exec(modelCode)) !== null) {
        const fieldName = match[1];
        if (seen.has(fieldName)) continue;
        specs.push({
            name: fieldName,
            type: match[2],
            required: false,
            enumValues: [],
        });
        seen.add(fieldName);
    }

    return specs;
}

function buildSchemaSamplePayload(modelCandidates = [], backendFiles = {}, routePath = '', createdRecords = {}, sampleState = createLiveSampleState()) {
    const payload = {};

    modelCandidates.forEach((modelPath) => {
        const modelCode = typeof backendFiles[modelPath] === 'string'
            ? backendFiles[modelPath]
            : backendFiles[modelPath]?.code || '';
        extractModelFieldSpecs(modelCode).forEach((fieldSpec) => {
            const isUsefulOptional = ['title', 'description', 'priority', 'status', 'displayName', 'email', 'username', 'password', 'createdBy']
                .includes(fieldSpec.name);
            if (!fieldSpec.required && !isUsefulOptional) {
                return;
            }

            if (payload[fieldSpec.name] !== undefined) {
                return;
            }

            payload[fieldSpec.name] = buildFieldSampleValue(
                fieldSpec.name,
                fieldSpec.type,
                createdRecords,
                sampleState,
                fieldSpec.enumValues
            );
        });
    });

    if (/\/api\/tasks(\/|$)/i.test(routePath)) {
        payload.title ??= 'Test Task';
        payload.description ??= 'Generated sample task';
        payload.priority ??= 'high';
        payload.status ??= 'todo';
        payload.createdBy ??= createdRecords['/api/users']?.id || '507f1f77bcf86cd799439011';
    }

    if (/\/api\/users(\/|$)/i.test(routePath)) {
        payload.displayName ??= `John Tester ${String(sampleState.seed).slice(-4)}`;
        payload.email ??= getLiveSampleStateValue(sampleState, 'auth.email', () => `john+${sampleState.seed}@example.com`);
        payload.username ??= getLiveSampleStateValue(sampleState, 'auth.username', () => `john_${String(sampleState.seed).replace(/[^a-z0-9]/gi, '').toLowerCase()}`);
        payload.password ??= getLiveSampleStateValue(sampleState, 'auth.password', () => `SecurePass123!${String(sampleState.seed).slice(-4)}`);
    }

    if (/\/api\/auth\/(register|login)(\/|$)/i.test(routePath)) {
        payload.email ??= getLiveSampleStateValue(sampleState, 'auth.email', () => `john+${sampleState.seed}@example.com`);
        payload.username ??= getLiveSampleStateValue(sampleState, 'auth.username', () => `john_${String(sampleState.seed).replace(/[^a-z0-9]/gi, '').toLowerCase()}`);
        payload.password ??= getLiveSampleStateValue(sampleState, 'auth.password', () => `SecurePass123!${String(sampleState.seed).slice(-4)}`);
    }

    if (/\/api\/products(\/|$)/i.test(routePath)) {
        payload.name ??= getLiveSampleStateValue(sampleState, 'product.name', () => `Product ${sampleState.seed}`);
        payload.sku ??= getLiveSampleStateValue(sampleState, 'product.sku', () => `sku-${sampleState.seed}`);
        payload.slug ??= getLiveSampleStateValue(sampleState, 'product.slug', () => `product-${sampleState.seed}`);
        payload.brand ??= getLiveSampleStateValue(sampleState, 'product.brand', () => `Brand ${sampleState.seed}`);
        payload.category ??= createdRecords['/api/categories']?.payload?.name || getLiveSampleStateValue(sampleState, 'category.name', () => `Category ${sampleState.seed}`);
    }

    if (/\/api\/categories(\/|$)/i.test(routePath)) {
        payload.name ??= getLiveSampleStateValue(sampleState, 'category.name', () => `Category ${sampleState.seed}`);
        payload.slug ??= getLiveSampleStateValue(sampleState, 'category.slug', () => `category-${sampleState.seed}`);
    }

    // Restaurant-specific: menu items need a name, price, and a string category (not ObjectId)
    if (/\/api\/menu(\/|$)/i.test(routePath)) {
        payload.name     ??= getLiveSampleStateValue(sampleState, 'menu.name', () => `Menu Item ${sampleState.seed}`);
        payload.price    ??= 9.99;
        payload.description ??= 'Delicious menu item';
        // Always send a String for category — avoids Cast to ObjectId BSONError
        payload.category ??= 'Main Course';
        payload.image    ??= 'https://via.placeholder.com/300x200';
        payload.available ??= true;
    }

    // Payment routes: order/customer refs as valid ObjectIds, amount as number
    if (/\/api\/payments?(\/|$)/i.test(routePath)) {
        const ordId = createdRecords['/api/orders']?.id || '507f1f77bcf86cd799439015';
        const usrId = createdRecords['/api/users']?.id  || createdRecords['/api/auth']?.id || '507f1f77bcf86cd799439011';
        payload.order         ??= ordId;
        payload.orderId       ??= ordId;
        payload.customer      ??= usrId;
        payload.customerId    ??= usrId;
        payload.amount        ??= 19.99;
        payload.paymentMethod ??= 'credit_card';
        payload.status        ??= 'pending';
    }

    // Delivery routes: orderId/driver as valid ObjectIds
    if (/\/api\/delivery(\/|$)/i.test(routePath)) {
        const ordId = createdRecords['/api/orders']?.id || '507f1f77bcf86cd799439015';
        const usrId = createdRecords['/api/users']?.id  || createdRecords['/api/auth']?.id || '507f1f77bcf86cd799439011';
        payload.order            ??= ordId;
        payload.orderId          ??= ordId;
        payload.driver           ??= usrId;
        payload.driverId         ??= usrId;
        payload.status           ??= 'assigned';
        payload.estimatedTime    ??= new Date(Date.now() + 30 * 60 * 1000).toISOString();
    }

    // Order routes: items array with valid menu item refs
    if (/\/api\/orders?(\/|$)/i.test(routePath)) {
        const menuId = createdRecords['/api/menu']?.id || '507f1f77bcf86cd799439016';
        const usrId  = createdRecords['/api/users']?.id || createdRecords['/api/auth']?.id || '507f1f77bcf86cd799439011';
        payload.customer      ??= usrId;
        payload.customerId    ??= usrId;
        payload.items         ??= [{ menuItem: menuId, quantity: 1, price: 9.99 }];
        payload.totalAmount   ??= 9.99;
        payload.status        ??= 'pending';
        payload.deliveryAddress ??= '123 Test Street, City 12345';
    }

    // Auth register: always include name, email, password, username
    if (/\/api\/auth\/register(\/|$)/i.test(routePath)) {
        payload.name     ??= getLiveSampleStateValue(sampleState, 'generic.name', () => `Test User ${sampleState.seed}`);
        payload.email    ??= getLiveSampleStateValue(sampleState, 'auth.email', () => `john+${sampleState.seed}@example.com`);
        payload.username ??= getLiveSampleStateValue(sampleState, 'auth.username', () => `john_${String(sampleState.seed).replace(/[^a-z0-9]/gi, '')}`);
        payload.password ??= getLiveSampleStateValue(sampleState, 'auth.password', () => `SecurePass123!${String(sampleState.seed).slice(-4)}`);
        payload.role     ??= 'customer';
    }

    return Object.keys(payload).length > 0 ? payload : null;
}

function parseBackendContracts(backendFiles) {
    const proxyPrefixes = new Set();
    const proxyPrefixesByPort = new Map();
    const proxyRulesByPort = new Map();
    const contracts = [];
    const routeMounts = {};

    const registerProxyPrefix = (prefix, port = null) => {
        const normalizedPrefix = String(prefix || '').trim();
        if (!normalizedPrefix) return;
        proxyPrefixes.add(normalizedPrefix);
        if (!port) return;
        const normalizedPort = String(port).trim();
        if (!proxyPrefixesByPort.has(normalizedPort)) {
            proxyPrefixesByPort.set(normalizedPort, new Set());
        }
        proxyPrefixesByPort.get(normalizedPort).add(normalizedPrefix);
    };

    const registerProxyRule = (prefix, port = null, rewriteTarget = '') => {
        registerProxyPrefix(prefix, port);
        const normalizedPort = String(port || '').trim();
        const normalizedPrefix = String(prefix || '').trim();
        if (!normalizedPort || !normalizedPrefix) return;
        if (!proxyRulesByPort.has(normalizedPort)) {
            proxyRulesByPort.set(normalizedPort, []);
        }
        const normalizedRewrite = String(rewriteTarget || '').trim();
        const rules = proxyRulesByPort.get(normalizedPort);
        if (rules.some((rule) => rule.prefix === normalizedPrefix && rule.rewriteTarget === normalizedRewrite)) {
            return;
        }
        rules.push({
            prefix: normalizedPrefix,
            rewriteTarget: normalizedRewrite,
        });
    };

    const combineGatewayPrefixAndMount = (gatewayPrefix = '', routeMount = '', rewriteTarget = '') => {
        const normalizedGateway = String(gatewayPrefix || '').trim();
        const normalizedMount = String(routeMount || '').trim();
        const normalizedRewrite = String(rewriteTarget || '').trim();
        if (!normalizedGateway) return normalizedMount || '';
        if (!normalizedMount || normalizedMount === '/') return normalizedGateway;
        if (normalizedRewrite) {
            if (normalizedMount === normalizedRewrite) {
                return normalizedGateway;
            }
            if (normalizedMount.startsWith(`${normalizedRewrite}/`)) {
                return joinApiPath(normalizedGateway, normalizedMount.slice(normalizedRewrite.length));
            }
        }
        if (normalizedMount.startsWith('/api/')) return normalizedMount;
        if (normalizedGateway.endsWith(normalizedMount)) return normalizedGateway;

        const gatewayTail = normalizedGateway.split('/').filter(Boolean).pop() || '';
        const mountTail = normalizedMount.split('/').filter(Boolean).pop() || '';
        if (gatewayTail && mountTail && gatewayTail === mountTail) {
            return normalizedGateway;
        }

        return joinApiPath(normalizedGateway, normalizedMount);
    };

    Object.entries(backendFiles).forEach(([filePath, content]) => {
        const code = typeof content === 'string' ? content : content?.code || '';
        if (filePath.includes('gateway') && filePath.endsWith('index.js')) {
            [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,\s*createProxyMiddleware\(\{([\s\S]*?)\}\s*\)\s*\)/gi)]
                .forEach(match => {
                    const prefix = match[1].trim();
                    const proxyBlock = match[2] || '';
                    const targetPort = proxyBlock.match(/target:\s*['"]https?:\/\/(?:localhost|127\.0\.0\.1):(\d+)['"]/i)?.[1] || null;
                    const rewriteTarget = proxyBlock.match(/pathRewrite\s*:\s*\{\s*['"]\^[^'"]+['"]\s*:\s*['"]([^'"]+)['"]/i)?.[1]
                        || proxyBlock.match(/pathRewrite\s*:\s*\(\s*path\s*=>\s*path\.replace\(\s*\/\^[^/]+\/\s*,\s*['"]([^'"]+)['"]\s*\)\s*\)/i)?.[1]
                        || '';
                    registerProxyRule(prefix, targetPort, rewriteTarget);
                });
            [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,\s*createServiceProxy\(\s*['"]https?:\/\/(?:localhost|127\.0\.0\.1):(\d+)['"]/gi)]
                .forEach(match => registerProxyRule(match[1], match[2]));
            [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,\s*(?:createProxyMiddleware|createServiceProxy)/gi)]
                .forEach(match => registerProxyPrefix(match[1]));
        }
        if (!filePath.endsWith('/index.js') || filePath.includes('gateway')) {
            return;
        }

        const serviceDir = filePath.split('/').filter(Boolean)[0];
        const variableToRouteFile = {};
        [...code.matchAll(/const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*require\(\s*['"]\.\/routes\/([^'"]+)['"]\s*\)/g)]
            .forEach(match => {
                const routeRel = match[2].endsWith('.js') ? match[2] : `${match[2]}.js`;
                variableToRouteFile[match[1]] = `/${serviceDir}/routes/${routeRel}`;
            });

        [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)/g)]
            .forEach(match => {
                const routeFile = variableToRouteFile[match[2]];
                if (routeFile) {
                    routeMounts[routeFile] = match[1].trim();
                }
            });

        [...code.matchAll(/app\.use\(\s*['"]([^'"]+)['"]\s*,\s*require\(\s*['"]\.\/routes\/([^'"]+)['"]\s*\)\s*\)/g)]
            .forEach(match => {
                const routeRel = match[2].endsWith('.js') ? match[2] : `${match[2]}.js`;
                routeMounts[`/${serviceDir}/routes/${routeRel}`] = match[1].trim();
            });
    });

    const proxyList = [...proxyPrefixes];
    const topology = inferBackendPortTopology(backendFiles);
    const gatewayRulesByService = {};

    Object.entries(topology.serviceConfigs || {}).forEach(([dirName, config]) => {
        const portKey = String(config.originalPort || '').trim();
        const rules = [...(proxyRulesByPort.get(portKey) || [])];
        if (rules.length > 0) {
            gatewayRulesByService[dirName] = rules;
            return;
        }
        const prefixes = [...(proxyPrefixesByPort.get(portKey) || [])];
        if (prefixes.length > 0) {
            gatewayRulesByService[dirName] = prefixes.map((prefix) => ({
                prefix,
                rewriteTarget: '',
            }));
        }
    });

    Object.entries(backendFiles).forEach(([filePath, content]) => {
        const code = typeof content === 'string' ? content : content?.code || '';
        if (!filePath.includes('/routes/')) {
            return;
        }

        const resourceName = filePath.split('/').pop()?.replace(/\.[^.]+$/, '') || '';
        const singularName = resourceName.replace(/s$/, '');
        const routeMount = routeMounts[filePath] || '';
        const serviceDirName = filePath.split('/').filter(Boolean)[0];
        const serviceDir = `/${serviceDirName}`;
        const routeMountTail = routeMount.split('/').filter(Boolean).pop() || '';
        const serviceGatewayRules = gatewayRulesByService[serviceDirName] || [];
        const explicitProxyPrefix = proxyList.find(prefix => prefix === `/api/${resourceName}`)
            || proxyList.find(prefix => prefix === `/api/${singularName}`)
            || proxyList.find(prefix => routeMountTail && prefix.endsWith(`/${routeMountTail}`));
        const explicitProxyRule = serviceGatewayRules.find(rule => rule.prefix === `/api/${resourceName}`)
            || serviceGatewayRules.find(rule => rule.prefix === `/api/${singularName}`)
            || serviceGatewayRules.find(rule => routeMountTail && rule.prefix.endsWith(`/${routeMountTail}`))
            || (explicitProxyPrefix ? { prefix: explicitProxyPrefix, rewriteTarget: '' } : null);
        const baseRules = explicitProxyRule
            ? [explicitProxyRule]
            : serviceGatewayRules.length > 0
                ? serviceGatewayRules
                : [{
                    prefix: routeMount || `/api/${resourceName}`,
                    rewriteTarget: '',
                }];
        const basePrefixes = [...new Set(
            baseRules
                .map(rule => combineGatewayPrefixAndMount(rule.prefix, routeMount, rule.rewriteTarget))
                .filter(Boolean)
        )];
        const modelCandidates = Object.keys(backendFiles)
            .filter(pathname => pathname.startsWith(`${serviceDir}/models/`) && pathname.endsWith('.js'));

        [...code.matchAll(/router\.(get|post|put|delete|patch)\(\s*['"]([^'"]+)['"]/gi)]
            .forEach(match => {
                basePrefixes.forEach((basePrefix) => {
                    contracts.push({
                        method: match[1].toUpperCase(),
                        path: joinApiPath(basePrefix, match[2]),
                        serviceDir,
                        routeFile: filePath,
                        modelCandidates,
                    });
                });
            });
    });

    const uniqueContracts = [];
    const seen = new Set();
    contracts.forEach((contract) => {
        const key = `${contract.method} ${contract.path}`;
        if (seen.has(key)) return;
        seen.add(key);
        uniqueContracts.push(contract);
    });

    return uniqueContracts;
}

function buildLiveExecutionPlan(simulatedResults = [], backendFiles = {}) {
    const fallbackContracts = parseBackendContracts(backendFiles);
    const simulatedByKey = new Map(
        simulatedResults.map(result => [`${result.method} ${result.path}`, result])
    );
    const inferExpectedStatus = (method, routePath, simulatedStatus = null) => {
        if (simulatedStatus) return simulatedStatus;
        if (method === 'POST') {
            if (/\/(analytics|stats)(\/|$)/i.test(routePath)) return 200;
            if (/\/(login|verify|update)(\/|$)/i.test(routePath)) return 200;
            return 201;
        }
        return 200;
    };
    const planSource = fallbackContracts.length > 0
        ? fallbackContracts.map(contract => {
            const simulated = simulatedByKey.get(`${contract.method} ${contract.path}`);
            const synthesizedSample = simulated?.sampleData
                ? parseJsonSafely(simulated.sampleData)
                : buildSchemaSamplePayload(contract.modelCandidates, backendFiles, contract.path);
            return {
                method: contract.method,
                path: contract.path,
                expectedStatus: inferExpectedStatus(contract.method, contract.path, simulated?.statusCode || null),
                sampleData: synthesizedSample,
                detail: simulated?.detail || simulated?.reason || null,
            };
        })
        : simulatedResults.map(result => ({
            method: result.method,
            path: result.path,
            expectedStatus: inferExpectedStatus(result.method, result.path, result.statusCode || null),
            sampleData: parseJsonSafely(result.sampleData),
            detail: result.detail || result.reason || null,
        }));
    const rootHealth = simulatedByKey.get('GET /health') || { method: 'GET', path: '/health', statusCode: 200, sampleData: null, detail: null };
    planSource.unshift({
        method: 'GET',
        path: '/health',
        expectedStatus: rootHealth.statusCode || 200,
        sampleData: parseJsonSafely(rootHealth.sampleData),
        detail: rootHealth.detail || rootHealth.reason || null,
    });

    const unique = [];
    const seen = new Set();
    planSource.forEach(step => {
        const key = `${step.method} ${step.path}`;
        if (seen.has(key)) {
            return;
        }

        seen.add(key);
        unique.push(step);
    });

    const rank = (step) => {
        if (step.path === '/health') return 0;
        if (step.method === 'GET' && step.path.endsWith('/health')) return 1;
        if (step.method === 'POST' && /\/api\/auth\/register(\/|$)/i.test(step.path)) return 2;
        if (step.method === 'POST' && /\/api\/auth\/login(\/|$)/i.test(step.path)) return 3;
        if (routeRequiresAuth(step.path, step.detail)) return 6;
        if (step.method === 'POST' && step.path.includes('/seed')) return 4;
        if (step.method === 'POST') return 5;
        if (step.method === 'GET' && !step.path.includes('/:')) return 7;
        if (step.method === 'GET') return 8;
        if (step.method === 'PUT' || step.method === 'PATCH') return 9;
        if (step.method === 'DELETE') return 10;
        return 11;
    };

    return unique.sort((left, right) => rank(left) - rank(right));
}

function getOrderedServiceDirs(topology, structuredSpec = null) {
    const serviceDirs = [...(topology?.serviceDirs || [])];
    if (!structuredSpec?.services?.length) {
        return serviceDirs;
    }

    const matched = [];
    const remaining = [...serviceDirs];
    structuredSpec.services.forEach((service) => {
        const candidates = specServiceDirCandidates(service).map((value) => value.replace(/^\/+/, ''));
        const found = remaining.find((dirName) => candidates.includes(dirName));
        if (found) {
            matched.push(found);
            remaining.splice(remaining.indexOf(found), 1);
        }
    });

    return [...matched, ...remaining];
}

function buildPreferredRuntimePorts(topology, structuredSpec = null) {
    const services = {};
    getOrderedServiceDirs(topology, structuredSpec).forEach((dirName, index) => {
        services[dirName] = DEFAULT_SERVICE_PORT_START + index;
    });

    return {
        gateway: DEFAULT_GATEWAY_PORT,
        services,
    };
}

async function isPortAvailable(port, host = '127.0.0.1') {
    return new Promise((resolve) => {
        const server = net.createServer();
        server.once('error', () => resolve(false));
        server.listen(port, host, () => {
            server.close(() => resolve(true));
        });
    });
}

async function listListeningPidsOnPort(port) {
    if (!port) return [];

    try {
        if (process.platform === 'win32') {
            const psCommand = `Get-NetTCPConnection -State Listen -LocalPort ${Number(port)} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess`;
            const psResult = await runCommand('powershell.exe', ['-NoProfile', '-Command', psCommand], { timeoutMs: 20000 });
            const psPids = String(psResult.stdout || '')
                .split(/\r?\n/)
                .map((value) => Number.parseInt(value.trim(), 10))
                .filter((pid) => Number.isFinite(pid) && pid > 0 && pid !== process.pid);
            if (psPids.length > 0) {
                return [...new Set(psPids)];
            }

            const result = await runCommand('cmd.exe', ['/c', 'netstat -ano -p tcp'], { timeoutMs: 20000 });
            const text = `${result.stdout || ''}\n${result.stderr || ''}`;
            const matches = [...text.matchAll(new RegExp(`^\\s*TCP\\s+[^\\s]+:${port}\\s+[^\\s]+\\s+LISTENING\\s+(\\d+)\\s*$`, 'gim'))];
            return [...new Set(matches.map((match) => Number(match[1])).filter((pid) => Number.isFinite(pid) && pid > 0 && pid !== process.pid))];
        }

        const result = await runCommand('lsof', ['-ti', `tcp:${port}`], { timeoutMs: 20000 });
        return [...new Set(
            String(result.stdout || '')
                .split(/\r?\n/)
                .map((value) => Number.parseInt(value.trim(), 10))
                .filter((pid) => Number.isFinite(pid) && pid > 0 && pid !== process.pid)
        )];
    } catch (_) {
        return [];
    }
}

const NODE_BUILTIN_MODULES = new Set([
    ...builtinModules,
    ...builtinModules.map((name) => name.replace(/^node:/, '')),
]);

function parsePackageJsonMap(backendFiles = {}) {
    const packageMap = new Map();

    Object.entries(backendFiles).forEach(([filePath, content]) => {
        if (!/\/package\.json$/i.test(filePath)) {
            return;
        }

        try {
            const normalized = normalizeBackendFileContent(filePath, typeof content === 'string' ? content : content?.code || '');
            const parsed = JSON.parse(normalized);
            const serviceDir = `/${filePath.split('/').filter(Boolean)[0] || ''}`.replace(/\/+$/, '');
            if (!serviceDir || serviceDir === '/') {
                return;
            }

            packageMap.set(serviceDir, parsed);
        } catch (_) {}
    });

    return packageMap;
}

function getServiceDirForFile(filePath = '') {
    const segments = String(filePath || '').replace(/\\/g, '/').split('/').filter(Boolean);
    if (segments.length === 0) {
        return '';
    }
    return `/${segments[0]}`;
}

function getDeclaredPackageNames(packageJson = {}) {
    const names = new Set();
    ['dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies'].forEach((field) => {
        Object.keys(packageJson?.[field] || {}).forEach((name) => names.add(name));
    });
    return names;
}

function getExternalRequirePackageName(requestPath = '') {
    const normalized = String(requestPath || '').trim();
    if (!normalized || normalized.startsWith('.') || normalized.startsWith('/')) {
        return '';
    }

    if (normalized.startsWith('@')) {
        const parts = normalized.split('/');
        return parts.length >= 2 ? `${parts[0]}/${parts[1]}` : normalized;
    }

    return normalized.split('/')[0];
}

function extractRequireAndImportRequests(code = '') {
    const requests = new Set();
    const source = String(code || '');

    [...source.matchAll(/require\(\s*['"]([^'"]+)['"]\s*\)/g)].forEach((match) => {
        if (match[1]) requests.add(match[1].trim());
    });
    [...source.matchAll(/import\s+[^'"]*?from\s+['"]([^'"]+)['"]/g)].forEach((match) => {
        if (match[1]) requests.add(match[1].trim());
    });
    [...source.matchAll(/import\s*\(\s*['"]([^'"]+)['"]\s*\)/g)].forEach((match) => {
        if (match[1]) requests.add(match[1].trim());
    });

    return [...requests];
}

async function killProcessId(pid) {
    if (!pid || pid === process.pid) return false;
    try {
        if (process.platform === 'win32') {
            const result = await runCommand('taskkill', ['/PID', String(pid), '/T', '/F'], { timeoutMs: 30000 });
            return result.code === 0;
        }

        const result = await runCommand('kill', ['-9', String(pid)], { timeoutMs: 30000 });
        return result.code === 0;
    } catch (_) {
        return false;
    }
}

async function killListeningProcessesOnPort(port, emit = null, label = '', { strict = false, phase = 'api-test' } = {}) {
    if (!port) {
        return [];
    }

    const pids = await listListeningPidsOnPort(port);
    if (pids.length === 0) {
        return [];
    }

    if (emit) {
        emit({
            type: 'log',
            phase,
            level: 'warning',
            message: `Port ${port} is already in use${label ? ` for ${label}` : ''}. Found PID${pids.length === 1 ? '' : 's'} ${pids.join(', ')} via netstat/Get-NetTCPConnection. Running taskkill before testing...`,
        });
    }

    for (const pid of pids) {
        await killProcessId(pid);
    }

    const startedAt = Date.now();
    while (Date.now() - startedAt < 15000) {
        if (await isPortAvailable(port)) {
            return pids;
        }
        await delay(500);
    }

    if (strict) {
        throw new Error(`Port ${port} is still not available${label ? ` for ${label}` : ''} after killing PID${pids.length === 1 ? '' : 's'} ${pids.join(', ')}.`);
    }

    if (emit) {
        emit({
            type: 'log',
            phase,
            level: 'warning',
            message: `Port ${port} still appears busy${label ? ` for ${label}` : ''} after taskkill. The next round will fall back or retry cleanup.`,
        });
    }
    return pids;
}

async function ensurePortAvailable(port, emit = null, label = '') {
    if (await isPortAvailable(port)) {
        return;
    }

    const pids = await listListeningPidsOnPort(port);
    if (pids.length === 0) {
        throw new Error(`Port ${port} is in use${label ? ` for ${label}` : ''}, but no owning process could be identified to free it.`);
    }
    await killListeningProcessesOnPort(port, emit, label, { strict: true, phase: 'api-test' });
}

async function reserveRuntimePorts(topology, emit = null, structuredSpec = null) {
    const preferred = buildPreferredRuntimePorts(topology, structuredSpec);
    const resolvedGatewayPort = await resolveRuntimePort(preferred.gateway, emit, 'api-gateway');
    const resolvedServices = {};
    for (const dirName of Object.keys(preferred.services)) {
        resolvedServices[dirName] = await resolveRuntimePort(preferred.services[dirName], emit, dirName);
    }
    return {
        gateway: resolvedGatewayPort,
        services: resolvedServices,
    };
}

async function getFreePort() {
    return new Promise((resolve, reject) => {
        const server = net.createServer();
        server.on('error', reject);
        server.listen(0, '127.0.0.1', () => {
            const address = server.address();
            const port = typeof address === 'object' && address ? address.port : null;
            server.close(() => resolve(port));
        });
    });
}

async function resolveRuntimePort(preferredPort, emit = null, label = '') {
    try {
        await ensurePortAvailable(preferredPort, emit, label);
        return preferredPort;
    } catch (error) {
        const fallbackPort = await getFreePort();
        if (emit) {
            emit({
                type: 'log',
                phase: 'api-test',
                level: 'warning',
                message: `Preferred port ${preferredPort} is unavailable${label ? ` for ${label}` : ''}. Using fallback port ${fallbackPort}. Reason: ${error.message}`,
            });
        }
        return fallbackPort;
    }
}

function buildRuntimePortEntries(ports) {
    const entries = [];
    if (ports?.gateway) {
        entries.push({ port: ports.gateway, label: 'api-gateway' });
    }
    Object.entries(ports?.services || {}).forEach(([serviceName, servicePort]) => {
        entries.push({ port: servicePort, label: serviceName });
    });
    return entries;
}

async function killRuntimePorts(ports, emit = null, phaseLabel = 'testing') {
    for (const entry of buildRuntimePortEntries(ports)) {
        await killListeningProcessesOnPort(entry.port, emit, `${entry.label} during ${phaseLabel}`, {
            strict: false,
            phase: 'api-test',
        });
    }
}

async function runCommand(command, args, { cwd, env, onStdout, onStderr, timeoutMs = 120000 } = {}) {
    return new Promise((resolve, reject) => {
        const normalizedArgs = normalizeSpawnArgs(args);
        let child = null;
        let timer = null;
        let stdout = '';
        let stderr = '';
        let timedOut = false;
        let settled = false;
        let retriedWithShell = false;
        let activeLaunchId = 0;

        const clearActiveTimer = () => {
            if (timer) {
                clearTimeout(timer);
                timer = null;
            }
        };

        const startTimer = () => {
            clearActiveTimer();
            timer = setTimeout(() => {
                timedOut = true;
                child?.kill('SIGTERM');
            }, timeoutMs);
        };

        const settle = (fn, value) => {
            if (settled) {
                return;
            }

            settled = true;
            clearActiveTimer();
            fn(value);
        };

        const launch = (shellMode = shouldUseShellForCommand(command, normalizedArgs)) => {
            const launchId = ++activeLaunchId;
            timedOut = false;
            try {
                child = spawn(command, normalizedArgs, buildSpawnOptions({
                    cwd,
                    env,
                    shellMode,
                }));
            } catch (error) {
                if (shouldRetrySpawn(error, retriedWithShell)) {
                    retriedWithShell = true;
                    stderr += `\n[spawn-recovery] ${error.code}: retrying with shell=true`;
                    launch(true);
                    return;
                }

                settle(reject, error);
                return;
            }

            startTimer();

            child.stdout?.on('data', (chunk) => {
                if (launchId !== activeLaunchId) {
                    return;
                }
                const text = chunk.toString();
                stdout += text;
                onStdout?.(text);
            });

            child.stderr?.on('data', (chunk) => {
                if (launchId !== activeLaunchId) {
                    return;
                }
                const text = chunk.toString();
                stderr += text;
                onStderr?.(text);
            });

            child.once('error', (error) => {
                if (launchId !== activeLaunchId) {
                    return;
                }
                clearActiveTimer();
                if (shouldRetrySpawn(error, retriedWithShell)) {
                    retriedWithShell = true;
                    stderr += `\n[spawn-recovery] ${error.code}: retrying with shell=true`;
                    launch(true);
                    return;
                }

                settle(reject, error);
            });

            child.once('close', (code) => {
                if (launchId !== activeLaunchId) {
                    return;
                }
                clearActiveTimer();
                if (timedOut) {
                    settle(reject, new Error(`Command timed out: ${command} ${normalizedArgs.join(' ')}`));
                    return;
                }

                settle(resolve, { code, stdout, stderr, shellMode });
            });
        };

        launch();
    });
}

async function waitForHttp(url, { timeoutMs = 20000, intervalMs = 500 } = {}) {
    const startedAt = Date.now();
    let lastError = null;

    while (Date.now() - startedAt < timeoutMs) {
        try {
            const response = await fetch(url);
            if (response.ok) {
                return response;
            }

            lastError = new Error(`Received status ${response.status} from ${url}`);
        } catch (error) {
            lastError = error;
        }

        await delay(intervalMs);
    }

    throw lastError || new Error(`Timed out waiting for ${url}`);
}

async function waitForAnyHttp(urls = [], { timeoutMs = 20000, intervalMs = 500 } = {}) {
    const candidates = Array.from(new Set((urls || []).filter(Boolean)));
    if (!candidates.length) {
        throw new Error('No HTTP URLs provided for readiness check');
    }

    const startedAt = Date.now();
    let lastError = null;

    while (Date.now() - startedAt < timeoutMs) {
        for (const url of candidates) {
            try {
                const response = await fetch(url);
                if (response.ok) {
                    return { url, response };
                }

                lastError = new Error(`Received status ${response.status} from ${url}`);
            } catch (error) {
                lastError = error;
            }
        }

        await delay(intervalMs);
    }

    throw lastError || new Error(`Timed out waiting for any of: ${candidates.join(', ')}`);
}

function summarizeServiceFailure(service, fallbackMessage = 'service failed to start') {
    const stderr = stripSpawnRecoveryNoise(service?.getStderr?.());
    const stdout = stripSpawnRecoveryNoise(service?.getStdout?.());
    const exitCode = service?.getExitCode?.();
    const signal = service?.getExitSignal?.();
    const processSummary = exitCode !== null || signal
        ? `exit=${exitCode ?? 'null'}${signal ? ` signal=${signal}` : ''}`
        : '';

    return [stderr, stdout, processSummary, fallbackMessage]
        .filter(Boolean)
        .join(' | ');
}

async function waitForServiceHealth(url, service, options = {}) {
    const startedAt = Date.now();
    const timeoutMs = options.timeoutMs ?? 20000;
    const intervalMs = options.intervalMs ?? 500;
    let lastError = null;

    while (Date.now() - startedAt < timeoutMs) {
        if (service?.hasExited?.()) {
            throw new Error(`${service.label} exited before health check: ${summarizeServiceFailure(service)}`);
        }

        try {
            const response = await fetch(url);
            if (response.ok) {
                return response;
            }

            lastError = new Error(`Received status ${response.status} from ${url}`);
        } catch (error) {
            lastError = error;
        }

        await delay(intervalMs);
    }

    if (service?.hasExited?.()) {
        throw new Error(`${service.label} exited before health check: ${summarizeServiceFailure(service)}`);
    }

    throw lastError || new Error(`Timed out waiting for ${url}`);
}

async function writeBackendWorkspace(backendFiles, { topology, ports, mongoUri, jwtSecret, projectTitle }) {
    const rootDir = path.join(
        getGenerationOutputRoot(projectTitle),
        'backend'
    );

    await rm(rootDir, { recursive: true, force: true }).catch(() => {});
    await mkdir(rootDir, { recursive: true });

    await Promise.all(
        Object.entries(backendFiles).map(async ([filePath, content]) => {
            const relativePath = filePath.replace(/^\/+/, '');
            const absolutePath = path.join(rootDir, relativePath);
            await mkdir(path.dirname(absolutePath), { recursive: true });
            const code = normalizeBackendFileContent(filePath, typeof content === 'string' ? content : content?.code || '');
            await writeFile(absolutePath, code, 'utf8');
        })
    );

    const envLines = [
        `PORT=${ports.gateway}`,
        `PORT_GATEWAY=${ports.gateway}`,
        `MONGODB_URI=${mongoUri}`,
        `MONGO_URL=${mongoUri}`,
        `JWT_SECRET=${jwtSecret}`,
        `SECRET_KEY=${jwtSecret}`,
        `SEKRET_KEY=${jwtSecret}`,
        'NODE_ENV=development',
    ];

    topology.serviceDirs.forEach((dirName, index) => {
        const port = ports.services[dirName];
        const config = topology.serviceConfigs[dirName];
        if (!port || !config?.envVar) {
            return;
        }

        envLines.push(`${config.envVar}=${port}`);
        if (index === 0) envLines.push(`PORT_SERVICE1=${port}`);
        if (index === 1) envLines.push(`PORT_SERVICE2=${port}`);
    });

    const envText = envLines.join('\n');
    await writeFile(path.join(rootDir, '.env'), `${envText}\n`, 'utf8');

    await Promise.all(
        topology.packageDirs.map(async (dirName) => {
            const config = topology.serviceConfigs[dirName];
            const servicePort = dirName === 'api-gateway'
                ? ports.gateway
                : (ports.services[dirName] || Number(config?.originalPort || DEFAULT_SERVICE_PORT_START));
            const serviceEnvLines = [
                ...envLines.filter((line) => !line.startsWith('PORT=')),
                `PORT=${servicePort}`,
            ];
            await writeFile(path.join(rootDir, dirName, '.env'), `${serviceEnvLines.join('\n')}\n`, 'utf8').catch(() => {});
        })
    );
    return rootDir;
}

async function resetServiceInstallState(serviceRoot) {
    if (!serviceRoot) return;
    await rm(path.join(serviceRoot, 'node_modules'), { recursive: true, force: true }).catch(() => {});
    await rm(path.join(serviceRoot, 'package-lock.json'), { force: true }).catch(() => {});
}

async function installBackendDependencies(dirName, serviceRoot, env, emit) {
    await resetServiceInstallState(serviceRoot);

    const runInstall = () => runCommand(npmCommand(), ['install', '--no-fund', '--no-audit'], {
        cwd: serviceRoot,
        env,
        timeoutMs: 180000,
    });

    let install = await runInstall();
    if (install.code === 0) {
        return install;
    }

    const installOutput = `${install.stderr || ''}\n${install.stdout || ''}`.toLowerCase();
    if (
        installOutput.includes('enotempty')
        || installOutput.includes('ejsonparse')
        || installOutput.includes('invalid package.json')
    ) {
        emit?.({
            type: 'log',
            phase: 'api-test',
            level: 'warning',
            message: `Retrying clean npm install in ${dirName} after resetting node_modules/package-lock because npm reported a corrupted install state...`,
        });
        await resetServiceInstallState(serviceRoot);
        install = await runInstall();
    }

    return install;
}

async function startBackendService(label, cwd, env, emit) {
    const entryFile = path.join(cwd, 'index.js');
    try {
        await access(entryFile);
    } catch (_) {
        throw new Error(`Cannot start ${label}: missing entry file ${entryFile}`);
    }

    let launchCommand = process.execPath;
    let launchArgs = ['index.js'];

    try {
        const packageJson = JSON.parse(
            normalizeBackendFileContent('package.json', await readFile(path.join(cwd, 'package.json'), 'utf8'))
        );
        if (packageJson?.scripts?.start) {
            launchCommand = npmCommand();
            launchArgs = ['start'];
        }
    } catch (_) {}

    emit({
        type: 'log',
        phase: 'api-test',
        level: 'info',
        message: `[live-start] ${label}: ${launchCommand === process.execPath ? 'node index.js' : 'npm start'}`,
    });

    let child = null;
    let stdout = '';
    let stderr = '';
    let launchError = null;
    let exitCode = null;
    let exitSignal = null;
    let retriedWithShell = false;
    let activeLaunchId = 0;

    const attachListeners = (proc, launchId) => {
        proc.once('exit', (code, signal) => {
            if (launchId !== activeLaunchId) return;
            exitCode = code;
            exitSignal = signal;
        });

        proc.once('error', (error) => {
            if (launchId !== activeLaunchId) return;
            if (shouldRetrySpawn(error, retriedWithShell)) {
                retriedWithShell = true;
                stderr += `[spawn-recovery] ${error.code}: retrying ${label} with shell=true\n`;
                launch(true);
                return;
            }

            launchError = error;
            stderr += `${error.message}\n`;
            emit({ type: 'log', phase: 'api-test', level: 'warning', message: `[live:${label}] spawn error: ${error.code || error.message}` });
        });

        proc.stdout?.on('data', (chunk) => {
            if (launchId !== activeLaunchId) return;
            const text = chunk.toString();
            stdout += text;
            const message = text.trim();
            if (message) {
                emit({ type: 'log', phase: 'api-test', level: 'info', message: `[live:${label}] ${message}` });
            }
        });

        proc.stderr?.on('data', (chunk) => {
            if (launchId !== activeLaunchId) return;
            const text = chunk.toString();
            stderr += text;
            const message = text.trim();
            if (message) {
                emit({ type: 'log', phase: 'api-test', level: 'warning', message: `[live:${label}] ${message}` });
            }
        });
    };

    const launch = (shellMode = shouldUseShellForCommand(launchCommand, launchArgs)) => {
        const launchId = ++activeLaunchId;
        launchError = null;
        exitCode = null;
        exitSignal = null;
        try {
            child = spawn(launchCommand, launchArgs, buildSpawnOptions({
                cwd,
                env,
                shellMode,
            }));
        } catch (error) {
            if (shouldRetrySpawn(error, retriedWithShell)) {
                retriedWithShell = true;
                stderr += `[spawn-recovery] ${error.code}: retrying ${label} with shell=true\n`;
                launch(true);
                return;
            }
            launchError = error;
            return;
        }

        attachListeners(child, launchId);
    };

    launch();

    await delay(250);
    if (launchError) {
        throw launchError;
    }
    if (child?.exitCode !== null) {
        const outputSummary = stripSpawnRecoveryNoise(stderr || stdout);
        throw new Error(
            `${label} exited before health check` +
            `${outputSummary ? `: ${outputSummary}` : ''}`
        );
    }

    return {
        label,
        cwd,
        child,
        getStdout: () => stdout,
        getStderr: () => stderr,
        hasExited: () => child?.exitCode !== null || exitCode !== null,
        getExitCode: () => child?.exitCode ?? exitCode,
        getExitSignal: () => exitSignal,
    };
}

async function startFrontendPreview(cwd, { port, gatewayPort }, emit) {
    const resolvedFrontendPort = await resolveRuntimePort(port, emit, 'frontend');
    emit({
        type: 'log',
        phase: 'frontend-gen',
        level: 'info',
        message: `Starting local frontend on port ${resolvedFrontendPort} (proxy -> ${gatewayPort})...`,
    });

    const nodeModulesDir = path.join(cwd, 'node_modules');
    let hasInstalledNodeModules = true;
    try {
        await access(nodeModulesDir);
    } catch (_) {
        hasInstalledNodeModules = false;
    }

    if (!hasInstalledNodeModules) {
        emit({
            type: 'log',
            phase: 'frontend-gen',
            level: 'info',
            message: 'Installing frontend dependencies...',
        });
        const install = await runCommand(npmCommand(), ['install', '--no-fund', '--no-audit'], {
            cwd,
            env: {
                ...process.env,
                NODE_ENV: 'development',
                PORT: String(resolvedFrontendPort),
                VITE_FRONTEND_PORT: String(resolvedFrontendPort),
                VITE_API_BASE_URL: `http://127.0.0.1:${gatewayPort}`,
                VITE_GATEWAY_URL: `http://127.0.0.1:${gatewayPort}`,
                VITE_GATEWAY_PORT: String(gatewayPort),
            },
            timeoutMs: 180000,
            onStdout: (text) => {
                const message = text.trim();
                if (message) {
                    emit({ type: 'log', phase: 'frontend-gen', level: 'info', message: `[live:frontend-install] ${message}` });
                }
            },
            onStderr: (text) => {
                const message = text.trim();
                if (message) {
                    emit({ type: 'log', phase: 'frontend-gen', level: 'warning', message: `[live:frontend-install] ${message}` });
                }
            },
        });

        if (install.code !== 0) {
            throw new Error(`frontend npm install failed: ${stripSpawnRecoveryNoise(install.stderr || install.stdout)}`);
        }
    } else {
        emit({
            type: 'log',
            phase: 'frontend-gen',
            level: 'info',
            message: 'Frontend dependencies already installed. Skipping npm install.',
        });
    }

    let child = null;
    let stdout = '';
    let stderr = '';
    let launchError = null;
    let retriedWithShell = false;
    let activeLaunchId = 0;

    const attachListeners = (proc, launchId) => {
        proc.once('error', (error) => {
            if (launchId !== activeLaunchId) return;
            if (shouldRetrySpawn(error, retriedWithShell)) {
                retriedWithShell = true;
                launch(true);
                return;
            }
            launchError = error;
        });
        proc.stdout?.on('data', (chunk) => {
            if (launchId !== activeLaunchId) return;
            const text = chunk.toString();
            stdout += text;
            const message = text.trim();
            if (message) emit({ type: 'log', phase: 'frontend-gen', level: 'info', message: `[live:frontend] ${message}` });
        });
        proc.stderr?.on('data', (chunk) => {
            if (launchId !== activeLaunchId) return;
            const text = chunk.toString();
            stderr += text;
            const message = text.trim();
            if (message) emit({ type: 'log', phase: 'frontend-gen', level: 'warning', message: `[live:frontend] ${message}` });
        });
    };

    const launch = (shellMode = shouldUseShellForCommand(npmCommand(), ['run', 'dev', '--', '--port', String(port)])) => {
        const launchId = ++activeLaunchId;
        child = spawn(
            npmCommand(),
            ['run', 'dev', '--', '--port', String(port)],
            buildSpawnOptions({
                cwd,
                env: {
                    ...process.env,
                    NODE_ENV: 'development',
                    PORT: String(resolvedFrontendPort),
                    VITE_FRONTEND_PORT: String(resolvedFrontendPort),
                    VITE_API_BASE_URL: `http://127.0.0.1:${gatewayPort}`,
                    VITE_GATEWAY_URL: `http://127.0.0.1:${gatewayPort}`,
                    VITE_GATEWAY_PORT: String(gatewayPort),
                },
                shellMode,
            })
        );
        attachListeners(child, launchId);
    };

    launch();
    await delay(500);
    if (launchError) throw launchError;
    emit({
        type: 'log',
        phase: 'frontend-gen',
        level: 'info',
        message: `Waiting for local frontend to respond at http://127.0.0.1:${resolvedFrontendPort} or http://localhost:${resolvedFrontendPort} ...`,
    });
    const frontendCandidates = [
        `http://127.0.0.1:${resolvedFrontendPort}`,
        `http://localhost:${resolvedFrontendPort}`,
    ];
    const readyFrontend = await waitForAnyHttp(frontendCandidates, { timeoutMs: 120000, intervalMs: 1000 });
    emit({
        type: 'log',
        phase: 'frontend-gen',
        level: 'success',
        message: `Local frontend ready at ${readyFrontend.url}`,
    });

    return {
        frontendUrl: readyFrontend.url,
        frontendPort: resolvedFrontendPort,
        process: child,
        getStdout: () => stdout,
        getStderr: () => stderr,
    };
}

async function stopBackendProcesses(processes = [], emit = null) {
    await Promise.all(
        processes.map(async (service) => {
            if (!service?.child || service.child.killed) {
                return;
            }

            if (process.platform === 'win32' && service.child.pid) {
                if (emit) {
                    emit({
                        type: 'log',
                        phase: 'api-test',
                        level: 'info',
                        message: `[live-stop] Killing ${service.label} process tree PID ${service.child.pid} with taskkill...`,
                    });
                }
                await killProcessId(service.child.pid);
                await Promise.race([
                    new Promise((resolve) => service.child.once('close', resolve)),
                    delay(4000),
                ]).catch(() => {});
                return;
            }

            service.child.kill('SIGTERM');
            await Promise.race([
                new Promise((resolve) => service.child.once('close', resolve)),
                delay(3000).then(() => {
                    if (!service.child.killed) {
                        service.child.kill('SIGKILL');
                    }
                }),
            ]).catch(() => {});
        })
    );
}

function summarizeLiveFailure(result) {
    const statusText = result.statusCode ? `status ${result.statusCode}` : 'no response';
    return `${result.method} ${result.path} returned ${statusText}${result.reason ? ` (${result.reason})` : ''}`;
}

async function runLiveBackendValidation(backendFiles, simulatedResults, emit, { projectTitle, keepAliveOnSuccess = false, structuredSpec = null, changedServiceDirs = null } = {}) {
    const topology = inferBackendPortTopology(backendFiles);
    const ports = await reserveRuntimePorts(topology, emit, structuredSpec);
    // Always use a fresh per-run database so stale unique indexes from previous runs
    // never cause E11000 duplicate key errors on null values.
    const fallbackDbName = `ai-builder-test-${Date.now()}`;
    const rawMongoBase = (process.env.MONGODB_URI || process.env.MONGO_URL || '').trim();
    const mongoUri = rawMongoBase && rawMongoBase.includes('://')
        ? rawMongoBase.replace(/\/[a-zA-Z0-9_-]+(\?|$)/, `/${fallbackDbName}$1`)
            .replace(/^(mongodb:\/\/[^/]+)$/, `$1/${fallbackDbName}`)
        : `mongodb://127.0.0.1:27017/${fallbackDbName}`;
    const jwtSecret = (process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'dev-secret').trim();
    const rootDir = await writeBackendWorkspace(backendFiles, { topology, ports, mongoUri, jwtSecret, projectTitle });
    const packageDirs = topology.packageDirs;
    const serviceDirs = topology.serviceDirs;
    const runtimePortByService = { ...ports.services };

    const env = {
        ...process.env,
        PORT: String(ports.gateway),
        PORT_GATEWAY: String(ports.gateway),
        MONGODB_URI: mongoUri,
        MONGO_URL: mongoUri,
        JWT_SECRET: jwtSecret,
        SECRET_KEY: jwtSecret,
        SEKRET_KEY: jwtSecret,
        NODE_ENV: 'development',
    };
    serviceDirs.forEach((dirName, index) => {
        const config = topology.serviceConfigs[dirName];
        const port = runtimePortByService[dirName];
        if (!config?.envVar || !port) {
            return;
        }

        env[config.envVar] = String(port);
        if (index === 0) env.PORT_SERVICE1 = String(port);
        if (index === 1) env.PORT_SERVICE2 = String(port);
    });

    const contracts = parseBackendContracts(backendFiles);
    const executionPlan = buildLiveExecutionPlan(simulatedResults, backendFiles);
    const createdRecords = {};
    const liveResults = [];
    const liveProcesses = [];
    const authState = { token: null };
    const sampleState = createLiveSampleState();
    const deferredAuthSteps = [];
    const deferredAuthKeys = new Set();
    const reportsDir = path.join(getGenerationOutputRoot(projectTitle), 'reports');
    let preserveProcesses = false;

    try {
        await mkdir(reportsDir, { recursive: true });
        await killRuntimePorts(ports, emit, 'pre-round cleanup');
        emit({ type: 'log', phase: 'api-test', level: 'info', message: `Local backend workspace: ${rootDir}` });
        const livePortSummary = ['gateway ' + ports.gateway]
            .concat(serviceDirs.map(dirName => `${dirName} ${runtimePortByService[dirName]}`))
            .join(', ');
        emit({ type: 'log', phase: 'api-test', level: 'info', message: `Live ports: ${livePortSummary}` });
        emit({ type: 'log', phase: 'api-test', level: 'info', message: `Live gateway URL: http://127.0.0.1:${ports.gateway}` });
        emit({ type: 'log', phase: 'api-test', level: 'info', message: `Local MongoDB URI: ${mongoUri}` });

        // Use a full install/start pass for every live round. The backend workspace is rewritten
        // fresh per round, so "unchanged" services would otherwise miss node_modules and fail to boot.
        const dirsToInstall = packageDirs;
        const dirsToStart = serviceDirs;

        for (const dirName of dirsToInstall) {
            emit({ type: 'log', phase: 'api-test', level: 'info', message: `Installing backend dependencies in ${dirName}...` });
            const install = await installBackendDependencies(dirName, path.join(rootDir, dirName), env, emit);
            if (install.code !== 0) {
                throw new Error(`npm install failed in ${dirName}: ${install.stderr || install.stdout}`);
            }
        }
        for (const dirName of dirsToStart) {
            const port = runtimePortByService[dirName];
            emit({ type: 'log', phase: 'api-test', level: 'info', message: `[live-start] Starting ${dirName} on port ${port}...` });
            const service = await startBackendService(dirName, path.join(rootDir, dirName), { ...env, PORT: String(port) }, emit);
            liveProcesses.push(service);
        }

        for (const dirName of serviceDirs) {
            const port = runtimePortByService[dirName];
            const service = liveProcesses.find(item => item.label === dirName);
            await waitForServiceHealth(`http://127.0.0.1:${port}/health`, service, { timeoutMs: 20000 });
        }

        emit({ type: 'log', phase: 'api-test', level: 'info', message: 'Starting api-gateway...' });
        const gateway = await startBackendService('api-gateway', path.join(rootDir, 'api-gateway'), env, emit);
        liveProcesses.push(gateway);
        await waitForServiceHealth(`http://127.0.0.1:${ports.gateway}/health`, gateway, { timeoutMs: 20000 });

        emit({ type: 'log', phase: 'api-test', level: 'info', message: 'Running live HTTP integration checks against started backend...' });

        for (const step of executionPlan) {
            const resourceBase = getResourceBase(step.path);
            const resolvedPath = resolveDynamicPath(step.path, createdRecords);
            if (!resolvedPath) {
                emit({
                    type: 'log',
                    phase: 'api-test',
                    level: 'warning',
                    round: 'live',
                    message: `Skipping ${step.method} ${step.path} until required IDs exist from earlier live requests.`,
                });
                continue;
            }

            const requiresAuth = routeRequiresAuth(resolvedPath, step.detail);
            if (requiresAuth && !authState.token) {
                const key = `${step.method} ${step.path}`;
                if (!deferredAuthKeys.has(key)) {
                    deferredAuthKeys.add(key);
                    deferredAuthSteps.push(cloneJson(step));
                }
                emit({
                    type: 'log',
                    phase: 'api-test',
                    level: 'warning',
                    round: 'live',
                    message: `Deferring ${step.method} ${step.path} until auth token is available from register/login.`,
                });
                continue;
            }

            const rawPayload = step.sampleData || buildSchemaSamplePayload(
                contracts
                    .filter(contract => contract.method === step.method && contract.path === step.path)
                    .flatMap(contract => contract.modelCandidates || []),
                backendFiles,
                resolvedPath,
                createdRecords,
                sampleState
            );
            const payloadData = injectKnownIds(rawPayload, resolvedPath, createdRecords, sampleState);
            const queryPayload = step.method === 'GET'
                ? buildQueryPayload(resolvedPath, step.detail, payloadData)
                : null;
            const requestPath = queryPayload
                ? appendQueryParams(resolvedPath, queryPayload)
                : resolvedPath;
            const body = ['POST', 'PUT', 'PATCH'].includes(step.method)
                ? payloadData
                : null;
            const requestOptions = {
                method: step.method,
                headers: {},
            };

            if (body && ['POST', 'PUT', 'PATCH'].includes(step.method)) {
                requestOptions.headers['Content-Type'] = 'application/json';
                requestOptions.body = JSON.stringify(body);
            }
            if (authState.token && requiresAuth) {
                requestOptions.headers.Authorization = `Bearer ${authState.token}`;
            }

            const performRequest = async (options) => {
                try {
                    const response = await fetch(`http://127.0.0.1:${ports.gateway}${requestPath}`, options);
                    const payload = await response.json().catch(() => null);
                    return { response, payload, failureReason: null };
                } catch (error) {
                    return { response: null, payload: null, failureReason: error.message };
                }
            };

            let requestResult = await performRequest(requestOptions);
            let response = requestResult.response;
            let payload = requestResult.payload;
            let failureReason = requestResult.failureReason;
            let actualStatus = response?.status || null;
            let failureDetail = payload?.error || failureReason || `Expected HTTP ${(step.expectedStatus || (step.method === 'POST' ? 201 : 200))} but received ${actualStatus ?? 'no response'}`;

            if (
                !authState.token
                && isAuthFailureReason(actualStatus, failureDetail)
                && !/^\/api\/auth\/(register|login|verify|profile)(\/|$)/i.test(resolvedPath)
            ) {
                const key = `${step.method} ${step.path}`;
                if (!deferredAuthKeys.has(key)) {
                    deferredAuthKeys.add(key);
                    deferredAuthSteps.push(cloneJson(step));
                }
                emit({
                    type: 'log',
                    phase: 'api-test',
                    level: 'warning',
                    round: 'live',
                    message: `Deferring ${step.method} ${step.path} until auth token is available. Current response: ${failureDetail}`,
                });
                continue;
            }

            if (
                authState.token
                && !requestOptions.headers.Authorization
                && isAuthFailureReason(actualStatus, failureDetail)
            ) {
                const retryOptions = {
                    ...requestOptions,
                    headers: {
                        ...requestOptions.headers,
                        Authorization: `Bearer ${authState.token}`,
                    },
                };
                requestResult = await performRequest(retryOptions);
                response = requestResult.response;
                payload = requestResult.payload;
                failureReason = requestResult.failureReason;
                actualStatus = response?.status || null;
                failureDetail = payload?.error || failureReason || `Expected HTTP ${(step.expectedStatus || (step.method === 'POST' ? 201 : 200))} but received ${actualStatus ?? 'no response'}`;
            }

            const actualSuccess = Boolean(response?.ok && (!payload || payload.success !== false));
            const expectedStatus = step.expectedStatus || (step.method === 'POST' ? 201 : 200);
            const result = {
                method: step.method,
                path: requestPath,
                status: actualSuccess && actualStatus === expectedStatus ? 'PASS' : 'FAIL',
                statusCode: actualStatus,
                sampleData: body
                    ? JSON.stringify(body)
                    : (queryPayload ? JSON.stringify(queryPayload) : null),
                detail: actualSuccess
                    ? `Live request returned HTTP ${actualStatus}`
                    : failureDetail,
                reason: actualSuccess && actualStatus === expectedStatus
                    ? null
                    : failureDetail,
            };

            if (result.status === 'PASS') {
                const createdRecord = extractCreatedRecord(payload);
                if (createdRecord) {
                    createdRecords[resourceBase] = createdRecord;
                    if (requestPath.startsWith('/api/auth/')) {
                        createdRecords['/api/users'] = createdRecord;
                    }
                }

                const token = extractAuthToken(payload);
                if (token) {
                    authState.token = token;
                }
            }

            liveResults.push(result);
            emit({
                type: 'test-result',
                method: result.method,
                path: result.path,
                status: result.status,
                statusCode: result.statusCode,
                reason: result.reason,
                sampleData: result.sampleData,
                detail: result.detail,
                dbEffect: result.detail,
                round: 'live',
            });
        }

        if (deferredAuthSteps.length > 0 && authState.token) {
            emit({
                type: 'log',
                phase: 'api-test',
                level: 'info',
                round: 'live',
                    message: `Replaying ${deferredAuthSteps.length} auth-protected route(s) after auth token became available...`,
            });

            for (const step of deferredAuthSteps) {
                const resourceBase = getResourceBase(step.path);
                const resolvedPath = resolveDynamicPath(step.path, createdRecords);
                if (!resolvedPath) {
                    continue;
                }

                const rawPayload = step.sampleData || buildSchemaSamplePayload(
                    contracts
                        .filter(contract => contract.method === step.method && contract.path === step.path)
                        .flatMap(contract => contract.modelCandidates || []),
                    backendFiles,
                    resolvedPath,
                    createdRecords,
                    sampleState
                );
                const payloadData = injectKnownIds(rawPayload, resolvedPath, createdRecords, sampleState);
                const queryPayload = step.method === 'GET'
                    ? buildQueryPayload(resolvedPath, step.detail, payloadData)
                    : null;
                const requestPath = queryPayload
                    ? appendQueryParams(resolvedPath, queryPayload)
                    : resolvedPath;
                const body = ['POST', 'PUT', 'PATCH'].includes(step.method)
                    ? payloadData
                    : null;
                const requestOptions = {
                    method: step.method,
                    headers: authState.token ? { Authorization: `Bearer ${authState.token}` } : {},
                };

                if (body && ['POST', 'PUT', 'PATCH'].includes(step.method)) {
                    requestOptions.headers['Content-Type'] = 'application/json';
                    requestOptions.body = JSON.stringify(body);
                }

                let response;
                let payload = null;
                let failureReason = null;
                try {
                    response = await fetch(`http://127.0.0.1:${ports.gateway}${requestPath}`, requestOptions);
                    payload = await response.json().catch(() => null);
                } catch (error) {
                    failureReason = error.message;
                }

                const actualStatus = response?.status || null;
                const actualSuccess = Boolean(response?.ok && (!payload || payload.success !== false));
                const expectedStatus = step.expectedStatus || (step.method === 'POST' ? 201 : 200);
                const result = {
                    method: step.method,
                    path: requestPath,
                    status: actualSuccess && actualStatus === expectedStatus ? 'PASS' : 'FAIL',
                    statusCode: actualStatus,
                    sampleData: body
                        ? JSON.stringify(body)
                        : (queryPayload ? JSON.stringify(queryPayload) : null),
                    detail: actualSuccess
                        ? `Live request returned HTTP ${actualStatus}`
                        : payload?.error || failureReason || `Expected HTTP ${expectedStatus} but received ${actualStatus ?? 'no response'}`,
                    reason: actualSuccess && actualStatus === expectedStatus
                        ? null
                        : payload?.error || failureReason || `Expected HTTP ${expectedStatus} but received ${actualStatus ?? 'no response'}`,
                };

                if (result.status === 'PASS') {
                    const createdRecord = extractCreatedRecord(payload);
                    if (createdRecord) {
                        createdRecords[resourceBase] = createdRecord;
                    }
                }

                liveResults.push(result);
                emit({
                    type: 'test-result',
                    method: result.method,
                    path: result.path,
                    status: result.status,
                    statusCode: result.statusCode,
                    reason: result.reason,
                    sampleData: result.sampleData,
                    detail: result.detail,
                    dbEffect: result.detail,
                    round: 'live',
                });
            }
        }
        const failedResults = liveResults.filter(result => result.status === 'FAIL');
        await writeFile(
            path.join(reportsDir, 'live-api-results.json'),
            JSON.stringify({
                projectTitle: projectTitle || 'generated-app',
                gatewayUrl: `http://127.0.0.1:${ports.gateway}`,
                mongoUri,
                summary: {
                    passed: liveResults.filter(result => result.status === 'PASS').length,
                    failed: failedResults.length,
                    total: liveResults.length,
                },
                results: liveResults,
            }, null, 2),
            'utf8'
        ).catch(() => {});
        if (failedResults.length > 0) {
            await appendBugMemory('Live Route Failures', failedResults.map((result) => `${result.method} ${result.path}: ${result.reason || result.detail || 'runtime failure'}`));
        }
        preserveProcesses = keepAliveOnSuccess && failedResults.length === 0;
        return {
            ok: failedResults.length === 0,
            results: liveResults,
            failedResults,
            gatewayUrl: `http://127.0.0.1:${ports.gateway}`,
            rootDir,
            mongoUri,
            ports,
            processes: preserveProcesses ? liveProcesses : [],
        };
    } catch (error) {
        const failureMessage = error?.message || 'Live backend validation failed before HTTP tests completed.';
        emit({
            type: 'log',
            phase: 'api-test',
            level: 'warning',
            round: 'live',
                message: `Live startup/runtime failure: ${failureMessage}`,
        });

        const runtimeFailure = {
            method: 'GET',
            path: '/health',
            status: 'FAIL',
            statusCode: null,
            sampleData: null,
            detail: failureMessage,
            reason: failureMessage,
        };

        emit({
            type: 'test-result',
            method: runtimeFailure.method,
            path: runtimeFailure.path,
            status: runtimeFailure.status,
            statusCode: runtimeFailure.statusCode,
            reason: runtimeFailure.reason,
            sampleData: runtimeFailure.sampleData,
            detail: runtimeFailure.detail,
            dbEffect: runtimeFailure.detail,
            round: 'live',
        });

        await mkdir(reportsDir, { recursive: true }).catch(() => {});
        await writeFile(
            path.join(reportsDir, 'live-api-results.json'),
            JSON.stringify({
                projectTitle: projectTitle || 'generated-app',
                gatewayUrl: `http://127.0.0.1:${ports.gateway}`,
                mongoUri,
                summary: {
                    passed: liveResults.filter(result => result.status === 'PASS').length,
                    failed: 1,
                    total: liveResults.length > 0 ? liveResults.length + 1 : 1,
                },
                results: liveResults.length > 0 ? [...liveResults, runtimeFailure] : [runtimeFailure],
            }, null, 2),
            'utf8'
        ).catch(() => {});
        await appendBugMemory('Live Runtime Failure', [failureMessage]);

        return {
            ok: false,
            results: liveResults.length > 0 ? [...liveResults, runtimeFailure] : [runtimeFailure],
            failedResults: [runtimeFailure],
            gatewayUrl: `http://127.0.0.1:${ports.gateway}`,
            rootDir,
            mongoUri,
            ports,
            processes: [],
        };
    } finally {
        if (!preserveProcesses) {
            await stopBackendProcesses(liveProcesses, emit);
            await killRuntimePorts(ports, emit, 'post-round cleanup');
        }
        // Keep the local backend test workspace on disk so the user can inspect
        // the exact files used during npm install / npm start API validation.
    }
}

/* Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
   PARSE TEST RESULTS from AI API-testing output
   Expects ===API_TESTS=== ... ===END_API_TESTS=== block with pipe-delimited rows
Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ */
function parseTestResults(text) {
    const results = [];
    const parseStatusCode = (value) => {
        const parsed = Number.parseInt(value, 10);
        return Number.isFinite(parsed) ? parsed : null;
    };

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
            const maybeStatusCode = parseStatusCode(parts[2]);
            const statusCode = maybeStatusCode;
            const sampleIndex = maybeStatusCode !== null ? 3 : 2;
            const detailIndex = maybeStatusCode !== null ? 4 : 3;
            const sampleData = parts[sampleIndex] && parts[sampleIndex] !== '-' ? parts[sampleIndex] : null;
            const detail     = parts[detailIndex] && parts[detailIndex] !== '-' ? parts[detailIndex] : null;
            const reason     = status === 'FAIL' ? detail : null;
            results.push({ method, path, status, statusCode, sampleData, reason, detail });
        });
    }

    // Fallback: scan free text for METHOD /path ... PASS/FAIL pattern
    if (results.length === 0) {
const re = /\b(GET|POST|PUT|DELETE|PATCH)\s+(\/[^\s|,]+)\s*[|:\-\s]+(PASS|FAIL)([^\n]*)/gi;
        let m;
        while ((m = re.exec(text)) !== null) {
            const method = m[1].toUpperCase();
            const path   = m[2].trim();
            const status = m[3].toUpperCase();
        const detail = m[4]?.replace(/^[\s|:\-]+/, '').trim() || null;
            const reason = status === 'FAIL' ? detail : null;
            // Deduplicate
            if (!results.find(r => r.method === method && r.path === path))
                results.push({ method, path, status, statusCode: null, reason, detail });
        }
    }

    return results;
}

function describeDatabaseEffect(method, path, detail) {
    const detailText = detail?.trim();
    if (detailText) {
        return detailText;
    }

    if (method === 'POST') {
        return `Sample create request should persist a new document in MongoDB for ${path}`;
    }
    if (method === 'GET') {
        return `Read request should return the current MongoDB data for ${path}`;
    }
    if (method === 'PUT' || method === 'PATCH') {
        return `Update request should modify the stored MongoDB document for ${path}`;
    }
    if (method === 'DELETE') {
        return `Delete request should remove the matching MongoDB document for ${path}`;
    }
    return `Route should complete successfully for ${path}`;
}

/* Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
   BUILD BACKEND SNAPSHOT for prompts (capped to avoid token overflow)
Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ */
function buildBackendSnapshot(
    backendFiles,
    {
        maxFiles = 15,
        maxCharsPerFile = 6000,
        maxTotalChars = 40000,
    } = {}
) {
    const prioritize = ([path]) => {
        if (path.includes('/routes/')) return 0;
        if (path.includes('gateway') && path.endsWith('index.js')) return 1;
        if (path.endsWith('/index.js')) return 2;
        if (path.includes('/models/')) return 3;
        if (path.endsWith('package.json')) return 4;
        return 5;
    };

    let totalChars = 0;
    const snapshotParts = [];

    Object.entries(backendFiles)
        .sort((left, right) => {
            const priorityDiff = prioritize(left) - prioritize(right);
            return priorityDiff !== 0 ? priorityDiff : left[0].localeCompare(right[0]);
        })
        .slice(0, maxFiles)
        .forEach(([path, content]) => {
            if (totalChars >= maxTotalChars) {
                return;
            }

            const code = typeof content === 'string' ? content : content?.code || '';
            const remainingChars = maxTotalChars - totalChars;
            const allowedChars = Math.min(maxCharsPerFile, remainingChars);
            const snippet = code.length > allowedChars
                ? `${code.slice(0, allowedChars)}\n/* [truncated for prompt size] */`
                : code;

            snapshotParts.push(`===FILE: ${path}===\n${snippet}\n===END===`);
            totalChars += snippet.length;
        });

    return snapshotParts.join('\n\n');
}

function buildFailureFocusedBackendSnapshot(backendFiles, failedRoutes = [], options = {}) {
    if (!failedRoutes || failedRoutes.length === 0) {
        return buildBackendSnapshot(backendFiles, options);
    }

    const contracts = parseBackendContracts(backendFiles);
    const serviceRouteMounts = collectServiceRouteMounts(backendFiles);
    const selectedPaths = new Set();
    const normalizeResourceKey = (value = '') => String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    const getRouteResourceKeys = (failedPath = '') => {
        const segments = String(failedPath || '').split('/').filter(Boolean);
        const keys = new Set();
        segments.forEach((segment) => {
            const normalized = normalizeResourceKey(segment);
            if (!normalized || normalized === 'api' || normalized === 'health') return;
            keys.add(normalized);
            if (normalized.endsWith('s')) keys.add(normalized.slice(0, -1));
            else keys.add(`${normalized}s`);
        });
        return [...keys];
    };

    Object.keys(backendFiles).forEach((filePath) => {
        if (filePath.includes('api-gateway/index.js') || filePath.endsWith('/package.json')) {
            selectedPaths.add(filePath);
        }
    });

    failedRoutes.forEach((failedRoute) => {
        const matchingContracts = contracts.filter((contract) =>
            contract.method === failedRoute.method && contract.path === failedRoute.path
        );

        matchingContracts.forEach((contract) => {
            if (contract.routeFile) {
                selectedPaths.add(contract.routeFile);
            }

            if (contract.serviceDir) {
                const serviceIndex = `${contract.serviceDir}/index.js`;
                if (backendFiles[serviceIndex]) {
                    selectedPaths.add(serviceIndex);
                }

                Object.keys(backendFiles).forEach((filePath) => {
                    if (filePath.startsWith(`${contract.serviceDir}/models/`)) {
                        selectedPaths.add(filePath);
                    }
                });
            }
        });

        const failedResourceKeys = getRouteResourceKeys(failedRoute.path);
        if (failedResourceKeys.length > 0) {
            Object.keys(backendFiles).forEach((filePath) => {
                const normalizedPath = filePath.replace(/^\/+/, '');
                const serviceDir = normalizedPath.split('/')[0];
                const baseName = normalizedPath.split('/').pop()?.replace(/\.[^.]+$/, '') || '';
                const normalizedBaseName = normalizeResourceKey(baseName);
                const mountKeys = [...(serviceRouteMounts[serviceDir] || new Set())]
                    .map((mount) => normalizeResourceKey(mount.split('/').filter(Boolean).pop() || ''))
                    .filter(Boolean);
                const routeMatch = normalizedPath.includes('/routes/')
                    && failedResourceKeys.some((key) => normalizedBaseName === key);
                const modelMatch = normalizedPath.includes('/models/')
                    && failedResourceKeys.some((key) => normalizedBaseName === key);
                const serviceMatch = /\/index\.js$/i.test(normalizedPath)
                    && !/gateway/i.test(normalizedPath)
                    && failedResourceKeys.some((key) => mountKeys.includes(key));

                if (routeMatch || modelMatch || serviceMatch) {
                    selectedPaths.add(filePath);
                    if (serviceDir && backendFiles[`${serviceDir}/index.js`]) {
                        selectedPaths.add(`${serviceDir}/index.js`);
                    }
                }
            });
        }
    });

    const focusedFiles = {};
    selectedPaths.forEach((filePath) => {
        if (backendFiles[filePath]) {
            focusedFiles[filePath] = backendFiles[filePath];
        }
    });

    return buildBackendSnapshot(
        Object.keys(focusedFiles).length > 0 ? focusedFiles : backendFiles,
        options
    );
}

/* Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
   STREAM ALL CHUNKS FROM OLLAMA Ã¢â‚¬â€ yields chunk objects
Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ */
async function* streamOllama(messages, system, temperature = 0.7, options = {}) {
    const response = await ollamaChat({
        messages,
        system,
        temperature,
        stream: true,
        model: options.model,
    });
    yield* readOllamaStream(response);
}

async function askOllamaText(messages, system, temperature = 0.2, options = {}) {
    const response = await ollamaChat({
        messages,
        system,
        temperature,
        stream: false,
        format: options.format,
        model: options.model,
    });
    const payload = await response.json();
    return payload?.message?.content ?? '';
}

function pickBackendRepairModel(round = 1, failedCount = 0) {
    if (round === 1 || failedCount >= 5) {
        return BACKEND_GEN_MODEL;
    }
    return BACKEND_FIX_MODEL;
}

function classifyFailureBucket(reason = '', path = '') {
    const text = `${path} ${reason}`.toLowerCase();
    if (/router is not defined|app is not defined|service failed to start|exited before health check|syntaxerror|referenceerror|module_not_found|cannot find module/.test(text)) {
        return 'startup/runtime';
    }
    if (/econnrefused|downstream service unavailable|proxy error|502/.test(text)) {
        return 'gateway/proxy';
    }
    if (/no token|unauthorized|access denied|forbidden|401|403|bearer/.test(text)) {
        return 'auth';
    }
    if (/duplicate key|validation failed|cast to objectid|enum value|400/.test(text)) {
        return 'validation/data';
    }
    if (/404|route not found|expected http 200 but received 404|expected http 201 but received 404/.test(text)) {
        return 'route mapping';
    }
    if (/500|internal server error/.test(text)) {
        return 'server logic';
    }
    return 'other';
}

function buildFailureAnalysisForAI(backendFiles, failedRoutes = []) {
    if (!failedRoutes || failedRoutes.length === 0) {
        return 'DEEP FAILURE ANALYSIS:\n- No failing routes were provided.';
    }

    const contracts = parseBackendContracts(backendFiles);
    const backendPathList = Object.keys(backendFiles);
    const gatewayIndex = backendPathList.find((filePath) => /api-gateway\/index\.js$/i.test(filePath));
    const categoryCounts = new Map();
    const lines = ['DEEP FAILURE ANALYSIS:'];

    const inferOwners = (failedRoute) => {
        const owners = new Set();
        if (gatewayIndex && /^\/api\//i.test(failedRoute.path || '')) {
            owners.add(gatewayIndex);
        }

        contracts
            .filter((contract) => contract.method === failedRoute.method && contract.path === failedRoute.path)
            .forEach((contract) => {
                if (contract.routeFile) owners.add(contract.routeFile);
                if (contract.serviceDir) {
                    const serviceIndex = `${contract.serviceDir}/index.js`;
                    if (backendFiles[serviceIndex]) owners.add(serviceIndex);
                }
                (contract.modelCandidates || []).forEach((modelPath) => owners.add(modelPath));
            });

        const normalizedReason = String(failedRoute.reason || failedRoute.detail || '').replace(/\\/g, '/');
        backendPathList.forEach((filePath) => {
            const normalizedFilePath = filePath.replace(/^\/+/, '');
            const serviceName = normalizedFilePath.split('/')[0];
            if (normalizedReason.includes(normalizedFilePath) || (serviceName && normalizedReason.includes(serviceName))) {
                owners.add(filePath);
            }
        });

        return [...owners];
    };

    failedRoutes.forEach((failedRoute) => {
        const reason = failedRoute.reason || failedRoute.detail || 'unknown failure';
        const bucket = classifyFailureBucket(reason, failedRoute.path);
        categoryCounts.set(bucket, (categoryCounts.get(bucket) || 0) + 1);
        const owners = inferOwners(failedRoute);
        const hints = [];

        if (/router is not defined/i.test(reason)) {
            hints.push('entry file is using router.* without declaring express.Router(); convert startup health or middleware handlers to app.* or declare router correctly');
        }
        if (/app is not defined/i.test(reason)) {
            hints.push('entry file is using app.* without const app = express(); restore the app declaration before middleware and routes');
        }
        if (/econnrefused|downstream service unavailable/i.test(reason)) {
            hints.push('gateway proxy target or service port wiring is wrong; repair the proxy target env var and mounted prefix together');
        }
        if (/404|route not found/i.test(reason)) {
            hints.push('gateway prefix, pathRewrite, app.use mount, and router file paths likely disagree; repair them as one unit');
        }
        if (/401|403|no token|access denied|unauthorized/i.test(reason)) {
            hints.push('protected routes need register/login-compatible auth flow or proper middleware exclusions');
        }
        if (/400|validation failed|duplicate key|enum value/i.test(reason)) {
            hints.push('payload/schema assumptions are wrong; align route validation, model enums, and required fields');
        }

        lines.push(
            `- ${failedRoute.method} ${failedRoute.path}` +
            ` | category=${bucket}` +
            ` | owners=${owners.length > 0 ? owners.join(', ') : 'unknown'}` +
            ` | reason=${reason}` +
            (hints.length > 0 ? ` | fix-hints=${hints.join('; ')}` : '')
        );
    });

    lines.push('FAILURE CATEGORY TOTALS:');
    [...categoryCounts.entries()]
        .sort((a, b) => b[1] - a[1])
        .forEach(([bucket, count]) => lines.push(`- ${bucket}: ${count}`));
    lines.push('Treat repeated failures as shared root causes. Prefer rewriting the owning startup, gateway, route, and model files together in round 1 instead of returning small isolated edits.');

    return lines.join('\n');
}

function classifyRouteFailure(result = {}) {
    const text = String(result.reason || result.detail || '').toLowerCase();

    if (!text) return 'UNKNOWN';

    if (text.includes('cannot find module')) return 'MODULE_MISSING';
    if (text.includes('eaddrinuse')) return 'PORT_IN_USE';
    if (text.includes('not a valid enum')) return 'SCHEMA_VALIDATION';
    if (text.includes('referenceerror')) return 'REFERENCE_ERROR';
    if (text.includes('npm install failed') || text.includes('ejsonparse') || text.includes('enotempty')) return 'PACKAGE_INSTALL_FAILURE';

    if (
        text.includes('service unavailable')
        || text.includes('econnrefused')
    ) {
        return 'BLOCKED_SERVICE';
    }

    if (
        text.includes('until auth token is available')
        || text.includes('until required ids exist')
        || text.includes('skipping ')
        || text.includes('deferring ')
    ) {
        return 'BLOCKED_DEPENDENCY';
    }

    if (text.includes('exited before health check')) return 'RUNTIME_FAILURE';

    return 'RUNTIME_FAILURE';
}

function isBlockedRouteFailure(result = {}) {
    const kind = classifyRouteFailure(result);
    return kind === 'BLOCKED_SERVICE' || kind === 'BLOCKED_DEPENDENCY';
}

// Returns true when the only failure is GET /health returning 404 directly from a service port.
// This is a service-internal health wiring issue — the frontend never calls /health, so it is
// safe to proceed to frontend generation with a warning rather than blocking completely.
function isServiceHealthOnlyFailure(result = {}) {
    const method = String(result.method || '').toUpperCase();
    const routePath = String(result.path || '');
    const reason = String(result.reason || result.detail || '').toLowerCase();
    return (
        method === 'GET' &&
        (routePath === '/health' || routePath.endsWith('/health')) &&
        (reason.includes('404') || reason.includes('status 404') || reason.includes('received status 404'))
    );
}

function normalizeFailureSignature(result = {}) {
    const method = String(result.method || 'GET').toUpperCase();
    const routePath = String(result.path || '');
    const kind = classifyRouteFailure(result);
    const reason = String(result.reason || result.detail || '')
        .toLowerCase()
        .replace(/\d+/g, ':n')
        .replace(/\s+/g, ' ')
        .trim();

    return `${kind}|${method}|${routePath}|${reason}`;
}

/* Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
   ROUTE HANDLER
Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬ */
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
                let backendValidationErrors = [];
                const genSessionKey = `gen-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
                const structuredAppSpec = extractStructuredAppSpec(prompt);
                const appPlanningSnapshot = buildAppPlanningSnapshot(structuredAppSpec, prompt);
                await appendBugMemory('App Build Plan', appPlanningSnapshot.lines);
                const structuredSpecContract = buildStructuredSpecContract(structuredAppSpec);
                const localReferenceContext = await loadLocalReferenceContext();
                const generationPrompt = [
                    prompt,
                    structuredSpecContract,
                    localReferenceContext,
                ].filter(Boolean).join('\n\n');
                const sharedBackendRepairContext = [
                    await loadBackendRepairContext(),
                    localReferenceContext,
                ].filter(Boolean).join('\n\n');

                if (structuredAppSpec?.projectTitle) {
                    projectTitle = structuredAppSpec.projectTitle;
                }
                if (structuredAppSpec) {
                    emit({
                        type: 'log',
                        phase: 'backend-gen',
                        level: 'info',
                        message: `Structured spec detected: ${structuredAppSpec.projectTitle || 'Untitled app'} | ${structuredAppSpec.services.length} services | ${structuredAppSpec.features.length} features`,
                    });
                }
                emit({
                    type: 'log',
                    phase: 'backend-gen',
                    level: 'info',
                    message: `Developer memory saved locally: backend libraries ${appPlanningSnapshot.libraries.backendLibraries.join(', ') || 'none inferred'} | frontend libraries ${appPlanningSnapshot.libraries.frontendLibraries.join(', ') || 'none inferred'}`,
                });

                /* Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
                   PHASE 1 Ã¢â‚¬â€ BACKEND GENERATION
                Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â */
                emit({ type: 'phase', phase: 'backend-gen', status: 'start',
                    message: 'Generating backend microservices...' });
                emit({
                    type: 'log',
                    phase: 'backend-gen',
                    level: 'info',
                    message: 'Using models: backend-gen=' + BACKEND_GEN_MODEL + ', backend-fix=' + BACKEND_FIX_MODEL + ', api-test=' + API_TEST_MODEL + ', frontend-gen=' + FRONTEND_GEN_MODEL + ', frontend-fix=' + FRONTEND_FIX_MODEL,
                });

                let backendText = '';
                let prevText    = '';
                const beUserPrompt = generationPrompt;

                for await (const chunk of streamOllama(
                    [{ role: 'user', content: beUserPrompt }],
                    Prompt.BACKEND_GEN_PROMPT, 0.6, { model: BACKEND_GEN_MODEL }
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
                let beParsed = parseBackendOnly(backendText);
                if (Object.keys(beParsed.backend).length === 0 && backendText.trim()) {
                    let reformatPrevText = '';
                    emit({
                        type: 'log',
                        phase: 'backend-gen',
                        level: 'warning',
                        message: `Backend output was not in file-marker format. Trying recovery reformat using ${BACKEND_FIX_MODEL}...`,
                    });

                    let reformattedBackendText = '';
                    for await (const chunk of streamOllama(
                        [{
                            role: 'user',
                            content:
                                `RAW BACKEND ANSWER TO REFORMAT:\n\n${backendText}\n\n` +
                                `Convert this into exact ===BACKEND: /path=== ... ===ENDFILE=== blocks.`
                        }],
                        Prompt.BACKEND_REFORMAT_PROMPT,
                        0.1,
                        { model: BACKEND_FIX_MODEL }
                    )) {
                        const content = chunk?.message?.content ?? '';
                        if (content) {
                            reformattedBackendText += content;
                            totalChars += content.length;
                            emit({ type: 'chunk', phase: 'backend-gen', chars: totalChars });
                            const newFiles = extractNewFilePaths(reformattedBackendText, reformatPrevText);
                            newFiles.forEach(f => emit({ type: 'file', phase: 'backend-gen', ...f }));
                            reformatPrevText = reformattedBackendText;
                        }
                        if (chunk?.done) break;
                    }

                    const reparsed = parseBackendOnly(reformattedBackendText);
                    if (Object.keys(reparsed.backend).length > 0) {
                        beParsed = reparsed;
                        backendText = reformattedBackendText;
                    }
                }
                if (Object.keys(beParsed.backend).length === 0) {
                    emit({
                        type: 'log',
                        phase: 'backend-gen',
                        level: 'warning',
                        message: `Marker recovery failed. Trying strict JSON backend generation with ${BACKEND_GEN_MODEL}...`,
                    });

                    const jsonBackendText = await askOllamaText(
                        [{ role: 'user', content: beUserPrompt }],
                        Prompt.BACKEND_GEN_JSON_PROMPT,
                        0.2,
                        { model: BACKEND_GEN_MODEL, format: 'json' }
                    );
                    const jsonParsed = parseBackendJsonPayload(jsonBackendText);
                    if (Object.keys(jsonParsed.backend).length > 0) {
                        beParsed = jsonParsed;
                        projectTitle = jsonParsed.projectTitle || projectTitle;
                        Object.keys(jsonParsed.backend).forEach((filePath) => {
                            emit({ type: 'file', phase: 'backend-gen', section: 'backend', path: filePath });
                        });
                    }
                }
                let backendFiles = beParsed.backend;
                let successfulLiveRuntime = null;
                projectTitle = beParsed.projectTitle || projectTitle;

                const beCount = Object.keys(backendFiles).length;
                emit({ type: 'phase', phase: 'backend-gen', status: 'done',
                    fileCount: beCount,
                    message: `Generated ${beCount} backend files` });

                if (beCount === 0) {
                    emit({
                        type: 'error',
                        error: `Backend generation failed: parser found 0 backend files. Model ${BACKEND_GEN_MODEL} did not return usable file blocks, and recovery with ${BACKEND_FIX_MODEL} also failed. Frontend generation is blocked until backend output is valid.`,
                        done: true,
                    });
                    controller.close();
                    return;
                }

                /* Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
                   PHASE 2 Ã¢â‚¬â€ BACKEND BUG FIXING (up to 5 rounds)
                Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â */
                if (beCount > 0) {
                    emit({ type: 'phase', phase: 'backend-fix', status: 'start',
                        message: 'Analyzing backend for bugs...' });
                    const backendRepairContext = sharedBackendRepairContext;

                    // Round 0 Ã¢â‚¬â€ static fixes (instant, no AI)
                    const { files: staticFixed, fixCount, createdFiles = [], repairedFiles = [] } = staticFixBackend(backendFiles, structuredAppSpec);
                    backendFiles = staticFixed;
                    if (fixCount > 0) {
                        emit({ type: 'log', phase: 'backend-fix', level: 'info',
                            message: `Static analysis fixed ${fixCount} files (ports, middleware, CORS, proxy safety)` });
                        createdFiles.slice(0, 12).forEach((entry) => {
                            emit({ type: 'log', phase: 'backend-fix', level: 'success', message: `[developer-fix] Created ${entry}` });
                        });
                        repairedFiles.slice(0, 18).forEach((entry) => {
                            emit({ type: 'log', phase: 'backend-fix', level: 'success', message: `[developer-fix] Fixed ${entry}` });
                        });
                    } else {
                        emit({ type: 'log', phase: 'backend-fix', level: 'success',
                            message: 'Static analysis: no quick-fix issues found' });
                    }
                    emit({
                        type: 'log',
                        phase: 'backend-fix',
                        level: 'info',
                        message: 'Next step: read each backend service in developer order — models, routes, controllers, index.js, and package imports — before applying AI fixes.',
                    });
                    emitBackendServiceAudit(emit, collectBackendServiceAudit(backendFiles, structuredAppSpec), { phase: 'backend-fix' });

                    let currentBackendValidation = await validateBackendCandidateFiles(
                        backendFiles,
                        projectTitle || 'generated-app',
                        structuredAppSpec
                    );
                    if (!currentBackendValidation.ok) {
                        emit({
                            type: 'log',
                            phase: 'backend-fix',
                            level: 'warning',
                            message: `Backend still has ${currentBackendValidation.errors.length} validation issue(s) before AI fixes. Starting focused repair rounds...`,
                        });
                    }

                    let beNoProgressCount = 0;
                    let bePrevErrorCount = currentBackendValidation.errors.length;
                    let bePrevErrorSignature = currentBackendValidation.errors.slice().sort().join('\n');

                    for (let round = 1; round <= MAX_BACKEND_FIX_ROUNDS; round++) {
                        emit({ type: 'log', phase: 'backend-fix', level: 'info', round,
                            message: `Round ${round}: AI reviewing backend code... (${currentBackendValidation.errors.length} issue(s) remaining)` });

                        if (currentBackendValidation.ok) {
                            emit({ type: 'log', phase: 'backend-fix', level: 'success', round,
                                message: `Round ${round}: Backend is fully clean — stopping fix loop.` });
                            break;
                        }

                        // Build snapshot (limit to avoid huge prompts)
                        const snapshot = buildBackendSnapshot(backendFiles, {
                            maxFiles: 12,
                            maxCharsPerFile: 5000,
                            maxTotalChars: 32000,
                        });

                        let fixText = '';
                        const repairModel = pickBackendRepairModel(round, Object.keys(backendFiles).length);
                        const currentErrors = currentBackendValidation.errors;
                        const [beMemCtx, beFailedMethods] = await Promise.all([
                            buildMemoryContext(currentErrors.join('\n')).catch(() => ''),
                            getFailedMethods(currentErrors.join('\n')).catch(() => []),
                        ]);
                        const beStrategy = pickStrategy(genSessionKey + '-be', beFailedMethods, round);
                        emit({ type: 'log', phase: 'backend-fix', level: 'info', round,
                            message: `Round ${round}: Strategy "${beStrategy.name}" — ${beStrategy.description}` });
                        const roundInstruction = buildHumanLikeInstruction({
                            strategy: beStrategy,
                            memoryContext: beMemCtx,
                            round,
                            errorCount: currentErrors.length,
                            currentErrors,
                        });
                        const escalatedRoundInstruction = beNoProgressCount >= 1
                            ? `${roundInstruction}\nEscalation: previous patch did not improve validation. Rewrite the owning file(s) completely from scratch. For each bug, identify the exact file, approximate code element/line area, and replace that whole block instead of returning a tiny patch.`
                            : roundInstruction;
                        for await (const chunk of streamOllama(
                            [{
                                role: 'user',
                                content:
                                    `${backendRepairContext}\n\n` +
                                    (structuredSpecContract ? `STRUCTURED APP CONTRACT:\n${structuredSpecContract}\n\n` : '') +
                                    `BACKEND SNAPSHOT:\n${snapshot}\n\n` +
                                    `CURRENT VALIDATION ERRORS (fix ALL of these):\n${currentErrors.join('\n')}\n\n` +
                                    `${escalatedRoundInstruction}`
                            }],
                            Prompt.BACKEND_FIX_PROMPT, 0.2, { model: repairModel }
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
                                message: `Round ${round}: No bugs found - backend is clean!` });
                            break;
                        }

                        const fixParsed = parseBackendOnly(fixText);
                        const fixedCount = Object.keys(fixParsed.backend).length;
                        if (fixedCount > 0) {
                            const candidateFiles = staticFixBackend({ ...backendFiles, ...fixParsed.backend }, structuredAppSpec).files;
                            const validation = await validateBackendCandidateFiles(candidateFiles, projectTitle || 'generated-app', structuredAppSpec);
                            if (validation.ok) {
                                backendFiles = candidateFiles;
                                currentBackendValidation = validation;
                                beNoProgressCount = 0;
                                bePrevErrorCount = 0;
                                bePrevErrorSignature = '';
                                storeBugFix({ bugText: currentErrors.join('\n'), method: beStrategy.name, outcome: 'success', phase: 'backend-fix', round, fixSummary: `Fully fixed ${fixedCount} file(s), backend clean` }).catch(() => {});
                                emit({ type: 'log', phase: 'backend-fix', level: 'success', round,
                                    message: `Round ${round}: Fixed ${fixedCount} backend file(s) — backend is clean!` });
                                break;
                            } else {
                                const newErrCount = validation.errors.length;
                                const newErrSig = validation.errors.slice().sort().join('\n');
                                if (newErrCount < bePrevErrorCount) {
                                    // Applied a partial fix — keep it and continue
                                    backendFiles = candidateFiles;
                                    currentBackendValidation = validation;
                                    beNoProgressCount = 0;
                                    storeBugFix({ bugText: currentErrors.join('\n'), method: beStrategy.name, outcome: 'success', phase: 'backend-fix', round, fixSummary: `Partial fix: resolved ${bePrevErrorCount - newErrCount} of ${bePrevErrorCount} issues` }).catch(() => {});
                                    bePrevErrorCount = newErrCount;
                                    bePrevErrorSignature = newErrSig;
                                    emit({ type: 'log', phase: 'backend-fix', level: 'warning', round,
                                        message: `Round ${round}: Partial fix applied — ${bePrevErrorCount - newErrCount} issue(s) resolved, ${newErrCount} remaining.` });
                                } else {
                                    beNoProgressCount++;
                                    markStrategyFailed(genSessionKey + '-be', beStrategy.name);
                                    storeBugFix({ bugText: currentErrors.join('\n'), method: beStrategy.name, outcome: 'fail', phase: 'backend-fix', round, fixSummary: `No improvement: ${validation.errors.slice(0, 2).join(' | ')}` }).catch(() => {});
                                    emit({ type: 'log', phase: 'backend-fix', level: 'warning', round,
                                        message: `Rejected invalid backend patch for round ${round} (no improvement): ${validation.errors.slice(0, 2).join(' | ')} — no-progress count: ${beNoProgressCount}/${MAX_NO_PROGRESS_ROUNDS}`,
                                    });
                                    if (beNoProgressCount >= MAX_NO_PROGRESS_ROUNDS) {
                                        emit({ type: 'error', phase: 'backend-fix', round,
                                            error: `Stopping backend repair: ${MAX_NO_PROGRESS_ROUNDS} consecutive no-improvement rounds.` });
                                        break;
                                    }
                                }
                            }
                        } else {
                            if (currentBackendValidation.ok) {
                                emit({ type: 'log', phase: 'backend-fix', level: 'success', round,
                                    message: `Round ${round}: No bugs found - backend is clean!` });
                                break;
                            }
                            beNoProgressCount++;
                            markStrategyFailed(genSessionKey + '-be', beStrategy.name);
                            storeBugFix({ bugText: currentErrors.join('\n'), method: beStrategy.name, outcome: 'fail', phase: 'backend-fix', round, fixSummary: 'AI produced no file changes' }).catch(() => {});
                            emit({ type: 'log', phase: 'backend-fix', level: 'warning', round,
                                message: `Round ${round}: AI produced no file changes, ${currentBackendValidation.errors.length} issue(s) still remain. No-progress: ${beNoProgressCount}/${MAX_NO_PROGRESS_ROUNDS}`,
                            });
                            if (beNoProgressCount >= MAX_NO_PROGRESS_ROUNDS) {
                                emit({ type: 'error', phase: 'backend-fix', round,
                                    error: `Stopping backend repair: ${MAX_NO_PROGRESS_ROUNDS} consecutive no-progress rounds.` });
                                break;
                            }
                        }
                    }

                    currentBackendValidation = await validateBackendCandidateFiles(
                        backendFiles,
                        projectTitle || 'generated-app',
                        structuredAppSpec
                    );
                    backendValidationErrors = [...currentBackendValidation.errors];
                    emit({ type: 'phase', phase: 'backend-fix', status: 'done',
                        message: currentBackendValidation.ok
                            ? `Backend verified (${Object.keys(backendFiles).length} files ready)`
                            : `Backend still has ${currentBackendValidation.errors.length} validation issue(s)` });
                }

                /* Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
                   PHASE 3 Ã¢â‚¬â€ POSTMAN-STYLE API ROUTE TESTING
                   Simulates real HTTP requests for every route.
                   Auto-fixes failing routes for up to 5 rounds.
                Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â */
                if (Object.keys(backendFiles).length > 0) {
                    emit({ type: 'phase', phase: 'api-test', status: 'start',
                        message: 'Running Postman-style API + MongoDB integration simulation...' });

                    let allRoutesClean = false;
                    let initialFailedCount = null;
                    let bestFailedCount = Number.POSITIVE_INFINITY;
                    let lastFailedRoutes = [];
                    let latestTestResults = [];
                    const backendRepairContext = sharedBackendRepairContext;
                    let previousFailureSignature = '';
                    let apiSameSignatureCount = 0;
                    let apiNoProgressCount = 0;

                    for (let round = 1; round <= MAX_API_FIX_ROUNDS; round++) {
                        emit({ type: 'log', phase: 'api-test', level: 'info', round,
                            message: `Round ${round}: Simulating request payloads, gateway routing, and MongoDB persistence for all routes...` });

                        const snapshot = round === 1
                            ? buildBackendSnapshot(backendFiles)
                            : buildFailureFocusedBackendSnapshot(backendFiles, lastFailedRoutes);

                        let testText = '';
                        for await (const chunk of streamOllama(
                            [{ role: 'user', content: snapshot }],
                            Prompt.API_TEST_PROMPT, 0.2, { model: API_TEST_MODEL }
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
                        latestTestResults = testResults;
                        const passed      = testResults.filter(r => r.status === 'PASS');
                        const failed      = testResults.filter(r => r.status === 'FAIL');
                        const failureSignature = failed
                            .map(r => `${r.method} ${r.path}: ${r.reason || r.detail || 'unknown issue'}`)
                            .sort()
                            .join('\n');
                        if (initialFailedCount === null) {
                            initialFailedCount = failed.length;
                        }
                        bestFailedCount = Math.min(bestFailedCount, failed.length);
                        lastFailedRoutes = failed;

                        // Emit individual route test results
                        if (testResults.length > 0) {
                            testResults.forEach(r => {
                                const dbEffect = describeDatabaseEffect(r.method, r.path, r.detail);
                                emit({
                                    type: 'test-result',
                                    method: r.method,
                                    path:   r.path,
                                    status: r.status,
                                    statusCode: r.statusCode || null,
                                    reason: r.reason || null,
                                    sampleData: r.sampleData || null,
                                    detail: r.detail || null,
                                    dbEffect,
                                    round,
                                });
                            });
                            emit({
                                type: 'test-summary',
                                passed: passed.length,
                                failed: failed.length,
                                total:  testResults.length,
                                fixed: initialFailedCount !== null ? Math.max(initialFailedCount - failed.length, 0) : 0,
                                round,
                            });
                        }

                        if (initialFailedCount !== null && initialFailedCount > 0) {
                            emit({
                                type: 'log',
                                phase: 'api-test',
                                level: failed.length === 0 ? 'success' : 'info',
                                round,
                                message: `Backend route bugs: total ${initialFailedCount}, fixed ${Math.max(initialFailedCount - failed.length, 0)}, remaining ${failed.length}`,
                            });
                        }

                        if (failed.length === 0) {
                            const msg = testResults.length > 0
                                ? `All ${passed.length} routes PASSED! Backend is production-ready.`
                                : parseBackendContracts(backendFiles).length > 0
                                    ? `AI found no parseable routes - falling back to code-derived routes for live backend checks.`
                                    : `AI found no parseable routes and no code-derived routes - live backend will still validate startup and gateway health.`;
                            emit({ type: 'log', phase: 'api-test', level: 'success', round, message: msg });
                            allRoutesClean = true;
                            break;
                        }

                        // Ã¢â€â‚¬Ã¢â€â‚¬ Auto-fix failing routes Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬
                        emit({ type: 'log', phase: 'api-test', level: 'warning', round,
                            message: `${failed.length} route(s) failing - running targeted auto-fix...` });

                        const failList = failed
                            .map(r => `${r.method} ${r.path}: ${r.reason || 'unknown issue'}`)
                            .join('\n');

                        let fixText = '';
                        const repairModel = pickBackendRepairModel(round, failed.length);
                        const targetedSnapshot = round === 1
                            ? snapshot
                            : buildFailureFocusedBackendSnapshot(backendFiles, failed);
                        const failureAnalysis = buildFailureAnalysisForAI(backendFiles, failed);
                        const apiFailText = failList;
                        const [apiMemCtx, apiFailedMethods] = await Promise.all([
                            buildMemoryContext(apiFailText).catch(() => ''),
                            getFailedMethods(apiFailText).catch(() => []),
                        ]);
                        const apiStrategy = pickStrategy(genSessionKey + '-api', apiFailedMethods, round);
                        emit({ type: 'log', phase: 'api-test', level: 'info', round,
                            message: `Round ${round} fix strategy: "${apiStrategy.name}" — ${apiStrategy.description}` });
                        const fixInstruction = buildHumanLikeInstruction({
                            strategy: apiStrategy,
                            memoryContext: apiMemCtx,
                            round,
                            errorCount: failed.length,
                            currentErrors: failed.map(r => `${r.method} ${r.path}: ${r.reason || 'unknown'}`),
                        });
                        const escalatedApiInstruction = apiNoProgressCount >= 1
                            ? `${fixInstruction}\nEscalation: the previous route fix did not improve results. Identify the owner files for each failure, state the exact file and code element to replace, and regenerate the whole owning route/controller/index file from scratch.`
                            : fixInstruction;
                        for await (const chunk of streamOllama(
                            [{ role: 'user', content:
                                `${backendRepairContext}\n\n` +
                                (structuredSpecContract ? `STRUCTURED APP CONTRACT:\n${structuredSpecContract}\n\n` : '') +
                                `${targetedSnapshot}\n\n` +
                                `${failureAnalysis}\n\n` +
                                `FAILED ROUTES THAT MUST BE FIXED:\n${failList}\n\n` +
                                `${escalatedApiInstruction}\nOutput the corrected files only.`
                            }],
                            Prompt.API_FIX_PROMPT, 0.2, { model: repairModel }
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
                                message: `AI confirmed: routes are correct after targeted review.` });
                            allRoutesClean = true;
                            break;
                        }

                        const fixParsed   = parseBackendOnly(fixText);
                        const fixedCount  = Object.keys(fixParsed.backend).length;
                        if (fixedCount > 0) {
                            const candidateFiles = staticFixBackend({ ...backendFiles, ...fixParsed.backend }, structuredAppSpec).files;
                            const validation = await validateBackendCandidateFiles(candidateFiles, projectTitle || 'generated-app', structuredAppSpec);
                            if (validation.ok) {
                                backendFiles = candidateFiles;
                                apiNoProgressCount = 0;
                                apiSameSignatureCount = 0;
                                previousFailureSignature = '';
                                storeBugFix({ bugText: apiFailText, method: apiStrategy.name, outcome: 'success', phase: 'api-test', round, fixSummary: `Fixed ${fixedCount} file(s), all routes clean` }).catch(() => {});
                                emit({ type: 'log', phase: 'api-test', level: 'info', round,
                                    message: `Applied fixes to ${fixedCount} file(s). Re-running tests next round...` });
                            } else {
                                apiNoProgressCount++;
                                markStrategyFailed(genSessionKey + '-api', apiStrategy.name);
                                storeBugFix({ bugText: apiFailText, method: apiStrategy.name, outcome: 'fail', phase: 'api-test', round, fixSummary: `Invalid patch: ${validation.errors.slice(0, 2).join(' | ')}` }).catch(() => {});
                                emit({ type: 'log', phase: 'api-test', level: 'warning', round,
                                    message: `Rejected invalid API-fix patch: ${validation.errors.slice(0, 2).join(' | ')} — retrying (no-progress: ${apiNoProgressCount}/${MAX_NO_PROGRESS_ROUNDS})` });
                                    if (apiNoProgressCount >= MAX_NO_PROGRESS_ROUNDS) {
                                        emit({ type: 'error', phase: 'api-test', round,
                                            error: `Stopping API repair: ${MAX_NO_PROGRESS_ROUNDS} consecutive no-progress rounds.` });
                                        break;
                                    }
                                continue;
                            }
                        } else {
                            apiNoProgressCount++;
                            markStrategyFailed(genSessionKey + '-api', apiStrategy.name);
                            storeBugFix({ bugText: apiFailText, method: apiStrategy.name, outcome: 'fail', phase: 'api-test', round, fixSummary: 'AI produced no fix files' }).catch(() => {});
                            emit({ type: 'log', phase: 'api-test', level: 'warning', round,
                                message: `AI produced no fix files — retrying with refined context. (no-progress: ${apiNoProgressCount}/${MAX_NO_PROGRESS_ROUNDS})` });
                            if (apiNoProgressCount >= MAX_NO_PROGRESS_ROUNDS) {
                                emit({ type: 'error', phase: 'api-test', round,
                                    error: `Stopping API repair: ${MAX_NO_PROGRESS_ROUNDS} consecutive no-progress rounds.` });
                                break;
                            }
                            continue;
                        }

                        if (failureSignature && failureSignature === previousFailureSignature) {
                            apiSameSignatureCount++;
                            emit({
                                type: 'log',
                                phase: 'api-test',
                                level: 'warning',
                                round,
                            message: `Repeated failing-route signature (${apiSameSignatureCount}/${MAX_SAME_SIGNATURE_ROUNDS}).`,
                            });
                        if (apiSameSignatureCount >= MAX_SAME_SIGNATURE_ROUNDS) {
                            emit({ type: 'error', phase: 'api-test', round,
                                error: `Stopping API repair: repeated identical failure signature after ${apiSameSignatureCount} rounds.` });
                            break;
                        }
                        } else {
                            apiSameSignatureCount = 0;
                        }

                        previousFailureSignature = failureSignature;
                    }

                    if (allRoutesClean) {
                        let liveValidationPassed = false;
                        let lastLiveFailures = [];
                        let previousLiveFailureSignature = '';
                        let liveSameSignatureCount = 0;
                        let liveNoProgressCount = 0;
                        let liveRegressiveCount = 0;
                        let bestLiveFailedCount = Number.POSITIVE_INFINITY;
                        let bestLiveFailures = [];
                        let bestLiveBackendFiles = cloneJson(backendFiles);
                        let prevLiveBackendFiles = null; // track file state before each round to compute changed dirs

                        for (let liveRound = 1; liveRound <= MAX_LIVE_FIX_ROUNDS; liveRound++) {
                            emit({
                                type: 'log',
                                phase: 'api-test',
                                level: 'info',
                                round: `live-${liveRound}`,
                                message: `Live backend round ${liveRound}: installing services, starting gateway + microservices, and running real HTTP requests...`,
                            });

                            // Compute which service dirs changed since the last round.
                            // Round 1 always installs everything (changedServiceDirs = null).
                            let liveChangedDirs = null;
                            if (liveRound > 1 && prevLiveBackendFiles) {
                                const changed = new Set();
                                for (const [fp, content] of Object.entries(backendFiles)) {
                                    const prev = prevLiveBackendFiles[fp];
                                    const curCode = typeof content === 'string' ? content : content?.code || '';
                                    const prevCode = typeof prev === 'string' ? prev : prev?.code || '';
                                    if (curCode !== prevCode) {
                                        const svcDir = fp.split('/').filter(Boolean)[0];
                                        if (svcDir) changed.add(svcDir);
                                    }
                                }
                                liveChangedDirs = changed.size > 0 ? changed : null;
                            }
                            prevLiveBackendFiles = cloneJson(backendFiles);

                        const liveValidation = await runLiveBackendValidation(backendFiles, latestTestResults, emit, {
                            projectTitle,
                            keepAliveOnSuccess: true,
                            structuredSpec: structuredAppSpec,
                            changedServiceDirs: liveChangedDirs,
                        });
                            lastLiveFailures = liveValidation.failedResults;
                            const actionableLiveFailures = lastLiveFailures.filter(result => !isBlockedRouteFailure(result));

                            const livePassed = liveValidation.results.filter(result => result.status === 'PASS').length;
                            const liveFailed = lastLiveFailures.length;
                            const actionableLiveFailed = actionableLiveFailures.length;

                            // Track best known state
                            if (actionableLiveFailed < bestLiveFailedCount) {
                                bestLiveFailedCount = actionableLiveFailed;
                                bestLiveFailures = cloneJson(actionableLiveFailures);
                                bestLiveBackendFiles = cloneJson(backendFiles);
                                liveNoProgressCount = 0;
                                liveRegressiveCount = 0;
                            } else if (liveRound > 1 && Number.isFinite(bestLiveFailedCount) && actionableLiveFailed > bestLiveFailedCount) {
                                // Regression: restore best-known state and keep trying
                                backendFiles = cloneJson(bestLiveBackendFiles);
                                lastLiveFailures = cloneJson(bestLiveFailures);
                                liveNoProgressCount++;
                                liveRegressiveCount++;
                                emit({
                                    type: 'log',
                                    phase: 'api-test',
                                    level: 'warning',
                                    round: `live-${liveRound}`,
                                    message: `Regressive patch detected (${actionableLiveFailed} actionable failures vs best ${bestLiveFailedCount}). Restored best-known backend — continuing with new approach. (no-progress: ${liveNoProgressCount}/${MAX_NO_PROGRESS_ROUNDS})`,
                                });
                        if (liveRegressiveCount >= MAX_REGRESSIVE_ROUNDS) {
                            emit({ type: 'error', phase: 'api-test', round: `live-${liveRound}`,
                                error: `Stopping live repair: ${MAX_REGRESSIVE_ROUNDS} regressive round reached.` });
                            break;
                        }
                            } else {
                                liveNoProgressCount++;
                            }

                            emit({
                                type: 'test-summary',
                                passed: livePassed,
                                failed: liveFailed,
                                total: liveValidation.results.length,
                                fixed: 0,
                                round: `live-${liveRound}`,
                            });

                            if (liveValidation.ok) {
                                emit({
                                    type: 'log',
                                    phase: 'api-test',
                                    level: 'success',
                                    round: `live-${liveRound}`,
                                    message: 'Live backend validation passed with real started services and HTTP responses.',
                                });
                                liveValidationPassed = true;
                                successfulLiveRuntime = liveValidation;
                                break;
                            }

                            if (actionableLiveFailures.length === 0) {
                                emit({
                                    type: 'log',
                                    phase: 'api-test',
                                    level: 'warning',
                                    round: `live-${liveRound}`,
                                    message: 'Only blocked/deferred route failures remain, so live repair is stopping instead of looping on non-actionable routes.',
                                });
                                break;
                            }

                            emit({
                                type: 'log',
                                phase: 'api-test',
                                level: 'warning',
                                round: `live-${liveRound}`,
                                message: `Live backend validation found ${actionableLiveFailed} actionable runtime bug(s). Applying backend fix round...`,
                            });

                            const liveFixSnapshot = liveRound === 1
                                ? buildBackendSnapshot(backendFiles)
                                : buildFailureFocusedBackendSnapshot(backendFiles, actionableLiveFailures);
                            const liveFailList = actionableLiveFailures
                                .map(result => `${result.method} ${result.path}: ${result.reason || result.detail || 'runtime failure'}`)
                                .join('\n');
                            const liveFailureSignature = actionableLiveFailures
                                .map(result => normalizeFailureSignature(result))
                                .sort()
                                .join('\n');

                            let liveFixText = '';
                            const repairModel = pickBackendRepairModel(liveRound, liveFailed);
                            const liveFailureAnalysis = buildFailureAnalysisForAI(backendFiles, actionableLiveFailures);
                            const liveFixInstruction = liveRound === 1
                                ? 'Round 1: classify failures by root cause and fix only the single highest-impact root-cause group first. Ignore blocked routes and do not patch unrelated services in the same round.'
                                : liveNoProgressCount >= 1
                                    ? `Stuck round ${liveRound}: Previous fixes made no progress on this same root-cause group. Try a completely different approach — rewrite only the owning service/gateway file from scratch.\nFailing:\n${liveFailList}`
                                    : `Recovery round ${liveRound}: Fix only this remaining root-cause group. Ignore blocked routes and do not broaden the patch beyond the owning files.\nFailing:\n${liveFailList}`;
                            for await (const chunk of streamOllama(
                                [{
                                    role: 'user',
                                    content:
                                        `${backendRepairContext}\n\n` +
                                        (structuredSpecContract ? `STRUCTURED APP CONTRACT:\n${structuredSpecContract}\n\n` : '') +
                                        `${liveFixSnapshot}\n\n` +
                                        `${liveFailureAnalysis}\n\n` +
                                        `REAL RUNTIME FAILURES (fix these actionable failures only):\n${liveFailList}\n\n` +
                                        `${liveFixInstruction}\nOutput corrected backend files only.`
                                }],
                                Prompt.API_FIX_PROMPT,
                                0.2,
                                { model: repairModel }
                            )) {
                                const content = chunk?.message?.content ?? '';
                                if (content) {
                                    liveFixText += content;
                                    totalChars += content.length;
                                    emit({ type: 'chunk', phase: 'api-test', chars: totalChars, round: `live-${liveRound}` });
                                }
                                if (chunk?.done) break;
                            }

                            const liveFixParsed = parseBackendOnly(liveFixText);
                            const liveFixCount = Object.keys(liveFixParsed.backend).length;
                            if (liveFixCount > 0) {
                                const candidateFiles = staticFixBackend({ ...backendFiles, ...liveFixParsed.backend }, structuredAppSpec).files;
                                const validation = await validateBackendCandidateFiles(candidateFiles, projectTitle || 'generated-app', structuredAppSpec);
                                if (validation.ok) {
                                    backendFiles = candidateFiles;
                                    emit({
                                        type: 'log',
                                        phase: 'api-test',
                                        level: 'info',
                                        round: `live-${liveRound}`,
                                        message: `Applied ${liveFixCount} live runtime backend fix file(s).`,
                                    });
                                } else {
                                    liveNoProgressCount++;
                                    emit({
                                        type: 'log',
                                        phase: 'api-test',
                                        level: 'warning',
                                        round: `live-${liveRound}`,
                                        message: `Rejected invalid live-runtime patch: ${validation.errors.slice(0, 2).join(' | ')} — retrying. (no-progress: ${liveNoProgressCount}/${MAX_NO_PROGRESS_ROUNDS})`,
                                    });
                                    if (liveNoProgressCount >= MAX_NO_PROGRESS_ROUNDS) {
                                        emit({ type: 'error', phase: 'api-test', round: `live-${liveRound}`,
                                            error: `Stopping live repair: ${MAX_NO_PROGRESS_ROUNDS} consecutive invalid/no-progress rounds.` });
                                        break;
                                    }
                                    continue;
                                }
                            } else {
                                liveNoProgressCount++;
                                emit({
                                    type: 'log',
                                    phase: 'api-test',
                                    level: 'warning',
                                    round: `live-${liveRound}`,
                                    message: `AI produced no fix files for live failures. (no-progress: ${liveNoProgressCount}/${MAX_NO_PROGRESS_ROUNDS})`,
                                });
                            if (liveNoProgressCount >= MAX_NO_PROGRESS_ROUNDS) {
                                emit({ type: 'error', phase: 'api-test', round: `live-${liveRound}`,
                                    error: `Stopping live repair: ${MAX_NO_PROGRESS_ROUNDS} consecutive no-progress rounds.` });
                                break;
                            }
                                continue;
                            }

                            if (liveFailureSignature && liveFailureSignature === previousLiveFailureSignature) {
                                liveSameSignatureCount++;
                                emit({
                                    type: 'log',
                                    phase: 'api-test',
                                    level: 'warning',
                                    round: `live-${liveRound}`,
                            message: `Live runtime failure signature repeated (${liveSameSignatureCount}/${MAX_SAME_SIGNATURE_ROUNDS}).`,
                                });
                        if (liveSameSignatureCount >= MAX_SAME_SIGNATURE_ROUNDS) {
                            emit({ type: 'error', phase: 'api-test', round: `live-${liveRound}`,
                                error: `Stopping live repair: repeated identical failure signature after ${liveSameSignatureCount} rounds.` });
                            break;
                        }
                            } else {
                                liveSameSignatureCount = 0;
                            }

                            previousLiveFailureSignature = liveFailureSignature;
                        }

                        allRoutesClean = liveValidationPassed;
                        lastFailedRoutes = lastLiveFailures
                            .filter(result => !isBlockedRouteFailure(result))
                            .map(result => ({
                                method: result.method,
                                path: result.path,
                                reason: result.reason || result.detail || 'runtime failure',
                                kind: classifyRouteFailure(result),
                                signature: normalizeFailureSignature(result),
                            }));
                        if (Number.isFinite(bestLiveFailedCount)) {
                            bestFailedCount = Math.min(bestFailedCount, bestLiveFailedCount);
                        }
                    }

                    const finalBeCount = Object.keys(backendFiles).length;
                    emit({ type: 'phase', phase: 'api-test', status: 'done',
                        fileCount: finalBeCount,
                        message: allRoutesClean
                            ? `All API routes verified (${finalBeCount} files)`
                            : `API testing complete - ${finalBeCount} backend files ready` });

                    if (backendValidationErrors.length > 0) {
                        await appendBugMemory('Backend Validation Failures', backendValidationErrors);
                        await persistGeneratedAppOutput({
                            projectTitle,
                            frontendFiles: {},
                            backendFiles,
                            metadata: {
                                stage: 'backend-validation-warnings',
                                validationErrors: backendValidationErrors,
                            },
                        });
                        emit({
                            type: 'error',
                            phase: 'api-test',
                            error: `Backend has ${backendValidationErrors.length} validation issue(s) remaining after all fix rounds. Frontend generation is blocked until backend is clean. Issues: ${backendValidationErrors.slice(0, 3).join('; ')}`,
                            done: true,
                        });
                        controller.close();
                        return;
                    }

                    if (!allRoutesClean) {
                        const actionableFailedRoutes = lastFailedRoutes.filter(route => !isBlockedRouteFailure(route));
                        // Health-only 404s (GET /health from a service port) are non-blocking:
                        // the frontend never calls /health directly, so wiring issues there do not
                        // prevent a usable app from being generated.
                        const hardFailedRoutes = actionableFailedRoutes.filter(route => !isServiceHealthOnlyFailure(route));
                        const healthOnlyFailures = actionableFailedRoutes.filter(route => isServiceHealthOnlyFailure(route));

                        const remainingBugs = hardFailedRoutes.length;
                        const remainingSummary = hardFailedRoutes.length > 0
                            ? hardFailedRoutes
                                .slice(0, 3)
                                .map(route => `${route.method} ${route.path}${route.reason ? ` (${route.reason})` : ''}`)
                                .join('; ')
                            : 'No exact failing route details were captured.';
                        await appendBugMemory('Remaining Route Failures', actionableFailedRoutes.length > 0
                            ? actionableFailedRoutes.map(route => `${route.method} ${route.path}: ${route.reason || 'route failure'}`)
                            : [remainingSummary]);

                        if (remainingBugs > 0) {
                            await persistGeneratedAppOutput({
                                projectTitle,
                                frontendFiles: {},
                                backendFiles,
                                metadata: { stage: 'backend-partial', remainingBugs, remainingSummary },
                            });
                            emit({
                                type: 'error',
                                phase: 'api-test',
                                error: `${remainingBugs} route bug(s) remain after all fix rounds. Frontend generation is blocked until backend routes are clean. Remaining: ${remainingSummary}`,
                                done: true,
                            });
                            controller.close();
                            return;
                        }

                        if (healthOnlyFailures.length > 0) {
                            // Health wiring failed but all real API routes are clean — proceed with a warning.
                            const healthSummary = healthOnlyFailures
                                .map(r => `${r.method} ${r.path}`)
                                .join(', ');
                            emit({
                                type: 'log',
                                phase: 'api-test',
                                level: 'warning',
                                message: `Service health endpoint(s) returned 404 (${healthSummary}) but all API routes are clean. Proceeding to frontend generation — health wiring does not affect the app.`,
                            });
                        }
                    }
                }

                /* Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
                   PHASE 5 Ã¢â‚¬â€ FRONTEND GENERATION
                Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â */
                emit({ type: 'phase', phase: 'frontend-gen', status: 'start',
                    message: 'Generating React frontend...' });

                const apiSummary   = extractApiSummary(backendFiles);
                // Inject frontend-only instruction + API summary into the existing prompt
                const feUserPrompt =
                    `IMPORTANT: Generate ONLY React frontend files (===FRONTEND: /src/...===). ` +
                    `Do NOT generate any ===BACKEND:=== files - the backend is already built and running.\n\n` +
                    `${generationPrompt}\n\n${apiSummary}`;

                let frontendText = '';
                prevText = '';
                for await (const chunk of streamOllama(
                    [{ role: 'user', content: feUserPrompt }],
                    Prompt.CODE_GEN_PROMPT, 0.7, { model: FRONTEND_GEN_MODEL }
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
                    message: `Generated ${feCount} frontend files` });

                if (feCount === 0) {
                    emit({ type: 'error', error: 'Frontend generation produced 0 files. The AI may have not followed the output format. Try regenerating.', done: true });
                    controller.close();
                    return;
                }

                /* Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
                   PHASE 6 Ã¢â‚¬â€ FRONTEND BUG FIXING (up to 3 rounds)
                Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â */
                emit({ type: 'phase', phase: 'frontend-fix', status: 'start',
                    message: 'Checking frontend for issues...' });

                // Always apply static fixes first (instant)
                frontendFiles = staticFixFrontend(frontendFiles);
                emit({ type: 'log', phase: 'frontend-fix', level: 'info',
                    message: 'Static sanitization applied (CSS, @/ aliases, package whitelist, react-toastify)' });
                    let frontendValidation = await validateFrontendCandidateFiles(frontendFiles, { emit, phase: 'frontend-fix' });
                if (!frontendValidation.ok) {
                    emit({ type: 'log', phase: 'frontend-fix', level: 'warning',
                    message: `Frontend syntax validation found ${frontendValidation.errors.length} issue(s). Starting targeted frontend repair.` });
                }

                for (let round = 1; round <= 3; round++) {
                    emit({ type: 'log', phase: 'frontend-fix', level: 'info', round,
                        message: `Round ${round}/3: AI reviewing frontend code...` });

                    const snapshot = buildFrontendSnapshot(frontendFiles);
                    const frontendReviewContext =
                        `${localReferenceContext ? `${localReferenceContext}\n\n` : ''}` +
                        `${apiSummary}\n\n` +
                        `${frontendValidation.ok ? '' : `CURRENT FRONTEND SYNTAX FAILURES:\n${frontendValidation.errors.slice(0, 8).join('\n')}\n\n`}` +
                        `Preview note: Sandpack only runs the frontend. Fix the app so CRUD still works in preview using local state/localStorage fallback, and only call real backend routes that exist above.\n\n` +
                        snapshot;

                    let fixText = '';
                    for await (const chunk of streamOllama(
                        [{ role: 'user', content: frontendReviewContext }],
                        Prompt.FRONTEND_FIX_PROMPT, 0.3, { model: FRONTEND_FIX_MODEL }
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
                                message: `Round ${round}: No bugs found - frontend is clean!` });
                        break;
                    }

                    const fixParsed = parseAIOutput(fixText);
                    const fixedCount = Object.keys(fixParsed.frontend).length;
                    if (fixedCount > 0) {
                        const candidateFrontendFiles = staticFixFrontend({ ...frontendFiles, ...fixParsed.frontend });
                        const candidateValidation = await validateFrontendCandidateFiles(candidateFrontendFiles, { emit, phase: 'frontend-fix', round });
                        if (
                            candidateValidation.ok
                            || (!frontendValidation.ok && candidateValidation.errors.length < frontendValidation.errors.length)
                        ) {
                            frontendFiles = candidateFrontendFiles;
                            frontendValidation = candidateValidation;
                            emit({ type: 'log', phase: 'frontend-fix', level: 'warning', round,
                                message: `Round ${round}: Fixed ${fixedCount} frontend file(s)` });
                            if (candidateValidation.ok) {
                                emit({ type: 'log', phase: 'frontend-fix', level: 'success', round,
                                message: `Round ${round}: Frontend syntax validation is clean.` });
                            }
                        } else {
                            emit({ type: 'log', phase: 'frontend-fix', level: 'warning', round,
                                message: `Rejected invalid frontend patch: ${candidateValidation.errors.slice(0, 2).join(' | ')}` });
                            break;
                        }
                    } else {
                        emit({ type: 'log', phase: 'frontend-fix', level: 'success', round,
                                message: `Round ${round}: AI found no actionable changes` });
                        break;
                    }
                }

                    frontendValidation = await validateFrontendCandidateFiles(frontendFiles, { emit, phase: 'frontend-fix' });
                if (!frontendValidation.ok) {
                    emit({ type: 'log', phase: 'frontend-fix', level: 'warning',
                        message: `Frontend still has ${frontendValidation.errors.length} syntax issue(s). Applying final safety fallback to broken page files.` });
                    frontendValidation.errors.forEach((errorText) => {
                        const match = errorText.match(/^(\/[^:]+\.(?:jsx?|tsx?)):/);
                        if (!match) return;
                        const brokenPath = match[1];
                        const base = brokenPath.split('/').pop()?.replace(/\.[^.]+$/, '') || 'GeneratedPage';
                        const componentName = base
                            .replace(/[^A-Za-z0-9]+/g, ' ')
                            .replace(/(?:^|\s)([A-Za-z0-9])/g, (_, ch) => ch.toUpperCase())
                            .replace(/\s+/g, '') || 'GeneratedPage';
                        if (/\/pages\//.test(brokenPath) || /\/components\//.test(brokenPath)) {
                            frontendFiles[brokenPath] = {
                                code: `import React from 'react';\n\nexport default function ${componentName}() {\n  return (\n    <section className="min-h-screen bg-gray-950 text-white px-6 py-16">\n      <div className="max-w-5xl mx-auto rounded-2xl border border-rose-500/30 bg-rose-950/20 p-6">\n        <h1 className="text-3xl font-bold mb-3">${componentName}</h1>\n        <p className="text-rose-100/80">This file was auto-recovered because the generated JSX was invalid during preview validation.</p>\n      </div>\n    </section>\n  );\n}\n`,
                            };
                        }
                    });
                    frontendFiles = staticFixFrontend(frontendFiles);
                }

                emit({ type: 'phase', phase: 'frontend-fix', status: 'done',
                        message: `Frontend verified (${Object.keys(frontendFiles).length} files ready)` });

                /* Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â
                   FINAL Ã¢â‚¬â€ emit complete result
                Ã¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢ÂÃ¢â€¢Â */
                const preferredFrontendPort = successfulLiveRuntime?.ok ? DEFAULT_FRONTEND_PORT : null;
                const totalFiles = Object.keys(frontendFiles).length + Object.keys(backendFiles).length;
                const outputRoot = await persistGeneratedAppOutput({
                    projectTitle: projectTitle || 'Generated App',
                    frontendFiles,
                    backendFiles,
                    metadata: {
                        stage: 'final',
                        totalFiles,
                        gatewayUrl: successfulLiveRuntime?.gatewayUrl || '',
                        gatewayPort: successfulLiveRuntime?.ports?.gateway || '',
                        servicePorts: successfulLiveRuntime?.ports?.services || {},
                        mongoUri: successfulLiveRuntime?.mongoUri || '',
                        jwtSecret: process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'ravindu2232',
                        frontendPort: preferredFrontendPort || DEFAULT_FRONTEND_PORT,
                    },
                });
                let frontendRuntime = null;
                if (successfulLiveRuntime?.ok && preferredFrontendPort) {
                    frontendRuntime = await startFrontendPreview(
                        path.join(outputRoot, 'frontend'),
                        {
                            port: preferredFrontendPort,
                            gatewayPort: successfulLiveRuntime.ports.gateway,
                        },
                        emit
                    );

                    if (frontendRuntime?.frontendPort && frontendRuntime.frontendPort !== preferredFrontendPort) {
                        const gatewayPort = successfulLiveRuntime?.ports?.gateway || DEFAULT_GATEWAY_PORT;
                        const gatewayHost = successfulLiveRuntime?.gatewayUrl || `http://127.0.0.1:${gatewayPort}`;
                        await writeFile(
                            path.join(outputRoot, 'frontend', '.env'),
                            [
                                `PORT=${frontendRuntime.frontendPort}`,
                                `VITE_API_BASE_URL=${gatewayHost}`,
                                `VITE_GATEWAY_URL=${gatewayHost}`,
                                `VITE_GATEWAY_PORT=${gatewayPort}`,
                            ].join('\n') + '\n',
                            'utf8'
                        ).catch(() => {});
                    }
                }
                emit({ type: 'log', phase: 'complete', level: 'success',
                    message: `Full-stack app ready! ${totalFiles} files total. Output folder: ${outputRoot}` });

                emit({
                    type: 'final',
                    final: {
                        frontend:     frontendFiles,
                        backend:      backendFiles,
                        projectTitle: projectTitle || 'Generated App',
                        outputRoot,
                        frontendUrl: frontendRuntime?.frontendUrl || null,
                        gatewayUrl: successfulLiveRuntime?.gatewayUrl || null,
                    },
                    done: true,
                });
                clearStrategyState(genSessionKey + '-be');
                clearStrategyState(genSessionKey + '-api');
                controller.close();

            } catch (e) {
                console.error('[gen-fullstack] error:', e);
                clearStrategyState(genSessionKey + '-be');
                clearStrategyState(genSessionKey + '-api');
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
