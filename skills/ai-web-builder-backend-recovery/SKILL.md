# AI Web Builder Backend Recovery

Use this local project skill when the generator is fixing backend bugs, startup failures, route mismatches, or MongoDB integration issues.

## Goals

- Fix all known backend bugs in the first repair pass whenever possible.
- Use up to five passes total, but stop early as soon as the backend is clean.
- Use the full backend snapshot for round 1, then switch to focused snapshots around only the remaining failed routes/files in later rounds.
- Prevent frontend generation from starting while backend routes still fail.
- Prefer full-file rewrites over tiny patches when repeated failures come from the same route file.

## Recovery playbook

1. Sanitize backend code first.
   - Remove stray non-ASCII executable characters.
   - Normalize malformed route files before asking the model to repair logic.
2. Align gateway and service contracts.
   - Match proxy prefixes to route file resource names.
   - Keep `/api/tasks`, `/api/users`, `/api/boards`, and similar resources consistent across gateway, services, and frontend.
3. Fix write-path reliability.
   - Ensure `cors()` and `express.json()` exist.
   - Add `fixRequestBody`, proxy timeouts, and JSON `502` downstream failure responses in the gateway.
   - Prefer `process.env.MONGODB_URI` or `process.env.MONGO_URL` during live validation so every run is isolated from previous test data.
   - Accept auth secrets from `process.env.JWT_SECRET`, `process.env.SECRET_KEY`, or `process.env.SEKRET_KEY`.
4. Fix route correctness.
   - Add `try/catch` to async handlers.
   - Return `{ success: true, data }` or `{ success: false, error }`.
   - Validate IDs before database access.
   - Put literal routes like `/health`, `/status`, `/search`, and `/stats` before parameterized routes such as `/:id`.
   - Avoid cross-service `populate()` chains; return raw IDs if the related model belongs to another microservice.
5. Run live validation.
   - Install dependencies.
   - Start services and gateway.
   - Allocate a unique port for every service instead of assuming only two services exist.
   - Send real HTTP requests with sample payloads.
   - Reuse created IDs and auth tokens across later live requests.
   - Treat protected routes such as `/api/users/me`, `/api/auth/profile`, and `/api/auth/verify` as Bearer-token routes during live validation.
   - Send realistic query params for GET routes that require them, such as analytics date-range endpoints.
   - Prefer external gateway `/api/...` route prefixes over internal service-only mounts when building live request paths.
   - If sample POST bodies are missing, synthesize them from the discovered Mongoose schema so required-field validation does not repeat forever.
   - Normalize frontend collection responses to arrays before rendering, so `.map()` and `.filter()` do not crash when the backend returns nested payload shapes.
   - Skip live requests that still depend on unresolved IDs or tokens rather than forcing fake placeholders.
   - Confirm MongoDB-backed CRUD behavior before frontend generation.
6. Recover from repeated failures.
   - If the same failure signature appears twice, stop extra loops and surface the exact remaining blocker.
   - Only hard-block frontend generation when the remaining backend bug count meets the configured blocking threshold.
   - If Windows install/startup throws `spawn EINVAL` or `ENOENT`, retry with a shell-backed launch for install commands.

## Inspirations used in this project

- Agentless: localization, repair, then validation.
- Auto Code Rover: retry with memory from earlier failed attempts.
- SWE-agent: trajectory-aware recovery and validation before claiming success.


