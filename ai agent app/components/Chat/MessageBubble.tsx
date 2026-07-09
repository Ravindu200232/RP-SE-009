'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  FileCode2,
  Loader2,
  CheckCircle2,
  Sparkles,
  Brain,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { parseArtifact, stripArtifactTags } from '@/lib/artifact/parser';
import { useBuilder, type UiMessage } from '@/lib/store';

function BuildCard({
  files,
  streaming,
}: {
  files: { path: string }[];
  streaming?: boolean;
}) {
  const selectFile = useBuilder((s) => s.selectFile);
  const selectedPath = useBuilder((s) => s.selectedPath);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-bg-soft">
      <div className="flex items-center gap-2 border-b border-border-soft bg-bg-panel px-3 py-2 text-xs font-medium">
        {streaming ? (
          <Loader2 size={13} className="animate-spin text-accent-soft" />
        ) : (
          <CheckCircle2 size={13} className="text-emerald-400" />
        )}
        {streaming ? 'Building project…' : `Generated ${files.length} files`}
      </div>
      <div className="max-h-56 overflow-y-auto py-1">
        {files.map((f) => (
          <button
            key={f.path}
            onClick={() => selectFile(f.path)}
            className={
              'flex w-full items-center gap-2 px-3 py-1 text-left text-xs transition hover:bg-bg-panel ' +
              (selectedPath === f.path ? 'text-accent-soft' : 'text-text-muted')
            }
          >
            <FileCode2 size={12} className="shrink-0 text-text-faint" />
            <span className="truncate font-mono">{f.path}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** Collapsible live "thinking" panel — auto-open while reasoning, collapses once the answer starts. */
function ThinkingBlock({ text, active }: { text: string; active: boolean }) {
  const [override, setOverride] = useState<boolean | null>(null);
  const open = override ?? active;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-bg-soft">
      <button
        onClick={() => setOverride(!open)}
        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-text-muted"
      >
        {active ? (
          <Loader2 size={12} className="animate-spin text-accent-soft" />
        ) : (
          <Brain size={12} className="text-text-faint" />
        )}
        <span className="font-medium">{active ? 'Thinking…' : 'Thought process'}</span>
        {open ? (
          <ChevronDown size={12} className="ml-auto text-text-faint" />
        ) : (
          <ChevronRight size={12} className="ml-auto text-text-faint" />
        )}
      </button>
      {open && (
        <div className="max-h-52 overflow-y-auto whitespace-pre-wrap border-t border-border-soft px-3 py-2 font-mono text-[11px] leading-relaxed text-text-muted">
          {text}
        </div>
      )}
    </div>
  );
}

export function MessageBubble({
  message,
  streaming,
}: {
  message: UiMessage;
  streaming?: boolean;
}) {
  if (message.role === 'user') {
    return (
      <div className="flex animate-fade-in justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm border border-accent/20 bg-accent/15 px-3.5 py-2 text-sm">
          {message.content}
        </div>
      </div>
    );
  }

  const prose = stripArtifactTags(message.content);
  const { files } = parseArtifact(message.content);
  const hasOpenFileTag = /<file\b/i.test(message.content);
  const building = !!streaming && hasOpenFileTag && files.length === 0;
  const waitingForAnswer =
    !!streaming && !prose && files.length === 0 && !hasOpenFileTag;
  const thinkingActive =
    !!streaming && !!message.thinking && files.length === 0 && !hasOpenFileTag;
  const showThinkingDots = waitingForAnswer && !message.thinking;

  return (
    <div className="flex animate-fade-in gap-2.5">
      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-accent to-accent-soft text-white shadow-sm">
        <Sparkles size={13} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        {message.thinking && (
          <ThinkingBlock text={message.thinking} active={thinkingActive} />
        )}

        {prose && (
          <div className="markdown max-w-full text-text">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{prose}</ReactMarkdown>
          </div>
        )}

        {(files.length > 0 || building) && (
          <BuildCard files={files} streaming={streaming} />
        )}

        {showThinkingDots && (
          <div className="flex items-center gap-2 text-sm text-text-muted">
            <Loader2 size={14} className="animate-spin" /> Thinking…
          </div>
        )}
      </div>
    </div>
  );
}
