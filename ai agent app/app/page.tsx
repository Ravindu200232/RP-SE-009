'use client';

import { useEffect } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';
import { useBuilder } from '@/lib/store';
import { Header } from '@/components/Header';
import { TopProgressBar } from '@/components/TopProgressBar';
import { ProjectsSidebar } from '@/components/ProjectsSidebar';
import { ChatPanel } from '@/components/Chat/ChatPanel';
import { Workbench } from '@/components/Workbench/Workbench';

export default function Page() {
  const refreshStatus = useBuilder((s) => s.refreshStatus);
  const refreshProjects = useBuilder((s) => s.refreshProjects);

  useEffect(() => {
    refreshStatus();
    refreshProjects();
    const t = setInterval(refreshStatus, 15000);
    return () => clearInterval(t);
  }, [refreshStatus, refreshProjects]);

  return (
    <div className="flex h-full flex-col">
      <Header />
      <TopProgressBar />
      <div className="flex min-h-0 flex-1">
        <ProjectsSidebar />
        <PanelGroup
          direction="horizontal"
          autoSaveId="aiwb-layout"
          className="min-w-0 flex-1"
        >
          <Panel defaultSize={36} minSize={24} maxSize={60} className="min-w-0">
            <ChatPanel />
          </Panel>
          <PanelResizeHandle className="group relative w-px bg-border outline-none">
            <span className="absolute inset-y-0 -left-1.5 -right-1.5 z-10 transition-colors group-hover:bg-accent/30 group-data-[resize-handle-state=drag]:bg-accent/60" />
          </PanelResizeHandle>
          <Panel defaultSize={64} minSize={30} className="min-w-0">
            <Workbench />
          </Panel>
        </PanelGroup>
      </div>
    </div>
  );
}
