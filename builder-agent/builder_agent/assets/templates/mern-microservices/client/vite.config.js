import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    // In development the client is its own port, so /api is proxied to the
    // gateway. In production the gateway serves this build and there is no
    // proxy at all — one origin either way, so no CORS in either mode.
    proxy: { '/api': { target: 'http://127.0.0.1:4000', changeOrigin: true } },
  },
});
