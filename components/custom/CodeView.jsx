"use client"
import React, { useContext, useState, useEffect, useCallback, useRef, memo } from 'react';
import dynamic from 'next/dynamic';
import Lookup from '@/data/Lookup';
import { MessagesContext } from '@/context/MessagesContext';
import { useParams } from 'next/navigation';
import {
    Download, ExternalLink, Copy, Check, Code2, Eye,
    Server, Layers, AlertTriangle, X, FileCode2, Terminal,
    CheckCircle2, Circle, Loader2, ChevronRight,
} from 'lucide-react';
import JSZip from 'jszip';

const SandpackProvider     = dynamic(() => import("@codesandbox/sandpack-react").then(m => m.SandpackProvider),     { ssr: false });
const SandpackLayout       = dynamic(() => import("@codesandbox/sandpack-react").then(m => m.SandpackLayout),       { ssr: false });
const SandpackCodeEditor   = dynamic(() => import("@codesandbox/sandpack-react").then(m => m.SandpackCodeEditor),   { ssr: false });
const SandpackPreview      = dynamic(() => import("@codesandbox/sandpack-react").then(m => m.SandpackPreview),      { ssr: false });
const SandpackFileExplorer = dynamic(() => import("@codesandbox/sandpack-react").then(m => m.SandpackFileExplorer), { ssr: false });

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

// ── Design seeds ──────────────────────────────────────────────────────────────
const DESIGN_SEEDS = [
    { id: 'midnight-purple', bg: 'gray-950',    primary: 'purple',  gradient: 'from-purple-600 to-pink-600',    style: 'glassmorphism dark' },
    { id: 'ocean-blue',      bg: 'slate-900',   primary: 'blue',    gradient: 'from-blue-500 to-cyan-400',      style: 'modern dark with glass cards' },
    { id: 'forest-green',    bg: 'gray-900',    primary: 'emerald', gradient: 'from-emerald-500 to-teal-400',   style: 'clean dark soft cards' },
    { id: 'sunset-fire',     bg: 'zinc-950',    primary: 'orange',  gradient: 'from-orange-500 to-red-500',     style: 'bold dark vibrant accents' },
    { id: 'rose-bloom',      bg: 'gray-950',    primary: 'rose',    gradient: 'from-rose-500 to-pink-400',      style: 'elegant dark soft glows' },
    { id: 'golden-amber',    bg: 'neutral-950', primary: 'yellow',  gradient: 'from-yellow-400 to-amber-500',   style: 'warm dark golden accents' },
    { id: 'cyber-indigo',    bg: 'indigo-950',  primary: 'indigo',  gradient: 'from-indigo-500 to-violet-600',  style: 'cyber dark neon glow' },
    { id: 'clean-white',     bg: 'gray-50',     primary: 'blue',    gradient: 'from-blue-600 to-purple-600',    style: 'clean minimal light theme' },
    { id: 'teal-cyber',      bg: 'gray-900',    primary: 'teal',    gradient: 'from-teal-400 to-cyan-500',      style: 'tech dark teal glow' },
    { id: 'fuchsia-pop',     bg: 'zinc-950',    primary: 'fuchsia', gradient: 'from-fuchsia-500 to-purple-600', style: 'vibrant dark magenta neon' },
    { id: 'neo-brutalist',   bg: 'yellow-300',  primary: 'black',   gradient: 'from-black to-gray-700',         style: 'neo-brutalist bold stark contrast' },
    { id: 'lime-dark',       bg: 'gray-950',    primary: 'lime',    gradient: 'from-lime-400 to-green-500',     style: 'dark electric lime accents' },
];
const randomSeed = () => DESIGN_SEEDS[Math.floor(Math.random() * DESIGN_SEEDS.length)];

// ── Packages allowed in Sandpack ──────────────────────────────────────────────
const ALLOWED = new Set([
    'react', 'react-dom', 'react-router-dom', 'lucide-react',
    'framer-motion', 'react-toastify', 'tailwind-merge', 'uuid',
    'react-beautiful-dnd', 'recharts', 'date-fns',
]);

