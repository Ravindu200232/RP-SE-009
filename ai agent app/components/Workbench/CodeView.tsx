'use client';

import { useEffect, useRef, useState } from 'react';
import { Highlight, themes } from 'prism-react-renderer';
import { Copy, Check } from 'lucide-react';
import { useBuilder } from '@/lib/store';

function languageFromPath(path: string): string {
  const name = path.toLowerCase();
  if (name.includes('.env') || name.endsWith('.gitignore')) return 'bash';
  const ext = name.split('.').pop() ?? '';
  const map: Record<string, string> = {
    ts: 'tsx',
    tsx: 'tsx',
    js: 'jsx',
    jsx: 'jsx',
    mjs: 'jsx',
    cjs: 'jsx',
    json: 'json',
    css: 'css',
    scss: 'css',
    html: 'markup',
    md: 'markdown',
    mdx: 'markdown',
    yml: 'yaml',
    yaml: 'yaml',
    sh: 'bash',
  };
  return map[ext] ?? 'tsx';
}

export function CodeView() {
  const files = useBuilder((s) => s.files);
  const selectedPath = useBuilder((s) => s.selectedPath);
  const isBuilding = useBuilder((s) => s.isBuilding);
  const streamingPath = useBuilder((s) => s.streamingPath);
  const [copied, setCopied] = useState(false);
  const codeScrollRef = useRef<HTMLDivElement>(null);

  const file = files.find((f) => f.path === selectedPath) ?? null;

  useEffect(() => {
    if (!file || (!isBuilding && !streamingPath)) return;
    const frame = requestAnimationFrame(() => {
      const el = codeScrollRef.current;
      el?.scrollTo({ top: el.scrollHeight });
    });
    return () => cancelAnimationFrame(frame);
  }, [file, isBuilding, streamingPath]);

  const copy = async () => {
    if (!file) return;
    try {
      await navigator.clipboard.writeText(file.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* ignore */
    }
  };

  if (!file) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-text-faint">
        Select a file to view its contents
      </div>
    );
  }

  const language = languageFromPath(file.path);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-9 shrink-0 items-center justify-between border-b border-border bg-bg-soft px-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate font-mono text-xs text-text-muted">{file.path}</span>
          <span className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] uppercase text-text-faint">
            {language}
          </span>
        </div>
        <button
          onClick={copy}
          className="flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-text-faint transition hover:text-text"
        >
          {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>

      <div ref={codeScrollRef} className="min-h-0 flex-1 overflow-auto bg-bg">
        <Highlight theme={themes.github} code={file.content} language={language}>
          {({ tokens, getLineProps, getTokenProps }) => (
            <pre className="min-w-full py-3 font-mono text-xs leading-5" style={{ background: 'transparent' }}>
              {tokens.map((line, i) => {
                const { key: _lk, ...lineProps } = getLineProps({ line });
                return (
                  <div key={i} {...lineProps} className="flex">
                    <span className="sticky left-0 w-10 shrink-0 select-none border-r border-border-soft bg-bg pr-3 text-right text-text-faint">
                      {i + 1}
                    </span>
                    <span className="px-3 whitespace-pre">
                      {line.map((token, key) => {
                        const { key: _tk, ...tokenProps } = getTokenProps({ token });
                        return <span key={key} {...tokenProps} />;
                      })}
                    </span>
                  </div>
                );
              })}
            </pre>
          )}
        </Highlight>
      </div>
    </div>
  );
}
