'use client';

import { useState } from 'react';
import { RiLoader4Line } from 'react-icons/ri';
import { HiSparkles } from 'react-icons/hi2';

const COLS = [
  [124,58,237], [16,185,129], [6,182,212],
  [245,158,11], [239,68,68],  [99,102,241], [236,72,153],
];

export default function PDFExporter({ srs }) {
  const [loading, setLoading] = useState(false);

  const exportPDF = async () => {
    if (!srs || loading) return;
    setLoading(true);
    try {
      const { jsPDF } = await import('jspdf');
      const doc = new jsPDF({ orientation:'portrait', unit:'mm', format:'a4' });
      buildPDF(doc, srs);
      const name = (srs.metadata?.project_name || 'SRS').replace(/\s+/g,'_');
      doc.save(`${name}_IEEE_SRS.pdf`);
    } catch (e) {
      alert('PDF export failed: ' + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button onClick={exportPDF} disabled={loading || !srs}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg btn-gold text-xs disabled:opacity-50 disabled:cursor-not-allowed">
      {loading ? <RiLoader4Line className="animate-spin" /> : <HiSparkles />}
      {loading ? 'Exporting...' : 'Export PDF'}
    </button>
  );
}

// ── PDF Builder ───────────────────────────────────────────────────────────────
function buildPDF(doc, srs) {
  const W = 210, H = 297, M = 14, CW = W - M * 2;

  const bg = () => {
    doc.setFillColor(3, 3, 15);
    doc.rect(0, 0, W, H, 'F');
    // Subtle nebula
    doc.setFillColor(124, 58, 237);
    doc.setGState(doc.GState({ opacity: 0.05 }));
    doc.ellipse(25, 35, 75, 55, 'F');
    doc.setFillColor(37, 99, 235);
    doc.ellipse(185, 260, 75, 55, 'F');
    doc.setGState(doc.GState({ opacity: 1 }));
    // Stars
    doc.setFillColor(255,255,255);
    for (let i = 0; i < 45; i++) {
      const sx = (i * 37.3) % W, sy = (i * 53.7) % H, sr = (i%3===0)?0.5:0.2;
      doc.setGState(doc.GState({ opacity: 0.1 + (i%5)*0.08 }));
      doc.circle(sx, sy, sr, 'F');
    }
    doc.setGState(doc.GState({ opacity: 1 }));
  };

  const newPage = (title, ci = 0) => {
    doc.addPage(); bg();
    const [r,g,b] = COLS[ci % COLS.length];
    doc.setFillColor(r,g,b);
    doc.setGState(doc.GState({ opacity: 0.12 }));
    doc.rect(0, 0, W, 20, 'F');
    doc.setGState(doc.GState({ opacity: 1 }));
    doc.setFillColor(r,g,b); doc.rect(0, 0, 4, 20, 'F');
    doc.setFont('helvetica','bold'); doc.setFontSize(10);
    doc.setTextColor(r,g,b);
    doc.text(title, M+2, 13);
    doc.setFont('helvetica','normal'); doc.setFontSize(7);
    doc.setTextColor(71,85,105);
    const p = doc.internal.getCurrentPageInfo().pageNumber;
    doc.text(String(p), W-M, 13, { align:'right' });
    return 26;
  };

  const reqBlock = (y, id, title, desc, prio, ci) => {
    const [r,g,b] = COLS[ci % COLS.length];
    const lineH = 24;
    doc.setFillColor(r,g,b); doc.setGState(doc.GState({ opacity:0.08 }));
    doc.roundedRect(M, y, CW, lineH, 2, 2, 'F');
    doc.setGState(doc.GState({ opacity:1 }));
    doc.setFillColor(r,g,b); doc.roundedRect(M, y, 3, lineH, 1, 1, 'F');
    doc.setFont('courier','bold'); doc.setFontSize(7); doc.setTextColor(r,g,b);
    doc.text(String(id||'').slice(0,12), M+5, y+7);
    doc.setFont('helvetica','bold'); doc.setFontSize(8.5); doc.setTextColor(226,232,240);
    doc.text(String(title||'').slice(0,55), M+5, y+14);
    doc.setFont('helvetica','normal'); doc.setFontSize(7.5); doc.setTextColor(148,163,184);
    const dl = doc.splitTextToSize(String(desc||'').slice(0,160), CW-20);
    doc.text(dl.slice(0,1), M+5, y+21);
    const pc = prio==='High'?[239,68,68]:prio==='Low'?[100,116,139]:[245,158,11];
    doc.setFillColor(...pc); doc.setGState(doc.GState({ opacity:0.2 }));
    doc.roundedRect(W-M-20, y+4, 18, 5, 2, 2, 'F');
    doc.setGState(doc.GState({ opacity:1 }));
    doc.setFont('helvetica','bold'); doc.setFontSize(5.5); doc.setTextColor(...pc);
    doc.text((prio||'Med').toUpperCase(), W-M-11, y+8, { align:'center' });
    return y + lineH + 3;
  };

  // ── Cover ─────────────────────────────────────────────────────────────────
  bg();
  // Globe
  doc.setDrawColor(124,58,237); doc.setLineWidth(0.5);
  doc.setFillColor(6,6,26); doc.circle(W/2, 45, 22, 'FD');
  doc.setGState(doc.GState({ opacity:0.45 }));
  doc.setLineWidth(0.3);
  ['ellipse','line','ellipse2'].forEach((_,i) => {
    if (i===0) doc.ellipse(W/2, 45, 11, 22, 'S');
    else if (i===1) { doc.line(W/2-22, 45, W/2+22, 45); doc.ellipse(W/2, 45, 22, 11, 'S'); }
    else doc.ellipse(W/2, 45, 19, 22, 'S');
  });
  doc.setGState(doc.GState({ opacity:1 }));

  doc.setFont('helvetica','bold'); doc.setFontSize(20); doc.setTextColor(255,255,255);
  doc.text('SOFTWARE REQUIREMENTS', W/2, 82, { align:'center' });
  doc.text('SPECIFICATION', W/2, 92, { align:'center' });

  // Gradient bar
  [[124,58,237,0.45],[37,99,235,0.3],[6,182,212,0.25]].forEach(([r,g,b,w],i) => {
    doc.setFillColor(r,g,b);
    doc.rect(M + CW*i*0.33, 97, CW*0.33, 0.8, 'F');
  });

  const pn = srs.metadata?.project_name || 'Software Project';
  doc.setFontSize(14); doc.setTextColor(200,180,255);
  doc.text(pn.slice(0,50), W/2, 108, { align:'center' });

  const metaItems = [
    ['Domain', srs.metadata?.domain||'—'],['Type',srs.metadata?.application_type||'Web'],
    ['Version',srs.metadata?.version||'1.0'],['Status',srs.metadata?.status||'draft'],
    ['Date',srs.metadata?.date_created||new Date().toLocaleDateString()],['Standard','IEEE SRS'],
  ];
  metaItems.forEach(([lbl,val],i) => {
    const col = i%3, row = Math.floor(i/3), bw = CW/3-2;
    const bx = M + col*(CW/3), by = 120 + row*16;
    doc.setFillColor(20,20,55); doc.roundedRect(bx, by, bw, 12, 2, 2, 'F');
    doc.setFillColor(124,58,237); doc.roundedRect(bx, by, 3, 12, 1, 1, 'F');
    doc.setFont('helvetica','normal'); doc.setFontSize(6.5); doc.setTextColor(148,163,184);
    doc.text(lbl.toUpperCase(), bx+5, by+5);
    doc.setFont('helvetica','bold'); doc.setFontSize(8); doc.setTextColor(226,232,240);
    doc.text(String(val).slice(0,20), bx+5, by+10);
  });

  if (srs.sections?.introduction?.purpose) {
    const lines = doc.splitTextToSize(srs.sections.introduction.purpose, CW);
    doc.setFont('helvetica','normal'); doc.setFontSize(8.5); doc.setTextColor(148,163,184);
    doc.text(lines.slice(0,3), M, 168);
  }

  doc.setFontSize(7); doc.setTextColor(71,85,105);
  doc.text('Generated by SRS Maker Agent · MiniCPM-O 4.5 + DeepSeek V3', W/2, H-10, { align:'center' });

  // ── Features page ─────────────────────────────────────────────────────────
  const feats = srs.sections?.system_features || [];
  if (feats.length > 0) {
    let y = newPage('⚡  SYSTEM FEATURES', 1);
    feats.forEach((feat, fi) => {
      if (y > H-55) { y = newPage('⚡  FEATURES (cont.)', 1); }
      const [r,g,b] = COLS[fi%COLS.length];
      doc.setFillColor(r,g,b); doc.setGState(doc.GState({ opacity:0.1 }));
      doc.roundedRect(M, y, CW, 10, 2, 2, 'F'); doc.setGState(doc.GState({ opacity:1 }));
      doc.setFont('helvetica','bold'); doc.setFontSize(8.5);
      doc.setTextColor(r,g,b); doc.text(feat.feature_id||`F-${fi+1}`, M+3, y+7);
      doc.setTextColor(255,255,255); doc.text((feat.feature_name||'Feature').slice(0,50), M+18, y+7);
      y += 12;
      if (feat.description_and_priority?.description) {
        doc.setFont('helvetica','normal'); doc.setFontSize(7.5); doc.setTextColor(148,163,184);
        const dl = doc.splitTextToSize(feat.description_and_priority.description, CW-4);
        doc.text(dl.slice(0,2), M+4, y); y += dl.slice(0,2).length * 4 + 2;
      }
      (feat.functional_requirements||[]).slice(0,4).forEach(req => {
        if (y > H-40) { y = newPage('⚡  FEATURES (cont.)', 1); }
        y = reqBlock(y, req.requirement_id, req.title||'', req.description||'', req.priority||'Medium', fi);
      });
      y += 4;
    });
  }

  // ── NFR page ───────────────────────────────────────────────────────────────
  const nfr = srs.sections?.other_nonfunctional_requirements;
  if (nfr) {
    let y = newPage('📊  NON-FUNCTIONAL REQUIREMENTS', 3);
    [
      { label:'Performance', reqs: nfr.performance_requirements||[], ci:3 },
      { label:'Security',    reqs: nfr.security_requirements||[],    ci:4 },
      { label:'Quality',     reqs: nfr.software_quality_attributes||[], ci:5 },
    ].forEach(({ label, reqs, ci }) => {
      if (!reqs.length) return;
      if (y > H-45) { y = newPage('📊  NFR (cont.)', 3); }
      const [r,g,b] = COLS[ci%COLS.length];
      doc.setFont('helvetica','bold'); doc.setFontSize(9); doc.setTextColor(r,g,b);
      doc.text(label.toUpperCase(), M, y); y += 6;
      reqs.slice(0,3).forEach(req => {
        if (y > H-40) { y = newPage('📊  NFR (cont.)', 3); }
        y = reqBlock(y, req.requirement_id||req.attribute_id, req.attribute_name||req.description?.slice(0,40), req.description||'', 'Medium', ci);
      });
      y += 3;
    });
  }

  // ── Microservices page ─────────────────────────────────────────────────────
  if (srs.services?.length > 0) {
    let y = newPage('🌐  MICROSERVICES ARCHITECTURE', 5);
    srs.services.forEach((svc, si) => {
      if (y > H-60) { y = newPage('🌐  MICROSERVICES (cont.)', 5); }
      const [r,g,b] = COLS[si%COLS.length];
      doc.setFillColor(r,g,b); doc.setGState(doc.GState({ opacity:0.1 }));
      doc.roundedRect(M, y, CW, 9, 2, 2, 'F'); doc.setGState(doc.GState({ opacity:1 }));
      doc.setFillColor(r,g,b); doc.roundedRect(M, y, 3, 9, 1, 1, 'F');
      doc.setFont('courier','bold'); doc.setFontSize(8.5); doc.setTextColor(r,g,b);
      doc.text(svc.name||`svc-${si}`, M+5, y+6.5);
      doc.setFont('courier','normal'); doc.setFontSize(7); doc.setTextColor(148,163,184);
      doc.text(`:${svc.port}`, W-M, y+6.5, { align:'right' });
      y += 11;
      if (svc.description) {
        doc.setFont('helvetica','normal'); doc.setFontSize(7); doc.setTextColor(148,163,184);
        doc.text(svc.description.slice(0,90), M+4, y); y += 5;
      }
      const mc = { GET:[16,185,129], POST:[37,99,235], PUT:[245,158,11], DELETE:[239,68,68] };
      (svc.endpoints||[]).slice(0,4).forEach(ep => {
        doc.setFont('courier','bold'); doc.setFontSize(7); doc.setTextColor(...(mc[ep.method]||[148,163,184]));
        doc.text(ep.method, M+4, y);
        doc.setFont('courier','normal'); doc.setTextColor(148,163,184);
        doc.text((ep.path||'').slice(0,40), M+16, y);
        doc.setTextColor(71,85,105); doc.text((ep.description||'').slice(0,45), M+68, y);
        y += 4;
      });
      y += 4;
    });
  }

  // ── Page numbers ──────────────────────────────────────────────────────────
  const total = doc.internal.getNumberOfPages();
  for (let p = 1; p <= total; p++) {
    doc.setPage(p);
    doc.setFont('helvetica','normal'); doc.setFontSize(7); doc.setTextColor(71,85,105);
    doc.text(`Page ${p} / ${total}`, W-M, H-6, { align:'right' });
    doc.text('IEEE SRS · SRS Maker Agent', M, H-6);
    doc.setDrawColor(30,30,60); doc.setLineWidth(0.3);
    doc.line(M, H-8, W-M, H-8);
  }
}
