'use client';
import { useState } from 'react';
import { ChevronRight, ChevronDown, File, Folder, FolderOpen } from 'lucide-react';
import { GeneratedFile } from '@/types';

interface FileNode {
  name: string;
  path: string;
  content?: string;
  children?: FileNode[];
  isDir: boolean;
  service?: string;
}

function buildTree(files: GeneratedFile[]): FileNode[] {
  const root: Record<string, FileNode> = {};

  files.forEach(file => {
    const parts = file.path.replace(/\\/g, '/').split('/');
    let current = root;

    parts.forEach((part, i) => {
      const isLast = i === parts.length - 1;
      const key = parts.slice(0, i + 1).join('/');

      if (!current[key]) {
        current[key] = {
          name: part,
          path: key,
          isDir: !isLast,
          children: isLast ? undefined : [],
          content: isLast ? file.content : undefined,
          service: file.service
        };
      }

      if (!isLast && current[key].children) {
        const nextKey = parts.slice(0, i + 2).join('/');
        if (!current[nextKey]) {
          const subNode: FileNode = {
            name: parts[i + 1],
            path: nextKey,
            isDir: i + 1 < parts.length - 1,
            children: i + 1 < parts.length - 1 ? [] : undefined,
            content: i + 1 === parts.length - 1 ? files.find(f => f.path.replace(/\\/g, '/') === nextKey)?.content : undefined,
            service: file.service
          };
          current[key].children?.push(subNode);
          current[nextKey] = subNode;
        }
      }
    });
  });

  // Build simple flat tree grouped by service
  const serviceGroups: Record<string, GeneratedFile[]> = {};
  files.forEach(f => {
    const svc = f.service || 'other';
    if (!serviceGroups[svc]) serviceGroups[svc] = [];
    serviceGroups[svc].push(f);
  });

  return Object.entries(serviceGroups).map(([service, svcFiles]) => ({
    name: service,
    path: service,
    isDir: true,
    service,
    children: svcFiles.map(f => ({
      name: f.path.split('/').pop() || f.path,
      path: f.path,
      content: f.content,
      isDir: false,
      service: f.service
    }))
  }));
}

const serviceColors: Record<string, string> = {
  frontend: 'text-blue-400',
  gateway:  'text-orange-400',
  default:  'text-purple-400'
};

const fileIcon = (name: string) => {
  if (name.endsWith('.json')) return '{}';
  if (name.endsWith('.ts') || name.endsWith('.tsx')) return 'TS';
  if (name.endsWith('.js') || name.endsWith('.jsx')) return 'JS';
  if (name.endsWith('.css')) return 'CS';
  if (name.endsWith('.env')) return 'EV';
  if (name === 'package.json') return 'PM';
  return 'F';
};

function TreeNode({
  node, depth, onSelect, selectedPath
}: {
  node: FileNode; depth: number; onSelect: (f: GeneratedFile) => void; selectedPath: string;
}) {
  const [open, setOpen] = useState(depth === 0);

  if (node.isDir) {
    const color = serviceColors[node.name] || serviceColors.default;
    return (
      <div>
        <div
          className="flex items-center gap-1.5 px-2 py-1 hover:bg-white/5 cursor-pointer rounded text-xs file-tree-item"
          style={{ paddingLeft: `${8 + depth * 12}px` }}
          onClick={() => setOpen(!open)}
        >
          {open ? <ChevronDown size={12} className="text-slate-500" /> : <ChevronRight size={12} className="text-slate-500" />}
          {open ? <FolderOpen size={12} className={color} /> : <Folder size={12} className={color} />}
          <span className={`font-medium ${color}`}>{node.name}</span>
          {node.children && (
            <span className="ml-auto text-[10px] text-slate-600">{node.children.length}</span>
          )}
        </div>
        {open && node.children?.map((child, i) => (
          <TreeNode key={i} node={child} depth={depth + 1} onSelect={onSelect} selectedPath={selectedPath} />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`flex items-center gap-1.5 px-2 py-1 hover:bg-white/5 cursor-pointer rounded text-xs file-tree-item transition-colors ${
        selectedPath === node.path ? 'bg-purple-500/10 border-l-2 border-purple-500' : ''
      }`}
      style={{ paddingLeft: `${8 + depth * 12}px` }}
      onClick={() => node.content !== undefined && onSelect({ path: node.path, content: node.content!, service: node.service || '' })}
    >
      <span className="w-4 text-center text-[9px] font-bold text-slate-600 font-mono">
        {fileIcon(node.name)}
      </span>
      <File size={11} className="text-slate-500 shrink-0" />
      <span className="text-slate-300 truncate">{node.name}</span>
    </div>
  );
}

interface FileExplorerProps {
  files: GeneratedFile[];
  onSelect: (file: GeneratedFile) => void;
  selectedPath: string;
}

export function FileExplorer({ files, onSelect, selectedPath }: FileExplorerProps) {
  const tree = buildTree(files);

  return (
    <div className="h-full overflow-y-auto py-2">
      {files.length === 0 ? (
        <div className="text-center text-slate-600 text-xs py-8 px-4">
          Generated files will appear here
        </div>
      ) : (
        tree.map((node, i) => (
          <TreeNode key={i} node={node} depth={0} onSelect={onSelect} selectedPath={selectedPath} />
        ))
      )}
    </div>
  );
}
