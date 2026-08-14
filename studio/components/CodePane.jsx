'use client'

import { useEffect, useRef } from 'react'
import { FileCode2 } from 'lucide-react'
import { useStore } from '@/lib/store'
import { cn } from '@/lib/utils'

export default function CodePane({ hidden }) {
  const files = useStore(s => s.files)
  const activeFile = useStore(s => s.activeFile)
  const setActiveFile = useStore(s => s.setActiveFile)
  const liveFile = useStore(s => s.liveFile)
  const liveBuf = useStore(s => s.liveBuf)
  const tailRef = useRef(null)

  useEffect(() => {
    if (liveFile) tailRef.current?.scrollIntoView({ block: 'end' })
  }, [liveBuf, liveFile])

  const names = Object.keys(files).sort()
  const streaming = !!liveFile
  const shown = streaming ? liveFile : activeFile
  const body = streaming ? liveBuf : (activeFile ? files[activeFile] : '')

  return (
    <div className={cn('flex min-h-0 flex-1 flex-col', hidden && 'hidden')}>
      <div className="flex shrink-0 items-center gap-2 border-b border-line
                      bg-panel px-3.5 py-2">
        <FileCode2 className="size-3.5 shrink-0 text-muted2" />
        <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-muted">
          {shown || 'No file selected'}
        </span>
        {streaming && (
          <span className="shrink-0 rounded border border-accent/40 px-2 py-0.5
                           font-mono text-[8.5px] text-accent">
            writing…
          </span>
        )}
      </div>

      <div className="flex min-h-0 flex-1">
        <div className="w-[180px] shrink-0 overflow-y-auto border-r border-line
                        bg-panel">
          {names.map(n => (
            <button key={n} onClick={() => setActiveFile(n)}
                    className={cn('flex w-full items-center gap-1.5 px-3 py-1.5',
                      'text-left font-mono text-[10.5px] transition-colors',
                      n === shown ? 'bg-accent/10 text-accent'
                                  : 'text-muted hover:bg-panel2 hover:text-ink')}>
              <span className="truncate">{n}</span>
            </button>
          ))}
          {!names.length && (
            <p className="px-3 py-2 font-mono text-[10px] text-muted2">
              No files yet.
            </p>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-auto bg-code">
          {body ? (
            <pre className="whitespace-pre-wrap break-words p-4 font-mono
                            text-[11.5px] leading-[1.75] text-[#a0aab8]">
              {body}
              {streaming && (
                <span className="ml-0.5 inline-block h-[1em] w-[7px]
                                 animate-pulse bg-accent align-text-bottom" />
              )}
              <span ref={tailRef} />
            </pre>
          ) : (
            <p className="p-4 font-mono text-[11px] text-muted2">
              {names.length ? 'Pick a file from the list.'
                            : 'Files appear here as they are written.'}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
