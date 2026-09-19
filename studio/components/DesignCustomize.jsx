'use client'

import { useEffect, useMemo, useState } from 'react'
import { api } from '@/lib/api'
import { Button, Input, Modal, TextArea } from './ui'
import { Check, Eye, Moon, Search, Sparkles, Sun } from 'lucide-react'

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

const DEFAULT_PALETTE = {
  primary: '#2563eb',
  secondary: '#64748b',
  surface: '#ffffff',
  text: '#0f172a',
  button: '#2563eb',
  success: '#16a34a',
  warning: '#d97706',
  danger: '#dc2626',
}

const COLOR_PRESETS = [
  {
    name: 'Modern SaaS',
    tag: 'Popular',
    colors: {
      primary: '#2563eb',
      secondary: '#64748b',
      surface: '#ffffff',
      text: '#0f172a',
      button: '#2563eb',
      success: '#16a34a',
      warning: '#d97706',
      danger: '#dc2626',
    },
  },
  {
    name: 'Fintech Emerald',
    tag: 'Finance',
    colors: {
      primary: '#059669',
      secondary: '#10b981',
      surface: '#f8fafc',
      text: '#064e3b',
      button: '#059669',
      success: '#16a34a',
      warning: '#f59e0b',
      danger: '#e11d48',
    },
  },
  {
    name: 'Creative Violet',
    tag: 'AI / Tech',
    colors: {
      primary: '#7c3aed',
      secondary: '#a855f7',
      surface: '#faf5ff',
      text: '#1e1b4b',
      button: '#7c3aed',
      success: '#10b981',
      warning: '#f59e0b',
      danger: '#ef4444',
    },
  },
  {
    name: 'Warm Sunset',
    tag: 'Editorial',
    colors: {
      primary: '#d97706',
      secondary: '#f59e0b',
      surface: '#fffbeb',
      text: '#292524',
      button: '#d97706',
      success: '#16a34a',
      warning: '#f59e0b',
      danger: '#dc2626',
    },
  },
  {
    name: 'Crimson Bold',
    tag: 'Energy',
    colors: {
      primary: '#e11d48',
      secondary: '#f43f5e',
      surface: '#fff1f2',
      text: '#18181b',
      button: '#e11d48',
      success: '#16a34a',
      warning: '#eab308',
      danger: '#be123c',
    },
  },
  {
    name: 'Monochrome',
    tag: 'Minimal',
    colors: {
      primary: '#18181b',
      secondary: '#71717a',
      surface: '#ffffff',
      text: '#09090b',
      button: '#18181b',
      success: '#15803d',
      warning: '#b45309',
      danger: '#b91c1c',
    },
  },
  {
    name: 'Cyber Dark',
    tag: 'Dark Mode',
    colors: {
      primary: '#38bdf8',
      secondary: '#818cf8',
      surface: '#0f172a',
      text: '#f8fafc',
      button: '#38bdf8',
      success: '#34d399',
      warning: '#fbbf24',
      danger: '#f87171',
    },
  },
]

const FIDELITY_OPTIONS = [
  {
    value: 'AI Polished',
    title: 'AI Polished (Recommended)',
    desc: 'Uses wireframes as blueprints; enhances with modern UI layouts, card grids, badges & responsive polish',
  },
  {
    value: 'Strict Wireframe',
    title: 'Strict Wireframe (1:1)',
    desc: 'Follows wireframe component placement and spatial hierarchy strictly without rearranging',
  },
]

const POPULAR_FONTS = [
  'Inter', 'Roboto', 'Poppins', 'Open Sans', 'Montserrat', 'Lato',
  'Plus Jakarta Sans', 'Outfit', 'Space Grotesk', 'Playfair Display',
  'Merriweather', 'Lora', 'DM Sans', 'DM Serif Display', 'IBM Plex Sans',
  'Nunito', 'Work Sans', 'Syne', 'Cinzel', 'JetBrains Mono', 'Fira Code',
]

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
  wireframeFidelity: 'AI Polished',
}

