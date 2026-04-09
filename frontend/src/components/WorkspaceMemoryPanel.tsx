'use client';

import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

export function WorkspaceMemoryPanel({
  files,
  selectedFile,
  onSelect
}: {
  files: Record<string, string>;
  selectedFile: string;
  onSelect: (fileName: string) => void;
}) {
  const fileNames = Object.keys(files);
  if (fileNames.length === 0) {
    return <div className="p-4 text-sm text-slate-500">Memory files will appear once a workspace is generated.</div>;
  }

  return (
    <div className="flex h-full">
      <div className="w-56 shrink-0 border-r border-[#1a1a2e] p-2">
        {fileNames.map((fileName) => (
          <button
            key={fileName}
            onClick={() => onSelect(fileName)}
            className={`mb-1 block w-full rounded-lg px-3 py-2 text-left text-xs transition ${
              selectedFile === fileName
                ? 'bg-purple-500/10 text-purple-300'
                : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
            }`}
          >
            {fileName}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-auto">
        <SyntaxHighlighter
          language={selectedFile.endsWith('.json') ? 'json' : 'markdown'}
          style={vscDarkPlus}
          customStyle={{ margin: 0, minHeight: '100%', background: '#080810', fontSize: '11px' }}
          showLineNumbers
        >
          {files[selectedFile] || ''}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}

export default WorkspaceMemoryPanel;
