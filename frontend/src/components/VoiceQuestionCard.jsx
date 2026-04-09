'use client';

import { useEffect, useRef, useState } from 'react';
import { RiArrowRightLine, RiCheckLine, RiMicLine, RiStopLine, RiVolumeUpLine } from 'react-icons/ri';
import { HiSparkles } from 'react-icons/hi2';
import { cancelSpeech, createSpeechRecognition, matchSpokenOptions, speakText } from '../lib/speech';

const SECTION_STYLE = {
  metadata: { border: 'border-purple-500/30', badge: 'bg-purple-500/20 text-purple-300', icon: 'Idea', label: 'The Basics' },
  users: { border: 'border-cyan-500/30', badge: 'bg-cyan-500/20 text-cyan-300', icon: 'Users', label: 'Your Users' },
  features: { border: 'border-green-500/30', badge: 'bg-green-500/20 text-green-300', icon: 'Flow', label: 'Features' },
  technical: { border: 'border-blue-500/30', badge: 'bg-blue-500/20 text-blue-300', icon: 'Setup', label: 'Setup' },
  security: { border: 'border-red-500/30', badge: 'bg-red-500/20 text-red-300', icon: 'Auth', label: 'Sign In' },
  nfr: { border: 'border-yellow-500/30', badge: 'bg-yellow-500/20 text-yellow-300', icon: 'Perf', label: 'Performance' },
  legal: { border: 'border-pink-500/30', badge: 'bg-pink-500/20 text-pink-300', icon: 'Rules', label: 'Privacy' },
  basics: { border: 'border-purple-500/30', badge: 'bg-purple-500/20 text-purple-300', icon: 'Idea', label: 'The Basics' },
  accounts: { border: 'border-blue-500/30', badge: 'bg-blue-500/20 text-blue-300', icon: 'Auth', label: 'Sign In' },
  privacy: { border: 'border-pink-500/30', badge: 'bg-pink-500/20 text-pink-300', icon: 'Safe', label: 'Privacy & Safety' },
  integrations: { border: 'border-indigo-500/30', badge: 'bg-indigo-500/20 text-indigo-300', icon: 'Link', label: 'Integrations' },
  operations: { border: 'border-yellow-500/30', badge: 'bg-yellow-500/20 text-yellow-300', icon: 'Ops', label: 'Operations' },
  interfaces: { border: 'border-cyan-500/30', badge: 'bg-cyan-500/20 text-cyan-300', icon: 'UI', label: 'Interfaces' },
};

function mergeTextValue(previousValue, transcript) {
  const cleanTranscript = transcript.trim();
  if (!cleanTranscript) {
    return previousValue;
  }
  if (!previousValue) {
    return cleanTranscript;
  }
  return `${previousValue} ${cleanTranscript}`.trim();
}

