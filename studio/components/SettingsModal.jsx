'use client'

import { useEffect, useState } from 'react'
import {
  Check, Cpu, Database, Keyboard,
  LayoutGrid, Loader2, Palette, SlidersHorizontal, X, Link2,
} from 'lucide-react'
import { api } from '@/lib/api'
import { Modal } from './ui'
import { cn } from '@/lib/utils'
import { useStore } from '@/lib/store'
import { useAuthStore } from '@/lib/auth'
import { modelLabel } from '@/lib/models'
import DeployAccounts from './deploy/DeployAccounts'

export default function SettingsModal({ onClose, onSaved }) {
  const storeModels = useStore(s => s.models)
  const user = useAuthStore(s => s.user)

  const [activeTab, setActiveTab] = useState('general')

  // Real server settings — loaded via api.settings()
  const [host, setHost] = useState('')
  const [ctx, setCtx] = useState('')
  const [key, setKey] = useState('')
  const [mongo, setMongo] = useState('')
  const [meta, setMeta] = useState(null)
  const [saving, setSaving] = useState(false)
  const [note, setNote] = useState('loading…')
  const [tone, setTone] = useState('muted')

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
  // AgentForge's own engine and database are the whole machine's, so they are
  // its admin's. Everyone's deployment accounts are their own — Integrations.
  const isAdmin = Boolean(meta?.admin)

  const displayName = user?.name || user?.username || 'User'
  const displayEmail = user?.email || ''
  const initial = (user?.name || user?.username || 'U')[0]?.toUpperCase() || 'U'

  const settingsNav = [
    { id: 'general',      label: 'General',      Icon: SlidersHorizontal },
    { id: 'application',  label: 'Application',  Icon: LayoutGrid },
    { id: 'models',       label: 'Models',       Icon: Cpu },
    { id: 'appearance',   label: 'Appearance',   Icon: Palette },
    { id: 'integrations', label: 'Integrations', Icon: Link2 },
    { id: 'shortcuts',    label: 'Shortcuts',    Icon: Keyboard },
  ]

  return (
    <Modal onClose={onClose} className="max-w-none w-[min(1040px,95vw)] h-[min(650px,88vh)] p-0 overflow-hidden flex flex-col rounded-[26px] border border-white/15 bg-[#0e1320] shadow-[0_30px_90px_rgba(0,0,0,0.85)]">
      <div className="flex flex-1 min-h-0 overflow-hidden">

        {/* ── Left Sidebar ── */}
        <aside className="w-56 shrink-0 border-r border-white/10 bg-[#0a0d16]/95 flex flex-col justify-between p-3 select-none">
          <div className="flex-1 overflow-y-auto pr-1">
            <div className="px-2.5 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-wider text-white/35">
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
                        : 'text-white/55 hover:text-white hover:bg-white/[.05] font-medium'
                    )}
                  >
                    <item.Icon className={cn('size-3.5 shrink-0', active ? 'text-blue-400' : 'text-white/40')} />
                    <span>{item.label}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* User profile footer */}
          <div className="pt-2 border-t border-white/10">
            <div className="flex items-center gap-2.5 px-2 py-2 rounded-xl bg-white/[.02]">
              <div className="size-7 rounded-full bg-blue-600 flex items-center justify-center text-[12px] font-bold text-white shrink-0 shadow-md shadow-blue-500/25">
                {initial}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[11.5px] font-semibold text-white/90">{displayName}</div>
                {displayEmail && (
                  <div className="truncate text-[10px] text-white/40 font-mono">{displayEmail}</div>
                )}
              </div>
            </div>
          </div>
        </aside>

        {/* ── Right Content ── */}
        <main className="flex-1 flex flex-col min-w-0 bg-[#0e1320] overflow-hidden">
          {/* Header */}
          <header className="h-[58px] shrink-0 border-b border-white/10 px-6 flex items-center justify-between">
            <div>
              <h2 className="font-display text-[16px] font-bold tracking-tight text-white">
                {activeTab === 'general'      ? 'General'
               : activeTab === 'application'  ? 'Application'
               : activeTab === 'models'       ? 'AI Models'
               : activeTab === 'appearance'   ? 'Appearance'
               : activeTab === 'integrations' ? 'Integrations'
               : 'Keyboard Shortcuts'}
              </h2>
              <p className="text-[11px] text-white/40 mt-0.5">
                {activeTab === 'general'
                  ? isAdmin ? 'Ollama engine, API key and MongoDB connection.'
                            : 'What this machine runs, and what is yours.'
                  : activeTab === 'application'
                  ? 'Running services and database status.'
                  : activeTab === 'models'
                  ? 'Active AI models for each build role.'
                  : activeTab === 'appearance'
                  ? 'Studio visual theme.'
                  : activeTab === 'integrations'
                  ? 'Connect GitHub, AWS, Vercel and production database for deployments.'
                  : 'Key bindings active in AgentForge Studio.'}
              </p>
            </div>
            <button
              onClick={onClose}
              title="Close"
              className="rounded-xl p-1.5 text-white/40 hover:bg-white/10 hover:text-white transition-all"
            >
              <X className="size-4" />
            </button>
          </header>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-5 text-white" style={{ scrollbarWidth: 'thin' }}>

            {/* ── GENERAL ── */}
            {activeTab === 'general' && !isAdmin && (
              <div className="space-y-4 max-w-[700px]">
                <p className="rounded-xl border border-white/10 bg-white/[.03] px-4 py-3 text-[12px] text-white/60">
                  The Ollama engine, its key and AgentForge's own database are
                  shared by everyone on this machine, so only its admin changes
                  them. Your GitHub, AWS, Vercel and production database are
                  yours alone — they are under <b className="text-white/80">Integrations</b>.
                </p>
                <MongoState mongo={meta?.mongo} />
              </div>
            )}

            {activeTab === 'general' && isAdmin && (
              <div className="space-y-5 max-w-[700px]">
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-white/55">Ollama Host</span>
                    <input
                      value={host}
                      onChange={e => setHost(e.target.value)}
                      placeholder="http://127.0.0.1:11434"
                      className="w-full rounded-xl border border-white/10 bg-white/[.04] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-white/25 focus:border-blue-500/60 transition-colors"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-white/55">ollama.com API Key</span>
                    <input
                      type="password"
                      value={key}
                      onChange={e => setKey(e.target.value)}
                      placeholder={meta?.api_key_hint ? `saved (${meta.api_key_hint})` : 'Paste your key'}
                      className="w-full rounded-xl border border-white/10 bg-white/[.04] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-white/25 focus:border-blue-500/60 transition-colors"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-white/55">Local Context Window</span>
                    <input
                      value={ctx}
                      onChange={e => setCtx(e.target.value)}
                      placeholder="e.g. 32768"
                      className="w-full rounded-xl border border-white/10 bg-white/[.04] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-white/25 focus:border-blue-500/60 transition-colors"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-white/55">MongoDB URI</span>
                    <input
                      value={mongo}
                      onChange={e => setMongo(e.target.value)}
                      placeholder={meta?.mongodb_uri_set ? `saved (${meta.mongodb_uri_hint})` : 'mongodb+srv://…'}
                      className="w-full rounded-xl border border-white/10 bg-white/[.04] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-white/25 focus:border-blue-500/60 transition-colors"
                    />
                  </label>
                </div>

                <MongoState mongo={meta?.mongo} />

                <div className="flex items-center justify-between pt-4 border-t border-white/10">
                  <div className="flex items-center gap-2 text-[11.5px]">
                    <span className={cn(
                      'size-2 rounded-full',
                      cloudOn ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]'
                      : tone === 'bad' ? 'bg-rose-400'
                      : 'bg-amber-400'
                    )} />
                    <span className="text-white/50 font-mono">{note}</span>
                  </div>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={save}
                    className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-[12px] font-semibold text-white shadow-lg shadow-blue-500/20 hover:bg-blue-500 disabled:opacity-50 transition-all active:scale-95"
                  >
                    {saving && <Loader2 className="size-3.5 animate-spin" />}
                    Save Settings
                  </button>
                </div>
              </div>
            )}

            {/* ── APPLICATION ── */}
            {activeTab === 'application' && (
              <div className="space-y-4 max-w-[700px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] divide-y divide-white/10">
                  {[
                    { name: 'HTTP Gateway',     desc: 'API server on port 7824',              status: 'Running' },
                    { name: 'WebSocket Bridge', desc: 'Live stream on ws://127.0.0.1:7825',   status: 'Connected' },
                    { name: 'SRS Agent',        desc: 'Specification planner on port 7826',   status: 'Running' },
                  ].map(svc => (
                    <div key={svc.name} className="flex items-center justify-between p-4">
                      <div>
                        <div className="text-[13px] font-medium text-white">{svc.name}</div>
                        <div className="text-[11.5px] text-white/40 mt-0.5">{svc.desc}</div>
                      </div>
                      <span className="rounded-lg bg-emerald-500/15 border border-emerald-500/20 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
                        {svc.status}
                      </span>
                    </div>
                  ))}
                </div>

                <MongoState mongo={meta?.mongo} />

                {isAdmin && meta?.mongo && !meta.mongo.downloaded && !meta.mongo.override && (
                  <button
                    type="button"
                    onClick={() => api.mongoPrefetch().catch(() => {})}
                    className="rounded-xl border border-white/15 bg-white/[.05] px-4 py-2 text-[12px] font-medium text-white hover:bg-white/[.10] transition-colors"
                  >
                    Download mongod binary
                  </button>
                )}
              </div>
            )}

            {/* ── MODELS ── */}
            {activeTab === 'models' && (
              <div className="space-y-4 max-w-[700px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] divide-y divide-white/10">
                  {[
                    { role: 'Agent (default)', key: 'agent' },
                    { role: 'Builder',         key: 'builder' },
                    { role: 'Planner',         key: 'planner' },
                    { role: 'Design',          key: 'design' },
                    { role: 'QA & Testing',    key: 'qa' },
                    { role: 'SRS',             key: 'srs' },
                  ].map(({ role, key }) => {
                    const m = storeModels?.[key] || ''
                    const label = m ? (modelLabel ? modelLabel(m) : m) : '—'
                    return (
                      <div key={key} className="flex items-center justify-between px-4 py-3.5">
                        <div className="text-[12.5px] font-medium text-white/75">{role}</div>
                        <span className="rounded-lg bg-white/[.06] border border-white/10 px-3 py-1 font-mono text-[11px] text-blue-300 max-w-[260px] truncate">
                          {label}
                        </span>
                      </div>
                    )
                  })}
                </div>
                <p className="text-[11px] text-white/30">
                  Models are selected in the build panel when starting a project.
                </p>
              </div>
            )}

            {/* ── APPEARANCE ── */}
            {activeTab === 'appearance' && (
              <div className="space-y-4 max-w-[700px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] p-5">
                  <div className="text-[13px] font-medium text-white mb-3">Color Theme</div>
                  <div className="grid grid-cols-2 gap-3">
                    {/* Dark Bolt — active */}
                    <div className="relative rounded-xl border-2 border-blue-500/60 bg-[#0c0f17] p-4 shadow-[0_0_20px_rgba(59,130,246,0.12)]">
                      <div className="flex gap-1.5 mb-3">
                        <span className="size-2.5 rounded-full bg-[#1a2035]" />
                        <span className="size-2.5 rounded-full bg-blue-500/60" />
                        <span className="size-2.5 rounded-full bg-purple-500/60" />
                      </div>
                      <div className="text-[12px] font-semibold text-white">Dark Bolt</div>
                      <div className="text-[10.5px] text-white/40 mt-0.5">Active theme</div>
                      <Check className="absolute top-3 right-3 size-3.5 text-blue-400" />
                    </div>

                    {/* Light — coming soon */}
                    <div className="rounded-xl border border-white/10 bg-white/[.03] p-4 opacity-35 cursor-not-allowed">
                      <div className="flex gap-1.5 mb-3">
                        <span className="size-2.5 rounded-full bg-white/20" />
                        <span className="size-2.5 rounded-full bg-white/30" />
                        <span className="size-2.5 rounded-full bg-white/40" />
                      </div>
                      <div className="text-[12px] font-semibold text-white/50">Light</div>
                      <div className="text-[10.5px] text-white/25 mt-0.5">Coming soon</div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ── INTEGRATIONS ── */}
            {activeTab === 'integrations' && (
              <div className="space-y-4 max-w-[700px]">
                <DeployAccounts deploy={meta?.deploy} onSaved={() => {
                  api.settings().then(setMeta).catch(() => {})
                  onSaved?.()
                }} />
              </div>
            )}

            {/* ── SHORTCUTS ── */}
            {activeTab === 'shortcuts' && (
              <div className="max-w-[700px]">
                <div className="rounded-2xl border border-white/10 bg-white/[.025] divide-y divide-white/10">
                  {[
                    { key: 'Ctrl + Enter', action: 'Submit prompt and start build' },
                    { key: 'Escape',       action: 'Close modal or dropdown' },
                    { key: 'Ctrl + /',     action: 'Focus prompt input' },
                  ].map((s, i) => (
                    <div key={i} className="flex items-center justify-between px-4 py-3.5">
                      <span className="text-[12.5px] text-white/75">{s.action}</span>
                      <kbd className="rounded-lg border border-white/15 bg-white/[.07] px-2.5 py-1 font-mono text-[11px] text-white font-medium">
                        {s.key}
                      </kbd>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        </main>
      </div>
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
    tone = mongo.reason ? 'text-rose-400' : 'text-white/40'
  }
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[.03] px-3.5 py-2.5 font-mono text-[11px]">
      <Database className="size-3.5 shrink-0 text-blue-400" />
      <span className={tone}>{text}</span>
    </div>
  )
}
