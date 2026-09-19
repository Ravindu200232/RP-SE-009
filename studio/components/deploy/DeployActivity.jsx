'use client'

import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Bot, Bug, Check, Loader2, SquareTerminal, Wrench, X } from 'lucide-react'
import { api } from '@/lib/api'

const SHOWN = ['agent', 'log', 'tool', 'step', 'state', 'question', 'error', 'warning', 'terminal']

/** Collapse repeats and fold a tool's result onto the call that made it. */
function conversation(events) {
  const rows = []
  const tools = new Map()
  for (const event of events) {
    if (!SHOWN.includes(event.type)) continue
    const call = event.type === 'tool' && event.data?.tool_call_id
    if (call && tools.has(call)) rows[tools.get(call)] = event
    else {
      const previous = rows.at(-1)
      if (!call && previous && previous.type === event.type && previous.stage === event.stage &&
          previous.status === event.status && previous.message === event.message) {
        rows[rows.length - 1] = { ...event, event_id: previous.event_id }
      } else { if (call) tools.set(call, rows.length); rows.push(event) }
    }
  }
  return rows
}

/** Formats and styles a deployment event row based on its type and repair status. */
function look(event) {
  const failed = event.type === 'error' || event.status === 'failed'
  const fixing = event.stage === 'repair'
  if (failed) return { Icon: AlertTriangle, tone: 'text-red-400', box: 'border-red-500/20 bg-red-500/5', text: 'text-red-200', label: fixing ? 'Fix attempt failed' : 'Failed' }
  if (event.type === 'warning') return { Icon: AlertTriangle, tone: 'text-amber-300', box: 'border-amber-500/20 bg-amber-500/5', text: 'text-white/80', label: 'Warning' }
  if (fixing) return { Icon: event.type === 'tool' ? Wrench : Bug, tone: 'text-amber-300', box: 'border-amber-400/25 bg-amber-400/[.06]', text: 'text-amber-50/90', label: event.type === 'tool' ? 'Fixing' : 'Found a problem' }
  if (event.type === 'terminal') return { Icon: SquareTerminal, tone: 'text-blue-400', box: 'border-white/10 bg-white/[.025]', text: 'text-white/80', label: event.stage || 'Terminal' }
  if (event.type === 'tool') return { Icon: Wrench, tone: 'text-blue-400', box: 'border-white/10 bg-white/[.025]', text: 'text-white/80', label: event.stage || 'Tool' }
  return { Icon: Bot, tone: 'text-blue-400', box: 'border-white/10 bg-white/[.025]', text: 'text-white/80', label: event.stage || 'Deployment agent' }
}

/** Renders interactive deployment agent questions directly within the event timeline. */
function Ask({ question, onPick, picked }) {
  return (
    <article className="flex items-start gap-2.5">
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-blue-500/10">
        <Bot className="size-3.5 text-blue-400" />
      </span>
      <div className="min-w-0 flex-1 rounded-xl border border-blue-500/30 bg-blue-500/[.06] px-3 py-2.5">
        <p className="mb-1 text-[10px] text-white/40">Deployment agent · waiting for you</p>
        <p className="whitespace-pre-wrap break-words text-[11.5px] leading-relaxed text-white">{question.text}</p>
        {(question.choices || []).length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {question.choices.map(choice => (
              <button key={choice} onClick={() => onPick(choice)}
                className={`rounded-ctl border px-2 py-1 text-[11px] transition ${picked === choice
                  ? 'border-blue-400 bg-blue-500/20 text-white' : 'border-white/20 text-white/80 hover:text-white'}`}>
                {choice}
              </button>
            ))}
          </div>
        )}
      </div>
    </article>
  )
}

// Validate deployment targets through the destination picker according to architecture capabilities.
const TARGET_TALK = /\b(vercel|netlify|azure|aws|ec2|ecs|fargate)\b/i
const CHANGE_TALK = /\b(deploy|change|switch|move|use|instead|rather|host|put)\b/i

