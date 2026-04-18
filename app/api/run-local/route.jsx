import { spawn } from 'node:child_process';
import { mkdir, writeFile, rm } from 'node:fs/promises';
import path from 'node:path';

const FRONTEND_PORT = 3010;
const GATEWAY_PORT = 3005;
const DEFAULT_SERVICE_PORT = 3006;

function slugify(value = 'generated-app') {
    return String(value || 'generated-app')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        || 'generated-app';
}

function normalizeFrontendSourcePath(filePath = '') {
    const trimmed = String(filePath || '').replace(/\\/g, '/').trim();
    if (!trimmed) return '/src/App.jsx';
    if (trimmed.startsWith('/src/')) return trimmed;
    if (trimmed.startsWith('/public/')) return trimmed;
    return trimmed.startsWith('/') ? `/src${trimmed}` : `/src/${trimmed}`;
}

function inferBackendTopology(backendFiles = {}) {
    const packageDirs = [...new Set(
        Object.keys(backendFiles)
            .filter((filePath) => filePath.endsWith('package.json'))
            .map((filePath) => filePath.replace(/^\/+/, '').split('/')[0])
    )];
    const serviceDirs = packageDirs.filter((dirName) => dirName !== 'api-gateway');
    const serviceConfigs = {};

    serviceDirs.forEach((dirName, index) => {
        serviceConfigs[dirName] = {
            index,
            port: DEFAULT_SERVICE_PORT + index,
            envVar: `PORT_${dirName.replace(/[^A-Za-z0-9]+/g, '_').toUpperCase()}`,
        };
    });

    return { packageDirs, serviceDirs, serviceConfigs };
}

