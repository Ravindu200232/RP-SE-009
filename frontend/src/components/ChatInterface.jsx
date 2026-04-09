'use client';

import { useState, useRef, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { RiSendPlane2Line, RiImageLine, RiFilePdf2Line, RiMicLine, RiCloseLine } from 'react-icons/ri';
import { HiPaperClip } from 'react-icons/hi2';
import QuestionCard from './QuestionCard';

export default function ChatInterface({ phase, messages, questions, knownInfo = {}, onStart, onAnswers, idle = false, srsTokens = '' }) {
  const [prompt, setPrompt]       = useState('');
  const [files, setFiles]         = useState([]);
  const [answers, setAnswers]     = useState({});
  const [submitted, setSubmitted] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'image/*': [], 'application/pdf': [], 'audio/*': [], 'text/plain': [] },
    onDrop: (a) => setFiles(p => [...p, ...a].slice(0, 5)),
    noClick: true,
  });

  const send = () => {
    if (!prompt.trim() && files.length === 0) return;
    onStart(prompt.trim(), files);
    setPrompt(''); setFiles([]);
  };

  const onKey = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };

  const removeFile = (i) => setFiles(p => p.filter((_, idx) => idx !== i));

  const fileIcon = (f) => {
    if (f.type?.startsWith('image/')) return <RiImageLine className="text-cyan-400" />;
    if (f.type === 'application/pdf')  return <RiFilePdf2Line className="text-red-400" />;
    if (f.type?.startsWith('audio/'))  return <RiMicLine className="text-green-400" />;
    return <HiPaperClip className="text-slate-400" />;
  };

  const busy = ['processing','generating'].includes(phase);

  return (
    <div className="flex flex-col h-full relative" {...getRootProps()}>
      <input {...getInputProps()} />

      {isDragActive && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-purple-900/80 backdrop-blur-sm border-2 border-dashed border-purple-400 rounded-xl m-2">
          <div className="text-center">
            <div className="text-5xl mb-2">📂</div>
            <p className="text-purple-200 font-semibold">Drop files here</p>
            <p className="text-purple-400 text-sm">Images · PDFs · Audio · Text</p>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-4">
        {idle && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 opacity-40">
            <div className="text-4xl mb-2 animate-float">🌐</div>
            <p className="text-slate-400 text-sm">Describe your idea below, or drop an image/document</p>
          </div>
        )}

        {messages.map((msg) => {
          if (msg.role === 'question' && msg.questions) {
            return (
              <div key={msg.id} className="animate-slide-up">
                <QuestionCard questions={msg.questions} knownInfo={knownInfo}
                  answers={answers} setAnswers={setAnswers}
                  onSubmit={() => { setSubmitted(true); onAnswers({ ...knownInfo, ...answers }); }}
                  submitted={submitted} />
              </div>
            );
          }

          return (
            <div key={msg.id} className={`flex gap-2.5 animate-slide-up ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role !== 'user' && (
                <div className="w-7 h-7 rounded-lg btn-primary flex-shrink-0 flex items-center justify-center text-xs mt-0.5">🌐</div>
              )}
              <div className={`max-w-[80%] px-4 py-3 text-sm leading-relaxed ${msg.role === 'user' ? 'bubble-user text-white' : 'bubble-agent text-slate-200'} ${msg.isError ? '!border-red-500/30 !bg-red-900/10' : ''}`}>
                {msg.files?.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {msg.files.map((f, i) => <span key={i} className="px-2 py-0.5 rounded-full bg-white/10 text-xs">📎 {f}</span>)}
                  </div>
                )}
                <MdText text={msg.content} />
              </div>
              {msg.role === 'user' && (
                <div className="w-7 h-7 rounded-lg bg-slate-700 flex-shrink-0 flex items-center justify-center text-xs mt-0.5">👤</div>
              )}
            </div>
          );
        })}

        {phase === 'generating' && !srsTokens && (
          <div className="flex gap-2.5 justify-start animate-slide-up">
            <div className="w-7 h-7 rounded-lg btn-primary flex-shrink-0 flex items-center justify-center text-xs">🌐</div>
            <div className="bubble-agent px-4 py-3">
              <span className="flex items-center gap-2 text-sm text-slate-400">
                <span className="flex gap-1">
                  {[0,150,300].map(d => <span key={d} className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-bounce" style={{ animationDelay:`${d}ms` }} />)}
                </span>
                DeepSeek generating IEEE SRS...
              </span>
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-white/5 shrink-0">
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {files.map((f, i) => (
              <div key={i} className="flex items-center gap-1.5 px-2 py-1 rounded-lg glass border border-white/10 text-xs">
                {fileIcon(f)}
                <span className="text-slate-300 max-w-[90px] truncate">{f.name}</span>
                <button onClick={() => removeFile(i)} className="text-slate-500 hover:text-red-400"><RiCloseLine /></button>
              </div>
            ))}
          </div>
        )}
        <div className="flex gap-2 items-end">
          <label className="w-8 h-8 rounded-xl glass glass-hover flex items-center justify-center cursor-pointer text-slate-400 hover:text-purple-400 transition-colors border border-white/5 shrink-0">
            <HiPaperClip />
            <input type="file" className="hidden" multiple accept="image/*,application/pdf,audio/*,text/plain"
              onChange={(e) => setFiles(p => [...p, ...Array.from(e.target.files)].slice(0, 5))} />
          </label>
          <textarea value={prompt} onChange={e => setPrompt(e.target.value)} onKeyDown={onKey}
            placeholder={idle ? 'e.g. "I want an app where people can order food from nearby restaurants"' : 'Type anything...'}
            disabled={busy || submitted} rows={1}
            className="flex-1 cosmic-input rounded-xl px-3 py-2 text-sm resize-none min-h-[36px] max-h-28" />
          <button onClick={send} disabled={busy || (!prompt.trim() && files.length === 0)}
            className="w-8 h-8 rounded-xl btn-primary flex items-center justify-center shrink-0 disabled:opacity-40">
            {busy
              ? <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              : <RiSendPlane2Line />}
          </button>
        </div>
        <p className="text-center text-slate-700 text-[10px] mt-1.5">
          You can also drag & drop an image, photo, PDF, or voice note
        </p>
      </div>
    </div>
  );
}

function MdText({ text }) {
  if (!text) return null;
  return (
    <span>
      {text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
        p.startsWith('**') && p.endsWith('**')
          ? <strong key={i} className="text-white font-semibold">{p.slice(2,-2)}</strong>
          : <span key={i}>{p}</span>
      )}
    </span>
  );
}
