"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Icon, Btn } from "../core/ui";
import { startAgent2Build, getAgent2Build, getAgent2BuildFile } from "../core/agent2-api";

const STYLE_LABELS = {
  minimal: "Minimal",
  bold: "Bold",
  glass: "Glass",
  brutalist: "Brutalist",
  corporate: "Corporate",
};

const STYLE_ACCENTS = {
  minimal: "bg-gray-900",
  bold: "bg-pink-500",
  glass: "bg-cyan-400",
  brutalist: "bg-yellow-400",
  corporate: "bg-blue-700",
};

const CATEGORY_LABELS = {
  header: "Header",
  footer: "Footer",
  nav: "Navigation",
  card: "Card",
  page: "Page",
};

const SAMPLE_SRS = {
  project_name: "BookStay",
  description: "Hotel and short-stay booking platform.",
  features: [
    { name: "Search Rooms", description: "Filter by city, dates, guests." },
    { name: "Room Details", description: "Images, amenities, reviews." },
    { name: "Secure Checkout", description: "Stripe payments." },
    { name: "Host Dashboard", description: "Manage listings and bookings." },
  ],
  pages: [
    { id: "dashboard", name: "Host Dashboard" },
    { id: "login", name: "Sign In" },
    { id: "landing", name: "Discover Stays" },
    { id: "table", name: "Bookings" },
    { id: "settings", name: "Account Settings" },
  ],
  navigation: ["Discover", "My Trips", "Hosting", "Inbox", "Account"],
  brand: { name: "BookStay", tagline: "Find your next stay in seconds.", primary_color: "#2563eb" },
};

function SrsModal({ open, onClose, onSubmit, defaultModel }) {
  const [text, setText] = useState("");
  const [model, setModel] = useState(defaultModel || "qwen2.5:14b");
  const [error, setError] = useState("");
  const fileRef = useRef(null);

  useEffect(() => {
    if (!open) {
      setText("");
      setError("");
    }
  }, [open]);

  if (!open) return null;

  const onPickFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const content = await file.text();
    setText(content);
    setError("");
  };

  const useSample = () => {
    setText(JSON.stringify(SAMPLE_SRS, null, 2));
    setError("");
  };

  const submit = () => {
    let parsed;
    try {
      parsed = JSON.parse(text);
    } catch (exc) {
      setError("Invalid JSON: " + exc.message);
      return;
    }
    onSubmit({ srsJson: parsed, model });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-2xl border border-gray-200 w-[640px] max-h-[80vh] flex flex-col overflow-hidden"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <p className="text-base font-semibold text-gray-900">Add SRS JSON</p>
            <p className="text-xs text-gray-500 mt-0.5">Provide an SRS object to drive Agent 2 generation.</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <Icon name="X" size={18} />
          </button>
        </div>

        <div className="px-5 py-3 flex items-center gap-2 border-b border-gray-100 bg-gray-50">
          <Btn size="xs" icon="Upload" onClick={() => fileRef.current?.click()}>Upload .json</Btn>
          <Btn size="xs" icon="FileText" onClick={useSample}>Use Sample</Btn>
          <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={onPickFile} />
          <div className="ml-auto flex items-center gap-2 text-xs text-gray-600">
            <span>Model</span>
            <input
              value={model}
              onChange={(event) => setModel(event.target.value)}
              className="px-2 py-1 border border-gray-200 rounded text-xs font-mono w-44"
            />
          </div>
        </div>

        <div className="flex-1 overflow-hidden p-4">
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder='{"project_name": "MyApp", "features": [...], "pages": [...]}'
            className="w-full h-72 font-mono text-xs p-3 border border-gray-200 rounded-lg resize-none focus:outline-none focus:border-blue-400"
            spellCheck={false}
          />
          {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
        </div>

        <div className="px-5 py-3 border-t border-gray-200 bg-gray-50 flex justify-end gap-2">
          <Btn size="sm" onClick={onClose}>Cancel</Btn>
          <Btn size="sm" variant="primary" icon="Sparkles" onClick={submit} disabled={!text.trim()}>
            Generate Designs
          </Btn>
        </div>
      </div>
    </div>
  );
}

