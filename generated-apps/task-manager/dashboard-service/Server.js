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

app.use(
  helmet({
    contentSecurityPolicy: false,
    crossOriginEmbedderPolicy: false,
    crossOriginOpenerPolicy: false,
    hsts: false,
  })
);

app.use(cors());
app.use(bodyParser.json());

app.use(
  rateLimit({
    windowMs: 15 * 60 * 1000,
    max: 100,
    standardHeaders: true,
    legacyHeaders: false,
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
    info: { title: "Dashboard Service API", version: "1.0.0" },
    servers: [{ url: process.env.SERVER_URL || `http://localhost:${process.env.PORT}` }],
    components: { securitySchemes: { bearerAuth: { type: "http", scheme: "bearer", bearerFormat: "JWT" } } }
  },
  apis: ["./routes/*.js"]
};

const swaggerSpec = swaggerJsdoc(swaggerOptions);
app.use("/api-docs", swaggerUi.serve, swaggerUi.setup(swaggerSpec));
app.get("/api-docs.json", (req, res) => res.json(swaggerSpec));

connectToDatabase();

app.get("/health", (req, res) => {
  res.json({ status: "healthy", service: "dashboard-service", timestamp: new Date().toISOString() });
});

import { statsRouter } from "./routes/stats.js";
app.use("/api/v1/dashboard", statsRouter);

const PORT = process.env.PORT || 3003;
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(err.status || 500).json({ error: err.message || 'Internal Server Error' });
});

app.listen(PORT, () => console.log(`Service running on port ${PORT}`));