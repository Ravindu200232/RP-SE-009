'use client';

import { Sparkles } from 'lucide-react';
import { StatusPill } from './StatusPill';

export function Header() {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-bg-soft/80 px-4 backdrop-blur">
      <div className="flex items-center gap-2.5">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-soft text-white shadow-[0_2px_10px_rgba(124,92,255,0.4)]">
          <Sparkles size={16} />
        </div>
        <div className="flex flex-col leading-none">
          <span className="text-sm font-semibold tracking-tight">AI Web Builder</span>
          <span className="mt-0.5 text-[10px] text-text-faint">Next.js + MongoDB · local deepseek-r1</span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <StatusPill />
      </div>
    </header>
  );
}
