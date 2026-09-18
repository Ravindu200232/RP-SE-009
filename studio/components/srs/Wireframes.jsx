'use client'

/**
 * The wireframes, and the journeys that run through them.
 *
 * A wireframe here is an HTML page: black and white, drawn from the
 * specification's own handoff documents, with real sample data in it. It is
 * edited in place - pick a part, move it, copy it, retype it - because the
 * page is served from this origin and its document is therefore reachable.
 *
 * There used to be a second representation: blocks on a 0-100 grid, projected
 * from the specification and then redrawn by a model. It is gone. It could not
 * say what a row looked like, so every table came out as grey bars, and the
 * model pass that was meant to fix that failed a page at a time on a JSON
 * contract the endpoint would not enforce. The page itself has no such
 * contract to miss.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button, Empty, Modal } from '../ui'

/** The `prj_…` id the drawings live under, whichever way the owner is named. */
function useSrsId(owner) {
  const [srsId, setSrsId] = useState(() => (/^prj_/.test(owner || '') ? owner : ''))
  useEffect(() => {
    if (!owner) return
    if (/^prj_/.test(owner)) { setSrsId(owner); return }
    // A built project owns its pages by name; `link.json` is the only thing
    // that knows both names, and the studio reads it through `srs-results`.
    let live = true
    api.srsResults(owner)
      .then(found => { if (live) setSrsId(found?.link?.srs_id || '') })
      .catch(() => {})
    return () => { live = false }
  }, [owner])
  return srsId
}

/** One page, rendered small and not interactive. */
function Thumbnail({ srsId, page }) {
  if (!srsId || !page.has_html) {
    return (
      <span className="flex h-full items-center justify-center text-[11px] text-muted2">
        not drawn yet
      </span>
    )
  }
  return (
    <iframe
      title={page.page_name || page.route}
      src={api.wireframeHtmlUrl(srsId, page.route)}
      loading="lazy"
      tabIndex={-1}
      aria-hidden="true"
      // Rendered at full width and scaled down, so the thumbnail is the page
      // as it really is rather than a second drawing that can disagree with it.
      className="pointer-events-none origin-top-left border-0"
      style={{ width: '1280px', height: '1000px', transform: 'scale(0.23)' }}
    />
  )
}

/* One page, full size, with the tools that edit it.
 *
 * The page is served from the studio's own origin, so the frame's document is
 * reachable from here: pick a part, move it among its neighbours, copy it,
 * take it out, retype it. No model is asked anything, and nothing touches
 * colour, which a wireframe does not have. */
