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
    return <PlanDecision question={question} left={left} sending={sending} onAnswer={answer} />
  }
  if (question.kind === 'setup') {
    return <SetupDecision question={question} left={left} sending={sending} onAnswer={answer} />
  }
  if (question.kind === 'question') {
    return <AskDecision question={question} left={left} sending={sending} onAnswer={answer} />
  }
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
    <Modal onClose={() => { }} className="max-w-[620px]">
      <header className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-xl bg-accent/10 text-accent">
          <KeyRound className="size-4" />
        </span>
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold text-ink">{question.purpose}</h2>
          <p className="mt-0.5 text-[11px] text-muted">
            These stay on this machine, in the project’s .env.local. They are not
            sent to the model.
          </p>
        </div>
        <span className="flex-1" />
        <Countdown left={left} />
      </header>

      {choices.length > 0 && (
        <div className="mt-4">
          {question.question && (
            <p className="mb-2 text-[12px] text-ink">{question.question}</p>
          )}
          <div className="grid gap-1.5 sm:grid-cols-2">
            {choices.map(option => (
              <button key={option.id} onClick={() => setChoice(option.id)}
                      aria-pressed={choice === option.id}
                      className={cn('rounded-xl border px-3 py-2 text-left transition-colors',
                        choice === option.id ? 'border-accent bg-accent/[.06]'
                                             : 'border-line hover:border-line2')}>
                <span className="block text-[12px] font-medium text-ink">{option.label}</span>
                {option.hint && (
                  <span className="mt-0.5 block text-[10.5px] leading-relaxed text-muted2">
                    {option.hint}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 space-y-3">
        {fields.map(field => (
          <div key={field.key}>
            <label htmlFor={`setup-${field.key}`}
                   className="flex items-baseline gap-2 text-[12px] font-medium text-ink">
              {field.label}
              <code className="font-mono text-[9.5px] text-muted2">{field.key}</code>
              {field.required === false && (
                <span className="text-[10px] text-muted2">optional</span>
              )}
            </label>
            {field.hint && (
              <p className="mt-0.5 text-[10.5px] leading-relaxed text-muted2">{field.hint}</p>
            )}
            <div className="mt-1.5 flex items-center gap-1.5">
              <input id={`setup-${field.key}`}
                     type={field.secret && !shown[field.key] ? 'password' : 'text'}
                     value={values[field.key] || ''} spellCheck={false}
                     autoComplete="off" placeholder={field.example}
                     onChange={e => set(field.key, e.target.value)}
                     className="h-9 flex-1 rounded-xl border border-line bg-white/70 px-3 font-mono text-[11.5px] text-ink outline-none transition-colors focus:border-accent dark:bg-white/5" />
              {field.secret && (
                <button onClick={() => setShown(s => ({ ...s, [field.key]: !s[field.key] }))}
                        title={shown[field.key] ? 'Hide it' : 'Show what you typed'}
                        className="grid size-9 shrink-0 place-items-center rounded-xl border border-line text-muted transition-colors hover:text-ink">
                  {shown[field.key] ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                </button>
              )}
            </div>
            <p className="mt-1 font-mono text-[10px] text-muted2">e.g. {field.example}</p>
          </div>
        ))}
      </div>

      <footer className="mt-5 flex items-center gap-2 border-t border-line/70 pt-4">
        <span className="flex-1 text-[10.5px] text-muted2">
          {needed ? `${filled}/${needed} filled in` : 'Nothing to fill in'}
        </span>
        <Button variant="outline" disabled={Boolean(sending)}
                title="The build carries on and writes the names into .env.example for you to fill in"
                onClick={() => onAnswer({ decision: 'later' })}>
          {sending === 'later' ? <Loader2 className="size-3 animate-spin" />
                               : <SkipForward className="size-3" />}
          Not now
        </Button>
        <Button variant="solid" disabled={Boolean(sending) || (Boolean(fields.length) && !anything)}
                onClick={() => onAnswer({ decision: 'save', choice, values })}>
          {sending === 'save' ? <Loader2 className="size-3 animate-spin" />
                              : <Check className="size-3" />}
          Save and continue
        </Button>
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
    <span className="text-[10.5px] text-muted2">
      building anyway in {minutes}:{seconds}
    </span>
  )
}

/**
 * A question the agent stopped to ask.
 *
 * Not a credential and not an approval: a decision that was always the user's
 * and that the request never settled — whether a booking can be cancelled an
 * hour before it starts, whether the manager sees other people's pay. Deciding
 * those quietly is how a build ends up not being the application somebody
 * asked for.
 *
 * It says what it will do if nobody replies, and then does that, because a
 * question that stops a build is worse than a decision that was explained.
 */
function AskDecision({ question, left, sending, onAnswer }) {
  const options = question.options || []
  const [reply, setReply] = useState('')

  return (
    <Modal onClose={() => { }} className="max-w-[560px]">
      <header className="flex items-start gap-2.5">
        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-xl bg-accent/10 text-accent">
          <MessageCircleQuestion className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[14px] font-semibold leading-snug text-ink">
            {question.question}
          </h2>
          {question.why && (
            <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{question.why}</p>
          )}
        </div>
        <Countdown left={left} />
      </header>

      {options.length > 0 && (
        <div className="mt-4 space-y-1.5">
          {options.map(option => (
            <button key={option.id} disabled={Boolean(sending)}
                    onClick={() => onAnswer({ decision: 'answer', reply: option.label })}
                    className="w-full rounded-xl border border-line px-3 py-2.5 text-left transition-colors hover:border-accent hover:bg-accent/[.05] disabled:opacity-50">
              <span className="block text-[12.5px] font-medium text-ink">{option.label}</span>
              {option.hint && (
                <span className="mt-0.5 block text-[10.5px] leading-relaxed text-muted2">
                  {option.hint}
                </span>
              )}
            </button>
          ))}
        </div>
      )}

      <textarea value={reply} rows={2} autoFocus={!options.length}
                placeholder={options.length ? 'Or say it in your own words…'
                                            : 'Your answer…'}
                onChange={e => setReply(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey && reply.trim()) {
                    e.preventDefault()
                    onAnswer({ decision: 'answer', reply: reply.trim() })
                  }
                }}
                className="mt-3 w-full resize-y rounded-xl border border-line bg-white/70 px-3 py-2.5 text-[12.5px] leading-relaxed outline-none focus:border-accent dark:bg-white/5" />

      <footer className="mt-4 flex items-center gap-2 border-t border-line/70 pt-4">
        <span className="flex-1 text-[10.5px] leading-relaxed text-muted2">
          {question.assumption
            ? `No answer: it will ${question.assumption}`
            : 'No answer: it will decide and say what it assumed.'}
        </span>
        <Button variant="outline" disabled={Boolean(sending)}
                onClick={() => onAnswer({ decision: 'default' })}>
          {sending === 'default' ? <Loader2 className="size-3 animate-spin" />
                                 : <SkipForward className="size-3" />}
          You decide
        </Button>
        <Button variant="solid" disabled={Boolean(sending) || !reply.trim()}
                onClick={() => onAnswer({ decision: 'answer', reply: reply.trim() })}>
          {sending === 'answer' ? <Loader2 className="size-3 animate-spin" />
                                : <Check className="size-3" />}
          Send
        </Button>
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
    <Modal onClose={() => { }} className="max-w-[760px]">
      <header className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-xl bg-accent/10 text-accent">
          <Search className="size-4" />
        </span>
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold text-ink">The plan</h2>
          <p className="mt-0.5 text-[11px] text-muted">
            {question.goal}
          </p>
        </div>
        <span className="flex-1" />
        <Countdown left={left} />
      </header>

      <div className="mt-4 max-h-[52vh] overflow-auto rounded-xl border border-line bg-panel2/40 px-4 py-3.5">
        <PlanReading plan={question.plan} />
      </div>

      {revising && (
        <textarea value={feedback} autoFocus rows={3}
                  placeholder="What should it do differently? Leave empty to let it reconsider on its own."
                  onChange={e => setFeedback(e.target.value)}
                  className="mt-3 w-full resize-y rounded-xl border border-line bg-white/70 px-3 py-2.5 text-[12.5px] leading-relaxed outline-none focus:border-accent dark:bg-white/5" />
      )}

      <footer className="mt-4 flex items-center gap-2 border-t border-line/70 pt-4">
        <span className="flex-1 text-[10.5px] text-muted2">
          {round >= rounds
            ? 'Last round — the build starts after this.'
            : `Revision ${round + 1} of ${rounds + 1}`}
        </span>
        {round < rounds && (
          <Button variant="outline" disabled={Boolean(sending)}
                  onClick={() => revising ? onAnswer({ decision: 'revise', feedback })
                                          : setRevising(true)}>
            {sending === 'revise' ? <Loader2 className="size-3 animate-spin" />
                                  : <RotateCcw className="size-3" />}
            {revising ? 'Send it back' : 'Revise'}
          </Button>
        )}
        <Button variant="solid" disabled={Boolean(sending)}
                onClick={() => onAnswer({ decision: 'accept' })}>
          {sending === 'accept' ? <Loader2 className="size-3 animate-spin" />
                                : <Check className="size-3" />}
          Build this
        </Button>
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
    <Modal onClose={() => { }} className="max-w-[1180px]">
      <header className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-xl bg-accent/10 text-accent">
          <Palette className="size-4" />
        </span>
        <div>
          <h2 className="text-[15px] font-semibold text-ink">How should it look?</h2>
          <p className="mt-0.5 text-[11px] text-muted">
            Every choice here shows on the page beside it, and the build follows
            it exactly. Nothing is decided for you that you cannot change.
          </p>
        </div>
        <span className="flex-1" />
        <Countdown left={left} />
      </header>


      <div className="mt-4 grid gap-5 lg:grid-cols-[1fr_400px]">
        <div className="space-y-4">
          <Field label="Palette">
            <div className="grid gap-1.5 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
              {(question.palettes || []).map(option => (
                <button key={option.id} onClick={() => setPick(p => ({ ...p, palette: option.id }))}
                        title={option.mood}
                        className={cn('flex items-center gap-2 rounded-xl border px-2.5 py-2 text-left transition-colors',
                          pick.palette === option.id
                            ? 'border-accent bg-accent/[.07]' : 'border-line hover:border-line2')}>
                  <span className="flex shrink-0 gap-0.5">
                    {['primary', 'accent', 'background'].map(role => (
                      <span key={role} className="size-3.5 rounded-[4px] ring-1 ring-black/[.08]"
                            style={{ background: option.light?.[role] }} />
                    ))}
                  </span>
                  <span className="min-w-0 truncate text-[11.5px] font-medium text-ink">
                    {option.name}
                  </span>
                </button>
              ))}
            </div>
          </Field>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Type">
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
            <Field label="Width">
              <Choices options={ids(question.containers)} value={pick.container}
                       onChange={v => set('container', v)} />
            </Field>
          </div>

          <Field label={question.planned
            ? `Screens in the plan (${pick.pages.length} of ${(question.pages || []).length})`
            : `Optional screen additions (${pick.pages.length})`}>
            <p className="mb-2 text-[11px] leading-relaxed text-muted2">
              {question.planned
                ? 'These are the screens the approved plan describes. Every one is included; turn off any you do not want built.'
                : 'The approved plan already defines your screens. Select only additions you want.'}
            </p>
            <div className="space-y-1">
              {(question.pages || []).map(page => {
                const on = pick.pages.includes(page.id)
                return (
                  <button key={page.id} onClick={() => togglePage(page.id)}
                          aria-pressed={on}
                          className={cn('flex w-full items-start gap-2.5 rounded-lg border px-2.5 py-2 text-left transition-colors',
                            on ? 'border-accent/50 bg-accent/[.05]'
                               : 'border-line bg-panel opacity-60 hover:opacity-100')}>
                    <span className={cn('mt-[3px] grid size-3.5 shrink-0 place-items-center rounded-[4px] border',
                      on ? 'border-accent bg-accent text-white' : 'border-line2')}>
                      {on && <Check className="size-2.5" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-baseline gap-1.5">
                        <span className="text-[11.5px] font-medium text-ink">{page.label}</span>
                        {page.route && (
                          <code className="font-mono text-[9.5px] text-muted2">{page.route}</code>
                        )}
                      </span>
                      {page.what && (
                        <span className="mt-0.5 block text-[10.5px] leading-relaxed text-muted2">
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

        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-[.14em] text-muted2">
            Your application
          </p>
          <DesignPreview tokens={tokens} question={question} pick={pick}
                         screens={(question.pages || []).filter(p => pick.pages.includes(p.id))} />
          <p className="text-[10px] leading-relaxed text-muted2">
            Every choice on the left shows here. This is the product, not a swatch.
          </p>
        </div>
      </div>

      <footer className="mt-4 flex items-center gap-2 border-t border-line/70 pt-4">
        <span className="flex-1 text-[10.5px] text-muted2">{palette?.mood}</span>
        <Button variant="ghost" disabled={Boolean(sending)}
                onClick={() => onAnswer({ decision: 'skip' })}>
          <SkipForward className="size-3" /> Let it decide
        </Button>
        <Button variant="solid" disabled={Boolean(sending)}
                onClick={() => onAnswer({ decision: 'apply', selection: pick })}>
          {sending === 'apply' ? <Loader2 className="size-3 animate-spin" />
                               : <Check className="size-3" />}
          Use this
        </Button>
      </footer>
    </Modal>
  )
}

const Field = ({ label, children }) => (
  <div>
    <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[.14em] text-muted2">
      {label}
    </p>
    {children}
  </div>
)

/** A catalogue row renders as its own id: they are already the human word.
 *
 * The catalogue also writes a sentence about each option - "200-320ms springs,
 * slide-ins, staggered lists" - and nothing ever showed them, so every choice
 * was a word you either knew or guessed at.
 */
const ids = (rows) => (rows || []).map(row => ({ id: row.id, label: row.id, hint: row.hint }))

const Choices = ({ options, value, onChange }) => (
  <div className="flex flex-wrap gap-1">
    {options.map(option => (
      <button key={option.id} onClick={() => onChange(option.id)} title={option.hint || ''}
              className={cn('rounded-lg border px-2 py-1 text-[10.5px] capitalize transition-colors',
                value === option.id ? 'border-accent bg-accent/[.07] text-accent'
                                    : 'border-line text-muted hover:text-ink')}>
        {option.label}
      </button>
    ))}
  </div>
)
