'use client'

/**
 * The two decisions a build stops for.
 *
 * Everything else the agent does is unattended by design. These two are worth
 * asking about because both are cheap to change now and expensive to change
 * once the app is written: what it is going to build, and what it will look
 * like.
 *
 * Neither blocks. The question carries its own deadline, and if nobody answers
 * the run proceeds with what it had chosen anyway — so closing this window
 * costs a choice, never a build.
 */

import { useEffect, useMemo, useState } from 'react'
import { Check, Loader2, Palette, RotateCcw, Search, SkipForward } from 'lucide-react'

import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
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

  return question.kind === 'plan'
    ? <PlanDecision question={question} left={left} sending={sending} onAnswer={answer} />
    : <DesignDecision question={question} left={left} sending={sending} onAnswer={answer} />
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

      <pre className="mt-4 max-h-[46vh] overflow-auto whitespace-pre-wrap rounded-xl border border-line bg-panel2/60 p-3.5 font-mono text-[11.5px] leading-relaxed text-ink">
        {question.plan}
      </pre>

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
  const [blockSearch, setBlockSearch] = useState('')
  const [blockCategory, setBlockCategory] = useState('all')
  const [pick, setPick] = useState({
    palette: chosen.palette, font: chosen.font, radius: chosen.radius,
    density: chosen.density, typeScale: chosen.typeScale, themeMode: chosen.themeMode,
    border: chosen.border, elevation: chosen.elevation, motion: chosen.motion,
    tone: chosen.tone, contrast: chosen.contrast, container: chosen.container,
    pages: chosen.pages || [], blocks: chosen.blocks || [],
  })
  const set = (field, value) => setPick(p => ({ ...p, [field]: value }))
  const togglePage = id => setPick(p => ({
    ...p,
    pages: p.pages.includes(id) ? p.pages.filter(x => x !== id) : [...p.pages, id],
  }))
  const toggleBlock = id => setPick(p => ({
    ...p,
    blocks: p.blocks.includes(id) ? p.blocks.filter(x => x !== id) : [...p.blocks, id],
  }))
  const visibleBlocks = useMemo(() => {
    const query = blockSearch.trim().toLowerCase()
    return (question.blocks || []).filter(block => {
      if (blockCategory !== 'all' && block.category !== blockCategory) return false
      return !query || `${block.name} ${block.category} ${block.description}`
        .toLowerCase().includes(query)
    })
  }, [question.blocks, blockSearch, blockCategory])
  const blockCategories = useMemo(() => [
    'all', ...Array.from(new Set((question.blocks || []).map(block => block.category))).sort(),
  ], [question.blocks])

  const palette = useMemo(
    () => (question.palettes || []).find(p => p.id === pick.palette) || question.palettes?.[0],
    [question.palettes, pick.palette])
  const tokens = (palette || {})[pick.themeMode === 'dark' ? 'dark' : 'light'] || {}

  return (
    <Modal onClose={() => { }} className="max-w-[1120px]">
      <header className="flex items-center gap-2.5">
        <span className="grid size-8 place-items-center rounded-xl bg-accent/10 text-accent">
          <Palette className="size-4" />
        </span>
        <div>
          <h2 className="text-[15px] font-semibold text-ink">How should it look?</h2>
          <p className="mt-0.5 text-[11px] text-muted">
            {question.uiKit?.name || 'The selected UI framework'} is already in the scaffold. Planner suggestions are selected and marked; every available provider block remains open to you.
          </p>
        </div>
        <span className="flex-1" />
        <Countdown left={left} />
      </header>

      <section className="mt-4 rounded-2xl border border-line bg-canvas/40 p-3.5">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <label htmlFor="design-block-search" className="text-[11.5px] font-semibold text-ink">
              Provider blocks ({pick.blocks.length} selected · {(question.blocks || []).length} available)
            </label>
            <div className="relative mt-1.5">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted2" />
              <input id="design-block-search" value={blockSearch}
                     onChange={event => setBlockSearch(event.target.value)}
                     placeholder="Search all provider blocks"
                     className="h-9 w-full rounded-xl border border-line bg-panel pl-9 pr-3 text-[11.5px] text-ink outline-none focus:border-accent" />
            </div>
          </div>
          {blockCategories.length > 2 && (
            <div>
              <label htmlFor="design-block-category" className="text-[10px] font-semibold uppercase tracking-[.12em] text-muted2">
                Category
              </label>
              <select id="design-block-category" value={blockCategory}
                      onChange={event => setBlockCategory(event.target.value)}
                      className="mt-1.5 h-9 rounded-xl border border-line bg-panel px-3 text-[11px] text-ink outline-none focus:border-accent">
                {blockCategories.map(category => (
                  <option key={category} value={category}>
                    {category === 'all' ? 'All blocks' : category}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="rounded-xl border border-line bg-panel px-3 py-2 text-right">
            <span className="block text-[9.5px] text-muted2">UI framework</span>
            <span className="text-[11.5px] font-semibold text-ink">{question.uiKit?.name || 'Selected kit'}</span>
          </div>
        </div>
        <p className="mt-2 text-[10.5px] leading-relaxed text-muted2">
          Only real provider sources appear here. Suggested blocks match the request and approved plan; select as many additional blocks as the product needs.
        </p>
        {question.uiKit?.blockNote && (
          <p className="mt-2 rounded-lg border border-line bg-panel px-3 py-2 text-[10.5px] leading-relaxed text-muted2">
            {question.uiKit.blockNote}
          </p>
        )}
        <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {visibleBlocks.map(block => {
            const selected = pick.blocks.includes(block.id)
            return (
              <button key={block.id} type="button" onClick={() => toggleBlock(block.id)}
                      aria-pressed={selected}
                      className={cn('overflow-hidden rounded-xl border bg-panel text-left transition-colors',
                        selected ? 'border-accent ring-2 ring-accent/15' : 'border-line hover:border-line2')}>
                <span className="block aspect-[4/3] overflow-hidden border-b border-line bg-canvas">
                  <img src={block.preview} alt={`Preview of ${block.name}`}
                       loading="lazy" className="size-full object-cover" />
                </span>
                <span className="block p-3">
                  <span className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-[11.5px] font-semibold text-ink">{block.name}</span>
                    {block.recommended && (
                      <span className="rounded-md bg-accent/10 px-1.5 py-0.5 text-[9px] font-semibold text-accent">
                        Suggested
                      </span>
                    )}
                    <span className="rounded-md bg-tint px-1.5 py-0.5 text-[9px] font-medium text-deep">{block.category}</span>
                  </span>
                  <span className="mt-1.5 block text-[10px] leading-relaxed text-muted2">{block.description}</span>
                </span>
              </button>
            )
          })}
        </div>
        {!visibleBlocks.length && (
          <p className="py-8 text-center text-[11px] text-muted2">
            No provider block matches this search or filter.
          </p>
        )}
      </section>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_260px]">
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
              <Choices options={(question.fonts || []).map(f => ({ id: f.id, label: f.name }))}
                       value={pick.font} onChange={v => set('font', v)} />
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

          <Field label={`Optional screen additions (${pick.pages.length})`}>
            <p className="mb-2 text-[11px] leading-relaxed text-muted2">
              The approved plan already defines your screens. Select only additions you want.
            </p>
            <div className="flex flex-wrap gap-1">
              {(question.pages || []).map(page => (
                <button key={page.id} onClick={() => togglePage(page.id)} title={page.label}
                        className={cn('rounded-lg border px-2 py-1 text-[10.5px] transition-colors',
                          pick.pages.includes(page.id)
                            ? 'border-accent bg-accent/[.07] text-accent'
                            : 'border-line text-muted hover:text-ink')}>
                  {page.label}
                </button>
              ))}
            </div>
          </Field>
        </div>

        <Preview tokens={tokens} radius={pick.radius} question={question} pick={pick} />
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

/** The chosen tokens on something shaped like a page, not a swatch grid. */
function Preview({ tokens, radius, question, pick }) {
  const corner = (question.radii || []).find(r => r.id === radius)?.value || '8px'
  const font = (question.fonts || []).find(f => f.id === pick.font)
  return (
    <div className="overflow-hidden rounded-xl border border-line"
         style={{ background: tokens.background }}>
      <div className="p-3.5" style={{ fontFamily: font?.body }}>
        <p className="text-[13px] font-semibold" style={{ color: tokens.text, fontFamily: font?.heading }}>
          Your application
        </p>
        <p className="mt-1 text-[10.5px]" style={{ color: tokens.textMuted }}>
          This is how its surfaces and type will read.
        </p>
        <div className="mt-3 p-2.5"
             style={{ background: tokens.surface, borderRadius: corner,
                      border: `1px solid ${tokens.border}` }}>
          <p className="text-[11px]" style={{ color: tokens.text }}>A card on the page</p>
          <div className="mt-2 flex gap-1.5">
            <span className="px-2.5 py-1 text-[10.5px] font-semibold"
                  style={{ background: tokens.primary, color: tokens.onPrimary,
                           borderRadius: corner }}>
              Primary
            </span>
            <span className="px-2.5 py-1 text-[10.5px]"
                  style={{ background: tokens.surfaceAlt, color: tokens.text,
                           borderRadius: corner }}>
              Secondary
            </span>
          </div>
        </div>
        <div className="mt-2 flex gap-1.5">
          {['success', 'warning', 'danger'].map(role => (
            <span key={role} className="h-1.5 flex-1 rounded-full"
                  style={{ background: tokens[role] }} />
          ))}
        </div>
      </div>
    </div>
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

/** A catalogue row renders as its own id: they are already the human word. */
const ids = (rows) => (rows || []).map(row => ({ id: row.id, label: row.id }))

const Choices = ({ options, value, onChange }) => (
  <div className="flex flex-wrap gap-1">
    {options.map(option => (
      <button key={option.id} onClick={() => onChange(option.id)}
              className={cn('rounded-lg border px-2 py-1 text-[10.5px] capitalize transition-colors',
                value === option.id ? 'border-accent bg-accent/[.07] text-accent'
                                    : 'border-line text-muted hover:text-ink')}>
        {option.label}
      </button>
    ))}
  </div>
)
