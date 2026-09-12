---
name: vitest
description: Plan, write, debug, and run Vitest unit, integration, or component tests for AgentX-generated Next.js JavaScript + MongoDB/Mongoose applications.
---

# Vitest testing

Vitest is the permanent unit and integration runner for this builder. Preserve
the project's package manager, module system, framework conventions, aliases,
test layout and pinned versions; do not substitute another runner.

Read this skill at task start when selected, and again immediately before the
unit-test phase, after compaction, or when new failure evidence changes the
repair. Do not reread it between unchanged retries.

## One run, one record

Run the suite through `runTests` from its very first execution, with a stable
suite ID and the `covers` requirement IDs. Have that same command write Vitest
JSON (`--reporter=json --outputFile=.agentforge/qa/vitest.json`) and pass
`reportPath: ".agentforge/qa/vitest.json"`; create the directory with a file
write if the installed runner needs it. Never execute the suite a second time
to register evidence, produce a report, or change a `findstr`/`grep` filter —
filtering saved output is an output-reading task, not a reason to run anything.
Capture once, then read that artifact until a source, test or config change
earns fresh evidence. Once the current checks pass, go on to E2E and finish.

Coverage is optional diagnostic information. Do not add tests, rerun a passing
suite, or block completion to move a percentage. When machine coverage is
required, configure or reuse an Istanbul JSON summary, LCOV or Cobertura
report, keep it to changed and high-risk first-party source rather than tests,
generated files or framework glue, and prefer that plus a concise terminal
summary over dumping every covered file into context. Report the measured
percentages honestly; never edit tests or thresholds to raise one. A
transform or parser failure while collecting coverage is a build defect to
repair, not a reason to narrow coverage until it disappears.

## Before planning or editing

Inspect the source under test with its imports, types and callers, the nearby
tests, `package.json` and the lockfile, the Vitest configuration and any Vite
config it actually consumes, setup files, environment selection, path aliases,
and the dependency interfaces in play. In Planner, put any installation or file
creation in the blueprint; do not perform it before approval.

Choose tests from behavior and risk, not line count:

- Cover the critical business rules, changed and high-risk behaviour,
  boundaries, error and async paths, and a regression for every repaired bug.
- Match the existing `test`/`it`, `describe`, fixture, naming and import
  conventions.
- Assert observable outputs, state, errors and contracts. Avoid existence-only
  assertions, snapshots of volatile output, and assertions coupled to call
  order or private implementation.
- Mock only nondeterministic or external boundaries; prefer real collaborators
  when they are fast and isolated, and restore spies and mocks so no test leaks
  state.
- Keep every test independently runnable. Prefer test-scoped fixtures for
  mutable state, and close databases, timers and servers in cleanup that runs
  even after a failure.
- Use Vitest APIs — `vi.fn`, `vi.mock`, `vi.spyOn` — never Jest globals, and
  respect the configured `globals`, `environment`, `setupFiles` and
  `restoreMocks` rather than guessing them.
- Use `async`/`await` and `resolves`/`rejects` correctly. Add empty, nullish,
  invalid, boundary, dependency-failure and concurrency cases when the contract
  actually has them.
- Use table-driven cases where they express one rule more clearly than repeated
  tests. Enable concurrency only for genuinely isolated work; a concurrent
  assertion must use the test-context `expect`.

## Passing on the first run

A suite that fails on its first run and is then repaired costs several model
turns per failure, and most of those failures are not defects in the code under
test — they are the test disagreeing with an implementation nobody looked at.
Aim for a first-run pass, and get it mechanically rather than by writing weaker
assertions.

- **Read the module before you test it.** Copy the real export names,
  signatures, argument order, return shape and error type out of the file. Not
  from what it should look like, not from what you wrote earlier in the run.
- **Import the way the application imports.** Same specifier, same default or
  named form, same extension. A test that reaches past the public entry point
  into an internal path breaks the moment the module moves.
- **Assert the shape you actually produce.** A function returning a document is
  not a plain object; one returning cents is not a formatted string; one
  throwing a typed error is asserted by type, not by a message that will be
  reworded.
- **Give every test its own data.** Create the rows it needs inside it with
  unique keys and clear only what it created. Tests sharing seeded rows pass
  alone and fail in a suite, which reads as a product bug and is not one.
- **Reset shared state between tests, not once per file.** Collections, caches,
  rate-limiter counters and module-level singletons all survive a test and
  change the next one's result.
- **Await everything.** Every promise gets `await` or a `resolves`/`rejects`
  matcher. A floating promise becomes an unhandled rejection attributed to
  whichever test happened to be running.
- **Never assert on wall-clock time or the local timezone.** Fix the instant
  with fake timers or an injected clock and compare instants, not formatted
  dates.
- **Write the failing edge case last.** Get the happy path green first; an edge
  case written against an untested happy path multiplies the causes of one
  failure.

### The setup file and `globals` are one decision

Measured on a real build: every service suite passed on its first run and the
React client suite collected **zero** tests, on this alone.

A matcher package such as `@testing-library/jest-dom` works by extending the
runner's `expect`, so importing it from a setup file requires an `expect` to
exist in that scope — and one exists globally only when the config enables it.
A setup file that extends matchers plus a config without `globals` is therefore
a contradiction, and it fails at collection with `ReferenceError: expect is not
defined`, pointing at the setup file when the config is what disagrees.

Pick one and make them agree: import the runner-specific entry
`@testing-library/jest-dom/vitest`, which brings its own `expect` and needs no
globals (prefer this — nothing becomes global that was not already), or enable
`globals: true` and import nothing anywhere. The same rule covers any setup
file touching `expect`, `vi` or lifecycle hooks: whatever it reaches for is
either imported there or enabled in the config. Read the config before writing
the setup file, not after the failure.

