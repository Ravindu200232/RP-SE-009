import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  // Apply JSX transformation to .js files used in Next.js App Router routes.
  plugins: [react({ include: /\.(js|jsx)$/ })],
  // The same `@/` alias the application uses. A test that reaches past it with
  // a relative path breaks the moment a file moves.
  resolve: { alias: { '@': path.resolve(process.cwd()) } },
  test: {
    // Default test environment to jsdom for client and page component testing.
    environment: 'jsdom',
    // Enable global assertions required by test matchers setup file.
    globals: true,
    setupFiles: ['vitest.setup.js'],
    include: ['test/**/*.test.{js,jsx}'],
    testTimeout: 15000,
    hookTimeout: 15000,
  },
});
