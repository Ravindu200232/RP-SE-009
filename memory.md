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



## Live Route Failures | 2026-04-18T07:43:56.609Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Runtime Failure | 2026-04-18T07:44:46.093Z
- auth-service exited before health check: (node:60764) [MONGODB DRIVER] Warning: useNewUrlParser is a deprecated option: useNewUrlParser has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
(Use `node --trace-warnings ...` to show where the warning was created)
(node:60764) [MONGODB DRIVER] Warning: useUnifiedTopology is a deprecated option: useUnifiedTopology has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3006
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\node_modules\express\lib\application.js:635:24)
    at Object.<anonymous> (E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\index.js:67:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3006
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T07:45:18.481Z
- auth-service exited before health check: node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3006
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\node_modules\express\lib\application.js:635:24)
    at E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\index.js:34:9
    at process.processTicksAndRejections (node:internal/process/task_queues:103:5)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3006
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js

Connected to MongoDB | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T07:45:41.249Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Runtime Failure | 2026-04-18T07:46:08.660Z
- auth-service exited before health check: node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3006
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\node_modules\express\lib\application.js:635:24)
    at E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\index.js:33:9
    at process.processTicksAndRejections (node:internal/process/task_queues:103:5)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3006
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js

Connected to MongoDB | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T07:46:25.239Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:46:50.755Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/api/auth/register: Expected HTTP 201 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/api/auth/login: Expected HTTP 200 but received 404
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:47:45.305Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Runtime Failure | 2026-04-18T07:48:12.011Z
- auth-service exited before health check: node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3006
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\node_modules\express\lib\application.js:635:24)
    at E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\index.js:33:9
    at process.processTicksAndRejections (node:internal/process/task_queues:103:5)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3006
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js

Connected to MongoDB | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T07:48:48.197Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:49:27.665Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:49:59.846Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:50:32.170Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Runtime Failure | 2026-04-18T07:51:18.087Z
- auth-service exited before health check: node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3006
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\node_modules\express\lib\application.js:635:24)
    at E:\final_research_agentic\output\quickbite-restaurant-ordering-system\backend\auth-service\index.js:33:9
    at process.processTicksAndRejections (node:internal/process/task_queues:103:5)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3006
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js

Auth service connected to MongoDB | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T07:51:34.641Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:52:08.137Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:52:45.268Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:53:24.713Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:53:54.382Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:54:25.520Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:54:58.906Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:55:39.674Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:56:13.372Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:56:49.346Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:57:20.448Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/api/auth/register: Expected HTTP 201 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/api/auth/login: Expected HTTP 200 but received 404
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:57:32.399Z
- GET /api/tasks/health: Expected HTTP 200 but received 404
- GET /columns/health: Expected HTTP 200 but received 404
- GET /api/users/health: Expected HTTP 200 but received 404
- GET /auth/health: Expected HTTP 200 but received 404
- GET /api/boards/health: Expected HTTP 200 but received 404
- GET /api/analytics/health: Expected HTTP 200 but received 404
- POST /api/tasks: Expected HTTP 201 but received 404
- POST /columns: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T07:57:50.049Z
- GET /api/d极速elivery/health: Expected HTTP 200 but received 404
- POST /api/auth/register: Internal server error
- POST /api/auth/login: Invalid credentials
- POST /api/payments: Internal server error
- POST /api/d极速elivery: Expected HTTP 201 but received 404
- POST /api/menu: Internal server error

## Live Route Failures | 2026-04-18T07:58:15.880Z
- GET /api/tasks/health: Expected HTTP 200 but received 404
- GET /columns/health: Expected HTTP 200 but received 404
- GET /api/users/health: Expected HTTP 200 but received 404
- GET /auth/health: Expected HTTP 200 but received 404
- GET /api/boards/health: Expected HTTP 200 but received 404
- GET /api/analytics/health: Expected HTTP 200 but received 404
- POST /api/tasks: Expected HTTP 201 but received 404
- POST /columns: Expected HTTP 201 but received 404

## Live Runtime Failure | 2026-04-18T07:58:17.360Z
- npm install failed in delivery-service:

## Live Route Failures | 2026-04-18T08:03:58.515Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33aee68373a177be24f76/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33aee68373a177be24f76: Quiz not found for this course
- GET /api/quizzes/69e33aee68373a177be24f76/results: No attempt found

## Live Route Failures | 2026-04-18T08:05:08.364Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33b3468373a177be24f7b/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33b3468373a177be24f7b: Quiz not found for this course
- GET /api/quizzes/69e33b3468373a177be24f7b/results: No attempt found

## Live Route Failures | 2026-04-18T08:06:17.784Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33b7968373a177be24f80/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33b7968373a177be24f80: Quiz not found for this course
- GET /api/quizzes/69e33b7968373a177be24f80/results: No attempt found

## Live Route Failures | 2026-04-18T08:07:07.882Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33bab68373a177be24f85/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33bab68373a177be24f85: Quiz not found for this course
- GET /api/quizzes/69e33bab68373a177be24f85/results: No attempt found

## Live Route Failures | 2026-04-18T08:08:03.503Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33be368373a177be24f8a/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33be368373a177be24f8a: Quiz not found for this course
- GET /api/quizzes/69e33be368373a177be24f8a/results: No attempt found

## Live Route Failures | 2026-04-18T08:09:00.959Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33c1c68373a177be24f8f/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33c1c68373a177be24f8f: Quiz not found for this course
- GET /api/quizzes/69e33c1c68373a177be24f8f/results: No attempt found

## Live Route Failures | 2026-04-18T08:10:01.439Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33c5968373a177be24f94/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33c5968373a177be24f94: Quiz not found for this course
- GET /api/quizzes/69e33c5968373a177be24f94/results: No attempt found

## Live Route Failures | 2026-04-18T08:10:55.357Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33c8f68373a177be24f99/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33c8f68373a177be24f99: Quiz not found for this course
- GET /api/quizzes/69e33c8f68373a177be24f99/results: No attempt found

## Live Route Failures | 2026-04-18T08:11:58.273Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33cce68373a177be24f9e/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33cce68373a177be24f9e: Quiz not found for this course
- GET /api/quizzes/69e33cce68373a177be24f9e/results: No attempt found

## Live Route Failures | 2026-04-18T08:12:42.914Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33cfa68373a177be24fa3/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33cfa68373a177be24fa3: Quiz not found for this course
- GET /api/quizzes/69e33cfa68373a177be24fa3/results: No attempt found

