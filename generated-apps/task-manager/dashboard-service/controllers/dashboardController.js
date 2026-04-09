import { checkHasAccount, checkAdmin } from "./authController.js";
import DashboardStats from "../models/DashboardStats.js";

export async function getStats(req, res) {
  try {
    if (!checkHasAccount(req)) return res.status(401).json({ message: "Please login" });
    
    const stats = await DashboardStats.findOne();
    if (!stats) {
      return res.status(404).json({ message: "No dashboard statistics found." });
    }
    
    // Fetch task data from task-service
    const taskServiceUrl = process.env.TASK_SERVICE_URL || "http://localhost:3002";
    const response = await axios.get(`${taskServiceUrl}/api/v1/tasks`);
    const tasks = response.data;
    
    // Update totalTasks and completedTasks in DashboardStats model
    stats.totalTasks = tasks.length;
    stats.completedTasks = tasks.filter(task => task.status === 'completed').length;

    await stats.save();
    
    return res.json(stats);
  } catch (error) {
    console.error(error.message);
    return res.status(500).json({ message: "Internal server error" });
  }
}