import { api } from '@/lib/api'
import { guideForDiagram } from '@/lib/diagram-guide'

function diagramRows(rows) {
  return (rows || [])
    .filter(d => d && (d.source || d.svg))
    .map(d => {
      const name = d.kind || d.name || 'diagram'
      const guide = guideForDiagram(name)
      return {
      name,
      title: d.title || name.replaceAll('_', ' '),
      question: d.question || guide.question,
      definition: d.definition || guide.definition,
      drawingRules: d.drawing_rules || d.drawingRules || guide.drawingRules,
      notation: d.notation || guide.notation,
      standard: d.standard || '',
      applicable: d.applicable !== false,
      applicabilityNote: d.applicability_note || '',
      mermaid: d.source || d.mermaid || '',

      svg: d.svg || '',
      png: Boolean(d.png_path),

      rendered: Boolean(d.svg || d.svg_path || d.png_path),
    }})
}

export async function loadSrsView(projectId) {
  const at = (p) => `/projects/${projectId}${p}`
  const ok = (promise) => promise.then(v => v).catch(() => null)

  const detail = await api.srs(at(''))
  const [diagrams, handoff, plan, interview] = await Promise.all([
    ok(api.srs(at('/diagrams'))),
    ok(api.srs(at('/builder-handoff'))),
    ok(api.srs(at('/plan'))),
    ok(api.srs(at('/interview'))),
  ])

  const envelope = detail?.srs || {}
  const document = envelope.srs_document || envelope || {}
  if (!document || !Object.keys(document).length) {
    throw new Error('the project has no specification yet')
  }
  const rows = diagramRows(diagrams?.diagrams)

  const planText = document.approved_plan_markdown || plan?.markdown || ''

  return {
    project: projectId,
    document,
    plan: planText,
    handoff: handoff || {},
    diagrams: rows,
    interview: interview || {},

    versions: detail?.versions || [],
    summary: detail?.summary || null,
    status: detail?.project?.status || '',
    version: document.version || detail?.project?.current_version || '',
    have: {
      document: Boolean(document && Object.keys(document).length),
      plan: Boolean(planText.trim()),
      handoff: Boolean(handoff?.prompt),
      interview: Boolean((interview?.transcript || []).length),
      diagrams: rows.length > 0,

      pdf: Boolean(document && Object.keys(document).length),
    },
  }
}

export function srsViewFromVersion(row, projectId) {
  const envelope = row?.srs || {}
  const document = envelope.srs_document || envelope || {}
  const rows = diagramRows(document.diagrams)
  const planText = document.approved_plan_markdown || ''
  return {
    project: projectId,
    document,
    plan: planText,
    handoff: document.builder_handoff || {},
    diagrams: rows,
    interview: {},
    versions: [],
    summary: null,
    status: '',
    version: row?.version || document.version || '',
    have: {
      document: Boolean(document && Object.keys(document).length),
      plan: Boolean(planText.trim()),
      handoff: Boolean(document.builder_handoff?.prompt),

      interview: false,
      diagrams: rows.length > 0,
      pdf: false,
    },
  }
}
