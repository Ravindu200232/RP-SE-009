'use client'

/**
 * The attach and record controls, and the list of what came back.
 *
 * The list shows the extracted text rather than just a filename with a tick.
 * A tick is a claim that the file was read; the first line of what was read is
 * the evidence. It is also the only place a customer can catch the case that
 * matters — a photo the model described wrongly, or a recording transcribed
 * into something they did not say — while they can still remove it.
 */
import { useRef } from 'react'
import { AlertTriangle, Check, FileText, Image as ImageIcon, Loader2, Mic,
         Paperclip, Square, X } from 'lucide-react'

import { ACCEPT_UPLOAD } from '@/lib/api'
import { useRecorder } from '@/lib/use-attachments'
import { Button } from '../ui'
import { cn } from '@/lib/utils'

const ICON = { document: FileText, picture: ImageIcon, recording: Mic, file: FileText }

function size(bytes) {
  if (!bytes) return ''
  return bytes < 1_000_000 ? `${Math.max(1, Math.round(bytes / 1000))} KB`
                           : `${(bytes / 1_000_000).toFixed(1)} MB`
}

function clock(s) {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function AttachButtons({ attach, disabled, label = 'Attach' }) {
  const picker = useRef(null)
  const recorder = useRecorder(file => attach.add([file]))

  return (
    <>
      <input ref={picker} type="file" multiple hidden accept={ACCEPT_UPLOAD}
             onChange={e => {
               attach.add(e.target.files)
               // Cleared so re-picking the same file fires change again.
               e.target.value = ''
             }} />

      <Button variant="ghost" size="sm" disabled={disabled}
              onClick={() => picker.current?.click()}
              title="Attach a document, a photo or a recording — a price list, a form you use today, a screenshot of the old system">
        <Paperclip className="size-3" /> {label}
      </Button>

      <Button variant={recorder.recording ? 'solid' : 'ghost'} size="sm"
              disabled={disabled} onClick={recorder.toggle}
              title={recorder.recording ? 'Stop recording' : 'Say it instead of typing it'}>
        {recorder.recording
          ? <><Square className="size-2.5 fill-current" /> {clock(recorder.seconds)}</>
          : <><Mic className="size-3" /> Record</>}
      </Button>

      {recorder.error && (
        <span className="text-[10.5px] text-bad">{recorder.error}</span>
      )}
    </>
  )
}

export function AttachList({ attach, className }) {
  if (!attach.items.length) return null

  return (
    <ul className={cn('space-y-1', className)}>
      {attach.items.map(it => {
        const Icon = ICON[it.kind] || FileText
        const failed = it.state === 'failed'
        return (
          <li key={it.key}
              className={cn('flex items-start gap-2 rounded-ctl border px-2 py-1.5',
                            failed ? 'border-bad/40 bg-bad/5' : 'border-line bg-panel2')}>
            <Icon className={cn('mt-px size-3 shrink-0',
                                failed ? 'text-bad' : 'text-muted')} />

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="truncate text-[11.5px] text-ink">{it.name}</span>
                <span className="shrink-0 font-mono text-[9.5px] text-muted2">
                  {size(it.size)}
                </span>
                {it.state === 'reading' && (
                  <Loader2 className="size-2.5 shrink-0 animate-spin text-accent" />
                )}
                {it.state === 'done' && !it.note && (
                  <Check className="size-2.5 shrink-0 text-ok" />
                )}
                {(failed || (it.state === 'done' && it.note)) && (
                  <AlertTriangle className="size-2.5 shrink-0 text-warn" />
                )}
              </div>

              {it.read && (
                <p className="mt-0.5 line-clamp-2 text-[10.5px] leading-snug text-muted">
                  {it.read.slice(0, 220)}
                </p>
              )}
              {it.note && (
                <p className={cn('mt-0.5 text-[10.5px] leading-snug',
                                 failed ? 'text-bad' : 'text-warn')}>
                  {it.note}
                </p>
              )}
              {it.state === 'reading' && (
                <p className="mt-0.5 text-[10.5px] text-muted">
                  {it.kind === 'recording' ? 'Transcribing…'
                    : it.kind === 'picture' ? 'Showing it to the model…'
                    : 'Reading it…'}
                </p>
              )}
            </div>

            <button onClick={() => attach.remove(it.key)}
                    disabled={it.state === 'reading'}
                    title="Remove"
                    className="mt-px shrink-0 text-muted2 transition-colors
                               hover:text-ink disabled:opacity-30">
              <X className="size-3" />
            </button>
          </li>
        )
      })}
    </ul>
  )
}
