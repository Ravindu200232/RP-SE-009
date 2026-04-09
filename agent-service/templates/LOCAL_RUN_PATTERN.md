# Local Run Pattern

This file explains how to run the full project locally with:

- multiple backend microservices
- the React client
- correct local ports
- local `.env` setup

It is written for the current repo structure:

```text
client/
service/
  user-service/
  Restaurant-service/
  order-service/
  payment-service/
  deliver-service/
  notification-server/
```

## 1. What Runs Locally

You need to run:

- `user-service`
- `Restaurant-service`
- `order-service`
- `payment-service`
- `deliver-service`
- `notification-server`
- `client`

That means 7 running processes in development.

## 2. Required Local Ports

Use these local ports:

- `user-service` -> `3001`
- `Restaurant-service` -> `3002`
- `order-service` -> `3003`
- `payment-service` -> `3004`
- `deliver-service` -> `3005`
- `notification-server` -> `3006`
- `client` -> `5173`

Important note:

- `user-service` source code falls back to `3000`
- but the frontend and the project pattern expect `3001`
- so set `PORT=3001` in `service/user-service/.env`

## 3. Local Environment Setup

### 3.1 Backend `.env` pattern

Create or update a `.env` inside each backend service folder.

### `service/user-service/.env`

```env
MONGO_URL=your_mongodb_connection_string
SEKRET_KEY=your_shared_jwt_secret
PORT=3001
SERVER_URL=http://localhost:3001
NODE_ENV=development
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_gmail_app_password
```

### `service/Restaurant-service/.env`

```env
MONGO_URL=your_mongodb_connection_string
SEKRET_KEY=your_shared_jwt_secret
PORT=3002
SERVER_URL=http://localhost:3002
NODE_ENV=development
```

### `service/order-service/.env`

```env
MONGO_URL=your_mongodb_connection_string
SEKRET_KEY=your_shared_jwt_secret
PORT=3003
SERVER_URL=http://localhost:3003
NODE_ENV=development
```

### `service/payment-service/.env`

```env
MONGO_URL=your_mongodb_connection_string
SEKRET_KEY=your_shared_jwt_secret
PORT=3004
SERVER_URL=http://localhost:3004
NODE_ENV=development
ORDER_SERVICE_URL=http://localhost:3003
```

### `service/deliver-service/.env`

```env
MONGO_URL=your_mongodb_connection_string
SEKRET_KEY=your_shared_jwt_secret
PORT=3005
SERVER_URL=http://localhost:3005
NODE_ENV=development
ORDER_SERVICE_URL=http://localhost:3003
```

### `service/notification-server/.env`

```env
MONGO_URL=your_mongodb_connection_string
SEKRET_KEY=your_shared_jwt_secret
PORT=3006
SERVER_URL=http://localhost:3006
NODE_ENV=development
RESTAURANT_SERVICE_URL=http://localhost:3002
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_gmail_app_password
```

## 4. Client `.env` For Local Run

The checked-in `client/.env` currently points to deployed URLs, not localhost.

For local development, set:

### `client/.env`

```env
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

## 5. Install Pattern

Open PowerShell in the project root:

```powershell
cd C:\Users\ravin\OneDrive\Desktop\template
```

Install client dependencies:

```powershell
cd client
npm install
```

Install backend dependencies one by one:

```powershell
cd ..\service\user-service
npm install

cd ..\Restaurant-service
npm install

cd ..\order-service
npm install

cd ..\payment-service
npm install

cd ..\deliver-service
npm install

