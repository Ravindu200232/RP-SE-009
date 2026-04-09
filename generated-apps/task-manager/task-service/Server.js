import express from "express";
import bodyParser from "body-parser";
import dotenv from "dotenv";
import helmet from "helmet";
import rateLimit from "express-rate-limit";
import swaggerJsdoc from "swagger-jsdoc";
import swaggerUi from "swagger-ui-express";
import jwt from "jsonwebtoken";
import cors from "cors";
import { connectToDatabase } from "./DbConnection.js";

dotenv.config();

const app = express();

app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.use(cors());

app.use(
  helmet({
    contentSecurityPolicy: false,
    crossOriginEmbedderPolicy: false,
    crossOriginOpenerPolicy: false,
    hsts: false
  })
);

app.use(
  rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 100,
    message: { error: "Too many requests, please try again later." },
    standardHeaders: true,
    legacyHeaders: false
  })
);

app.use((req, res, next) => {
  let token = req.header("Authorization");

  if (token) {
    token = token.replace("Bearer ", "");
    jwt.verify(token, process.env.SEKRET_KEY, (err, decode) => {
      if (!err) {
        req.user = decode;
      }
    });
  }

  next();
});

const swaggerOptions = {
  definition: {
    openapi: "3.0.0",
    info: { title: "Task Service API", version: "1.0.0" },
    servers: [{ url: process.env.SERVER_URL || `http://localhost:${process.env.PORT}` }],
    components: { securitySchemes: { bearerAuth: { type: "http", scheme: "bearer", bearerFormat: "JWT" } } }
  },
  apis: ["./routes/*.js"]
};

const swaggerSpec = swaggerJsdoc(swaggerOptions);
app.use("/api-docs", swaggerUi.serve, swaggerUi.setup(swaggerSpec));
app.get("/api-docs.json", (req, res) => res.json(swaggerSpec));

connectToDatabase();

import taskRoutes from "./routes/taskRoutes.js";

app.use(taskRoutes);

app.get("/health", (req, res) => {
  res.json({ status: "healthy", service: "task-service", timestamp: new Date().toISOString() });
});

const PORT = process.env.PORT || 3002;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));

app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ message: err.message });
});
