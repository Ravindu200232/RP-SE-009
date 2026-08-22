'use client'

import { useMemo, useState } from 'react'
import { Check, ChevronsUpDown, Search } from 'lucide-react'
import { Dropdown, Tag, Tip } from './ui'
import { cn } from '@/lib/utils'

export default function ModelPicker({
  label, value, options, onChange, placeholder = 'choose…', hint,
}) {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')

  const unique = useMemo(() => {
    const seen = new Set()
    return options.filter(m => {
      const k = m.id ?? ''
      if (seen.has(k)) return false
      seen.add(k)
      return true
    })
  }, [options])

  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return unique
    return unique.filter(m => (m.id || '').toLowerCase().includes(needle)
                           || (m.label || '').toLowerCase().includes(needle))
  }, [unique, q])

  const current = unique.find(m => m.id === value)

  return (
    <div className="relative px-3 pb-1.5">
      <div className="mb-1 text-[8.5px] font-semibold uppercase tracking-[1.4px]
                      text-muted2">
        {label}
      </div>
      <Tip text={hint} className="w-full">
        <button onClick={(e) => { e.stopPropagation(); setOpen(o => !o); setQ('') }}
                className={cn('flex w-full items-center gap-2 rounded-ctl border',
                  'bg-bg px-2.5 py-[7px] text-left transition-colors',
                  open ? 'border-accent/60' : 'border-line hover:border-line2')}>
          <span className="text-[13px] leading-none">{current?.icon || '◇'}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate font-mono text-[11px] text-ink">
              {value || placeholder}
            </span>
            {current?.ctx ? (
              <span className="mt-px block text-[9px] text-muted2">
                {Math.round(current.ctx / 1024)}k{current.vision ? ' · vision' : ''}
              </span>
            ) : null}
          </span>
          <ChevronsUpDown className="size-3 shrink-0 text-muted2" />
        </button>
      </Tip>

      <Dropdown open={open} onClose={() => setOpen(false)}
                className="left-3 right-3 top-[calc(100%+2px)]">
        <div className="flex items-center gap-2 border-b border-line px-2.5">
          <Search className="size-3 shrink-0 text-muted2" />
          <input autoFocus value={q} placeholder="Search models…"
                 onChange={e => setQ(e.target.value)}
                 className="w-full bg-transparent py-2 text-[11.5px] text-ink
                            outline-none placeholder:text-muted2" />
        </div>
        <div className="max-h-[320px] overflow-auto p-1">
          {shown.map(m => (
            <button key={m.id || '__inherit'}
                    onClick={() => { onChange(m.id); setOpen(false) }}
                    className={cn('flex w-full items-start gap-2 rounded-ctl px-2 py-[7px]',
                      'text-left transition-colors',
                      m.id === value ? 'bg-accent/12' : 'hover:bg-panel2')}>
              <Check className={cn('mt-px size-3 shrink-0 text-accent',
                                   m.id === value ? 'opacity-100' : 'opacity-0')} />
              <span className="text-[13px] leading-none">{m.icon || '◇'}</span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-1 text-[11.5px] text-ink">
                  {m.label || m.id}
                  {m.tag && <Tag tone={TAG[m.tag]}>{m.tag}</Tag>}
                  {m.ctx ? <Tag>{Math.round(m.ctx / 1024)}k</Tag> : null}
                  {m.vision && <Tag tone="accent">vision</Tag>}
                  {m.willPull && <Tag tone="warn">will pull</Tag>}
                </span>
                {m.desc && (
                  <span className="mt-0.5 block text-[9.5px] leading-snug text-muted">
                    {m.desc}
                  </span>
                )}
              </span>
            </button>
          ))}
          {!shown.length && (
            <p className="px-2 py-3 text-[11px] text-muted">Nothing matches “{q}”.</p>
          )}
        </div>
      </Dropdown>
    </div>
  )
}

const TAG = { code: 'ok', cloud: 'accent', fast: 'warn', big: 'mute', local: 'mute' }
