'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { io, Socket } from 'socket.io-client';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { AlertCircle, Clock3, FolderOpen, Layers3, Loader2, Play, RefreshCcw, Sparkles } from 'lucide-react';

import { AgentTeam } from '@/components/AgentTeam';
import { FileExplorer } from '@/components/FileExplorer';
import { LiveLinks } from '@/components/LiveLinks';
import { ProgressLog } from '@/components/ProgressLog';
import { WorkspaceAuditPanel } from '@/components/WorkspaceAuditPanel';
import { WorkspaceStatusBar } from '@/components/WorkspaceStatusBar';
import { WorkspaceThreadPanel } from '@/components/WorkspaceThreadPanel';
import type {
  AgentStatus,
  GeneratedFile,
  GenerationJob,
  LogEntry,
  ThreadMessage,
  WorkspaceDetail,
  WorkspaceSummary
} from '@/types';

const AGENT_SERVICE = 'http://localhost:5000';
const EXAMPLE_SRS = {
  projectName: 'task-manager',
  description: 'A task management application with auth, dashboards, and analytics.',
  features: ['User authentication', 'Task CRUD', 'Status workflow', 'Priority and due dates', 'Dashboard metrics'],
  techStack: 'MERN Stack Microservices',
  database: 'MongoDB'
};

type DashboardMode = 'new' | 'continue' | 'followup';
type DashboardTab = 'log' | 'plan' | 'audit' | 'threads' | 'files' | 'links';

const TABS: { id: DashboardTab; label: string }[] = [
  { id: 'log', label: 'Execution Log' },
  { id: 'plan', label: 'Plan' },
  { id: 'audit', label: 'Artifact Audit' },
  { id: 'threads', label: 'Threads' },
  { id: 'files', label: 'Files' },
  { id: 'links', label: 'Live Links' }
];

const FALLBACK_MODELS = [
  'kimi-k2.5:cloud',
  'deepseek-v3.1:671b-cloud',
  'gpt-oss:120b-cloud',
  'gemma4:31b-cloud',
  'qwen2.5:14b'
];

const TIMEOUT_OPTIONS = [300, 600, 900, 1200];

function prettyJson(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value ?? '');
  }
}

