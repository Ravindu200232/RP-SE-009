'use client';

import { useBuilder } from '@/lib/store';
import { cn } from '@/lib/utils';
import { Plus, Trash2, FolderGit2 } from 'lucide-react';

export function ProjectsSidebar() {
  const projects = useBuilder((s) => s.projects);
  const projectId = useBuilder((s) => s.projectId);
  const isStreaming = useBuilder((s) => s.isStreaming);
  const newProject = useBuilder((s) => s.newProject);
  const loadProject = useBuilder((s) => s.loadProject);
  const deleteProject = useBuilder((s) => s.deleteProject);

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-bg-soft">
      <div className="p-2.5">
        <button
          onClick={newProject}
          disabled={isStreaming}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white transition hover:bg-accent-soft disabled:opacity-50"
        >
          <Plus size={15} /> New app
        </button>
      </div>

      <div className="px-3 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wider text-text-faint">
        Projects
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-2">
        {projects.length === 0 ? (
          <p className="px-2 py-3 text-xs text-text-faint">
            No projects yet. Describe an app to create one.
          </p>
        ) : (
          projects.map((p) => (
            <div
              key={p.id}
              className={cn(
                'group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm',
                p.id === projectId
                  ? 'bg-bg-elevated text-text'
                  : 'text-text-muted hover:bg-bg-panel',
              )}
            >
              <FolderGit2 size={14} className="shrink-0 text-text-faint" />
              <button
                onClick={() => loadProject(p.id)}
                className="min-w-0 flex-1 truncate text-left"
                title={p.name}
              >
                {p.name || 'Untitled app'}
              </button>
              <button
                onClick={() => deleteProject(p.id)}
                className="shrink-0 text-text-faint opacity-0 transition hover:text-rose-400 group-hover:opacity-100"
                title="Delete"
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
