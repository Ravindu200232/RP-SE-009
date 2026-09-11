'use client'

import { useEffect, useRef, useState } from 'react'
import { Eye, Code2, FileText, FlaskConical, Plus, Rocket, Layers } from 'lucide-react'
import { useStore } from '@/lib/store'
import { answerQuestion, connect, send } from '@/lib/ws'
import { forgetConsole } from '@/lib/console-log'
import { api } from '@/lib/api'
import { catalogue, TIERS } from '@/lib/models'
import { readFolder } from '@/lib/importer'
import Sidebar from '@/components/Sidebar'
import Home from '@/components/Home'
import ProjectsView from '@/components/ProjectsView'
import PreviewPane from '@/components/PreviewPane'
import PrototypePane from '@/components/PrototypePane'
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
  { id: 'prototype', label: 'Prototype', Icon: Layers },
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
  const busyProject = useStore(s => s.busyProject)
  const testsRunning = useStore(s => s.tests.running)
  const qa = useStore(s => s.qaReport)
  const setQa = useStore(s => s.setQaReport)
  const liveFile = useStore(s => s.liveFile)

  const [projects, setProjects] = useState([])
  const [cat, setCat] = useState(() => catalogue(null))
  const [screen, setScreen] = useState('home')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const opening = useRef(0)

  const refreshProjects = () => api.projects()
    .then(r => {
      const list = Array.isArray(r) ? r : (r.projects || [])
      setProjects(list)
      return list
    })
    .catch(() => [])

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
      const known = new Set([...c.cloud, ...(c.local || [])].map(m => m.id))
      api.settings().then(s => {
        const fallback = TIERS.medium.model
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
        useStore.setState({ models: {
          ...now,
          planner: now.planner || TIERS.medium.model,
          design: now.design || TIERS.medium.model,
          builder: now.builder || TIERS.medium.model,
        } })
      })
    }).catch(() => { })
    return disconnect
  }, [])

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

  const currentProjectObj = projects.find(p => p.name === project)
  const specOnly = Boolean(currentProjectObj?.spec_only) && busyProject !== project
  const prototypeOnly = Boolean(currentProjectObj?.prototype_only) && busyProject !== project

  let tabs = TABS
  if (specOnly) {
    tabs = TABS.filter(tab => tab.id === 'srs')
  } else if (prototypeOnly) {
    tabs = TABS.filter(tab => tab.id === 'prototype')
  }

  useEffect(() => {
    if (liveFile) setScreen('workspace')
  }, [liveFile])

  const drawing = useStore(s => s.drawing)

  useEffect(() => {
    if (drawing && view !== 'prototype') setView('prototype')
  }, [drawing, view, setView])

  useEffect(() => {
    if (specOnly && view !== 'srs') setView('srs')
    else if (prototypeOnly && view !== 'prototype') setView('prototype')
  }, [specOnly, prototypeOnly, view, setView])

  async function openProject(name, row = null) {
    const st = useStore.getState()
    if (!name || (st.opening && st.project === name)) return
    const request = ++opening.current
    const rowObj = row || projects.find(p => p.name === name)

    if (st.project === name && st.runtimes[name]?.status === 'running') {
      try {
        st.setRuntime(await api.open(name))
        if (opening.current === request) {
          setScreen('workspace')
          if (rowObj?.spec_only) setView('srs')
          else if (rowObj?.prototype_only) setView('prototype')
          else setView('preview')
        }
      } catch (error) {
        if (opening.current === request) st.addLog('WARN', `Could not open app: ${error.message}`)
      }
      return
    }

    st.reset(name)
    setScreen('workspace')

    if (rowObj?.spec_only) setView('srs')
    else if (rowObj?.prototype_only) setView('prototype')
    else setView('preview')

    st.setOpening(true)
    st.setProgress(`Opening ${name}…`, 0)
    forgetConsole()

    api.session(name)
      .then(({ stats }) => {
        if (stats && Object.keys(stats).length
            && useStore.getState().project === name) useStore.getState().setRunStats(stats)
      })
      .catch(() => { })

    api.stream(name)
      .then(({ stream }) => {
        const store = useStore.getState()
        if (store.project !== name) return
        if (stream?.logs?.length || stream?.chat?.length) store.adoptStream(stream)
      })
      .catch(() => { })

    let opened = false
    try {
      const runtime = await api.open(name)
      useStore.getState().setRuntime(runtime)
      opened = true

      const raw = await retry(() => api.files(name), 4, 700)
      if (opening.current !== request || useStore.getState().project !== name) return

      const out = {}
      for (const [path, v] of Object.entries(raw || {})) {
        out[path] = typeof v === 'string' ? v : (v?.content ?? '')
      }
      useStore.getState().setFiles(out)
      useStore.getState().setOpening(false)
    } catch (e) {
      if (opening.current !== request) return
      useStore.getState().addLog('WARN', `could not open ${name}: ${e.message}`)
      useStore.getState().setOpening(false)
      if (!opened) useStore.getState().setRuntime({ ...useStore.getState().runtimes[name],
        project: name, status: 'failed', error: e.message })
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
    <div className="flex h-full w-full overflow-hidden bg-bg text-ink">
      <Sidebar
        projects={projects}
        onOpen={openProject}
        onImport={importFolder}
        onSettings={() => setSettingsOpen(true)}
        onZip={downloadZip}
        onResume={resumeBuild}
        screen={screen}
        onScreenChange={setScreen}
        onDeleted={(name) => {
          refreshProjects()
          if (project === name) setScreen('home')
        }}
      />

      <AgentDecision />

      {settingsOpen && (
        <SettingsModal onClose={() => setSettingsOpen(false)}
                       onSaved={() => api.models().then(r => setCat(catalogue(r)))
                                         .catch(() => { })} />
      )}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-panel">
        {/* Workspace Top Navbar */}
        <div className="flex h-[48px] shrink-0 items-center gap-2 border-b border-line bg-panel/95 px-4 backdrop-blur-md">
          {screen === 'home' && (
            <span className="flex items-center rounded-full bg-white/[.05] border border-white/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[.14em] text-white/60">
              New project
            </span>
          )}
          {screen === 'projects' && (
            <span className="flex items-center rounded-full bg-white/[.05] border border-white/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-[.14em] text-white/60">
              Projects
            </span>
          )}

          {screen === 'workspace' && (
            <div className="flex items-center gap-1 rounded-full bg-panel2/80 p-0.5 border border-line">
              {tabs.map(({ id, label, Icon }) => (
                <button key={id} onClick={() => setView(id)}
                        className={cn('inline-flex h-7 items-center gap-1.5 rounded-full px-3',
                          'font-display text-[11px] font-semibold transition-all',
                          view === id ? 'bg-accent/15 text-accent shadow-sm ring-1 ring-accent/30 dark:bg-white/10 dark:text-ink dark:ring-white/10'
                                      : 'text-muted hover:bg-black/[.03] hover:text-ink dark:hover:bg-white/5')}>
                  <Icon className="size-3.5 shrink-0" />
                  {label}
                  {id === 'testing' && unitStatus?.failed > 0
                    && !(busy && (!busyProject || busyProject === project)) && (
                    <Badge tone="bad">{unitStatus.failed}</Badge>
                  )}
                </button>
              ))}
            </div>
          )}

          <span className="flex-1" />

          {/* Action to Build full app from SRS-only project */}
          {screen === 'workspace' && specOnly && !busy && (
            <button
              onClick={resumeBuild}
              title="Build this application from the approved SRS"
              className="inline-flex h-9 items-center gap-2 rounded-full bg-accent px-4 text-[11.5px] font-semibold text-white shadow-md transition-all hover:bg-press mr-2"
            >
              <Rocket className="size-[13px]" /> Build Now
            </button>
          )}

          {/* Action to Build full app from Prototype-only project */}
          {screen === 'workspace' && prototypeOnly && !busy && (
            <button
              onClick={resumeBuild}
              title="Build full application from this prototype"
              className="inline-flex h-9 items-center gap-2 rounded-full bg-blue-600 px-4 text-[11.5px] font-semibold text-white shadow-md transition-all hover:bg-blue-500 mr-2"
            >
              <Rocket className="size-[13px]" /> Build App Now
            </button>
          )}

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
          <Home modelOptions={cat.all} onStarted={() => setScreen('workspace')}
                onKept={async (name) => {
                  const list = await refreshProjects()
                  openProject(name, list.find(p => p.name === name))
                }} />
        ) : screen === 'projects' ? (
          <ProjectsView
            projects={projects}
            activeProject={project}
            busyProject={busyProject}
            onOpen={(name, p) => openProject(name, p)}
            onCreateNew={() => setScreen('home')}
            onDelete={(name) => {
              refreshProjects()
              if (project === name) setScreen('home')
            }}
            onBuildProject={(name, p) => {
              openProject(name, p)
              setTimeout(resumeBuild, 400)
            }}
          />
        ) : (
          <div className="flex min-h-0 flex-1 bg-bg/40">
            <AgentChat />

            <div className="relative flex min-w-0 flex-1 flex-col">
              <ScopeQuestion />

              <PreviewPane key={`preview-${project}`} hidden={view !== 'preview'} onBuild={resumeBuild} />
              <PrototypePane key={`proto-${project}`} project={project} hidden={view !== 'prototype'} onBuild={resumeBuild} />
              <CodePane hidden={view !== 'code'} />
              {view === 'testing' && <TestingResult key={`testing-${project}`} />}
              {view === 'srs' && (
                <SrsResult key={`srs-${project}`} specOnly={specOnly}
                           onBuild={resumeBuild} />
              )}
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
