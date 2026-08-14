'use client'

import { useEffect, useRef, useState } from 'react'
import { Eye, Code2, FileText, FlaskConical, Plus, Rocket } from 'lucide-react'
import { useStore } from '@/lib/store'
import { connect, send } from '@/lib/ws'
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
  const jumped = useRef(false)

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

  useEffect(() => {
    if (liveFile && !jumped.current) {
      jumped.current = true
      setScreen('workspace')
      setView('code')
    }
    if (!busy) jumped.current = false
  }, [liveFile, busy, setView])

  async function openProject(name) {
    useStore.getState().reset(name)
    useStore.setState({ project: name })
    setScreen('workspace')
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

    send({ type: 'agent_update', project, prompt: full,
           model: st.models.agent || st.models.build, think: st.think })
    st.addLog('INFO', 'Update: ' + v)
    st.setBusy(true)
    attach.reset()
    setAsk('')
  }

  return (
    <div className="flex h-full">
      <Sidebar models={cat} projects={projects} onOpen={openProject}
               onImport={importFolder} onSettings={() => setSettingsOpen(true)}
               onZip={downloadZip} onResume={resumeBuild} />

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

              <PreviewPane hidden={view !== 'preview'} />
              <CodePane hidden={view !== 'code'} />
              {view === 'testing' && <TestingResult />}
              {view === 'srs' && <SrsResult />}
              {view === 'deploy' && (
                <DeployPanel onSettings={() => setSettingsOpen(true)} />
              )}
</div>
          </div>
        )}
      </div>
    </div>
  )
}
