
import { useStore, KEYS } from './store'
import { api, API, HTTP_FALLBACK } from './api'
import { refreshQaReport } from './qa-results'


const STEP_ALIAS = { plan: 'build', generate: 'build' }

// What each outgoing message is, in the terms the overlay presents.
const WORK_KIND = {
  agent_build: 'build',
  agent_update: 'edit', agent_resume: 'build',
  feature: 'feature',
  element_edit: 'select',
}

let sock = null
let retry = null
let lastEdit = null

let streamPending = ''
let streamTimer = null
let e2eVersion = 0

function flushStream() {
  if (!streamPending) return
  const chunk = streamPending
  streamPending = ''
  streamTimer = null
  useStore.setState(st => ({ liveBuf: st.liveBuf + chunk }))
}

function queueStream(token) {
  streamPending += token || ''
  if (streamTimer) return
  streamTimer = setTimeout(flushStream, 32)
}

function resetStreamQueue() {
  if (streamTimer) clearTimeout(streamTimer)
  streamTimer = null
  streamPending = ''
}


/** Resend the last edit with an answer or instruction. */
export function answerQuestion(prompt) {
  const base = lastEdit
  useStore.setState({ question: null })
  if (!base) return false
  useStore.getState().addLog('INFO', `Edit: ${prompt}`)
  useStore.getState().setBusy(true)
  send({ ...base, prompt: `${base.prompt}\n\nScope clarification: ${prompt}` })
  return true
}

function wsUrl() {
  const host = (typeof location !== 'undefined' && location.hostname) || 'localhost'
  return `ws://${host}:7825`
}

/**
 * Ask the backend what it is waiting on.
 *
 * A question is announced once, over a socket. A studio that reloaded, or that
 * connected a second late, never hears it — and the run then waits out its
 * whole timeout on a question nobody was shown.
 */
async function recoverPendingDecision() {
  try {
    const { pending } = await api.decisions()
    const question = (pending || [])[0]
    const store = useStore.getState()
    if (question && !store.approval) store.setApproval(question)
  } catch {
    // An older backend has no such endpoint; the announcement is all there is.
  }
}


export function connect() {
  if (typeof window === 'undefined') return
  const s = useStore.getState()

  // Close whatever is already open FIRST.
  if (sock) {
    try {
      sock.onclose = null
      sock.onmessage = null
      sock.onerror = null
      sock.close()
    } catch { }
    sock = null
  }
  clearTimeout(retry)

  try {
    sock = new WebSocket(wsUrl())
  } catch (e) {
    s.setStatus('disconnected', 'no socket')
    return
  }
  const mine = sock
  // Every handler checks it is still the current socket before it speaks.
  sock.onopen = () => {
    if (mine !== sock) return
    useStore.getState().setStatus('live', 'ready')
    recoverPendingDecision()
  }
  sock.onclose = () => {
    if (mine !== sock) return
    useStore.getState().setStatus('disconnected', 'reconnecting…')
    clearTimeout(retry)
    retry = setTimeout(connect, 3000)
  }
  sock.onerror = () => {
    if (mine === sock) useStore.getState().setStatus('disconnected', 'error')
  }
  sock.onmessage = (e) => {
    if (mine !== sock) return
    let m
    try { m = JSON.parse(e.data) } catch { return }
    handle(m)
  }

  if (typeof window !== 'undefined') window.__studioFeed = handle
  return disconnect
}

export function disconnect() {
  clearTimeout(retry)
  retry = null
  if (sock) {
    sock.onopen = sock.onclose = sock.onerror = sock.onmessage = null
    sock.close()
    sock = null
  }
  flushStream()
  resetStreamQueue()
}

