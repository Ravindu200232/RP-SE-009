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
  MessageSquare, MousePointerClick, Palette, Pencil, Search, Send, Sparkles,
  Square, Terminal, Wrench, X,
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
  const selection = useStore(s => s.selection)
  const removeSelection = useStore(s => s.removeSelection)
  const clearSelection = useStore(s => s.clearSelection)

  // Collapsing gives the whole width back to the work when someone wants it.
  const [open, setOpen] = useState(true)
  const [text, setText] = useState('')
  const [reading, setReading] = useState(false)
  const [pending, setPending] = useState(null)
  const attach = useEditAttachments()
  const end = useRef(null)
  const box = useRef(null)

  const turns = useMemo(() => chatTurns(logs, chat), [logs, chat])

  useEffect(() => {
    if (busy) setOpen(true)     // a run is the thing you watch
  }, [busy])

  // Pointing at something in the preview is the start of a sentence, so the
  // box that finishes it comes to meet you.
  useEffect(() => {
    if (!selection.length) return
    setOpen(true)
    box.current?.focus()
  }, [selection.length])

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

    const route = selection[0]?.route || useStore.getState().previewRoute || ''
    const payload = {
      type: selection.length ? 'element_edit' : 'agent_update',
      project, route,
      model: useStore.getState().models.builder || useStore.getState().models.agent,
      think: useStore.getState().think,
      qa_model: useStore.getState().models.qa || '',
      console: consoleReport(),
    }
    if (selection.length) {
      payload.elements = selection.filter(s => s.kind === 'element').map(s => s.info)
      payload.shots = selection.filter(s => s.shot)
        .map(s => ({ kind: s.kind, image: s.shot, label: s.label }))
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
    setPending({ payload, shown: typed, typed: full, tuned,
                 shots: selection.filter(s => s.shot).map(s => s.shot) })
  }

  function fire(payload, body, shown) {
    const s = useStore.getState()
    pushChat({ role: 'user', text: shown, at: Date.now(),
               shots: pending?.shots || [] })
    send({ ...payload, prompt: body })
    forgetConsole()
    s.setBusy(true)
    attach.reset()
    clearSelection()
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
    <aside className="flex w-[var(--chat-w,460px)] shrink-0 flex-col overflow-hidden border-r border-line/60 bg-panel/80">
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
            <>
              <span className="flex items-center gap-1.5 rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-semibold text-accent">
                <Loader2 className="size-2.5 animate-spin" /> working
              </span>
              <CancelRun />
            </>
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
              <Attached items={selection} onRemove={removeSelection} />
              <div className="flex items-end gap-2">
                <textarea
                  ref={box}
                  value={text} rows={1}
                  disabled={!project || busy || reading}
                  placeholder={question
                    ? 'Answer the question above…'
                    : busy ? 'The agent is working — this opens again when it finishes'
                    : selection.length
                      ? 'Say what should change about it…'
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
 * What is riding along with the message being written.
 *
 * A click in the preview and a stroke of the pencil both land here, each with
 * its own photograph, and stay until the message is sent. Seeing them stack up
 * is the only way to know that three clicks attached three things — and the
 * cross on each one is how you take back the one you did not mean.
 */
function Attached({ items, onRemove }) {
  if (!items.length) return null
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {items.map(item => {
        const Icon = item.kind === 'drawing' ? Pencil : MousePointerClick
        return (
          <span key={item.key} title={item.label}
                className="group relative flex max-w-[190px] items-center gap-1.5 rounded-lg border border-line/80 bg-panel2/70 py-1 pl-1 pr-1.5">
            <span className="grid size-8 shrink-0 place-items-center overflow-hidden rounded-md bg-white ring-1 ring-line/70 dark:bg-white/10">
              {item.state === 'shooting'
                ? <Loader2 className="size-3 animate-spin text-accent" />
                : item.shot
                  ? <img src={item.shot} alt="" className="size-full object-cover object-top" />
                  : <Icon className="size-3 text-muted2" />}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[10.5px] font-medium text-ink">
                {item.kind === 'drawing' ? 'Drawing' : shortLabel(item.label)}
              </span>
              <span className="block truncate font-mono text-[9px] text-muted2">
                {item.route || '/'}
              </span>
            </span>
            <button onClick={() => onRemove(item.key)}
                    title="Remove this from the message"
                    className="shrink-0 text-muted2 transition-colors hover:text-bad">
              <X className="size-3" />
            </button>
          </span>
        )
      })}
    </div>
  )
}

/** `<button> Add to basket   /plants` -> `<button> Add to basket`. */
function shortLabel(label) {
  const text = String(label || '').split(/\s{2,}/)[0].trim()
  return text.length > 34 ? text.slice(0, 33) + '…' : text || 'Element'
}

/**
 * Stopping the run, from the one place that is always on screen.
 *
 * This used to live on the build screen, which is gone; the chat header is
 * where someone looks when they want a run to stop, because it is what they
 * are already watching.
 */
function CancelRun() {
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
    <button onClick={() => setAsking(true)} title="Stop this run"
            className="grid size-7 place-items-center rounded-lg text-muted transition-colors hover:bg-bad/10 hover:text-bad">
      <Square className="size-3" />
    </button>
  )

  return (
    <span className="flex items-center gap-1">
      <button onClick={stop} disabled={sending}
              className="inline-flex items-center gap-1 rounded-full bg-bad px-2 py-0.5 text-[10px] font-semibold text-white disabled:opacity-60">
        {sending ? <Loader2 className="size-2.5 animate-spin" /> : <Square className="size-2.5" />}
        {sending ? 'Stopping' : 'Stop'}
      </button>
      <button onClick={() => setAsking(false)} disabled={sending}
              className="rounded-full px-1.5 py-0.5 text-[10px] text-muted hover:text-ink">
        Keep going
      </button>
    </span>
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
      <div className="flex flex-col items-end gap-1.5">
        {(turn.shots || []).length > 0 && (
          <div className="flex max-w-[88%] flex-wrap justify-end gap-1.5">
            {turn.shots.map((shot, i) => (
              <img key={i} src={shot} alt="What they pointed at"
                   className="max-h-[104px] rounded-xl border border-line/70 object-cover object-top shadow-sm" />
            ))}
          </div>
        )}
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
