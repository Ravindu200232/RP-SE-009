import React, { useEffect, useRef, useState } from "react";
import { AF_DATA } from "../core/data";
import {
  BUILD_STEPS,
  CODE_LOGS,
  BuilderHeader,
  BuildTimelinePane,
  CodeLogPane,
  LivePreviewModal,
  FrontendPagesPane,
  BackendServicesPane,
  CoderPane,
} from "./agent2-sections";

function Agent2View({ onNavigate, onToast }) {
  const [buildStep, setBuildStep] = useState(-1);
  const [buildDone, setBuildDone] = useState(false);
  const [codeLogs, setCodeLogs] = useState([]);
  const [tab, setTab] = useState("timeline");
  const [selectedFile, setSelectedFile] = useState("LoginPage.tsx");
  const [previewPage, setPreviewPage] = useState(null);
  const codeLogRef = useRef(null);

  useEffect(() => {
    let step = 0;

    const runStep = () => {
      if (step < BUILD_STEPS.length) {
        const currentStep = step;
        setBuildStep(currentStep);

        const logsForStep = CODE_LOGS.slice(currentStep * 2, currentStep * 2 + 2);
        logsForStep.forEach((log, index) => {
          setTimeout(() => {
            setCodeLogs((current) => [...current, log]);
          }, index * 1500);
        });

        step += 1;
        setTimeout(runStep, 5000);
        return;
      }

      setBuildDone(true);
      setCodeLogs((current) => [...current, CODE_LOGS[CODE_LOGS.length - 1]]);
      onToast("Build complete! Auto-navigating to QA Center...", "success");
      setTimeout(() => onNavigate("agent3"), 2500);
    };

    const timer = setTimeout(runStep, 800);
    return () => clearTimeout(timer);
  }, [onNavigate, onToast]);

  useEffect(() => {
    if (codeLogRef.current) {
      codeLogRef.current.scrollTop = codeLogRef.current.scrollHeight;
    }
  }, [codeLogs]);

  const tabViews = {
    timeline: (
      <div className="flex h-full">
        <BuildTimelinePane buildStep={buildStep} />
        <CodeLogPane buildDone={buildDone} codeLogs={codeLogs} codeLogRef={codeLogRef} />
      </div>
    ),
    frontend: <FrontendPagesPane pages={AF_DATA.pages} onOpenPreview={setPreviewPage} />,
    backend: <BackendServicesPane services={AF_DATA.services} />,
    coder: <CoderPane selectedFile={selectedFile} onSelectFile={setSelectedFile} />,
  };

  return (
    <div className="flex h-full overflow-hidden bg-white">
      <div className="flex-1 flex flex-col overflow-hidden">
        <BuilderHeader buildDone={buildDone} buildStep={buildStep} tab={tab} onChangeTab={setTab} />
        <div className="flex-1 overflow-hidden">{tabViews[tab]}</div>
      </div>
      {previewPage && <LivePreviewModal page={previewPage} onClose={() => setPreviewPage(null)} />}
    </div>
  );
}

export default Agent2View;
