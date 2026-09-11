
import { create } from 'zustand'
import { advance, emptyProgress } from './progress-model'

const LS = typeof window === 'undefined' ? null : window.localStorage
const read = (k, fallback) => {
  try { return LS?.getItem(k) ?? fallback } catch { return fallback }
}
const readJSON = (k, fallback) => {
  try { return JSON.parse(LS?.getItem(k) || '') ?? fallback } catch { return fallback }
}


const DEFAULTS = {
// Use the light theme until the browser saves another choice.
  theme: 'light',

  models: { planner: '', design: '', builder: '', agent: '', qa: '',
            srs: '', deploy: '', image: 'fooocus' },
  think: false,
  // Whether the run in flight is actually reasoning, as reported by the
  // engine - not the same thing as the `think` switch, which is only a request.
  reasoning: false,
  images: false,
  hist: [],
}


export const KEYS = {
  theme: 'agentforge-theme', hist: 'agentforge-hist',
  agent: 'agentforge-am',
  planner: 'agentforge-pm', design: 'agentforge-design-m',
  builder: 'agentforge-builder-m', qa: 'agentforge-qm',
  srs: 'agentforge-sm', deploy: 'agentforge-dm', image: 'agentforge-im',

  srsId: 'agentforge-srs-id', srsPhase: 'agentforge-srs-phase',
  think: 'agentforge-think', images: 'agentforge-img',
}


const RESUMABLE_SRS_PHASES = new Set(['interview', 'plan', 'review'])




