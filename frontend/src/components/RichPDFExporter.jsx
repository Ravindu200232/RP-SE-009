'use client';

import { useState } from 'react';
import { RiLoader4Line } from 'react-icons/ri';
import { HiSparkles } from 'react-icons/hi2';

const PAGE = { width: 210, height: 297, marginLeft: 22, marginRight: 18, top: 24, bottom: 18 };
const CONTENT_WIDTH = PAGE.width - PAGE.marginLeft - PAGE.marginRight;

function formatLabel(value = '') {
  return String(value)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function isEmpty(value) {
  if (value === null || value === undefined || value === '') {
    return true;
  }
  if (Array.isArray(value)) {
    return value.length === 0;
  }
  if (typeof value === 'object') {
    return Object.values(value).every((entry) => isEmpty(entry));
  }
  return false;
}

function buildSectionEntries(srs) {
  return [
    { title: '1. Introduction', value: srs?.sections?.introduction },
    { title: '2. Overall Description', value: srs?.sections?.overall_description },
    { title: '3. External Interface Requirements', value: srs?.sections?.external_interface_requirements },
    { title: '4. System Features', value: srs?.sections?.system_features },
    { title: '5. Other Nonfunctional Requirements', value: srs?.sections?.other_nonfunctional_requirements },
    { title: '6. Other Requirements', value: srs?.sections?.other_requirements },
    { title: 'Appendix A. Glossary', value: srs?.appendices?.glossary },
    { title: 'Appendix B. Analysis Models', value: srs?.appendices?.analysis_models },
    { title: 'Appendix C. To Be Determined List', value: srs?.appendices?.to_be_determined_list },
    { title: 'Quality Check', value: srs?.quality_check },
  ].filter((entry) => !isEmpty(entry.value));
}

function writeWrappedText(doc, text, x, y, options = {}) {
  const lines = doc.splitTextToSize(String(text || ''), options.maxWidth || CONTENT_WIDTH);
  doc.text(lines, x, y);
  return y + lines.length * (options.lineHeight || 5);
}

function drawHeader(doc, metadata, pageNumber) {
  doc.setFont('times', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(20, 20, 20);
  doc.text(`Software Requirements Specification for ${metadata.project_name || 'Project'}`, PAGE.marginLeft, 14);
  doc.text(`Page ${pageNumber}`, PAGE.width - PAGE.marginRight, 14, { align: 'right' });
  doc.setDrawColor(110, 110, 110);
  doc.setLineWidth(0.2);
  doc.line(PAGE.marginLeft, 16, PAGE.width - PAGE.marginRight, 16);
}

function drawFooter(doc) {
  doc.setDrawColor(150, 150, 150);
  doc.setLineWidth(0.2);
  doc.line(PAGE.marginLeft, PAGE.height - 12, PAGE.width - PAGE.marginRight, PAGE.height - 12);
}

function startBodyPage(doc, metadata, pageNumber) {
  if (doc.getNumberOfPages() > 0) {
    doc.addPage();
  }
  drawHeader(doc, metadata, pageNumber);
  drawFooter(doc);
  return PAGE.top;
}

function renderRevisionHistory(doc, srs, metadata, pageNumber) {
  let y = startBodyPage(doc, metadata, pageNumber);

  doc.setFont('times', 'bold');
  doc.setFontSize(15);
  doc.text('Revision History', PAGE.marginLeft, y);
  y += 8;

  const rows = Array.isArray(srs.revision_history) && srs.revision_history.length
    ? srs.revision_history
    : [];

  doc.setFont('times', 'bold');
  doc.setFontSize(10.5);
  doc.text('Name', PAGE.marginLeft, y);
  doc.text('Date', 82, y);
  doc.text('Reason For Changes', 112, y);
  doc.text('Version', PAGE.width - PAGE.marginRight, y, { align: 'right' });
  y += 3;
  doc.setLineWidth(0.2);
  doc.line(PAGE.marginLeft, y, PAGE.width - PAGE.marginRight, y);
  y += 6;

  doc.setFont('times', 'normal');
  doc.setFontSize(10);

  rows.forEach((row) => {
    const reasonLines = doc.splitTextToSize(String(row.reason_for_changes || ''), 72);
    const height = Math.max(reasonLines.length * 5, 5);
    doc.text(String(row.name || ''), PAGE.marginLeft, y);
    doc.text(String(row.date || ''), 82, y);
    doc.text(reasonLines, 112, y);
    doc.text(String(row.version || ''), PAGE.width - PAGE.marginRight, y, { align: 'right' });
    y += height + 3;
  });
}

function renderNode(doc, label, value, depth, y, metadata, pageRef) {
  const ensureSpace = (neededHeight = 10) => {
    if (y + neededHeight <= PAGE.height - PAGE.bottom) {
      return;
    }
    pageRef.current += 1;
    doc.addPage();
    drawHeader(doc, metadata, pageRef.current);
    drawFooter(doc);
    y = PAGE.top;
  };

  if (isEmpty(value)) {
    return y;
  }

  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    ensureSpace(10);
    doc.setFont('times', 'bold');
    doc.setFontSize(10.5);
    if (label) {
      doc.text(`${label}`, PAGE.marginLeft + depth * 6, y);
      y += 5;
    }
    doc.setFont('times', 'normal');
    doc.setFontSize(10.5);
    y = writeWrappedText(doc, String(value), PAGE.marginLeft + depth * 6, y, { maxWidth: CONTENT_WIDTH - depth * 6, lineHeight: 5 }) + 2;
    return y;
  }

  if (Array.isArray(value)) {
    ensureSpace(8);
    if (label) {
      doc.setFont('times', 'bold');
      doc.setFontSize(10.5);
      doc.text(label, PAGE.marginLeft + depth * 6, y);
      y += 6;
    }

    value.forEach((entry, index) => {
      ensureSpace(8);
      if (typeof entry === 'object' && entry !== null) {
        doc.setFont('times', 'italic');
        doc.setFontSize(10);
        doc.text(`${label ? 'Item' : 'Entry'} ${index + 1}`, PAGE.marginLeft + (depth + 1) * 6, y);
        y += 5;
        Object.entries(entry)
          .filter(([, childValue]) => !isEmpty(childValue))
          .forEach(([childKey, childValue]) => {
            y = renderNode(doc, formatLabel(childKey), childValue, depth + 1, y, metadata, pageRef);
          });
      } else {
        doc.setFont('times', 'normal');
        doc.setFontSize(10.5);
        y = writeWrappedText(doc, `- ${String(entry)}`, PAGE.marginLeft + (depth + 1) * 6, y, {
          maxWidth: CONTENT_WIDTH - (depth + 1) * 6,
          lineHeight: 5,
        }) + 1.5;
      }
    });

    return y + 1;
  }

  ensureSpace(8);
  if (label) {
    doc.setFont('times', 'bold');
    doc.setFontSize(10.5);
    doc.text(label, PAGE.marginLeft + depth * 6, y);
    y += 6;
  }

  Object.entries(value)
    .filter(([, childValue]) => !isEmpty(childValue))
    .forEach(([childKey, childValue]) => {
      y = renderNode(doc, formatLabel(childKey), childValue, depth + 1, y, metadata, pageRef);
    });

  return y + 1;
}

function renderFormalPdf(doc, srs) {
  const metadata = srs?.metadata || {};
  const pageRef = { current: 1 };

  doc.setProperties({
    title: `${metadata.project_name || 'Project'} - Software Requirements Specification`,
    subject: 'IEEE Software Requirements Specification',
    author: metadata.author || 'SRS Maker Agent',
    creator: 'SRS Maker Agent',
  });

  doc.setFont('times', 'normal');
  doc.setTextColor(0, 0, 0);

  doc.setFont('times', 'bold');
  doc.setFontSize(24);
  doc.text('Software Requirements', PAGE.width / 2, 70, { align: 'center' });
  doc.text('Specification', PAGE.width / 2, 82, { align: 'center' });

  doc.setFont('times', 'normal');
  doc.setFontSize(16);
  doc.text('for', PAGE.width / 2, 102, { align: 'center' });
  doc.setFont('times', 'italic');
  doc.text(metadata.project_name || '<Project>', PAGE.width / 2, 116, { align: 'center' });

  doc.setFont('times', 'normal');
  doc.setFontSize(12);
  doc.text(`Version ${metadata.version || '1.0'} ${metadata.status || 'approved'}`, PAGE.width / 2, 132, { align: 'center' });
  doc.text(`Prepared by ${metadata.author || '<author>'}`, PAGE.width / 2, 148, { align: 'center' });
  doc.text(metadata.organization || '<organization>', PAGE.width / 2, 160, { align: 'center' });
  doc.text(metadata.date_created || new Date().toISOString().split('T')[0], PAGE.width / 2, 172, { align: 'center' });
  doc.text('-- 1 of N --', PAGE.width / 2, PAGE.height - 16, { align: 'center' });

  doc.addPage();
  pageRef.current = 2;
  drawHeader(doc, metadata, 'ii');
  drawFooter(doc);

  const sectionEntries = buildSectionEntries(srs);
  renderRevisionHistory(doc, srs, metadata, 1);
  pageRef.current = 3;
  const tocEntries = [
    { title: 'Table of Contents', page: 'ii' },
    { title: 'Revision History', page: 1 },
  ];

  sectionEntries.forEach((entry) => {
    tocEntries.push({ title: entry.title, page: pageRef.current });
    let sectionY = startBodyPage(doc, metadata, pageRef.current);
    doc.setFont('times', 'bold');
    doc.setFontSize(15);
    doc.text(entry.title, PAGE.marginLeft, sectionY);
    sectionY += 8;
    renderNode(doc, '', entry.value, 0, sectionY, metadata, pageRef);
    pageRef.current += 1;
  });

  doc.setPage(2);
  drawHeader(doc, metadata, 'ii');
  drawFooter(doc);
  let y = PAGE.top;
  doc.setFont('times', 'bold');
  doc.setFontSize(16);
  doc.text('Table of Contents', PAGE.marginLeft, y);
  y += 10;

  doc.setFont('times', 'normal');
  doc.setFontSize(11);
  tocEntries.forEach((entry) => {
    const title = entry.title;
    const page = String(entry.page);
    const dots = '.'.repeat(Math.max(6, 110 - title.length - page.length));
    y = writeWrappedText(doc, `${title} ${dots} ${page}`, PAGE.marginLeft, y, { maxWidth: CONTENT_WIDTH, lineHeight: 5.5 }) + 1;
  });

  const totalPages = doc.getNumberOfPages();
  for (let pageNumber = 1; pageNumber <= totalPages; pageNumber += 1) {
    doc.setPage(pageNumber);
    doc.setFont('times', 'normal');
    doc.setFontSize(10);
    doc.text(`-- ${pageNumber} of ${totalPages} --`, PAGE.width / 2, PAGE.height - 16, { align: 'center' });
  }
}

export default function RichPDFExporter({ srs }) {
  const [loading, setLoading] = useState(false);

  const exportPDF = async () => {
    if (!srs || loading) {
      return;
    }

    setLoading(true);
    try {
      const { jsPDF } = await import('jspdf');
      const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
      renderFormalPdf(doc, srs);
      const fileName = (srs.metadata?.project_name || 'SRS').replace(/\s+/g, '_');
      doc.save(`${fileName}_IEEE_SRS.pdf`);
    } catch (error) {
      alert(`PDF export failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={exportPDF}
      disabled={loading || !srs}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg btn-gold text-xs disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading ? <RiLoader4Line className="animate-spin" /> : <HiSparkles />}
      {loading ? 'Exporting...' : 'Export PDF'}
    </button>
  );
}
