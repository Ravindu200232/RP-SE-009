'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { io } from 'socket.io-client';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';
import { RiRobot2Line, RiGlobalLine, RiBrainLine } from 'react-icons/ri';
import { HiSparkles } from 'react-icons/hi2';
import ChatInterface from './VoiceChatInterface';
import ExecutionLog from './ExecutionLog';
import SRSViewer from './RichSRSViewer';

const BACKEND = 'http://localhost:3200';

const PHASE = {
  IDLE:       'idle',
  PROCESSING: 'processing',
  QUESTIONS:  'questions',
  GENERATING: 'generating',
  COMPLETE:   'complete',
};

// Random stars (memoised so they don't re-render)
const STARS = Array.from({ length: 55 }, (_, i) => ({
  id: i,
  x: (i * 37.3) % 100,
  y: (i * 53.7) % 100,
  size: (i % 3) + 1,
  dur: ((i % 4) + 2).toFixed(1),
  del: ((i % 3) * 0.7).toFixed(1),
}));

export default function SRSMakerPage() {
  const [phase, setPhase]             = useState(PHASE.IDLE);
  const [sessionId, setSessionId]     = useState(null);
  const [messages, setMessages]       = useState([]);
  const [logs, setLogs]               = useState([]);
  const [questions, setQuestions]     = useState([]);
  const [knownInfo, setKnownInfo]     = useState({});
  const [srs, setSrs]                 = useState(null);
  const [srsTokens, setSrsTokens]     = useState('');
  const [activePanel, setActivePanel] = useState('chat');
  const socketRef = useRef(null);

  // ── Socket.IO ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const socket = io(BACKEND, { transports: ['websocket', 'polling'] });
    socketRef.current = socket;

    socket.on('log',        (e) => setLogs(p => [...p, e]));
    socket.on('srs:token',  ({ token }) => setSrsTokens(p => p + token));
    socket.on('srs:complete', ({ srs }) => {
      setSrs(srs);
      setPhase(PHASE.COMPLETE);
      setSrsTokens('');
      addMsg('agent', '🎉 Your **app plan is ready!** You can view all the details in the panel on the right, or download it as a PDF.');
      toast.success('IEEE SRS generated!');
    });

    return () => socket.disconnect();
  }, []);

  const joinSession = useCallback((sid) => socketRef.current?.emit('join:session', sid), []);

  const addMsg = useCallback((role, content, extra = {}) =>
    setMessages(p => [...p, { id: Date.now() + Math.random(), role, content, ...extra, ts: new Date().toISOString() }])
  , []);

  // ── Start ─────────────────────────────────────────────────────────────────
  const handleStart = useCallback(async (prompt, files) => {
    setPhase(PHASE.PROCESSING);
    setLogs([]); setSrs(null); setSrsTokens(''); setQuestions([]);

    addMsg('user', prompt || `[${files.length} file(s) uploaded]`, { files: files.map(f => f.name) });
    addMsg('agent', '👋 Got it! Let me read through everything you shared...');

    try {
      const { data: { sessionId: sid } } = await axios.post(`${BACKEND}/api/srs/session`);
      setSessionId(sid);
      joinSession(sid);

      const form = new FormData();
      form.append('sessionId', sid);
      form.append('prompt', prompt || '');
      files.forEach(f => form.append('files', f));

      const { data } = await axios.post(`${BACKEND}/api/srs/start`, form);
      setKnownInfo(data.knownInfo || {});

      const qCount = data.questions?.length || 0;
      addMsg('agent',
        `✅ **I understood your idea!** ${data.summary}\n\n${qCount > 0 ? `I just need to ask you **${qCount} quick question${qCount > 1 ? 's' : ''}** to get everything right. No tech knowledge needed! 😊` : '🚀 I have everything I need — building your app plan now!'}`
      );

      if (qCount > 0) {
        setQuestions(data.questions);
        setPhase(PHASE.QUESTIONS);
        addMsg('question', null, { questions: data.questions, knownInfo: data.knownInfo });
      } else {
        await doGenerate(sid, data.knownInfo || {});
      }
    } catch (err) {
      toast.error(err.response?.data?.error || err.message);
      addMsg('agent', `❌ Error: ${err.message}`, { isError: true });
      setPhase(PHASE.IDLE);
    }
  }, [addMsg, joinSession]);

  // ── Answer questions ──────────────────────────────────────────────────────
  const handleAnswers = useCallback(async (answers) => {
    const sid = sessionId;
    if (!sid) return;
    const summary = Object.entries(answers).map(([k, v]) => `**${k}:** ${Array.isArray(v) ? v.join(', ') : v}`).join('\n');
    addMsg('user', summary);
    addMsg('agent', '✅ Perfect! I have everything I need.\n\n🏗️ Now building your **complete app specification**... This takes about a minute, grab a coffee! ☕');
    setPhase(PHASE.GENERATING);
    setActivePanel('srs');
    await doGenerate(sid, { ...knownInfo, ...answers });
  }, [sessionId, knownInfo, addMsg]);

  const doGenerate = async (sid, answers) => {
    try {
      setPhase(PHASE.GENERATING);
      await axios.post(`${BACKEND}/api/srs/answer`, { sessionId: sid, answers });
    } catch (err) {
      toast.error(err.response?.data?.error || err.message);
      addMsg('agent', `❌ Generation error: ${err.message}`, { isError: true });
      setPhase(PHASE.IDLE);
    }
  };

  const handleReset = () => {
    setPhase(PHASE.IDLE); setSessionId(null); setMessages([]); setLogs([]);
    setQuestions([]); setKnownInfo({}); setSrs(null); setSrsTokens(''); setActivePanel('chat');
  };

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col" style={{ background: '#03030F' }}>
      <Toaster position="top-right" toastOptions={{ style: { background: '#0F0F3D', color: '#E2E8F0', border: '1px solid rgba(124,58,237,0.3)' } }} />

      {/* ── Stars ── */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
        {STARS.map(s => (
          <div key={s.id} className="absolute rounded-full bg-white star"
            style={{ left:`${s.x}%`, top:`${s.y}%`, width:s.size, height:s.size, '--dur':`${s.dur}s`, '--del':`${s.del}s` }} />
        ))}
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(ellipse at 15% 25%,rgba(124,58,237,.12) 0%,transparent 45%),radial-gradient(ellipse at 85% 75%,rgba(37,99,235,.1) 0%,transparent 45%)'
        }} />
      </div>

      {/* ── Header ── */}
      <header className="relative z-10 flex items-center justify-between px-5 py-3 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl btn-primary flex items-center justify-center text-lg shrink-0">🌐</div>
          <div>
            <p className="font-display font-bold text-white text-sm leading-none">SRS Maker Agent</p>
            <p className="text-[10px] text-slate-500 mt-0.5">Turn your idea into a complete app plan — no tech skills needed</p>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-2">
          {[
            { icon: <RiBrainLine />, label: 'MiniCPM-O 4.5', color: 'text-purple-400 border-purple-500/20' },
            { icon: <RiRobot2Line />, label: 'DeepSeek V3',   color: 'text-blue-400 border-blue-500/20' },
            { icon: <RiGlobalLine />, label: 'Local Ollama',  color: 'text-cyan-400 border-cyan-500/20' },
          ].map(({ icon, label, color }) => (
            <span key={label} className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full glass text-xs font-medium border ${color}`}>
              {icon} {label}
            </span>
          ))}
        </div>

        <div className="flex items-center gap-2">
          {phase !== PHASE.IDLE && (
            <div className="flex rounded-lg overflow-hidden border border-white/10">
              {['chat','srs'].map(p => (
                <button key={p} onClick={() => setActivePanel(p)}
                  className={`px-3 py-1.5 text-xs font-medium transition-all ${activePanel === p ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5'}`}>
                  {p === 'chat' ? 'Chat' : `SRS ${srs ? '✓' : ''}`}
                </button>
              ))}
            </div>
          )}
          {phase !== PHASE.IDLE && (
            <button onClick={handleReset} className="px-3 py-1.5 rounded-lg glass glass-hover text-xs text-slate-400 hover:text-white transition-all">
              New Session
            </button>
          )}
        </div>
      </header>

      {/* ── Idle hero ── */}
      {phase === PHASE.IDLE && (
        <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 pb-8 overflow-y-auto">
          <div className="text-center mb-8 animate-fade-in">
            <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full glass border border-yellow-500/20 text-yellow-400 text-xs font-semibold mb-5">
              <HiSparkles /> Agent 1 — SRS JSON Maker
            </span>
            <h1 className="text-5xl md:text-6xl font-display font-bold text-white mb-4 leading-tight">
              Dream, <span className="gradient-text">Describe,</span><br />Generate SRS
            </h1>
            <p className="text-slate-400 text-lg max-w-xl mx-auto">
              Just tell us your idea in plain words — or upload a photo, voice note, or document.<br />
              Our AI will ask a few simple questions and build your <span className="text-purple-400 font-medium">full app plan</span>.
            </p>
            <div className="flex flex-wrap gap-2 justify-center mt-5">
              {['🖼️ Upload a photo','🎤 Voice note','📄 PDF document','✍️ Type your idea','🤖 AI understands it','❓ Quick questions','📋 Full app plan','📥 Download PDF'].map(f => (
                <span key={f} className="px-3 py-1 rounded-full glass text-xs text-slate-300 border border-white/5">{f}</span>
              ))}
            </div>
          </div>
          <div className="w-full max-w-2xl">
            <ChatInterface phase={phase} messages={[]} questions={[]} onStart={handleStart} onAnswers={handleAnswers} idle />
          </div>
        </div>
      )}

      {/* ── Active session layout ── */}
      {phase !== PHASE.IDLE && (
        <div className="relative z-10 flex-1 flex overflow-hidden">
          {/* Chat panel */}
          <div className={`flex flex-col overflow-hidden transition-all ${activePanel === 'srs' ? 'hidden lg:flex lg:w-[30%]' : 'flex-1 lg:w-[30%]'}`}>
            <ChatInterface phase={phase} messages={messages} questions={questions} knownInfo={knownInfo}
              onStart={handleStart} onAnswers={handleAnswers} srsTokens={srsTokens} />
          </div>

          {/* SRS Viewer */}
          <div className={`flex flex-col border-l border-white/5 transition-all ${activePanel === 'srs' ? 'flex-1' : 'hidden lg:flex lg:flex-1'}`}>
            <SRSViewer srs={srs} tokens={srsTokens} phase={phase} sessionId={sessionId} />
          </div>

          {/* Execution Log */}
          <div className="hidden xl:flex flex-col w-64 border-l border-white/5 shrink-0">
            <ExecutionLog logs={logs} phase={phase} />
          </div>
        </div>
      )}

      {/* Mobile log bubble */}
      {phase !== PHASE.IDLE && logs.length > 0 && (
        <div className="xl:hidden fixed bottom-4 right-4 z-50">
          <details>
            <summary className="btn-primary px-3 py-2 rounded-xl cursor-pointer text-xs font-semibold list-none">
              ⚡ {logs.length} logs
            </summary>
            <div className="absolute bottom-10 right-0 w-72 max-h-80 glass border border-white/10 rounded-xl overflow-hidden">
              <ExecutionLog logs={logs} phase={phase} compact />
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
