// @ts-nocheck
'use client';
import { useState, useEffect, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import {
  Send, Upload, Loader2, CheckCircle, XCircle, AlertCircle,
  ChevronRight, Code2, History, Globe, Zap
} from 'lucide-react';
import { AgentTeam } from '@/components/AgentTeam';
import { ProgressLog } from '@/components/ProgressLog';
import { FileExplorer } from '@/components/FileExplorer';
import { LiveLinks } from '@/components/LiveLinks';
import WorkspaceDashboard from '@/components/WorkspaceDashboard';
import {
  GenerationJob, GeneratedFile, LogEntry, AgentStatus, AgentName, AllUrls
} from '@/types';

const AGENT_SERVICE = 'http://localhost:5000';

const EXAMPLE_SRS = {
  projectName: "task-manager",
  description: "A simple task management application",
  features: [
    "User authentication (register/login)",
    "Create, read, update, delete tasks",
    "Task status tracking (todo, in-progress, done)",
    "Task priority (low, medium, high)",
    "Dashboard with task statistics"
  ],
  techStack: "MERN Stack Microservices",
  users: ["single user - internal use"],
  database: "MongoDB"
};

const STATUS_STEPS = [
  'pending', 'planning', 'generating', 'analyzing', 'fixing', 'installing', 'running', 'complete'
] as const;

function StatusBar({ status, progress }: { status: string; progress: number }) {
  const idx = STATUS_STEPS.indexOf(status as any);
  const colors: Record<string, string> = {
    pending:    'text-slate-400',
    planning:   'text-purple-400',
    generating: 'text-cyan-400',
    analyzing:  'text-green-400',
    fixing:     'text-amber-400',
    installing: 'text-blue-400',
    running:    'text-orange-400',
    complete:   'text-green-400',
    error:      'text-red-400'
  };

  return (
    <div className="px-4 py-2 border-b border-[#1a1a2e] flex items-center gap-3">
      <div className="flex items-center gap-2 text-xs">
        <span className={`font-medium capitalize ${colors[status] || 'text-slate-400'}`}>
          {status === 'complete' ? '✓ Complete' :
           status === 'error' ? '✗ Error' :
           status === 'pending' ? 'Ready' :
           `● ${status.charAt(0).toUpperCase() + status.slice(1)}...`}
        </span>
      </div>

      {/* Progress bar */}
      <div className="flex-1 h-1 bg-[#1a1a2e] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            status === 'complete' ? 'bg-green-400' :
            status === 'error' ? 'bg-red-400' :
            'progress-gradient'
          }`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <span className="text-xs text-slate-500 w-8 text-right">{progress}%</span>
    </div>
  );
}

export default function Home() {
  return <WorkspaceDashboard />;

  const [srsInput, setSrsInput] = useState(JSON.stringify(EXAMPLE_SRS, null, 2));
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<GeneratedFile | null>(null);
  const [streamingToken, setStreamingToken] = useState('');
  const [currentAgent, setCurrentAgent] = useState('');
  const [activeTab, setActiveTab] = useState<'log' | 'files' | 'links'>('log');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [srsError, setSrsError] = useState<string | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const streamBufferRef = useRef('');

  // Load history
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${AGENT_SERVICE}/api/history`);
      const data = await res.json();
      setHistory(data.jobs || []);
    } catch {}
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  // Socket.IO setup
  useEffect(() => {
    const socket = io(AGENT_SERVICE, { transports: ['websocket', 'polling'] });
    socketRef.current = socket;
    return () => { socket.disconnect(); };
  }, []);

  const joinJob = useCallback((jId: string) => {
    socketRef.current?.emit('join:job', jId);

    const socket = socketRef.current;
    if (!socket) return;

    socket.off('agent:working');
    socket.off('agent:token');
    socket.off('agent:stream');
    socket.off('log');
    socket.off('status:update');
    socket.off('progress:update');
    socket.off('files:generated');
    socket.off('generation:complete');
    socket.off('generation:error');
    socket.off('service:running');
    socket.off('service:error');
    socket.off('plan:ready');

    socket.on('agent:working', ({ agent, message }: any) => {
      setCurrentAgent(agent);
      setStreamingToken('');
      streamBufferRef.current = '';
      setAgents(prev => {
        const updated = prev.map(a => a.status === 'working' ? { ...a, status: 'done' as const } : a);
        const exists = updated.find(a => a.name === agent);
        if (exists) return updated.map(a => a.name === agent ? { ...a, status: 'working', message } : a);
        return [...updated, { name: agent as AgentName, status: 'working', message }];
      });
    });

    socket.on('agent:token', ({ agent, token }: any) => {
      streamBufferRef.current += token;
      setStreamingToken(streamBufferRef.current);
    });

    socket.on('agent:stream', ({ agent, token }: any) => {
      streamBufferRef.current += token;
      setStreamingToken(streamBufferRef.current);
    });

    socket.on('log', (log: LogEntry) => {
      setLogs(prev => [...prev, { ...log, timestamp: log.timestamp || new Date().toISOString() }]);
    });

    socket.on('status:update', ({ status, progress, agent }: any) => {
      setJob(prev => prev ? { ...prev, status, progress, currentAgent: agent } : null);
      setCurrentAgent(agent || '');
    });

    socket.on('progress:update', ({ progress }: any) => {
      setJob(prev => prev ? { ...prev, progress } : null);
    });

    socket.on('plan:ready', ({ plan }: any) => {
      setJob(prev => prev ? { ...prev, plan } : null);
    });

    socket.on('files:generated', ({ service, files }: any) => {
      setActiveTab('files');
      // Poll for latest files
      setTimeout(() => fetchJobFiles(jId), 1000);
    });

    socket.on('service:running', ({ service, port, url }: any) => {
      setJob(prev => {
        if (!prev) return null;
        const services = (prev.services || []).map(s =>
          s.name === service ? { ...s, status: 'running' as const, url } : s
        );
        return { ...prev, services };
      });
      setActiveTab('links');
    });

    socket.on('service:error', ({ service, error }: any) => {
      setJob(prev => {
        if (!prev) return null;
        const services = (prev.services || []).map(s =>
          s.name === service ? { ...s, status: 'error' as const, error } : s
        );
        return { ...prev, services };
      });
    });

    socket.on('generation:complete', ({ jobId: jId, urls }: any) => {
      setStreamingToken('');
      streamBufferRef.current = '';
      setJob(prev => prev ? { ...prev, status: 'complete', progress: 100, allUrls: urls } : null);
      setAgents(prev => prev.map(a => a.status === 'working' ? { ...a, status: 'done' } : a));
      setActiveTab('links');
      setLoading(false);
      loadHistory();
    });

    socket.on('generation:error', ({ error }: any) => {
      setStreamingToken('');
      setJob(prev => prev ? { ...prev, status: 'error', error } : null);
      setError(error);
      setLoading(false);
    });
  }, []);

  const fetchJobFiles = async (jId: string) => {
    try {
      const res = await fetch(`${AGENT_SERVICE}/api/generate/${jId}/files`);
      const data = await res.json();
      if (data.files) {
        // Fetch content for visible files (limit to avoid too many requests)
        setGeneratedFiles(data.files.slice(0, 200).map((f: any) => ({
          path: f.path, service: f.service, content: ''
        })));
      }
    } catch {}
  };

  const fetchFileContent = async (file: GeneratedFile) => {
    if (file.content) { setSelectedFile(file); return; }
    try {
      const res = await fetch(`${AGENT_SERVICE}/api/generate/${jobId}/file?filePath=${encodeURIComponent(file.path)}`);
      const data = await res.json();
      const withContent = { ...file, content: data.content || '' };
      setSelectedFile(withContent);
      setGeneratedFiles(prev => prev.map(f => f.path === file.path ? withContent : f));
    } catch {}
  };

  const validateSRS = (input: string): object | null => {
    try {
      const parsed = JSON.parse(input);
      if (typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Must be a JSON object');
      return parsed;
    } catch (e: any) {
      setSrsError(e.message);
      return null;
    }
  };

  const handleGenerate = async () => {
    setSrsError(null);
    setError(null);
    const srs = validateSRS(srsInput);
    if (!srs) return;

    setLoading(true);
    setLogs([]);
    setGeneratedFiles([]);
    setSelectedFile(null);
    setAgents([]);
    setStreamingToken('');
    streamBufferRef.current = '';
    setJob(null);
    setActiveTab('log');

    try {
      const res = await fetch(`${AGENT_SERVICE}/api/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ srs })
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.message || data.error || 'Failed to start generation');
        setLoading(false);
        return;
      }

      const newJobId = data.jobId;
      setJobId(newJobId);
      setJob({ jobId: newJobId, status: 'pending', progress: 0, currentAgent: '', logs: [] });
      joinJob(newJobId);

    } catch (err: any) {
      setError(`Cannot connect to agent service at ${AGENT_SERVICE}. Is it running?`);
      setLoading(false);
    }
  };

  const getFileLanguage = (path: string): string => {
    if (path.endsWith('.tsx') || path.endsWith('.ts')) return 'typescript';
    if (path.endsWith('.jsx') || path.endsWith('.js')) return 'javascript';
    if (path.endsWith('.json')) return 'json';
    if (path.endsWith('.css')) return 'css';
    if (path.endsWith('.html')) return 'html';
    if (path.endsWith('.env')) return 'bash';
    if (path.endsWith('.sh')) return 'bash';
    return 'javascript';
  };

  const handleLoadHistory = async (histJob: any) => {
    setShowHistory(false);
    setJobId(histJob.jobId);
    try {
      const res = await fetch(`${AGENT_SERVICE}/api/generate/${histJob.jobId}`);
      const data = await res.json();
      setJob(data);
      setLogs(data.logs || []);
      await fetchJobFiles(histJob.jobId);
      if (data.allUrls) setActiveTab('links');
    } catch {}
  };

  return (
    <div className="flex flex-col h-screen bg-[#080810]">
      {/* ── Header ────────────────────────────────────────────── */}
      <header className="flex items-center gap-3 px-4 py-3 border-b border-[#1a1a2e] shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-purple-600 to-cyan-600 flex items-center justify-center">
            <Zap size={14} className="text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white leading-none">Code Developer Agent</h1>
            <p className="text-[10px] text-slate-500">Powered by Ollama + DeepSeek</p>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={() => { setShowHistory(!showHistory); loadHistory(); }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#0f0f1a] border border-[#1a1a2e] rounded-lg hover:border-purple-500/40 text-slate-400 hover:text-slate-200 transition-all"
          >
            <History size={12} />
            History ({history.length})
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* ── Left Panel: SRS Input ────────────────────────────── */}
        <div className="w-80 shrink-0 flex flex-col border-r border-[#1a1a2e]">
          <div className="p-3 border-b border-[#1a1a2e]">
            <div className="flex items-center gap-2 mb-2">
              <Upload size={13} className="text-purple-400" />
              <span className="text-xs font-medium text-slate-300">SRS JSON Document</span>
            </div>
            <p className="text-[11px] text-slate-500">
              Paste your Software Requirements Specification as JSON.
              The AI team will build a full MERN microservice app.
            </p>
          </div>

          <div className="flex-1 p-3 flex flex-col gap-3 overflow-hidden">
            <textarea
              value={srsInput}
              onChange={e => { setSrsInput(e.target.value); setSrsError(null); }}
              className="flex-1 bg-[#0a0a14] border border-[#1a1a2e] rounded-lg p-3 text-xs font-mono text-slate-300 resize-none focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/20 transition-all"
              placeholder='{"projectName": "my-app", "description": "...", "features": [...]}'
              spellCheck={false}
            />

            {srsError && (
              <div className="flex items-start gap-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
                <AlertCircle size={12} className="shrink-0 mt-0.5" />
                <span>Invalid JSON: {srsError}</span>
              </div>
            )}

            {error && (
              <div className="flex items-start gap-2 p-2 bg-red-500/10 border border-red-500/20 rounded-lg text-xs text-red-400">
                <XCircle size={12} className="shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            <button
              onClick={handleGenerate}
              disabled={loading}
              className="flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-all duration-200 shadow-lg shadow-purple-500/20"
            >
              {loading ? (
                <><Loader2 size={14} className="animate-spin" /> Generating App...</>
              ) : (
                <><Send size={14} /> Generate App</>
              )}
            </button>

            {/* Example SRS hint */}
            <button
              onClick={() => setSrsInput(JSON.stringify(EXAMPLE_SRS, null, 2))}
              className="text-[11px] text-slate-600 hover:text-slate-400 transition-colors underline"
            >
              Load example SRS (Task Manager)
            </button>
          </div>

          {/* Plan preview */}
          {job?.plan && (
            <div className="p-3 border-t border-[#1a1a2e]">
              <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wider mb-2">Project Plan</div>
              <div className="text-xs font-bold text-purple-300 mb-1">{job.plan.projectName}</div>
              <div className="space-y-1">
                {job.plan.services?.map((svc, i) => (
                  <div key={i} className="flex items-center gap-2 text-[11px] text-slate-400">
                    <ChevronRight size={10} className="text-cyan-500" />
                    <span>{svc.name}</span>
                    <span className="ml-auto text-slate-600">:{svc.port}</span>
                  </div>
                ))}
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <ChevronRight size={10} className="text-blue-500" />
                  <span>frontend</span>
                  <span className="ml-auto text-slate-600">:3001</span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <Globe size={10} className="text-orange-500" />
                  <span>gateway (all services)</span>
                  <span className="ml-auto text-slate-600">:8080</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Right Panel ───────────────────────────────────────── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Agent team bar */}
          <AgentTeam agents={agents} currentAgent={currentAgent} streamingToken={streamingToken} />

          {/* Status bar */}
          {job && <StatusBar status={job.status} progress={job.progress} />}

          {/* Tab bar */}
          <div className="flex border-b border-[#1a1a2e] shrink-0">
            {[
              { key: 'log',   label: 'Execution Log', icon: <Code2 size={11} /> },
              { key: 'files', label: `Files (${generatedFiles.length})`, icon: <Code2 size={11} /> },
              { key: 'links', label: 'Live Links', icon: <Globe size={11} /> }
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key as any)}
                className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium border-b-2 transition-all ${
                  activeTab === tab.key
                    ? 'border-purple-500 text-purple-400 bg-purple-500/5'
                    : 'border-transparent text-slate-500 hover:text-slate-300 hover:bg-white/3'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Main content area */}
          <div className="flex-1 overflow-hidden flex">
            {activeTab === 'log' && (
              <div className="flex-1">
                <ProgressLog logs={logs} streamingToken={streamingToken} currentAgent={currentAgent} />
              </div>
            )}

            {activeTab === 'files' && (
              <>
                {/* File tree */}
                <div className="w-56 shrink-0 border-r border-[#1a1a2e] overflow-hidden">
                  <div className="px-3 py-2 border-b border-[#1a1a2e] text-[10px] text-slate-500 font-medium uppercase tracking-wider">
                    File Explorer
                  </div>
                  <FileExplorer
                    files={generatedFiles}
                    onSelect={fetchFileContent}
                    selectedPath={selectedFile?.path || ''}
                  />
                </div>

                {/* Code viewer */}
                <div className="flex-1 overflow-auto">
                  {selectedFile ? (
                    <div className="h-full flex flex-col">
                      <div className="px-3 py-2 border-b border-[#1a1a2e] flex items-center gap-2 text-xs shrink-0">
                        <Code2 size={11} className="text-purple-400" />
                        <span className="text-slate-300 font-mono">{selectedFile.path}</span>
                        <span className="ml-auto text-slate-600">{selectedFile.service}</span>
                      </div>
                      <div className="flex-1 overflow-auto">
                        <SyntaxHighlighter
                          language={getFileLanguage(selectedFile.path)}
                          style={vscDarkPlus}
                          customStyle={{ margin: 0, background: '#080810', fontSize: '11px', minHeight: '100%' }}
                          showLineNumbers
                          lineNumberStyle={{ color: '#2d2d4e', fontSize: '10px' }}
                        >
                          {selectedFile.content || '// Loading...'}
                        </SyntaxHighlighter>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-full text-slate-600 text-xs">
                      Select a file to view its content
                    </div>
                  )}
                </div>
              </>
            )}

            {activeTab === 'links' && (
              <div className="flex-1 overflow-auto">
                <LiveLinks urls={job?.allUrls || null} services={job?.services || []} />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── History Panel (overlay) ──────────────────────────── */}
      {showHistory && (
        <div className="absolute top-14 right-4 w-80 bg-[#0f0f1a] border border-[#1a1a2e] rounded-xl shadow-2xl z-50 overflow-hidden animate-[fadeIn_0.2s_ease-in-out]">
          <div className="px-4 py-3 border-b border-[#1a1a2e] flex items-center justify-between">
            <span className="text-sm font-medium text-slate-200">Generation History</span>
            <button onClick={() => setShowHistory(false)} className="text-slate-500 hover:text-slate-300 text-lg leading-none">&times;</button>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {history.length === 0 ? (
              <div className="text-center text-slate-600 text-xs py-8">No previous generations</div>
            ) : history.map((j, i) => (
              <button
                key={i}
                onClick={() => handleLoadHistory(j)}
                className="w-full text-left px-4 py-3 border-b border-[#1a1a2e] hover:bg-white/3 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium ${j.status === 'complete' ? 'text-green-400' : j.status === 'error' ? 'text-red-400' : 'text-amber-400'}`}>
                    {j.status === 'complete' ? '✓' : j.status === 'error' ? '✗' : '●'}
                  </span>
                  <span className="text-sm text-slate-200">{j.projectName}</span>
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  {j.servicesCount} services • {new Date(j.createdAt).toLocaleString()}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
