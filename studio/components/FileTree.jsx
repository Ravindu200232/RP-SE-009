'use client'

import { useMemo, useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'


/**
 * The project as a tree, the way an editor shows it.
 *
 * The pane used to list `Object.keys(files).sort()` — sixty full paths in one
 * flat column, each one truncated in a 180px gutter, so `app/api/customers/`
 * and `app/api/products/` were told apart by the last few characters that
 * happened to fit. A tree is not decoration here: it is the only way the
 * shape of a generated project is legible at all.
 *
 * No icon font and no icon package. This runs with no network, and the studio
 * already has `lucide-react`; what makes a file type recognisable at a glance
 * is mostly COLOUR, not glyph — VS Code's own themes lean on exactly that. So
 * the badge is the extension in its own colour, which stays sharp at 10px
 * where a two-tone glyph turns to mush.
 */


// Roughly the colours a developer already expects from an editor's icon theme,
// pinned as literals rather than theme tokens: a file type means the same
// thing in light mode and dark, and the badges have to stay apart from each
// other rather than from the panel behind them.
const KIND = {
  jsx:  ['#61dafb', 'JSX'],
  js:   ['#f0db4f', 'JS'],
  mjs:  ['#f0db4f', 'JS'],
  cjs:  ['#f0db4f', 'JS'],
  ts:   ['#3178c6', 'TS'],
  tsx:  ['#3178c6', 'TSX'],
  json: ['#cbcb41', '{ }'],
  css:  ['#42a5f5', 'CSS'],
  scss: ['#c6538c', 'CSS'],
  html: ['#e34c26', '<>'],
  md:   ['#9aa4b2', 'MD'],
  py:   ['#4b8bbe', 'PY'],
  env:  ['#e8bb4d', 'ENV'],
  png:  ['#a074c4', 'IMG'],
  jpg:  ['#a074c4', 'IMG'],
  jpeg: ['#a074c4', 'IMG'],
  svg:  ['#ffb13b', 'SVG'],
  webp: ['#a074c4', 'IMG'],
  ico:  ['#a074c4', 'IMG'],
  lock: ['#8a94a6', 'LCK'],
  txt:  ['#8a94a6', 'TXT'],
}

// A few names carry more meaning than their extension does, exactly as they do
// in an editor's icon theme: `package.json` is not just some JSON.
const BY_NAME = {
  'package.json': ['#8bc34a', 'NPM'],
  'package-lock.json': ['#8a94a6', 'LCK'],
  'next.config.mjs': ['#ffffff', 'NXT'],
  'next.config.js': ['#ffffff', 'NXT'],
  'tailwind.config.js': ['#38bdf8', 'TW'],
  'postcss.config.js': ['#dd3a0a', 'PC'],
  'jsconfig.json': ['#f0db4f', 'CFG'],
  'vitest.config.mjs': ['#729b1b', 'TEST'],
  'playwright.config.js': ['#2ead33', 'TEST'],
  '.env.local': ['#e8bb4d', 'ENV'],
  '.gitignore': ['#f14e32', 'GIT'],
  'plan.md': ['#5b7cf7', 'PLAN'],
}


export function fileBadge(name) {
  const known = BY_NAME[name]
  if (known) return known
  if (/\.test\.[jt]sx?$/.test(name)) return ['#729b1b', 'TEST']
  const ext = name.includes('.') ? name.split('.').pop().toLowerCase() : ''
  return KIND[ext] || ['#8a94a6', ext.slice(0, 4).toUpperCase() || '•']
}


/** `{path: content}` → nested `{name, path, children[]}`, folders before files. */
function build(paths) {
  const root = { name: '', path: '', dirs: new Map(), files: [] }
  for (const p of paths) {
    const parts = p.split('/')
    let node = root
    for (let i = 0; i < parts.length - 1; i++) {
      const seg = parts[i]
      if (!node.dirs.has(seg)) {
        node.dirs.set(seg, {
          name: seg, path: parts.slice(0, i + 1).join('/'),
          dirs: new Map(), files: [],
        })
      }
      node = node.dirs.get(seg)
    }
    node.files.push({ name: parts[parts.length - 1], path: p })
  }

  const shape = (node) => ({
    ...node,
    dirs: [...node.dirs.values()]
      .sort((a, b) => a.name.localeCompare(b.name))
      .map(shape),
    files: node.files.sort((a, b) => a.name.localeCompare(b.name)),
  })
  return shape(root)
}


/**
 * Which folders start open.
 *
 * All of them, unless the project is big enough that "all of them" is the flat
 * list again with extra indentation. Past the threshold only the top level
 * opens, which is what an editor does with a large repository.
 */
function initialOpen(tree, total) {
  const open = new Set()
  const walk = (node, depth) => {
    for (const d of node.dirs) {
      if (total <= 40 || depth === 0) open.add(d.path)
      walk(d, depth + 1)
    }
  }
  walk(tree, 0)
  return open
}


export default function FileTree({ files, active, dirty, onPick }) {
  const paths = useMemo(() => Object.keys(files || {}), [files])
  const tree = useMemo(() => build(paths), [paths])
  const [open, setOpen] = useState(() => new Set())
  const [seeded, setSeeded] = useState('')

  // Re-seeded when the project changes, not on every render: a folder the
  // reader closed must stay closed while they work, and `files` changes on
  // every file an agent writes.
  const stamp = paths.length + ':' + (paths[0] || '')
  if (stamp !== seeded) {
    setSeeded(stamp)
    setOpen(initialOpen(tree, paths.length))
  }

  const toggle = (path) => setOpen(prev => {
    const next = new Set(prev)
    if (!next.delete(path)) next.add(path)
    return next
  })

  if (!paths.length) {
    return (
      <p className="px-3 py-2 font-mono text-[10px] text-muted2">No files yet.</p>
    )
  }

  const rows = []
  const walk = (node, depth) => {
    for (const dir of node.dirs) {
      const isOpen = open.has(dir.path)
      rows.push(
        <button key={'d:' + dir.path} onClick={() => toggle(dir.path)}
                className="flex w-full items-center gap-1 py-[3px] pr-2 text-left
                           text-[11px] text-muted transition-colors
                           hover:bg-panel2 hover:text-ink"
                style={{ paddingLeft: 6 + depth * 11 }}>
          {isOpen ? <ChevronDown className="size-3 shrink-0 opacity-60" />
                  : <ChevronRight className="size-3 shrink-0 opacity-60" />}
          <span className="truncate">{dir.name}</span>
        </button>
      )
      if (isOpen) walk(dir, depth + 1)
    }
    for (const f of node.files) {
      const [colour, label] = fileBadge(f.name)
      const on = f.path === active
      rows.push(
        <button key={'f:' + f.path} onClick={() => onPick(f.path)}
                title={f.path}
                className={cn('flex w-full items-center gap-1.5 py-[3px] pr-2',
                  'text-left text-[11px] transition-colors',
                  on ? 'bg-accent/12 text-accent'
                     : 'text-muted hover:bg-panel2 hover:text-ink')}
                style={{ paddingLeft: 10 + depth * 11 }}>
          <span className="shrink-0 rounded-[3px] px-[3px] py-px font-mono
                           text-[7.5px] font-bold leading-[10px]"
                style={{ color: colour, border: `1px solid ${colour}55`,
                         background: `${colour}18` }}>
            {label}
          </span>
          <span className="truncate">{f.name}</span>
          {dirty?.has(f.path) && (
            <span title="unsaved"
                  className="ml-auto size-[5px] shrink-0 rounded-full bg-warn" />
          )}
        </button>
      )
    }
  }
  walk(tree, 0)

  return <div className="py-1">{rows}</div>
}
