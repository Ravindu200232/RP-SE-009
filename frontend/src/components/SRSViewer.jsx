'use client';

import { useRef, useState } from 'react';
import { RiDownloadLine, RiCodeSSlashLine, RiFileTextLine, RiGlobalLine } from 'react-icons/ri';
import PDFExporter from './PDFExporter';

const THEMES = {
  intro:    { bg:'from-blue-900/25 to-blue-800/5',    border:'border-blue-500/25',    icon:'📖', label:'Introduction' },
  features: { bg:'from-green-900/25 to-green-800/5',  border:'border-green-500/25',   icon:'⚡', label:'System Features' },
  nfr:      { bg:'from-yellow-900/25 to-yellow-800/5',border:'border-yellow-500/25',  icon:'📊', label:'Non-Functional Req.' },
  security: { bg:'from-red-900/25 to-red-800/5',      border:'border-red-500/25',     icon:'🔐', label:'Security' },
  ifaces:   { bg:'from-cyan-900/25 to-cyan-800/5',    border:'border-cyan-500/25',    icon:'🔌', label:'Interfaces' },
  services: { bg:'from-indigo-900/25 to-indigo-800/5',border:'border-indigo-500/25',  icon:'🌐', label:'Microservices' },
  other:    { bg:'from-pink-900/25 to-pink-800/5',    border:'border-pink-500/25',    icon:'📋', label:'Other' },
};

const FEAT_COLORS = ['text-green-400','text-cyan-400','text-blue-400','text-purple-400','text-yellow-400','text-pink-400'];
const PRIORITY_STYLE = {
  High:   'bg-red-500/20 text-red-300 border-red-500/30',
  Medium: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  Low:    'bg-slate-500/20 text-slate-300 border-slate-500/30',
};
const METHOD_COLOR = { GET:'text-green-400', POST:'text-blue-400', PUT:'text-yellow-400', DELETE:'text-red-400', PATCH:'text-orange-400' };

