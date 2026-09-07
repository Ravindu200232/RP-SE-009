---
name: express
description: Build production-quality Express APIs and microservices with explicit routing, middleware order, validation, error contracts, auth boundaries, health endpoints, and graceful runtime behavior.
compatibility: AgentX mern-microservices stack, Express 5 or the project's installed version.
---

# Express service engineering

Inspect installed Express version, entry point, routers, middleware order, auth, validation, error handler, health/readiness endpoints, and tests.

## Service shape
- Keep transport handlers thin: validate request, call domain/service logic, map result/error to the API contract.
- Organize routers by bounded domain, not one giant routes file.
- Middleware order is part of behavior: request context/logging → parsing/limits → auth/authorization → routes → not-found → error handler.
- Ensure middleware either finishes the response or passes control; avoid hanging requests.
- Use one consistent JSON error shape for application APIs and do not leak stack traces/secrets in production.
- Validate path/query/body input before domain/database calls.
- Set sensible body limits and security headers through maintained packages/config where selected.
- Expose liveness/readiness endpoints that prove what the orchestrator actually needs.
- Separate graceful shutdown from crash handling and close database/resources.

## Express 5 note
Promise-returning handlers can propagate rejected async errors to Express 5 error handling. Preserve the installed-version behavior rather than adding redundant wrappers blindly.

Official references:
- https://expressjs.com/en/5x/guide/using-middleware/
- https://expressjs.com/en/5x/guide/error-handling/
- https://expressjs.com/en/guide/routing/
