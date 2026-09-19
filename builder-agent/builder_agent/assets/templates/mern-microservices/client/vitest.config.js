import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    // Enable test globals so setup files can extend expect.
    globals: true,
    setupFiles: ['test/setup.js'],
    include: ['test/**/*.test.jsx'],
  },
});
