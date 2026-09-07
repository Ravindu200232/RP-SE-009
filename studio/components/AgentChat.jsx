'use client'

/**
 * The conversation with the agent, beside the work.
 *
 * This replaced a terminal drawer, twice over. A terminal is the right tool
 * when you are debugging the backend and the wrong one when you are watching
 * an app get built: the interesting line scrolls past between two hundred npm
 * warnings. And a drawer, however good its contents, covers the preview it is
 * describing — so you close it, and then you cannot see the agent.
 *
 * A column solves both. The stream, the plan, the design and the run's context
 * are always visible on the left; the preview, code, tests and deployment keep
 * the whole right-hand side.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ChevronDown, CircleAlert, CircleCheck, FileCode2, FlaskConical, Loader2,
  MessageSquare, Palette, Search, Send, Sparkles, Terminal, Wrench,
} from 'lucide-react'

import { api } from '@/lib/api'
import { chatTurns } from '@/lib/chat'
import { consoleReport, forgetConsole } from '@/lib/console-log'
import { useStore } from '@/lib/store'
import { useEditAttachments } from '@/lib/use-edit-attachments'
import { answerQuestion, send } from '@/lib/ws'
import { cn } from '@/lib/utils'
import EditAttach from './EditAttach'
import TunePrompt from './TunePrompt'

const ICONS = {
  read: Search, plan: Search, write: FileCode2, build: FileCode2,
  test: FlaskConical, run: Terminal, fix: Wrench, design: Palette,
  verify: CircleCheck, done: CircleCheck, warn: CircleAlert,
  setup: Sparkles, note: Sparkles,
}

const KIND_TONE = {
  warn: 'bg-warn-tint text-warn',
  done: 'bg-ok-tint text-ok',
}

export default function AgentChat() {
  const logs = useStore(s => s.logs)
  const chat = useStore(s => s.chat)
  const busy = useStore(s => s.busy)
  const project = useStore(s => s.project)
  const question = useStore(s => s.question)
  const stats = useStore(s => s.runStats)
  const agentState = useStore(s => s.agentState)
  const pushChat = useStore(s => s.pushChat)

  // Collapsing gives the whole width back to the work when someone wants it.
  const [open, setOpen] = useState(true)
  const [text, setText] = useState('')
  const [reading, setReading] = useState(false)
  const [pending, setPending] = useState(null)
  const attach = useEditAttachments()
  const end = useRef(null)

  const turns = useMemo(() => chatTurns(logs, chat), [logs, chat])

  useEffect(() => {
    if (busy) setOpen(true)     // a run is the thing you watch
  }, [busy])

  useEffect(() => {
    if (open) end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [open, turns.length])

  async function submit() {
    const typed = text.trim()
    if (!typed || !project || busy) return

    // A paused scope question is answered by the next thing they type.
    if (question && answerQuestion(typed)) {
      pushChat({ role: 'user', text: typed, at: Date.now() })
      setText('')
      return
    }

    let full = typed
    if (attach.items.length) {
      setReading(true)
      try {
        full = typed + await attach.collect(project)
      } catch (e) {
        useStore.getState().addLog('WARN', e.message)
      }
      setReading(false)
    }

    const payload = {
      type: 'agent_update', project,
      route: useStore.getState().previewRoute || '',
      model: useStore.getState().models.builder || useStore.getState().models.agent,
      think: useStore.getState().think,
      qa_model: useStore.getState().models.qa || '',
      console: consoleReport(),
    }

    // The same rewording pass the Ask dialog used, kept because it is what
    // turns "the button is broken" into something an agent can act on.
    let tuned = full
    try {
      const r = await api.tune({ prompt: full, project, route: payload.route,
                                 model: payload.model })
      tuned = (r?.prompt || '').trim() || full
    } catch {
      // The request is still sendable exactly as typed.
    }
    setPending({ payload, shown: typed, typed: full, tuned })
  }

  function fire(payload, body, shown) {
    const s = useStore.getState()
    pushChat({ role: 'user', text: shown, at: Date.now() })
    send({ ...payload, prompt: body })
    forgetConsole()
    s.setBusy(true)
    attach.reset()
    setText('')
    setPending(null)
  }

  if (!open) {
    return (
      <div className="flex w-[46px] shrink-0 flex-col items-center gap-3 border-r border-line/60 bg-panel/70 py-3">
        <button onClick={() => setOpen(true)} title="Show the agent"
                className="grid size-8 place-items-center rounded-xl text-accent transition-colors hover:bg-accent/10">
          <MessageSquare className="size-4" />
        </button>
        {busy && <Loader2 className="size-3.5 animate-spin text-accent" />}
      </div>
    )
  }

  return (
    <aside className="flex w-[var(--chat-w,380px)] shrink-0 flex-col overflow-hidden border-r border-line/60 bg-panel/80">
      {pending && (
        <TunePrompt
          typed={pending.shown} tuned={pending.tuned}
          onSend={body => fire(pending.payload, body, pending.shown)}
          onSendTyped={() => fire(pending.payload, pending.typed, pending.shown)}
          onCancel={() => setPending(null)}
          onRetune={async body => {
            const r = await api.tune({ prompt: body, project,
                                       route: pending.payload.route,
                                       model: pending.payload.model })
            return (r?.prompt || '').trim()
          }} />
      )}

      <header className="shrink-0 border-b border-line/60 px-3.5 py-3">
        <div className="flex items-center gap-2">
          <span className="grid size-7 place-items-center rounded-xl bg-accent/10 text-accent">
            <MessageSquare className="size-3.5" />
          </span>
          <div className="min-w-0">
            <p className="text-[12.5px] font-semibold leading-none text-ink">Agent</p>
            <p className="mt-1 truncate text-[10px] text-muted2">
              {project || 'no project open'}
            </p>
          </div>
          <span className="flex-1" />
          {busy && (
            <span className="flex items-center gap-1.5 rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-semibold text-accent">
              <Loader2 className="size-2.5 animate-spin" /> working
            </span>
          )}
          <button onClick={() => setOpen(false)} title="Hide the agent"
                  className="grid size-7 place-items-center rounded-lg text-muted transition-colors hover:bg-black/[.05] hover:text-ink dark:hover:bg-white/[.06]">
            <ChevronDown className="size-3.5 -rotate-90" />
          </button>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-3.5 py-3">
        <div className="space-y-3">
          {turns.map((turn, i) => <Turn key={`${turn.at}-${i}`} turn={turn} />)}
          {!turns.length && (
            <p className="py-10 text-center text-[11.5px] text-muted">
              {project ? 'Ask for a change, or report something that is broken.'
                       : 'Open a project to talk to the agent.'}
            </p>
          )}
          <div ref={end} />
        </div>
      </div>

      <footer className="shrink-0 border-t border-line/60 px-3 py-2.5">
              <div className="flex items-end gap-2">
                <textarea
                  value={text} rows={1}
                  disabled={!project || busy || reading}
                  placeholder={question
                    ? 'Answer the question above…'
                    : busy ? 'The agent is working — this opens again when it finishes'
                    : project ? 'Describe a change, or what is broken…'
                              : 'Open a project first'}
                  onChange={e => setText(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
                  }}
                  className="max-h-[110px] min-h-[38px] flex-1 resize-y rounded-xl border border-line bg-white/70 px-3 py-2 text-[12.5px] leading-relaxed outline-none transition-colors focus:border-accent disabled:opacity-45 dark:bg-white/5" />
                <button onClick={submit}
                        disabled={!project || busy || reading || !text.trim()}
                        title="Send (Enter)"
                        className="grid size-[38px] shrink-0 place-items-center rounded-xl bg-accent text-white shadow-sm transition-opacity disabled:opacity-35">
                  {reading ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
                </button>
              </div>
              {project && (
                <EditAttach attach={attach} disabled={busy || reading} className="mt-1.5" />
              )}
      </footer>

      <StatusLine stats={stats} />
    </aside>
  )
}

/**
 * What the run is costing, along the bottom.
 *
 * The context bar is the number that decides whether a long build survives:
 * when it fills, older history is summarised and the model works from a
 * checkpoint instead of the transcript. Watching it fill is how you know that
 * is about to happen, so it is a bar rather than a percentage in a tooltip.
 */
