const express = require('express');
const router = express.Router();
const Workspace = require('../models/Workspace');

function sanitizeMessages(messages) {
    if (!Array.isArray(messages)) {
        return [];
    }

    return messages
        .map((message) => ({
            role: typeof message?.role === 'string' ? message.role.trim() : '',
            content: typeof message?.content === 'string' ? message.content.trim() : '',
        }))
        .filter((message) => message.role && message.content);
}

// POST / - Create new workspace
router.post('/', async (req, res) => {
    try {
        const { messages } = req.body;
        const workspace = new Workspace({ messages: sanitizeMessages(messages) });
        await workspace.save();
        res.status(201).json({
            workspaceId: workspace._id.toString(),
            workspace
        });
    } catch (err) {
        console.error('Create workspace error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// GET /:id - Get workspace by ID
router.get('/:id', async (req, res) => {
    try {
        const workspace = await Workspace.findById(req.params.id);
        if (!workspace) {
            return res.status(404).json({ error: 'Workspace not found' });
        }
        res.json(workspace);
    } catch (err) {
        console.error('Get workspace error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// PUT /:id/messages - Update chat messages
router.put('/:id/messages', async (req, res) => {
    try {
        const { messages } = req.body;
        const sanitizedMessages = sanitizeMessages(messages);
        const workspace = await Workspace.findByIdAndUpdate(
            req.params.id,
            { $set: { messages: sanitizedMessages, updatedAt: new Date() } },
            { new: true, runValidators: true }
        );
        if (!workspace) {
            return res.status(404).json({ error: 'Workspace not found' });
        }
        res.json(workspace);
    } catch (err) {
        console.error('Update messages error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// PUT /:id/files - Update generated files (frontend + optional backend)
router.put('/:id/files', async (req, res) => {
    try {
        const { files, backendFiles, projectTitle } = req.body;
        const update = { fileData: files, projectTitle: projectTitle || '', updatedAt: new Date() };
        if (backendFiles && Object.keys(backendFiles).length > 0) {
            update.backendData = backendFiles;
        }
        const workspace = await Workspace.findByIdAndUpdate(
            req.params.id,
            { $set: update },
            { new: true }
        );
        if (!workspace) {
            return res.status(404).json({ error: 'Workspace not found' });
        }
        res.json(workspace);
    } catch (err) {
        console.error('Update files error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

module.exports = router;
