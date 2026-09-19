import mongoose from 'mongoose';

/**
 * The three things every suite that touches MongoDB needs, written once.
 *
 * Copied into each test file instead, they drift: one file forgets to clear
 * between tests, another connects per test and exhausts the pool, and the
 * failures read as product bugs in whichever suite happens to run second.
 */

/** Connect once per process. `readyState` 1 is connected, 0 is disconnected. */
export async function connectTestDb(uri = process.env.MONGODB_URI ?? 'mongodb://127.0.0.1:27017/app_test') {
  if (mongoose.connection.readyState === 1) return mongoose.connection;
  await mongoose.connect(uri);
  return mongoose.connection;
}

/**
 * Empty every collection.
 *
 * Call it in `beforeEach`, not `beforeAll`: a document left behind changes the
 * next test's result, and that failure reads as a defect in the code under
 * test rather than in the fixture.
 */
export async function clearCollections() {
  const { collections } = mongoose.connection;
  await Promise.all(Object.values(collections).map((collection) => collection.deleteMany({})));
}

/** Close in `afterAll`, or the runner hangs on an open handle. */
export async function closeTestDb() {
  if (mongoose.connection.readyState !== 0) await mongoose.disconnect();
}
