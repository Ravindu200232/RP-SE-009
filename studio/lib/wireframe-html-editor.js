/**
 * Direct editing of a drawn wireframe page, with no model in the loop.
 *
 * The blocks editor works because a block is a row in a list we own. A drawn
 * page has no such list - it is a document - so the thing to edit is the
 * document itself. The page is served from the studio's own origin, which is
 * what makes this possible at all: the parent can reach into the frame, listen
 * for a click, move a node among its siblings, and read the whole thing back
 * out as text when someone saves.
 *
 * Deliberately structural. Move, duplicate, remove, retype: the operations a
 * reviewer wants on a wireframe. Nothing here changes colour, because a
 * wireframe has none, and nothing here asks a model anything.
 */

const STYLE_ID = '__wf_editor_style'
const MARK = 'data-wf-selected'

const CSS = `
  [${MARK}] { outline: 2px solid #2563eb !important; outline-offset: 1px; }
  [${MARK}]::after {
    content: attr(data-wf-tag);
    position: absolute; z-index: 2147483647;
    transform: translateY(-100%);
    background: #2563eb; color: #fff;
    font: 600 10px/1.6 ui-monospace, Menlo, monospace;
    padding: 0 6px; border-radius: 3px 3px 0 0;
    pointer-events: none; white-space: nowrap;
  }
  .__wf_hover { outline: 1px dashed #93c5fd !important; outline-offset: 1px; }
  [contenteditable="true"] { outline: 2px solid #16a34a !important; }
`

/* The parts a wireframe is made of, as markup rather than as blocks.
 *
 * The same catalogue the block editor had - a nav, a table, a card grid, a
 * stat - written in the plain monochrome the drawn pages already use, so an
 * inserted part sits in the page instead of announcing itself. Tailwind is
 * loaded on every drawn page, which is what lets these be markup and nothing
 * else: no stylesheet to inject and nothing to keep in step.
 */
const CELL = 'border border-black px-3 py-2 text-left'
const BOX = 'border-2 border-black'
const IMG = `${BOX} flex items-center justify-center bg-[#F3F4F6] text-[11px]`

export const PARTS = [
  ['Navigation & layout', [
    ['nav', 'Nav', `<nav class="${BOX} flex items-center justify-between px-6 py-4 mb-4">
      <span class="font-bold">Product</span>
      <span class="flex gap-6 text-sm"><span>Overview</span><span>Records</span><span>Settings</span></span>
    </nav>`],
    ['footer', 'Footer', `<footer class="${BOX} grid grid-cols-3 gap-6 px-6 py-6 mt-4 text-sm">
      <div><div class="font-bold mb-2">Product</div><div>About</div><div>Contact</div></div>
      <div><div class="font-bold mb-2">Help</div><div>Guides</div><div>Support</div></div>
      <div><div class="font-bold mb-2">Legal</div><div>Terms</div><div>Privacy</div></div>
    </footer>`],
    ['panel', 'Panel', `<section class="${BOX} p-5 mb-4">
      <h3 class="font-bold mb-3">Panel title</h3>
      <p class="text-sm">What this grouping is for.</p>
    </section>`],
    ['tabs', 'Tabs', `<div class="flex gap-2 mb-4">
      <span class="${BOX} px-4 py-2 text-sm font-bold bg-black text-white">All</span>
      <span class="${BOX} px-4 py-2 text-sm">Open</span>
      <span class="${BOX} px-4 py-2 text-sm">Closed</span>
    </div>`],
    ['divider', 'Divider', '<hr class="border-t-2 border-black my-6" />'],
  ]],
  ['Typography & media', [
    ['heading', 'Heading', '<h1 class="text-3xl font-bold mb-2">Page heading</h1>'],
    ['title', 'Title', '<h2 class="text-xl font-bold mb-2">Section title</h2>'],
    ['text', 'Text', `<p class="text-sm mb-4 max-w-2xl">Two or three sentences of the copy this
      part of the page carries, written out so the length and the tone are visible.</p>`],
    ['image', 'Image', `<div class="${IMG} mb-4" style="height:220px">[ Image / Banner Placeholder ]</div>`],
    ['icon', 'Icon', `<span class="${BOX} inline-flex items-center justify-center rounded-full"
      style="width:44px;height:44px">ICON</span>`],
  ]],
  ['Inputs & actions', [
    ['field', 'Field', `<label class="block mb-4 max-w-md">
      <span class="block text-xs font-bold uppercase tracking-wide mb-1">Field label</span>
      <input class="${BOX} w-full px-3 py-2 text-sm" value="Typed value" />
    </label>`],
    ['button', 'Button', `<button type="button" class="${BOX} px-5 py-2 text-sm font-bold mr-2 mb-4">Action</button>`],
    ['search', 'Search', `<div class="flex gap-2 mb-4 max-w-xl">
      <input class="${BOX} flex-1 px-3 py-2 text-sm" placeholder="Search…" />
      <button type="button" class="${BOX} px-5 py-2 text-sm font-bold">Search</button>
    </div>`],
  ]],
  ['Data & analytics', [
    ['table', 'Table', `<table class="${BOX} w-full border-collapse text-sm mb-4">
      <thead><tr class="bg-[#F3F4F6]">
        <th class="${CELL}">Name</th><th class="${CELL}">Owner</th><th class="${CELL}">Status</th>
      </tr></thead>
      <tbody>
        <tr><td class="${CELL}">First record</td><td class="${CELL}">A. Rivera</td><td class="${CELL}">Open</td></tr>
        <tr><td class="${CELL}">Second record</td><td class="${CELL}">M. Chen</td><td class="${CELL}">Closed</td></tr>
      </tbody>
    </table>`],
    ['row', 'Table row', `<tr><td class="${CELL}">New record</td><td class="${CELL}">Someone</td><td class="${CELL}">Open</td></tr>`],
    ['cards', 'Cards', `<div class="grid grid-cols-3 gap-4 mb-4">
      ${[1, 2, 3].map(n => `<div class="${BOX} p-4">
        <div class="${IMG} mb-3" style="height:120px">[ Image ]</div>
        <div class="font-bold text-sm">Item ${n}</div>
        <div class="text-xs">A line about it.</div>
      </div>`).join('')}
    </div>`],
    ['list', 'List', `<ul class="${BOX} divide-y divide-black text-sm mb-4">
      <li class="px-4 py-3">First item</li><li class="px-4 py-3">Second item</li>
      <li class="px-4 py-3">Third item</li>
    </ul>`],
    ['stat', 'Stat', `<div class="${BOX} p-4 mb-4 inline-block mr-3">
      <div class="text-xs uppercase tracking-wide">Total</div>
      <div class="text-3xl font-bold">128</div>
    </div>`],
    ['chart', 'Chart', `<div class="${BOX} flex items-end gap-2 p-4 mb-4" style="height:180px">
      ${[45, 70, 35, 85, 60, 75].map(h =>
        `<span class="flex-1 bg-[#E5E7EB] border border-black" style="height:${h}%"></span>`).join('')}
    </div>`],
    ['rating', 'Rating', '<div class="text-xl mb-4">★ ★ ★ ★ ☆</div>'],
  ]],
]

