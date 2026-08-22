'use client'

import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Loader2, Sparkles } from 'lucide-react'
import { useStore } from '@/lib/store'
import { send } from '@/lib/ws'
import { api } from '@/lib/api'
import { Button, TextArea } from './ui'
import { cn } from '@/lib/utils'
import { useAttachments } from '@/lib/use-attachments'
import { AttachButtons, AttachList } from './srs/Attachments'
import LogoPanel from './LogoPanel'
import Interview from './srs/Interview'
import PlanReview from './srs/PlanReview'
import SrsReview from './srs/SrsReview'


const EXAMPLES = [
  { label: 'Darkroom co-op',
    text: 'A community darkroom with three roles. MEMBER: browses sessions with '
        + 'photos, filters by film type, books a bench for a session on a date, '
        + 'and sees their own bookings with any balance owed. TECHNICIAN: sees '
        + 'only their own bench — today\u2019s jobs in time order, marks one done '
        + 'with a form, and records the chemicals used. MANAGER: the only role '
        + 'that sees money and stock. Each screen is its own page under its '
        + 'role\u2019s section. Seed enough data that every screen has something on '
        + 'it, and one demo user of each role.' },
  { label: 'Bike workshop',
    text: 'A neighbourhood bicycle workshop. RIDER: browses repair slots, books '
        + 'one, and sees their bookings. MECHANIC: today\u2019s repairs in time '
        + 'order, marks a repair done, records the parts used, and has a page '
        + 'for warranty claims. TREASURER: dues paid and unpaid this month, and '
        + 'the parts bin with reorder levels. Seed real data and a demo user for '
        + 'each role.' },
  { label: 'Small hotel',
    text: 'A boutique hotel site. A guest browses rooms with photos, checks '
        + 'availability for a date range and books one. An admin sees every '
        + 'booking, can change a room\u2019s price and mark a booking paid. Seed a '
        + 'handful of rooms and bookings, and a demo user of each role.' },
]

