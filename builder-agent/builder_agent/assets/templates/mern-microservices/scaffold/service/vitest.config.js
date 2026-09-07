import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Server code runs in Node. Moving it into a browser-like environment to
    // make something pass hides the environment the code actually runs in.
    environment: 'node',
    include: ['test/**/*.test.js'],
    // Every service in this workspace shares one MongoDB. Run files in
    // parallel and they clear each other's collections mid-test, which reads
    // as a defect in whichever suite happened to run second.
    fileParallelism: false,
    testTimeout: 15000,
    hookTimeout: 15000,
  },
});
