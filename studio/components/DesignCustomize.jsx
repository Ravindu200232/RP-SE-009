'use client'

import { useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import { Button, Input, Modal, TextArea } from './ui'

const ASSETS = '/__agentforge/design-themes'
const LIVE = '/__agentforge/api/design-theme-preview'
const RADII = [['Sharp', '0px'], ['Slight', '6px'], ['Rounded', '12px'], ['Pill', '9999px']]
const DENSITIES = ['Comfortable', 'Compact', 'Spacious']
const SWATCHES = ['primary', 'secondary', 'surface', 'text']
const BLANK = {
  slug: '', direction: '', density: 'Comfortable', radius: '12px',
  colors: {}, headingFont: '', bodyFont: '', custom: false,
}

function tokenLines(state, theme) {
  const colors = { ...(theme?.colors || {}), ...state.colors }
  const rows = SWATCHES.filter(key => colors[key]).map(key => `${key} ${colors[key]}`)
  if (state.button) rows.push(`button ${state.button}`)
  return rows
}

// The theme's own prompt is far longer than anything that belongs in a chat
// message, so the direction names the theme and the engine reads the file.
// Everything the user actually changed is spelled out, because an override is
// only an override if it is stated after the theme it overrides.
function composeDirection(state, theme) {
  const parts = []
  if (theme) parts.push(`Design theme: ${theme.name} (design-theme:${theme.slug}). ${theme.description}`)
  const tokens = tokenLines(state, theme)
  if (tokens.length) parts.push(`Colors: ${tokens.join(', ')}.`)
  const fonts = [state.headingFont && `headings ${state.headingFont}`,
                 state.bodyFont && `body ${state.bodyFont}`].filter(Boolean)
  if (fonts.length) parts.push(`Typography: ${fonts.join(', ')}.`)
  parts.push(`Button radius: ${state.radius}. Spacing: ${state.density}.`)
  if (state.direction.trim()) parts.push(state.direction.trim())
  return parts.join('\n')
}

function Swatch({ label, value, fallback, onChange }) {
  const shown = value || fallback || '#000000'
  return (
    <label className="flex items-center gap-2 text-xs capitalize text-muted">
      <input type="color" value={shown} onChange={e => onChange(e.target.value)} aria-label={label}
        className="h-7 w-7 cursor-pointer rounded border border-line bg-transparent p-0" />
      <span className="min-w-14">{label}</span>
      <code className="text-[11px] text-ink/70">{shown}</code>
    </label>
  )
}

function ThemeCard({ theme, selected, onOpen }) {
  return (
    <button type="button" onClick={onOpen}
      className={`group overflow-hidden rounded-xl border text-left transition
        ${selected ? 'border-[#1877F2] ring-2 ring-[#1877F2] shadow-md' : 'border-line hover:border-[#1877F2]/60'}`}>
      <span className="block aspect-[16/10] overflow-hidden bg-panel2">
        {theme.hasPreview
          ? <img src={`${ASSETS}/${theme.slug}.png`} alt="" loading="lazy"
              className="h-full w-full object-cover object-top transition group-hover:scale-[1.03]" />
          : <span className="flex h-full items-center justify-center text-xs text-muted">No preview</span>}
      </span>
      <span className="flex items-center justify-between gap-2 px-3 py-2">
        <span className="truncate text-sm font-medium text-ink">{theme.name}</span>
        <span className="flex shrink-0 gap-1">
          {SWATCHES.map(key => theme.colors?.[key] && (
            <span key={key} className="h-3 w-3 rounded-full border border-line"
              style={{ background: theme.colors[key] }} />
          ))}
        </span>
      </span>
    </button>
  )
}

export default function DesignCustomize({ projectId, onContinue, onBack }) {
  const [themes, setThemes] = useState([])
  const [query, setQuery] = useState('')
  const [preview, setPreview] = useState(null)
  const [live, setLive] = useState({ slug: '', drawing: false, error: '' })
  const [state, setState] = useState(BLANK)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(`${ASSETS}/themes.json`)
      .then(r => r.ok ? r.json() : {})
      .then(data => setThemes(Object.values(data)))
      .catch(() => setThemes([]))
  }, [])

  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(`agentforge-design-${projectId}`) || '{}')
      setState({ ...BLANK, ...saved, colors: saved.colors || {} })
    } catch { }
  }, [projectId])

  function save(patch) {
    setState(prev => {
      const next = { ...prev, ...patch }
      try { localStorage.setItem(`agentforge-design-${projectId}`, JSON.stringify(next)) } catch { }
      return next
    })
  }

  const theme = useMemo(() => themes.find(t => t.slug === state.slug) || null, [themes, state.slug])
  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return themes
    return themes.filter(t => `${t.name} ${t.description}`.toLowerCase().includes(needle))
  }, [themes, query])

  function choose(picked) {
    save({
      slug: picked.slug, colors: {}, custom: false,
      headingFont: picked.fonts?.[0] || '', bodyFont: picked.fonts?.[1] || picked.fonts?.[0] || '',
    })
    setPreview(null)
  }

  async function draw(slug) {
    if (live.drawing) return
    setLive({ slug: '', drawing: true, error: '' })
    try {
      await api.drawThemePreview(slug, '')
      setLive({ slug, drawing: false, error: '' })
    } catch (failure) {
      setLive({ slug: '', drawing: false, error: failure.message })
    }
  }

  async function apply() {
    if (saving) return
    setSaving(true); setError('')
    try { await onContinue(composeDirection(state, theme)) }
    catch (failure) { setError(failure.message) }
    finally { setSaving(false) }
  }

  return (
    <section className="mx-auto my-auto w-full max-w-5xl rounded-2xl border border-line bg-panel p-7 text-ink">
      <p className="text-xs font-semibold text-accent">SRS approved · Designer</p>
      <h1 className="mt-2 text-2xl font-semibold">Customize the design</h1>
      <p className="mt-2 text-sm text-muted">
        Pick a theme for the look and feel. The designer reads its full design system, then your changes on top.
      </p>

      <div className="mt-5 flex items-center gap-3">
        <Input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search themes…"
          className="w-full max-w-xs rounded-lg border border-line bg-panel2 p-2 text-sm" />
        <span className="text-xs text-muted">{shown.length} of {themes.length}</span>
        {state.slug && (
          <button type="button" onClick={() => save({ slug: '', colors: {}, headingFont: '', bodyFont: '' })}
            className="ml-auto text-xs text-muted underline hover:text-ink">Clear theme</button>
        )}
      </div>

      <div className="mt-4 grid max-h-[46vh] grid-cols-2 gap-3 overflow-y-auto pr-1 sm:grid-cols-3 lg:grid-cols-4">
        {shown.map(item => (
          <ThemeCard key={item.slug} theme={item} selected={item.slug === state.slug}
            onOpen={() => { setPreview(item); setLive({ slug: '', drawing: false, error: '' }) }} />
        ))}
        {!themes.length && <p className="col-span-full py-8 text-center text-sm text-muted">Loading themes…</p>}
      </div>

      <div className="mt-6 rounded-xl border border-line bg-panel2 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-medium">
            {theme ? <>Theme: <span className="text-accent">{theme.name}</span></>
                   : 'No theme selected — the designer follows the product requirements'}
          </p>
          <button type="button" onClick={() => save({ custom: !state.custom })}
            className="text-xs text-accent underline">
            {state.custom ? 'Hide customization' : "Doesn't fit? Customize it"}
          </button>
        </div>

        {state.custom && (
          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">Colors</p>
              <div className="grid gap-2">
                {SWATCHES.map(key => (
                  <Swatch key={key} label={key} value={state.colors[key]} fallback={theme?.colors?.[key]}
                    onChange={value => save({ colors: { ...state.colors, [key]: value } })} />
                ))}
                <Swatch label="button" value={state.button} fallback={theme?.colors?.primary}
                  onChange={value => save({ button: value })} />
              </div>
            </div>
            <div className="grid content-start gap-4">
              <label className="text-xs font-semibold uppercase tracking-wide text-muted">Heading font
                <Input value={state.headingFont} onChange={e => save({ headingFont: e.target.value })}
                  placeholder="e.g. Playfair Display"
                  className="mt-2 w-full rounded-lg border border-line bg-panel p-2 text-sm font-normal normal-case tracking-normal text-ink" />
              </label>
              <label className="text-xs font-semibold uppercase tracking-wide text-muted">Body font
                <Input value={state.bodyFont} onChange={e => save({ bodyFont: e.target.value })}
                  placeholder="e.g. Inter"
                  className="mt-2 w-full rounded-lg border border-line bg-panel p-2 text-sm font-normal normal-case tracking-normal text-ink" />
              </label>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Button corners</p>
                <div className="flex flex-wrap gap-2">
                  {RADII.map(([label, value]) => (
                    <button key={value} type="button" onClick={() => save({ radius: value })}
                      style={{ borderRadius: value }}
                      className={`border px-3 py-1.5 text-xs transition
                        ${state.radius === value ? 'border-accent bg-accent/15 text-ink' : 'border-line text-muted hover:text-ink'}`}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <label className="text-xs font-semibold uppercase tracking-wide text-muted">Spacing
                <select value={state.density} onChange={e => save({ density: e.target.value })}
                  className="mt-2 block w-full rounded-lg border border-line bg-panel p-2 text-sm font-normal normal-case tracking-normal text-ink">
                  {DENSITIES.map(value => <option key={value}>{value}</option>)}
                </select>
              </label>
            </div>
          </div>
        )}
      </div>

      <label className="mt-5 block text-sm">Anything else about the look and feel
        <TextArea value={state.direction} onChange={e => save({ direction: e.target.value })} rows={3}
          placeholder="Reference sites, imagery, tone, anything the theme does not cover…"
          className="mt-2 w-full rounded-lg border border-line bg-panel2 p-3" />
      </label>

      {error && <p role="alert" className="mt-3 text-sm text-bad">{error}</p>}

      <div className="mt-6 flex justify-between gap-3">
        <Button variant="outline" onClick={onBack}>Review SRS</Button>
        <Button disabled={saving} onClick={apply}>{saving ? 'Applying design…' : 'Apply to prototype'}</Button>
      </div>

      {preview && (
        <Modal onClose={() => setPreview(null)} className="max-w-3xl overflow-hidden p-0">
          <div className="flex items-start justify-between gap-4 border-b border-line p-4">
            <div>
              <h2 className="text-lg font-semibold">{preview.name}</h2>
              <p className="mt-1 max-w-xl text-sm text-muted">{preview.description}</p>
            </div>
            <Button onClick={() => choose(preview)}>
              {preview.slug === state.slug ? 'Selected' : 'Use this theme'}
            </Button>
          </div>
          {live.slug === preview.slug
            ? <iframe title={`${preview.name} live preview`} src={`${LIVE}/${preview.slug}`}
                className="h-[60vh] w-full border-0 bg-white" />
            : preview.hasPreview
              ? <div className="max-h-[60vh] overflow-y-auto bg-panel2">
                  <img src={`${ASSETS}/${preview.slug}.png`} alt={`${preview.name} preview`} className="w-full" />
                </div>
              : <p className="flex h-40 items-center justify-center bg-panel2 text-sm text-muted">
                  No screenshot for this theme — draw a live page to see it.
                </p>}
          <div className="flex flex-wrap gap-5 border-t border-line p-4 text-xs text-muted">
            <span className="flex items-center gap-2">
              {SWATCHES.map(key => preview.colors?.[key] && (
                <span key={key} title={`${key} ${preview.colors[key]}`}
                  className="h-4 w-4 rounded-full border border-line" style={{ background: preview.colors[key] }} />
              ))}
            </span>
            {preview.fonts?.length > 0 && <span>Fonts: {preview.fonts.join(', ')}</span>}
            <span className="ml-auto flex items-center gap-3">
              {live.error && <span role="alert" className="text-bad">{live.error}</span>}
              <button type="button" onClick={() => draw(preview.slug)} disabled={live.drawing}
                className="text-accent underline disabled:opacity-50">
                {live.drawing ? 'Drawing…'
                  : live.slug === preview.slug ? 'Redraw live page' : 'Live preview'}
              </button>
            </span>
          </div>
        </Modal>
      )}
    </section>
  )
}
