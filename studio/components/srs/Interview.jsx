'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft, ArrowRight, FileText, Loader2, SkipForward,
  Sparkles,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { TYPE_ANOTHER } from '@/lib/srs-constants'
import { useAttachments } from '@/lib/use-attachments'
import { AttachButtons, AttachList } from './Attachments'
import { Button, TextArea } from '../ui'
import { cn } from '@/lib/utils'
import InterviewIntegrations from './InterviewIntegrations'

export default function Interview({ projectId, onDone, onCancel }) {
  const addLog = useStore(s => s.addLog)
  const [state, setState] = useState({ question: null, transcript: [], answers: [], done: false })
  const [phase, setPhase] = useState('loading')
  const [typing, setTyping] = useState(false)
  const [text, setText] = useState('')
  const [picked, setPicked] = useState([])
  const [error, setError] = useState('')
  const composer = useRef(null)
  const tail = useRef(null)
  const attach = useAttachments()
  const [integrations, setIntegrations] = useState(null)

  async function refresh() {
    try {
      const setup = await api.integrations(projectId)
      if (!setup.confirmed) { setIntegrations(setup.questions); setPhase('integrations'); return }
      setIntegrations(null)
      const next = await api.srs(`/projects/${projectId}/interview`)
      setState(next)
      setTyping(false)
      setText('')
      if (next.done || !next.question) return onDone?.(next)
      setPhase('asking')
    } catch (e) {
      if (/404|not found/i.test(e.message || '')) return onCancel?.()
      setError(e.message)
      setPhase('error')
    }
  }

  useEffect(() => { refresh() }, [projectId])
  useEffect(() => { tail.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [state.question?.id, state.answers?.length])
  useEffect(() => { if (typing) composer.current?.focus() }, [typing])

  const q = state.question
  const options = q?.options?.length ? q.options : (q?.suggested_options || []).map(o => ({ label: o, value: o }))
  const multi = /multi/.test(q?.answer_type || '')
  const prefill = q?.prefill || []
  const recommended = q?.recommended

  useEffect(() => {
    setPicked(multi ? prefill.map(String) : [])
    setText(!options.length && prefill.length ? String(prefill[0]) : '')
  }, [q?.id])

  async function answer(payload) {
    setPhase('sending')
    setError('')
    try {
      let attachments = []
      if (attach.items.length) {
        const uploaded = await attach.upload(projectId)
        attachments = uploaded.ids || []
        const said = payload.value != null || (payload.selected || []).length || String(payload.text || '').trim()
        if (!attachments.length && !said) {
          setError('That attachment could not be read. Try it again, or answer in text.')
          setPhase('asking')
          return
        }
      }
      await api.srs(`/projects/${projectId}/interview/answer`, attachments.length ? { ...payload, attachments } : payload)
      attach.reset()
      await refresh()
    } catch (e) {
      setError(e.message)
      addLog('WARN', `The SRS could not record that answer — ${e.message}`)
      setPhase('asking')
    }
  }

  const history = useMemo(() => {
    const byId = Object.fromEntries((state.answers || []).map(a => [a.question_id, a]))
    return (state.transcript || []).filter(row => byId[row.id]).map(row => ({ row, answer: byId[row.id] }))
  }, [state.transcript, state.answers])
  const answered = (state.answers || []).length
  const total = Math.max((state.transcript || []).length, answered + 1, 8)
  if (integrations) return <InterviewIntegrations key={projectId} projectId={projectId} questions={integrations} onDone={refresh} />

  if (phase === 'loading') return <div className="grid min-h-0 flex-1 place-items-center"><Waiting>Preparing your interview…</Waiting></div>
  if (phase === 'error' && !q) return (
    <div className="grid min-h-0 flex-1 place-items-center p-8">
      <div className="max-w-[460px] rounded-[28px] bg-white/75 p-6 shadow-xl ring-1 ring-line dark:bg-white/[.04]">
        <p className="text-[13px] text-ink">The interview could not start.</p>
        <p className="mt-2 text-[12px] text-muted">{error}</p>
        <Button variant="outline" className="mt-4" onClick={onCancel}>Back</Button>
      </div>
    </div>
  )

  return (
    <div className="srs-messenger flex min-h-0 flex-1 flex-col bg-[radial-gradient(circle_at_50%_0%,#152e68_0%,#0c152a_40%,#080c16_100%)] text-white">
      <header className="flex shrink-0 items-center gap-3 border-b border-white/10 px-7 py-4 backdrop-blur-md">
        <button onClick={onCancel} className="grid size-9 place-items-center rounded-xl border border-white/10 bg-white/[.04] text-white/70 transition hover:bg-white/[.08] hover:text-white">
          <ArrowLeft className="size-4" />
        </button>
        <div>
          <p className="font-display text-[14.5px] font-bold tracking-tight text-white">Plan conversation</p>
          <p className="text-[11px] text-white/50">Question {answered + 1} of about {total}</p>
        </div>
        <span className="flex-1" />
        <div className="hidden items-center gap-1.5 sm:flex">
          {Array.from({ length: Math.min(total, 10) }).map((_, i) => (
            <span key={i} className={cn('h-1.5 rounded-full transition-all', i < answered ? 'w-5 bg-emerald-400' : i === answered ? 'w-8 bg-blue-500' : 'w-3 bg-white/15')} />
          ))}
        </div>
        <button onClick={() => onDone?.(state)} className="ml-2 inline-flex h-9 items-center gap-2 rounded-xl border border-white/10 bg-white/[.05] px-3.5 text-[11.5px] font-semibold text-white/90 transition hover:bg-white/[.1] hover:text-white">
          <SkipForward className="size-3.5 text-blue-400" /> Draft plan now
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
        <div className="mx-auto max-w-[820px] py-4">
          <div className="mb-7 flex justify-center">
            <span className="rounded-full border border-white/10 bg-white/[.04] px-4 py-1 text-[11px] font-medium text-white/60 shadow-sm backdrop-blur-md">
              AgentForge asks only what it needs to build the app correctly.
            </span>
          </div>

          {history.map(({ row, answer: a }, i) => (
            <div key={row.id || i} className="mb-7">
              <Message side="left" label="AgentForge">{row.question}</Message>
              <Message side="right" label="You">{said(a)}</Message>
            </div>
          ))}

          {q && (
            <div className="mb-5">
              <Message side="left" label="AgentForge" current>
                <span className="block text-[16px] font-bold leading-[1.45] text-white">{q.question}</span>
                {q.why_needed && <span className="mt-2.5 block text-[12px] leading-relaxed text-white/60">{q.why_needed}</span>}
                {q.prefill_note && <span className="mt-2 block text-[11.5px] font-medium text-blue-400">You previously said “{q.prefill_note}”.</span>}
              </Message>
            </div>
          )}

          {!typing && options.length > 0 && (
            <div className="ml-11 max-w-[680px]">
              <div className="flex flex-wrap gap-2.5">
                {options.map((o, i) => {
                  const value = o.value ?? o.label
                  const known = prefill.map(String).includes(String(value))
                  const chosen = picked.includes(value) || (!multi && known)
                  const suggested = o.suggested || value === recommended
                  return (
                    <button key={`${value}-${i}`} disabled={phase === 'sending'} onClick={() => {
                      if (value === TYPE_ANOTHER) return setTyping(true)
                      if (multi) return setPicked(p => p.includes(value) ? p.filter(x => x !== value) : [...p, value])
                      answer({ key: q.id, value, selected: [String(value)] })
                    }} className={cn('rounded-full px-4 py-2 text-[12px] font-medium transition-all shadow-sm disabled:opacity-45',
                      chosen
                        ? 'bg-blue-600 text-white border border-blue-400 shadow-lg shadow-blue-500/25'
                        : 'border border-white/10 bg-white/[.05] text-white/80 hover:bg-white/[.1] hover:text-white hover:border-white/20'
                    )}>
                      {o.label ?? String(value)}
                      {(suggested || known) && <span className={cn('ml-2 text-[9px] font-semibold uppercase tracking-wider', chosen ? 'text-white/80' : 'text-white/40')}>{known ? 'from brief' : 'suggested'}</span>}
                    </button>
                  )
                })}
              </div>
              <div className="mt-4 flex items-center gap-3">
                {multi && <Button variant="solid" disabled={!picked.length || phase === 'sending'} onClick={() => answer({ key: q.id, value: picked, selected: picked.map(String) })}>Continue with {picked.length}</Button>}
                <button onClick={() => setTyping(true)} className="text-[11.5px] font-medium text-white/50 hover:text-white transition">Write a different answer</button>
              </div>
            </div>
          )}

          {(typing || options.length === 0) && (
            <div className="ml-auto mt-4 max-w-[690px] rounded-2xl border border-white/15 bg-[#121622]/95 p-4 shadow-2xl backdrop-blur-2xl transition-all focus-within:border-blue-500/50 focus-within:shadow-[0_15px_40px_rgba(37,99,235,.15)]">
              <TextArea ref={composer} value={text} rows={3} placeholder="Type your answer…" onChange={e => setText(e.target.value)} onKeyDown={e => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && text.trim()) answer({ key: q.id, value: text.trim(), text: text.trim() })
              }} className="w-full resize-none bg-transparent px-1 py-1 text-[13.5px] leading-relaxed text-white outline-none placeholder:text-white/40 caret-blue-400" />
              <AttachList attach={attach} className="mx-1 mb-2" />
              <div className="flex items-center gap-2 border-t border-white/10 px-1 pt-3">
                <AttachButtons attach={attach} disabled={phase === 'sending'} />
                <span className="flex-1" />
                {options.length > 0 && <button onClick={() => { setTyping(false); setText('') }} className="rounded-xl px-3 py-1.5 text-[11px] font-medium text-white/60 hover:bg-white/[.06] hover:text-white transition">Options</button>}
                <button disabled={phase === 'sending' || (!text.trim() && !attach.items.length)} onClick={() => answer({ key: q.id, value: text.trim() || null, text: text.trim() })} className="inline-flex h-9 items-center gap-2 rounded-xl bg-blue-600 px-4 text-[12px] font-semibold text-white shadow-lg shadow-blue-500/25 transition hover:bg-blue-500 disabled:opacity-40">
                  {phase === 'sending' ? <Loader2 className="size-3.5 animate-spin" /> : <ArrowRight className="size-3.5" />} Send
                </button>
              </div>
            </div>
          )}

          {error && <p className="ml-auto mt-3 max-w-[690px] rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-[11.5px] text-red-300">{error}</p>}
          <div ref={tail} />
        </div>
      </div>

      <footer className="shrink-0 border-t border-white/10 bg-black/30 px-6 py-3 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[820px] items-center gap-2 text-[11px] text-white/60">
          <Sparkles className="size-3.5 text-blue-400" /> Your answers become the implementation contract. You can review the full plan before anything is built.
          <span className="flex-1" />
          <button disabled={answered === 0} onClick={() => onDone?.(state)} className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[.06] px-3.5 py-1.5 font-medium text-white/90 transition hover:bg-white/[.12] disabled:opacity-40">
            <FileText className="size-3 text-amber-400" /> Review plan
          </button>
        </div>
      </footer>
    </div>
  )
}

