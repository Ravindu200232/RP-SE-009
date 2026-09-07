/**
 * The build, as a conversation.
 *
 * The panel beside the preview used to be a terminal: raw backend lines,
 * scrolling past faster than anyone could read, with the one sentence that
 * mattered buried in it. What people actually want to know is what the agent
 * is doing and what it found — so the same event stream is folded into turns.
 *
 * Nothing new is invented here. Assistant turns come from what the agent
 * explicitly said; activity turns are the tool lines the log already carries,
 * grouped so twelve file writes read as one step rather than twelve.
 */

import { activityEvent } from './activity'

/** Consecutive activity of the same kind collapses into one turn. */
const GROUP_MS = 45_000

export function chatTurns(logs = [], chat = []) {
  const turns = []
  const seen = new Set()

  for (const row of logs) {
    const event = activityEvent(row.text, row.level)
    if (!event) continue
    const key = `${event.kind}:${event.title}:${event.detail}`
    if (seen.has(key)) continue
    seen.add(key)

    const last = turns.at(-1)
    if (last && last.role === 'activity' && last.kind === event.kind
        && row.at - last.at < GROUP_MS) {
      // Same kind of work, still going: extend the turn instead of adding one.
      last.items.push({ title: event.title, detail: event.detail })
      last.at = row.at
      continue
    }
    turns.push({
      role: 'activity', kind: event.kind, at: row.at,
      items: [{ title: event.title, detail: event.detail }],
    })
  }

  for (const entry of chat) turns.push({ ...entry, role: entry.role || 'assistant' })
  turns.sort((a, b) => (a.at || 0) - (b.at || 0))
  return turns
}

/** A one-line verdict for a finished run, from the evidence it produced. */
export function verdictOf(qa) {
  const unit = qa?.vitest
  const e2e = qa?.report?.e2e
  const bits = []
  if (unit) {
    const cases = (unit.testResults || [])
      .flatMap(s => s.assertionResults || [])
    const passed = cases.filter(c => c.status === 'passed').length
    if (cases.length) bits.push(`${passed}/${cases.length} unit tests passing`)
  }
  if (e2e?.stage_total) {
    bits.push(`${e2e.stage_passed}/${e2e.stage_total} browser stages passing`)
  }
  const findings = qa?.report?.security?.findings || []
  if (findings.length) bits.push(`${findings.length} security finding(s)`)
  return bits.join(' · ')
}