function ProgressPanel({ status, logs, stats, error }) {
  const expected = stats?.expected || 45;
  const generated = stats?.files || 0;
  const percent = Math.min(100, Math.round((generated / expected) * 100));
  const lastLogs = logs.slice(-12);

  return (
    <div className="p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-9 h-9 rounded-full bg-blue-50 border border-blue-200 flex items-center justify-center">
          {status === "completed" ? (
            <Icon name="CheckCircle2" size={18} className="text-green-500" />
          ) : status === "failed" ? (
            <Icon name="AlertCircle" size={18} className="text-red-500" />
          ) : (
            <span className="w-3 h-3 rounded-full bg-blue-500 animate-pulse" />
          )}
        </div>
        <div>
          <p className="text-sm font-semibold text-gray-900">
            {status === "completed" ? "Generation complete" : status === "failed" ? "Generation failed" : "Generating designs..."}
          </p>
          <p className="text-xs text-gray-500">
            {status === "failed"
              ? error || "An error occurred."
              : `Qwen 2.5 14B via Ollama · ${generated} / ${expected} files`}
          </p>
        </div>
      </div>

      <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden mb-4">
        <div className="h-full bg-blue-500 transition-all duration-500" style={{ width: `${percent}%` }} />
      </div>

      <div className="bg-gray-900 rounded-lg p-3 font-mono text-[11px] text-gray-200 max-h-72 overflow-y-auto">
        {lastLogs.length === 0 && <p className="text-gray-500">Waiting for first log line...</p>}
        {lastLogs.map((line, idx) => (
          <div key={idx} className="leading-5 whitespace-pre-wrap break-words">
            <span className="text-blue-400">▸</span> {line}
          </div>
        ))}
      </div>
    </div>
  );
}

function MiniPreview({ accent }) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden bg-white">
      <div className={`h-2 w-full ${accent}`} />
      <div className="p-2 space-y-1.5">
        <div className="h-2 w-3/4 bg-gray-200 rounded" />
        <div className="h-1.5 w-1/2 bg-gray-100 rounded" />
        <div className="grid grid-cols-3 gap-1 mt-2">
          <div className="h-6 bg-gray-100 rounded" />
          <div className="h-6 bg-gray-100 rounded" />
          <div className="h-6 bg-gray-100 rounded" />
        </div>
      </div>
    </div>
  );
}

