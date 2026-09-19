# Local generated previews

Each supported project has its own runtime. Opening another project preserves
running previews and the existing build concurrency policy. Next.js uses one
public port; MERN uses a gateway port and the declared service ports. Shared
database services retain their existing configuration and lifecycle.

The stable preview address is `http://p-<project-hash>.localhost:7824/`, with the
backend's configured UI port replacing `7824` when applicable. Studio and the
generated document have separate origins. HTTP, WebSocket connections, activity,
and the validated picker/console bridge pass through the shared backend router.

## Idle lifecycle

The default idle period is 600 seconds after startup and any active build/QA
lease have completed. Clicks, typing, scrolling, user navigation, and refresh
extend that period. Status requests, API polling, HMR, and an open tab do not.
Expiry closes only that project's owned process trees and releases its ports.
Files, database data, and saved conversations remain available.

Clicking a project or refreshing its existing preview tab starts it again.
Concurrent opens share one startup; opening a running project reuses its runtime.
The router displays a loading document during startup. Background asset or API
requests receive 503 while stopped and cannot restart the app.

## Runtime interface

- `POST /__agentforge/api/open/<project>` returns `project`, `requestId`,
  `runtimeId`, `status`, and `previewUrl`, plus ordering and failure details.
- `GET /__agentforge/api/runtime/<project>` observes that snapshot without
  extending the idle deadline.
- `POST /__agentforge/api/runtime/<project>/activity` accepts the current
  `runtimeId`. Activity from an earlier runtime is ignored.
- `runtime_state` WebSocket events carry the same snapshot. Clients use
  `serverId` and `revision` to ignore out-of-order updates, and keep selection
  separate from runtime and build state.

The runtime manager reserves available ports before startup. A configured port
is preferred; an occupied port falls back to an OS-assigned port. Startup bind
races trigger cleanup of owned processes and up to three total attempts.
`PORT`, service `*_PORT` values, and matching local service URLs are supplied
through the process environment. Generated supervisors must preserve inherited
values when reading dotenv files. The builder's `runtimeInfo` tool exposes the
allocated values for CLI flags and runtime probes, without exposing secrets.

## Verification

Run backend, builder, QA, and integration regressions with:

```powershell
python -m unittest discover -s test -t . -q
python studio/scripts/verify_ui_contract.py
cd studio
npm run build
```

The preview unit tests cover fake-clock expiry, work leases, stale activity,
duplicate starts, port collisions, bounded retries, proxy routing, refresh
reopening, and owned child-process cleanup. Browser verification should also
exercise Next.js HMR/navigation, MERN service calls and authentication, switching
projects, separate tabs, and picker/drawing screenshots. Run one real 600-second
idle check to confirm the inactive project's process and ports disappear while
another active project remains available.
