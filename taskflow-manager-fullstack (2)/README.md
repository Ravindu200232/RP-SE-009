# TaskFlow Manager

## Quick Start

### Frontend
```bash
cd frontend && npm install && npm run dev
```

### Backend
```bash
cd backend/api-gateway && npm install && npm start
cd backend/[service]-service && npm install && npm start
```

## Ports
- Frontend: 3000
- API Gateway: 3005
- Service 1: 3006 / Service 2: 3007
- MongoDB: 27017

## Smoke Test
Run this after starting the frontend and backend services to verify the gateway, task CRUD API, board API, and datastore writes:

```bash
node backend/scripts/smoke-test.js
```
