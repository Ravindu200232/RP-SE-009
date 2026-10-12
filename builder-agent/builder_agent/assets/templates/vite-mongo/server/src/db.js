import mongoose from 'mongoose';

/** One connection, cached on the module - not per request. */
let connection = null;

export async function connectDb(uri = process.env.MONGODB_URI ?? 'mongodb://127.0.0.1:27017/__APP_DB__') {
  if (mongoose.connection.readyState === 1) {
    connection = mongoose.connection;
    return connection;
  }
  connection = await mongoose.connect(uri);
  return connection;
}

export async function disconnectDb() {
  if (mongoose.connection.readyState !== 0) await mongoose.disconnect();
  connection = null;
}