## Live Route Failures | 2026-04-18T08:13:46.462Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33d3a68373a177be24fa8/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33d3a68373a177be24fa8: Quiz not found for this course
- GET /api/quizzes/69e33d3a68373a177be24fa8/results: No attempt found

## Live Route Failures | 2026-04-18T08:14:37.457Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33d6d68373a177be24fad/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33d6d68373a177be24fad: Quiz not found for this course
- GET /api/quizzes/69e33d6d68373a177be24fad/results: No attempt found

## Live Route Failures | 2026-04-18T08:15:34.564Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33da668373a177be24fb2/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33da668373a177be24fb2: Quiz not found for this course
- GET /api/quizzes/69e33da668373a177be24fb2/results: No attempt found

## Live Route Failures | 2026-04-18T08:16:29.865Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33ddd68373a177be24fb7/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33ddd68373a177be24fb7: Quiz not found for this course
- GET /api/quizzes/69e33ddd68373a177be24fb7/results: No attempt found

## Live Route Failures | 2026-04-18T08:17:22.473Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33e1268373a177be24fbc/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33e1268373a177be24fbc: Quiz not found for this course
- GET /api/quizzes/69e33e1268373a177be24fbc/results: No attempt found

## Live Route Failures | 2026-04-18T08:22:28.042Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes: Quiz validation failed: title: Path `title` is required.

## Live Route Failures | 2026-04-18T08:23:00.039Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33f6368373a177be24fc2/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33f6368373a177be24fc2: Quiz not found for this course
- GET /api/quizzes/69e33f6368373a177be24fc2/results: No attempt found

## Live Route Failures | 2026-04-18T08:23:11.956Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes: Quiz validation failed: title: Path `title` is required.

## Live Route Failures | 2026-04-18T08:23:51.946Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33f9768373a177be24fc8/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33f9768373a177be24fc8: Quiz not found for this course
- GET /api/quizzes/69e33f9768373a177be24fc8/results: No attempt found

## Live Route Failures | 2026-04-18T08:23:59.977Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33f9f68373a177be24fcd/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33f9f68373a177be24fcd: Quiz not found for this course
- GET /api/quizzes/69e33f9f68373a177be24fcd/results: No attempt found

## Live Route Failures | 2026-04-18T08:24:53.821Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33fd568373a177be24fd2/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33fd568373a177be24fd2: Quiz not found for this course
- GET /api/quizzes/69e33fd568373a177be24fd2/results: No attempt found

## Live Route Failures | 2026-04-18T08:25:08.032Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e33fe368373a177be24fd7/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e33fe368373a177be24fd7: Quiz not found for this course
- GET /api/quizzes/69e33fe368373a177be24fd7/results: No attempt found

## Live Route Failures | 2026-04-18T08:25:51.630Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e3400f68373a177be24fdc/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e3400f68373a177be24fdc: Quiz not found for this course
- GET /api/quizzes/69e3400f68373a177be24fdc/results: No attempt found

## Live Route Failures | 2026-04-18T08:26:04.345Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e3401c68373a177be24fe1/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e3401c68373a177be24fe1: Quiz not found for this course
- GET /api/quizzes/69e3401c68373a177be24fe1/results: No attempt found

## Live Route Failures | 2026-04-18T08:26:39.220Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e3403f68373a177be24fe6/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e3403f68373a177be24fe6: Quiz not found for this course
- GET /api/quizzes/69e3403f68373a177be24fe6/results: No attempt found

## Live Route Failures | 2026-04-18T08:27:05.900Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- GET /api/quizzes/course/69e3405968373a177be24feb: Quiz not found for this course
- GET /api/quizzes/69e3405968373a177be24feb/results: No attempt found

## Live Route Failures | 2026-04-18T08:27:26.309Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes/69e3406e68373a177be24fef/submit: Cannot read properties of undefined (reading 'forEach')
- GET /api/quizzes/course/69e3406e68373a177be24fef: Quiz not found for this course
- GET /api/quizzes/69e3406e68373a177be24fef/results: No attempt found

## Live Route Failures | 2026-04-18T08:27:57.632Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:28:08.461Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:28:35.988Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:29:17.056Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:30:24.004Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:30:48.753Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:31:32.246Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:31:38.409Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:32:25.126Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:32:28.484Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:33:02.885Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:33:33.847Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:33:42.363Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:34:30.028Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:34:58.323Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:35:59.109Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:36:14.600Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:36:42.974Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:37:08.027Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Runtime Failure | 2026-04-18T08:38:50.915Z
- lesson-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\lesson-service\\index.js'
  ]
}

Node.js v22.22.2

## Live Route Failures | 2026-04-18T08:38:57.335Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:39:06.839Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:39:26.541Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:39:31.818Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:40:05.672Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:40:12.315Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:40:46.343Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:40:55.303Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:41:31.653Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:41:46.889Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:42:17.385Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:42:25.647Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: bcrypt is not defined
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Runtime Failure | 2026-04-18T08:42:38.317Z
- api-gateway exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\api-gateway\\index.js'
  ]
}

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:42:46.634Z
- lesson-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\lesson-service\\index.js'
  ]
}

Node.js v22.22.2

## Live Runtime Failure | 2026-04-18T08:42:59.377Z
- course-service exited before health check: (node:1552) [MONGODB DRIVER] Warning: useNewUrlParser is a deprecated option: useNewUrlParser has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
(Use `node --trace-warnings ...` to show where the warning was created)
(node:1552) [MONGODB DRIVER] Warning: useUnifiedTopology is a deprecated option: useUnifiedTopology has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3007
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\node_modules\express\lib\application.js:635:24)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:27:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3007
}

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T08:43:09.599Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes: Only instructors can create quizzes
- PUT /api/auth/profile: fetch failed
- GET /api/courses: fetch failed
- POST /api/courses: fetch failed
- POST /api/enrollments: fetch failed
- GET /api/enrollments/my: fetch failed

## Live Route Failures | 2026-04-18T08:43:14.923Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T08:43:28.109Z
- npm install failed in auth-service: npm error code ENOTEMPTY
npm error syscall rmdir
npm error path E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\object-inspect\test
npm error errno -4051
npm error ENOTEMPTY: directory not empty, rmdir 'E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\object-inspect\test'
npm error A complete log of this run can be found in: C:\Users\ravin\AppData\Local\npm-cache\_logs\2026-04-18T08_43_25_794Z-debug-0.log

## Live Runtime Failure | 2026-04-18T08:43:29.574Z
- spawn C:\WINDOWS\system32\cmd.exe ENOENT

