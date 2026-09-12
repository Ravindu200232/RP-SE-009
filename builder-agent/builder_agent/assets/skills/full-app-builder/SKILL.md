---
name: full-app-builder
description: Build or substantially extend a complete application from requirements through stack-native build/debug, focused unit tests, critical E2E journeys, runtime probes, visual UI review, and final regression.
---

# Full application builder

Use this skill when the user asks to create, generate, or substantially
complete an application. Build in the stack the user selected, verify units
with Vitest and journeys with AgentX's direct-CDP browser, and preserve the
approved stack and product throughout.

This skill owns the order the phases run in and what has to be true to leave
one. The detail belongs to the phase skills: read each when its phase begins —
`page-composition` and `frontend-design` for the screens, `vitest` for the unit
suite, `browser-e2e` for the journeys — and follow it there.

## Discover before acting

Read the request, the project-layout snapshot, project guidance, manifests,
lockfiles, existing source, environment examples, scripts, and the project
skills the task actually matches. Read only the skills that resolve a concrete
uncertainty; the greenfield checklist is not the opening sequence for a
one-screen change.

- Call `search` before any uncertain file or directory, and use the snapshot's
  observed script commands, test roots and config paths. Never probe guessed
  path or extension variants one at a time.
- Detect the real operating system and shell rather than assuming one.
- Treat the selected builder contract and the installed versions as
  authoritative. When a command or API could have changed, read local CLI help
  and current official documentation instead of model memory.
- `recallKnowledge` returns what earlier runs on this project proved. Reuse it,
  and re-check anything time-sensitive against the code in front of you.
- Continuing a run keeps its reads and its passing checks. A new phase does not
  invalidate them; inspect the missing evidence, and reread a file when it
  changed or when a specific uncertainty needs it.
- A follow-up message continues the same project. Read "that page" or "add this
  too" against the request and implementation already in memory, apply the
  change to the current application, and reopen broad discovery only when the
  new work genuinely needs it.

### A greenfield workspace has one root

Decide the canonical application root from the generator's output and the
observed alias/`baseUrl` configuration before writing a feature file. Never
start a second parallel `lib`/`models`/`components`/route tree outside it
because the workspace root was convenient. Re-run `inspectProject` after any
promotion or structural move.

AgentX metadata directories do not make a workspace an existing application. If
a generator refuses a non-empty root, read its help for a no-install option and
scaffold into a clean staging directory. Promote an explicit inventory —
application source, public assets, configuration, manifests — and never an
unfiltered whole-tree copy: dependency directories, nested version control,
build caches, coverage output, test results and screenshots stay behind.
Install dependencies once, in the final root, from the transferred manifest and
lockfile. If the generator cannot skip installation, either keep the generated
child as the deliberate root or transfer that explicit inventory only.

## The order

Each step is a barrier. A failed or pending done-condition stops the next step
from starting or being announced, until it passes or is N/A with evidence. A
failure returns to the phase that owns it — not to the start of the build. When
you are handed one verification pass (QA unit, QA E2E), run that pass, return
its evidence, and leave the other phases to the caller; repairing a defect the
pass exposed is still yours.

Derive authentication from the approved requirements. Where there are accounts,
private data or privileged operations, prove both the allowed and the denied
case in units and in the browser. A public product can have public write
routes: do not invent login because a method writes data or a route is called
dashboard.

1. **Requirements and material decisions.** What is being built, for whom, and
   which choices need asking rather than assuming.
2. **Architecture, contracts, and the data and journey map.** One coherent
   design, settled before files are written.
3. **Generate the application.** Implement complete vertical flows —
   validation, authorization, persistence, errors, loading and empty states,
   navigation, responsive UI — in dependency order.
   - Read `page-composition` and `frontend-design` at the moment the screens
     start, not in the opening sweep. Composition, rhythm and hierarchy are
     decided in the markup — a styling pass afterwards can only tidy what the
     structure already got wrong, and a count read thirty files ago is not a
     count.
   - Write the screens as their own stretch of work rather than trailing them
     after the API routes, and finish one screen before starting the next: two
     screens in one reply get one reply's worth of attention between them.
   - When `.agents/skills/design-system/blocks.json` exists, read the selected
     entries and their installed sources before the first screen. They are full
     blocks from the chosen provider: adapt them to the product and keep their
     hierarchy, responsiveness and states. Do not replace one with a smaller
     hand-made lookalike, do not reinstall what the design phase already saved,
     and use as many as the approved screens need. If the provider has no
     eligible blocks, use its installed framework directly rather than
     inventing choices the user never saw.
   - Finish every file the accepted scope needs before running any
     verification. No test file, no build, no browser until the application
     itself is complete.
4. **Build.** Discover the repository's package manager and its actual scripts,
   then run its finite lint/build commands and repair what fails. Write the
   README now, beside the implementation — documentation written after
   verification makes the finished evidence stale.
5. **Verify the runtime.** Start task-owned services on available configured
   ports, wait for observable readiness, then record representative pages,
   APIs, assets, persistence and failure probes with `runTests(kind="runtime")`.
   Keep the ready service for the browser journeys. Long-lived services belong
   in background process management; finite commands must finish.
6. **Run focused unit and component tests.** Re-read the Vitest skill at this
   boundary. Write the suite from real behaviour, run it through `runTests`
   with the requirement IDs it covers, and read every failure before repairing
   any of them — twenty tests failing on one missing fixture is one defect.
   Cover the critical business rules, the changed and high-risk paths,
   validation, and a regression for each repair.
7. **Review the UI.** Inventory the user-visible routes and look at
   representative desktop and mobile layouts and the critical states: missing
   content, overlap, overflow, contrast, typography, loading and error. Fix
   what reproduces and recapture those views before E2E.
