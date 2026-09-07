---
name: vitest
description: Plan, write, debug, and run Vitest unit, integration, or component tests for AgentX-generated Next.js JavaScript + MongoDB/Mongoose applications.
---

# Vitest testing

Vitest is the permanent project unit/integration runner for this builder. Preserve the project's package manager, module system, Next.js conventions, aliases, test layout, and pinned versions; do not substitute another unit runner.

Read this skill at task start when selected and again immediately before entering the unit-test phase, after context compaction, or when a new unit-test failure changes the repair approach. Do not reread it between unchanged retries.

## Before planning or editing

Inspect the source under test with its imports/types and callers, nearby tests, `package.json` and lockfile, Vitest configuration (and any underlying Vite config only when Vitest actually consumes it), setup files, environment selection, path aliases, and relevant dependency interfaces. In Planner, put any installation or file creation in the blueprint; do not perform it before approval.

Choose tests from behavior and risk, not line count:

- Cover critical business rules, changed/high-risk behavior, boundaries, error/async paths, and a regression for every repaired bug.
- Match existing `test`/`it`, `describe`, fixture, naming, and import conventions.
- Assert observable outputs, state, errors, and contracts. Avoid weak existence-only assertions, snapshots of volatile output, and assertions coupled only to call order or private implementation.
- Mock only nondeterministic or external boundaries. Prefer real collaborators when fast and isolated; restore spies/mocks so tests cannot leak state.
- Keep tests independently runnable. Prefer test-scoped fixtures for mutable state and use fixture cleanup or lifecycle hooks to close databases, timers, servers, and other resources even after failure.
- Use Vitest APIs such as `vi.fn`, `vi.mock`, and `vi.spyOn`, never Jest globals. Respect `globals`, `environment`, `setupFiles`, and `restoreMocks` rather than guessing them.
- Use `async`/`await` and `resolves`/`rejects` correctly. Include empty, nullish, invalid, boundary, dependency-failure, and concurrency cases only when relevant to the actual contract.
- Use table-driven cases when they express one rule more clearly than repeated tests. Enable concurrency only for genuinely isolated work; concurrent snapshots/assertions must use the test-context `expect`.

## Passing on the first run

A suite that fails on its first run and then gets repaired costs several model
turns per failure, and most of those failures are not defects in the code under
test — they are the test disagreeing with an implementation the author did not
look at. Aim for a first-run pass, and get it mechanically rather than by
writing weaker assertions.

- **Read the module before you test it.** Open the file and copy the real export
  names, signatures, argument order, return shape and error type. Never write a
  test from what the implementation *should* look like or from what you wrote
  earlier in the run: read it now.
- **Import the way the application imports.** Same specifier, same default vs
  named form, same extension. A test that reaches past the public entry point
  into an internal path will break the moment the module moves.
- **Assert the shape you actually produce.** If a function returns a document,
  do not assert a plain object; if it returns cents, do not assert a formatted
  string; if it throws a typed error, assert that type, not a message that will
  be reworded.
- **Give every test its own data.** Create the rows a test needs inside that
  test with unique keys, and clear only what it created. Tests that share seeded
  rows pass alone and fail in a suite, which reads as a product bug and is not
  one.
- **Reset shared state between tests, not once per file.** Database collections,
  in-memory caches, rate-limiter counters and module-level singletons all
  survive a test and change the result of the next one.
- **Await everything.** Every promise gets `await` or a `resolves`/`rejects`
  matcher. A floating promise turns into an unhandled rejection attributed to
  whichever test happens to be running.
- **Do not assert on wall-clock time or the local timezone.** Fix the instant
  with fake timers or an injected clock, and compare instants rather than
  formatted dates.
- **Write the failing edge case last.** Get the happy path green first; an edge
  case written against an untested happy path multiplies the causes of one
  failure.

### The setup file and `globals` are one decision

Measured on a real build: every service suite passed on its first run and the
React client suite collected **zero** tests, on this alone.

A matcher package such as `@testing-library/jest-dom` works by extending the
runner's `expect`. Importing it from a setup file therefore requires an `expect`
to already exist in that scope, and one only exists globally when the config
enables it. So a setup file that extends matchers and a config without
`globals` is a contradiction, and it fails at collection with
`ReferenceError: expect is not defined` — pointing at the setup file, which
looks like the setup file is broken when the config is what disagrees.

Pick one and make the config and the setup file agree:

- **Import the runner-specific entry** — `@testing-library/jest-dom/vitest` —
  which brings its own `expect` and needs no globals. Prefer this: nothing
  becomes global that was not already.
- **Or enable `globals: true`** in the config, and then `describe`/`it`/`expect`
  need no import anywhere.

The same rule covers any setup file that touches `expect`, `vi` or lifecycle
hooks: whatever it reaches for must be either imported there or enabled in the
config. Read the config before writing the setup file, not after the failure.

When a first run does fail, read every failure before repairing any of them and
group them by cause. A whole file failing on import, or twenty tests failing on
the same missing fixture, is one defect, not twenty.

For DOM/component behavior, query the rendered interface the way a user or assistive technology does: prefer role and accessible name, then labels and visible text. Use the query whose timing contract matches the UI (`getBy*` for present-now, `findBy*` for async appearance, `queryBy*` for absence). Prefer a fresh `userEvent.setup()` inside each test and await interactions; use low-level event dispatch only when the real interaction cannot be expressed otherwise.

