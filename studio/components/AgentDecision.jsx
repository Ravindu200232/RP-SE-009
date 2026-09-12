'use client'

/**
 * The three things a build stops to ask about.
 *
 * Everything else the agent does is unattended by design. What it is going to
 * build and what it will look like are worth asking because both are cheap to
 * change now and expensive to change once the app is written. The third is a
 * different kind of thing: an account setting nobody but the user has, which
 * no amount of reading the project will ever produce.
 *
 * The drawing of the application is a fourth, and it is not here: it is shown
 * in the preview, where the select and pencil tools work and where it can be
 * walked by clicking its own navigation. A dialog over the top of it would
 * hide the thing being judged.
 *
 * None of them blocks. Each question carries its own deadline, and if nobody
 * answers the run proceeds with what it had chosen anyway — so closing this
 * window costs a choice, never a build.
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Check, Eye, EyeOff, KeyRound, Loader2, MessageCircleQuestion, Palette, RotateCcw,
  Search, SkipForward,
} from 'lucide-react'

import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import PlanReading from './PlanReading'
import DesignPreview from './DesignPreview'
import { Button, Modal } from './ui'
import { cn } from '@/lib/utils'

/**
 * Close the question that was answered, and only that one.
 *
 * Answering the plan is an await, and the run does not wait for it: by the
 * time the request comes back the next question - the design - has already
 * arrived over the socket. Clearing unconditionally here threw that one away,
 * so accepting a plan looked like the design customiser had been skipped.
 */
function dismiss(id) {
  const store = useStore.getState()
  if (!id || store.approval?.id === id) store.setApproval(null)
}

export default function AgentDecision() {
  const question = useStore(s => s.approval)
  const [sending, setSending] = useState('')
  const [left, setLeft] = useState(0)

  useEffect(() => {
    if (!question) return
    if (question.kind === 'plan') {
      answer({ decision: 'accept' })
      return
    }
    const deadline = Date.now() + (Number(question.timeout) || 300) * 1000
    setLeft(Math.round((deadline - Date.now()) / 1000))
    const tick = setInterval(() => {
      const remaining = Math.round((deadline - Date.now()) / 1000)
      setLeft(remaining)
      if (remaining <= 0) dismiss(question.id)
    }, 1000)
    return () => clearInterval(tick)
  }, [question])

  if (!question) return null

  async function answer(body) {
    const answered = question.id
    setSending(body.decision)
    try {
      await api.decide({ id: answered, ...body })
    } catch (e) {
      useStore.getState().addLog('WARN', `Could not send that decision — ${e.message}`)
    }
    setSending('')
    dismiss(answered)
  }

  if (question.kind === 'plan') {
    // Automatically accepted; do not present plan approval modal to the user
    return null
  }
  if (question.kind === 'setup') {
    return <SetupDecision question={question} left={left} sending={sending} onAnswer={answer} />
  }
  if (question.kind === 'question') {
    return <AskDecision question={question} left={left} sending={sending} onAnswer={answer} />
  }
  // A drawing is looked at, not answered. It belongs in the preview with the
  // select and pencil tools, so nothing is rendered here for it.
  if (question.kind === 'prototype') return null
  return <DesignDecision question={question} left={left} sending={sending} onAnswer={answer} />
}

/**
 * The settings only the account holder has.
 *
 * A Stripe secret or a Cloudinary cloud name cannot be worked out from the
 * project, so a build that needs one either invents a placeholder and ships an
 * app that fails on first use, or stops. It asks instead, here, while the
 * person is already watching it work.
 *
 * Every field shows a real example. Told only "API key", people paste an
 * account id, a publishable key where a secret belongs, or the whole line they
 * copied out of a dashboard; shown `sk_test_51H8...`, they paste the right
 * thing. The values go straight to the run and into the project's .env.local —
 * they are not sent to the model, and nothing here puts one on screen twice.
 */
