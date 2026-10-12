import pg from 'pg';

/** The one thing every suite that touches Postgres directly needs, written once. */
const TEST_DATABASE_URL = process.env.TEST_DATABASE_URL ?? 'postgresql://postgres:postgres@127.0.0.1:54322/postgres';

function assertLocalTestServer(url) {
  const hostname = new URL(url.replace(/^postgres(ql)?:/, 'http:')).hostname;
  if (!['127.0.0.1', 'localhost', '::1'].includes(hostname)) {
    throw new Error(
      `Refusing to run tests against "${hostname}": a test database must be local (127.0.0.1), `
      + "never the project's real Supabase project. Run `supabase start` and leave "
      + 'TEST_DATABASE_URL unset.',
    );
  }
}

let pool;

/** One connection pool per process, to the local stack only. */
export function testDb() {
  assertLocalTestServer(TEST_DATABASE_URL);
  pool ??= new pg.Pool({ connectionString: TEST_DATABASE_URL });
  return pool;
}

/** Truncate every table in the `public` schema. */
export async function clearTables() {
  const db = testDb();
  const { rows } = await db.query("select tablename from pg_tables where schemaname = 'public'");
  if (!rows.length) return;
  const names = rows.map((row) => `"${row.tablename}"`).join(', ');
  await db.query(`truncate table ${names} restart identity cascade`);
}

/** Close in `afterAll`, or the runner hangs on an open handle. */
export async function closeTestDb() {
  await pool?.end();
  pool = undefined;
}
