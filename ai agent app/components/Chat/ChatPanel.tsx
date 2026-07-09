'use client';

import { useEffect, useRef, useState } from 'react';
import { useBuilder } from '@/lib/store';
import { MessageBubble } from './MessageBubble';
import { BuildChecklist } from './BuildChecklist';
import { Send, Square, Sparkles } from 'lucide-react';

const EXAMPLES = [
  'A todo app where I can add, complete and delete tasks',
  'A blog with posts stored in MongoDB and a create-post form',
  'A notes app with search and tags',
];

export function ChatPanel() {
  const messages = useBuilder((s) => s.messages);
  const isStreaming = useBuilder((s) => s.isStreaming);
  const isPlanning = useBuilder((s) => s.isPlanning);
  const isBuilding = useBuilder((s) => s.isBuilding);
  const projectName = useBuilder((s) => s.projectName);
  const sendMessage = useBuilder((s) => s.sendMessage);
  const stopGeneration = useBuilder((s) => s.stopGeneration);

  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const busy = isStreaming || isPlanning || isBuilding;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  const submit = () => {
    if (busy) return;
    const text = input;
    setInput('');
    void sendMessage(text);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex h-full flex-col bg-bg">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border px-4 text-xs font-medium text-text-muted">
        <Sparkles size={13} className="text-accent-soft" />
        {projectName ? projectName : 'New app'}
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-5 text-center">
            <div>
              <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent-soft text-white shadow-[0_4px_20px_rgba(124,92,255,0.4)]">
                <Sparkles size={22} />
              </div>
              <h2 className="text-base font-semibold">Build a full Next.js app</h2>
              <p className="mt-1 max-w-xs text-sm text-text-muted">
                Describe an app or paste an SRS. deepseek-r1 detects the app type and
                builds a complete Next.js + MongoDB project locally.
              </p>
            </div>
            <div className="flex w-full max-w-xs flex-col gap-1.5">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => void sendMessage(ex)}
                  disabled={busy}
                  className="rounded-lg border border-border bg-bg-soft px-3 py-2 text-left text-xs text-text-muted transition hover:border-accent/40 hover:text-text disabled:opacity-50"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) => (
            <MessageBubble
              key={m.id}
              message={m}
              streaming={busy && i === messages.length - 1}
            />
          ))
        )}
        <BuildChecklist />
      </div>

      <div className="shrink-0 border-t border-border p-3">
        <div className="flex items-end gap-2 rounded-xl border border-border bg-bg-soft p-2 transition focus-within:border-accent/50">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            disabled={busy}
            placeholder={
              busy ? 'Generating...' : 'Describe an app, paste an SRS, or request a change...'
            }
            className="max-h-40 min-h-0 flex-1 resize-none bg-transparent px-1.5 py-1 text-sm outline-none placeholder:text-text-faint disabled:opacity-60"
          />
          {busy ? (
            <button
              onClick={stopGeneration}
              title="Stop generating"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-rose-500/90 text-white transition hover:bg-rose-500"
            >
              <Square size={13} className="fill-current" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!input.trim()}
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition hover:bg-accent-soft disabled:opacity-40"
            >
              <Send size={15} />
            </button>
          )}
        </div>
        <p className="mt-1.5 px-1 text-[10px] text-text-faint">
          Enter to send | Shift+Enter for newline
        </p>
      </div>
    </div>
  );
}
