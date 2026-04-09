/**
 * SRS API Routes
 *
 * POST /api/srs/session        — Create new session
 * POST /api/srs/start          — Process initial input (multimodal)
 * POST /api/srs/answer         — Submit question answers
 * GET  /api/srs/session/:id    — Get session state
 * GET  /api/srs/json/:id       — Get generated SRS JSON
 */

import express from 'express';
import multer from 'multer';
import path from 'path';
import { fileURLToPath } from 'url';
import srsBuilderAgent from '../services/srsBuilderAgent.js';

const router = express.Router();
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ── Multer file upload configuration ────────────────────────────────────────
const storage = multer.diskStorage({
  destination: path.join(__dirname, '../../../uploads'),
  filename: (req, file, cb) => {
    const unique = Date.now() + '-' + Math.round(Math.random() * 1e9);
    cb(null, unique + path.extname(file.originalname));
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 50 * 1024 * 1024 }, // 50MB
  fileFilter: (req, file, cb) => {
    const allowedMimeTypes = new Set([
      'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/svg+xml',
      'application/pdf',
      'audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/x-wav', 'audio/mp4',
      'audio/m4a', 'audio/x-m4a', 'audio/ogg', 'audio/webm', 'audio/aac',
      'text/plain', 'text/markdown', 'text/x-markdown', 'application/json', 'text/csv'
    ]);
    const allowedExtensions = new Set([
      '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg',
      '.pdf',
      '.mp3', '.wav', '.m4a', '.ogg', '.webm', '.aac',
      '.txt', '.md', '.markdown', '.json', '.csv'
    ]);
    const extension = path.extname(file.originalname || '').toLowerCase();

    if (allowedMimeTypes.has(file.mimetype) || allowedExtensions.has(extension)) {
      cb(null, true);
    } else {
      cb(new Error(`File type ${file.mimetype} not supported`));
    }
  }
});

// ── Create session ────────────────────────────────────────────────────────────
router.post('/session', (req, res) => {
  try {
    const sessionId = srsBuilderAgent.createSession();
    res.json({ sessionId });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Start: Process multimodal input ──────────────────────────────────────────
router.post('/start', upload.array('files', 10), async (req, res) => {
  const { sessionId, prompt } = req.body;
  const files = req.files || [];

  if (!sessionId) {
    return res.status(400).json({ error: 'sessionId is required' });
  }
  if (!prompt && files.length === 0) {
    return res.status(400).json({ error: 'Provide a text prompt or upload files' });
  }

  try {
    const result = await srsBuilderAgent.processInitialInput(
      sessionId, prompt || '', files, req.io
    );
    res.json(result);
  } catch (err) {
    console.error('[Route] /start error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Answer: Submit answers to gap-filling questions ───────────────────────────
router.post('/answer', async (req, res) => {
  const { sessionId, answers } = req.body;

  if (!sessionId || !answers) {
    return res.status(400).json({ error: 'sessionId and answers are required' });
  }

  try {
    const result = await srsBuilderAgent.generateWithAnswers(sessionId, answers, req.io);
    res.json({ success: true, srs: result.srs });
  } catch (err) {
    console.error('[Route] /answer error:', err);
    res.status(500).json({ error: err.message });
  }
});

// ── Get session state ─────────────────────────────────────────────────────────
router.get('/session/:id', (req, res) => {
  const session = srsBuilderAgent.getSession(req.params.id);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  res.json({
    id: session.id,
    status: session.status,
    knownInfo: session.knownInfo,
    pendingQuestions: session.pendingQuestions,
    questionPlanPath: session.questionPlanPath,
    srsJsonPath: session.srsJsonPath,
    validationReport: session.validationReport,
    validationReportPath: session.validationReportPath,
    logs: session.logs
  });
});

// ── Get SRS JSON ──────────────────────────────────────────────────────────────
router.get('/json/:id', (req, res) => {
  const srs = srsBuilderAgent.getSRS(req.params.id);
  if (!srs) return res.status(404).json({ error: 'SRS not generated yet' });
  res.json(srs);
});

// ── Download SRS as raw JSON file ─────────────────────────────────────────────
router.get('/download/:id', (req, res) => {
  const srs = srsBuilderAgent.getSRS(req.params.id);
  if (!srs) return res.status(404).json({ error: 'SRS not found' });
  const name = srs.metadata?.project_name?.replace(/\s+/g, '_') || 'srs';
  res.setHeader('Content-Disposition', `attachment; filename=${name}_SRS.json`);
  res.setHeader('Content-Type', 'application/json');
  res.send(JSON.stringify(srs, null, 2));
});

export default router;
