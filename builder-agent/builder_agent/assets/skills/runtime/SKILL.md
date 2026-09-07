---
name: runtime
description: Start, probe, debug, and finish generated applications through real runtime paths, dependency readiness, browser checks, and clean process lifecycle.
---

# Runtime verification

Use this skill for application startup, runtime debugging, readiness, route/API smoke checks, background servers, or final completion evidence. Discover behavior from the project rather than assuming a framework command.

For a full application task, read this skill at task start and again before runtime/visual verification, after context compaction, or when runtime evidence changes the recovery approach. Do not reread it in an unchanged polling loop.

## Discover the real runtime

Inspect package/build manifests, lockfiles, scripts, environment examples, service manifests, containers, entry points, configured ports, health/readiness routes, external dependencies, and existing runbooks. Determine the selected package manager and exact development and production commands. If the technology or installed version is unfamiliar, consult its current official documentation; do not use a fixed command table.

## Run safely

- Validate required configuration without printing secrets. Distinguish configuration, dependency, build, application, and test failures.
- Detect the real operating system and active shell and use its syntax. Do not send POSIX-only commands to Windows `cmd`/PowerShell or Windows-only commands to a POSIX shell.
- Use a task-owned available port and pass it through the app's supported configuration. Do not kill or replace an unrelated process on the default port.
- Put long-lived servers in AgentX background-process management, wait on an observable readiness condition, capture logs, and guarantee cleanup on success/failure.
- Serialize finite package-manager, generator, build, and test commands that use the same manifest, lockfile, dependency tree, or generated output. Never start a second dependency mutation while the first is running, even if the first has produced no new output.
- After a pending wait returns no new output, continue independent inspection or implementation before checking again. Do not burn turns by polling an unchanged process every few seconds, and never restart the command to manufacture progress.
- Before a destructive dependency reset, inspect the exact diagnostic and dependency graph, then stop or wait for every task-owned process that can hold files. Preserve the lockfile and use the smallest repair unless evidence proves a clean reinstall is necessary.
- Do not treat a listening socket as complete evidence. Probe representative routes, static assets, APIs, redirects, persistence dependencies, and failure responses.
- In browsers, inspect console errors, failed requests, blank/error pages, hydration, navigation, responsive layout, and critical interactions. Capture visual evidence only for selected representative/high-risk pages or a page showing a defect.

During implementation, rerun affected fast checks. In the final stable phase, run the discovered production build and one full regression/readiness pass. Report exact commands, exit status, tested URLs, and unresolved environmental limits; never turn missing evidence into a pass.

Some tools use documented nonzero success codes. Prefer portable project/file operations; otherwise interpret the tool's documented status deliberately instead of labelling a successful transfer as a failure.
