const mongoose = require('mongoose');
const Task = require('../models/Task');
const { mongoUri } = require('../../shared/config');
const {
  createSampleTasks,
  normalizePriority,
  normalizeStatus,
} = require('../../shared/sampleData');
const fileTaskStore = require('./fileTaskStore');

const storageState = {
  connected: false,
  error: null,
  mode: 'file',
};

const toNumber = (value) => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : null;
};

const applyFilters = (filters = {}) => {
  const query = {};

  if (filters.status) {
    query.status = normalizeStatus(filters.status);
  }

  if (filters.priority) {
    query.priority = normalizePriority(filters.priority);
  }

  if (filters.search) {
    query.$or = [
      { title: { $regex: filters.search, $options: 'i' } },
      { description: { $regex: filters.search, $options: 'i' } },
    ];
  }

  return query;
};

const reindexMongoStatus = async (status) => {
  const tasks = await Task.find({ status }).sort({ position: 1, createdAt: 1 });

  if (tasks.length === 0) {
    return;
  }

  await Task.bulkWrite(
    tasks.map((task, index) => ({
      updateOne: {
        filter: { _id: task._id },
        update: { position: index },
      },
    }))
  );
};

const getNextMongoPosition = async (status) => {
  const highestPositionTask = await Task.findOne({ status }).sort({ position: -1, createdAt: -1 });
  return highestPositionTask ? highestPositionTask.position + 1 : 0;
};

const initialize = async () => {
  try {
    await mongoose.connect(mongoUri, {
      serverSelectionTimeoutMS: 3000,
    });

    storageState.connected = true;
    storageState.mode = 'mongo';
    storageState.error = null;
  } catch (error) {
    storageState.connected = false;
    storageState.mode = 'file';
    storageState.error = error.message;
    await fileTaskStore.ensureStore();
  }

  return { ...storageState };
};

const getStorageState = () => ({ ...storageState });

const listTasks = async (filters = {}) => {
  if (storageState.mode === 'mongo') {
    return Task.find(applyFilters(filters)).sort({ position: 1, createdAt: -1 }).lean();
  }

  return fileTaskStore.listTasks(filters);
};

const getTaskById = async (id) => {
  if (storageState.mode === 'mongo') {
    if (!mongoose.Types.ObjectId.isValid(id)) {
      return null;
    }

    return Task.findById(id).lean();
  }

  return fileTaskStore.getTaskById(id);
};

const createTask = async (input) => {
  if (storageState.mode === 'mongo') {
    const status = normalizeStatus(input.status);
    const task = await Task.create({
      title: String(input.title || '').trim(),
      description: String(input.description || '').trim(),
      priority: normalizePriority(input.priority),
      status,
      deadline: input.deadline || null,
      position:
        toNumber(input.position) !== null ? toNumber(input.position) : await getNextMongoPosition(status),
    });

    await reindexMongoStatus(status);
    return task.toObject();
  }

  return fileTaskStore.createTask(input);
};

const updateTask = async (id, updates) => {
  if (storageState.mode === 'mongo') {
    if (!mongoose.Types.ObjectId.isValid(id)) {
      return null;
    }

    const task = await Task.findById(id);
    if (!task) {
      return null;
    }

    const oldStatus = task.status;
    const nextStatus = updates.status !== undefined ? normalizeStatus(updates.status) : task.status;
    const statusChanged = oldStatus !== nextStatus;

    if (updates.title !== undefined) {
      task.title = String(updates.title).trim();
    }

    if (updates.description !== undefined) {
      task.description = String(updates.description).trim();
    }

    if (updates.priority !== undefined) {
      task.priority = normalizePriority(updates.priority);
    }

    if (updates.deadline !== undefined) {
      task.deadline = updates.deadline;
    }

    if (statusChanged) {
      task.status = nextStatus;
      task.position =
        toNumber(updates.position) !== null
          ? toNumber(updates.position)
          : await getNextMongoPosition(nextStatus);
    } else if (toNumber(updates.position) !== null) {
      task.position = toNumber(updates.position);
    }

    await task.save();
    await reindexMongoStatus(oldStatus);
    await reindexMongoStatus(task.status);
    return task.toObject();
  }

  return fileTaskStore.updateTask(id, updates);
};

const deleteTask = async (id) => {
  if (storageState.mode === 'mongo') {
    if (!mongoose.Types.ObjectId.isValid(id)) {
      return null;
    }

    const deletedTask = await Task.findByIdAndDelete(id).lean();
    if (!deletedTask) {
      return null;
    }

    await reindexMongoStatus(deletedTask.status);
    return deletedTask;
  }

  return fileTaskStore.deleteTask(id);
};

const seedTasks = async ({ replace = false } = {}) => {
  if (storageState.mode === 'mongo') {
    const existingCount = await Task.countDocuments();

    if (existingCount > 0 && !replace) {
      return Task.find().sort({ position: 1, createdAt: -1 }).lean();
    }

    if (replace) {
      await Task.deleteMany({});
    }

    const samples = createSampleTasks();
    const createdTasks = [];

    for (const sample of samples) {
      const created = await Task.create({
        ...sample,
        position: await getNextMongoPosition(sample.status),
      });
      createdTasks.push(created.toObject());
    }

    await reindexMongoStatus('todo');
    await reindexMongoStatus('in-progress');
    await reindexMongoStatus('done');
    return createdTasks;
  }

  return fileTaskStore.seedTasks({ replace });
};

module.exports = {
  createTask,
  deleteTask,
  getStorageState,
  getTaskById,
  initialize,
  listTasks,
  seedTasks,
  updateTask,
};
