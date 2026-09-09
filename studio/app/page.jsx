'use client'

import { useEffect, useState } from 'react'
import { Eye, Code2, FileText, FlaskConical, Plus, Rocket } from 'lucide-react'
import { useStore } from '@/lib/store'
import { answerQuestion, connect, send } from '@/lib/ws'
import { forgetConsole } from '@/lib/console-log'
import { api } from '@/lib/api'
import { catalogue } from '@/lib/models'
import { readFolder } from '@/lib/importer'
import Sidebar from '@/components/Sidebar'
import Home from '@/components/Home'
import PreviewPane from '@/components/PreviewPane'
import CodePane from '@/components/CodePane'
import SettingsModal from '@/components/SettingsModal'
import TestingResult from '@/components/testing/TestingResult'
import SrsResult from '@/components/srs/SrsResult'
import DeployPanel from '@/components/deploy/DeployPanel'
import AgentChat from '@/components/AgentChat'
import AgentDecision from '@/components/AgentDecision'
import { Badge, Button } from '@/components/ui'
import { cn } from '@/lib/utils'
import { projectUnitTestStatus } from '@/lib/test-counts'


const TABS = [

  { id: 'srs', label: 'SRS', Icon: FileText },
  { id: 'preview', label: 'Preview', Icon: Eye },
  { id: 'code', label: 'Code', Icon: Code2 },
  { id: 'testing', label: 'Testing', Icon: FlaskConical },

  { id: 'deploy', label: 'Deploy', Icon: Rocket },
]


async function retry(fn, times, waitMs) {
  let last
  for (let i = 0; i < times; i++) {
    try { return await fn() } catch (e) {
      last = e
      await new Promise(r => setTimeout(r, waitMs))
    }
  }
  throw last
}

