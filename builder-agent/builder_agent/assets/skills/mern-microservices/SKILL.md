---
name: mern-microservices
description: Build a React + Express/Node microservice application on MongoDB that runs locally with plain Node behind a single port, and ships a Dockerfile as an artifact rather than a runtime requirement.
---

# MERN microservices

A React client, several Express/Node services, one MongoDB server. The whole
application is reachable on **one port**, and it runs with `node` alone.

## The single-port rule

Everything — the browser, the E2E journeys, and the user — talks to one origin.
A gateway process owns that port and does two jobs:

1. Serves the client's production build as static files, with an SPA fallback so
   a deep link like `/orders/42` returns `index.html` rather than 404.
2. Proxies each service under its own path prefix — `/api/<service>/...` — to the
   port that service listens on.

Services bind to `127.0.0.1` on ports taken from their own environment variables
with sensible defaults. They are internal: nothing outside the gateway addresses
them, and no journey, probe or screenshot may use a service port directly.

Why this shape: a microservice app whose parts are only reachable on separate
ports cannot be driven by a browser, produces cross-origin failures that look
like product bugs, and forces the user to start six things by hand. One origin
removes all three problems and costs one small process.

## Write the unit tests in parallel

Once every service is implemented and you enter the unit phase, cover the
packages concurrently with `delegateUnitTests`: one unit per service and one for
the client, each confined to its own directory.

This is the phase where splitting is safe. Writing one service's tests needs
only that service's source, so the units are genuinely disjoint. Implementation
is not — a decision taken in one service reaches the contract every other
service is built against — so build the services yourself, in one place, and
delegate only the testing.

Pass both:

- `context` — what the project already decided: chosen versions, directory
  layout, the auth and error models, naming conventions. Units must follow these
  rather than re-decide them.
- `contract` — the shapes packages exchange: gateway prefixes, request and
  response payloads, shared env names.

A unit reads and tests only its own package, stubs the boundary where it calls a
sibling, and never imports a sibling's source. It installs nothing and starts no
servers. When it returns, you run the suites, record the evidence, and own every
remaining phase: coverage, browser journeys, runtime probes and the final audit.

## One workspace, one install

Declare every package in root `package.json` `workspaces` (for example
`["packages/*", "client"]`) and install **once** from the repository root.

A per-package `npm install` is the default mistake here and it is expensive: a
gateway, three services and a client means five installs, five dependency trees
and five lockfiles, for packages that share almost all of their dependencies.
Workspaces hoist the shared tree, produce one lockfile, and cut the slowest
non-model part of the build to a fraction of it.

- One `npm install` at the root. Never run it inside a package directory.
- One `package-lock.json`, at the root. Do not commit per-package lockfiles.
- Run a package's scripts with `npm run <script> --workspace <name>`, and the
  whole suite with `npm run <script> --workspaces`.
- Keep a dependency in the package that actually imports it; workspaces hoist it
  automatically, so listing it everywhere buys nothing.

## Running locally — no container runtime

- Every service starts with plain `node`. Never require Docker, Compose, or any
  container runtime to run, test, or verify the application.
- One command at the repository root starts the whole system: the gateway plus
  every service. Use a small Node supervisor script, or `npm-run-all`/
  `concurrently` if the project already depends on one. Do not write a shell
  script that only works on one platform.
- Start it through AgentX as a managed service and verify readiness on the
  gateway port before any journey.
- MongoDB is an already-running server the app connects to, not something the
  app starts. Each service uses its own database name or its own collections.

## Docker is a deliverable, not a dependency

Generate a `Dockerfile` for each service and the gateway, plus a
`docker-compose.yml` when more than one service exists. They must be correct and
buildable, and they are part of what you hand over.

Never run them during verification. Do not `docker build`, do not `docker
compose up`, and never make a test, journey or readiness probe depend on a
container. If Docker is absent from the machine that is not a failure and needs
no repair.

## Service boundaries

- A service owns its collections. No service reads or writes another service's
  data directly; it calls that service's HTTP API.
- Keep a shared contract explicit — request/response shapes at the edges — and
  validate input at every service boundary, not only at the gateway.
- Auth is verified where it is enforced. The gateway may pass a session or token
  through, but a service that exposes protected data checks it itself.
- A service that is down must produce a clean, described failure at the gateway,
  never an unhandled crash or a hanging request.

## Verification

- Unit/integration: Vitest, in every service and in the client. Cover each
  service's own domain rules and its boundary validation.
- E2E: AgentX CDP journeys against the **gateway origin only**. Build the client
  first; journeys must exercise the served production build, not a dev server on
  a different port.
- Runtime: probe the gateway for the client, for at least one route per service,
  and for the failure path when a service is unavailable.
- Capture visual evidence with `screenshot` steps inside the journeys, as the
  browser-e2e skill describes.

## Common failures to avoid

- Hard-coding a service port in client code — the client calls the gateway path
  prefix, never a port.
- A dev proxy that exists only in the Vite config, so the production build is
  unreachable. The gateway must serve the built client.
- Starting services in a way that leaves orphans when the run ends; use the
  managed-process tooling so cleanup works.
- Treating "the container builds" as evidence the application runs.
