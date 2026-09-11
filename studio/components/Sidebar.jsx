'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Moon, Sun, FolderUp, Settings, Download, ExternalLink, Search, Play, Trash2,
  PanelLeftClose, PanelLeftOpen,
} from 'lucide-react'
import { useStore, KEYS } from '@/lib/store'
import { api } from '@/lib/api'
import { Badge, Button, Input, SectionLabel, Tag, Tip } from './ui'
import { cn } from '@/lib/utils'


export default function Sidebar({
  projects, onOpen, onImport, onSettings, onZip, onResume, onDeleted,
}) {
  // One field at a time on purpose. Reading the whole store here subscribed
  // the sidebar to every change in it, and during a build a log line arrives
  // several times a second - so the project list, all thirty rows of it, was
  // re-rendering on the arrival of text it does not show.
  const project = useStore(z => z.project)
  const status = useStore(z => z.status)
  const statusText = useStore(z => z.statusText)
  const theme = useStore(z => z.theme)
  const busyProject = useStore(z => z.busyProject)
  const persist = useStore(z => z.persist)
  const addLog = useStore(z => z.addLog)
  const setTheme = useStore(z => z.setTheme)
  // Collapsed, the sidebar keeps only what you would reopen it for: which
  // project is live, and whether anything is running.
  const [collapsed, setCollapsed] = useState(false)
  const folderRef = useRef(null)
  const [q, setQ] = useState('')
  const [confirming, setConfirming] = useState('')
  const [removing, setRemoving] = useState('')

  async function remove(name) {
    setRemoving(name)
    try {
      await api.deleteProject(name)
      addLog('SUCCESS', `Deleted ${name}`)
    } catch (e) {
      // Reported, not trusted.
      addLog('WARN', `Delete of ${name} did not report back — ${e.message}. `
                     + 'Checking whether it went.')
    }
      // Release a project folder that may no longer exist.
    if (project === name) useStore.getState().reset(null)
    onDeleted?.(name)
    setRemoving('')
    setConfirming('')
  }

  // Whether pictures are drawn is the server's setting, and the only thing
  // in the studio that reads it is the logo panel the home screen offers. It
  // is followed here rather than switched here: the switch went when the
  // sidebar stopped being a settings page.
  useEffect(() => {
    api.settings()
      .then(cfg => {
        if (!cfg || !('image_enabled' in cfg)) return
        useStore.setState({ images: !!cfg.image_enabled })
        persist(KEYS.images, cfg.image_enabled ? '1' : '0')
      })
      .catch(() => { })
  }, [persist])

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return projects
    return projects.filter(p =>
      String(p.title || p.name || p).toLowerCase().includes(needle) ||
      String(p.name || '').toLowerCase().includes(needle))
  }, [projects, q])

  const dot = { live: 'bg-ok', busy: 'bg-warn', connecting: 'bg-muted2' }[status]
    || 'bg-bad'

  if (collapsed) {
    return (
      <aside className="glass-panel flex w-[56px] shrink-0 flex-col items-center gap-2 overflow-hidden rounded-[24px] py-3">
        <Tip text="Show the sidebar" side="right">
          <button onClick={() => setCollapsed(false)}
                  className="grid size-9 place-items-center rounded-xl text-ink transition-colors hover:bg-ink/[.07]">
            <PanelLeftOpen className="size-4" />
          </button>
        </Tip>
        <span className={cn('size-2 shrink-0 rounded-full', dot)} title={statusText} />
        <span className="my-1 h-px w-6 bg-line2" />
        <Tip text="Settings" side="right">
          <button onClick={onSettings}
                  className="grid size-9 place-items-center rounded-xl text-muted transition-colors hover:bg-ink/[.07] hover:text-ink">
            <Settings className="size-3.5" />
          </button>
        </Tip>
        <Tip text="Resume this build where it stopped" side="right">
          <button onClick={onResume} disabled={!project || status === 'busy'}
                  className="grid size-9 place-items-center rounded-xl text-muted transition-colors hover:bg-ink/[.07] hover:text-ink disabled:pointer-events-none disabled:text-faint">
            <Play className="size-3.5" />
          </button>
        </Tip>
        <span className="flex-1" />
        {project && (
          <span className="max-h-[220px] [writing-mode:vertical-rl] truncate text-[10px] font-semibold text-muted"
                title={project}>
            {project}
          </span>
        )}
      </aside>
    )
  }

  return (
    <aside className="glass-panel flex w-[var(--sidebar-w)] shrink-0 flex-col overflow-hidden rounded-[24px]">
      <header className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-line/70 px-4 py-4">
        <img src="/__agentforge/agentforge-mark.png" alt="AgentForge"
             width={34} height={34}
             className="size-9 shrink-0 rounded-xl border border-white/60 object-cover shadow-sm" />
        <div className="min-w-0">
          <div className="font-display text-[16px] font-bold leading-none
                          tracking-[-.02em] text-ink">
            AGENTFORGE
          </div>
          <div className="mt-[5px] flex items-center gap-[6px]">
            <span className="h-[2px] w-[15px] rounded-full bg-accent" />
            <span className="text-[9.5px] font-semibold tracking-[.24em] text-label">
              STUDIO
            </span>
          </div>
        </div>
        <span className="flex items-center gap-1">
          <Tip text="Toggle theme">
            <Button variant="outline" size="icon" className="size-[28px]"
                    onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
              <Moon className="hidden size-3.5 dark:block" />
              <Sun className="size-3.5 dark:hidden" />
            </Button>
          </Tip>
          <Tip text="Hide the sidebar">
            <Button variant="outline" size="icon" className="size-[28px]"
                    onClick={() => setCollapsed(true)}>
              <PanelLeftClose className="size-3.5" />
            </Button>
          </Tip>
        </span>
      </header>

      <div className="mx-3 mt-3 flex items-center gap-2 rounded-xl border border-line/70 bg-white/45 px-3 py-2 shadow-sm dark:bg-white/[.025]">
        <span className={cn('size-2 shrink-0 rounded-full shadow-sm', dot)} />
        <span className="min-w-0 truncate font-mono text-[10.5px] text-muted">
          {statusText}
        </span>
        <span className="flex-1" />
        <span className="label-2xs shrink-0 text-muted2">{status}</span>
      </div>

      <SectionLabel className="border-b border-line2 px-[14px] py-[9px]"
                    right={<span className="font-mono text-[10px] font-normal
                                            tracking-normal text-muted2">
                             {String(projects.length).padStart(2, '0')}
                           </span>}>
        Projects
      </SectionLabel>

      {projects.length > 6 && (
        <div className="relative border-b border-line2 p-2">
          <Search className="pointer-events-none absolute left-[11px] top-1/2 size-3
                             -translate-y-1/2 text-muted2" />
          <Input value={q} onChange={e => setQ(e.target.value)} placeholder="Filter…"
                 className="pl-[26px]" />
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        {shown.map((p, i) => {
          const name = p.name || p
          const on = project === name
          const asking = confirming === name
          const busyHere = removing === name
          // A run keeps going while you look at another project, so the row
          // says which one is working rather than the header saying "busy".
          const working = busyProject === name
          return (
            <div key={name}
                 className={cn('group grid w-full grid-cols-[26px_1fr_auto]',
                   'items-center gap-2.5 rounded-[14px] border-l-[3px]',
                   'py-[11px] pl-[7px] pr-[14px] transition-colors',
                   asking ? 'border-l-accent bg-tint'
                          : on ? 'border-l-accent bg-panel2'
                               : 'border-l-transparent hover:bg-panel2')}>
              {working ? (
                <span title="This project is working"
                      className="grid size-[18px] place-items-center">
                  <span className="block size-[15px] animate-spin rounded-full border-[2px] border-accent/25 border-t-accent" />
                </span>
              ) : (
                <span className={cn('font-mono text-[10.5px] tabular-nums',
                                    on || asking ? 'text-accent' : 'text-faint')}>
                  {String(i + 1).padStart(2, '0')}
                </span>
              )}
              <button onClick={() => onOpen(name, p)} disabled={asking || busyHere}
                      className="min-w-0 text-left">
                <span className={cn('block truncate text-[13.5px] leading-tight',
                                    'tracking-[-.012em] text-ink',
                                    on ? 'font-extrabold' : 'font-semibold')}>
                  {p.title || name}
                </span>
                <span className={cn('mt-[3px] block truncate text-[11px] leading-tight',
                                    asking ? 'text-deep' : 'text-muted2')}>
                  {asking ? 'delete this and its database?'
                          : p.spec_only ? 'specification only'
                          : (p.file_count ? `${p.file_count} files` : 'project')}
                </span>
              </button>

              {asking ? (
                <span className="flex shrink-0 items-center">
                  <button onClick={() => remove(name)} disabled={busyHere}
                          className="border border-accent bg-accent px-[6px] py-px
                                     font-mono text-[10px] text-bg transition-colors
                                     hover:bg-press disabled:opacity-50">
                    {busyHere ? '…' : 'delete'}
                  </button>
                  <button onClick={() => setConfirming('')} disabled={busyHere}
                          className="px-1.5 font-mono text-[10px] text-muted
                                     hover:text-ink">
                    keep
                  </button>
                </span>
              ) : (
                <span className="flex shrink-0 items-center gap-1.5">
                  <DeployTag deployed={p.deployed} />
                  {p.unfinished ? <Badge tone="bad">{p.unfinished}</Badge> : null}
                  <Tip text={`Delete ${name} from disk`}>
                    <button onClick={() => setConfirming(name)}
                            className="shrink-0 p-0.5 text-muted2 opacity-0
                                       transition-opacity hover:text-accent
                                       group-hover:opacity-100">
                      <Trash2 className="size-3" />
                    </button>
                  </Tip>
                </span>
              )}
            </div>
          )
        })}
        {!shown.length && (
          <p className="px-[14px] py-3 text-[11.5px] text-muted">
            {projects.length ? `Nothing matches “${q}”.` : 'No projects yet.'}
          </p>
        )}
      </div>

      <footer className="flex items-stretch border-t-2 border-line2">
        <input ref={folderRef} type="file" hidden
               webkitdirectory="" directory="" multiple
               onChange={e => {
                 const list = e.target.files
                 e.target.value = ''
                 if (list?.length) onImport(list)
               }} />
        <Foot icon={FolderUp} tip="Import a project folder"
              onClick={() => folderRef.current?.click()} />
        <Foot icon={Play} tip="Resume this build where it stopped"
              disabled={!project || status === 'busy'} onClick={onResume} />
        <Foot icon={Settings} tip="Settings" onClick={onSettings} />
        <Foot icon={Download} tip="Download this project as a zip"
              disabled={!project} onClick={onZip} />
        <Foot icon={ExternalLink} tip="Open the app in a new tab"
              disabled={!project} onClick={async () => {
                const tab = window.open('about:blank', '_blank')
                try {
                  const runtime = await api.open(project)
                  useStore.getState().setRuntime(runtime)
                  if (tab) { tab.opener = null; tab.location.href = runtime.previewUrl }
                } catch (error) {
                  tab?.close()
                  useStore.getState().addLog('WARN', `Could not open app: ${error.message}`)
                }
              }} />
      </footer>
    </aside>
  )
}


function DeployTag({ deployed }) {
  if (!deployed) return null
  const gone = deployed.state === 'deleted'
  const where = deployed.target?.startsWith('aws') ? 'aws'
              : deployed.target === 'vercel' ? 'vercel'
              : ''
  return (
    <Tip text={gone ? 'Deployed, then deleted'
                    : `Deployed${where ? ` to ${where}` : ''}`}>
      <Tag tone={gone ? 'mute' : 'solid'}>{gone ? 'gone' : (where || 'deployed')}</Tag>
    </Tip>
  )
}

const Foot = ({ icon: Icon, tip, ...rest }) => (
  <Tip className="flex-1 border-r border-line2 last:border-r-0" text={tip}>
    <button {...rest}
            className="grid h-[34px] w-full place-items-center text-ink
                       transition-colors hover:bg-ink/[.07]
                       disabled:pointer-events-none disabled:text-faint">
      <Icon className="size-3.5" />
    </button>
  </Tip>
)
