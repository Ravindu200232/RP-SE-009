import express from "express";
import { getTasks, createTask } from "../controllers/taskController.js";

const router = express.Router();

router.get("/api/v1/tasks", getTasks);
router.post("/api/v1/tasks", createTask);

export default router;