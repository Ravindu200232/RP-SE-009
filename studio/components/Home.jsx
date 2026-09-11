'use client'

import { useEffect, useRef, useState } from 'react'
import {
  ArrowRight, ChevronDown, Languages, PencilLine, Sparkles, FileText, Layers,
  FlaskConical, Rocket,
} from 'lucide-react'
import { useStore, KEYS } from '@/lib/store'
import { send } from '@/lib/ws'
import { api } from '@/lib/api'
import { TextArea } from './ui'
import { cn } from '@/lib/utils'
import { useAttachments } from '@/lib/use-attachments'
import { AttachButtons, AttachList } from './srs/Attachments'
import LogoPanel from './LogoPanel'
import BuildSetup from './BuildSetup'
import Interview from './srs/Interview'
import PlanReview from './srs/PlanReview'
import SrsReview from './srs/SrsReview'
import SrsActivity from './srs/SrsActivity'
import { displaySrsLanguages, SRS_LANGUAGES } from '@/lib/languages'
import { TIERS, tierDisplayName } from '@/lib/models'

const EXAMPLES = [
  {
    label: 'Darkroom co-op',
    blurb: 'Three roles — member, technician, manager. Benches, chemicals, money.',
    text: 'A community darkroom with three roles. MEMBER: browses sessions with '
        + 'photos, filters by film type, books a bench for a session on a date, '
        + 'and sees their own bookings with any balance owed. TECHNICIAN: sees '
        + 'only their own bench — today\u2019s jobs in time order, marks one done '
        + 'with a form, and records the chemicals used. MANAGER: the only role '
        + 'that sees money and stock. Each screen is its own page under its '
        + 'role\u2019s section. Seed enough data that every screen has something on '
        + 'it, and one demo user of each role.',
  },
  {
    label: 'Bike workshop',
    blurb: 'Rider bookings, a mechanic’s day, dues and the parts bin.',
    text: 'A neighbourhood bicycle workshop. RIDER: browses repair slots, books '
        + 'one, and sees their bookings. MECHANIC: today\u2019s repairs in time '
        + 'order, marks a repair done, records the parts used, and has a page '
        + 'for warranty claims. TREASURER: dues paid and unpaid this month, and '
        + 'the parts bin with reorder levels. Seed real data and a demo user for '
        + 'each role.',
  },
  {
    label: 'Small hotel',
    blurb: 'Rooms with photos, availability by date, an admin who sees every booking.',
    text: 'A boutique hotel site. A guest browses rooms with photos, checks '
        + 'availability for a date range and books one. An admin sees every '
        + 'booking, can change a room\u2019s price and mark a booking paid. Seed a '
        + 'handful of rooms and bookings, and a demo user of each role.',
  },
]