function GeneratedGrid({ buildId, files, selections, onSelect }) {
  const [activeCategory, setActiveCategory] = useState("header");
  const [previewFile, setPreviewFile] = useState(null);
  const [previewCode, setPreviewCode] = useState("");
  const [loadingCode, setLoadingCode] = useState(false);

  const grouped = useMemo(() => {
    const map = { header: [], footer: [], nav: [], card: [], page: [] };
    for (const file of files) {
      if (map[file.category]) map[file.category].push(file);
    }
    return map;
  }, [files]);

  const visible = grouped[activeCategory] || [];

  const showCode = async (file) => {
    setPreviewFile(file);
    setLoadingCode(true);
    try {
      const data = await getAgent2BuildFile(buildId, file.path);
      setPreviewCode(data.content);
    } catch (exc) {
      setPreviewCode(`// Failed to load: ${exc.message}`);
    } finally {
      setLoadingCode(false);
    }
  };

  const categories = [
    { id: "header", count: grouped.header.length },
    { id: "footer", count: grouped.footer.length },
    { id: "nav", count: grouped.nav.length },
    { id: "card", count: grouped.card.length },
    { id: "page", count: grouped.page.length },
  ];

  return (
    <div className="flex h-full overflow-hidden">
      <div className="w-44 border-r border-gray-200 bg-gray-50 p-3 space-y-1 flex-shrink-0">
        <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-2 px-1">Generated</p>
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setActiveCategory(cat.id)}
            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
              activeCategory === cat.id ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            <span>{CATEGORY_LABELS[cat.id]}</span>
            <span className={`text-[10px] ${activeCategory === cat.id ? "text-blue-100" : "text-gray-400"}`}>
              {cat.count}
            </span>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-xs text-gray-500">
            <strong className="text-gray-900">{CATEGORY_LABELS[activeCategory]}</strong> — {visible.length} generated variants. Click to select; click code icon to preview.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {visible.map((file) => {
            const isSelected = selections[activeCategory] === file.path;
            return (
              <div
                key={file.path}
                className={`rounded-2xl border-2 transition-all overflow-hidden ${
                  isSelected ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white hover:border-blue-300"
                }`}
              >
                <button
                  onClick={() => onSelect(activeCategory, file.path)}
                  className="block w-full text-left p-3"
                >
                  <MiniPreview accent={STYLE_ACCENTS[file.style] || "bg-gray-300"} />
                </button>
                <div className="px-3 pb-3 flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold text-gray-900">{STYLE_LABELS[file.style] || file.style}</p>
                    <p className="text-[10px] text-gray-500 truncate max-w-[140px]">{file.path.split("/").pop()}</p>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => showCode(file)}
                      className="w-6 h-6 rounded-md bg-gray-100 hover:bg-gray-200 flex items-center justify-center"
                      title="View code"
                    >
                      <Icon name="Code2" size={11} className="text-gray-600" />
                    </button>
                    {isSelected && (
                      <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center">
                        <Icon name="Check" size={11} className="text-white" />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {previewFile && (
          <div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm flex items-center justify-center"
            onClick={() => setPreviewFile(null)}
          >
            <div
              className="bg-white rounded-2xl border border-gray-200 w-[760px] max-h-[80vh] flex flex-col overflow-hidden"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-gray-900">{previewFile.path}</p>
                  <p className="text-[11px] text-gray-500">
                    {CATEGORY_LABELS[previewFile.category]} · {STYLE_LABELS[previewFile.style] || previewFile.style}
                  </p>
                </div>
                <button onClick={() => setPreviewFile(null)} className="text-gray-400 hover:text-gray-600">
                  <Icon name="X" size={18} />
                </button>
              </div>
              <pre className="flex-1 overflow-auto bg-gray-900 text-gray-100 text-[11px] font-mono p-4 leading-5 whitespace-pre-wrap">
                {loadingCode ? "Loading..." : previewCode}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function DesignGenerator({ onNavigate, onToast }) {
  const [phase, setPhase] = useState("idle"); // idle | generating | ready | failed
  const [modalOpen, setModalOpen] = useState(false);
  const [buildId, setBuildId] = useState(null);
  const [build, setBuild] = useState(null);
  const [selections, setSelections] = useState({});
  const pollRef = useRef(null);

  useEffect(() => () => clearTimeout(pollRef.current), []);

  const startBuild = async ({ srsJson, model }) => {
    setModalOpen(false);
    setPhase("generating");
    setBuild(null);
    setSelections({});
    try {
      const data = await startAgent2Build({ srsJson, model });
      setBuildId(data.build_id);
      pollBuild(data.build_id);
      onToast?.(`Build ${data.build_id.slice(0, 8)} started.`, "info");
    } catch (exc) {
      setPhase("failed");
      setBuild({ status: "failed", logs: [], error: exc.message });
      onToast?.(`Build failed: ${exc.message}`, "error");
    }
  };

  const pollBuild = (id) => {
    const tick = async () => {
      try {
        const data = await getAgent2Build(id);
        setBuild(data);
        if (data.status === "completed") {
          setPhase("ready");
          onToast?.("Designs generated. Pick the variant you like for each category.", "success");
          return;
        }
        if (data.status === "failed") {
          setPhase("failed");
          onToast?.(`Build failed: ${data.error || "unknown"}`, "error");
          return;
        }
      } catch (exc) {
        setBuild((current) => ({ ...(current || {}), error: exc.message }));
      }
      pollRef.current = setTimeout(tick, 1500);
    };
    tick();
  };

  const handleSelect = (category, path) => {
    setSelections((current) => ({ ...current, [category]: path }));
  };

  const approve = () => {
    onToast?.("Design selections sent to Agent 2.", "success");
    setTimeout(() => onNavigate?.("agent2"), 600);
  };

  const allSelected = ["header", "footer", "nav", "card", "page"].every((cat) => selections[cat]);

  return (
    <div className="flex h-full overflow-hidden bg-white">
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="px-5 pt-4 pb-3 border-b border-gray-200 bg-white flex-shrink-0">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
                <span>AgentForge</span>
                <Icon name="ChevronRight" size={10} />
                <span>Design Generator</span>
              </div>
              <h1 className="text-xl font-bold text-gray-900">Design Generator</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                LangChain · LangGraph · Ollama · Qwen 2.5 14B — generates 5 styled variants per category from your SRS.
              </p>
            </div>
            <div className="flex gap-2 pt-1">
              <Btn icon="FileCode" variant="primary" onClick={() => setModalOpen(true)}>
                Add SRS JSON
              </Btn>
              {phase === "ready" && (
                <Btn icon="ArrowRight" variant="success" onClick={approve} disabled={!allSelected}>
                  Send Selections to Agent 2
                </Btn>
              )}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          {phase === "idle" && (
            <div className="h-full flex items-center justify-center">
              <div className="text-center max-w-md p-8">
                <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-200 flex items-center justify-center mx-auto mb-4">
                  <Icon name="FileJson" size={26} className="text-blue-600" />
                </div>
                <p className="text-lg font-semibold text-gray-900 mb-1">Ready to generate</p>
                <p className="text-sm text-gray-500 mb-5">
                  Provide your SRS JSON. Agent 2 will produce 5 distinct-style React components for Header, Footer, Nav, Card, and 5 page templates.
                </p>
                <Btn icon="FileCode" variant="primary" onClick={() => setModalOpen(true)}>
                  Add SRS JSON
                </Btn>
              </div>
            </div>
          )}

          {phase === "generating" && (
            <ProgressPanel
              status={build?.status || "running"}
              logs={build?.logs || []}
              stats={build?.stats}
              error={build?.error}
            />
          )}

          {phase === "failed" && (
            <ProgressPanel
              status="failed"
              logs={build?.logs || []}
              stats={build?.stats}
              error={build?.error}
            />
          )}

          {phase === "ready" && build && (
            <GeneratedGrid
              buildId={buildId}
              files={build.files || []}
              selections={selections}
              onSelect={handleSelect}
            />
          )}
        </div>
      </div>

      <div className="w-56 border-l border-gray-200 bg-gray-50 flex flex-col overflow-y-auto flex-shrink-0">
        <div className="px-4 py-3 border-b border-gray-200">
          <p className="text-xs font-semibold text-gray-700">Build Status</p>
        </div>
        <div className="p-4 space-y-3 flex-1">
          <div>
            <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Phase</p>
            <p className="text-xs font-medium text-gray-700 capitalize">{phase}</p>
          </div>
          {buildId && (
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Build ID</p>
              <p className="text-[11px] font-mono text-gray-600 break-all">{buildId}</p>
            </div>
          )}
          {build?.model && (
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Model</p>
              <p className="text-xs text-gray-700">{build.model}</p>
            </div>
          )}
          {build?.stats && (
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Files</p>
              <p className="text-xs text-gray-700">
                {build.stats.files} / {build.stats.expected}
              </p>
            </div>
          )}
          {phase === "ready" && (
            <div>
              <p className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Selected</p>
              {["header", "footer", "nav", "card", "page"].map((cat) => (
                <div key={cat} className="text-[11px] text-gray-600 flex items-center justify-between">
                  <span className="capitalize">{cat}</span>
                  {selections[cat] ? (
                    <Icon name="Check" size={11} className="text-green-500" />
                  ) : (
                    <span className="text-gray-300">·</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="p-4 border-t border-gray-200 space-y-2">
          {phase === "ready" && (
            <Btn size="xs" variant="primary" icon="ArrowRight" onClick={approve} disabled={!allSelected} className="w-full justify-center">
              Send to Agent 2
            </Btn>
          )}
          <Btn size="xs" icon="ArrowLeft" onClick={() => onNavigate?.("agent1")} className="w-full justify-center">
            Back to Analyser
          </Btn>
        </div>
      </div>

      <SrsModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={startBuild}
        defaultModel="qwen2.5:14b"
      />
    </div>
  );
}
