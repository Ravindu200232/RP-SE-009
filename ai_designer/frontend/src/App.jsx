import React, { useState, useEffect, useRef } from 'react';
import { Send, RefreshCw, Smartphone, Tablet, Monitor, Download, FileText, Crosshair, X, FileUp, AlertCircle } from 'lucide-react';
import { errText } from './lib/errText.js';
import { isVersionSuccess } from './lib/versioning.js';

const API_BASE_URL = 'http://localhost:8000';

// ── Log line classifier (terminal colour buckets) ──────────────────────────
function logClass(log) {
  if (log.startsWith('[USER]:')) return 'tl-user';
  if (log.startsWith('[DONE]')) return 'tl-done';
  if (/^BUILD ERROR|CRITICAL ERROR|IMAGE ERROR/.test(log)) return 'tl-error';
  if (/^---\s*\[PHASE/.test(log)) return 'tl-phase';
  if (/^---\s*\[/.test(log)) return 'tl-agent';
  if (/^\[(AGENT|EDIT |ADD |STYLE|VALIDATE|BUILD|PREVIEW)\]/.test(log)) return 'tl-agent-msg';
  if (/failed|error|unavailable/i.test(log)) return 'tl-warning';
  return 'tl-sys';
}

// Which gutter symbol for a log line
function logGutter(log) {
  if (log.startsWith('[USER]:')) return '❯';
  if (log.startsWith('[DONE]')) return '✓';
  if (/^BUILD ERROR|CRITICAL ERROR|IMAGE ERROR/.test(log)) return '✗';
  if (/^---\s*\[PHASE/.test(log)) return '─';
  if (/^---\s*\[/.test(log)) return '·';
  return ' ';
}

function App() {
  // ── State ──────────────────────────────────────────────────────────────────
  const [prompt, setPrompt] = useState('');
  const [activeTab, setActiveTab] = useState('chat');
  const [mode, setMode] = useState('preview');
  const [previewSize, setPreviewSize] = useState('desktop');
  const [projectId, setProjectId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState('idle');
  const [files, setFiles] = useState({});
  const [selectedFile, setSelectedFile] = useState(null);
  const [promptsHistory, setPromptsHistory] = useState([]);
  const [previewVersion, setPreviewVersion] = useState(0);
  const [phase, setPhase] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [inspect, setInspect] = useState(false);
  const [pinned, setPinned] = useState(null);
  const [interview, setInterview] = useState(null);
  const [answers, setAnswers] = useState(null);
  const [interviewPrompt, setInterviewPrompt] = useState('');
  const [interviewLoading, setInterviewLoading] = useState(false);
  const [lang, setLang] = useState('en');
  const [appType, setAppType] = useState('hybrid');
  const [meta, setMeta] = useState({ languages: [{ value: 'en', label: 'English' }], app_types: [] });
  const [plan, setPlan] = useState(null);
  const [question, setQuestion] = useState(null);
  const [draft, setDraft] = useState(null);
  const [progress, setProgress] = useState({ index: 0, total: 0 });
  const [stepHistory, setStepHistory] = useState([]);
  const [editing, setEditing] = useState(false);
  const [editMode, setEditMode] = useState('edit');
  const [insertPosition, setInsertPosition] = useState('after');
  const [imageModal, setImageModal] = useState(false);
  const [imgPrompt, setImgPrompt] = useState('');
  const imgFileRef = useRef(null);
  const [vpFill, setVpFill] = useState(false);

  const logsEndRef = useRef(null);
  const iframeRef = useRef(null);
  const srsFileRef = useRef(null);

  // ── Phase labels ───────────────────────────────────────────────────────────
  const PHASE_LABELS = {
    planning: 'planning…',
    genome: 'choosing design…',
    scaffold: 'writing scaffold…',
    pages: 'generating pages…',
    image_generating: 'generating images…',
    image_integrating: 'integrating images…',
    qa: 'quality check…',
    validating: 'validating…',
    building: 'building…',
    error: 'build error',
  };

  // ── Gated preview: poll phase, reveal iframe only when done ───────────────
  useEffect(() => {
    if (!projectId || previewUrl) return;
    if (!['generating', 'updating', 'completed'].includes(status)) return;
    let stop = false;
    const tick = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/status?project_id=${projectId}`);
        if (res.ok) {
          const s = await res.json();
          if (stop) return;
          setPhase(s.phase || null);
          if (s.phase === 'done') {
            const pr = await fetch(`${API_BASE_URL}/api/preview`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ prompt: '', project_id: projectId }),
            });
            if (pr.ok) { const { url } = await pr.json(); if (!stop) setPreviewUrl(url); }
            return;
          }
          if (s.phase === 'error') return;
        }
      } catch (e) {}
      if (!stop) setTimeout(tick, 2500);
    };
    tick();
    return () => { stop = true; };
  }, [projectId, status, previewUrl]);

  // ── Select-Element message bridge ─────────────────────────────────────────
  useEffect(() => {
    const onMsg = (e) => {
      const d = e.data || {};
      if (d.type === 'INSPECTOR_STATE') setInspect(!!d.active);
      if (d.type === 'VISUAL_ELEMENT_SELECTED') {
        setInspect(false);
        setPinned({ componentId: d.componentId, label: d.label, tag: d.tag, className: d.className, isImage: d.isImage, src: d.src, text: d.text });
        setEditMode('edit');
        if (d.isImage && d.src) setImageModal(true);
        setActiveTab('chat');
        setPrompt('');
      }
    };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, []);

  // ── Interview meta ────────────────────────────────────────────────────────
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/interview/meta`).then(r => r.json()).then(setMeta).catch(() => {});
  }, []);

  // ── Auto-scroll logs ──────────────────────────────────────────────────────
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // ── Fetch file list ───────────────────────────────────────────────────────
  const fetchLatestCode = async (id) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/latest-code?project_id=${id}`);
      if (res.ok) {
        const data = await res.json();
        setFiles(data.files);
        if (!selectedFile || !data.files[selectedFile]) {
          const def = Object.keys(data.files).find(f => f.endsWith('index.html')) || Object.keys(data.files)[0];
          setSelectedFile(def);
        }
      }
    } catch (err) { console.error('fetchLatestCode:', err); }
  };

  // ── SRS file upload ───────────────────────────────────────────────────────
  const handleSrsUpload = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    e.target.value = '';
    setLogs(prev => [...prev, `[USER]: uploaded ${file.name}`, '[AGENT]: Reading your SRS…']);
    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const r = new FileReader();
        r.onload = () => resolve(String(r.result || ''));
        r.onerror = reject;
        r.readAsDataURL(file);
      });
      const res = await fetch(`${API_BASE_URL}/api/srs/extract`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: file.name, data_b64: dataUrl }),
      });
      const data = await res.json();
      if (!res.ok || !data.text) throw new Error(errText(data, 'could not read file'));
      runGeneration(data.text, null, true, `Uploaded ${file.name}`);
    } catch (err) {
      setLogs(prev => [...prev, `SRS upload failed: ${err.message}`]);
    }
  };

  // ── Core generation / update ──────────────────────────────────────────────
  const runGeneration = async (currentPrompt, intakeAnswers, isNew, versionLabel) => {
    setStatus(isNew ? 'generating' : 'updating');
    if (isNew) { setPreviewUrl(null); setPhase('planning'); }
    setLogs(prev => [...prev, `[USER]: ${currentPrompt}`]);
    const url = isNew ? `${API_BASE_URL}/api/generate` : `${API_BASE_URL}/api/update`;
    const payload = { prompt: currentPrompt, project_id: projectId, intake: intakeAnswers || null, ai_sections: false };
    try {
      const response = await fetch(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error('Failed to connect to API server.');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));
              setLogs(prev => [...prev, data.log]);
              if (data.project_id && isNew) setProjectId(data.project_id);
              if (data.status === 'completed') {
                setStatus('completed');
                if (versionLabel || currentPrompt) setPromptsHistory(prev => [...prev, versionLabel || currentPrompt]);
                await fetchLatestCode(data.project_id || projectId);
                setPreviewVersion(v => v + 1);
              } else if (data.status === 'failed') {
                setStatus('failed');
              }
            } catch (e) { console.error('SSE parse error:', e); }
          }
        }
      }
    } catch (err) {
      setLogs(prev => [...prev, `CRITICAL ERROR: ${err.message}`]);
      setStatus('failed');
    }
  };

  // ── Interview step engine ─────────────────────────────────────────────────
  const draftFor = (q) => {
    if (!q) return null;
    if (q.kind === 'text') return q.default || '';
    if (q.kind === 'toggle') return q.default === true;
    if (q.kind === 'single') return q.default || (q.options && q.options[0] && q.options[0].value) || '';
    if (q.kind === 'entity_layouts') return (q.default || q.items || []).map(it => ({ ...it }));
    if (q.id === 'pages') {
      const opts = q.options || [];
      return (q.default || []).map(v => { const o = opts.find(x => x.value === v); return o ? { value: o.value, label: o.label, template: o.template } : { value: v, label: v, template: 'content' }; });
    }
    return [...(q.default || [])];
  };

  const applyStep = (data) => {
    if (data.done) {
      setPlan(null); setQuestion(null); setDraft(null); setStepHistory([]);
      runGeneration(interviewPrompt, data.answers, true);
      return;
    }
    setQuestion(data.question);
    setDraft(draftFor(data.question));
    setProgress(data.progress || { index: 0, total: 0 });
  };

  const startInterview = async (p) => {
    setInterviewLoading(true);
    setLogs(prev => [...prev, `[USER]: ${p.length > 120 ? p.slice(0, 120) + '…' : p}`, '[AGENT]: Planning your questions…']);
    try {
      const res = await fetch(`${API_BASE_URL}/api/interview/start`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: p, app_type: appType, language: lang }),
      });
      if (!res.ok) throw new Error('interview unavailable');
      const data = await res.json();
      setPlan(data.plan); setAnswers({}); setStepHistory([]); setInterviewPrompt(p);
      applyStep(data);
    } catch (e) {
      setLogs(prev => [...prev, `Interview unavailable (${e.message}); generating directly.`]);
      runGeneration(p, null, true);
    } finally { setInterviewLoading(false); }
  };

  const recordAnswer = (q, d, prev) => {
    const a = { ...prev };
    if (q.id === 'pages') { a.pages = d; a.components = { ...(a.components || {}) }; }
    else if (q.id.startsWith('sections:')) { a.components = { ...(a.components || {}), [q.id.slice(9)]: d }; }
    else if (q.id === 'auth') a.auth = d;
    else if (q.id === 'roles') a.roles = d;
    else if (q.id === 'entities') a.entities = d;
    else if (q.id.startsWith('design:')) a.design = { ...(a.design || {}), [q.id.slice(7)]: d };
    else if (q.id.startsWith('cov:')) a.coverage = { ...(a.coverage || {}), [q.id.slice(4)]: d };
    else if (q.id.startsWith('extra:')) a.extras = { ...(a.extras || {}), [q.id.slice(6)]: d };
    else if (q.id === 'theme') a.theme = d;
    return a;
  };

  const nextStep = async () => {
    if (!question) return;
    const newAnswers = recordAnswer(question, draft, answers);
    setStepHistory(h => [...h, { answers, question, draft, progress }]);
    setAnswers(newAnswers);
    setInterviewLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/interview/step`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan, answers: newAnswers }),
      });
      applyStep(await res.json());
    } catch (e) { setLogs(prev => [...prev, `Step failed (${e.message}).`]); }
    finally { setInterviewLoading(false); }
  };

  const stepBack = () => setStepHistory(h => {
    if (!h.length) return h;
    const last = h[h.length - 1];
    setAnswers(last.answers); setQuestion(last.question); setDraft(last.draft); setProgress(last.progress);
    return h.slice(0, -1);
  });

  const cancelInterview = () => { setPlan(null); setQuestion(null); setDraft(null); setStepHistory([]); };

  const apiPost = async (path, body) => {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    return res.json();
  };

  // ── Element editing ───────────────────────────────────────────────────────
  const editElement = async (instruction) => {
    setEditing(true);
    setLogs(prev => [...prev, `[EDIT ${pinned?.label || pinned?.componentId}]: ${instruction}`]);
    try {
      const data = await apiPost('/api/edit-element', {
        project_id: projectId, component_id: pinned.componentId, prompt: instruction,
        tag: pinned.tag, text: pinned.text, class_name: pinned.className,
      });
      if (isVersionSuccess(data)) { setLogs(prev => [...prev, `[AGENT]: Updated ${data.file} ✓ (${data.mode})`]); setPromptsHistory(prev => [...prev, instruction]); setPinned(null); }
      else if (data.needs_clarification) { setLogs(prev => [...prev, `[AGENT ❓]: ${data.question || 'Could you clarify that edit?'}`]); }
      else setLogs(prev => [...prev, `[AGENT]: ${errText(data, 'edit failed')}${data.reverted ? ' (reverted)' : ''}`]);
    } catch (err) { setLogs(prev => [...prev, `Edit failed: ${err.message}`]); }
    finally { setEditing(false); }
  };

  const quickStyle = async (instruction) => {
    if (!pinned || editing) return;
    setEditing(true);
    try {
      const data = await apiPost('/api/edit-element', {
        project_id: projectId, component_id: pinned.componentId, prompt: instruction,
        tag: pinned.tag, text: null, class_name: pinned.className,
      });
      if (data.ok) {
        setLogs(prev => [...prev, `[STYLE] ${pinned.tag}: ${instruction} ✓`]);
        if (data.new_class_name) setPinned(pn => pn ? { ...pn, className: data.new_class_name } : pn);
      } else setLogs(prev => [...prev, `[AGENT]: ${errText(data, 'could not apply')}`]);
    } catch (err) { setLogs(prev => [...prev, `Style failed: ${err.message}`]); }
    finally { setEditing(false); }
  };

  const addSection = async (instruction) => {
    setEditing(true);
    setLogs(prev => [...prev, `[ADD SECTION on ${pinned?.label}]: ${instruction}`]);
    try {
      const data = await apiPost('/api/add-section', {
        project_id: projectId, component_id: pinned.componentId, prompt: instruction,
        insert_position: insertPosition, selected_text: pinned.text, selected_class: pinned.className,
      });
      if (isVersionSuccess(data)) { setLogs(prev => [...prev, `[AGENT]: Added section to ${data.file} ✓${data.placement ? ` (${data.placement})` : ''}`]); setPromptsHistory(prev => [...prev, instruction]); setPinned(null); setEditMode('edit'); }
      else setLogs(prev => [...prev, `[AGENT]: ${errText(data, 'could not add section')}${data.reverted ? ' (reverted)' : ''}`]);
    } catch (err) { setLogs(prev => [...prev, `Add-section failed: ${err.message}`]); }
    finally { setEditing(false); }
  };

  // ── Image modal ───────────────────────────────────────────────────────────
  const replaceImageUpload = async (file) => {
    if (!file || !pinned?.src) return;
    setEditing(true);
    const dataUrl = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result || '')); r.onerror = rej; r.readAsDataURL(file); });
    const data = await apiPost('/api/upload-image', { project_id: projectId, component_id: pinned.componentId, src: pinned.src, data_b64: dataUrl });
    setLogs(prev => [...prev, data.ok ? '[AGENT]: Image replaced ✓' : `[AGENT]: ${errText(data, 'image upload failed')}`]);
    if (data.ok) { setImageModal(false); setPinned(null); setPreviewVersion(v => v + 1); }
    setEditing(false);
  };

  const replaceImageAI = async () => {
    if (!imgPrompt.trim() || !pinned?.src) return;
    setEditing(true);
    setLogs(prev => [...prev, `[AGENT]: Generating image — "${imgPrompt}"…`]);
    const data = await apiPost('/api/generate-image', { project_id: projectId, component_id: pinned.componentId, src: pinned.src, prompt: imgPrompt });
    setLogs(prev => [...prev, data.ok ? '[AGENT]: New image generated ✓' : `[AGENT]: ${errText(data, 'image generation failed')}`]);
    if (data.ok) { setImageModal(false); setPinned(null); setImgPrompt(''); setPreviewVersion(v => v + 1); }
    setEditing(false);
  };

  // ── Send / dispatch ───────────────────────────────────────────────────────
  const handleSend = () => {
    if (!prompt.trim()) return;
    const currentPrompt = prompt;
    setPrompt('');
    if (projectId && pinned && editMode === 'add') addSection(currentPrompt);
    else if (projectId && pinned) editElement(currentPrompt);
    else if (!projectId) runGeneration(currentPrompt, null, true);
    else runGeneration(currentPrompt, null, false);
  };

  // ── Interview draft helpers ───────────────────────────────────────────────
  const toggleDraftValue = (v, label, template) => setDraft(d => {
    const arr = Array.isArray(d) ? d : [];
    const has = arr.some(x => (x.value ?? x) === v);
    if (has) return arr.filter(x => (x.value ?? x) !== v);
    return [...arr, question.id === 'pages' ? { value: v, label: label || v, template: template || 'content' } : v];
  });
  const addDraftCustom = (text) => {
    const t = String(text).trim(); if (!t) return;
    if (question.id === 'pages') {
      const v = t.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 24) || 'page';
      setDraft(d => (d || []).some(x => x.value === v) ? d : [...(d || []), { value: v, label: t, template: 'content' }]);
    } else {
      setDraft(d => (d || []).includes(t) ? d : [...(d || []), t]);
    }
  };
  const setEntityLayoutDraft = (name, layout) => setDraft(d => (d || []).map(e => e.name === name ? { ...e, layout } : e));
  const addEntityDraft = (name) => {
    const v = String(name).trim();
    if (!v) return;
    setDraft(d => (d || []).some(e => e.name === v) ? d : [...(d || []), { name: v.replace(/[^A-Za-z0-9]/g, ''), label: v, layout: 'table' }]);
  };

  const handleDownload = () => { if (!projectId) return; window.open(`${API_BASE_URL}/api/download?project_id=${projectId}`); };
  const toggleInspect = () => {
    const next = !inspect;
    setInspect(next);
    try { iframeRef.current?.contentWindow?.postMessage({ type: 'SET_INSPECTOR_STATE', active: next }, '*'); } catch (e) {}
  };

  // ── Chip / input style helpers (interview UI) ─────────────────────────────
  const chipSt = (active, sm) => ({
    padding: sm ? '3px 8px' : '5px 11px', borderRadius: '4px', fontSize: sm ? '11px' : '12px',
    cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap', fontFamily: 'var(--font-mono)',
    border: '1px solid ' + (active ? 'var(--acc)' : 'var(--bdr)'),
    background: active ? 'rgba(217,119,6,.15)' : 'transparent',
    color: active ? 'var(--acc)' : 'var(--muted)',
  });
  const inputSt = {
    width: '100%', marginTop: '6px', padding: '6px 9px', fontSize: '12px', borderRadius: '4px',
    border: '1px solid var(--bdr)', background: 'transparent', color: 'inherit', fontFamily: 'var(--font-mono)',
  };
  const vpBtn = {
    padding: '2px 8px', borderRadius: '3px', fontSize: '11px', cursor: 'pointer', whiteSpace: 'nowrap',
    border: '1px solid var(--bdr)', background: 'rgba(255,255,255,.03)', color: 'var(--muted)', fontFamily: 'var(--font-mono)',
  };
  const vpMini = (active) => ({
    padding: '1px 7px', borderRadius: '3px', fontSize: '10px', cursor: 'pointer', fontFamily: 'var(--font-mono)',
    border: '1px solid ' + (active ? 'var(--acc)' : 'transparent'),
    background: active ? 'rgba(217,119,6,.18)' : 'transparent',
    color: active ? 'var(--acc)' : 'var(--muted)',
  });
  const VP_CONTROLS = [
    ['Bold', 'make it bold'], ['Thin', 'make it thin'], ['A−', 'smaller text'], ['A+', 'bigger text'],
    ['Left', 'align left'], ['Center', 'center the text'], ['Right', 'align right'], ['Italic', 'italic'],
    ['Round', 'rounded corners'], ['Pill', 'pill shape'], ['Square', 'sharp corners'],
    ['Pad−', 'less padding'], ['Pad+', 'more padding'], ['Shadow', 'add a big shadow'], ['Border', 'add a thin border'],
  ];
  const VP_SWATCHES = [['#0f172a','slate'],['#ef4444','red'],['#f59e0b','amber'],['#10b981','emerald'],['#3b82f6','blue'],['#8b5cf6','violet'],['#ec4899','pink'],['#ffffff','white']];

  const isWorking = status === 'generating' || status === 'updating';

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="app-container">

      {/* ═══════════════════════════════ LEFT PANEL ═══════════════════════════ */}
      <div className="sidebar">

        {/* Title bar */}
        <div className="sidebar-titlebar">
          <span className="sidebar-title">
            <span className="title-diamond">◆</span> AI Designer
          </span>
          {isWorking && phase && phase !== 'done' && phase !== 'error' && (
            <span className="phase-badge">
              <span className="phase-pulse" />
              {PHASE_LABELS[phase] || 'working…'}
            </span>
          )}
          {status === 'completed' && (
            <span className="phase-done">✓ done</span>
          )}
          {status === 'failed' && (
            <span className="phase-error">✗ failed</span>
          )}
        </div>

        {/* Tab switcher */}
        <div className="tab-row">
          <button className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
            chat
          </button>
          <button className={`tab-btn ${activeTab === 'files' ? 'active' : ''}`} onClick={() => setActiveTab('files')} disabled={!projectId}>
            source
          </button>
          <div style={{ flex: 1 }} />
          <input ref={srsFileRef} type="file" accept=".pdf,.json,.txt,application/json,application/pdf" style={{ display: 'none' }} onChange={handleSrsUpload} />
          <button className="srs-upload-btn" onClick={() => srsFileRef.current?.click()} title="Upload SRS JSON spec">
            <FileUp size={13} /> SRS
          </button>
        </div>

        {/* ── CHAT TAB ── */}
        {activeTab === 'chat' && (
          <div className="chat-panel">

            {/* ── INTERVIEW WIZARD ── */}
            {question ? (
              <div className="interview-body">
                <div className="interview-header">
                  <span className="iw-app-name">{plan?.app_name || 'Your app'}</span>
                  <span className="iw-progress">{Math.min((progress.index || 0) + 1, progress.total || 1)}/{progress.total || 1}</span>
                </div>
                <div className="iw-progress-bar">
                  <div className="iw-progress-fill" style={{ width: `${Math.round(100 * (progress.index || 0) / Math.max(1, progress.total || 1))}%` }} />
                </div>

                <div className="iw-question">{question.label}</div>
                {question.hint && <div className="iw-hint">{question.hint}</div>}

                {question.kind === 'text' ? (
                  <textarea value={draft || ''} onChange={e => setDraft(e.target.value)} rows={4}
                    placeholder="Type here…" style={{ ...inputSt, resize: 'vertical' }} />
                ) : question.kind === 'toggle' ? (
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <span onClick={() => setDraft(true)} style={chipSt(draft === true)}>{question.yes || 'Yes'}</span>
                    <span onClick={() => setDraft(false)} style={chipSt(draft !== true)}>{question.no || 'No'}</span>
                  </div>
                ) : question.kind === 'single' ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                    {(question.options || []).map(o => (
                      <span key={o.value} onClick={() => setDraft(o.value)} style={chipSt(draft === o.value)}>{o.label}</span>
                    ))}
                  </div>
                ) : question.kind === 'entity_layouts' ? (
                  <div>
                    {(draft || []).map(e => (
                      <div key={e.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '5px' }}>
                        <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)' }}>{e.label || e.name}</span>
                        <select value={e.layout} onChange={ev => setEntityLayoutDraft(e.name, ev.target.value)} style={{ ...inputSt, width: 'auto', marginTop: 0 }}>
                          {(question.layout_options || ['table']).map(l => <option key={l} value={l}>{l}</option>)}
                        </select>
                      </div>
                    ))}
                    {question.allow_custom && <input placeholder="+ add data entity, press Enter" onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addEntityDraft(e.target.value); e.target.value = ''; } }} style={inputSt} />}
                  </div>
                ) : (
                  <div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                      {(question.options || []).map(o => (
                        <span key={o.value} onClick={() => toggleDraftValue(o.value, o.label, o.template)} style={chipSt((draft || []).some(x => (x.value ?? x) === o.value))}>{o.label}</span>
                      ))}
                      {(draft || []).filter(x => !(question.options || []).some(o => o.value === (x.value ?? x))).map(x => (
                        <span key={x.value ?? x} onClick={() => toggleDraftValue(x.value ?? x)} style={chipSt(true)}>{(x.label ?? x)} ✕</span>
                      ))}
                    </div>
                    {question.allow_custom && <input placeholder="+ type your own, press Enter" onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addDraftCustom(e.target.value); e.target.value = ''; } }} style={inputSt} />}
                  </div>
                )}

                <div style={{ flex: 1 }} />
                <div style={{ display: 'flex', gap: '8px' }}>
                  {stepHistory.length > 0 && (
                    <button onClick={stepBack} disabled={interviewLoading} className="iw-back-btn">← back</button>
                  )}
                  <button onClick={nextStep} disabled={interviewLoading || (question.id === 'pages' && (!draft || draft.length === 0))} className="iw-next-btn">
                    {interviewLoading ? 'thinking…' : ((progress.index >= (progress.total - 1)) ? (plan?.labels?.generate || 'generate →') : 'next →')}
                  </button>
                </div>
                <button onClick={cancelInterview} className="iw-cancel-btn">cancel</button>
              </div>
            ) : (
              <>
                {/* ── TERMINAL STREAM (main content area) ── */}
                <div className="term-stream">
                  {logs.length === 0 && !interviewLoading ? (
                    /* Welcome state */
                    <div className="term-welcome">
                      <div className="tw-pre">$ ai designer</div>
                      <div className="tw-heading">Build full-stack web apps</div>
                      <div className="tw-sub">
                        Upload an SRS JSON spec for zero-question generation — pages, roles, CRUD, workflows, and real domain images all built automatically.
                      </div>
                      <div className="tw-divider" />
                      <div className="tw-sub" style={{ opacity: 0.5, marginBottom: 0 }}>
                        Or describe what you want below and press Enter.
                      </div>
                    </div>
                  ) : (
                    /* Live terminal log stream */
                    <>
                      {promptsHistory.length > 0 && (
                        <div className="term-versions">
                          {promptsHistory.map((label, i) => (
                            <span key={i} className="ver-chip">v{i + 1}</span>
                          ))}
                        </div>
                      )}
                      {logs.map((log, i) => (
                        <div key={i} className={`term-line ${logClass(log)}`}>
                          <span className="tl-gutter">{logGutter(log)}</span>
                          <span className="tl-text">{log}</span>
                        </div>
                      ))}
                      {isWorking && <span className="term-cursor">▮</span>}
                    </>
                  )}
                  <div ref={logsEndRef} />
                </div>

                {/* ── PROMPT INPUT ── */}
                {!plan && (
                  <div className="prompt-area">
                    {/* Pinned element chip */}
                    {pinned && (
                      <div className="pinned-chip">
                        <div className="pinned-top">
                          <Crosshair size={11} />
                          <span className="pinned-tag">{pinned.tag || 'el'}</span>
                          <span className="pinned-label">{pinned.label}</span>
                          <button onClick={() => { setPinned(null); setEditMode('edit'); }} className="pinned-clear">
                            <X size={11} />
                          </button>
                        </div>
                        <div className="pinned-modes">
                          <span onClick={() => setEditMode('edit')} className={`mode-chip ${editMode === 'edit' ? 'active' : ''}`}>edit</span>
                          <span onClick={() => setEditMode('add')} className={`mode-chip ${editMode === 'add' ? 'active' : ''}`}>+ add section</span>
                          {pinned.isImage && <span onClick={() => setImageModal(true)} className="mode-chip">change image</span>}
                        </div>

                        {editMode === 'add' && (
                          <div className="pinned-pos">
                            <span className="pos-label">position</span>
                            {['before', 'after', 'inside'].map(pos => (
                              <span key={pos} onClick={() => setInsertPosition(pos)} className={`mode-chip ${insertPosition === pos ? 'active' : ''}`}>{pos}</span>
                            ))}
                          </div>
                        )}

                        {editMode === 'edit' && !pinned.isImage && (
                          <div className="vpm-panel" style={{ opacity: editing ? 0.5 : 1, pointerEvents: editing ? 'none' : 'auto' }}>
                            <div className="vpm-row">
                              <span className="vpm-label">COLOR</span>
                              <span onClick={() => setVpFill(false)} style={vpMini(!vpFill)}>text</span>
                              <span onClick={() => setVpFill(true)} style={vpMini(vpFill)}>fill</span>
                            </div>
                            <div className="vpm-swatches">
                              {VP_SWATCHES.map(([hex, name]) => (
                                <button key={name} title={name} disabled={editing} onClick={() => quickStyle(`${name}${vpFill ? ' background' : ' text'}`)}
                                  style={{ width: '16px', height: '16px', borderRadius: '50%', background: hex, border: '1px solid rgba(255,255,255,.25)', cursor: 'pointer', padding: 0 }} />
                              ))}
                            </div>
                            <div className="vpm-controls">
                              {VP_CONTROLS.map(([label, instr]) => (
                                <button key={label} disabled={editing} onClick={() => quickStyle(instr)} style={vpBtn}>{label}</button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    <textarea
                      className="prompt-textarea"
                      placeholder={
                        pinned
                          ? (editMode === 'add' ? 'Describe the new section…' : `Describe the change to "${pinned.label}"…`)
                          : projectId ? 'Describe changes or new features…' : 'Describe the app you want to build…'
                      }
                      value={prompt}
                      onChange={e => setPrompt(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                      disabled={isWorking}
                    />
                    <div className="prompt-footer">
                      <span className="prompt-hint">
                        {isWorking ? (PHASE_LABELS[phase] || 'working…') : 'enter to send · shift+enter for newline'}
                      </span>
                      <button className="send-btn" onClick={handleSend} disabled={!prompt.trim() || isWorking}>
                        <Send size={14} />
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ── SOURCE TAB ── */}
        {activeTab === 'files' && projectId && (
          <div className="source-panel">
            <div className="source-heading">workspace files</div>
            {Object.keys(files).map(filepath => (
              <div key={filepath} className={`source-item ${selectedFile === filepath ? 'active' : ''}`}
                onClick={() => { setSelectedFile(filepath); setMode('code'); }}>
                <FileText size={12} style={{ color: filepath.endsWith('.html') ? '#f97316' : '#38bdf8', flexShrink: 0 }} />
                <span>{filepath}</span>
              </div>
            ))}
          </div>
        )}

        {/* ── Image modal ── */}
        {imageModal && pinned?.isImage && (
          <div className="modal-backdrop" onClick={() => setImageModal(false)}>
            <div className="img-modal" onClick={e => e.stopPropagation()}>
              <div className="img-modal-header">
                <span>update image</span>
                <button onClick={() => setImageModal(false)} className="modal-close"><X size={14} /></button>
              </div>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '12px' }}>
                <input ref={imgFileRef} type="file" accept="image/*" style={{ display: 'none' }}
                  onChange={e => { const f = e.target.files?.[0]; e.target.value = ''; if (f) replaceImageUpload(f); }} />
                <button onClick={() => imgFileRef.current?.click()} disabled={editing} className="img-upload-zone">
                  ↑ upload
                </button>
                <div style={{ width: '80px', height: '80px', borderRadius: '4px', overflow: 'hidden', border: '1px solid var(--acc)' }}>
                  <img src={`${previewUrl || ''}${pinned.src}`} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={e => { e.currentTarget.style.display = 'none'; }} />
                </div>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '6px' }}>or regenerate with AI</div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <input value={imgPrompt} onChange={e => setImgPrompt(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') replaceImageAI(); }}
                  placeholder="Describe the new image…" style={{ ...inputSt, marginTop: 0, flex: 1 }} disabled={editing} />
                <button onClick={replaceImageAI} disabled={editing || !imgPrompt.trim()} className="img-gen-btn">
                  {editing ? '…' : 'gen'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ═══════════════════════════════ RIGHT PANEL ══════════════════════════ */}
      <div className="preview-pane">

        {/* Pane header */}
        <div className="pane-header">
          <div className="view-tabs">
            <button className={`view-tab ${mode === 'preview' ? 'active' : ''}`} onClick={() => setMode('preview')} disabled={!projectId}>preview</button>
            <button className={`view-tab ${mode === 'code' ? 'active' : ''}`} onClick={() => setMode('code')} disabled={!projectId}>code</button>
          </div>

          {projectId && (
            <div className="pane-controls">
              {mode === 'preview' && (
                <>
                  <button className="ctrl-btn" onClick={() => setPreviewVersion(v => v + 1)} title="Reload preview">
                    <RefreshCw size={15} />
                  </button>
                  <button className={`ctrl-btn ${inspect ? 'active' : ''}`} onClick={toggleInspect} disabled={!previewUrl} title="Select element">
                    <Crosshair size={15} />
                  </button>
                  <div className="size-group">
                    <button className={`ctrl-btn ${previewSize === 'mobile' ? 'active' : ''}`} onClick={() => setPreviewSize('mobile')} title="Mobile">
                      <Smartphone size={14} />
                    </button>
                    <button className={`ctrl-btn ${previewSize === 'tablet' ? 'active' : ''}`} onClick={() => setPreviewSize('tablet')} title="Tablet">
                      <Tablet size={14} />
                    </button>
                    <button className={`ctrl-btn ${previewSize === 'desktop' ? 'active' : ''}`} onClick={() => setPreviewSize('desktop')} title="Desktop">
                      <Monitor size={14} />
                    </button>
                  </div>
                </>
              )}
              <button className="download-btn" onClick={handleDownload}>
                <Download size={14} /> download
              </button>
            </div>
          )}
        </div>

        {/* Preview / Code area */}
        {!projectId ? (
          /* Empty state */
          <div className="preview-empty">
            <div className="empty-ascii">◆</div>
            <div className="empty-title">no project yet</div>
            <div className="empty-sub">upload an SRS spec or describe your app in the chat to start generating</div>
          </div>
        ) : mode === 'preview' ? (
          <div className="preview-area">
            {!previewUrl ? (
              /* Build loading state */
              <div className="build-status">
                {phase === 'error' ? (
                  <div className="bs-error">
                    <AlertCircle size={20} />
                    <span>build failed — check logs</span>
                  </div>
                ) : (
                  <div className="bs-working">
                    <div className="bs-steps">
                      {['planning','scaffold','pages','images','building'].map((s, i) => {
                        const phaseOrder = { planning: 0, genome: 0, scaffold: 1, pages: 2, image_generating: 3, image_integrating: 3, qa: 3, validating: 3, building: 4 };
                        const cur = phaseOrder[phase] ?? -1;
                        const done = cur > i;
                        const active = cur === i;
                        return (
                          <React.Fragment key={s}>
                            <span className={`bs-step ${done ? 'done' : active ? 'active' : ''}`}>{done ? '✓' : active ? '●' : '○'} {s}</span>
                            {i < 4 && <span className="bs-sep">──</span>}
                          </React.Fragment>
                        );
                      })}
                    </div>
                    <div className="bs-label">{PHASE_LABELS[phase] || 'working…'}</div>
                    <div className="bs-bar">
                      <div className="bs-bar-fill" style={{ width: `${({ planning: 10, genome: 15, scaffold: 25, pages: 45, image_generating: 65, image_integrating: 75, qa: 80, validating: 85, building: 95 }[phase] || 5)}%` }} />
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className={`iframe-wrap ${previewSize}`} style={{ position: 'relative' }}>
                <iframe
                  ref={iframeRef}
                  className="preview-iframe"
                  src={`${previewUrl}?v=${previewVersion}`}
                  title="AI Designer Preview"
                  style={{ filter: editing ? 'blur(4px)' : 'none', pointerEvents: editing ? 'none' : 'auto', transition: 'filter .15s' }}
                />
                {editing && (
                  <div className="edit-overlay">
                    <div className="edit-spinner" />
                    <span>{pinned ? `updating ${pinned.label}…` : 'updating…'}</span>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          /* Code view */
          <div className="code-view">
            <div className="code-header">
              <span className="code-filename">{selectedFile || '─'}</span>
            </div>
            <pre className="code-body">
              <code>{selectedFile ? files[selectedFile] : '// select a file from the source tab'}</code>
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
