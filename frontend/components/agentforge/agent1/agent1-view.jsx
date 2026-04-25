import React, { useState } from "react";
import { AF_DATA } from "../core/data";
import {
  Agent1Header,
  Agent1Tabs,
  SrsDocumentTab,
  FunctionalRequirementsTab,
  JsonOutputTab,
  DiagramsTab,
  AmbiguitiesTab,
  RiskTab,
  AnalysisInspector,
} from "./agent1-sections";

function Agent1View({ onNavigate, onToast }) {
  const [tab, setTab] = useState("srs");
  const [running, setRunning] = useState(false);
  const { srsRequirements } = AF_DATA;

  const runAnalysis = () => {
    setRunning(true);
    setTimeout(() => {
      setRunning(false);
      onToast("Analysis complete. SRS v1.2 generated with 14 requirements.", "success");
    }, 2000);
  };

  const approve = () => {
    onToast("Requirements approved. Design selection is now required before code generation.", "success");
    setTimeout(() => onNavigate("design-selector"), 800);
  };

  const tabViews = {
    srs: <SrsDocumentTab />,
    functional: <FunctionalRequirementsTab requirements={srsRequirements} />,
    json: <JsonOutputTab />,
    diagrams: <DiagramsTab />,
    ambiguities: <AmbiguitiesTab />,
    risk: <RiskTab />,
  };

  return (
    <div className="flex h-full overflow-hidden">
      <div className="flex-1 flex flex-col overflow-hidden bg-white">
        <Agent1Header
          running={running}
          onRunAnalysis={runAnalysis}
          onApprove={approve}
          onNavigate={onNavigate}
        />
        <Agent1Tabs tab={tab} onChange={setTab} />
        <div className="flex-1 overflow-y-auto p-5">{tabViews[tab]}</div>
      </div>
      <AnalysisInspector onApprove={approve} onNavigate={onNavigate} />
    </div>
  );
}

export default Agent1View;
