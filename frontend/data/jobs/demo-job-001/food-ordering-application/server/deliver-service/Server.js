import express from "express";
import bodyParser from "body-parser";
import dotenv from "dotenv";
import helmet from "helmet";
import rateLimit from "express-rate-limit";
import swaggerJsdoc from "swagger-jsdoc";
import swaggerUi from "swagger-ui-express";
import { connectToDatabase } from "./DbConnection.js";
import jwt from "jsonwebtoken";
import cors from "cors";
import driverRoute from "./routes/driverRoute.js";
import deliveryRoute from "./routes/deliveryRoute.js";

dotenv.config();

const app = express();

app.use(helmet({
  contentSecurityPolicy: false,
  crossOriginEmbedderPolicy: false,
  crossOriginOpenerPolicy: false,
  hsts: false,
}));


app.use(cors());

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  message: { error: "Too many requests, please try again later." },
  standardHeaders: true,
  legacyHeaders: false,
});
app.use(limiter);

app.use(bodyParser.json());

app.use((req, res, next) => {
  let token = req.header("Authorization");
  if (token != null) {
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
    info: {
      title: "Delivery Service API",
      version: "1.0.0",
      description: "Delivery Service for Food Ordering App",
    },
    servers: [{ url: process.env.SERVER_URL || `http://localhost:${process.env.PORT || 3005}` }],
    components: {
      securitySchemes: {
        bearerAuth: { type: "http", scheme: "bearer", bearerFormat: "JWT" },
      },
    },
  },
  apis: ["./routes/*.js"],
};
const swaggerSpec = swaggerJsdoc(swaggerOptions);
app.use("/api-docs", swaggerUi.serve, swaggerUi.setup(swaggerSpec));
app.get("/api-docs.json", (req, res) => res.json(swaggerSpec));

connectToDatabase();

app.get("/health", (req, res) => {
  res.json({
    status: "healthy",
    service: "deliver-service",
    timestamp: new Date().toISOString(),
  });
});

app.use("/api/v1/driver", driverRoute);
app.use("/api/v1/delivery", deliveryRoute);

const PORT = process.env.PORT || 3005;
app.listen(PORT, () => {
  console.log(`Deliver service running on port ${PORT}`);

  console.log(`Environment: ${process.env.NODE_ENV}`);
});
