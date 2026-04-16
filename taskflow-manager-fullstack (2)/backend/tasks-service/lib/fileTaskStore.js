const fs = require('fs/promises');
const path = require('path');
const { randomUUID } = require('crypto');
const { dataStoreFile } = require('../../shared/config');
const {
  createSampleTasks,
  normalizePriority,
  normalizeStatus,
} = require('../../shared/sampleData');

const baseState = {
  tasks: [],
  meta: {
    lastSeededAt: null,
  },
};

const ensureStore = async () => {
  await fs.mkdir(path.dirname(dataStoreFile), { recursive: true });

  try {
    await fs.access(dataStoreFile);
  } catch (error) {
    await fs.writeFile(dataStoreFile, JSON.stringify(baseState, null, 2), 'utf8');
  }
};

const readStore = async () => {
  await ensureStore();
  const raw = await fs.readFile(dataStoreFile, 'utf8');
  return raw ? JSON.parse(raw) : { ...baseState };
};

const writeStore = async (store) => {
  await ensureStore();
  await fs.writeFile(dataStoreFile, JSON.stringify(store, null, 2), 'utf8');
  return store;
};

const sortByPosition = (tasks) =>
  [...tasks].sort((left, right) => {
    if (left.position === right.position) {
      return new Date(left.createdAt).getTime() - new Date(right.createdAt).getTime();
    }

    return left.position - right.position;
  });

const reindexStatus = (tasks, status) => {
  sortByPosition(tasks)
    .filter((task) => task.status === status)
    .forEach((task, index) => {
      task.position = index;
    });
};

const filterTasks = (tasks, filters = {}) => {
  const search = filters.search ? String(filters.search).trim().toLowerCase() : '';
  return sortByPosition(tasks).filter((task) => {
    if (filters.status && task.status !== normalizeStatus(filters.status)) {
      return false;
    }

    if (filters.priority && task.priority !== normalizePriority(filters.priority)) {
      return false;
    }

    if (!search) {
      return true;
    }

    return [task.title, task.description || '']
      .join(' ')
      .toLowerCase()
      .includes(search);
  });
};

const getNextPosition = (tasks, status) => {
  const matchingTasks = tasks.filter((task) => task.status === status);
  if (matchingTasks.length === 0) {
    return 0;
  }

  return Math.max(...matchingTasks.map((task) => task.position || 0)) + 1;
};

const createTaskPayload = (input, tasks) => {
  const status = normalizeStatus(input.status);
  const now = new Date().toISOString();

  return {
    _id: randomUUID(),
    title: String(input.title || '').trim(),
    description: String(input.description || '').trim(),
    priority: normalizePriority(input.priority),
    status,
    deadline: input.deadline || null,
    position:
      typeof input.position === 'number' && Number.isFinite(input.position)
        ? input.position
        : getNextPosition(tasks, status),
    createdAt: now,
    updatedAt: now,
  };
};

const updateTaskPayload = (task, updates, tasks) => {
  const nextStatus = normalizeStatus(updates.status || task.status);
  const statusChanged = nextStatus !== task.status;

  task.title = updates.title !== undefined ? String(updates.title).trim() : task.title;
  task.description =
    updates.description !== undefined ? String(updates.description).trim() : task.description;
  task.priority =
    updates.priority !== undefined ? normalizePriority(updates.priority) : task.priority;
  task.deadline = updates.deadline !== undefined ? updates.deadline : task.deadline;

  if (statusChanged) {
    task.status = nextStatus;
    task.position =
      typeof updates.position === 'number' && Number.isFinite(updates.position)
        ? updates.position
        : getNextPosition(tasks, nextStatus);
  } else if (typeof updates.position === 'number' && Number.isFinite(updates.position)) {
    task.position = updates.position;
  }

  task.updatedAt = new Date().toISOString();
  return { task, previousStatus: statusChanged ? task.status : nextStatus };
};

const listTasks = async (filters = {}) => {
  const store = await readStore();
  return filterTasks(store.tasks, filters);
};

const getTaskById = async (id) => {
  const store = await readStore();
  return store.tasks.find((task) => task._id === id) || null;
};

const createTask = async (input) => {
  const store = await readStore();
  const task = createTaskPayload(input, store.tasks);
  store.tasks.push(task);
  reindexStatus(store.tasks, task.status);
  await writeStore(store);
  return task;
};

const updateTask = async (id, updates) => {
  const store = await readStore();
  const task = store.tasks.find((item) => item._id === id);

  if (!task) {
    return null;
  }

  const oldStatus = task.status;
  updateTaskPayload(task, updates, store.tasks);
  reindexStatus(store.tasks, oldStatus);
  reindexStatus(store.tasks, task.status);
  await writeStore(store);
  return task;
};

const deleteTask = async (id) => {
  const store = await readStore();
  const index = store.tasks.findIndex((task) => task._id === id);

  if (index === -1) {
    return null;
  }

  const [removedTask] = store.tasks.splice(index, 1);
  reindexStatus(store.tasks, removedTask.status);
  await writeStore(store);
  return removedTask;
};

const seedTasks = async ({ replace = false } = {}) => {
  const store = await readStore();

  if (!replace && store.tasks.length > 0) {
    return store.tasks;
  }

  const seededTasks = createSampleTasks().map((task, index) => ({
    ...task,
    _id: randomUUID(),
    position: index,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }));

  store.tasks = seededTasks;
  store.meta.lastSeededAt = new Date().toISOString();
  await writeStore(store);
  return seededTasks;
};

module.exports = {
  createTask,
  deleteTask,
  ensureStore,
  getTaskById,
  listTasks,
  readStore,
  seedTasks,
  updateTask,
};
