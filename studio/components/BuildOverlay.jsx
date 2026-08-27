'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Check, FileCode2, Loader2, MousePointerSquareDashed,
  Pencil, Puzzle, Square, Wrench, ImageIcon,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { activityEvent, liveFileActivity } from '@/lib/activity'
import { cn } from '@/lib/utils'

const WORK = {
  build:   { Icon: FileCode2, label: 'Building your app' },
  feature: { Icon: Puzzle, label: 'Adding the feature' },
  repair:  { Icon: Wrench, label: 'Applying your update' },
  select:  { Icon: MousePointerSquareDashed, label: 'Updating the selected element' },
  pencil:  { Icon: Pencil, label: 'Applying your drawing' },
  image:   { Icon: ImageIcon, label: 'Updating the picture' },
}

function CancelBuild() {
  const [asking, setAsking] = useState(false)
  const [sending, setSending] = useState(false)
  const addLog = useStore(s => s.addLog)

  async function stop() {
    setSending(true)
    try {
      await api.cancelBuild()
    } catch (e) {
      addLog('WARN', `could not cancel — ${e.message}`)
      setSending(false)
      setAsking(false)
    }
  }

  if (!asking) return (
    <button onClick={() => setAsking(true)}
            className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white/80 px-3 py-1.5 text-[11px] font-medium text-muted shadow-sm backdrop-blur transition hover:border-bad/30 hover:text-bad">
      <Square className="size-3" /> Cancel
    </button>
  )

  return (
    <div className="flex items-center gap-1.5 rounded-full bg-white/90 p-1 shadow-sm ring-1 ring-line">
      <span className="px-2 text-[10.5px] text-muted">Stop this run?</span>
      <button onClick={stop} disabled={sending}
              className="inline-flex items-center gap-1.5 rounded-full bg-bad px-3 py-1.5 text-[11px] font-semibold text-white disabled:opacity-60">
        {sending ? <Loader2 className="size-3 animate-spin" /> : <Square className="size-3" />}
        {sending ? 'Stopping' : 'Stop'}
      </button>
      <button onClick={() => setAsking(false)} disabled={sending}
              className="rounded-full px-3 py-1.5 text-[11px] text-muted hover:text-ink">
        Keep going
      </button>
    </div>
  )
}

