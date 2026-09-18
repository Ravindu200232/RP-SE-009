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

import { memo, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowDown, Check, CheckCircle2, ChevronDown, ChevronRight, CircleAlert, CircleCheck, Clock, Copy, ExternalLink, Eye, FileCode2, FlaskConical, ListChecks, Loader2,
  MessageSquare, MousePointerClick, Palette, Pencil, Search, Send, Sparkles,
  Square, Terminal, Wrench, X,
} from 'lucide-react'

import { api } from '@/lib/api'
import { chatTurns } from '@/lib/chat'
import { consoleReport, forgetConsole } from '@/lib/console-log'
import { computeLineDiff } from '@/lib/diff'
import { useStore } from '@/lib/store'
import { useRunData } from '@/lib/use-run-data'
import DeployActivity from './deploy/DeployActivity'
import { useEditAttachments } from '@/lib/use-edit-attachments'
import { answerQuestion, reviseDrawing, send } from '@/lib/ws'
import { cn } from '@/lib/utils'
import EditAttach from './EditAttach'
import SrsRevisionsPanel from './srs/SrsRevisionsPanel'

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

/**
 * The deployment agent's conversation, in the same place as the other two.
 *
 * It reads the run the Deploy panel published to the store rather than
 * fetching the deployment state again, so both show the same run and answering
 * here is answering there.
 */
function DeployChat() {
  const runId = useStore(s => s.deployRunId)
  const run = useRunData(runId)
  const running = Boolean(run.events?.length) && !run.question && run.busy
  if (!runId) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-6 text-center">
        <p className="text-[11.5px] text-muted">
          No deployment has run for this project yet. Start one from the Deploy tab
          and its conversation appears here.
        </p>
      </div>
    )
  }
  // Not a scroller wrapping a fixed block: the stream is the column, so it
  // takes the panel's whole height and the log scrolls inside it.
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <DeployActivity fill events={run.events} running={running} question={run.question}
                      runId={runId} onAnswered={run.reload} />
    </div>
  )
}

