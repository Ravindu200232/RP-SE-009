const express = require('express');
const router = express.Router();
const { buildBoardFromTasks, normalizeStatus } = require('../../shared/sampleData');
const { serviceUrls } = require('../../shared/config');

const fetchTasks = async () => {
  const response = await fetch(`${serviceUrls.tasks}/api/tasks`);
  const payload = await response.json();

  if (!response.ok || !payload.success) {
    throw new Error(payload.error || 'Unable to load tasks from tasks-service');
  }

  return payload.data;
};

// GET board state
router.get('/', async (req, res) => {
  try {
    const tasks = await fetchTasks();
    const board = buildBoardFromTasks(tasks);
    res.json({ success: true, data: board });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});

// PATCH update board (move tasks between columns)
router.patch('/move-task', async (req, res) => {
  try {
    const { taskId, toColumn, newPosition } = req.body || {};
    if (!taskId || !toColumn) {
      return res.status(400).json({ success: false, error: 'taskId and toColumn are required' });
    }

    const response = await fetch(`${serviceUrls.tasks}/api/tasks/${taskId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        status: normalizeStatus(toColumn),
        position: typeof newPosition === 'number' ? newPosition : undefined,
      }),
    });

    const payload = await response.json();
    if (!response.ok || !payload.success) {
      return res.status(response.status || 400).json(payload);
    }

    const tasks = await fetchTasks();
    res.json({ success: true, data: buildBoardFromTasks(tasks) });
  } catch (error) {
    res.status(400).json({ success: false, error: error.message });
  }
});

module.exports = router;
