"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Icon, Btn } from "../core/ui";
import {
  generateSandbox,
  getSandbox,
  getSandboxPreviewUrl,
  planSandboxSrs,
  refineSandbox,
  repairSandbox,
} from "../core/agent2-api";

const SAMPLE_SRS = {
  project_name: "TaskFlow",
  domain: "task management",
  description:
    "A team task management web app with kanban board, projects, due dates, and assignees.",
  entities: [
    {
      name: "Task",
      fields: [
        { name: "id", type: "string" },
        { name: "title", type: "string" },
        { name: "description", type: "text" },
        { name: "status", type: "enum", values: ["todo", "in_progress", "review", "done"] },
        { name: "priority", type: "enum", values: ["low", "medium", "high"] },
        { name: "assignee", type: "string" },
        { name: "due_date", type: "date" },
        { name: "tags", type: "string[]" },
      ],
    },
    {
      name: "Project",
      fields: [
        { name: "id", type: "string" },
        { name: "name", type: "string" },
        { name: "color", type: "string" },
      ],
    },
  ],
  features: [
    { name: "Kanban Board", description: "Columns: Todo, In Progress, Review, Done." },
    { name: "Quick Add Task", description: "Inline form to create a task." },
    { name: "Filter by Project / Priority", description: "Top filter chips." },
    { name: "Task Detail Modal", description: "Click a task to edit fields." },
    { name: "Project Sidebar", description: "List of projects with color dot and counts." },
    { name: "Stats Dashboard", description: "Overview screen: counts per status, upcoming due." },
  ],
  pages: ["Dashboard", "Board", "List", "Settings"],
  brand: { name: "TaskFlow", primary_color: "#6366f1" },
};

const SUGGESTIONS = [
  {
    label: "Task manager",
    icon: "CheckSquare",
    text:
      "A team task manager with a kanban board, multiple projects, due dates, assignees, priority levels, filter chips, and a stats dashboard.",
  },
  {
    label: "CRM",
    icon: "Layers",
    text:
      "A small-business CRM with contacts, companies, a deals pipeline (kanban by stage), an activities timeline, and email templates.",
  },
  {
    label: "Hotel booking",
    icon: "Globe",
    text:
      "A boutique hotel booking app with room types, an availability calendar, guest profiles, and a reservations list with check-in / check-out actions.",
  },
  {
    label: "Recipe vault",
    icon: "FileText",
    text:
      "A personal recipe vault with categories, ingredients, step-by-step cooking mode, weekly meal planning, and a shopping list.",
  },
  {
    label: "Inventory",
    icon: "Package",
    text:
      "A warehouse inventory app with SKUs, stock levels, locations, transfer history, low-stock alerts, and a quick-receive form.",
  },
];

function looksLikeJson(text) {
  const t = text.trim();
  if (!t.startsWith("{") || !t.endsWith("}")) return false;
  try {
    JSON.parse(t);
    return true;
  } catch {
    return false;
  }
}

function deriveTitle(text) {
  const first = text.split(/[.\n]/)[0].trim();
  if (!first) return "Generated App";
  const words = first.split(/\s+/).slice(0, 4).join(" ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function SrsPasteModal({ open, onClose, onSubmit }) {
  const [text, setText] = useState("");
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
    setText(await file.text());
    setError("");
  };

  const useSample = () => {
    setText(JSON.stringify(SAMPLE_SRS, null, 2));
    setError("");
  };

  const submit = () => {
    try {
      const value = JSON.parse(text);
      onSubmit(value);
    } catch (exc) {
      setError("Invalid JSON: " + exc.message);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl border border-gray-200 w-[720px] max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <p className="text-base font-semibold text-gray-900">Attach SRS JSON</p>
            <p className="text-xs text-gray-500 mt-0.5">
              Paste a structured SRS to start the build directly. The planner will still enrich missing fields.
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <Icon name="X" size={18} />
          </button>
        </div>

        <div className="px-5 py-2 flex items-center gap-2 border-b border-gray-100 bg-gray-50">
          <Btn size="xs" icon="Upload" onClick={() => fileRef.current?.click()}>
            Upload .json
          </Btn>
          <Btn size="xs" icon="FileText" onClick={useSample}>
            Use sample
          </Btn>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={onPickFile}
          />
        </div>

        <div className="flex-1 overflow-hidden p-4">
          <textarea
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setError("");
            }}
            placeholder='{"project_name":"TaskManager","features":["kanban","comments"]}'
            className="w-full h-72 font-mono text-xs p-3 border border-gray-200 rounded-lg resize-none focus:outline-none focus:border-blue-400"
            spellCheck={false}
          />
          {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
        </div>

        <div className="px-5 py-3 border-t border-gray-200 bg-gray-50 flex items-center justify-end gap-2">
          <Btn size="sm" onClick={onClose}>
            Cancel
          </Btn>
          <Btn size="sm" variant="primary" icon="Sparkles" onClick={submit} disabled={!text.trim()}>
            Use this SRS
          </Btn>
        </div>
      </div>
    </div>
  );
}

