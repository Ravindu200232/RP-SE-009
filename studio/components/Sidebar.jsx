'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  FolderUp, Settings, Download, ExternalLink, Search, Play, Trash2,
  PanelLeftClose, PanelLeftOpen, Home, LayoutGrid, Star, Clock, Folder,
  BookOpen, FileText, Activity, ChevronDown, Gift,
} from 'lucide-react'
import { useStore, KEYS } from '@/lib/store'
import { api } from '@/lib/api'
import { Badge, Button, Input, SectionLabel, Tag, Tip } from './ui'
import { cn } from '@/lib/utils'

export default function Sidebar({
  projects = [],
  onOpen,
  onImport,
  onSettings,
  onZip,
  onResume,
  onDeleted,
  screen = 'home',
  onScreenChange,
}) {
  const project = useStore(z => z.project)
  const status = useStore(z => z.status)
  const statusText = useStore(z => z.statusText)
  const busyProject = useStore(z => z.busyProject)
  const persist = useStore(z => z.persist)
  const addLog = useStore(z => z.addLog)

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
      addLog('WARN', `Delete of ${name} did not report back — ${e.message}. `
                     + 'Checking whether it went.')
    }
    if (project === name) useStore.getState().reset(null)
    onDeleted?.(name)
    setRemoving('')
    setConfirming('')
  }

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

  const dot = { live: 'bg-emerald-500', busy: 'bg-amber-400', connecting: 'bg-blue-400' }[status]
    || 'bg-rose-500'

  if (collapsed) {
    return (
      <aside className="flex w-[52px] shrink-0 flex-col items-center gap-2 overflow-hidden h-full border-r border-line bg-[#0c0f17] py-3">
        <Tip text="Show the sidebar" side="right">
          <button onClick={() => setCollapsed(false)}
                  className="grid size-9 place-items-center rounded-xl text-white/70 transition-colors hover:bg-white/[.08] hover:text-white">
            <PanelLeftOpen className="size-4" />
          </button>
        </Tip>
        <span className={cn('size-2 shrink-0 rounded-full', dot)} title={statusText} />
        <span className="my-1 h-px w-6 bg-white/10" />

        <Tip text="Home" side="right">
          <button onClick={() => onScreenChange?.('home')}
                  className={cn('grid size-9 place-items-center rounded-xl transition-colors',
                    screen === 'home' ? 'bg-accent/20 text-accent font-semibold' : 'text-white/60 hover:bg-white/[.06] hover:text-white')}>
            <Home className="size-4" />
          </button>
        </Tip>

        <Tip text="All Projects" side="right">
          <button onClick={() => onScreenChange?.('projects')}
                  className={cn('grid size-9 place-items-center rounded-xl transition-colors',
                    screen === 'projects' ? 'bg-accent/20 text-accent font-semibold' : 'text-white/60 hover:bg-white/[.06] hover:text-white')}>
            <LayoutGrid className="size-4" />
          </button>
        </Tip>

        <Tip text="Settings" side="right">
          <button onClick={onSettings}
                  className="grid size-9 place-items-center rounded-xl text-white/60 transition-colors hover:bg-white/[.06] hover:text-white">
            <Settings className="size-3.5" />
          </button>
        </Tip>
        <Tip text="Resume this build where it stopped" side="right">
          <button onClick={onResume} disabled={!project || status === 'busy'}
                  className="grid size-9 place-items-center rounded-xl text-white/60 transition-colors hover:bg-white/[.06] hover:text-white disabled:pointer-events-none disabled:text-white/20">
            <Play className="size-3.5" />
          </button>
        </Tip>
        <span className="flex-1" />
        {project && (
          <span className="max-h-[220px] [writing-mode:vertical-rl] truncate text-[10px] font-semibold text-white/40"
                title={project}>
            {project}
          </span>
        )}
      </aside>
    )
  }

  return (
    <aside className="flex w-[var(--sidebar-w)] shrink-0 flex-col overflow-hidden h-full border-r border-line bg-[#0c0f17]">
      {/* Top Header: Brand and Controls */}
      <header className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-line px-4 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-accent/15 ring-1 ring-accent/25 shadow-sm overflow-hidden">
            <img src="/__agentforge/agentforge-mark.png" alt="AgentForge"
                 width={22} height={22}
                 className="size-5 object-contain" />
          </div>
          <span className="font-display text-[14.5px] font-bold tracking-tight text-white">
            agentforge<span className="text-accent text-[12px] font-normal ml-0.5">.ai</span>
          </span>
        </div>

        <div className="flex justify-end items-center gap-1 col-span-2">
          <Tip text="Hide the sidebar">
            <button
              className="grid size-[26px] place-items-center rounded-lg border border-white/10 bg-white/[.04] text-white/70 transition-colors hover:bg-white/[.08] hover:text-white"
              onClick={() => setCollapsed(true)}
            >
              <PanelLeftClose className="size-3" />
            </button>
          </Tip>
        </div>
      </header>

      {/* User Profile Pill */}
      <div className="p-3 border-b border-line">
        <div className="flex items-center justify-between gap-2.5 rounded-xl border border-white/10 bg-white/[.03] p-2 shadow-sm transition-all hover:bg-white/[.06]">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="grid size-7 shrink-0 place-items-center rounded-lg bg-gradient-to-tr from-pink-500 to-purple-600 font-display text-[12px] font-bold text-white shadow-sm">
              R
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[12px] font-semibold leading-none text-white/90">
                ravindu2232@gmail.com
              </div>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <span className="rounded-md bg-accent/20 px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wide text-accent">
              Free
            </span>
            <ChevronDown className="size-3 text-white/40" />
          </div>
        </div>
      </div>

      {/* Primary Navigation Menu */}
      <nav className="flex flex-col gap-0.5 p-2 border-b border-line text-[13px]">
        <button
          onClick={() => onScreenChange?.('home')}
          className={cn(
            'flex items-center gap-3 rounded-xl px-3 py-2 font-medium transition-colors text-left',
            screen === 'home'
              ? 'bg-accent/15 text-accent border border-accent/25 font-semibold shadow-sm'
              : 'text-white/70 hover:bg-white/[.05] hover:text-white'
          )}
        >
          <Home className="size-4 shrink-0" />
          <span>Home</span>
        </button>

        <button
          onClick={() => onScreenChange?.('projects')}
          className={cn(
            'flex items-center justify-between rounded-xl px-3 py-2 font-medium transition-colors text-left',
            screen === 'projects'
              ? 'bg-accent/15 text-accent border border-accent/25 font-semibold shadow-sm'
              : 'text-white/70 hover:bg-white/[.05] hover:text-white'
          )}
        >
          <div className="flex items-center gap-3">
            <LayoutGrid className="size-4 shrink-0" />
            <span>Projects</span>
          </div>
          <span className="rounded-full bg-white/10 px-2 py-0.5 font-mono text-[10px] text-white/70">
            {projects.length}
          </span>
        </button>

        <button className="flex items-center gap-3 rounded-xl px-3 py-1.5 text-white/60 hover:bg-white/[.05] hover:text-white">
          <Star className="size-4 shrink-0 text-white/40" />
          <span>Starred</span>
        </button>

        <button className="flex items-center gap-3 rounded-xl px-3 py-1.5 text-white/60 hover:bg-white/[.05] hover:text-white">
          <Clock className="size-4 shrink-0 text-white/40" />
          <span>Recently viewed</span>
        </button>

        <button className="flex items-center gap-3 rounded-xl px-3 py-1.5 text-white/60 hover:bg-white/[.05] hover:text-white">
          <Folder className="size-4 shrink-0 text-white/40" />
          <span>Shared with you</span>
        </button>
      </nav>

      {/* Secondary Resources & Status */}
      <div className="flex flex-col gap-0.5 p-2 border-b border-line text-[12px]">
        <button className="flex items-center gap-3 rounded-xl px-3 py-1.5 text-white/60 hover:bg-white/[.05] hover:text-white">
          <BookOpen className="size-3.5 shrink-0 text-white/40" />
          <span>Help Center</span>
        </button>
        <button className="flex items-center gap-3 rounded-xl px-3 py-1.5 text-white/60 hover:bg-white/[.05] hover:text-white">
          <FileText className="size-3.5 shrink-0 text-white/40" />
          <span>Release notes</span>
        </button>
        <div className="flex items-center justify-between rounded-xl px-3 py-1.5 text-white/60">
          <div className="flex items-center gap-3">
            <Activity className="size-3.5 shrink-0 text-white/40" />
            <span>Status</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={cn('size-2 rounded-full', dot)} />
            <span className="font-mono text-[10px] text-white/50">{status}</span>
          </div>
        </div>
      </div>

      {/* Active Project Card (Contract requirement: busyProject === name) */}
      {project && (() => {
        const name = project
        const working = busyProject === name
        return (
          <div className="p-3 border-b border-line">
            <div className="mb-1.5 px-1 text-[10px] font-bold uppercase tracking-wider text-white/40">
              Active Workspace
            </div>
            <div className="flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/[.03] p-2.5 shadow-sm">
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12.5px] font-semibold text-white/90">{name}</div>
              </div>
              {working ? (
                <span className="flex items-center gap-1.5 rounded-full bg-accent/20 px-2 py-0.5 text-[10px] font-semibold text-accent">
                  <span className="size-1.5 rounded-full bg-accent animate-pulse" />
                  working
                </span>
              ) : (
                <button
                  onClick={() => onScreenChange?.('projects')}
                  className="text-[11px] font-medium text-accent hover:underline"
                >
                  Change
                </button>
              )}
            </div>
          </div>
        )
      })()}

      {/* Spacer to push Referral banner and Footer to bottom */}
      <div className="flex-1" />

      {/* Earn $50 referral banner from Bolt.new */}
      <div className="border-t border-line p-2">
        <div className="flex items-center justify-between rounded-xl bg-accent/15 border border-accent/25 px-3 py-2 text-[12px] text-accent">
          <div className="flex items-center gap-2">
            <Gift className="size-3.5" />
            <span className="font-semibold">Earn $50</span>
          </div>
          <span className="size-2 rounded-full bg-accent animate-pulse" />
        </div>
      </div>

      {/* Bottom Footer Actions */}
      <footer className="flex items-stretch border-t border-line bg-black/20">
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
  <Tip className="flex-1 border-r border-line last:border-r-0" text={tip}>
    <button {...rest}
            className="grid h-[36px] w-full place-items-center text-white/60
                       transition-colors hover:bg-white/[.08] hover:text-white
                       disabled:pointer-events-none disabled:text-white/20">
      <Icon className="size-3.5" />
    </button>
  </Tip>
)