export function send(obj) {
  if (obj && obj.type) {
    useStore.getState().setWorkKind(WORK_KIND[obj.type] || 'build')
    // Whose run this is. The project on screen can change while it works.
    if (obj.project) useStore.getState().setBusyProject(obj.project)
  }
  if (obj && obj.prompt !== undefined) {
    lastEdit = obj
    useStore.setState({ question: null })
  }
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

    case 'project':
      // The directory exists now, so the run has a name. Adopting it here is
      // what lets the chat header, the file tree and the preview all say what
      // is being built instead of waiting for the run to finish.
      if (m.project) {
        useStore.setState({ project: m.project })
        s.setBusyProject(m.project)     // a new build had no name until now
      }
      s.bumpProjects()
      break

    case 'step':         s.setStep(STEP_ALIAS[m.step] || m.step, m.status); break
    case 'progress':     s.setProgress(m.step, m.pct); break
    case 'phase':
      s.upsertPhase(m)

      s.setStage(m.status === 'active' ? (m.title || '') : '')
      break
    case 'file':         s.putFile(m.name, m.content || ''); break
    case 'stream_start':
      resetStreamQueue()
      useStore.setState({ liveFile: m.file, liveBuf: '', follow: true })
      break
    case 'stream':
      queueStream(m.token || '')
      break
    case 'stream_end':
      flushStream()
      resetStreamQueue()
      s.putFile(m.file, m.content || '')
      useStore.setState({ liveFile: null, liveBuf: '' })
      break

    case 'test_start':
      e2eVersion += 1
      s.setE2eLive(null)
      s.testStart()
      break
    case 'test_run':     s.testRun(m.attempt); break
    case 'test_result':  s.testResult(m); break
    case 'test_report': {
      if (m.project === s.project) refreshQaReport(m.project)
        .catch(error => useStore.getState().addLog('WARN', `Testing results: ${error.message}`))
      break
    }
    case 'test_fixing':  s.testFixing(m); break
    case 'e2e_parallel':  s.e2eParallelEvent(m); break
    case 'e2e_event': {
      s.e2eEvent(m)
      // A journey no longer carries its own picture: there is one browser and
      // it streams into the preview. What survives here is where it is and
      // what it is doing.
      const prior = m.state === 'journey_start' ? {} : (s.e2eLive || {})
      const at = Date.now()
      s.setE2eLive({ ...prior, ...m, at })
      if (m.state === 'journey_done') {
        const version = ++e2eVersion
        setTimeout(() => {
          const current = useStore.getState().e2eLive
          if (version === e2eVersion && current?.at === at) {
            useStore.getState().setE2eLive(null)
          }
        }, 1500)
      }
      break
    }

  // Close every stream when the run ends.
    case 'done':
      s.setBusy(false)
      s.setBusyProject('')
      s.setWorkKind('')
      s.testDone()
      s.setAgentState('')
      s.setApproval(null)
      s.setBrowserFrame(null)
      resetStreamQueue()
      useStore.setState({ liveFile: null, liveBuf: '', e2eLive: null })
      s.pushChat({ role: 'assistant', tone: 'ok', title: 'Finished',
                   text: 'The app is running in the preview. Ask for a change '
                       + 'here, or open Testing for the evidence.' })
  // Invalidate the cached QA report after project changes.
      if (m.project) useStore.setState({ project: m.project })
      if (m.project) refreshQaReport(m.project)
        .catch(error => useStore.getState().addLog('WARN', `Testing results: ${error.message}`))
      s.bumpProjects()
      break
    // Cancelled is not an error and must not read like one.
    case 'cancelled':
      s.setBusy(false)
      s.setBusyProject('')
      s.setWorkKind('')
      s.testDone()
      s.setAgentState('')
      s.setApproval(null)
      s.setBrowserFrame(null)
      resetStreamQueue()
      useStore.setState({ liveFile: null, liveBuf: '', e2eLive: null, project: '' })
      s.setQaReport(null)
      s.pushChat({ role: 'assistant', tone: 'bad', title: 'Stopped',
                   text: m.project ? `${m.project} and its specification were removed.`
                                   : 'The run was cancelled.' })
      s.addLog('WARN', m.project
        ? `cancelled — ${m.project} and its specification were removed`
        : 'cancelled')
      s.bumpProjects()
      break
    case 'error':
      s.setBusy(false)
      s.setBusyProject('')
      s.setWorkKind('')
      s.testDone()
      s.setAgentState('')
      s.setApproval(null)
      s.setBrowserFrame(null)
      resetStreamQueue()
      useStore.setState({ liveFile: null, liveBuf: '', e2eLive: null })
      s.pushChat({ role: 'assistant', tone: 'bad', title: 'That did not work',
                   text: m.text || 'The run failed.' })
      s.addLog('ERROR', m.text || 'failed')
      break

    // Question that paused the run.
    case 'ask':
      s.pushChat({ role: 'assistant', title: 'One thing first',
                   text: `${m.file || 'That element'} appears on `
                       + `${(m.routes || []).length} routes. Which did you mean?` })
      useStore.setState({ question: {
        kind: m.kind || 'scope', file: m.file || '', route: m.route || '',
        routes: m.routes || [], options: m.options || [],
      } })
      break

    case 'detected':     s.addLog('INFO', `type: ${m.site_type} · ${m.strategy}`); break
    case 'chat_intent':  s.addLog('INFO', `${m.intent || 'ask'} — ${m.summary || ''}`); break
    case 'agent_msg':
      // The plan and the design contract arrive this way. They are the two
      // things the build is about to act on, so they get their own shape
      // rather than being flattened into one more grey paragraph.
      s.pushChat({ role: 'assistant', text: m.text, title: m.title,
                   kind: m.kind, design: m.design })
      break
    case 'memory':       s.setRunStats(m); break
    case 'agent_state':  s.setAgentState(m.state || ''); break
    case 'approval':     s.setApproval(m); break
    case 'browser_frame':
      s.setBrowserFrame(m.frame ? m : null)
      break
    case 'approval_resolved':
      // The next question can already be on screen by the time this lands.
      if (!m.id || useStore.getState().approval?.id === m.id) s.setApproval(null)
      s.pushChat({ role: 'assistant', title: m.kind === 'plan' ? 'The plan' : 'Design system',
                   text: m.decision === 'revise' ? 'Sent back for another round.'
                       : m.decision === 'skip' ? 'Left for the build to decide.'
                       : 'Accepted.' })
      break
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
      s.addLog('INFO', `undo point saved (${(m.files || []).join(', ')})`)
      break
    default: break
  }
}
