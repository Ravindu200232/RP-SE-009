// Single source of truth for "did this operation actually succeed?" — used to gate
// version-history entries so a failed edit / image / section / generation can NEVER
// be recorded as a successful version.
//
// A result is version-worthy ONLY when:
//   - an edit/section/image endpoint returned  { ok: true }
//   - a streamed generation reached            { status: 'completed' }
// Everything else is NOT a version:
//   ok:false · FastAPI 422 {detail:[...]} · {error:...} · status:'failed'
//   · 'running'/partial · HTTP error · thrown exception (no result) · null/undefined
export function isVersionSuccess(result) {
  if (!result || typeof result !== 'object') return false;
  if (result.ok === true) return true;
  if (result.status === 'completed') return true;
  return false;
}

export default isVersionSuccess;
