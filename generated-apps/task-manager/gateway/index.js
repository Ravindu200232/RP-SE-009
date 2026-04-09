require('dotenv').config();
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cors());

app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    gateway: true,
    routes: [{"prefix":"/api/v1/auth","service":"auth-service","target":"http://localhost:3001"},{"prefix":"/api/v1/tasks","service":"task-service","target":"http://localhost:3002"},{"prefix":"/api/v1/task","service":"task-service","target":"http://localhost:3002"},{"prefix":"/api/v1/dashboard","service":"dashboard-service","target":"http://localhost:3003"}]
  });
});

// ── Service Proxies ──────────────────────────────────────────

// auth-service
app.use('/api/v1/auth', createProxyMiddleware({
  target: 'http://localhost:3001',
  changeOrigin: true,
  on: {
    error: (err, req, res) => {
      console.error('[Gateway] auth-service unreachable:', err.message);
      if (!res.headersSent) res.status(502).json({ error: 'Service unavailable: auth-service' });
    }
  }
}));

// task-service
app.use('/api/v1/tasks', createProxyMiddleware({
  target: 'http://localhost:3002',
  changeOrigin: true,
  on: {
    error: (err, req, res) => {
      console.error('[Gateway] task-service unreachable:', err.message);
      if (!res.headersSent) res.status(502).json({ error: 'Service unavailable: task-service' });
    }
  }
}));

// task-service
app.use('/api/v1/task', createProxyMiddleware({
  target: 'http://localhost:3002',
  changeOrigin: true,
  on: {
    error: (err, req, res) => {
      console.error('[Gateway] task-service unreachable:', err.message);
      if (!res.headersSent) res.status(502).json({ error: 'Service unavailable: task-service' });
    }
  }
}));

// dashboard-service
app.use('/api/v1/dashboard', createProxyMiddleware({
  target: 'http://localhost:3003',
  changeOrigin: true,
  on: {
    error: (err, req, res) => {
      console.error('[Gateway] dashboard-service unreachable:', err.message);
      if (!res.headersSent) res.status(502).json({ error: 'Service unavailable: dashboard-service' });
    }
  }
}));

// ── Frontend Proxy ───────────────────────────────────────────
app.use('/', createProxyMiddleware({
  target: 'http://localhost:5173',
  changeOrigin: true,
  ws: true,
  on: {
    error: (err, req, res) => {
      if (!res.headersSent) res.status(502).json({ error: 'Frontend not ready. Run: npm run dev in frontend/' });
    }
  }
}));

const PORT = process.env.GATEWAY_PORT || 8080;
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(err.status || 500).json({ error: err.message || 'Internal Server Error' });
});

app.listen(PORT, () => {
  console.log(`Gateway running at http://localhost:${PORT}`);
  console.log('Proxying:');
  console.log('  /api/v1/auth → http://localhost:3001 (auth-service)');
  console.log('  /api/v1/tasks → http://localhost:3002 (task-service)');
  console.log('  /api/v1/task → http://localhost:3002 (task-service)');
  console.log('  /api/v1/dashboard → http://localhost:3003 (dashboard-service)');
  console.log(`  / → http://localhost:5173 (frontend)`);
});
