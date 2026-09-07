import path from 'node:path';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import express from 'express';
import { proxyTo } from './proxy.js';

const here = path.dirname(fileURLToPath(import.meta.url));
// packages/gateway/src -> packages/gateway -> packages -> repo root -> client
const clientDist = path.resolve(here, '../../../client/dist');

export function createApp(config) {
  const app = express();
  app.use(express.json());

  // Readiness is about this process. It must not report the whole system
  // healthy, because a 200 here says nothing about the services behind it.
  app.get('/ready', (req, res) => res.json({ ok: true, clientBuilt: existsSync(clientDist) }));

  app.use('/api/products', proxyTo(config.services.catalog));

  if (existsSync(clientDist)) {
    app.use(express.static(clientDist));
    // The SPA fallback comes last and must not swallow /api: a missing API
    // route has to stay a 404, not silently return index.html with status 200.
    app.get(/^(?!\/api\/).*/, (req, res) => res.sendFile(path.join(clientDist, 'index.html')));
  } else {
    app.get('/', (req, res) => res.status(503).type('text/plain')
      .send('Client bundle is not built. Run: npm run build'));
  }
  app.use((req, res) => res.status(404).json({ error: 'Not found' }));
  return app;
}
