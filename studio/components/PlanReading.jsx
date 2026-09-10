'use client'

/**
 * The plan, laid out to be read.
 *
 * This is the one moment someone is asked to approve what is about to be
 * built, and it used to arrive as raw Markdown in a monospace block — the
 * shape of a file, not of a proposal. Headings become headings, bullets
 * become bullets, and the parts that matter are legible at a glance.
 */

import { readInline, readPlan } from '@/lib/plan-read'
import { cn } from '@/lib/utils'

function Inline({ text }) {
  return readInline(text).map((part, i) => {
    if (part.kind === 'strong') return <b key={i} className="font-semibold text-ink">{part.text}</b>
    if (part.kind === 'em') return <i key={i}>{part.text}</i>
    if (part.kind === 'code') {
      return (
        <code key={i} className="rounded-[5px] bg-ink/[.06] px-1 py-[1px] font-mono text-[10.5px] text-ink dark:bg-white/10">
          {part.text}
        </code>
      )
    }
    return <span key={i}>{part.text}</span>
  })
}

export default function PlanReading({ plan, className }) {
  const blocks = readPlan(plan)
  if (!blocks.length) {
    return <p className={cn('text-[12px] text-muted', className)}>The planner returned nothing to read.</p>
  }

  return (
    <div className={cn('space-y-3', className)}>
      {blocks.map((block, i) => {
        if (block.kind === 'heading') {
          // Every heading below the title reads at one weight: a plan is not
          // a document with chapters, it is a list of what will happen.
          return (
            <h3 key={i} className={cn('text-ink', block.level <= 1
              ? 'pt-1 text-[13.5px] font-semibold'
              : 'pt-1 text-[12px] font-semibold uppercase tracking-[.08em] text-muted')}>
              <Inline text={block.text} />
            </h3>
          )
        }

        if (block.kind === 'bullets') {
          return (
            <ul key={i} className="space-y-1.5">
              {block.items.map((item, j) => (
                <li key={j} className="flex gap-2.5 text-[12px] leading-relaxed text-muted">
                  <span className="mt-[7px] size-1 shrink-0 rounded-full bg-accent/60" />
                  <span className="min-w-0"><Inline text={item} /></span>
                </li>
              ))}
            </ul>
          )
        }

        if (block.kind === 'steps') {
          return (
            <ol key={i} className="space-y-1.5">
              {block.items.map((item, j) => (
                <li key={j} className="flex gap-2.5 text-[12px] leading-relaxed text-muted">
                  <span className="mt-[1px] grid size-[17px] shrink-0 place-items-center rounded-full bg-accent/10 font-mono text-[9.5px] font-semibold text-accent">
                    {j + 1}
                  </span>
                  <span className="min-w-0"><Inline text={item} /></span>
                </li>
              ))}
            </ol>
          )
        }

        if (block.kind === 'code') {
          return (
            <pre key={i} className="overflow-x-auto rounded-lg border border-line/70 bg-panel2/60 p-2.5 font-mono text-[10.5px] leading-relaxed text-ink">
              {block.text}
            </pre>
          )
        }

        return (
          <p key={i} className="text-[12px] leading-relaxed text-muted">
            <Inline text={block.text} />
          </p>
        )
      })}
    </div>
  )
}
