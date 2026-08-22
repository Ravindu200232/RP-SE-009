'use client'

import { useEffect, useState } from 'react'
import { ArrowLeft, Check, ChevronDown, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { Badge, Button, Panel, Table, TD, TH, TR, TextArea } from '../ui'
import { Waiting } from './Interview'

export default function PlanReview({ projectId, onGenerated, onCancel }) {
  const addLog = useStore(s => s.addLog)
  const [state, setState] = useState(null)
  const [phase, setPhase] = useState('loading')
  const [revision, setRevision] = useState('')
  const [error, setError] = useState('')
  const [waited, setWaited] = useState(0)
  const [full, setFull] = useState(false)
  const [hasSrs, setHasSrs] = useState(false)

  const [dirty, setDirty] = useState(false)

  async function generate(text) {
    setPhase(text ? 'revising' : 'loading')
    setError('')
    try {
      setState(await api.srs(`/projects/${projectId}/plan`, { revision: text || '' }))
      setRevision('')
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
      setError('')
      try {
        const existing = await api.srs(`/projects/${projectId}/plan`)
        if (!live) return
        if (existing?.plan) {
          setState(existing)
          setPhase('ready')
          return
        }
      } catch {  }
      if (live) await generate('')
    })()
    return () => { live = false }
  }, [projectId])

  useEffect(() => {
    if (phase !== 'generating') return
    const t = setInterval(() => setWaited(w => w + 1), 1000)
    return () => clearInterval(t)
  }, [phase])

  useEffect(() => {
    let live = true
    api.srs(`/projects/${projectId}`)
      .then(d => { if (live) setHasSrs(Boolean(d?.srs)) })
      .catch(() => {  })
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
      addLog('INFO', '📄 SRS written — read it before anything is built')
      onGenerated?.(projectId)
    } catch (e) {
      setError(e.message)
      setPhase('ready')
    }
  }

  if (phase === 'loading' && !state) {
    return <Waiting sub="Turning everything you said into a plan you can check before anything is built.">
      Writing the plan…
    </Waiting>
  }
  if (phase === 'generating') {
    return <Waiting sub={`Writing the specification, the diagrams and the PDF. This usually takes one to three minutes — ${waited}s so far.`}>
      Building the SRS…
    </Waiting>
  }

  const body = state?.plan || {}
  const blocking = (body.open_questions || []).filter(q => q.required)
  const screens = body.screens || []
  const users = body.users || []
  const records = body.records || []
  const workflows = body.workflows || []
  const features = body.features || []
  const assumptions = body.assumptions || []

  const settled = state?.approved || state?.can_approve
  const why = state?.reason || ''

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <button onClick={onCancel}
                className="flex items-center gap-1 text-[11px] text-muted2 hover:text-ink">
          <ArrowLeft className="size-3" /> Back
        </button>
        <span className="flex-1" />
        {state?.version != null && (
          <Badge tone="mute">
            v{state.version}{(state.versions || []).length > 1
              ? ` of ${state.versions.length}` : ''}
          </Badge>
        )}
        <span className="font-mono text-[10px] text-muted2">
          {screens.length} screens · {users.length} roles · {records.length} records
        </span>
      </div>

      <Panel className="p-5">
        <p className="font-display text-[16px] font-bold text-ink">
          {body.app_name || 'Your app'}
        </p>
        <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted">
          {body.product_intent}
        </p>

        {body.customer_notes && (
          <p className="mt-3 border-l-2 border-line pl-3 text-[12px]
                        italic leading-relaxed text-muted">
            “{body.customer_notes}”
          </p>
        )}

        {users.length > 0 && (
          <Block label="WHO USES IT">
            <ul className="space-y-1.5">
              {users.map((u, i) => (
                <li key={i} className="text-[12px] leading-relaxed">
                  <b className="font-semibold text-ink">{u.role || u.name || String(u)}</b>
                  {(u.can_do || []).length > 0 && (
                    <span className="text-muted"> — {u.can_do.join(', ')}</span>
                  )}
                </li>
              ))}
            </ul>
          </Block>
        )}

        {screens.length > 0 && (
          <Block label="SCREENS">
            <Table>
              <thead><TR><TH>Screen</TH><TH>What it is for</TH><TH>Who</TH></TR></thead>
              <tbody>
                {screens.map((sc, i) => (
                  <TR key={i}>
                    <TD>{sc.name}</TD>
                    <TD className="text-muted">{sc.purpose || '—'}</TD>
                    <TD className="text-muted">{(sc.who || []).join(', ') || '—'}</TD>
                  </TR>
                ))}
              </tbody>
            </Table>
          </Block>
        )}

        {records.length > 0 && (
          <Block label="WHAT IT KEEPS TRACK OF">
            <ul className="space-y-1">
              {records.map((r, i) => (
                <li key={i} className="text-[12px] leading-relaxed text-ink">
                  <b className="font-semibold">{r.name}</b>
                  {(r.keeps || []).length > 0 && (
                    <span className="text-muted"> — {r.keeps.join(', ')}</span>
                  )}
                </li>
              ))}
            </ul>
          </Block>
        )}

        {workflows.length > 0 && (
          <Block label="HOW THE WORK FLOWS">
            <ul className="space-y-2">
              {workflows.map((w, i) => (
                <li key={i} className="text-[12px] leading-relaxed">
                  <b className="font-semibold text-ink">{w.name}</b>
                  <ol className="mt-0.5 list-decimal pl-5 text-muted">
                    {(w.steps || []).map((s, j) => <li key={j}>{s}</li>)}
                  </ol>
                </li>
              ))}
            </ul>
          </Block>
        )}

        {features.length > 0 && (
          <Block label="WHAT IT DOES">
            <ul className="space-y-1">
              {features.map((f, i) => (
                <li key={i} className="text-[12px] leading-relaxed text-ink">• {f}</li>
              ))}
            </ul>
          </Block>
        )}

        {body.look_and_feel && (
          <Block label="LOOK AND FEEL">
            <p className="text-[12px] leading-relaxed text-muted">{body.look_and_feel}</p>
          </Block>
        )}

        {assumptions.length > 0 && (
          <Block label="THINGS WE ASSUMED">
            <ul className="space-y-1">
              {assumptions.map((a, i) => (
                <li key={i} className="text-[12px] leading-relaxed text-muted">• {a}</li>
              ))}
            </ul>
          </Block>
        )}
      </Panel>

      {state?.markdown && (
        <Panel className="mt-3 p-4">
          <button onClick={() => setFull(f => !f)}
                  className="flex w-full items-center gap-1.5 text-[11px]
                             font-medium text-muted2 hover:text-ink">
            <ChevronDown className={`size-3 transition-transform ${full ? '' : '-rotate-90'}`} />
            THE PLAN IN FULL
          </button>
          {full && (
            <pre className="mt-3 whitespace-pre-wrap break-words font-mono
                            text-[11.5px] leading-relaxed text-ink">
              {state.markdown}
            </pre>
          )}
        </Panel>
      )}

      {blocking.length > 0 && (
        <Panel className="mt-3 border-warn/30 p-4">
          <p className="text-[11px] font-medium text-warn">
            STILL TO SETTLE ({blocking.length})
          </p>
          <ul className="mt-1.5 space-y-1">
            {blocking.map((q, i) => (
              <li key={i} className="text-[12px] leading-relaxed text-ink">{q.question}</li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-muted">
            Answer these below and the plan will be rewritten around them.
          </p>
        </Panel>
      )}

      <div className="mt-3 rounded-panel border border-line bg-panel p-2">
        <TextArea value={revision} rows={2}
                  placeholder={blocking.length
                    ? 'Answer the open questions, or describe any other change…'
                    : 'Want something changed? Describe it and the plan is rewritten…'}
                  onChange={e => setRevision(e.target.value)}
                  className="w-full resize-none bg-transparent p-2 text-[12.5px]
                             leading-relaxed text-ink outline-none
                             placeholder:text-muted2" />
        <div className="flex items-center gap-2 px-2 pb-1">
          <span className="flex-1" />
          <Button variant="outline" disabled={!revision.trim() || phase === 'revising'}
                  onClick={() => generate(revision.trim())}>
            {phase === 'revising'
              ? <><Loader2 className="size-3 animate-spin" /> Rewriting…</>
              : 'Rewrite the plan'}
          </Button>
        </div>
      </div>

      {error && <p className="mt-3 text-[11.5px] text-bad">{error}</p>}

      <Button variant="solid" className="mt-4 w-full justify-center py-2.5"
              disabled={!settled || phase === 'revising'}
              onClick={accept}>
        <Check className="size-3.5" />
        {!settled ? (why || 'Not ready yet')
          : hasSrs && !dirty ? 'Back to the specification'
          : hasSrs ? 'Rewrite the specification from this plan'
          : 'Approve the plan and write the SRS'}
      </Button>
      <p className="mt-2 text-center text-[10.5px] text-muted2">
        {hasSrs && !dirty
          ? 'Your specification is safe — this only takes you back to it.'
          : hasSrs
            ? 'The plan changed, so the specification is written again from it. '
              + 'Revisions you made to the old one stay in its history.'
            : 'The specification is written next. You read it, change anything '
              + 'you want, and nothing is built until you approve it.'}
      </p>
    </div>
  )
}

function Block({ label, children }) {
  return (
    <div className="mt-4">
      <p className="mb-1.5 text-[11px] font-medium text-muted2">{label}</p>
      {children}
    </div>
  )
}
