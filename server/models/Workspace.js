const mongoose = require('mongoose');

const MessageSchema = new mongoose.Schema({
    role: { type: String, required: true },
    content: { type: String, required: true }
}, { _id: false });

const WorkspaceSchema = new mongoose.Schema({
    messages: { type: [MessageSchema], default: [] },
    fileData: { type: mongoose.Schema.Types.Mixed, default: {} },
    backendData: { type: mongoose.Schema.Types.Mixed, default: {} },
    projectTitle: { type: String, default: '' },
    createdAt: { type: Date, default: Date.now },
    updatedAt: { type: Date, default: Date.now }
});

module.exports = mongoose.model('Workspace', WorkspaceSchema);
