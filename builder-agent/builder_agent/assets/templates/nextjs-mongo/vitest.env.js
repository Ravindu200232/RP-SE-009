/** Environment for every suite, imported before the code under test (vitest.config.js, setupFiles). */
process.env.TEST_MONGODB_URI ??= 'mongodb://127.0.0.1:27017/__APP_DB___test';
process.env.MONGODB_URI = process.env.TEST_MONGODB_URI;
process.env.SESSION_SECRET ??= 'test-session-secret-not-a-live-value-0123456789';