export default function SRSViewer({ srs, tokens, phase, sessionId }) {
  const [view, setView] = useState('visual');
  const viewerRef = useRef(null);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-2">
          <RiFileTextLine className="text-slate-400 text-sm" />
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">IEEE SRS Document</span>
          {phase === 'complete'   && <span className="px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 text-[10px] font-semibold">COMPLETE</span>}
          {phase === 'generating' && <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 text-[10px] font-semibold animate-pulse">GENERATING</span>}
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg overflow-hidden border border-white/10">
            {['visual','json'].map(v => (
              <button key={v} onClick={() => setView(v)}
                className={`px-2.5 py-1 text-xs transition-all flex items-center gap-1 ${view===v ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white'}`}>
                {v === 'visual' ? <><RiGlobalLine /> Visual</> : <><RiCodeSSlashLine /> JSON</>}
              </button>
            ))}
          </div>
          {phase === 'complete' && srs && (
            <div className="flex gap-1.5">
              <PDFExporter srs={srs} viewerRef={viewerRef} />
              <a href={`http://localhost:3200/api/srs/download/${sessionId}`} download
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg glass glass-hover text-xs text-cyan-400 border border-cyan-500/20 transition-all">
                <RiDownloadLine /> JSON
              </a>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {/* Empty */}
        {!srs && !tokens && (
          <div className="flex flex-col items-center justify-center h-full opacity-30 text-center p-8">
            <div className="text-5xl mb-3 animate-float">📋</div>
            <p className="text-slate-400 text-sm">IEEE SRS appears here after generation</p>
          </div>
        )}

        {/* Live token stream */}
        {tokens && !srs && (
          <div className="p-4">
            <div className="glass rounded-xl p-4 border border-purple-500/20">
              <div className="flex items-center gap-2 mb-3">
                <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
                <span className="text-xs text-purple-400 font-medium">DeepSeek generating IEEE SRS...</span>
              </div>
              <pre className="text-[10px] text-slate-400 font-mono whitespace-pre-wrap break-all max-h-[70vh] overflow-y-auto scrollbar-thin leading-relaxed">
                {tokens}<span className="animate-pulse text-purple-400">▋</span>
              </pre>
            </div>
          </div>
        )}

        {/* Visual */}
        {srs && view === 'visual' && (
          <div ref={viewerRef} className="p-4 space-y-4" id="srs-doc">
            {/* Cover */}
            <div className="rounded-2xl overflow-hidden" style={{ background:'linear-gradient(135deg,#1a1040,#0d0d2e)', border:'1px solid rgba(124,58,237,0.3)' }}>
              <div className="p-5">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-semibold uppercase">IEEE SRS Standard</span>
                      <span className="px-2.5 py-0.5 rounded-full bg-green-500/20 text-green-300 text-[10px] font-semibold uppercase">{srs.metadata?.status||'draft'}</span>
                    </div>
                    <h2 className="text-xl font-display font-bold text-white mb-1">{srs.metadata?.project_name||'Software Requirements Specification'}</h2>
                    <p className="text-slate-400 text-sm">{srs.metadata?.domain} · {srs.metadata?.application_type} · v{srs.metadata?.version||'1.0'}</p>
                  </div>
                  <span className="text-4xl opacity-50">🌐</span>
                </div>
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {[['Author',srs.metadata?.author||'AI'],['Org',srs.metadata?.organization||'—'],
                    ['Created',srs.metadata?.date_created||new Date().toLocaleDateString()],['Lang',srs.metadata?.language||'en']
                  ].map(([l,v]) => (
                    <div key={l} className="bg-white/5 rounded-lg px-3 py-2">
                      <div className="text-[9px] text-slate-500 uppercase tracking-wider">{l}</div>
                      <div className="text-xs text-slate-200 font-medium mt-0.5 truncate">{v}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Introduction */}
            {srs.sections?.introduction && (
              <Section theme={THEMES.intro}>
                {srs.sections.introduction.purpose && <p className="text-sm text-slate-300 leading-relaxed mb-3">{srs.sections.introduction.purpose}</p>}
                {srs.sections.introduction.product_scope?.goals?.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {srs.sections.introduction.product_scope.goals.map((g,i) => (
                      <span key={i} className="px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-300 text-xs border border-blue-500/20">🎯 {g}</span>
                    ))}
                  </div>
                )}
              </Section>
            )}

            {/* Features */}
            {srs.sections?.system_features?.length > 0 && (
              <Section theme={THEMES.features} title={`System Features (${srs.sections.system_features.length})`}>
                <div className="space-y-3">
                  {srs.sections.system_features.map((f,i) => <FeatureBlock key={i} feature={f} index={i} />)}
                </div>
              </Section>
            )}

            {/* NFR */}
            {srs.sections?.other_nonfunctional_requirements && (
              <Section theme={THEMES.nfr}>
                <div className="space-y-2">
                  {srs.sections.other_nonfunctional_requirements.performance_requirements?.slice(0,2).map((r,i) => (
                    <div key={i} className="flex gap-2 text-xs">
                      <span className="text-yellow-400 font-mono shrink-0">{r.requirement_id}</span>
                      <span className="text-slate-300">{r.description}</span>
                    </div>
                  ))}
                  {srs.sections.other_nonfunctional_requirements.software_quality_attributes?.slice(0,4).map((qa,i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-300 text-[10px] border border-yellow-500/20">{qa.attribute_name}</span>
                      <span className="text-xs text-slate-400">{qa.description}</span>
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Microservices */}
            {srs.services?.length > 0 && (
              <Section theme={THEMES.services} title={`Microservices (${srs.services.length})`}>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {srs.services.map((svc,i) => <ServiceBlock key={i} service={svc} />)}
                </div>
              </Section>
            )}

            <div className="text-center py-3 text-[10px] text-slate-600">
              Generated by SRS Maker Agent · MiniCPM-O 4.5 + DeepSeek V3 · {new Date().toLocaleDateString()}
            </div>
          </div>
        )}

        {/* JSON raw */}
        {srs && view === 'json' && (
          <div className="p-4">
            <pre className="text-[10px] font-mono text-slate-300 whitespace-pre-wrap break-all bg-black/30 rounded-xl p-4 border border-white/5 leading-relaxed">
              {JSON.stringify(srs, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ theme, title, children }) {
  return (
    <div className={`rounded-2xl bg-gradient-to-br ${theme.bg} border ${theme.border} overflow-hidden`}>
      <div className="px-4 py-2.5 border-b border-white/5 flex items-center gap-2">
        <span>{theme.icon}</span>
        <h3 className="text-sm font-semibold text-white">{title || theme.label}</h3>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function FeatureBlock({ feature, index }) {
  const color = FEAT_COLORS[index % FEAT_COLORS.length];
  const reqs = feature.functional_requirements || [];
  const p = feature.description_and_priority?.priority || 'Medium';
  return (
    <div className="glass rounded-xl p-3 border border-white/5">
      <div className="flex items-start gap-2 mb-2">
        <span className={`text-xs font-mono font-bold ${color} mt-0.5 shrink-0`}>{feature.feature_id||`F-${index+1}`}</span>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-white truncate">{feature.feature_name}</h4>
          <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{feature.description_and_priority?.description}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium border ${PRIORITY_STYLE[p]||PRIORITY_STYLE.Medium}`}>{p}</span>
            {reqs.length > 0 && <span className="text-[10px] text-slate-500">{reqs.length} req.</span>}
          </div>
        </div>
      </div>
      {reqs.slice(0,3).map((r,i) => (
        <div key={i} className="flex gap-2 text-[11px] mt-1">
          <span className="text-slate-600 font-mono shrink-0">{r.requirement_id}</span>
          <span className="text-slate-400 line-clamp-1">{r.description||r.title}</span>
        </div>
      ))}
      {reqs.length > 3 && <div className="text-[10px] text-slate-600 mt-1">+{reqs.length-3} more</div>}
    </div>
  );
}

function ServiceBlock({ service }) {
  return (
    <div className="glass rounded-xl p-3 border border-indigo-500/20">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs font-mono font-bold text-indigo-300">{service.name}</span>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">:{service.port}</span>
      </div>
      <p className="text-xs text-slate-400 mb-2 line-clamp-2">{service.description}</p>
      {service.endpoints?.slice(0,4).map((ep,i) => (
        <div key={i} className="flex gap-2 text-[10px] font-mono mb-0.5">
          <span className={`font-bold shrink-0 ${METHOD_COLOR[ep.method]||'text-slate-400'}`}>{ep.method}</span>
          <span className="text-slate-500 truncate">{ep.path}</span>
        </div>
      ))}
      {service.entities?.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {service.entities.map((e,i) => <span key={i} className="px-1.5 py-0.5 rounded bg-white/5 text-[10px] text-slate-400">📦 {e}</span>)}
        </div>
      )}
    </div>
  );
}