export default function BuildOverlay() {
  const busy = useStore(s => s.busy)
  const opening = useStore(s => s.opening)
  const workKind = useStore(s => s.workKind)
  const logs = useStore(s => s.logs)
  const progress = useStore(s => s.progress)
  const liveFile = useStore(s => s.liveFile)
  const tests = useStore(s => s.tests)
  const phases = useStore(s => s.phases)
  const startedAt = useRef(0)
  const known = useRef(new Set())
  const queued = useRef([])
  const [visible, setVisible] = useState([])
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    if (!busy) {
      known.current = new Set()
      queued.current = []
      setVisible([])
      return
    }
    startedAt.current = Date.now()
    setNow(Date.now())
    const clock = setInterval(() => setNow(Date.now()), 1000)
    const reveal = setInterval(() => {
      const next = queued.current.shift()
      if (next) setVisible(rows => [...rows, next].slice(-5))
    }, 10000)
    return () => {
      clearInterval(clock)
      clearInterval(reveal)
    }
  }, [busy])

  const events = useMemo(() => {
    const rows = []
    const seen = new Set()
    for (const row of logs.slice(-360)) {
      const event = activityEvent(row.text, row.level)
      if (!event) continue
      const key = `${event.kind}:${event.title}:${event.detail || ''}`
      if (seen.has(key)) continue
      seen.add(key)
      rows.push({ ...event, at: row.at, key })
    }
    if (liveFile) {
      const current = liveFileActivity(liveFile)
      const key = `${current.kind}:${current.title}:${current.detail || ''}`
      if (!seen.has(key)) rows.push({ ...current, at: Date.now(), key, current: true })
    }
    return rows.slice(-80)
  }, [logs, liveFile])

  useEffect(() => {
    if (!busy) return
    const fresh = events.filter(event => !known.current.has(event.key))
    if (!fresh.length) return
    for (const event of fresh) known.current.add(event.key)

    // The first meaningful milestone appears immediately. Later milestones are
    // deliberately paced so a burst of backend logs reads like a live agent,
    // not a terminal dump. The newest five are all the UI keeps on screen.
    if (!visible.length && !queued.current.length) {
      const [first, ...rest] = fresh
      setVisible(first ? [first] : [])
      queued.current.push(...rest)
    } else {
      queued.current.push(...fresh)
    }
  }, [busy, events, visible.length])

  if (!busy) return null

  if (opening) return (
    <div data-theme="light"
         className="absolute inset-0 z-[20] grid place-items-center bg-white">
      <div className="flex flex-col items-center gap-3 px-8 text-center">
        <Loader2 className="size-6 animate-spin text-accent" />
        <p className="text-[14px] font-semibold text-ink">{progress.step || 'Opening the project…'}</p>
        <p className="text-[12px] text-muted">Reading the saved files and starting the preview.</p>
      </div>
    </div>
  )

  const work = WORK[workKind] || WORK.build
  const Icon = work.Icon
  const elapsed = Math.max(0, Math.floor((now - startedAt.current) / 1000))
  const phaseDone = phases.filter(p => p.status === 'done').length
  const phaseTotal = phases.length
  const latest = events.at(-1)
  const summary = latest?.title || friendlyStep(progress.step, tests.running)

  return (
    <div data-theme="light"
         className="absolute inset-0 z-[20] overflow-y-auto bg-white">
      <div className="absolute right-6 top-6 z-20"><CancelBuild /></div>

      <div className="mx-auto grid min-h-full w-full max-w-[1260px] items-center gap-7 px-7 py-10 lg:grid-cols-[.84fr_1.16fr]">
        <section className="flex min-h-[560px] flex-col p-6">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-[15px] bg-accent text-white shadow-[0_10px_24px_rgba(93,106,251,.24)]"><Icon className="size-4.5" /></span>
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-ink">{work.label}</p>
              <p className="mt-0.5 truncate text-[10.5px] text-muted">{summary}</p>
            </div>
            <span className="flex-1" />
            <span className="font-mono text-[10px] tabular-nums text-muted">{formatTime(elapsed)}</span>
          </div>

          <div className="mt-7 flex min-h-0 flex-1 flex-col justify-end gap-3 overflow-hidden">
            {!visible.length && (
              <div className="mb-auto px-1 py-4">
                <div className="flex items-center gap-2"><Loader2 className="size-3.5 animate-spin text-accent" /><p className="text-[12px] font-semibold text-ink">Creating the build plan</p></div>
                <p className="mt-1.5 text-[10.5px] leading-relaxed text-muted">Useful milestones will arrive here as the agent works.</p>
              </div>
            )}
            {visible.map((event, i) => {
              const active = i === visible.length - 1 && busy
              return (
                <article key={`${event.key}-${event.at || i}`}
                         className="max-w-[94%] px-1 py-3.5 text-ink transition-colors">
                  <div className="flex items-center gap-2">
                    <span className={cn('grid size-6 place-items-center rounded-full', active ? 'bg-accent text-white' : event.kind === 'done' ? 'bg-ok-tint text-ok' : 'bg-tint text-accent')}>
                      {active ? <Loader2 className="size-3 animate-spin" /> : event.kind === 'done' ? <Check className="size-3" /> : <span className="size-1.5 rounded-full bg-current" />}
                    </span>
                    <p className="text-[12px] font-semibold">{event.title}</p>
                  </div>
                  {event.detail && <p className="mt-1.5 pl-8 text-[10.5px] leading-relaxed text-muted">{event.detail}</p>}
                </article>
              )
            })}
          </div>

          <div className="mt-5 flex items-center gap-2 border-t border-line/60 pt-4 text-[10px] text-muted">
            <span className="size-1.5 animate-pulse rounded-full bg-accent" />
            {phaseTotal ? `${phaseDone}/${phaseTotal} build tasks complete` : 'Working through the approved plan'}
            {queued.current.length > 0 && <span>· {queued.current.length} activity update{queued.current.length === 1 ? '' : 's'} queued</span>}
          </div>
        </section>

        <section className="relative flex min-h-[560px] items-center justify-center overflow-hidden p-5">
          <div className="absolute left-5 top-5 z-10 rounded-full bg-white/85 px-3 py-1.5 text-[10px] font-medium text-muted shadow-sm ring-1 ring-line/60 backdrop-blur">AgentForge build flow</div>
          <img src="/__agentforge/builder-flow.gif" alt="AgentForge build flow"
               className="h-auto max-h-[515px] w-full max-w-[760px] select-none object-contain" />
        </section>
      </div>
    </div>
  )
}

function friendlyStep(step, testing) {
  const raw = String(step || '').replace(/[.…]+$/, '').trim()
  if (testing) return 'Running verification'
  if (!raw) return 'Creating the build plan'
  if (/plan/i.test(raw)) return 'Creating the build plan'
  if (/test|vitest/i.test(raw)) return 'Running unit tests'
  if (/e2e|journey|playwright/i.test(raw)) return 'Running end-to-end testing'
  if (/repair|fix/i.test(raw)) return 'Repairing the affected flow'
  return raw
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m ? `${m}m ${String(s).padStart(2, '0')}s` : `${s}s`
}
