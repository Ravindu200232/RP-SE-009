const express = require('express');
const { v4: uuidv4 } = require('uuid');
const Generation = require('../models/Generation');
const GenerationOrchestrator = require('../services/generationOrchestrator');

module.exports = (io) => {
  const router = express.Router();
  const orchestrator = new GenerationOrchestrator(io);

  /**
   * POST /api/generate
   * Start a new code generation job.
   * Body: { srs: { ... } }   — SRS JSON document
   */
  router.post('/', async (req, res) => {
    try {
      const { srs } = req.body;

      if (!srs || typeof srs !== 'object') {
        return res.status(400).json({
          error: 'Invalid request',
          message: 'Body must contain a "srs" object with your Software Requirements Specification'
        });
      }

      // Check Ollama is available
      const ollamaService = new (require('../services/ollamaService'))(io);
      const health = await ollamaService.checkHealth();
      if (!health.ok) {
        return res.status(503).json({
          error: 'Ollama not available',
          message: health.error,
          hint: `Make sure Ollama is running: ollama serve\nThen pull the model: ollama pull ${process.env.OLLAMA_MODEL}`
        });
      }

      const jobId = uuidv4();
      const job = await Generation.create({ jobId, srs, status: 'pending' });

      // Respond immediately with jobId
      res.status(202).json({
        jobId,
        message: 'Generation started. Connect to WebSocket and join room with jobId to receive updates.',
        wsRoom: jobId,
        statusUrl: `/api/generate/${jobId}`
      });

      // Run orchestration in background (no await)
      orchestrator.run(jobId, srs).catch((err) => {
        console.error(`[Generate] Job ${jobId} failed:`, err.message);
      });

    } catch (err) {
      console.error('[Generate] Error:', err);
      res.status(500).json({ error: 'Internal server error', message: err.message });
    }
  });

  /**
   * GET /api/generate/:jobId
   * Get status and details of a generation job.
   */
  router.get('/:jobId', async (req, res) => {
    try {
      const job = await Generation.findOne({ jobId: req.params.jobId })
        .select('-generatedFiles'); // exclude large field for status checks

      if (!job) {
        return res.status(404).json({ error: 'Job not found' });
      }

      res.json({
        jobId: job.jobId,
        status: job.status,
        progress: job.progress,
        currentAgent: job.currentAgent,
        plan: job.plan,
        services: job.services,
        gatewayUrl: job.gatewayUrl,
        frontendUrl: job.frontendUrl,
        allUrls: job.allUrls,
        error: job.error,
        logs: job.logs?.slice(-50), // last 50 logs
        createdAt: job.createdAt,
        updatedAt: job.updatedAt
      });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  /**
   * GET /api/generate/:jobId/files
   * Get all generated files for a job.
   */
  router.get('/:jobId/files', async (req, res) => {
    try {
      const job = await Generation.findOne({ jobId: req.params.jobId })
        .select('jobId generatedFiles status');

      if (!job) return res.status(404).json({ error: 'Job not found' });

      res.json({
        jobId: job.jobId,
        status: job.status,
        totalFiles: job.generatedFiles.length,
        files: job.generatedFiles.map(f => ({
          path: f.path,
          service: f.service,
          size: f.content?.length || 0
        }))
      });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  /**
   * GET /api/generate/:jobId/files/:filePath
   * Get content of a specific generated file.
   */
  router.get('/:jobId/file', async (req, res) => {
    try {
      const { filePath } = req.query;
      const job = await Generation.findOne({ jobId: req.params.jobId })
        .select('generatedFiles');

      if (!job) return res.status(404).json({ error: 'Job not found' });

      const file = job.generatedFiles.find(f => f.path === filePath);
      if (!file) return res.status(404).json({ error: 'File not found' });

      res.json({ path: file.path, content: file.content, service: file.service });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  /**
   * DELETE /api/generate/:jobId
   * Cancel or clean up a generation job.
   */
  router.delete('/:jobId', async (req, res) => {
    try {
      await orchestrator.runner.stopAll();
      await Generation.updateOne({ jobId: req.params.jobId }, { status: 'error', error: 'Cancelled by user' });
      res.json({ message: 'Job cancelled' });
    } catch (err) {
      res.status(500).json({ error: err.message });
    }
  });

  return router;
};
