import User from "../models/user.js";

export async function listUsers(filter = {}) {
  return User.find(filter);
}

export async function getUserById(id) {
  return User.findById(id);
}

export async function createUser(payload) {
  return User.create(payload);
}

export async function updateUser(id, payload) {
  return User.findByIdAndUpdate(id, payload, { new: true });
}

export async function deleteUser(id) {
  return User.findByIdAndDelete(id);
}

export default {
  listUsers,
  getUserById,
  createUser,
  updateUser,
  deleteUser
};