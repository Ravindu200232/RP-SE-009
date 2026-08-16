'use client'

import { forwardRef, useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'


export function Button({ variant = 'ghost', size = 'md', className, ...rest }) {
  return (
    <button
      className={cn(
        'inline-flex shrink-0 items-center justify-center gap-1.5 rounded-ctl',
        'font-medium transition-colors outline-none',
        'focus-visible:ring-2 focus-visible:ring-accent/50',
        'disabled:pointer-events-none disabled:opacity-40',
        { sm: 'h-6 px-2 text-[10.5px]', md: 'h-7 px-2.5 text-[11.5px]',
          lg: 'h-9 px-4 text-[13px]', icon: 'size-7', 'icon-sm': 'size-6' }[size],
        { solid: 'bg-accent text-white hover:brightness-110',
          outline: 'border border-line text-ink hover:border-line2 hover:bg-panel2',
          ghost: 'text-muted hover:bg-panel2 hover:text-ink',
          subtle: 'bg-panel2 text-ink hover:bg-raised' }[variant],
        className)}
      {...rest} />
  )
}

export function Tag({ tone = 'mute', className, children }) {
  return (
    <span className={cn(
      'inline-flex items-center rounded-[3px] px-[5px] py-px',
      'text-[7.5px] font-bold uppercase tracking-wide',
      { mute: 'bg-line text-muted', ok: 'bg-ok/15 text-ok', bad: 'bg-bad/15 text-bad',
        warn: 'bg-warn/15 text-warn', accent: 'bg-accent/15 text-accent' }[tone],
      className)}>
      {children}
    </span>
  )
}

export function Badge({ tone = 'mute', className, children }) {
  return (
    <span className={cn(
      'inline-flex items-center rounded font-mono text-[9px] px-1.5 py-px',
      { mute: 'bg-line text-muted2', ok: 'bg-ok/15 text-ok', bad: 'bg-bad/15 text-bad',
        warn: 'bg-warn/15 text-warn', accent: 'bg-accent/15 text-accent' }[tone],
      className)}>
      {children}
    </span>
  )
}

export function SectionLabel({ children, right, className }) {
  return (
    <div className={cn('flex items-center justify-between',
      'text-[9px] font-semibold uppercase tracking-[1.5px] text-muted2',
      className)}>
      <span>{children}</span>
      {right}
    </div>
  )
}

export const Panel = ({ className, children }) => (
  <div className={cn('rounded-panel border border-line bg-panel', className)}>
    {children}
  </div>
)

export const Empty = ({ children, bad }) => (
  <p className={cn('px-1 py-7 text-[12.5px]', bad ? 'text-bad' : 'text-muted')}>
    {children}
  </p>
)

export function Modal({ onClose, children, className }) {
  useEffect(() => {
    const key = (e) => { if (e.key === 'Escape') onClose?.() }
    document.addEventListener('keydown', key)
    return () => document.removeEventListener('keydown', key)
  }, [onClose])
  return (
    <div onClick={onClose}
         className="fixed inset-0 z-[600] flex items-center justify-center
                    bg-black/60 p-4 backdrop-blur-sm">
      <div onClick={e => e.stopPropagation()}
           className={cn('w-full max-w-[520px] rounded-panel border border-line2',
             'bg-panel p-5 shadow-2xl', className)}>
        {children}
      </div>
    </div>
  )
}

export function Dropdown({ open, onClose, children, className }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return
    const away = (e) => {
      if (!ref.current?.parentElement?.contains(e.target)) onClose()
    }
    const key = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('click', away)
    document.addEventListener('keydown', key)
    return () => {
      document.removeEventListener('click', away)
      document.removeEventListener('keydown', key)
    }
  }, [open, onClose])
  if (!open) return null
  return (
    <div ref={ref}
         className={cn('absolute z-[500] overflow-hidden rounded-panel',
           'border border-line2 bg-panel shadow-2xl', className)}>
      {children}
    </div>
  )
}

export function Tip({ text, children, className, side = 'top' }) {
  const [on, setOn] = useState(false)
  return (
    <span className={cn('relative inline-flex', className)}
          onMouseEnter={() => setOn(true)} onMouseLeave={() => setOn(false)}>
      {children}
      {on && text && (
        <span className={cn('pointer-events-none absolute z-[700] whitespace-nowrap',
          'rounded-ctl border border-line2 bg-raised px-2 py-1 text-[10.5px]',
          'text-ink shadow-lg',
          side === 'top' ? 'bottom-full left-1/2 mb-1.5 -translate-x-1/2'
                         : 'left-full top-1/2 ml-1.5 -translate-y-1/2')}>
          {text}
        </span>
      )}
    </span>
  )
}

/**
 * What every editable field in the studio has to carry.
 *
 * Writing extensions rewrite a field before React hydrates it. Grammarly adds
 * `data-gramm`, QuillBot adds `data-qb-tmp-id` with a fresh random id, and
 * both add `spellcheck` — so the server's HTML and the client's DOM disagree
 * on attributes this app never set, and React reports a hydration mismatch on
 * a page that is perfectly correct. It cannot be fixed by matching them: the
 * QuillBot id is random per load, so there is nothing to match.
 *
 * `suppressHydrationWarning` is React's own answer for exactly this — it stops
 * the warning for this element's attributes and nothing else. The opt-out
 * attributes are set as well, so the extensions that honour them leave the
 * field alone rather than being merely tolerated: in a code editor a grammar
 * checker is not noise, it underlines source and offers to correct it.
 */
export const plainField = {
  suppressHydrationWarning: true,
  spellCheck: false,
  'data-gramm': 'false',
  'data-gramm_editor': 'false',
  'data-enable-grammarly': 'false',
}

export const Input = ({ className, ...rest }) => (
  <input className={cn('h-7 w-full rounded-ctl border border-line bg-bg px-2.5',
    'text-[11.5px] text-ink outline-none transition-colors',
    'placeholder:text-muted2 focus:border-accent/60', className)}
    {...plainField} {...rest} />
)

/** A textarea with the same protection. Everything else passes through. */
export const TextArea = forwardRef(function TextArea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={className} {...plainField} {...rest} />
})

export const Table = ({ className, children }) => (
  <div className="w-full overflow-x-auto">
    <table className={cn('w-full border-collapse text-[11.5px]', className)}>
      {children}
    </table>
  </div>
)
export const TR = ({ className, children, ...rest }) => (
  <tr className={cn('border-b border-line last:border-0', className)} {...rest}>
    {children}
  </tr>
)
export const TH = ({ className, children }) => (
  <th className={cn('px-2.5 py-2 text-left text-[9px] font-semibold uppercase',
    'tracking-[1px] text-muted2', className)}>{children}</th>
)
export const TD = ({ className, children }) => (
  <td className={cn('px-2.5 py-2 align-top', className)}>{children}</td>
)
