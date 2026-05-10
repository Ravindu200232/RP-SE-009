import React, { useState } from "react";
import { AF_DATA } from "../core/data";
import {
  MemoryHeader,
  MemoryTabs,
  FailureMemoryPane,
  ArchitecturePatternsPane,
  PromptHistoryPane,
  AgentEventsPane,
  ExecutionLogsPane,
} from "./memory-sections";

function MemoryView({ onToast }) {
  const [tab, setTab] = useState("failures");
  const { memoryPatterns } = AF_DATA;

  const tabViews = {
    failures: <FailureMemoryPane memoryPatterns={memoryPatterns} />,
    patterns: <ArchitecturePatternsPane />,
    prompts: <PromptHistoryPane />,
    events: <AgentEventsPane />,
    logs: <ExecutionLogsPane />,
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-white">
      <MemoryHeader onExport={() => onToast("Memory report exported.", "success")} />
      <MemoryTabs tab={tab} memoryCount={memoryPatterns.length} onChange={setTab} />
      <div className="flex-1 overflow-y-auto p-5">{tabViews[tab]}</div>
    </div>
  );
}

export default MemoryView;
