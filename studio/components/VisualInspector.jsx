'use client'

import { useState, useEffect, useRef } from 'react'
import {
  X, MoveUp, MoveDown, Trash2, Eye, EyeOff, Save, Check,
  Palette, Type, AlignLeft, AlignCenter, AlignRight,
  Maximize2, Minimize2, Sliders, ChevronDown, ChevronUp,
  Sparkles, CornerUpLeft, Plus, Minus
} from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'

const THEME_SWATCHES = [
  { name: 'Cream', hex: '#F4EFE5' },
  { name: 'Sand', hex: '#EAE1D0' },
  { name: 'Ink', hex: '#16241B' },
  { name: 'Pine', hex: '#22352A' },
  { name: 'Moss', hex: '#5C6B5E' },
  { name: 'Brass', hex: '#A97B3F' },
  { name: 'Gold', hex: '#C39A5E' },
  { name: 'White', hex: '#FFFFFF' },
  { name: 'Black', hex: '#000000' },
  { name: 'Indigo', hex: '#4F46E5' },
  { name: 'Blue', hex: '#2563EB' },
  { name: 'Red', hex: '#EF4444' },
  { name: 'Green', hex: '#10B981' },
]

const FONT_SIZES = ['12px', '14px', '16px', '18px', '22px', '28px', '36px', '48px']
const RADII = [
  { label: '0', val: '0px' },
  { label: 'sm', val: '4px' },
  { label: 'md', val: '8px' },
  { label: 'lg', val: '16px' },
  { label: 'pill', val: '9999px' },
]

