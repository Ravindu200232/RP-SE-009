# AI Website Builder Bug Memory

This project keeps recurring backend failures in memory so later runs can avoid duplicate bugs and recover faster.

## Known recurring backend bugs

- Gateway proxies must use `fixRequestBody` when `express.json()` runs before proxying.
- Gateway routes and service routes must keep singular/plural names aligned, such as `/api/tasks` and `/api/boards`.
- Backend JavaScript must be ASCII-safe in executable code. Remove corrupted tokens such as stray non-ASCII characters.
- Async Express handlers need `try/catch` and must return `{ success, data/error }`.
- The backend must be fully clean before frontend generation starts.
- Live validation must use real HTTP requests and real MongoDB writes, not only simulated route checks.
- Windows process startup may fail with `spawn EINVAL` or `ENOENT`; retry with a shell-backed launch for install commands.
- MongoDB creates collections after the first write unless the service explicitly creates them.
- Live sandbox validation must allocate unique ports for every generated service, not only two fixed service slots.
- Resource router literal routes such as `/health` must appear before parameterized routes like `/:id` to avoid route shadowing and `CastError`.
- Generated services should respect `process.env.MONGODB_URI` during live validation so each run uses an isolated database.
- Generated services and the live sandbox runner should accept both `process.env.MONGODB_URI` and `process.env.MONGO_URL`.
- Auth code should accept `process.env.JWT_SECRET`, `process.env.SECRET_KEY`, or `process.env.SEKRET_KEY` so sandbox secrets do not get missed by alias mismatches.
- Live execution plans must use real created IDs and auth tokens, and skip routes that cannot yet be exercised instead of forcing `missing-id`.
- Protected routes such as `/api/users/me`, `/api/auth/profile`, and `/api/auth/verify` must reuse the Bearer token captured from live register/login responses.
- GET routes that require query params, especially analytics date-range routes, must receive realistic sample query values during live validation.
- When gateway proxy prefixes exist, live route contracts must prefer the external `/api/...` path over internal service-only mounts like `/tasks`.
- If AI route simulation does not provide sample POST bodies, live validation must synthesize payloads from the service schema so required-field errors do not loop forever.
- Frontend collection state such as tasks/items/users/columns must be normalized to arrays before calling .map() or .filter(), because generated backends may return nested shapes like `{ data: { tasks: [...] } }`.
- Microservices should not rely on Mongoose `populate()` for models owned by another service.
- Auth sample payloads should include `username` when the schema has a unique username index.

## Repair strategy

- Round 1: fix every currently known backend bug in one pass.
- Round 1 should use the broad snapshot and aim to end the entire backend repair in that pass whenever possible.
- Rounds 2-5: recovery-only rounds for exact remaining failures.
- Rounds 2-5 should use focused snapshots around only the remaining failing routes/files instead of re-fixing the whole backend.
- If a failure repeats, rewrite the owning route file or gateway/service registration fully instead of shipping a small partial patch.
- Stop extra rounds when the backend is clean or the failure signature is unchanged, and report the exact blocking routes.

## Validation strategy

- Verify real status codes such as `200`, `201`, `400`, `404`, and `500`.
- Send sample POST/PUT/PATCH payloads through the gateway.
- Confirm create, read, update, and delete flows against MongoDB-backed routes.
- Block frontend generation if any backend route still fails.
- Only hard-block frontend generation when remaining backend route bugs reach the configured threshold; smaller residual counts should surface as warnings and continue.


