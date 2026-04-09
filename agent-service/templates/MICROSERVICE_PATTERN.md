# AI-Ready MERN Microservice Pattern README

This repository already shows a MERN-style microservice application with:

- `client/` for the React frontend
- `service/` for backend microservices
- shared JWT verification across services
- MongoDB + Mongoose
- Swagger on every service
- service-to-service communication with `axios`
- Tailwind CSS on the frontend
- Supabase storage for React image upload

This file rewrites the project as a reusable implementation pattern so you can hand it to another AI model and say:

`Build my app using this same MERN microservice pattern.`

## 1. Target Architecture

Use this structure:

```text
project-root/
|-- client/
|   |-- src/
|   |   |-- components/
|   |   |-- pages/
|   |   |-- utils/
|   |-- package.json
|   |-- tailwind.config.js
|   |-- postcss.config.js
|   |-- .env.example
|
|-- service/
|   |-- user-service/
|   |   |-- controllers/
|   |   |-- models/
|   |   |-- routes/
|   |   |-- Server.js
|   |   |-- DbConnection.js
|   |   |-- package.json
|   |
|   |-- Restaurant-service/
|   |-- order-service/
|   |-- payment-service/
|   |-- deliver-service/
|   |-- notification-server/
|
|-- .env.example
|-- docker-compose.yml
|-- README.md
|-- MICROSERVICE_PATTERN_README.md
```

## 2. Service Responsibilities

Keep the backend split by business domain:

- `user-service`: registration, login, OTP, account management, shared auth entry point for users
- `Restaurant-service`: restaurant CRUD, collections, reviews, open/close, verify
- `order-service`: order creation, quote calculation, status updates
- `payment-service`: payment records, secure card-field hashing, update order payment state
- `deliver-service`: driver registration/login, delivery creation, location and status tracking
- `notification-server`: send emails and fetch supporting data from other services

## 3. Backend Library Pattern

The current repo uses almost the same package template in every service.

Install this base set inside each backend service:

```bash
npm install express mongoose dotenv cors helmet express-rate-limit body-parser jsonwebtoken bcrypt axios nodemailer swagger-jsdoc swagger-ui-express nodemon
npm install -D jest babel-jest @babel/core @babel/preset-env
```

Recommended `package.json` pattern:

```json
{
  "name": "user-service",
  "version": "1.0.0",
  "type": "module",
  "main": "Server.js",
  "scripts": {
    "start": "nodemon Server.js",
    "test": "jest",
    "test:coverage": "jest --coverage"
  },
  "jest": {
    "testEnvironment": "node",
    "transform": {
      "^.+\\.js$": "babel-jest"
    }
  }
}
```

Babel config used by the services:

```js
// babel.config.cjs
module.exports = {
  presets: [["@babel/preset-env", { targets: { node: "current" } }]],
};
```

## 4. Standard Backend Service Pattern

Each service follows the same internal structure:

```text
service-name/
|-- controllers/
|-- models/
|-- routes/
|-- __tests__/
|-- DbConnection.js
|-- Server.js
|-- package.json
|-- babel.config.cjs
```

### 4.1 `DbConnection.js` Pattern

```js
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
```

### 4.2 `Server.js` Pattern

Every service in this repo follows nearly this exact bootstrap pattern:

```js
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
    message: { error: "Too many requests, please try again later." },
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
    info: {
      title: "Service API",
      version: "1.0.0",
      description: "Microservice API",
    },
    servers: [
      {
        url: process.env.SERVER_URL || `http://localhost:${process.env.PORT}`,
      },
    ],
    components: {
      securitySchemes: {
        bearerAuth: {
          type: "http",
          scheme: "bearer",
          bearerFormat: "JWT",
        },
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
    service: "service-name",
    timestamp: new Date().toISOString(),
  });
});

app.use("/api/v1/resource", resourceRouter);

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Service running on port ${PORT}`);
});
```

Important repo convention:

- the JWT secret env name is spelled `SEKRET_KEY` in the current codebase, so keep that exact name unless you refactor all services together

## 5. Auth Helper Pattern

Each service contains the same role helper logic in `controllers/authController.js`:

