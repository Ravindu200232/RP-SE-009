'use client'

import { useEffect, useState } from 'react'
import { Eye, Code2, FileText, FlaskConical, Plus, Rocket } from 'lucide-react'
import { useStore } from '@/lib/store'
import { answerQuestion, connect, send } from '@/lib/ws'
import { consoleReport, forgetConsole } from '@/lib/console-log'
import { api } from '@/lib/api'
import { catalogue } from '@/lib/models'
import { readFolder } from '@/lib/importer'
import Sidebar from '@/components/Sidebar'
import Home from '@/components/Home'
import Pipeline from '@/components/Pipeline'
import PreviewPane from '@/components/PreviewPane'
import CodePane from '@/components/CodePane'
import SettingsModal from '@/components/SettingsModal'
import TestingResult from '@/components/testing/TestingResult'
import SrsResult from '@/components/srs/SrsResult'
import DeployPanel from '@/components/deploy/DeployPanel'
import EditAttach from '@/components/EditAttach'
import { useEditAttachments } from '@/lib/use-edit-attachments'
import { Badge, Button, Input } from '@/components/ui'
import { cn } from '@/lib/utils'


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

/**
 * The question a picker edit stopped on, with its answers as buttons.
 *
 * It was already being said — as log lines, in a panel that truncates every
 * one of them at the width of a sidebar, with nothing in it to press. What
 * arrived on screen was a spinner reading "Waiting for you" above three cut
 * sentences, and the instruction to retype a sixty-character sentence with a
 * suffix on it.
 *
 * `answerQuestion` re-sends the edit that was asked about, so the element the
 * preview has already forgotten does not have to be found and clicked again.
 * If that message is gone — a reload since — the answer goes into the ask box
 * instead, which is where the log lines were telling them to type it anyway.
 */
