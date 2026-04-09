import { checkHasAccount, checkAdmin } from "./authController.js";
import Task from "../models/Task.js";

export async function getTasks(req, res) {
  try {
    if (!checkHasAccount(req)) {
      return res.status(401).json({ message: "Please login" });
    }

    const tasks = await Task.find();
    return res.json(tasks);
  } catch (error) {
    return res.status(500).json({ message: "Internal server error" });
  }
}

export async function createTask(req, res) {
  try {
    if (!checkAdmin(req)) {
      return res.status(403).json({ message: "Access denied" });
    }

    const { title } = req.body;

    const task = new Task({
      title,
      completed: false
    });

    await task.save();
    return res.json(task);
  } catch (error) {
    return res.status(500).json({ message: "Internal server error" });
  }
}
