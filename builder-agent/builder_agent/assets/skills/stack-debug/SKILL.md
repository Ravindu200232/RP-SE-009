---
name: stack-debug
description: "The page that defines the rule behind a build, runtime or test failure - the official Next.js and Vitest documentation for errors, directives, the Server/Client boundary and the test runner, plus a minimal-diff build-error procedure. Read this index, then open the one page the error names with readSkill resourcePath."
---

# Fixing a failing build

18 entries. Open one with
`readSkill(name="stack-debug", resourcePath="<entry>.md")`.

Reading the same source file again does not tell you anything the first read did
not. When an error repeats, the next thing to open is the page that defines the
rule it names - not the file.

## What to run, and in what order

`npm run build` first - before the dev server, and whether or not the dev
server complained. It type-checks and bundles every route in one pass, so one
run names every error in the project instead of the one route you opened. Fix
what it names, build again, and only then start the dev server and **read the
browser console**: a build passes on code that throws on first render, hydrates
differently, or fetches a 404, and the console says all three plainly. A page
that renders is not a page that works.

The full procedure is in `build-error-resolver.md`.

## Start here

- **`build-error-resolver.md`** — The procedure: read the error, locate the true cause, apply the smallest diff that fixes it, re-run. Use on any build, type or lint failure.

## Next.js - what the error names

- **`error-handling.md`** — Expected errors and uncaught exceptions; where each is handled.
- **`error-file-convention.md`** — `error.js`, `global-error.js`: what they must export and where they may live.
- **`not-found.md`** — `not-found.js` and the `notFound()` function.
- **`catch-error.md`** — Catching and typing errors around async work.
- **`server-and-client-boundary.md`** — What may cross between server and client, and the errors raised when something may not.
- **`directives.md`** — `'use client'` and `'use server'`: the rules for both.
- **`use-client-directive.md`** — Where `'use client'` must appear and what it makes of the module.
- **`use-server-directive.md`** — Where `'use server'` must appear; why a function may not be exported from a client module.
- **`file-conventions.md`** — Which filenames Next.js gives meaning to, and what each must export.
- **`route-handlers.md`** — `route.js`: the exported verbs, their signatures and their return values.
- **`server-actions.md`** — Actions, their `'use server'` placement, form binding and revalidation.
- **`debugging.md`** — Attaching a debugger, and reading a Next.js stack trace back to the source.
- **`fast-refresh.md`** — Why a change forces a full reload, and what a stale module means for an error that will not clear.

## Vitest - when the test run is the failure

- **`vitest-cli.md`** — Every flag: filtering, reporters, watch, coverage, exit behaviour.
- **`vitest-config.md`** — `environment`, `setupFiles`, `include`, aliases - the settings a failing suite usually needs.
- **`vitest-expect.md`** — Every matcher and what its failure message means.
- **`vitest-mocking.md`** — `vi.mock`, spies, timers, and hoisting order.

## Reading an error

Take the words the runtime actually printed and open the entry that defines
them. A syntax error (`Return statement is not allowed here`, `Unexpected
token`) is in the file's own structure, so `build-error-resolver.md` applies;
anything naming a directive, a boundary, a reserved filename or a Next.js export
is a framework rule, and its page is above.
