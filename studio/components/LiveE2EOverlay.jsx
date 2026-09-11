'use client'

import { CheckCircle2, Loader2, MousePointer2, Play, UserRound } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function LiveE2EOverlay({ event }) {
  if (!event) return null
  const done = event.state === 'journey_done'
  const failed = event.state === 'step_failed'
  const total = Number(event.total || 0)
  const index = Number(event.index || 0)
  const pct = total ? Math.max(4, Math.min(100, Math.round(index / total * 100))) : 8

  return (
    <div className="pointer-events-none absolute inset-x-5 top-5 z-[12] flex justify-center">
      <div className="w-full max-w-[620px] rounded-2xl border border-white/15 bg-[#121622]/95 p-4 shadow-[0_20px_60px_rgba(0,0,0,0.6)] backdrop-blur-2xl">
        <div className="flex items-center gap-3.5">
          <div className={cn('grid size-10 place-items-center rounded-xl',
            failed ? 'border border-rose-500/30 bg-rose-500/20 text-rose-400' 
              : done ? 'border border-emerald-500/30 bg-emerald-500/20 text-emerald-400' 
              : 'border border-blue-500/30 bg-blue-500/20 text-blue-400')}>
            {failed ? <MousePointer2 className="size-4" />
              : done ? <CheckCircle2 className="size-4" />
              : <Loader2 className="size-4 animate-spin" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-[10.5px] font-semibold uppercase tracking-[.18em] text-blue-400">
              <Play className="size-3" /> Live browser test
              {event.role && <><span>·</span><UserRound className="size-3" /><span className="text-slate-400">{event.role}</span></>}
            </div>
            <p className="mt-0.5 truncate text-[13.5px] font-bold text-white">
              {event.title || 'End-to-end journey'}
            </p>
            <p className={cn('mt-0.5 truncate text-[12px]', failed ? 'text-rose-400 font-medium' : done ? 'text-emerald-400 font-medium' : 'text-slate-400')}>
              {done ? 'Journey passed in the real browser'
                : failed ? (event.message || event.label || 'The browser found a problem')
                : friendlyStep(event)}
            </p>
          </div>
          {total > 0 && (
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 font-mono text-[11px] font-semibold text-slate-300 shadow-sm">
              {Math.min(index, total)}/{total}
            </span>
          )}
        </div>
        {!done && total > 0 && (
          <div className="mt-3.5 h-1.5 overflow-hidden rounded-full bg-white/10">
            <div className={cn('h-full rounded-full transition-all duration-500', failed ? 'bg-rose-500' : 'bg-blue-500 shadow-[0_0_12px_rgba(59,130,246,0.6)]')}
                 style={{ width: `${pct}%` }} />
          </div>
        )}
      </div>
    </div>
  )
}

function friendlyStep(event) {
  const verb = String(event.verb || '').toUpperCase()
  const value = String(event.value || '')
  if (verb === 'GOTO') return `Opening ${friendlyRoute(value || event.route)}`
  if (verb === 'CLICK') return `Clicking ${clean(event.label)}`
  if (verb === 'FILL') return `Entering ${clean(event.label)}`
  if (verb === 'SELECT') return `Choosing ${clean(event.label)}`
  if (verb.startsWith('EXPECT')) return `Checking ${clean(event.label)}`
  return clean(event.label) || 'Using the app like a real user'
}

function clean(s) {
  return String(s || '').replace(/\s+/g, ' ').replace(/^(CLICK|FILL|SELECT|EXPECT_[A-Z_]+|GOTO)\s*::?\s*/i, '').slice(0, 100)
}

function friendlyRoute(route) {
  const cleanRoute = String(route || '').split('?')[0].replace(/^\/+|\/+$/g, '')
  if (!cleanRoute) return 'the home page'
  const parts = cleanRoute.split('/').filter(x => x && !/^[0-9a-f]{8,}$/i.test(x))
  const words = parts.map(x => x.replace(/[-_]+/g, ' ')).filter(Boolean)
  if (!words.length) return 'the next page'
  const last = words.at(-1)
  if (words[0] === 'admin') return `${last.replace(/\b\w/g, c => c.toUpperCase())} management`
  return `${last.replace(/\b\w/g, c => c.toUpperCase())} page`
}
