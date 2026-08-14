'use client'

import { useEffect, useRef } from 'react'
import { ArrowRight, Search, Boxes, PackageOpen, FlaskConical, Globe } from 'lucide-react'
import { useStore } from '@/lib/store'
import { Badge, Button, SectionLabel } from './ui'
import { cn } from '@/lib/utils'

const STEPS = [
  { id: 'refine', name: 'Refine', sub: 'idea analysis', Icon: Search },
  { id: 'build', name: 'Build', sub: 'code generation', Icon: Boxes },
  { id: 'install', name: 'Install', sub: 'npm dependencies', Icon: PackageOpen },
  { id: 'test', name: 'Test', sub: 'browser checks', Icon: FlaskConical },
  { id: 'serve', name: 'Serve', sub: 'localhost:5173', Icon: Globe },
]

const LOG_TONE = {
  ERROR: 'text-bad', WARN: 'text-warn', SUCCESS: 'text-ok', DEBUG: 'opacity-50',
}

export default function Pipeline() {
  const steps = useStore(s => s.steps)
  const phases = useStore(s => s.phases)
  const logs = useStore(s => s.logs)
  const files = useStore(s => s.files)
  const tests = useStore(s => s.tests)
  const activeFile = useStore(s => s.activeFile)
  const setActiveFile = useStore(s => s.setActiveFile)
  const setView = useStore(s => s.setView)
  const tailRef = useRef(null)

  useEffect(() => { tailRef.current?.scrollIntoView({ block: 'end' }) }, [logs.length])

  const names = Object.keys(files).sort()

  return (
    <div className="flex w-[310px] shrink-0 flex-col overflow-hidden border-r
                    border-line bg-panel">
      <SectionLabel className="border-b border-line px-3.5 py-2.5">
        Pipeline
      </SectionLabel>

      <div className="space-y-1 p-2">
        {STEPS.map(({ id, name, sub, Icon }) => {
          const st = steps[id] || 'pending'
          return (
            <div key={id}
                 className={cn('flex items-center gap-2.5 rounded-ctl border p-2',
                   'transition-all duration-300',
                   st === 'pending' ? 'border-transparent opacity-20'
                     : st === 'active' ? 'border-accent/30 bg-accent/[0.06] opacity-100'
                     : st === 'error' ? 'border-bad/30 bg-bad/[0.06] opacity-100'
                     : 'border-transparent opacity-100')}>
              <span className={cn('grid size-7 shrink-0 place-items-center rounded-lg',
                'border border-line bg-panel2',
                st === 'active' ? 'text-accent' : st === 'done' ? 'text-ok'
                  : st === 'error' ? 'text-bad' : 'text-muted2')}>
                <Icon className="size-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="text-[12px] font-semibold text-ink">{name}</div>
                <div className="mt-px truncate font-mono text-[9.5px] text-muted2">
                  {sub}
                </div>
              </div>
              <span className={cn('rounded border px-[7px] py-0.5 font-mono text-[8px]',
                st === 'active' ? 'border-accent/40 text-accent'
                  : st === 'done' ? 'border-ok/40 text-ok'
                  : st === 'error' ? 'border-bad/40 text-bad'
                  : 'border-line text-muted2')}>
                {BADGE[st]}
              </span>
            </div>
          )
        })}
      </div>

      {phases.length > 0 && (
        <div className="border-t border-line px-3 py-2">
          <SectionLabel className="pb-1.5">Build tasks</SectionLabel>
          {phases.map((p, i) => (
            <div key={i} className={cn('flex gap-2 py-0.5 text-[10.5px]',
              p.status === 'active' ? 'text-accent'
                : p.status === 'done' ? 'text-ok' : 'text-muted')}>
              <span className="flex-1 truncate">{p.title}</span>
              {p.written ? <span className="font-mono">{p.written}</span> : null}
            </div>
          ))}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto border-t
                      border-line px-2.5 py-2 font-mono text-[10.5px] leading-[1.9]">
        {logs.map((l, i) => (
          <div key={i} className={cn('whitespace-pre-wrap text-muted', LOG_TONE[l.level])}>
            {l.text}
          </div>
        ))}
        {!logs.length && <div className="text-muted2">Waiting for a build…</div>}
        <div ref={tailRef} />
      </div>

      {(tests.rows.length > 0 || tests.running) && (
        <div className="max-h-[140px] shrink-0 overflow-y-auto border-t border-line
                        bg-panel2 px-3 py-2">
          <SectionLabel className="pb-1"
                        right={<span className="font-mono text-[9px] normal-case tracking-normal">
                          {tests.pass} passed
                          {tests.fail ? ` · ${tests.fail} failed` : ''}
                          {tests.warn ? ` · ${tests.warn} warn` : ''}
                        </span>}>
            Tests
          </SectionLabel>
          {tests.rows.slice(-6).map((r, i) => (
            <div key={i} className="flex gap-2 py-px font-mono text-[10px]">
              <span className={TEST_TONE[r.status] || 'text-muted2'}>
                {TEST_ICON[r.status] || '·'}
              </span>
              <span className="flex-1 truncate text-muted">{r.msg}</span>
            </div>
          ))}
          <Button variant="outline" size="sm" className="mt-2 w-full"
                  onClick={() => setView('testing')}>
            Full results <ArrowRight className="size-3" />
          </Button>
        </div>
      )}

      <div className="max-h-[140px] shrink-0 overflow-y-auto border-t border-line
                      px-3 py-2">
        <SectionLabel className="pb-1"
                      right={<span className="font-mono">{names.length}</span>}>
          Files
        </SectionLabel>
        {names.map(n => (
          <button key={n} onClick={() => { setActiveFile(n); setView('code') }}
                  className={cn('block w-full truncate text-left font-mono',
                    'text-[10px] leading-[1.8]',
                    activeFile === n ? 'text-accent' : 'text-muted hover:text-ink')}>
            {n}
          </button>
        ))}
        {!names.length && (
          <p className="font-mono text-[10px] text-muted2">No files yet.</p>
        )}
      </div>
    </div>
  )
}

const BADGE = { pending: 'waiting', active: 'running', done: 'done', error: 'failed' }


const TEST_ICON = { pass: '✓', fail: '✗', warn: '!', skip: '–', run: '·' }
const TEST_TONE = { pass: 'text-ok', fail: 'text-bad', warn: 'text-warn' }
