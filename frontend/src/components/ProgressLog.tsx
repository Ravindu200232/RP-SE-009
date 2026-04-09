'use client';
import { useEffect, useRef, useState } from 'react';
import { LogEntry } from '@/types';

interface ProgressLogProps {
  logs: LogEntry[];
  streamingToken: string;
  currentAgent: string;
}

// ── Styles per log level ─────────────────────────────────────────────────

const LEVEL_STYLES: Record<string, { text: string; bg: string; prefix: string }> = {
  info:     { text: 'text-slate-300',   bg: '',                          prefix: '  ' },
  success:  { text: 'text-green-400',   bg: '',                          prefix: '✓ ' },
  error:    { text: 'text-red-400',     bg: 'bg-red-500/5',              prefix: '✗ ' },
  warning:  { text: 'text-amber-400',   bg: '',                          prefix: '⚠ ' },
  warn:     { text: 'text-amber-400',   bg: '',                          prefix: '⚠ ' },
  command:  { text: 'text-cyan-300',    bg: 'bg-cyan-500/5 rounded px-1',prefix: '' },
  terminal: { text: 'text-slate-400',   bg: '',                          prefix: '  │ ' },
  prompt:   { text: 'text-purple-300',  bg: 'bg-purple-500/5 rounded',   prefix: '🤖 ' },
  code:     { text: 'text-cyan-400',    bg: '',                          prefix: '  ' },
};

const AGENT_COLORS: Record<string, string> = {
  Planner:     'text-purple-400',
  Developer:   'text-cyan-400',
  Analyzer:    'text-green-400',
  Fixer:       'text-amber-400',
  Runner:      'text-red-400',
  Terminal:    'text-slate-500',
  'AI Prompt': 'text-purple-500',
  Orchestrator:'text-slate-400',
};

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('en-US', {
      hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  } catch { return '--:--:--'; }
}

// ── Single Log Line ───────────────────────────────────────────────────────

function LogLine({ entry, index }: { entry: LogEntry & { level: string }; index: number }) {
  const level = entry.level || entry.type || 'info';
  const style = LEVEL_STYLES[level] || LEVEL_STYLES.info;
  const agentColor = AGENT_COLORS[entry.agent] || 'text-slate-500';
  const isPrompt = level === 'prompt';
  const isCommand = level === 'command';
  const isSection = entry.message.startsWith('\n──') || entry.message.startsWith('──');

  // Section headers get special treatment
  if (isSection) {
    const clean = entry.message.replace(/^\n/, '').trim();
    return (
      <div className="flex items-center gap-2 mt-3 mb-1 opacity-70">
        <div className="flex-1 h-px bg-[#1a1a2e]" />
        <span className="text-[10px] font-medium text-slate-500 uppercase tracking-widest whitespace-nowrap">{clean}</span>
        <div className="flex-1 h-px bg-[#1a1a2e]" />
      </div>
    );
  }

  // Multi-line content (prompts, errors with newlines)
  const lines = entry.message.split('\n').filter((_, i, arr) => i < arr.length - 1 || arr[i].trim());

  return (
    <div className={`animate-[fadeIn_0.15s_ease-in] ${isPrompt ? 'border-l-2 border-purple-500/40 pl-2 my-1' : ''} ${isCommand ? 'mt-1' : ''}`}>
      {lines.map((line, li) => (
        <div
          key={li}
          className={`flex gap-2 leading-relaxed min-h-[1.4rem] ${style.bg} ${isPrompt ? 'py-0.5' : ''}`}
        >
          {/* Timestamp — only on first line */}
          <span className={`text-slate-600 shrink-0 font-mono text-[10px] w-[52px] pt-0.5 ${li > 0 ? 'opacity-0' : ''}`}>
            {li === 0 ? formatTime(entry.timestamp) : ''}
          </span>

          {/* Agent badge — only on first line */}
          <span className={`shrink-0 font-mono text-[10px] w-[72px] truncate pt-0.5 ${li === 0 ? agentColor : 'opacity-0'}`}>
            {li === 0 ? `[${entry.agent || ''}]` : ''}
          </span>

          {/* Message */}
          <span className={`font-mono text-[11px] break-all flex-1 ${style.text}`}>
            {li === 0 && style.prefix}{line || ' '}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Main ProgressLog ──────────────────────────────────────────────────────

export function ProgressLog({ logs, streamingToken, currentAgent }: ProgressLogProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [showPrompts, setShowPrompts] = useState(true);

  // Auto-scroll when new logs arrive
  useEffect(() => {
    if (autoScroll) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs.length, streamingToken, autoScroll]);

  // Detect manual scroll to pause auto-scroll
  const handleScroll = () => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 60;
    setAutoScroll(isAtBottom);
  };

  // Filter logs based on toggle
  const visibleLogs = showPrompts
    ? logs
    : logs.filter(l => (l.level || (l as any).type) !== 'prompt');

  // Split streaming token into lines for display
  const streamLines = streamingToken
    ? streamingToken.split('\n').filter(Boolean).slice(-6) // show last 6 lines of stream
    : [];

  return (
    <div className="flex flex-col h-full">
      {/* ── Toolbar ──────────────────────────────────────── */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-[#1a1a2e] shrink-0">
        <div className={`w-1.5 h-1.5 rounded-full ${streamingToken ? 'bg-purple-400 animate-pulse' : 'bg-green-400'}`} />
        <span className="text-[10px] font-medium text-slate-400">Execution Log</span>
        <span className="text-[10px] text-slate-600">{visibleLogs.length} entries</span>

        <div className="ml-auto flex items-center gap-2">
          {/* Show/hide AI prompts toggle */}
          <button
            onClick={() => setShowPrompts(!showPrompts)}
            className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
              showPrompts
                ? 'border-purple-500/40 text-purple-400 bg-purple-500/10'
                : 'border-[#1a1a2e] text-slate-600 hover:text-slate-400'
            }`}
          >
            🤖 AI Prompts
          </button>

          {/* Auto-scroll indicator */}
          {!autoScroll && (
            <button
              onClick={() => { setAutoScroll(true); bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }}
              className="text-[10px] px-2 py-0.5 rounded border border-cyan-500/40 text-cyan-400 bg-cyan-500/10 hover:bg-cyan-500/20 transition-colors"
            >
              ↓ Resume scroll
            </button>
          )}
        </div>
      </div>

      {/* ── Log Content ──────────────────────────────────── */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-3 space-y-0"
        style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace" }}
      >
        {visibleLogs.length === 0 && !streamingToken && (
          <div className="text-slate-600 text-xs text-center py-12">
            <div className="text-2xl mb-2 opacity-30">⚡</div>
            Paste your SRS JSON and click Generate App
          </div>
        )}

        {visibleLogs.map((log, i) => (
          <LogLine
            key={i}
            index={i}
            entry={log as LogEntry & { level: string }}
          />
        ))}

        {/* ── Live streaming output ──────────────────────── */}
        {streamingToken && (
          <div className="border-l-2 border-purple-500/30 pl-2 mt-1 animate-[fadeIn_0.15s_ease-in]">
            <div className="text-[10px] text-purple-500 mb-0.5">[{currentAgent || 'AI'}] generating...</div>
            {streamLines.map((line, i) => (
              <div key={i} className={`text-[11px] text-purple-300 font-mono leading-relaxed break-all ${i === streamLines.length - 1 ? 'cursor-blink' : 'opacity-70'}`}>
                {line}
              </div>
            ))}
          </div>
        )}

        <div ref={bottomRef} className="h-4" />
      </div>
    </div>
  );
}
