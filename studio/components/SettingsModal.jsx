'use client'

import { useEffect, useState } from 'react'
import {
  Check, ChevronDown, Cloud, CloudOff, Cpu, Database, ExternalLink,
  FileCode, FileText, Folder, FolderCode, Globe, Info, Keyboard,
  LayoutGrid, Loader2, Lock, MessageCircleQuestion, MessageSquare,
  Palette, Pencil, Plus, Puzzle, RefreshCw, Rocket, Shield,
  SlidersHorizontal, Sparkles, User, Wrench, X,
} from 'lucide-react'
import { api } from '@/lib/api'
import { Modal } from './ui'
import { cn } from '@/lib/utils'
import { useStore } from '@/lib/store'
import { useAuthStore } from '@/lib/auth'
import DeployAccounts from './deploy/DeployAccounts'

export default function SettingsModal({ onClose, onSaved }) {
  const project = useStore(z => z.project) || 'RP-SE-009'
  const user = useAuthStore(s => s.user)

  // Active navigation tab — default to current project view as in reference image
  const [activeTab, setActiveTab] = useState('project')

  // Server settings state
  const [host, setHost] = useState('')
  const [ctx, setCtx] = useState('')
  const [key, setKey] = useState('')
  const [mongo, setMongo] = useState('')
  const [meta, setMeta] = useState(null)
  const [saving, setSaving] = useState(false)
  const [note, setNote] = useState('loading…')
  const [tone, setTone] = useState('muted')

  // Project preferences state (matching reference image)
  const [securityPreset, setSecurityPreset] = useState('turbo')
  const [artifactPolicy, setArtifactPolicy] = useState('inherit')
  const [projectFolders, setProjectFolders] = useState([`${project}/`])
  const [feedbackText, setFeedbackText] = useState('')
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false)

  // Modals for file & network rules
  const [rulesModal, setRulesModal] = useState(null) // 'file' | 'network' | null

  useEffect(() => {
    let alive = true
    api.settings()
      .then(d => {
        if (!alive) return
        setHost(d.ollama_host || '')
        setCtx(d.local_num_ctx || '')
        setMeta(d)
        setNote(d.cloud_enabled ? 'cloud enabled' : 'cloud off — local only')
        setTone(d.cloud_enabled ? 'ok' : 'muted')
      })
      .catch(() => { if (alive) { setNote('server offline'); setTone('bad') } })
    return () => { alive = false }
  }, [])

  async function save() {
    setSaving(true)
    setNote('saving…')
    setTone('muted')
    const body = { ollama_host: host.trim(), local_num_ctx: String(ctx).trim() }
    if (key.trim()) body.ollama_api_key = key.trim()
    if (mongo.trim()) body.mongodb_uri = mongo.trim() === '-' ? '' : mongo.trim()

    try {
      const d = await api.saveSettings(body)
      setNote(!d.cloud_enabled ? 'cloud off — local only'
        : d.cloud_reachable ? 'cloud key verified' : 'key saved but not accepted')
      setTone(!d.cloud_enabled ? 'muted' : d.cloud_reachable ? 'ok' : 'bad')
      onSaved?.()
      if (d.cloud_reachable) setTimeout(onClose, 800)
    } catch (e) {
      setNote('save failed — ' + e.message)
      setTone('bad')
    }
    setSaving(false)
  }

  const cloudOn = tone === 'ok'

  const displayName = user?.name || user?.username || 'Ravindu Subasinha'
  const displayEmail = user?.email || 'ravindusubasinha082@gmail.com'
  const initial = (user?.name || user?.username || 'R')[0]?.toUpperCase() || 'R'

  // Nav configuration mirroring reference image
  const settingsNav = [
    { id: 'general', label: 'General', Icon: SlidersHorizontal },
    { id: 'application', label: 'Application', Icon: LayoutGrid },
    { id: 'appearance', label: 'Appearance', Icon: Palette },
    { id: 'models', label: 'Models', Icon: Cpu },
    { id: 'customizations', label: 'Customizations', Icon: Puzzle },
    { id: 'browser', label: 'Browser', Icon: Globe },
  ]

  return (
    <Modal onClose={onClose} className="max-w-none w-[min(1060px,95vw)] h-[min(690px,90vh)] p-0 overflow-hidden flex flex-col rounded-[26px] border border-white/15 bg-[#0e1320] shadow-[0_30px_90px_rgba(0,0,0,0.85)]">
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left Sidebar (matching reference image) */}
        <aside className="w-60 shrink-0 border-r border-white/10 bg-[#0a0d16]/95 flex flex-col justify-between p-3 select-none">
          <div className="flex-1 overflow-y-auto space-y-4 pr-1 custom-scrollbar">
            {/* Settings Group */}
            <div>
              <div className="px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-white/40">
                Settings
              </div>
              <div className="space-y-0.5">
                {settingsNav.map(item => {
                  const active = activeTab === item.id
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setActiveTab(item.id)}
                      className={cn(
                        'w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-xl text-left text-[12px] transition-all',
                        active
                          ? 'bg-white/[.12] text-white font-semibold shadow-sm'
                          : 'text-white/60 hover:text-white hover:bg-white/[.05] font-medium'
                      )}
                    >
                      <item.Icon className={cn('size-3.5 shrink-0', active ? 'text-blue-400' : 'text-white/50')} />
                      <span>{item.label}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Projects Group */}
            <div>
              <div className="px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-white/40">
                Projects
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('project')}
                className={cn(
                  'w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-xl text-left text-[12px] transition-all',
                  activeTab === 'project'
                    ? 'bg-white/[.12] text-white font-semibold shadow-sm'
                    : 'text-white/60 hover:text-white hover:bg-white/[.05] font-medium'
                )}
              >
                <FolderCode className={cn('size-3.5 shrink-0', activeTab === 'project' ? 'text-blue-400' : 'text-white/50')} />
                <span className="truncate">{project}</span>
              </button>
            </div>

            {/* Not in Project Group */}
            <div>
              <div className="px-2.5 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-white/40">
                Not in Project
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('conversations')}
                className={cn(
                  'w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-xl text-left text-[12px] transition-all',
                  activeTab === 'conversations'
                    ? 'bg-white/[.12] text-white font-semibold shadow-sm'
                    : 'text-white/60 hover:text-white hover:bg-white/[.05] font-medium'
                )}
              >
                <MessageSquare className={cn('size-3.5 shrink-0', activeTab === 'conversations' ? 'text-blue-400' : 'text-white/50')} />
                <span>Conversations</span>
              </button>
            </div>
          </div>

          {/* Bottom Group: Shortcuts, Feedback & User Profile (matching reference image) */}
          <div className="pt-2 border-t border-white/10 space-y-1">
            <button
              type="button"
              onClick={() => setActiveTab('shortcuts')}
              className={cn(
                'w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-xl text-left text-[11.5px] transition-all',
                activeTab === 'shortcuts'
                  ? 'bg-white/[.12] text-white font-semibold'
                  : 'text-white/60 hover:text-white hover:bg-white/[.05] font-medium'
              )}
            >
              <Keyboard className="size-3.5 shrink-0 text-white/50" />
              <span>Shortcuts</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('feedback')}
              className={cn(
                'w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-xl text-left text-[11.5px] transition-all',
                activeTab === 'feedback'
                  ? 'bg-white/[.12] text-white font-semibold'
                  : 'text-white/60 hover:text-white hover:bg-white/[.05] font-medium'
              )}
            >
              <MessageCircleQuestion className="size-3.5 shrink-0 text-white/50" />
              <span>Provide Feedback</span>
            </button>

            {/* User Profile Card at foot */}
            <div className="mt-2 pt-2 border-t border-white/10 flex items-center gap-2.5 px-2 py-1.5 rounded-xl bg-white/[.02]">
              <div className="size-7 rounded-full bg-blue-600 flex items-center justify-center text-[12px] font-bold text-white shrink-0 shadow-md shadow-blue-500/25">
                {initial}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[11.5px] font-semibold text-white/90">
                  {displayName}
                </div>
                <div className="truncate text-[10px] text-white/45 font-mono">
                  {displayEmail}
                </div>
              </div>
            </div>
          </div>
        </aside>

        {/* Right Content Panel */}
        <main className="flex-1 flex flex-col min-w-0 bg-[#0e1320] overflow-hidden">
          {/* Header */}
          <header className="h-16 shrink-0 border-b border-white/10 px-6 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-display text-[17px] font-bold tracking-tight text-white">
                  {activeTab === 'project' ? project
                    : activeTab === 'general' ? 'General Settings'
                    : activeTab === 'application' ? 'Application & Runtime'
                    : activeTab === 'appearance' ? 'Appearance'
                    : activeTab === 'models' ? 'Models & AI Engine'
                    : activeTab === 'customizations' ? 'Customizations & Rules'
                    : activeTab === 'browser' ? 'Browser & Deployments'
                    : activeTab === 'conversations' ? 'Conversations History'
                    : activeTab === 'shortcuts' ? 'Keyboard Shortcuts'
                    : 'Provide Feedback'}
                </h2>
                {activeTab === 'project' && (
                  <button title="Rename project" className="text-white/40 hover:text-white transition-colors">
                    <Pencil className="size-3" />
                  </button>
                )}
              </div>
              <p className="text-[11.5px] text-white/50 mt-0.5">
                {activeTab === 'project'
                  ? 'Manage project folders, agent settings, and permissions.'
                  : activeTab === 'general'
                  ? 'Core Ollama engine host, MongoDB connection URI, and cloud synchronization.'
                  : activeTab === 'application'
                  ? 'Local server services status, database daemon, and dev proxies.'
                  : activeTab === 'models'
                  ? 'Configured AI models for planner, design, builder, and testing agents.'
                  : activeTab === 'browser'
                  ? 'E2E browser testing automation parameters and cloud deployment providers.'
                  : 'Customize workspace behavior and environment configuration.'}
              </p>
            </div>

            <button
              onClick={onClose}
              title="Close Settings"
              className="rounded-xl p-1.5 text-white/50 hover:bg-white/10 hover:text-white transition-all"
            >
              <X className="size-4" />
            </button>
          </header>

          {/* Main Scrollable Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar text-white">
            {/* 1. PROJECT TAB (100% Matching Reference Image media_1789155707625.png) */}
            {activeTab === 'project' && (
              <div className="space-y-6 max-w-[800px]">
                {/* Folders Section */}
                <div>
                  <h3 className="text-[13px] font-semibold text-white mb-2.5">
                    Folders
                  </h3>
                  <div className="space-y-2">
                    {projectFolders.map((folder, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[.03] px-3.5 py-2.5 shadow-sm"
                      >
                        <div className="flex items-center gap-2 font-mono text-[12.5px] text-white/90">
                          <Folder className="size-4 text-blue-400/80" />
                          <span>{folder}</span>
                        </div>
                        {projectFolders.length > 1 && (
                          <button
                            type="button"
                            onClick={() => setProjectFolders(projectFolders.filter((_, i) => i !== idx))}
                            className="text-white/40 hover:text-white transition-colors"
                          >
                            <X className="size-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => {
                        const next = prompt('Enter folder path to add:', `${project}/src/`)
                        if (next) setProjectFolders([...projectFolders, next])
                      }}
                      className="w-full py-2.5 rounded-xl border border-dashed border-white/15 bg-white/[.015] hover:bg-white/[.05] hover:border-white/25 text-[12px] font-medium text-white/70 hover:text-white transition-all flex items-center justify-center gap-1.5"
                    >
                      <Plus className="size-3.5" />
                      <span>Add Folder</span>
                    </button>
                  </div>
                </div>

                {/* Agent Settings Section */}
                <div>
                  <h3 className="text-[13px] font-semibold text-white mb-2.5">
                    Agent Settings
                  </h3>
                  <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4 flex items-center justify-between gap-4">
                    <div>
                      <div className="text-[13px] font-medium text-white">Security Preset</div>
                      <div className="text-[11.5px] text-white/50 mt-0.5">Controls the actions the agent can take.</div>
                      <div className="mt-1 flex items-center gap-1 text-[11px] text-blue-400 hover:text-blue-300 cursor-pointer">
                        <span>Learn more about Turbo mode</span>
                        <Info className="size-3 inline" />
                      </div>
                    </div>
                    <div className="relative shrink-0">
                      <select
                        value={securityPreset}
                        onChange={e => setSecurityPreset(e.target.value)}
                        className="h-8 rounded-xl border border-white/10 bg-white/[.06] pl-3 pr-7 text-[11.5px] font-medium text-white appearance-none outline-none cursor-pointer focus:border-blue-500/50"
                      >
                        <option value="turbo" className="bg-[#121622] text-white">Turbo Mode</option>
                        <option value="standard" className="bg-[#121622] text-white">Standard Mode</option>
                        <option value="strict" className="bg-[#121622] text-white">Strict Sandbox</option>
                      </select>
                      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 size-2.5 text-white/40" />
                    </div>
                  </div>
                </div>

                {/* Agent Behavior Section */}
                <div>
                  <h3 className="text-[13px] font-semibold text-white mb-2.5">
                    Agent Behavior
                  </h3>
                  <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4 flex items-center justify-between gap-4">
                    <div>
                      <div className="text-[13px] font-medium text-white">Artifact Review Policy</div>
                      <div className="text-[11.5px] text-white/50 mt-0.5">Whether the agent asks you to review its documents.</div>
                    </div>
                    <div className="relative shrink-0">
                      <select
                        value={artifactPolicy}
                        onChange={e => setArtifactPolicy(e.target.value)}
                        className="h-8 rounded-xl border border-white/10 bg-white/[.06] pl-3 pr-7 text-[11.5px] font-medium text-white appearance-none outline-none cursor-pointer focus:border-blue-500/50"
                      >
                        <option value="inherit" className="bg-[#121622] text-white">Inherit General</option>
                        <option value="always" className="bg-[#121622] text-white">Always Review</option>
                        <option value="auto" className="bg-[#121622] text-white">Auto-Accept</option>
                      </select>
                      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 size-2.5 text-white/40" />
                    </div>
                  </div>
                </div>

                {/* Local Permissions Section */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="text-[13px] font-semibold text-white">
                      Local Permissions
                    </h3>
                  </div>
                  <p className="text-[11.5px] text-white/50 mb-2.5">
                    Also includes <span className="text-blue-400 hover:underline cursor-pointer" onClick={() => setActiveTab('general')}>global settings</span> when working in this project.{' '}
                    <span className="text-blue-400 hover:underline cursor-pointer">Learn more.</span>
                  </p>

                  <div className="rounded-2xl border border-white/10 bg-white/[.025] divide-y divide-white/10">
                    <div className="p-4 flex items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-[13px] font-medium text-white">File Access Rules</span>
                          <span className="rounded-md bg-white/[.08] px-1.5 py-0.2 text-[10.5px] font-semibold text-white/70">2</span>
                        </div>
                        <div className="text-[11.5px] text-white/50 mt-0.5">
                          Configure allowed and denied paths for file reads and writes.
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setRulesModal('file')}
                        className="rounded-xl border border-white/10 bg-white/[.05] px-3.5 py-1.5 text-[11.5px] font-medium text-white hover:bg-white/[.10] transition-colors"
                      >
                        Open
                      </button>
                    </div>

                    <div className="p-4 flex items-center justify-between gap-4">
                      <div>
                        <span className="text-[13px] font-medium text-white">Network Access Rules</span>
                        <div className="text-[11.5px] text-white/50 mt-0.5">
                          Configure allowed and denied URLs for reading.
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setRulesModal('network')}
                        className="rounded-xl border border-white/10 bg-white/[.05] px-3.5 py-1.5 text-[11.5px] font-medium text-white hover:bg-white/[.10] transition-colors"
                      >
                        Open
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 2. GENERAL TAB (Preserving core server configuration) */}
            {activeTab === 'general' && (
              <div className="space-y-5 max-w-[800px]">
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-white/70">Ollama Host</span>
                    <input
                      value={host}
                      onChange={e => setHost(e.target.value)}
                      placeholder="http://127.0.0.1:11434"
                      className="w-full rounded-xl border border-white/10 bg-white/[.04] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-white/30 focus:border-blue-500/60"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-white/70">ollama.com API Key</span>
                    <input
                      type="password"
                      value={key}
                      onChange={e => setKey(e.target.value)}
                      placeholder={meta?.api_key_hint ? `key saved (${meta.api_key_hint})` : 'Paste your key'}
                      className="w-full rounded-xl border border-white/10 bg-white/[.04] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-white/30 focus:border-blue-500/60"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-white/70">Local Context Window</span>
                    <input
                      value={ctx}
                      onChange={e => setCtx(e.target.value)}
                      placeholder="e.g. 32768"
                      className="w-full rounded-xl border border-white/10 bg-white/[.04] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-white/30 focus:border-blue-500/60"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-white/70">MongoDB URI</span>
                    <input
                      value={mongo}
                      onChange={e => setMongo(e.target.value)}
                      placeholder={meta?.mongodb_uri_set ? `saved (${meta.mongodb_uri_hint})` : 'MongoDB URI or cluster string'}
                      className="w-full rounded-xl border border-white/10 bg-white/[.04] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-white/30 focus:border-blue-500/60"
                    />
                  </label>
                </div>

                <MongoState mongo={meta?.mongo} />

                <div className="flex items-center justify-between pt-3 border-t border-white/10">
                  <div className="flex items-center gap-2 text-[11.5px]">
                    <span className={cn('size-2 rounded-full', cloudOn ? 'bg-emerald-400' : 'bg-amber-400')} />
                    <span className="text-white/60 font-mono">{note}</span>
                  </div>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={save}
                    className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 font-display text-[12px] font-semibold text-white shadow-lg shadow-blue-500/25 hover:bg-blue-500 disabled:opacity-50 transition-all"
                  >
                    {saving && <Loader2 className="size-3 animate-spin" />}
                    <span>Save Settings</span>
                  </button>
                </div>
              </div>
            )}

            {/* 3. APPLICATION & RUNTIME TAB */}
            {activeTab === 'application' && (
              <div className="space-y-4 max-w-[800px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-[13px] font-medium text-white">Studio HTTP Gateway</div>
                      <div className="text-[11.5px] text-white/50">Active on port 7824 with CORS enabled</div>
                    </div>
                    <span className="rounded-md bg-emerald-500/20 px-2 py-0.5 text-[10.5px] font-semibold text-emerald-300">
                      Running
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-3 border-t border-white/10">
                    <div>
                      <div className="text-[13px] font-medium text-white">WebSocket Stream Bridge</div>
                      <div className="text-[11.5px] text-white/50">Active on ws://127.0.0.1:7825</div>
                    </div>
                    <span className="rounded-md bg-emerald-500/20 px-2 py-0.5 text-[10.5px] font-semibold text-emerald-300">
                      Connected
                    </span>
                  </div>
                </div>

                <MongoState mongo={meta?.mongo} />

                {meta?.mongo && !meta.mongo.downloaded && !meta.mongo.override && (
                  <button
                    type="button"
                    onClick={() => api.mongoPrefetch().catch(() => { })}
                    className="rounded-xl border border-white/15 bg-white/[.06] px-4 py-2 text-[12px] font-medium text-white hover:bg-white/[.12] transition-colors"
                  >
                    Download mongod binary
                  </button>
                )}
              </div>
            )}

            {/* 4. MODELS TAB */}
            {activeTab === 'models' && (
              <div className="space-y-4 max-w-[800px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-[13px] font-medium text-white">Builder Agent Model</div>
                      <div className="text-[11.5px] text-white/50">Used for generating source code and dependencies.</div>
                    </div>
                    <span className="rounded-lg bg-white/[.06] px-3 py-1 font-mono text-[11.5px] text-blue-300">
                      qwen2.5-coder:32b
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-3 border-t border-white/10">
                    <div>
                      <div className="text-[13px] font-medium text-white">Planner & Architecture Model</div>
                      <div className="text-[11.5px] text-white/50">Used for project blueprint and SRS requirements.</div>
                    </div>
                    <span className="rounded-lg bg-white/[.06] px-3 py-1 font-mono text-[11.5px] text-blue-300">
                      qwen2.5-coder:32b
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-3 border-t border-white/10">
                    <div>
                      <div className="text-[13px] font-medium text-white">Testing & QA Agent Model</div>
                      <div className="text-[11.5px] text-white/50">Used for writing unit tests and E2E verification.</div>
                    </div>
                    <span className="rounded-lg bg-white/[.06] px-3 py-1 font-mono text-[11.5px] text-emerald-300">
                      deepseek-r1:14b
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* 5. APPEARANCE TAB */}
            {activeTab === 'appearance' && (
              <div className="space-y-4 max-w-[800px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4 flex items-center justify-between">
                  <div>
                    <div className="text-[13px] font-medium text-white">Theme Palette</div>
                    <div className="text-[11.5px] text-white/50">Dark Bolt.new edge-to-edge aesthetic</div>
                  </div>
                  <span className="rounded-xl border border-blue-500/40 bg-blue-600/20 px-3 py-1 text-[11.5px] font-semibold text-blue-300">
                    Dark Bolt (Default)
                  </span>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4 flex items-center justify-between">
                  <div>
                    <div className="text-[13px] font-medium text-white">Editor Font Ligatures</div>
                    <div className="text-[11.5px] text-white/50">Enable modern font ligatures in code preview</div>
                  </div>
                  <span className="rounded-xl bg-white/[.06] px-3 py-1 text-[11.5px] font-medium text-white">
                    Enabled
                  </span>
                </div>
              </div>
            )}

            {/* 6. CUSTOMIZATIONS TAB */}
            {activeTab === 'customizations' && (
              <div className="space-y-4 max-w-[800px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4 space-y-2">
                  <div className="text-[13px] font-medium text-white">Custom Agent Skills</div>
                  <div className="text-[11.5px] text-white/50">
                    AgentForge loads skills from <code className="text-blue-300">.agentforge/skills</code> in the active workspace.
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/[.03] p-3 text-[11px] font-mono text-white/80">
                    d:\Github\RP-SE-009\.agentforge\skills
                  </div>
                </div>
              </div>
            )}

            {/* 7. BROWSER & DEPLOY TAB */}
            {activeTab === 'browser' && (
              <div className="space-y-5 max-w-[800px]">
                <DeployAccounts deploy={meta?.deploy} onSaved={() => {
                  api.settings().then(setMeta).catch(() => { })
                  onSaved?.()
                }} />
              </div>
            )}

            {/* 8. CONVERSATIONS TAB */}
            {activeTab === 'conversations' && (
              <div className="space-y-4 max-w-[800px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] p-4 flex items-center justify-between">
                  <div>
                    <div className="text-[13px] font-medium text-white">Active Conversation Memory</div>
                    <div className="text-[11.5px] text-white/50">Retains recent chat turns and tool execution trace.</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => alert('Conversation memory is active and synchronizing with server.')}
                    className="rounded-xl border border-white/10 bg-white/[.05] px-3 py-1.5 text-[11.5px] font-medium text-white hover:bg-white/[.10]"
                  >
                    Export Transcript
                  </button>
                </div>
              </div>
            )}

            {/* 9. SHORTCUTS TAB */}
            {activeTab === 'shortcuts' && (
              <div className="space-y-3 max-w-[800px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] divide-y divide-white/10">
                  {[
                    { key: 'Ctrl / ⌘ + Enter', action: 'Submit prompt & begin build' },
                    { key: 'Escape', action: 'Dismiss modals or active dropdowns' },
                    { key: 'Ctrl / ⌘ + B', action: 'Toggle sidebar collapse state' },
                    { key: 'Ctrl / ⌘ + K', action: 'Open quick project command bar' },
                    { key: 'Ctrl / ⌘ + /', action: 'Focus prompt input box' },
                  ].map((s, i) => (
                    <div key={i} className="p-3.5 flex items-center justify-between">
                      <span className="text-[12.5px] text-white/80">{s.action}</span>
                      <kbd className="rounded-lg border border-white/15 bg-white/[.08] px-2.5 py-1 font-mono text-[11px] text-white font-medium">
                        {s.key}
                      </kbd>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 10. FEEDBACK TAB */}
            {activeTab === 'feedback' && (
              <div className="space-y-4 max-w-[800px]">
                {feedbackSubmitted ? (
                  <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-5 text-center">
                    <Check className="size-6 text-emerald-400 mx-auto mb-2" />
                    <div className="text-[14px] font-semibold text-white">Thank you for your feedback!</div>
                    <div className="text-[11.5px] text-white/60 mt-1">Our engineering team reviews all community input.</div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-white/10 bg-white/[.025] p-5 space-y-3">
                    <div className="text-[13px] font-medium text-white">Tell us what you think</div>
                    <textarea
                      rows={4}
                      value={feedbackText}
                      onChange={e => setFeedbackText(e.target.value)}
                      placeholder="Share bug reports, feature suggestions, or general feedback..."
                      className="w-full rounded-xl border border-white/10 bg-white/[.04] p-3 text-[12px] text-white outline-none placeholder:text-white/35 focus:border-blue-500/50 resize-none"
                    />
                    <button
                      type="button"
                      disabled={!feedbackText.trim()}
                      onClick={() => setFeedbackSubmitted(true)}
                      className="rounded-xl bg-blue-600 px-4 py-2 font-display text-[12px] font-semibold text-white shadow-md hover:bg-blue-500 disabled:opacity-40 transition-all"
                    >
                      Submit Feedback
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Auxiliary Rules Modal Popup */}
      {rulesModal && (
        <div className="fixed inset-0 z-[700] flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-2xl border border-white/15 bg-[#121622] p-5 shadow-2xl space-y-3 text-white">
            <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
              <h3 className="font-display text-[14px] font-bold">
                {rulesModal === 'file' ? 'File Access Rules' : 'Network Access Rules'}
              </h3>
              <button onClick={() => setRulesModal(null)} className="text-white/40 hover:text-white">
                <X className="size-3.5" />
              </button>
            </div>
            <div className="text-[12px] text-white/60 space-y-2">
              {rulesModal === 'file' ? (
                <>
                  <div className="rounded-lg bg-white/[.03] border border-white/10 p-2 font-mono text-[11px]">
                    ALLOW: ./** (Workspace read/write)
                  </div>
                  <div className="rounded-lg bg-white/[.03] border border-white/10 p-2 font-mono text-[11px]">
                    DENY: ../** (External traversal blocked)
                  </div>
                </>
              ) : (
                <div className="rounded-lg bg-white/[.03] border border-white/10 p-2 font-mono text-[11px]">
                  ALLOW: * (HTTP/HTTPS GET requests allowed for web research)
                </div>
              )}
            </div>
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                onClick={() => setRulesModal(null)}
                className="rounded-xl bg-white/[.08] hover:bg-white/[.12] px-3.5 py-1.5 text-[11.5px] font-medium text-white"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </Modal>
  )
}

function MongoState({ mongo }) {
  if (!mongo) return null
  let text, tone
  if (mongo.override) {
    text = 'using your MONGODB_URI'
    tone = 'text-emerald-300'
  } else if (mongo.running) {
    text = mongo.external
      ? `adopted the MongoDB already on :${mongo.port}`
      : `MongoDB running on :${mongo.port}`
    tone = 'text-emerald-300'
  } else if (mongo.downloaded) {
    text = 'mongod downloaded, not running'
    tone = 'text-amber-300'
  } else {
    text = mongo.reason || 'mongod not downloaded yet'
    tone = mongo.reason ? 'text-rose-400' : 'text-white/50'
  }
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[.03] px-3.5 py-2 font-mono text-[11px] text-white/80">
      <Database className="size-3.5 shrink-0 text-blue-400" />
      <span className={tone}>{text}</span>
    </div>
  )
}
