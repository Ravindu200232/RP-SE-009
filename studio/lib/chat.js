/**
 * The build, as a conversation.
 *
 * The panel beside the preview used to be a terminal: raw backend lines,
 * scrolling past faster than anyone could read, with the one sentence that
 * mattered buried in it. The build screen has the opposite problem — it is
 * deliberately calm, shows five paced milestones, and drops everything else,
 * so watching it you cannot tell whether the agent is working or stuck.
 *
 * This is the middle: every action the agent takes, in the order it took it,
 * named in English. Nothing is dropped. A line this does not recognise is
 * shown as it arrived rather than swallowed, because an unrecognised line is
 * usually the interesting one.
 */

/** Consecutive work of the same kind collapses into one turn. */
const GROUP_MS = 60_000
const MAX_TURNS = 120

const KINDS = [
  // [pattern, kind, how to title it]
  [/^\s*Reading\s+(.+)$/i, 'read', m => `Read ${m[1]}`],
  [/^\s*(?:Searching|globFiles|grepSearch)\s+(.+)$/i, 'read', m => `Searched for ${m[1]}`],
  [/^\s*listDir\s+(.+)$/i, 'read', m => `Listed ${m[1]}`],
  [/^\s*Looking at the project/i, 'read', () => 'Looked at the project layout'],
  [/^\s*Deciding what to prove\s*(.*)$/i, 'plan', () => 'Decided what to prove'],
  [/^\s*scope:\s*(\d+)\s*requirement/i, 'plan', m => `Verification scope: ${m[1]} requirement(s)`],
  [/^\s*(written|created|patched|edited)\s+(\S+)\s*\((\d+) lines\)/i, 'write',
    m => `${m[1][0].toUpperCase()}${m[1].slice(1)} ${m[2]} (${m[3]} lines)`],
  [/^\s*(written|created|patched|edited)\s+(\S+)/i, 'write',
    m => `${m[1][0].toUpperCase()}${m[1].slice(1)} ${m[2]}`],
  [/^\s*removed\s+(\S+)/i, 'write', m => `Removed ${m[1]}`],
  [/^\s*Writing\s+(.+)$/i, 'write', m => `Writing ${m[1]}`],
  [/^\s*Editing\s+(.+)$/i, 'write', m => `Editing ${m[1]}`],
  [/^\s*running\s+(unit|e2e|runtime)\/(.+)$/i, 'test', m => `Running ${m[1]} suite: ${m[2]}`],
  [/^\s*Testing\s+(.+)$/i, 'test', m => `Testing ${m[1]}`],
  [/^\s*Checking in the browser\s*(.*)$/i, 'test', m => `Browser journey${m[1] ? `: ${m[1]}` : ''}`],
  [/^\s*Running\s+(.+)$/i, 'run', m => `Ran ${m[1]}`],
  [/^\s*\$\s+(.+)$/i, 'run', m => m[1]],
  [/^\s*Design contract:\s*(.+)$/i, 'design', m => `Design: ${m[1]}`],
  [/^\s*Scaffolded\s+(.+)$/i, 'setup', m => `Scaffolded ${m[1]}`],
  [/^\s*Prepared project skills:\s*(.+)$/i, 'setup', m => 'Prepared the project skills'],
  [/^\s*Context checkpoint/i, 'setup', () => 'Summarised older context to make room'],
]

/** Lines that are noise in a conversation, however useful they are in a log. */
const MUTED = [
  /^\s*\$\s/,                       // the echoed command; the "Ran …" line covers it
  /^\s*(?:HTTP|WS|connection)\b/i,
  /^\s*type:\s/i,
  /fast refresh|webpack|destination stream closed/i,
]

function classify(row) {
  const line = String(row.text || '').replace(/\s+/g, ' ').trim()
  if (!line) return null
  if (MUTED.some(pattern => pattern.test(line))) return null

  if (row.level === 'ERROR') {
    return { kind: 'warn', title: line.replace(/^[⚠✗\s]+/, ''), detail: '' }
  }
  if (row.level === 'WARN') {
    return { kind: 'warn', title: line.replace(/^[⚠\s]+/, '').slice(0, 200), detail: '' }
  }
  for (const [pattern, kind, title] of KINDS) {
    const match = pattern.exec(line)
    if (match) return { kind, title: title(match), detail: '' }
  }
  if (row.level === 'SUCCESS') return { kind: 'done', title: line.replace(/^[✅\s]+/, ''), detail: '' }
  // Not recognised. Show it rather than drop it — the line nobody wrote a rule
  // for is usually the one worth reading.
  return { kind: 'note', title: line.slice(0, 220), detail: '' }
}

export function chatTurns(logs = [], chat = []) {
  const turns = []
  for (const row of logs) {
    const event = classify(row)
    if (!event) continue

    const last = turns.at(-1)
    if (last && last.role === 'activity' && last.kind === event.kind
        && row.at - last.at < GROUP_MS) {
      // Same kind of work, still going: extend the turn rather than add one.
      if (!last.items.some(item => item.title === event.title)) {
        last.items.push({ title: event.title, detail: event.detail })
      }
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
  return turns.slice(-MAX_TURNS)
}

/** A one-line verdict for a finished run, from the evidence it produced. */
export function verdictOf(qa) {
  const unit = qa?.vitest
  const e2e = qa?.report?.e2e
  const bits = []
  if (unit) {
    const cases = (unit.testResults || []).flatMap(s => s.assertionResults || [])
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