export function WireframeEditor({ owner, page, onClose, onSaved, srsId: given = '' }) {
  const resolved = useSrsId(owner)
  const srsId = given || resolved

  const [drawing, setDrawing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [problem, setProblem] = useState('')
  const [stamp, setStamp] = useState(page.has_html ? 1 : 0)
  const [stale, setStale] = useState(Boolean(page.html_stale))
  const [picked, setPicked] = useState('')
  const [dirty, setDirty] = useState(false)
  const [typing, setTyping] = useState(false)
  const frame = useRef(null)
  const editor = useRef(null)

  // `has_html` is a snapshot taken when the grid was listed, so a page drawn
  // since opens saying "nothing drawn yet" over a page that exists. The server
  // is the authority, and asking it costs one request.
  useEffect(() => {
    if (!srsId) return
    let live = true
    fetch(api.wireframeHtmlUrl(srsId, page.route))
      .then(r => { if (live && r.ok) setStamp(n => n || 1) })
      .catch(() => {})
    return () => { live = false }
  }, [srsId, page.route])

  const [parts, setParts] = useState([])

  const attach = useCallback(() => {
    editor.current?.detach?.()
    import('@/lib/wireframe-html-editor').then(({ attachEditor, PARTS }) => {
      editor.current = attachEditor(frame.current, { onSelect: setPicked, onDirty: setDirty })
      setParts(PARTS)
      if (!editor.current) setProblem('This page cannot be edited in place here.')
    })
  }, [])

  useEffect(() => () => editor.current?.detach?.(), [])

  async function draw() {
    setDrawing(true); setProblem('')
    try {
      await api.drawWireframeHtml(srsId, page.route)
      setStamp(n => n + 1)
      setStale(false); setDirty(false); setPicked(''); setTyping(false)
    } catch (failure) {
      setProblem(failure?.message || 'The page could not be drawn.')
    } finally {
      setDrawing(false)
    }
  }

  async function save() {
    if (!editor.current) return
    setSaving(true); setProblem('')
    try {
      if (typing) { editor.current.editText(false); setTyping(false) }
      await api.saveWireframeHtml(srsId, page.route, editor.current.serialize())
      editor.current.saved()
      onSaved?.(null)
    } catch (failure) {
      setProblem(failure?.message || 'That layout could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  const act = (name, ...args) => () => {
    editor.current?.[name]?.(...args)
    if (name === 'undo') { setStamp(n => n + 1); setDirty(false); setPicked('') }
  }

  const Tool = ({ onClick, children, on = false, always = false }) => (
    <button type="button" onClick={onClick} disabled={!picked && !always}
      className={cn('rounded-md px-2 py-1 text-[11px] font-medium transition',
        'disabled:opacity-30 disabled:cursor-not-allowed',
        on ? 'bg-blue-600 text-white'
           : 'bg-white/[.06] text-white/75 hover:bg-white/[.12] hover:text-white')}>
      {children}
    </button>
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-[#121622]/90 shadow-2xl backdrop-blur-xl">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-white/10 bg-black/30 px-5 py-3 backdrop-blur-md">
        <div className="flex min-w-0 items-center gap-3">
          <Button variant="outline" size="sm" onClick={onClose}
            className="h-8 rounded-xl border-white/10 bg-white/[.05] text-white/80 text-[11.5px]">
            ← Wireframes
          </Button>
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-semibold text-white">
              {page.page_name || page.route}
            </span>
            <span className="block truncate font-mono text-[10.5px] text-white/50">
              {page.route}{page.roles?.length ? ` · ${page.roles.join(', ')}` : ''}
            </span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          {dirty && (
            <Button variant="solid" size="sm" onClick={save} disabled={saving}
              className="h-8 rounded-xl bg-blue-600 hover:bg-blue-500 text-[11.5px] text-white">
              {saving ? <><Loader2 className="mr-1 size-3 animate-spin" /> Saving…</> : 'Save page'}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={draw} disabled={drawing || !srsId}
            className="h-8 rounded-xl border-white/10 bg-white/[.05] text-white/80 text-[11.5px]">
            {drawing ? <><Loader2 className="mr-1 size-3 animate-spin" /> Drawing…</>
                     : stamp ? 'Draw again' : 'Draw this page'}
          </Button>
        </div>
      </div>

      {stamp ? (
        <div className="flex shrink-0 flex-wrap items-center gap-1.5 border-b border-white/10 bg-white/[.03] px-4 py-2">
          <span className="mr-1 font-mono text-[10px] text-white/40">
            {picked ? `<${picked}>` : 'click a part of the page'}
          </span>
          <Tool onClick={act('parent')}>Parent</Tool>
          <Tool onClick={act('move', -1)}>↑ Up</Tool>
          <Tool onClick={act('move', 1)}>↓ Down</Tool>
          <span className="mx-1 h-4 w-px bg-white/10" />
          <Tool onClick={act('align', 'left')}>Left</Tool>
          <Tool onClick={act('align', 'center')}>Centre</Tool>
          <Tool onClick={act('align', 'right')}>Right</Tool>
          <Tool onClick={act('align', 'full')}>Full width</Tool>
          <Tool onClick={act('wider', -10)}>Narrower</Tool>
          <Tool onClick={act('wider', 10)}>Wider</Tool>
          <span className="mx-1 h-4 w-px bg-white/10" />
          <Tool onClick={act('duplicate')}>Duplicate</Tool>
          <Tool onClick={act('remove')}>Remove</Tool>
          <Tool on={typing} onClick={() => { editor.current?.editText(!typing); setTyping(!typing) }}>
            {typing ? 'Done typing' : 'Edit text'}
          </Tool>
          <span className="flex-1" />
          <Tool always onClick={act('undo')}>Undo</Tool>
        </div>
      ) : null}

      {stale && stamp ? (
        <p className="shrink-0 border-b border-amber-400/20 bg-amber-400/10 px-4 py-2 text-[11.5px] text-amber-200">
          The specification has changed since this page was drawn — draw it again to bring it up to date.
        </p>
      ) : null}
      {problem ? (
        <p role="alert" className="shrink-0 border-b border-rose-400/20 bg-rose-500/10 px-4 py-2 text-[11.5px] text-rose-300">
          {problem}
        </p>
      ) : null}

      {stamp ? (
        <div className="flex min-h-0 flex-1">
          {/* The catalogue. A part is inserted after whatever is picked, so
              building a page is: pick the thing it goes under, then add it. */}
          <aside className="w-[188px] shrink-0 overflow-y-auto border-r border-white/10 bg-[#0d111a] p-3">
            <p className="mb-2 font-display text-[10.5px] font-bold uppercase tracking-wider text-white/70">
              Add components
            </p>
            <p className="mb-3 text-[10px] leading-snug text-white/35">
              {picked ? 'Goes in after the part you picked.' : 'Goes at the end of the page.'}
            </p>
            {parts.map(([group, items]) => (
              <div key={group} className="mb-3">
                <p className="mb-1.5 text-[9.5px] font-semibold uppercase tracking-wider text-white/35">
                  {group}
                </p>
                <div className="grid grid-cols-2 gap-1">
                  {items.map(([kind, label]) => (
                    <button key={kind} type="button" onClick={act('insert', kind)}
                      className="rounded-md bg-white/[.05] px-2 py-1.5 text-left text-[10.5px]
                                 text-white/70 transition hover:bg-white/[.12] hover:text-white">
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </aside>
          <iframe
            key={stamp}
            ref={frame}
            onLoad={attach}
            title={`${page.page_name || page.route} wireframe`}
            src={srsId ? api.wireframeHtmlUrl(srsId, page.route) : 'about:blank'}
            className="min-h-0 min-w-0 flex-1 border-0 bg-white"
          />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 items-center justify-center bg-[#0a0d14] text-[12px] text-muted">
          {srsId ? `Nothing drawn for ${page.route} yet.`
                 : 'This project has no specification to draw from.'}
        </div>
      )}
    </div>
  )
}

/** The modal the workspace opens a page in. */
function PageEditor({ owner, page, onClose, onSaved, srsId = '' }) {
  return (
    <Modal
      onClose={onClose}
      overlayClassName="!p-0 backdrop-blur-none"
      style={{ maxWidth: 'none', width: '100%', height: '100%', maxHeight: '100%' }}
      className="overflow-hidden rounded-none border-0 p-0"
    >
      <div className="flex h-full min-h-0 gap-4 bg-[#0a0d14] p-5">
        <WireframeEditor owner={owner} srsId={srsId} page={page}
          onClose={onClose} onSaved={onSaved} />
      </div>
    </Modal>
  )
}

export function Wireframes({ srs, onEditPage }) {
  const owner = srs?.project || srs?.srs_id || srs?.id || ''
  const srsId = useSrsId(owner)
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)
  const [error, setError] = useState('')
  const [drawing, setDrawing] = useState(false)

  const load = useCallback(() => {
    if (!owner) return
    api.wireframes(owner)
      .then(setData)
      .catch(failure => setError(failure?.message || 'The wireframes could not be read.'))
  }, [owner])

  useEffect(() => { load() }, [load])

  /** Draw every page that has no drawing yet, and redraw the rest. */
  async function drawAll() {
    if (!srsId) return
    setDrawing(true); setError('')
    try {
      await api.drawWireframeHtml(srsId)
      load()
    } catch (failure) {
      setError(failure?.message || 'The pages could not be drawn.')
    } finally {
      setDrawing(false)
    }
  }

  const pages = data?.pages || []
  if (error) return <Empty>{error}</Empty>
  if (!data) return <Empty>Reading the wireframes…</Empty>
  if (!pages.length) return <Empty>No pages in the specification yet, so there is nothing to draw.</Empty>

  const drawn = pages.filter(p => p.has_html).length

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-[11.5px] text-muted">
          {pages.length} page{pages.length === 1 ? '' : 's'}, black and white, with sample data.
          Open one to move things, retype them, or ask for a change.
          {drawn === pages.length
            ? ' All drawn.'
            : ` ${drawn} of ${pages.length} drawn so far.`}
        </p>
        <Button variant="outline" disabled={drawing || !srsId} onClick={drawAll}>
          {drawing ? <><Loader2 className="mr-1 size-3 animate-spin" /> Drawing…</>
                   : drawn ? 'Draw them again' : 'Draw every page'}
        </Button>
      </div>
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
        {pages.map(page => (
          <button key={page.route} type="button"
            onClick={() => (onEditPage ? onEditPage(page) : setOpen(page))}
            className="group overflow-hidden rounded-xl border border-line text-left transition hover:border-accent cursor-pointer">
            <span className="block aspect-[16/11] overflow-hidden border-b border-line bg-white">
              <Thumbnail srsId={srsId} page={page} />
            </span>
            <span className="block space-y-1 p-3">
              <span className="truncate block text-[12px] font-medium text-ink">{page.page_name}</span>
              <span className="block truncate font-mono text-[10px] text-muted2">{page.route}</span>
              <span className="block truncate text-[10px] text-muted2">
                {page.roles?.length ? page.roles.join(', ') : 'public'}
                {page.html_stale ? ' · out of date' : ''}
              </span>
            </span>
          </button>
        ))}
      </div>
      {open && (
        <PageEditor owner={owner} srsId={srsId} page={open}
          onClose={() => setOpen(null)}
          onSaved={() => { load(); setOpen(null) }} />
      )}
    </div>
  )
}

export function UserJourney({ srs }) {
  const owner = srs?.project || srs?.srs_id || srs?.id || ''
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!owner) return
    api.wireframes(owner).then(setData).catch(() => setData({ journeys: [] }))
  }, [owner])

  const journeys = data?.journeys || []
  const routes = useMemo(
    () => new Map((data?.pages || []).map(p => [p.route, p.page_name])), [data])

  if (!data) return <Empty>Reading the journeys…</Empty>
  if (!journeys.length) return <Empty>No workflows in the specification yet.</Empty>

  return (
    <div className="space-y-4">
      <p className="text-[11.5px] text-muted">
        {journeys.length} journey{journeys.length === 1 ? '' : 's'} through the product, each step
        on the screen it happens on. A step marked <span className="text-muted2">carried</span> did
        not name a screen itself — it continues on the one before it.
      </p>
      {journeys.map(flow => (
        <div key={flow.workflow_name} className="rounded-xl border border-line bg-panel p-4">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <h3 className="text-[13px] font-semibold text-ink">{flow.workflow_name}</h3>
            {flow.who && <span className="text-[11px] text-muted2">{flow.who}</span>}
          </div>
          <ol className="mt-3 space-y-0">
            {flow.steps.map((step, i) => (
              <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
                <span className="relative flex flex-col items-center">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded-full
                                   border border-line bg-panel2 font-mono text-[10px] text-muted">
                    {i + 1}
                  </span>
                  {i < flow.steps.length - 1 && (
                    <span className="mt-1 w-px flex-1 bg-line" />
                  )}
                </span>
                <span className="min-w-0 flex-1 pb-1">
                  <span className="block text-[11.5px] text-ink">{step.step}</span>
                  {step.route && (
                    <span className="mt-0.5 flex flex-wrap items-baseline gap-2">
                      <code className="font-mono text-[10px] text-accent">{step.route}</code>
                      <span className="text-[10px] text-muted2">
                        {routes.get(step.route) || ''}{step.named === false ? ' · carried' : ''}
                      </span>
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  )
}