## Live Runtime Failure | 2026-04-18T08:43:30.713Z
- auth-service exited before health check: node:internal/modules/cjs/loader:510
      throw err;
      ^

Error: Cannot find module 'E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\object-inspect\index.js'. Please verify that the package.json has a valid "main" entry
    at tryPackage (node:internal/modules/cjs/loader:502:19)
    at Function._findPath (node:internal/modules/cjs/loader:764:18)
    at Function._resolveFilename (node:internal/modules/cjs/loader:1369:27)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16) {
  code: 'MODULE_NOT_FOUND',
  path: '\\\\?\\E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\node_modules\\object-inspect\\package.json',
  requestPath: 'object-inspect'
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:43:57.873Z
- course-service exited before health check: (node:3816) [MONGODB DRIVER] Warning: useNewUrlParser is a deprecated option: useNewUrlParser has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
(Use `node --trace-warnings ...` to show where the warning was created)
(node:3816) [MONGODB DRIVER] Warning: useUnifiedTopology is a deprecated option: useUnifiedTopology has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3007
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\node_modules\express\lib\application.js:635:24)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:35:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3007
}

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:44:02.840Z
- Cannot start lesson-service: missing entry file E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js

## Live Route Failures | 2026-04-18T08:44:09.611Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T08:44:24.374Z
- auth-service exited before health check: node:internal/modules/cjs/loader:510
      throw err;
      ^

Error: Cannot find module 'E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\debug\src\index.js'. Please verify that the package.json has a valid "main" entry
    at tryPackage (node:internal/modules/cjs/loader:502:19)
    at Function._findPath (node:internal/modules/cjs/loader:764:18)
    at Function._resolveFilename (node:internal/modules/cjs/loader:1369:27)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16) {
  code: 'MODULE_NOT_FOUND',
  path: '\\\\?\\E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\node_modules\\debug\\package.json',
  requestPath: 'debug'
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:44:32.169Z
- auth-service exited before health check: (node:35076) [MONGODB DRIVER] Warning: useNewUrlParser is a deprecated option: useNewUrlParser has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
(Use `node --trace-warnings ...` to show where the warning was created)
(node:35076) [MONGODB DRIVER] Warning: useUnifiedTopology is a deprecated option: useUnifiedTopology has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3006
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\express\lib\application.js:635:24)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:35:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3006
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T08:44:34.089Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T08:45:00.776Z
- lesson-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\lesson-service\\index.js'
  ]
}

Node.js v22.22.2

## Live Runtime Failure | 2026-04-18T08:45:04.516Z
- auth-service exited before health check: (node:83364) [MONGODB DRIVER] Warning: useNewUrlParser is a deprecated option: useNewUrlParser has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
(Use `node --trace-warnings ...` to show where the warning was created)
(node:83364) [MONGODB DRIVER] Warning: useUnifiedTopology is a deprecated option: useUnifiedTopology has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3006
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\express\lib\application.js:635:24)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:27:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3006
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:45:06.634Z
- api-gateway exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:64
server.on('error', (error) => {
^

ReferenceError: server is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:64:1)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js

[HPM] Proxy created: /  -> http://127.0.0.1:3006
[HPM] Proxy created: /  -> http://127.0.0.1:3007
[HPM] Proxy created: /  -> http://127.0.0.1:3008
[HPM] Proxy created: /  -> http://127.0.0.1:3009
[HPM] Proxy created: /  -> http://127.0.0.1:3009 | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:45:30.218Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:6:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:45:46.366Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:27:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:45:46.444Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:27:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:46:14.181Z
- course-service exited before health check: (node:61240) [MONGODB DRIVER] Warning: useNewUrlParser is a deprecated option: useNewUrlParser has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
(Use `node --trace-warnings ...` to show where the warning was created)
(node:61240) [MONGODB DRIVER] Warning: useUnifiedTopology is a deprecated option: useUnifiedTopology has no effect since Node.js Driver version 4.0.0 and will be removed in the next major version
node:events:497
      throw er; // Unhandled 'error' event
      ^

Error: listen EADDRINUSE: address already in use :::3007
    at Server.setupListenHandle [as _listen2] (node:net:1940:16)
    at listenInCluster (node:net:1997:12)
    at Server.listen (node:net:2102:7)
    at Function.listen (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\node_modules\express\lib\application.js:635:24)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:35:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
Emitted 'error' event on Server instance at:
    at emitErrorNT (node:net:1976:8)
    at process.processTicksAndRejections (node:internal/process/task_queues:89:21) {
  code: 'EADDRINUSE',
  errno: -4091,
  syscall: 'listen',
  address: '::',
  port: 3007
}

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:46:17.947Z
- api-gateway exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\api-gateway\\index.js'
  ]
}

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:46:25.957Z
- auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:43
server.on('error', (error) => {
^

ReferenceError: server is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:43:1)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T08:46:37.259Z
- spawn C:\WINDOWS\system32\cmd.exe ENOENT

## Live Runtime Failure | 2026-04-18T08:46:40.201Z
- lesson-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\lesson-service\\index.js'
  ]
}

Node.js v22.22.2

## Live Runtime Failure | 2026-04-18T08:47:05.226Z
- Cannot start lesson-service: missing entry file E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js

