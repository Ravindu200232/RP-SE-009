import mongoose from "mongoose";
import dotenv from "dotenv";

dotenv.config();

export function connectToDatabase() {
  const mongoUrl = process.env.MONGO_URL;
  mongoose.connect(mongoUrl);

  const connection = mongoose.connection;
  connection.once("open", () => {
    console.log("MongoDB database connection established successfully");
  });
}