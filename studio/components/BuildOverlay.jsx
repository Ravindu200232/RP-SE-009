'use client'

import { useEffect, useRef, useState } from 'react'
import { useStore } from '@/lib/store'
import { cn } from '@/lib/utils'


const NOISE = [
  /^\[next\]\s+(GET|POST|PUT|PATCH|DELETE|HEAD)\s/i,
  /^\[next\]\s+[-✓○▲]/,
  /^\[next\]\s+(Local|Network|Environments):/i,
  /^\[browser\]/i,
  /^\$\s/,
  /^\s*$/,
  /Fast Refresh/i,
  /^exit \d+/i,
  /Download the React DevTools/i,
]


const KINDS = [
  { re: /^[✅🎉]/u, tone: 'ok' },
  { re: /^[❌⛔]/u, tone: 'bad' },
  { re: /^[⚠❗↩]/u, tone: 'warn' },
  { re: /^[🔧🩹➕🗑]/u, tone: 'fix' },
  { re: /^[📝🧪]/u, tone: 'write' },
  { re: /^[🔍🎯📍🔒🔐]/u, tone: 'look' },
  { re: /^[⏱📊⚡]/u, tone: 'muted' },
]

const TONE = {
  ok: 'text-ok',
  bad: 'text-bad',
  warn: 'text-warn',
  fix: 'text-accent',
  write: 'text-ink',
  look: 'text-muted',
  muted: 'text-muted2',
  plain: 'text-muted',
}

function toneOf(text) {
  for (const { re, tone } of KINDS) if (re.test(text)) return tone
  return 'plain'
}

function keep(text) {
  const t = (text || '').trim()
  if (!t) return false
  return !NOISE.some(re => re.test(t))
}


const ROWS = 7

export default function BuildOverlay() {
  const busy = useStore(s => s.busy)
  const logs = useStore(s => s.logs)
  const progress = useStore(s => s.progress)
  const liveFile = useStore(s => s.liveFile)
  const phases = useStore(s => s.phases)

  const mark = useRef(0)
  const [, tick] = useState(0)
  useEffect(() => {
    if (busy) {
      mark.current = Date.now()
      tick(n => n + 1)
    }
  }, [busy])

  if (!busy) return null

  const feed = logs
    .filter(l => l.at >= mark.current - 1500 && keep(l.text))
    .slice(-ROWS)

  const active = phases.filter(p => p.status === 'active').slice(-1)[0]
  const headline = active?.title || progress.step || 'Working…'
  const pct = Math.max(0, Math.min(100, progress.pct || 0))

  return (
    <div className="absolute inset-0 z-[20] flex flex-col items-center
                    justify-center gap-5 bg-bg/70 px-8 backdrop-blur-[20px]">
      <div className="flex w-full max-w-[520px] flex-col items-center gap-2">
        <div className="flex items-center gap-2">
          <Spinner />
          <span className="font-display text-[15px] font-bold text-ink">
            {headline}
          </span>
        </div>
        <div className="h-[3px] w-[240px] overflow-hidden rounded-full bg-line">
          {pct > 0 ? (
            <div className="h-full rounded-full bg-accent
                            transition-[width] duration-700 ease-out"
                 style={{ width: `${Math.max(3, pct)}%` }} />
          ) : (
            <div className="h-full w-1/3 rounded-full bg-accent/70 lc-sweep" />
          )}
        </div>
      </div>

      <div className="flex w-full max-w-[520px] flex-col justify-end gap-[3px]"
           style={{ minHeight: ROWS * 22 }}>
        {feed.map((l, i) => {
          const depth = feed.length - 1 - i
          return (
            <div key={`${l.at}-${i}`}
                 className={cn(
                   'lc-rise flex items-baseline gap-2 truncate text-[11.5px]',
                   'leading-[18px]', TONE[toneOf(l.text)])}
                 style={{
                   opacity: Math.max(0.18, 1 - depth * 0.16),
                   transform: `scale(${1 - depth * 0.012})`,
                 }}>
              <span className="truncate">{l.text.trim()}</span>
            </div>
          )
        })}
      </div>

      {liveFile && (
        <div className="max-w-[520px] truncate font-mono text-[10px] text-accent">
          {liveFile}
        </div>
      )}

    </div>
  )
}

function Spinner() {
  return (
    <span className="relative inline-flex size-[13px] shrink-0">
      <span className="absolute inset-0 rounded-full border-[1.5px]
                       border-line" />
      <span className="absolute inset-0 animate-spin rounded-full
                       border-[1.5px] border-transparent border-t-accent" />
    </span>
  )
}
