'use client'

import { useState } from 'react'
import { ChevronDown, ChevronRight, CircleCheck, CircleX, CircleDashed } from 'lucide-react'
import { Badge, Empty, Panel } from '../ui'
import { cn } from '@/lib/utils'
import { e2eStageSummary, journeyStageSummary } from '@/lib/e2e-rate'

export default function EndToEnd({ qa }) {
  const e2e = qa?.report?.e2e
  if (!e2e || !Object.keys(e2e).length) {
    return <Empty>The end-to-end stage has no record for this project.</Empty>
  }
  const failures = e2e.failures || []
  const failed = e2e.failed ?? failures.length
  const score = e2eStageSummary(e2e)
  const flows = e2e.flows || []

  return (
    <div className="space-y-4">
      <div className="grid gap-3 lg:grid-cols-[220px_1fr]">
        <ScoreCard score={score} />
        <Panel className="p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-muted2">Final browser proof</p>
              <h3 className="mt-1 font-display text-[20px] font-semibold text-ink">
                {score.total ? `${score.passed}/${score.total} stages passed` : 'No stages measured'}
              </h3>
              <p className="mt-1 max-w-[720px] text-[11px] leading-relaxed text-muted">
                Only the latest accepted run of each journey is counted. Repair and re-author retries never inflate the score.
              </p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Badge tone={failed ? 'bad' : 'ok'}>{failed ? `${failed} failure(s)` : 'browser gate green'}</Badge>
              {score.notReached ? <Badge>{score.notReached} not reached</Badge> : null}
              {e2e.fixed ? <Badge>{e2e.fixed} repaired file(s)</Badge> : null}
            </div>
          </div>
        </Panel>
      </div>

      {!e2e.ran && <Panel className="p-4 text-[11.5px] text-muted">The stage did not run.</Panel>}

      {flows.length > 0 && (
        <div className="grid gap-2">
          {flows.map((flow, i) => <Journey key={`${flow.title}-${i}`} flow={flow} />)}
        </div>
      )}

      {e2e.global_integrity?.ran && (
        <Panel className="flex items-center justify-between gap-3 p-3.5">
          <div>
            <p className="text-[11.5px] font-medium text-ink">Global route & role integrity</p>
            <p className="mt-0.5 text-[10.5px] text-muted">One final proof after the user journeys: route health, auth boundaries and role separation.</p>
          </div>
          <Badge tone={e2e.global_integrity.passed ? 'ok' : 'bad'}>
            {e2e.global_integrity.passed ? 'pass' : `${e2e.global_integrity.failures || 1} failure(s)`}
          </Badge>
        </Panel>
      )}

      {failures.length > 0 && (
        <Panel className="p-4">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[.12em] text-muted2">Failure evidence</p>
          <ul className="space-y-1.5">
            {failures.map((f, i) => (
              <li key={i} className="rounded-panel border border-line border-l-2 border-l-bad bg-panel2/40 px-3 py-2 text-[11.5px]">
                <code className="font-mono text-ink">{f.target || f.file || f.case}</code>
                <span className="text-muted"> — {f.case || f.message}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  )
}

function ScoreCard({ score }) {
  const deg = Math.max(0, Math.min(360, score.rate * 3.6))
  return (
    <Panel className="relative overflow-hidden p-4">
      <div className="absolute inset-x-6 bottom-1 h-4 rounded-full bg-black/10 blur-lg" />
      <div className="relative flex items-center gap-4">
        <div className="relative grid size-24 shrink-0 place-items-center rounded-full p-[10px] shadow-[0_10px_24px_rgba(15,23,42,.16)]"
             style={{ background: `conic-gradient(var(--ok) 0deg ${deg}deg, var(--line) ${deg}deg 360deg)` }}>
          <div className="grid size-full place-items-center rounded-full bg-panel shadow-inner">
            <div className="text-center">
              <div className={cn('font-display text-[24px] font-bold leading-none', score.rate === 100 ? 'text-ok' : score.rate >= 80 ? 'text-warn' : 'text-bad')}>{score.rate}%</div>
              <div className="mt-1 text-[8px] uppercase tracking-[.14em] text-muted2">E2E</div>
            </div>
          </div>
        </div>
        <div className="min-w-0">
          <div className="font-display text-[22px] font-bold text-ink">{score.passed}/{score.total}</div>
          <div className="text-[10.5px] text-muted">all final E2E stages</div>
          <div className="mt-2 flex gap-2 text-[9.5px]">
            <span className="text-ok">{score.passed} pass</span>
            <span className="text-bad">{score.failed} fail</span>
          </div>
        </div>
      </div>
    </Panel>
  )
}

function Journey({ flow }) {
  const [open, setOpen] = useState(false)
  const score = journeyStageSummary(flow)
  const stages = flow.stages || []
  return (
    <Panel className="overflow-hidden">
      <button onClick={() => setOpen(v => !v)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-panel2/60">
        {open ? <ChevronDown className="size-3.5 text-muted" /> : <ChevronRight className="size-3.5 text-muted" />}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-[12px] font-semibold text-ink">{flow.title || flow.flow || 'Journey'}</span>
            {flow.role ? <Badge>{flow.role}</Badge> : null}
            {flow.blocked_upstream ? <Badge tone="bad">blocked</Badge> : null}
          </div>
          <div className="mt-1 text-[10.5px] text-muted">
            {score.total ? `${score.passed}/${score.total} stages passed · ${score.rate}%` : 'No measurable browser stages'}
          </div>
        </div>
        <div className="w-28">
          <div className="mb-1 flex justify-between text-[9px] text-muted2"><span>proof</span><span>{score.rate}%</span></div>
          <div className="h-1.5 overflow-hidden rounded-full bg-line"><div className="h-full rounded-full bg-ok transition-all" style={{ width: `${score.rate}%` }} /></div>
        </div>
      </button>
      {open && (
        <div className="border-t border-line bg-panel2/25 px-4 py-3">
          {stages.length ? (
            <ol className="space-y-2">
              {stages.map((stage, i) => <Stage key={`${stage.index}-${i}`} stage={stage} />)}
            </ol>
          ) : <p className="text-[10.5px] text-muted">This older run has no stage ledger.</p>}
        </div>
      )}
    </Panel>
  )
}

function Stage({ stage }) {
  const Icon = stage.status === 'pass' ? CircleCheck : stage.status === 'fail' ? CircleX : CircleDashed
  return (
    <li className="flex items-start gap-2.5 text-[10.5px]">
      <Icon className={cn('mt-px size-3.5 shrink-0', stage.status === 'pass' ? 'text-ok' : stage.status === 'fail' ? 'text-bad' : 'text-muted2')} />
      <span className="w-5 shrink-0 font-mono text-muted2">{String(stage.index || '').padStart(2, '0')}</span>
      <code className={cn('break-all font-mono', stage.status === 'not_reached' ? 'text-muted2' : 'text-ink')}>{stage.label}</code>
      <span className={cn('ml-auto shrink-0 text-[9px] font-semibold uppercase tracking-[.1em]', stage.status === 'pass' ? 'text-ok' : stage.status === 'fail' ? 'text-bad' : 'text-muted2')}>{String(stage.status || '').replace('_', ' ')}</span>
    </li>
  )
}