const PHASE_COPY = {
  idle: { label: "Ready", tone: "text-gray-500", dot: "bg-gray-300" },
  thinking: { label: "Planning SRS", tone: "text-blue-600", dot: "bg-blue-500 animate-pulse" },
  generating: { label: "Generating app", tone: "text-violet-600", dot: "bg-violet-500 animate-pulse" },
  refining: { label: "Refining", tone: "text-blue-600", dot: "bg-blue-500 animate-pulse" },
  repairing: { label: "Auto-repairing", tone: "text-amber-600", dot: "bg-amber-500 animate-pulse" },
  ready: { label: "Live preview", tone: "text-green-600", dot: "bg-green-500" },
  failed: { label: "Failed", tone: "text-red-600", dot: "bg-red-500" },
};

function ThinkingMessage({ label, sub }) {
  return (
    <div className="flex gap-3 items-start">
      <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
        <Icon name="Sparkles" size={14} className="text-white" />
      </div>
      <div className="flex-1 pt-0.5">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-gray-900">Agent 2</span>
          <span className="text-[10px] text-gray-400">thinking…</span>
        </div>
        <div className="mt-1 inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-gradient-to-r from-blue-50 to-violet-50 border border-blue-100">
          <span className="flex gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            <span
              className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"
              style={{ animationDelay: "150ms" }}
            />
            <span
              className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"
              style={{ animationDelay: "300ms" }}
            />
          </span>
          <span className="text-xs text-gray-700">{label}</span>
        </div>
        {sub && <p className="text-[11px] text-gray-500 mt-1.5">{sub}</p>}
      </div>
    </div>
  );
}

