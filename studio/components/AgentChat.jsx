'use client'

/**
 * The conversation with the agent, docked under the preview.
 *
 * This replaced a terminal pane. A terminal is the right tool when you are
 * debugging the backend and the wrong one when you are watching an app get
 * built: the interesting line scrolls past between two hundred npm warnings.
 * A chat keeps the same information in the order a person reads it, and gives
 * them somewhere to answer from.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ChevronDown, CircleAlert, CircleCheck, FileCode2, FlaskConical, Loader2,
  MessageSquare, Search, Send, Sparkles, Wrench,
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
  plan: Search, build: FileCode2, test: FlaskConical, fix: Wrench,
  verify: CircleCheck, done: Sparkles, warn: CircleAlert, setup: Sparkles,
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
  const pushChat = useStore(s => s.pushChat)

  const [open, setOpen] = useState(true)
  const [text, setText] = useState('')
  const [reading, setReading] = useState(false)
  const [pending, setPending] = useState(null)
  const attach = useEditAttachments()
  const end = useRef(null)

  const turns = useMemo(() => chatTurns(logs, chat), [logs, chat])

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

  return (
    <div className="pointer-events-none absolute inset-x-4 bottom-3 z-[45]">
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

      <div className={cn(
        'pointer-events-auto mx-auto flex w-full max-w-[980px] flex-col overflow-hidden',
        'rounded-[22px] border border-white/70 bg-white/92 shadow-[0_22px_55px_rgba(15,23,42,.18)]',
        'backdrop-blur-2xl transition-all duration-300 dark:border-white/10 dark:bg-[#111824]/94',
        open ? 'h-[360px]' : 'h-[52px]')}>

        <header className="flex h-[52px] shrink-0 items-center gap-2 px-3">
          <MessageSquare className="size-3.5 text-accent" />
          <span className="text-[12px] font-semibold text-ink">Agent</span>
          {busy && (
            <span className="flex items-center gap-1.5 rounded-full bg-accent/10 px-2 py-0.5 text-[10px] font-semibold text-accent">
              <Loader2 className="size-2.5 animate-spin" /> working
            </span>
          )}
          {!open && turns.length > 0 && (
            <span className="min-w-0 flex-1 truncate text-[11px] text-muted">
              {lastLine(turns.at(-1))}
            </span>
          )}
          <span className="flex-1" />
          <button onClick={() => setOpen(v => !v)}
                  title={open ? 'Collapse' : 'Expand'}
                  className="grid size-7 place-items-center rounded-lg text-muted transition-colors hover:bg-black/[.05] hover:text-ink dark:hover:bg-white/[.06]">
            <ChevronDown className={cn('size-3.5 transition-transform', open || 'rotate-180')} />
          </button>
        </header>

        {open && (
          <>
            <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-2">
              <div className="mx-auto max-w-[760px] space-y-3">
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
              <div className="mx-auto flex max-w-[760px] items-end gap-2">
                <textarea
                  value={text} rows={1}
                  disabled={!project || busy || reading}
                  placeholder={question
                    ? 'Answer the question above…'
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
                <div className="mx-auto max-w-[760px]">
                  <EditAttach attach={attach} disabled={busy || reading} className="mt-1.5" />
                </div>
              )}
            </footer>
          </>
        )}
      </div>
    </div>
  )
}

function Turn({ turn }) {
  if (turn.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[76%] rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-[12px] leading-relaxed text-white shadow-sm">
          {turn.text}
        </p>
      </div>
    )
  }

  if (turn.role === 'assistant') {
    return (
      <div className="flex gap-2.5">
        <span className={cn('mt-0.5 grid size-6 shrink-0 place-items-center rounded-full',
          turn.tone === 'bad' ? 'bg-bad/12 text-bad'
            : turn.tone === 'ok' ? 'bg-ok-tint text-ok' : 'bg-tint text-accent')}>
          <Sparkles className="size-3" />
        </span>
        <div className="min-w-0 flex-1">
          {turn.title && <p className="text-[12px] font-semibold text-ink">{turn.title}</p>}
          <p className="whitespace-pre-wrap text-[12px] leading-relaxed text-muted">{turn.text}</p>
        </div>
      </div>
    )
  }

  const Icon = ICONS[turn.kind] || Sparkles
  return (
    <div className="flex gap-2.5">
      <span className={cn('mt-0.5 grid size-6 shrink-0 place-items-center rounded-full',
        KIND_TONE[turn.kind] || 'bg-tint text-accent')}>
        <Icon className="size-3" />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        {turn.items.map((item, i) => (
          <div key={i}>
            <p className="text-[12px] font-medium text-ink">{item.title}</p>
            {item.detail && (
              <p className="text-[11px] leading-relaxed text-muted">{item.detail}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function lastLine(turn) {
  if (!turn) return ''
  if (turn.role === 'activity') return turn.items.at(-1)?.title || ''
  return turn.title || turn.text || ''
}