function StatusLine({ stats }) {
  if (!stats) return null
  const percent = Math.max(0, Math.min(100, Number(stats.percent) || 0))
  const spent = (Number(stats.sent) || 0) + (Number(stats.received) || 0)
  return (
    <div className="shrink-0 border-t border-line/60 bg-panel2/50 px-3.5 py-2">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[9.5px] text-muted2">context</span>
        <span className="h-[5px] min-w-0 flex-1 overflow-hidden rounded-full bg-line">
          <span className={cn('block h-full rounded-full transition-[width] duration-500',
            percent >= 90 ? 'bg-bad' : percent >= 70 ? 'bg-warn' : 'bg-accent')}
                style={{ width: `${percent}%` }} />
        </span>
        <span className="font-mono text-[9.5px] tabular-nums text-muted">
          {compact(stats.tokens)}/{compact(stats.limit)}
        </span>
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[9.5px] text-muted2">
        {stats.model && <span title="model">{stats.model}</span>}
        {stats.requests > 0 && <span title="requests to the model">{stats.requests} req</span>}
        {spent > 0 && (
          <span title="tokens sent / received across the run">
            {compact(stats.sent)}↑ {compact(stats.received)}↓
          </span>
        )}
        {stats.iterations > 0 && <span title="loop steps">{stats.iterations} steps</span>}
        {stats.tools > 0 && <span title="tool calls">{stats.tools} tools</span>}
        {stats.files > 0 && <span title="files written">{stats.files} files</span>}
      </div>
    </div>
  )
}

