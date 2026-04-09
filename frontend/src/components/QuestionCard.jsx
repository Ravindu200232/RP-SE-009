'use client';

import { useState } from 'react';
import { RiCheckLine, RiArrowRightLine } from 'react-icons/ri';
import { HiSparkles } from 'react-icons/hi2';

const SECTION_STYLE = {
  // Legacy keys kept for backward compat
  metadata:  { border: 'border-purple-500/30', badge: 'bg-purple-500/20 text-purple-300', icon: '💡', label: 'The Basics' },
  users:     { border: 'border-cyan-500/30',   badge: 'bg-cyan-500/20 text-cyan-300',     icon: '👥', label: 'Your Users' },
  features:  { border: 'border-green-500/30',  badge: 'bg-green-500/20 text-green-300',   icon: '⚡', label: 'Features' },
  technical: { border: 'border-blue-500/30',   badge: 'bg-blue-500/20 text-blue-300',     icon: '🔧', label: 'Setup' },
  security:  { border: 'border-red-500/30',    badge: 'bg-red-500/20 text-red-300',       icon: '🔑', label: 'Sign In' },
  nfr:       { border: 'border-yellow-500/30', badge: 'bg-yellow-500/20 text-yellow-300', icon: '⚙️', label: 'Performance' },
  legal:     { border: 'border-pink-500/30',   badge: 'bg-pink-500/20 text-pink-300',     icon: '🛡️', label: 'Privacy' },
  // New user-friendly section keys
  basics:    { border: 'border-purple-500/30', badge: 'bg-purple-500/20 text-purple-300', icon: '💡', label: 'The Basics' },
  accounts:  { border: 'border-blue-500/30',   badge: 'bg-blue-500/20 text-blue-300',     icon: '🔑', label: 'Sign In' },
  privacy:   { border: 'border-pink-500/30',   badge: 'bg-pink-500/20 text-pink-300',     icon: '🛡️', label: 'Privacy & Safety' },
};

export default function QuestionCard({ questions, knownInfo, answers, setAnswers, onSubmit, submitted }) {
  const [idx, setIdx] = useState(0);
  if (!questions?.length) return null;

  const q = questions[idx];
  const style = SECTION_STYLE[q.section] || SECTION_STYLE.metadata;
  const isLast = idx === questions.length - 1;
  const allDone = questions.every(qq => {
    const val = answers[qq.key];
    if (qq.inputType === 'multiselect') return Array.isArray(val) && val.length > 0;
    return val !== undefined && val !== '';
  });
  const set = (key, val) => setAnswers(p => ({ ...p, [key]: val }));

  return (
    <div className={`rounded-2xl bubble-question border ${style.border} p-4 max-w-2xl w-full`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className="flex items-center gap-1.5 text-yellow-300 text-xs font-semibold uppercase tracking-widest">
          <HiSparkles /> Just a few quick questions
        </span>
        <div className="flex gap-1">
          {questions.map((_, i) => (
            <button key={i} onClick={() => setIdx(i)}
              className={`rounded-full transition-all ${i === idx ? 'bg-yellow-400 w-4 h-2' : answers[questions[i].key] ? 'bg-green-500 w-2 h-2' : 'bg-white/20 w-2 h-2'}`} />
          ))}
        </div>
      </div>

      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium mb-3 ${style.badge}`}>
        {style.icon} {style.label}
      </span>

      <p className="text-white font-medium text-sm mb-3 leading-relaxed">{idx + 1}. {q.question}</p>

      <div className="mb-4">
        {q.inputType === 'text' && (
          <input type="text" value={answers[q.key] || ''} onChange={e => set(q.key, e.target.value)}
            placeholder={q.placeholder || 'Your answer...'} disabled={submitted}
            className="w-full cosmic-input rounded-xl px-4 py-2.5 text-sm" />
        )}
        {q.inputType === 'textarea' && (
          <textarea value={answers[q.key] || ''} onChange={e => set(q.key, e.target.value)}
            placeholder={q.placeholder || 'Describe...'} disabled={submitted} rows={3}
            className="w-full cosmic-input rounded-xl px-4 py-2.5 text-sm resize-none" />
        )}
        {(q.inputType === 'select' || q.inputType === 'multiselect') && (
          <div className="flex flex-wrap gap-2">
            {q.options.map(opt => {
              const sel = q.inputType === 'select'
                ? answers[q.key] === opt
                : (answers[q.key] || []).includes(opt);
              return (
                <button key={opt} disabled={submitted}
                  onClick={() => {
                    if (q.inputType === 'select') set(q.key, opt);
                    else {
                      const prev = answers[q.key] || [];
                      set(q.key, sel ? prev.filter(v => v !== opt) : [...prev, opt]);
                    }
                  }}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all border ${
                    sel ? 'border-purple-500 bg-purple-500/20 text-purple-200' : 'border-white/10 glass glass-hover text-slate-300'
                  }`}>
                  {sel && <RiCheckLine className="inline mr-1" />}{opt}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between">
        <button onClick={() => setIdx(i => i - 1)} disabled={idx === 0 || submitted}
          className="px-3 py-1.5 rounded-lg glass glass-hover text-xs text-slate-400 disabled:opacity-40 transition-all">
          ← Prev
        </button>
        <span className="text-slate-500 text-xs">{idx + 1}/{questions.length}</span>
        {isLast ? (
          <button onClick={onSubmit} disabled={submitted || !allDone}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${allDone && !submitted ? 'btn-gold glow-gold' : 'glass text-slate-500 cursor-not-allowed'}`}>
            {submitted ? '✓ Submitted' : <><HiSparkles /> Generate SRS</>}
          </button>
        ) : (
          <button onClick={() => setIdx(i => i + 1)} disabled={submitted}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg btn-primary text-xs font-medium">
            Next <RiArrowRightLine />
          </button>
        )}
      </div>
    </div>
  );
}
