
import { create } from 'zustand'

const LS = typeof window === 'undefined' ? null : window.localStorage
const read = (k, fallback) => {
  try { return LS?.getItem(k) ?? fallback } catch { return fallback }
}
const readJSON = (k, fallback) => {
  try { return JSON.parse(LS?.getItem(k) || '') ?? fallback } catch { return fallback }
}


const DEFAULTS = {
  theme: 'dark',

  models: { refine: 'llama3.1:8b', build: 'qwen2.5-coder:14b', agent: '', qa: '',
            srs: '', deploy: '' },
  agentMode: true,
  think: false,
  images: false,
  hist: [],
}


export const KEYS = {
  theme: 'agentforge-theme', hist: 'agentforge-hist',
  refine: 'agentforge-rm', build: 'agentforge-bm', agent: 'agentforge-am', qa: 'agentforge-qm',
  srs: 'agentforge-sm', deploy: 'agentforge-dm',

  srsId: 'agentforge-srs-id', srsPhase: 'agentforge-srs-phase',
  agentMode: 'agentforge-agent', think: 'agentforge-think', images: 'agentforge-img',
}


export const RESUMABLE_SRS_PHASES = new Set(['interview', 'plan', 'review'])


function adoptOldKeys() {
  try {
    for (const next of Object.values(KEYS)) {
      const previous = next.replace(/^agentforge-/, 'locode-')
      if (previous === next || LS.getItem(next) !== null) continue
      const value = LS.getItem(previous)
      if (value !== null) LS.setItem(next, value)
    }
  } catch {  }
}

