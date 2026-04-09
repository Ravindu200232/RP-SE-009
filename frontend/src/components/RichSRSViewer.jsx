'use client';

import { useMemo, useState } from 'react';
import { RiCodeSSlashLine, RiDownloadLine, RiFileTextLine, RiGlobalLine } from 'react-icons/ri';
import RichPDFExporter from './RichPDFExporter';

const SECTION_THEMES = {
  introduction: { bg: 'from-blue-900/25 to-blue-800/5', border: 'border-blue-500/25', label: 'Introduction' },
  overall_description: { bg: 'from-cyan-900/25 to-cyan-800/5', border: 'border-cyan-500/25', label: 'Overall Description' },
  external_interface_requirements: { bg: 'from-indigo-900/25 to-indigo-800/5', border: 'border-indigo-500/25', label: 'Interfaces' },
  system_features: { bg: 'from-green-900/25 to-green-800/5', border: 'border-green-500/25', label: 'System Features' },
  other_nonfunctional_requirements: { bg: 'from-yellow-900/25 to-yellow-800/5', border: 'border-yellow-500/25', label: 'Nonfunctional Requirements' },
  other_requirements: { bg: 'from-pink-900/25 to-pink-800/5', border: 'border-pink-500/25', label: 'Other Requirements' },
  appendices: { bg: 'from-purple-900/25 to-purple-800/5', border: 'border-purple-500/25', label: 'Appendices' },
  services: { bg: 'from-indigo-900/25 to-indigo-800/5', border: 'border-indigo-500/25', label: 'Services' },
  quality_check: { bg: 'from-emerald-900/25 to-emerald-800/5', border: 'border-emerald-500/25', label: 'Quality Check' },
};