/** Input composer allowing the user to respond to active deployment agent questions. */
function Composer({ question, runId, onAnswered, answer, setAnswer }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const refused = Boolean(answer.trim()) && TARGET_TALK.test(answer) && CHANGE_TALK.test(answer)

  async function submit() {
    if (!answer.trim() || busy || !question || refused) return
    setBusy(true); setError('')
    try {
      await api.deploy(`/runs/${runId}/answer`, { question_id: question.id, answer })
      setAnswer(''); onAnswered?.()
    } catch (failure) { setError(failure.message) } finally { setBusy(false) }
  }

  return (
    <div className="mt-3 border-t border-white/10 pt-3">
      <div className="flex items-center gap-2">
        <input aria-label="Message the deployment agent" value={answer} disabled={!question}
          onChange={e => setAnswer(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') submit() }}
          placeholder={question ? 'Answer the question above…'
            : 'The agent is working — it will ask here when it needs you'}
          className="min-w-0 flex-1 rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-[11.5px] text-white placeholder:text-white/35 disabled:opacity-50" />
        <button disabled={busy || !answer.trim() || !question || refused} onClick={submit}
          className="rounded-lg bg-blue-600 px-3 py-1.5 text-[11px] text-white disabled:opacity-40">
          {busy ? 'Sending…' : 'Send'}
        </button>
      </div>
      {refused ? (
        <p role="alert" className="mt-1.5 text-[10.5px] text-amber-300">
          The destination is chosen in <b className="font-semibold">Where should it go?</b> above, not here —
          that list is what knows which hosts can run this project.
        </p>
      ) : (
        <p className="mt-1.5 text-[10px] text-white/45">
          Credentials belong in Settings. Answer only with a choice or a confirmation.
        </p>
      )}
      {error && <p role="alert" className="mt-1.5 text-[11px] text-red-300">{error}</p>}
    </div>
  )
}

export default function DeployActivity({ events = [], running, question, runId, onAnswered,
                                         fill = false }) {
  const body = useRef(null)
  const follow = useRef(true)
  const [answer, setAnswer] = useState('')
  useEffect(() => { setAnswer('') }, [runId, question?.id])
  const messages = conversation(events).slice(-200)
  const fixes = messages.filter(e => e.stage === 'repair' && e.type !== 'question').length

  useEffect(() => {
    if (follow.current && body.current) body.current.scrollTop = body.current.scrollHeight
  }, [events.length, question?.id])

  return (
    // Expand activity log to occupy full column height in the chat panel.
    <section aria-label="Deployment agent activity"
             className={'border-t border-white/10 bg-[#121622] px-4 py-3'
               + (fill ? ' flex min-h-0 flex-1 flex-col' : '')}>
      <header className="flex items-center gap-2 text-[12px] font-semibold text-white">
        <Bot className="size-4 text-blue-400" /><span>Deployment chat</span>
        {fixes > 0 && (
          <span className="flex items-center gap-1 rounded-full bg-amber-400/10 px-2 py-0.5 text-[10px] font-normal text-amber-300">
            <Bug className="size-2.5" />{fixes} fix step{fixes === 1 ? '' : 's'}
          </span>
        )}
        <span className="ml-auto flex items-center gap-1.5 text-[10px] font-normal text-white/45">
          {question ? 'Waiting for you' : running ? <><Loader2 className="size-3 animate-spin" />Working</> : 'Read only'}
        </span>
      </header>
      <div ref={body} role="log" aria-live="polite" aria-relevant="additions text"
           onScroll={() => {
             const el = body.current
             follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 35
           }}
           className={'mt-3 space-y-3 overflow-auto pr-2 '
             + (fill ? 'min-h-0 flex-1' : 'h-[340px]')}>
        {!messages.length && !question && (
          <p className="py-4 text-[11px] text-white/40">Deployment agent messages will appear here.</p>
        )}
        {messages.map(event => {
          const { Icon, tone, box, text, label } = look(event)
          return (
            <article key={event.data?.tool_call_id || event.event_id} className="flex items-start gap-2.5">
              <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-blue-500/10">
                <Icon className={`size-3.5 ${tone}`} />
              </span>
              <div className={`min-w-0 flex-1 rounded-xl border px-3 py-2.5 ${box}`}>
                <div className="mb-1 flex items-center gap-2 text-[10px] capitalize text-white/40">
                  <span>{label}</span>
                  {running && event.status === 'running' && event === messages.at(-1) && (
                    <Loader2 className="size-2.5 animate-spin" />
                  )}
                  {event.type === 'tool' && event.status === 'complete' && <Check className="size-2.5 text-emerald-400" />}
                  {event.type === 'tool' && event.status === 'failed' && <X className="size-2.5 text-red-400" />}
                </div>
                <p className={`whitespace-pre-wrap break-words text-[11.5px] leading-relaxed ${text}`}>{event.message}</p>
              </div>
            </article>
          )
        })}
        {question && <Ask question={question} picked={answer} onPick={setAnswer} />}
        {running && !question && (
          <p className="flex items-center gap-2 pl-10 text-[11px] text-white/40">
            <Loader2 className="size-3 animate-spin" />Agent is working…
          </p>
        )}
      </div>
      <Composer question={question} runId={runId} onAnswered={onAnswered}
                answer={answer} setAnswer={setAnswer} />
    </section>
  )
}

/** Kept for callers that still render the question on its own. */
export function DeploymentQuestion({ question, runId, onAnswered }) {
  const [answer, setAnswer] = useState('')
  if (!question) return null
  return (
    <section aria-label="Deployment question" className="rounded-2xl border border-blue-500/20 bg-[#121622] p-4">
      <Ask question={question} picked={answer} onPick={setAnswer} />
      <Composer question={question} runId={runId} onAnswered={onAnswered}
                answer={answer} setAnswer={setAnswer} />
    </section>
  )
}