export const useStore = create((set, get) => ({

  status: 'connecting',
  statusText: 'connecting…',
  setStatus: (status, statusText) => set({ status, statusText }),

  busy: false,
  // Preview startup is independent of an agent build in another project.
  opening: false,
  runtimes: {},
  setRuntime: (runtime) => set(state => {
    if (!runtime?.project) return {}
    const previous = state.runtimes[runtime.project]
    if (previous?.serverId === runtime.serverId && previous.revision > runtime.revision) return {}
    return { runtimes: { ...state.runtimes, [runtime.project]: runtime },
      ...(state.project === runtime.project ? { opening: runtime.status === 'starting' } : {}) }
  }),

  // Increment when projects on disk change.
  projectsStamp: 0,

  // Which kind of work is running.
  workKind: '',
  setWorkKind: (workKind) => set({ workKind }),
  setOpening: (opening) => set({ opening }),
  askOpen: false,
  setAskOpen: (askOpen) => set({ askOpen }),
  setBusy: (busy) => set(busy ? { busy } : { busy, opening: false }),
  bumpProjects: () => set(s => ({ projectsStamp: s.projectsStamp + 1 })),

  // Which page of the generated app the preview is showing.
  previewRoute: '/',
  setPreviewRoute: (previewRoute) => set({ previewRoute }),

  e2eLive: null,
  setE2eLive: (e2eLive) => set({ e2eLive }),
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

  // What the console shows about the run itself: the model, how much of its
  // context window is in use, and how much work it has done.
  runStats: null,
  setRunStats: (runStats) => set({ runStats }),

  // Composing the next move, or carrying one out. The gap between the two is
  // where a feed looks stalled, so it is shown rather than left blank.
  agentState: '',
  setAgentState: (agentState) => set({ agentState }),

  // The one question a run is waiting on, if any. It carries its own deadline
  // and clears itself, so a closed dialog costs a choice and not a build.
  approval: null,
  setApproval: (approval) => set({ approval }),

  // The drawing waiting to be approved.
  //
  // Kept apart from `approval` because it is not answered in a dialog: it is
  // shown in the preview, where the select and pencil tools already work, and
  // walked by clicking its own navigation. A popup over the top of it would
  // hide the thing being judged.
  drawing: null,
  setDrawing: (drawing) => set({ drawing }),

  // The engine's own browser, as it is right now. Headless, so this is the
  // only way to see what it is doing.
  browserFrame: null,
  setBrowserFrame: (browserFrame) => set({ browserFrame }),

  // What the user has pointed at for the message they are still writing:
  // elements they clicked, regions they drew on. Each one carries its own
  // screenshot, so the attachment is a picture and not just a selector.
  selection: [],
  addSelection: (item) => set(s => (
    s.selection.some(x => x.key === item.key)
      ? s
      : { selection: [...s.selection, item].slice(-8) })),
  patchSelection: (key, patch) => set(s => ({
    selection: s.selection.map(x => (x.key === key ? { ...x, ...patch } : x)),
  })),
  removeSelection: (key) => set(s => ({
    selection: s.selection.filter(x => x.key !== key),
  })),
  clearSelection: () => set({ selection: [] }),

  // What the agent and the user actually said to each other, as opposed to the
  // tool activity the chat panel derives from `logs`.
  chat: [],
  pushChat: (entry) => set(s => ({
    chat: [...s.chat.slice(-200), { at: Date.now(), ...entry }],
  })),

  // What was said while the agent was still working.
  //
  // The box used to lock itself for the length of a run and tell you to come
  // back later, which is the one moment you most want to say something - the
  // next thing to do usually occurs to you while you are watching the last
  // thing happen. Only one run may touch a project at a time, so what is typed
  // waits here and goes the moment the run ends, in the order it was typed.
  queue: [],
  enqueue: (entry) => set(s => ({
    queue: [...s.queue, { id: `q-${Date.now()}-${s.queue.length}`, at: Date.now(), ...entry }],
  })),
  dropQueued: (id) => set(s => ({ queue: s.queue.filter(item => item.id !== id) })),
  takeQueued: (project) => {
    const next = get().queue.find(item => item.project === project)
    if (next) set(s => ({ queue: s.queue.filter(item => item.id !== next.id) }))
    return next || null
  },

  steps: {},
  setStep: (id, status) => set(s => ({ steps: { ...s.steps, [id]: status } })),
  progress: emptyProgress(),
  setProgress: (step, pct) =>
    set(s => ({ progress: advance(s.progress, step, pct) })),
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

  // While a file is being written the code pane follows the writer.
  follow: true,
  putFile: (name, content) => set(s => ({ files: { ...s.files, [name]: content } })),
  setFiles: (files) => set({ files }),
  setActiveFile: (activeFile) => set({ activeFile, follow: false }),

  ...DEFAULTS,

  hydrate: () => {
    if (!LS) return
    const theme = read(KEYS.theme, DEFAULTS.theme)
    // Migrate the former single Agent choice into each explicit role. Once a
    // role is picked it has its own key and no longer follows the legacy one.
    const legacyAgent = read(KEYS.agent, DEFAULTS.models.agent)

    try { document.documentElement.setAttribute('data-theme', theme) } catch { }
    set({
      theme,
      models: {
        planner: read(KEYS.planner, legacyAgent),
        design: read(KEYS.design, legacyAgent),
        builder: read(KEYS.builder, legacyAgent),
        agent: legacyAgent,
        qa: read(KEYS.qa, DEFAULTS.models.qa),
        srs: read(KEYS.srs, DEFAULTS.models.srs),
        deploy: read(KEYS.deploy, DEFAULTS.models.deploy),
        image: read(KEYS.image, DEFAULTS.models.image),
      },
      // Fresh installs start with thinking off. A user must opt in with the
      // shared Builder + QA Think button before either role receives it.
      think: read(KEYS.think, DEFAULTS.think ? '1' : '0') === '1',
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

  /**
   * Every project's own stream, kept while you are looking at another one.
   *
   * Switching projects used to empty the feed: the work carried on, and the
   * account of it was gone. What one project has said belongs to that project,
   * so it is set aside on the way out and handed back on the way in.
   */
  streams: {},

  // The project a run belongs to, which is not always the one on screen: you
  // can start a build and go and look at something else while it works.
  busyProject: '',
  setBusyProject: (busyProject) => set({ busyProject }),

  /**
   * Put a project's saved stream back, behind anything that has arrived since.
   *
   * The fetch that reads it races the socket that is already reporting: a run
   * started the moment the project opened would otherwise have its first lines
   * overwritten by a record written before they happened.
   */
  adoptStream: (stream) => set(state => ({
    logs: [...(stream.logs || []), ...state.logs],
    chat: [...(stream.chat || []), ...state.chat],
  })),

      // Set this project's stream aside, and take up the next one's. What is
      // set aside is also written down, because a tab that is closed next
      // takes the in-memory copy with it.
  reset: (project) => set(state => {
    if (state.project && (state.logs.length || state.chat.length)) {
      import('./api').then(({ api }) =>
        api.saveStream(state.project, state.logs, state.chat).catch(() => { }))
    }
    return {
    streams: state.project
      ? { ...state.streams,
          [state.project]: { logs: state.logs, chat: state.chat,
                             runStats: state.runStats } }
      : state.streams,
    ...restored(state.streams[project]),
    project, agentState: '', approval: null, drawing: null,
    browserFrame: null, selection: [],
    steps: {}, phases: [], files: {},
    activeFile: null, liveFile: null, liveBuf: '', follow: true,
    progress: emptyProgress(),
    tests: emptyTests(),
    question: null,
    qaReport: null,
    undo: null,
    previewRoute: '/',
    e2eLive: null,
    e2eParallel: emptyE2eParallel(),
    }
  }),

  tests: emptyTests(),
  testStart: () => set({
    tests: { ...emptyTests(), running: true, startedAt: Date.now() },
    e2eParallel: emptyE2eParallel(),
  }),
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
  testDone: () => set(s => ({
    tests: { ...s.tests, running: false },
    e2eParallel: { ...s.e2eParallel, active: false },
  })),

  e2eParallel: emptyE2eParallel(),
  e2eParallelEvent: (m) => set(s => {
    const current = s.e2eParallel || emptyE2eParallel()
    if (m.state === 'start') {
      return { e2eParallel: {
        ...emptyE2eParallel(), active: true,
        workers: Math.max(1, Math.min(4, Number(m.workers) || 1)),
        waves: Number(m.waves) || 0,
      } }
    }
    if (m.state === 'wave') {
      return { e2eParallel: {
        ...current, active: true, wave: Number(m.wave) || 0,
        waves: Number(m.waves) || current.waves,
        lanes: emptyE2eLanes(),
      } }
    }
    if (m.state === 'done') {
      return { e2eParallel: { ...current, active: false } }
    }
    return { e2eParallel: current }
  }),
  e2eEvent: (m) => set(s => {
    const current = s.e2eParallel || emptyE2eParallel()
    const laneNo = Math.max(1, Math.min(4, Number(m.lane) || 1))
    const lanes = [...(current.lanes || emptyE2eLanes())]
    const old = lanes[laneNo - 1] || emptyE2eLane(laneNo)
    const state = String(m.state || '')
    lanes[laneNo - 1] = {
      ...old,
      lane: laneNo,
      state,
      title: m.title ?? old.title,
      role: m.role ?? old.role,
      route: m.route ?? old.route,
      label: m.label ?? old.label,
      message: m.message ?? (state === 'journey_start' ? '' : old.message),
      index: Number.isFinite(Number(m.index)) ? Number(m.index) : old.index,
      total: Number.isFinite(Number(m.total)) ? Number(m.total) : old.total,
      ok: m.ok ?? old.ok,
      updatedAt: Date.now(),
    }
    return { e2eParallel: {
      ...current,
      active: current.active || state !== 'journey_done',
      workers: Math.max(current.workers || 0, laneNo),
      lanes,
    } }
  }),

  qaReport: null,
  setQaReport: (qaReport) => set({ qaReport }),

  undo: null,
  setUndo: (undo) => set({ undo }),

  // A question the run stopped on, waiting for an answer.
  question: null,
}))

/** A project's saved stream, or a clean one for a project with no history. */
function restored(stream) {
  return { logs: stream?.logs || [], chat: stream?.chat || [],
           runStats: stream?.runStats || null }
}


function emptyTests() {
  return { running: false, attempt: 0, rows: [], fixing: [],
           pass: 0, fail: 0, warn: 0, startedAt: 0 }
}

function emptyE2eLane(lane) {
  return {
    lane, state: 'idle', title: '', role: '', route: '', label: '',
    message: '', index: 0, total: 0, ok: null, updatedAt: 0,
  }
}

function emptyE2eLanes() {
  return [1, 2, 3, 4].map(emptyE2eLane)
}

function emptyE2eParallel() {
  return { active: false, workers: 0, waves: 0, wave: 0, lanes: emptyE2eLanes() }
}

