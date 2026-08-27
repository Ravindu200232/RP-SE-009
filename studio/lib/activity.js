function words(value = '') {
  return String(value)
    .replace(/\.[^.\/]+$/, '')
    .replace(/\[([^\]]+)\]/g, '$1')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[-_]+/g, ' ')
    .replace(/\b(id|slug)\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function title(value = '') {
  const out = words(value)
  return (out || 'app').replace(/\b\w/g, c => c.toUpperCase())
}

export function friendlyTarget(path = '') {
  const clean = String(path).replace(/\\/g, '/').replace(/^\.\//, '')
  const parts = clean.split('/').filter(Boolean)
  if (!parts.length) return 'the app'

  if (parts[0] === 'tests') {
    const base = parts.at(-1)?.replace(/\.(?:test|spec)\.[jt]sx?$/, '') || 'feature'
    return `${title(base)} test`
  }
  if (parts[0] === 'app' && parts[1] === 'api') {
    const route = parts.slice(2, -1).filter(x => !/^\[/.test(x))
    return `${title(route.at(-1) || 'app')} service`
  }
  if (parts[0] === 'app' && /^page\.[jt]sx?$/.test(parts.at(-1) || '')) {
    const route = parts.slice(1, -1).filter(x => !/^\[/.test(x))
    return `${title(route.at(-1) || 'home')} page`
  }
  if (parts[0] === 'components') return title(parts.at(-1) || 'component')
  if (parts[0] === 'lib') return `${title(parts.at(-1) || 'app')} logic`
  return title(parts.at(-1) || parts.at(-2) || 'app')
}

function pathFrom(line = '') {
  const match = String(line).match(/(?:^|\s)((?:(?:app|components|lib|tests|qa|public)\/[A-Za-z0-9_@.\-\[\]\/]+\.(?:jsx?|tsx?|json|css|md)))/i)
  return match?.[1] || ''
}

function countMatch(line, pattern) {
  const m = line.match(pattern)
  return m ? m.slice(1).map(Number) : null
}

export function activityEvent(text = '', level = 'INFO') {
  const line = String(text).replace(/\s+/g, ' ').trim()
  const low = line.toLowerCase()
  const path = pathFrom(line)
  const target = path ? friendlyTarget(path) : ''
  if (!line) return null

  // The build screen is intentionally calm. Technical output remains in Terminal.
  if (/^\[?next\]?/i.test(line) || low.includes('http request:') || low.includes('webpack')) return null
  if (low.includes('destination stream closed early') || low.includes('fast refresh')) return null
  if (low.includes('mongodb') && (low.includes('connected') || low.includes('adopting'))) return null
  if ((level === 'WARN' || level === 'ERROR') && !/repair|fix|root cause|correcting|rewrit/i.test(low)) return null

  let m = countMatch(line, /(\d+)\/(\d+) files on disk/i)
  if (m) return { kind: 'build', title: `${m[0]} of ${m[1]} files created`, detail: 'The approved app structure is being written.' }

  m = countMatch(line, /journey\s+(\d+)\/(\d+)/i)
  if (m) return { kind: 'test', title: `End-to-end testing — ${m[0]} of ${m[1]}`, detail: 'The browser is following a real user journey.' }

  m = countMatch(line, /round\s+(\d+)(?:\/\d+)?/i)
  if (m && (/unit|vitest/i.test(low) || /passing|test\(s\).*failing|test cases?/i.test(low))) return { kind: 'test', title: `Unit testing — round ${m[0]}`, detail: 'Focused checks are running against the latest code.' }
  if (m && /e2e|end-to-end|agentic/i.test(low)) return { kind: 'fix', title: `Repairing end-to-end flow — round ${m[0]}`, detail: 'A failed user step is being traced and checked again.' }

  if (/planning.*plan\.md|writing plan\.md|\bplanning\b/.test(low) && !/replan|repair/.test(low)) {
    return { kind: 'plan', title: 'Creating the build plan', detail: 'Pages, data, roles and user flows are being mapped.' }
  }
  if (/plan ready|replanned|plan completeness|capability proof map/.test(low)) {
    return { kind: 'done', title: 'Build plan ready', detail: 'The builder has a complete map of what to create.' }
  }
  if (/requirement.*coverage|coverage.*analy|capabilit.*coverage/.test(low)) {
    return { kind: 'test', title: 'Analyzing requirement coverage', detail: 'Checking that the requested behavior is represented in the app.' }
  }

  if (/authored .*test|writing tests|test harness ready|test file\(s\) written/.test(low)) {
    return { kind: 'test', title: 'Creating unit tests', detail: 'Focused checks are being prepared for the code that was created.' }
  }
  if (/vitest run|running unit|unit test\(s\).*failing|unit tests? passed/.test(low)) {
    return { kind: 'test', title: 'Running unit tests', detail: 'The latest behavior is being checked before browser testing.' }
  }

  if (/journeys? to walk|starting.*e2e|e2e testing start|final e2e/.test(low)) {
    return { kind: 'test', title: 'Starting end-to-end testing', detail: 'A browser is about to use the app from start to finish.' }
  }
  if (/clean-room|final.*end-to-end|final.*journey/.test(low)) {
    return { kind: 'test', title: 'Final end-to-end verification', detail: 'The finished app is being checked from a clean browser session.' }
  }

  if (/repair|root cause|fixing|repaired|correcting|rewrit/.test(low)) {
    return { kind: 'fix', title: target ? `Repairing ${target}` : 'Repairing a failed step', detail: 'The affected code is being corrected, then the same behavior will be checked again.' }
  }

  if (path && (low.includes('📝') || low.includes('written') || low.includes('rewritten') || low.includes('created'))) {
    return { kind: 'done', title: `${target} created`, detail: 'This part is ready for its next check.' }
  }

  if (/npm run build|checking the app build/.test(low)) {
    return { kind: 'test', title: 'Checking the complete build', detail: 'Making sure the finished project compiles cleanly.' }
  }
  if (/build clean/.test(low)) {
    return { kind: 'done', title: 'Complete build is ready', detail: 'The latest project compiled successfully.' }
  }
  if (/api verification/.test(low)) {
    return { kind: 'test', title: 'Checking app services', detail: 'The app services needed by the user flows are being verified.' }
  }
  if (/security/.test(low)) {
    return { kind: 'test', title: 'Checking access rules', detail: 'Role and route access is being verified.' }
  }
  if (/ready|serving|live preview/.test(low)) {
    return { kind: 'done', title: 'Preparing the live preview', detail: 'The finished app is being refreshed for you.' }
  }
  return null
}

export function liveFileActivity(path = '') {
  const target = friendlyTarget(path)
  if (path.startsWith('tests/')) {
    return { kind: 'test', title: `Creating ${target}`, detail: 'A focused check is being written for the latest behavior.' }
  }
  return { kind: 'build', title: `Creating ${target}`, detail: 'This part of the app is being written now.' }
}
