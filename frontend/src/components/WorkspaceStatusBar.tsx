'use client';

const STATUS_COLORS: Record<string, string> = {
  pending: 'text-slate-400',
  planning: 'text-purple-400',
  generating: 'text-cyan-400',
  analyzing: 'text-green-400',
  running: 'text-amber-400',
  complete: 'text-green-400',
  error: 'text-red-400'
};

export function WorkspaceStatusBar({
  status,
  progress,
  stage
}: {
  status: string;
  progress: number;
  stage?: string;
}) {
  return (
    <div className="flex items-center gap-3 border-b border-[#1a1a2e] px-4 py-2">
      <div className={`text-xs font-medium capitalize ${STATUS_COLORS[status] || 'text-slate-400'}`}>
        {status}
      </div>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-[#1a1a2e]">
        <div className="progress-gradient h-full rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>
      <div className="w-24 text-right text-[11px] text-slate-500">{stage || status}</div>
    </div>
  );
}

export default WorkspaceStatusBar;
