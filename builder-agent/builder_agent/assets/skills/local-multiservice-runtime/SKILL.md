---
name: local-multiservice-runtime
description: Run and supervise a multi-service Node/React application locally without Docker using one root command, deterministic readiness, prefixed logs, graceful shutdown, and a single public origin.
metadata:
  compatibility: AgentX mern-microservices local development and E2E.
---

# Docker-free local multi-service runtime

Use for the MERN local runner (`dev-all.mjs` or equivalent).

## Supervisor requirements
- Discover the package manager and actual service scripts from manifests.
- Start required child processes in a deterministic dependency-aware order only where order is truly required; otherwise start in parallel and wait for readiness.
- Reserve/configure internal ports centrally and avoid collisions. Never teach browser/client code those ports.
- Prefix stdout/stderr with service names and retain enough recent output for failure evidence.
- Poll real readiness endpoints with a bounded startup deadline; process spawn alone is not readiness.
- If any required child exits early or never becomes ready, stop the whole owned process tree and return non-zero.
- Forward SIGINT/SIGTERM and on Windows terminate descendant processes without leaving orphan Node/Vite children.
- Support clean restart without stale listeners.

## Single public port
The gateway is the public target. Once ready, all browser/runtime probes and E2E use `PUBLIC_APP_URL` or the gateway URL only.

## Readiness means the public origin serves the app

Polling a `/ready` that only checks the process and its upstreams will report a
healthy stack while the page itself is broken — measured: `/ready` 200, every
API 200, `/` 503. The supervisor's readiness gate must fetch the public origin
the browser will use and require a real page back, not merely a status from a
health route. Only then is "all services ready" true.

## Verification
When creating or changing the supervisor, prove cold start, readiness, representative UI/API requests, internal service failure behaviour, graceful shutdown, and a second start. For an ordinary feature in an existing app, reuse its healthy gateway and prove the changed route plus affected service integration. The supervisor lifecycle tests need another run only when its behaviour changes.
