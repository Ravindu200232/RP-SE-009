const express = require('express');
const { createProxyMiddleware, fixRequestBody } = require('http-proxy-middleware');
const cors = require('cors');
const { servicePorts, serviceUrls } = require('../shared/config');

const app = express();
const PORT = servicePorts.gateway;

app.use(cors());
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    service: 'api-gateway'
  });
});

const createServiceProxy = (target, serviceName) =>
  createProxyMiddleware({
    target,
    changeOrigin: true,
    logLevel: 'debug',
    proxyTimeout: 10000,
    timeout: 10000,
    onProxyReq: fixRequestBody,
    onError: (error, req, res) => {
      if (res.headersSent) {
        return;
      }

      res.status(502).json({
        success: false,
        error: `${serviceName} is unavailable`,
        details: error.code || error.message,
      });
    },
  });

// Proxy configuration
app.use('/api/tasks', createServiceProxy(serviceUrls.tasks, 'tasks-service'));
app.use('/api/board', createServiceProxy(serviceUrls.board, 'board-service'));
app.use('/api/boards', createServiceProxy(serviceUrls.board, 'board-service'));

app.listen(PORT, () => {
  console.log(`API Gateway running on port ${PORT}`);
});
