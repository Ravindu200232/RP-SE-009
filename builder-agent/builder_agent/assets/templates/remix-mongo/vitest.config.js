import react from '@vitejs/plugin-react';
import path from 'node:path';
import { defineConfig } from 'vitest/config';

/**
 * The Remix plugin is deliberately absent here.
 *
 * It rewrites route modules for the framework's own loader/action split and
 * expects a Remix request to be in flight. Under the test runner there is
 * none, so including it turns every component test into an error about a
 * missing route context. Tests import the component; the plugin belongs to
 * `vite.config.js` and to the build.
 */
export default defineConfig({
  plugins: [react({ include: /\.(js|jsx)$/ })],
  // The same two aliases the application uses: `~/` for app code, which is the
  // Remix convention, and `@/` for the project root.
  resolve: {
    alias: {
      '~': path.resolve(process.cwd(), 'app'),
      '@': path.resolve(process.cwd()),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['vitest.setup.js'],
    include: ['test/**/*.test.{js,jsx}'],
    testTimeout: 15000,
    hookTimeout: 15000,
  },
});
