import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// base './' so the built app works served from ANY subpath (the studio serves
// each prototype from /output/<project>/dist/) - absolute '/assets/...' URLs
// are the classic Vite-static-hosting routing bug.
export default defineConfig({
  base: './',
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  build: {
    chunkSizeWarningLimit: 1500,
  },
});
