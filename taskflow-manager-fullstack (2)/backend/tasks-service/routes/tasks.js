const express = require('express');
const router = express.Router();
const taskRepository = require('../lib/taskRepository');

// GET all tasks
router.get('/', async (req, res) => {
  try {
    const { status, priority, search } = req.query;
    const tasks = await taskRepository.listTasks({ status, priority, search });
    res.json({ success: true, data: tasks });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// GET task by ID
router.get('/:id', async (req, res) => {
  try {
    const task = await taskRepository.getTaskById(req.params.id);
    if (!task) {
      return res.status(404).json({ success: false, error: 'Task not found' });
    }
    res.json({ success: true, data: task });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// POST create new task
router.post('/', async (req, res) => {
  try {
    if (!req.body?.title) {
      return res.status(400).json({ success: false, error: 'Task title is required' });
    }

    const task = await taskRepository.createTask(req.body);
    res.status(201).json({ success: true, data: task });
  } catch (error) {
    res.status(400).json({ success: false, error: error.message });
  }
});

// POST seed sample data
router.post('/seed', async (req, res) => {
  try {
    const replace = Boolean(req.body?.replace);
    const tasks = await taskRepository.seedTasks({ replace });
    res.status(201).json({
      success: true,
      data: tasks,
      meta: {
        replaced: replace,
        storage: taskRepository.getStorageState(),
      },
    });
  } catch (error) {
    res.status(400).json({ success: false, error: error.message });
  }
});

// PUT update task
router.put('/:id', async (req, res) => {
  try {
    const updatedTask = await taskRepository.updateTask(req.params.id, req.body || {});
    if (!updatedTask) {
      return res.status(404).json({ success: false, error: 'Task not found' });
    }

    res.json({ success: true, data: updatedTask });
  } catch (error) {
    res.status(400).json({ success: false, error: error.message });
  }
});

// DELETE task
router.delete('/:id', async (req, res) => {
  try {
    const deletedTask = await taskRepository.deleteTask(req.params.id);
    if (!deletedTask) {
      return res.status(404).json({ success: false, error: 'Task not found' });
    }

    res.json({ success: true, data: deletedTask });
  } catch (error) {
    res.status(400).json({ success: false, error: error.message });
  }
});

module.exports = router;
