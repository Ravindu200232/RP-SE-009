/**
 * Every value the service needs, read once, with a default that works on a
 * developer machine. Reading process.env deeper in the code is what makes a
 * service impossible to test.
 */
export function loadConfig(env = process.env) {
  return {
    port: Number(env.CATALOG_PORT ?? 4101),
    mongoUri: env.MONGODB_URI ?? 'mongodb://127.0.0.1:27017/sketch_mern',
  };
}
