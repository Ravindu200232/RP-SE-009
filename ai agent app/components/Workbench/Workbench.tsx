'use client';

import { useEffect, useState } from 'react';
import {
  Download,
  TerminalSquare,
  Code2,
  Eye,
  ClipboardList,
  PencilLine,
  PanelsTopLeft,
  X,
} from 'lucide-react';
import { useBuilder } from '@/lib/store';
import { FileTree } from './FileTree';
import { CodeView } from './CodeView';
import { PreviewPanel } from './PreviewPanel';
import { PlannerView } from './PlannerView';
import { ThinkingView, useThinkingViewActive } from './ThinkingView';
import { cn } from '@/lib/utils';

function RunDialog({ id, onClose }: { id: string; onClose: () => void }) {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/40 p-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-bg-panel p-4 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Run this app yourself</h3>
          <button onClick={onClose} className="text-text-faint hover:text-text">
            <X size={16} />
          </button>
        </div>
        <p className="mb-2 text-xs text-text-muted">
          The project is on disk with a ready <code>.env.local</code>. In a terminal:
        </p>
        <pre className="mb-3 overflow-x-auto rounded-lg border border-border bg-bg-soft p-3 font-mono text-xs text-text">
{`cd workspace/${id}
npm install
npm run dev`}
        </pre>
        <p className="text-xs text-text-muted">
          Then open <span className="text-accent-soft">http://localhost:3000</span>.
        </p>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition',
        active
          ? 'bg-bg-elevated text-text'
          : 'text-text-muted hover:bg-bg-panel hover:text-text',
      )}
    >
      {icon}
      {label}
    </button>
  );
}

export function Workbench() {
  const files = useBuilder((s) => s.files);
  const projectId = useBuilder((s) => s.projectId);
  const streamingPath = useBuilder((s) => s.streamingPath);
  const isBuilding = useBuilder((s) => s.isBuilding);
  const isPlanning = useBuilder((s) => s.isPlanning);
  const autoPreviewToken = useBuilder((s) => s.autoPreviewToken);
  const [tab, setTab] = useState<'planner' | 'code' | 'preview'>('code');
  const [showRun, setShowRun] = useState(false);
  const showThinkingView = useThinkingViewActive();

  useEffect(() => {
    if (isPlanning) setTab('planner');
  }, [isPlanning]);

  useEffect(() => {
    if (isBuilding || streamingPath) setTab('code');
  }, [isBuilding, streamingPath]);

  useEffect(() => {
    if (autoPreviewToken > 0) setTab('preview');
  }, [autoPreviewToken]);

  const hasFiles = files.length > 0;

  const exportZip = () => {
    if (!projectId) return;
    const a = document.createElement('a');
    a.href = `/api/export/${projectId}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="relative flex h-full flex-col bg-bg">
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-border bg-bg-soft px-2.5">
        <div className="flex min-w-0 items-center gap-1">
          <TabButton
            active={tab === 'planner'}
            onClick={() => setTab('planner')}
            icon={<ClipboardList size={13} />}
            label="Planner"
          />
          <TabButton
            active={tab === 'code'}
            onClick={() => setTab('code')}
            icon={<Code2 size={13} />}
            label="Code"
          />
          <TabButton
            active={tab === 'preview'}
            onClick={() => setTab('preview')}
            icon={<Eye size={13} />}
            label="Preview"
          />
          {streamingPath && (
            <span className="ml-2 flex min-w-0 items-center gap-1 text-[11px] text-accent-soft">
              <PencilLine size={12} className="shrink-0 animate-pulse" />
              <span className="truncate font-mono">{streamingPath}</span>
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            onClick={() => setShowRun(true)}
            disabled={!hasFiles}
            className="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs text-text-muted transition hover:text-text disabled:opacity-40"
          >
            <TerminalSquare size={13} /> Run locally
          </button>
          <button
            onClick={exportZip}
            disabled={!hasFiles}
            className="flex items-center gap-1.5 rounded-md bg-accent px-2.5 py-1 text-xs font-medium text-white transition hover:bg-accent-soft disabled:opacity-40"
          >
            <Download size={13} /> Export ZIP
          </button>
        </div>
      </div>

      {showThinkingView ? (
        <ThinkingView />
      ) : tab === 'preview' ? (
        <PreviewPanel />
      ) : tab === 'planner' ? (
        <PlannerView />
      ) : !hasFiles ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
          <PanelsTopLeft size={28} className="text-text-faint/50" />
          <p className="text-sm text-text-muted">No files yet</p>
          <p className="max-w-xs text-xs text-text-faint">
            Describe an app or paste an SRS in the chat. Files appear here as
            they are built, ready to preview, export, and run.
          </p>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          <div className="flex w-60 shrink-0 flex-col border-r border-border bg-bg-soft">
            <div className="flex items-center justify-between px-3 py-2 text-[11px] font-semibold uppercase tracking-wider text-text-faint">
              <span>Files</span>
              <span>{files.length}</span>
            </div>
            <FileTree />
          </div>
          <CodeView />
        </div>
      )}

      {showRun && projectId && (
        <RunDialog id={projectId} onClose={() => setShowRun(false)} />
      )}
    </div>
  );
}
