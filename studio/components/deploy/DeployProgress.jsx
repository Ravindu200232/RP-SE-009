'use client'

import { AlertTriangle, Check, Loader2, Rocket } from 'lucide-react'
import { PIPELINE, STATE_TEXT, progressOf } from '@/lib/deploy-constants'
import { Badge, Panel, SectionLabel } from '../ui'
import { cn } from '@/lib/utils'

export default function DeployProgress({ run }) {
  if (!run) return null
  const stages = PIPELINE[run.target] || PIPELINE.vercel
  const { rows, pct } = progressOf(run.events, stages)
  const [label, tone] = STATE_TEXT[run.state] || [run.state || 'Working', 'run']

  return (
    <Panel className="p-4">
      <SectionLabel right={<Badge tone={{ pass: 'ok', fail: 'bad', run: 'accent' }[tone] || 'mute'}>
                             {label}
                           </Badge>}>
        Deploying to {run.target === 'vercel' ? 'Vercel' : 'AWS EC2'}
      </SectionLabel>

      <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-line">
        <div className={cn('h-full transition-all duration-500',
                           tone === 'fail' ? 'bg-bad' : 'bg-accent')}
             style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-muted">
        <span className="font-mono text-[10px] text-muted2">{pct}%</span>
        {run.message}
      </p>

      <ol className="mt-4 space-y-1">
        {rows.map(r => (
          <li key={r.id} className="flex items-start gap-2.5 py-[3px]">
            <span className="mt-[3px] grid size-3.5 shrink-0 place-items-center">
              {r.status === 'done'
                ? <Check className="size-3.5 text-ok" />
                : r.status === 'error'
                ? <AlertTriangle className="size-3.5 text-bad" />
                : r.status === 'active'
                ? <Loader2 className="size-3 animate-spin text-accent" />
                : <span className="size-1.5 rounded-full bg-line2" />}
            </span>
            <span className="min-w-0 flex-1">
              <span className={cn('block text-[12px]',
                r.status === 'pending' ? 'text-muted2'
                  : r.status === 'error' ? 'text-bad' : 'text-ink')}>
                {r.title}
              </span>
              <span className="block text-[10.5px] leading-snug text-muted2">
                {r.message || r.detail}
              </span>
            </span>
          </li>
        ))}
      </ol>

      {run.error && (
        <p className="mt-3 flex items-start gap-2 rounded-ctl border border-bad/40
                      bg-bad/10 px-2.5 py-2 text-[11.5px] text-bad">
          <AlertTriangle className="mt-px size-3.5 shrink-0" />
          <span className="min-w-0">{run.error}</span>
        </p>
      )}

      {run.url && (
        <a href={run.url} target="_blank" rel="noreferrer"
           className="mt-3 flex items-center gap-2 rounded-ctl border border-ok/40
                      bg-ok/10 px-2.5 py-2 text-[12px] text-ok hover:brightness-125">
          <Rocket className="size-3.5 shrink-0" />
          <span className="min-w-0 truncate">{run.url}</span>
        </a>
      )}
    </Panel>
  )
}