## Live Runtime Failure | 2026-04-18T08:47:19.604Z
- auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:44
server.on('error', (error) => {
^

ReferenceError: server is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:44:1)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T08:47:51.214Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T08:47:55.509Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404

## Live Runtime Failure | 2026-04-18T08:48:08.959Z
- spawn C:\WINDOWS\system32\cmd.exe ENOENT

## Live Runtime Failure | 2026-04-18T08:48:51.975Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:19:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T08:49:46.609Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T08:50:10.030Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:27:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T08:51:10.298Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: Registration failed
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T08:51:36.162Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:27:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T08:52:33.447Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T08:52:59.174Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:27:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T08:53:40.789Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T08:54:10.823Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:27:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T08:54:59.513Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable
- GET /api/courses: Expected HTTP 200 but received 404
- POST /api/courses: Expected HTTP 201 but received 404
- POST /api/enrollments: Expected HTTP 201 but received 404
- GET /api/enrollments/my: Expected HTTP 200 but received 404

## Live Runtime Failure | 2026-04-18T08:55:35.473Z
- Cannot start lesson-service: missing entry file E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js

## Live Runtime Failure | 2026-04-18T08:56:18.512Z
- Cannot start enrollment-service: missing entry file E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js

## Live Runtime Failure | 2026-04-18T08:56:57.563Z
- Cannot start quiz-service: missing entry file E:\final_research_agentic\output\learnhub-learning-management-system\backend\quiz-service\index.js

## Live Route Failures | 2026-04-18T08:57:49.193Z
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials

## Live Route Failures | 2026-04-18T08:58:22.009Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T08:58:48.042Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T08:59:15.225Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T08:59:40.759Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:00:24.851Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:00:54.593Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:01:23.589Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:01:57.547Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:02:28.056Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:02:56.574Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:03:25.898Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:03:47.758Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:04:25.654Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:04:51.353Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:05:30.868Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:06:01.318Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:06:25.936Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:06:50.599Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:07:14.965Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:07:47.125Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T09:08:09.510Z
- spawn C:\WINDOWS\system32\cmd.exe ENOENT

## Live Runtime Failure | 2026-04-18T09:08:12.969Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:27:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T09:08:45.342Z
- spawn C:\WINDOWS\system32\cmd.exe ENOENT

## Live Runtime Failure | 2026-04-18T09:08:55.497Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:24:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T09:09:22.548Z
- spawn C:\WINDOWS\system32\cmd.exe ENOENT

## Live Runtime Failure | 2026-04-18T09:09:33.216Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module '../models/User'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\routes\authRoutes.js
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\routes\authRoutes.js:4:14)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\routes\\authRoutes.js',
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Remaining Route Failures | 2026-04-18T09:09:41.259Z
- GET /health: spawn C:\WINDOWS\system32\cmd.exe ENOENT

## Live Route Failures | 2026-04-18T09:10:10.534Z
- GET /api/lessons/health: Expected HTTP 200 but received 404
- GET /api/quizzes/health: Expected HTTP 200 but received 404
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Expected HTTP 201 but received 404
- POST /api/quizzes: Expected HTTP 201 but received 404

## Live Route Failures | 2026-04-18T09:10:44.971Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:11:09.348Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:11:33.535Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:11:57.478Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:12:21.697Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:12:47.872Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:13:14.066Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:13:57.103Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:14:22.950Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:14:56.824Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:15:21.963Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:15:57.109Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:16:22.880Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:16:47.986Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T09:17:08.499Z
- npm install failed in auth-service: npm error code ENOTEMPTY
npm error syscall rmdir
npm error path E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongodb\src
npm error errno -4051
npm error ENOTEMPTY: directory not empty, rmdir 'E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongodb\src'
npm error A complete log of this run can be found in: C:\Users\ravin\AppData\Local\npm-cache\_logs\2026-04-18T09_17_06_269Z-debug-0.log

## Live Route Failures | 2026-04-18T09:17:16.769Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T09:17:29.699Z
- npm install failed in api-gateway: npm error code EJSONPARSE
npm error path E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway/package.json
npm error JSON.parse Unexpected non-whitespace character after JSON at position 330 (line 16 column 4) while parsing near "...\": \"^16.0.0\"\n  }\n}  \"devDependencies\": {..."
npm error JSON.parse Failed to parse JSON data.
npm error JSON.parse Note: package.json must be actual JSON, not just JavaScript.
npm error A complete log of this run can be found in: C:\Users\ravin\AppData\Local\npm-cache\_logs\2026-04-18T09_17_29_061Z-debug-0.log

## Live Runtime Failure | 2026-04-18T09:17:33.333Z
- npm install failed in api-gateway: npm error code EJSONPARSE
npm error path E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway/package.json
npm error JSON.parse Unexpected non-whitespace character after JSON at position 330 (line 16 column 4) while parsing near "...\": \"^16.0.0\"\n  }\n}  \"devDependencies\": {..."
npm error JSON.parse Failed to parse JSON data.
npm error JSON.parse Note: package.json must be actual JSON, not just JavaScript.
npm error A complete log of this run can be found in: C:\Users\ravin\AppData\Local\npm-cache\_logs\2026-04-18T09_17_32_879Z-debug-0.log

## Live Runtime Failure | 2026-04-18T09:17:49.082Z
- api-gateway exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\api-gateway\\index.js'
  ]
}

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T09:18:09.402Z
- course-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\index.js'
  ]
}

Node.js v22.22.2

## Remaining Route Failures | 2026-04-18T09:18:19.884Z
- No exact failing route details were captured.

## Live Route Failures | 2026-04-18T09:18:24.013Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:19:00.463Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:19:34.873Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:20:17.332Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:21:00.967Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:21:32.286Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:21:57.941Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:22:23.751Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:22:49.892Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:23:24.859Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:23:50.893Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:24:19.956Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:24:52.323Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:25:24.743Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:26:11.048Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:26:39.626Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:27:06.723Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:27:37.902Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:28:13.354Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:28:37.812Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:29:09.271Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:29:45.756Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:30:11.185Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T09:30:34.283Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T09:30:48.559Z
- course-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\index.js'
  ]
}

Node.js v22.22.2

## Remaining Route Failures | 2026-04-18T09:30:58.857Z
- No exact failing route details were captured.

## Live Route Failures | 2026-04-18T09:31:10.182Z
- GET /api/lessons/health: downstream service unavailable
- GET /api/quizzes/health: downstream service unavailable
- POST /api/auth/register: Invalid role
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: downstream service unavailable
- POST /api/quizzes: downstream service unavailable

## Live Route Failures | 2026-04-18T09:31:46.935Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:32:21.529Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:32:59.710Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Route Failures | 2026-04-18T09:35:38.078Z
- GET /api/lessons/health: Lesson service unavailable
- GET /api/quizzes/health: Quiz service unavailable
- POST /api/auth/register: User validation failed: role: `customer` is not a valid enum value for path `role`.
- POST /api/auth/login: Invalid credentials
- POST /api/lessons: Lesson service unavailable
- POST /api/quizzes: Quiz service unavailable

## Live Runtime Failure | 2026-04-18T10:10:25.059Z
- auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:7
app.use(cors());
    ^

ReferenceError: cors is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:7:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T10:11:42.461Z
- course-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:5
app.use(cors());
    ^

ReferenceError: cors is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:5:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T10:12:29.603Z
- course-service exited before health check: > course-service@1.0.0 start
> node index.js | exit=0 | service failed to start

## Live Runtime Failure | 2026-04-18T10:13:20.991Z
- enrollment-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:5
app.use(cors());
    ^

ReferenceError: cors is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:5:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > enrollment-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T10:14:11.128Z
- lesson-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:5
app.use(cors());
    ^

