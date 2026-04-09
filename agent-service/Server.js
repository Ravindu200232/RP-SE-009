/**
 * SRS Maker Agent — Server
 * Agent 1: Multimodal SRS JSON Generator
 *
 * Models:
 *  - openbmb/minicpm-o4.5 (local Ollama) — reads images, voice, PDF, text
 *  - deepseek-v3.1:671b-cloud (local Ollama) — generates IEEE SRS JSON
 */

import express from 'express';
import cors from 'cors';
import http from 'http';
import { Server as SocketIOServer } from 'socket.io';
import helmet from 'helmet';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import srsRoutes from './src/routes/srs.js';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const server = http.createServer(app);

const io = new SocketIOServer(server, {
  cors: { origin: '*', methods: ['GET', 'POST'] }
});

// ── Middleware ───────────────────────────────────────────────────────────────
app.use(helmet({ contentSecurityPolicy: false }));
app.use(cors());
app.use(express.json({ limit: '100mb' }));
app.use(express.urlencoded({ extended: true, limit: '100mb' }));

// Pass io to routes via request
app.use((req, res, next) => {
  req.io = io;
  next();
});

// ── Static uploads ───────────────────────────────────────────────────────────
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// ── Routes ───────────────────────────────────────────────────────────────────
app.use('/api/srs', srsRoutes);

app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'srs-maker-agent', timestamp: new Date().toISOString() });
});

// ── Socket.IO ────────────────────────────────────────────────────────────────
io.on('connection', (socket) => {
  console.log(`[Socket] Client connected: ${socket.id}`);
  socket.on('join:session', (sessionId) => {
    socket.join(sessionId);
    console.log(`[Socket] ${socket.id} joined session: ${sessionId}`);
  });
  socket.on('disconnect', () => {
    console.log(`[Socket] Client disconnected: ${socket.id}`);
  });
});

// ── Start ────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3200;
server.listen(PORT, () => {
  console.log(`\n🚀 SRS Maker Agent running on http://localhost:${PORT}`);
  console.log(`   MiniCPM model: ${process.env.MINICPM_MODEL}`);
  console.log(`   DeepSeek model: ${process.env.DEEPSEEK_MODEL}`);
  console.log(`   Ollama: ${process.env.OLLAMA_URL}\n`);
});

export { io };
