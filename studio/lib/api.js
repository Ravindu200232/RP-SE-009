
export const API = '/__agentforge/api'

let authToken = ''

export function setAuthToken(token) {
  authToken = token || ''
  if (typeof window !== 'undefined') {
    if (token) localStorage.setItem('agentforge_token', token)
    else localStorage.removeItem('agentforge_token')
  }
}

export function getAuthToken() {
  if (authToken) return authToken
  if (typeof window !== 'undefined') {
    return localStorage.getItem('agentforge_token') || ''
  }
  return ''
}

let onSignedOut = null

/** Called when the server says this session is over, from wherever it happens. */
export function whenSignedOut(fn) {
  onSignedOut = fn
}

async function req(path, opts = {}) {
  const token = getAuthToken()
  const headers = { ...(opts.headers || {}) }
  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const r = await fetch(API + path, { ...opts, headers })
  const text = await r.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = { raw: text } }
  // The session expired, or was ended elsewhere: back to the sign-in page
  // rather than a studio full of errors about someone who is not signed in.
  if (r.status === 401 && data?.auth === 'required' && token === getAuthToken()) onSignedOut?.()
  if (!r.ok) {
    const error = new Error((data && (data.error || data.detail)) || `HTTP ${r.status}`)
    error.status = r.status
    throw error
  }
  return data
}

const post = (path, body) => req(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {}),
})

export const api = {
  auth: {
    signup: (data) => post('/auth/signup', data),
    login: (data) => post('/auth/login', data),
    me: () => req('/auth/me'),
    logout: () => post('/auth/logout', {}),
  },
  // A project belongs to whoever built it, from the moment it is created;
  // there is nothing for the studio to assign.
  projects: () => req('/projects'),
  models: () => req('/models'),
  mongo: () => req('/mongo'),
  settings: () => req('/settings'),
  saveSettings: (s) => post('/settings', s),
  imageCheck: () => req('/image-check'),
  imageStart: () => post('/image-start', {}),
  files: (project, agent = 'developer') => req(`/files/${encodeURIComponent(project)}?agent=${agent}`),
  saveFile: (project, path, content) => post('/save-file', { project, path, content }),
  open: (project) => post(`/open/${encodeURIComponent(project)}`, {}),
  runtime: (project) => req(`/runtime/${encodeURIComponent(project)}`),

  // An address for this project's app that works away from this machine.
  previewLink: (project) => post('/preview-link', { project }),
  previewActivity: (project, runtimeId) => post(`/runtime/${encodeURIComponent(project)}/activity`, { runtimeId }),
  deleteProject: (project) => post('/delete-project', { project }),

  // Stop the running build.
  cancelBuild: (project, agent) => post('/build/cancel', { project, agent }),

  // Answer a question the run is waiting on: the plan, or the design.
  decide: (body) => post('/decision', body),

  // What a run is waiting on right now, for a studio that missed the message.
  decisions: () => req('/decisions'),

  // What a project's conversation is already holding, for the status line.
  session: (project) => req(`/session/${encodeURIComponent(project)}`),

  // Everything that has happened to a project, so a reload does not lose it.
  stream: (project) => req(`/stream/${encodeURIComponent(project)}`),
  retrySync: project => post('/sync/retry', { project }),
  workflow: (project) => req(`/workflow/${encodeURIComponent(project)}`),
  saveStream: (project, logs, chat) => post('/stream', { project, logs, chat }),

  // Throw away a specification that has not been approved.
  discardSrs: (srs_id) => post('/discard-srs', { srs_id }),

  // Keep an approved specification as a project, without building it.
  keepSrs: (srs_id) => post('/keep-srs', { srs_id }),
  undo: (project, id) => post('/undo', { project, id }),

  logoPrompt: (prompt, model, opts) => localJob('/logo-prompt', { prompt, model }, opts),
  image: (body, opts) => localJob('/image', body, opts),

  // The same answer as `image`, from a file instead of a prompt.
  imageUpload: (file, body) => Promise.resolve(tooBig(file)).then(big => {
    if (big) throw big
    return fileToBase64(file).then(data_base64 =>
      post('/image-upload', { ...body, filename: file.name, data_base64 }))
  }),

  // Photograph what the user pointed at, so it can travel with the message.
  shot: (body) => post('/shot', body),

  // Read one attachment for an editing chat.
  attach: (file, body) => Promise.resolve(tooBig(file)).then(big => {
    if (big) throw big
    return fileToBase64(file).then(data_base64 =>
      post('/attach', { ...body, filename: file.name, data_base64 }))
  }),

  // Hold one file for a build that has no project yet. Over HTTP on purpose:
  // the build message itself goes over the socket, which refuses this size.
  buildAttach: (token, file, opts = {}) => Promise.resolve(tooBig(file)).then(big => {
    if (big) throw big
    return fileToBase64(file).then(data_base64 =>
      post('/build-attach', { token, filename: file.name || 'upload',
                              purpose: opts.purpose || '', data_base64 }))
  }),

  uploadProject: (body) => post('/upload-project', body),
  mongoPrefetch: () => post('/mongo/prefetch', {}),

  qa: (project) => req(`/qa/${encodeURIComponent(project)}`),
  qaScreenshotUrl: (project, path, at = '') => `${API}/qa-screenshot/${encodeURIComponent(project)}?path=${encodeURIComponent(path)}&v=${encodeURIComponent(at)}`,
  qaPdfUrl: (project) => `${API}/qa-pdf/${encodeURIComponent(project)}`,

  srsResults: (project) => req(`/srs-results/${encodeURIComponent(project)}`),

  srsPdfUrl: (project) => `${API}/srs-pdf/${encodeURIComponent(project)}`,
  srsStatus: () => req('/srs-status'),
  integrations: (project) => req(`/srs/projects/${encodeURIComponent(project)}/integrations`),
  saveIntegrations: (project, answers) => post(`/srs/projects/${encodeURIComponent(project)}/integrations`, { answers }),

  resumeSrs: path => resumeSrsJob(path),
  srs: (path, body) => body === undefined
    ? req(`/srs${path}`)
    : srsJob(path, body),

  // `purpose` describes how the file will be used.
  srsUpload: (project, file, opts = {}) => Promise.resolve(tooBig(file)).then(big => {
    if (big) throw big
    return fileToBase64(file).then(data_base64 =>
      srsJob(`/projects/${encodeURIComponent(project)}/inputs-json`, {
        mode: uploadMode(file),
        filename: file.name || 'upload',
        content_type: file.type || '',
        purpose: opts.purpose || '',
        data_base64,
      }, opts))
  }),

  deployStatus: () => req('/deploy-status'),
  deployResults: (project) => req(`/deploy-results/${encodeURIComponent(project)}`),
  deployStart: (body) => post('/deploy-start', body),

  deploy: (path, body) => body === undefined
    ? req(`/deploy${path}`)
    : deployJob('POST', path, body),

  deployRead: (path, opts) => deployJob('GET', path, null, opts),
}


