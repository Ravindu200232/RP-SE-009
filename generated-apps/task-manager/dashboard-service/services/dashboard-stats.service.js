import DashboardStats from "../models/dashboardStats.js";

export async function listDashboardStats(filter = {}) {
  return DashboardStats.find(filter);
}

export async function getDashboardStatsById(id) {
  return DashboardStats.findById(id);
}

export async function createDashboardStats(payload) {
  return DashboardStats.create(payload);
}

export async function updateDashboardStats(id, payload) {
  return DashboardStats.findByIdAndUpdate(id, payload, { new: true });
}

export async function deleteDashboardStats(id) {
  return DashboardStats.findByIdAndDelete(id);
}

export default {
  listDashboardStats,
  getDashboardStatsById,
  createDashboardStats,
  updateDashboardStats,
  deleteDashboardStats
};