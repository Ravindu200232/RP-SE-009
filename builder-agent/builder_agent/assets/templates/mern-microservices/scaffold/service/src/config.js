/** Every value this service needs, read once, with a default that works on a developer machine. */
export function loadConfig(env = process.env) {
  return {
    // Give each service its own internal port.
    port: Number(env.SERVICE_PORT ?? 4001),
    mongoUri: env.MONGODB_URI ?? 'mongodb://127.0.0.1:27017/__APP_DB__',
  };
}