ReferenceError: cors is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:5:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > lesson-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T10:15:10.023Z
- quiz-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\quiz-service\index.js:5
app.use(cors());
    ^

ReferenceError: cors is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\quiz-service\index.js:5:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > quiz-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T10:18:39.527Z
- api-gateway exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:5
app.use(cors());
    ^

ReferenceError: cors is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:5:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T10:21:24.123Z
- api-gateway exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:5
app.use(cors());
    ^

ReferenceError: cors is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:5:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js | exit=1 | service failed to start

## Remaining Route Failures | 2026-04-18T10:22:16.543Z
- GET /health: api-gateway exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:5
app.use(cors());
    ^

ReferenceError: cors is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:5:5)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T10:22:30.321Z
- checkin-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './models/Reservation'
Require stack:
- E:\final_research_agentic\output\stayease-hotel-booking-system\backend\checkin-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\stayease-hotel-booking-system\backend\checkin-service\index.js:4:21)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\stayease-hotel-booking-system\\backend\\checkin-service\\index.js'
  ]
}

Node.js v22.22.2 | > checkin-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T10:23:45.404Z
- checkin-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './models/Reservation'
Require stack:
- E:\final_research_agentic\output\stayease-hotel-booking-system\backend\checkin-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\stayease-hotel-booking-system\backend\checkin-service\index.js:4:21)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\stayease-hotel-booking-system\\backend\\checkin-service\\index.js'
  ]
}

Node.js v22.22.2 | > checkin-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-18T10:24:58.669Z
- GET /api/rooms/health: Server error
- GET /api/reservations/health: Server error
- GET /api/checkin/health: Expected HTTP 200 but received 404
- GET /api/checkout/health: Expected HTTP 200 but received 404
- POST /api/reservations: Server error
- POST /api/checkin: Invalid user ID
- POST /api/checkout: Invalid user ID
- POST /api/payments/69e35bfa527e76dbe4c7fa53/refund: Expected HTTP 201 but received 200

## Backend Validation Failures | 2026-04-18T10:25:09.315Z
- /checkin-service/index.js: missing local require ./models/Reservation

## Live Runtime Failure | 2026-04-18T10:48:09.614Z
- Received status 404 from http://127.0.0.1:3006/health

## Live Runtime Failure | 2026-04-18T10:52:22.287Z
- Received status 404 from http://127.0.0.1:3006/health

## Live Runtime Failure | 2026-04-18T10:53:50.638Z
- Received status 404 from http://127.0.0.1:3006/health

## Remaining Route Failures | 2026-04-18T10:56:12.552Z
- GET /health: Received status 404 from http://127.0.0.1:3006/health

## Live Runtime Failure | 2026-04-18T11:24:09.812Z
- api-gateway exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './auth/routes'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:5:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\api-gateway\\index.js'
  ]
}

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T11:25:26.828Z
- api-gateway exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './auth/routes'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:5:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\api-gateway\\index.js'
  ]
}

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js | exit=1 | service failed to start

## Backend Validation Failures | 2026-04-18T11:25:42.486Z
- Missing package.json for backend service: auth
- Missing index.js for backend service: auth
- Missing package.json for backend service: course
- Missing index.js for backend service: course
- Missing package.json for backend service: enrollment
- Missing index.js for backend service: enrollment
- Missing package.json for backend service: learning
- Missing index.js for backend service: learning

## Live Route Failures | 2026-04-18T11:31:07.510Z
- GET /api/lessons/health: Server error
- POST /api/lessons: All fields are required
- POST /api/quizzes: All fields are required
- GET /api/auth/me: Server error
- PUT /api/auth/profile: Email is required
- POST /api/courses: All fields are required
- POST /api/enrollments: Student ID and Course ID are required
- GET /api/enrollments/my: Server error

## Live Route Failures | 2026-04-18T11:35:31.000Z
- GET /api/auth/health: Expected HTTP 200 but received 404
- GET /api/lessons/health: Server error
- GET /api/quizzes/health: Expected HTTP 200 but received 404
- POST /api/lessons: All fields are required
- POST /api/quizzes: Expected HTTP 201 but received 404
- GET /api/auth/me: Server error
- PUT /api/auth/profile: Email is required
- POST /api/courses: All fields are required

## Remaining Route Failures | 2026-04-18T11:35:39.916Z
- GET /api/lessons/health: Server error
- POST /api/lessons: All fields are required
- POST /api/quizzes: All fields are required
- GET /api/auth/me: Server error
- PUT /api/auth/profile: Email is required
- POST /api/courses: All fields are required
- POST /api/enrollments: Student ID and Course ID are required
- GET /api/enrollments/my: Server error

## Live Runtime Failure | 2026-04-18T11:42:17.310Z
- auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:53
app.get('/api/auth/me', authMiddleware, async (req, res) => {
                        ^

ReferenceError: Cannot access 'authMiddleware' before initialization
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:53:25)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T11:43:33.364Z
- auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:53
app.get('/api/auth/me', authMiddleware, async (req, res) => {
                        ^

ReferenceError: Cannot access 'authMiddleware' before initialization
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:53:25)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T11:44:36.637Z
- course-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:36
app.post('/api/courses', authMiddleware, async (req, res) => {
                         ^

ReferenceError: Cannot access 'authMiddleware' before initialization
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:36:26)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Remaining Route Failures | 2026-04-18T11:45:18.357Z
- GET /health: course-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:36
app.post('/api/courses', authMiddleware, async (req, res) => {
                         ^

ReferenceError: Cannot access 'authMiddleware' before initialization
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:36:26)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T12:35:11.264Z
- auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:99
app.listen(PORT, () => console.log(`Auth Service listening on port ${port}`));
                                                                     ^

ReferenceError: port is not defined
    at Server.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:99:70)
    at Object.onceWrapper (node:events:633:28)
    at Server.emit (node:events:531:35)
    at emitListeningNT (node:net:1983:10)
    at process.processTicksAndRejections (node:internal/process/task_queues:88:21)

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T12:36:20.728Z
- course-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\index.js'
  ]
}

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T12:37:01.007Z
- enrollment-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\index.js'
  ]
}

Node.js v22.22.2 | > enrollment-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T12:37:40.860Z
- course-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'cors'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:1:14)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\index.js'
  ]
}

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T12:38:17.423Z
- enrollment-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\index.js'
  ]
}