export default function Home({ onStarted }) {
  const s = useStore()
  const { agentMode, images, think, models, srsId, srsPhase } = s
  const [prompt, setPrompt] = useState('')
  const [logoFor, setLogoFor] = useState(null)
  const [srsError, setSrsError] = useState('')
  const box = useRef(null)
  const attach = useAttachments()

  function begin(p, srs = '') {
    if (!p) return
    if (agentMode && images) return setLogoFor({ idea: p, srs })
    startBuild(p, '', srs)
  }

  function submit() {
    begin(prompt.trim())
  }

  function startBuild(p, logo, srs = '') {
    setLogoFor(null)
    s.reset(null)
    s.setBusy(true)
    s.setProgress('Starting…', 0)
    onStarted?.()
    if (agentMode) {
      s.addLog('INFO', `🤖 Agent mode — ${models.agent}`)
      if (logo) s.addLog('INFO', '🖼 Building around the logo you accepted')
      if (srs) s.addLog('INFO', '📄 Building from the SRS you approved')
      send({ type: 'agent_build', prompt: p, model: models.agent,
             think, qa_model: models.qa, logo, srs_id: srs || '' })
    } else {
      send({ type: 'build', prompt: p,
             refine_model: models.refine, build_model: models.build })
    }
  }

  async function planFirst() {
    const idea = prompt.trim()
    const files = attach.items.length
    if (!idea && !files) return box.current?.focus()
    setSrsError('')
    s.setSrs({ srsPhase: 'planning', srsBusy: 'Reading your idea…' })
    try {

      await api.saveSettings({ srs_model: models.srs || models.agent || '' })
        .catch(() => { })
      // A project has to exist before anything can be attached to it, and the
      // idea is required — so somebody who uploaded a spec and typed nothing
      // still gets a project, with the document as the thing that describes it.
      const created = await api.srs('/projects', { idea: idea || 'See the attached files.' })
      const id = created.project.id

      if (files) {
        // Before `analyze`, not after: the questions are generated from the
        // brief, and the brief is the idea plus every source. Attaching the
        // price list after the questions exist means being asked what is on it.
        s.setSrs({ srsId: id, srsBusy: `Reading your ${files === 1 ? 'attachment' : `${files} attachments`}…` })
        const { ids, failed } = await attach.upload(id)

        // Nothing typed and nothing readable is nothing to plan from, so say so
        // rather than interview them about an idea that does not exist. With an
        // idea typed, a failed attachment is a warning: the rest still works.
        if (failed && !ids.length && !idea) {
          throw new Error(files === 1
            ? 'that file could not be read, and there is nothing typed to go on'
            : 'none of those files could be read, and there is nothing typed to go on')
        }
        if (failed) {
          s.addLog('WARN', `⚠ ${failed} of ${files} attachments could not be read — `
                         + 'carrying on with the rest.')
        }
      }

      s.setSrs({ srsId: id, srsBusy: 'Working out what to ask you…' })
      await api.srs(`/projects/${id}/analyze`, {})
      s.setSrs({ srsPhase: 'interview', srsBusy: '' })
    } catch (e) {
      setSrsError(e.message)
      s.resetSrs()
    }
  }

  function acceptSrs(handoffPrompt, id) {
    s.setSrs({ srsPhase: 'idle', srsBusy: '' })
    setPrompt(handoffPrompt)
    setTimeout(() => begin(handoffPrompt, id), 900)
  }

  if (srsPhase === 'review' && srsId) {
    return (
      <SrsReview projectId={srsId}
                 onApproved={acceptSrs}
                 onBack={() => s.setSrs({ srsPhase: 'plan' })} />
    )
  }

  return (
    <div className="relative flex min-h-0 flex-1 items-center justify-center
                    overflow-auto px-6">
      <div aria-hidden
           className="pointer-events-none absolute inset-x-0 top-0 h-[380px] opacity-[0.06]
                      [background:radial-gradient(60%_100%_at_50%_0%,var(--accent),transparent_70%)]" />

      <div className="relative w-full max-w-[680px] py-10">
        {/* The full lockup goes here and nowhere smaller. It carries the
            wordmark, the taglines and a detailed illustration — at 34px in the
            sidebar all of that is a smudge, which is why the mark cropped to
            the hexagon is what goes there. Here there is room for it, and the
            heading it replaces said the same words in worse type. */}
        <div className="mb-7 text-center">
          <img src="/__agentforge/agentforge-logo.png"
               alt="AgentForge Studio — AI-powered full stack app builder"
               className="mx-auto h-auto w-full max-w-[330px] select-none" />
          <p className="mx-auto mt-3 max-w-[420px] text-[13px] leading-relaxed text-muted">
            Describe an app. It gets planned, written, tested, repaired and
            served — and you watch every step.
          </p>
        </div>

        {srsPhase === 'interview' && srsId && (
          <Interview projectId={srsId}
                     onDone={() => s.setSrs({ srsPhase: 'plan' })}
                     onCancel={() => s.resetSrs()} />
        )}
        {srsPhase === 'plan' && srsId && (
          <PlanReview projectId={srsId}
                      onGenerated={() => s.setSrs({ srsPhase: 'review' })}
                      onCancel={() => s.setSrs({ srsPhase: 'interview' })} />
        )}
        {srsPhase === 'planning' && (
          <div className="rounded-panel border border-line bg-panel p-8 text-center">
            <Loader2 className="mx-auto mb-3 size-5 animate-spin text-accent" />
            <p className="text-[12.5px] text-ink">{s.srsBusy || 'Working…'}</p>
          </div>
        )}

        {srsPhase === 'idle' && (<>
        <div className="rounded-panel border border-line bg-panel p-2
                        transition-colors focus-within:border-accent/40">
          <TextArea value={prompt} autoFocus rows={5} ref={box}
                    placeholder="A community darkroom with three roles: members book sessions, technicians run the bench, a manager sees the money…"
                    onChange={e => setPrompt(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit()
                    }}
                    className="min-h-[100px] w-full resize-none bg-transparent p-2.5
                               text-[13px] leading-relaxed text-ink outline-none
                               placeholder:text-muted2" />
          <AttachList attach={attach} className="mx-2.5 mb-1.5" />

          <div className="flex items-center gap-1.5 px-2.5 pb-1 pt-0.5">
            <AttachButtons attach={attach} />
            <span className="min-w-0 flex-1 truncate font-mono text-[10px] text-muted">
              {agentMode ? models.agent : `${models.refine} → ${models.build}`}
              {think ? ' · thinking' : ''}{images ? ' · images' : ''}
            </span>
            <kbd className="hidden font-mono text-[9.5px] text-muted2 sm:block">⌘↵</kbd>
            <Button variant="outline" onClick={planFirst}
                    title="Answer a few questions first, and get a written spec before anything is built">
              <Sparkles className="size-3" /> Plan it first
            </Button>
            <Button variant="solid" size="icon" disabled={!prompt.trim()}
                    onClick={submit}>
              <ArrowUp className="size-3.5" />
            </Button>
          </div>
        </div>

        {attach.items.length > 0 && (
          <p className="mt-2 text-center text-[11px] text-muted">
            Attachments are read into the specification — press{' '}
            <b className="font-medium text-ink">Plan it first</b>. Building
            straight from the box uses only what you typed.
          </p>
        )}

        {srsError && srsPhase === 'idle' && (
          <p className="mt-2 text-center text-[11px] text-bad">
            The SRS could not start — {srsError}
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <span className="text-[10px] text-muted2">Try:</span>
          {EXAMPLES.map(e => (
            <button key={e.label} onClick={() => setPrompt(e.text)}
                    className={cn('rounded-full border border-line bg-panel px-3 py-1',
                      'text-[10.5px] text-muted transition-colors',
                      'hover:border-accent/40 hover:text-ink')}>
              {e.label}
            </button>
          ))}
        </div>
        </>)}
      </div>

      {logoFor && (
        <LogoPanel idea={logoFor.idea} model={models.agent}
                   onAccept={(file) => startBuild(logoFor.idea, file, logoFor.srs)}
                   onSkip={() => startBuild(logoFor.idea, '', logoFor.srs)} />
      )}
    </div>
  )
}
