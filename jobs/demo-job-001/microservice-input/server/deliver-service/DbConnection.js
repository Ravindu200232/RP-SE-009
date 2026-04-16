import mongoose from "mongoose";
import dotenv from "dotenv";


dotenv.config();

export async function connectToDatabase() {
  const MONGO_URL = process.env.MONGO_URL;
    console.log("MONGO_URL:", process.env.MONGO_URL);

  try {
    await mongoose.connect(MONGO_URL);
    console.log("MongoDB database connection established successfully");
  } catch (error) {
    console.error("MongoDB connection failed:", error);
  }
}
