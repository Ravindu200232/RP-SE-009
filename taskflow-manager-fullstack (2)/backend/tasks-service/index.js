const express = require('express');
const cors = require('cors');
const { servicePorts } = require('../shared/config');
const taskRepository = require('./lib/taskRepository');

const app = express();
const PORT = servicePorts.tasks;

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/api/tasks', require('./routes/tasks'));

// Health check
app.get('/health', (req, res) => {
  const storage = taskRepository.getStorageState();
  res.json({ 
    status: 'ok', 
    timestamp: new Date().toISOString(),
    service: 'tasks-service',
    storage
  });
});

taskRepository
  .initialize()
  .then((storage) => {
    console.log(`Tasks service using ${storage.mode} storage`);
    if (storage.error) {
      console.warn(`MongoDB unavailable, falling back to file storage: ${storage.error}`);
    }

    app.listen(PORT, () => {
      console.log(`Tasks service running on port ${PORT}`);
    });
  })
  .catch((error) => {
    console.error('Failed to initialize tasks service', error);
    process.exit(1);
  });
