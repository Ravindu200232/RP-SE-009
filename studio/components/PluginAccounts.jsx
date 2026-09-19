'use client'

/** Central account management for third-party integrations and per-project plugin enablement. */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Check, ChevronDown, ExternalLink, Eye, EyeOff, Loader2, Plug, Trash2 } from 'lucide-react'

import { api } from '@/lib/api'
import { useStore } from '@/lib/store'
import { cn } from '@/lib/utils'

/** Shared hook to load available plugins and synchronize project-level activation state. */
export function usePlugins(project, pending, onPending) {
  const [state, setState] = useState({ plugins: [], groups: [], saved: [], loading: true })
  const [enabled, setEnabled] = useState([])

  const load = useCallback(async () => {
    try {
      const answer = await api.plugins()
      setState({ ...answer, loading: false })
    } catch {
      setState(s => ({ ...s, loading: false }))
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!project) return setEnabled([])
    let live = true
    api.projectPlugins(project)
       .then(answer => { if (live) setEnabled(answer.enabled || []) })
       .catch(() => { })
    return () => { live = false }
  }, [project])

  const savedById = useMemo(
    () => Object.fromEntries((state.saved || []).map(row => [row.id, row])), [state.saved])

  const chosen = onPending ? (pending || []) : enabled

  const tick = useCallback(async (id, on) => {
    const next = on ? [...new Set([...chosen, id])] : chosen.filter(x => x !== id)
    if (onPending) return onPending(next)
    if (!project) return
    setEnabled(next)
    try {
      const answer = await api.setProjectPlugins(project, next)
      setEnabled(answer.enabled || next)
    } catch (e) {
      setEnabled(enabled)
      useStore.getState().addLog('WARN', `Could not change that plugin — ${e.message}`)
    }
  }, [chosen, enabled, project, onPending])

  return { ...state, savedById, enabled: chosen, tick, reload: load,
           onSaved: saved => setState(s => ({ ...s, saved })) }
}

