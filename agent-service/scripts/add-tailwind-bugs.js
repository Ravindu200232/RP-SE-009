/**
 * One-off script: Insert Tailwind/Vite bug patterns into BugStore.
 * Run: node scripts/add-tailwind-bugs.js
 */
require('dotenv').config();
const mongoose = require('mongoose');

const BugStoreSchema = new mongoose.Schema({
  patternId: { type: String, unique: true, required: true },
  name: String, category: String, severity: String,
  description: String, badCode: String, goodCode: String,
  preventionRule: String, affectsServices: [String],
  occurrences: { type: Number, default: 1 },
  autoFixable: { type: Boolean, default: true }
});
const BugStore = mongoose.model('BugStore', BugStoreSchema);

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/codeagent';

const newBugs = [
  {
    patternId: 'tailwind-postcss-wrong-vite',
    name: 'Tailwind used as PostCSS plugin instead of Vite plugin',
    category: 'vite-config-error',
    severity: 'critical',
    description: 'Vite+React projects must use @tailwindcss/vite plugin, NOT tailwindcss as a PostCSS plugin. Using tailwindcss in postcss.config.js breaks the Vite build.',
    badCode: '// postcss.config.js — WRONG for Vite projects\nexport default { plugins: { tailwindcss: {}, autoprefixer: {} } }',
    goodCode: '// vite.config.js — CORRECT\nimport tailwindcss from "@tailwindcss/vite";\nexport default defineConfig({ plugins: [react(), tailwindcss()] });\n// src/index.css: @import "tailwindcss";',
    preventionRule: 'For Vite+React: NEVER create postcss.config.js for Tailwind. ALWAYS use @tailwindcss/vite as a Vite plugin. src/index.css must start with: @import "tailwindcss";',
    affectsServices: ['vite', 'react', 'frontend'],
    occurrences: 3,
    autoFixable: true
  },
  {
    patternId: 'vite-missing-tailwind-import',
    name: 'Vite frontend missing @import "tailwindcss" in index.css',
    category: 'vite-config-error',
    severity: 'high',
    description: 'When using @tailwindcss/vite plugin, index.css must contain @import "tailwindcss" — not @tailwind base/components/utilities directives',
    badCode: '/* WRONG */\n@tailwind base;\n@tailwind components;\n@tailwind utilities;',
    goodCode: '/* CORRECT for @tailwindcss/vite */\n@import "tailwindcss";',
    preventionRule: 'With @tailwindcss/vite plugin: index.css must use @import "tailwindcss" NOT the old @tailwind directives',
    affectsServices: ['vite', 'react', 'frontend'],
    occurrences: 2,
    autoFixable: true
  },
  {
    patternId: 'vite-config-no-preview-port',
    name: 'vite.config.js missing preview port config',
    category: 'vite-config-error',
    severity: 'medium',
    description: 'Vite preview server uses random port if not configured — must set port: 3001 for both server and preview',
    badCode: 'export default defineConfig({ plugins: [react()] })',
    goodCode: 'export default defineConfig({ plugins: [react(), tailwindcss()], server: { port: 3001 }, preview: { port: 3001, strictPort: true } })',
    preventionRule: 'Always set server.port AND preview.port in vite.config.js to ensure consistent port for dev and production preview',
    affectsServices: ['vite', 'react', 'frontend'],
    occurrences: 1,
    autoFixable: true
  }
];

async function main() {
  await mongoose.connect(MONGODB_URI);
  console.log('Connected to MongoDB');

  let inserted = 0;
  for (const bug of newBugs) {
    const result = await BugStore.updateOne(
      { patternId: bug.patternId },
      { $setOnInsert: bug },
      { upsert: true }
    );
    if (result.upsertedCount > 0) {
      console.log(`✓ Inserted: ${bug.name}`);
      inserted++;
    } else {
      console.log(`- Already exists: ${bug.patternId}`);
    }
  }

  const total = await BugStore.countDocuments();
  console.log(`\nDone! Inserted ${inserted} new bug patterns. Total in DB: ${total}`);
  await mongoose.disconnect();
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