function SetupDecision({ question, left, sending, onAnswer }) {
  const choices = question.choices || []
  const [choice, setChoice] = useState(choices[0]?.id || '')
  // Choosing Stripe should not ask for PayHere's merchant id, so the fields
  // belong to the option and the question shows only the chosen one's.
  const fields = [...(question.fields || []),
                  ...(choices.find(option => option.id === choice)?.fields || [])]
  const [values, setValues] = useState({})
  const [shown, setShown] = useState({})

  const set = (key, value) => setValues(v => ({ ...v, [key]: value }))
  const typed = (field) => Boolean(String(values[field.key] || '').trim())
  // Progress is over the settings that are actually needed. Counting every
  // filled box against only the required ones reported "3/2 filled in" the
  // moment somebody filled in an optional one.
  const required = fields.filter(f => f.required !== false)
  const filled = required.filter(typed).length
  const needed = required.length
  const anything = fields.some(typed)

  return (
    <Modal onClose={() => { }} className="max-w-[640px]">
      <header className="flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-2xl border border-emerald-500/25 bg-emerald-500/10 text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.15)]">
          <KeyRound className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[16px] font-bold tracking-tight text-white">{question.purpose}</h2>
          <p className="mt-0.5 text-xs text-slate-400 leading-relaxed">
            These stay on this machine, in the project’s .env.local. They are not
            sent to the model.
          </p>
        </div>
        <Countdown left={left} />
      </header>

      {choices.length > 0 && (
        <div className="mt-5">
          {question.question && (
            <p className="mb-2.5 text-xs font-semibold text-slate-300">{question.question}</p>
          )}
          <div className="grid gap-2 sm:grid-cols-2">
            {choices.map(option => (
              <button key={option.id} onClick={() => setChoice(option.id)}
                      aria-pressed={choice === option.id}
                      className={cn('rounded-xl border p-3 text-left transition-all',
                        choice === option.id
                          ? 'border-emerald-500/50 bg-emerald-500/15 shadow-[0_0_20px_rgba(16,185,129,0.12)]'
                          : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.06]')}>
                <span className="block text-xs font-bold text-white">{option.label}</span>
                {option.hint && (
                  <span className="mt-0.5 block text-[11px] leading-relaxed text-slate-400">
                    {option.hint}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5 space-y-3.5">
        {fields.map(field => (
          <div key={field.key} className="rounded-xl border border-white/10 bg-[#080b12] p-3 shadow-inner">
            <label htmlFor={`setup-${field.key}`}
                   className="flex items-baseline gap-2 text-xs font-semibold text-slate-200">
              {field.label}
              <code className="font-mono text-[10px] text-emerald-400">{field.key}</code>
              {field.required === false && (
                <span className="text-[10px] text-slate-500">optional</span>
              )}
            </label>
            {field.hint && (
              <p className="mt-0.5 text-[11px] leading-relaxed text-slate-400">{field.hint}</p>
            )}
            <div className="mt-2 flex items-center gap-2">
              <input id={`setup-${field.key}`}
                     type={field.secret && !shown[field.key] ? 'password' : 'text'}
                     value={values[field.key] || ''} spellCheck={false}
                     autoComplete="off" placeholder={field.example}
                     onChange={e => set(field.key, e.target.value)}
                     className="h-9 flex-1 rounded-xl border border-white/10 bg-white/[0.04] px-3 font-mono text-xs text-white outline-none transition-all placeholder:text-slate-500 focus:border-emerald-500/60 focus:ring-1 focus:ring-emerald-500/40" />
              {field.secret && (
                <button onClick={() => setShown(s => ({ ...s, [field.key]: !s[field.key] }))}
                        title={shown[field.key] ? 'Hide it' : 'Show what you typed'}
                        className="grid size-9 shrink-0 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-slate-400 transition-all hover:bg-white/[0.08] hover:text-white">
                  {shown[field.key] ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                </button>
              )}
            </div>
            <p className="mt-1.5 font-mono text-[10px] text-slate-500">e.g. {field.example}</p>
          </div>
        ))}
      </div>

      <footer className="mt-5 flex items-center gap-3 border-t border-white/10 pt-4">
        <span className="flex-1 font-mono text-xs text-slate-400">
          {needed ? `${filled}/${needed} filled in` : 'Nothing to fill in'}
        </span>
        <button disabled={Boolean(sending)}
                title="The build carries on and writes the names into .env.example for you to fill in"
                onClick={() => onAnswer({ decision: 'later' })}
                className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.05] px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-white/[0.1] hover:text-white transition-all disabled:opacity-40">
          {sending === 'later' ? <Loader2 className="size-3.5 animate-spin" />
                               : <SkipForward className="size-3.5" />}
          Not now
        </button>
        <button disabled={Boolean(sending) || (Boolean(fields.length) && !anything)}
                onClick={() => onAnswer({ decision: 'save', choice, values })}
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white shadow-lg shadow-emerald-500/25 hover:bg-emerald-500 transition-all disabled:opacity-40">
          {sending === 'save' ? <Loader2 className="size-3.5 animate-spin" />
                              : <Check className="size-3.5" />}
          Save and continue
        </button>
      </footer>
    </Modal>
  )
}

/** How long the build will wait before carrying on by itself. */
function Countdown({ left }) {
  if (left <= 0) return null
  const minutes = Math.floor(left / 60)
  const seconds = String(left % 60).padStart(2, '0')
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 font-mono text-[11px] font-medium text-amber-300 shadow-sm">
      <span className="size-1.5 rounded-full bg-amber-400 animate-pulse" />
      <span>{minutes}:{seconds}</span>
    </div>
  )
}

/**
 * A question the agent stopped to ask.
 */
function AskDecision({ question, left, sending, onAnswer }) {
  const options = question.options || []
  const [reply, setReply] = useState('')

  return (
    <Modal onClose={() => { }} className="max-w-[580px]">
      <header className="flex items-start gap-3">
        <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-2xl border border-indigo-500/25 bg-indigo-500/10 text-indigo-400 shadow-[0_0_20px_rgba(99,102,241,0.15)]">
          <MessageCircleQuestion className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-bold leading-snug text-white">
            {question.question}
          </h2>
          {question.why && (
            <p className="mt-1 text-xs leading-relaxed text-slate-400">{question.why}</p>
          )}
        </div>
        <Countdown left={left} />
      </header>

      {options.length > 0 && (
        <div className="mt-5 space-y-2">
          {options.map(option => (
            <button key={option.id} disabled={Boolean(sending)}
                    onClick={() => onAnswer({ decision: 'answer', reply: option.label })}
                    className="w-full rounded-xl border border-white/10 bg-white/[0.03] p-3 text-left transition-all hover:border-indigo-500/50 hover:bg-indigo-500/10 disabled:opacity-50">
              <span className="block text-xs font-bold text-white">{option.label}</span>
              {option.hint && (
                <span className="mt-0.5 block text-[11px] leading-relaxed text-slate-400">
                  {option.hint}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      <textarea value={reply} rows={3} autoFocus={!options.length}
                placeholder={options.length ? 'Or say it in your own words…'
                                            : 'Your answer…'}
                onChange={e => setReply(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey && reply.trim()) {
                    e.preventDefault()
                    onAnswer({ decision: 'answer', reply: reply.trim() })
                  }
                }}
                className="mt-4 w-full resize-y rounded-xl border border-white/10 bg-[#080b12] p-3 text-xs leading-relaxed text-white outline-none placeholder:text-slate-500 focus:border-indigo-500/60 focus:ring-1 focus:ring-indigo-500/40" />

      <footer className="mt-5 flex items-center gap-3 border-t border-white/10 pt-4">
        <span className="flex-1 text-[11px] leading-relaxed text-slate-400">
          {question.assumption
            ? `No answer: it will ${question.assumption}`
            : 'No answer: it will decide and say what it assumed.'}
        </span>
        <button disabled={Boolean(sending)}
                onClick={() => onAnswer({ decision: 'default' })}
                className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.05] px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-white/[0.1] hover:text-white transition-all disabled:opacity-40">
          {sending === 'default' ? <Loader2 className="size-3.5 animate-spin" />
                                 : <SkipForward className="size-3.5" />}
          You decide
        </button>
        <button disabled={Boolean(sending) || !reply.trim()}
                onClick={() => onAnswer({ decision: 'answer', reply: reply.trim() })}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-5 py-2 text-xs font-bold text-white shadow-lg shadow-indigo-500/25 hover:bg-indigo-500 transition-all disabled:opacity-40">
          {sending === 'answer' ? <Loader2 className="size-3.5 animate-spin" />
                                : <Check className="size-3.5" />}
          Send
        </button>
      </footer>
    </Modal>
  )
}

function PlanDecision({ question, left, sending, onAnswer }) {
  const [feedback, setFeedback] = useState('')
  const [revising, setRevising] = useState(false)
  const rounds = Number(question.maxRevisions || 0)
  const round = Number(question.revision || 0)

  return (
    <Modal onClose={() => { }} className="max-w-[820px]">
      <header className="flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-2xl border border-blue-500/25 bg-blue-500/10 text-blue-400 shadow-[0_0_20px_rgba(59,130,246,0.18)]">
          <Search className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[17px] font-bold tracking-tight text-white">The plan</h2>
          <p className="mt-0.5 text-xs text-slate-400 leading-relaxed max-w-xl truncate">
            {question.goal}
          </p>
        </div>
        <Countdown left={left} />
      </header>

      <div className="mt-5 max-h-[55vh] overflow-auto rounded-2xl border border-white/10 bg-[#080b12] p-5 shadow-2xl">
        <PlanReading plan={question.plan} />
      </div>

      {revising && (
        <textarea value={feedback} autoFocus rows={3}
                  placeholder="What should it do differently? Leave empty to let it reconsider on its own."
                  onChange={e => setFeedback(e.target.value)}
                  className="mt-4 w-full resize-y rounded-xl border border-white/10 bg-[#080b12] px-4 py-3 text-xs leading-relaxed text-white outline-none placeholder:text-slate-500 focus:border-blue-500/60 focus:ring-1 focus:ring-blue-500/50 shadow-inner" />
      )}

      <footer className="mt-5 flex items-center gap-3 border-t border-white/10 pt-4">
        <span className="flex-1 font-mono text-xs text-slate-400">
          {round >= rounds
            ? 'Last round — the build starts after this.'
            : `Revision ${round + 1} of ${rounds + 1}`}
        </span>
        {round < rounds && (
          <button disabled={Boolean(sending)}
                  onClick={() => revising ? onAnswer({ decision: 'revise', feedback })
                                          : setRevising(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.05] px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-white/[0.1] hover:text-white transition-all disabled:opacity-40">
            {sending === 'revise' ? <Loader2 className="size-3.5 animate-spin" />
                                  : <RotateCcw className="size-3.5" />}
            {revising ? 'Send it back' : 'Revise'}
          </button>
        )}
        <button disabled={Boolean(sending)}
                onClick={() => onAnswer({ decision: 'accept' })}
                className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-6 py-2.5 text-xs font-bold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500 transition-all disabled:opacity-40">
          {sending === 'accept' ? <Loader2 className="size-3.5 animate-spin" />
                                : <Check className="size-3.5" />}
          Build this
        </button>
      </footer>
    </Modal>
  )
}

function DesignDecision({ question, left, sending, onAnswer }) {
  const chosen = question.chosen || {}
  const [pick, setPick] = useState({
    palette: chosen.palette, font: chosen.font, radius: chosen.radius,
    density: chosen.density, typeScale: chosen.typeScale, themeMode: chosen.themeMode,
    border: chosen.border, elevation: chosen.elevation, motion: chosen.motion,
    tone: chosen.tone, contrast: chosen.contrast, container: chosen.container,
    // The screens the plan named, all of them on until one is turned off.
    pages: chosen.pages || [],
  })
  const set = (field, value) => setPick(p => ({ ...p, [field]: value }))
  const togglePage = id => setPick(p => ({
    ...p,
    pages: p.pages.includes(id) ? p.pages.filter(x => x !== id) : [...p.pages, id],
  }))
  const palette = useMemo(
    () => (question.palettes || []).find(p => p.id === pick.palette) || question.palettes?.[0],
    [question.palettes, pick.palette])
  const tokens = (palette || {})[pick.themeMode === 'dark' ? 'dark' : 'light'] || {}

  return (
    <Modal onClose={() => { }} className="max-w-[1240px]">
      <header className="flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-2xl border border-purple-500/25 bg-purple-500/10 text-purple-400 shadow-[0_0_20px_rgba(168,85,247,0.18)]">
          <Palette className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[17px] font-bold tracking-tight text-white">How should it look?</h2>
          <p className="mt-0.5 text-xs text-slate-400 leading-relaxed">
            Every choice here shows on the page beside it, and the build follows
            it exactly. Nothing is decided for you that you cannot change.
          </p>
        </div>
        <Countdown left={left} />
      </header>

      <div className="mt-5 grid gap-6 lg:grid-cols-[1fr_420px]">
        <div className="space-y-4 max-h-[64vh] overflow-y-auto pr-1">
          <Field label="Palette">
            <div className="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
              {(question.palettes || []).map(option => (
                <button key={option.id} onClick={() => setPick(p => ({ ...p, palette: option.id }))}
                        title={option.mood}
                        className={cn('flex items-center gap-2.5 rounded-xl border p-2.5 text-left transition-all',
                          pick.palette === option.id
                            ? 'border-blue-500 bg-blue-500/15 shadow-[0_0_20px_rgba(59,130,246,0.15)] ring-1 ring-blue-500/40'
                            : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.06] hover:border-white/20')}>
                  <span className="flex shrink-0 gap-1">
                    {['primary', 'accent', 'background'].map(role => (
                      <span key={role} className="size-3.5 rounded-[5px] ring-1 ring-white/15"
                            style={{ background: option.light?.[role] }} />
                    ))}
                  </span>
                  <span className="min-w-0 truncate text-xs font-semibold text-white">
                    {option.name}
                  </span>
                </button>
              ))}
            </div>
          </Field>

          <div className="rounded-2xl border border-white/10 bg-[#080b12] p-4 shadow-inner">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Typography">
                <Choices options={(question.fonts || []).map(f => ({
                           id: f.id, label: f.name, hint: `${f.heading} headings, ${f.body} body` }))}
                         value={pick.font} onChange={v => set('font', v)} />
              </Field>
              <Field label="Type scale">
                <Choices options={(question.typeScales || []).map(s => ({
                           id: s.id, label: s.id,
                           hint: `${s.base}px body, each step ${s.ratio}x the last` }))}
                         value={pick.typeScale} onChange={v => set('typeScale', v)} />
              </Field>
              <Field label="Theme">
                <Choices options={ids(question.themeModes)} value={pick.themeMode}
                         onChange={v => set('themeMode', v)} />
              </Field>
              <Field label="Corners">
                <Choices options={ids(question.radii)} value={pick.radius}
                         onChange={v => set('radius', v)} />
              </Field>
              <Field label="Spacing">
                <Choices options={ids(question.densities)} value={pick.density}
                         onChange={v => set('density', v)} />
              </Field>
              <Field label="Borders">
                <Choices options={ids(question.borders)} value={pick.border}
                         onChange={v => set('border', v)} />
              </Field>
              <Field label="Depth">
                <Choices options={ids(question.elevations)} value={pick.elevation}
                         onChange={v => set('elevation', v)} />
              </Field>
              <Field label="Motion">
                <Choices options={ids(question.motions)} value={pick.motion}
                         onChange={v => set('motion', v)} />
              </Field>
              <Field label="Voice">
                <Choices options={ids(question.tones)} value={pick.tone}
                         onChange={v => set('tone', v)} />
              </Field>
              <Field label="Contrast">
                <Choices options={(question.contrasts || []).map(c => ({
                           id: c.id, label: c.id.toUpperCase() }))}
                         value={pick.contrast} onChange={v => set('contrast', v)} />
              </Field>
              <Field label="Container Width">
                <Choices options={ids(question.containers)} value={pick.container}
                         onChange={v => set('container', v)} />
              </Field>
            </div>
          </div>

          <Field label={question.planned
            ? `Screens in the plan (${pick.pages.length} of ${(question.pages || []).length})`
            : `Optional screen additions (${pick.pages.length})`}>
            <p className="mb-2.5 text-xs leading-relaxed text-slate-400">
              {question.planned
                ? 'These are the screens the approved plan describes. Every one is included; turn off any you do not want built.'
                : 'The approved plan already defines your screens. Select only additions you want.'}
            </p>
            <div className="space-y-1.5">
              {(question.pages || []).map(page => {
                const on = pick.pages.includes(page.id)
                return (
                  <button key={page.id} onClick={() => togglePage(page.id)}
                          aria-pressed={on}
                          className={cn('flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-all',
                            on ? 'border-blue-500/50 bg-blue-500/10'
                               : 'border-white/10 bg-white/[0.02] opacity-60 hover:opacity-100')}>
                    <span className={cn('mt-0.5 grid size-4 shrink-0 place-items-center rounded-md border transition-all',
                      on ? 'border-blue-500 bg-blue-600 text-white' : 'border-white/20 bg-white/[0.04]')}>
                      {on && <Check className="size-3" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline gap-2">
                        <span className="text-xs font-bold text-white">{page.label}</span>
                        {page.route && (
                          <code className="font-mono text-[10px] text-blue-400">{page.route}</code>
                        )}
                      </span>
                      {page.what && (
                        <span className="mt-0.5 block text-[11px] leading-relaxed text-slate-400">
                          {page.what}
                        </span>
                      )}
                    </span>
                  </button>
                )
              })}
            </div>
          </Field>
        </div>

        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-bold uppercase tracking-[.15em] text-slate-400">
              Live Application Preview
            </p>
            <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-emerald-400 shadow-sm">
              <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live Preview
            </div>
          </div>

          <div className="overflow-hidden rounded-2xl border border-white/15 bg-[#080b12] shadow-2xl">
            <div className="flex items-center gap-2 border-b border-white/10 bg-white/[0.03] px-3.5 py-2">
              <div className="flex items-center gap-1.5">
                <span className="size-2 rounded-full bg-rose-500/80" />
                <span className="size-2 rounded-full bg-amber-500/80" />
                <span className="size-2 rounded-full bg-emerald-500/80" />
              </div>
              <div className="mx-auto flex h-4 max-w-[180px] flex-1 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] px-2 font-mono text-[9px] text-slate-400 truncate">
                {question.goal || 'scaffold-preview'}
              </div>
            </div>
            <div className="p-3">
              <DesignPreview tokens={tokens} question={question} pick={pick}
                             screens={(question.pages || []).filter(p => pick.pages.includes(p.id))} />
            </div>
          </div>

          <p className="text-center text-[11px] leading-relaxed text-slate-400 mt-2">
            Every choice on the left updates this canvas live. This is your product scaffold, not a swatch.
          </p>
        </div>
      </div>

      <footer className="mt-5 flex items-center gap-3 border-t border-white/10 pt-4">
        <span className="flex-1 text-xs text-slate-400 italic truncate">{palette?.mood}</span>
        <button disabled={Boolean(sending)}
                onClick={() => onAnswer({ decision: 'skip' })}
                className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.05] px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-white/[0.1] hover:text-white transition-all disabled:opacity-40">
          <SkipForward className="size-3.5" /> Let it decide
        </button>
        <button disabled={Boolean(sending)}
                onClick={() => onAnswer({ decision: 'apply', selection: pick })}
                className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-6 py-2.5 text-xs font-bold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500 transition-all disabled:opacity-40">
          {sending === 'apply' ? <Loader2 className="size-3.5 animate-spin" />
                               : <Check className="size-3.5" />}
          Use this
        </button>
      </footer>
    </Modal>
  )
}

const Field = ({ label, children }) => (
  <div>
    <p className="mb-2 text-[10.5px] font-bold uppercase tracking-[.15em] text-slate-400">
      {label}
    </p>
    {children}
  </div>
)

const ids = (rows) => (rows || []).map(row => ({ id: row.id, label: row.id, hint: row.hint }))

const Choices = ({ options, value, onChange }) => (
  <div className="flex flex-wrap gap-1.5">
    {options.map(option => (
      <button key={option.id} onClick={() => onChange(option.id)} title={option.hint || ''}
              className={cn('rounded-xl border px-2.5 py-1.5 text-[11px] font-medium capitalize transition-all',
                value === option.id
                  ? 'border-blue-500 bg-blue-500/20 text-white shadow-sm ring-1 ring-blue-500/40'
                  : 'border-white/10 bg-white/[0.03] text-slate-400 hover:text-white hover:bg-white/[0.07]')}>
        {option.label}
      </button>
    ))}
  </div>
)
