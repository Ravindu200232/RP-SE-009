import express from 'express';
import bodyParser from 'body-parser';
import dotenv from 'dotenv';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import swaggerJsdoc from 'swagger-jsdoc';
import swaggerUi from 'swagger-ui-express';
import { connectToDatabase } from './DbConnection.js';
import jwt from 'jsonwebtoken';
import cors from 'cors';
import restaurantRoute from './routes/restaurantRoute.js';
import collectionRoute from './routes/collectionRoute.js';
import reviewRouter from './routes/reviewRouter.js';

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
  message: { error: 'Too many requests, please try again later.' },
  standardHeaders: true,
  legacyHeaders: false,
});
app.use(limiter);

app.use(bodyParser.json());

app.use((req, res, next) => {
  let token = req.header('Authorization');
  if (token != null) {
    token = token.replace('Bearer ', '');
    jwt.verify(token, process.env.SEKRET_KEY, (err, decode) => {
      if (!err) { req.user = decode; }
    });
  }
  next();
});

const swaggerOptions = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'Restaurant Service API',
      version: '1.0.0',
      description: 'Restaurant Service for Food Ordering App',
    },
    servers: [{ url: process.env.SERVER_URL || `http://localhost:${process.env.PORT || 3002}` }],
    components: {
      securitySchemes: {
        bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT' },
      },
    },
  },
  apis: ['./routes/*.js'],
};
const swaggerSpec = swaggerJsdoc(swaggerOptions);
app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec));
app.get('/api-docs.json', (req, res) => res.json(swaggerSpec));

connectToDatabase();

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'Restaurant-service', timestamp: new Date().toISOString() });
});

app.use('/api/v1/restaurant', restaurantRoute);
app.use('/api/v1/collection', collectionRoute);
app.use('/api/v1/reviews', reviewRouter);

const PORT = process.env.PORT || 3002;
app.listen(PORT, () => {
  console.log(`Restaurant service running on port ${PORT}`);
  console.log(`Environment: ${process.env.NODE_ENV}`);
});
