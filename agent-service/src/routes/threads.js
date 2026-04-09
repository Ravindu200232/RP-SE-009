const express = require('express');
const { v4: uuidv4 } = require('uuid');

const Thread = require('../models/Thread');
const Message = require('../models/Message');
const Generation = require('../models/Generation');
const WorkflowOrchestrator = require('../services/workflowOrchestrator');

module.exports = (io) => {
  const router = express.Router();
  const orchestrator = new WorkflowOrchestrator(io);

  router.get('/:threadId/messages', async (req, res) => {
    try {
      const messages = await Message.find({ threadId: req.params.threadId }).sort({ createdAt: 1 }).lean();
      res.json({
        threadId: req.params.threadId,
        totalMessages: messages.length,
        messages: messages.map((message) => ({
          role: message.role,
          agent: message.agent,
          phase: message.phase,
          content: message.content,
          createdAt: message.createdAt
        }))
      });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  });

  router.post('/:threadId/run', async (req, res) => {
    try {
      const thread = await Thread.findOne({ threadId: req.params.threadId });
      if (!thread) {
        return res.status(404).json({ error: 'Thread not found' });
      }

      const task = req.body?.task || '';
      const model = req.body?.model || process.env.OLLAMA_MODEL || 'qwen2.5:14b';
      const timeoutSeconds = Math.max(60, Number(req.body?.timeoutSeconds) || 900);
      if (!task) {
        return res.status(400).json({ error: 'Task is required' });
      }

      const jobId = uuidv4();
      await Generation.create({
        jobId,
        srs: {},
        status: 'pending',
        stage: 'pending',
        workspaceId: thread.workspaceId,
        threadId: thread.threadId,
        task,
        mode: 'continue',
        model,
        timeoutSeconds
      });

      res.status(202).json({
        jobId,
        workspaceId: thread.workspaceId,
        threadId: thread.threadId,
        task,
        model,
        timeoutSeconds,
        statusUrl: `/api/generate/${jobId}`
      });

      orchestrator.run(jobId, {
        workspaceId: thread.workspaceId,
        threadId: thread.threadId,
        task,
        mode: 'continue',
        model,
        timeoutSeconds
      }).catch((error) => {
        console.error(`[ThreadRun] Job ${jobId} failed:`, error.message);
      });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  });

  return router;
};
