import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  // Next.js App Router files are `.js` and contain JSX. Vite only applies the
  // JSX transform to `.jsx` unless told otherwise, so a test that imports a
  // page fails to parse at the first `<`. This is the whole fix.
  plugins: [react({ include: /\.(js|jsx)$/ })],
  // The same `@/` alias the application uses. A test that reaches past it with
  // a relative path breaks the moment a file moves.
  resolve: { alias: { '@': path.resolve(process.cwd()) } },
  test: {
    // Components need a DOM. A file that needs Node instead says so in its own
    // docblock, which is cheaper and clearer
    // than a second config that drifts from this one.
    environment: 'jsdom',
    // The setup file extends `expect`, which only exists globally when this is
    // on. Config without it plus a matcher setup file is a contradiction that
    // fails at collection with "expect is not defined".
    globals: true,
    setupFiles: ['vitest.setup.js'],
    include: ['test/**/*.test.{js,jsx}'],
    testTimeout: 15000,
    hookTimeout: 15000,
  },
});