function PlanMessage({ srs }) {
  const summary = useMemo(() => {
    const entities = (srs?.entities || []).length;
    const features = (srs?.features || []).length;
    const pages = (srs?.pages || []).length;
    return { entities, features, pages };
  }, [srs]);

  return (
    <div className="flex gap-3 items-start">
      <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
        <Icon name="Sparkles" size={14} className="text-white" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-gray-900">Agent 2</span>
          <span className="text-[10px] text-gray-400">planned the SRS</span>
        </div>
        <div className="bg-white border border-gray-200 rounded-2xl p-3 max-w-md">
          <div className="flex items-center gap-2 mb-2">
            <Icon name="BrainCircuit" size={14} className="text-violet-500" />
            <span className="text-xs font-semibold text-gray-900 truncate">
              {srs?.project_name || "Generated App"}
            </span>
          </div>
          {srs?.description && (
            <p className="text-[11px] text-gray-600 leading-relaxed mb-2 line-clamp-3">
              {srs.description}
            </p>
          )}
          <div className="flex flex-wrap gap-1.5">
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-100">
              {summary.entities} entities
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 border border-violet-100">
              {summary.features} features
            </span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-100">
              {summary.pages} pages
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ArtifactMessage({ title, version, kind, refinement, onOpen }) {
  const kindCopy = {
    generate: { label: "Initial build", icon: "Sparkles", color: "text-blue-600" },
    refine: { label: "Refined", icon: "Edit2", color: "text-violet-600" },
    repair: { label: "Auto-repaired", icon: "ShieldCheck", color: "text-amber-600" },
  };
  const k = kindCopy[kind] || kindCopy.generate;

  return (
    <div className="flex gap-3 items-start">
      <div className="w-7 h-7 rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center flex-shrink-0">
        <Icon name="Sparkles" size={14} className="text-white" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-gray-900">Agent 2</span>
          <span className="text-[10px] text-gray-400">{k.label}</span>
        </div>
        {refinement && (
          <p className="text-[11px] text-gray-500 mb-1.5 italic line-clamp-2">"{refinement}"</p>
        )}
        <button
          onClick={onOpen}
          className="group flex items-center gap-3 bg-white border border-gray-200 hover:border-blue-300 hover:shadow-sm rounded-2xl p-3 max-w-md w-full text-left transition-all"
        >
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100 border border-gray-200 flex items-center justify-center flex-shrink-0">
            <Icon name={k.icon} size={18} className={k.color} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-gray-900 truncate">{title}</p>
            <p className="text-[11px] text-gray-500">v{version} · React + Tailwind sandbox</p>
          </div>
          <Icon
            name="ArrowRight"
            size={14}
            className="text-gray-400 group-hover:text-blue-500 group-hover:translate-x-0.5 transition-all"
          />
        </button>
      </div>
    </div>
  );
}

function ErrorMessage({ message, onRepair, busy }) {
  return (
    <div className="flex gap-3 items-start">
      <div className="w-7 h-7 rounded-xl bg-red-50 border border-red-200 flex items-center justify-center flex-shrink-0">
        <Icon name="AlertTriangle" size={14} className="text-red-500" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold text-red-600">Sandbox runtime error</span>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-2xl p-3 max-w-md">
          <p className="text-[11px] font-mono text-red-700 break-words leading-relaxed mb-2">
            {message}
          </p>
          {onRepair && (
            <Btn size="xs" variant="primary" icon="Sparkles" onClick={onRepair} disabled={busy}>
              {busy ? "Repairing…" : "Auto-repair"}
            </Btn>
          )}
        </div>
      </div>
    </div>
  );
}

function UserMessage({ text }) {
  return (
    <div className="flex gap-3 items-start justify-end">
      <div className="max-w-md bg-blue-600 text-white text-xs leading-relaxed rounded-2xl rounded-tr-md px-4 py-2.5 shadow-sm">
        <p className="whitespace-pre-wrap break-words">{text}</p>
      </div>
      <div className="w-7 h-7 rounded-xl bg-gray-100 border border-gray-200 flex items-center justify-center flex-shrink-0">
        <span className="text-[10px] font-semibold text-gray-600">YOU</span>
      </div>
    </div>
  );
}

function ArtifactTabs({ active, onChange, hasCode, hasSrs }) {
  const tabs = [
    { id: "preview", label: "Preview", icon: "Eye" },
    { id: "code", label: "Code", icon: "Code2", disabled: !hasCode },
    { id: "srs", label: "SRS", icon: "FileText", disabled: !hasSrs },
  ];
  return (
    <div className="flex items-center gap-1">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => !t.disabled && onChange(t.id)}
          disabled={t.disabled}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs transition-all ${
            active === t.id
              ? "bg-white text-gray-900 shadow-sm border border-gray-200 font-medium"
              : t.disabled
              ? "text-gray-300 cursor-not-allowed"
              : "text-gray-500 hover:text-gray-900 hover:bg-white/60"
          }`}
        >
          <Icon name={t.icon} size={12} />
          {t.label}
        </button>
      ))}
    </div>
  );
}

export default function SandboxStudio({ onNavigate, onToast }) {
  const [messages, setMessages] = useState([]);
  const [phase, setPhase] = useState("idle");
  const [input, setInput] = useState("");
  const [model, setModel] = useState("qwen2.5:14b");
  const [sandboxId, setSandboxId] = useState(null);
  const [sandbox, setSandbox] = useState(null);
  const [srsJson, setSrsJson] = useState(null);
  const [activeTab, setActiveTab] = useState("preview");
  const [runtimeError, setRuntimeError] = useState(null);
  const [repairBusy, setRepairBusy] = useState(false);
  const [srsModalOpen, setSrsModalOpen] = useState(false);
  const [codeCopied, setCodeCopied] = useState(false);

  const idRef = useRef(0);
  const chatRef = useRef(null);
  const iframeRef = useRef(null);
  const pollRef = useRef(null);
  const sandboxIdRef = useRef(null);
  const repairAttemptRef = useRef(0);
  const repairInFlightRef = useRef(false);
  const errorHandlerRef = useRef(null);
  const MAX_AUTO_REPAIRS = 3;

  const newId = () => `msg-${++idRef.current}`;
  const appendMessage = (m) => {
    const id = newId();
    setMessages((cur) => [...cur, { id, ...m }]);
    return id;
  };
  const removeMessage = (id) => setMessages((cur) => cur.filter((x) => x.id !== id));

  useEffect(() => {
    sandboxIdRef.current = sandboxId;
  }, [sandboxId]);

  useEffect(() => () => clearTimeout(pollRef.current), []);

  useEffect(() => {
    if (chatRef.current) {
      chatRef.current.scrollTop = chatRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    const onMessage = (event) => {
      const data = event.data;
      if (!data || data.type !== "sandbox-error") return;
      errorHandlerRef.current?.({
        message: data.message || "Unknown sandbox runtime error",
        stack: data.stack || "",
      });
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  const previewUrl = useMemo(() => {
    if (!sandboxId || !sandbox || sandbox.status !== "ready") return null;
    return getSandboxPreviewUrl(sandboxId, sandbox.version);
  }, [sandboxId, sandbox]);

  const pollSandbox = (id, onDone) => {
    clearTimeout(pollRef.current);
    const tick = async () => {
      try {
        const data = await getSandbox(id, { includeHtml: false });
        setSandbox(data);
        if (data.status === "ready") {
          try {
            const full = await getSandbox(id, { includeHtml: true });
            setSandbox(full);
          } catch {}
          return onDone({ ready: true, record: data });
        }
        if (data.status === "failed") {
          return onDone({ failed: true, error: data.error });
        }
      } catch (exc) {
        // keep polling
      }
      pollRef.current = setTimeout(tick, 1500);
    };
    tick();
  };

  const startBuildFromSrs = async (rough, userText) => {
    if (userText) appendMessage({ role: "user", text: userText });
    repairAttemptRef.current = 0;
    repairInFlightRef.current = false;
    setRuntimeError(null);
    setPhase("thinking");
    const planId = appendMessage({
      role: "assistant",
      kind: "thinking",
      label: "Planning a high-quality SRS…",
      sub: "Inferring entities, features, pages, and seed data.",
    });
    let planned;
    try {
      const data = await planSandboxSrs({ srsJson: rough, model });
      planned = data.srs_json;
      setSrsJson(planned);
      removeMessage(planId);
      appendMessage({ role: "assistant", kind: "plan", srs: planned });
    } catch (exc) {
      removeMessage(planId);
      appendMessage({ role: "assistant", kind: "error", message: `Plan failed: ${exc.message}` });
      setPhase("failed");
      onToast?.(`Plan failed: ${exc.message}`, "error");
      return;
    }

    setPhase("generating");
    const genId = appendMessage({
      role: "assistant",
      kind: "thinking",
      label: "Building the sandbox app…",
      sub: `Qwen 2.5 14B is composing the JSX for ${planned.project_name || "your app"}.`,
    });
    try {
      const gen = await generateSandbox({ srsJson: planned, model });
      setSandboxId(gen.sandbox_id);
      pollSandbox(gen.sandbox_id, ({ ready, record, failed, error }) => {
        if (ready) {
          removeMessage(genId);
          appendMessage({
            role: "assistant",
            kind: "artifact",
            version: record.version,
            title: planned.project_name || "Generated App",
            artifactKind: "generate",
          });
          setPhase("ready");
          setActiveTab("preview");
          onToast?.("Sandbox is live — refine it in chat.", "success");
        } else if (failed) {
          removeMessage(genId);
          appendMessage({
            role: "assistant",
            kind: "error",
            message: error || "Generation failed",
          });
          setPhase("failed");
        }
      });
    } catch (exc) {
      removeMessage(genId);
      appendMessage({ role: "assistant", kind: "error", message: exc.message });
      setPhase("failed");
      onToast?.(`Build failed: ${exc.message}`, "error");
    }
  };

  const sendChat = async () => {
    const text = input.trim();
    if (!text || phase === "thinking" || phase === "generating" || phase === "refining" || phase === "repairing") {
      return;
    }
    setInput("");

    if (!sandboxId) {
      let rough;
      if (looksLikeJson(text)) {
        rough = JSON.parse(text);
      } else {
        rough = { description: text, project_name: deriveTitle(text) };
      }
      await startBuildFromSrs(rough, text);
      return;
    }

    appendMessage({ role: "user", text });
    setPhase("refining");
    setRuntimeError(null);
    repairAttemptRef.current = 0;
    repairInFlightRef.current = false;
    const id = appendMessage({
      role: "assistant",
      kind: "thinking",
      label: "Applying your changes…",
      sub: text,
    });
    try {
      await refineSandbox(sandboxId, text);
      pollSandbox(sandboxId, ({ ready, record, failed, error }) => {
        if (ready) {
          removeMessage(id);
          appendMessage({
            role: "assistant",
            kind: "artifact",
            version: record.version,
            title: srsJson?.project_name || "Generated App",
            artifactKind: "refine",
            refinement: text,
          });
          setPhase("ready");
        } else if (failed) {
          removeMessage(id);
          appendMessage({ role: "assistant", kind: "error", message: error || "Refine failed" });
          setPhase("failed");
        }
      });
    } catch (exc) {
      removeMessage(id);
      appendMessage({ role: "assistant", kind: "error", message: exc.message });
      setPhase("ready");
    }
  };

  const triggerSuggestion = (text) => {
    if (phase === "thinking" || phase === "generating") return;
    setInput("");
    startBuildFromSrs({ description: text, project_name: deriveTitle(text) }, text);
  };

  const triggerSample = () => {
    if (phase === "thinking" || phase === "generating") return;
    startBuildFromSrs(SAMPLE_SRS, "Build the TaskFlow sample SRS.");
  };

  const onSrsPaste = (srs) => {
    setSrsModalOpen(false);
    startBuildFromSrs(srs, "Use the SRS JSON I attached.");
  };

  const silentAutoRepair = async ({ message, stack }) => {
    const id = sandboxIdRef.current;
    if (!id || repairInFlightRef.current) return;
    repairInFlightRef.current = true;
    setPhase("repairing");
    try {
      await repairSandbox(id, { errorMessage: message, errorStack: stack });
      pollSandbox(id, ({ ready, failed }) => {
        repairInFlightRef.current = false;
        if (ready) {
          setPhase("ready");
        } else if (failed) {
          setPhase("ready");
        }
      });
    } catch {
      repairInFlightRef.current = false;
      setPhase("ready");
    }
  };

  errorHandlerRef.current = ({ message, stack }) => {
    if (!sandboxIdRef.current) return;
    if (repairInFlightRef.current) return;
    if (repairAttemptRef.current >= MAX_AUTO_REPAIRS) {
      setRuntimeError({ message, stack, ts: Date.now() });
      return;
    }
    repairAttemptRef.current += 1;
    silentAutoRepair({ message, stack });
  };

  const handleAutoRepair = async () => {
    if (!sandboxId || !runtimeError || repairBusy) return;
    setRepairBusy(true);
    setPhase("repairing");
    const snap = runtimeError;
    setRuntimeError(null);
    repairAttemptRef.current = 0;
    try {
      await repairSandbox(sandboxId, {
        errorMessage: snap.message,
        errorStack: snap.stack,
      });
      pollSandbox(sandboxId, ({ ready, failed, error }) => {
        if (ready) {
          setPhase("ready");
        } else if (failed) {
          appendMessage({ role: "assistant", kind: "error", message: error || "Repair failed" });
          setPhase("failed");
        }
      });
    } catch (exc) {
      appendMessage({ role: "assistant", kind: "error", message: exc.message });
      setPhase("ready");
    } finally {
      setRepairBusy(false);
    }
  };

  const onPromptKey = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendChat();
    }
  };

  const reloadIframe = () => {
    if (iframeRef.current && previewUrl) {
      iframeRef.current.src = previewUrl + "&t=" + Date.now();
    }
  };

  const approve = () => {
    onToast?.("Design approved. Sending to Agent 2 final build.", "success");
    setTimeout(() => onNavigate?.("agent2"), 600);
  };

  const copyCode = () => {
    if (!sandbox?.code) return;
    navigator.clipboard?.writeText(sandbox.code).catch(() => {});
    setCodeCopied(true);
    setTimeout(() => setCodeCopied(false), 1500);
  };

  const composerBusy =
    phase === "thinking" ||
    phase === "generating" ||
    phase === "refining" ||
    phase === "repairing";

  const placeholder = !sandboxId
    ? "Describe an app you want to build, or paste an SRS JSON…"
    : composerBusy
    ? "Working on it…"
    : "Refine: \"smaller navbar\", \"glass banner\", \"teal accent\", \"add dark mode\"…";

  const isEmpty = messages.length === 0;
  const phaseCopy = PHASE_COPY[phase] || PHASE_COPY.idle;

  if (isEmpty) {
    return (
      <div className="flex flex-col h-full overflow-hidden bg-gradient-to-b from-gray-50 to-white">
        <div className="px-6 pt-5 pb-3 border-b border-gray-200 bg-white/60 backdrop-blur flex items-center justify-between flex-shrink-0">
          <div>
            <div className="flex items-center gap-2 text-xs text-gray-400 mb-1">
              <span>AgentForge</span>
              <Icon name="ChevronRight" size={10} />
              <span>Sandbox Studio</span>
            </div>
            <h1 className="text-xl font-bold text-gray-900">Design with Agent 2</h1>
          </div>
          <Btn icon="ArrowLeft" size="sm" onClick={() => onNavigate?.("agent1")}>
            Back to Analyser
          </Btn>
        </div>

        <div className="flex-1 overflow-y-auto flex items-center justify-center px-6 py-10">
          <div className="w-full max-w-3xl">
            <div className="text-center mb-8">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center mx-auto mb-5 shadow-lg shadow-blue-500/20">
                <Icon name="Sparkles" size={26} className="text-white" />
              </div>
              <h2 className="text-3xl font-bold text-gray-900 tracking-tight">
                What should we build today?
              </h2>
              <p className="text-sm text-gray-500 mt-2 max-w-xl mx-auto leading-relaxed">
                Describe the app in plain English and Agent 2 will plan an SRS, generate a working
                React sandbox, and let you refine it conversationally — just like Claude.
              </p>
            </div>

            <div className="bg-white border border-gray-200 rounded-3xl shadow-sm p-3 focus-within:border-blue-400 focus-within:shadow-md transition-all">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={onPromptKey}
                placeholder="A team task manager with kanban board, projects, due dates, and a stats dashboard…"
                rows={3}
                className="w-full px-3 py-2 text-sm text-gray-900 placeholder-gray-400 bg-transparent border-0 focus:outline-none resize-none leading-relaxed"
                autoFocus
              />
              <div className="flex items-center justify-between gap-2 px-2 pt-1">
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setSrsModalOpen(true)}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-100 transition-colors"
                    title="Attach SRS JSON"
                  >
                    <Icon name="FileCode" size={14} />
                    <span>Attach SRS</span>
                  </button>
                  <button
                    onClick={triggerSample}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-gray-600 hover:bg-gray-100 transition-colors"
                  >
                    <Icon name="Star" size={14} />
                    <span>Use sample</span>
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-gray-50 border border-gray-200">
                    <Icon name="Cpu" size={12} className="text-gray-400" />
                    <input
                      value={model}
                      onChange={(event) => setModel(event.target.value)}
                      className="bg-transparent text-xs font-mono w-32 focus:outline-none text-gray-700"
                    />
                  </div>
                  <button
                    onClick={sendChat}
                    disabled={!input.trim()}
                    className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all ${
                      input.trim()
                        ? "bg-blue-600 hover:bg-blue-700 text-white shadow-sm"
                        : "bg-gray-100 text-gray-300 cursor-not-allowed"
                    }`}
                    title="Send"
                  >
                    <Icon name="ArrowRight" size={16} />
                  </button>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-gray-400 text-center mt-3">
              Enter to send · Shift+Enter for newline
            </p>

            <div className="mt-8">
              <p className="text-[11px] uppercase tracking-wider text-gray-400 font-semibold text-center mb-3">
                Try one of these
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.label}
                    onClick={() => triggerSuggestion(s.text)}
                    className="group flex items-center gap-2 px-3 py-2 rounded-xl bg-white border border-gray-200 hover:border-blue-300 hover:shadow-sm transition-all text-xs text-gray-700"
                  >
                    <Icon name={s.icon} size={14} className="text-gray-400 group-hover:text-blue-500" />
                    {s.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <SrsPasteModal
          open={srsModalOpen}
          onClose={() => setSrsModalOpen(false)}
          onSubmit={onSrsPaste}
        />
      </div>
    );
  }

  return (
    <div className="flex h-full overflow-hidden bg-gray-50">
      <div className="w-[460px] flex-shrink-0 border-r border-gray-200 bg-white flex flex-col overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center">
              <Icon name="Sparkles" size={14} className="text-white" />
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-900">Agent 2 · Designer</p>
              <div className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${phaseCopy.dot}`} />
                <span className={`text-[10px] ${phaseCopy.tone}`}>{phaseCopy.label}</span>
              </div>
            </div>
          </div>
          <button
            onClick={() => onNavigate?.("agent1")}
            className="text-[11px] text-gray-500 hover:text-gray-900 flex items-center gap-1"
            title="Back to analyser"
          >
            <Icon name="ArrowLeft" size={12} />
            Analyser
          </button>
        </div>

        <div ref={chatRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.map((m) => {
            if (m.role === "user") {
              return <UserMessage key={m.id} text={m.text} />;
            }
            if (m.kind === "thinking") {
              return <ThinkingMessage key={m.id} label={m.label} sub={m.sub} />;
            }
            if (m.kind === "plan") {
              return <PlanMessage key={m.id} srs={m.srs} />;
            }
            if (m.kind === "artifact") {
              return (
                <ArtifactMessage
                  key={m.id}
                  title={m.title}
                  version={m.version}
                  kind={m.artifactKind}
                  refinement={m.refinement}
                  onOpen={() => setActiveTab("preview")}
                />
              );
            }
            if (m.kind === "error") {
              return (
                <ErrorMessage
                  key={m.id}
                  message={m.message}
                  onRepair={m.repairable && runtimeError && !repairBusy ? handleAutoRepair : null}
                  busy={repairBusy}
                />
              );
            }
            return null;
          })}
        </div>

        <div className="p-3 border-t border-gray-200 bg-gray-50 flex-shrink-0">
          <div className="bg-white border border-gray-200 rounded-2xl shadow-sm focus-within:border-blue-400 transition-all">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={onPromptKey}
              placeholder={placeholder}
              disabled={composerBusy}
              rows={2}
              className="w-full px-3 py-2.5 text-xs text-gray-900 placeholder-gray-400 bg-transparent border-0 focus:outline-none resize-none leading-relaxed disabled:opacity-50"
            />
            <div className="flex items-center justify-between gap-2 px-2 pb-2">
              <div className="flex items-center gap-1">
                {!sandboxId && (
                  <button
                    onClick={() => setSrsModalOpen(true)}
                    disabled={composerBusy}
                    className="flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] text-gray-500 hover:bg-gray-100 disabled:opacity-40 transition-colors"
                    title="Attach SRS JSON"
                  >
                    <Icon name="FileCode" size={12} />
                    SRS
                  </button>
                )}
                <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-gray-50 border border-gray-200">
                  <Icon name="Cpu" size={10} className="text-gray-400" />
                  <input
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    className="bg-transparent text-[11px] font-mono w-24 focus:outline-none text-gray-600"
                  />
                </div>
              </div>
              <button
                onClick={sendChat}
                disabled={!input.trim() || composerBusy}
                className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all ${
                  input.trim() && !composerBusy
                    ? "bg-blue-600 hover:bg-blue-700 text-white"
                    : "bg-gray-100 text-gray-300 cursor-not-allowed"
                }`}
              >
                <Icon name="ArrowRight" size={14} />
              </button>
            </div>
          </div>
          <p className="text-[10px] text-gray-400 mt-1.5 px-1">
            {composerBusy ? phaseCopy.label + "…" : "Enter to send · Shift+Enter for newline"}
          </p>
        </div>
      </div>

      <div className="flex-1 flex flex-col overflow-hidden bg-gray-100">
        <div className="px-4 py-2.5 border-b border-gray-200 bg-white flex items-center justify-between gap-3 flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-gray-50 to-gray-100 border border-gray-200 flex items-center justify-center flex-shrink-0">
              <Icon name="Box" size={14} className="text-gray-500" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-semibold text-gray-900 truncate">
                {srsJson?.project_name || (sandbox ? "Generated App" : "Artifact")}
              </p>
              <div className="flex items-center gap-1.5">
                {sandbox?.version != null && (
                  <span className="text-[10px] text-gray-400">v{sandbox.version}</span>
                )}
                <span className={`w-1 h-1 rounded-full ${phaseCopy.dot}`} />
                <span className={`text-[10px] ${phaseCopy.tone}`}>{phaseCopy.label}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="flex items-center gap-1 p-1 bg-gray-100 rounded-xl">
              <ArtifactTabs
                active={activeTab}
                onChange={setActiveTab}
                hasCode={Boolean(sandbox?.code)}
                hasSrs={Boolean(srsJson)}
              />
            </div>
            {previewUrl && activeTab === "preview" && (
              <Btn size="xs" icon="RefreshCw" onClick={reloadIframe}>
                Reload
              </Btn>
            )}
            {sandbox?.code && activeTab === "code" && (
              <Btn size="xs" icon={codeCopied ? "Check" : "Copy"} onClick={copyCode}>
                {codeCopied ? "Copied" : "Copy"}
              </Btn>
            )}
            <Btn
              size="xs"
              variant="primary"
              icon="CheckCircle2"
              onClick={approve}
              disabled={phase !== "ready"}
            >
              Approve
            </Btn>
          </div>
        </div>

        <div className="flex-1 overflow-hidden p-4">
          {activeTab === "preview" && (
            <div className="h-full rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden flex flex-col">
              <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50 flex-shrink-0">
                <div className="flex gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-red-300" />
                  <span className="w-2.5 h-2.5 rounded-full bg-yellow-300" />
                  <span className="w-2.5 h-2.5 rounded-full bg-green-300" />
                </div>
                <p className="text-[11px] font-mono text-gray-500 ml-2 truncate">
                  {previewUrl || "preview will appear when ready"}
                </p>
                {sandbox?.model && (
                  <span className="ml-auto text-[10px] text-gray-400 font-mono">{sandbox.model}</span>
                )}
              </div>

              {previewUrl ? (
                <div className="relative flex-1 w-full bg-white overflow-hidden">
                  <iframe
                    ref={iframeRef}
                    src={previewUrl}
                    title="Live Sandbox"
                    className="absolute inset-0 w-full h-full bg-white"
                    sandbox="allow-scripts allow-same-origin allow-forms"
                  />
                  {(phase === "repairing" || phase === "refining") && (
                    <div className="absolute inset-0 bg-white/85 backdrop-blur-sm flex items-center justify-center transition-opacity">
                      <div className="text-center">
                        <div className="w-10 h-10 rounded-full border-4 border-blue-200 border-t-blue-500 animate-spin mx-auto mb-3" />
                        <p className="text-sm font-semibold text-gray-700">
                          {phase === "refining" ? "Updating preview…" : "Polishing the design…"}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">A new version is being prepared.</p>
                      </div>
                    </div>
                  )}
                  {phase === "ready" && runtimeError && (
                    <div className="absolute inset-0 bg-white/90 backdrop-blur-sm flex items-center justify-center p-6">
                      <div className="max-w-sm text-center">
                        <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center mx-auto mb-3">
                          <Icon name="AlertTriangle" size={22} className="text-amber-500" />
                        </div>
                        <p className="text-sm font-semibold text-gray-800">
                          This version had a small render hiccup.
                        </p>
                        <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
                          Try a quick refine in chat — e.g. "rebuild the dashboard cleanly" or
                          "simplify the sidebar".
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 flex items-center justify-center">
                  {phase === "failed" ? (
                    <div className="text-center max-w-md p-8">
                      <div className="w-12 h-12 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-center mx-auto mb-3">
                        <Icon name="AlertCircle" size={22} className="text-red-500" />
                      </div>
                      <p className="text-sm font-semibold text-red-700">
                        {sandbox?.error || "Generation failed"}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Try a different prompt or attach an SRS in the chat.
                      </p>
                    </div>
                  ) : (
                    <div className="text-center">
                      <div className="w-12 h-12 rounded-full border-4 border-blue-200 border-t-blue-500 animate-spin mx-auto mb-3" />
                      <p className="text-sm font-semibold text-gray-700">{phaseCopy.label}…</p>
                      <p className="text-xs text-gray-500 mt-1">
                        Qwen 2.5 14B is composing the JSX — first build is the slowest.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === "code" && (
            <div className="h-full rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden flex flex-col">
              <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 bg-gray-50 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <Icon name="Code2" size={12} className="text-gray-400" />
                  <span className="text-[11px] font-mono text-gray-500">App.jsx</span>
                </div>
                <span className="text-[10px] text-gray-400">
                  {(sandbox?.code || "").split("\n").length} lines
                </span>
              </div>
              <pre className="flex-1 overflow-auto p-4 text-[11px] font-mono leading-relaxed text-gray-700 whitespace-pre">
                {sandbox?.code || "// Code will appear here once the sandbox is ready."}
              </pre>
            </div>
          )}

          {activeTab === "srs" && (
            <div className="h-full rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden flex flex-col">
              <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 bg-gray-50 flex-shrink-0">
                <div className="flex items-center gap-2">
                  <Icon name="FileText" size={12} className="text-gray-400" />
                  <span className="text-[11px] font-mono text-gray-500">srs.json</span>
                </div>
                <button
                  onClick={() => {
                    if (srsJson) {
                      navigator.clipboard?.writeText(JSON.stringify(srsJson, null, 2)).catch(() => {});
                      onToast?.("SRS JSON copied.", "success");
                    }
                  }}
                  className="text-[10px] text-gray-500 hover:text-gray-900 flex items-center gap-1"
                >
                  <Icon name="Copy" size={10} />
                  Copy
                </button>
              </div>
              <pre className="flex-1 overflow-auto p-4 text-[11px] font-mono leading-relaxed text-gray-700 whitespace-pre">
                {srsJson ? JSON.stringify(srsJson, null, 2) : "// Plan an SRS to see it here."}
              </pre>
            </div>
          )}
        </div>
      </div>

      <SrsPasteModal
        open={srsModalOpen}
        onClose={() => setSrsModalOpen(false)}
        onSubmit={onSrsPaste}
      />
    </div>
  );
}