function Message({ side, label, current, children }) {
  const right = side === 'right'
  return (
    <div className={cn('flex items-end gap-3', right && 'justify-end')}>
      {!right && (
        <span className="grid size-8 shrink-0 place-items-center rounded-xl bg-accent/20 border border-accent/30 text-[11px] font-bold text-accent shadow-sm">
          AF
        </span>
      )}
      <div className={cn('max-w-[75%]', right && 'text-right')}>
        <div className="mb-1.5 px-1 text-[9.5px] font-bold uppercase tracking-[.14em] text-white/40">{label}</div>
        <div className={cn('inline-block rounded-2xl px-4 py-3.5 text-left text-[13px] leading-relaxed shadow-lg',
          right
            ? 'rounded-tr-sm bg-accent/20 border border-accent/30 text-white font-medium'
            : current
              ? 'rounded-tl-sm bg-[#121622]/95 border border-blue-500/30 ring-1 ring-blue-500/20 text-white'
              : 'rounded-tl-sm bg-[#121622]/80 border border-white/10 text-white/90'
        )}>
          {children}
        </div>
      </div>
    </div>
  )
}

function said(a) {
  if (!a) return ''
  const v = Array.isArray(a.value) ? a.value.join(', ') : a.value
  return v != null && String(v).trim() ? String(v) : (a.raw_text || 'Answered')
}

export function Waiting({ children, sub }) {
  return (
    <div className="flex items-center gap-3.5 rounded-2xl border border-white/10 bg-[#121622]/90 px-7 py-6 shadow-2xl backdrop-blur-2xl">
      <Loader2 className="size-5 shrink-0 animate-spin text-blue-400" />
      <div><p className="text-[13.5px] font-semibold text-white">{children}</p>{sub && <p className="mt-1 text-[11px] text-white/50">{sub}</p>}</div>
    </div>
  )
}