When a first run does fail, read every failure before repairing any of them and
group them by cause. A whole file failing on import, or twenty tests failing on
one missing fixture, is a single defect.

## Components and the network

Query the rendered interface the way a user or assistive technology does:
prefer role and accessible name, then labels and visible text. Use the query
whose timing contract matches the UI — `getBy*` for present-now, `findBy*` for
async appearance, `queryBy*` for absence. Prefer a fresh `userEvent.setup()`
inside each test and await the interactions; drop to low-level event dispatch
only when the real interaction cannot be expressed otherwise.

Mock at the network boundary only when real local integration would be slow,
unsafe or nondeterministic. A request interceptor such as MSW is optional, not
a default dependency; when used, let production request code run unchanged,
fail on unexpected first-party requests, reset handlers between tests, and keep
separate real integration evidence for the critical contracts.

That preference for real collaborators is about your own code. **A third
party's API is never called from a unit test** — not Stripe, not a mail or SMS
provider, not an image host, not a map or model API. Stub the client with
`vi.mock` and assert what your code asked it for. A unit suite that reaches the
internet is slow, fails on a plane, fails in CI, and either spends someone's
quota or fails on a placeholder key — and "Invalid API key" tells you nothing
about the code under test. Real provider traffic belongs in a sandbox E2E
journey, if anywhere.

## Execute and verify

Use the existing package script or package manager. Direct commands must be
finite — `vitest run` or `vitest --no-watch`, never the default watch loop. Run
the affected tests after an edit, then the full discovered regression once the
implementation is stable.

A file filter is runner input, not shell expansion. A positional filter checks
whether the test-file path contains that string; it does not parse regular
expressions or globs unless the terminal expanded them first — and no terminal
on Windows expands `**`. So before a filtered run, use `search` or the
project-layout snapshot to find the real test directory or the exact file, and
pass an observed substring or observed paths. Never guess `tests` against
`test` against `src/test`, and never probe `vitest.config` extensions one by
one — search for it and use the extension you observe. If a filtered command
fails without new evidence, read its diagnostic and change the filter or the
owning code; do not submit the identical command again.

Vitest transforms TypeScript but does not replace the project's type checker;
run the discovered typecheck separately. Choose Node, DOM emulation or browser
mode from the behaviour under test — do not make server code pass by putting
everything in a browser-like environment.

Make time deterministic with fake timers only where the contract depends on
clocks, delays or intervals, and restore real timers and mocks in cleanup even
when assertions fail. Treat unhandled rejections, uncaught errors, resource
leaks and warnings caused by the changed code as failures to diagnose, not
noise to suppress.

## Dependencies and configuration

Before the first test run, derive one install and config checklist from the
planned evidence — the runner, its required build or runtime peer, an
exact-version coverage provider if machine coverage is needed, the chosen
environment, and only the component wrappers actually used — and verify that
peer-complete graph once, before generating a large suite.

- Keep `@vitest/coverage-v8` or another provider on the exact version line the
  installed runner requires. Never resolve runner and provider independently
  as `latest`.
- Run one package-manager mutation at a time in a workspace.
- Install the smallest test surface the project uses. The core runner does not
  imply the interactive UI package, a browser package, a DOM emulator or a
  framework build plugin; add each adapter only when the planned tests or
  config use it, and never add a Vite framework plugin to a non-Vite app out of
  habit.
- On a named peer-range conflict, align or remove the exact conflicting
  declaration, or pick a runner version compatible with the supported runtime.
  Do not reach for force or legacy peer resolution first — it can produce an
  install that fails only once tests load.
- Before a component-testing wrapper or interaction helper, read its current
  peer dependencies and install one compatible peer-complete set in the same
  serialized operation. A wrapper may deliberately require its DOM core as a
  peer rather than bundling it, and a missing peer found on the first test run
  is a preventable setup defect — not a reason for repeated one-package
  installs when the metadata already names the set.
- Match the test-config filename and syntax to the package's ESM/CommonJS
  contract; do not leave an ESM config to be loaded as CommonJS, or silence the
  warning that says so.
- A dedicated `vitest.config.*` takes precedence rather than inheriting every
  Vite option, so merge the application config explicitly when its plugins,
  aliases, transforms or defines are required — and do not maintain a drifting
  copy of that setup in two configs.
- Keep the runners' discovery boundaries disjoint. Unit and component config
  includes its own sources and tests and excludes browser-E2E artifacts,
  reports, build output and dependency trees. AgentX browser journeys are
  external harness evidence and must never be imported into Vitest. Inspect the
  discovered file set before a broad run so one runner never loads another
  runner's test API as application code.
- Do not delete the lockfile or the dependency directory as a first repair.
  Read the package-manager diagnostic and the graph, stop task-owned processes
  holding the tree, then apply the smallest compatible manifest or lockfile
  repair. If a clean install is genuinely required, serialize it and confirm no
  build, server or test process is holding native modules.

Read current official documentation when configuration or version behaviour is
uncertain: https://vitest.dev/guide/, https://vitest.dev/guide/coverage.html,
https://vitest.dev/config/, https://vitest.dev/guide/test-context,
https://testing-library.com/docs/queries/about/,
https://testing-library.com/docs/user-event/intro/, and the
`vitest-dev/vitest`, `testing-library/react-testing-library` and `mswjs/msw`
repositories.

Run generated tests immediately. Treat import, API and config errors and flaky
behaviour as defects to diagnose, never as reasons to weaken assertions or
raise retries.
