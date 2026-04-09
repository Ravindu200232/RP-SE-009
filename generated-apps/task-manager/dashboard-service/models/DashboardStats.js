import mongoose from "mongoose";

const schema = new mongoose.Schema({
  totalTasks: { type: Number, default: 0 },
  completedTasks: { type: Number, default: 0 }
}, { timestamps: true });

export default mongoose.model("DashboardStats", schema);