Node.js v22.22.2 | > enrollment-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T12:39:05.013Z
- api-gateway exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:60
app.listen(port, () => console.log(`API Gateway listening on port ${port}`));
           ^

ReferenceError: port is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:60:12)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > api-gateway@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T12:40:10.468Z
- course-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'cors'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js:1:14)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\index.js'
  ]
}

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T12:40:49.888Z
- enrollment-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\index.js'
  ]
}

Node.js v22.22.2 | > enrollment-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Backend Validation Failures | 2026-04-18T12:41:07.322Z
- /learning-service/routes/lessons.js: route shadowing — '/course/:id' defined after parameterized '/:id'; move literal routes before /:param routes

## Remaining Route Failures | 2026-04-18T12:41:07.345Z
- GET /health: enrollment-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'express'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:1:17)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\index.js'
  ]
}

Node.js v22.22.2 | > enrollment-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## App Build Plan | 2026-04-18T13:08:32.395Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-18T13:11:48.964Z
- api-gateway exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:67
```json
   ^^^^

SyntaxError: Unexpected identifier 'json'
    at wrapSafe (node:internal/modules/cjs/loader:1637:18)
    at Module._compile (node:internal/modules/cjs/loader:1679:20)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2

## Live Runtime Failure | 2026-04-18T13:12:15.171Z
- api-gateway exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:67
```json
   ^^^^

SyntaxError: Unexpected identifier 'json'
    at wrapSafe (node:internal/modules/cjs/loader:1637:18)
    at Module._compile (node:internal/modules/cjs/loader:1679:20)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2

## Backend Validation Failures | 2026-04-18T13:12:36.659Z
- Missing package.json in generated backend output

