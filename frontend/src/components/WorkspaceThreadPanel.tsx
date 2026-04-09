'use client';

import type { ThreadMessage, ThreadSummary } from '@/types';

export function WorkspaceThreadPanel({
  threads,
  selectedThreadId,
  messages,
  onSelect
}: {
  threads: ThreadSummary[];
  selectedThreadId: string;
  messages: ThreadMessage[];
  onSelect: (threadId: string) => void;
}) {
  return (
    <div className="flex h-full">
      <div className="w-72 shrink-0 border-r border-[#1a1a2e] p-3">
        {threads.length === 0 && <div className="text-sm text-slate-500">No threads yet.</div>}
        {threads.map((thread) => (
          <button
            key={thread.threadId}
            onClick={() => onSelect(thread.threadId)}
            className={`mb-2 w-full rounded-xl border px-3 py-3 text-left transition ${
              selectedThreadId === thread.threadId
                ? 'border-purple-500/30 bg-purple-500/10'
                : 'border-[#1a1a2e] bg-[#0f0f1a] hover:border-[#2c2c44]'
            }`}
          >
            <div className="mb-1 flex items-center justify-between">
              <div className="text-sm font-medium text-white">{thread.title}</div>
              <div className="text-[11px] uppercase tracking-[0.2em] text-slate-500">{thread.mode}</div>
            </div>
            <div className="text-xs text-slate-400">{thread.latestTask || 'No task summary'}</div>
            <div className="mt-2 text-[11px] text-slate-500">{thread.messageCount} messages</div>
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-auto p-4">
        {messages.length === 0 ? (
          <div className="text-sm text-slate-500">Select a thread to inspect its message history.</div>
        ) : (
          <div className="space-y-3">
            {messages.map((message, index) => (
              <div key={`${message.createdAt}-${index}`} className="rounded-xl border border-[#1a1a2e] bg-[#0f0f1a] p-3">
                <div className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-[0.2em] text-slate-500">
                  <span>{message.role}</span>
                  <span>{message.agent || message.phase || 'message'}</span>
                </div>
                <pre className="whitespace-pre-wrap text-xs text-slate-300">{message.content}</pre>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default WorkspaceThreadPanel;
