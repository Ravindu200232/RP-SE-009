'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowUp, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { TYPE_ANOTHER } from '@/lib/srs-constants'
import { useAttachments } from '@/lib/use-attachments'
import { AttachButtons, AttachList } from './Attachments'
import { Button, Panel } from '../ui'
import { cn } from '@/lib/utils'

export default function Interview({ projectId, onDone, onCancel }) {
  const addLog = useStore(s => s.addLog)
  const [state, setState] = useState({ question: null, transcript: [], done: false })
  const [phase, setPhase] = useState('loading')
  const [typing, setTyping] = useState(false)
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const box = useRef(null)

  async function refresh() {
    try {
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

  useEffect(() => { refresh()  }, [projectId])
  useEffect(() => { if (typing) box.current?.focus() }, [typing])

  async function answer(payload) {
    setPhase('sending')
    setError('')
    try {
      // Whatever is attached belongs to the question on screen, so it goes up
      // before the answer does and rides along as source ids — that is the
      // shape `InterviewAnswer.attachments` takes. An answer that is nothing
      // but a photo of a form is a valid answer; the interview agent reads the
      // extracted text as the reply when nothing was picked or typed.
      let attachments = []
      if (attach.items.length) {
        const { ids, failed } = await attach.upload(projectId)
        attachments = ids

        // If the file WAS the answer and none of it arrived, posting anyway
        // records an empty answer and moves the interview on for good — the
        // question is never asked again. Stay here instead.
        const said = payload.value != null
          || (payload.selected || []).length > 0
          || (payload.text || '').trim().length > 0
        if (!attachments.length && !said) {
          setError(failed === 1
            ? 'That file could not be read — try again, or type the answer instead.'
            : 'None of those files could be read — try again, or type the answer instead.')
          setPhase('asking')
          return
        }
      }
      await api.srs(`/projects/${projectId}/interview/answer`,
                    attachments.length ? { ...payload, attachments } : payload)
      attach.reset()
      await refresh()
    } catch (e) {
      setError(e.message)
      addLog('WARN', `⚠ The SRS could not record that answer — ${e.message}`)
      setPhase('asking')
    }
  }

  const q = state.question
  const options = (q?.options?.length ? q.options
    : (q?.suggested_options || []).map(o => ({ label: o, value: o })))
  const multi = /multi/.test(q?.answer_type || '')

  const prefill = q?.prefill || []
  const recommended = q?.recommended
  const [picked, setPicked] = useState([])
  const attach = useAttachments()

  useEffect(() => { setPicked(multi ? prefill.map(String) : []) },
 [q?.id])

  if (phase === 'loading') {
    return <Waiting>Reading the first question…</Waiting>
  }
  if (phase === 'error' && !q) {
    return (
      <Panel className="p-5 text-center">
        <p className="text-[12.5px] text-bad">The interview could not start — {error}</p>
        <Button variant="outline" className="mt-3" onClick={onCancel}>Back</Button>
      </Panel>
    )
  }

  const answered = (state.answers || []).length
  const total = Math.max((state.transcript || []).length, answered + 1)

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <button onClick={onCancel}
                className="flex items-center gap-1 text-[11px] text-muted2 hover:text-ink">
          <ArrowLeft className="size-3" /> Back
        </button>
        <span className="flex-1" />
        <span className="font-mono text-[10px] text-muted2">
          question {answered + 1} · {answered} answered
        </span>
      </div>

      <div className="mb-5 h-[2px] w-full overflow-hidden rounded-full bg-line">
        <div className="h-full rounded-full bg-accent transition-[width] duration-500"
             style={{ width: `${Math.min(92, (answered / Math.max(total, 8)) * 100)}%` }} />
      </div>

      <Panel className="p-5">
        <p className="font-display text-[16px] font-bold leading-snug text-ink">
          {q.question}
        </p>
        {q.why_needed && (
          <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
            {q.why_needed}
          </p>
        )}

        {q.prefill_note && (
          <p className="mt-3 border-l-2 border-accent/40 pl-2.5 text-[11.5px]
                        leading-relaxed text-muted">
            You said: “{q.prefill_note}”
          </p>
        )}

        {!typing && options.length > 0 && (
          <div className="mt-4 space-y-1.5">
            {options.map((o, i) => {
              const value = o.value ?? o.label
              const known = prefill.map(String).includes(String(value))
              const chosen = picked.includes(value) || (!multi && known)
              const flagged = o.suggested || value === recommended
              return (
                <button key={`${value}-${i}`} disabled={phase === 'sending'}
                        onClick={() => {

                          if (value === TYPE_ANOTHER) return setTyping(true)
                          if (multi) {
                            setPicked(p => p.includes(value)
                              ? p.filter(x => x !== value) : [...p, value])
                            return
                          }
                          answer({ key: q.id, value, selected: [String(value)] })
                        }}
                        className={cn(
                          'flex w-full items-start gap-2.5 rounded-ctl border px-3 py-2.5',
                          'text-left text-[12.5px] transition-colors disabled:opacity-50',
                          chosen
                            ? 'border-accent/50 bg-accent/10 text-ink'
                            : 'border-line bg-panel2 text-ink hover:border-accent/40')}>
                    <span className={cn('mt-[3px] size-3 shrink-0 rounded-full border',
                      chosen ? 'border-accent bg-accent' : 'border-muted2')} />
                    <span>
                      {o.label ?? String(value)}
                      {flagged && !known && (
                        <span className="ml-1.5 rounded-full border border-accent/40
                                         px-1.5 py-px align-middle text-[9px]
                                         font-medium text-accent">
                          suggested
                        </span>
                      )}
                      {known && (
                        <span className="ml-1.5 rounded-full border border-ok/40
                                         px-1.5 py-px align-middle text-[9px]
                                         font-medium text-ok">
                          from what you said
                        </span>
                      )}
                      {o.hint && (
                        <span className="mt-0.5 block text-[11px] text-muted">{o.hint}</span>
                      )}
                    </span>
                  </button>
                )
            })}
            {multi && (
              <Button variant="solid" className="mt-2 w-full justify-center"
                      disabled={!picked.length || phase === 'sending'}
                      onClick={() => answer({
                        key: q.id, value: picked,
                        selected: picked.map(String),
                      })}>
                Continue with {picked.length} selected
              </Button>
            )}
            <button onClick={() => setTyping(true)}
                    className="pt-1 text-[11px] text-muted2 hover:text-ink">
              None of these — let me type it
            </button>
          </div>
        )}

        {(typing || options.length === 0) && (
          <div className="mt-4">
            <textarea ref={box} value={text} rows={3}
                      placeholder="Type your answer…"
                      onChange={e => setText(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                          if (text.trim()) answer({ key: q.id, value: text.trim(),
                                                    text: text.trim() })
                        }
                      }}
                      className="w-full resize-none rounded-ctl border border-line
                                 bg-panel2 p-2.5 text-[12.5px] leading-relaxed text-ink
                                 outline-none placeholder:text-muted2
                                 focus:border-accent/40" />
            <div className="mt-2 flex items-center gap-2">
              {options.length > 0 && (
                <button onClick={() => { setTyping(false); setText('') }}
                        className="text-[11px] text-muted2 hover:text-ink">
                  Back to the options
                </button>
              )}
              <span className="flex-1" />
              <Button variant="solid" size="icon"
                      disabled={!text.trim() || phase === 'sending'}
                      onClick={() => answer({ key: q.id, value: text.trim(),
                                              text: text.trim() })}>
                <ArrowUp className="size-3.5" />
              </Button>
            </div>
          </div>
        )}

        <div className="mt-4 border-t border-line pt-3">
          <AttachList attach={attach} className="mb-2" />
          <div className="flex flex-wrap items-center gap-1.5">
            <AttachButtons attach={attach} disabled={phase === 'sending'}
                           label="Attach" />
            <span className="min-w-0 flex-1 text-[10.5px] leading-snug text-muted2">
              {attach.items.length > 0 && options.length > 0
                ? 'Sent with whichever option you choose.'
                : 'Easier to show than to say — a price list, a form you use today, or just talk it through.'}
            </span>
            {/* A file can *be* the answer only where the answer is free text.
                On a question with options it is context that travels with the
                choice: `record` promotes attachment text to the value
                when nothing was picked, and for `app_type` the value is then
                forced through `guess_app_type`, which returns "saas" at zero
                confidence for anything it does not recognise. A photo of an
                order slip would silently become "SaaS Platform", and that one
                answer drives every question after it. */}
            {attach.items.length > 0 && options.length === 0 && !text.trim() && (
              <Button variant="solid" size="sm" disabled={phase === 'sending'}
                      onClick={() => answer({ key: q.id, value: null })}>
                Send {attach.items.length === 1 ? 'this' : `these ${attach.items.length}`}
              </Button>
            )}
          </div>
        </div>

        {phase === 'sending' && (
          <p className="mt-3 flex items-center gap-1.5 text-[11px] text-muted">
            <Loader2 className="size-3 animate-spin" />
            {attach.busy ? 'Reading what you attached…' : 'Thinking about what to ask next…'}
          </p>
        )}
        {error && phase !== 'sending' && (
          <p className="mt-3 text-[11px] text-bad">{error}</p>
        )}
      </Panel>

      {answered > 0 && (
        <p className="mt-3 text-center text-[10.5px] text-muted2">
          Everything you have answered is saved — closing this does not lose it.
        </p>
      )}
    </div>
  )
}

export function Waiting({ children, sub }) {
  return (
    <Panel className="p-8 text-center">
      <Loader2 className="mx-auto mb-3 size-5 animate-spin text-accent" />
      <p className="text-[12.5px] text-ink">{children}</p>
      {sub && <p className="mx-auto mt-1.5 max-w-[400px] text-[11.5px] leading-relaxed text-muted">{sub}</p>}
    </Panel>
  )
}