/** Show a paused picker question and its answers. */
function ScopeQuestion() {
  const question = useStore(s => s.question)
  if (!question) return null

  const routes = question.routes || []
  return (
    <div className="mb-2 border-l-[3px] border-accent bg-tint p-2.5">
      <p className="text-[12px] leading-relaxed text-ink">
        <b className="font-semibold">{question.file}</b> is on {routes.length} route
        {routes.length === 1 ? '' : 's'}, not just{' '}
        {question.route || 'this page'} — which did you mean?
      </p>
      {routes.length > 0 && (
        <p className="mt-1 truncate font-mono text-[10px] text-muted"
           title={routes.join(', ')}>
          {routes.join(' · ')}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {(question.options || []).map((option, i) => (
          <button key={option} title={option}
                  onClick={() => answerQuestion(option)}
                  className="border border-line2 bg-panel px-2.5 py-1
                             text-left text-[11px] font-semibold text-ink
                             transition-colors hover:border-accent hover:text-accent">
            {i === 0 ? `${question.route || 'This page'} only`
                     : `All ${routes.length} routes`}
          </button>
        ))}
        <button onClick={() => useStore.setState({ question: null })}
                className="px-1.5 text-[11px] text-muted hover:text-ink">
          Leave it
        </button>
      </div>
    </div>
  )
}


export default function Studio() {
  const view = useStore(s => s.view)
  const setView = useStore(s => s.setView)
  const project = useStore(s => s.project)
  const busy = useStore(s => s.busy)
  const testsRunning = useStore(s => s.tests.running)
  const qa = useStore(s => s.qaReport)
  const setQa = useStore(s => s.setQaReport)
  const liveFile = useStore(s => s.liveFile)

  const [projects, setProjects] = useState([])
  const [cat, setCat] = useState(() => catalogue(null))
  const [screen, setScreen] = useState('home')
  const [settingsOpen, setSettingsOpen] = useState(false)

  const refreshProjects = () => api.projects()
    .then(r => setProjects(Array.isArray(r) ? r : (r.projects || [])))
    .catch(() => { })

  // The socket cannot call refreshProjects.
  const projectsStamp = useStore(s => s.projectsStamp)
  useEffect(() => {
    if (projectsStamp) refreshProjects()
  }, [projectsStamp])

  useEffect(() => {

    useStore.getState().hydrate()
    const disconnect = connect()
    refreshProjects()
    api.models().then(r => {
      const c = catalogue(r)
      setCat(c)

      const cur = useStore.getState().models
      if (cur.planner && cur.design && cur.builder) return
      // Fill only roles this browser has not chosen. Server-side role settings
      // fall back to the former single Agent setting during migration.
      const known = new Set([...c.cloud, ...(c.local || [])].map(m => m.id))
      api.settings().then(s => {
        const fallback = c.cloud[0]?.id || ''
        const legacy = String(s?.agent_model || '').trim()
        const pick = value => {
          const saved = String(value || legacy).trim()
          return (saved && known.has(saved)) ? saved : fallback
        }
        const now = useStore.getState().models
        useStore.setState({ models: {
          ...now,
          planner: now.planner || pick(s?.planner_model),
          design: now.design || pick(s?.design_model),
          builder: now.builder || pick(s?.builder_model),
        } })
      }).catch(() => {
        const now = useStore.getState().models
        if (!c.cloud[0]) return
        useStore.setState({ models: {
          ...now,
          planner: now.planner || c.cloud[0].id,
          design: now.design || c.cloud[0].id,
          builder: now.builder || c.cloud[0].id,
        } })
      })
    }).catch(() => { })
    return disconnect
  }, [])

  // Preview and the persistent tab bar need the same final suite report as
  // Testing/Deploy. Streamed test_result events include repair retries and E2E
  // stages, so their accumulated failure count is not a unit-test count.
  useEffect(() => {
    if (!project || testsRunning || qa?.project === project) return
    let active = true
    retry(() => api.qa(project), 4, 700).then(report => {
      const current = useStore.getState()
      if (active && current.project === project && !current.tests.running) {
        setQa(report)
      }
    }).catch(() => { })
    return () => { active = false }
  }, [project, testsRunning, qa?.project, setQa])

  const unitStatus = projectUnitTestStatus(qa, project)

  // A run brings the workspace up.
  useEffect(() => {
    if (liveFile) setScreen('workspace')
  }, [liveFile])

  async function openProject(name) {
    const st = useStore.getState()
    st.reset(name)
    useStore.setState({ project: name })
    setScreen('workspace')

    // Busy from the click, not from the first file.
    st.setBusy(true)
    st.setOpening(true)
    st.setProgress(`Opening ${name}…`, 0)
    st.addLog('INFO', `Opening ${name}`)

    // The previous project's console errors are not this one's evidence.
    forgetConsole()

    // The status line is fed by events, and events only arrive while a run is
    // going. A project whose conversation is alive but idle showed nothing at
    // all, then came back at zero on the next message — which read as the
    // context having been thrown away when it had not.
    api.session(name)
      .then(({ stats }) => {
        if (stats && Object.keys(stats).length
            && useStore.getState().project === name) useStore.getState().setRunStats(stats)
      })
      .catch(() => { /* an older backend has no session to report */ })

    try {
      await api.open(name)

      const raw = await retry(() => api.files(name), 4, 700)

      const out = {}
      for (const [path, v] of Object.entries(raw || {})) {
        out[path] = typeof v === 'string' ? v : (v?.content ?? '')
      }
      useStore.getState().setFiles(out)
    } catch (e) {
      useStore.getState().addLog('WARN', `could not open ${name}: ${e.message}`)
      useStore.getState().setBusy(false)
    }
  }

  function resumeBuild() {
    const st = useStore.getState()
    const name = st.project
    if (!name || st.busy) return
    st.setBusy(true)
    st.setProgress('Resuming…', 0)
    st.addLog('INFO', `Resuming ${name} — picking up where it stopped`)
    setScreen('workspace')
    send({ type: 'agent_resume', project: name,
           model: st.models.builder || st.models.agent,
           builder_model: st.models.builder || st.models.agent,
           planner_model: st.models.planner || st.models.agent,
           design_model: st.models.design || st.models.agent,
           think: st.think,
           qa_model: st.models.qa })
  }

  async function importFolder(list) {
    const s = useStore.getState()
    setScreen('workspace')
    s.reset(null)
    s.setBusy(true)
    s.setStatus('busy', 'importing…')
    try {
      const { name, title, files, skipped } = await readFolder(list, (done, total) => {
        if (done % 25 === 0 || done === total) {
          s.setProgress(`Reading ${done}/${total}…`, Math.round(done / total * 60))
        }
      })
      s.addLog('INFO', `${Object.keys(files).length} file(s) to import`
                     + (skipped ? `, ${skipped} skipped` : ''))
      const r = await api.uploadProject({ name, title, files })
      const imported = r.project || r.name || name
      s.addLog('SUCCESS', `Imported ${imported}`)
      s.setBusy(false)
      s.setStatus('live', 'ready')
      await refreshProjects()
      await openProject(imported)
    } catch (e) {
      s.addLog('ERROR', 'Import failed: ' + e.message)
      s.setBusy(false)
      s.setStatus('disconnected', 'import failed')
    }
  }

  async function downloadZip() {
    const st = useStore.getState()
    if (!st.project) return
    try {
      const { default: JSZip } = await import('jszip')
      const zip = new JSZip()
      for (const [path, body] of Object.entries(st.files)) zip.file(path, body)
      const blob = await zip.generateAsync({ type: 'blob' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = st.project + '.zip'
      a.click()
      URL.revokeObjectURL(url)
      st.addLog('SUCCESS', `Downloaded ${st.project}.zip`)
    } catch (e) {
      st.addLog('WARN', 'Could not build the zip: ' + e.message)
    }
  }

  return (
    <div className="flex h-full bg-[radial-gradient(circle_at_20%_0%,#f8faff_0%,#edf1f7_42%,#e7ebf3_100%)] p-2.5 dark:bg-[radial-gradient(circle_at_20%_0%,#1a2030_0%,#111722_42%,#0c1119_100%)]">
      <Sidebar models={cat} projects={projects} onOpen={openProject}
               onImport={importFolder} onSettings={() => setSettingsOpen(true)}
               onZip={downloadZip} onResume={resumeBuild}
               onDeleted={(name) => {
                 refreshProjects()
                 if (project === name) setScreen('home')
               }} />

      <AgentDecision />

      {settingsOpen && (
        <SettingsModal onClose={() => setSettingsOpen(false)}
                       onSaved={() => api.models().then(r => setCat(catalogue(r)))
                                        .catch(() => { })} />
      )}

      <div className="ml-2.5 flex min-w-0 flex-1 flex-col overflow-hidden rounded-[30px] bg-panel/92 shadow-[0_28px_75px_rgba(30,41,59,.13)] ring-1 ring-white/75 backdrop-blur-2xl dark:shadow-[0_28px_75px_rgba(0,0,0,.42)] dark:ring-white/[.055]">
        {/* macOS-style workspace tabs. */}
        <div className="flex h-[60px] shrink-0 items-center gap-1.5 border-b border-line/55 bg-white/48 px-4 backdrop-blur-2xl dark:bg-white/[.02]">
          {screen === 'home' && (
            <span className="flex items-center rounded-full bg-panel2 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[.16em] text-label">
              New project
            </span>
          )}
          {screen === 'workspace' && TABS.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => setView(id)}
                    className={cn('inline-flex h-9 items-center gap-[7px] rounded-full px-3.5',
                      'font-display text-[11px] font-semibold transition-all',
                      view === id ? 'bg-white/90 text-ink shadow-[0_5px_16px_rgba(30,41,59,.08)] ring-1 ring-black/[.04] dark:bg-white/10 dark:ring-white/[.06]'
                                  : 'text-muted hover:bg-white/55 hover:text-ink dark:hover:bg-white/5')}>
              <Icon className="size-[13px] shrink-0" />
              {label}
              {id === 'testing' && unitStatus?.failed > 0 && (
                <Badge tone="bad">{unitStatus.failed}</Badge>
              )}
            </button>
          ))}
          <span className="flex-1" />
          {screen === 'home' && !busy && (
            <span className="flex items-center px-5 font-mono text-[10.5px] text-muted2">
              ⌘↵ to build
            </span>
          )}
          {busy && (
            <span className="flex items-center gap-2 rounded-full bg-accent/10 px-3 py-1.5 text-[11px] font-medium text-accent">
              <span className="size-1.5 animate-pulse bg-accent" />
              working
            </span>
          )}
          {screen === 'workspace' && (
            <button onClick={() => {

                      useStore.getState().resetSrs()
                      setScreen('home')
                    }}
                    className="inline-flex h-9 items-center gap-2 rounded-full bg-white/72 px-3.5 text-[11px] font-semibold text-ink shadow-sm ring-1 ring-line/70 transition-all hover:bg-white dark:bg-white/5 dark:hover:bg-white/10">
              <Plus className="size-[13px]" /> New
            </button>
          )}
        </div>

        {screen === 'home' ? (
          <Home modelOptions={cat.all} onStarted={() => setScreen('workspace')} />
        ) : (
          <div className="flex min-h-0 flex-1 bg-bg/40">
            {/* The conversation sits beside the work rather than on top of
                it. As a drawer it covered the thing it was describing, and
                collapsing it to get the preview back hid the agent. */}
            <AgentChat />

            <div className="relative flex min-w-0 flex-1 flex-col">
              <ScopeQuestion />

              <PreviewPane key={`preview-${project}`} hidden={view !== 'preview'} />
              <CodePane hidden={view !== 'code'} />
              {view === 'testing' && <TestingResult key={`testing-${project}`} />}
              {view === 'srs' && <SrsResult key={`srs-${project}`} />}
              {view === 'deploy' && (
                <DeployPanel key={`deploy-${project}`}
                             onSettings={() => setSettingsOpen(true)} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