async function deployJob(method, path, body, { onWait, signal } = {}) {
  const started = await post('/deploy/jobs', { path, method, body })
  const id = started.job_id
  for (let i = 0; ; i++) {
    if (signal?.aborted) throw new Error('cancelled')
    await new Promise(r => setTimeout(r, i < 10 ? 300 : 900))
    const job = await req(`/deploy/jobs/${id}`)
    if (job.status === 'running') { onWait?.(job.elapsed); continue }
    if (job.status === 'error') throw new Error(job.error || 'the deployment agent failed')
    if (job.http_status >= 400) {
      const detail = job.result?.error ?? job.result?.detail
      throw new Error(typeof detail === 'string'
        ? detail : `HTTP ${job.http_status}`)
    }
    return job.result
  }
}

const srsInflight = new Map()
async function digest(text) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, '0')).join('')
}
async function srsPrefix() { return `agentforge-srs-job:${await digest(getAuthToken())}:` }
async function pollSrs(id, key, { onWait, signal } = {}) {
  const started = Date.now()
  let failures = 0
  while (Date.now() - started < 60 * 60 * 1000) {
    if (signal?.aborted) throw new Error('cancelled')
    await new Promise(resolve => setTimeout(resolve, 1500))
    let job
    try { job = await req(`/srs/jobs/${id}`); failures = 0 }
    catch (error) {
      if (error.status === 404) { try { localStorage.removeItem(key) } catch { }; throw error }
      if (++failures >= 3) throw error
      continue
    }
    if (job.status === 'running') { onWait?.(job.elapsed); continue }
    try { localStorage.removeItem(key) } catch { }
    if (job.status === 'error') throw new Error(job.error || 'The SRS update failed')
    if (job.http_status >= 400) throw new Error(job.result?.detail || job.result?.error || `HTTP ${job.http_status}`)
    return job.result
  }
  throw new Error('The SRS job is still pending. Reopen this project to continue following it.')
}
async function srsJob(path, body, options = {}) {
  const key = (await srsPrefix()) + await digest(path + JSON.stringify(body))
  if (srsInflight.has(key)) return srsInflight.get(key)
  const work = (async () => {
    let saved
    try { saved = JSON.parse(localStorage.getItem(key) || 'null') } catch { }
    if (!saved) {
      const started = await post('/srs/jobs', { path, method: 'POST', body })
      saved = { id: started.job_id, path, started: Date.now() }
      try { localStorage.setItem(key, JSON.stringify(saved)) } catch { }
    }
    return pollSrs(saved.id, key, options)
  })()
  srsInflight.set(key, work)
  try { return await work } finally { srsInflight.delete(key) }
}
async function resumeSrsJob(path) {
  const prefix = await srsPrefix()
  for (const key of Object.keys(localStorage)) {
    if (!key.startsWith(prefix)) continue
    let saved
    try { saved = JSON.parse(localStorage.getItem(key)) } catch { continue }
    if (saved?.path !== path) continue
    try { return { resumed: true, result: await (srsInflight.get(key) || pollSrs(saved.id, key)) } }
    catch (error) { if (error.status !== 404) throw error }
  }
  return { resumed: false }
}