function formatLabel(value = '') {
  return String(value)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isEmptyNode(value) {
  if (value === null || value === undefined || value === '') {
    return true;
  }
  if (Array.isArray(value)) {
    return value.length === 0;
  }
  if (typeof value === 'object') {
    return Object.values(value).every((entry) => isEmptyNode(entry));
  }
  return false;
}

function PrimitiveValue({ value }) {
  return <p className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">{String(value)}</p>;
}

function RenderNode({ value, depth = 0 }) {
  if (isEmptyNode(value)) {
    return <p className="text-xs text-slate-500">Not provided</p>;
  }

  if (Array.isArray(value)) {
    if (value.every((entry) => typeof entry !== 'object')) {
      return (
        <div className="flex flex-wrap gap-2">
          {value.map((entry, index) => (
            <span key={`${entry}-${index}`} className="px-2 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-slate-300">
              {String(entry)}
            </span>
          ))}
        </div>
      );
    }

    return (
      <div className="space-y-3">
        {value.map((entry, index) => (
          <div key={index} className="rounded-xl bg-black/20 border border-white/5 p-3">
            <RenderNode value={entry} depth={depth + 1} />
          </div>
        ))}
      </div>
    );
  }

  if (typeof value === 'object') {
    return (
      <div className="space-y-3">
        {Object.entries(value)
          .filter(([, entryValue]) => !isEmptyNode(entryValue))
          .map(([key, entryValue]) => (
            <div key={key}>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-1">{formatLabel(key)}</div>
              <RenderNode value={entryValue} depth={depth + 1} />
            </div>
          ))}
      </div>
    );
  }

  return <PrimitiveValue value={value} />;
}

function SectionCard({ sectionKey, title, value }) {
  const theme = SECTION_THEMES[sectionKey] || SECTION_THEMES.introduction;

  return (
    <div className={`rounded-2xl bg-gradient-to-br ${theme.bg} border ${theme.border} overflow-hidden`}>
      <div className="px-4 py-2.5 border-b border-white/5">
        <h3 className="text-sm font-semibold text-white">{title || theme.label}</h3>
      </div>
      <div className="p-4">
        <RenderNode value={value} />
      </div>
    </div>
  );
}

function CoverCard({ srs }) {
  const metadata = srs?.metadata || {};
  const detailPairs = [
    ['Project ID', metadata.project_id || 'N/A'],
    ['Domain', metadata.domain || 'N/A'],
    ['Type', metadata.application_type || 'Web'],
    ['Version', metadata.version || '1.0'],
    ['Status', metadata.status || 'draft'],
    ['Created', metadata.date_created || new Date().toISOString().split('T')[0]],
    ['Updated', metadata.last_updated || metadata.date_created || new Date().toISOString().split('T')[0]],
    ['Author', metadata.author || 'AI'],
  ];

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: 'linear-gradient(135deg,#1a1040,#0d0d2e)', border: '1px solid rgba(124,58,237,0.3)' }}>
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-semibold uppercase">IEEE SRS Standard</span>
              <span className="px-2.5 py-0.5 rounded-full bg-green-500/20 text-green-300 text-[10px] font-semibold uppercase">{metadata.status || 'draft'}</span>
              {srs?.quality_check?.status && (
                <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-semibold uppercase">
                  Recheck: {srs.quality_check.status}
                </span>
              )}
              {typeof srs?.quality_check?.pdf_ready === 'boolean' && (
                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase ${srs.quality_check.pdf_ready ? 'bg-cyan-500/20 text-cyan-300' : 'bg-amber-500/20 text-amber-300'}`}>
                  PDF: {srs.quality_check.pdf_ready ? 'ready' : 'review'}
                </span>
              )}
              {typeof srs?.quality_check?.json_ready === 'boolean' && (
                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase ${srs.quality_check.json_ready ? 'bg-blue-500/20 text-blue-300' : 'bg-amber-500/20 text-amber-300'}`}>
                  JSON: {srs.quality_check.json_ready ? 'ready' : 'review'}
                </span>
              )}
            </div>
            <h2 className="text-xl font-display font-bold text-white mb-1">{metadata.project_name || 'Software Requirements Specification'}</h2>
            <p className="text-slate-400 text-sm">
              {metadata.domain || 'General'} | {metadata.application_type || 'Web'} | v{metadata.version || '1.0'}
            </p>
          </div>
          <span className="text-4xl opacity-50">SRS</span>
        </div>

        <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-2">
          {detailPairs.map(([label, value]) => (
            <div key={label} className="bg-white/5 rounded-lg px-3 py-2">
              <div className="text-[9px] text-slate-500 uppercase tracking-wider">{label}</div>
              <div className="text-xs text-slate-200 font-medium mt-0.5 truncate">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function RichSRSViewer({ srs, tokens, phase, sessionId }) {
  const [view, setView] = useState('visual');

  const visualSections = useMemo(() => {
    if (!srs) {
      return [];
    }

    return [
      ['quality_check', 'Quality Check', srs.quality_check],
      ['introduction', 'Introduction', srs.sections?.introduction],
      ['overall_description', 'Overall Description', srs.sections?.overall_description],
      ['external_interface_requirements', 'External Interface Requirements', srs.sections?.external_interface_requirements],
      ['system_features', 'System Features', srs.sections?.system_features],
      ['other_nonfunctional_requirements', 'Other Nonfunctional Requirements', srs.sections?.other_nonfunctional_requirements],
      ['other_requirements', 'Other Requirements', srs.sections?.other_requirements],
      ['appendices', 'Appendices', srs.appendices],
      ['services', 'Services', srs.services],
    ].filter(([, , value]) => !isEmptyNode(value));
  }, [srs]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5 shrink-0">
        <div className="flex items-center gap-2">
          <RiFileTextLine className="text-slate-400 text-sm" />
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">IEEE SRS Document</span>
          {phase === 'complete' && <span className="px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 text-[10px] font-semibold">COMPLETE</span>}
          {phase === 'generating' && <span className="px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 text-[10px] font-semibold animate-pulse">GENERATING</span>}
        </div>

        <div className="flex items-center gap-2">
          <div className="flex rounded-lg overflow-hidden border border-white/10">
            {['visual', 'json'].map((mode) => (
              <button
                key={mode}
                onClick={() => setView(mode)}
                className={`px-2.5 py-1 text-xs transition-all flex items-center gap-1 ${view === mode ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white'}`}
              >
                {mode === 'visual' ? <><RiGlobalLine /> Visual</> : <><RiCodeSSlashLine /> JSON</>}
              </button>
            ))}
          </div>

          {phase === 'complete' && srs && (
            <div className="flex gap-1.5">
              <RichPDFExporter srs={srs} />
              <a
                href={`http://localhost:3200/api/srs/download/${sessionId}`}
                download
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg glass glass-hover text-xs text-cyan-400 border border-cyan-500/20 transition-all"
              >
                <RiDownloadLine /> JSON
              </a>
            </div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {!srs && !tokens && (
          <div className="flex flex-col items-center justify-center h-full opacity-30 text-center p-8">
            <div className="text-5xl mb-3 animate-float">SRS</div>
            <p className="text-slate-400 text-sm">The full IEEE SRS appears here after generation and recheck.</p>
          </div>
        )}

        {tokens && !srs && (
          <div className="p-4">
            <div className="glass rounded-xl p-4 border border-purple-500/20">
              <div className="flex items-center gap-2 mb-3">
                <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
                <span className="text-xs text-purple-400 font-medium">DeepSeek generating and rechecking the IEEE SRS...</span>
              </div>
              <pre className="text-[10px] text-slate-400 font-mono whitespace-pre-wrap break-all max-h-[70vh] overflow-y-auto scrollbar-thin leading-relaxed">
                {tokens}
                <span className="animate-pulse text-purple-400">|</span>
              </pre>
            </div>
          </div>
        )}

        {srs && view === 'visual' && (
          <div className="p-4 space-y-4">
            <CoverCard srs={srs} />
            {visualSections.map(([sectionKey, title, value]) => (
              <SectionCard key={sectionKey} sectionKey={sectionKey} title={title} value={value} />
            ))}
            <div className="text-center py-3 text-[10px] text-slate-600">
              Generated by SRS Maker Agent | DeepSeek question planning | template recheck complete
            </div>
          </div>
        )}

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
