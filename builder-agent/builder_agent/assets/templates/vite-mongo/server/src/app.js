import path from 'node:path';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import express from 'express';

const here = path.dirname(fileURLToPath(import.meta.url));
// server/src -> server -> repo root -> client.
const clientDist = path.resolve(here, '../../client/dist');

export function createApp() {
  const app = express();
  // `X-Powered-By: Express` tells a scanner which framework to attack.
  app.disable('x-powered-by');
  // This server is the only public door, so it is where response headers are set.
  const frameAncestors = process.env.FRAME_ANCESTORS?.trim() || "'none'";
  app.use((req, res, next) => {
    res.set({
      ...(frameAncestors === "'none'" ? { 'X-Frame-Options': 'DENY' } : {}),
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
      'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
      'Content-Security-Policy': [
        "default-src 'self'", "script-src 'self' 'unsafe-inline'", "style-src 'self' 'unsafe-inline' https:",
        "img-src 'self' data: blob: https:", "font-src 'self' data: https:", "connect-src 'self'",
        `frame-ancestors ${frameAncestors}`, "base-uri 'self'", "form-action 'self'", "object-src 'none'",
      ].join('; '),
    });
    next();
  });
  app.use(express.json());

  // Readiness is about this process, not the database behind it: a 200 here must not be read as "MongoDB is reachable".
  app.get('/ready', (req, res) => res.json({ ok: true, clientBuilt: existsSync(clientDist) }));

  // Replace this with the application's own routes under /api.
  app.get('/api/health', (req, res) => res.json({ ok: true }));

  if (existsSync(clientDist)) {
    app.use(express.static(clientDist));
    // The SPA fallback comes last and must not swallow /api: a missing API route has to stay a 404, not silently return index.html with status 200.
    app.get(/^(?!\/api\/).*/, (req, res) => res.sendFile(path.join(clientDist, 'index.html')));
  } else {
    app.get('/', (req, res) => res.status(503).type('text/plain')
      .send('Client bundle is not built. Run: npm run build'));
  }
  app.use((req, res) => res.status(404).json({ error: 'Not found' }));
  return app;
}
