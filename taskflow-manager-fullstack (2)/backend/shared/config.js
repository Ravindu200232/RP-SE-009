const path = require('path');
const dotenv = require('dotenv');

const backendRoot = path.resolve(__dirname, '..');
dotenv.config({ path: path.join(backendRoot, '.env') });

const toPort = (value, fallback) => {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const servicePorts = {
  gateway: toPort(process.env.PORT_GATEWAY, 3005),
  tasks: toPort(process.env.PORT_SERVICE1, 3006),
  board: toPort(process.env.PORT_SERVICE2, 3007),
};

const serviceUrls = {
  gateway: `http://127.0.0.1:${servicePorts.gateway}`,
  tasks: `http://127.0.0.1:${servicePorts.tasks}`,
  board: `http://127.0.0.1:${servicePorts.board}`,
};

module.exports = {
  backendRoot,
  mongoUri: process.env.MONGODB_URI || 'mongodb://127.0.0.1:27017/taskflow-manager',
  nodeEnv: process.env.NODE_ENV || 'development',
  servicePorts,
  serviceUrls,
  dataStoreFile: path.join(backendRoot, 'data', 'taskflow-store.json'),
};
