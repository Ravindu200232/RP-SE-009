'use client'

import { useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import { Button, Input, Modal, TextArea } from './ui'

const ASSETS = '/__agentforge/design-themes'
const LIVE = '/__agentforge/api/design-theme-preview'
const RADII = [['Sharp', '0px'], ['Slight', '6px'], ['Rounded', '12px'], ['Pill', '9999px']]
const DENSITIES = ['Comfortable', 'Compact', 'Spacious']
const SWATCHES = ['primary', 'secondary', 'surface', 'text']
// Status colours are their own group: a theme sets brand colour, and a product
// still has to say what "failed" looks like. Left unset they follow the theme.
const STATUS_SWATCHES = ['success', 'warning', 'danger']
const APPEARANCES = ['Light', 'Dark', 'Light and dark']
const BORDERS = ['None', 'Hairline', 'Bold']
const SHADOWS = ['Flat', 'Soft', 'Dramatic']
const ICONS = ['Outline', 'Solid', 'Duotone']
const WIDTHS = ['Narrow', 'Normal', 'Wide', 'Full width']
const NAVS = ['Top bar', 'Left sidebar', 'Top bar and sidebar']
const MOTIONS = ['None', 'Subtle', 'Expressive']
// Pairs that are known to sit well together, so the common case is one click
// rather than remembering two font names and spelling them correctly.
const PAIRINGS = [
  ['Theme default', '', ''],
  ['Inter / Inter', 'Inter', 'Inter'],
  ['Poppins / Roboto', 'Poppins', 'Roboto'],
  ['Playfair Display / Lato', 'Playfair Display', 'Lato'],
  ['Space Grotesk / IBM Plex Sans', 'Space Grotesk', 'IBM Plex Sans'],
  ['DM Serif Display / DM Sans', 'DM Serif Display', 'DM Sans'],
  ['Outfit / Outfit', 'Outfit', 'Outfit'],
]
const BLANK = {
  slug: '', direction: '', density: 'Comfortable', radius: '12px',
  colors: {}, headingFont: '', bodyFont: '', custom: false,
  appearance: '', border: '', shadow: '', icons: '', width: '', nav: '', motion: '',
}

function tokenLines(state, theme) {
  const colors = { ...(theme?.colors || {}), ...state.colors }
  const rows = SWATCHES.filter(key => colors[key]).map(key => `${key} ${colors[key]}`)
  if (state.button) rows.push(`button ${state.button}`)
  // Status colours come only from the user: an unset one is not an override,
  // and naming the theme's own value back at it is noise, not instruction.
  STATUS_SWATCHES.forEach(key => {
    if (state.colors[key]) rows.push(`${key} ${state.colors[key]}`)
  })
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
  // Only what the user actually set. An unset control is the theme's business,
  // and listing a default as a choice tells the agent a decision was made when
  // none was - which is how a direction ends up arguing with its own theme.
  const chosen = [
    state.appearance && `Appearance: ${state.appearance}.`,
    state.border && `Borders: ${state.border.toLowerCase()}.`,
    state.shadow && `Shadows: ${state.shadow.toLowerCase()}.`,
    state.icons && `Icons: ${state.icons.toLowerCase()}.`,
    state.width && `Content width: ${state.width.toLowerCase()}.`,
    state.nav && `Navigation: ${state.nav.toLowerCase()}.`,
    state.motion && `Motion: ${state.motion.toLowerCase()}.`,
  ].filter(Boolean)
  if (chosen.length) parts.push(chosen.join(' '))
  // Uploaded pictures are not named here. They are files on disk with captions
  // beside them, and `images.md` says what each one is for — repeating a
  // half-remembered list in the direction is how a caption and a prompt end up
  // disagreeing about the same photograph.
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

/**
 * One row of mutually exclusive choices, where choosing nothing is a real answer.
 *
 * Every control here is an override of the theme, so it starts unset and the
 * selected option can be clicked again to clear it. A control that cannot be
 * cleared forces a decision the user did not want to make, and the direction
 * then tells the agent to override something nobody asked to override.
 */
function Choice({ label, options, value, onPick }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
        {label} {!value && <span className="font-normal normal-case text-muted2">theme default</span>}
      </p>
      <div className="flex flex-wrap gap-2">
        {options.map(option => (
          <button key={option} type="button" onClick={() => onPick(value === option ? '' : option)}
            className={`rounded-ctl border px-3 py-1.5 text-xs transition
              ${value === option ? 'border-accent bg-accent/15 text-ink'
                                 : 'border-line text-muted hover:text-ink'}`}>
            {option}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * Every picture the finished product should carry — the logo among them.
 *
 * Nothing in this system draws artwork, so an uploaded file is the only real
 * photograph a page can ever show. Each one gets a line saying what it is for,
 * because a folder of files tells the designer nothing about where any of them
 * belongs, and a picture placed at a guess is worse than one left out.
 */
function SiteImages({ projectId }) {
  const [rows, setRows] = useState([])
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState('')
  // What is typed, before it is saved: re-rendering from the server on every
  // keystroke would fight the cursor.
  const [draft, setDraft] = useState({})

  useEffect(() => {
    if (!projectId) return
    let open = true
    api.siteImages(projectId)
      .then(answer => { if (open) setRows(answer?.images || []) })
      .catch(() => { })
    return () => { open = false }
  }, [projectId])

  async function add(files) {
    const picked = [...(files || [])]
    if (!picked.length || !projectId) return
    setBusy(true); setProblem('')
    try {
      let answer = null
      // One at a time: a rejected file should not take the rest of the
      // selection down with it, and the list is rewritten by every reply.
      for (const file of picked) {
        try { answer = await api.siteImageSave(projectId, file) }
        catch (failure) { setProblem(`${file.name}: ${failure?.message || 'could not be uploaded'}`) }
      }
      if (answer?.images) setRows(answer.images)
    } finally {
      setBusy(false)
    }
  }

  async function describe(file, purpose) {
    setDraft(prev => ({ ...prev, [file]: undefined }))
    try {
      const answer = await api.siteImageDescribe(projectId, file, purpose)
      if (answer?.images) setRows(answer.images)
    } catch (failure) {
      setProblem(failure?.message || 'That note could not be saved.')
    }
  }

  async function drop(file) {
    try {
      const answer = await api.siteImageDrop(projectId, file)
      setRows(answer?.images || [])
    } catch (failure) {
      setProblem(failure?.message || 'That image could not be removed.')
    }
  }

  const unexplained = rows.filter(row => !row.purpose).length

  return (
    <div className="md:col-span-2">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">
          Images {!rows.length && <span className="font-normal normal-case text-muted2">optional</span>}
        </p>
        <label className={`cursor-pointer rounded-ctl border border-line px-3 py-1 text-xs
                           text-muted transition hover:text-ink ${busy ? 'opacity-50' : ''}`}>
          {busy ? 'Uploading…' : rows.length ? 'Add more' : 'Upload images'}
          <input type="file" accept="image/*" multiple className="hidden" disabled={busy || !projectId}
            onChange={e => { add(e.target.files); e.target.value = '' }} />
        </label>
        <span className="text-[11px] text-muted2">
          {rows.length
            ? `${rows.length} image${rows.length === 1 ? '' : 's'}`
              + (unexplained ? ` · ${unexplained} with no note yet` : '')
            : 'logo, photographs, anything the pages should show'}
        </span>
      </div>

      {rows.length > 0 && (
        <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(150px,1fr))]">
          {rows.map(row => (
            <div key={row.file} className="overflow-hidden rounded-lg border border-line bg-panel">
              {/* A stored upload: its dimensions are the customer's, not ours. */}
              <img src={api.siteImageUrl(projectId, row.file)} alt={row.purpose || row.file}
                className="h-24 w-full border-b border-line bg-panel2 object-contain" />
              <div className="space-y-1.5 p-2">
                <div className="flex items-baseline justify-between gap-2">
                  <code className="truncate text-[10px] text-ink/70" title={row.file}>{row.file}</code>
                  <button type="button" onClick={() => drop(row.file)}
                    className="shrink-0 text-[10px] text-muted underline hover:text-ink">remove</button>
                </div>
                <Input
                  value={draft[row.file] ?? row.purpose}
                  onChange={e => setDraft(prev => ({ ...prev, [row.file]: e.target.value }))}
                  onBlur={e => e.target.value !== row.purpose && describe(row.file, e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && e.currentTarget.blur()}
                  placeholder="What is this for?"
                  aria-label={`What ${row.file} is for`}
                  className="w-full rounded border border-line bg-panel2 px-2 py-1 text-[11px]" />
              </div>
            </div>
          ))}
        </div>
      )}
      {problem && <p role="alert" className="mt-2 text-[11px] text-bad">{problem}</p>}
    </div>
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

  // A page drawn in any earlier session is already cached on disk, and the popup
  // used to ignore it: every theme opened on "No screenshot for this theme" and
  // asked for a draw that had already happened. Ask the cache when the popup
  // opens, so a theme that has a page shows it straight away.
  useEffect(() => {
    const slug = preview?.slug
    if (!slug || live.drawing || live.slug === slug) return
    let open = true
    fetch(`${LIVE}/${encodeURIComponent(slug)}`, { method: 'GET' })
      .then(answer => { if (open && answer.ok) setLive({ slug, drawing: false, error: '' }) })
      .catch(() => {})
    return () => { open = false }
  }, [preview, live.drawing, live.slug])
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

  /**
   * Draw one theme's preview page, then wait for it to land.
   *
   * The draw is a model call that takes half a minute, and holding one request
   * open for it does not survive the hop through the dev proxy - it answered
   * `HTTP 500 socket hang up` while the page was still being written, and the
   * finished page then sat in the cache with the popup reporting failure. The
   * request is a trigger; the cached page is the result, so ask for the page
   * until it exists and only treat the deadline as failure.
   */
  async function draw(slug) {
    if (live.drawing) return
    setLive({ slug: '', drawing: true, error: '' })
    let refused = ''
    api.drawThemePreview(slug, '').catch(failure => { refused = failure?.message || '' })
    const deadline = Date.now() + 240000
    while (Date.now() < deadline) {
      await new Promise(resume => setTimeout(resume, 2000))
      let there = false
      try {
        there = (await fetch(`${LIVE}/${encodeURIComponent(slug)}`, { method: 'GET' })).ok
      } catch { /* the proxy dropping a poll is not an answer either */ }
      if (there) {
        setLive({ slug, drawing: false, error: '' })
        return
      }
    }
    setLive({ slug: '', drawing: false, error: refused || 'The preview took too long to draw.' })
  }

  async function apply() {
    if (saving) return
    setSaving(true); setError('')
    try { await onContinue(composeDirection(state, theme)) }
    catch (failure) { setError(failure.message) }
    finally { setSaving(false) }
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-y-auto w-full px-3.5 sm:px-6 py-6 sm:py-10">
      <section className="mx-auto w-full max-w-5xl rounded-2xl border border-line bg-panel p-7 text-ink shadow-2xl ring-1 ring-white/10 shrink-0">
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
                {STATUS_SWATCHES.map(key => (
                  <Swatch key={key} label={key} value={state.colors[key]} fallback={theme?.colors?.[key]}
                    onChange={value => save({ colors: { ...state.colors, [key]: value } })} />
                ))}
              </div>
              <Choice label="Appearance" options={APPEARANCES} value={state.appearance}
                onPick={value => save({ appearance: value })} />
              <Choice label="Borders" options={BORDERS} value={state.border}
                onPick={value => save({ border: value })} />
              <Choice label="Shadows" options={SHADOWS} value={state.shadow}
                onPick={value => save({ shadow: value })} />
              <Choice label="Icons" options={ICONS} value={state.icons}
                onPick={value => save({ icons: value })} />
            </div>
            <div className="grid content-start gap-4">
              <label className="text-xs font-semibold uppercase tracking-wide text-muted">Font pairing
                <select
                  value={PAIRINGS.some(([, h, b]) => h === state.headingFont && b === state.bodyFont)
                    ? `${state.headingFont}|${state.bodyFont}` : 'custom'}
                  onChange={e => {
                    if (e.target.value === 'custom') return
                    const [heading, body] = e.target.value.split('|')
                    save({ headingFont: heading, bodyFont: body })
                  }}
                  className="mt-2 block w-full rounded-lg border border-line bg-panel p-2 text-sm font-normal normal-case tracking-normal text-ink">
                  {PAIRINGS.map(([label, heading, body]) => (
                    <option key={label} value={`${heading}|${body}`}>{label}</option>
                  ))}
                  <option value="custom">Custom (typed below)</option>
                </select>
              </label>
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
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                  Corner radius <span className="font-normal normal-case text-muted2">{state.radius}</span>
                </p>
                <input type="range" min="0" max="32" step="1" aria-label="Corner radius"
                  value={parseInt(state.radius, 10) || 0}
                  onChange={e => save({ radius: `${e.target.value}px` })}
                  className="w-full accent-[#1877F2]" />
              </div>
              <Choice label="Content width" options={WIDTHS} value={state.width}
                onPick={value => save({ width: value })} />
              <Choice label="Navigation" options={NAVS} value={state.nav}
                onPick={value => save({ nav: value })} />
              <Choice label="Motion" options={MOTIONS} value={state.motion}
                onPick={value => save({ motion: value })} />
            </div>
          </div>
        )}
      </div>

      {/* Its own panel, not folded into "Customize it": a photograph is not an
          override of the theme, and a customer who uploads one has to be able
          to find it again without opening a panel about borders and shadows. */}
      <div className="mt-5 rounded-xl border border-line bg-panel2 p-5">
        <SiteImages projectId={projectId} />
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
    </div>
  )
}
