# PROJECT_STATE

Updated: 2026-04-09T14:11:29.837Z
Thread: Workspace thread for task-manager
Task: Initial generation
Status: error

## Stack
- task-manager
- A task management application with auth, dashboards, and analytics.
- MERN Stack Microservices

## Services
- auth-service: port 3001
- task-service: port 3002
- dashboard-service: port 3003

## Pending
- none

## Naming Rules
- Backend flow: Route -> Controller -> Service -> Model
- Shared env vars: PORT, MONGO_URL, SEKRET_KEY, SERVER_URL
- Internal service URLs use *_SERVICE_URL env variables