## Remaining Route Failures | 2026-04-18T13:12:36.669Z
- GET /health: api-gateway exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\api-gateway\index.js:67
```json
   ^^^^

SyntaxError: Unexpected identifier 'json'
    at wrapSafe (node:internal/modules/cjs/loader:1637:18)
    at Module._compile (node:internal/modules/cjs/loader:1679:20)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2

## App Build Plan | 2026-04-18T13:23:37.218Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-18T13:29:30.261Z
- enrollment-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:39
app.get('/api/enrollments/my', auth, async (req, res) => {
                               ^

ReferenceError: auth is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:39:32)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > enrollment-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-18T13:30:39.867Z
- lesson-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:30
app.get('/api/lessons/course/:id', auth, async (req, res) => {
                                   ^

ReferenceError: auth is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:30:36)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > lesson-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Remaining Route Failures | 2026-04-18T13:31:07.639Z
- GET /health: lesson-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:30
app.get('/api/lessons/course/:id', auth, async (req, res) => {
                                   ^

ReferenceError: auth is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:30:36)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > lesson-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## App Build Plan | 2026-04-19T05:09:32.015Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-19T05:13:39.427Z
- auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:86
app.listen(PORT, () => console.log('Auth Service is running on port 5001'));
           ^

ReferenceError: PORT is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:86:12)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## App Build Plan | 2026-04-19T05:18:39.068Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Route Failures | 2026-04-19T05:27:41.050Z
- GET /api/auth/health: downstream service unavailable
- GET /api/lessons/health: downstream service unavailable
- GET /api/quizzes/health: downstream service unavailable
- POST /api/auth/register: downstream service unavailable
- POST /api/auth/login: downstream service unavailable
- POST /api/lessons: downstream service unavailable
- POST /api/quizzes: downstream service unavailable

## Backend Validation Failures | 2026-04-19T05:27:46.024Z
- Missing package.json for backend service: auth-service
- Missing package.json for backend service: course-service
- Missing package.json for backend service: enrollment-service
- Missing package.json for backend service: lesson-service
- Missing package.json for backend service: quiz-service
- /auth-service/index.js: missing package dependency express in /auth-service/package.json
- /auth-service/index.js: missing package dependency cors in /auth-service/package.json
- /auth-service/index.js: missing package dependency body-parser in /auth-service/package.json

## App Build Plan | 2026-04-19T05:36:12.307Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-19T05:44:30.185Z
- course-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './models/Course'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\routes\courses.js
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\routes\courses.js:4:16)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\routes\\courses.js',
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\index.js'
  ]
}

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-19T05:47:05.006Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/quizzes: fetch failed

## Backend Validation Failures | 2026-04-19T05:47:15.348Z
- /course-service/index.js: missing local require ../middleware/auth
- /course-service/routes/courses.js: missing local require ./models/Course

## App Build Plan | 2026-04-19T05:49:43.856Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-19T05:58:00.851Z
- course-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'jsonwebtoken'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\middleware\auth.js
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\middleware\auth.js:1:13)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\middleware\\auth.js',
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\index.js'
  ]
}

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-19T06:00:13.741Z
- course-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module 'jsonwebtoken'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\middleware\auth.js
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\course-service\middleware\auth.js:1:13)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\middleware\\auth.js',
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\course-service\\index.js'
  ]
}

Node.js v22.22.2 | > course-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Backend Validation Failures | 2026-04-19T06:00:46.365Z
- /course-service/routes/courses.js: missing local require ../../models/Course
- /quiz-service/index.js: entry file uses app.* without declaring const app = express()
- /course-service/middleware/auth.js: missing package dependency jsonwebtoken in /course-service/package.json
- /lesson-service/middleware/auth.js: missing package dependency jsonwebtoken in /lesson-service/package.json
- /quiz-service/middleware/auth.js: missing package dependency jsonwebtoken in /quiz-service/package.json

## App Build Plan | 2026-04-19T06:05:11.596Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-19T06:12:13.518Z
- lesson-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:11
app.get('/health', (req, res) => {
^

ReferenceError: app is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:11:1)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > lesson-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-19T06:13:32.672Z
- lesson-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:11
app.get('/health', (req, res) => {
^

ReferenceError: app is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:11:1)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | > lesson-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Backend Validation Failures | 2026-04-19T06:13:48.068Z
- /lesson-service/index.js: entry file uses app.* without declaring const app = express()
- /quiz-service/index.js: entry file uses app.* without declaring const app = express()

## App Build Plan | 2026-04-19T06:16:02.640Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Route Failures | 2026-04-19T06:23:55.432Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/quizzes: fetch failed

## Live Route Failures | 2026-04-19T06:27:15.176Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/quizzes: fetch failed

## Live Route Failures | 2026-04-19T06:30:35.031Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/quizzes: fetch failed

## Live Route Failures | 2026-04-19T06:34:04.228Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/quizzes: fetch failed

## Remaining Route Failures | 2026-04-19T06:35:44.485Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/quizzes: fetch failed

## App Build Plan | 2026-04-19T07:02:48.385Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Route Failures | 2026-04-19T07:10:13.404Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/quizzes: fetch failed

## App Build Plan | 2026-04-19T07:14:08.361Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-19T07:20:45.879Z
- lesson-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/lessons'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:3:16)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\lesson-service\\index.js'
  ]
}

Node.js v22.22.2 | > lesson-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Route Failures | 2026-04-19T07:24:07.079Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/lessons/000000000000000000000001/complete: fetch failed
- POST /api/quizzes: fetch failed
- POST /api/quizzes/000000000000000000000001/submit: fetch failed
- GET /api/auth/me: Expected HTTP 200 but received 404
- PUT /api/auth/profile: fetch failed

## Remaining Route Failures | 2026-04-19T07:24:16.641Z
- GET /health: lesson-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/lessons'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\lesson-service\index.js:3:16)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\lesson-service\\index.js'
  ]
}

Node.js v22.22.2 | > lesson-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## App Build Plan | 2026-04-19T07:28:36.980Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Route Failures | 2026-04-19T07:37:28.355Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/lessons/000000000000000000000001/complete: fetch failed
- POST /api/quizzes: fetch failed
- POST /api/quizzes/000000000000000000000001/submit: fetch failed
- GET /api/auth/me: Expected HTTP 200 but received 404
- PUT /api/auth/profile: fetch failed

## Live Route Failures | 2026-04-19T07:42:39.673Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/lessons/000000000000000000000001/complete: fetch failed
- POST /api/quizzes: fetch failed
- POST /api/quizzes/000000000000000000000001/submit: fetch failed
- GET /api/auth/me: Expected HTTP 200 but received 404
- PUT /api/auth/profile: fetch failed

## Live Route Failures | 2026-04-19T07:47:41.568Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/lessons/000000000000000000000001/complete: fetch failed
- POST /api/quizzes: fetch failed
- POST /api/quizzes/000000000000000000000001/submit: fetch failed
- GET /api/auth/me: Expected HTTP 200 but received 404
- PUT /api/auth/profile: fetch failed

## App Build Plan | 2026-04-19T07:49:54.992Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-19T07:57:50.511Z
- enrollment-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:12
router.use('/api/enrollments', enrollments);
                               ^

ReferenceError: enrollments is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:12:32)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | exit=1 | service failed to start

## Live Route Failures | 2026-04-19T08:01:07.821Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/lessons/000000000000000000000001/complete: fetch failed
- POST /api/quizzes: fetch failed
- POST /api/quizzes/000000000000000000000001/submit: fetch failed
- GET /api/auth/me: Expected HTTP 200 but received 404
- PUT /api/auth/profile: fetch failed

## Remaining Route Failures | 2026-04-19T08:01:18.151Z
- GET /health: enrollment-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:12
router.use('/api/enrollments', enrollments);
                               ^

ReferenceError: enrollments is not defined
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js:12:32)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Function.executeUserEntryPoint [as runMain] (node:internal/modules/run_main:171:5)
    at node:internal/main/run_main_module:36:49

Node.js v22.22.2 | exit=1 | service failed to start

## App Build Plan | 2026-04-19T09:54:06.308Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Route Failures | 2026-04-19T10:03:55.371Z
- POST /api/auth/register: fetch failed
- POST /api/auth/login: fetch failed
- POST /api/lessons: fetch failed
- POST /api/lessons/000000000000000000000001/complete: fetch failed
- POST /api/quizzes: fetch failed
- POST /api/quizzes/000000000000000000000001/submit: fetch failed
- GET /api/auth/me: Expected HTTP 200 but received 404
- PUT /api/auth/profile: fetch failed

## App Build Plan | 2026-04-19T10:09:49.607Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## App Build Plan | 2026-04-19T10:34:56.869Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-19T10:43:54.036Z
- auth-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module './routes/auth'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\index.js:10:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\auth-service\\index.js'
  ]
}

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-19T10:45:15.391Z
- enrollment-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module '../config/default.json'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\middleware\auth.js
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\routes\enrollments.js
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\middleware\auth.js:2:16)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\middleware\\auth.js',
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\routes\\enrollments.js',
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\index.js'
  ]
}

Node.js v22.22.2 | exit=1 | service failed to start

## Backend Validation Failures | 2026-04-19T10:45:57.660Z
- /enrollment-service/middleware/auth.js: missing local require ../config/default.json

## App Build Plan | 2026-04-19T10:50:07.533Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-19T10:59:26.372Z
- enrollment-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module '../../models/Enrollment'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\routes\enrollments.js
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\routes\enrollments.js:8:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\routes\\enrollments.js',
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\index.js'
  ]
}

Node.js v22.22.2 | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-19T11:00:53.572Z
- enrollment-service exited before health check: node:internal/modules/cjs/loader:1386
  throw err;
  ^

Error: Cannot find module '../../models/Enrollment'
Require stack:
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\routes\enrollments.js
- E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\index.js
    at Function._resolveFilename (node:internal/modules/cjs/loader:1383:15)
    at defaultResolveImpl (node:internal/modules/cjs/loader:1025:19)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1030:22)
    at Function._load (node:internal/modules/cjs/loader:1192:37)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)
    at wrapModuleLoad (node:internal/modules/cjs/loader:237:24)
    at Module.require (node:internal/modules/cjs/loader:1463:12)
    at require (node:internal/modules/helpers:147:16)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\enrollment-service\routes\enrollments.js:8:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\routes\\enrollments.js',
    'E:\\final_research_agentic\\output\\learnhub-learning-management-system\\backend\\enrollment-service\\index.js'
  ]
}

Node.js v22.22.2 | exit=1 | service failed to start

## Backend Validation Failures | 2026-04-19T11:01:26.390Z
- /enrollment-service/routes/enrollments.js: missing local require ../../models/Enrollment

## App Build Plan | 2026-04-19T11:06:33.415Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Route Failures | 2026-04-19T11:16:52.633Z
- POST /api/auth/register: Expected HTTP 201 but received 200
- POST /api/lessons: fetch failed
- POST /api/lessons/000000000000000000000001/complete: fetch failed
- POST /api/quizzes: fetch failed
- POST /api/quizzes/000000000000000000000001/submit: fetch failed
- PUT /api/auth/profile: Expected HTTP 200 but received 404
- GET /api/courses: fetch failed
- POST /api/courses: Course validation failed: description: Path `description` is required.

## Live Route Failures | 2026-04-19T11:21:09.893Z
- POST /api/lessons: Expected HTTP 201 but received 400
- POST /api/lessons/000000000000000000000001/complete: mongoose is not defined
- POST /api/quizzes: Expected HTTP 201 but received 400
- POST /api/quizzes/000000000000000000000001/submit: mongoose is not defined
- GET /api/auth/me: Expected HTTP 200 but received 404
- PUT /api/auth/profile: Expected HTTP 200 but received 400
- GET /api/courses: fetch failed
- POST /api/courses: Expected HTTP 201 but received 400

## Remaining Route Failures | 2026-04-19T11:21:20.832Z
- POST /api/auth/register: Expected HTTP 201 but received 200
- POST /api/lessons: fetch failed
- POST /api/lessons/000000000000000000000001/complete: fetch failed
- POST /api/quizzes: fetch failed
- POST /api/quizzes/000000000000000000000001/submit: fetch failed
- PUT /api/auth/profile: Expected HTTP 200 but received 404
- GET /api/courses: fetch failed
- POST /api/courses: Course validation failed: description: Path `description` is required.

## App Build Plan | 2026-04-19T11:31:44.065Z
- Project: LearnHub Learning Management System
- Services: Auth Service (4 endpoints), Course Service (5 endpoints), Enrollment Service (3 endpoints), Lesson Service (5 endpoints), Quiz Service (4 endpoints)
- Features: User Authentication, Course Management, Enrollment Management, Lesson and Content Delivery, Quiz and Assessment
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom, recharts
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Runtime Failure | 2026-04-19T11:41:01.435Z
- auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:1405
    throw new TypeError(`Invalid schema configuration: \`${name}\` is not ` +
    ^

