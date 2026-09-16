'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowLeft, ArrowRight, Eye, EyeOff, FileText, KeyRound, Loader2, Lock, SkipForward,
  Sparkles,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { TYPE_ANOTHER } from '@/lib/srs-constants'
import { useAttachments } from '@/lib/use-attachments'
import { AttachButtons, AttachList } from './Attachments'
import { Button, TextArea } from '../ui'
import { cn } from '@/lib/utils'

export default function Interview({ projectId, onDone, onCancel }) {
  const addLog = useStore(s => s.addLog)
  const [state, setState] = useState({ question: null, transcript: [], answers: [], done: false })
  const [phase, setPhase] = useState('loading')
  const [typing, setTyping] = useState(false)
  const [text, setText] = useState('')
  const [picked, setPicked] = useState([])
  const [error, setError] = useState('')
  const [showSecret, setShowSecret] = useState(false)
  const composer = useRef(null)
  const tail = useRef(null)
  const attach = useAttachments()

  // Feature-Triggered Integrations State
  const [integSetup, setIntegSetup] = useState(null)
  const [integStep, setIntegStep] = useState(null) // { kind: 'payments' | 'notifications' | 'image-uploads', stage: 'choice' | 'field' }
  const [integAnswers, setIntegAnswers] = useState({})
  const [integHistory, setIntegHistory] = useState([])
  const [integChoice, setIntegChoice] = useState(null)
  const [integFieldIndex, setIntegFieldIndex] = useState(0)

  async function saveIntegrationsSnapshot(currentMap) {
    const payload = [
      { id: 'notifications', choice: currentMap?.notifications?.choice || 'log-only', values: currentMap?.notifications?.values || {} },
      { id: 'payments', choice: currentMap?.payments?.choice || 'none', values: currentMap?.payments?.values || {} },
      { id: 'image-uploads', choice: currentMap?.['image-uploads']?.choice || 'local', values: currentMap?.['image-uploads']?.values || {} },
    ]
    try {
      await api.saveIntegrations(projectId, payload)
    } catch (e) {
      console.warn('saveIntegrations snapshot error:', e.message)
    }
  }

  async function refresh() {
    try {
      const setup = await api.integrations(projectId)
      setIntegSetup(setup.questions || [])
      if (setup.confirmed && setup.answers?.length && Object.keys(integAnswers).length === 0) {
        const byId = {}
        setup.answers.forEach(a => { byId[a.id] = { choice: a.provider, values: {} } })
        setIntegAnswers(byId)
      }
      const next = await api.srs(`/projects/${projectId}/interview`)
      setState(next)
      setTyping(false)
      setText('')
      if (next.done || !next.question) {
        await saveIntegrationsSnapshot(integAnswers)
        return onDone?.(next)
      }
      setPhase('asking')
    } catch (e) {
      if (/404|not found/i.test(e.message || '')) return onCancel?.()
      setError(e.message)
      setPhase('error')
    }
  }

  useEffect(() => { refresh() }, [projectId])
  useEffect(() => { tail.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }) }, [state.question?.id, state.answers?.length, integHistory.length, integStep?.stage, integFieldIndex])
  useEffect(() => { if (typing) composer.current?.focus() }, [typing])

  const isInteg = Boolean(integStep && integSetup)

  const currentIntegQuestion = useMemo(() => {
    if (!isInteg) return null
    const qDef = (integSetup || []).find(q => q.id === integStep.kind)
    if (!qDef) return null

    if (integStep.stage === 'choice') {
      const choices = (qDef.choices || []).filter(c => c.id !== 'none')
      const titles = {
        payments: 'Which payment provider or gateway would you like to use for online payments?',
        notifications: 'Which notification service would you like to use for automated messages?',
        'image-uploads': 'Where should uploaded pictures and files be kept and served from?'
      }
      const whys = {
        payments: 'Configure the payment processor for transactions and checkout.',
        notifications: 'Configure email delivery or SMS for receipts and alerts.',
        'image-uploads': 'Configure file storage and media delivery.'
      }
      const optionsList = choices.map(c => ({
        label: c.label,
        value: c.id,
        hint: c.hint,
      }))

      if (integStep.kind === 'payments') {
        optionsList.push({ label: 'Manual / Cash only (no online gateway)', value: 'none', hint: 'No card processor or gateway needed' })
      } else if (integStep.kind === 'notifications') {
        optionsList.push({ label: 'Test only — log messages without sending', value: 'log-only', hint: 'No live provider account needed' })
      } else if (integStep.kind === 'image-uploads') {
        optionsList.push({ label: 'No picture or file uploads needed', value: 'none', hint: 'Text-only app' })
      }

      return {
        id: `${integStep.kind}_choice`,
        question: titles[integStep.kind] || qDef.question || qDef.purpose,
        why_needed: whys[integStep.kind],
        options: optionsList,
        isSecret: false,
        isField: false,
      }
    }

    if (integStep.stage === 'field' && integChoice) {
      const fields = [...(qDef.fields || []), ...(integChoice.fields || [])]
      const field = fields[integFieldIndex]
      if (!field) return null
      return {
        id: `${integStep.kind}_field_${field.key}`,
        question: `Please enter your ${field.label} for ${integChoice.label}.`,
        why_needed: field.hint || `Needed to configure ${integChoice.label}. Credentials are saved to .env.local only.`,
        hint: field.hint,
        example: field.example,
        fieldKey: field.key,
        fieldLabel: field.label,
        isSecret: Boolean(field.secret),
        required: field.required !== false,
        isField: true,
        options: [
          { label: field.required === false ? 'Skip (Optional)' : 'Skip / Configure later in .env.local', value: '__skip__' }
        ]
      }
    }
    return null
  }, [isInteg, integStep, integSetup, integChoice, integFieldIndex])

  const q = isInteg ? currentIntegQuestion : state.question
  const options = isInteg
    ? (q?.options || [])
    : (q?.options?.length ? q.options : (q?.suggested_options || []).map(o => ({ label: o, value: o })))
  const multi = !isInteg && /multi/.test(q?.answer_type || '')
  const prefill = isInteg ? [] : (q?.prefill || [])
  const recommended = isInteg ? null : q?.recommended

  useEffect(() => {
    setPicked(multi ? prefill.map(String) : [])
    if (!isInteg) {
      setText(!options.length && prefill.length ? String(prefill[0]) : '')
    } else {
      setText('')
      setShowSecret(false)
    }
  }, [q?.id, isInteg])

  async function handleIntegAnswer(rawVal) {
    const currentQ = currentIntegQuestion
    if (!currentQ || !integStep) return
    const qDef = (integSetup || []).find(item => item.id === integStep.kind)

    if (integStep.stage === 'choice') {
      const chosen = (qDef?.choices || []).find(c => c.id === rawVal || c.label === rawVal) || { id: rawVal, label: rawVal }
      setIntegHistory(h => [...h, { question: currentQ.question, answer: chosen.label || chosen.id }])

      if (chosen.id === 'none' || chosen.id === 'log-only' || chosen.id === 'local') {
        const updated = { ...integAnswers, [integStep.kind]: { choice: chosen.id, values: {} } }
        setIntegAnswers(updated)
        setIntegStep(null)
        setIntegChoice(null)
        setIntegFieldIndex(0)
        setText('')
        await saveIntegrationsSnapshot(updated)
        await refresh()
        return
      }

      setIntegChoice(chosen)
      const fields = [...(qDef?.fields || []), ...(chosen.fields || [])]
      if (!fields.length) {
        const updated = { ...integAnswers, [integStep.kind]: { choice: chosen.id, values: {} } }
        setIntegAnswers(updated)
        setIntegStep(null)
        setIntegChoice(null)
        setIntegFieldIndex(0)
        setText('')
        await saveIntegrationsSnapshot(updated)
        await refresh()
      } else {
        setIntegStep({ kind: integStep.kind, stage: 'field' })
        setIntegFieldIndex(0)
        setText('')
      }
      return
    }

    if (integStep.stage === 'field' && integChoice) {
      const fields = [...(qDef?.fields || []), ...(integChoice.fields || [])]
      const currentField = fields[integFieldIndex]
      const isSkip = rawVal === '__skip__' || (!rawVal && rawVal !== 0) || String(rawVal).trim().toLowerCase() === 'skip'
      const entered = isSkip ? '' : String(rawVal).trim()
      const displayAnswer = isSkip
        ? 'Skipped (will configure later in .env.local)'
        : (currentField?.secret ? '••••••••••••' : entered)

      setIntegHistory(h => [...h, { question: currentQ.question, answer: displayAnswer }])

      const priorValues = integAnswers[integStep.kind]?.values || {}
      const updatedValues = currentField?.key ? { ...priorValues, [currentField.key]: entered } : priorValues
      const updatedKindObj = { choice: integChoice.id, values: updatedValues }
      const updatedAnswers = { ...integAnswers, [integStep.kind]: updatedKindObj }
      setIntegAnswers(updatedAnswers)

      setText('')
      setShowSecret(false)

      if (integFieldIndex + 1 < fields.length) {
        setIntegFieldIndex(i => i + 1)
      } else {
        setIntegStep(null)
        setIntegChoice(null)
        setIntegFieldIndex(0)
        await saveIntegrationsSnapshot(updatedAnswers)
        await refresh()
      }
    }
  }

  async function draftPlanNow() {
    await saveIntegrationsSnapshot(integAnswers)
    onDone?.(state)
  }

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

      // Inspect whether this question or the user's answer triggers an integration!
      const currentVal = payload.value != null ? payload.value : (payload.selected || payload.text || '')
      const valStr = Array.isArray(currentVal) ? currentVal.join(' ') : String(currentVal)
      const qContext = `${q?.topic || ''} ${q?.id || ''} ${q?.question || ''}`

      // 1. Payments Trigger
      const paymentTopic = /pos_payments|store_payments|saas_plans/.test(q?.topic || '') ||
        /\b(payment|payments|checkout|billing|credit card|card payment|payhere|stripe|take money)\b/i.test(qContext)
      const paymentAnswer = /\b(card|online|stripe|payhere|checkout|gateway|payment|pay)\b/i.test(valStr)
      const isPurelyNoPayment = /^(cash|cod|none|no|false)$/i.test(valStr.trim())

      if (!integAnswers.payments && (paymentTopic || paymentAnswer)) {
        if (isPurelyNoPayment) {
          const updated = { ...integAnswers, payments: { choice: 'none', values: {} } }
          setIntegAnswers(updated)
          await saveIntegrationsSnapshot(updated)
        } else {
          const qDef = (integSetup || []).find(item => item.id === 'payments')
          const matchedChoice = (qDef?.choices || []).find(c => c.id !== 'none' && (valStr.toLowerCase().includes(c.id.toLowerCase()) || valStr.toLowerCase().includes(c.label.toLowerCase())))
          if (matchedChoice) {
            setIntegChoice(matchedChoice)
            const fields = [...(qDef.fields || []), ...(matchedChoice.fields || [])]
            if (fields.length) {
              setIntegStep({ kind: 'payments', stage: 'field' })
              setIntegFieldIndex(0)
            } else {
              const updated = { ...integAnswers, payments: { choice: matchedChoice.id, values: {} } }
              setIntegAnswers(updated)
              await saveIntegrationsSnapshot(updated)
              await refresh()
              return
            }
          } else {
            setIntegStep({ kind: 'payments', stage: 'choice' })
          }
          setPhase('asking')
          setText('')
          return
        }
      }

      // 2. Notifications Trigger
      const notifTopic = /pos_receipt/.test(q?.topic || '') ||
        /\b(notification|notifications|email receipt|sms alert|send email)\b/i.test(qContext)
      const notifAnswer = /\b(email|sms|notification|notifications|alert|text message)\b/i.test(valStr)
      const isPurelyNoNotif = /^(none|no|print|false)$/i.test(valStr.trim())

      if (!integAnswers.notifications && (notifTopic || notifAnswer)) {
        if (isPurelyNoNotif) {
          const updated = { ...integAnswers, notifications: { choice: 'log-only', values: {} } }
          setIntegAnswers(updated)
          await saveIntegrationsSnapshot(updated)
        } else {
          setIntegStep({ kind: 'notifications', stage: 'choice' })
          setPhase('asking')
          setText('')
          return
        }
      }

      // 3. Image/File Uploads Trigger
      const uploadTopic = /images|image_kinds/.test(q?.topic || '') ||
        /\b(upload|uploads|pictures?|images?|photos?|avatar|document)\b/i.test(qContext)
      const uploadAnswer = /\b(upload|uploads|photo|photos|image|images|avatar|gallery)\b/i.test(valStr)
      const isPurelyNoUpload = /^(none|no|false)$/i.test(valStr.trim())

      if (!integAnswers['image-uploads'] && (uploadTopic || uploadAnswer)) {
        if (isPurelyNoUpload) {
          const updated = { ...integAnswers, 'image-uploads': { choice: 'none', values: {} } }
          setIntegAnswers(updated)
          await saveIntegrationsSnapshot(updated)
        } else {
          setIntegStep({ kind: 'image-uploads', stage: 'choice' })
          setPhase('asking')
          setText('')
          return
        }
      }

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
          <p className="text-[11px] text-white/50">
            {isInteg
              ? `Question ${answered + 1} · ${integStep.kind === 'payments' ? 'Payment Gateway' : integStep.kind === 'notifications' ? 'Notifications' : 'Media Storage'}`
              : `Question ${answered + 1} of about ${total}`}
          </p>
        </div>
        <span className="flex-1" />
        <div className="hidden items-center gap-1.5 sm:flex">
          {Array.from({ length: Math.min(total, 10) }).map((_, i) => (
            <span key={i} className={cn('h-1.5 rounded-full transition-all',
              i < answered
                ? 'w-5 bg-emerald-400'
                : i === answered
                  ? 'w-8 bg-blue-500'
                  : 'w-3 bg-white/15'
            )} />
          ))}
        </div>
        <button onClick={draftPlanNow} className="ml-2 inline-flex h-9 items-center gap-2 rounded-xl border border-white/10 bg-white/[.05] px-3.5 text-[11.5px] font-semibold text-white/90 transition hover:bg-white/[.1] hover:text-white">
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

          {integHistory.map((item, idx) => (
            <div key={`integ-${idx}`} className="mb-7">
              <Message side="left" label="AgentForge">{item.question}</Message>
              <Message side="right" label="You">{item.answer}</Message>
            </div>
          ))}

          {q && (
            <div className="mb-5">
              <Message side="left" label="AgentForge" current>
                <span className="block text-[16px] font-bold leading-[1.45] text-white">{q.question}</span>
                {q.why_needed && <span className="mt-2.5 block text-[12px] leading-relaxed text-white/60">{q.why_needed}</span>}
                {q.hint && !q.why_needed?.includes(q.hint) && <span className="mt-2 block text-[11.5px] font-medium text-amber-300/85">{q.hint}</span>}
                {q.prefill_note && <span className="mt-2 block text-[11.5px] font-medium text-blue-400">You previously said “{q.prefill_note}”.</span>}
              </Message>
            </div>
          )}

          {isInteg && q?.isField ? (
            <div className="ml-auto mt-4 max-w-[690px] rounded-2xl border border-line bg-[#1C252E] p-4 shadow-2xl backdrop-blur-2xl transition-all focus-within:border-[#1877F2]/50 focus-within:shadow-[0_15px_40px_rgba(24,119,242,.15)]">
              <div className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[.04] px-3.5 py-3">
                {q.isSecret ? <Lock className="size-4 shrink-0 text-[#FFAB00]" /> : <KeyRound className="size-4 shrink-0 text-[#1877F2]" />}
                <input
                  ref={composer}
                  type={q.isSecret && !showSecret ? 'password' : 'text'}
                  value={text}
                  autoComplete="off"
                  spellCheck="false"
                  placeholder={q.example || `Enter ${q.fieldLabel || q.fieldKey}`}
                  onChange={e => setText(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') handleIntegAnswer(text.trim())
                  }}
                  className="flex-1 bg-transparent text-[13px] font-mono text-white placeholder:text-white/30 outline-none"
                />
                {q.isSecret && (
                  <button
                    type="button"
                    onClick={() => setShowSecret(s => !s)}
                    className="rounded-lg p-1 text-white/50 hover:bg-white/[.08] hover:text-white transition"
                    title={showSecret ? 'Hide secret' : 'Show secret'}
                  >
                    {showSecret ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                )}
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-3 px-1">
                <span className="text-[11px] text-white/45">
                  Saved directly to <code className="rounded bg-white/10 px-1 py-0.5 text-white/70">.env.local</code>. Never exposed in prompts.
                </span>
                <div className="flex items-center gap-2">
                  <button
                    disabled={phase === 'sending'}
                    onClick={() => handleIntegAnswer('__skip__')}
                    className="rounded-xl px-3 py-1.5 text-[11.5px] font-medium text-white/60 hover:bg-white/[.06] hover:text-white transition disabled:opacity-40"
                  >
                    {q.required === false ? 'Skip (Optional)' : 'Skip / Add later'}
                  </button>
                  <button
                    disabled={phase === 'sending' || !text.trim()}
                    onClick={() => handleIntegAnswer(text.trim())}
                    className="inline-flex h-9 items-center gap-2 rounded-xl bg-[#1877F2] px-4 text-[12px] font-semibold text-white shadow-[0_8px_16px_0_rgba(24,119,242,0.24)] transition hover:bg-[#0C44AE] disabled:opacity-40"
                  >
                    {phase === 'sending' ? <Loader2 className="size-3.5 animate-spin" /> : <ArrowRight className="size-3.5" />}
                    Continue
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <>
              {options.length > 0 && (
                <div className="ml-11 mb-4 max-w-[680px]">
                  <div className="flex flex-wrap gap-2.5">
                    {options.map((o, i) => {
                      const value = o.value ?? o.label
                      const known = prefill.map(String).includes(String(value))
                      const chosen = picked.includes(value) || (!multi && known)
                      const suggested = o.suggested || value === recommended
                      return (
                        <button key={`${value}-${i}`} disabled={phase === 'sending'} onClick={() => {
                          if (value === TYPE_ANOTHER) {
                            composer.current?.focus()
                            return
                          }
                          if (isInteg) return handleIntegAnswer(value)
                          if (multi) return setPicked(p => p.includes(value) ? p.filter(x => x !== value) : [...p, value])
                          answer({ key: q.id, value, selected: [String(value)] })
                        }} className={cn('rounded-full px-4 py-2 text-[12px] font-medium transition-all shadow-sm disabled:opacity-45 text-left',
                          chosen
                            ? 'bg-[#1877F2] text-white border border-[#1877F2] shadow-[0_4px_12px_0_rgba(24,119,242,0.24)]'
                            : 'border border-white/10 bg-white/[.05] text-white/80 hover:bg-white/[.1] hover:text-white hover:border-white/20'
                        )}>
                          <span>{o.label ?? String(value)}</span>
                          {o.hint && <span className="mt-0.5 block text-[10.5px] font-normal text-white/50">{o.hint}</span>}
                          {(suggested || known) && <span className={cn('ml-2 text-[9px] font-semibold uppercase tracking-wider', chosen ? 'text-white/80' : 'text-white/40')}>{known ? 'from brief' : 'suggested'}</span>}
                        </button>
                      )
                    })}
                  </div>
                  {multi && (
                    <div className="mt-3 flex items-center gap-3">
                      <Button variant="solid" disabled={!picked.length || phase === 'sending'} onClick={() => answer({ key: q.id, value: picked, selected: picked.map(String) })}>
                        Continue with {picked.length} selected
                      </Button>
                    </div>
                  )}
                </div>
              )}

              <div className="ml-auto mt-2 max-w-[690px] rounded-2xl border border-line bg-[#1C252E] p-4 shadow-2xl backdrop-blur-2xl transition-all focus-within:border-[#1877F2]/50 focus-within:shadow-[0_15px_40px_rgba(24,119,242,.15)]">
                {options.length > 0 && (
                  <div className="mb-2 px-1 text-[11px] font-medium text-white/45">
                    Or type your own answer:
                  </div>
                )}
                <TextArea
                  ref={composer}
                  value={text}
                  rows={options.length > 0 ? 2 : 3}
                  placeholder={options.length > 0 ? "Type custom details or a different answer…" : "Type your answer…"}
                  onChange={e => setText(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && text.trim()) {
                      if (isInteg) handleIntegAnswer(text.trim())
                      else {
                        const payload = { key: q.id, value: text.trim(), text: text.trim() }
                        if (multi && picked.length) payload.selected = picked.map(String)
                        answer(payload)
                      }
                    }
                  }}
                  className="w-full resize-none bg-transparent px-1 py-1 text-[13.5px] leading-relaxed text-white outline-none placeholder:text-white/40 caret-blue-400"
                />
                <AttachList attach={attach} className="mx-1 mb-2" />
                <div className="flex items-center gap-2 border-t border-white/10 px-1 pt-3">
                  <AttachButtons attach={attach} disabled={phase === 'sending'} />
                  <span className="flex-1" />
                  <button
                    disabled={phase === 'sending' || (!text.trim() && !attach.items.length && !(multi && picked.length))}
                    onClick={() => {
                      if (isInteg) handleIntegAnswer(text.trim())
                      else {
                        const val = text.trim() || (multi && picked.length ? picked : null)
                        const payload = { key: q.id, value: val, text: text.trim() }
                        if (multi && picked.length) payload.selected = picked.map(String)
                        answer(payload)
                      }
                    }}
                    className="inline-flex h-9 items-center gap-2 rounded-xl bg-[#1877F2] px-4 text-[12px] font-semibold text-white shadow-[0_8px_16px_0_rgba(24,119,242,0.24)] transition hover:bg-[#0C44AE] disabled:opacity-40"
                  >
                    {phase === 'sending' ? <Loader2 className="size-3.5 animate-spin" /> : <ArrowRight className="size-3.5" />} Send
                  </button>
                </div>
              </div>
            </>
          )}

          {error && <p className="ml-auto mt-3 max-w-[690px] rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-[11.5px] text-red-300">{error}</p>}
          <div ref={tail} />
        </div>
      </div>

      <footer className="shrink-0 border-t border-line bg-[#141A21]/90 px-6 py-3 backdrop-blur-xl">
        <div className="mx-auto flex max-w-[820px] items-center gap-2 text-[11px] text-white/60">
          <Sparkles className="size-3.5 text-[#1877F2]" /> Your answers become the implementation contract. You can review the full plan before anything is built.
          <span className="flex-1" />
          <button disabled={answered === 0 && !integHistory.length} onClick={draftPlanNow} className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-white/[.06] px-3.5 py-1.5 font-medium text-white/90 transition hover:bg-white/[.12] disabled:opacity-40">
            <FileText className="size-3 text-[#FFAB00]" /> Review plan
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
              ? 'rounded-tl-sm bg-[#1C252E] border border-[#1877F2]/30 ring-1 ring-[#1877F2]/20 text-white'
              : 'rounded-tl-sm bg-[#1C252E] border border-line text-white/90'
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
    <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-[#1C252E] px-7 py-6 shadow-2xl backdrop-blur-2xl">
      <Loader2 className="size-5 shrink-0 animate-spin text-[#1877F2]" />
      <div><p className="text-[13.5px] font-semibold text-white">{children}</p>{sub && <p className="mt-1 text-[11px] text-white/50">{sub}</p>}</div>
    </div>
  )
}