function normalizeBackendForLocalRun(backendFiles = {}, topology) {
    const fixed = {};

    Object.entries(backendFiles || {}).forEach(([filePath, content]) => {
        let code = typeof content === 'string' ? content : content?.code || '';
        const originalCode = code;
        const relativePath = filePath.replace(/^\/+/, '');
        const serviceName = relativePath.split('/')[0] || '';
        const serviceConfig = topology.serviceConfigs[serviceName];
        const servicePort = serviceName === 'api-gateway'
            ? GATEWAY_PORT
            : (serviceConfig?.port || DEFAULT_SERVICE_PORT);
        const serviceEnvVar = serviceConfig?.envVar || 'PORT_SERVICE';

        if (relativePath === 'api-gateway/index.js') {
            code = code.replace(
                /const\s+(PORT|port)\s*=\s*[^;]+;/g,
                `const PORT = Number(process.env.PORT || process.env.PORT_GATEWAY || ${GATEWAY_PORT});`
            );
            code = code.replace(
                /process\.env\.PORT\s*\|\|\s*\d+/g,
                `process.env.PORT || process.env.PORT_GATEWAY || ${GATEWAY_PORT}`
            );
            code = code.replace(
                /app\.listen\(\s*(?:PORT|port|process\.env\.[A-Z_]+(?:\s*\|\|\s*\d+)?|\d+)\s*,/g,
                'app.listen(PORT,'
            );
            if (!/const\s+PORT\s*=/.test(code) && /app\.listen\(PORT,/.test(code)) {
                code = `const PORT = Number(process.env.PORT || process.env.PORT_GATEWAY || ${GATEWAY_PORT});\n${code}`;
            }
        }

        if (serviceName && serviceName !== 'api-gateway' && relativePath.endsWith('/index.js')) {
            code = code.replace(
                /const\s+(PORT|port)\s*=\s*[^;]+;/g,
                `const PORT = Number(process.env.PORT || process.env.${serviceEnvVar} || ${servicePort});`
            );
            code = code.replace(
                /process\.env\.PORT\s*\|\|\s*\d+/g,
                `process.env.PORT || process.env.${serviceEnvVar} || ${servicePort}`
            );
            code = code.replace(
                /app\.listen\(\s*(?:PORT|port|process\.env\.[A-Z_]+(?:\s*\|\|\s*\d+)?|\d+)\s*,/g,
                'app.listen(PORT,'
            );
            code = code.replace(/app\.listen\(PORT\(\)\s*=>/g, 'app.listen(PORT, () =>');
            code = code.replace(/app\.listen\(PORT\s*\)\s*=>/g, 'app.listen(PORT, () =>');
            if (!/const\s+PORT\s*=/.test(code) && /app\.listen\(PORT,/.test(code)) {
                code = `const PORT = Number(process.env.PORT || process.env.${serviceEnvVar} || ${servicePort});\n${code}`;
            }
        }

        fixed[filePath] = { code: code || originalCode };
    });

    return fixed;
}

async function writeGeneratedWorkspace({ rootDir, projectTitle, frontendFiles, backendFiles }) {
    const slug = slugify(projectTitle || rootDir.split(path.sep).pop());
    const frontendDir = path.join(rootDir, 'frontend');
    const frontendSrcDir = path.join(frontendDir, 'src');
    const backendDir = path.join(rootDir, 'backend');
    const topology = inferBackendTopology(backendFiles);
    const normalizedBackendFiles = normalizeBackendForLocalRun(backendFiles, topology);

    await rm(rootDir, { recursive: true, force: true }).catch(() => {});
    await mkdir(frontendSrcDir, { recursive: true });
    await mkdir(path.join(frontendDir, 'public'), { recursive: true });
    await mkdir(backendDir, { recursive: true });

    const frontendPackage = {
        name: slug,
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
    };

    const viteConfig = `import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: ${FRONTEND_PORT},
    proxy: { '/api': { target: 'http://localhost:${GATEWAY_PORT}', changeOrigin: true } },
  },
});
`;

    await writeFile(path.join(frontendDir, 'package.json'), JSON.stringify(frontendPackage, null, 2), 'utf8');
    await writeFile(path.join(frontendDir, 'vite.config.js'), viteConfig, 'utf8');
    await writeFile(path.join(frontendDir, 'tailwind.config.js'), `export default { content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'], theme: { extend: {} }, plugins: [] };`, 'utf8');
    await writeFile(path.join(frontendDir, 'postcss.config.js'), `export default { plugins: { tailwindcss: {}, autoprefixer: {} } };`, 'utf8');
    await writeFile(path.join(frontendDir, 'index.html'), `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" /><title>${projectTitle || 'Generated App'}</title></head><body><div id="root"></div><script type="module" src="/src/main.jsx"></script></body></html>`, 'utf8');
    await writeFile(path.join(frontendSrcDir, 'App.css'), `@tailwind base;\n@tailwind components;\n@tailwind utilities;\n*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }\nbody { font-family: 'Inter', system-ui, -apple-system, sans-serif; -webkit-font-smoothing: antialiased; }\n#root { min-height: 100vh; }\n`, 'utf8');
    await writeFile(path.join(frontendSrcDir, 'main.jsx'), `import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './App.css';\nimport 'react-toastify/dist/ReactToastify.css';\ncreateRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);\n`, 'utf8');

    await Promise.all(Object.entries(frontendFiles || {}).map(async ([filePath, content]) => {
        const code = typeof content === 'string' ? content : content?.code;
        if (!code) return;
        const normalized = normalizeFrontendSourcePath(filePath).replace(/^\/src\//, '');
        const destination = path.join(frontendSrcDir, normalized);
        await mkdir(path.dirname(destination), { recursive: true });
        await writeFile(destination, code, 'utf8');
    }));

    const mongoUri = `mongodb://127.0.0.1:27017/${slug}`;
    const envLines = [
        `MONGODB_URI=${mongoUri}`,
        `MONGO_URL=${mongoUri}`,
        `PORT=${GATEWAY_PORT}`,
        `PORT_GATEWAY=${GATEWAY_PORT}`,
        'JWT_SECRET=ravindu2232',
        'SECRET_KEY=ravindu2232',
        'SEKRET_KEY=ravindu2232',
        'NODE_ENV=development',
    ];

    topology.serviceDirs.forEach((dirName, index) => {
        const config = topology.serviceConfigs[dirName];
        envLines.push(`${config.envVar}=${config.port}`);
        if (index === 0) envLines.push(`PORT_SERVICE1=${config.port}`);
        if (index === 1) envLines.push(`PORT_SERVICE2=${config.port}`);
    });

    const rootEnvText = `${envLines.join('\n')}\n`;
    await writeFile(path.join(backendDir, '.env'), rootEnvText, 'utf8');

    await Promise.all(Object.entries(normalizedBackendFiles || {}).map(async ([filePath, content]) => {
        const code = typeof content === 'string' ? content : content?.code;
        if (!code) return;
        const relativePath = filePath.replace(/^\/+/, '');
        const destination = path.join(backendDir, relativePath);
        await mkdir(path.dirname(destination), { recursive: true });
        await writeFile(destination, code, 'utf8');
        const firstDir = relativePath.split('/')[0];
        if (firstDir) {
            const serviceConfig = topology.serviceConfigs[firstDir];
            const servicePort = firstDir === 'api-gateway'
                ? GATEWAY_PORT
                : (serviceConfig?.port || DEFAULT_SERVICE_PORT);
            const serviceEnvLines = [
                ...envLines.filter((line) => !line.startsWith('PORT=')),
                `PORT=${servicePort}`,
            ];
            await writeFile(path.join(backendDir, firstDir, '.env'), `${serviceEnvLines.join('\n')}\n`, 'utf8').catch(() => {});
        }
    }));

    return {
        frontendDir,
        backendDir,
        mongoUri,
        topology,
    };
}

function launchWindowsTerminal(title, command, cwd) {
    const safeTitle = String(title || 'AI Builder').replace(/[\r\n"]/g, ' ').trim();
    const wrappedCommand = `title ${safeTitle} && ${command}`;
    spawn('cmd.exe', ['/c', 'start', '""', 'cmd.exe', '/k', wrappedCommand], {
        cwd,
        detached: true,
        stdio: 'ignore',
        windowsHide: false,
        shell: false,
    }).unref();
}

function openBrowser(url, cwd) {
    spawn('cmd.exe', ['/c', 'start', '""', url], {
        cwd,
        detached: true,
        stdio: 'ignore',
        windowsHide: true,
        shell: false,
    }).unref();
}

export async function POST(request) {
    try {
        const { workspaceId, projectTitle, frontendFiles, backendFiles } = await request.json();
        if (!frontendFiles || typeof frontendFiles !== 'object' || Object.keys(frontendFiles).length === 0) {
            return Response.json({ success: false, error: 'No frontend files were provided for local run.' }, { status: 400 });
        }

        const runSlug = slugify(projectTitle || workspaceId || 'generated-app');
        const rootDir = path.join(process.cwd(), 'local-runs', runSlug);
        await mkdir(path.dirname(rootDir), { recursive: true });

        const { frontendDir, backendDir, mongoUri, topology } = await writeGeneratedWorkspace({
            rootDir,
            projectTitle,
            frontendFiles,
            backendFiles: backendFiles || {},
        });

        topology.packageDirs.forEach((dirName) => {
            const serviceDir = path.join(backendDir, dirName);
            const title = `AI Builder ${dirName}`;
            const servicePort = dirName === 'api-gateway'
                ? GATEWAY_PORT
                : (topology.serviceConfigs[dirName]?.port || DEFAULT_SERVICE_PORT);
            const command = [
                `set "PORT=${servicePort}"`,
                `set "PORT_GATEWAY=${GATEWAY_PORT}"`,
                `set "MONGODB_URI=${mongoUri}"`,
                `set "MONGO_URL=${mongoUri}"`,
                'set "JWT_SECRET=ravindu2232"',
                'set "SECRET_KEY=ravindu2232"',
                'set "SEKRET_KEY=ravindu2232"',
                'set "NODE_ENV=development"',
                'if not exist node_modules (npm install)',
                'node index.js',
            ].join(' && ');
            launchWindowsTerminal(title, command, serviceDir);
        });

        const frontendCommand = `if not exist node_modules (npm install) && npm run dev -- --port ${FRONTEND_PORT}`;
        launchWindowsTerminal('AI Builder Frontend', frontendCommand, frontendDir);
        openBrowser(`http://localhost:${FRONTEND_PORT}`, frontendDir);

        return Response.json({
            success: true,
            workspacePath: rootDir,
            frontendUrl: `http://localhost:${FRONTEND_PORT}`,
            gatewayUrl: Object.keys(backendFiles || {}).length > 0 ? `http://localhost:${GATEWAY_PORT}` : null,
            mongoUri,
        });
    } catch (error) {
        return Response.json({
            success: false,
            error: error?.message || 'Local run failed.',
        }, { status: 500 });
    }
}
