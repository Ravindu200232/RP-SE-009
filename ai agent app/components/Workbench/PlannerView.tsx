'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Brain, CheckCircle2, FileText, Loader2 } from 'lucide-react';
import { useBuilder } from '@/lib/store';
import { cn } from '@/lib/utils';

type StageKey = 'implementation';

const STAGES: Array<{
  key: StageKey;
  title: string;
  short: string;
}> = [
  { key: 'implementation', title: 'Implementation Plan', short: 'Complete build blueprint' },
];

export function PlannerView() {
  const plans = useBuilder((s) => s.plans);
  const isPlanning = useBuilder((s) => s.isPlanning);
  const planningStage = useBuilder((s) => s.planningStage);
  const planningThinking = useBuilder((s) => s.planningThinking);
  const planningThinkingText = useBuilder((s) => s.planningThinkingText);
  const projectName = useBuilder((s) => s.projectName);
  const stages = useMemo(() => STAGES, []);
  const [selected, setSelected] = useState<StageKey>('implementation');
  const contentScrollRef = useRef<HTMLDivElement>(null);
  const thinkingScrollRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    if (planningStage) setSelected(planningStage);
  }, [planningStage]);

  useEffect(() => {
    if (plans[selected]) return;
    const firstReady = stages.find((stage) => plans[stage.key]?.trim());
    if (firstReady) setSelected(firstReady.key);
  }, [plans, selected, stages]);

  const selectedStage = stages.find((stage) => stage.key === selected) ?? stages[0];
  const content = selectedStage ? plans[selectedStage.key] ?? '' : '';
  const thinkingPreview =
    planningThinkingText.length > 6000
      ? planningThinkingText.slice(-6000)
      : planningThinkingText;

  useEffect(() => {
    if (!isPlanning && !planningThinking) return;
    const frame = requestAnimationFrame(() => {
      const contentEl = contentScrollRef.current;
      const thinkingEl = thinkingScrollRef.current;
      contentEl?.scrollTo({ top: contentEl.scrollHeight });
      thinkingEl?.scrollTo({ top: thinkingEl.scrollHeight });
    });
    return () => cancelAnimationFrame(frame);
  }, [content, thinkingPreview, isPlanning, planningThinking, selectedStage?.key]);

  return (
    <div className="flex min-h-0 flex-1 bg-bg">
      <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-bg-soft">
        <div className="border-b border-border px-3 py-2">
          <div className="truncate text-xs font-semibold text-text">
            {projectName || 'Planner'}
          </div>
          <div className="text-[11px] text-text-faint">
            {isPlanning ? 'Streaming implementation plan live' : 'Implementation plan'}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {stages.map((stage) => {
            const active = planningStage === stage.key;
            const done = Boolean(plans[stage.key]?.trim());
            return (
              <button
                key={stage.key}
                onClick={() => setSelected(stage.key)}
                className={cn(
                  'mb-1 flex w-full items-start gap-2 rounded-md px-2.5 py-2 text-left transition',
                  selected === stage.key
                    ? 'bg-bg-elevated text-text'
                    : 'text-text-muted hover:bg-bg-panel hover:text-text',
                )}
              >
                <span className="mt-0.5 shrink-0">
                  {active ? (
                    <Loader2 size={13} className="animate-spin text-accent-soft" />
                  ) : done ? (
                    <CheckCircle2 size={13} className="text-emerald-400" />
                  ) : (
                    <FileText size={13} className="text-text-faint" />
                  )}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-xs font-medium">{stage.title}</span>
                  <span className="block truncate text-[11px] text-text-faint">
                    {stage.short}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      <main className="flex min-h-0 flex-1 flex-col">
        <div className="flex h-9 shrink-0 items-center justify-between border-b border-border bg-bg-soft px-3">
          <div className="flex min-w-0 items-center gap-2">
            <FileText size={13} className="text-text-faint" />
            <span className="truncate text-xs font-medium text-text">
              {selectedStage?.title ?? 'Planner'}
            </span>
            {planningStage === selectedStage?.key && (
              <span className="rounded bg-accent/10 px-1.5 py-0.5 text-[10px] uppercase text-accent-soft">
                live
              </span>
            )}
          </div>
          <span className="text-[11px] text-text-faint">
            {content.length ? `${content.length.toLocaleString()} chars` : 'waiting'}
          </span>
        </div>

        {thinkingPreview && (planningThinking || !content) && (
          <div className="shrink-0 border-b border-border bg-bg-panel px-3 py-2">
            <div className="mb-1 flex items-center gap-2 text-[11px] font-medium text-text-muted">
              {planningThinking ? (
                <Loader2 size={12} className="animate-spin text-accent-soft" />
              ) : (
                <Brain size={12} className="text-text-faint" />
              )}
              deepseek-r1 thinking
            </div>
            <pre
              ref={thinkingScrollRef}
              className="max-h-24 overflow-y-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-text-faint"
            >
              {thinkingPreview}
            </pre>
          </div>
        )}

        <div ref={contentScrollRef} className="min-h-0 flex-1 overflow-auto px-5 py-4">
          {content ? (
            <div className="markdown max-w-none text-sm text-text">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center">
              <FileText size={28} className="text-text-faint/50" />
              <p className="text-sm text-text-muted">
                {isPlanning ? 'Planning is starting...' : 'No plan file selected yet'}
              </p>
              <p className="max-w-sm text-xs text-text-faint">
                Paste an app request or SRS in chat. The planner will stream the
                implementation plan here as deepseek-r1 writes it.
              </p>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
