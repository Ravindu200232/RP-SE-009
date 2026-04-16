const express = require('express');
const cors = require('cors');
const { servicePorts } = require('../shared/config');

const app = express();
const PORT = servicePorts.board;

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/api/board', require('./routes/board'));

// Health check
app.get('/health', (req, res) => {
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    service: 'board-service'
  });
});

app.listen(PORT, () => {
  console.log(`Board service running on port ${PORT}`);
});
