const mongoose = require('mongoose');

const workspaceSchema = new mongoose.Schema({
  workspaceId: { type: String, required: true, unique: true, index: true },
  slug: { type: String, required: true, unique: true, index: true },
  name: { type: String, required: true },
  description: { type: String, default: '' },
  stack: { type: String, default: 'MERN Stack Microservices' },
  appDir: { type: String, required: true },
  memoryDir: { type: String, required: true },
  latestPlan: { type: Object, default: null },
  latestGenerationId: { type: String, default: '' },
  latestThreadId: { type: String, default: '' },
  lastRunSettings: { type: Object, default: {} },
  lastError: { type: String, default: '' },
  lastErrorSummary: { type: String, default: '' },
  memorySummary: { type: Object, default: {} },
  serviceNames: { type: [String], default: [] },
  status: { type: String, default: 'idle' }
}, { timestamps: true });

workspaceSchema.index({ updatedAt: -1 });

module.exports = mongoose.model('Workspace', workspaceSchema);
