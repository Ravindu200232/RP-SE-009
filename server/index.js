require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const workspaceRoutes = require('./routes/workspace');

const app = express();
const PORT = process.env.PORT || 5000;
const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/ai-website-builder';

// Middleware
app.use(cors({ origin: true, credentials: true }));
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Routes
app.use('/api/workspaces', workspaceRoutes);

// Health check
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        mongodb: mongoose.connection.readyState === 1 ? 'connected' : 'disconnected',
        timestamp: new Date().toISOString()
    });
});

// Connect to MongoDB and start server
mongoose.connect(MONGODB_URI)
    .then(() => {
        console.log('✅ Connected to MongoDB at', MONGODB_URI);
        app.listen(PORT, () => {
            console.log(`🚀 AI Website Builder server running on http://localhost:${PORT}`);
        });
    })
    .catch((err) => {
        console.error('❌ MongoDB connection error:', err.message);
        console.error('Make sure MongoDB is running on port 27017');
        process.exit(1);
    });
