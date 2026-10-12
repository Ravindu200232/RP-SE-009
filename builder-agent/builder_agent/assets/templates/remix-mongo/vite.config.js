import { vitePlugin as remix } from '@remix-run/dev';
import { defineConfig } from 'vite';

/** Remix runs as a Vite plugin. */
export default defineConfig({
  plugins: [
    remix({
      future: {
        v3_fetcherPersist: true,
        v3_relativeSplatPath: true,
        v3_throwAbortReason: true,
        v3_singleFetch: true,
        v3_lazyRouteDiscovery: true,
      },
    }),
  ],
  server: {
    // Studio supplies an isolated port for every project preview.
    host: '127.0.0.1',
    port: Number(process.env.PORT ?? 0),
    strictPort: true,
  },
});
