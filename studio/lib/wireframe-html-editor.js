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
