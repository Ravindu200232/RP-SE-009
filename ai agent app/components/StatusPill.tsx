'use client';

import { useBuilder } from '@/lib/store';
import { cn } from '@/lib/utils';

function Dot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className={cn(
          'h-2 w-2 rounded-full',
          ok ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]' : 'bg-rose-500',
        )}
      />
      <span className="text-text-muted">{label}</span>
    </span>
  );
}

export function StatusPill() {
  const status = useBuilder((s) => s.status);

  const llm = status?.ollama;
  const codeModel = llm?.codeModel || llm?.model;
  const codeModelInstalled = llm?.codeModelInstalled ?? llm?.modelInstalled;
  const llmOk = !!llm?.reachable && !!llm?.modelInstalled && !!codeModelInstalled;
  const providerLabel = 'Ollama';
  const llmLabel = !status
    ? 'checking...'
    : !llm?.reachable
      ? `${providerLabel} offline`
      : !llm?.modelInstalled
        ? `${llm.model} not available`
        : !codeModelInstalled
          ? `${codeModel} not available`
          : llm.model === codeModel
            ? `${providerLabel}: ${llm.model}`
            : `${llm.model} + ${codeModel}`;

  const dbOk = !!status?.db.connected;

  return (
    <div className="flex items-center gap-4 text-xs">
      <Dot ok={llmOk} label={llmLabel} />
      <Dot ok={dbOk} label={dbOk ? 'MongoDB' : 'MongoDB offline'} />
    </div>
  );
}
