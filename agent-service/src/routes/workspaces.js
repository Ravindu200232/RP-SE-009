const express = require('express');
const Workspace = require('../models/Workspace');
const Thread = require('../models/Thread');
const workspaceService = require('../services/workspaceService');
const memoryStore = require('../services/memoryStore');

const router = express.Router();

router.get('/', async (req, res) => {
  try {
    const workspaces = await workspaceService.listWorkspaces();
    res.json({
      workspaces: workspaces.map((workspace) => ({
        workspaceId: workspace.workspaceId,
        slug: workspace.slug,
        name: workspace.name,
        description: workspace.description,
        status: workspace.status,
        latestThreadId: workspace.latestThreadId,
        latestGenerationId: workspace.latestGenerationId,
        lastRunSettings: workspace.lastRunSettings || {},
        lastErrorSummary: workspace.lastErrorSummary || '',
        memorySummary: workspace.memorySummary || {},
        serviceNames: workspace.serviceNames || [],
        updatedAt: workspace.updatedAt,
        createdAt: workspace.createdAt
      }))
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/:workspaceId', async (req, res) => {
  try {
    const workspace = await Workspace.findOne({ workspaceId: req.params.workspaceId }).lean();
    if (!workspace) {
      return res.status(404).json({ error: 'Workspace not found' });
    }

    const threads = await Thread.find({ workspaceId: workspace.workspaceId }).sort({ updatedAt: -1 }).lean();

    res.json({
      workspace,
      threads: threads.map((thread) => ({
        threadId: thread.threadId,
        title: thread.title,
        mode: thread.mode,
        latestTask: thread.latestTask,
        status: thread.status,
        messageCount: thread.messageCount,
        updatedAt: thread.updatedAt,
        createdAt: thread.createdAt
      }))
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

router.get('/:workspaceId/memory', async (req, res) => {
  try {
    const workspace = await Workspace.findOne({ workspaceId: req.params.workspaceId });
    if (!workspace) {
      return res.status(404).json({ error: 'Workspace not found' });
    }

    const memory = await memoryStore.read(workspace.appDir);
    res.json({
      workspaceId: workspace.workspaceId,
      summary: memory.summary,
      files: memory.files
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