function sanitize(code) {
    if (typeof code !== 'string') return code;
    let processed = code.replace(/from\s+['"]@\/([^'"]+)['"]/g, "from '/$1'");
    processed = processed.replace(/import\s*\(\s*['"]@\/([^'"]+)['"]\s*\)/g, "import('/$1')");
    return processed.split('\n').map(line => {
        if (/^\s*import\s+['"][^'"]+\.css['"]/.test(line)) return `// [css import removed for sandpack preview]`;
        if (line.includes('react-hot-toast')) {
            line = line
                .replace(/from ['"]react-hot-toast['"]/, "from 'react-toastify'")
                .replace(/from "react-hot-toast"/, 'from "react-toastify"')
                .replace(/\bToaster\b/, 'ToastContainer');
            return line;
        }
        if (line.includes('<Toaster') && !line.includes('Container'))
            return line.replace(/<Toaster([^>]*)\/>/, '<ToastContainer$1/>');
        const m = line.match(/^\s*import\s+.*?from\s+['"]([^'"./][^'"@][^'"]*)['"]/);
        if (m) {
            const pkg = m[1].split('/')[0];
            if (!ALLOWED.has(pkg)) return `// [removed unsupported pkg: ${pkg}]`;
        }
        return line;
    }).join('\n');
}

function sandpackPath(filePath) {
    return filePath.replace(/^\/src\//, '/');
}

// ── Phase metadata ────────────────────────────────────────────────────────────
const PHASES = [
    { key: 'backend-gen',  label: 'Backend Gen',      icon: '⚙️',  color: 'text-yellow-400' },
    { key: 'backend-fix',  label: 'Backend Fix',      icon: '🔍',  color: 'text-orange-400' },
    { key: 'api-test',     label: 'API Testing',      icon: '🧪',  color: 'text-green-400'  },
    { key: 'frontend-gen', label: 'Frontend Gen',     icon: '🎨',  color: 'text-blue-400'   },
    { key: 'frontend-fix', label: 'Frontend Fix',     icon: '🔧',  color: 'text-purple-400' },
];

// ── Developer Console ─────────────────────────────────────────────────────────
const DeveloperConsole = memo(({ phases, logs, chars, currentPhase, done }) => {
    const bottomRef = useRef(null);
    useEffect(() => {
        if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }, [logs.length]);

    const getPhaseStatus = (key) => {
        if (!phases[key]) return 'pending';
        return phases[key].status;
    };

    const logColor = (level) => {
        if (level === 'success') return 'text-green-400';
        if (level === 'warning') return 'text-yellow-400';
        if (level === 'error')   return 'text-red-400';
        return 'text-gray-300';
    };

    return (
        <div className="absolute inset-0 bg-gray-950/97 backdrop-blur-sm z-20 flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-gray-900 border-b border-gray-800 shrink-0">
                <div className="flex items-center gap-2">
                    <Terminal className="h-4 w-4 text-green-400"/>
                    <span className="text-white font-semibold text-sm">AI Developer Console</span>
                    <span className="text-gray-500 text-xs">— Live Build Pipeline</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                    {chars > 0 && (
                        <span className="text-blue-400">{(chars / 1000).toFixed(1)}k tokens</span>
                    )}
                    {!done && (
                        <span className="flex items-center gap-1 text-green-400">
                            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"/>
                            Building…
                        </span>
                    )}
                    {done && <span className="text-green-400">✅ Complete</span>}
                </div>
            </div>

            {/* Phase progress bar */}
            <div className="flex border-b border-gray-800 shrink-0 bg-gray-900/60">
                {PHASES.map((ph, idx) => {
                    const status = getPhaseStatus(ph.key);
                    const isActive = currentPhase === ph.key;
                    return (
                        <div key={ph.key}
                            className={`flex-1 flex items-center gap-1.5 px-3 py-2 border-r border-gray-800 last:border-r-0 transition-colors
                                ${status === 'done'   ? 'bg-green-900/20' :
                                  isActive            ? 'bg-blue-900/20'  : 'bg-transparent'}`}>
                            {status === 'done' ? (
                                <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0"/>
                            ) : isActive ? (
                                <Loader2 className="h-3.5 w-3.5 text-blue-400 animate-spin shrink-0"/>
                            ) : (
                                <Circle className="h-3.5 w-3.5 text-gray-700 shrink-0"/>
                            )}
                            <div className="min-w-0">
                                <div className={`text-xs font-medium truncate
                                    ${status === 'done' ? 'text-green-400' :
                                      isActive ? 'text-blue-300' : 'text-gray-600'}`}>
                                    {ph.icon} {ph.label}
                                </div>
                                {phases[ph.key]?.fileCount != null && (
                                    <div className="text-gray-600 text-[10px]">{phases[ph.key].fileCount} files</div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Log stream */}
            <div className="flex-1 overflow-y-auto p-4 font-mono text-xs space-y-0.5">
                {logs.map((line, i) => {
                    // Test result rows get a subtle row background
                    const isTestRow = line.message?.startsWith('✅') || line.message?.startsWith('❌');
                    const isSummary = line.message?.startsWith('📊');
                    return (
                        <div key={i}
                            className={`flex items-start gap-2 leading-relaxed px-1 rounded
                                ${isTestRow && line.level === 'success' ? 'bg-green-950/20' :
                                  isTestRow && line.level === 'error'   ? 'bg-red-950/20'   :
                                  isSummary                             ? 'bg-gray-800/40 border-l-2 border-blue-600/40 pl-2 my-1' :
                                  ''} ${logColor(line.level)}`}>
                            <ChevronRight className="h-3 w-3 mt-0.5 shrink-0 opacity-40"/>
                            <span className="text-gray-700 shrink-0 tabular-nums">{line.ts}</span>
                            {line.round && <span className="text-gray-600 shrink-0">[R{line.round}]</span>}
                            <span className={isSummary ? 'font-semibold' : ''}>{line.message}</span>
                        </div>
                    );
                })}
                <div ref={bottomRef}/>
            </div>
        </div>
    );
});
DeveloperConsole.displayName = 'DeveloperConsole';

// ── Backend file tree ─────────────────────────────────────────────────────────
const BackendTree = memo(({ files }) => {
    const [sel, setSel] = useState(null);
    const entries = Object.keys(files).sort();
    if (!entries.length) return (
        <div className="flex items-center justify-center h-full text-gray-600 text-sm">No backend files generated</div>
    );
    const rawCode = sel ? (files[sel]?.code ?? files[sel] ?? '') : null;
    const code = typeof rawCode === 'string' ? rawCode : JSON.stringify(rawCode, null, 2);
    return (
        <div className="h-full flex overflow-hidden bg-gray-950">
            <div className="w-64 border-r border-gray-800 overflow-y-auto p-3 shrink-0">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-800">
                    <Terminal className="h-4 w-4 text-green-400"/>
                    <span className="text-green-400 text-xs font-semibold">Microservices</span>
                    <span className="ml-auto text-gray-600 text-xs">{entries.length} files</span>
                </div>
                {entries.map(f => {
                    const name  = f.replace(/^\//, '');
                    const depth = (name.match(/\//g) || []).length;
                    const fname = name.split('/').pop();
                    const color = f.includes('/models/')   ? 'text-yellow-400'
                        :         f.includes('/routes/')   ? 'text-blue-400'
                        :         f.includes('gateway')    ? 'text-purple-400'
                        :         fname === 'package.json' ? 'text-orange-400'
                        :         'text-gray-300';
                    return (
                        <div key={f} onClick={() => setSel(f === sel ? null : f)}
                            className={`py-1 px-2 rounded cursor-pointer transition-colors ${sel===f ? 'bg-blue-900/40 border border-blue-700/30' : 'hover:bg-gray-800'}`}
                            style={{ paddingLeft: `${depth * 14 + 8}px` }}>
                            <span className={`text-xs font-mono ${color}`}>{depth > 0 ? '└─ ' : ''}{fname}</span>
                        </div>
                    );
                })}
            </div>
            <div className="flex-1 overflow-auto">
                {code ? (
                    <pre className="text-xs text-gray-200 p-4 font-mono leading-relaxed whitespace-pre-wrap">{code}</pre>
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-gray-600 gap-2">
                        <FileCode2 className="h-8 w-8 opacity-40"/>
                        <span className="text-sm">Click a file to view code</span>
                    </div>
                )}
            </div>
        </div>
    );
});
BackendTree.displayName = 'BackendTree';

// ── Main component ────────────────────────────────────────────────────────────
export default function CodeView() {
    const { id }                          = useParams();
    const { messages }                    = useContext(MessagesContext);
    const [activeTab, setActiveTab]       = useState('code');
    const [files, setFiles]               = useState(Lookup.DEFAULT_FILE);
    const [backendFiles, setBackendFiles] = useState({});
    const [rawFrontend, setRawFrontend]   = useState({});
    const [projectTitle, setProjectTitle] = useState('');
    const [fileCount, setFileCount]       = useState(0);
    const [copied, setCopied]             = useState(false);
    const [loading, setLoading]           = useState(false);
    const [genError, setGenError]         = useState('');
    const lastGeneratedMsg                = useRef('');

    // ── Developer console state ───────────────────────────────────────────
    const [consoleLogs,    setConsoleLogs]    = useState([]);  // { ts, phase, level, message, round }
    const [consolePhases,  setConsolePhases]  = useState({});  // { [phaseKey]: { status, fileCount } }
    const [currentPhase,   setCurrentPhase]   = useState('');
    const [totalChars,     setTotalChars]     = useState(0);
    const [consoleDone,    setConsoleDone]    = useState(false);
    const currentPhaseRef                     = useRef('');

    const addLog = useCallback((entry) => {
        const ts = new Date().toLocaleTimeString('en-US', { hour12: false, hour:'2-digit', minute:'2-digit', second:'2-digit' });
        setConsoleLogs(prev => [...prev, { ts, ...entry }]);
    }, []);

    // ── File preprocessing ────────────────────────────────────────────────
    const preprocessFiles = useCallback((rawFiles) => {
        if (!rawFiles || typeof rawFiles !== 'object') return {};
        const out = {};
        Object.entries(rawFiles).forEach(([path, content]) => {
            const code = typeof content === 'string' ? content
                : content?.code != null ? String(content.code) : null;
            if (!code) return;
            let spPath = sandpackPath(path);
            if (spPath.endsWith('.js') && !spPath.includes('/index') &&
                (code.includes('</') || code.includes('/>'))) {
                spPath = spPath.replace(/\.js$/, '.jsx');
            }
            out[spPath] = { code: sanitize(code) };
        });
        return out;
    }, []);

    const mergeWithDefaults = useCallback((processed) => {
        return { ...Lookup.DEFAULT_FILE, ...processed };
    }, []);

    // ── Load saved workspace ──────────────────────────────────────────────
    const loadFiles = useCallback(async () => {
        if (!id) return;
        try {
            const res  = await fetch(`${BACKEND_URL}/api/workspaces/${id}`);
            if (!res.ok) return;
            const data = await res.json();
            if (data.fileData && Object.keys(data.fileData).length > 0) {
                setRawFrontend(data.fileData);
                setFiles(mergeWithDefaults(preprocessFiles(data.fileData)));
                setFileCount(Object.keys(data.fileData).length);
                setActiveTab('preview');
            }
            if (data.backendData && Object.keys(data.backendData).length > 0)
                setBackendFiles(data.backendData);
            if (data.projectTitle) setProjectTitle(data.projectTitle);
        } catch (e) { console.error('loadFiles:', e); }
    }, [id, preprocessFiles, mergeWithDefaults]);

    useEffect(() => { loadFiles(); }, [loadFiles]);

    // ── Code generation — uses /api/gen-fullstack ─────────────────────────
    const generateCode = useCallback(async () => {
        if (!messages || !id) return;
        const msgs = Array.isArray(messages) ? messages : [messages];
        if (!msgs.length) return;
        const lastMsg = msgs[msgs.length - 1];
        if (lastMsg?.role !== 'user') return;

        const msgKey = lastMsg.content?.slice(0, 200);
        if (lastGeneratedMsg.current === msgKey) return;
        lastGeneratedMsg.current = msgKey;

        const seed = randomSeed();
        // Build the full prompt once — design seed + user messages
        const fullPrompt =
            `DESIGN SEED: palette="${seed.id}" bg=${seed.bg} primary=${seed.primary} ` +
            `gradient="${seed.gradient}" style="${seed.style}". Use these colors everywhere.\n\n` +
            `USER REQUEST:\n${JSON.stringify(msgs)}`;

        setLoading(true);
        setGenError('');
        setConsoleLogs([]);
        setConsolePhases({});
        setCurrentPhase('');
        setTotalChars(0);
        setConsoleDone(false);

        try {
            const response = await fetch('/api/gen-fullstack', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: fullPrompt }),
            });
            if (!response.ok) throw new Error(`Server error ${response.status}`);

            const reader  = response.body.getReader();
            const decoder = new TextDecoder();
            let finalData  = null;
            let errMsg     = '';
            // ── SSE buffering: accumulate partial lines across chunks ──────
            // Large events (final JSON with all files) span multiple read()s.
            // Without a buffer, the split-on-\n drops incomplete lines silently.
            let sseBuffer = '';

            const processLine = (line) => {
                if (!line.startsWith('data: ')) return;
                try {
                    const d = JSON.parse(line.slice(6));

                        // Phase events
                        if (d.type === 'phase') {
                            if (d.status === 'start') {
                                currentPhaseRef.current = d.phase;
                                setCurrentPhase(d.phase);
                                setConsolePhases(prev => ({ ...prev, [d.phase]: { status: 'running' } }));
                                addLog({ phase: d.phase, level: 'info', message: d.message || `Phase: ${d.phase}` });
                            } else if (d.status === 'done') {
                                setConsolePhases(prev => ({
                                    ...prev,
                                    [d.phase]: { status: 'done', fileCount: d.fileCount },
                                }));
                                addLog({ phase: d.phase, level: 'success', message: d.message || `✅ ${d.phase} complete` });
                            }
                        }

                        // Log lines
                        if (d.type === 'log') {
                            addLog({ phase: d.phase, level: d.level || 'info', message: d.message, round: d.round });
                        }

                        // File-found events
                        if (d.type === 'file') {
                            addLog({ phase: d.phase, level: 'info',
                                message: `  📄 ${d.section === 'backend' ? '[BE]' : '[FE]'} ${d.path}` });
                        }

                        // API test result — individual route
                        if (d.type === 'test-result') {
                            const icon   = d.status === 'PASS' ? '✅' : '❌';
                            const method = `${d.method?.padEnd(6, ' ')}`;
                            const reason = d.reason ? ` — ${d.reason}` : '';
                            addLog({
                                phase: 'api-test',
                                level: d.status === 'PASS' ? 'success' : 'error',
                                round: d.round,
                                message: `${icon} ${method} ${d.path}${reason}`,
                            });
                        }

                        // API test summary
                        if (d.type === 'test-summary') {
                            const allPass = d.failed === 0;
                            addLog({
                                phase: 'api-test',
                                level: allPass ? 'success' : 'warning',
                                round: d.round,
                                message: `📊 Round ${d.round} results: ${d.passed} passed, ${d.failed} failed out of ${d.total} routes${allPass ? ' 🎉' : ` — fixing ${d.failed} route(s)…`}`,
                            });
                        }

                        // Chunk — update char counter
                        if (d.type === 'chunk') {
                            setTotalChars(d.chars || 0);
                        }

                        // Error
                        if (d.type === 'error') {
                            errMsg = d.error;
                            addLog({ phase: currentPhaseRef.current, level: 'error', message: `❌ ${d.error}` });
                        }

                        // Final
                        if (d.type === 'final' && d.final) {
                            finalData = d.final;
                            setConsoleDone(true);
                            setCurrentPhase('');
                        }

                        if (d.done && !finalData && !errMsg) {
                            errMsg = 'Generation ended without final data.';
                        }
                    } catch (parseErr) {
                        // JSON parse failed — might be a partial line; skip silently
                    }
                };

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                // Append new data to buffer
                sseBuffer += decoder.decode(value, { stream: true });
                // Split on newline — last element may be an incomplete line
                const lines = sseBuffer.split('\n');
                sseBuffer   = lines.pop() ?? '';   // save incomplete tail
                for (const line of lines) processLine(line);
            }
            // Flush any remaining buffered data (e.g. if stream closes without trailing \n)
            if (sseBuffer) processLine(sseBuffer);

            if (!finalData) {
                setGenError(errMsg || 'AI did not produce valid output. Please try again.');
                setLoading(false);
                return;
            }

            const frontendFiles = finalData.frontend || {};
            const beFiles       = finalData.backend  || {};
            const fCount        = Object.keys(frontendFiles).length;

            if (fCount === 0) {
                setGenError('No frontend files found. Try regenerating.');
                setLoading(false);
                return;
            }

            setRawFrontend(frontendFiles);
            const sandpackFiles = mergeWithDefaults(preprocessFiles(frontendFiles));
            setFiles(sandpackFiles);
            setFileCount(fCount);
            if (finalData.projectTitle) setProjectTitle(finalData.projectTitle);
            if (Object.keys(beFiles).length > 0) setBackendFiles(beFiles);

            // Save to MongoDB
            await fetch(`${BACKEND_URL}/api/workspaces/${id}/files`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    files: frontendFiles,
                    backendFiles: beFiles,
                    projectTitle: finalData.projectTitle || '',
                })
            });

            // Brief pause so user can read "complete" state, then switch to preview
            await new Promise(r => setTimeout(r, 1200));
            setActiveTab('preview');

        } catch (e) {
            console.error('generateCode:', e);
            setGenError(`Generation error: ${e.message}`);
            addLog({ phase: currentPhaseRef.current || 'system', level: 'error', message: `❌ ${e.message}` });
        } finally {
            setLoading(false);
        }
    }, [messages, id, preprocessFiles, mergeWithDefaults, addLog]);

    useEffect(() => { generateCode(); }, [messages]); // eslint-disable-line

    // ── Actions ───────────────────────────────────────────────────────────
    const previewUrl = typeof window !== 'undefined'
        ? `${window.location.origin}/preview/${id}` : `/preview/${id}`;

    const copyLink = async () => {
        try { await navigator.clipboard.writeText(previewUrl); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch (_) {}
    };

    // ── Download ZIP ──────────────────────────────────────────────────────
    const downloadFiles = useCallback(async () => {
        const zip  = new JSZip();
        const slug = projectTitle ? projectTitle.toLowerCase().replace(/\s+/g, '-') : 'generated-app';
        const fe   = zip.folder('frontend');
        const srcDir = fe.folder('src');

        fe.file('index.html', `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${projectTitle || 'App'}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>`);

        fe.file('vite.config.js', `import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 3000,
    proxy: { '/api': { target: 'http://localhost:3005', changeOrigin: true } },
  },
});`);

        fe.file('tailwind.config.js', `/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
};`);

        fe.file('postcss.config.js', `export default { plugins: { tailwindcss: {}, autoprefixer: {} } };`);

        fe.file('package.json', JSON.stringify({
            name: slug, version: '1.0.0', private: true, type: 'module',
            scripts: { dev: 'vite', build: 'vite build', preview: 'vite preview' },
            dependencies: {
                react: '^18.2.0', 'react-dom': '^18.2.0', 'react-router-dom': '^6.20.0',
                'lucide-react': '^0.363.0', 'framer-motion': '^10.18.0', 'react-toastify': '^10.0.0',
                'tailwind-merge': '^2.4.0', uuid: '^9.0.0', 'react-beautiful-dnd': '^13.1.1',
                recharts: '^2.10.3', 'date-fns': '^3.3.1',
            },
            devDependencies: {
                '@vitejs/plugin-react': '^4.2.1', vite: '^5.0.0',
                tailwindcss: '^3.4.1', postcss: '^8.4.35', autoprefixer: '^10.4.17',
            },
        }, null, 2));

        srcDir.file('App.css', `@tailwind base;\n@tailwind components;\n@tailwind utilities;\n*, *::before, *::after { box-sizing: border-box; }\nbody { margin: 0; font-family: 'Inter', system-ui, -apple-system, sans-serif; }\n`);
        srcDir.file('main.jsx', `import React from 'react';\nimport { createRoot } from 'react-dom/client';\nimport App from './App.jsx';\nimport './App.css';\nimport 'react-toastify/dist/ReactToastify.css';\ncreateRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);\n`);

        const sourceFiles = Object.keys(rawFrontend).length > 0 ? rawFrontend : files;
        Object.entries(sourceFiles).forEach(([filePath, content]) => {
            if (['/index.js','/index.html','/App.css','/public/index.html'].includes(filePath)) return;
            const code = typeof content === 'string' ? content : content?.code;
            if (!code) return;
            let dest = filePath.startsWith('/src/')
                ? filePath.slice(1)
                : `src/${filePath.replace(/^\//, '')}`;
            if (dest.endsWith('.js') && (code.includes('</') || code.includes('/>')))
                dest = dest.replace(/\.js$/, '.jsx');
            fe.file(dest, code);
        });

        if (Object.keys(backendFiles).length > 0) {
            const be = zip.folder('backend');
            be.file('.env', [
                `MONGODB_URI=mongodb://localhost:27017/${slug}`,
                'PORT_GATEWAY=3005', 'PORT_SERVICE1=3006', 'PORT_SERVICE2=3007',
                'JWT_SECRET=change-me-in-production', 'NODE_ENV=development',
            ].join('\n'));
            Object.entries(backendFiles).forEach(([p, c]) => {
                const code = typeof c === 'string' ? c : c?.code;
                if (code) be.file(p.replace(/^\//, ''), code);
            });
        }

        zip.file('README.md', `# ${projectTitle || slug}\n\n## Quick Start\n\n### Frontend\n\`\`\`bash\ncd frontend && npm install && npm run dev\n\`\`\`\n\n### Backend\n\`\`\`bash\ncd backend/api-gateway && npm install && npm start\ncd backend/[service]-service && npm install && npm start\n\`\`\`\n\n## Ports\n- Frontend: 3000\n- API Gateway: 3005\n- Service 1: 3006 / Service 2: 3007\n- MongoDB: 27017\n`);

        const beKeys  = Object.keys(backendFiles);
        const hasBack = beKeys.length > 0;
        const svcDirs = hasBack ? [...new Set(beKeys.map(p => p.replace(/^\//, '').split('/')[0]))] : [];

        const bat = ['@echo off', `title ${slug} Launcher`, 'echo.', `echo  =========== Starting ${projectTitle || slug} ===========`, 'echo.'];
        svcDirs.forEach((dir, i) => {
            bat.push(`echo  [${i+1}/${svcDirs.length+1}] Starting backend: ${dir}`);
            bat.push(`start "${dir}" cmd /k "cd /d "%~dp0backend\\${dir}" && (if not exist node_modules npm install) && node index.js"`);
            bat.push('timeout /t 2 /nobreak >nul');
        });
        bat.push(`echo  [${svcDirs.length+1}/${svcDirs.length+1}] Starting Frontend`);
        bat.push(`start "Frontend" cmd /k "cd /d "%~dp0frontend" && npm install && npm run dev"`);
        bat.push('timeout /t 10 /nobreak >nul', 'start "" "http://localhost:3000"', 'echo.', 'echo  ========================================');
        if (hasBack) bat.push('echo    Gateway  : http://localhost:3005');
        bat.push('echo    Frontend : http://localhost:3000', 'echo  ========================================', 'pause');
        zip.file('start.bat', bat.join('\r\n'));

        const sh = ['#!/bin/bash', `echo "Starting ${projectTitle || slug}..."`, ''];
        svcDirs.forEach(dir => sh.push(`(cd "$(dirname "$0")/backend/${dir}" && npm install --silent && node index.js) &`));
        sh.push('(cd "$(dirname "$0")/frontend" && npm install && npm run dev) &', 'sleep 8', 'command -v open &>/dev/null && open http://localhost:3000 || xdg-open http://localhost:3000 2>/dev/null || true');
        zip.file('start.sh', sh.join('\n'));
        zip.file('.gitignore', 'node_modules\n.env\ndist\n.DS_Store\n');

        const blob = await zip.generateAsync({ type: 'blob' });
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.href = url; a.download = `${slug}-fullstack.zip`;
        document.body.appendChild(a); a.click();
        URL.revokeObjectURL(url); document.body.removeChild(a);
    }, [rawFrontend, files, backendFiles, projectTitle]);

    const hasBackend   = Object.keys(backendFiles).length > 0;
    const hasGenerated = fileCount > 0;

    return (
        <div className="relative flex flex-col bg-[#0e0e0e] rounded-xl border border-gray-800 overflow-hidden">

            {/* ── Toolbar ─────────────────────────────────────────────── */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-gray-900 border-b border-gray-800 gap-3 flex-wrap">
                <div className="flex items-center gap-1 bg-gray-950 rounded-lg p-1">
                    {[
                        { key:'code',    icon:<Code2  className="h-3.5 w-3.5"/>, label:'Code' },
                        { key:'preview', icon:<Eye    className="h-3.5 w-3.5"/>, label:'Preview' },
                        hasBackend && { key:'backend', icon:<Server className="h-3.5 w-3.5"/>, label:'Backend' },
                    ].filter(Boolean).map(t => (
                        <button key={t.key} onClick={() => setActiveTab(t.key)}
                            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all
                                ${activeTab===t.key ? 'bg-blue-600 text-white shadow' : 'text-gray-400 hover:text-gray-200'}`}>
                            {t.icon}{t.label}
                        </button>
                    ))}
                </div>

                <div className="flex items-center gap-2 text-xs">
                    {projectTitle && (
                        <>
                            <Layers className="h-3.5 w-3.5 text-blue-400"/>
                            <span className="text-gray-300 font-medium truncate max-w-[160px]">{projectTitle}</span>
                            <span className="bg-gray-800 text-gray-500 px-2 py-0.5 rounded-full">{fileCount}f</span>
                        </>
                    )}
                    {hasBackend && <span className="bg-green-900/40 text-green-400 border border-green-800/40 px-2 py-0.5 rounded-full">+backend</span>}
                    {hasGenerated && !hasBackend && <span className="bg-blue-900/40 text-blue-400 border border-blue-800/40 px-2 py-0.5 rounded-full">frontend</span>}
                </div>

                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 bg-gray-800/60 border border-gray-700/50 rounded-lg px-2 py-1.5">
                        <span className="text-xs text-gray-500 font-mono hidden sm:block">/preview/{id?.slice(0,8)}…</span>
                        <button onClick={copyLink} className="text-gray-400 hover:text-white p-0.5" title="Copy preview link">
                            {copied ? <Check className="h-3.5 w-3.5 text-green-400"/> : <Copy className="h-3.5 w-3.5"/>}
                        </button>
                        <a href={previewUrl} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-blue-400 p-0.5">
                            <ExternalLink className="h-3.5 w-3.5"/>
                        </a>
                    </div>
                    <button onClick={downloadFiles}
                        className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-xs font-medium transition-all">
                        <Download className="h-3.5 w-3.5"/>
                        {hasBackend ? 'Full-Stack ZIP' : 'Download ZIP'}
                    </button>
                </div>
            </div>

            {/* ── Error banner ─────────────────────────────────────────── */}
            {genError && (
                <div className="flex items-center gap-3 bg-red-950/70 border-b border-red-800/50 px-4 py-2.5">
                    <AlertTriangle className="h-4 w-4 text-red-400 shrink-0"/>
                    <span className="text-red-300 text-xs flex-1">{genError}</span>
                    <button onClick={() => setGenError('')} className="text-red-500 hover:text-red-300"><X className="h-4 w-4"/></button>
                </div>
            )}

            {/* ── Content ──────────────────────────────────────────────── */}
            {activeTab === 'backend' ? (
                <div style={{ height:'80vh' }}><BackendTree files={backendFiles}/></div>
            ) : (
                <SandpackProvider
                    key={JSON.stringify(Object.keys(files))}
                    files={files}
                    template="react"
                    theme="dark"
                    customSetup={{ dependencies: { ...Lookup.DEPENDANCY }, entry: '/index.js' }}
                    options={{
                        externalResources: [
                            'https://cdn.tailwindcss.com',
                            'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap',
                        ],
                        bundlerTimeoutSecs: 120,
                        recompileMode: 'delayed',
                        recompileDelay: 800,
                        autorun: true,
                    }}
                >
                    <SandpackLayout>
                        {activeTab === 'code' ? (
                            <>
                                <SandpackFileExplorer style={{ height:'80vh' }}/>
                                <SandpackCodeEditor style={{ height:'80vh' }} showTabs showLineNumbers showInlineErrors wrapContent/>
                            </>
                        ) : (
                            <SandpackPreview style={{ height:'80vh' }} showNavigator showOpenInCodeSandbox={false} showRefreshButton/>
                        )}
                    </SandpackLayout>
                </SandpackProvider>
            )}

            {/* ── Developer Console overlay (shown during generation) ───── */}
            {loading && (
                <DeveloperConsole
                    phases={consolePhases}
                    logs={consoleLogs}
                    chars={totalChars}
                    currentPhase={currentPhase}
                    done={consoleDone}
                />
            )}
        </div>
    );
}