const SNIPPETS = Object.fromEntries(
  PARTS.flatMap(([, items]) => items.map(([kind, , html]) => [kind, html])))

/** Never select the page itself, or the wrappers that hold everything. */
function selectable(node, doc) {
  if (!node || node === doc.documentElement || node === doc.body) return null
  return node
}

function label(node) {
  const tag = node.tagName.toLowerCase()
  const cls = String(node.getAttribute('class') || '').split(/\s+/).filter(Boolean)[0]
  return cls ? `${tag}.${cls}` : tag
}

/**
 * Attach the editor to a loaded, same-origin frame.
 * Returns a handle, or null when the document cannot be reached.
 */
export function attachEditor(iframe, { onSelect, onDirty } = {}) {
  let doc
  try {
    doc = iframe.contentDocument
    if (!doc || !doc.body) return null
  } catch {
    return null                       // cross-origin: nothing to attach to
  }

  let selected = null
  let dirty = false
  // Whole-document snapshots. A wireframe page is tens of kilobytes and an
  // edit is a click apart from the last one, so keeping the text is simpler
  // and more reliable than replaying inverse operations.
  const undoStack = []

  if (!doc.getElementById(STYLE_ID)) {
    const style = doc.createElement('style')
    style.id = STYLE_ID
    style.textContent = CSS
    doc.head.appendChild(style)
  }

  function touched() {
    if (!dirty) { dirty = true; onDirty?.(true) }
  }

  function snapshot() {
    undoStack.push(doc.documentElement.outerHTML)
    if (undoStack.length > 40) undoStack.shift()
  }

  function select(node) {
    if (selected) { selected.removeAttribute(MARK); selected.removeAttribute('data-wf-tag') }
    selected = selectable(node, doc)
    if (selected) {
      selected.setAttribute(MARK, '')
      selected.setAttribute('data-wf-tag', label(selected))
      // The badge is absolutely positioned against the nearest positioned
      // ancestor, so the element has to be one itself or the label drifts to
      // the far corner of the page.
      if (doc.defaultView.getComputedStyle(selected).position === 'static') {
        selected.style.position = 'relative'
      }
    }
    onSelect?.(selected ? label(selected) : '')
  }

  let hovered = null
  const onOver = event => {
    if (hovered) hovered.classList.remove('__wf_hover')
    hovered = selectable(event.target, doc)
    hovered?.classList.add('__wf_hover')
  }
  const onOut = () => { hovered?.classList.remove('__wf_hover'); hovered = null }

  const onClick = event => {
    // A wireframe is full of links and buttons; clicking one should pick it,
    // not follow it.
    if (doc.body.getAttribute('data-wf-editing') === 'text') return
    event.preventDefault()
    event.stopPropagation()
    select(event.target)
  }

  doc.addEventListener('click', onClick, true)
  doc.addEventListener('mouseover', onOver, true)
  doc.addEventListener('mouseout', onOut, true)

  const api = {
    selected: () => selected,
    parent() {
      if (selected?.parentElement) select(selected.parentElement)
    },
    move(delta) {
      if (!selected?.parentElement) return
      const sibling = delta < 0
        ? selected.previousElementSibling
        : selected.nextElementSibling
      if (!sibling) return
      snapshot()
      if (delta < 0) sibling.before(selected)
      else sibling.after(selected)
      selected.scrollIntoView({ block: 'nearest' })
      touched()
    },
    duplicate() {
      if (!selected?.parentElement) return
      snapshot()
      const copy = selected.cloneNode(true)
      copy.removeAttribute(MARK)
      copy.removeAttribute('data-wf-tag')
      selected.after(copy)
      touched()
    },
    remove() {
      if (!selected?.parentElement) return
      snapshot()
      const next = selected.nextElementSibling || selected.parentElement
      selected.remove()
      select(next)
      touched()
    },
    wider(step) {
      if (!selected) return
      snapshot()
      const now = parseFloat(selected.style.width) || 100
      selected.style.width = `${Math.max(10, Math.min(100, now + step))}%`
      touched()
    },
    /** Left, centre or right. There is no grid, so this is what "position" is. */
    align(how) {
      if (!selected) return
      snapshot()
      selected.style.marginLeft = how === 'center' || how === 'right' ? 'auto' : ''
      selected.style.marginRight = how === 'center' || how === 'left' ? 'auto' : ''
      if (how === 'left') selected.style.marginLeft = ''
      if (how === 'right') selected.style.marginRight = ''
      selected.style.textAlign = how === 'center' ? 'center' : ''
      if (how === 'full') {
        selected.style.width = ''
        selected.style.marginLeft = ''
        selected.style.marginRight = ''
        selected.style.display = 'block'
      }
      touched()
    },
    /** Put a new part after the selection, or at the end of the page. */
    insert(kind) {
      const markup = SNIPPETS[kind]
      if (!markup) return
      snapshot()
      // A <tr> is only valid inside a table, so it is built in one; everything
      // else is built in a plain div. Without this the browser drops the row.
      const host = doc.createElement(kind === 'row' ? 'tbody' : 'div')
      if (kind === 'row') {
        const table = doc.createElement('table')
        table.innerHTML = `<tbody>${markup}</tbody>`
        const row = table.querySelector('tr')
        const body = selected?.closest('tbody') || doc.querySelector('tbody')
        if (!body || !row) return
        body.appendChild(row)
        select(row)
        touched()
        return
      }
      host.innerHTML = markup.trim()
      const node = host.firstElementChild
      if (!node) return
      if (selected && selected.parentElement) selected.after(node)
      else (doc.querySelector('main, body > div, body') || doc.body).appendChild(node)
      select(node)
      node.scrollIntoView({ block: 'center' })
      touched()
    },
    editText(on) {
      if (!selected) return
      selected.contentEditable = on ? 'true' : 'false'
      doc.body.setAttribute('data-wf-editing', on ? 'text' : '')
      if (on) { snapshot(); selected.focus() } else { touched() }
    },
    undo() {
      const previous = undoStack.pop()
      if (!previous) return
      doc.open(); doc.write(previous); doc.close()
      // The rewritten document is a new one; the caller reattaches.
      return true
    },
    /** The page as text, with every trace of the editor taken back out. */
    serialize() {
      const clone = doc.documentElement.cloneNode(true)
      clone.querySelectorAll(`[${MARK}]`).forEach(n => {
        n.removeAttribute(MARK); n.removeAttribute('data-wf-tag')
      })
      clone.querySelectorAll('.__wf_hover').forEach(n => n.classList.remove('__wf_hover'))
      clone.querySelectorAll('[contenteditable]').forEach(n => n.removeAttribute('contenteditable'))
      clone.querySelector(`#${STYLE_ID}`)?.remove()
      clone.querySelector('body')?.removeAttribute('data-wf-editing')
      return `<!DOCTYPE html>\n${clone.outerHTML}`
    },
    saved() { dirty = false; onDirty?.(false) },
    detach() {
      doc.removeEventListener('click', onClick, true)
      doc.removeEventListener('mouseover', onOver, true)
      doc.removeEventListener('mouseout', onOut, true)
    },
  }
  return api
}