function compact(n) {
  const value = Number(n) || 0
  return value >= 1000 ? `${Math.round(value / 100) / 10}k` : String(value)
}

/** The design the customiser chose, as the swatches it actually picked. */
function DesignCard({ design }) {
  const tokens = design?.tokens || {}
  const swatches = ['primary', 'accent', 'background', 'surface', 'text']
    .filter(role => tokens[role])
  return (
    <div className="mt-1.5 rounded-xl border border-line/70 bg-panel2/60 p-3">
      <p className="text-[12px] font-semibold text-ink">{design.palette}</p>
      <p className="mt-0.5 text-[11px] leading-relaxed text-muted">{design.mood}</p>
      {swatches.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {swatches.map(role => (
            <span key={role} title={`${role} ${tokens[role]}`}
                  className="flex items-center gap-1.5 rounded-lg border border-line/70 bg-panel px-1.5 py-1">
              <span className="size-3 rounded-[4px] ring-1 ring-black/[.08]"
                    style={{ background: tokens[role] }} />
              <span className="font-mono text-[9.5px] text-muted2">{tokens[role]}</span>
            </span>
          ))}
        </div>
      )}
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-0.5 text-[10.5px] text-muted">
        <Row label="Theme" value={design.theme} />
        <Row label="Type" value={design.font} />
        <Row label="Corners" value={design.radius} />
        <Row label="Spacing" value={design.density} />
      </dl>
      <p className="mt-2 font-mono text-[9.5px] text-muted2">{design.path}</p>
    </div>
  )
}

const Row = ({ label, value }) => (
  <div className="flex gap-1.5">
    <dt className="text-muted2">{label}</dt>
    <dd className="truncate text-ink">{value}</dd>
  </div>
)

/**
 * The model composing its next move.
 *
 * Between a request going out and the tool call coming back there is nothing
 * to log, and an empty feed for twenty seconds reads as a stall. The word and
 * the animation are the whole message: the reasoning text itself is the
 * model's working, not the user's.
 */
function Thinking() {
  return (
    <div className="flex items-center gap-2.5 py-0.5">
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-tint text-accent">
        <Sparkles className="size-3 animate-pulse" />
      </span>
      <span className="text-[12px] font-medium text-muted">Thinking</span>
      <span className="flex gap-1" aria-hidden="true">
        {[0, 1, 2].map(i => (
          <span key={i}
                className="size-1 animate-bounce rounded-full bg-accent/60"
                style={{ animationDelay: `${i * 140}ms`, animationDuration: '900ms' }} />
        ))}
      </span>
    </div>
  )
}

function Turn({ turn, live }) {
  if (turn.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[88%] rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-[12px] leading-relaxed text-white shadow-sm">
          {turn.text}
        </p>
      </div>
    )
  }

  if (turn.role === 'assistant') {
    const Icon = turn.kind === 'plan' ? Search
      : turn.kind === 'design' ? Palette : Sparkles
    return (
      <div className="flex gap-2.5">
        <span className={cn('mt-0.5 grid size-6 shrink-0 place-items-center rounded-full',
          turn.tone === 'bad' ? 'bg-bad/12 text-bad'
            : turn.tone === 'ok' ? 'bg-ok-tint text-ok' : 'bg-tint text-accent')}>
          <Icon className="size-3" />
        </span>
        <div className="min-w-0 flex-1">
          {turn.title && <p className="text-[12px] font-semibold text-ink">{turn.title}</p>}
          {turn.kind === 'design' && turn.design
            ? <DesignCard design={turn.design} />
            : turn.kind === 'plan'
              ? <pre className="mt-1 max-h-[280px] overflow-auto whitespace-pre-wrap rounded-xl border border-line/70 bg-panel2/60 p-3 font-mono text-[11px] leading-relaxed text-ink">{turn.text}</pre>
              : <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-muted">{turn.text}</p>}
        </div>
      </div>
    )
  }

  const Icon = ICONS[turn.kind] || Sparkles
  return (
    <div className="flex gap-2.5">
      <span className={cn('mt-0.5 grid size-6 shrink-0 place-items-center rounded-full',
        KIND_TONE[turn.kind] || 'bg-tint text-accent')}>
        {/* The step actually happening spins; the ones behind it do not. */}
        {live ? <Loader2 className="size-3 animate-spin" /> : <Icon className="size-3" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className={cn('break-words text-[12px] font-medium',
          turn.kind === 'warn' ? 'text-bad' : 'text-ink')}>{turn.title}</p>
        {turn.detail && (
          <p className="mt-0.5 text-[11px] leading-relaxed text-muted">{turn.detail}</p>
        )}
      </div>
    </div>
  )
}

function lastLine(turn) {
  if (!turn) return ''
  return turn.title || turn.text || ''
}