8. **Run the critical E2E journeys.** Re-read the browser-e2e skill and drive
   `browserRunJourney` against the ready app. Derive the journeys from the
   approved requirements and the controls you observed; exercise
   authentication, payments or roles only where the product has them.
9. **Finish.** When the runtime, unit and E2E evidence is current and passing,
   report Done and reuse those results for the report. Do not open a second QA
   authoring pass, reread the project, or rerun checks to improve a number. A
   real failure still needs a repair and its affected check. Completion needs
   evidence recorded after the last relevant code edit.
10. **Hand over.** Give the working URL and the current verification results.

The README written in step 4 records what was actually used, not what was
intended, and is not rewritten at every completion attempt:

- the stack, and the exact installed versions of the framework, database driver
  and test runner
- every command a person needs: install, seed, run, test, coverage, build
- the ports and environment variables the app expects, and where the design
  contract lives if one was approved
- anything deliberately left out, and why
- one line naming what to say to change each of them — "to swap the test
  runner, ask for it by name; the suites and config are regenerated"

Undocumented choices can only be changed by rediscovering them, and rediscovery
is the most expensive thing a later run can be asked to do.

The active Low/Medium/High/Ultra quality profile is the verification budget. It
changes how deep the evidence goes, never which framework is used.

## First-pass reliability

- Work in small coherent vertical slices *inside* step 3, but do not pull a
  later step into it. A slice orders the implementation; it is not licence to
  build one feature, test it, and move on.
- **Batch every verification step.** Write the entire unit suite in one pass,
  run it once, read all the failures together and repair them by shared cause.
  Same for E2E: define every required journey, then run them. A
  write-run-fix loop per file is the slowest available shape — each turn costs
  a full model round trip plus the suite's own start-up, and a failure seen
  alone hides the ones that share its root cause.
- Run the cheapest relevant check after a slice so defects stay local, and
  repair the owning implementation rather than weakening tests, lengthening
  waits or looping an unchanged command. While repairing one layer, rerun its
  affected check first; return to the full ordered regression once the
  implementation is stable.
- Inspect the contracts and the rendered state before writing consumers, tests
  or selectors. Routes, links, API shapes, models, fixtures and assertions stay
  aligned from the first implementation, not from the first failure.
- Verify the durability the task asked for. If it says persistent, local-first
  or restart-safe, prove the data survives the reload or the process restart.
  A module-level array does not satisfy that unless a disposable demo was what
  the user asked for.
- Preserve the lockfile and the installed-version compatibility. Never run
  overlapping package-manager operations in one workspace, and never resolve
  two packages that share a version line independently as `latest`.
- Re-read a testing skill after compaction, when returning to its phase, or
  when new failure evidence changes the repair. Do not reread it between two
  identical no-progress retries.
- Use real shell syntax for the detected shell and read exit codes for what
  they are. A platform mismatch or a dependency-runtime failure is not
  application syntax.
- Never claim bug-free, complete or verified from generated code alone. Report
  the evidence you have and the limitation you know about.

### Start from the sketch, not from memory

Before the first file of a new application, read the sketch skill for the
selected stack: `nextjs-sketch` for Next.js + MongoDB, `mern-microservices-sketch`
for the React client + Express services stack. Each ships a complete
application under its own `sketch/` directory that was installed, unit-tested,
built, seeded, started and opened in a browser, with the run recorded in the
skill.

`listDir` that directory, `readFile` the file matching the one you are about to
write, and adapt it to this task's entities and routes. The twenty files every
application needs — the workspace manifest, the connection, the model, the
Vitest configs, the gateway, the seed — are where most first-round failures
were measured, and they have the least reason to be written from memory. Keep
the structure and the lifecycle; change the names and the fields.

### The edit protocol, mechanically

Measured across three real builds, a stale or wrong-shaped edit was the most
common avoidable failure — more common than failing tests — and each one costs
a rejected call, a re-read and a retry.

1. **A revision is valid only until the next write to that file.** Read, then
   patch in the very next call. If anything touched the file in between — your
   own earlier patch, a formatter, an install, a generator — what you are
   holding is stale. Re-read and copy the revision that read returns.
2. **Never batch two patches to the same file in one turn.** The second carries
   a revision the first already invalidated.
3. **Choose the write operation from the existing file.** `patchFile` for a
   partial change, `editFile` for a tiny exact-string change, `writeFile` with
   `overwrite:true` for a scaffold file being replaced in full — read it first.
   Leave overwrite off for a new file. File tools create parent directories.
4. **Never repair a JSON manifest with line patches.** Use `patchJson` path
   operations. Hand-managed commas and braces in `package.json` are where
   malformed-manifest failures come from, and a broken manifest blocks every
   command after it.
5. **Read a file once, not a page at a time.** Measured in one build: 72 of 73
   truncated reads were one file being walked in 20–200 line windows, and a
   single 838-line test file took eight reads to cover it twice. Every window
   is a whole model turn. `readFile` extends a slice to the end of the file
   when the context affords it, so ask for the region you need and use what
   comes back. A still-truncated read prints the one call that returns
   everything left and a map of what it did not show; jump there with
   `aroundLine` rather than walking toward it.

### When a repair is not converging

State one falsifiable hypothesis, make the smallest coherent edit, rerun the
affected check, then broaden. Read from the failing source outward — owning
function, callers, contract or schema, boundary evidence — instead of dumping
the repository into context. If the same fingerprint repeats without a state
change, the hypothesis is wrong; change it rather than the retry count.

## Finish cleanly

Stop the task-owned temporary services and close test and database resources,
unless the user asked to keep the preview running. Keep generated reports and
screenshots out of source control unless the project tracks them deliberately.
Preserve the user's work and any unrelated changes.
