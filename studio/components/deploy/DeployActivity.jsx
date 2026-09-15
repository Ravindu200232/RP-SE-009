'use client'

import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, Bot, Check, Loader2, SquareTerminal, Wrench } from 'lucide-react'
import { api } from '@/lib/api'

export default function DeployActivity({ events = [], running }) {
  const body = useRef(null)
  const follow = useRef(true)
  const rows = []
  const tools = new Map()
  for (const event of events) {
    if (!['agent', 'log', 'tool', 'step', 'state', 'question', 'error', 'warning', 'terminal'].includes(event.type)) continue
    const call = event.type === 'tool' && event.data?.tool_call_id
    if (call && tools.has(call)) rows[tools.get(call)] = event
    else {
      const previous = rows.at(-1)
      if (!call && previous && previous.type === event.type && previous.stage === event.stage &&
          previous.status === event.status && previous.message === event.message) {
        rows[rows.length - 1] = {...event, event_id: previous.event_id}
      } else { if (call) tools.set(call, rows.length); rows.push(event) }
    }
  }
  const messages = rows.slice(-100)
  useEffect(() => {
    if (follow.current && body.current) body.current.scrollTop = body.current.scrollHeight
  }, [events.length])
  return <section aria-label="Deployment agent activity" className="border-t border-white/10 bg-[#121622] px-4 py-3">
    <header className="flex items-center gap-2 text-[12px] font-semibold text-white">
      <Bot className="size-4 text-blue-400" /><span>Deployment chat</span>
      <span className="ml-auto flex items-center gap-1.5 text-[10px] font-normal text-white/45">
        {running && <Loader2 className="size-3 animate-spin" />}{running ? 'Working' : 'Read only'}
      </span>
    </header>
    <div ref={body} role="log" aria-live="polite" aria-relevant="additions text"
         onScroll={() => { const el = body.current; follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 35 }}
         className="mt-3 h-[220px] space-y-3 overflow-auto pr-2">
      {!messages.length && <p className="py-4 text-[11px] text-white/40">Deployment agent messages will appear here.</p>}
      {messages.map(event => {
        const failed = event.type === 'error' || event.status === 'failed'
        const warning = event.type === 'warning'
        const Icon = failed || warning ? AlertTriangle : event.type === 'terminal' ? SquareTerminal : event.type === 'tool' ? Wrench : Bot
        return <article key={event.data?.tool_call_id || event.event_id} className="flex items-start gap-2.5">
          <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-blue-500/10"><Icon className={`size-3.5 ${failed ? 'text-red-400' : warning ? 'text-amber-300' : 'text-blue-400'}`} /></span>
          <div className={`min-w-0 flex-1 rounded-xl border px-3 py-2.5 ${failed ? 'border-red-500/20 bg-red-500/5' : warning ? 'border-amber-500/20 bg-amber-500/5' : 'border-white/10 bg-white/[.025]'}`}>
            <div className="mb-1 flex items-center gap-2 text-[10px] capitalize text-white/40">
              <span>{event.stage || 'Deployment agent'}</span>
              {running && event.status === 'running' && event === messages.at(-1) && <Loader2 className="size-2.5 animate-spin" />}
              {event.type === 'tool' && event.status === 'complete' && <Check className="size-2.5 text-emerald-400" />}
            </div>
            <p className={`whitespace-pre-wrap break-words text-[11.5px] leading-relaxed ${failed ? 'text-red-200' : 'text-white/80'}`}>{event.message}</p>
          </div>
        </article>
      })}
      {running && <p className="flex items-center gap-2 pl-10 text-[11px] text-white/40"><Loader2 className="size-3 animate-spin" />Agent is working…</p>}
    </div>
  </section>
}

export function DeploymentQuestion({ question, runId, onAnswered }) {
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { setAnswer(''); setError('') }, [runId, question?.id])
  async function submit() {
    setBusy(true); setError('')
    try {
      await api.deploy(`/runs/${runId}/answer`, { question_id: question.id, answer })
      setAnswer(''); onAnswered?.()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  if (!question) return null
  return <section aria-label="Deployment question" className="rounded-2xl border border-blue-500/20 bg-[#121622] p-4">
    <p className="mb-3 text-[12px] font-semibold text-white">Deployment needs a choice</p>
      <label className="text-[12px] text-white">{question.text}
        <input aria-label="Deployment question answer" value={answer} onChange={e => setAnswer(e.target.value)} className="mt-2 block w-full rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-white" />
      </label>
      <p className="mt-1 text-[10px] text-white/50">Save credentials in Settings or the selected provider. Enter only a choice or confirmation here.</p>
      <div className="mt-2 flex flex-wrap gap-2">{(question.choices || []).map(choice => <button key={choice} onClick={() => setAnswer(choice)} className="rounded border border-white/20 px-2 py-1 text-[11px] text-white/80">{choice}</button>)}</div>
      <button disabled={busy || !answer.trim()} onClick={submit} className="mt-2 rounded-lg bg-blue-600 px-3 py-1.5 text-[11px] text-white disabled:opacity-40">{busy ? 'Sending…' : 'Answer and continue'}</button>
      {error && <p className="mt-2 text-[11px] text-red-300">{error}</p>}
  </section>
}
