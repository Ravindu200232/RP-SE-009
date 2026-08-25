import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const source = fs.readFileSync(path.join(root, 'lib', 'activity.js'), 'utf8')
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
const mod = await import(moduleUrl)

const cases = [
  ['Planning — writing plan.md', 'INFO', 'Creating the build plan'],
  ['📝 app/login/page.jsx (5.0KB)', 'INFO', 'Login page created'],
  ['17/25 files on disk (turn 4, +3)', 'INFO', '17 of 25 files created'],
  ['🧪 authored 3 test file(s)', 'INFO', 'Creating unit tests'],
  ['$ npx --no-install vitest run', 'INFO', 'Running unit tests'],
  ['📊 round 1: 33/44 passing (75%)', 'INFO', 'Unit testing — round 1'],
  ['requirement coverage analyzing', 'INFO', 'Analyzing requirement coverage'],
  ['🎭 6 journeys to walk: Booking · Pricing', 'INFO', 'Starting end-to-end testing'],
  ['🎭 journey 1/6 — Booking (as guest)', 'INFO', 'End-to-end testing — 1 of 6'],
  ['🧠 Agentic E2E round 1/2 (hard cap 6)', 'INFO', 'Repairing end-to-end flow — round 1'],
  ['🧠 repair root cause — checkout action is missing', 'WARN', 'Repairing a failed step'],
]

for (const [raw, level, expected] of cases) {
  const event = mod.activityEvent(raw, level)
  if (!event || event.title !== expected) {
    throw new Error(`activity mismatch for ${raw}: ${JSON.stringify(event)}; expected ${expected}`)
  }
  if (/\b(?:app|components|lib|tests)\//i.test(event.title) || /\.(?:jsx?|tsx?)\b/i.test(event.title)) {
    throw new Error(`technical path leaked into activity title: ${event.title}`)
  }
}

const quiet = [
  ['[next] GET /rooms 200 in 277ms', 'INFO'],
  ['webpack compiled with warnings', 'WARN'],
  ['unrelated warning from a dependency', 'WARN'],
  ['random technical error text', 'ERROR'],
]
for (const [raw, level] of quiet) {
  if (mod.activityEvent(raw, level) !== null) {
    throw new Error(`technical noise should stay out of build milestones: ${raw}`)
  }
}

const live = mod.liveFileActivity('app/login/page.jsx')
if (live.title !== 'Creating Login page') {
  throw new Error(`live file activity mismatch: ${JSON.stringify(live)}`)
}

console.log('Human build activity verification: OK')
