import React, { useState } from "react";
import {
  DEPLOY_STEPS,
  DeployWizard,
  DevOpsHeader,
  DeploymentTimelinePane,
  ContainersPane,
  CicdPane,
  CloudConfigPane,
  ReleasesPane,
} from "./agent4-sections";

function Agent4View({ onToast }) {
  const [showWizard, setShowWizard] = useState(true);
  const [deployStep, setDeployStep] = useState(-1);
  const [deployDone, setDeployDone] = useState(false);
  const [tab, setTab] = useState("timeline");

  const startDeploy = () => {
    setShowWizard(false);
    let step = 0;

    const run = () => {
      if (step < DEPLOY_STEPS.length) {
        setDeployStep(step);
        step += 1;
        setTimeout(run, 3000);
        return;
      }

      setDeployDone(true);
      onToast("Deployment pipeline complete! Release v1.0.0 is live.", "success");
    };

    setTimeout(run, 500);
  };

  const tabViews = {
    timeline: <DeploymentTimelinePane showWizard={showWizard} deployStep={deployStep} deployDone={deployDone} />,
    containers: deployDone ? <ContainersPane /> : null,
    cicd: deployDone ? <CicdPane /> : null,
    cloud: deployDone ? <CloudConfigPane /> : null,
    releases: deployDone ? <ReleasesPane /> : null,
  };

  return (
    <div className="flex h-full overflow-hidden bg-white">
      <div className="flex-1 flex flex-col overflow-hidden">
        <DevOpsHeader deployDone={deployDone} tab={tab} onChangeTab={setTab} />
        <div className="flex-1 overflow-y-auto p-5">{tabViews[tab]}</div>
      </div>
      {showWizard && <DeployWizard onStart={startDeploy} onCancel={() => setShowWizard(false)} />}
    </div>
  );
}

export default Agent4View;
