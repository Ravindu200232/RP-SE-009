// Regression test for the inspector componentId derivation.
// Run: node _test_componentid.mjs   (exit 1 on any failure)
// Guarantees the inspector NEVER sends component_id: null/undefined.
import { routeComponentId, selectedComponentId } from './src/lib/componentId.js';

const noMarker = { closest: () => null };
const marked = (id) => ({ closest: () => ({ getAttribute: (a) => (a === 'data-component-id' ? id : null) }) });

const cases = [
  // [name, actual, expected]
  ['"/" -> home', routeComponentId('/'), 'home'],
  ['"/dashboard" -> dashboard', routeComponentId('/dashboard'), 'dashboard'],
  ['"/courses" -> page-courses', routeComponentId('/courses'), 'page-courses'],
  ['"/events-calendar" -> page-events-calendar', routeComponentId('/events-calendar'), 'page-events-calendar'],
  ['"/profile" -> profile', routeComponentId('/profile'), 'profile'],
  ['CRUD list "/e/courses" -> route', routeComponentId('/e/courses'), 'route:/e/courses'],
  ['CRUD detail "/e/courses/123" -> route', routeComponentId('/e/courses/123'), 'route:/e/courses/123'],
  ['CRUD edit "/e/courses/123/edit" -> route', routeComponentId('/e/courses/123/edit'), 'route:/e/courses/123/edit'],
  ['CRUD new "/e/courses/new" -> route', routeComponentId('/e/courses/new'), 'route:/e/courses/new'],
  ['CRUD create "/e/courses/create" -> route', routeComponentId('/e/courses/create'), 'route:/e/courses/create'],
  ['trailing slash "/courses/" -> page-courses', routeComponentId('/courses/'), 'page-courses'],
  ['home click WITHOUT marker -> home', selectedComponentId(noMarker, '/'), 'home'],
  ['marked element -> its real id', selectedComponentId(marked('navbar'), '/dashboard'), 'navbar'],
  ['marked element overrides route', selectedComponentId(marked('crud-orders'), '/e/orders/5'), 'crud-orders'],
];

let failed = 0;
for (const [name, actual, expected] of cases) {
  const ok = actual === expected;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name.padEnd(46)} -> ${JSON.stringify(actual)}`);
  if (!ok) { failed++; console.log(`       expected ${JSON.stringify(expected)}`); }
}

// Hard invariant: NEVER null/undefined/empty for ANY input
const weird = [null, undefined, '', '/', '///', '/x/y/z', '/E/Courses/9', '/a b c', '/page?q=1#h', '/123'];
for (const p of weird) {
  const r = routeComponentId(p);
  const s = selectedComponentId(noMarker, p);
  if (!r || typeof r !== 'string' || !s || typeof s !== 'string') {
    console.log(`FAIL  never-null for ${JSON.stringify(p)} -> route=${r} sel=${s}`);
    failed++;
  }
}
console.log('='.repeat(60));
console.log(failed === 0 ? 'ALL COMPONENTID TESTS GREEN — component_id null is impossible' : `${failed} FAILED`);
process.exit(failed === 0 ? 0 : 1);
