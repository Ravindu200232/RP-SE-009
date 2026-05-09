import React, { useEffect, useRef, useState } from "react";
import {
  PHASE,
  IdeaIntakeStage,
  AnalysisStage,
  QuestioningStage,
  PreparingStage,
  GeneratingStage,
  GeneratedSrsStage,
} from "./new-project-sections";

function NewProjectView({ onNavigate, onToast }) {
  const [phase, setPhase] = useState(PHASE.INTAKE);
  const [idea, setIdea] = useState("");
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [showNextQ, setShowNextQ] = useState(false);
  const chatRef = useRef(null);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [answers, currentQ, phase]);

  const handleCreate = () => {
    if (!idea.trim()) {
      return;
    }

    setPhase(PHASE.ANALYZING);
  };

  const handleAnswer = (answer) => {
    const nextAnswers = [...answers, answer];
    setAnswers(nextAnswers);
    setShowNextQ(false);

    if (currentQ < 9) {
      setTimeout(() => {
        setCurrentQ((value) => value + 1);
        setShowNextQ(true);
      }, 1200);
      return;
    }

    setTimeout(() => setPhase(PHASE.PREPARING), 1200);
  };

  const phaseViews = {
    [PHASE.INTAKE]: (
      <IdeaIntakeStage idea={idea} onIdeaChange={setIdea} onCreate={handleCreate} />
    ),
    [PHASE.ANALYZING]: <AnalysisStage idea={idea} onComplete={() => {
      setPhase(PHASE.QUESTIONING);
      setShowNextQ(true);
    }} />,
    [PHASE.QUESTIONING]: (
      <QuestioningStage
        chatRef={chatRef}
        currentQ={currentQ}
        answers={answers}
        showNextQ={showNextQ}
        onAnswer={handleAnswer}
      />
    ),
    [PHASE.PREPARING]: <PreparingStage onComplete={() => setPhase(PHASE.GENERATING)} />,
    [PHASE.GENERATING]: <GeneratingStage onComplete={() => setPhase(PHASE.SRS)} />,
    [PHASE.SRS]: (
      <GeneratedSrsStage
        onContinue={() => {
          onToast("SRS approved. Launching Agent 2 Build Studio...", "success");
          setTimeout(() => onNavigate("agent2"), 800);
        }}
      />
    ),
  };

  return <div className="flex h-full overflow-hidden">{phaseViews[phase]}</div>;
}

export default NewProjectView;
