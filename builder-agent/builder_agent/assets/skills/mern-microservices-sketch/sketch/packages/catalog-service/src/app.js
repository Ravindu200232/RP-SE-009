import express from 'express';
import { productsRouter } from './routes/products.routes.js';

/**
 * The app is built without listening, so tests can drive it over supertest and
 * the server file stays the only place that binds a port.
 */
export function createApp() {
  const app = express();
  app.use(express.json());
  app.get('/health', (req, res) => res.json({ ok: true, service: 'catalog' }));
  app.use('/products', productsRouter);
  app.use((req, res) => res.status(404).json({ error: 'Not found' }));
  // Four arguments: Express only treats this as an error handler with all four.
  app.use((error, req, res, next) => {
    if (error?.code === 11000) return res.status(409).json({ error: 'Duplicate key' });
    res.status(500).json({ error: 'Internal error' });
  });
  return app;
}