cd ..\notification-server
npm install
```

## 6. Run Pattern With Multiple Terminals

The simplest pattern is:

- open 7 terminals
- run one process per terminal

### Terminal 1

```powershell
cd C:\Users\ravin\OneDrive\Desktop\template\service\user-service
npm start
```

### Terminal 2

```powershell
cd C:\Users\ravin\OneDrive\Desktop\template\service\Restaurant-service
npm start
```

### Terminal 3

```powershell
cd C:\Users\ravin\OneDrive\Desktop\template\service\order-service
npm start
```

### Terminal 4

```powershell
cd C:\Users\ravin\OneDrive\Desktop\template\service\payment-service
npm start
```

### Terminal 5

```powershell
cd C:\Users\ravin\OneDrive\Desktop\template\service\deliver-service
npm start
```

### Terminal 6

```powershell
cd C:\Users\ravin\OneDrive\Desktop\template\service\notification-server
npm start
```

### Terminal 7

```powershell
cd C:\Users\ravin\OneDrive\Desktop\template\client
npm run dev
```

## 7. Recommended Startup Order

Use this order:

1. `user-service`
2. `Restaurant-service`
3. `order-service`
4. `payment-service`
5. `deliver-service`
6. `notification-server`
7. `client`

Reason:

- all services need MongoDB first
- some services depend on other service URLs
- client should start after backend URLs are ready

## 8. Expected Local URLs

After all processes start, use:

- user service: [http://localhost:3001](http://localhost:3001)
- restaurant service: [http://localhost:3002](http://localhost:3002)
- order service: [http://localhost:3003](http://localhost:3003)
- payment service: [http://localhost:3004](http://localhost:3004)
- deliver service: [http://localhost:3005](http://localhost:3005)
- notification service: [http://localhost:3006](http://localhost:3006)
- client: [http://localhost:5173](http://localhost:5173)

Swagger pages:

- [http://localhost:3001/api-docs](http://localhost:3001/api-docs)
- [http://localhost:3002/api-docs](http://localhost:3002/api-docs)
- [http://localhost:3003/api-docs](http://localhost:3003/api-docs)
- [http://localhost:3004/api-docs](http://localhost:3004/api-docs)
- [http://localhost:3005/api-docs](http://localhost:3005/api-docs)
- [http://localhost:3006/api-docs](http://localhost:3006/api-docs)

## 9. Health Check Pattern

Each backend service has a `/health` endpoint.

Use these to confirm the services are running:

- [http://localhost:3001/health](http://localhost:3001/health)
- [http://localhost:3002/health](http://localhost:3002/health)
- [http://localhost:3003/health](http://localhost:3003/health)
- [http://localhost:3004/health](http://localhost:3004/health)
- [http://localhost:3005/health](http://localhost:3005/health)
- [http://localhost:3006/health](http://localhost:3006/health)

If a service fails:

- check `.env`
- check MongoDB connection
- check port conflicts
- check whether another service URL is wrong

## 10. Local JWT Pattern

To make the frontend work locally:

1. start all backend services
2. start client
3. register or login from the frontend
4. token is saved in localStorage
5. frontend uses that token across services

Important rule:

- all services must use the same `SEKRET_KEY`
- otherwise JWT verification will fail between services

## 11. Common Local Issues In This Repo

### Client still points to deployed backend

Fix:

- replace deployed URLs in `client/.env` with localhost URLs

### `user-service` starts on `3000`

Fix:

- set `PORT=3001` in `service/user-service/.env`

### Google login not working locally

Fix:

- set `VITE_GOOGLE_CLIENT_ID`
- ensure your Google OAuth app allows your local frontend origin

### Supabase image upload not working locally

Fix:

- set `VITE_SUPABASE_URL`
- set `VITE_SUPABASE_ANON_KEY`
- set `VITE_SUPABASE_BUCKET`

### Email features not working

Fix:

- set `EMAIL_USER`
- set `EMAIL_PASS`
- use Gmail app password if using Gmail SMTP

## 12. Docker Note

There is a `docker-compose.yml` in the repo, but the current folder structure is `service/...` while the compose file points to `server/...`.

So for this repo as it exists now:

- the safest local run method is manual multi-terminal startup
- if you want Docker Compose, update the compose paths from `server/...` to `service/...`

## 13. Best Practice Pattern

For local development in this repo, use this workflow:

1. keep one terminal tab per service
2. keep client in its own tab
3. use localhost URLs in `client/.env`
4. keep the same `SEKRET_KEY` in all services
5. check `/health` before opening the frontend

## 14. Reusable Prompt For Another AI

```text
Add a local development run guide for this MERN microservice project.

Requirements:
- explain how to run all backend services and the React client locally
- use one terminal per service
- define the localhost ports:
  user-service 3001
  Restaurant-service 3002
  order-service 3003
  payment-service 3004
  deliver-service 3005
  notification-server 3006
  client 5173
- include .env examples for each service
- include client .env localhost URLs
- explain the shared JWT secret requirement
- include health-check URLs
- mention that client/.env must not point to deployed URLs for local development
```
