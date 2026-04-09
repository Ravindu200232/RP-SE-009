'use client';

import { useEffect, useRef } from 'react';
import { RiTerminalBoxLine } from 'react-icons/ri';

const L = { info:'log-info', success:'log-success', warning:'log-warning', error:'log-error', thinking:'log-thinking' };
const P = { info:'○', success:'✓', warning:'⚠', error:'✗', thinking:'◎', agent:'◈' };
const PHASE_STATUS = {
  idle:       { label:'Idle',       dot:'bg-slate-600',  color:'text-slate-500' },
  processing: { label:'Processing', dot:'bg-blue-500 animate-pulse', color:'text-blue-400' },
  questions:  { label:'Collecting', dot:'bg-yellow-500', color:'text-yellow-400' },
  generating: { label:'Generating', dot:'bg-purple-500 animate-pulse', color:'text-purple-400' },
  complete:   { label:'Complete',   dot:'bg-green-500',  color:'text-green-400' },
};

export default function ExecutionLog({ logs = [], phase, compact = false }) {
  const endRef = useRef(null);
  const ps = PHASE_STATUS[phase] || PHASE_STATUS.idle;
  useEffect(() => { endRef.current?.scrollIntoView({ behavior:'smooth' }); }, [logs]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 shrink-0">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider">
          <RiTerminalBoxLine /> Execution Log
        </span>
        <span className={`flex items-center gap-1.5 text-xs ${ps.color}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${ps.dot}`} />{ps.label}
        </span>
      </div>

      {!compact && (
        <div className="grid grid-cols-3 gap-1 px-3 py-2 border-b border-white/5 shrink-0">
          <Stat label="Total"   value={logs.length}                                 color="text-slate-300" />
          <Stat label="OK"      value={logs.filter(l=>l.level==='success').length}  color="text-green-400" />
          <Stat label="Warn"    value={logs.filter(l=>l.level==='warning').length}  color="text-yellow-400" />
        </div>
      )}

      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-0.5 font-mono text-[11px]">
        {!logs.length && (
          <div className="text-slate-600 text-center py-8">
            <RiTerminalBoxLine className="text-2xl mx-auto mb-2 opacity-20" />
            <p>Waiting for activity...</p>
          </div>
        )}
        {logs.map((l, i) => (
          <div key={i} className={`flex gap-2 leading-relaxed animate-fade-in ${L[l.level]||'log-info'}`}>
            <span className="opacity-60 shrink-0">{P[l.level]||'○'}</span>
            <span className="break-all">{l.message}</span>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {logs.length > 0 && !compact && (
        <div className="px-3 py-1.5 border-t border-white/5 text-[10px] text-slate-600 shrink-0">
          Last: {new Date(logs[logs.length-1].timestamp).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="text-center">
      <div className={`text-sm font-bold ${color}`}>{value}</div>
      <div className="text-[9px] text-slate-600 uppercase tracking-wider">{label}</div>
    </div>
  );
}
