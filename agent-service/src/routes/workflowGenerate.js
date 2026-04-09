const express = require('express');
const fs = require('fs-extra');
const path = require('path');
const { v4: uuidv4 } = require('uuid');

const Generation = require('../models/Generation');
const WorkflowOrchestrator = require('../services/workflowOrchestrator');

module.exports = (io) => {
  const router = express.Router();
  const orchestrator = new WorkflowOrchestrator(io);
  const MODEL_OPTIONS = [
    'kimi-k2.5:cloud',
    'deepseek-v3.1:671b-cloud',
    'gpt-oss:120b-cloud',
    'gemma4:31b-cloud',
    'qwen2.5:14b'
  ];

  router.get('/options', async (req, res) => {
    try {
      const ollamaService = new (require('../services/ollamaService'))(io);
      const health = await ollamaService.checkHealth();
      const availableModels = Array.isArray(health.models) ? health.models : [];
      const models = Array.from(new Set([...MODEL_OPTIONS, ...availableModels]));

      res.json({
        models,
        defaultModel: process.env.OLLAMA_MODEL || 'qwen2.5:14b',
        defaultTimeoutSeconds: Number.parseInt(process.env.OLLAMA_TIMEOUT_MS || '900000', 10) / 1000,
        availableModels
      });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  });

  router.post('/', async (req, res) => {
    try {
      const {
        srs,
        workspaceId = '',
        threadId = '',
        task = '',
        model = process.env.OLLAMA_MODEL || 'qwen2.5:14b',
        timeoutSeconds = 900,
        mode = workspaceId || threadId || task ? 'continue' : 'new'
      } = req.body || {};

      if (mode === 'new' && (!srs || typeof srs !== 'object')) {
        return res.status(400).json({
          error: 'Invalid request',
          message: 'New runs require an "srs" object.'
        });
      }

      if (mode === 'continue' && !workspaceId && !threadId) {
        return res.status(400).json({
          error: 'Invalid request',
          message: 'Continue runs require workspaceId or threadId.'
        });
      }

      const ollamaService = new (require('../services/ollamaService'))(io);
      const health = await ollamaService.checkHealth(model);
      if (!health.ok) {
        return res.status(503).json({
          error: 'Ollama not available',
          message: health.error,
          hint: `Make sure Ollama is running: ollama serve\nThen pull the model: ollama pull ${model}`
        });
      }

      const jobId = uuidv4();
      await Generation.create({
        jobId,
        srs: srs || {},
        status: 'pending',
        stage: 'pending',
        workspaceId,
        threadId,
        task,
        mode,
        model,
        timeoutSeconds: Math.max(60, Number(timeoutSeconds) || 900)
      });

      res.status(202).json({
        jobId,
        mode,
        workspaceId,
        threadId,
        model,
        timeoutSeconds: Math.max(60, Number(timeoutSeconds) || 900),
        message: 'Generation started. Join the job room over Socket.IO to stream updates.',
        wsRoom: jobId,
        statusUrl: `/api/generate/${jobId}`
      });

      orchestrator.run(jobId, {
        srs,
        workspaceId,
        threadId,
        task,
        mode,
        model,
        timeoutSeconds: Math.max(60, Number(timeoutSeconds) || 900)
      }).catch((error) => {
        console.error(`[Generate] Job ${jobId} failed:`, error.message);
      });
    } catch (error) {
      console.error('[Generate] Error:', error);
      res.status(500).json({ error: 'Internal server error', message: error.message });
    }
  });

  router.get('/:jobId', async (req, res) => {
    try {
      const job = await Generation.findOne({ jobId: req.params.jobId }).select('-generatedFiles');
      if (!job) {
        return res.status(404).json({ error: 'Job not found' });
      }

      res.json({
        jobId: job.jobId,
        workspaceId: job.workspaceId,
        threadId: job.threadId,
        mode: job.mode,
        task: job.task,
        model: job.model,
        timeoutSeconds: job.timeoutSeconds,
        status: job.status,
        stage: job.stage,
        progress: job.progress,
        currentAgent: job.currentAgent,
        plan: job.plan,
        services: job.services,
        gatewayUrl: job.gatewayUrl,
        frontendUrl: job.frontendUrl,
        allUrls: job.allUrls,
        stepResults: job.stepResults,
        memorySummary: job.memorySummary,
        artifactAudit: job.artifactAudit,
        error: job.error,
        errorSummary: job.errorSummary,
        logs: job.logs?.slice(-80) || [],
        createdAt: job.createdAt,
        updatedAt: job.updatedAt
      });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  });

  router.get('/:jobId/files', async (req, res) => {
    try {
      const job = await Generation.findOne({ jobId: req.params.jobId }).select('jobId generatedFiles status');
      if (!job) return res.status(404).json({ error: 'Job not found' });

      res.json({
        jobId: job.jobId,
        status: job.status,
        totalFiles: job.generatedFiles.length,
        files: job.generatedFiles.map((file) => ({
          path: file.path,
          service: file.service,
          size: file.content?.length || 0
        }))
      });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  });

  router.get('/:jobId/file', async (req, res) => {
    try {
      const { filePath } = req.query;
      const job = await Generation.findOne({ jobId: req.params.jobId }).select('generatedFiles appDir');
      if (!job) return res.status(404).json({ error: 'Job not found' });

      const generatedFile = job.generatedFiles.find((file) => file.path === filePath);
      if (generatedFile) {
        return res.json({ path: generatedFile.path, content: generatedFile.content, service: generatedFile.service });
      }

      if (job.appDir && filePath) {
        const absolutePath = path.join(job.appDir, String(filePath));
        if (await fs.pathExists(absolutePath)) {
          const content = await fs.readFile(absolutePath, 'utf8');
          return res.json({
            path: filePath,
            content,
            service: String(filePath).split(/[\\/]/)[0]
          });
        }
      }

      return res.status(404).json({ error: 'File not found' });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  });

  router.delete('/:jobId', async (req, res) => {
    try {
      await orchestrator.runner.stopAll();
      await Generation.updateOne(
        { jobId: req.params.jobId },
        { status: 'error', stage: 'cancelled', error: 'Cancelled by user' }
      );
      res.json({ message: 'Job cancelled' });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  });

  return router;
};
