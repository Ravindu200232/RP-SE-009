const mongoose = require('mongoose');

// Stores full conversation history per job - used for error context & AI memory
const messageSchema = new mongoose.Schema({
  jobId: { type: String, required: true, index: true },
  workspaceId: { type: String, index: true },
  threadId: { type: String, index: true },
  generationId: { type: String, index: true },
  role: { type: String, enum: ['system', 'user', 'assistant'], required: true },
  content: { type: String, required: true },
  agent: { type: String }, // planner | architect | developer | analyzer | fixer
  phase: { type: String }, // plan | architecture | code_service_X | analyze | fix
  metadata: { type: Object, default: {} }
}, { timestamps: true });

messageSchema.index({ jobId: 1, createdAt: 1 });

module.exports = mongoose.model('Message', messageSchema);
