'use client';

import type { ArtifactAudit } from '@/types';

export function WorkspaceAuditPanel({ audit }: { audit?: ArtifactAudit }) {
  const services = Object.values(audit?.services || {});
  if (services.length === 0) {
    return <div className="p-4 text-sm text-slate-500">Artifact audits will appear after validation runs.</div>;
  }

  return (
    <div className="space-y-3 p-4">
      {services.map((serviceAudit) => (
        <div key={serviceAudit.service} className="rounded-xl border border-[#1a1a2e] bg-[#0f0f1a] p-4">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm font-semibold text-white">{serviceAudit.service}</div>
            <div className={`text-xs ${serviceAudit.missingFiles.length === 0 ? 'text-green-400' : 'text-amber-400'}`}>
              {serviceAudit.missingFiles.length === 0 ? 'Ready' : `${serviceAudit.missingFiles.length} missing`}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-[0.2em] text-slate-500">Expected</div>
              <pre className="overflow-auto text-[11px] text-slate-300">{serviceAudit.expectedFiles.join('\n') || 'None'}</pre>
            </div>
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-[0.2em] text-slate-500">Found</div>
              <pre className="overflow-auto text-[11px] text-slate-300">{serviceAudit.foundFiles.join('\n') || 'None'}</pre>
            </div>
            <div>
              <div className="mb-1 text-[11px] uppercase tracking-[0.2em] text-slate-500">Missing</div>
              <pre className="overflow-auto text-[11px] text-amber-300">{serviceAudit.missingFiles.join('\n') || 'None'}</pre>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default WorkspaceAuditPanel;
