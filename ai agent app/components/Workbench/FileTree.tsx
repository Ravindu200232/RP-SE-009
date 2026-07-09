'use client';

import { useState } from 'react';
import { ChevronRight, ChevronDown, FileCode2, Folder, FolderOpen } from 'lucide-react';
import { useBuilder } from '@/lib/store';
import type { GeneratedFile } from '@/lib/artifact/types';
import { cn } from '@/lib/utils';

interface TreeNode {
  name: string;
  path: string;
  dir: boolean;
  children: TreeNode[];
}

function buildTree(files: GeneratedFile[]): TreeNode[] {
  const root: TreeNode = { name: '', path: '', dir: true, children: [] };
  for (const f of files) {
    const parts = f.path.split('/').filter(Boolean);
    let cur = root;
    parts.forEach((part, idx) => {
      const isLeaf = idx === parts.length - 1;
      const path = parts.slice(0, idx + 1).join('/');
      let child = cur.children.find((c) => c.name === part && c.dir === !isLeaf);
      if (!child) {
        child = { name: part, path, dir: !isLeaf, children: [] };
        cur.children.push(child);
      }
      cur = child;
    });
  }
  const sortRec = (n: TreeNode) => {
    n.children.sort((a, b) =>
      a.dir !== b.dir ? (a.dir ? -1 : 1) : a.name.localeCompare(b.name),
    );
    n.children.forEach(sortRec);
  };
  sortRec(root);
  return root.children;
}

function fileColor(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  if (ext === 'tsx' || ext === 'ts') return 'text-sky-400';
  if (ext === 'js' || ext === 'jsx' || ext === 'mjs' || ext === 'cjs') return 'text-yellow-400';
  if (ext === 'json') return 'text-amber-400';
  if (ext === 'css' || ext === 'scss') return 'text-pink-400';
  if (ext === 'md') return 'text-text-muted';
  return 'text-text-faint';
}

function Row({ node, depth }: { node: TreeNode; depth: number }) {
  const selectedPath = useBuilder((s) => s.selectedPath);
  const selectFile = useBuilder((s) => s.selectFile);
  const [open, setOpen] = useState(true);

  const pad = { paddingLeft: 8 + depth * 12 };

  if (node.dir) {
    return (
      <div>
        <button
          onClick={() => setOpen((o) => !o)}
          style={pad}
          className="flex w-full items-center gap-1 py-1 pr-2 text-left text-xs text-text-muted hover:text-text"
        >
          {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          {open ? (
            <FolderOpen size={13} className="text-accent-soft/80" />
          ) : (
            <Folder size={13} className="text-text-faint" />
          )}
          <span className="truncate">{node.name}</span>
        </button>
        {open && node.children.map((c) => <Row key={c.path} node={c} depth={depth + 1} />)}
      </div>
    );
  }

  return (
    <button
      onClick={() => selectFile(node.path)}
      style={pad}
      className={cn(
        'flex w-full items-center gap-1.5 py-1 pr-2 text-left text-xs',
        selectedPath === node.path
          ? 'bg-bg-elevated text-accent-soft'
          : 'text-text-muted hover:bg-bg-panel hover:text-text',
      )}
    >
      <span className="w-3" />
      <FileCode2 size={13} className={cn('shrink-0', fileColor(node.name))} />
      <span className="truncate font-mono">{node.name}</span>
    </button>
  );
}

export function FileTree() {
  const files = useBuilder((s) => s.files);
  const tree = buildTree(files);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto py-1">
      {tree.map((n) => (
        <Row key={n.path} node={n} depth={0} />
      ))}
    </div>
  );
}