export default function AgentChat() {
  const logs = useStore(s => s.logs)
  const chat = useStore(s => s.chat)
  const busy = useStore(s => s.busy)
  const buildAllowed = useStore(s => Boolean(s.buildAvailability[s.project]))
  const project = useStore(s => s.project)
  const agentRole = useStore(s => s.agentRole)
  const onDeploy = useStore(s => s.view === 'deploy')
  const onSrs = useStore(s => s.view === 'srs')
  const switchAgent = useStore(s => s.switchAgent)
  const question = useStore(s => s.question)
  const drawing = useStore(s => s.drawing)
  const stats = useStore(s => s.runStats)
  const agentState = useStore(s => s.agentState)
  const reasoning = useStore(s => s.reasoning)
  const pushChat = useStore(s => s.pushChat)
  const selection = useStore(s => s.selection)
  const removeSelection = useStore(s => s.removeSelection)
  const clearSelection = useStore(s => s.clearSelection)

  // Collapsing gives the whole width back to the work when someone wants it.
  const [open, setOpen] = useState(true)
  const text = useStore(s => s.draft || '')
  const setText = useStore(s => s.setDraft)
  const [reading, setReading] = useState(false)
  const attach = useEditAttachments()
  const end = useRef(null)
  const box = useRef(null)
  const scrollRef = useRef(null)
  const userScrolledUp = useRef(false)
  const [showScrollBottom, setShowScrollBottom] = useState(false)

  const turns = useMemo(() => chatTurns(logs, chat), [logs, chat])
  const waiting = useStore(s => s.queue)
  const queued = useMemo(() => waiting.filter(item => item.project === project && item.payload?.agent === agentRole),
                         [waiting, project, agentRole])

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

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const isBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
    userScrolledUp.current = !isBottom
    setShowScrollBottom(!isBottom)
  }

  const scrollToBottom = () => {
    userScrolledUp.current = false
    setShowScrollBottom(false)
    end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }

  useEffect(() => {
    if (open && !userScrolledUp.current) {
      end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
    }
  }, [open, turns.length])

  // The moment a run ends, the next thing they typed goes. Firing sets the
  // agent working again, which brings this back for the one after it.
  useEffect(() => {
    if (busy || !project) return
    const next = useStore.getState().takeQueued(project, agentRole) // takeQueued(project)
    if (next) fire(next.payload, next.body, next.shown, next.shots)
  }, [busy, project])

  async function submit() {
    const typed = text.trim()
    if (!typed || !project || reading) return

    // A paused scope question is answered by the next thing they type.
    if (question && answerQuestion(typed)) {
      pushChat({ role: 'user', text: typed, at: Date.now() })
      setText('')
      return
    }

    // So is a drawing waiting in the preview: there is no dialog to type into,
    // so what they say here is what changes about it.
    if (drawing && reviseDrawing(typed)) {
      pushChat({ role: 'user', text: typed, at: Date.now() })
      setText('')
      return
    }

    let full = typed
    setReading(true)
    if (attach.items.length) {
      try {
        full = typed + await attach.collect(project)
      } catch (e) {
        useStore.getState().addLog('WARN', e.message)
      }
    }

    if (useStore.getState().project !== project || useStore.getState().agentRole !== agentRole) return
    const route = agentRole === 'designer' ? '/prototype' : (selection[0]?.route || useStore.getState().previewRoute || '/')
    const payload = {
      type: selection.length ? 'element_edit' : 'agent_update',
      project, route, agent: agentRole,
      model: (agentRole === 'designer' ? useStore.getState().models.design : useStore.getState().models.builder) || useStore.getState().models.agent,
      think: useStore.getState().think,
      qa_model: useStore.getState().models.qa || '',
      console: consoleReport(),
    }
    if (selection.length) {
      payload.elements = selection.filter(s => s.kind === 'element').map(s => s.info)
      payload.shots = selection.filter(s => s.shot)
        .map(s => ({ kind: s.kind, image: s.shot, label: s.label }))
    }

    const shots = selection.filter(s => s.shot).map(s => s.shot)
    if (busy) {
      queueUp(payload, full, typed, shots)
    } else {
      fire(payload, full, typed, shots)
    }
    setReading(false)
  }

  /** Hold it until the run in front of it is done. */
  function queueUp(payload, body, shown, shots) {
    useStore.getState().enqueue({ project, payload, body, shown, shots })
    // The console evidence in the payload has been taken; what arrives after
    // this belongs to whatever is said next.
    forgetConsole()
    attach.reset()
    clearSelection()
    setText('')
  }

  /**
   * Say it, and it goes.
   *
   * A dialog used to open here first, offering a reworded version of the
   * sentence and asking whether that was what you meant. It was answering a
   * question nobody had: pasting a stack trace and being asked to approve a
   * paraphrase of it is a step between you and the agent, not a help. What
   * you typed is what the agent gets.
   */
  function fire(payload, body, shown, shots = []) {
    const s = useStore.getState()
    // The server journals and echoes the message, including queued requests.
    send({ ...payload, prompt: body })
    forgetConsole()
    s.setBusy(true)
    attach.reset()
    clearSelection()
    setText('')
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
    <aside className="flex w-[100%] lg:w-[var(--chat-w,460px)] max-w-full shrink-0 flex-col overflow-hidden border-r border-line/60 bg-panel/80">
      <div className="flex gap-1 border-b border-line p-2" aria-label="Agent conversations">
        {[['designer', 'Designer · UI/UX'], ['developer', 'Developer · QA']].map(([role, label]) => (
          <button key={role} disabled={role === 'developer' && !buildAllowed} title={role === 'developer' && !buildAllowed ? 'Complete the prototype first' : label} onClick={() => { switchAgent(role); useStore.getState().setView(role === 'designer' ? 'prototype' : 'preview') }}
            className={cn('flex-1 rounded-lg px-2 py-2 text-xs font-semibold', !onDeploy && !onSrs && agentRole === role ? 'bg-accent/15 text-accent' : 'text-muted hover:text-ink')}
            aria-pressed={!onDeploy && !onSrs && agentRole === role}>{label}</button>
        ))}
        {/* The deployment has its own agent, so it gets its own conversation
            here rather than a stream buried under the panel on the right. */}
        <button disabled={!buildAllowed} title={buildAllowed ? 'Deployment' : 'Complete the prototype first'}
          onClick={() => useStore.getState().setView('deploy')}
          className={cn('flex-1 rounded-lg px-2 py-2 text-xs font-semibold',
            onDeploy ? 'bg-accent/15 text-accent' : 'text-muted hover:text-ink')}
          aria-pressed={onDeploy}>Deployment</button>
        {/* The specification is the fourth conversation. It is keyed on the
            view rather than on an agent role, so opening the SRS tab selects
            it on its own - which is where someone reading the document would
            look for its history anyway. */}
        <button title="The specification and its revisions"
          onClick={() => useStore.getState().setView('srs')}
          className={cn('flex-1 rounded-lg px-2 py-2 text-xs font-semibold',
            onSrs ? 'bg-accent/15 text-accent' : 'text-muted hover:text-ink')}
          aria-pressed={onSrs}>Specification</button>
      </div>
      {onSrs ? (
        <SrsRevisionsPanel />
      ) : onDeploy ? (
        <DeployChat />
      ) : (<>
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

      <div ref={scrollRef} onScroll={handleScroll} className="relative min-h-0 flex-1 overflow-y-auto px-3.5 py-3">
        <div className="space-y-3">
          {/* The last row is the one happening now, so it is the one that
              spins; the rows behind it have already happened. */}
          {turns.map((turn, i) => (
            <Turn key={turn.id || `${turn.at}-${i}`} turn={turn}
                  live={busy && i === turns.length - 1} />
          ))}
          {busy && agentState === 'thinking' && <Thinking reasoning={reasoning} />}
          {queued.map(item => (
            <Queued key={item.id} item={item}
                    onDrop={() => useStore.getState().dropQueued(item.id)} />
          ))}
          {!turns.length && !queued.length && (
            <p className="py-10 text-center text-[11.5px] text-muted">
              {project ? 'Continue this project with your next request.'
                       : 'Open a project to talk to the agent.'}
            </p>
          )}
          <div ref={end} />
        </div>
        {showScrollBottom && (
          <button onClick={scrollToBottom}
                  title="Scroll to latest messages"
                  className="sticky bottom-3 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1.5 rounded-full border border-line/90 bg-panel px-3.5 py-1.5 text-[11px] font-semibold text-accent shadow-xl backdrop-blur hover:bg-accent hover:text-white transition-all">
            <ArrowDown className="size-3.5" /> Latest messages
          </button>
        )}
      </div>

      <footer className="shrink-0 border-t border-line px-3.5 py-3">
        <Attached items={selection} onRemove={removeSelection} />
        <div className="rounded-2xl border border-line bg-panel2/70 p-2.5 focus-within:border-accent/50 focus-within:bg-panel shadow-sm transition-all">
          <textarea
            ref={box}
            aria-label="Continue this project"
            value={text} rows={2}
            disabled={!project || reading}
            placeholder={question
              ? 'Answer the question above…'
              : drawing ? 'Say what to change about the drawing…'
              : busy ? 'Say what is next — it goes when this finishes'
              : selection.length
                ? 'Say what should change about it…'
              : project ? 'How can AgentForge help you today? (or /command)'
                        : 'Open a project first'}
            onChange={e => setText(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
            }}
            className="w-full resize-none bg-transparent px-2 py-1 text-[13px] leading-relaxed text-ink outline-none placeholder:text-muted2 disabled:opacity-45" />
          <div className="mt-1 flex items-center justify-between border-t border-line/40 pt-1.5 px-1">
            {project ? (
              <EditAttach attach={attach} project={project}
                      onSpoken={said => setText((text ? text.trimEnd() + ' ' : '') + said)} disabled={reading} />
            ) : <span />}
            <button onClick={submit}
                    disabled={!project || reading || !text.trim()}
                    title={busy ? 'Queue this (Enter)' : 'Send (Enter)'}
                    className="grid size-8 shrink-0 place-items-center rounded-xl bg-accent text-white shadow-sm transition-all hover:bg-press disabled:opacity-30">
              {reading ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
            </button>
          </div>
        </div>
      </footer>

      <StatusLine stats={stats} />
      </>)}
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
      const current = useStore.getState()
      await api.cancelBuild(current.project, current.agentRole)
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
      {/* The model is chosen in Settings and is the same for every run, so
          naming it on every line of every chat said nothing that changed. */}
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 font-mono text-[9.5px] text-muted2">
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
/**
 * The agent is between one tool call and the next.
 *
 * Which is not the same as the model reasoning, and this said "Thinking" for
 * both — so a run with the thinking switch off looked exactly like one with it
 * on, and there was no way to tell from the screen which you had. The engine
 * now says which it is and the label follows it.
 */
function Thinking({ reasoning = false }) {
  return (
    <div className="flex items-center gap-2.5 py-0.5">
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-tint text-accent">
        <Sparkles className="size-3 animate-pulse" />
      </span>
      <span className="text-[12px] font-medium text-muted">
        {reasoning ? 'Thinking' : 'Working'}
      </span>
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

/** Something said while the agent was busy, waiting its turn. */
function Queued({ item, onDrop }) {
  return (
    <div className="flex flex-col items-end gap-1">
      <div className="max-w-[88%] rounded-2xl rounded-br-md border border-dashed border-accent/45 bg-accent/[.05] px-3 py-2 text-[12.5px] leading-relaxed text-ink">
        {item.shown}
      </div>
      <span className="flex items-center gap-2 pr-1 text-[10px] text-muted2">
        <Clock className="size-2.5" /> waiting for the current run
        <button onClick={onDrop} className="text-muted2 underline-offset-2 hover:text-ink hover:underline">
          don’t send
        </button>
      </span>
    </div>
  )
}

function parseFileInfo(title) {
  const clean = String(title || '').replace(/^(written|created|patched|edited|writing|editing|removed|reading|read)\s+/i, '').trim()
  const pathOnly = clean.replace(/\s*\(\d+\s*lines\)/i, '').trim()
  const parts = pathOnly.split('/')
  const fileName = parts[parts.length - 1] || pathOnly
  return { fileName, filePath: pathOnly }
}

function FileActionCard({ turn, live }) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const [fetchedContent, setFetchedContent] = useState(null)
  const [fetching, setFetching] = useState(false)

  const { fileName, filePath } = parseFileInfo(turn.file || turn.title)
  const files = useStore(s => s.files)
  const fileHistory = useStore(s => s.fileHistory || {})
  const readFiles = useStore(s => s.readFiles || {})
  const project = useStore(s => s.project)
  const agentRole = useStore(s => s.agentRole)

  const isPatch = turn.action === 'patched' || turn.action === 'edited' || turn.action === 'editing' || /patched|edited|editing/i.test(turn.title || '')
  const isRead = turn.kind === 'read'

  // History & contents
  const history = fileHistory[filePath] || fileHistory[fileName] || {}
  const oldText = history.oldContent || ''
  const currentText = files[filePath] || files[fileName] || history.newContent || fetchedContent || ''
  const readContent = readFiles[filePath] || readFiles[fileName] || currentText || ''

  const diff = useMemo(() => {
    if (!isPatch) return null
    return computeLineDiff(oldText, currentText)
  }, [isPatch, oldText, currentText])

  // Lazy fetch if expanded and not in memory
  useEffect(() => {
    if (expanded && !currentText && !readContent && !fetching && project) {
      setFetching(true)
      api.files(project, agentRole)
        .then(res => {
          if (res?.files?.[filePath]) setFetchedContent(res.files[filePath])
        })
        .catch(() => {})
        .finally(() => setFetching(false))
    }
  }, [expanded, currentText, readContent, fetching, project, agentRole, filePath])

  const copyCode = (e) => {
    e.stopPropagation()
    const textToCopy = isRead ? readContent : currentText
    if (!textToCopy) return
    navigator.clipboard.writeText(textToCopy).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const openInEditor = (e) => {
    e.stopPropagation()
    useStore.getState().setView('code')
    if (filePath) useStore.getState().selectFile(filePath)
  }

  const iconBg = isRead
    ? 'bg-[#FFAB00]/15 text-[#FFAB00]'
    : isPatch
      ? 'bg-[#8E33FF]/15 text-[#8E33FF]'
      : 'bg-[#1877F2]/15 text-[#1877F2]'

  const IconComponent = isRead ? Eye : Pencil

  const badgeText = isRead
    ? 'read'
    : isPatch
      ? (diff && (diff.additions > 0 || diff.deletions > 0) ? `+${diff.additions} -${diff.deletions}` : (turn.inProgress ? 'editing' : 'patched'))
      : (turn.inProgress ? (turn.action || 'writing') : (turn.action || 'created'))

  const badgeStyle = isRead
    ? 'bg-[#FFAB00]/15 text-[#FFAB00] border-[#FFAB00]/30'
    : isPatch
      ? 'bg-[#8E33FF]/15 text-[#8E33FF] border-[#8E33FF]/30'
      : 'bg-[#1877F2]/15 text-[#1877F2] border-[#1877F2]/30'

  return (
    <div className="my-1.5 overflow-hidden rounded-2xl border border-line bg-panel2/60 shadow-sm transition-all hover:border-accent/40">
      <div onClick={() => setExpanded(prev => !prev)}
           title={expanded ? 'Click to collapse' : 'Click to inspect code'}
           className="flex items-center justify-between gap-3 p-3 cursor-pointer select-none hover:bg-panel transition-colors">
        <div className="flex items-center gap-3 min-w-0">
          <div className={cn('grid size-9 shrink-0 place-items-center rounded-xl transition-transform', iconBg)}>
            <IconComponent className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="truncate font-semibold text-ink text-[13px]">{fileName}</p>
              <span className={cn('rounded px-1.5 py-0.5 text-[9px] font-mono border uppercase tracking-wide', badgeStyle)}>
                {badgeText}
              </span>
            </div>
            <p className="truncate font-mono text-[11px] text-muted">{filePath || fileName}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {live || turn.inProgress ? (
            <Loader2 className="size-4 animate-spin text-accent" />
          ) : (
            <CheckCircle2 className="size-5 text-emerald-500" />
          )}
          <ChevronRight className={cn('size-4 text-muted2 transition-transform duration-200', expanded && 'rotate-90 text-ink')} />
        </div>
      </div>

      {expanded && (
        <div className="border-t border-line/60 bg-[#0c0f17] p-3 text-white">
          <div className="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-white/10 text-xs">
            <span className="font-mono text-[11px] text-slate-400 truncate max-w-[220px]" title={filePath}>
              {filePath}
            </span>
            <div className="flex items-center gap-1.5 shrink-0">
              <button onClick={copyCode}
                      title="Copy code"
                      className="flex items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[11px] font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors">
                {copied ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
              <button onClick={openInEditor}
                      title="Open in editor"
                      className="flex items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[11px] font-medium text-slate-300 hover:bg-white/10 hover:text-white transition-colors">
                <ExternalLink className="size-3" /> Editor
              </button>
            </div>
          </div>

          <div className="max-h-[320px] overflow-auto rounded-lg border border-white/10 bg-[#080b11] p-2 font-mono text-[11px] leading-relaxed select-text">
            {fetching ? (
              <div className="py-6 flex items-center justify-center gap-2 text-slate-400 text-xs">
                <Loader2 className="size-3.5 animate-spin text-accent" /> Loading file content…
              </div>
            ) : isPatch && diff ? (
              <div className="space-y-0.5">
                {diff.lines.map((line, idx) => (
                  <div key={idx}
                       className={cn('flex items-start px-2 py-0.5 rounded-[3px]',
                         line.type === 'del' && 'bg-rose-500/15 text-rose-300 border-l-2 border-rose-500 font-medium',
                         line.type === 'add' && 'bg-emerald-500/15 text-emerald-300 border-l-2 border-emerald-500 font-medium',
                         line.type === 'same' && 'text-slate-400 hover:bg-white/[0.03]')}>
                    <span className="w-8 shrink-0 select-none text-right pr-2 opacity-40 tabular-nums">
                      {line.type === 'del' ? line.oldNo : line.type === 'add' ? line.newNo : line.newNo || line.oldNo}
                    </span>
                    <span className="w-4 shrink-0 select-none text-center font-bold">
                      {line.type === 'del' ? '-' : line.type === 'add' ? '+' : ' '}
                    </span>
                    <span className="flex-1 whitespace-pre-wrap break-all">{line.text || ' '}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-0.5">
                {((isRead ? readContent : currentText) || '// File content empty or loaded from environment').split(/\r?\n/).map((line, idx) => (
                  <div key={idx} className="flex items-start px-2 py-0.5 text-slate-300 hover:bg-white/[0.03] rounded-[3px]">
                    <span className="w-8 shrink-0 select-none text-right pr-2 opacity-40 tabular-nums">
                      {idx + 1}
                    </span>
                    <span className="flex-1 whitespace-pre-wrap break-all">{line || ' '}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * One row of the feed.
 *
 * Memoised because the feed is rebuilt whenever a line arrives and the rows
 * behind the newest one have not changed: a build writes several lines a
 * second, and each of them was re-rendering the whole visible history to add
 * one row to the end of it. The turns themselves are stable objects, so this
 * compares by identity and almost always skips.
 */
const Turn = memo(function Turn({ turn, live }) {
  if (turn.role === 'user') {
    return (
      <div className="flex flex-col items-end gap-1.5 my-1">
        {(turn.shots || []).length > 0 && (
          <div className="flex max-w-[88%] flex-wrap justify-end gap-1.5">
            {turn.shots.map((shot, i) => (
              <img key={i} src={shot} alt="What they pointed at"
                   className="max-h-[104px] rounded-xl border border-line/70 object-cover object-top shadow-sm" />
            ))}
          </div>
        )}
        <p className="max-w-[88%] rounded-2xl rounded-tr-sm bg-accent/15 border border-accent/25 px-4 py-2.5 text-[13px] leading-relaxed text-ink shadow-sm dark:bg-[#1877F2]/15 dark:border-[#1877F2]/30 dark:text-white">
          {turn.text}
        </p>
      </div>
    )
  }

  if (turn.role === 'assistant') {
    const Icon = turn.kind === 'plan' ? Search
      : turn.kind === 'design' ? Palette : Sparkles
    return (
      <div className="flex gap-2.5 my-1">
        <span className={cn('mt-0.5 grid size-6 shrink-0 place-items-center rounded-full',
          turn.tone === 'bad' ? 'bg-bad/12 text-bad'
            : turn.tone === 'ok' ? 'bg-ok-tint text-ok' : 'bg-tint text-accent')}>
          <Icon className="size-3" />
        </span>
        <div className="min-w-0 flex-1">
          {turn.title && <p className="text-[12.5px] font-semibold text-ink">{turn.title}</p>}
          {turn.kind === 'design' && turn.design
            ? <DesignCard design={turn.design} />
            : turn.kind === 'plan'
              ? (
                <div className="mt-1 rounded-xl border border-line bg-panel2/60 p-3">
                  <div className="flex items-center gap-2 text-accent font-semibold text-[12px] mb-2">
                    <ListChecks className="size-3.5" /> Plan
                  </div>
                  <pre className="max-h-[280px] overflow-auto whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-ink">{turn.text}</pre>
                </div>
              )
              : <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink/90 font-normal">{turn.text}</p>}
        </div>
      </div>
    )
  }

  // Bolt File Action Card (Image 1)
  // Interactive File Action Card for write, patch and read (Image 1)
  if (turn.file && (turn.kind === 'write' || turn.kind === 'read')) {
    return <FileActionCard turn={turn} live={live} />
  }

  const Icon = ICONS[turn.kind] || Sparkles
  return (
    <div className="flex gap-2.5 my-1">
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
})

function lastLine(turn) {
  if (!turn) return ''
  return turn.title || turn.text || ''
}
