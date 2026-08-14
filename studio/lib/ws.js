
import { useStore, KEYS } from './store'
import { API, HTTP_FALLBACK } from './api'


const STEP_ALIAS = { plan: 'build', generate: 'build' }

let sock = null
let retry = null

export function wsUrl() {
  const host = (typeof location !== 'undefined' && location.hostname) || 'localhost'
  return `ws://${host}:7825`
}

export function connect() {
  if (typeof window === 'undefined') return
  const s = useStore.getState()
  try {
    sock = new WebSocket(wsUrl())
  } catch (e) {
    s.setStatus('disconnected', 'no socket')
    return
  }
  sock.onopen = () => useStore.getState().setStatus('live', 'ready')
  sock.onclose = () => {
    useStore.getState().setStatus('disconnected', 'reconnecting…')
    clearTimeout(retry)
    retry = setTimeout(connect, 3000)
  }
  sock.onerror = () => useStore.getState().setStatus('disconnected', 'error')
  sock.onmessage = (e) => {
    let m
    try { m = JSON.parse(e.data) } catch { return }
    handle(m)
  }

  if (typeof window !== 'undefined') window.__studioFeed = handle
}

export function send(obj) {
  if (sock && sock.readyState === 1) {
    sock.send(JSON.stringify(obj))
    return
  }
  const ep = HTTP_FALLBACK[obj.type]
  if (!ep) {
    useStore.getState().addLog('WARN',
      `not sent — the socket is down and ${obj.type} has no fallback route`)
    return
  }
  fetch(API + ep, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(obj),
  }).catch(err => useStore.getState().addLog('WARN', `send failed: ${err.message}`))
}

function handle(m) {
  const s = useStore.getState()
  switch (m.type) {
    case 'log':          s.addLog(m.level, m.text); break

    case 'step':         s.setStep(STEP_ALIAS[m.step] || m.step, m.status); break
    case 'progress':     s.setProgress(m.step, m.pct); break
    case 'phase':
      s.upsertPhase(m)

      s.setStage(m.status === 'active' ? (m.title || '') : '')
      break
    case 'file':         s.putFile(m.name, m.content || ''); break
    case 'stream_start': useStore.setState({ liveFile: m.file, liveBuf: '' }); break
    case 'stream':       useStore.setState(st => ({ liveBuf: st.liveBuf + (m.token || '') })); break
    case 'stream_end':
      s.putFile(m.file, m.content || '')
      useStore.setState({ liveFile: null, liveBuf: '' })
      break

    case 'test_start':   s.testStart(); break
    case 'test_run':     s.testRun(m.attempt); break
    case 'test_result':  s.testResult(m); break
    case 'test_fixing':  s.testFixing(m); break

    case 'done':
      s.setBusy(false)
      s.testDone()
      if (m.project) useStore.setState({ project: m.project })
      break
    case 'error':
      s.setBusy(false)
      s.testDone()
      s.addLog('ERROR', m.text || 'failed')
      break

    case 'detected':     s.addLog('INFO', `type: ${m.site_type} · ${m.strategy}`); break
    case 'chat_intent':  s.addLog('INFO', `${m.intent || 'ask'} — ${m.summary || ''}`); break
    case 'agent_msg':    s.addLog('INFO', m.text); break
    case 'memory':       break
    case 'mongo':        break
    case 'command':      break
    case 'demo_accounts': break
    case 'feature_plan': break
    case 'element_picked':
      s.addLog('INFO', `   ${m.file}${m.line ? ':' + m.line : ''}`)
      if (m.file) s.setActiveFile(m.file)
      break
    case 'undo_point':
      s.setUndo({ id: m.id, files: m.files || [] })
      s.addLog('INFO', `   ↩ undo point saved (${(m.files || []).join(', ')})`)
      break
    default: break
  }
}

export { KEYS }
