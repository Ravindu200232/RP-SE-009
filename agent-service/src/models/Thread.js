const mongoose = require('mongoose');

const threadSchema = new mongoose.Schema({
  threadId: { type: String, required: true, unique: true, index: true },
  workspaceId: { type: String, required: true, index: true },
  title: { type: String, required: true },
  mode: { type: String, enum: ['new', 'continue'], default: 'new' },
  latestTask: { type: String, default: '' },
  lastGenerationId: { type: String, default: '' },
  status: { type: String, default: 'idle' },
  messageCount: { type: Number, default: 0 }
}, { timestamps: true });

threadSchema.index({ workspaceId: 1, updatedAt: -1 });

module.exports = mongoose.model('Thread', threadSchema);
