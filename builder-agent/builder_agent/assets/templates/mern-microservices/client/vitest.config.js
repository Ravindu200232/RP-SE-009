import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // The setup file below extends `expect`, which only exists globally when
    // this is on. Without it the whole suite fails at collection with
    // "expect is not defined", pointing at the setup file.
    globals: true,
    setupFiles: ['test/setup.js'],
    include: ['test/**/*.test.jsx'],
  },
});
