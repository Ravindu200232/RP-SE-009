const express = require('express');
const router = express.Router();
const Generation = require('../models/Generation');
const Message = require('../models/Message');

/**
 * GET /api/history
 * List all generation jobs (most recent first).
 */
router.get('/', async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 20;
    const skip = (page - 1) * limit;

    const [jobs, total] = await Promise.all([
      Generation.find()
        .select('-generatedFiles -logs')
        .sort({ createdAt: -1 })
        .skip(skip)
        .limit(limit),
      Generation.countDocuments()
    ]);

    res.json({
      jobs: jobs.map(j => ({
        jobId: j.jobId,
        projectName: j.plan?.projectName || 'Unknown',
        status: j.status,
        progress: j.progress,
        servicesCount: j.services?.length || 0,
        gatewayUrl: j.gatewayUrl,
        createdAt: j.createdAt
      })),
      pagination: { page, limit, total, pages: Math.ceil(total / limit) }
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /api/history/:jobId/messages
 * Get full conversation history (prompts + AI outputs) for a job.
 * This is the "chat history" used for error fixing context.
 */
router.get('/:jobId/messages', async (req, res) => {
  try {
    const messages = await Message.find({ jobId: req.params.jobId })
      .sort({ createdAt: 1 })
      .lean();

    res.json({
      jobId: req.params.jobId,
      totalMessages: messages.length,
      messages: messages.map(m => ({
        role: m.role,
        agent: m.agent,
        phase: m.phase,
        content: m.content.slice(0, 2000) + (m.content.length > 2000 ? '...[truncated]' : ''),
        timestamp: m.createdAt
      }))
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /api/history/:jobId/logs
 * Get execution logs for a job.
 */
router.get('/:jobId/logs', async (req, res) => {
  try {
    const job = await Generation.findOne({ jobId: req.params.jobId })
      .select('logs status progress currentAgent');

    if (!job) return res.status(404).json({ error: 'Job not found' });

    res.json({
      jobId: req.params.jobId,
      status: job.status,
      progress: job.progress,
      currentAgent: job.currentAgent,
      logs: job.logs
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * DELETE /api/history/:jobId
 * Delete a generation job and its messages.
 */
router.delete('/:jobId', async (req, res) => {
  try {
    await Promise.all([
      Generation.deleteOne({ jobId: req.params.jobId }),
      Message.deleteMany({ jobId: req.params.jobId })
    ]);
    res.json({ message: 'Deleted successfully' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
