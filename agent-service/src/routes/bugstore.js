const express = require('express');
const router = express.Router();
const BugStore = require('../models/BugStore');
const bugStoreService = require('../services/bugStoreService');

/**
 * GET /api/bugs
 * List all known bugs, ordered by severity + frequency.
 */
router.get('/', async (req, res) => {
  try {
    const { category, severity, limit = 50 } = req.query;
    const filter = {};
    if (category) filter.category = category;
    if (severity) filter.severity = severity;

    const bugs = await BugStore.find(filter)
      .sort({ severity: -1, occurrences: -1 })
      .limit(parseInt(limit));

    res.json({
      total: bugs.length,
      bugs: bugs.map(b => ({
        patternId: b.patternId,
        name: b.name,
        category: b.category,
        severity: b.severity,
        description: b.description,
        preventionRule: b.preventionRule,
        badCode: b.badCode,
        goodCode: b.goodCode,
        occurrences: b.occurrences,
        lastSeenJobId: b.lastSeenJobId,
        autoFixable: b.autoFixable
      }))
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /api/bugs/stats
 * Summary statistics of the bug store.
 */
router.get('/stats', async (req, res) => {
  try {
    const [total, bySeverity, byCategory, topBugs] = await Promise.all([
      BugStore.countDocuments(),
      BugStore.aggregate([{ $group: { _id: '$severity', count: { $sum: 1 }, totalOccurrences: { $sum: '$occurrences' } } }]),
      BugStore.aggregate([{ $group: { _id: '$category', count: { $sum: 1 } } }]),
      BugStore.find().sort({ occurrences: -1 }).limit(5).select('name occurrences severity category')
    ]);

    res.json({ total, bySeverity, byCategory, topBugs });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * POST /api/bugs/seed
 * Re-seed the bug store with base patterns.
 */
router.post('/seed', async (req, res) => {
  try {
    await BugStore.deleteMany({});
    await bugStoreService.seed();
    const count = await BugStore.countDocuments();
    res.json({ message: `Bug store seeded with ${count} patterns` });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

module.exports = router;