const MAX_UPLOAD_BYTES = 7_500_000

function tooBig(file) {
  if ((file?.size || 0) <= MAX_UPLOAD_BYTES) return null
  const mb = n => `${(n / 1_000_000).toFixed(1)} MB`
  return new Error(
    `${file.name || 'that file'} is ${mb(file.size)} — the limit is ${mb(MAX_UPLOAD_BYTES)}.`)
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error(`${file.name} could not be read`))
    // readAsDataURL gives "data:<type>;base64,<payload>".
    reader.onload = () => resolve(String(reader.result || '').split(',')[1] || '')
    reader.readAsDataURL(file)
  })
}

// Everything the engine can actually read. A document or an archive used to be
// unpickable here and unreadable there, so the one format most requirements
// arrive in — a Word file — could not be attached at all.
export const ACCEPT_UPLOAD =
  '.pdf,.png,.jpg,.jpeg,.webp,.gif,.bmp,.wav,.mp3,.m4a,.ogg,.webm,.flac,'
  + '.doc,.docx,.pptx,.xlsx,.rtf,.zip,.txt,.md,.csv,.tsv,.json,.yaml,.yml,.html,.xml,'
  + 'image/*,audio/*,application/pdf,application/zip'

export function uploadMode(file) {
  const type = (file.type || '').toLowerCase()
  const name = (file.name || '').toLowerCase()
  if (type.includes('pdf') || name.endsWith('.pdf')) return 'pdf'
  if (type.startsWith('image/') || /\.(png|jpe?g|webp|gif|bmp)$/.test(name)) return 'image'
  if (type.startsWith('audio/') || /\.(wav|mp3|m4a|ogg|webm|flac)$/.test(name)) return 'voice'
  if (/\.(docx?|pptx|xlsx|rtf)$/.test(name)) return 'document'
  if (/\.zip$/.test(name) || type.includes('zip')) return 'archive'
  return 'text'
}

async function localJob(path, body, { onWait, signal } = {}) {
  const started = await post('/jobs', { path, method: 'POST', body })
  const id = started.job_id
  for (let i = 0; ; i++) {
    if (signal?.aborted) throw new Error('cancelled')
    await new Promise(r => setTimeout(r, i < 10 ? 300 : 900))
    const job = await req(`/jobs/${id}`)
    if (job.status === 'running') { onWait?.(job.elapsed); continue }
    if (job.status === 'unknown') throw new Error(job.error || 'the job expired')
    if (job.status === 'error') throw new Error(job.error || 'the request failed')
    if (job.http_status >= 400) {
      const detail = job.result?.error ?? job.result?.detail
      throw new Error(typeof detail === 'string' ? detail : `HTTP ${job.http_status}`)
    }
    return job.result
  }
}

export const HTTP_FALLBACK = {
  agent_build: '/agent-build',
  agent_update: '/agent-update',
  agent_resume: '/resume',
  feature: '/feature',
  element_edit: '/element-edit',
}
