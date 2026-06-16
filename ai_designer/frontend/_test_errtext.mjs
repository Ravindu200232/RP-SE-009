// Regression test for the centralized error formatter.
// Run: node _test_errtext.mjs   (exit 1 on any failure)
// Guarantees the studio can NEVER render "[object Object]" for any backend error.
import { errText } from './src/lib/errText.js';

const FB = 'FALLBACK';
// [name, input, expected]  - expected null = "any non-empty text, just never [object Object]"
const cases = [
  ['simple string error', 'simple string error', 'simple string error'],
  ['Error instance', new Error('boom failed'), 'boom failed'],
  ['FastAPI 422 detail array', { detail: [{ loc: ['body', 'component_id'], msg: 'Input should be a valid string' }] }, 'Input should be a valid string'],
  ['FastAPI 422 multi-item', { detail: [{ msg: 'field a required' }, { msg: 'field b required' }] }, 'field a required; field b required'],
  ['FastAPI detail string', { detail: 'Something failed' }, 'Something failed'],
  ['backend error string', { error: 'Something failed' }, 'Something failed'],
  ['backend error object {message}', { error: { message: 'Bad request' } }, 'Bad request'],
  ['unknown nested object', { error: { a: { b: 1 } } }, null],
  ['deeply nested {error:{detail:[...]}}', { error: { detail: [{ msg: 'nested msg' }] } }, 'nested msg'],
  ['empty object', {}, FB],
  ['null', null, FB],
  ['undefined', undefined, FB],
  ['number', 42, '42'],
  ['object that stringifies to nothing useful', { weird: true }, null],
];

let failed = 0;
for (const [name, input, expected] of cases) {
  const out = errText(input, FB);
  const noObjObj = typeof out === 'string' && !out.includes('[object Object]');
  const matches = expected === null ? (out && out !== FB) : out === expected;
  const ok = noObjObj && matches;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name.padEnd(38)} -> ${JSON.stringify(out)}`);
  if (!ok) failed++;
}

// Hard invariant: NOTHING produces "[object Object]"
const adversarial = [{ error: {} }, { detail: {} }, { error: [{}] }, [{}], { a: 1 }, () => {}, Symbol('x') ? { s: 1 } : null];
for (const a of adversarial) {
  const out = errText(a, FB);
  if (typeof out !== 'string' || out.includes('[object Object]')) {
    console.log(`FAIL  adversarial ${JSON.stringify(a)} -> ${out}`);
    failed++;
  }
}

console.log('='.repeat(60));
console.log(failed === 0 ? 'ALL ERRTEXT TESTS GREEN — [object Object] is impossible' : `${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