/** One provider: its icon, what it is for, and what it still needs. */
function Card({ plugin, saved, ticking, on, onTick, onSaved }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState(saved?.mode || plugin.modes[0].choice)
  const [values, setValues] = useState({})
  const [shown, setShown] = useState({})
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const chosen = plugin.modes.find(m => m.choice === mode) || plugin.modes[0]
  const configured = Boolean(saved?.configured)
  const already = new Set(saved?.set || [])

  async function save() {
    setBusy('save'); setError('')
    try {
      onSaved(await api.savePlugin(plugin.id, mode, values))
      setValues({})
      setOpen(false)
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }

  async function forget() {
    setBusy('forget'); setError('')
    try {
      onSaved(await api.forgetPlugin(plugin.id))
      setValues({})
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }

  return (
    <div className={cn('rounded-2xl border bg-panel2/50 transition-colors',
      on ? 'border-accent/45' : 'border-line')}>
      <div className="flex items-center gap-3 p-3">
        {ticking && (
          <button onClick={() => onTick(plugin.id, !on)} aria-pressed={on}
                  title={on ? `Stop using ${plugin.name} in this app`
                            : `Use ${plugin.name} in this app`}
                  className={cn('grid size-5 shrink-0 place-items-center rounded-md border transition-all',
                    on ? 'border-accent bg-accent text-white'
                       : 'border-line2 bg-panel hover:border-accent')}>
            {on && <Check className="size-3" />}
          </button>
        )}
        {/* The studio is served under a basePath and a plain <img> does not
            get it - only next/image and next/link do - so the prefix is
            written out, the way every other asset in here writes it. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`/__agentforge/plugins/${plugin.icon}`} alt="" width={28} height={28}
             className="size-7 shrink-0 rounded-lg" />
        <button onClick={() => setOpen(o => !o)} className="min-w-0 flex-1 text-left">
          <span className="flex items-baseline gap-2">
            <span className="text-[12.5px] font-semibold text-ink">{plugin.name}</span>
            {configured
              ? <span className="text-[10px] font-semibold text-ok">saved</span>
              : <span className="text-[10px] text-muted2">not set up</span>}
          </span>
          <span className="mt-0.5 block truncate text-[11px] text-muted">{plugin.what}</span>
        </button>
        <ChevronDown className={cn('size-3.5 shrink-0 text-muted2 transition-transform',
          open && 'rotate-180 text-ink')} />
      </div>

      {open && (
        <div className="border-t border-line/60 px-3 pb-3.5 pt-3">
          {plugin.modes.length > 1 && (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {plugin.modes.map(m => (
                <button key={m.choice} onClick={() => setMode(m.choice)} title={m.hint}
                        aria-pressed={mode === m.choice}
                        className={cn('rounded-xl border px-2.5 py-1.5 text-[11px] font-semibold transition-all',
                          mode === m.choice
                            ? 'border-accent bg-accent/15 text-accent'
                            : 'border-line2 bg-panel text-muted hover:text-ink')}>
                  {m.label}
                </button>
              ))}
            </div>
          )}
          {chosen.hint && (
            <p className="mb-3 text-[11px] leading-relaxed text-muted">{chosen.hint}</p>
          )}

          <div className="space-y-2.5">
            {chosen.fields.map(field => (
              <label key={field.key} className="block">
                <span className="flex items-baseline gap-2">
                  <span className="text-[11px] font-semibold text-ink">{field.label}</span>
                  <code className="font-mono text-[9.5px] text-accent">{field.key}</code>
                  {already.has(field.key) && (
                    <span className="font-mono text-[9.5px] text-ok">
                      {saved.hints?.[field.key]}
                    </span>
                  )}
                  {!field.required && <span className="text-[9.5px] text-muted2">optional</span>}
                </span>
                {field.hint && (
                  <span className="mt-0.5 block text-[10.5px] leading-relaxed text-muted">
                    {field.hint}
                  </span>
                )}
                <span className="mt-1.5 flex items-center gap-1.5">
                  <input type={field.secret && !shown[field.key] ? 'password' : 'text'}
                         value={values[field.key] ?? ''} spellCheck={false} autoComplete="off"
                         placeholder={already.has(field.key) ? 'leave blank to keep it'
                                                             : field.example}
                         onChange={e => setValues(v => ({ ...v, [field.key]: e.target.value }))}
                         className="h-8 min-w-0 flex-1 rounded-lg border border-line bg-panel px-2.5 font-mono text-[11px] text-ink outline-none placeholder:text-muted2 focus:border-accent" />
                  {field.secret && (
                    <button onClick={() => setShown(s => ({ ...s, [field.key]: !s[field.key] }))}
                            title={shown[field.key] ? 'Hide it' : 'Show what you typed'}
                            className="grid size-8 shrink-0 place-items-center rounded-lg border border-line bg-panel text-muted hover:text-ink">
                      {shown[field.key] ? <EyeOff className="size-3" /> : <Eye className="size-3" />}
                    </button>
                  )}
                </span>
                {!already.has(field.key) && field.example && (
                  <span className="mt-1 block font-mono text-[9.5px] text-muted2">
                    e.g. {field.example}
                  </span>
                )}
              </label>
            ))}
          </div>

          {error && <p className="mt-2.5 text-[11px] text-bad">{error}</p>}

          <div className="mt-3 flex items-center gap-2 border-t border-line/50 pt-3">
            {plugin.site && (
              <a href={plugin.site} target="_blank" rel="noreferrer noopener"
                 className="inline-flex items-center gap-1 text-[10.5px] font-medium text-muted hover:text-accent">
                <ExternalLink className="size-3" /> Where to find these
              </a>
            )}
            <span className="flex-1" />
            {configured && (
              <button onClick={forget} disabled={Boolean(busy)} title="Forget these settings"
                      className="inline-flex items-center gap-1 rounded-lg px-2 py-1.5 text-[10.5px] font-semibold text-muted hover:text-bad disabled:opacity-40">
                {busy === 'forget' ? <Loader2 className="size-3 animate-spin" />
                                   : <Trash2 className="size-3" />}
                Forget
              </button>
            )}
            <button onClick={save} disabled={Boolean(busy) || !Object.values(values).some(v => String(v || '').trim())}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-3.5 py-1.5 text-[11px] font-semibold text-white transition-colors hover:bg-press disabled:opacity-40">
              {busy === 'save' ? <Loader2 className="size-3 animate-spin" />
                               : <Check className="size-3" />}
              {configured ? 'Update' : 'Save'}
            </button>
          </div>
          <p className="mt-2 text-[10px] leading-relaxed text-muted2">
            Kept with your account, sealed, and written into each app you tick.
            They are never shown back to you and never reach the model, which
            reads them from the environment as it runs.
          </p>
        </div>
      )}
    </div>
  )
}

/** Renders categorized plugin provider cards with credential inputs and project activation toggles. */
export default function PluginAccounts({ project = '', pending, onPending, className = '' }) {
  const { plugins, groups, savedById, enabled, tick, loading, onSaved } =
    usePlugins(project, pending, onPending)
  const ticking = Boolean(project) || Boolean(onPending)

  if (loading) {
    return (
      <p className="flex items-center gap-2 py-6 text-[11.5px] text-muted">
        <Loader2 className="size-3.5 animate-spin text-accent" /> Reading your plugins…
      </p>
    )
  }
  if (!plugins.length) {
    return <p className="py-6 text-[11.5px] text-muted">No plugins are available.</p>
  }

  const order = groups.length ? groups : [...new Set(plugins.map(p => p.group))]
  return (
    <div className={cn('space-y-5', className)}>
      {project ? (
        <p className="text-[11.5px] leading-relaxed text-muted">
          Tick the ones <b className="font-semibold text-ink">{project}</b> should use. Their
          settings go into that app’s environment on its next run, and the agent is
          given each provider’s own page to build against.
        </p>
      ) : onPending ? null : (
        <p className="text-[11.5px] leading-relaxed text-muted">
          Set a provider up once here and every app you tick it for gets it.
          Open a project to choose which apps use which.
        </p>
      )}
      {order.map(group => {
        const rows = plugins.filter(p => p.group === group)
        if (!rows.length) return null
        return (
          <section key={group}>
            <p className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[.14em] text-muted2">
              <Plug className="size-3" /> {group}
            </p>
            <div className="space-y-2">
              {rows.map(plugin => (
                <Card key={plugin.id} plugin={plugin} saved={savedById[plugin.id]}
                      ticking={ticking} on={enabled.includes(plugin.id)}
                      onTick={tick} onSaved={onSaved} />
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}
