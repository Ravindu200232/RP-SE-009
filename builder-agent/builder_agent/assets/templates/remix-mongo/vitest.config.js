import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vitest/config';

/** The Remix plugin is deliberately absent here. */
export default defineConfig({
  plugins: [react({ include: /\.(js|jsx)$/ })],
  // The same two aliases the application uses: `~/` for app code, which is the Remix convention, and `@/` for the project root.
  resolve: {
    alias: {
      '~': path.resolve(process.cwd(), 'app'),
      '@': path.resolve(process.cwd()),
    },
  },
  test: {
    // jsdom is for components.
    environment: 'jsdom',
    // The suites share one test database.
    fileParallelism: false,
    globals: true,
    // `test/helpers/fetch.js` stubs `fetch` for a test; the real one comes back after each test.
    unstubGlobals: true,
    setupFiles: ['vitest.env.js', 'vitest.setup.js'],
    include: ['test/**/*.test.{js,jsx}'],
    // `npm run test:coverage`.
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'json-summary'],
      reportsDirectory: '.agentforge/qa/coverage',
      include: ['app/**/*.{js,jsx}', 'lib/**/*.js', 'models/**/*.js', 'hooks/**/*.{js,jsx}', 'services/**/*.js'],
      exclude: ['**/*.test.*', 'test/**', 'e2e/**', 'lib/db.js', 'app/entry.*'],
    },
    testTimeout: 15000,
    hookTimeout: 15000,
  },
});
