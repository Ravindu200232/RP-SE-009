# SERVICE_COMMUNICATION

## auth-service
Base URL: http://localhost:3001
Depends on:
- none

## task-service
Base URL: http://localhost:3002
Depends on:
- auth-service: AUTH_SERVICE_URL -> http://localhost:3001

## dashboard-service
Base URL: http://localhost:3003
Depends on:
- auth-service: AUTH_SERVICE_URL -> http://localhost:3001
- task-service: TASK_SERVICE_URL -> http://localhost:3002
