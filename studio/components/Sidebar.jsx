'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  FolderUp, Settings, Download, ExternalLink, Search, Play, Trash2,
  PanelLeftClose, PanelLeftOpen, Home, LayoutGrid, Star, Clock, Folder,
  BookOpen, FileText, Activity, ChevronDown, Gift, CreditCard, LogOut,
  X, Menu,
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
  user = null,
  onLogout = null,
  mobileOpen = false,
  onMobileClose = null,
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

  const [accountOpen, setAccountOpen] = useState(false)
  const accountMenuRef = useRef(null)

  const initial = (user?.name || user?.username || 'R')[0]?.toUpperCase() || 'R'
  const displayName = user?.name || user?.username || 'Ravindu'
  const displaySubtitle = user?.email || 'Developer Workspace'

  useEffect(() => {
    if (!accountOpen) return
    const handleClickAway = (e) => {
      if (accountMenuRef.current && !accountMenuRef.current.contains(e.target)) {
        setAccountOpen(false)
      }
    }
    window.addEventListener('mousedown', handleClickAway)
    return () => window.removeEventListener('mousedown', handleClickAway)
  }, [accountOpen])

  async function openInNewTab() {
    if (!project) return
    const tab = window.open('about:blank', '_blank')
    try {
      const runtime = await api.open(project)
      useStore.getState().setRuntime(runtime)
      if (tab) { tab.opener = null; tab.location.href = runtime.previewUrl }
    } catch (error) {
      tab?.close()
      useStore.getState().addLog('WARN', `Could not open app: ${error.message}`)
    }
  }

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

  const dot = { live: 'bg-[#22C55E]', busy: 'bg-[#FFAB00]', connecting: 'bg-[#1877F2]' }[status]
    || 'bg-[#FF5630]'

  const renderBody = (isMobile = false) => (
    <>
      {/* Primary Navigation Menu */}
      <nav className="flex flex-col gap-0.5 p-2 border-b border-line text-[13px]">
        <button
          onClick={() => {
            onScreenChange?.('home')
            if (isMobile) onMobileClose?.()
          }}
          className={cn(
            'flex items-center gap-3 rounded-xl px-3 py-2 font-medium transition-all text-left',
            screen === 'home'
              ? 'bg-[#1877F2]/10 text-[#1877F2] font-semibold shadow-sm'
              : 'text-white/70 hover:bg-white/[.04] hover:text-white'
          )}
        >
          <Home className="size-4 shrink-0" />
          <span>Home</span>
        </button>

        <button
          onClick={() => {
            onScreenChange?.('projects')
            if (isMobile) onMobileClose?.()
          }}
          className={cn(
            'flex items-center justify-between rounded-xl px-3 py-2 font-medium transition-all text-left',
            screen === 'projects'
              ? 'bg-[#1877F2]/10 text-[#1877F2] font-semibold shadow-sm'
              : 'text-white/70 hover:bg-white/[.04] hover:text-white'
          )}
        >
          <div className="flex items-center gap-3">
            <LayoutGrid className="size-4 shrink-0" />
            <span>Projects</span>
          </div>
          <span className={cn(
            "rounded-full px-2 py-0.5 font-mono text-[10px]",
            screen === 'projects' ? "bg-[#1877F2]/20 text-[#1877F2] font-bold" : "bg-white/10 text-white/70"
          )}>
            {projects.length}
          </span>
        </button>

        <button
          onClick={() => {
            onSettings?.()
            if (isMobile) onMobileClose?.()
          }}
          className="flex items-center gap-3 rounded-xl px-3 py-1.5 text-white/60 hover:bg-white/[.05] hover:text-white text-left"
        >
          <Settings className="size-4 shrink-0 text-white/40" />
          <span>Settings</span>
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

      {/* Active Project Card */}
      {project && (() => {
        const name = project
        const working = busyProject === name
        return (
          <div className="p-3 border-b border-line">
            <div className="mb-1.5 px-1 text-[10px] font-bold uppercase tracking-wider text-white/40">
              Active Workspace
            </div>
            <div className="flex items-center justify-between gap-2 rounded-xl border border-line bg-[#1C252E] p-2.5 shadow-sm">
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12.5px] font-semibold text-white/90">{name}</div>
              </div>
              {working ? (
                <span className="flex items-center gap-1.5 rounded-full bg-[#1877F2]/15 px-2 py-0.5 text-[10px] font-semibold text-[#1877F2]">
                  <span className="size-1.5 rounded-full bg-[#1877F2] animate-pulse" />
                  working
                </span>
              ) : (
                <button
                  onClick={() => {
                    onScreenChange?.('projects')
                    if (isMobile) onMobileClose?.()
                  }}
                  className="text-[11px] font-medium text-[#1877F2] hover:underline"
                >
                  Change
                </button>
              )}
            </div>
          </div>
        )
      })()}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Earn $50 referral banner */}
      <div className="border-t border-line p-2">
        <div className="flex items-center justify-between rounded-xl bg-[#1877F2]/10 border border-[#1877F2]/20 px-3 py-2 text-[12px] text-[#1877F2]">
          <div className="flex items-center gap-2">
            <Gift className="size-3.5" />
            <span className="font-semibold">Earn $50</span>
          </div>
          <span className="size-2 rounded-full bg-[#1877F2] animate-pulse" />
        </div>
      </div>

      {/* User Account Row */}
      <div className="relative border-t border-line px-3 py-2.5" ref={accountMenuRef}>
        {/* Hidden folder input for import */}
        <input ref={folderRef} type="file" hidden
               webkitdirectory="" directory="" multiple
               onChange={e => {
                 const list = e.target.files
                 e.target.value = ''
                 if (list?.length) onImport(list)
               }} />

        {/* Account Menu Popover */}
        {accountOpen && (
          <div
            className="absolute bottom-full left-3 mb-2 w-56 rounded-2xl border border-line bg-[#1C252E] p-1.5 shadow-[0_20px_40px_-4px_rgba(0,0,0,0.48)] backdrop-blur-2xl z-50 animate-in fade-in zoom-in-95"
          >
            <button
              onClick={() => { setAccountOpen(false); onSettings?.(); if (isMobile) onMobileClose?.() }}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white transition-colors"
            >
              <Settings className="size-4 text-white/80" />
              <span>Settings</span>
            </button>
            <button
              onClick={() => { setAccountOpen(false); folderRef.current?.click(); if (isMobile) onMobileClose?.() }}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white transition-colors"
            >
              <FolderUp className="size-4 text-white/80" />
              <span>Import project folder</span>
            </button>
            <button
              onClick={() => { setAccountOpen(false); onResume?.(); if (isMobile) onMobileClose?.() }}
              disabled={!project || status === 'busy'}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              <Play className="size-4 text-white/80" />
              <span>Resume build</span>
            </button>
            <button
              onClick={() => { setAccountOpen(false); onZip?.(); if (isMobile) onMobileClose?.() }}
              disabled={!project}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              <Download className="size-4 text-white/80" />
              <span>Download project as zip</span>
            </button>
            <button
              onClick={() => { setAccountOpen(false); openInNewTab(); if (isMobile) onMobileClose?.() }}
              disabled={!project}
              className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white disabled:opacity-40 disabled:pointer-events-none transition-colors"
            >
              <ExternalLink className="size-4 text-white/80" />
              <span>Open in new tab</span>
            </button>
            {onLogout && (
              <>
                <div className="my-1 border-t border-line" />
                <button
                  onClick={() => { setAccountOpen(false); onLogout?.(); if (isMobile) onMobileClose?.() }}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-[#FF5630] hover:bg-[#FF5630]/10 hover:text-[#FF5630] transition-colors"
                >
                  <LogOut className="size-4" />
                  <span>Sign out</span>
                </button>
              </>
            )}
          </div>
        )}

        <button
          onClick={() => setAccountOpen(v => !v)}
          className="flex w-full items-center justify-between gap-2.5 rounded-xl p-1.5 hover:bg-white/[.06] transition-colors group"
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-[#1877F2] font-bold text-[13px] text-white shadow-sm transition-transform group-hover:scale-105">
              {initial}
            </div>
            <div className="min-w-0 text-left">
              <div className="truncate text-[12.5px] font-semibold text-white/90">{displayName}</div>
              <div className="truncate text-[10.5px] text-white/40">{displaySubtitle}</div>
            </div>
          </div>
          <ChevronDown className={cn("size-3.5 text-white/40 transition-transform", accountOpen && "rotate-180")} />
        </button>
      </div>
    </>
  )

  const renderMobileDrawer = () => (
    <div className={cn(
      "fixed inset-0 z-50 md:hidden transition-all duration-300",
      mobileOpen ? "visible opacity-100" : "invisible opacity-0 pointer-events-none"
    )}>
      <div
        className="absolute inset-0 bg-black/75 backdrop-blur-sm"
        onClick={onMobileClose}
      />
      <aside className={cn(
        "absolute top-0 bottom-0 left-0 w-[280px] max-w-[85vw] flex flex-col bg-[#141A21] border-r border-line shadow-2xl transition-transform duration-300 ease-out z-10",
        mobileOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <header className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-[#1877F2]/10 ring-1 ring-[#1877F2]/20 shadow-sm overflow-hidden">
              <img src="/__agentforge/agentforge-mark.png" alt="AgentForge" width={22} height={22} className="size-5 object-contain" />
            </div>
            <span className="font-display text-[14.5px] font-bold tracking-tight text-white">
              agentforge<span className="text-accent text-[12px] font-normal ml-0.5">.ai</span>
            </span>
          </div>
          <button
            onClick={onMobileClose}
            className="grid size-7 place-items-center rounded-lg border border-white/10 bg-white/[.04] text-white/70 hover:bg-white/[.08] hover:text-white"
          >
            <X className="size-3.5" />
          </button>
        </header>
        {renderBody(true)}
      </aside>
    </div>
  )

  if (collapsed) {
    return (
      <>
        {renderMobileDrawer()}
        <aside className="hidden md:flex w-[52px] shrink-0 flex-col items-center gap-2 overflow-hidden h-full border-r border-line bg-[#141A21] py-3">
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
                      screen === 'home' ? 'bg-[#1877F2]/15 text-[#1877F2] font-semibold' : 'text-white/60 hover:bg-white/[.06] hover:text-white')}>
              <Home className="size-4" />
            </button>
          </Tip>

          <Tip text="All Projects" side="right">
            <button onClick={() => onScreenChange?.('projects')}
                    className={cn('grid size-9 place-items-center rounded-xl transition-colors',
                      screen === 'projects' ? 'bg-[#1877F2]/15 text-[#1877F2] font-semibold' : 'text-white/60 hover:bg-white/[.06] hover:text-white')}>
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

          {/* Collapsed Account Avatar Button with Popover */}
          <div className="relative mt-auto" ref={accountMenuRef}>
            {accountOpen && (
              <div
                className="absolute bottom-0 left-full ml-3 w-56 rounded-2xl border border-line bg-[#1C252E] p-1.5 shadow-[0_20px_40px_-4px_rgba(0,0,0,0.48)] backdrop-blur-2xl z-50 animate-in fade-in zoom-in-95"
              >
                <button
                  onClick={() => { setAccountOpen(false); onSettings?.() }}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white transition-colors"
                >
                  <Settings className="size-4 text-white/80" />
                  <span>Settings</span>
                </button>
                <button
                  onClick={() => { setAccountOpen(false); folderRef.current?.click() }}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white transition-colors"
                >
                  <FolderUp className="size-4 text-white/80" />
                  <span>Import project folder</span>
                </button>
                <button
                  onClick={() => { setAccountOpen(false); onResume?.() }}
                  disabled={!project || status === 'busy'}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white disabled:opacity-40 disabled:pointer-events-none transition-colors"
                >
                  <Play className="size-4 text-white/80" />
                  <span>Resume build</span>
                </button>
                <button
                  onClick={() => { setAccountOpen(false); onZip?.() }}
                  disabled={!project}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white disabled:opacity-40 disabled:pointer-events-none transition-colors"
                >
                  <Download className="size-4 text-white/80" />
                  <span>Download project as zip</span>
                </button>
                <button
                  onClick={() => { setAccountOpen(false); openInNewTab() }}
                  disabled={!project}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-white/90 hover:bg-white/[.06] hover:text-white disabled:opacity-40 disabled:pointer-events-none transition-colors"
                >
                  <ExternalLink className="size-4 text-white/80" />
                  <span>Open in new tab</span>
                </button>
                {onLogout && (
                  <>
                    <div className="my-1 border-t border-line" />
                    <button
                      onClick={() => { setAccountOpen(false); onLogout?.() }}
                      className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-[#FF5630] hover:bg-[#FF5630]/10 hover:text-[#FF5630] transition-colors"
                    >
                      <LogOut className="size-4" />
                      <span>Sign out</span>
                    </button>
                  </>
                )}
              </div>
            )}
            <button
              onClick={() => setAccountOpen(v => !v)}
              title={`Account: ${displayName}`}
              className="flex size-8 items-center justify-center rounded-lg bg-[#1877F2] font-bold text-[13px] text-white shadow-sm transition-transform hover:scale-105 active:scale-95"
            >
              {initial}
            </button>
          </div>
        </aside>
      </>
    )
  }

  return (
    <>
      {renderMobileDrawer()}
      <aside className="hidden md:flex w-[var(--sidebar-w)] shrink-0 flex-col overflow-hidden h-full border-r border-line bg-[#141A21]">
        {/* Top Header: Brand and Controls */}
        <header className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-line px-4 py-3">
          <div className="flex items-center gap-2.5">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-[#1877F2]/10 ring-1 ring-[#1877F2]/20 shadow-sm overflow-hidden">
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
        {renderBody(false)}
      </aside>
    </>
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