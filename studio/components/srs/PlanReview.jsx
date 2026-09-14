'use client'

import { useEffect, useState } from 'react'
import {
  ArrowLeft, Check, ChevronDown, Loader2, MessageCircleMore, PencilLine,
  Route, ShieldCheck, Sparkles, UsersRound, Workflow,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { Button, TextArea } from '../ui'
import SrsActivity from './SrsActivity'
import { cn } from '@/lib/utils'

export default function PlanReview({ projectId, onGenerated, onCancel }) {
  const addLog = useStore(s => s.addLog)
  const [state, setState] = useState(null)
  const [phase, setPhase] = useState('loading')
  const [revision, setRevision] = useState('')
  const [error, setError] = useState('')
  const [waited, setWaited] = useState(0)
  const [full, setFull] = useState(false)
  const [hasSrs, setHasSrs] = useState(false)
  const [replies, setReplies] = useState({})
  const [dirty, setDirty] = useState(false)

  async function generate(text) {
    setPhase(text ? 'revising' : 'loading')
    setWaited(0)
    setError('')
    try {
      setState(await api.srs(`/projects/${projectId}/plan`, { revision: text || '' }))
      setRevision('')
      setReplies({})
      if (text) setDirty(true)
      setPhase('ready')
    } catch (e) {
      setError(e.message)
      setPhase('ready')
    }
  }

  useEffect(() => {
    let live = true
    ;(async () => {
      setPhase('loading')
      try {
        const pending = await api.resumeSrs(`/projects/${projectId}/generate-srs`)
        if (!live) return
        if (pending.resumed) { onGenerated?.(projectId); return }
        const existing = await api.srs(`/projects/${projectId}/plan`)
        if (!live) return
        if (existing?.plan) {
          setState(existing)
          setPhase('ready')
          return
        }
      } catch { }
      if (live) await generate('')
    })()
    return () => { live = false }
  }, [projectId])

  useEffect(() => {
    if (!['loading', 'revising', 'generating'].includes(phase)) return
    const id = setInterval(() => setWaited(v => v + 1), 1000)
    return () => clearInterval(id)
  }, [phase])

  useEffect(() => {
    let live = true
    api.srs(`/projects/${projectId}`).then(d => { if (live) setHasSrs(Boolean(d?.srs)) }).catch(() => { })
    return () => { live = false }
  }, [projectId])

  async function accept() {
    if (hasSrs && !dirty) return onGenerated?.(projectId)
    setPhase('generating')
    setWaited(0)
    setError('')
    try {
      await api.srs(`/projects/${projectId}/plan/approve`, {})
      await api.srs(`/projects/${projectId}/generate-srs`, {})
      addLog('INFO', 'SRS written — read it before anything is built')
      onGenerated?.(projectId)
    } catch (e) {
      setError(e.message)
      setPhase('ready')
    }
  }

  if (phase === 'loading' && !state) return <SrsActivity phase="reviewing" seconds={waited} message="Turning the interview into a clear plan you can approve…" />
  if (phase === 'generating') return <SrsActivity phase="generating" seconds={waited} message="Writing the specification, traceability and diagrams…" />

  const body = state?.plan || {}
  const open = (body.open_questions || []).filter(q => String(q?.question || '').trim())
  const blocking = open.filter(q => q.required)
  const answeredCount = open.filter(q => (replies[q.question] || '').trim()).length
  const screens = body.screens || []
  const users = body.users || []
  const records = body.records || []
  const workflows = body.workflows || []
  const features = body.features || []
  const assumptions = body.assumptions || []
  const settled = state?.approved || state?.can_approve
  const why = state?.reason || ''

  const stat = [
    { label: 'screens', value: screens.length },
    { label: 'roles', value: users.length },
    { label: 'workflows', value: workflows.length },
    { label: 'features', value: features.length },
  ]

  return (
    <div className="mx-auto w-full max-w-[1040px] pb-8 text-white">
      <div className="mb-6 flex items-center gap-3">
        <button onClick={onCancel} className="grid size-9 place-items-center rounded-xl border border-white/10 bg-white/[.04] text-white/70 transition hover:bg-white/[.08] hover:text-white"><ArrowLeft className="size-4" /></button>
        <div>
          <p className="font-display text-[11px] font-bold uppercase tracking-[.18em] text-blue-400">Plan review</p>
          <p className="mt-0.5 text-[13px] text-white/60">Check the structure before the specification is written.</p>
        </div>
        <span className="flex-1" />
        {state?.version != null && <span className="rounded-full border border-white/10 bg-white/[.05] px-3 py-1 text-[11px] font-medium text-white/70">Version {state.version}{(state.versions || []).length > 1 ? ` of ${state.versions.length}` : ''}</span>}
      </div>

      <section className="overflow-hidden rounded-2xl border border-white/10 bg-[linear-gradient(135deg,#0e1526_0%,#131c33_50%,#1d284a_100%)] p-7 text-white shadow-2xl">
        <div className="flex flex-wrap items-start gap-6">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-[.18em] text-blue-300"><Sparkles className="size-3.5" /> Product blueprint</div>
            <h2 className="mt-3 font-display text-[30px] font-bold tracking-tight text-white">{body.app_name || 'Your app'}</h2>
            <p className="mt-2 max-w-[680px] text-[13.5px] leading-relaxed text-white/70">{body.product_intent || 'Your interview has been turned into an implementation plan.'}</p>
            {body.customer_notes && <p className="mt-3 max-w-[680px] text-[12px] italic leading-relaxed text-white/50">“{body.customer_notes}”</p>}
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-xl border border-white/10 bg-white/[.04] px-5 py-4 backdrop-blur-xl">
            {stat.map(x => <div key={x.label}><div className="font-display text-[22px] font-bold tabular-nums text-white">{x.value}</div><div className="text-[10px] font-semibold uppercase tracking-[.14em] text-white/40">{x.label}</div></div>)}
          </div>
        </div>
      </section>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        {users.length > 0 && <Section icon={UsersRound} title="Who uses it" subtitle="Roles and what each person can do">
          <div className="space-y-2.5">{users.map((u, i) => <div key={i} className="rounded-xl border border-white/5 bg-white/[.03] px-4 py-3"><p className="text-[12.5px] font-semibold text-white">{u.role || u.name || String(u)}</p>{(u.can_do || []).length > 0 && <p className="mt-1 text-[11px] leading-relaxed text-white/60">{u.can_do.join(' · ')}</p>}</div>)}</div>
        </Section>}

        {screens.length > 0 && <Section icon={Route} title="App spaces" subtitle="Pages and who can reach them">
          <div className="space-y-2">{screens.map((sc, i) => <div key={i} className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[.02] px-3 py-2.5 transition hover:bg-white/[.05]"><span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-blue-500/15 border border-blue-500/20 text-[11px] font-bold text-blue-400">{i + 1}</span><div className="min-w-0"><p className="text-[12.5px] font-semibold text-white">{sc.name}</p><p className="mt-0.5 text-[11px] leading-relaxed text-white/60">{sc.purpose || 'App page'}{(sc.who || []).length ? ` · ${(sc.who || []).join(', ')}` : ''}</p></div></div>)}</div>
        </Section>}

        {workflows.length > 0 && <Section icon={Workflow} title="User journeys" subtitle="How the important work moves through the app">
          <div className="space-y-3">{workflows.map((w, i) => <div key={i} className="rounded-xl border border-white/5 bg-white/[.03] px-4 py-3"><p className="text-[12.5px] font-semibold text-white">{w.name}</p><ol className="mt-2 space-y-1.5 text-[11px] leading-relaxed text-white/60">{(w.steps || []).map((step, j) => <li key={j} className="flex gap-2"><span className="font-semibold text-blue-400">{j + 1}.</span><span>{step}</span></li>)}</ol></div>)}</div>
        </Section>}

        {features.length > 0 && <Section icon={ShieldCheck} title="Feature promise" subtitle="Everything the finished app must actually do">
          <div className="space-y-2">{features.map((f, i) => <div key={i} className="flex gap-3 rounded-xl border border-white/5 bg-white/[.02] px-3 py-2.5"><span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-md bg-emerald-500/15 border border-emerald-500/25 text-emerald-400"><Check className="size-3" /></span><p className="text-[12px] leading-relaxed text-white/80">{f}</p></div>)}</div>
        </Section>}
      </div>

      {(records.length > 0 || body.look_and_feel || assumptions.length > 0) && (
        <section className="mt-4 rounded-2xl border border-white/10 bg-[#121622]/80 p-5 shadow-xl backdrop-blur-xl">
          <div className="grid gap-5 md:grid-cols-3">
            {records.length > 0 && <Mini title="Data"><p className="space-y-1 text-[11.5px] leading-relaxed text-white/60">{records.map((r, i) => <span key={i} className="block"><b className="font-semibold text-white">{r.name}</b>{(r.keeps || []).length ? ` — ${r.keeps.join(', ')}` : ''}</span>)}</p></Mini>}
            {body.look_and_feel && <Mini title="Look & feel"><p className="text-[11.5px] leading-relaxed text-white/60">{body.look_and_feel}</p></Mini>}
            {assumptions.length > 0 && <Mini title="Assumptions"><ul className="space-y-1 text-[11.5px] leading-relaxed text-white/60">{assumptions.map((a, i) => <li key={i}>• {a}</li>)}</ul></Mini>}
          </div>
        </section>
      )}

      {state?.markdown && (
        <div className="mt-4 rounded-2xl border border-white/10 bg-[#121622]/60 p-1">
          <button onClick={() => setFull(v => !v)} className="flex w-full items-center gap-2 rounded-xl px-4 py-3 text-[11.5px] font-semibold text-white/60 transition hover:bg-white/[.05] hover:text-white"><ChevronDown className={cn('size-3.5 transition-transform', !full && '-rotate-90')} /> Full technical plan</button>
          {full && <pre className="max-h-[380px] overflow-auto whitespace-pre-wrap break-words px-4 pb-4 font-mono text-[11px] leading-[1.7] text-white/80">{state.markdown}</pre>}
        </div>
      )}

      {open.length > 0 && (
        <section className="mt-5 rounded-2xl border border-blue-500/20 bg-[linear-gradient(180deg,rgba(37,99,235,.08),rgba(18,22,34,.95))] p-5 shadow-xl backdrop-blur-xl">
          <div className="flex items-start gap-3"><span className="grid size-9 place-items-center rounded-xl bg-blue-600 text-white shadow-md shadow-blue-500/30"><MessageCircleMore className="size-4" /></span><div><p className="text-[14px] font-bold text-white">{blocking.length ? `${blocking.length} details still matter` : 'A few optional details'}</p><p className="mt-0.5 text-[11.5px] text-white/60">Answer them like a conversation. The planner rewrites only the relevant part.</p></div></div>
          <div className="mx-auto mt-5 max-w-[760px] space-y-5">
            {open.map((q, i) => <div key={q.question || i}>
              <div className="flex items-end gap-3"><span className="grid size-7 place-items-center rounded-lg bg-accent/20 border border-accent/30 text-[9px] font-bold text-accent">AF</span><div className="max-w-[78%] rounded-2xl rounded-bl-sm border border-white/10 bg-[#121622] px-4 py-3 text-[12.5px] leading-relaxed text-white shadow-sm">{q.question}</div></div>
              {(q.options || []).length > 0 && <div className="ml-10 mt-2.5 flex flex-wrap gap-2">{q.options.map(opt => { const on = (replies[q.question] || '').trim() === opt; return <button key={opt} disabled={phase === 'revising'} onClick={() => setReplies(r => ({ ...r, [q.question]: on ? '' : opt }))} className={cn('rounded-full px-3.5 py-1.5 text-[11.5px] font-medium transition', on ? 'bg-blue-600 text-white border border-blue-400 shadow-md shadow-blue-500/25' : 'border border-white/10 bg-white/[.05] text-white/80 hover:bg-white/[.1] hover:text-white')}>{opt}</button> })}</div>}
              <div className="ml-auto mt-2 max-w-[72%] rounded-2xl rounded-br-sm border border-white/10 bg-[#121622]/90 px-3.5 py-2.5 shadow-sm"><TextArea rows={2} value={replies[q.question] || ''} placeholder="Your answer…" disabled={phase === 'revising'} onChange={e => setReplies(r => ({ ...r, [q.question]: e.target.value }))} className="w-full resize-none bg-transparent text-[12px] leading-relaxed text-white outline-none placeholder:text-white/40" /></div>
            </div>)}
          </div>
          <div className="mt-5 flex justify-end"><Button variant="solid" className="rounded-xl bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/25" disabled={!answeredCount || phase === 'revising'} onClick={() => generate(composeAnswers(open, replies, revision))}>{phase === 'revising' ? <><Loader2 className="size-3 animate-spin" /> Updating…</> : <><Check className="size-3" /> Apply {answeredCount} answer{answeredCount === 1 ? '' : 's'}</>}</Button></div>
        </section>
      )}

      <section className="mt-5 rounded-2xl border border-white/10 bg-[#121622]/80 p-5 shadow-xl backdrop-blur-xl">
        <div className="flex items-center gap-2"><PencilLine className="size-4 text-blue-400" /><p className="text-[12.5px] font-semibold text-white">Change anything in the plan</p></div>
        <TextArea value={revision} rows={3} placeholder="For example: add a wishlist, rename the admin area, or change the checkout flow…" onChange={e => setRevision(e.target.value)} className="mt-3 w-full resize-none rounded-xl border border-white/10 bg-white/[.03] px-4 py-3 text-[12.5px] leading-relaxed text-white outline-none focus:border-blue-500/50 placeholder:text-white/40 caret-blue-400" />
        <div className="mt-3 flex justify-end"><Button variant="outline" className="rounded-xl border-white/10 bg-white/[.05] text-white/80 hover:bg-white/[.1] hover:text-white" disabled={!revision.trim() || phase === 'revising'} onClick={() => generate(revision.trim())}>{phase === 'revising' ? <><Loader2 className="size-3 animate-spin" /> Updating…</> : 'Update plan'}</Button></div>
      </section>

      {error && <p className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-[12px] text-red-300">{error}</p>}

      <div className="sticky bottom-4 mt-6 rounded-2xl border border-white/15 bg-[#121622]/95 p-4 shadow-2xl backdrop-blur-2xl">
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="font-display text-[13px] font-bold text-white">{settled ? 'This plan is ready for your approval.' : (why || 'A required detail is still missing.')}</p>
            <p className="mt-0.5 text-[11px] text-white/50">Nothing is built from this plan until you approve it.</p>
          </div>
          <button disabled={!settled || phase === 'revising'} onClick={accept} className="inline-flex h-11 items-center gap-2 rounded-xl bg-blue-600 px-6 text-[12.5px] font-semibold text-white shadow-lg shadow-blue-500/30 transition hover:bg-blue-500 disabled:opacity-40">
            <Check className="size-4" />{hasSrs && !dirty ? 'Open specification' : hasSrs ? 'Rewrite specification' : 'Approve & write SRS'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Section({ icon: Icon, title, subtitle, children }) {
  return (
    <section className="rounded-2xl border border-white/10 bg-[#121622]/80 p-5 shadow-xl backdrop-blur-xl">
      <div className="mb-4 flex items-start gap-3">
        <span className="grid size-9 place-items-center rounded-xl bg-blue-500/15 border border-blue-500/20 text-blue-400"><Icon className="size-4" /></span>
        <div><p className="font-display text-[13.5px] font-bold text-white">{title}</p><p className="mt-0.5 text-[11px] text-white/50">{subtitle}</p></div>
      </div>
      {children}
    </section>
  )
}

function Mini({ title, children }) { return <div><p className="mb-2 text-[10px] font-semibold uppercase tracking-[.14em] text-label">{title}</p>{children}</div> }

function composeAnswers(open, replies, extra) {
  const pairs = open.map(q => [q.question, (replies[q.question] || '').trim()]).filter(([, a]) => a).map(([q, a]) => `- ${q}\n  ANSWER: ${a}`)
  const parts = []
  if (pairs.length) {
    parts.push('Answers to the open questions in the plan:', pairs.join('\n'))
    parts.push('Fold each answer into the plan and drop that question from open_questions. Leave everything else as it stands.')
  }
  const rest = String(extra || '').trim()
  if (rest) parts.push('Also change this:', rest)
  return parts.join('\n\n')
}
