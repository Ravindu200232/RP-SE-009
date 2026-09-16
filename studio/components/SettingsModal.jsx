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
    <Modal onClose={onClose} className="max-w-none w-[min(1040px,95vw)] h-[min(650px,90vh)] p-0 overflow-hidden flex flex-col rounded-3xl border border-[rgba(145,158,171,0.2)] bg-[#141A21] shadow-[0_0_2px_0_rgba(145,158,171,0.2),0_24px_48px_0_rgba(0,0,0,0.24)]">
      <div className="flex flex-col sm:flex-row flex-1 min-h-0 overflow-hidden">

        {/* ── Left Sidebar / Mobile Top Nav ── */}
        <aside className="w-full sm:w-56 shrink-0 border-b sm:border-b-0 sm:border-r border-[rgba(145,158,171,0.16)] bg-[#1C252E] flex sm:flex-col justify-between p-2 sm:p-3 select-none">
          <div className="flex-1 overflow-x-auto sm:overflow-y-auto no-scrollbar sm:pr-1">
            <div className="hidden sm:block px-2.5 pb-2 pt-1 text-[11px] font-semibold uppercase tracking-wider text-[#919EAB]/60">
              Settings
            </div>
            <div className="flex sm:flex-col gap-1 sm:gap-0.5">
              {settingsNav.map(item => {
                const active = activeTab === item.id
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveTab(item.id)}
                    className={cn(
                      'shrink-0 sm:w-full flex items-center gap-2 sm:gap-2.5 px-2.5 py-1.5 rounded-xl text-left text-[12px] whitespace-nowrap transition-all',
                      active
                        ? 'bg-[#1877F2]/12 text-[#1877F2] font-semibold shadow-sm'
                        : 'text-[#919EAB] hover:text-white hover:bg-[rgba(145,158,171,0.08)] font-medium'
                    )}
                  >
                    <item.Icon className={cn('size-3.5 shrink-0', active ? 'text-[#1877F2]' : 'text-[#919EAB]/60')} />
                    <span>{item.label}</span>
                  </button>
                )
              })}
            </div>
          </div>

          {/* User profile footer */}
          <div className="hidden sm:block pt-2 border-t border-[rgba(145,158,171,0.16)]">
            <div className="flex items-center gap-2.5 px-2 py-2 rounded-xl bg-[rgba(145,158,171,0.06)] border border-[rgba(145,158,171,0.1)]">
              <div className="size-7 rounded-full bg-[#1877F2] flex items-center justify-center text-[12px] font-bold text-white shrink-0 shadow-md shadow-[#1877F2]/25">
                {initial}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[11.5px] font-semibold text-white/90">{displayName}</div>
                {displayEmail && (
                  <div className="truncate text-[10px] text-[#919EAB] font-mono">{displayEmail}</div>
                )}
              </div>
            </div>
          </div>
        </aside>

        {/* ── Right Content ── */}
        <main className="flex-1 flex flex-col min-w-0 bg-[#141A21] overflow-hidden">
          {/* Header */}
          <header className="h-[52px] sm:h-[58px] shrink-0 border-b border-[rgba(145,158,171,0.16)] px-4 sm:px-6 flex items-center justify-between">
            <div className="min-w-0 flex-1 pr-2">
              <h2 className="font-display text-[15px] sm:text-[16px] font-bold tracking-tight text-white truncate">
                {activeTab === 'general'      ? 'General'
               : activeTab === 'application'  ? 'Application'
               : activeTab === 'models'       ? 'AI Models'
               : activeTab === 'appearance'   ? 'Appearance'
               : activeTab === 'integrations' ? 'Integrations'
               : 'Keyboard Shortcuts'}
              </h2>
              <p className="text-[10.5px] sm:text-[11px] text-white/40 mt-0.5 truncate">
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
                  ? 'Connect GitHub, AWS, Vercel, Netlify, Azure and your production database.'
                  : 'Key bindings active in AgentForge Studio.'}
              </p>
            </div>
            <button
              onClick={onClose}
              title="Close"
              className="rounded-xl p-1.5 text-[#919EAB] hover:bg-[rgba(145,158,171,0.08)] hover:text-white transition-all shrink-0"
            >
              <X className="size-4" />
            </button>
          </header>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 text-white" style={{ scrollbarWidth: 'thin' }}>

            {/* ── GENERAL ── */}
            {activeTab === 'general' && !isAdmin && (
              <div className="space-y-4 max-w-[700px]">
                <p className="rounded-2xl border border-[rgba(145,158,171,0.16)] bg-[#1C252E] px-4 py-3 text-[12px] text-[#919EAB]">
                  The Ollama engine, its key and AgentForge's own database are
                  shared by everyone on this machine, so only its admin changes
                  them. Your GitHub, AWS, Vercel and production database are
                  yours alone — they are under <b className="text-white">Integrations</b>.
                </p>
                <MongoState mongo={meta?.mongo} />
              </div>
            )}

            {activeTab === 'general' && isAdmin && (
              <div className="space-y-5 max-w-[700px]">
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-[#919EAB]">Ollama Host</span>
                    <input
                      value={host}
                      onChange={e => setHost(e.target.value)}
                      placeholder="http://127.0.0.1:11434"
                      className="w-full rounded-xl border border-[rgba(145,158,171,0.2)] bg-[#1C252E] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-[#919EAB]/30 focus:border-[#1877F2] focus:ring-1 focus:ring-[#1877F2] transition-colors"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-[#919EAB]">ollama.com API Key</span>
                    <input
                      type="password"
                      value={key}
                      onChange={e => setKey(e.target.value)}
                      placeholder={meta?.api_key_hint ? `saved (${meta.api_key_hint})` : 'Paste your key'}
                      className="w-full rounded-xl border border-[rgba(145,158,171,0.2)] bg-[#1C252E] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-[#919EAB]/30 focus:border-[#1877F2] focus:ring-1 focus:ring-[#1877F2] transition-colors"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-[#919EAB]">Local Context Window</span>
                    <input
                      value={ctx}
                      onChange={e => setCtx(e.target.value)}
                      placeholder="e.g. 32768"
                      className="w-full rounded-xl border border-[rgba(145,158,171,0.2)] bg-[#1C252E] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-[#919EAB]/30 focus:border-[#1877F2] focus:ring-1 focus:ring-[#1877F2] transition-colors"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-1.5 block text-[11.5px] font-semibold text-[#919EAB]">MongoDB URI</span>
                    <input
                      value={mongo}
                      onChange={e => setMongo(e.target.value)}
                      placeholder={meta?.mongodb_uri_set ? `saved (${meta.mongodb_uri_hint})` : 'mongodb+srv://…'}
                      className="w-full rounded-xl border border-[rgba(145,158,171,0.2)] bg-[#1C252E] px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-[#919EAB]/30 focus:border-[#1877F2] focus:ring-1 focus:ring-[#1877F2] transition-colors"
                    />
                  </label>
                </div>

                <MongoState mongo={meta?.mongo} />

                <div className="flex items-center justify-between pt-4 border-t border-[rgba(145,158,171,0.16)]">
                  <div className="flex items-center gap-2 text-[11.5px]">
                    <span className={cn(
                      'size-2 rounded-full',
                      cloudOn ? 'bg-[#22C55E] shadow-[0_0_6px_rgba(34,197,94,0.6)]'
                      : tone === 'bad' ? 'bg-[#FF5630]'
                      : 'bg-[#FFAB00]'
                    )} />
                    <span className="text-[#919EAB] font-mono">{note}</span>
                  </div>
                  <button
                    type="button"
                    disabled={saving}
                    onClick={save}
                    className="inline-flex items-center gap-2 rounded-xl bg-[#1877F2] px-4 py-2 text-[12px] font-semibold text-white shadow-[0_8px_16px_0_rgba(24,119,242,0.24)] hover:bg-[#0C44AE] disabled:opacity-50 transition-all active:scale-95"
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
                <div className="rounded-2xl border border-[rgba(145,158,171,0.16)] bg-[#1C252E] divide-y divide-[rgba(145,158,171,0.12)]">
                  {[
                    { name: 'HTTP Gateway',     desc: 'API server on port 7824',              status: 'Running' },
                    { name: 'WebSocket Bridge', desc: 'Live stream on ws://127.0.0.1:7825',   status: 'Connected' },
                    { name: 'SRS Agent',        desc: 'Specification planner on port 7826',   status: 'Running' },
                  ].map(svc => (
                    <div key={svc.name} className="flex items-center justify-between p-4">
                      <div>
                        <div className="text-[13px] font-medium text-white">{svc.name}</div>
                        <div className="text-[11.5px] text-[#919EAB] mt-0.5">{svc.desc}</div>
                      </div>
                      <span className="rounded-lg bg-[#22C55E]/15 border border-[#22C55E]/20 px-2.5 py-0.5 text-[11px] font-semibold text-[#22C55E]">
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
                    className="rounded-xl border border-[rgba(145,158,171,0.2)] bg-[#28323D]/50 px-4 py-2 text-[12px] font-medium text-white hover:bg-[#333F4D]/60 transition-colors"
                  >
                    Download mongod binary
                  </button>
                )}
              </div>
            )}

            {/* ── MODELS ── */}
            {activeTab === 'models' && (
              <div className="space-y-4 max-w-[700px]">
                <div className="rounded-2xl border border-[rgba(145,158,171,0.16)] bg-[#1C252E] divide-y divide-[rgba(145,158,171,0.12)]">
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
                        <div className="text-[12.5px] font-medium text-white/90">{role}</div>
                        <span className="rounded-lg bg-[#1877F2]/10 border border-[#1877F2]/20 px-3 py-1 font-mono text-[11px] text-[#1877F2] max-w-[260px] truncate">
                          {label}
                        </span>
                      </div>
                    )
                  })}
                </div>
                <p className="text-[11px] text-[#919EAB]">
                  Models are selected in the build panel when starting a project.
                </p>
              </div>
            )}

            {/* ── APPEARANCE ── */}
            {activeTab === 'appearance' && (
              <div className="space-y-4 max-w-[700px]">
                <div className="rounded-2xl border border-[rgba(145,158,171,0.16)] bg-[#1C252E] p-5">
                  <div className="text-[13px] font-medium text-white mb-3">Color Theme</div>
                  <div className="grid grid-cols-2 gap-3">
                    {/* Dark Bolt — active */}
                    <div className="relative rounded-xl border-2 border-[#1877F2] bg-[#141A21] p-4 shadow-[0_0_20px_rgba(24,119,242,0.15)]">
                      <div className="flex gap-1.5 mb-3">
                        <span className="size-2.5 rounded-full bg-[#1877F2]" />
                        <span className="size-2.5 rounded-full bg-[#8E33FF]" />
                        <span className="size-2.5 rounded-full bg-[#22C55E]" />
                      </div>
                      <div className="text-[12px] font-semibold text-white">Material Kit Dark</div>
                      <div className="text-[10.5px] text-[#919EAB] mt-0.5">Active theme</div>
                      <Check className="absolute top-3 right-3 size-3.5 text-[#1877F2]" />
                    </div>

                    {/* Light — coming soon */}
                    <div className="rounded-xl border border-[rgba(145,158,171,0.16)] bg-[#141A21]/40 p-4 opacity-35 cursor-not-allowed">
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
                <div className="rounded-2xl border border-[rgba(145,158,171,0.16)] bg-[#1C252E] divide-y divide-[rgba(145,158,171,0.12)]">
                  {[
                    { key: 'Ctrl + Enter', action: 'Submit prompt and start build' },
                    { key: 'Escape',       action: 'Close modal or dropdown' },
                    { key: 'Ctrl + /',     action: 'Focus prompt input' },
                  ].map((s, i) => (
                    <div key={i} className="flex items-center justify-between px-4 py-3.5">
                      <span className="text-[12.5px] text-white/90">{s.action}</span>
                      <kbd className="rounded-lg border border-[rgba(145,158,171,0.2)] bg-[#141A21] px-2.5 py-1 font-mono text-[11px] text-white font-medium">
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
    tone = 'text-[#22C55E]'
  } else if (mongo.running) {
    text = mongo.external
      ? `adopted the MongoDB already on :${mongo.port}`
      : `MongoDB running on :${mongo.port}`
    tone = 'text-[#22C55E]'
  } else if (mongo.downloaded) {
    text = 'mongod downloaded, not running'
    tone = 'text-[#FFAB00]'
  } else {
    text = mongo.reason || 'mongod not downloaded yet'
    tone = mongo.reason ? 'text-[#FF5630]' : 'text-[#919EAB]'
  }
  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-[rgba(145,158,171,0.16)] bg-[#1C252E] px-3.5 py-2.5 font-mono text-[11px]">
      <Database className="size-3.5 shrink-0 text-[#1877F2]" />
      <span className={tone}>{text}</span>
    </div>
  )
}