```js
export function checkHasAccount(req) {
  return !!req.user;
}

export function checkAdmin(req) {
  return req.user?.role === "admin";
}

export function checkCustomer(req) {
  return req.user?.role === "customer";
}

export function checkRestaurant(req) {
  return req.user?.role === "restaurant";
}

export function checkDelivery(req) {
  return req.user?.role === "delivery";
}
```

Use these helpers inside controllers to protect endpoints.

## 6. JWT Token Pattern

This repo uses one shared JWT verification model across all services.

### 6.1 How JWT is created

Tokens are issued mainly from login endpoints:

- `user-service`: `POST /api/v1/users/login`
- `user-service`: `POST /api/v1/users/google`
- `deliver-service`: `POST /api/v1/driver/login`

Example token creation pattern used in controllers:

```js
const token = jwt.sign(
  {
    id: user._id,
    firstName: user.firstName,
    lastName: user.lastName,
    email: user.email,
    role: user.role,
    address: user.address,
    phone: user.phone,
    image: user.image,
    lat: user.lat,
    lng: user.lng,
  },
  process.env.SEKRET_KEY
);
```

### 6.2 How all services accept the same JWT

All services use the same middleware pattern:

- read `Authorization`
- remove `Bearer `
- verify using `process.env.SEKRET_KEY`
- attach decoded user to `req.user`

That means:

- customer, admin, and restaurant tokens can be created once and sent to all protected services
- driver tokens can also be verified by all services if they use the same shared `SEKRET_KEY`

### 6.3 How to get JWT for all services

Use this rule:

1. Login once through an auth endpoint.
2. Save the returned `token`.
3. Send the same token to other services in the header.

Header format:

```http
Authorization: Bearer <your_jwt_token>
```

Example flow:

```text
POST user-service /api/v1/users/login
-> returns token
-> frontend stores token in localStorage
-> frontend calls order-service, restaurant-service, payment-service, deliver-service, notification-server
-> every service verifies that same token with the shared secret
```

### 6.4 Frontend token usage pattern

The current React app stores the token like this:

```js
localStorage.setItem("token", res.data.token);
localStorage.setItem("user", JSON.stringify(res.data.user));
```

And sends it like this:

```js
const token = localStorage.getItem("token");

await axios.get(`${import.meta.env.VITE_ORDER_SERVICE_URL}/api/v1/orders`, {
  headers: {
    Authorization: `Bearer ${token}`,
  },
});
```

## 7. Controller Pattern

Use this controller style across services:

- validate auth first
- validate role second
- access Mongo model
- return JSON responses
- use `axios` for inter-service updates

Example pattern:

```js
export async function getItems(req, res) {
  try {
    if (!checkHasAccount(req)) {
      return res.status(401).json({ message: "Please login" });
    }

    if (!checkAdmin(req)) {
      return res.status(403).json({ message: "Access denied" });
    }

    const result = await Item.find();
    return res.json(result);
  } catch (error) {
    return res.status(500).json({ message: "Internal server error" });
  }
}
```

## 8. Route Pattern

Routes are thin and Swagger-documented.

Example:

```js
import express from "express";
import {
  createItem,
  getItems,
  updateItem,
  deleteItem,
} from "../controllers/itemController.js";

const router = express.Router();

router.post("/", createItem);
router.get("/", getItems);
router.put("/:id", updateItem);
router.delete("/:id", deleteItem);

export default router;
```

Repo route style notes:

- most APIs use `/api/v1/...`
- payment currently uses `/api/payment`
- notification currently uses `/api/v1/notification`
- restaurant service uses singular base paths like `/api/v1/restaurant`

## 9. MongoDB Model Pattern

Use Mongoose models under `models/`.

Example:

```js
import mongoose from "mongoose";

const userSchema = new mongoose.Schema(
  {
    firstName: String,
    lastName: String,
    email: { type: String, unique: true },
    password: String,
    role: {
      type: String,
      enum: ["admin", "customer", "restaurant", "delivery"],
      default: "customer",
    },
    address: String,
    phone: String,
    image: String,
  },
  { timestamps: true }
);

export default mongoose.model("User", userSchema);
```

## 10. Inter-Service Communication Pattern

This project already uses `axios` between services.

### Payment -> Order

```js
const orderServiceUrl = process.env.ORDER_SERVICE_URL || "http://localhost:3003";

await axios.put(`${orderServiceUrl}/api/v1/orders/status/${bookingId}`, {
  paymentStatus: "paid",
  status: "confirmed",
});
```

