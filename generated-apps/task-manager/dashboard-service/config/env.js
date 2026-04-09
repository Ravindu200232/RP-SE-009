import dotenv from "dotenv";

dotenv.config();

export const PORT = process.env.PORT;
export const MONGO_URL = process.env.MONGO_URL;
export const SEKRET_KEY = process.env.SEKRET_KEY;
export const SERVER_URL = process.env.SERVER_URL;
export const TASK_SERVICE_URL = process.env.TASK_SERVICE_URL;

export default {
  PORT,
  MONGO_URL,
  SEKRET_KEY,
  SERVER_URL,
  TASK_SERVICE_URL,
};