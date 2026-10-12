/** Environment for every suite, imported before the code under test (vitest.config.js, setupFiles). */
process.env.SUPABASE_URL = 'http://127.0.0.1:54321';
process.env.SUPABASE_ANON_KEY = process.env.TEST_SUPABASE_ANON_KEY ?? '';
process.env.SUPABASE_SERVICE_ROLE_KEY = process.env.TEST_SUPABASE_SERVICE_ROLE_KEY ?? '';
process.env.SESSION_SECRET ??= 'test-session-secret-not-a-live-value-0123456789';
