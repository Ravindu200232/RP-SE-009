'use client'

/**
 * The journeys running in parallel, and how far each one has got.
 *
 * Each lane used to reserve most of its card for a screenshot of its own
 * browser. There is one browser now and it streams into the preview, so that
 * space was a black rectangle that never filled in — and it pushed the step
 * the lane is actually on down to a line of small print.
 *
 * The step is the card now.
 */

import { useStore } from '@/lib/store'

function tone(state, ok) {
  if (state === 'step_failed' || ok === false) return 'border-bad/45 bg-bad/5'
  if (state === 'journey_done') return 'border-ok/35 bg-ok/5'
  if (state === 'step' || state === 'step_done' || state === 'journey_start') {
    return 'border-accent/35 bg-accent/5'
  }
  return 'border-line bg-panel'
}

function label(state) {
  if (state === 'journey_start') return 'starting'
  if (state === 'journey_done') return 'done'
  if (state === 'step_failed') return 'failed'
  if (state === 'step_done') return 'running'
  if (state === 'step') return 'running'
  return 'idle'
}

export default function E2ELiveLanes() {
  const e2e = useStore(s => s.e2eParallel)
  const workers = Math.max(1, Math.min(4, e2e?.workers || 4))
  const lanes = (e2e?.lanes || []).slice(0, workers)
  const active = lanes.some(x => x.title || x.state !== 'idle')

  if (!active && !e2e?.active) return null

  return (
    <div className="flex h-full min-h-0 flex-col p-4">
      <div className="mb-3 flex shrink-0 items-center gap-2">
        <span className="size-2 animate-pulse rounded-full bg-accent" />
        <span className="text-[12px] font-semibold text-ink">Parallel E2E</span>
        <span className="font-mono text-[10px] text-muted">
          {workers} lanes{e2e?.waves ? ` · wave ${e2e.wave || 1}/${e2e.waves}` : ''}
        </span>
      </div>

      <div className="grid min-h-0 flex-1 auto-rows-min grid-cols-1 gap-3 overflow-y-auto sm:grid-cols-2">
        {lanes.map((lane, i) => {
          const pct = lane.total ? Math.min(100, Math.round((lane.index / lane.total) * 100)) : 0
          return (
            <section key={lane.lane || i + 1}
                     className={`flex min-h-0 flex-col overflow-hidden rounded-panel border ${tone(lane.state, lane.ok)}`}>
              <div className="flex shrink-0 items-center gap-2 border-b border-line/70 px-3 py-2">
                <b className="font-mono text-[10px] text-accent">LANE {lane.lane || i + 1}</b>
                <span className="min-w-0 flex-1 truncate text-[11px] font-medium text-ink">
                  {lane.title || 'Waiting for a journey'}
                </span>
                <span className="text-[9px] uppercase tracking-wide text-muted">{label(lane.state)}</span>
              </div>

              <div className="space-y-2 px-3 py-2.5">
                <p className={`text-[11px] leading-relaxed ${lane.message ? 'text-bad' : 'text-ink'}`}>
                  {lane.message || lane.label || 'Waiting for a browser lane'}
                </p>
                <div className="flex items-center gap-2 text-[9.5px] text-muted">
                  <span className="truncate">{lane.role || 'browser'}</span>
                  <span>·</span>
                  <code className="min-w-0 flex-1 truncate">{lane.route || '/'}</code>
                  <span className="tabular-nums">{lane.total ? `${lane.index}/${lane.total}` : ''}</span>
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-panel2">
                  <div className={`h-full transition-[width] duration-200 ${
                    lane.ok === false ? 'bg-bad' : 'bg-accent'}`}
                       style={{ width: `${pct}%` }} />
                </div>
              </div>
            </section>
          )
        })}
      </div>
    </div>
  )
}