export default function VisualInspector({
  element,
  doc,
  project,
  currentFile,
  onClose,
  onLog
}) {
  if (!element || !doc) return null

  const [minimized, setMinimized] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  // Local state for inspector fields
  const [text, setText] = useState('')
  const [textColor, setTextColor] = useState('#000000')
  const [bgColor, setBgColor] = useState('')
  const [fontSize, setFontSize] = useState('')
  const [fontWeight, setFontWeight] = useState('normal')
  const [textAlign, setTextAlign] = useState('left')
  const [borderRadius, setBorderRadius] = useState('')
  const [isHidden, setIsHidden] = useState(false)
  const [padding, setPadding] = useState(0)
  const [margin, setMargin] = useState(0)

  // Read initial computed styles of the element
  useEffect(() => {
    if (!element) return
    try {
      const win = doc.defaultView || window
      const cs = win.getComputedStyle(element)

      // Text
      const isInput = ['INPUT', 'TEXTAREA'].includes(element.tagName)
      setText(isInput ? element.value || '' : element.innerText || '')

      // Color
      setTextColor(rgbToHex(cs.color) || '#000000')
      setBgColor(cs.backgroundColor === 'rgba(0, 0, 0, 0)' ? 'transparent' : rgbToHex(cs.backgroundColor) || '')

      // Typography
      setFontSize(cs.fontSize || '16px')
      setFontWeight(cs.fontWeight || '400')
      setTextAlign(cs.textAlign || 'left')
      setBorderRadius(cs.borderRadius || '0px')
      setIsHidden(cs.display === 'none')
      setPadding(parseInt(cs.paddingTop || '0', 10) || 0)
      setMargin(parseInt(cs.marginTop || '0', 10) || 0)
    } catch { }
  }, [element, doc])

  function rgbToHex(rgb) {
    if (!rgb || rgb === 'transparent') return 'transparent'
    const m = rgb.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/)
    if (!m) return rgb
    return '#' + [m[1], m[2], m[3]].map(x => parseInt(x, 10).toString(16).padStart(2, '0')).join('')
  }

  // Live text changes
  const handleTextChange = (newVal) => {
    setText(newVal)
    if (!element) return
    if (['INPUT', 'TEXTAREA'].includes(element.tagName)) {
      element.value = newVal
    } else {
      element.innerText = newVal
    }
  }

  // Live style changes
  const applyStyle = (prop, val) => {
    if (!element) return
    element.style[prop] = val
  }

  const handleTextColor = (hex) => {
    setTextColor(hex)
    applyStyle('color', hex)
  }

  const handleBgColor = (hex) => {
    setBgColor(hex)
    applyStyle('backgroundColor', hex === 'transparent' ? '' : hex)
  }

  const handleFontSize = (size) => {
    setFontSize(size)
    applyStyle('fontSize', size)
  }

  const handleFontWeight = (w) => {
    setFontWeight(w)
    applyStyle('fontWeight', w)
  }

  const handleTextAlign = (align) => {
    setTextAlign(align)
    applyStyle('textAlign', align)
  }

  const handleBorderRadius = (radius) => {
    setBorderRadius(radius)
    applyStyle('borderRadius', radius)
  }

  const handlePadding = (delta) => {
    const next = Math.max(0, padding + delta)
    setPadding(next)
    applyStyle('padding', `${next}px`)
  }

  const handleMargin = (delta) => {
    const next = Math.max(0, margin + delta)
    setMargin(next)
    applyStyle('margin', `${next}px`)
  }

  // DOM Movement
  const handleMoveUp = () => {
    if (!element || !element.parentElement) return
    const prev = element.previousElementSibling
    if (prev) {
      element.parentElement.insertBefore(element, prev)
      element.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }

  const handleMoveDown = () => {
    if (!element || !element.parentElement) return
    const next = element.nextElementSibling
    if (next) {
      element.parentElement.insertBefore(next, element)
      element.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }

  const handleToggleHide = () => {
    if (!element) return
    const next = !isHidden
    setIsHidden(next)
    element.style.display = next ? 'none' : ''
  }

  const handleDelete = () => {
    if (!element) return
    if (confirm(`Remove this <${element.tagName.toLowerCase()}> element?`)) {
      element.remove()
      onClose?.()
    }
  }

  // Instant Save to HTML File without LLM
  const handleSave = async () => {
    if (!project || !doc) return
    setSaving(true)
    try {
      // Temporarily remove inspector highlighting classes
      const highlighted = doc.querySelectorAll('.__vf_hi, .__lc_hi')
      highlighted.forEach(el => el.classList.remove('__vf_hi', '__lc_hi'))
      const styleTag = doc.getElementById('__vf_style')
      if (styleTag) styleTag.remove()

      const fullHtml = '<!DOCTYPE html>\n' + doc.documentElement.outerHTML

      const relPath = `.agentforge/prototype/${currentFile || 'index.html'}`
      await api.saveFile(project, relPath, fullHtml)
      setSaved(true)
      onLog?.('SUCCESS', `Saved ${relPath} directly via Visual Inspector (0 LLM cost)`)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      onLog?.('WARN', `Could not save HTML — ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  const tagName = element.tagName.toLowerCase()
  const classPreview = (element.className || '').trim().slice(0, 30)

  return (
    <div className="absolute right-4 top-16 z-50 w-80 rounded-2xl border border-line/80 bg-panel/95 p-4 shadow-2xl backdrop-blur-xl transition-all dark:border-white/10 dark:bg-[#12161f]/95">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-line/60 pb-3 dark:border-white/10">
        <div className="flex items-center gap-2 overflow-hidden">
          <span className="rounded-lg bg-emerald-500/15 px-2 py-0.5 font-mono text-[11px] font-bold text-emerald-600 dark:text-emerald-400">
            &lt;{tagName}&gt;
          </span>
          {classPreview && (
            <span className="truncate font-mono text-[10px] text-muted" title={element.className}>
              .{classPreview}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setMinimized(!minimized)}
            className="rounded-lg p-1 text-muted hover:bg-ink/[.06] hover:text-ink"
            title={minimized ? 'Expand' : 'Minimize'}
          >
            {minimized ? <ChevronDown className="size-3.5" /> : <ChevronUp className="size-3.5" />}
          </button>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-muted hover:bg-red-500/10 hover:text-red-500"
            title="Close Inspector"
          >
            <X className="size-3.5" />
          </button>
        </div>
      </div>

      {!minimized && (
        <div className="mt-3 flex flex-col gap-3.5 text-[11.5px]">
          {/* Quick Actions (Move & Visibility) */}
          <div className="flex items-center justify-between gap-1 rounded-xl bg-ink/[.03] p-1 dark:bg-white/[.04]">
            <button
              onClick={handleMoveUp}
              title="Move element up before previous sibling"
              className="flex flex-1 items-center justify-center gap-1 rounded-lg py-1.5 text-ink hover:bg-panel hover:shadow-xs active:scale-95 dark:text-white"
            >
              <MoveUp className="size-3 text-emerald-600 dark:text-emerald-400" />
              <span className="text-[11px] font-medium">Up</span>
            </button>
            <button
              onClick={handleMoveDown}
              title="Move element down after next sibling"
              className="flex flex-1 items-center justify-center gap-1 rounded-lg py-1.5 text-ink hover:bg-panel hover:shadow-xs active:scale-95 dark:text-white"
            >
              <MoveDown className="size-3 text-emerald-600 dark:text-emerald-400" />
              <span className="text-[11px] font-medium">Down</span>
            </button>
            <button
              onClick={handleToggleHide}
              title={isHidden ? 'Show element' : 'Hide element'}
              className="flex flex-1 items-center justify-center gap-1 rounded-lg py-1.5 text-ink hover:bg-panel hover:shadow-xs active:scale-95 dark:text-white"
            >
              {isHidden ? <EyeOff className="size-3 text-amber-500" /> : <Eye className="size-3 text-blue-500" />}
              <span className="text-[11px] font-medium">{isHidden ? 'Show' : 'Hide'}</span>
            </button>
            <button
              onClick={handleDelete}
              title="Remove element"
              className="flex items-center justify-center rounded-lg p-1.5 text-red-500 hover:bg-red-500/10 active:scale-95"
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>

          {/* Live Text Editing */}
          {['P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'BUTTON', 'A', 'SPAN', 'LABEL', 'LI', 'INPUT', 'TEXTAREA'].includes(element.tagName) && (
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                Text Content
              </label>
              <textarea
                value={text}
                onChange={(e) => handleTextChange(e.target.value)}
                rows={2}
                className="w-full resize-none rounded-xl border border-line/70 bg-panel px-2.5 py-1.5 font-sans text-[12px] text-ink outline-none ring-accent/30 focus:ring-2 dark:border-white/10 dark:bg-black/20 dark:text-white"
                placeholder="Type new text..."
              />
            </div>
          )}

          {/* Color Palette */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">Colors</span>
              <div className="flex items-center gap-3">
                {/* Text Color */}
                <label className="flex cursor-pointer items-center gap-1" title="Text Color">
                  <span className="text-[10.5px] font-medium text-ink dark:text-white">Text</span>
                  <input
                    type="color"
                    value={textColor.startsWith('#') ? textColor : '#000000'}
                    onChange={(e) => handleTextColor(e.target.value)}
                    className="size-4 cursor-pointer rounded-full border-0 p-0"
                  />
                </label>
                {/* Bg Color */}
                <label className="flex cursor-pointer items-center gap-1" title="Background Color">
                  <span className="text-[10.5px] font-medium text-ink dark:text-white">Bg</span>
                  <input
                    type="color"
                    value={bgColor.startsWith('#') ? bgColor : '#ffffff'}
                    onChange={(e) => handleBgColor(e.target.value)}
                    className="size-4 cursor-pointer rounded-full border-0 p-0"
                  />
                </label>
              </div>
            </div>

            {/* Quick Swatches */}
            <div className="flex flex-wrap gap-1.5">
              {THEME_SWATCHES.slice(0, 10).map(({ name, hex }) => (
                <button
                  key={name}
                  onClick={() => handleBgColor(hex)}
                  title={`Set bg to ${name} (${hex})`}
                  style={{ backgroundColor: hex }}
                  className="size-4.5 rounded-full border border-black/15 shadow-xs transition-transform hover:scale-125 dark:border-white/20"
                />
              ))}
              <button
                onClick={() => handleBgColor('transparent')}
                title="Transparent background"
                className="rounded-full border border-line px-1.5 py-0.5 text-[9px] font-mono text-muted hover:text-ink"
              >
                None
              </button>
            </div>
          </div>

          {/* Typography & Layout */}
          <div className="grid grid-cols-2 gap-2 border-t border-line/60 pt-2.5 dark:border-white/10">
            {/* Font Size */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">Size</span>
              <div className="flex items-center gap-1">
                <select
                  value={fontSize}
                  onChange={(e) => handleFontSize(e.target.value)}
                  className="w-full rounded-lg border border-line/70 bg-panel px-1.5 py-1 text-[11px] text-ink outline-none dark:border-white/10 dark:bg-black/20 dark:text-white"
                >
                  {FONT_SIZES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>
            </div>

            {/* Font Weight */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">Weight</span>
              <div className="flex items-center rounded-lg border border-line/70 bg-panel p-0.5 dark:border-white/10 dark:bg-black/20">
                {['400', '600', '700'].map(w => (
                  <button
                    key={w}
                    onClick={() => handleFontWeight(w)}
                    className={cn(
                      'flex-1 rounded py-0.5 text-[10px] font-medium transition-colors',
                      fontWeight === w ? 'bg-accent text-white font-bold' : 'text-muted hover:text-ink'
                    )}
                  >
                    {w === '400' ? 'Reg' : w === '600' ? 'Med' : 'Bold'}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Alignment & Radius */}
          <div className="grid grid-cols-2 gap-2">
            {/* Text Align */}
            <div className="flex items-center rounded-lg border border-line/70 bg-panel p-0.5 dark:border-white/10 dark:bg-black/20">
              <button
                onClick={() => handleTextAlign('left')}
                className={cn('flex-1 rounded py-1 flex justify-center text-muted hover:text-ink', textAlign === 'left' && 'bg-accent/10 text-accent font-bold')}
                title="Align Left"
              >
                <AlignLeft className="size-3" />
              </button>
              <button
                onClick={() => handleTextAlign('center')}
                className={cn('flex-1 rounded py-1 flex justify-center text-muted hover:text-ink', textAlign === 'center' && 'bg-accent/10 text-accent font-bold')}
                title="Align Center"
              >
                <AlignCenter className="size-3" />
              </button>
              <button
                onClick={() => handleTextAlign('right')}
                className={cn('flex-1 rounded py-1 flex justify-center text-muted hover:text-ink', textAlign === 'right' && 'bg-accent/10 text-accent font-bold')}
                title="Align Right"
              >
                <AlignRight className="size-3" />
              </button>
            </div>

            {/* Corner Radius */}
            <div className="flex items-center rounded-lg border border-line/70 bg-panel p-0.5 dark:border-white/10 dark:bg-black/20">
              {RADII.map(r => (
                <button
                  key={r.label}
                  onClick={() => handleBorderRadius(r.val)}
                  className={cn(
                    'flex-1 rounded py-0.5 text-[9.5px] font-medium transition-colors',
                    borderRadius === r.val ? 'bg-accent text-white' : 'text-muted hover:text-ink'
                  )}
                  title={`Radius ${r.val}`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          {/* Spacing adjustments */}
          <div className="flex items-center justify-between border-t border-line/60 pt-2 text-[10.5px] text-muted dark:border-white/10">
            <div className="flex items-center gap-1.5">
              <span>Padding:</span>
              <button onClick={() => handlePadding(-2)} className="rounded bg-ink/[.05] px-1.5 py-0.5 hover:bg-ink/[.1] dark:bg-white/[.08]"><Minus className="size-2.5" /></button>
              <span className="font-mono text-ink dark:text-white">{padding}px</span>
              <button onClick={() => handlePadding(2)} className="rounded bg-ink/[.05] px-1.5 py-0.5 hover:bg-ink/[.1] dark:bg-white/[.08]"><Plus className="size-2.5" /></button>
            </div>
            <div className="flex items-center gap-1.5">
              <span>Margin:</span>
              <button onClick={() => handleMargin(-2)} className="rounded bg-ink/[.05] px-1.5 py-0.5 hover:bg-ink/[.1] dark:bg-white/[.08]"><Minus className="size-2.5" /></button>
              <span className="font-mono text-ink dark:text-white">{margin}px</span>
              <button onClick={() => handleMargin(2)} className="rounded bg-ink/[.05] px-1.5 py-0.5 hover:bg-ink/[.1] dark:bg-white/[.08]"><Plus className="size-2.5" /></button>
            </div>
          </div>

          {/* Instant Save to HTML button */}
          <button
            onClick={handleSave}
            disabled={saving}
            className={cn(
              'mt-1 flex w-full items-center justify-center gap-1.5 rounded-xl py-2 font-semibold text-white shadow-md transition-all active:scale-95 disabled:opacity-50',
              saved
                ? 'bg-emerald-600 shadow-emerald-500/20'
                : 'bg-accent hover:bg-accent/90 shadow-accent/20'
            )}
          >
            {saving ? (
              <span className="text-[11.5px]">Saving...</span>
            ) : saved ? (
              <>
                <Check className="size-3.5" />
                <span className="text-[11.5px]">Saved to HTML!</span>
              </>
            ) : (
              <>
                <Save className="size-3.5" />
                <span className="text-[11.5px]">Save to HTML (Instant)</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  )
}
