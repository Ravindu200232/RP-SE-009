import React, { useState, useEffect, useRef } from 'react';
import { Sparkles, Play, Send, RefreshCw, Smartphone, Tablet, Monitor, Download, FileText, ChevronRight, MessageSquare, Terminal, Crosshair, X, FileUp } from 'lucide-react';
import { errText } from './lib/errText.js';
import { isVersionSuccess } from './lib/versioning.js';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [prompt, setPrompt] = useState('');
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' | 'files'
  const [mode, setMode] = useState('preview'); // 'preview' | 'code'
  const [previewSize, setPreviewSize] = useState('desktop'); // 'desktop' | 'tablet' | 'mobile'
  const [projectId, setProjectId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState('idle'); // 'idle' | 'generating' | 'updating' | 'completed' | 'failed'
  const [files, setFiles] = useState({});
  const [selectedFile, setSelectedFile] = useState(null);
  const [promptsHistory, setPromptsHistory] = useState([]);
  const [showLogs, setShowLogs] = useState(true);
  const [previewVersion, setPreviewVersion] = useState(0); // bump to force iframe reload after (re)generation
  const [phase, setPhase] = useState(null); // backend status.json phase (gated preview)
  const [previewUrl, setPreviewUrl] = useState(null); // running Next app URL (set only when phase === done)
  const [inspect, setInspect] = useState(false); // "Select Element" inspector toggle
  const [pinned, setPinned] = useState(null); // {componentId,label} captured from the preview
  const [interview, setInterview] = useState(null); // questionnaire from /api/interview
  const [answers, setAnswers] = useState(null); // collected interview answers
  const [interviewPrompt, setInterviewPrompt] = useState(''); // original description being interviewed
  const [interviewLoading, setInterviewLoading] = useState(false);
  const [lang, setLang] = useState('en'); // chosen interview language
  const [appType, setAppType] = useState('hybrid'); // public | internal | hybrid
  const [meta, setMeta] = useState({ languages: [{ value: 'en', label: 'English' }], app_types: [] });
  const [plan, setPlan] = useState(null); // interview plan from /interview/start
  const [question, setQuestion] = useState(null); // current step question (one at a time)
  const [draft, setDraft] = useState(null); // answer being edited for the current question
  const [progress, setProgress] = useState({ index: 0, total: 0 });
  const [stepHistory, setStepHistory] = useState([]); // snapshots for the Back button
  const [aiSections, setAiSections] = useState(false); // opt-in: Gemma writes each section
  const [editing, setEditing] = useState(false); // a Select-Element edit is in flight
  const [editMode, setEditMode] = useState('edit'); // 'edit' | 'add' (add a section here)
  const [imageModal, setImageModal] = useState(false); // "Update image" popup
  const [imgPrompt, setImgPrompt] = useState('');
  const imgFileRef = useRef(null);
  const [vpFill, setVpFill] = useState(false); // Visual Parameter Map: colour target (false=text, true=background)

  const logsEndRef = useRef(null);
  const iframeRef = useRef(null);

  // Gated preview: poll the project phase while working; only when the backend
  // reports "done" do we start the Next server and reveal the preview.
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
            if (pr.ok) {
              const { url } = await pr.json();
              if (!stop) setPreviewUrl(url);
            }
            return;
          }
          if (s.phase === 'error') return;
        }
      } catch (e) { /* backend busy - keep polling */ }
      if (!stop) setTimeout(tick, 2500);
    };
    tick();
    return () => { stop = true; };
  }, [projectId, status, previewUrl]);

  // SECTION 4: "Select Element" - receive the component the user clicked inside
  // the preview iframe, pin it, and pre-fill the chat for a TARGETED edit.
  useEffect(() => {
    const onMsg = (e) => {
      const d = e.data || {};
      if (d.type === 'INSPECTOR_STATE') setInspect(!!d.active);
      if (d.type === 'VISUAL_ELEMENT_SELECTED') {
        setInspect(false);
        setPinned({ componentId: d.componentId, label: d.label, tag: d.tag, className: d.className, isImage: d.isImage, src: d.src, text: d.text });
        setEditMode('edit');
        if (d.isImage && d.src) setImageModal(true);   // image -> open the Update-image modal
        setActiveTab('chat');
        setPrompt('');   // pinned chip shows the target; user just types the change
      }
    };
    window.addEventListener('message', onMsg);
    return () => window.removeEventListener('message', onMsg);
  }, []);

  // Languages + app types for the first interview screen.
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/interview/meta`).then(r => r.json()).then(setMeta).catch(() => {});
  }, []);

  // Images generate in the background after the app is shown; refresh the
  // preview a few times so they pop in without the user reloading manually.
  useEffect(() => {
    if (!previewUrl) return;
    const timers = [60000, 150000, 300000].map(ms => setTimeout(() => setPreviewVersion(v => v + 1), ms));
    return () => timers.forEach(clearTimeout);
  }, [previewUrl]);

  const toggleInspect = () => {
    const next = !inspect;
    setInspect(next);
    try {
      iframeRef.current?.contentWindow?.postMessage({ type: 'SET_INSPECTOR_STATE', active: next }, '*');
    } catch (e) { /* iframe not ready */ }
  };

  // SRS JSON input: paste OR upload a .json spec; the backend detects it and
  // generates an app that fulfills the full spec (entities, roles, pages).
  const srsFileRef = useRef(null);
  const handleSrsUpload = async (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    e.target.value = '';
    // NOTE: no version is recorded here — only after generation completes (below),
    // so a failed SRS read / failed build never leaves a false "Uploaded X" version.
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
      // SRS is the single source of truth: NO questions - plan pages/flow/
      // functions/relations/CRUD from the spec and build straight away.
      runGeneration(data.text, null, true, aiSections, `Uploaded ${file.name}`);
    } catch (err) {
      setLogs(prev => [...prev, `SRS upload failed: ${err.message}`]);
    }
  };

  const PHASE_LABELS = {
    planning: 'Planning the application...',
    pages: 'Generating pages...',
    images: 'Image generating...',
    qa: 'Quality check...',
    building: 'Building the app...',
    error: 'Something went wrong during the build.',
  };

  // Auto-scroll logs
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // Fetch file list and code
  const fetchLatestCode = async (id) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/latest-code?project_id=${id}`);
      if (res.ok) {
        const data = await res.json();
        setFiles(data.files);
        // Automatically select index.html if nothing selected
        if (!selectedFile || !data.files[selectedFile]) {
          const defaultFile = Object.keys(data.files).find(f => f.endsWith('index.html')) || Object.keys(data.files)[0];
          setSelectedFile(defaultFile);
        }
      }
    } catch (err) {
      console.error('Error fetching source files:', err);
    }
  };

  // Run the actual generation/update SSE stream (optionally with interview answers).
  const runGeneration = async (currentPrompt, intakeAnswers, isNew, aiSecs, versionLabel) => {
    setStatus(isNew ? 'generating' : 'updating');
    if (isNew) { setPreviewUrl(null); setPhase('planning'); }
    setLogs(prev => [...prev, `[USER]: ${currentPrompt}`]);

    const url = isNew ? `${API_BASE_URL}/api/generate` : `${API_BASE_URL}/api/update`;
    const payload = { prompt: currentPrompt, project_id: projectId, intake: intakeAnswers || null, ai_sections: !!aiSecs };

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
                if (versionLabel || currentPrompt) setPromptsHistory(prev => [...prev, versionLabel || currentPrompt]);  // version recorded ONLY on success
                await fetchLatestCode(data.project_id || projectId);
                setPreviewVersion(v => v + 1);
              } else if (data.status === 'failed') {
                setStatus('failed');
              }
            } catch (e) { console.error('Error parsing SSE event:', e); }
          }
        }
      }
    } catch (err) {
      setLogs(prev => [...prev, `CRITICAL ERROR: ${err.message}`]);
      setStatus('failed');
    }
  };

  // ---- one-question-at-a-time interview (step engine) ----
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
    } finally {
      setInterviewLoading(false);
    }
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
    } catch (e) {
      setLogs(prev => [...prev, `Step failed (${e.message}).`]);
    } finally {
      setInterviewLoading(false);
    }
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

  // errText() is imported from ./lib/errText.js (centralized + unit-tested) so the
  // studio NEVER renders "[object Object]" for any backend error shape.

  // Select-Element: edit ONLY the pinned component (sends its tag + text so text
  // edits are deterministic; styling goes to Gemma, scoped to that element).
  const editElement = async (instruction) => {
    setEditing(true);
    setLogs(prev => [...prev, `[EDIT ${pinned?.label || pinned?.componentId}]: ${instruction}`]);
    try {
      const data = await apiPost('/api/edit-element', {
        project_id: projectId, component_id: pinned.componentId, prompt: instruction,
        tag: pinned.tag, text: pinned.text, class_name: pinned.className,
      });
      if (isVersionSuccess(data)) { setLogs(prev => [...prev, `[AGENT]: Updated ${data.file} ✓ (${data.mode})`]); setPromptsHistory(prev => [...prev, instruction]); setPinned(null); /* next dev Fast Refresh (HMR) live-updates the element in place — no full reload, state preserved */ }
      else setLogs(prev => [...prev, `[AGENT]: ${errText(data, 'edit failed')}${data.reverted ? ' (reverted — app unchanged)' : ''}`]);
    } catch (err) { setLogs(prev => [...prev, `Edit failed: ${err.message}`]); }
    finally { setEditing(false); }
  };

  // Visual Parameter Map: a no-code property tweak fired by the floating panel
  // buttons. Reuses the deterministic STYLE_TWEAK engine (instant), KEEPS the
  // element pinned so the user can keep tweaking, and syncs pinned.className from
  // the response so successive tweaks target the up-to-date class string.
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
        // HMR updates the preview live; panel stays open for more tweaks
      } else setLogs(prev => [...prev, `[AGENT]: ${errText(data, 'could not apply')}`]);
    } catch (err) { setLogs(prev => [...prev, `Style failed: ${err.message}`]); }
    finally { setEditing(false); }
  };

  // Add a brand-new section to the page the pinned element belongs to.
  const addSection = async (instruction) => {
    setEditing(true);
    setLogs(prev => [...prev, `[ADD SECTION on ${pinned?.label}]: ${instruction}`]);
    try {
      const data = await apiPost('/api/add-section', { project_id: projectId, component_id: pinned.componentId, prompt: instruction });
      if (isVersionSuccess(data)) { setLogs(prev => [...prev, `[AGENT]: Added a new section to ${data.file} ✓`]); setPromptsHistory(prev => [...prev, instruction]); setPinned(null); setEditMode('edit'); /* HMR live-updates the page with the new section */ }
      else setLogs(prev => [...prev, `[AGENT]: ${errText(data, 'could not add section')}${data.reverted ? ' (reverted)' : ''}`]);
    } catch (err) { setLogs(prev => [...prev, `Add-section failed: ${err.message}`]); }
    finally { setEditing(false); }
  };

  // Image modal — Option A (upload) / Option B (AI regenerate).
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
    setLogs(prev => [...prev, `[AGENT]: Generating a new image — “${imgPrompt}”…`]);
    const data = await apiPost('/api/generate-image', { project_id: projectId, component_id: pinned.componentId, src: pinned.src, prompt: imgPrompt });
    setLogs(prev => [...prev, data.ok ? '[AGENT]: New image generated ✓' : `[AGENT]: ${errText(data, 'image generation failed')}`]);
    if (data.ok) { setImageModal(false); setPinned(null); setImgPrompt(''); setPreviewVersion(v => v + 1); }
    setEditing(false);
  };

  const handleSend = () => {
    if (!prompt.trim()) return;
    const currentPrompt = prompt;
    setPrompt('');
    // NOTE: a version is recorded ONLY on success, inside each handler below, so a
    // failed edit never appears as a successful version in the history.
    if (projectId && pinned && editMode === 'add') addSection(currentPrompt);    // add a section here
    else if (projectId && pinned) editElement(currentPrompt);                    // edit the selected element
    else if (!projectId) runGeneration(currentPrompt, null, true, aiSections);   // direct generation
    else runGeneration(currentPrompt, null, false);                             // whole-app update
  };

  // ---- draft mutations for the CURRENT question ----
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
  const addEntityDraft = (name) => { const v = String(name).trim(); if (!v) return; setDraft(d => (d || []).some(e => e.name === v) ? d : [...(d || []), { name: v.replace(/[^A-Za-z0-9]/g, ''), label: v, layout: 'table' }]); };

  const handleDownload = () => {
    if (!projectId) return;
    window.open(`${API_BASE_URL}/api/download?project_id=${projectId}`);
  };

  const handleReloadIframe = () => {
    setPreviewVersion(v => v + 1);
  };

  // interview chip / input styling
  const chipStyle = (active, small) => ({
    padding: small ? '4px 9px' : '5px 11px', borderRadius: '14px', fontSize: small ? '11px' : '12px',
    cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap',
    border: '1px solid ' + (active ? 'var(--accent-color, #7c3aed)' : 'var(--border-color, #3a3a3a)'),
    background: active ? 'rgba(124,58,237,.18)' : 'transparent',
    color: active ? 'var(--accent-color, #a78bfa)' : 'var(--text-secondary, #aaa)',
  });
  const inputStyle = {
    width: '100%', marginTop: '6px', padding: '6px 9px', fontSize: '12px', borderRadius: '8px',
    border: '1px solid var(--border-color, #3a3a3a)', background: 'transparent', color: 'inherit',
  };
  // Visual Parameter Map button styles
  const vpBtn = {
    padding: '3px 8px', borderRadius: '7px', fontSize: '11px', cursor: 'pointer', whiteSpace: 'nowrap',
    border: '1px solid var(--border-color, #3a3a3a)', background: 'rgba(255,255,255,.03)', color: 'var(--text-secondary, #cbd5e1)',
  };
  const vpMini = (active) => ({
    padding: '1px 7px', borderRadius: '6px', fontSize: '10px', cursor: 'pointer',
    border: '1px solid ' + (active ? 'var(--accent-color, #7c3aed)' : 'transparent'),
    background: active ? 'rgba(124,58,237,.2)' : 'transparent', color: active ? '#a78bfa' : 'var(--text-secondary, #94a3b8)',
  });
  // each = [label, the canned instruction sent through the deterministic STYLE_TWEAK engine]
  const VP_CONTROLS = [
    ['Bold', 'make it bold'], ['Thin', 'make it thin'], ['A−', 'smaller text'], ['A+', 'bigger text'],
    ['Left', 'align left'], ['Center', 'center the text'], ['Right', 'align right'], ['Italic', 'italic'],
    ['Round', 'rounded corners'], ['Pill', 'pill shape'], ['Square', 'sharp corners'],
    ['Pad −', 'less padding'], ['Pad +', 'more padding'], ['Shadow', 'add a big shadow'], ['Border', 'add a thin border'],
  ];
  const VP_SWATCHES = [['#0f172a', 'slate'], ['#ef4444', 'red'], ['#f59e0b', 'amber'], ['#10b981', 'emerald'], ['#3b82f6', 'blue'], ['#8b5cf6', 'violet'], ['#ec4899', 'pink'], ['#ffffff', 'white']];

  return (
    <div className="app-container">
      {/* LEFT PANEL: Chat and File List */}
      <div className="control-sidebar">
        <div className="brand-header">
          <div className="brand-logo">
            <Sparkles size={20} />
          </div>
          <div className="brand-title">AI Designer</div>
        </div>

        {/* Sidebar tabs selection */}
        <div className="tab-switcher">
          <button 
            className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            Chat & Steps
          </button>
          <button 
            className={`tab-btn ${activeTab === 'files' ? 'active' : ''}`}
            onClick={() => setActiveTab('files')}
            disabled={!projectId}
          >
            Source Code
          </button>
        </div>

        {/* Tab 1: Chat Interface */}
        {activeTab === 'chat' && (
          <div className="chat-container">
            {question ? (
              <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '14px 14px 20px', display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px' }}>
                {/* header + progress */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontWeight: 700, fontSize: '14px' }}>{plan?.app_name || 'Your app'}</div>
                    <div style={{ fontSize: '11px', opacity: 0.6 }}>{Math.min((progress.index || 0) + 1, progress.total || 1)} / {progress.total || 1}</div>
                  </div>
                  <div style={{ height: '4px', borderRadius: '4px', background: 'var(--border-color, #2a2a2a)', marginTop: '8px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${Math.round(100 * (progress.index || 0) / Math.max(1, progress.total || 1))}%`, background: 'var(--accent-color, #7c3aed)', transition: 'width .2s' }} />
                  </div>
                </div>

                {/* current question */}
                <div style={{ fontWeight: 600, fontSize: '14px' }}>{question.label}</div>
                {question.hint && <div style={{ fontSize: '12px', opacity: 0.6, marginTop: '-8px' }}>{question.hint}</div>}

                {question.kind === 'text' ? (
                  <textarea value={draft || ''} onChange={e => setDraft(e.target.value)} rows={4}
                    placeholder="Type here in your own words… (optional)"
                    style={{ ...inputStyle, marginTop: 0, resize: 'vertical', fontFamily: 'inherit' }} />
                ) : question.kind === 'toggle' ? (
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <span onClick={() => setDraft(true)} style={chipStyle(draft === true)}>{question.yes || 'Yes'}</span>
                    <span onClick={() => setDraft(false)} style={chipStyle(draft !== true)}>{question.no || 'No'}</span>
                  </div>
                ) : question.kind === 'single' ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {(question.options || []).map(o => (
                      <span key={o.value} onClick={() => setDraft(o.value)} style={chipStyle(draft === o.value)}>{o.label}</span>
                    ))}
                  </div>
                ) : question.kind === 'entity_layouts' ? (
                  <div>
                    {(draft || []).map(e => (
                      <div key={e.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '5px' }}>
                        <span style={{ fontSize: '12px' }}>{e.label || e.name}</span>
                        <select value={e.layout} onChange={ev => setEntityLayoutDraft(e.name, ev.target.value)} style={{ ...inputStyle, width: 'auto', marginTop: 0, padding: '4px 6px' }}>
                          {(question.layout_options || ['table']).map(l => <option key={l} value={l}>{l}</option>)}
                        </select>
                      </div>
                    ))}
                    {question.allow_custom && <input placeholder="+ add a data section, press Enter" onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addEntityDraft(e.target.value); e.target.value = ''; } }} style={inputStyle} />}
                  </div>
                ) : (
                  <div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {(question.options || []).map(o => (
                        <span key={o.value} onClick={() => toggleDraftValue(o.value, o.label, o.template)} style={chipStyle((draft || []).some(x => (x.value ?? x) === o.value))}>{o.label}</span>
                      ))}
                      {(draft || []).filter(x => !(question.options || []).some(o => o.value === (x.value ?? x))).map(x => (
                        <span key={x.value ?? x} onClick={() => toggleDraftValue(x.value ?? x)} style={chipStyle(true)}>{(x.label ?? x)} ✕</span>
                      ))}
                    </div>
                    {question.allow_custom && <input placeholder="+ type your own, press Enter" onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addDraftCustom(e.target.value); e.target.value = ''; } }} style={inputStyle} />}
                  </div>
                )}

                <div style={{ flex: 1 }} />
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  {stepHistory.length > 0 && <button onClick={stepBack} disabled={interviewLoading} style={{ padding: '9px 12px', borderRadius: '9px', border: '1px solid var(--border-color, #3a3a3a)', background: 'transparent', color: 'inherit', cursor: 'pointer', fontSize: '13px' }}>← Back</button>}
                  <button onClick={nextStep} disabled={interviewLoading || (question.id === 'pages' && (!draft || draft.length === 0))} style={{ flex: 1, padding: '11px', borderRadius: '10px', border: 'none', background: interviewLoading ? '#555' : 'var(--accent-color, #7c3aed)', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: '14px' }}>
                    {interviewLoading ? 'Thinking…' : ((progress.index >= (progress.total - 1)) ? (plan?.labels?.generate || 'Generate website →') : 'Next →')}
                  </button>
                </div>
                <button onClick={cancelInterview} style={{ background: 'none', border: 'none', color: 'var(--text-secondary, #888)', fontSize: '12px', cursor: 'pointer' }}>Cancel</button>
              </div>
            ) : (
              <div className="prompt-history">
                {interviewLoading ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)', fontSize: '13px' }}>Planning your questions…</div>
                ) : promptsHistory.length === 0 ? (
                  <div style={{ padding: '6px 2px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '15px' }}>Upload your SRS to build</div>
                      <div style={{ opacity: 0.65, fontSize: '12px', marginTop: '2px' }}>Your SRS JSON is the single source of truth — I plan the pages, flow, functions, data relations & CRUD from it and build straight away. No questions. Refine afterwards by clicking any element in the preview.</div>
                    </div>
                    <div>
                      <input ref={srsFileRef} type="file" accept=".pdf,.json,.txt,application/json,application/pdf" style={{ display: 'none' }} onChange={handleSrsUpload} />
                      <button onClick={() => srsFileRef.current && srsFileRef.current.click()} style={{ width: '100%', padding: '12px', borderRadius: '10px', border: '1px solid var(--accent-color, #7c3aed)', background: 'rgba(124,58,237,.12)', color: 'inherit', cursor: 'pointer', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                        <FileUp size={15} /> Upload SRS JSON — build from spec
                      </button>
                    </div>
                    <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: 'pointer', padding: '8px 10px', borderRadius: '10px', border: '1px solid var(--border-color, #3a3a3a)' }}>
                      <input type="checkbox" checked={aiSections} onChange={e => setAiSections(e.target.checked)} style={{ marginTop: '2px' }} />
                      <span style={{ fontSize: '12px' }}>
                        <strong>Let AI design each section freely</strong>
                        <span style={{ opacity: 0.65 }}> — more unique, slightly slower. Off = the reliable templates.</span>
                      </span>
                    </label>
                    <div style={{ fontSize: '12px', opacity: 0.6, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <MessageSquare size={14} /> Type your app below and press Enter →
                    </div>
                  </div>
                ) : (
                  promptsHistory.map((pr, idx) => (
                    <div key={idx} className="history-item">
                      <div style={{ fontWeight: 600, fontSize: '11px', color: 'var(--accent-color)', marginBottom: '4px' }}>VERSION {idx + 1}</div>
                      <div>{pr}</div>
                    </div>
                  ))
                )}
              </div>
            )}

            {/* Chat Input Textarea (hidden while the interview wizard is open) */}
            {!plan && !question && (
            <div className="chat-input-area">
              {pinned && (
                <div style={{ marginBottom: '8px', padding: '8px 10px', borderRadius: '8px', background: 'rgba(124,58,237,.1)', border: '1px solid rgba(124,58,237,.3)', fontSize: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Crosshair size={13} />
                    <span style={{ padding: '1px 7px', borderRadius: '6px', background: '#7c3aed', color: '#fff', fontWeight: 600 }}>{pinned.tag || 'el'}</span>
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}><strong>{pinned.label}</strong></span>
                    <button onClick={() => { setPinned(null); setEditMode('edit'); }} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', display: 'flex' }} title="Clear selection">
                      <X size={13} />
                    </button>
                  </div>
                  <div style={{ display: 'flex', gap: '6px', marginTop: '7px' }}>
                    <span onClick={() => setEditMode('edit')} style={{ ...chipStyle(editMode === 'edit', true), cursor: 'pointer' }}>Edit this</span>
                    <span onClick={() => setEditMode('add')} style={{ ...chipStyle(editMode === 'add', true), cursor: 'pointer' }}>+ Add section here</span>
                    {pinned.isImage && <span onClick={() => setImageModal(true)} style={{ ...chipStyle(false, true), cursor: 'pointer' }}>🖼 Change image</span>}
                  </div>

                  {/* Visual Parameter Map — no-code property tweaks (Step 4a); each
                      fires the deterministic STYLE_TWEAK engine and keeps the panel open. */}
                  {editMode === 'edit' && !pinned.isImage && (
                    <div style={{ marginTop: '8px', borderTop: '1px solid rgba(124,58,237,.2)', paddingTop: '8px', opacity: editing ? 0.6 : 1, pointerEvents: editing ? 'none' : 'auto' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px', fontSize: '10px', letterSpacing: '.06em', opacity: 0.65 }}>
                        <span>COLOR</span>
                        <span onClick={() => setVpFill(false)} style={vpMini(!vpFill)}>Text</span>
                        <span onClick={() => setVpFill(true)} style={vpMini(vpFill)}>Fill</span>
                      </div>
                      <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginBottom: '8px' }}>
                        {VP_SWATCHES.map(([hex, name]) => (
                          <button key={name} title={`${name} ${vpFill ? 'background' : 'text'}`} disabled={editing}
                            onClick={() => quickStyle(`${name}${vpFill ? ' background' : ' text'}`)}
                            style={{ width: '18px', height: '18px', borderRadius: '50%', background: hex, border: '1px solid rgba(255,255,255,.35)', cursor: 'pointer', padding: 0 }} />
                        ))}
                      </div>
                      <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                        {VP_CONTROLS.map(([label, instr]) => (
                          <button key={label} disabled={editing} onClick={() => quickStyle(instr)} style={vpBtn}>{label}</button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
              <textarea
                className="chat-textarea"
                placeholder={pinned ? (editMode === 'add' ? 'Describe the new section to add here…' : `Describe the change to “${pinned.label}”…`) : projectId ? "Ask to modify the design or add features..." : "Describe the app you want to build..."}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                disabled={status === 'generating' || status === 'updating'}
              />
              <div className="input-footer">
                <span className="input-hint">Press Enter to start</span>
                <button
                  className="send-btn"
                  onClick={handleSend}
                  disabled={!prompt.trim() || status === 'generating' || status === 'updating'}
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
            )}
          </div>
        )}

        {/* Update-image modal (Select-Element on an <img>) */}
        {imageModal && pinned?.isImage && (
          <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setImageModal(false)}>
            <div onClick={e => e.stopPropagation()} style={{ width: '340px', background: 'var(--bg-primary, #0c1018)', border: '1px solid var(--border-color, #2a2a2a)', borderRadius: '14px', padding: '18px', boxShadow: '0 20px 60px rgba(0,0,0,.5)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <strong style={{ fontSize: '15px' }}>Update image</strong>
                <button onClick={() => setImageModal(false)} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}><X size={16} /></button>
              </div>
              <div style={{ display: 'flex', gap: '10px', marginBottom: '14px' }}>
                <input ref={imgFileRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={e => { const f = e.target.files && e.target.files[0]; e.target.value = ''; if (f) replaceImageUpload(f); }} />
                <button onClick={() => imgFileRef.current && imgFileRef.current.click()} disabled={editing} style={{ flex: 1, height: '90px', borderRadius: '10px', border: '1px dashed var(--border-color, #3a3a3a)', background: 'transparent', color: 'var(--text-secondary, #aaa)', cursor: 'pointer', fontSize: '12px' }} title="Upload from your device">＋<br />Upload</button>
                <div style={{ width: '90px', height: '90px', borderRadius: '10px', overflow: 'hidden', border: '2px solid var(--accent-color, #7c3aed)' }}>
                  <img src={`${previewUrl || ''}${pinned.src}`} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={e => { e.currentTarget.style.display = 'none'; }} />
                </div>
              </div>
              <div style={{ fontSize: '11px', opacity: 0.6, marginBottom: '6px' }}>Or regenerate with AI</div>
              <div style={{ display: 'flex', gap: '6px' }}>
                <input value={imgPrompt} onChange={e => setImgPrompt(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') replaceImageAI(); }} placeholder="Describe the new image…" style={{ ...inputStyle, marginTop: 0, flex: 1 }} disabled={editing} />
                <button onClick={replaceImageAI} disabled={editing || !imgPrompt.trim()} style={{ padding: '0 12px', borderRadius: '8px', border: 'none', background: 'var(--accent-color, #7c3aed)', color: '#fff', cursor: 'pointer', fontSize: '12px' }}>{editing ? '…' : 'Generate'}</button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: File Tree / File selection */}
        {activeTab === 'files' && projectId && (
          <div className="file-list-container">
            <div style={{ fontWeight: 600, fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>WORKSPACE FILES</div>
            {Object.keys(files).map((filepath) => (
              <div 
                key={filepath}
                className={`file-item ${selectedFile === filepath ? 'active' : ''}`}
                onClick={() => {
                  setSelectedFile(filepath);
                  setMode('code');
                }}
              >
                <FileText size={14} style={{ color: filepath.endsWith('.html') ? '#f97316' : '#38bdf8' }} />
                <span>{filepath}</span>
              </div>
            ))}
          </div>
        )}

        {/* Live SSE progress logs */}
        {logs.length > 0 && (
          <div className="logs-panel">
            <div className="logs-header" onClick={() => setShowLogs(!showLogs)}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Terminal size={14} />
                <span>EXECUTION LOGS</span>
              </div>
              <ChevronRight size={14} style={{ transform: showLogs ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
            </div>
            {showLogs && (
              <div className="logs-content">
                {logs.map((log, index) => (
                  <div key={index} className="log-entry">
                    <span className="log-bullet">&gt;</span>
                    <span>{log}</span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        )}
      </div>

      {/* RIGHT PANEL: Sandbox Preview / Code Viewer */}
      <div className="preview-pane">
        <div className="pane-header">
          {/* View mode toggle */}
          <div className="mode-selectors">
            <button 
              className={`mode-btn ${mode === 'preview' ? 'active' : ''}`}
              onClick={() => setMode('preview')}
              disabled={!projectId}
            >
              Interactive Preview
            </button>
            <button 
              className={`mode-btn ${mode === 'code' ? 'active' : ''}`}
              onClick={() => setMode('code')}
              disabled={!projectId}
            >
              Code Inspector
            </button>
          </div>

          {/* Action buttons (reload, sizes, zip download) */}
          {projectId && (
            <div className="action-controls">
              {mode === 'preview' && (
                <>
                  <button
                    className="control-icon-btn"
                    onClick={handleReloadIframe}
                    title="Reload sandbox preview"
                  >
                    <RefreshCw size={18} />
                  </button>
                  <button
                    className={`control-icon-btn ${inspect ? 'active' : ''}`}
                    onClick={toggleInspect}
                    disabled={!previewUrl}
                    title="Select Element - click a component in the preview to edit only that part"
                  >
                    <Crosshair size={18} />
                  </button>
                  <div style={{ display: 'flex', border: '1px solid var(--border-color)', borderRadius: '10px', overflow: 'hidden' }}>
                    <button 
                      className={`control-icon-btn ${previewSize === 'mobile' ? 'active' : ''}`}
                      style={{ border: 'none', borderRadius: 0 }}
                      onClick={() => setPreviewSize('mobile')}
                      title="Mobile view"
                    >
                      <Smartphone size={16} />
                    </button>
                    <button 
                      className={`control-icon-btn ${previewSize === 'tablet' ? 'active' : ''}`}
                      style={{ border: 'none', borderRadius: 0, borderLeft: '1px solid var(--border-color)', borderRight: '1px solid var(--border-color)' }}
                      onClick={() => setPreviewSize('tablet')}
                      title="Tablet view"
                    >
                      <Tablet size={16} />
                    </button>
                    <button 
                      className={`control-icon-btn ${previewSize === 'desktop' ? 'active' : ''}`}
                      style={{ border: 'none', borderRadius: 0 }}
                      onClick={() => setPreviewSize('desktop')}
                      title="Desktop view"
                    >
                      <Monitor size={16} />
                    </button>
                  </div>
                </>
              )}
              <button 
                className="download-btn"
                onClick={handleDownload}
              >
                <Download size={16} />
                <span>Download ZIP</span>
              </button>
            </div>
          )}
        </div>

        {/* View Content: Iframe Preview or Code Viewer */}
        {!projectId ? (
          <div className="sandbox-view">
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', color: 'var(--text-secondary)' }}>
              <div className="brand-logo" style={{ width: '60px', height: '60px', borderRadius: '14px', fontSize: '30px' }}>
                <Sparkles size={28} />
              </div>
              <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'var(--text-primary)' }}>Create Your Application Prototype</h2>
              <p style={{ maxWidth: '400px', textAlign: 'center', fontSize: '14px', lineHeight: 1.6 }}>Describe the layout, sections, user roles, or forms you need. The AI will generate a complete interactive web application.</p>
            </div>
          </div>
        ) : mode === 'preview' ? (
          <div className="sandbox-view">
            {/* GATED PREVIEW: nothing is shown until the app is fully built
                (pages -> images -> quality check -> build -> done). */}
            {!previewUrl ? (
              <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10 }}>
                <div className="splash-loading" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
                  {phase !== 'error' && <div className="spinner"></div>}
                  <span style={{ fontSize: '15px', fontWeight: 600 }}>
                    {PHASE_LABELS[phase] || 'Working...'}
                  </span>
                  <span style={{ fontSize: '12px', opacity: 0.65, maxWidth: '300px', textAlign: 'center' }}>
                    {phase === 'images'
                      ? 'AI Design Agent is generating images for your app.'
                      : phase === 'error'
                        ? 'Check the execution logs for details.'
                        : 'The preview will appear when everything is ready.'}
                  </span>
                </div>
              </div>
            ) : (
              <div className={`iframe-container ${previewSize}`} style={{ position: 'relative' }}>
                <iframe
                  ref={iframeRef}
                  className="sandbox-iframe"
                  src={`${previewUrl}?v=${previewVersion}`}
                  title="AI Designer Sandbox"
                  style={{ transition: 'filter .2s', filter: editing ? 'blur(5px)' : 'none', pointerEvents: editing ? 'none' : 'auto' }}
                />
                {editing && (
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px', background: 'rgba(8,12,22,.35)', backdropFilter: 'blur(2px)', zIndex: 5 }}>
                    <div className="spinner" />
                    <div style={{ fontSize: '14px', fontWeight: 600, color: '#fff', textShadow: '0 1px 4px rgba(0,0,0,.6)' }}>
                      {pinned ? `Updating ${pinned.label}…` : 'Updating…'}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="code-view-container">
            <div className="code-view-header">
              <div className="code-view-title">{selectedFile || 'Select a file'}</div>
            </div>
            <pre className="code-pre">
              <code>{selectedFile ? files[selectedFile] : '// Select a file from the source code tab to view.'}</code>
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