export const useStore = create((set, get) => ({

  status: 'connecting',
  statusText: 'connecting…',
  setStatus: (status, statusText) => set({ status, statusText }),

  busy: false,
  setBusy: (busy) => set({ busy }),

  // Which page of the generated app the preview is showing. The ask box needs
  // it — "this page is blank" and "the booking button does nothing" both mean
  // nothing without knowing which page — and the router and the reproduction
  // both take it. It lives here rather than in PreviewPane's own state because
  // the box that needs it is in the header, two components away.
  previewRoute: '/',
  setPreviewRoute: (previewRoute) => set({ previewRoute }),
  project: null,
  view: 'preview',
  setView: (view) => set({ view }),

  srsId: null,

  srsPhase: 'idle',
  srsBusy: '',

  setSrs: (patch) => {
    set(patch)
    try {
      const s = get()
      if (s.srsId) {
        LS?.setItem(KEYS.srsId, s.srsId)
        LS?.setItem(KEYS.srsPhase, s.srsPhase || 'idle')
      }
    } catch { }
  },
  resetSrs: () => {
    set({ srsId: null, srsPhase: 'idle', srsBusy: '' })
    try {
      LS?.removeItem(KEYS.srsId)
      LS?.removeItem(KEYS.srsPhase)
    } catch { }
  },

  logs: [],
  addLog: (level, text) => set(s => ({
    logs: [...s.logs.slice(-800), { level, text, at: Date.now() }],
  })),

  steps: {},
  setStep: (id, status) => set(s => ({ steps: { ...s.steps, [id]: status } })),
  progress: { step: '', pct: 0 },
  setProgress: (step, pct) => set({ progress: { step, pct } }),
  phases: [],
  upsertPhase: (p) => set(s => {
    const i = s.phases.findIndex(x => x.phase === p.phase)
    if (i < 0) return { phases: [...s.phases, p] }
    const next = s.phases.slice()
    next[i] = { ...next[i], ...p }
    return { phases: next }
  }),

  files: {},
  activeFile: null,
  liveFile: null,
  liveBuf: '',

  // While a file is being written the code pane follows the writer — that is
  // the point of watching a build. Picking a file from the list is the reader
  // saying "show me this one instead", so it stops following until the next
  // file starts. Without it the pane belonged to whichever stream was open,
  // and a stream that never closed (an agent that announced a write and then
  // refused it) made every click do nothing for the rest of the session.
  follow: true,
  putFile: (name, content) => set(s => ({ files: { ...s.files, [name]: content } })),
  setFiles: (files) => set({ files }),
  setActiveFile: (activeFile) => set({ activeFile, follow: false }),

  ...DEFAULTS,

  hydrate: () => {
    if (!LS) return
    adoptOldKeys()
    const theme = read(KEYS.theme, DEFAULTS.theme)

    try { document.documentElement.setAttribute('data-theme', theme) } catch { }
    set({
      theme,
      models: {
        refine: read(KEYS.refine, DEFAULTS.models.refine),
        build: read(KEYS.build, DEFAULTS.models.build),
        agent: read(KEYS.agent, DEFAULTS.models.agent),
        qa: read(KEYS.qa, DEFAULTS.models.qa),
        srs: read(KEYS.srs, DEFAULTS.models.srs),
        deploy: read(KEYS.deploy, DEFAULTS.models.deploy),
      },
      agentMode: read(KEYS.agentMode, '1') === '1',
      think: read(KEYS.think, '0') === '1',
      images: read(KEYS.images, '0') === '1',
      hist: readJSON(KEYS.hist, []),
    })

    const srsId = read(KEYS.srsId, '')
    const srsPhase = read(KEYS.srsPhase, 'idle')
    if (srsId && RESUMABLE_SRS_PHASES.has(srsPhase)) {
      set({ srsId, srsPhase })
    }
  },

  setTheme: (theme) => {
    set({ theme })
    try {
      document.documentElement.setAttribute('data-theme', theme)
      LS?.setItem(KEYS.theme, theme)
    } catch { }
  },
  persist: (key, value) => { try { LS?.setItem(key, value) } catch { } },

  // Everything here is about ONE project, so opening another one has to clear
  // all of it. `qaReport` and `undo` were left behind: the testing tab showed
  // the previous project's report until its own arrived, and the undo button
  // stayed live pointing at a snapshot id taken in a different project — which
  // `api.undo(project, id)` would have posted against the new one.
  reset: (project) => set({
    project, logs: [], steps: {}, phases: [], files: {},
    activeFile: null, liveFile: null, liveBuf: '', follow: true,
    progress: { step: '', pct: 0 },
    tests: emptyTests(),
    question: null,
    qaReport: null,
    undo: null,
    previewRoute: '/',
  }),

  tests: emptyTests(),
  testStart: () => set({ tests: { ...emptyTests(), running: true } }),
  testRun: (attempt) => set(s => ({ tests: { ...s.tests, attempt, running: true } })),

  stage: '',
  setStage: (stage) => set({ stage }),
  testResult: (m) => set(s => {
    const rows = [...s.tests.rows, {
      status: m.status || 'run', msg: m.msg || '', detail: m.detail || '',
      stage: s.stage, at: Date.now(),
    }]

    const pass = rows.filter(r => r.status === 'pass').length
    const fail = rows.filter(r => r.status === 'fail').length
    const warn = rows.filter(r => r.status === 'warn').length
    return { tests: { ...s.tests, rows, pass, fail, warn } }
  }),
  testFixing: (m) => set(s => ({
    tests: {
      ...s.tests,
      fixing: [...s.tests.fixing,
               { attempt: m.attempt, errors: m.errors || [], at: Date.now() }],
    },
  })),
  testDone: () => set(s => ({ tests: { ...s.tests, running: false } })),

  qaReport: null,
  setQaReport: (qaReport) => set({ qaReport }),

  undo: null,
  setUndo: (undo) => set({ undo }),

  // A question the run stopped on, waiting for an answer. Null the rest of the
  // time. `ws.answerQuestion` is what clears it.
  question: null,
}))

function emptyTests() {
  return { running: false, attempt: 0, rows: [], fixing: [],
           pass: 0, fail: 0, warn: 0 }
}