function ScopeQuestion({ onType }) {
  const question = useStore(s => s.question)
  if (!question) return null

  const routes = question.routes || []
  return (
    <div className="mb-2 rounded-ctl border border-warn/40 bg-warn/[0.06] p-2.5">
      <p className="text-[11.5px] leading-relaxed text-ink">
        <b className="font-medium">{question.file}</b> is on {routes.length} route
        {routes.length === 1 ? '' : 's'}, not just{' '}
        {question.route || 'this page'} — which did you mean?
      </p>
      {routes.length > 0 && (
        <p className="mt-1 truncate font-mono text-[10px] text-muted2"
           title={routes.join(', ')}>
          {routes.join(' · ')}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {/* The server sends the narrow answer first and the wide one second,
            and the label comes from that position rather than from reading the
            sentence — the instruction is pasted into both and may contain
            either word itself. The full sentence is the title, so what is
            actually being sent is one hover away. */}
        {(question.options || []).map((option, i) => (
          <button key={option} title={option}
                  onClick={() => { if (!answerQuestion(option)) onType(option) }}
                  className="rounded-ctl border border-line bg-panel2 px-2.5 py-1
                             text-left text-[11px] text-ink transition-colors
                             hover:border-accent/50 hover:text-accent">
            {i === 0 ? `${question.route || 'This page'} only`
                     : `All ${routes.length} routes`}
          </button>
        ))}
        <button onClick={() => useStore.setState({ question: null })}
                className="px-1.5 text-[11px] text-muted2 hover:text-ink">
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
  const tests = useStore(s => s.tests)
  const liveFile = useStore(s => s.liveFile)

  const [projects, setProjects] = useState([])
  const [cat, setCat] = useState(() => catalogue(null))
  const [screen, setScreen] = useState('home')
  const [ask, setAsk] = useState('')
  const [reading, setReading] = useState(false)
  const attach = useEditAttachments()
  const [settingsOpen, setSettingsOpen] = useState(false)

  const refreshProjects = () => api.projects()
    .then(r => setProjects(Array.isArray(r) ? r : (r.projects || [])))
    .catch(() => { })

  useEffect(() => {

    useStore.getState().hydrate()
    connect()
    refreshProjects()
    api.models().then(r => {
      const c = catalogue(r)
      setCat(c)

      const cur = useStore.getState().models
      if (!cur.agent && c.cloud[0]) {
        useStore.setState({ models: { ...cur, agent: c.cloud[0].id } })
      }
    }).catch(() => { })
  }, [])

  // A run brings the workspace up. It does NOT choose a tab.
  //
  // This used to switch to Code on the first file of every run — every build,
  // every edit, every repair — so whatever you were reading was taken away
  // from you the moment the model started writing, and the only way back was
  // to click the tab you were already on. It is the studio deciding it knows
  // better than the person watching, several times an hour.
  //
  // There is less than nothing to gain from it now: the preview holds the
  // build overlay with the log feed and the file being written already, so
  // Preview during a run shows the same progress Code would, over the pane
  // that was asked for. Code is one click away for anyone who wants it.
  useEffect(() => {
    if (liveFile) setScreen('workspace')
  }, [liveFile])

  async function openProject(name) {
    const st = useStore.getState()
    st.reset(name)
    useStore.setState({ project: name })
    setScreen('workspace')

    // Busy from the click, not from the first file.
    //
    // `api.open` returns as soon as the server has STARTED the thread that
    // installs dependencies and boots the dev server; the app is not on screen
    // for another few seconds to a minute. Until now nothing said so, and the
    // preview went on showing the project that had just been closed — the last
    // one's pages, under this one's name, live enough to click around in.
    //
    // `_open_project` ends with `edone`, which is what clears this. The
    // overlay covers the frame until then.
    st.setBusy(true)
    st.setProgress(`Opening ${name}…`, 0)
    st.addLog('INFO', `📂 Opening ${name}`)

    // The previous project's console errors are not this one's evidence.
    forgetConsole()

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
    st.addLog('INFO', `▶️ Resuming ${name} — picking up where it stopped`)
    setScreen('workspace')
    send({ type: 'agent_resume', project: name,
           model: st.models.agent, think: st.think,
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
      s.addLog('INFO', `📦 ${Object.keys(files).length} file(s) to import`
                     + (skipped ? `, ${skipped} skipped` : ''))
      const r = await api.uploadProject({ name, title, files })
      const imported = r.project || r.name || name
      s.addLog('SUCCESS', `✅ Imported ${imported}`)
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

  async function sendAsk() {
    const v = ask.trim()
    if (!v || !project) return
    const st = useStore.getState()

    // Attachments are read into the instruction before it goes, so a photo,
    // a spec or a spoken note reaches the same prompt the typing does.
    let full = v
    if (attach.items.length) {
      setReading(true)
      try {
        full = v + await attach.collect(project)
      } catch (e) {
        st.addLog('WARN', `⚠ ${e.message}`)
      }
      setReading(false)
    }

    // The page they are looking at goes with the message. The server routes on
    // it — a complaint about "this page" is meaningless without knowing which —
    // and the bug path reproduces the fault by opening that exact route.
    //
    // So does what that page's browser has already said. A complaint is typed
    // seconds after the thing went wrong, with the console still holding the
    // 500 and the stack that caused it; sending the sentence on its own throws
    // away the only part of the report that names a file.
    const saw = consoleReport()
    send({ type: 'agent_update', project, prompt: full, route: st.previewRoute || '',
           model: st.models.agent || st.models.build, think: st.think,
           qa_model: st.models.qa || '', console: saw })
    if (saw) {
      st.addLog('INFO', '   📋 sent with what the browser had already logged')
    }
    // Emptied once it has gone, so the NEXT complaint is about the next run.
    // A repair that works reloads the preview and the buffer refills clean; one
    // that does not puts the same 500 straight back. Keeping it would attach a
    // fault that has already been fixed to every message after it.
    forgetConsole()
    st.addLog('INFO', 'Update: ' + v)
    st.setBusy(true)
    attach.reset()
    setAsk('')
  }

  return (
    <div className="flex h-full">
      <Sidebar models={cat} projects={projects} onOpen={openProject}
               onImport={importFolder} onSettings={() => setSettingsOpen(true)}
               onZip={downloadZip} onResume={resumeBuild}
               onDeleted={(name) => {
                 refreshProjects()
                 if (project === name) setScreen('home')
               }} />

      {settingsOpen && (
        <SettingsModal onClose={() => setSettingsOpen(false)}
                       onSaved={() => api.models().then(r => setCat(catalogue(r)))
                                        .catch(() => { })} />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-[46px] shrink-0 items-center gap-2 border-b
                        border-line bg-panel px-4">
          {screen === 'workspace' && TABS.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => setView(id)}
                    className={cn('flex items-center gap-1.5 rounded-ctl px-3 py-[5px]',
                      'text-[12px] font-medium transition-colors',
                      view === id ? 'bg-accent/12 text-accent'
                                  : 'text-muted hover:bg-panel2 hover:text-ink')}>
              <Icon className="size-3.5" />
              {label}
              {id === 'testing' && tests.fail > 0 && (
                <Badge tone="bad">{tests.fail}</Badge>
              )}
            </button>
          ))}
          <span className="flex-1" />
          {busy && (
            <span className="flex items-center gap-1.5 font-mono text-[10px] text-accent">
              <span className="size-1.5 animate-pulse rounded-full bg-accent" />
              working
            </span>
          )}
          {screen === 'workspace' && (
            <Button variant="outline"
                    onClick={() => {

                      useStore.getState().resetSrs()
                      setScreen('home')
                    }}>
              <Plus className="size-3" /> New
            </Button>
          )}
        </div>

        {screen === 'home' ? (
          <Home onStarted={() => setScreen('workspace')} />
        ) : (
          <div className="flex min-h-0 flex-1">
            <Pipeline />

            <div className="relative flex min-w-0 flex-1 flex-col">
              <div className="shrink-0 border-b border-line bg-panel px-3 py-2">
                <ScopeQuestion onType={setAsk} />
                <Input value={ask}
                       placeholder={project
                         ? 'Describe a change, report a bug, or ask a question…'
                         : 'Open a project first'}
                       disabled={!project || busy || reading}
                       onChange={e => setAsk(e.target.value)}
                       onKeyDown={e => e.key === 'Enter' && sendAsk()} />
                {project && (
                  <EditAttach attach={attach} disabled={busy || reading}
                              className="mt-1.5" />
                )}
              </div>

              {/* Keyed on the project, every one of them.

                  These panels each hold a project's worth of state in local
                  `useState` — the deploy payload and its monitor snapshot, the
                  SRS document, which sub-tab is open, the preview's own
                  history trail — and none of it is reachable from `reset()`.
                  Switching projects while one was open left the panel showing
                  the project that had just been closed: another app's
                  deployment being monitored under this app's name. A key is
                  what says "this is a different one now", and React throws the
                  whole component away and builds it again. */}
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
