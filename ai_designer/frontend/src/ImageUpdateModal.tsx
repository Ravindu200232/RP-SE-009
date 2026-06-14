import React, { useRef, useState } from "react";

/**
 * Image Update modal — opens when a user clicks an <img> in the live preview.
 * Option A: upload a file (dashed "+" drop box).
 * Option B: regenerate with Fooocus AI from a text prompt.
 *
 * Both call the deterministic backend (no LLM patching): the clicked component's
 * src is surgically repointed at a fresh asset, syntax-checked and atomically saved.
 *   POST /api/upload-image   { project_id, component_id, src, data_b64 }
 *   POST /api/generate-image { project_id, component_id, src, prompt }
 */

const API_BASE_URL = "http://localhost:8000";

export interface ImageTarget {
  componentId: string; // locates the source file on the backend
  src: string;         // current src, e.g. /assets/about1.jpg
  label?: string;      // friendly name for the header (optional)
}

export interface ImageUpdateModalProps {
  projectId: string;
  target: ImageTarget;
  onClose: () => void;
  /** Called after a successful replace so the host can reload the preview iframe. */
  onApplied?: (newSrc: string) => void;
}

type ApiResult = { ok?: boolean; src?: string; mode?: string; error?: string; detail?: string };

async function postJSON(path: string, body: unknown): Promise<ApiResult> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json().catch(() => ({ ok: false, error: `HTTP ${res.status}` }));
}

const readAsDataURL = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result || ""));
    r.onerror = reject;
    r.readAsDataURL(file);
  });

export default function ImageUpdateModal({ projectId, target, onClose, onApplied }: ImageUpdateModalProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState<null | "upload" | "ai">(null);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

  const finish = (r: ApiResult) => {
    if (r.ok) {
      onApplied?.(r.src || target.src);
      onClose();
    } else {
      setError(r.error || r.detail || "Something went wrong. Please try again.");
    }
    setBusy(null);
  };

  const doUpload = async (file?: File | null) => {
    if (!file || busy) return;
    setError("");
    setBusy("upload");
    try {
      const data_b64 = await readAsDataURL(file);
      finish(await postJSON("/api/upload-image", { project_id: projectId, component_id: target.componentId, src: target.src, data_b64 }));
    } catch (e: any) {
      setError(e?.message || "Could not read that file.");
      setBusy(null);
    }
  };

  const doGenerate = async () => {
    if (!prompt.trim() || busy) return;
    setError("");
    setBusy("ai");
    finish(await postJSON("/api/generate-image", { project_id: projectId, component_id: target.componentId, src: target.src, prompt: prompt.trim() }));
  };

  return (
    <div style={S.overlay} onClick={busy ? undefined : onClose}>
      <div style={S.card} onClick={(e) => e.stopPropagation()}>
        <div style={S.header}>
          <div>
            <div style={S.title}>Update image</div>
            <div style={S.subtitle}>{target.label || target.src}</div>
          </div>
          <button aria-label="Close" style={S.close} onClick={onClose} disabled={!!busy}>×</button>
        </div>

        {/* Option A — file upload */}
        <div style={S.sectionLabel}>Upload an image</div>
        <div
          role="button"
          tabIndex={0}
          onClick={() => !busy && fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => { e.preventDefault(); setDragOver(false); doUpload(e.dataTransfer.files?.[0]); }}
          style={{ ...S.dropZone, ...(dragOver ? S.dropZoneActive : null), ...(busy === "upload" ? S.dropBusy : null) }}
        >
          <div style={S.plus}>+</div>
          <div style={S.dropTitle}>{busy === "upload" ? "Uploading…" : "Click to upload or drag & drop"}</div>
          <div style={S.dropHint}>PNG, JPG or WEBP</div>
          <input ref={fileRef} type="file" accept="image/*" style={{ display: "none" }}
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; doUpload(f); }} />
        </div>

        <div style={S.divider}><span style={S.dividerText}>or</span></div>

        {/* Option B — Fooocus AI generation */}
        <div style={S.sectionLabel}>Make changes with Fooocus AI</div>
        <div style={S.aiRow}>
          <input
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") doGenerate(); }}
            placeholder="Describe the new image…"
            disabled={!!busy}
            style={S.aiInput}
          />
          <button onClick={doGenerate} disabled={!!busy || !prompt.trim()} style={{ ...S.generate, ...(busy || !prompt.trim() ? S.generateDisabled : null) }}>
            {busy === "ai" ? "Generating…" : "Generate"}
          </button>
        </div>

        {error ? <div style={S.error}>{error}</div> : null}
      </div>
    </div>
  );
}

const S: Record<string, React.CSSProperties> = {
  overlay: { position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", backdropFilter: "blur(2px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 },
  card: { width: 440, maxWidth: "92vw", background: "#fff", borderRadius: 16, padding: 24, boxShadow: "0 24px 60px rgba(0,0,0,0.25)", color: "#0f172a", fontFamily: "system-ui, sans-serif" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 },
  title: { fontSize: 17, fontWeight: 700 },
  subtitle: { fontSize: 12, color: "#64748b", marginTop: 2, maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  close: { border: "none", background: "transparent", fontSize: 24, lineHeight: 1, color: "#94a3b8", cursor: "pointer", padding: 0 },
  sectionLabel: { fontSize: 12, fontWeight: 600, color: "#475569", marginBottom: 8 },
  dropZone: { border: "2px dashed #cbd5e1", borderRadius: 12, padding: "26px 16px", textAlign: "center", cursor: "pointer", transition: "all .15s", background: "#f8fafc" },
  dropZoneActive: { borderColor: "#7c3aed", background: "#faf5ff" },
  dropBusy: { opacity: 0.6, pointerEvents: "none" },
  plus: { width: 40, height: 40, borderRadius: "50%", background: "#ede9fe", color: "#7c3aed", fontSize: 26, lineHeight: "38px", margin: "0 auto 8px", fontWeight: 300 },
  dropTitle: { fontSize: 13, fontWeight: 600, color: "#334155" },
  dropHint: { fontSize: 11, color: "#94a3b8", marginTop: 2 },
  divider: { display: "flex", alignItems: "center", textAlign: "center", color: "#cbd5e1", margin: "18px 0", borderTop: "1px solid #e2e8f0", position: "relative" },
  dividerText: { position: "absolute", left: "50%", transform: "translateX(-50%)", top: -9, background: "#fff", padding: "0 10px", fontSize: 11, color: "#94a3b8" },
  aiRow: { display: "flex", gap: 8 },
  aiInput: { flex: 1, border: "1px solid #e2e8f0", borderRadius: 10, padding: "10px 12px", fontSize: 13, outline: "none" },
  generate: { padding: "0 16px", borderRadius: 10, border: "none", background: "#7c3aed", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer" },
  generateDisabled: { opacity: 0.5, cursor: "not-allowed" },
  error: { marginTop: 14, fontSize: 12, color: "#dc2626", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: "8px 10px" },
};
