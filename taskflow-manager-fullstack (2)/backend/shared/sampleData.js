const BOARD_COLUMNS = [
  { key: 'todo', name: 'To Do' },
  { key: 'in-progress', name: 'In Progress' },
  { key: 'done', name: 'Done' },
];

const SAMPLE_TASKS = [
  {
    title: 'Design onboarding checklist',
    description: 'Document the first-run steps for new users and highlight the key setup tasks.',
    priority: 'high',
    status: 'todo',
    deadline: '2026-04-18T09:00:00.000Z',
  },
  {
    title: 'Connect kanban filters to API',
    description: 'Make the board search and status filters use live backend data instead of only local state.',
    priority: 'medium',
    status: 'in-progress',
    deadline: '2026-04-19T12:00:00.000Z',
  },
  {
    title: 'Prepare sprint handoff notes',
    description: 'Summarize active work, blockers, and validation results for the Agent 2 developer handoff.',
    priority: 'low',
    status: 'done',
    deadline: '2026-04-17T16:00:00.000Z',
  },
];

const normalizeStatus = (value) => {
  if (!value) {
    return 'todo';
  }

  const normalized = String(value).trim().toLowerCase();
  if (normalized === 'inprogress' || normalized === 'in_progress') {
    return 'in-progress';
  }

  if (normalized === 'todo' || normalized === 'in-progress' || normalized === 'done') {
    return normalized;
  }

  return 'todo';
};

const normalizePriority = (value) => {
  if (!value) {
    return 'medium';
  }

  const normalized = String(value).trim().toLowerCase();
  return ['low', 'medium', 'high'].includes(normalized) ? normalized : 'medium';
};

const createSampleTasks = () =>
  SAMPLE_TASKS.map((task, index) => ({
    ...task,
    status: normalizeStatus(task.status),
    priority: normalizePriority(task.priority),
    position: index,
  }));

const buildBoardFromTasks = (tasks) => ({
  name: 'TaskFlow Board',
  columns: BOARD_COLUMNS.map((column) => ({
    ...column,
    tasks: tasks
      .filter((task) => normalizeStatus(task.status) === column.key)
      .sort((left, right) => left.position - right.position)
      .map((task) => task),
  })),
});

module.exports = {
  BOARD_COLUMNS,
  buildBoardFromTasks,
  createSampleTasks,
  normalizePriority,
  normalizeStatus,
};