TypeError: Invalid schema configuration: `True` is not a valid type at path `timestamps`. See https://bit.ly/mongoose-schematypes for a list of valid schema types.
    at Schema.interpretAsType (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:1405:11)
    at Schema.path (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:1028:27)
    at Schema.add (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:696:12)
    at new Schema (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:135:10)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\models\User.js:3:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Live Runtime Failure | 2026-04-19T11:42:07.684Z
- auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:1405
    throw new TypeError(`Invalid schema configuration: \`${name}\` is not ` +
    ^

TypeError: Invalid schema configuration: `True` is not a valid type at path `timestamps`. See https://bit.ly/mongoose-schematypes for a list of valid schema types.
    at Schema.interpretAsType (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:1405:11)
    at Schema.path (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:1028:27)
    at Schema.add (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:696:12)
    at new Schema (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:135:10)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\models\User.js:3:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## Remaining Route Failures | 2026-04-19T11:42:58.495Z
- GET /health: auth-service exited before health check: E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:1405
    throw new TypeError(`Invalid schema configuration: \`${name}\` is not ` +
    ^

TypeError: Invalid schema configuration: `True` is not a valid type at path `timestamps`. See https://bit.ly/mongoose-schematypes for a list of valid schema types.
    at Schema.interpretAsType (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:1405:11)
    at Schema.path (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:1028:27)
    at Schema.add (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:696:12)
    at new Schema (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\node_modules\mongoose\lib\schema.js:135:10)
    at Object.<anonymous> (E:\final_research_agentic\output\learnhub-learning-management-system\backend\auth-service\models\User.js:3:20)
    at Module._compile (node:internal/modules/cjs/loader:1705:14)
    at Object..js (node:internal/modules/cjs/loader:1838:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
    at TracingChannel.traceSync (node:diagnostics_channel:328:14)

Node.js v22.22.2 | > auth-service@1.0.0 start
> node index.js | exit=1 | service failed to start

## App Build Plan | 2026-04-19T11:44:58.141Z
- Project: StayEase Hotel Booking System
- Services: Auth Service (4 endpoints), Room Service (5 endpoints), Reservation Service (5 endpoints), Checkin Service (3 endpoints), Payment Service (3 endpoints)
- Features: User Authentication, Room Management, Reservation Management, Check-in and Check-out, Payment Processing
- Expected backend libraries: bcryptjs, cors, dotenv, express, http-proxy-middleware, jsonwebtoken, mongoose, multer
- Expected frontend libraries: axios, react, react-router-dom
- Developer workflow: understand app scope, remember expected libraries, then audit each backend service in order (models -> routes -> controllers -> index.js -> package.json) before patching.
- Frontend workflow: audit pages/files individually for syntax, local imports, and missing external libraries before final preview.

## Live Route Failures | 2026-04-19T11:53:34.868Z
- POST /api/reservations: Reservation validation failed: endDate: Path `endDate` is required., startDate: Path `startDate` is required., user: Path `user` is required.
- POST /api/checkin: GuestStay validation failed: roomId: Path `roomId` is required., checkInDate: Path `checkInDate` is required., checkOutDate: Path `checkOutDate` is required.
- POST /api/checkout: Expected HTTP 201 but received 204
- POST /api/payments: Payment validation failed: reservation: Cast to ObjectId failed for value "pending" (type string) at path "reservation" because of "BSONTypeError"

## Live Route Failures | 2026-04-19T11:57:19.415Z
- POST /api/reservations: Reservation validation failed: endDate: Path `endDate` is required., startDate: Path `startDate` is required., user: Path `user` is required.
- POST /api/checkin: GuestStay validation failed: roomId: Path `roomId` is required., checkInDate: Path `checkInDate` is required., checkOutDate: Path `checkOutDate` is required.
- POST /api/checkout: Expected HTTP 201 but received 204
- POST /api/payments: Payment validation failed: reservation: Cast to ObjectId failed for value "pending" (type string) at path "reservation" because of "BSONTypeError"

## Backend Validation Failures | 2026-04-19T11:59:31.834Z
- /auth-service/models/User.js: schema option timestamps is incorrectly declared inside the schema fields — move it to the second argument as new mongoose.Schema(fields, { timestamps: true })
- /reservation-service/models/Reservation.js: schema option timestamps is incorrectly declared inside the schema fields — move it to the second argument as new mongoose.Schema(fields, { timestamps: true })
- /payment-service/models/Payment.js: schema option timestamps is incorrectly declared inside the schema fields — move it to the second argument as new mongoose.Schema(fields, { timestamps: true })
