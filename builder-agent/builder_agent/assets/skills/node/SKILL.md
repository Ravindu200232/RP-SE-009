---
name: node
description: Build and diagnose Node.js services, scripts, and tooling using the project's installed runtime, module system, package manager, and operating environment.
---

# Node.js runtime work

Use this skill only when Node.js is selected or detected. Inspect `package.json`, lockfile, `engines`, scripts, module type, TypeScript/transpilation setup, environment contract, entry points, process lifecycle, and tests. Verify the local runtime/package-manager versions before using version-specific APIs.

- Preserve ESM/CommonJS boundaries and package exports. Avoid mixed-module fixes that merely move the failure to runtime.
- Validate configuration once at startup, keep secrets out of logs/client output, and distinguish absent, empty, and malformed environment values.
- Await or deliberately supervise async work. Propagate failures with useful context; do not swallow promise rejections or use fire-and-forget work for critical persistence.
- Bound external I/O with cancellation/timeouts where appropriate. Close servers, database clients, workers, and file handles on success, failure, and shutdown.
- Use task-owned dynamic ports for verification. Never kill an unrelated process occupying a conventional port.
- Preserve the selected package manager and pinned versions. Research current official APIs when installed behavior differs from model memory.
- Treat the manifest, lockfile, installed dependency tree, and native build artifacts as one shared mutation boundary. Run one package-manager mutation at a time, and wait for builds/tests/servers holding those files before a justified clean reinstall.
- Diagnose dependency import/export failures from the installed package graph and peer/version contract before editing application syntax. Align coupled tools/providers to compatible versions instead of independently installing `latest`.

Run finite lint/typecheck/unit commands, exercise the real entry point, probe readiness and failure behavior, and confirm the process exits cleanly when it should.

Current official references:

- https://nodejs.org/api/
- https://nodejs.org/api/process.html
- https://nodejs.org/api/errors.html