export function WorkspaceDashboard() {
  const [mode, setMode] = useState<DashboardMode>('new');
  const [activeTab, setActiveTab] = useState<DashboardTab>('log');
  const [srsInput, setSrsInput] = useState(prettyJson(EXAMPLE_SRS));
  const [followUpTask, setFollowUpTask] = useState('create task-service following Route -> Controller -> Service -> Model');
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [streamingToken, setStreamingToken] = useState('');
  const [currentAgent, setCurrentAgent] = useState('');
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<GeneratedFile | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState('');
  const [workspaceDetail, setWorkspaceDetail] = useState<WorkspaceDetail | null>(null);
  const [selectedThreadId, setSelectedThreadId] = useState('');
  const [threadMessages, setThreadMessages] = useState<ThreadMessage[]>([]);
  const [modelOptions, setModelOptions] = useState<string[]>(FALLBACK_MODELS);
  const [selectedModel, setSelectedModel] = useState('qwen2.5:14b');
  const [timeoutSeconds, setTimeoutSeconds] = useState(900);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<Socket | null>(null);
  const streamBufferRef = useRef('');

  const visibleTabs = useMemo(() => TABS.map((tab) => tab.id === 'files'
    ? { ...tab, label: `Files (${generatedFiles.length})` }
    : tab), [generatedFiles.length]);

  const loadWorkspaces = useCallback(async () => {
    const response = await fetch(`${AGENT_SERVICE}/api/workspaces`);
    const data = await response.json();
    setWorkspaces(data.workspaces || []);
  }, []);

  const loadRunOptions = useCallback(async () => {
    try {
      const response = await fetch(`${AGENT_SERVICE}/api/generate/options`);
      const data = await response.json();
      if (!response.ok) {
        return;
      }
      setModelOptions(data.models || FALLBACK_MODELS);
      if (data.defaultModel) setSelectedModel(data.defaultModel);
      if (data.defaultTimeoutSeconds) setTimeoutSeconds(data.defaultTimeoutSeconds);
    } catch {
      setModelOptions(FALLBACK_MODELS);
    }
  }, []);

  const fetchJobFiles = useCallback(async (runId: string) => {
    const response = await fetch(`${AGENT_SERVICE}/api/generate/${runId}/files`);
    const data = await response.json();
    setGeneratedFiles((data.files || []).map((file: { path: string; service: string }) => ({
      path: file.path,
      service: file.service,
      content: ''
    })));
  }, []);

  const loadJob = useCallback(async (runId: string) => {
    const response = await fetch(`${AGENT_SERVICE}/api/generate/${runId}`);
    const data = await response.json();
    setJob(data);
    setJobId(runId);
    if (data.workspaceId) setSelectedWorkspaceId(data.workspaceId);
    if (data.threadId) setSelectedThreadId(data.threadId);
    if (data.model) setSelectedModel(data.model);
    if (data.timeoutSeconds) setTimeoutSeconds(data.timeoutSeconds);
    setLogs(data.logs || []);
    setCurrentAgent(data.currentAgent || '');
    await fetchJobFiles(runId);
  }, [fetchJobFiles]);

  const loadWorkspace = useCallback(async (workspaceId: string) => {
    if (!workspaceId) return;
    const detailResponse = await fetch(`${AGENT_SERVICE}/api/workspaces/${workspaceId}`);
    const detail = await detailResponse.json();
    setWorkspaceDetail(detail);
    setSelectedThreadId(detail.threads?.[0]?.threadId || '');
    if (detail.workspace?.lastRunSettings?.model) {
      setSelectedModel(detail.workspace.lastRunSettings.model);
    }
    if (detail.workspace?.lastRunSettings?.timeoutSeconds) {
      setTimeoutSeconds(detail.workspace.lastRunSettings.timeoutSeconds);
    }

    if (detail.workspace?.latestGenerationId) {
      await loadJob(detail.workspace.latestGenerationId);
    }
  }, [loadJob]);

  const loadThreadMessages = useCallback(async (threadId: string) => {
    if (!threadId) return;
    const response = await fetch(`${AGENT_SERVICE}/api/threads/${threadId}/messages`);
    const data = await response.json();
    setThreadMessages(data.messages || []);
  }, []);

  const fetchFileContent = useCallback(async (file: GeneratedFile) => {
    if (!jobId) return;
    if (file.content) {
      setSelectedFile(file);
      return;
    }
    const response = await fetch(`${AGENT_SERVICE}/api/generate/${jobId}/file?filePath=${encodeURIComponent(file.path)}`);
    const data = await response.json();
    const nextFile = { ...file, content: data.content || '' };
    setSelectedFile(nextFile);
    setGeneratedFiles((current) => current.map((item) => item.path === file.path ? nextFile : item));
  }, [jobId]);

  const joinJob = useCallback((runId: string) => {
    const socket = socketRef.current;
    if (!socket) return;

    socket.emit('join:job', runId);
    ['agent:working', 'agent:token', 'agent:stream', 'log', 'status:update', 'progress:update', 'files:generated', 'generation:complete', 'generation:error', 'service:running'].forEach((event) => socket.off(event));

    socket.on('agent:working', ({ agent, message }: { agent: string; message: string }) => {
      setCurrentAgent(agent);
      setAgents((current) => {
        const next = current.map((item) => item.status === 'working' ? { ...item, status: 'done' as const } : item);
        const existing = next.find((item) => item.name === agent);
        if (existing) {
          return next.map((item) => item.name === agent ? { ...item, status: 'working', message } : item);
        }
        return [...next, { name: agent as AgentStatus['name'], status: 'working', message }];
      });
    });

    const handleStream = ({ token }: { token: string }) => {
      streamBufferRef.current += token;
      setStreamingToken(streamBufferRef.current);
    };

    socket.on('agent:token', handleStream);
    socket.on('agent:stream', handleStream);
    socket.on('log', (entry: LogEntry) => setLogs((current) => [...current, { ...entry, timestamp: entry.timestamp || new Date().toISOString() }]));
    socket.on('status:update', ({ status, progress, agent }: { status: string; progress: number; agent: string }) => {
      setJob((current) => current ? { ...current, status, progress, currentAgent: agent, stage: status } : current);
      setCurrentAgent(agent);
    });
    socket.on('progress:update', ({ progress }: { progress: number }) => setJob((current) => current ? { ...current, progress } : current));
    socket.on('files:generated', async () => {
      setActiveTab('files');
      await fetchJobFiles(runId);
    });
    socket.on('service:running', ({ service, url }: { service: string; url: string }) => {
      setJob((current) => current?.services ? {
        ...current,
        services: current.services.map((item) => item.name === service ? { ...item, status: 'running', url } : item)
      } : current);
    });
    socket.on('generation:complete', async () => {
      streamBufferRef.current = '';
      setStreamingToken('');
      setLoading(false);
      setAgents((current) => current.map((agent) => agent.status === 'working' ? { ...agent, status: 'done' } : agent));
      await loadJob(runId);
      await loadWorkspaces();
      if (selectedWorkspaceId) await loadWorkspace(selectedWorkspaceId);
      setActiveTab('links');
    });
    socket.on('generation:error', ({ error: message, errorSummary }: { error: string; errorSummary?: string }) => {
      setLoading(false);
      setError(errorSummary || message);
      streamBufferRef.current = '';
      setStreamingToken('');
    });
  }, [fetchJobFiles, loadJob, loadWorkspace, loadWorkspaces, selectedWorkspaceId]);

  useEffect(() => {
    const socket = io(AGENT_SERVICE, { transports: ['websocket', 'polling'] });
    socketRef.current = socket;
    loadWorkspaces().catch((loadError) => setError(loadError.message));
    loadRunOptions().catch(() => undefined);
    return () => {
      socket.disconnect();
    };
  }, [loadRunOptions, loadWorkspaces]);

  useEffect(() => {
    if (selectedWorkspaceId) {
      loadWorkspace(selectedWorkspaceId).catch((loadError) => setError(loadError.message));
    }
  }, [loadWorkspace, selectedWorkspaceId]);

  useEffect(() => {
    if (selectedThreadId) {
      loadThreadMessages(selectedThreadId).catch((loadError) => setError(loadError.message));
    }
  }, [loadThreadMessages, selectedThreadId]);

  const startNewWorkspace = async () => {
    setError(null);
    setLoading(true);
    setLogs([]);
    setGeneratedFiles([]);
    setSelectedFile(null);
    setAgents([]);
    streamBufferRef.current = '';
    setStreamingToken('');

    let parsedSrs: object;
    try {
      parsedSrs = JSON.parse(srsInput);
    } catch (parseError) {
      setLoading(false);
      setError((parseError as Error).message);
      return;
    }

    const response = await fetch(`${AGENT_SERVICE}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'new', srs: parsedSrs, model: selectedModel, timeoutSeconds })
    });
    const data = await response.json();
    if (!response.ok) {
      setLoading(false);
      setError(data.message || data.error || 'Failed to start workspace run');
      return;
    }

    setJob({ jobId: data.jobId, status: 'pending', progress: 0, currentAgent: '', mode: 'new', model: selectedModel, timeoutSeconds });
    setJobId(data.jobId);
    joinJob(data.jobId);
  };

  const continueWorkspace = async () => {
    if (!selectedWorkspaceId) {
      setError('Select a workspace first.');
      return;
    }
    await loadWorkspace(selectedWorkspaceId);
    setMode('followup');
  };

  const runFollowUpTask = async () => {
    if (!selectedWorkspaceId && !selectedThreadId) {
      setError('Select a workspace or thread first.');
      return;
    }
    if (!followUpTask.trim()) {
      setError('Describe the follow-up task.');
      return;
    }

    setLoading(true);
    setError(null);
    setLogs([]);
    setGeneratedFiles([]);
    setSelectedFile(null);
    setAgents([]);
    streamBufferRef.current = '';
    setStreamingToken('');

    const url = selectedThreadId ? `${AGENT_SERVICE}/api/threads/${selectedThreadId}/run` : `${AGENT_SERVICE}/api/generate`;
    const body = selectedThreadId
      ? { task: followUpTask, model: selectedModel, timeoutSeconds }
      : { mode: 'continue', workspaceId: selectedWorkspaceId, task: followUpTask, model: selectedModel, timeoutSeconds };

    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) {
      setLoading(false);
      setError(data.message || data.error || 'Failed to start follow-up task');
      return;
    }

    setJob({ jobId: data.jobId, status: 'pending', progress: 0, currentAgent: '', mode: 'continue', task: followUpTask, model: selectedModel, timeoutSeconds });
    setJobId(data.jobId);
    joinJob(data.jobId);
  };

  const selectedWorkspace = workspaces.find((workspace) => workspace.workspaceId === selectedWorkspaceId) || null;

  return (
    <div className="flex h-screen flex-col bg-[#080810]">
      <header className="flex items-center gap-4 border-b border-[#1a1a2e] px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 to-purple-600">
            <Sparkles size={18} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white">Agent2 Workspace Studio</div>
            <div className="text-xs text-slate-500">Instruction-aware local workflow for MERN microservices</div>
          </div>
        </div>
        <button
          onClick={() => loadWorkspaces().catch((loadError) => setError(loadError.message))}
          className="ml-auto inline-flex items-center gap-2 rounded-lg border border-[#1a1a2e] px-3 py-2 text-xs text-slate-300 transition hover:border-[#2c2c44] hover:bg-white/5"
        >
          <RefreshCcw size={12} />
          Refresh Workspaces
        </button>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="w-[360px] shrink-0 border-r border-[#1a1a2e]">
          <div className="border-b border-[#1a1a2e] p-4">
            <div className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-[0.2em] text-slate-500">
              <Layers3 size={12} />
              Workspace Actions
            </div>
            <div className="mb-4 grid grid-cols-3 gap-2">
              {([
                ['new', 'New Workspace'],
                ['continue', 'Continue Workspace'],
                ['followup', 'Run Follow-up Task']
              ] as [DashboardMode, string][]).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setMode(value)}
                  className={`rounded-xl px-3 py-3 text-left text-xs transition ${
                    mode === value ? 'bg-purple-500/10 text-purple-300' : 'bg-[#0f0f1a] text-slate-400 hover:bg-white/5 hover:text-slate-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="mb-4 grid grid-cols-2 gap-3">
              <label className="space-y-2">
                <div className="text-[11px] font-medium uppercase tracking-[0.2em] text-slate-500">Model</div>
                <select value={selectedModel} onChange={(event) => setSelectedModel(event.target.value)} className="w-full rounded-xl border border-[#1a1a2e] bg-[#0f0f1a] px-3 py-3 text-sm text-slate-200 outline-none">
                  {modelOptions.map((model) => <option key={model} value={model}>{model}</option>)}
                </select>
              </label>
              <label className="space-y-2">
                <div className="text-[11px] font-medium uppercase tracking-[0.2em] text-slate-500">Timeout</div>
                <select value={timeoutSeconds} onChange={(event) => setTimeoutSeconds(Number(event.target.value))} className="w-full rounded-xl border border-[#1a1a2e] bg-[#0f0f1a] px-3 py-3 text-sm text-slate-200 outline-none">
                  {TIMEOUT_OPTIONS.map((seconds) => <option key={seconds} value={seconds}>{seconds}s</option>)}
                </select>
              </label>
            </div>

            {mode === 'new' && (
              <div className="space-y-3">
                <textarea value={srsInput} onChange={(event) => setSrsInput(event.target.value)} className="h-52 w-full rounded-2xl border border-[#1a1a2e] bg-[#0f0f1a] p-3 font-mono text-xs text-slate-300 outline-none transition focus:border-purple-500/40" />
                <button onClick={startNewWorkspace} disabled={loading} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 px-4 py-3 text-sm font-medium text-white disabled:opacity-60">
                  {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                  Create Workspace
                </button>
              </div>
            )}

            {mode !== 'new' && (
              <div className="space-y-3">
                <select value={selectedWorkspaceId} onChange={(event) => setSelectedWorkspaceId(event.target.value)} className="w-full rounded-xl border border-[#1a1a2e] bg-[#0f0f1a] px-3 py-3 text-sm text-slate-200 outline-none">
                  <option value="">Select workspace</option>
                  {workspaces.map((workspace) => <option key={workspace.workspaceId} value={workspace.workspaceId}>{workspace.name}</option>)}
                </select>
                {mode === 'continue' && (
                  <button onClick={continueWorkspace} className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-[#1a1a2e] bg-[#0f0f1a] px-4 py-3 text-sm text-slate-200 transition hover:border-[#2c2c44]">
                    <FolderOpen size={14} />
                    Load Workspace
                  </button>
                )}
                {mode === 'followup' && (
                  <>
                    <select value={selectedThreadId} onChange={(event) => setSelectedThreadId(event.target.value)} className="w-full rounded-xl border border-[#1a1a2e] bg-[#0f0f1a] px-3 py-3 text-sm text-slate-200 outline-none">
                      <option value="">Select thread (optional)</option>
                      {(workspaceDetail?.threads || []).map((thread) => <option key={thread.threadId} value={thread.threadId}>{thread.title}</option>)}
                    </select>
                    <textarea value={followUpTask} onChange={(event) => setFollowUpTask(event.target.value)} className="h-28 w-full rounded-2xl border border-[#1a1a2e] bg-[#0f0f1a] p-3 text-sm text-slate-200 outline-none transition focus:border-cyan-500/40" />
                    <button onClick={runFollowUpTask} disabled={loading} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 px-4 py-3 text-sm font-medium text-white disabled:opacity-60">
                      {loading ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                      Run Follow-up Task
                    </button>
                  </>
                )}
              </div>
            )}

            {error && (
              <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
                <div className="mb-1 flex items-center gap-2 font-medium"><AlertCircle size={12} />Error</div>
                <div>{error}</div>
                <div className="mt-2 text-[11px] text-red-200/80">Model: {selectedModel} | Timeout: {timeoutSeconds}s</div>
              </div>
            )}
          </div>

          <div className="min-h-0 overflow-y-auto p-3">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-xs font-medium uppercase tracking-[0.2em] text-slate-500">Workspaces</div>
              <div className="text-[11px] text-slate-600">{workspaces.length}</div>
            </div>
            <div className="space-y-2">
              {workspaces.map((workspace) => (
                <button key={workspace.workspaceId} onClick={() => setSelectedWorkspaceId(workspace.workspaceId)} className={`w-full rounded-2xl border px-3 py-3 text-left transition ${selectedWorkspaceId === workspace.workspaceId ? 'border-purple-500/30 bg-purple-500/10' : 'border-[#1a1a2e] bg-[#0f0f1a] hover:border-[#2c2c44]'}`}>
                  <div className="mb-1 flex items-center justify-between">
                    <div className="text-sm font-semibold text-white">{workspace.name}</div>
                    <div className={`text-[11px] uppercase tracking-[0.2em] ${workspace.status === 'error' ? 'text-red-300' : 'text-slate-500'}`}>{workspace.status}</div>
                  </div>
                  <div className="line-clamp-2 text-xs text-slate-400">{workspace.description || 'No description saved yet.'}</div>
                  {workspace.lastRunSettings?.model && (
                    <div className="mt-2 text-[11px] text-slate-500">
                      {workspace.lastRunSettings.model} | {workspace.lastRunSettings.timeoutSeconds || 900}s
                    </div>
                  )}
                  {workspace.status === 'error' && workspace.lastErrorSummary && (
                    <div className="mt-2 rounded-xl border border-red-500/20 bg-red-500/10 px-2.5 py-2 text-[11px] text-red-200">
                      {workspace.lastErrorSummary}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        </aside>

        <main className="flex min-h-0 flex-1 flex-col">
          <AgentTeam agents={agents} currentAgent={currentAgent} streamingToken={streamingToken} />
          {job && <WorkspaceStatusBar status={job.status} progress={job.progress} stage={job.stage} />}
          <div className="flex border-b border-[#1a1a2e] px-2">
            {visibleTabs.map((tab) => (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`rounded-t-xl px-4 py-3 text-xs font-medium transition ${activeTab === tab.id ? 'bg-purple-500/10 text-purple-300' : 'text-slate-500 hover:text-slate-200'}`}>
                {tab.label}
              </button>
            ))}
          </div>

          <div className="min-h-0 flex-1 overflow-hidden">
            {activeTab === 'log' && <ProgressLog logs={logs} streamingToken={streamingToken} currentAgent={currentAgent} />}
            {activeTab === 'plan' && (
              <SyntaxHighlighter language="json" style={vscDarkPlus} customStyle={{ margin: 0, minHeight: '100%', background: '#080810', fontSize: '11px' }} showLineNumbers>
                {prettyJson(job?.plan || workspaceDetail?.workspace?.latestPlan || {})}
              </SyntaxHighlighter>
            )}
            {activeTab === 'audit' && <WorkspaceAuditPanel audit={job?.artifactAudit} />}
            {activeTab === 'threads' && <WorkspaceThreadPanel threads={workspaceDetail?.threads || []} selectedThreadId={selectedThreadId} messages={threadMessages} onSelect={setSelectedThreadId} />}
            {activeTab === 'files' && (
              <div className="flex h-full">
                <div className="w-64 shrink-0 border-r border-[#1a1a2e]">
                  <FileExplorer files={generatedFiles} onSelect={fetchFileContent} selectedPath={selectedFile?.path || ''} />
                </div>
                <div className="flex-1 overflow-auto">
                  {selectedFile ? (
                    <>
                      <div className="flex items-center justify-between border-b border-[#1a1a2e] px-4 py-3 text-xs text-slate-400">
                        <span>{selectedFile.path}</span>
                        <span>{selectedFile.service}</span>
                      </div>
                      <SyntaxHighlighter language={selectedFile.path.endsWith('.json') ? 'json' : selectedFile.path.endsWith('.tsx') || selectedFile.path.endsWith('.ts') ? 'typescript' : 'javascript'} style={vscDarkPlus} customStyle={{ margin: 0, minHeight: '100%', background: '#080810', fontSize: '11px' }} showLineNumbers>
                        {selectedFile.content || ''}
                      </SyntaxHighlighter>
                    </>
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-slate-500">Select a file to inspect it.</div>
                  )}
                </div>
              </div>
            )}
            {activeTab === 'links' && (
              <div className="flex h-full flex-col overflow-auto p-4">
                {selectedWorkspace && (
                  <div className="mb-4 rounded-2xl border border-[#1a1a2e] bg-[#0f0f1a] p-4">
                    <div className="mb-2 flex items-center justify-between">
                      <div>
                        <div className="text-sm font-semibold text-white">{selectedWorkspace.name}</div>
                        <div className="text-xs text-slate-500">{selectedWorkspace.description}</div>
                      </div>
                      <div className="inline-flex items-center gap-2 rounded-full bg-white/5 px-3 py-1 text-[11px] text-slate-400">
                        <Clock3 size={11} />
                        {new Date(selectedWorkspace.updatedAt).toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}
                <LiveLinks urls={job?.allUrls || null} services={job?.services || []} />
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

export default WorkspaceDashboard;