function loadGoogleFont(fontName) {
  if (!fontName || typeof document === 'undefined') return
  const clean = fontName.trim()
  if (!clean || clean.toLowerCase() === 'system-ui' || clean.toLowerCase() === 'sans-serif') return
  const id = `gfont-${clean.replace(/\s+/g, '-').toLowerCase()}`
  if (document.getElementById(id)) return
  const link = document.createElement('link')
  link.id = id
  link.rel = 'stylesheet'
  link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(clean)}:wght@400;500;600;700&display=swap`
  document.head.appendChild(link)
}

function getLuminance(hex) {
  if (!hex || typeof hex !== 'string') return 0.5
  let c = hex.replace('#', '').trim()
  if (c.length === 3) c = c.split('').map(x => x + x).join('')
  if (c.length !== 6) return 0.5
  const r = parseInt(c.slice(0, 2), 16) / 255
  const g = parseInt(c.slice(2, 4), 16) / 255
  const b = parseInt(c.slice(4, 6), 16) / 255
  const [R, G, B] = [r, g, b].map(v => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)))
  return 0.2126 * R + 0.7152 * G + 0.0722 * B
}

function getContrast(hex1, hex2) {
  const l1 = getLuminance(hex1)
  const l2 = getLuminance(hex2)
  const lighter = Math.max(l1, l2)
  const darker = Math.min(l1, l2)
  return ((lighter + 0.05) / (darker + 0.05)).toFixed(1)
}

function getContrastScore(ratio) {
  const num = parseFloat(ratio)
  if (num >= 7.0) return { label: 'AAA Pass', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' }
  if (num >= 4.5) return { label: 'AA Pass', color: 'text-blue-400 bg-blue-500/10 border-blue-500/30' }
  if (num >= 3.0) return { label: 'AA Large', color: 'text-amber-400 bg-amber-500/10 border-amber-500/30' }
  return { label: 'Low Contrast', color: 'text-rose-400 bg-rose-500/10 border-rose-500/30' }
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

// Formulate design directions by referencing the base theme and explicitly appending user customizations.
function composeDirection(state, theme) {
  const parts = []
  if (theme) parts.push(`Design theme: ${theme.name} (design-theme:${theme.slug}). ${theme.description}`)
  const tokens = tokenLines(state, theme)
  if (tokens.length) parts.push(`Colors: ${tokens.join(', ')}.`)
  const fonts = [state.headingFont && `headings ${state.headingFont}`,
                 state.bodyFont && `body ${state.bodyFont}`].filter(Boolean)
  if (fonts.length) parts.push(`Typography: ${fonts.join(', ')}.`)
  parts.push(`Button radius: ${state.radius}. Spacing: ${state.density}.`)

  // Wireframe Fidelity directive
  if (state.wireframeFidelity === 'Strict Wireframe') {
    parts.push('Wireframe layout fidelity: Strict 1:1. Follow the wireframe layout, component positions, and spatial hierarchy strictly without rearranging.')
  } else {
    parts.push('Wireframe layout fidelity: AI Polished. Use wireframes as functional architecture, upgrading with modern UI polish, component hierarchy, and responsive aesthetics.')
  }

  // Include only explicitly customized controls to avoid conflicting with base theme defaults.
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
  if (state.direction.trim()) parts.push(state.direction.trim())
  return parts.join('\n')
}

function Swatch({ label, value, fallback, onChange }) {
  const shown = value || fallback || DEFAULT_PALETTE[label] || '#2563eb'
  return (
    <label className="flex items-center gap-2 text-xs capitalize text-muted">
      <input
        type="color"
        value={shown}
        onChange={e => onChange(e.target.value)}
        aria-label={label}
        className="h-7 w-7 cursor-pointer rounded border border-line bg-transparent p-0"
      />
      <span className="min-w-14 font-medium">{label}</span>
      <code className="text-[11px] text-ink/70 font-mono">{shown}</code>
    </label>
  )
}

function Choice({ label, options, value, onPick }) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
        {label} {!value && <span className="font-normal normal-case text-muted2">theme default</span>}
      </p>
      <div className="flex flex-wrap gap-2">
        {options.map(option => (
          <button
            key={option}
            type="button"
            onClick={() => onPick(value === option ? '' : option)}
            className={`rounded-ctl border px-3 py-1.5 text-xs transition cursor-pointer
              ${value === option ? 'border-accent bg-accent/15 text-ink font-medium shadow-sm'
                                 : 'border-line text-muted hover:text-ink hover:bg-panel2'}`}
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  )
}

/** Searchable Google Fonts Combobox with real-time CDN query */
function FontPicker({ label, value, placeholder, catalog, onChange }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return catalog.slice(0, 50)
    return catalog.filter(f => f.toLowerCase().includes(q)).slice(0, 50)
  }, [catalog, query])

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-semibold uppercase tracking-wide text-muted">
          {label}
        </label>
        {value && (
          <span className="font-normal normal-case text-accent text-[11px] truncate max-w-[140px]">
            {value}
          </span>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        <Input
          value={value}
          onChange={e => {
            onChange(e.target.value)
            setQuery(e.target.value)
            loadGoogleFont(e.target.value)
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="w-full rounded-lg border border-line bg-panel p-2 text-sm font-normal text-ink"
        />
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="shrink-0 rounded-lg border border-line bg-panel px-2.5 py-2 text-xs text-muted hover:text-ink hover:border-accent transition cursor-pointer"
          title="Browse 1,900+ Google Fonts"
        >
          <Search className="size-3.5" />
        </button>
      </div>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full z-40 mt-1 max-h-60 w-full overflow-y-auto rounded-xl border border-line bg-panel p-2 shadow-2xl backdrop-blur-xl ring-1 ring-black/20">
            <div className="mb-2 px-1">
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="Search Google fonts…"
                className="w-full rounded-md border border-line bg-panel2 px-2.5 py-1.5 text-xs text-ink outline-none"
                autoFocus
              />
            </div>
            <div className="space-y-0.5">
              {filtered.map(font => (
                <button
                  key={font}
                  type="button"
                  onClick={() => {
                    onChange(font)
                    loadGoogleFont(font)
                    setOpen(false)
                  }}
                  className={`w-full rounded-md px-2.5 py-1.5 text-left text-xs transition flex items-center justify-between cursor-pointer ${
                    value === font ? 'bg-accent/15 text-accent font-semibold' : 'text-ink hover:bg-panel2'
                  }`}
                >
                  <span style={{ fontFamily: font }}>{font}</span>
                  {value === font && <Check className="size-3 text-accent shrink-0" />}
                </button>
              ))}
              {!filtered.length && (
                <p className="py-3 text-center text-xs text-muted">No fonts match "{query}"</p>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

/** Real-time Live Interactive Component Sandbox Widget */
function LiveComponentPreview({ state, theme }) {
  const [darkPreview, setDarkPreview] = useState(state.appearance === 'Dark')

  useEffect(() => {
    if (state.appearance === 'Dark') setDarkPreview(true)
    if (state.appearance === 'Light') setDarkPreview(false)
  }, [state.appearance])

  const colors = useMemo(() => {
    const primary = state.colors.primary || theme?.colors?.primary || DEFAULT_PALETTE.primary
    const secondary = state.colors.secondary || theme?.colors?.secondary || DEFAULT_PALETTE.secondary
    const surface = darkPreview
      ? (state.appearance === 'Dark' && state.colors.surface ? state.colors.surface : '#0f172a')
      : (state.colors.surface || theme?.colors?.surface || DEFAULT_PALETTE.surface)
    const text = darkPreview
      ? (state.appearance === 'Dark' && state.colors.text ? state.colors.text : '#f8fafc')
      : (state.colors.text || theme?.colors?.text || DEFAULT_PALETTE.text)
    const button = state.button || state.colors.button || primary
    const success = state.colors.success || DEFAULT_PALETTE.success
    const warning = state.colors.warning || DEFAULT_PALETTE.warning
    const danger = state.colors.danger || DEFAULT_PALETTE.danger

    return { primary, secondary, surface, text, button, success, warning, danger }
  }, [state.colors, state.button, state.appearance, theme, darkPreview])

  const headingFont = state.headingFont || theme?.fonts?.[0] || 'inherit'
  const bodyFont = state.bodyFont || theme?.fonts?.[1] || theme?.fonts?.[0] || 'inherit'
  const radius = state.radius || '12px'

  const shadowCss = useMemo(() => {
    if (state.shadow === 'Flat') return 'none'
    if (state.shadow === 'Dramatic') return '0 20px 25px -5px rgba(0,0,0,0.3), 0 8px 10px -6px rgba(0,0,0,0.25)'
    return '0 4px 16px -2px rgba(0,0,0,0.1), 0 2px 6px -1px rgba(0,0,0,0.06)'
  }, [state.shadow])

  const borderCss = useMemo(() => {
    if (state.border === 'None') return 'none'
    if (state.border === 'Bold') return `2px solid ${darkPreview ? 'rgba(255,255,255,0.25)' : 'rgba(0,0,0,0.25)'}`
    return `1px solid ${darkPreview ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.1)'}`
  }, [state.border, darkPreview])

  const densityPadding = useMemo(() => {
    if (state.density === 'Compact') return 'py-1 px-3 text-xs'
    if (state.density === 'Spacious') return 'py-2.5 px-5 text-sm'
    return 'py-2 px-4 text-xs'
  }, [state.density])

  const btnContrast = getContrast(colors.button, '#ffffff')
  const btnScore = getContrastScore(btnContrast)
  const textContrast = getContrast(colors.text, colors.surface)
  const textScore = getContrastScore(textContrast)

  return (
    <div className="rounded-2xl border border-line bg-panel overflow-hidden shadow-2xl transition-all">
      {/* Browser Chrome Bar */}
      <div className="flex items-center justify-between border-b border-line bg-panel2/80 px-3.5 py-2.5">
        <div className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full bg-[#ff5f56]" />
          <span className="size-2.5 rounded-full bg-[#ffbd2e]" />
          <span className="size-2.5 rounded-full bg-[#27c93f]" />
          <span className="ml-2 font-mono text-[11px] font-medium text-muted flex items-center gap-1">
            <Eye className="size-3 text-accent" /> Live Component Preview
          </span>
        </div>
        <button
          type="button"
          onClick={() => setDarkPreview(d => !d)}
          className="flex items-center gap-1 rounded-md border border-line bg-panel px-2 py-0.5 text-[10.5px] text-muted hover:text-ink transition cursor-pointer"
          title="Toggle Light / Dark Preview"
        >
          {darkPreview ? <Sun className="size-3 text-amber-400" /> : <Moon className="size-3 text-blue-400" />}
          <span>{darkPreview ? 'Dark' : 'Light'}</span>
        </button>
      </div>

      {/* Mockup Canvas */}
      <div
        style={{ backgroundColor: colors.surface, color: colors.text }}
        className="p-4 sm:p-5 transition-colors duration-200"
      >
        {/* Navigation Mockup Header */}
        <div
          style={{ borderBottom: borderCss }}
          className="mb-4 flex items-center justify-between pb-2 text-xs"
        >
          <div className="flex items-center gap-2 font-bold" style={{ fontFamily: headingFont }}>
            <span className="size-3.5 rounded-md shrink-0 shadow-sm" style={{ background: colors.primary }} />
            <span className="truncate">AgentForge Portal</span>
          </div>
          <div className="flex items-center gap-2.5 font-medium opacity-75" style={{ fontFamily: bodyFont }}>
            <span className="underline decoration-2 font-semibold" style={{ textDecorationColor: colors.primary }}>
              Overview
            </span>
            <span className="opacity-60">Analytics</span>
            <span className="opacity-60">Settings</span>
          </div>
        </div>

        {/* Hero Section */}
        <div className="space-y-1 mb-4">
          <h3
            className="text-lg font-bold leading-tight"
            style={{ fontFamily: headingFont, color: colors.text }}
          >
            Real-time Design Preview
          </h3>
          <p
            className="text-xs leading-relaxed opacity-75"
            style={{ fontFamily: bodyFont, color: colors.text }}
          >
            Review typography, button styles, and contrast before generating the final prototype.
          </p>
        </div>

        {/* Sample Component Card */}
        <div
          style={{
            borderRadius: radius,
            boxShadow: shadowCss,
            border: borderCss,
            backgroundColor: darkPreview ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)',
          }}
          className="p-3.5 space-y-3 mb-4"
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-xs" style={{ fontFamily: headingFont }}>
              Active Module
            </span>
            <span
              className="px-2 py-0.5 text-[10px] font-semibold text-white shadow-sm"
              style={{ backgroundColor: colors.success, borderRadius: radius }}
            >
              Operational
            </span>
          </div>

          <div className="space-y-1.5">
            <label className="text-[11px] font-medium opacity-80 block" style={{ fontFamily: bodyFont }}>
              Sample Input Field
            </label>
            <input
              type="text"
              readOnly
              value="user@organization.io"
              style={{
                borderRadius: radius,
                border: borderCss,
                fontFamily: bodyFont,
                color: colors.text,
                backgroundColor: darkPreview ? 'rgba(0,0,0,0.3)' : '#ffffff',
              }}
              className="w-full px-2.5 py-1.5 text-xs outline-none shadow-sm"
            />
          </div>

          {/* Interactive Buttons Row */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <button
              type="button"
              style={{
                backgroundColor: colors.button,
                borderRadius: radius,
                boxShadow: shadowCss,
                fontFamily: bodyFont,
              }}
              className={`font-semibold text-white transition hover:opacity-90 shadow-sm ${densityPadding}`}
            >
              Primary Action
            </button>
            <button
              type="button"
              style={{
                border: `1.5px solid ${colors.primary}`,
                color: colors.primary,
                borderRadius: radius,
                fontFamily: bodyFont,
              }}
              className={`font-semibold bg-transparent transition hover:bg-black/5 ${densityPadding}`}
            >
              Outline Action
            </button>
          </div>
        </div>

        {/* Status Badges Row */}
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
          <span
            style={{
              borderRadius: radius,
              backgroundColor: `${colors.success}22`,
              color: colors.success,
              border: `1px solid ${colors.success}44`,
            }}
            className="px-2 py-0.5 text-[10.5px] font-medium"
          >
            ✓ Success State
          </span>
          <span
            style={{
              borderRadius: radius,
              backgroundColor: `${colors.warning}22`,
              color: colors.warning,
              border: `1px solid ${colors.warning}44`,
            }}
            className="px-2 py-0.5 text-[10.5px] font-medium"
          >
            ⚠ Pending Review
          </span>
          <span
            style={{
              borderRadius: radius,
              backgroundColor: `${colors.danger}22`,
              color: colors.danger,
              border: `1px solid ${colors.danger}44`,
            }}
            className="px-2 py-0.5 text-[10.5px] font-medium"
          >
            ✕ Critical Alert
          </span>
        </div>
      </div>

      {/* WCAG Accessibility Rating Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line bg-panel2/70 px-3.5 py-2 text-[10.5px]">
        <div className="flex items-center gap-2 font-mono">
          <span className="text-muted2">Button Contrast:</span>
          <span className={`px-1.5 py-0.5 rounded border font-semibold ${btnScore.color}`}>
            {btnContrast}:1 ({btnScore.label})
          </span>
        </div>
        <div className="flex items-center gap-2 font-mono">
          <span className="text-muted2">Text Contrast:</span>
          <span className={`px-1.5 py-0.5 rounded border font-semibold ${textScore.color}`}>
            {textContrast}:1 ({textScore.label})
          </span>
        </div>
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
  const [fontCatalog, setFontCatalog] = useState(POPULAR_FONTS)

  // Check disk cache for existing theme preview images when opening the selection popup.
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

  // Load themes
  useEffect(() => {
    fetch(`${ASSETS}/themes.json`)
      .then(r => r.ok ? r.json() : {})
      .then(data => setThemes(Object.values(data)))
      .catch(() => setThemes([]))
  }, [])

  // Fetch free Google Fonts catalog
  useEffect(() => {
    let active = true
    fetch('https://cdn.jsdelivr.net/gh/hasinhayder/google-fonts/fonts.json')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (active && Array.isArray(data?.fonts)) {
          setFontCatalog(data.fonts)
        }
      })
      .catch(() => {})
    return () => { active = false }
  }, [])

  // Load saved state from localStorage
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(`agentforge-design-${projectId}`) || '{}')
      setState({ ...BLANK, ...saved, colors: saved.colors || {} })
      if (saved.headingFont) loadGoogleFont(saved.headingFont)
      if (saved.bodyFont) loadGoogleFont(saved.bodyFont)
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
    const h = picked.fonts?.[0] || ''
    const b = picked.fonts?.[1] || picked.fonts?.[0] || ''
    if (h) loadGoogleFont(h)
    if (b) loadGoogleFont(b)
    save({
      slug: picked.slug, colors: {}, custom: false,
      headingFont: h, bodyFont: b,
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
    setSaving(true)
    setError('')
    try {
      await onContinue(composeDirection(state, theme))
    } catch (failure) {
      setError(failure.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col overflow-y-auto w-full px-3.5 sm:px-6 py-6 sm:py-10">
      <section className="mx-auto w-full max-w-6xl rounded-2xl border border-line bg-panel p-6 sm:p-8 text-ink shadow-2xl ring-1 ring-white/10 shrink-0">
        <p className="text-xs font-semibold text-accent">SRS approved · Designer</p>
        <h1 className="mt-2 text-2xl font-semibold">Customize the design</h1>
        <p className="mt-2 text-sm text-muted">
          Pick a theme for the look and feel. The designer reads its full design system, then your changes on top.
        </p>

        {/* Theme Search */}
        <div className="mt-5 flex items-center gap-3">
          <Input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search themes…"
            className="w-full max-w-xs rounded-lg border border-line bg-panel2 p-2 text-sm"
          />
          <span className="text-xs text-muted">{shown.length} of {themes.length}</span>
          {state.slug && (
            <button
              type="button"
              onClick={() => save({ slug: '', colors: {}, headingFont: '', bodyFont: '' })}
              className="ml-auto text-xs text-muted underline hover:text-ink cursor-pointer"
            >
              Clear theme
            </button>
          )}
        </div>

        {/* Themes Grid */}
        <div className="mt-4 grid max-h-[42vh] grid-cols-2 gap-3 overflow-y-auto pr-1 sm:grid-cols-3 lg:grid-cols-4">
          {shown.map(item => (
            <ThemeCard
              key={item.slug}
              theme={item}
              selected={item.slug === state.slug}
              onOpen={() => { setPreview(item); setLive({ slug: '', drawing: false, error: '' }) }}
            />
          ))}
          {!themes.length && <p className="col-span-full py-8 text-center text-sm text-muted">Loading themes…</p>}
        </div>

        {/* Customization Section */}
        <div className="mt-6 rounded-xl border border-line bg-panel2 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-medium">
              {theme ? <>Theme: <span className="text-accent">{theme.name}</span></>
                     : 'No theme selected — the designer follows the product requirements'}
            </p>
            <button
              type="button"
              onClick={() => save({ custom: !state.custom })}
              className="text-xs text-accent underline cursor-pointer"
            >
              {state.custom ? 'Hide customization' : "Doesn't fit? Customize it"}
            </button>
          </div>

          {state.custom && (
            <div className="mt-5 space-y-6">
              {/* Wireframe Layout Fidelity Control */}
              <div className="rounded-xl border border-line/70 bg-panel/60 p-4 space-y-2.5">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                    Wireframe Layout Fidelity
                  </p>
                  <span className="text-[10px] text-muted2">Prototype generation strategy</span>
                </div>
                <div className="grid sm:grid-cols-2 gap-3">
                  {FIDELITY_OPTIONS.map(opt => {
                    const active = (state.wireframeFidelity || 'AI Polished') === opt.value
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => save({ wireframeFidelity: opt.value })}
                        className={`flex flex-col text-left rounded-xl border p-3 transition cursor-pointer ${
                          active
                            ? 'border-accent bg-accent/10 ring-1 ring-accent shadow-sm'
                            : 'border-line bg-panel hover:border-line/80'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-ink">{opt.title}</span>
                          {active && <Check className="size-3.5 text-accent" />}
                        </div>
                        <p className="mt-1 text-[11px] text-muted leading-relaxed">{opt.desc}</p>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* 1-Click Curated Color Mood Presets */}
              <div className="rounded-xl border border-line/70 bg-panel/60 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted flex items-center gap-1.5">
                    <Sparkles className="size-3.5 text-accent" />
                    1-Click Color Mood Presets
                  </p>
                  <span className="text-[10.5px] text-muted2">Harmonious color palettes</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {COLOR_PRESETS.map(preset => (
                    <button
                      key={preset.name}
                      type="button"
                      onClick={() => save({ colors: { ...preset.colors }, button: preset.colors.button })}
                      className="group flex flex-col gap-1.5 rounded-xl border border-line bg-panel p-2.5 text-left transition hover:border-accent hover:bg-panel2 cursor-pointer shadow-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-ink group-hover:text-accent truncate">
                          {preset.name}
                        </span>
                        <span className="rounded bg-panel2 px-1.5 py-0.5 font-mono text-[9px] text-muted2">
                          {preset.tag}
                        </span>
                      </div>
                      <div className="flex h-3 w-full overflow-hidden rounded-md border border-line/60">
                        <span className="flex-1" style={{ background: preset.colors.primary }} />
                        <span className="flex-1" style={{ background: preset.colors.secondary }} />
                        <span className="flex-1" style={{ background: preset.colors.surface }} />
                        <span className="flex-1" style={{ background: preset.colors.button }} />
                        <span className="flex-1" style={{ background: preset.colors.success }} />
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Two-Column Layout: Controls on Left, Sticky Live Preview on Right */}
              <div className="grid gap-6 lg:grid-cols-12">
                {/* Left Columns: Visual Controls */}
                <div className="space-y-6 lg:col-span-7">
                  {/* Colors & Appearance */}
                  <div className="rounded-xl border border-line bg-panel p-4 space-y-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted">Colors</p>
                    <div className="grid grid-cols-2 gap-3">
                      {SWATCHES.map(key => (
                        <Swatch
                          key={key}
                          label={key}
                          value={state.colors[key]}
                          fallback={theme?.colors?.[key]}
                          onChange={value => save({ colors: { ...state.colors, [key]: value } })}
                        />
                      ))}
                      <Swatch
                        label="button"
                        value={state.button}
                        fallback={theme?.colors?.primary}
                        onChange={value => save({ button: value })}
                      />
                      {STATUS_SWATCHES.map(key => (
                        <Swatch
                          key={key}
                          label={key}
                          value={state.colors[key]}
                          fallback={theme?.colors?.[key]}
                          onChange={value => save({ colors: { ...state.colors, [key]: value } })}
                        />
                      ))}
                    </div>

                    <div className="pt-2 border-t border-line/60 space-y-3">
                      <Choice label="Appearance" options={APPEARANCES} value={state.appearance}
                        onPick={value => save({ appearance: value })} />
                      <Choice label="Borders" options={BORDERS} value={state.border}
                        onPick={value => save({ border: value })} />
                      <Choice label="Shadows" options={SHADOWS} value={state.shadow}
                        onPick={value => save({ shadow: value })} />
                      <Choice label="Icons" options={ICONS} value={state.icons}
                        onPick={value => save({ icons: value })} />
                    </div>
                  </div>

                  {/* Typography & Layout */}
                  <div className="rounded-xl border border-line bg-panel p-4 space-y-4">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted">Typography</p>
                    
                    <label className="text-xs font-semibold uppercase tracking-wide text-muted block">
                      Quick Font Pairing
                      <select
                        value={PAIRINGS.some(([, h, b]) => h === state.headingFont && b === state.bodyFont)
                          ? `${state.headingFont}|${state.bodyFont}` : 'custom'}
                        onChange={e => {
                          if (e.target.value === 'custom') return
                          const [heading, body] = e.target.value.split('|')
                          if (heading) loadGoogleFont(heading)
                          if (body) loadGoogleFont(body)
                          save({ headingFont: heading, bodyFont: body })
                        }}
                        className="mt-1.5 block w-full rounded-lg border border-line bg-panel2 p-2 text-sm font-normal text-ink outline-none"
                      >
                        {PAIRINGS.map(([label, heading, body]) => (
                          <option key={label} value={`${heading}|${body}`}>{label}</option>
                        ))}
                        <option value="custom">Custom (Search Google Fonts below)</option>
                      </select>
                    </label>

                    <div className="grid sm:grid-cols-2 gap-3">
                      <FontPicker
                        label="Heading font"
                        value={state.headingFont}
                        placeholder="e.g. Playfair Display"
                        catalog={fontCatalog}
                        onChange={val => save({ headingFont: val })}
                      />
                      <FontPicker
                        label="Body font"
                        value={state.bodyFont}
                        placeholder="e.g. Inter"
                        catalog={fontCatalog}
                        onChange={val => save({ bodyFont: val })}
                      />
                    </div>

                    <div className="pt-2 border-t border-line/60 space-y-3">
                      <div>
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Button corners</p>
                        <div className="flex flex-wrap gap-2">
                          {RADII.map(([label, value]) => (
                            <button
                              key={value}
                              type="button"
                              onClick={() => save({ radius: value })}
                              style={{ borderRadius: value }}
                              className={`border px-3 py-1.5 text-xs transition cursor-pointer
                                ${state.radius === value ? 'border-accent bg-accent/15 text-ink font-medium' : 'border-line text-muted hover:text-ink hover:bg-panel2'}`}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <label className="text-xs font-semibold uppercase tracking-wide text-muted block">
                        Spacing & Density
                        <select
                          value={state.density}
                          onChange={e => save({ density: e.target.value })}
                          className="mt-1.5 block w-full rounded-lg border border-line bg-panel2 p-2 text-sm font-normal text-ink outline-none"
                        >
                          {DENSITIES.map(value => <option key={value}>{value}</option>)}
                        </select>
                      </label>

                      <div>
                        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                          Corner radius <span className="font-normal normal-case text-muted2">({state.radius})</span>
                        </p>
                        <input
                          type="range"
                          min="0"
                          max="32"
                          step="1"
                          aria-label="Corner radius"
                          value={parseInt(state.radius, 10) || 0}
                          onChange={e => save({ radius: `${e.target.value}px` })}
                          className="w-full accent-[#1877F2] cursor-pointer"
                        />
                      </div>

                      <Choice label="Content width" options={WIDTHS} value={state.width}
                        onPick={value => save({ width: value })} />
                      <Choice label="Navigation" options={NAVS} value={state.nav}
                        onPick={value => save({ nav: value })} />
                      <Choice label="Motion" options={MOTIONS} value={state.motion}
                        onPick={value => save({ motion: value })} />
                    </div>
                  </div>
                </div>

                {/* Right Column: Sticky Live Component Sandbox */}
                <div className="lg:col-span-5">
                  <div className="sticky top-6">
                    <LiveComponentPreview state={state} theme={theme} />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Site Images */}
        <div className="mt-5 rounded-xl border border-line bg-panel2 p-5">
          <SiteImages projectId={projectId} />
        </div>

        {/* Additional Look & Feel Directive */}
        <label className="mt-5 block text-sm font-medium">
          Anything else about the look and feel
          <TextArea
            value={state.direction}
            onChange={e => save({ direction: e.target.value })}
            rows={3}
            placeholder="Reference sites, imagery, tone, specific UI guidelines, anything the theme does not cover…"
            className="mt-2 w-full rounded-lg border border-line bg-panel2 p-3 text-ink"
          />
        </label>

        {error && <p role="alert" className="mt-3 text-sm text-bad">{error}</p>}

        {/* Action Bar */}
        <div className="mt-6 flex justify-between gap-3">
          <Button variant="outline" onClick={onBack}>Review SRS</Button>
          <Button disabled={saving} onClick={apply}>
            {saving ? 'Applying design…' : 'Apply to prototype'}
          </Button>
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
