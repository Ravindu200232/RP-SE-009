"use client";

import React, { useEffect, useRef, useState } from "react";
import { createAgent1Session, submitAgent1Answers, submitAgent1Intake } from "../core/agent1-api";
import { clearAgent1Session, saveAgent1Session } from "../core/agent1-session";
import { AiLoadingOverlay, IdeaIntakeStage, QuestioningStage } from "./new-project-sections";

const IMAGE_ACCEPT = ".png,.jpg,.jpeg,.webp,image/*";
const PDF_ACCEPT = ".pdf,application/pdf";

function hasAnswerValue(value) {
  return Array.isArray(value) ? value.length > 0 : Boolean(String(value || "").trim());
}

function findNextQuestionIndex(questions, nextAnswers, startIndex = 0) {
  for (let index = startIndex; index < questions.length; index += 1) {
    if (!hasAnswerValue(nextAnswers[questions[index].key])) {
      return index;
    }
  }
  return questions.length;
}

function emptyDraftFor(question, answerValue) {
  if (!question) {
    return "";
  }
  if (question.inputType === "multiselect") {
    return Array.isArray(answerValue) ? answerValue : [];
  }
  return answerValue || "";
}

export default function NewProjectView({ onNavigate, onToast }) {
  const [idea, setIdea] = useState("");
  const [browserTranscript, setBrowserTranscript] = useState("");
  const [files, setFiles] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [questionPlan, setQuestionPlan] = useState(null);
  const [answers, setAnswers] = useState({});
  const [draftAnswer, setDraftAnswer] = useState("");
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const imageInputRef = useRef(null);
  const pdfInputRef = useRef(null);
  const recorderRef = useRef(null);
  const recorderChunksRef = useRef([]);
  const recognitionRef = useRef(null);
  const streamRef = useRef(null);
  const chatRef = useRef(null);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop?.();
      recorderRef.current?.stop?.();
      streamRef.current?.getTracks?.().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    const currentQuestion = questionPlan?.questions?.[currentQuestionIndex];
    if (!currentQuestion) {
      setDraftAnswer("");
      return;
    }
    setDraftAnswer(emptyDraftFor(currentQuestion, answers[currentQuestion.key]));
  }, [answers, currentQuestionIndex, questionPlan]);

  useEffect(() => {
    if (!questionPlan) {
      return undefined;
    }
    const timer = window.setTimeout(() => {
      const node = chatRef.current;
      if (!node) {
        return;
      }
      node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
    }, 90);
    return () => window.clearTimeout(timer);
  }, [answers, currentQuestionIndex, draftAnswer, questionPlan]);

  function pushFiles(nextFiles) {
    setFiles((current) => [...current, ...Array.from(nextFiles)]);
  }

  function removeFile(index) {
    setFiles((current) => current.filter((_, currentIndex) => currentIndex !== index));
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      onToast("Voice capture is not available in this browser.", "error");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      recorderChunksRef.current = [];

      const recorder = new window.MediaRecorder(stream);
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recorderChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = () => {
        if (!recorderChunksRef.current.length) {
          return;
        }
        const blob = new Blob(recorderChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        const file = new File([blob], `voice-note-${Date.now()}.webm`, { type: blob.type || "audio/webm" });
        setFiles((current) => [...current, file]);
      };
      recorder.start();
      recorderRef.current = recorder;

      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.onresult = (event) => {
          let transcript = "";
          for (let index = 0; index < event.results.length; index += 1) {
            transcript += `${event.results[index][0].transcript} `;
          }
          setBrowserTranscript(transcript.trim());
        };
        recognition.start();
        recognitionRef.current = recognition;
      }

      setIsRecording(true);
    } catch (error) {
      onToast(error.message || "Could not start voice capture.", "error");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop?.();
    recognitionRef.current?.stop?.();
    streamRef.current?.getTracks?.().forEach((track) => track.stop());
    setIsRecording(false);
  }

  function resetFlow() {
    clearAgent1Session();
    setSessionId("");
    setQuestionPlan(null);
    setAnswers({});
    setDraftAnswer("");
    setCurrentQuestionIndex(0);
    setFiles([]);
    setBrowserTranscript("");
    setIdea("");
    setIsRecording(false);
  }

  async function handleIntake() {
    if (!idea.trim() && !browserTranscript.trim() && files.length === 0) {
      onToast("Add a project idea, files, or a voice note first.", "error");
      return;
    }

    setIsSubmitting(true);
    try {
      clearAgent1Session();
      const created = await createAgent1Session({
        project_name: "Untitled App",
        audience: "General users",
        idea,
      });
      setSessionId(created.session_id);

      const intake = await submitAgent1Intake({
        sessionId: created.session_id,
        message: idea,
        browserTranscript,
        files,
      });

      setQuestionPlan(intake.question_plan);
      setAnswers({});
      setCurrentQuestionIndex(findNextQuestionIndex(intake.question_plan?.questions || [], {}, 0));
      saveAgent1Session(intake.session);
      onToast("Project context analysed. Answer the guided questions to complete the SRS.", "success");
    } catch (error) {
      onToast(error.message, "error");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleAnswerSubmit(rawValue) {
    const currentQuestion = questionPlan?.questions?.[currentQuestionIndex];
    if (!currentQuestion) {
      return;
    }

    const normalizedValue =
      currentQuestion.inputType === "multiselect"
        ? (Array.isArray(rawValue) ? rawValue : [])
        : String(rawValue || "").trim();

    if (!hasAnswerValue(normalizedValue)) {
      onToast("Please add an answer before moving to the next question.", "error");
      return;
    }

    const nextAnswers = {
      ...answers,
      [currentQuestion.key]: normalizedValue,
    };

    setAnswers(nextAnswers);
    setCurrentQuestionIndex(findNextQuestionIndex(questionPlan.questions || [], nextAnswers, currentQuestionIndex + 1));
  }

  async function handleGenerate() {
    if (!sessionId) {
      onToast("Start the intake first.", "error");
      return;
    }

    if (questionPlan?.questions?.some((question) => !hasAnswerValue(answers[question.key]))) {
      onToast("Please answer all interview questions before Build App starts.", "error");
      return;
    }

    setIsGenerating(true);
    try {
      const result = await submitAgent1Answers({ sessionId, answers });
      saveAgent1Session(result.session);
      onToast("Build complete. Opening Agent 1 review.", "success");
      onNavigate("agent1");
    } catch (error) {
      onToast(error.message, "error");
    } finally {
      setIsGenerating(false);
    }
  }

  const totalQuestions = questionPlan?.questions?.length || 0;
  const answeredQuestions = (questionPlan?.questions || []).filter((question) =>
    hasAnswerValue(answers[question.key])
  ).length;
  const canGenerate = totalQuestions === 0 || answeredQuestions === totalQuestions;
  const loadingCopy = {
    title: "Building...",
    subtitle: "",
  };

  return (
    <div className="h-full overflow-y-auto">
      {!questionPlan ? (
        <IdeaIntakeStage
          idea={idea}
          onIdeaChange={setIdea}
          onCreate={handleIntake}
          onOpenAudio={() => {
            if (isRecording) {
              stopRecording();
              return;
            }
            startRecording();
          }}
          onOpenImage={() => imageInputRef.current?.click()}
          onOpenPdf={() => pdfInputRef.current?.click()}
          isRecording={isRecording}
          files={files}
          transcript={browserTranscript}
          onRemoveFile={removeFile}
          isSubmitting={isSubmitting}
        />
      ) : (
        <div className="p-6">
          <div className="mx-auto min-h-[78vh] max-w-5xl overflow-hidden rounded-[30px] border border-gray-200 bg-white shadow-[0_20px_80px_-48px_rgba(31,111,235,0.45)]">
            <QuestioningStage
              chatRef={chatRef}
              questions={questionPlan.questions || []}
              currentQ={currentQuestionIndex}
              answers={answers}
              draftAnswer={draftAnswer}
              onDraftAnswerChange={setDraftAnswer}
              onAnswer={handleAnswerSubmit}
              analysisSummary={questionPlan.summary}
              onReset={resetFlow}
              onGenerate={handleGenerate}
              isGenerating={isGenerating}
              canGenerate={canGenerate}
            />
          </div>
        </div>
      )}

      <input
        ref={imageInputRef}
        type="file"
        multiple
        accept={IMAGE_ACCEPT}
        className="hidden"
        onChange={(event) => {
          if (event.target.files?.length) {
            pushFiles(event.target.files);
          }
          event.target.value = "";
        }}
      />

      <input
        ref={pdfInputRef}
        type="file"
        multiple
        accept={PDF_ACCEPT}
        className="hidden"
        onChange={(event) => {
          if (event.target.files?.length) {
            pushFiles(event.target.files);
          }
          event.target.value = "";
        }}
      />

      {(isSubmitting || isGenerating) ? (
        <AiLoadingOverlay title={loadingCopy.title} subtitle={loadingCopy.subtitle} />
      ) : null}
    </div>
  );
}
