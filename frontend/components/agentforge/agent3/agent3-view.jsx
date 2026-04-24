import React, { useEffect, useState } from "react";
import {
  TEST_STEPS,
  BUGS_PER_ROUND,
  QA_SCORES,
  QaHeader,
  TimelinePane,
  FixLogPane,
  OverviewPane,
  BugReportsPane,
  ApiContractsPane,
  UnitTestingPane,
  IntegrationPane,
  QaInspector,
} from "./agent3-sections";

function Agent3View({ onNavigate, onToast }) {
  const [testStep, setTestStep] = useState(-1);
  const [testDone, setTestDone] = useState(false);
  const [round, setRound] = useState(0);
  const [showFixing, setShowFixing] = useState(false);
  const [allDone, setAllDone] = useState(false);
  const [tab, setTab] = useState("timeline");
  const [roundHistory, setRoundHistory] = useState([]);
  const [fixingRound, setFixingRound] = useState(0);

  const qaScore = QA_SCORES[Math.min(round, QA_SCORES.length - 1)];
  const bugs = BUGS_PER_ROUND[Math.min(round, BUGS_PER_ROUND.length - 1)];

  const runTestCycle = (nextRound) => {
    setTestStep(-1);
    setTestDone(false);
    setShowFixing(false);

    let step = 0;

    const runStep = () => {
      if (step < TEST_STEPS.length) {
        setTestStep(step);
        step += 1;
        setTimeout(runStep, 400);
        return;
      }

      setTestDone(true);
      const currentBugs = BUGS_PER_ROUND[Math.min(nextRound, BUGS_PER_ROUND.length - 1)];

      if (currentBugs.length > 0) {
        setTimeout(() => {
          setShowFixing(true);
          setFixingRound(nextRound);
          setRoundHistory((current) => [...current, { round: nextRound, score: QA_SCORES[nextRound], bugs: currentBugs.length }]);
        }, 800);
        return;
      }

      setAllDone(true);
      setRoundHistory((current) => [...current, { round: nextRound, score: QA_SCORES[nextRound], bugs: 0 }]);
      onToast("QA passed! Score 94%. Preparing Agent 4 deployment...", "success");
      setTimeout(() => onNavigate("agent4"), 2000);
    };

    setTimeout(runStep, 500);
  };

  useEffect(() => {
    runTestCycle(0);
  }, []);

  const handleFixDone = () => {
    setShowFixing(false);
    const nextRound = round + 1;
    setRound(nextRound);
    setTimeout(() => runTestCycle(nextRound), 1000);
  };

  const tabViews = {
    timeline: (
      <TimelinePane
        round={round}
        testStep={testStep}
        testDone={testDone}
        showFixing={showFixing}
        fixingRound={fixingRound}
        roundHistory={roundHistory}
        bugs={bugs}
        qaScore={qaScore}
        allDone={allDone}
        onFixDone={handleFixDone}
      />
    ),
    fixlog: showFixing ? <FixLogPane fixingRound={fixingRound} /> : null,
    overview: allDone ? <OverviewPane /> : null,
    unit: allDone ? <UnitTestingPane /> : null,
    integration: allDone ? <IntegrationPane /> : null,
    api: allDone ? <ApiContractsPane /> : null,
    bugs: <BugReportsPane bugs={bugs} showFixing={showFixing} />,
  };

  return (
    <div className="flex h-full overflow-hidden bg-white">
      <div className="flex-1 flex flex-col overflow-hidden">
        <QaHeader
          qaScore={qaScore}
          round={round}
          showFixing={showFixing}
          allDone={allDone}
          tab={tab}
          onChangeTab={setTab}
          bugCount={bugs.length}
        />
        <div className="flex-1 overflow-y-auto p-5">{tabViews[tab]}</div>
      </div>
      <QaInspector round={round} qaScore={qaScore} bugs={bugs} showFixing={showFixing} roundHistory={roundHistory} />
    </div>
  );
}

export default Agent3View;
