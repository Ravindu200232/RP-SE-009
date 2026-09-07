import { createApp } from './app.js';
import { loadConfig } from './config.js';
import { connectDb } from './db.js';

const config = loadConfig();
await connectDb(config.mongoUri);
createApp().listen(config.port, '127.0.0.1', () => {
  console.log('catalog-service listening on ' + config.port);
});
