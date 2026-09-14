'use client'

import { useEffect, useState } from 'react'
import { Button, TextArea } from './ui'

export default function DesignCustomize({ projectId, onContinue, onBack }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [direction, setDirection] = useState('')
  const [theme, setTheme] = useState('Follow the product requirements')
  const [density, setDensity] = useState('Comfortable')
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(`agentforge-design-${projectId}`) || '{}')
      setDirection(saved.direction || '')
      setTheme(saved.theme || 'Follow the product requirements')
      setDensity(saved.density || 'Comfortable')
    } catch { }
  }, [projectId])
  function save(patch) {
    const value = { direction, theme, density, ...patch }
    setDirection(value.direction); setTheme(value.theme); setDensity(value.density)
    try { localStorage.setItem(`agentforge-design-${projectId}`, JSON.stringify(value)) } catch { }
  }
  async function apply() {
    if (saving) return
    setSaving(true); setError('')
    try { await onContinue(`Design customization: theme ${theme}; spacing ${density}.\n${direction}`) }
    catch (failure) { setError(failure.message) }
    finally { setSaving(false) }
  }
  return (
    <section className="mx-auto my-auto w-full max-w-2xl rounded-2xl border border-line bg-panel p-7 text-ink">
      <p className="text-xs font-semibold text-accent">SRS approved · Designer</p>
      <h1 className="mt-2 text-2xl font-semibold">Customize the design</h1>
      <p className="mt-3 text-sm text-muted">The designer will use the specification and its handoff files to create the complete HTML prototype.</p>
      <div className="my-5 flex flex-wrap gap-5">
        <label className="text-sm">Theme
          <select value={theme} onChange={e => save({ theme: e.target.value })} className="mt-2 block rounded-lg border border-line bg-panel2 p-2">
            {['Follow the product requirements', 'Light', 'Dark', 'Light and dark'].map(value => <option key={value}>{value}</option>)}
          </select>
        </label>
        <label className="text-sm">Spacing
          <select value={density} onChange={e => save({ density: e.target.value })} className="mt-2 block rounded-lg border border-line bg-panel2 p-2">
            {['Comfortable', 'Compact', 'Spacious'].map(value => <option key={value}>{value}</option>)}
          </select>
        </label>
      </div>
      <label className="text-sm">Visual direction, colors, typography and reference details
        <TextArea value={direction} onChange={e => save({ direction: e.target.value })} rows={5}
          placeholder="Describe how you want the app to look and feel…" className="mt-2 w-full rounded-lg border border-line bg-panel2 p-3" />
      </label>
      {error && <p role="alert" className="mt-3 text-sm text-bad">{error}</p>}
      <div className="mt-6 flex justify-between gap-3">
        <Button variant="outline" onClick={onBack}>Review SRS</Button>
        <Button disabled={saving} onClick={apply}>{saving ? 'Applying design…' : 'Apply to prototype'}</Button>
      </div>
    </section>
  )
}