export default function VoiceQuestionCard({ questions, knownInfo, answers, setAnswers, onSubmit, submitted }) {
  const [idx, setIdx] = useState(0);
  const [isListening, setIsListening] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const recognitionRef = useRef(null);

  useEffect(() => () => {
    recognitionRef.current?.stop?.();
    cancelSpeech();
  }, []);

  useEffect(() => {
    setVoiceError('');
    setIsListening(false);
    recognitionRef.current?.stop?.();
  }, [idx]);

  if (!questions?.length) {
    return null;
  }

  const q = questions[idx];
  const style = SECTION_STYLE[q.section] || SECTION_STYLE.metadata;
  const isLast = idx === questions.length - 1;
  const allDone = questions.every((question) => {
    const value = answers[question.key];
    if (question.inputType === 'multiselect') {
      return Array.isArray(value) && value.length > 0;
    }
    return value !== undefined && value !== '';
  });

  const setAnswer = (key, value) => setAnswers((previous) => ({ ...previous, [key]: value }));

  const speakCurrentQuestion = () => {
    const optionsText = Array.isArray(q.options) && q.options.length ? ` Options are: ${q.options.join(', ')}.` : '';
    const didSpeak = speakText(`${q.question}${optionsText}`);
    if (!didSpeak) {
      setVoiceError('Browser voice read is not available here. You can still answer by typing or using the mic.');
      return;
    }
    setVoiceError('');
  };

  const applyVoiceAnswer = (transcript) => {
    if (!transcript.trim()) {
      return;
    }

    if (q.inputType === 'text' || q.inputType === 'textarea') {
      setAnswer(q.key, mergeTextValue(answers[q.key] || '', transcript));
      return;
    }

    if (q.inputType === 'select') {
      const matched = matchSpokenOptions(transcript, q.options || [], false);
      if (matched) {
        setAnswer(q.key, matched);
        return;
      }
      setVoiceError('Could not match that answer to one of the listed options.');
      return;
    }

    if (q.inputType === 'multiselect') {
      const matched = matchSpokenOptions(transcript, q.options || [], true);
      if (matched.length) {
        setAnswer(q.key, matched);
        return;
      }
      setVoiceError('Could not match that answer to the listed choices.');
    }
  };

  const toggleVoiceAnswer = () => {
    if (submitted) {
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop?.();
      setIsListening(false);
      return;
    }

    const recognition = createSpeechRecognition({ continuous: false, interimResults: false });
    if (!recognition) {
      setVoiceError('Voice recognition is not available in this browser.');
      return;
    }

    setVoiceError('');
    recognitionRef.current = recognition;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript || '')
        .join(' ')
        .trim();
      applyVoiceAnswer(transcript);
    };
    recognition.onerror = (event) => {
      setVoiceError(event.error === 'not-allowed' ? 'Microphone permission was denied.' : 'Voice capture failed. Try speaking again or type the answer.');
      setIsListening(false);
    };
    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.start();
    setIsListening(true);
  };

  return (
    <div className={`rounded-2xl bubble-question border ${style.border} p-4 max-w-2xl w-full`}>
      <div className="flex items-center justify-between mb-3">
        <span className="flex items-center gap-1.5 text-yellow-300 text-xs font-semibold uppercase tracking-widest">
          <HiSparkles /> Just a few quick questions
        </span>
        <div className="flex gap-1">
          {questions.map((question, index) => (
            <button
              key={question.key || index}
              onClick={() => setIdx(index)}
              className={`rounded-full transition-all ${index === idx ? 'bg-yellow-400 w-4 h-2' : answers[question.key] ? 'bg-green-500 w-2 h-2' : 'bg-white/20 w-2 h-2'}`}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${style.badge}`}>
          {style.icon} {style.label}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={speakCurrentQuestion}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg glass glass-hover text-xs text-slate-300 border border-white/10"
          >
            <RiVolumeUpLine /> Read
          </button>
          <button
            type="button"
            onClick={toggleVoiceAnswer}
            disabled={submitted}
            className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs border transition-all ${
              isListening
                ? 'border-emerald-400 bg-emerald-500/15 text-emerald-200'
                : 'border-white/10 glass glass-hover text-slate-300'
            } ${submitted ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {isListening ? <RiStopLine /> : <RiMicLine />}
            {isListening ? 'Listening' : 'Voice answer'}
          </button>
        </div>
      </div>

      <p className="text-white font-medium text-sm mb-3 leading-relaxed">
        {idx + 1}. {q.question}
      </p>

      <div className="mb-4">
        {q.inputType === 'text' && (
          <input
            type="text"
            value={answers[q.key] || ''}
            onChange={(event) => setAnswer(q.key, event.target.value)}
            placeholder={q.placeholder || 'Your answer...'}
            disabled={submitted}
            className="w-full cosmic-input rounded-xl px-4 py-2.5 text-sm"
          />
        )}

        {q.inputType === 'textarea' && (
          <textarea
            value={answers[q.key] || ''}
            onChange={(event) => setAnswer(q.key, event.target.value)}
            placeholder={q.placeholder || 'Describe...'}
            disabled={submitted}
            rows={3}
            className="w-full cosmic-input rounded-xl px-4 py-2.5 text-sm resize-none"
          />
        )}

        {(q.inputType === 'select' || q.inputType === 'multiselect') && (
          <div className="flex flex-wrap gap-2">
            {(q.options || []).map((option) => {
              const selected = q.inputType === 'select'
                ? answers[q.key] === option
                : (answers[q.key] || []).includes(option);

              return (
                <button
                  key={option}
                  disabled={submitted}
                  onClick={() => {
                    if (q.inputType === 'select') {
                      setAnswer(q.key, option);
                      return;
                    }

                    const previous = answers[q.key] || [];
                    setAnswer(q.key, selected ? previous.filter((value) => value !== option) : [...previous, option]);
                  }}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border ${
                    selected ? 'border-purple-500 bg-purple-500/20 text-purple-200' : 'border-white/10 glass glass-hover text-slate-300'
                  }`}
                >
                  {selected && <RiCheckLine className="inline mr-1" />}
                  {option}
                </button>
              );
            })}
          </div>
        )}

        {voiceError && <p className="text-xs text-amber-300 mt-2">{voiceError}</p>}
      </div>

      <div className="flex items-center justify-between">
        <button
          onClick={() => setIdx((value) => value - 1)}
          disabled={idx === 0 || submitted}
          className="px-3 py-1.5 rounded-lg glass glass-hover text-xs text-slate-400 disabled:opacity-40 transition-all"
        >
          Back
        </button>

        <span className="text-slate-500 text-xs">
          {idx + 1}/{questions.length}
        </span>

        {isLast ? (
          <button
            onClick={onSubmit}
            disabled={submitted || !allDone}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${allDone && !submitted ? 'btn-gold glow-gold' : 'glass text-slate-500 cursor-not-allowed'}`}
          >
            {submitted ? 'Submitted' : <><HiSparkles /> Generate SRS</>}
          </button>
        ) : (
          <button
            onClick={() => setIdx((value) => value + 1)}
            disabled={submitted}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg btn-primary text-xs font-medium"
          >
            Next <RiArrowRightLine />
          </button>
        )}
      </div>
    </div>
  );
}
