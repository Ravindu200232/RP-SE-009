const mongoose = require('mongoose');

const fileSchema = new mongoose.Schema({
  path: String,
  content: String,
  service: String
}, { _id: false });

const serviceSchema = new mongoose.Schema({
  name: String,
  port: Number,
  status: { type: String, enum: ['pending', 'generating', 'validating', 'installing', 'starting', 'running', 'error'], default: 'pending' },
  url: String,
  pid: Number,
  error: String,
  routes: [String]
}, { _id: false });

const stepSchema = new mongoose.Schema({
  name: String,
  stage: String,
  status: { type: String, enum: ['pending', 'running', 'success', 'warning', 'error'], default: 'pending' },
  summary: String,
  details: { type: Object, default: {} },
  startedAt: Date,
  completedAt: Date
}, { _id: false });

const logSchema = new mongoose.Schema({
  timestamp: { type: Date, default: Date.now },
  agent: String,
  message: String,
  type: { type: String, enum: ['info', 'success', 'error', 'warning', 'code', 'command', 'terminal', 'prompt', 'thinking'], default: 'info' }
}, { _id: false });

const generationSchema = new mongoose.Schema({
  jobId: { type: String, required: true, unique: true },
  workspaceId: { type: String, index: true },
  threadId: { type: String, index: true },
  mode: { type: String, enum: ['new', 'continue'], default: 'new' },
  task: { type: String, default: '' },
  model: { type: String, default: process.env.OLLAMA_MODEL || 'qwen2.5:14b' },
  timeoutSeconds: { type: Number, default: 900 },
  srs: { type: Object, required: true },
  status: {
    type: String,
    enum: ['pending', 'planning', 'architecting', 'generating', 'analyzing', 'fixing', 'installing', 'running', 'complete', 'error'],
    default: 'pending'
  },
  stage: { type: String, default: 'pending' },
  currentAgent: { type: String, default: '' },
  plan: { type: Object },
  architecture: { type: Object },
  generatedFiles: [fileSchema],
  services: [serviceSchema],
  gatewayUrl: { type: String },
  frontendUrl: { type: String },
  allUrls: { type: Object },
  appDir: { type: String },
  error: { type: String },
  errorSummary: { type: String, default: '' },
  logs: [logSchema],
  stepResults: [stepSchema],
  memorySummary: { type: Object, default: {} },
  artifactAudit: { type: Object, default: {} },
  progress: { type: Number, default: 0 }
}, { timestamps: true });

module.exports = mongoose.model('Generation', generationSchema);
