const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
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

// Proxy configuration
app.use('/api/tasks', createProxyMiddleware({
  target: serviceUrls.tasks,
  changeOrigin: true,
  logLevel: 'debug'
}));

app.use('/api/board', createProxyMiddleware({
  target: serviceUrls.board,
  changeOrigin: true,
  logLevel: 'debug'
}));

app.listen(PORT, () => {
  console.log(`API Gateway running on port ${PORT}`);
});
