'use client'

/** Files attached to an editing chat. */
import { useCallback, useRef, useState } from 'react'

import { api } from './api'

let seq = 0

export function useEditAttachments() {
  const [items, setItems] = useState([])
  const busy = useRef(false)

  const add = useCallback(files => {
    const fresh = Array.from(files || []).map(file => ({
      key: `ea-${++seq}`, file, name: file.name || 'upload',
      state: 'waiting', read: '', url: '', kind: '', note: '',
    }))
    if (fresh.length) setItems(list => [...list, ...fresh])
  }, [])

  const remove = useCallback(key => setItems(l => l.filter(i => i.key !== key)), [])
  const reset = useCallback(() => setItems([]), [])

  /** Read everything not yet read, and return the block to append. */
  const collect = useCallback(async project => {
    if (busy.current) return ''
    busy.current = true
    try {
      let queue = []
      setItems(list => {
        queue = list.filter(i => i.state !== 'done')
        return list.map(i => (i.state === 'done' ? i : { ...i, state: 'reading' }))
      })
      await Promise.resolve()

      for (const it of queue) {
        try {
          const r = await api.attach(it.file, { project })
          const got = { read: r.text || '', url: r.url || '', kind: r.kind || '',
                        note: r.note || '', path: r.path || '', truncated: !!r.truncated }
          setItems(l => l.map(x => x.key === it.key ? { ...x, state: 'done', ...got } : x))
          Object.assign(it, got)
        } catch (e) {
          setItems(l => l.map(x => x.key === it.key
            ? { ...x, state: 'failed', note: e.message } : x))
          it.failed = true
        }
      }

      let all = []
      setItems(list => { all = list; return list })
      await Promise.resolve()
      return blockFor(all)
    } finally {
      busy.current = false
    }
  }, [])

  return { items, add, remove, reset, collect,
           busy: items.some(i => i.state === 'reading') }
}

/** What each kind of attachment is, said once, in the prompt. */
const KIND_SAID = {
  audio: 'a recording, transcribed',
  pdf: 'a document',
  document: 'a document',
  archive: 'an archive, listed and read',
  text: 'a file',
}

/**
 * The text appended to the instruction.
 *
 * Every attached file is written into the project before this runs, so the
 * agent can open it with the same tools it uses on the rest of the code. What
 * travels in the prompt is what only the studio could work out — what a picture
 * shows, what a recording says — plus the path, so the agent reads the file
 * itself instead of answering from a truncated excerpt of it.
 */
function blockFor(items) {
  const usable = (items || []).filter(i => i.read || i.url || i.path)
  if (!usable.length) return ''

  const parts = usable.map(i => {
    if (i.kind === 'image') {
      return `### ${i.name} — a picture, already saved at ${i.url}\n`
        + `If they asked for this picture to appear, use exactly that path in `
        + `an <img>; it exists on disk, so do not invent another and do not `
        + `leave a placeholder. What it shows:\n${i.read || '(could not be read)'}`
    }
    const what = KIND_SAID[i.kind] || 'a file'
    const head = [`### ${i.name} — ${what}`]
    if (i.path) head.push(`Saved in this project at \`${i.path}\` — open it there for the whole file.`)
    if (i.read) head.push(i.truncated ? `The opening of it:\n${i.read}\n…` : i.read)
    else if (i.path) head.push('Nothing could be extracted from it here; read it from that path.')
    return head.join('\n')
  })

  return `\n\n## What they attached\n\n${parts.join('\n\n')}`
}
