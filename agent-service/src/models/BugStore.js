const mongoose = require('mongoose');

/**
 * BugStore — Persistent bug knowledge base.
 * Every bug found during any generation is stored here.
 * Before next generation, top bugs are injected into prompts so they NEVER happen again.
 */
const bugStoreSchema = new mongoose.Schema({
  // Unique identifier for this bug pattern
  patternId: { type: String, required: true, unique: true },

  // Short name for display
  name: { type: String, required: true },

  // Category for grouping
  category: {
    type: String,
    enum: [
      'missing-await',        // Forgot await on async
      'missing-middleware',   // Missing express.json, cors, etc.
      'wrong-import',         // Wrong require/import path
      'missing-error-handler',// No try/catch
      'env-not-used',         // Hardcoded value instead of process.env
      'cors-error',           // CORS not configured correctly
      'model-error',          // Mongoose model issue
      'route-not-mounted',    // Route file not used in index.js
      'port-issue',           // Port hardcoded or wrong
      'mongodb-issue',        // MongoDB connection issue
      'missing-export',       // module.exports missing
      'jwt-error',            // JWT handling wrong
      'syntax-error',         // JS syntax error
      'dependency-missing',   // npm package not in package.json
      'start-script-missing', // No "start" in package.json scripts
      'async-error',          // General async/promise error
      'validation-error',     // Input validation missing
      'frontend-api-error',   // Frontend calling wrong API URL
      'nextjs-error',         // Next.js specific error
      'other'
    ],
    default: 'other'
  },

  // Human-readable description
  description: { type: String, required: true },

  // Example of bad code that causes this bug
  badCode: { type: String },

  // The correct code that fixes this bug
  goodCode: { type: String },

  // Rule injected into developer prompts to prevent this bug
  preventionRule: { type: String, required: true },

  // Which service type this affects
  affectsServices: [{ type: String }], // 'express', 'nextjs', 'both', 'gateway'

  // How many times this bug has been seen across all generations
  occurrences: { type: Number, default: 1 },

  // Last seen in which job
  lastSeenJobId: { type: String },

  // Was it auto-fixed successfully?
  autoFixable: { type: Boolean, default: true },

  // Severity: how badly does this break the app?
  severity: { type: String, enum: ['critical', 'high', 'medium', 'low'], default: 'high' }
}, { timestamps: true });

bugStoreSchema.index({ occurrences: -1 });
bugStoreSchema.index({ category: 1 });
bugStoreSchema.index({ severity: 1 });

module.exports = mongoose.model('BugStore', bugStoreSchema);
