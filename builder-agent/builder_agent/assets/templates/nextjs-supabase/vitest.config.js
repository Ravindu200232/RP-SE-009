import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  // Apply JSX transformation to .js files used in Next.js App Router routes.
  plugins: [react({ include: /\.(js|jsx)$/ })],
  // The same `@/` alias the application uses.
  resolve: {
    alias: {
      '@': path.resolve(process.cwd()),
      'server-only': path.resolve(process.cwd(), 'test/helpers/server-only-stub.js'),
    },
  },
  test: {
    // jsdom is for components and pages.
    environment: 'jsdom',
    environmentMatchGlobs: [['test/**/*.node.test.{js,jsx}', 'node']],
    // A suite using test/helpers/db.js shares the local stack's tables with every other such suite.
    fileParallelism: false,
    // Enable global assertions required by test matchers setup file.
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
      include: ['app/**/*.{js,jsx}', 'components/**/*.{js,jsx}', 'lib/**/*.js', 'models/**/*.js', 'hooks/**/*.{js,jsx}', 'services/**/*.js', 'src/**/*.{js,jsx}', 'proxy.js', 'middleware.js'],
      exclude: ['**/*.test.*', 'test/**', 'e2e/**', 'lib/supabase.js'],
    },
    testTimeout: 15000,
    hookTimeout: 15000,
  },
});
