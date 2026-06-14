// Syntax-validate generated JSX using the frontend's @babel/parser.
// Exit 0 = valid (or parser unavailable -> don't block); exit 1 = syntax error.
const path = require('path');
const fs = require('fs');
let parser;
try {
  parser = require(path.join(__dirname, '..', 'frontend', 'node_modules', '@babel', 'parser'));
} catch (e) {
  process.exit(0); // parser not installed -> skip validation rather than block generation
}
try {
  const code = fs.readFileSync(process.argv[2], 'utf8');
  // 'unambiguous': ESM files (Next pages with import/export) and plain scripts
  // (legacy browser-global prototypes) both parse.
  parser.parse(code, { sourceType: 'unambiguous', plugins: ['jsx'] });
  process.exit(0);
} catch (e) {
  process.stderr.write(String(e.message).split('\n')[0]);
  process.exit(1);
}