If an application talks to HTTP/GraphQL services, mock at the network boundary only when real local integration would be slow, unsafe, or nondeterministic. A request interceptor such as MSW is optional, not a default dependency. When used, let production request code execute unchanged, fail tests on unexpected first-party requests, reset handlers between tests, and still keep separate real integration/E2E evidence for critical contracts.

## Execute and verify

Use the existing package script/package manager. Direct commands must be finite (`vitest run` or `vitest --no-watch`), never the default watch loop. Run affected tests after edits, then the full discovered unit regression once the implementation is stable.

Treat file filters as runner input, not as assumed shell expansion. On a cross-platform project, confirm the installed CLI's filter semantics or pass explicit test paths; a wildcard that works in one shell may reach Vitest literally in another. If a filtered command fails without new evidence, inspect its diagnostic and change the filter or owning code instead of submitting the identical command again.

Current Vitest CLI documentation is explicit: a positional filter checks whether the test-file path contains that string; it does not parse regular expressions or glob patterns unless the current terminal expands the glob first. Therefore, before a filtered run, use `search`/the project-layout snapshot to discover the actual test directory or exact test file. Prefer an observed directory substring such as the project's real test root, or explicit observed test paths. Never guess `tests` vs `test` vs `src/test`, and never assume `**` expansion on Windows. If you need a config file, call `search` for `vitest.config` and use the observed extension; do not probe `.ts`, `.js`, `.mjs` variants one by one.

Vitest transforms TypeScript but does not replace the project's type checker. Run the discovered typecheck separately. Choose Node, DOM emulation, or browser mode from the behavior under test; do not make server code pass by placing everything in a browser-like environment.

Before adding a coverage provider, inspect the installed Vitest version, manifest, lockfile, and current dependency graph. Keep `@vitest/coverage-v8` or another provider on the exact compatible version line required by the installed runner; do not resolve the runner and provider independently with `latest`. Run only one package-manager mutation at a time in a workspace. A provider import/export failure inside dependencies is a dependency-runtime mismatch, not application syntax.

Install the smallest test surface the project uses. The core runner does not imply that the interactive UI package, a browser package, DOM emulator, or a framework build plugin is required. Add each adapter only when the planned tests/config actually use it; do not add a Vite framework plugin to a non-Vite application by habit. When the solver reports a named peer range conflict, align or remove the exact conflicting declaration, or choose a runner version compatible with the project's supported runtime. Do not make force/legacy peer resolution the first repair because it can create an install that fails only when tests load.

Before installing a component-testing wrapper or interaction helper, inspect its current peer dependencies and install one compatible peer-complete set in the same serialized operation. For example, a wrapper may intentionally require its DOM core as a direct peer rather than bundling it. A missing peer discovered only on the first test run is a preventable setup defect; do not respond with repeated one-package installs when the package metadata already names the complete set.

Before the first test run, derive one install/config checklist from the planned evidence: runner, its required build/runtime peer, exact-version coverage provider when machine coverage is required, chosen environment, and only the component wrappers actually used. Verify that peer-complete graph once before generating a large suite. Match the test-config filename and syntax to the package's ESM/CommonJS contract; do not leave an ESM config to be loaded as CommonJS or silence the resulting warning.

Vitest reads Vite configuration by default. A dedicated `vitest.config.*` takes precedence rather than automatically inheriting every Vite option, so explicitly merge the application config when its plugins, aliases, transforms, or defines are required. Do not duplicate a drifting alias/plugin setup in two unrelated configs.

Keep runner discovery boundaries disjoint. Unit/component configuration must include its intended sources/tests and exclude browser-E2E artifacts, generated reports, build output, and dependency trees. AgentX browser journeys are external harness evidence and must not be imported into Vitest. Before a broad run, inspect the discovered file set so one runner never imports another runner's test API as application code.

Make time deterministic with fake timers only for code whose contract depends on clocks, delays, or intervals. Restore real timers and mocks in cleanup even when assertions fail; never leave fake time active for later tests. Treat unhandled rejections, uncaught errors, resource leaks, and warnings caused by the changed code as failures to diagnose rather than noise to suppress.

Do not delete the lockfile or dependency directory as the first repair. Read the package-manager diagnostic and graph, wait for or stop task-owned processes using the dependency tree, then apply the smallest compatible manifest/lockfile repair. If a clean install is genuinely required, serialize it and confirm no build, server, or test process is holding native modules first.

For AgentX coverage evidence, configure or reuse a machine-readable Istanbul JSON summary, LCOV, or Cobertura report. Current Vitest also supports concise agent-oriented terminal reporting; prefer machine-readable output plus concise summaries instead of dumping every fully covered file into model context. Configure coverage include/reporters from the installed project's needs and current docs, not from remembered defaults. Then and include relevant changed/high-risk first-party source. Confirm the report includes the intended source set instead of tests, generated files, build output, or unrelated framework glue. Meet the verification scope's configured floor; do not exclude difficult files, auto-update thresholds to hide regressions, or manufacture coverage. A transform/parser failure while collecting source coverage is a build/config defect to repair, not a reason to narrow coverage until it disappears.

Read current official documentation when configuration or version behavior is uncertain:

- https://vitest.dev/guide/
- https://vitest.dev/guide/coverage.html
- https://vitest.dev/config/
- https://vitest.dev/guide/test-context
- https://testing-library.com/docs/queries/about/
- https://testing-library.com/docs/user-event/intro/
- https://github.com/vitest-dev/vitest
- https://github.com/testing-library/react-testing-library
- https://github.com/mswjs/msw

Run generated tests immediately. Treat import/API/config errors and flaky behavior as defects to diagnose, not reasons to weaken assertions or raise retries.
