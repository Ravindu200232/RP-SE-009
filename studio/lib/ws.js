
import { useStore, KEYS } from './store'
import { api, API, HTTP_FALLBACK, getAuthToken } from './api'
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
let heartbeat = null
let lastEdit = null

// A socket with nothing on it is closed by whatever sits in the middle — a
// tunnel, a proxy — after a minute or two of silence, and a studio watching a
// build that is thinking looks like a studio that lost the server. A word
// every half a minute is enough to keep it open.
const HEARTBEAT_MS = 25000

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
  const store = useStore.getState()
  const base = lastEdit?.project === store.project && lastEdit?.agent === store.agentRole ? lastEdit : null
  useStore.setState({ question: null })
  if (!base) return false
  useStore.getState().addLog('INFO', `Edit: ${prompt}`)
  useStore.getState().setBusy(true)
  send({ ...base, prompt: `${base.prompt}\n\nScope clarification: ${prompt}` })
  return true
}

/**
 * Send the drawing back for another round with what they just typed.
 *
 * There is no dialog to type into, on purpose: the drawing fills the preview
 * so it can be walked and marked up, and the chat box is where changes to it
 * are asked for — the same box that asks for changes to everything else.
 * Returns false when no drawing is waiting, so the message goes where it
 * normally would.
 */
export function reviseDrawing(feedback) {
  const drawing = useStore.getState().drawing
  if (!drawing) return false
  useStore.getState().setDrawing(null)
  api.decide({ id: drawing.id, decision: 'revise', feedback })
     .catch(e => useStore.getState().addLog('WARN', `Could not send that back — ${e.message}`))
  return true
}

function wsUrl() {
  if (typeof location === 'undefined') return 'ws://127.0.0.1:7825'
  // Through the studio's own address rather than the backend's port: one
  // address to publish, and a wss:// feed when the studio is served over
  // HTTPS. next.config.js sends this path to the socket.
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${location.host}/__agentforge/ws`
}

/**
 * Ask the backend what it is waiting on.
 *
 * A question is announced once, over a socket. A studio that reloaded, or that
 * connected a second late, never hears it — and the run then waits out its
 * whole timeout on a question nobody was shown.
 */
/**
 * Put a decision where it is answered.
 *
 * A drawing goes to the preview, where it can be walked and marked up;
 * everything else is a dialog. Both the announcement and the recovery below go
 * through here, because when they disagreed a drawing recovered after a reload
 * went to the dialog that no longer renders one, and disappeared.
 */
function route(question) {
  const store = useStore.getState()
  if (question?.kind === 'prototype') store.setDrawing(question)
  else if (question?.kind === 'plan') {
    api.decide({ id: question.id, decision: 'accept' }).catch(() => {})
  }
  else store.setApproval(question)
}

async function recoverPendingDecision() {
  try {
    const { pending } = await api.decisions()
    const question = (pending || [])[0]
    const store = useStore.getState()
    if (question && question.project === store.project && (!question.agent || question.agent === store.agentRole) && !store.approval && !store.drawing) route(question)
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
  clearInterval(heartbeat)

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
    clearInterval(heartbeat)
    heartbeat = setInterval(() => {
      if (mine !== sock || sock.readyState !== 1) return
      try { sock.send(JSON.stringify({ type: 'ping' })) } catch { }
    }, HEARTBEAT_MS)
    const project = useStore.getState().project
    if (project) api.workflow(project).then(snapshot => useStore.getState().restoreProject(snapshot)).catch(() => {})
    recoverPendingDecision()
  }
  sock.onclose = (event) => {
    if (mine !== sock) return
    clearInterval(heartbeat)
    // 4401: nobody is signed in on this socket. Reconnecting cannot fix that;
    // signing in does, and that calls connect() again.
    if (event?.code === 4401) {
      sock = null
      useStore.getState().setStatus('disconnected', 'sign in to continue')
      return
    }
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
  clearInterval(heartbeat)
  retry = heartbeat = null
  if (sock) {
    sock.onopen = sock.onclose = sock.onerror = sock.onmessage = null
    sock.close()
    sock = null
  }
  flushStream()
  resetStreamQueue()
}

/**
 * Write down what this project has said.
 *
 * Called when a run ends, which is when the account of it is complete and
 * when losing it would cost the most.
 */
function keepStream(project) {
  const s = useStore.getState()
  const name = project || s.project
  if (!name) return
  api.saveStream(name, s.logs, s.chat).catch(() => {
    // An older backend keeps no stream; the session still has it in memory.
  })
}


export function send(obj) {
  const current = useStore.getState()
  const agent = obj.agent || current.agentRole || 'developer'
  obj = { ...obj, agent }
  if (obj.project) current.applyProjectEvent({ type: 'run_state', project: obj.project, agent, status: 'queued' })
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
    headers: { 'Content-Type': 'application/json', ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}) },
    body: JSON.stringify(obj),
  }).then(async response => { if (!response.ok) throw new Error((await response.json()).error || 'Request failed') }).catch(err => {
    useStore.getState().applyProjectEvent({ type: 'error', project: obj.project, agent, text: `Send failed: ${err.message}` })
  })
}

/**
 * Is this message about the project on screen?
 *
 * A run keeps going while you look elsewhere, and its output used to land in
 * whichever feed happened to be open: another project's npm commands
 * appearing in this one's stream. A message that names a project is only for
 * that project; one that names none is about the server and is for everyone.
 *
 * A build announces the name it has just been given through `project`, and
 * ends through `done` or `cancelled`, so those three arrive before - or after
 * - it is the project on screen and are always let through.
 */
function meantForMe(m) {
  const mine = useStore.getState().project
  if (!m?.project || !mine) return true
  if (m.type === 'project' || m.type === 'done' || m.type === 'cancelled') return true
  return m.project === mine
}


function handle(m) {
  const s = useStore.getState()
  // Contracts: approval?.id === m.id | browser_frame
  if (m.type === 'runtime_state') { s.setRuntime(m); return }
  if (m.type === 'project') {
    // Only the unnamed new run can adopt its server-assigned project.
    if (!s.project && s.busy) useStore.setState({ project: m.project, busyProject: m.project })
    s.bumpProjects()
    return
  }
  if (!m.project) return
  s.applyProjectEvent(m)
  if (['done', 'cancelled', 'error'].includes(m.type)) {
    s.bumpProjects()
    api.runtime(m.project).then(runtime => useStore.getState().setRuntime(runtime)).catch(() => {})
    if (m.agent !== 'designer' && m.type === 'done') {
      refreshQaReport(m.project).catch(() => {})
    }
  }
}
