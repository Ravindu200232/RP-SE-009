'use client';

import { useBuilder } from '@/lib/store';
import { Check, Loader2, Circle, FileCode2 } from 'lucide-react';

/**
 * The build checklist. The build engine emits one `step` per unit of work
 * (data layer, app shell, each page, each API batch) with a human label and
 * status start → done; this renders them as a ticking task list so the user
 * can watch the app assemble step by step.
 */
export function BuildChecklist() {
  const steps = useBuilder((s) => s.buildSteps);
  const isBuilding = useBuilder((s) => s.isBuilding);

  if (!isBuilding && steps.length === 0) return null;

  const ordered = [...steps].sort((a, b) => a.n - b.n);
  const doneCount = ordered.filter((s) => s.status === 'done').length;

  return (
    <div className="rounded-xl border border-border bg-bg-soft p-3">
      <div className="mb-2 flex items-center justify-between text-[11px] font-semibold text-text-muted">
        <span className="flex items-center gap-1.5">
          <FileCode2 size={13} className="text-accent-soft" />
          Building files
        </span>
        <span className="tabular-nums">
          {doneCount}/{ordered.length}
        </span>
      </div>
      <ul className="space-y-1">
        {ordered.map((step) => {
          const label = step.label ?? step.files?.[0] ?? `step ${step.n}`;
          const done = step.status === 'done';
          const active = step.status === 'start';
          return (
            <li
              key={step.n}
              className={`flex items-center gap-2 text-[11px] ${
                done ? 'text-text' : active ? 'text-accent-soft' : 'text-text-faint'
              }`}
            >
              {done ? (
                <Check size={12} className="shrink-0 text-emerald-400" />
              ) : active ? (
                <Loader2 size={12} className="shrink-0 animate-spin text-accent-soft" />
              ) : (
                <Circle size={12} className="shrink-0 opacity-40" />
              )}
              <span className="truncate font-mono">{label}</span>
              {done && step.written != null && step.written > 1 && (
                <span className="ml-auto shrink-0 text-text-faint">×{step.written}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
