'use client'

import { AlertTriangle, Check, Loader2, Rocket } from 'lucide-react'
import { PIPELINE, STATE_TEXT, TARGETS, progressOf } from '@/lib/deploy-constants'
import { SectionLabel, Tag } from '../ui'
import { cn } from '@/lib/utils'

export default function DeployProgress({ run }) {
  if (!run) return null
  const stages = PIPELINE[run.target] || PIPELINE.vercel
  const { rows, pct } = progressOf(run.events, stages)
  const [label, tone] = STATE_TEXT[run.state] || [run.state || 'Working', 'run']

  return (
    <div className="rounded-2xl border border-[rgba(145,158,171,0.16)] bg-[#1C252E] p-5 shadow-[0_0_2px_0_rgba(145,158,171,0.2),0_12px_24px_-4px_rgba(0,0,0,0.16)] backdrop-blur-xl text-white">
      <SectionLabel className="border-b border-[rgba(145,158,171,0.16)] pb-2"
                    right={<Tag tone={{ pass: 'ok', fail: 'bad',
                                        run: 'accent' }[tone] || 'mute'}>
                      {label}
                    </Tag>}>
        Deploying to {TARGETS.find(target => target.id === run.target)?.label || run.target}
      </SectionLabel>

      <div className="mt-4 flex h-2 overflow-hidden rounded-full bg-[#28323D]">
        <span className={cn('transition-all duration-500 rounded-full',
                            tone === 'fail' ? 'bg-[#FF5630]' : tone === 'pass' ? 'bg-[#22C55E]' : 'bg-[#1877F2]')}
              style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 flex items-center gap-2.5 text-[12px] text-[#919EAB]">
        <span className="font-mono text-[12px] font-bold text-[#1877F2]">{pct}%</span>
        {run.message}
      </p>

      <ol className="mt-4 overflow-hidden rounded-xl border border-[rgba(145,158,171,0.16)] bg-[#141A21]/40">
        {rows.map(r => (
          <li key={r.id}
              className={cn('flex items-start gap-3 border-b border-[rgba(145,158,171,0.08)] last:border-0',
                'border-l-[3px] py-2.5 px-3.5',
                r.status === 'active' ? 'border-l-[#1877F2] bg-[#1877F2]/10'
                  : r.status === 'error' ? 'border-l-[#FF5630] bg-[#FF5630]/10'
                  : r.status === 'done' ? 'border-l-[#22C55E]'
                  : 'border-l-transparent')}>
            <span className="mt-[2px] grid size-3.5 shrink-0 place-items-center">
              {r.status === 'done'
                ? <Check className="size-3.5 text-[#22C55E]" />
                : r.status === 'error'
                ? <AlertTriangle className="size-3.5 text-[#FF5630]" />
                : r.status === 'active'
                ? <Loader2 className="size-3 animate-spin text-[#1877F2]" />
                : <span className="size-1.5 rounded-full bg-white/20" />}
            </span>
            <span className="min-w-0 flex-1">
              <span className={cn('block text-[12.5px]',
                r.status === 'pending' ? 'text-[#919EAB]/60'
                  : r.status === 'error' ? 'font-semibold text-[#FF5630]'
                  : r.status === 'active' ? 'font-bold text-white' : 'text-white/90')}>
                {r.title}
              </span>
              <span className="block font-mono text-[10.5px] leading-snug text-[#919EAB] mt-0.5">
                {r.message || r.detail}
              </span>
            </span>
          </li>
        ))}
      </ol>

      {run.error && (
        <p className="mt-3.5 flex items-start gap-2.5 rounded-xl border border-[#FF5630]/30 bg-[#FF5630]/10 px-3.5 py-3 text-[12px] text-[#FF5630]">
          <AlertTriangle className="mt-px size-4 shrink-0 text-[#FF5630]" />
          <span className="min-w-0">{run.error}</span>
        </p>
      )}

      {run.url && (
        <a href={run.url} target="_blank" rel="noreferrer"
           className="mt-3.5 flex items-center gap-2.5 rounded-xl bg-[#1877F2] px-4 py-3 font-mono text-[12px] font-semibold text-white shadow-[0_8px_16px_0_rgba(24,119,242,0.24)] transition-all hover:bg-[#0C44AE]">
          <Rocket className="size-4 shrink-0" />
          <span className="min-w-0 truncate">{run.url}</span>
        </a>
      )}
    </div>
  )
}
