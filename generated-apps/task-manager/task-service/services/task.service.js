import Task from "../models/task.js";

export async function listTasks(filter = {}) {
  return Task.find(filter);
}

export async function getTaskById(id) {
  return Task.findById(id);
}

export async function createTask(payload) {
  return Task.create(payload);
}

export async function updateTask(id, payload) {
  return Task.findByIdAndUpdate(id, payload, { new: true });
}

export async function deleteTask(id) {
  return Task.findByIdAndDelete(id);
}

export default {
  listTasks,
  getTaskById,
  createTask,
  updateTask,
  deleteTask
};