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

- Reuse the application's already running public preview origin for an edit. Inspect its launch command and readiness before starting another server. If a service requires restart after a source change, restart its owned supervisor once, keep it alive through E2E, and hand the running preview back after verification. Stopping it before the last journey creates a connection failure rather than useful evidence.
- For portable HTTP probes, use a small Node script with `fetch`, explicit expected status checks, and a nonzero exit for mismatches. Windows `curl -o /dev/null` fails writing its output; `NUL` is the Windows sink. A local output-write error does not mean the API request failed, so inspect existing results before repeating a state-changing request.

- Validate required configuration without printing secrets. Distinguish configuration, dependency, build, application, and test failures.
- Detect the real operating system and active shell and use its syntax. Do not send POSIX-only commands to Windows `cmd`/PowerShell or Windows-only commands to a POSIX shell.
- Use the command processor reported in the run context. On Windows this engine runs `executeTerminal` through `COMSPEC` (`cmd.exe`), even when the Studio was started from PowerShell. Prefer one command per call; `;` and `$env:NAME` are PowerShell syntax, not cmd syntax. Use `listDir`/`readFile` for workspace inspection instead of shell-specific existence checks. If a shell command fails to parse, fix the shell syntax before retrying; the application has not failed.
- Use a task-owned available port and pass it through the app's supported configuration. Do not kill or replace an unrelated process on the default port.
- Put long-lived servers in AgentX background-process management, wait on an observable readiness condition, capture logs, and guarantee cleanup on success/failure.
- Serialize finite package-manager, generator, build, and test commands that use the same manifest, lockfile, dependency tree, or generated output. Never start a second dependency mutation while the first is running, even if the first has produced no new output.
- After a pending wait returns no new output, continue independent inspection or implementation before checking again. Do not burn turns by polling an unchanged process every few seconds, and never restart the command to manufacture progress.
- Before a destructive dependency reset, inspect the exact diagnostic and dependency graph, then stop or wait for every task-owned process that can hold files. Preserve the lockfile and use the smallest repair unless evidence proves a clean reinstall is necessary.
- Do not treat a listening socket as complete evidence. Probe representative routes, static assets, APIs, redirects, persistence dependencies, and failure responses.
- In browsers, inspect console errors, failed requests, blank/error pages, hydration, navigation, responsive layout, and critical interactions. Capture visual evidence only for selected representative/high-risk pages or a page showing a defect.

During implementation, rerun affected fast checks. For an existing-app feature, verify changed components/services and their public integration path; broaden regression only when shared changes or a failure justify it. Reuse passing build/test evidence when those inputs have not changed. Report exact commands, exit status, tested URLs, and unresolved environmental limits; never turn missing evidence into a pass.

Some tools use documented nonzero success codes. Prefer portable project/file operations; otherwise interpret the tool's documented status deliberately instead of labelling a successful transfer as a failure.
