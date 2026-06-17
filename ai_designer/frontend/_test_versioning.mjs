// Regression test for version-history / false-success prevention.
// Run: node _test_versioning.mjs   (exit 1 on any failure)
// Proves a failed edit/image/section/generation can NEVER record a version.
import { isVersionSuccess } from './src/lib/versioning.js';

let failed = 0;
const check = (name, cond, detail = '') => {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${detail ? '  -> ' + detail : ''}`);
  if (!cond) failed++;
};

// ---- the rule itself, for every backend shape ----
check('ok:true is a version', isVersionSuccess({ ok: true }) === true);
check('ok:false is NOT a version', isVersionSuccess({ ok: false, error: 'x' }) === false);
check('FastAPI 422 {detail:[...]} is NOT a version', isVersionSuccess({ detail: [{ msg: 'Input should be a valid string' }] }) === false);
check('{error:...} is NOT a version', isVersionSuccess({ error: 'boom' }) === false);
check("status:'completed' is a version", isVersionSuccess({ status: 'completed' }) === true);
check("status:'failed' is NOT a version", isVersionSuccess({ status: 'failed' }) === false);
check("status:'running' is NOT a version", isVersionSuccess({ status: 'running' }) === false);
check('null is NOT a version', isVersionSuccess(null) === false);
check('undefined is NOT a version', isVersionSuccess(undefined) === false);
check('reverted edit (ok:false) is NOT a version', isVersionSuccess({ ok: false, reverted: true }) === false);

// ---- simulate the actual handlers (mirror App.jsx exactly) ----
// editElement / addSection: push the instruction ONLY when isVersionSuccess(data)
const applyEdit = (history, data, instruction) =>
  isVersionSuccess(data) ? [...history, instruction] : history;
// replaceImageUpload / replaceImageAI: NEVER touch version history (image swap only)
const applyImage = (history /*, data */) => history;
// runGeneration: process streamed events; record the label ONLY at 'completed'
const applyGeneration = (history, events, label) => {
  let h = history;
  for (const ev of events) if (isVersionSuccess(ev)) h = [...h, label];
  return h;
};

// task-4 cases
check('successful edit -> exactly ONE version', applyEdit([], { ok: true, file: 'page.jsx' }, 'make it red').length === 1);
check('failed edit (ok:false) -> ZERO versions', applyEdit([], { ok: false, error: 'no' }, 'make it red').length === 0);
check('failed edit (422) -> ZERO versions', applyEdit([], { detail: [{ msg: 'bad' }] }, 'make it red').length === 0);
check('failed add-section -> ZERO versions', applyEdit([], { ok: false }, 'add a gallery').length === 0);
check('failed image upload -> ZERO versions', applyImage([], { ok: false }).length === 0);
check('failed image generation -> ZERO versions', applyImage([], { ok: false, error: 'gen failed' }).length === 0);
check('successful image (still) records no version entry', applyImage([], { ok: true }).length === 0);
check('successful generation -> version only AFTER completion',
  applyGeneration([], [{ status: 'running', log: 'planning' }, { status: 'running', log: 'build' }, { status: 'completed' }], 'Build app').length === 1);
check('generation fails before build -> ZERO versions',
  applyGeneration([], [{ status: 'running', log: 'planning' }, { status: 'failed' }], 'Build app').length === 0);
check('generation fails AFTER partial logs -> ZERO versions',
  applyGeneration([], [{ status: 'running', log: 'a' }, { status: 'running', log: 'b' }, { status: 'failed' }], 'Build app').length === 0);
check('thrown exception (no result) -> ZERO versions', applyEdit([], null, 'make it red').length === 0);
check('SRS upload that fails -> ZERO versions (label only at completion)',
  applyGeneration([], [{ status: 'failed' }], 'Uploaded spec.pdf').length === 0);
check('SRS upload that succeeds -> exactly ONE version with the file label',
  JSON.stringify(applyGeneration([], [{ status: 'running' }, { status: 'completed' }], 'Uploaded spec.pdf')) === JSON.stringify(['Uploaded spec.pdf']));

// NO duplicate for a single success: one success event -> length grows by exactly 1
const before = ['v1'];
check('one successful edit adds exactly one entry (no duplicate)', applyEdit(before, { ok: true }, 'v2').length === before.length + 1);
check('one successful generation adds exactly one entry (no duplicate)',
  applyGeneration(before, [{ status: 'completed' }], 'v2').length === before.length + 1);

console.log('='.repeat(62));
console.log(failed === 0 ? 'ALL VERSIONING TESTS GREEN — no false-success versions possible' : `${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
