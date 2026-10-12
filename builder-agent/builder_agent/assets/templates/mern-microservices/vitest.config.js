import { defineConfig } from 'vitest/config';

/** Root settings for `npm run test:coverage`. */
export default defineConfig({
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'json-summary'],
      reportsDirectory: '.agentforge/qa/coverage',
      include: ['packages/*/src/**/*.js', 'client/src/**/*.{js,jsx}'],
      exclude: ['**/*.test.*', '**/server.js', '**/main.jsx', '**/config.js', '**/db.js'],
    },
  },
});
