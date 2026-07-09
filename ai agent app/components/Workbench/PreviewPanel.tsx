'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Play,
  RefreshCw,
  ExternalLink,
  Loader2,
  TriangleAlert,
  Square,
} from 'lucide-react';
import { useBuilder } from '@/lib/store';

interface PageCheck {
  route: string;
  status: number;
  ok: boolean;
  fixed: string[];
}

interface PreviewStatus {
  phase: 'idle' | 'installing' | 'starting' | 'ready' | 'error' | 'stopped';
  port: number;
  url: string;
  logs: string[];
  error?: string;
  fixing?: boolean;
  pageChecks?: PageCheck[];
}

function LogBox({ logs }: { logs: string[] }) {
  const ref = useRef<HTMLPreElement>(null);
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight });
  }, [logs]);
  if (!logs?.length) return null;
  return (
    <pre
      ref={ref}
      className="mt-2 max-h-44 w-full max-w-lg overflow-auto rounded-lg border border-border bg-bg-soft p-2.5 text-left font-mono text-[11px] leading-4 text-text-muted"
    >
      {logs.slice(-60).join('\n')}
    </pre>
  );
}

export function PreviewPanel() {
  const projectId = useBuilder((s) => s.projectId);
  const autoPreviewToken = useBuilder((s) => s.autoPreviewToken);
  const [status, setStatus] = useState<PreviewStatus | null>(null);
  const [iframeKey, setIframeKey] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastAutoPreview = useRef(0);
  const wasFixing = useRef(false);
  const shownIframe = useRef(false);

  const stopPolling = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  };

  const fetchStatus = async (id: string) => {
    const s = (await fetch(`/api/preview/${id}`, { cache: 'no-store' }).then((r) =>
      r.json(),
    )) as PreviewStatus;
    setStatus(s);
    return s;
  };

  useEffect(() => {
    stopPolling();
    setStatus(null);
    if (projectId) void fetchStatus(projectId);
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const startPolling = () => {
    stopPolling();
    shownIframe.current = false;
    wasFixing.current = false;
    pollRef.current = setInterval(async () => {
      if (!projectId) return;
      const s = await fetchStatus(projectId);
      if (s.phase === 'ready') {
        // Show the iframe as soon as the server is up…
        if (!shownIframe.current) {
          shownIframe.current = true;
          setIframeKey((k) => k + 1);
        }
        // …but keep polling while the terminal bug-fixer walks the pages, so
        // its live progress shows. Reload the iframe once it finishes (fixes
        // changed files on disk) and then stop.
        if (s.fixing) {
          wasFixing.current = true;
        } else {
          if (wasFixing.current) setIframeKey((k) => k + 1);
          stopPolling();
        }
      } else if (s.phase === 'error' || s.phase === 'stopped') {
        stopPolling();
      }
    }, 1500);
  };

  const start = async () => {
    if (!projectId) return;
    const s = (await fetch(`/api/preview/${projectId}`, { method: 'POST' }).then((r) =>
      r.json(),
    )) as PreviewStatus;
    setStatus(s);
    startPolling();
  };

  const stop = async () => {
    if (!projectId) return;
    stopPolling();
    await fetch(`/api/preview/${projectId}`, { method: 'DELETE' });
    void fetchStatus(projectId);
  };

  useEffect(() => {
    if (!projectId || autoPreviewToken === 0) return;
    if (lastAutoPreview.current === autoPreviewToken) return;
    lastAutoPreview.current = autoPreviewToken;
    void start();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, autoPreviewToken]);

  const phase = status?.phase ?? 'idle';
  const running = phase === 'ready';
  const busy = phase === 'installing' || phase === 'starting';
  const fixing = !!status?.fixing;
  const checks = status?.pageChecks ?? [];
  const goodPages = checks.filter((c) => c.ok).length;
  const autofixLogs = (status?.logs ?? []).filter((l) => l.includes('[autofix]'));

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-9 shrink-0 items-center justify-between border-b border-border bg-bg-soft px-3 text-xs">
        {running ? (
          <span className="truncate font-mono text-text-muted">{status?.url}</span>
        ) : (
          <span className="text-text-muted">Live preview</span>
        )}
        <div className="flex items-center gap-1.5">
          {running && (
            <>
              <button
                onClick={() => setIframeKey((k) => k + 1)}
                title="Reload preview"
                className="text-text-faint transition hover:text-text"
              >
                <RefreshCw size={13} />
              </button>
              <a
                href={status?.url}
                target="_blank"
                rel="noreferrer"
                title="Open in new tab"
                className="text-text-faint transition hover:text-text"
              >
                <ExternalLink size={13} />
              </a>
              <button
                onClick={stop}
                className="flex items-center gap-1 rounded border border-border px-2 py-0.5 text-text-muted transition hover:text-rose-500"
              >
                <Square size={11} className="fill-current" /> Stop
              </button>
            </>
          )}
        </div>
      </div>

      {running && (fixing || checks.length > 0) && (
        <div className="shrink-0 border-b border-border bg-bg-soft px-3 py-1.5 text-[11px]">
          <div className="flex items-center gap-2 text-text-muted">
            {fixing ? (
              <>
                <Loader2 size={12} className="animate-spin text-accent" />
                <span>
                  Terminal bug-fixer running · {goodPages}/{checks.length || '…'} pages OK
                </span>
              </>
            ) : (
              <span className="text-emerald-500">
                ✓ Terminal bug-fixer done · {goodPages}/{checks.length} pages OK
              </span>
            )}
          </div>
          {fixing && autofixLogs.length > 0 && (
            <pre className="mt-1 max-h-20 overflow-auto font-mono text-[10px] leading-4 text-text-faint">
              {autofixLogs.slice(-6).join('\n')}
            </pre>
          )}
        </div>
      )}

      <div className="relative min-h-0 flex-1 bg-white">
        {running ? (
          <iframe
            key={iframeKey}
            src={status!.url}
            className="h-full w-full border-0"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          />
        ) : (
          <div className="flex h-full flex-col items-center justify-center p-6 text-center">
            {phase === 'idle' || phase === 'stopped' ? (
              <>
                <button
                  onClick={start}
                  className="flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition hover:bg-accent-soft"
                >
                  <Play size={15} /> Start preview
                </button>
                <p className="mt-3 max-w-xs text-xs text-text-faint">
                  Installs dependencies and runs the generated app, then shows it
                  live here. First run takes a minute.
                </p>
              </>
            ) : busy ? (
              <>
                <Loader2 size={22} className="animate-spin text-accent" />
                <p className="mt-3 text-sm text-text-muted">
                  {phase === 'installing'
                    ? 'Installing dependencies…'
                    : 'Starting dev server…'}
                </p>
                <LogBox logs={status?.logs ?? []} />
              </>
            ) : (
              <>
                <TriangleAlert size={22} className="text-rose-500" />
                <p className="mt-3 max-w-md text-sm text-text">
                  {status?.error || 'Preview failed'}
                </p>
                <button
                  onClick={start}
                  className="mt-3 rounded-lg border border-border px-3 py-1.5 text-xs text-text-muted transition hover:text-text"
                >
                  Retry
                </button>
                <LogBox logs={status?.logs ?? []} />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