function attachToken() {
  const raw = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`
  return raw.replace(/[^a-z0-9]/gi, '').slice(0, 24)
}

export default function Home({ onStarted, onKept, modelOptions = [] }) {
  const s = useStore()
  const { images, think, models, srsId, srsPhase } = s
  const [prompt, setPrompt] = useState('')
  const [activeMode, setActiveMode] = useState('app')
  const [logoFor, setLogoFor] = useState(null)
  const [srsError, setSrsError] = useState('')
  const [srsLanguage, setSrsLanguage] = useState('en')
  const [stack, setStack] = useState('')
  const [languageOptions, setLanguageOptions] = useState(SRS_LANGUAGES)
  const box = useRef(null)
  const attach = useAttachments()
  const builderModel = models.builder || models.agent || TIERS.medium.model
  const plannerModel = models.planner || models.agent || builderModel
  const designModel = models.design || models.agent || builderModel

  useEffect(() => { setLanguageOptions(displaySrsLanguages()) }, [])

  function begin(p, srs = '', prototypeOnly = false) {
    if (!p || !builderModel.trim()) return
    const config = { model: builderModel.trim(), stack, think }
    chooseModel(config.model)
    if (images && !prototypeOnly) return setLogoFor({ idea: p, srs, config })
    startBuild(p, '', srs, null, config, prototypeOnly)
  }

  function chooseModel(model) {
    const roles = ['agent', 'planner', 'design', 'builder']
    useStore.setState(state => ({
      models: {
        ...state.models,
        ...Object.fromEntries(roles.map(role => [role, model])),
      },
    }))
    for (const role of roles) s.persist(KEYS[role], model)
  }

  function chooseThinking(value) {
    useStore.setState({ think: value })
    s.persist(KEYS.think, value ? '1' : '0')
  }

  function submit() {
    begin(prompt.trim(), '', false)
  }

  function submitPrototype() {
    begin(prompt.trim(), '', true)
  }

  async function startBuild(p, logo, srs = '', uploads = null, config = null, prototypeOnly = false) {
    setLogoFor(null)
    s.reset(null)
    s.setBusy(true)

    let token = ''
    if (attach.items.length) {
      const wanted = attachToken()
      s.setProgress(attach.items.length === 1
        ? 'Sending your attachment…' : `Sending your ${attach.items.length} attachments…`, 0)
      const { staged, failed } = await attach.stage(wanted)
      if (failed) {
        s.addLog('WARN', `${failed} attachment(s) could not be sent — building with what did arrive.`)
      }
      if (staged) {
        token = wanted
        s.addLog('INFO', `${staged} attachment(s) go into the build`)
      }
    }

    s.setProgress('Starting…', 0)
    onStarted?.()
    const selected = config?.model || builderModel
    s.addLog('INFO', `Build mode — ${tierDisplayName(selected)} · Thinking — ${(config?.think ?? think) ? 'on' : 'off'}`)
    if (prototypeOnly) s.addLog('INFO', '🎨 Prototype Build mode — generating interactive HTML prototype first')
    if (logo) s.addLog('INFO', 'Building around the logo you accepted')
    if (srs) s.addLog('INFO', 'Building from the SRS you approved')

    send({
      type: 'agent_build',
      prompt: p,
      model: selected,
      builder_model: selected,
      planner_model: config?.model || plannerModel,
      design_model: config?.model || designModel,
      stack: config?.stack || stack,
      think: config?.think ?? think,
      qa_model: models.qa,
      logo,
      srs_id: srs || '',
      attachments: token || undefined,
      uploads: uploads && Object.keys(uploads).length ? uploads : undefined,
      prototype_only: Boolean(prototypeOnly),
    })
  }

  async function planFirst() {
    const idea = prompt.trim()
    const files = attach.items.length
    if (!idea && !files) return box.current?.focus()
    setSrsError('')
    s.setSrs({ srsPhase: 'planning', srsBusy: 'Reading your idea…' })
    try {
      const created = await api.srs('/projects', {
        idea: idea || 'See the attached files.',
        language: languageOptions.find(item => item.code === srsLanguage)?.name || srsLanguage,
      })
      const id = created.project.id

      if (files) {
        s.setSrs({ srsId: id, srsBusy: `Reading your ${files === 1 ? 'attachment' : `${files} attachments`}…` })
        const { ids, failed } = await attach.upload(id)

        if (failed && !ids.length && !idea) {
          throw new Error(files === 1
            ? 'that file could not be read, and there is nothing typed to go on'
            : 'none of those files could be read, and there is nothing typed to go on')
        }
        if (failed) {
          s.addLog('WARN', `${failed} of ${files} attachments could not be read — carrying on with the rest.`)
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
    setTimeout(() => begin(handoffPrompt, id, false), 900)
  }

  if (srsPhase === 'review' && srsId) {
    return (
      <SrsReview projectId={srsId}
                 onApproved={acceptSrs}
                 onKept={(project) => { s.resetSrs(); setPrompt(''); onKept?.(project) }}
                 onBack={() => s.setSrs({ srsPhase: 'plan' })} />
    )
  }

  if (srsPhase === 'interview' && srsId) {
    return (
      <Interview projectId={srsId}
                 onDone={() => s.setSrs({ srsPhase: 'plan' })}
                 onCancel={() => s.resetSrs()} />
    )
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-y-auto bg-[radial-gradient(circle_at_50%_15%,#152e68_0%,#0c152a_38%,#080c16_100%)] px-6 py-10 text-white">
      <div className="relative mx-auto my-auto w-full max-w-[940px]">
        {/* Bolt.new Style Hero */}
        <div className="text-center">
          <h1 className="font-display text-[46px] font-bold tracking-tight text-white md:text-[56px] leading-[1.08]">
            What will you build today?
          </h1>
          <p className="mt-3 text-[16px] text-white/65">
            Create stunning apps & websites by chatting with AI.
          </p>
        </div>

        {srsPhase === 'plan' && srsId && (
          <div className="mt-6">
            <PlanReview projectId={srsId}
                        onGenerated={() => s.setSrs({ srsPhase: 'review' })}
                        onCancel={() => s.setSrs({ srsPhase: 'interview' })} />
          </div>
        )}
        {srsPhase === 'planning' && (
          <div className="mt-6">
            <SrsActivity phase="planning" message={s.srsBusy || 'Reading your idea…'} />
          </div>
        )}

        {srsPhase === 'idle' && (
          <>
            {/* Main Central Prompt Box */}
            <div className="mt-8 overflow-hidden rounded-[26px] border border-white/15 bg-[#121622]/90 shadow-2xl backdrop-blur-2xl transition-all focus-within:border-blue-500/60 focus-within:shadow-[0_20px_60px_rgba(37,99,235,.2)]">
              <TextArea
                value={prompt}
                autoFocus
                rows={4}
                ref={box}
                aria-label="Describe your app"
                placeholder={
                  activeMode === 'srs'
                    ? 'Describe your project for SRS interview & specification generation...'
                    : activeMode === 'prototype'
                    ? 'Describe the prototype you want to generate (interactive HTML preview)...'
                    : 'How can AgentForge help you today? Describe an app, prototype, or SRS...'
                }
                onChange={e => setPrompt(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                    if (activeMode === 'srs') planFirst()
                    else if (activeMode === 'prototype') submitPrototype()
                    else submit()
                  }
                }}
                className="min-h-[130px] w-full resize-none bg-transparent p-5 text-[15px] leading-[1.6] text-white caret-blue-400 outline-none placeholder:text-white/40"
              />

              {/* Build Setup Configurations */}
              <div className="border-t border-white/10 px-5 pt-3 pb-2">
                <BuildSetup
                  model={builderModel}
                  stack={stack}
                  think={think}
                  options={modelOptions}
                  onModelChange={chooseModel}
                  onStackChange={setStack}
                  onThinkChange={chooseThinking}
                />
              </div>

              <AttachList attach={attach} className="mx-5 mb-2" />

              {/* Bottom Action Row with Attachments, Prettified Language Selector & Submit */}
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 bg-white/[.02] p-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <AttachButtons attach={attach} cell />

                  {/* Prettified Language Select Pill */}
                  <div
                    className="relative inline-flex h-9 items-center rounded-xl border border-white/10 bg-white/[.06] pl-3 pr-2 text-[11px] font-semibold text-white/90 shadow-sm transition-all hover:bg-white/[.12] hover:border-white/20 hover:text-white group"
                    title="Interview language. SRS and builder handoff stay in English."
                  >
                    <Languages className="size-3.5 shrink-0 text-blue-400 transition-colors group-hover:text-blue-300 mr-1.5" aria-hidden="true" />
                    <span className="sr-only">Interview language</span>
                    <select
                      id="srs-language"
                      value={srsLanguage}
                      onChange={event => setSrsLanguage(event.target.value)}
                      className="h-full bg-transparent appearance-none text-white/90 text-[11.5px] font-medium pr-5 outline-none cursor-pointer focus:outline-none"
                    >
                      {languageOptions.map(language => (
                        <option key={language.code} value={language.code} className="bg-[#121622] text-white">
                          {language.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="pointer-events-none absolute right-2.5 size-3 shrink-0 text-white/50 transition-colors group-hover:text-white" />
                  </div>
                </div>

                {/* Right Action: Clean Bolt-style Submit Button */}
                <button
                  disabled={!prompt.trim() || !builderModel.trim()}
                  onClick={() => {
                    if (activeMode === 'srs') planFirst()
                    else if (activeMode === 'prototype') submitPrototype()
                    else submit()
                  }}
                  title={
                    activeMode === 'srs'
                      ? 'SRS Generate: answer interview questions and get a complete software specification'
                      : activeMode === 'prototype'
                      ? 'Prototype Build: generate an interactive HTML prototype'
                      : 'App Build: generate full stack application with planner, design, builder, and testing'
                  }
                  className="inline-flex h-9 items-center gap-2 rounded-xl bg-blue-600 px-4 font-display text-[12.5px] font-semibold text-white shadow-lg shadow-blue-500/25 transition-all hover:bg-blue-500 active:scale-95 disabled:pointer-events-none disabled:opacity-40"
                >
                  <span>
                    {activeMode === 'srs' ? 'Generate SRS' : activeMode === 'prototype' ? 'Build Prototype' : 'Build App'}
                  </span>
                  <ArrowRight className="size-3.5" />
                </button>
              </div>
            </div>

            {srsError && srsPhase === 'idle' && (
              <p className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-[12px] text-red-300">
                The SRS could not start — {srsError}
              </p>
            )}

            {/* Quick-Start Mode Cards: SRS Generate | Prototype Build | App Build */}
            <div className="mt-7 flex flex-wrap items-center justify-center gap-4">
              {[
                {
                  id: 'srs',
                  label: 'SRS Generate',
                  desc: 'Interview & Spec',
                  Icon: FileText,
                  badge: 'Planning',
                  iconColor: 'text-amber-400',
                  iconBg: 'bg-amber-500/15 ring-1 ring-amber-500/25',
                  activeBorder: 'border-amber-500/50 bg-[#141a26] shadow-amber-500/10 ring-1 ring-amber-500/30',
                  onClick: () => {
                    setActiveMode('srs')
                    if (!prompt.trim() && !attach.items.length) {
                      box.current?.focus()
                      return
                    }
                    chooseModel(builderModel)
                    planFirst()
                  },
                },
                {
                  id: 'prototype',
                  label: 'Prototype Build',
                  desc: 'Fast UI Preview',
                  Icon: FlaskConical,
                  badge: 'Preview',
                  iconColor: 'text-purple-400',
                  iconBg: 'bg-purple-500/15 ring-1 ring-purple-500/25',
                  activeBorder: 'border-purple-500/50 bg-[#141a26] shadow-purple-500/10 ring-1 ring-purple-500/30',
                  onClick: () => {
                    setActiveMode('prototype')
                    if (!prompt.trim()) {
                      box.current?.focus()
                      return
                    }
                    submitPrototype()
                  },
                },
                {
                  id: 'app',
                  label: 'App Build',
                  desc: 'Full-Stack Code',
                  Icon: Rocket,
                  badge: 'Full Stack',
                  iconColor: 'text-blue-400',
                  iconBg: 'bg-blue-500/15 ring-1 ring-blue-500/25',
                  activeBorder: 'border-blue-500/50 bg-[#141a26] shadow-blue-500/10 ring-1 ring-blue-500/30',
                  onClick: () => {
                    setActiveMode('app')
                    if (!prompt.trim()) {
                      box.current?.focus()
                      return
                    }
                    submit()
                  },
                },
              ].map(card => {
                const isSelected = activeMode === card.id
                return (
                  <button
                    key={card.id}
                    type="button"
                    onClick={card.onClick}
                    className={cn(
                      "group relative flex flex-col items-center justify-center rounded-2xl border p-3.5 transition-all duration-200 hover:-translate-y-0.5 w-[136px] h-[98px] shadow-lg",
                      isSelected
                        ? card.activeBorder
                        : "border-white/10 bg-[#121622]/70 hover:border-white/20 hover:bg-[#121622] hover:shadow-xl"
                    )}
                  >
                    <div className={cn(
                      "flex size-9 items-center justify-center rounded-xl transition-transform group-hover:scale-110",
                      card.iconBg
                    )}>
                      <card.Icon className={cn("size-5", card.iconColor)} />
                    </div>
                    <span className="mt-2 text-[12px] font-semibold text-white/90 group-hover:text-white">
                      {card.label}
                    </span>
                    <span className="text-[10.5px] text-white/45 group-hover:text-white/70">
                      {card.desc}
                    </span>
                  </button>
                )
              })}
            </div>

            {/* Starter Briefs / Inspirations */}
            <div className="mt-8">
              <div className="text-center text-[12px] font-semibold text-white/50 mb-3">
                or start from one of these
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {EXAMPLES.map(e => (
                  <button
                    key={e.label}
                    onClick={() => setPrompt(e.text)}
                    className="rounded-2xl border border-white/10 bg-[#121622]/50 p-4 text-left shadow-sm transition-all hover:border-white/20 hover:bg-[#121622]/90 hover:shadow-md"
                  >
                    <div className="font-display text-[13.5px] font-bold text-white">
                      {e.label}
                    </div>
                    <div className="mt-1 text-[11px] leading-[1.5] text-white/50">
                      {e.blurb}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {logoFor && (
        <LogoPanel
          idea={logoFor.idea}
          model={designModel}
          onAccept={(file, uploads) => startBuild(logoFor.idea, file, logoFor.srs, uploads, logoFor.config, false)}
          onSkip={(uploads) => startBuild(logoFor.idea, '', logoFor.srs, uploads, logoFor.config, false)}
        />
      )}
    </div>
  )
}
