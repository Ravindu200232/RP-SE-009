import { checkHasAccount, checkAdmin } from "./authController.js";
import DashboardStats from "../models/DashboardStats.js";

export async function getStats(req, res) {
  try {
    if (!checkHasAccount(req)) return res.status(401).json({ message: "Please login" });
    if (!checkAdmin(req)) return res.status(403).json({ message: "Access denied" });

    const stats = await DashboardStats.findOne();
    
    // Fetch task count and completed tasks from the task-service
    const taskServiceUrl = process.env.TASK_SERVICE_URL || 'http://localhost:3002';
    const { data } = await axios.get(`${taskServiceUrl}/api/v1/tasks/stats`);
  
    const updatedStats = {
      totalTasks: data.totalTasks,
      completedTasks: data.completedTasks
    };
  
    if (!stats) {
      stats = new DashboardStats(updatedStats);
      await stats.save();
    } else {
      Object.assign(stats, updatedStats);
      await stats.save();
    }

    return res.json(stats);

  } catch (error) {
    console.error(error.message); // Log the error message for debugging purposes.
    return res.status(500).json({ message: "Internal server error" });
  }
}