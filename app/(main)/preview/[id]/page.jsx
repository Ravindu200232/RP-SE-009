"use client"
import React, { useEffect, useState, useCallback } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import Lookup from '@/data/Lookup';
import { ArrowLeft, Loader2, Maximize2, ExternalLink } from 'lucide-react';

const SandpackProvider = dynamic(() => import("@codesandbox/sandpack-react").then(m => m.SandpackProvider), { ssr: false });
const SandpackPreview  = dynamic(() => import("@codesandbox/sandpack-react").then(m => m.SandpackPreview),  { ssr: false });

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

const ALLOWED = new Set([
    'react','react-dom','react-router-dom','lucide-react',
    'framer-motion','react-toastify','tailwind-merge','uuid',
    'react-beautiful-dnd','recharts','date-fns',
]);

function sanitize(code) {
    if (typeof code !== 'string') return code;
    // Fix @/ path aliases → absolute /
    let out = code.replace(/from\s+['"]@\/([^'"]+)['"]/g, "from '/$1'");
    out = out.replace(/import\s*\(\s*['"]@\/([^'"]+)['"]\s*\)/g, "import('/$1')");
    return out.split('\n').map(line => {
        if (/^\s*import\s+['"][^'"]+\.css['"]/.test(line)) return '// [css removed]';
        if (line.includes('react-hot-toast')) {
            return line
                .replace(/from ['"]react-hot-toast['"]/, "from 'react-toastify'")
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
}

function sandpackPath(p) { return p.replace(/^\/src\//, '/'); }

function buildSandpackFiles(rawFiles) {
    const processed = {};
    Object.entries(rawFiles).forEach(([path, content]) => {
        const code = typeof content === 'string' ? content : content?.code;
        if (!code) return;
        let sp = sandpackPath(path);
        // Normalise JSX-in-.js → .jsx
        if (sp.endsWith('.js') && !sp.includes('/index') && (code.includes('</') || code.includes('/>')))
            sp = sp.replace(/\.js$/, '.jsx');
        processed[sp] = { code: sanitize(code) };
    });
    // Merge with defaults — generated /App.jsx overrides placeholder
    return { ...Lookup.DEFAULT_FILE, ...processed };
}

export default function PreviewPage() {
    const { id }    = useParams();
    const router    = useRouter();
    const [files, setFiles]               = useState(null);
    const [projectTitle, setProjectTitle] = useState('');
    const [loading, setLoading]           = useState(true);
    const [error, setError]               = useState('');

    useEffect(() => {
        if (!id) return;
        (async () => {
            setLoading(true);
            try {
                const res  = await fetch(`${BACKEND_URL}/api/workspaces/${id}`);
                if (!res.ok) throw new Error('Workspace not found');
                const data = await res.json();
                if (!data.fileData || Object.keys(data.fileData).length === 0)
                    throw new Error('No generated files yet. Go back and generate an app first.');
                setFiles(buildSandpackFiles(data.fileData));
                if (data.projectTitle) setProjectTitle(data.projectTitle);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        })();
    }, [id]);

    if (loading) return (
        <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center gap-4">
            <div className="w-12 h-12 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin"/>
            <p className="text-gray-400 text-sm">Loading preview…</p>
        </div>
    );

    if (error) return (
        <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center gap-6 px-4 text-center">
            <span className="text-5xl">⚠️</span>
            <div>
                <h2 className="text-white text-xl font-semibold mb-2">Preview Unavailable</h2>
                <p className="text-gray-400 max-w-sm text-sm">{error}</p>
            </div>
            <button onClick={() => router.push(`/workspace/${id}`)}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg font-medium transition-colors text-sm">
                <ArrowLeft className="h-4 w-4"/> Back to Workspace
            </button>
        </div>
    );

    return (
        <div className="min-h-screen bg-gray-950 flex flex-col">
            {/* ── Top bar ─────────────────────────────────────────── */}
            <div className="flex items-center justify-between px-4 py-2.5 bg-gray-900 border-b border-gray-800 shrink-0">
                <div className="flex items-center gap-3">
                    <button onClick={() => router.push(`/workspace/${id}`)}
                        className="flex items-center gap-1.5 text-gray-400 hover:text-white text-sm transition-colors">
                        <ArrowLeft className="h-4 w-4"/> Back to Editor
                    </button>
                    {projectTitle && (
                        <>
                            <span className="text-gray-700">|</span>
                            <span className="text-white text-sm font-semibold truncate max-w-xs">{projectTitle}</span>
                        </>
                    )}
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5 text-xs text-green-400">
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"/>
                        Live Preview
                    </div>
                    <a href={`/preview/${id}`} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-1 text-gray-400 hover:text-white text-xs transition-colors">
                        <ExternalLink className="h-3.5 w-3.5"/> Open in tab
                    </a>
                </div>
            </div>

            {/* ── Full-screen Sandpack Preview ─────────────────────── */}
            <div className="flex-1">
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
                        recompileDelay: 500,
                        autorun: true,
                    }}
                >
                    <SandpackPreview
                        style={{ height: 'calc(100vh - 49px)' }}
                        showNavigator
                        showOpenInCodeSandbox={false}
                        showRefreshButton
                    />
                </SandpackProvider>
            </div>
        </div>
    );
}
