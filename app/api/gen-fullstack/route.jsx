import { spawn } from 'node:child_process';
import { mkdir, writeFile, rm, readFile, access } from 'node:fs/promises';
import net from 'node:net';
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

const MAX_BACKEND_FIX_ROUNDS = 10;
const MAX_API_FIX_ROUNDS = 10;
const MAX_LIVE_FIX_ROUNDS = 10;
const MIN_BACKEND_BUGS_TO_BLOCK_FRONTEND = 3;
const BUG_MEMORY_PATH = path.join(process.cwd(), 'memory.md');
const BUG_SKILL_PATH = path.join(process.cwd(), 'skills', 'ai-web-builder-backend-recovery', 'SKILL.md');

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
            '- Round 1 must fix every currently known backend bug in one pass.',
            '- Rounds 2-5 are recovery rounds for exact remaining failures only.',
            '- Stop early as soon as every backend bug is fixed; do not spend extra rounds after the backend is clean.',
            '- If a failure repeats, rewrite the owning route file and related gateway/service registration completely instead of making a tiny patch.',
            '- Do not leave a known failing route for later rounds if its owning file is already being edited.',
        ].join('\n')
    );

    return sections.join('\n\n').trim();
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
    const frontendPort = Number(metadata.frontendPort || 3010);
    const gatewayPort = Number(gatewayPortMatch?.[1] || metadata.gatewayPort || 3005);
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
            const code = typeof content === 'string' ? content : content?.code || '';
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
            lines.push(`- ${service.name}${service.port ? ` (preferred port ${service.port})` : ''}: ${service.description || 'Implement fully.'}`);
            if (service.entities.length) {
                lines.push(`  Entities: ${service.entities.join(', ')}`);
            }
            if (service.dependencies.length) {
                lines.push(`  Dependencies: ${service.dependencies.join(', ')}`);
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

async function validateBackendCandidateFiles(backendFiles, projectTitle = 'generated-app', structuredSpec = null) {
    const errors = [];
    const contracts = parseBackendContracts(backendFiles);
    const backendPaths = Object.keys(backendFiles);
    const packagePaths = backendPaths.filter((filePath) => filePath.endsWith('package.json'));
    if (packagePaths.length === 0) {
        return { ok: false, errors: ['Missing package.json in generated backend output'] };
    }
    if (backendPaths.length < 6 && contracts.length === 0) {
        return { ok: false, errors: ['Backend output is too small and contains no parseable routes'] };
    }
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

        const requireMatches = [...code.matchAll(/require\(\s*['"](\.[^'"]+)['"]\s*\)/g)];
        requireMatches.forEach((match) => {
            const requestPath = match[1];
            const candidates = resolveLocalRequireCandidates(filePath, requestPath);
            const found = candidates.some(candidate => backendFiles[candidate]);
            if (!found) {
                errors.push(`${filePath}: missing local require ${requestPath}`);
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
    let nextFallbackPort = 3006;
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
    lines.push('Backend API (Gateway port 3005):');
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
        const proxyPrefix = proxyList.find(prefix => prefix === `/api/${resourceName}`)
            || proxyList.find(prefix => prefix === `/api/${singularName}`)
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
function staticFixBackend(backendFiles) {
    const sanitizeBackendCode = (code) =>
        code
            .replace(/\uFEFF/g, '')
            .replace(/[^\x09\x0A\x0D\x20-\x7E]/g, '');

    const topology = inferBackendPortTopology(backendFiles);
    const serviceRouteMounts = collectServiceRouteMounts(backendFiles);
    const fixed = {};
    let fixCount = 0;
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
            if (!code.includes('3005')) {
                code = code.replace(/app\.listen\(\s*(\d{4})\s*[,)]/g, (m, p) => p !== '3005' ? `app.listen(3005,` : m);
                changed = true;
            }
            code = code.replace(
                /const\s+(PORT|port)\s*=\s*[^;]+;/g,
                'const PORT = Number(process.env.PORT_GATEWAY || process.env.PORT || 3005);'
            );
            code = code.replace(
                /process\.env\.PORT\s*\|\|\s*\d+/g,
                'process.env.PORT_GATEWAY || process.env.PORT || 3005'
            );
            code = code.replace(/app\.listen\(\s*(?:\d+|process\.env\.[A-Z_]+[^,)]*|PORT)\s*,/g, 'app.listen(PORT,');
            if (!/const\s+PORT\s*=/.test(code) && /app\.listen\(PORT,/.test(code)) {
                code = code.replace(
                    /app\.use\(express\.json\(\)\);/,
                    'app.use(express.json());\nconst PORT = Number(process.env.PORT_GATEWAY || process.env.PORT || 3005);'
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
        if (path.includes('-service') && path.endsWith('index.js')) {
            const serviceConfig = topology.serviceConfigs[serviceName] || {
                envVar: 'PORT_SERVICE',
                originalPort: '3006',
            };
            const slotEnvName = serviceConfig.envVar;
            const fallbackPort = Number(serviceConfig.originalPort || 3006);
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
            code = code.replace(
                /mongoose\.connect\(\s*(['"`])([^'"`]+)\1/g,
                (match, quote, uri) => uri.startsWith('mongodb://')
                    ? `mongoose.connect(process.env.MONGODB_URI || process.env.MONGO_URL || ${quote}${uri}${quote}`
                    : match
            );
            code = code.replace(
                /const\s+(PORT|port)\s*=\s*[^;]+;/g,
                `const PORT = Number(process.env.PORT || process.env.${slotEnvName} || ${fallbackPort});`
            );
            code = code.replace(/process\.env\.PORT\s*\|\|\s*\d+/g, `process.env.PORT || process.env.${slotEnvName} || ${fallbackPort}`);
            code = code.replace(/app\.listen\(\s*[^,]+,\s*/g, 'app.listen(PORT, ');
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
            if (!/const\s+PORT\s*=/.test(code) && /app\.listen\(PORT,/.test(code)) {
                code = code.replace(
                    /app\.use\(express\.json\(\)\);/,
                    `app.use(express.json());\nconst PORT = Number(process.env.PORT || process.env.${slotEnvName} || ${fallbackPort});`
                );
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

            code = code.replace(/res\.json\(([^{][^)]+)\)/g, (m, inner) => {
                if (inner.includes('success')) return m;
                return `res.json({ success: true, data: ${inner} })`;
            });
        }
        if (code !== originalCode) changed = true;
        if (changed) fixCount++;
        fixed[path] = { code };
    });
    return { files: fixed, fixCount };
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

async function validateFrontendCandidateFiles(frontendFiles) {
    const candidateEntries = Object.entries(frontendFiles || {}).filter(([filePath]) => /\.(jsx?|tsx?)$/i.test(filePath));
    if (candidateEntries.length === 0) {
        return { ok: true, errors: [] };
    }

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
            const code = typeof content === 'string' ? content : content?.code || '';

            await mkdir(path.dirname(targetPath), { recursive: true });
            await writeFile(targetPath, code, 'utf8');
            manifest.push({ filePath, diskPath: targetPath });
        }

        const manifestPath = path.join(tempRoot, 'manifest.json');
        await writeFile(manifestPath, JSON.stringify(manifest), 'utf8');

        const validatorScript = `
const fs = require('node:fs');
const { transformSync } = require('esbuild');

const manifest = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
const errors = [];

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

process.stdout.write(JSON.stringify(errors));
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
        let code = typeof content === 'string' ? content : content?.code || '';
        code = repairCommonFrontendSyntax(code);
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
        return true;
    }

    return ['install', 'start', 'run'].includes(firstArg);
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
    const knownUserId = createdRecords['/api/users']?.id || '507f1f77bcf86cd799439011';
    const knownTaskId = createdRecords['/api/tasks']?.id || '507f1f77bcf86cd799439012';
    const knownColumnId = createdRecords['/api/columns']?.id || '507f1f77bcf86cd799439013';
    const normalizedEnumValues = Array.isArray(enumValues)
        ? enumValues.map((value) => String(value).trim()).filter(Boolean)
        : [];

    if (normalizedEnumValues.length > 0) return normalizedEnumValues[0];

    if (lowerName.includes('email')) return getLiveSampleStateValue(sampleState, 'auth.email', () => `john+${sampleState.seed}@example.com`);
    if (lowerName.includes('username')) return getLiveSampleStateValue(sampleState, 'auth.username', () => `john_${String(sampleState.seed).replace(/[^a-z0-9]/gi, '').toLowerCase()}`);
    if (lowerName.includes('displayname')) return `John Tester ${String(sampleState.seed).slice(-4)}`;
    if (lowerName === 'name') return getLiveSampleStateValue(sampleState, 'generic.name', () => `Sample ${sampleState.seed}`);
    if (lowerName.includes('title')) return 'Test Task';
    if (lowerName.includes('description')) return 'Generated sample description';
    if (lowerName.includes('priority')) return 'high';
    if (lowerName.includes('status')) return 'todo';
    if (lowerName.includes('password')) return getLiveSampleStateValue(sampleState, 'auth.password', () => `SecurePass123!${String(sampleState.seed).slice(-4)}`);
    if (lowerName.includes('theme')) return 'dark';
    if (lowerName === 'action') return 'created';
    if (lowerName.includes('createdby') || lowerName.includes('userid') || lowerName === 'user') return knownUserId;
    if (lowerName.includes('assignee')) return knownUserId;
    if (lowerName.includes('taskid')) return knownTaskId;
    if (lowerName.includes('columnid')) return knownColumnId;
    if (lowerName.includes('sku')) return getLiveSampleStateValue(sampleState, 'product.sku', () => `sku-${sampleState.seed}`);
    if (lowerName.includes('slug')) return getLiveSampleStateValue(sampleState, 'product.slug', () => `item-${sampleState.seed}`);
    if (lowerName.includes('brand')) return getLiveSampleStateValue(sampleState, 'product.brand', () => `Brand ${sampleState.seed}`);
    if (lowerName.includes('category')) return createdRecords['/api/categories']?.payload?.name || getLiveSampleStateValue(sampleState, 'category.name', () => `Category ${sampleState.seed}`);
    if (lowerName.includes('position')) return 0;
    if (lowerName.includes('count') || lowerName.includes('total')) return 1;
    if (lowerName.includes('date') || lowerName.includes('deadline')) return new Date().toISOString();

    if (normalizedType.includes('objectid')) return knownUserId;
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
                child = spawn(command, normalizedArgs, {
                    cwd,
                    env,
                    shell: shellMode,
                    windowsHide: true,
                });
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
            const code = typeof content === 'string' ? content : content?.code || '';
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
                : (ports.services[dirName] || Number(config?.originalPort || 3006));
            const serviceEnvLines = [
                ...envLines.filter((line) => !line.startsWith('PORT=')),
                `PORT=${servicePort}`,
            ];
            await writeFile(path.join(rootDir, dirName, '.env'), `${serviceEnvLines.join('\n')}\n`, 'utf8').catch(() => {});
        })
    );
    return rootDir;
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
            child = spawn(launchCommand, launchArgs, {
                cwd,
                env,
                shell: shellMode,
                windowsHide: true,
            });
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
    emit({
        type: 'log',
        phase: 'frontend-gen',
        level: 'info',
        message: `Starting local frontend on port ${port} (proxy -> ${gatewayPort})...`,
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
                PORT: String(port),
                VITE_FRONTEND_PORT: String(port),
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
        child = spawn(npmCommand(), ['run', 'dev', '--', '--port', String(port)], {
            cwd,
            env: {
                ...process.env,
                NODE_ENV: 'development',
                PORT: String(port),
                VITE_FRONTEND_PORT: String(port),
                VITE_API_BASE_URL: `http://127.0.0.1:${gatewayPort}`,
                VITE_GATEWAY_URL: `http://127.0.0.1:${gatewayPort}`,
                VITE_GATEWAY_PORT: String(gatewayPort),
            },
            shell: shellMode,
            windowsHide: true,
        });
        attachListeners(child, launchId);
    };

    launch();
    await delay(500);
    if (launchError) throw launchError;
    emit({
        type: 'log',
        phase: 'frontend-gen',
        level: 'info',
        message: `Waiting for local frontend to respond at http://127.0.0.1:${port} or http://localhost:${port} ...`,
    });
    const frontendCandidates = [
        `http://127.0.0.1:${port}`,
        `http://localhost:${port}`,
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
        process: child,
        getStdout: () => stdout,
        getStderr: () => stderr,
    };
}

async function stopBackendProcesses(processes = []) {
    await Promise.all(
        processes.map(async (service) => {
            if (!service?.child || service.child.killed) {
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

async function runLiveBackendValidation(backendFiles, simulatedResults, emit, { projectTitle, keepAliveOnSuccess = false } = {}) {
    const topology = inferBackendPortTopology(backendFiles);
    const servicePorts = {};
    for (const dirName of topology.serviceDirs) {
        servicePorts[dirName] = await getFreePort();
    }
    const ports = {
        gateway: await getFreePort(),
        services: servicePorts,
    };
    const fallbackDbName = `ai-website-builder-live-${Date.now()}`;
    const mongoUri = resolveMongoUri(
        process.env.MONGODB_URI || process.env.MONGO_URL,
        fallbackDbName
    ) || `mongodb://127.0.0.1:27017/${fallbackDbName}`;
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
        emit({ type: 'log', phase: 'api-test', level: 'info', message: `Local backend workspace: ${rootDir}` });
        const livePortSummary = ['gateway ' + ports.gateway]
            .concat(serviceDirs.map(dirName => `${dirName} ${runtimePortByService[dirName]}`))
            .join(', ');
        emit({ type: 'log', phase: 'api-test', level: 'info', message: `Live ports: ${livePortSummary}` });
        emit({ type: 'log', phase: 'api-test', level: 'info', message: `Live gateway URL: http://127.0.0.1:${ports.gateway}` });
        emit({ type: 'log', phase: 'api-test', level: 'info', message: `Local MongoDB URI: ${mongoUri}` });

        for (const dirName of packageDirs) {
            emit({ type: 'log', phase: 'api-test', level: 'info', message: `Installing backend dependencies in ${dirName}...` });
            const install = await runCommand(npmCommand(), ['install', '--no-fund', '--no-audit'], {
                cwd: path.join(rootDir, dirName),
                env,
                timeoutMs: 180000,
            });

            if (install.code !== 0) {
                throw new Error(`npm install failed in ${dirName}: ${install.stderr || install.stdout}`);
            }

        }

        for (const dirName of serviceDirs) {
            const port = runtimePortByService[dirName];
            emit({
                type: 'log',
                phase: 'api-test',
                level: 'info',
                message: `[live-start] Starting ${dirName} on port ${port}...`,
            });
            const serviceEnv = {
                ...env,
                PORT: String(port),
            };
            const service = await startBackendService(dirName, path.join(rootDir, dirName), serviceEnv, emit);
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
            await stopBackendProcesses(liveProcesses);
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
                const structuredAppSpec = extractStructuredAppSpec(prompt);
                const structuredSpecContract = buildStructuredSpecContract(structuredAppSpec);
                const generationPrompt = structuredSpecContract
                    ? `${prompt}\n\n${structuredSpecContract}`
                    : prompt;

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
                    const backendRepairContext = await loadBackendRepairContext();

                    // Round 0 Ã¢â‚¬â€ static fixes (instant, no AI)
                    const { files: staticFixed, fixCount } = staticFixBackend(backendFiles);
                    backendFiles = staticFixed;
                    if (fixCount > 0) {
                        emit({ type: 'log', phase: 'backend-fix', level: 'info',
                            message: `Static analysis fixed ${fixCount} files (ports, middleware, CORS, proxy safety)` });
                    } else {
                        emit({ type: 'log', phase: 'backend-fix', level: 'success',
                            message: 'Static analysis: no quick-fix issues found' });
                    }

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

                    for (let round = 1; round <= MAX_BACKEND_FIX_ROUNDS; round++) {
                        emit({ type: 'log', phase: 'backend-fix', level: 'info', round,
                            message: `Round ${round}/${MAX_BACKEND_FIX_ROUNDS}: AI reviewing backend code...` });

                        // Build snapshot (limit to avoid huge prompts)
                        const snapshot = buildBackendSnapshot(backendFiles, {
                            maxFiles: 12,
                            maxCharsPerFile: 5000,
                            maxTotalChars: 32000,
                        });

                        let fixText = '';
                        const repairModel = pickBackendRepairModel(round, Object.keys(backendFiles).length);
                        const roundInstruction = round === 1
                            ? 'This is round 1. Deeply analyze the backend as a whole and fix every backend bug you can see in one complete pass. Prefer broader startup, gateway, route, and model file rewrites over partial patches if that increases the chance of ending backend fixes in round 1.'
                            : `This is recovery round ${round}. Only exact leftovers from earlier rounds should remain. Finish every remaining blocker now and do not revisit already-clean files unless they are directly related.`;
                        for await (const chunk of streamOllama(
                            [{
                                role: 'user',
                                content:
                                    `${backendRepairContext}\n\n` +
                                    (structuredSpecContract ? `STRUCTURED APP CONTRACT:\n${structuredSpecContract}\n\n` : '') +
                                    `BACKEND SNAPSHOT:\n${snapshot}\n\n` +
                                    (!currentBackendValidation.ok
                                        ? `CURRENT VALIDATION ERRORS:\n${currentBackendValidation.errors.join('\n')}\n\n`
                                        : '') +
                                    `${roundInstruction}`
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
                            const candidateFiles = staticFixBackend({ ...backendFiles, ...fixParsed.backend }).files;
                            const validation = await validateBackendCandidateFiles(candidateFiles, projectTitle || 'generated-app', structuredAppSpec);
                            if (validation.ok) {
                                backendFiles = candidateFiles;
                                currentBackendValidation = validation;
                                emit({ type: 'log', phase: 'backend-fix', level: 'warning', round,
                                    message: `Round ${round}: Fixed ${fixedCount} backend file(s)` });
                            } else {
                                emit({
                                    type: 'log',
                                    phase: 'backend-fix',
                                    level: 'warning',
                                    round,
                                    message: `Rejected invalid backend patch for round ${round}: ${validation.errors.slice(0, 2).join(' | ')}`,
                                });
                                currentBackendValidation = validation;
                                continue;
                            }
                        } else {
                            if (currentBackendValidation.ok) {
                                emit({ type: 'log', phase: 'backend-fix', level: 'success', round,
                                    message: `Round ${round}: No bugs found - backend is clean!` });
                                break;
                            }
                            emit({
                                type: 'log',
                                phase: 'backend-fix',
                                level: 'warning',
                                round,
                                message: `Round ${round}: AI found no actionable changes, but ${currentBackendValidation.errors.length} validation issue(s) still remain.`,
                            });
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
                    const backendRepairContext = await loadBackendRepairContext();
                    let previousFailureSignature = '';

                    for (let round = 1; round <= MAX_API_FIX_ROUNDS; round++) {
                        emit({ type: 'log', phase: 'api-test', level: 'info', round,
                            message: `Round ${round}/${MAX_API_FIX_ROUNDS}: Simulating request payloads, gateway routing, and MongoDB persistence for all routes...` });

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
                        const fixInstruction = round === 1
                            ? 'Round 1 must deeply analyze the full failure bundle and fix every currently failing route in one pass. If multiple failures share a file or root cause, rewrite that whole file completely.'
                            : `Recovery round ${round}: fix only these remaining routes and finish them now. Do not broaden the patch beyond files that own the failures unless gateway wiring or shared middleware is involved.`;
                        for await (const chunk of streamOllama(
                            [{ role: 'user', content:
                                `${backendRepairContext}\n\n` +
                                (structuredSpecContract ? `STRUCTURED APP CONTRACT:\n${structuredSpecContract}\n\n` : '') +
                                `${targetedSnapshot}\n\n` +
                                `${failureAnalysis}\n\n` +
                                `FAILED ROUTES THAT MUST BE FIXED:\n${failList}\n\n` +
                                `${fixInstruction}\nOutput the corrected files only.`
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
                            const candidateFiles = staticFixBackend({ ...backendFiles, ...fixParsed.backend }).files;
                        const validation = await validateBackendCandidateFiles(candidateFiles, projectTitle || 'generated-app', structuredAppSpec);
                            if (validation.ok) {
                                backendFiles = candidateFiles;
                                emit({ type: 'log', phase: 'api-test', level: 'info', round,
                                    message: `Applied fixes to ${fixedCount} file(s). Re-running tests next round...` });
                            } else {
                                emit({ type: 'log', phase: 'api-test', level: 'warning', round,
                                    message: `Rejected invalid API-fix patch: ${validation.errors.slice(0, 2).join(' | ')}` });
                                break;
                            }
                        } else {
                            emit({ type: 'log', phase: 'api-test', level: 'warning', round,
                                message: `Could not generate fixes automatically. Moving on.` });
                            break;
                        }

                        if (failureSignature && failureSignature === previousFailureSignature) {
                            emit({
                                type: 'log',
                                phase: 'api-test',
                                level: 'warning',
                                round,
                                message: 'Repeated failing-route signature detected. Stopping extra rounds and surfacing the exact remaining blockers.',
                            });
                            break;
                        }

                        previousFailureSignature = failureSignature;
                    }

                    if (allRoutesClean) {
                        let liveValidationPassed = false;
                        let lastLiveFailures = [];
                        let previousLiveFailureSignature = '';
                        let bestLiveFailedCount = Number.POSITIVE_INFINITY;
                        let bestLiveFailures = [];
                        let bestLiveBackendFiles = cloneJson(backendFiles);

                        for (let liveRound = 1; liveRound <= MAX_LIVE_FIX_ROUNDS; liveRound++) {
                            emit({
                                type: 'log',
                                phase: 'api-test',
                                level: 'info',
                                round: `live-${liveRound}`,
                                message: `Live backend round ${liveRound}/${MAX_LIVE_FIX_ROUNDS}: installing services, starting gateway + microservices, and running real HTTP requests...`,
                            });

                            const liveValidation = await runLiveBackendValidation(backendFiles, latestTestResults, emit, {
                                projectTitle,
                                keepAliveOnSuccess: true,
                            });
                            lastLiveFailures = liveValidation.failedResults;

                            const livePassed = liveValidation.results.filter(result => result.status === 'PASS').length;
                            const liveFailed = liveValidation.failedResults.length;
                            if (liveFailed < bestLiveFailedCount) {
                                bestLiveFailedCount = liveFailed;
                                bestLiveFailures = cloneJson(liveValidation.failedResults);
                                bestLiveBackendFiles = cloneJson(backendFiles);
                            } else if (liveRound > 1 && Number.isFinite(bestLiveFailedCount) && liveFailed > bestLiveFailedCount) {
                                backendFiles = cloneJson(bestLiveBackendFiles);
                                lastLiveFailures = cloneJson(bestLiveFailures);
                                emit({
                                    type: 'log',
                                    phase: 'api-test',
                                    level: 'warning',
                                    round: `live-${liveRound}`,
                                    message: `Rejected a regressive live-runtime patch: this round had ${liveFailed} failing routes, but the best previous round had ${bestLiveFailedCount}. Restored the best-known backend and stopped extra live rounds.`,
                                });
                                break;
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

                            emit({
                                type: 'log',
                                phase: 'api-test',
                                level: 'warning',
                                round: `live-${liveRound}`,
                                message: `Live backend validation found ${liveFailed} runtime bug(s). Applying another backend fix round...`,
                            });

                            const snapshot = liveRound === 1
                                ? buildBackendSnapshot(backendFiles)
                                : buildFailureFocusedBackendSnapshot(backendFiles, lastLiveFailures);
                            const liveFailList = lastLiveFailures
                                .map(result => `${result.method} ${result.path}: ${result.reason || result.detail || 'runtime failure'}`)
                                .join('\n');
                            const liveFailureSignature = lastLiveFailures
                                .map(result => `${result.method} ${result.path}: ${result.reason || result.detail || 'runtime failure'}`)
                                .sort()
                                .join('\n');

                            let liveFixText = '';
                            const repairModel = pickBackendRepairModel(liveRound, liveFailed);
                            const failureAnalysis = buildFailureAnalysisForAI(backendFiles, lastLiveFailures);
                            const liveFixInstruction = liveRound === 1
                                ? 'Round 1 must deeply analyze the full live runtime failure bundle and fix every live runtime failure in one pass. If startup, env wiring, proxy registration, or route mapping is involved, rewrite the owning startup file completely.'
                                : `Recovery round ${liveRound}: fix only the remaining live runtime failures and close them out now. Keep edits focused on the files that own these failures unless shared gateway/service wiring is the cause.`;
                            for await (const chunk of streamOllama(
                                [{
                                    role: 'user',
                                    content:
                                        `${backendRepairContext}\n\n` +
                                        (structuredSpecContract ? `STRUCTURED APP CONTRACT:\n${structuredSpecContract}\n\n` : '') +
                                        `${snapshot}\n\n` +
                                        `${failureAnalysis}\n\n` +
                                        `REAL RUNTIME FAILURES FROM STARTED SERVICES:\n${liveFailList}\n\n` +
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
                                const candidateFiles = staticFixBackend({ ...backendFiles, ...liveFixParsed.backend }).files;
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
                                    emit({
                                        type: 'log',
                                        phase: 'api-test',
                                        level: 'warning',
                                        round: `live-${liveRound}`,
                                        message: `Rejected invalid live-runtime patch: ${validation.errors.slice(0, 2).join(' | ')}`,
                                    });
                                    break;
                                }
                            } else {
                                break;
                            }

                            if (liveFailureSignature && liveFailureSignature === previousLiveFailureSignature) {
                                emit({
                                    type: 'log',
                                    phase: 'api-test',
                                    level: 'warning',
                                    round: `live-${liveRound}`,
                                    message: 'Live runtime failure signature repeated. Stopping extra live rounds and keeping the exact remaining blockers.',
                                });
                                break;
                            }

                            previousLiveFailureSignature = liveFailureSignature;
                        }

                        allRoutesClean = liveValidationPassed;
                        lastFailedRoutes = lastLiveFailures.map(result => ({
                            method: result.method,
                            path: result.path,
                            reason: result.reason || result.detail || 'runtime failure',
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
                        await persistGeneratedAppOutput({
                            projectTitle,
                            frontendFiles: {},
                            backendFiles,
                            metadata: {
                                stage: 'backend-validation-blocked',
                                validationErrors: backendValidationErrors,
                            },
                        });
                        emit({
                            type: 'error',
                            error: `Backend verification failed. ${backendValidationErrors.length} backend validation issue(s) still remain after auto-fix, so frontend generation is blocked until backend is valid. Remaining validation issues: ${backendValidationErrors.slice(0, 3).join('; ')}`,
                            done: true,
                        });
                        controller.close();
                        return;
                    }

                    if (!allRoutesClean) {
                        const remainingBugs = lastFailedRoutes.length > 0
                            ? lastFailedRoutes.length
                            : (Number.isFinite(bestFailedCount) && bestFailedCount > 0 ? bestFailedCount : 0);
                        const remainingSummary = lastFailedRoutes.length > 0
                            ? lastFailedRoutes
                                .slice(0, 3)
                                .map(route => `${route.method} ${route.path}${route.reason ? ` (${route.reason})` : ''}`)
                                .join('; ')
                            : 'No exact failing route details were captured.';
                        if (remainingBugs < MIN_BACKEND_BUGS_TO_BLOCK_FRONTEND) {
                            emit({
                                type: 'log',
                                phase: 'api-test',
                                level: 'warning',
                                message: `Backend verification still has ${remainingBugs} route bug(s), but that is below the frontend block threshold of ${MIN_BACKEND_BUGS_TO_BLOCK_FRONTEND}. Continuing to frontend generation. Remaining routes: ${remainingSummary}`,
                            });
                        } else {
                        await persistGeneratedAppOutput({
                            projectTitle,
                            frontendFiles: {},
                            backendFiles,
                            metadata: {
                                stage: 'backend-blocked',
                                remainingBugs,
                                remainingSummary,
                            },
                        });
                        emit({
                            type: 'error',
                            error: `Backend verification failed. ${remainingBugs} route bug(s) still remain after auto-fix, so frontend generation is blocked until backend is clean. Remaining routes: ${remainingSummary}`,
                            done: true,
                        });
                        controller.close();
                        return;
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
                let frontendValidation = await validateFrontendCandidateFiles(frontendFiles);
                if (!frontendValidation.ok) {
                    emit({ type: 'log', phase: 'frontend-fix', level: 'warning',
                    message: `Frontend syntax validation found ${frontendValidation.errors.length} issue(s). Starting targeted frontend repair.` });
                }

                for (let round = 1; round <= 3; round++) {
                    emit({ type: 'log', phase: 'frontend-fix', level: 'info', round,
                        message: `Round ${round}/3: AI reviewing frontend code...` });

                    const snapshot = buildFrontendSnapshot(frontendFiles);
                    const frontendReviewContext =
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
                        const candidateValidation = await validateFrontendCandidateFiles(candidateFrontendFiles);
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

                frontendValidation = await validateFrontendCandidateFiles(frontendFiles);
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
                const frontendLaunchPort = successfulLiveRuntime?.ok ? await getFreePort() : null;
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
                        frontendPort: frontendLaunchPort || 3010,
                    },
                });
                let frontendRuntime = null;
                if (successfulLiveRuntime?.ok && frontendLaunchPort) {
                    frontendRuntime = await startFrontendPreview(
                        path.join(outputRoot, 'frontend'),
                        {
                            port: frontendLaunchPort,
                            gatewayPort: successfulLiveRuntime.ports.gateway,
                        },
                        emit
                    );
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

