---
name: api-gateway
description: Design and verify a single-origin API gateway for AgentX microservices with stable routing, auth propagation, request IDs, timeout/error mapping, client serving, and service readiness.
compatibility: AgentX mern-microservices stack.
---

# API gateway

The gateway is the only browser-facing origin in MERN microservices mode.

- Define stable public prefixes such as `/api/auth`, `/api/catalog`, `/api/orders`; internal host/port details never appear in client code.
- Centralize cross-cutting transport concerns that truly belong at the edge: correlation IDs, coarse request logging, CORS for non-single-origin deployments, auth/session handoff, rate limits, and common error mapping.
- Do not move domain business rules into the gateway.
- Propagate only the identity/claims needed by downstream services and still enforce authorization at the owning service for privileged actions.
- Configure upstream timeouts and map connection failures/timeouts to explicit 502/503/504-style behavior as appropriate.
- Preserve status codes and safe response bodies; never turn every upstream failure into 500.
- Add `/health` and `/ready` semantics suitable for the local supervisor and containers.
- In development, proxy or serve the React client so users and E2E use one public port.

## Serving the client: the failure that reports itself as healthy

Measured on a real build. The gateway returned **200** on `/ready`, every API
prefix returned **200**, its own 27 unit tests passed — and `/` returned **503**
with "Client build not found", because the dist path was resolved one directory
short:

```
path.resolve(__dirname, '../../client/dist')
  __dirname = packages/gateway/src
  ../../    = packages/          ->  packages/client/dist   (does not exist)
  needed    = ../../../          ->  client/dist            (the repository root)
```

Two rules come out of it, and both generalise past this one path:

- **Readiness must include what the browser actually loads.** A `/ready` that
  only reports "my process is up and my upstreams answered" is not readiness
  for a gateway whose main job is serving a page. Have it confirm the client
  entry file exists and is readable, so a missing or mislocated build fails at
  the readiness check instead of at the first visitor.
- **A path built from `__dirname` is resolved against the file's own directory,
  not the package root.** Do not count the `..` segments in your head: resolve
  the path and check the file exists at startup, then log the resolved location
  when it does not. `packages/<name>/src/x.js` is three levels below the
  repository root, and every extra `src/` or `dist/` in the layout shifts it
  again.

Degrading gracefully is right — a clear 503 beats a crash — but a graceful
degradation that readiness reports as healthy is a silent outage. Make the check
and the behaviour agree.

Verify routing for every service prefix, auth boundary, error mapping, unavailable upstream behavior, and no direct browser dependency on internal ports.
