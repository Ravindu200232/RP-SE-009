require('dotenv').config();
const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const connectDB = require('./config/db');
const createGenerateRoutes = require('./routes/workflowGenerate');
const historyRoutes = require('./routes/history');
const bugStoreRoutes = require('./routes/bugstore');
const workspacesRoutes = require('./routes/workspaces');
const createThreadsRoutes = require('./routes/threads');
const bugStoreService = require('./services/bugStoreService');

const app = express();
const server = http.createServer(app);

const io = new Server(server, {
  cors: { origin: '*', methods: ['GET', 'POST'] }
});

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true }));

// Connect to MongoDB then seed bug store
connectDB();
// Seed bug store after short delay (lets mongoose connect first)
setTimeout(() => bugStoreService.seed().catch(console.error), 2000);

// Routes
app.use('/api/generate', createGenerateRoutes(io));
app.use('/api/history', historyRoutes);
app.use('/api/bugs', bugStoreRoutes);
app.use('/api/workspaces', workspacesRoutes);
app.use('/api/threads', createThreadsRoutes(io));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', model: process.env.OLLAMA_MODEL, ollama: process.env.OLLAMA_URL });
});

// Socket.IO connection
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);
  socket.on('disconnect', () => console.log('Client disconnected:', socket.id));
  socket.on('join:job', (jobId) => {
    socket.join(jobId);
    console.log(`Socket ${socket.id} joined job room: ${jobId}`);
  });
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, () => {
  console.log(`\n🤖 Code Developer Agent Service`);
  console.log(`   Running on: http://localhost:${PORT}`);
  console.log(`   Ollama:     ${process.env.OLLAMA_URL}`);
  console.log(`   Model:      ${process.env.OLLAMA_MODEL}`);
  console.log(`   MongoDB:    ${process.env.MONGODB_URI}\n`);
});

module.exports = { io };
