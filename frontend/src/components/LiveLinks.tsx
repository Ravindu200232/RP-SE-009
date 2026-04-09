'use client';
import { ExternalLink, Globe, Server, Copy, Check } from 'lucide-react';
import { useState } from 'react';
import { AllUrls } from '@/types';

interface LiveLinksProps {
  urls: AllUrls | null;
  services: { name: string; port: number; status: string; url?: string }[];
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button onClick={copy} className="p-1 hover:bg-white/10 rounded text-slate-500 hover:text-slate-300 transition-colors">
      {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
    </button>
  );
}

function LinkRow({ label, url, highlight }: { label: string; url: string; highlight?: boolean }) {
  return (
    <div className={`flex items-center gap-3 p-2.5 rounded-lg border transition-all ${
      highlight ? 'border-purple-500/30 bg-purple-500/5' : 'border-[#1a1a2e] bg-[#0f0f1a]'
    }`}>
      <div className={`w-1.5 h-1.5 rounded-full ${highlight ? 'bg-purple-400' : 'bg-green-400'} status-running`} />
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-slate-500 font-medium">{label}</div>
        <div className={`text-xs font-mono truncate ${highlight ? 'text-purple-300' : 'text-slate-300'}`}>{url}</div>
      </div>
      <CopyButton text={url} />
      <a href={url} target="_blank" rel="noopener noreferrer"
        className="p-1 hover:bg-white/10 rounded text-slate-500 hover:text-slate-300 transition-colors">
        <ExternalLink size={12} />
      </a>
    </div>
  );
}

export function LiveLinks({ urls, services }: LiveLinksProps) {
  if (!urls && services.filter(s => s.status === 'running').length === 0) {
    return (
      <div className="p-4 text-center text-slate-600 text-xs">
        <Globe size={20} className="mx-auto mb-2 opacity-30" />
        Live links will appear when services start
      </div>
    );
  }

  return (
    <div className="p-3 space-y-2 overflow-y-auto">
      {/* Primary gateway URL */}
      {urls?.gateway && (
        <div>
          <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wider mb-1.5 flex items-center gap-1">
            <Globe size={10} />
            Main Application
          </div>
          <LinkRow label="API Gateway (All Services)" url={urls.gateway} highlight />
          {urls.frontend && <LinkRow label="Frontend (Direct)" url={urls.frontend} />}
        </div>
      )}

      {/* API Routes via Gateway */}
      {urls?.apiRoutes && urls.apiRoutes.length > 0 && (
        <div>
          <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wider mb-1.5 flex items-center gap-1 mt-2">
            <Server size={10} />
            API Routes (via Gateway)
          </div>
          {urls.apiRoutes.map((route, i) => (
            <LinkRow
              key={i}
              label={`${route.prefix}`}
              url={route.viaGateway || `http://localhost:8080${route.prefix}`}
            />
          ))}
        </div>
      )}

      {/* Individual service URLs */}
      {services.filter(s => s.status === 'running' && s.url).length > 0 && (
        <div>
          <div className="text-[10px] text-slate-500 font-medium uppercase tracking-wider mb-1.5 mt-2">
            Direct Service URLs
          </div>
          {services.filter(s => s.status === 'running' && s.url).map((svc, i) => (
            <LinkRow key={i} label={svc.name} url={svc.url!} />
          ))}
        </div>
      )}

      {/* Failed services */}
      {services.filter(s => s.status === 'error').map((svc, i) => (
        <div key={i} className="flex items-center gap-2 p-2 rounded-lg border border-red-500/20 bg-red-500/5 text-xs">
          <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
          <span className="text-red-400">{svc.name} — failed to start</span>
        </div>
      ))}
    </div>
  );
}
