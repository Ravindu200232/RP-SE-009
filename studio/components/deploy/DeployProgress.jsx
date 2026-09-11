'use client'

import { AlertTriangle, Check, Loader2, Rocket } from 'lucide-react'
import { PIPELINE, STATE_TEXT, progressOf } from '@/lib/deploy-constants'
import { SectionLabel, Tag } from '../ui'
import { cn } from '@/lib/utils'

export default function DeployProgress({ run }) {
  if (!run) return null
  const stages = PIPELINE[run.target] || PIPELINE.vercel
  const { rows, pct } = progressOf(run.events, stages)
  const [label, tone] = STATE_TEXT[run.state] || [run.state || 'Working', 'run']

  return (
    <div className="rounded-2xl border border-white/10 bg-[#121622]/90 p-5 shadow-xl backdrop-blur-xl text-white">
      <SectionLabel className="border-b border-white/10 pb-2"
                    right={<Tag tone={{ pass: 'ok', fail: 'bad',
                                        run: 'accent' }[tone] || 'mute'}>
                      {label}
                    </Tag>}>
        Deploying to {run.target === 'vercel' ? 'Vercel' : 'AWS EC2'}
      </SectionLabel>

      <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-white/10">
        <span className={cn('transition-all duration-500 rounded-full',
                            tone === 'fail' ? 'bg-rose-500' : tone === 'pass' ? 'bg-emerald-400' : 'bg-blue-500')}
              style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 flex items-center gap-2.5 text-[12px] text-white/60">
        <span className="font-mono text-[12px] font-bold text-blue-400">{pct}%</span>
        {run.message}
      </p>

      <ol className="mt-4 overflow-hidden rounded-xl border border-white/10 bg-white/[.02]">
        {rows.map(r => (
          <li key={r.id}
              className={cn('flex items-start gap-3 border-b border-white/5 last:border-0',
                'border-l-[3px] py-2.5 px-3.5',
                r.status === 'active' ? 'border-l-blue-500 bg-blue-500/[.06]'
                  : r.status === 'error' ? 'border-l-rose-500 bg-rose-500/[.06]'
                  : r.status === 'done' ? 'border-l-emerald-400'
                  : 'border-l-transparent')}>
            <span className="mt-[2px] grid size-3.5 shrink-0 place-items-center">
              {r.status === 'done'
                ? <Check className="size-3.5 text-emerald-400" />
                : r.status === 'error'
                ? <AlertTriangle className="size-3.5 text-rose-400" />
                : r.status === 'active'
                ? <Loader2 className="size-3 animate-spin text-blue-400" />
                : <span className="size-1.5 rounded-full bg-white/20" />}
            </span>
            <span className="min-w-0 flex-1">
              <span className={cn('block text-[12.5px]',
                r.status === 'pending' ? 'text-white/40'
                  : r.status === 'error' ? 'font-semibold text-rose-300'
                  : r.status === 'active' ? 'font-bold text-white' : 'text-white/90')}>
                {r.title}
              </span>
              <span className="block font-mono text-[10.5px] leading-snug text-white/50 mt-0.5">
                {r.message || r.detail}
              </span>
            </span>
          </li>
        ))}
      </ol>

      {run.error && (
        <p className="mt-3.5 flex items-start gap-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 px-3.5 py-3 text-[12px] text-rose-300">
          <AlertTriangle className="mt-px size-4 shrink-0 text-rose-400" />
          <span className="min-w-0">{run.error}</span>
        </p>
      )}

      {run.url && (
        <a href={run.url} target="_blank" rel="noreferrer"
           className="mt-3.5 flex items-center gap-2.5 rounded-xl bg-blue-600 px-4 py-3 font-mono text-[12px] font-semibold text-white shadow-lg shadow-blue-500/25 transition-all hover:bg-blue-500">
          <Rocket className="size-4 shrink-0" />
          <span className="min-w-0 truncate">{run.url}</span>
        </a>
      )}
    </div>
  )
}