### Delivery -> Order

```js
const orderServiceUrl = process.env.ORDER_SERVICE_URL || "http://localhost:3003";

await axios.put(
  `${orderServiceUrl}/api/v1/orders/status/${updatedDelivery.orderId}`,
  { status }
);
```

### Notification -> Restaurant

```js
const restaurantServiceUrl =
  process.env.RESTAURANT_SERVICE_URL || "http://localhost:3002";

const restaurantRes = await axios.get(
  `${restaurantServiceUrl}/api/v1/restaurant/getOne/${restaurantId}`
);
```

Pattern rule:

- never hardcode another service URL inside business logic
- always use env variables like `ORDER_SERVICE_URL` and `RESTAURANT_SERVICE_URL`

## 11. Frontend Library Pattern

Install the frontend with Vite + React + Tailwind and the same supporting libraries:

```bash
npm install react react-dom react-router-dom axios react-hot-toast react-icons react-toastify sweetalert2 @react-oauth/google @supabase/supabase-js leaflet @react-google-maps/api @smastrom/react-rating lucide-react
npm install -D vite @vitejs/plugin-react eslint @eslint/js eslint-plugin-react eslint-plugin-react-hooks eslint-plugin-react-refresh globals tailwindcss postcss autoprefixer
```

The current `client/package.json` also contains `@tailwindcss/vite`, but the working repo pattern is the standard Tailwind config with:

- `tailwind.config.js`
- `postcss.config.js`
- `src/index.css`

## 12. Tailwind CSS Install Pattern

Inside `client/`:

```bash
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

`tailwind.config.js`

```js
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: "#050818",
        secondary: "#ffffff",
        accent: "#7DC4FF",
      },
    },
  },
  plugins: [],
};
```

`postcss.config.js`

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

`src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

## 13. React Service URL Pattern

Use one env variable per backend service:

```env
VITE_USER_SERVICE_URL=http://localhost:3001
VITE_RESTAURANT_SERVICE_URL=http://localhost:3002
VITE_ORDER_SERVICE_URL=http://localhost:3003
VITE_PAYMENT_SERVICE_URL=http://localhost:3004
VITE_DELIVER_SERVICE_URL=http://localhost:3005
VITE_NOTIFICATION_SERVICE_URL=http://localhost:3006
```

Frontend request pattern:

```js
await axios.post(`${import.meta.env.VITE_USER_SERVICE_URL}/api/v1/users/login`, {
  email,
  password,
});
```

## 14. Supabase Image Upload Pattern For React

The repo already has a Supabase upload helper in `client/src/utils/mediaUpload.js`.

Use this safe env-based version:

```js
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const bucketName = import.meta.env.VITE_SUPABASE_BUCKET || "images";

const supabase = createClient(supabaseUrl, supabaseAnonKey);

export default function mediaUpload(file) {
  return new Promise((resolve, reject) => {
    if (!file) {
      reject("No file selected");
      return;
    }

    const fileName = `${Date.now()}-${file.name}`;

    supabase.storage
      .from(bucketName)
      .upload(fileName, file, {
        cacheControl: "3600",
        upsert: false,
      })
      .then(({ error }) => {
        if (error) {
          reject(error.message);
          return;
        }

        const publicUrl = supabase.storage
          .from(bucketName)
          .getPublicUrl(fileName).data.publicUrl;

        resolve(publicUrl);
      })
      .catch(() => {
        reject("Error uploading file");
      });
  });
}
```

Usage example:

```js
import mediaUpload from "../utils/mediaUpload";

async function handleImageUpload(file) {
  const imageUrl = await mediaUpload(file);
  console.log(imageUrl);
}
```

Supabase requirements:

- create a bucket, usually `images`
- allow upload policy for authenticated or public usage based on your app
- keep `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in env, not in source code

## 15. Google Login Env Pattern

The frontend uses `@react-oauth/google`.

Use env instead of hardcoding the client id:

```jsx
import { GoogleOAuthProvider } from "@react-oauth/google";

<GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
  <App />
</GoogleOAuthProvider>
```

## 16. Environment Variable Pattern

There are two env layers in this architecture:

### 16.1 Root/backend `.env`

Use this for backend services and service-to-service URLs:

```env
NODE_ENV=development
MONGO_URL=mongodb+srv://USERNAME:PASSWORD@cluster.mongodb.net/APP_DB
SEKRET_KEY=replace_with_shared_jwt_secret

EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_gmail_app_password

USER_SERVICE_URL=http://localhost:3001
RESTAURANT_SERVICE_URL=http://localhost:3002
ORDER_SERVICE_URL=http://localhost:3003
PAYMENT_SERVICE_URL=http://localhost:3004
DELIVER_SERVICE_URL=http://localhost:3005
NOTIFICATION_SERVICE_URL=http://localhost:3006
```

### 16.2 Per-service env idea

Each service also needs:

```env
PORT=3001
SERVER_URL=http://localhost:3001
```

Change `PORT` and `SERVER_URL` per service.

### 16.3 Frontend `client/.env`

```env
VITE_BACKEND_URL=http://localhost:3001
VITE_USER_SERVICE_URL=http://localhost:3001
VITE_RESTAURANT_SERVICE_URL=http://localhost:3002
VITE_ORDER_SERVICE_URL=http://localhost:3003
VITE_PAYMENT_SERVICE_URL=http://localhost:3004
VITE_DELIVER_SERVICE_URL=http://localhost:3005
VITE_NOTIFICATION_SERVICE_URL=http://localhost:3006

VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
VITE_SUPABASE_BUCKET=images

VITE_GOOGLE_CLIENT_ID=your_google_oauth_client_id
```

## 17. Secure Coding Notes For This Pattern

If another AI model builds from this README, it should follow these rules:

- do not hardcode Gmail passwords, JWT secrets, AWS keys, Google client ids, or Supabase keys in code
- use env variables for all secrets and service URLs
- use the shared JWT verification middleware in every protected service
- keep service ownership separate by domain
- use Swagger in every service
- use `axios` for service-to-service communication
- keep React service URLs in `import.meta.env`
- store the JWT on login and send `Authorization: Bearer <token>` on protected requests

## 18. Minimal Build Order

If you want an AI model to recreate this app, ask it to build in this order:

1. Create `client/` and `service/`
2. Create one reusable backend service template
3. Clone that service template into all microservices
4. Add Mongoose models and controllers by domain
5. Add JWT login in `user-service` and `deliver-service`
6. Add shared JWT middleware to every service
7. Add React frontend with Vite and Tailwind
8. Add service URL env variables in the client
9. Add Supabase image upload helper
10. Add Swagger docs and health routes for every service

## 19. AI Prompt You Can Reuse

Give this to another AI model:

```text
Build a MERN microservice application using this pattern:

- Frontend in client/ using React + Vite + Tailwind CSS
- Backend in service/ with separate microservices:
  user-service, Restaurant-service, order-service, payment-service, deliver-service, notification-server
- Every backend service must use Express, MongoDB with Mongoose, dotenv, cors, helmet, express-rate-limit, body-parser, jsonwebtoken, swagger-jsdoc, swagger-ui-express
- Every service must have Server.js, DbConnection.js, controllers/, models/, routes/
- Use shared JWT verification middleware in every service with env name SEKRET_KEY
- user-service must issue JWT on login
- deliver-service can also issue JWT for driver login
- Other services must verify the same token and read req.user
- Use role helpers: checkAdmin, checkCustomer, checkRestaurant, checkDelivery, checkHasAccount
- Use axios for service-to-service calls
- payment-service must notify order-service
- notification-server must fetch restaurant data from restaurant-service
- Frontend must store JWT in localStorage and send Authorization: Bearer <token>
- Frontend must use import.meta.env service URLs
- Add Tailwind config, postcss config, and src/index.css directives
- Add Supabase image upload helper using VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, and VITE_SUPABASE_BUCKET
- Add VITE_GOOGLE_CLIENT_ID for Google login
- Never hardcode secrets in source code
- Add .env.example files for backend and frontend
```

## 20. Final Pattern Summary

This repo's reusable pattern is:

- React frontend talks directly to domain microservices
- services share one JWT verification secret
- login happens once, token is reused everywhere
- each service owns its own routes, models, and controllers
- MongoDB is connected per service with the same `DbConnection.js` pattern
- Tailwind is configured in the standard Vite way
- Supabase is used from React for image upload
- env files define every secret and every service URL

If you keep those rules, another AI model can generate new MERN microservice apps that match this project style very closely.
