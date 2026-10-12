import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Server code runs in Node.
    environment: 'node',
    include: ['test/**/*.test.js'],
    // Run service test suites sequentially to prevent shared database collisions.
    fileParallelism: false,
    testTimeout: 15000,
    hookTimeout: 15000,
  },
});
