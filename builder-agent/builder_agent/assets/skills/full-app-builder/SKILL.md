---
name: full-app-builder
description: Build or substantially extend a complete application from requirements through stack-native build/debug, focused unit tests, critical E2E journeys, runtime probes, visual UI review, and final regression.
---

# Full application builder

Use this skill when the user asks to create, generate, or substantially complete an application. Use the stack selected by the user and the matching sketch, with Vitest unit/integration verification and AgentX direct-CDP browser E2E. Discover versions, paths, scripts and product requirements; preserve the approved stack.

## Discover before acting

For a focused change to an existing application, start with the requested behaviour and its affected files. Read only skills that resolve a concrete uncertainty; the full greenfield stack checklist is not the starting sequence for every feature. Plan evidence kinds together so the first test execution records unit/runtime/browser results with matching requirement IDs. A targeted test already run through `runTests` does not need another execution merely to enter a later phase.

Use the existing conversation, verification scope and evidence when continuing a run. A new phase does not invalidate current reads or passing checks. Inspect missing evidence first; reread files when their content is missing, changed, or needed to resolve a specific uncertainty. Preserve the approved product and design.

A follow-up chat message continues the same project conversation. Interpret references such as "that page" or "add this too" using the earlier request, implementation, and decisions already in memory. Apply the new request to the current application; reopen broad discovery only when the requested change or missing context calls for it. Reuse unchanged skill text from the transcript and inspect the current files affected by the new work.

Read the request, machine project-layout snapshot, project guidance, manifests, lockfiles, existing source, environment examples, scripts, and task-matched project skills. Use the snapshot's observed script commands/test roots/config candidates and call `search` before any uncertain file or directory; never probe guessed path/extension variants. Detect the actual operating system and shell. Treat the selected builder contract and installed compatible versions as authoritative. When a required command or API is uncertain or could have changed, inspect local CLI help and current official documentation rather than relying on model memory. Use `recallKnowledge` to reuse prior project-verified lessons, but re-check current code and time-sensitive docs.

For a greenfield workspace, decide one canonical application/source root from the generator output plus observed alias/baseUrl configuration before writing feature files. Never create a second parallel `lib`/`models`/`components`/route tree outside the configured source root merely because the workspace root is convenient. Re-run `inspectProject` after scaffold promotion or any structural move.

For a greenfield workspace, inspect existing AgentX metadata before scaffolding. Metadata directories do not make the workspace an existing application. If a generator refuses a non-empty root, inspect its help for a no-install option and use a clean staging directory. Promote an explicit inventory of application source, public assets, configuration, and manifests into the intended root; never use an unfiltered whole-tree recursive copy or move. Dependency directories, nested version-control metadata, build caches, coverage, test results, screenshots, and browser artifacts must stay behind. Install dependencies once in the final root. If the generator cannot skip installation, either keep the generated child as the deliberate application root or transfer only that explicit inventory—do not copy its installed dependency tree.

## Required delivery order

For an assigned verification pass (for example QA unit or QA E2E), apply only that pass's part of this workflow and return its evidence to the caller. Do not restart other phases or declare them blocked; the calling workflow handles them. Product repairs remain available when a test exposes a defect.

Derive authentication and authorization from the approved product requirements. For accounts, private data or privileged operations, verify both allowed and denied access in unit and browser tests. Public products without accounts can expose public write routes; do not invent login because an HTTP method writes data or a route is named dashboard.

1. **Generate the application.** Convert the requirements into one coherent architecture and implement complete vertical flows, including validation, authorization, persistence, errors, loading/empty states, navigation, and responsive UI. Read the `frontend-design` skill before writing the first page and apply it as you write: composition, spacing rhythm and hierarchy are decided in the markup, and a styling pass afterwards can only tidy what the structure already got wrong. Do not stop at a scaffold or a collection of disconnected pages. Finish every file the accepted scope needs before running any verification: no test file, no build, no browser until the application itself is complete.
   Before writing or running tests, define the verification scope. Run the production build and runtime readiness first. Run unit/integration suites through `runTests` with the requirement ids they cover; do not run the same npm test command earlier through `executeTerminal` and repeat it later merely to record evidence.
   When `.agents/skills/design-system/blocks.json` exists, read the selected entries and the installed source paths before writing the first screen. They are full blocks from the chosen provider. Adapt those complete structures to the product and preserve their hierarchy, responsiveness and states; do not replace them with smaller hand-made lookalikes. Use every selected block the approved screens need, with no arbitrary count limit. Do not search for or reinstall the same blocks during the build because the design phase already saved them locally. If the selected provider has no eligible full blocks, use its installed framework directly and do not invent block choices that were never shown to the user.
2. **Build the application.** Discover the repository's package manager and actual scripts, then run its finite lint/build commands. Repair build failures before starting the runtime. Write the README's "Built with" and run instructions now, alongside the implementation; documentation writes after verification would unnecessarily make the finished evidence stale.
3. **Verify the runtime.** Start task-owned services on available configured ports, wait for observable readiness, and record representative pages/APIs/assets/persistence/failure probes with `runTests(kind="runtime")`. Keep the ready service for the later browser journeys. Long-lived services belong in background process management; finite commands must finish.
4. **Run focused unit/component tests.** Re-read the Vitest skill at this phase boundary. Write the suite from real behavior, then run it through `runTests` with requirement IDs. Read failures together and repair their shared causes before another execution. Cover critical business rules, changed/high-risk paths, validation, and repaired regressions. Coverage percentages are optional diagnostics; do not add or rerun tests solely to raise them.
5. **Review the UI visually.** Inventory user-visible routes and inspect representative desktop/mobile layouts and critical states. Check missing content, overlap, overflow, contrast, typography and loading/error states. Fix reproducible defects and recapture affected views before final E2E.
6. **Run critical E2E journeys.** Re-read the browser-e2e skill and use `browserRunJourney` against the ready app. Derive journeys from the approved requirements and observed controls; exercise authentication, payments or roles only when the product includes them. Do not generate project E2E framework files.
7. **Finish after E2E.** When the required runtime, unit and E2E evidence is current and passing, report Done. Reuse these results for the report; do not start a second QA authoring pass, reread the whole project or rerun checks to improve a coverage number. A real failure still needs a repair and an affected check.
8. **Hand the project over.** Summarize the working URL and the current verification results. The README written during implementation starts with a short "Built with" section before the setup instructions, so the choices remain visible to whoever opens the repository next. Do not rewrite it at every completion attempt.

   It records what was actually used, not what was intended:

   - the stack, and the exact versions installed for the framework, database driver and test runner
   - every command a person needs: install, seed, run, test, coverage, build
   - the ports and environment variables the app expects, and where the design contract lives if one was approved
   - anything deliberately left out, and why

   Then one line naming what to say to change each of them — for example "to swap the test runner, ask for it by name; the suites and config are regenerated". A project whose choices are undocumented can only be changed by rediscovering them, and rediscovery is the most expensive thing a later run can be asked to do.

## First-pass reliability

- Work in small coherent vertical slices *within* step 1, but do not carry a later step into it. Slices order the implementation; they are not an excuse to build one feature, test it, and move on. Finish the whole application first, then build, then test.
- Batch every verification step. Write the entire unit suite in one pass, run it once, read all the failures together, and repair them by shared cause before running it again. Do the same for E2E: define every required journey, then run them. A write-run-fix loop per file is the slowest available shape — each turn of it costs a full model round trip plus the suite's own start-up, and a failure seen on its own hides the ones that share its root cause.
- Existing-file updates should be revision-safe line patches: read the relevant region, then transmit only changed lines; do not regenerate unchanged modules. For valid JSON manifests/config, use `patchJson` path operations instead of hand-managing commas/braces with line patches.

### Start from the sketch, not from memory

Before writing the first file of a new application, read the sketch skill for
the selected stack: `nextjs-sketch` for Next.js + MongoDB, or
`mern-microservices-sketch` for the React client + Express services stack. Each
one ships a complete application under its own `sketch/` directory that was
installed, unit-tested, built, seeded, started and opened in a browser — the
run is recorded in the skill.

`listDir` that directory, `readFile` the file matching the one you are about to
write, and adapt it to this task's entities and routes. The twenty files every
application needs — the workspace manifest, the connection, the model, the
Vitest configs, the gateway, the seed — are where most first-round failures
were measured, and they are the files with the least reason to be written from
memory. Keep the structure and the lifecycle; change the names and the fields.

### The edit protocol, mechanically

Measured across three real builds, a stale or wrong-shaped edit was the single
most common avoidable failure — more common than failing tests. Every one costs
a rejected call, a re-read and a retry. These four rules remove almost all of
them:

1. **A revision is only valid until the next write to that file.** Read, then
   patch in the very next call. If anything at all touched the file in
   between — your own earlier patch, a formatter, an install, a generator — the
   revision you are holding is stale. Re-read and use the revision that read
   returns, copied exactly.
2. **Never batch two patches to the same file in one turn.** The second carries
   a revision the first has already invalidated. Patch, see the new revision,
   then patch again.
3. **Choose the write operation from the existing file.** Use `patchFile` for
   a partial change, or `editFile` for a tiny exact-string change. If a scaffold
   file must be replaced in full, read it first and use `writeFile` with
   `overwrite:true` in the initial call. For a new file, leave overwrite off.
   File tools create parent directories; a separate shell mkdir is unnecessary.
4. **Never repair a JSON manifest with line patches.** Use `patchJson` path
   operations. Hand-managing commas and braces in `package.json` is where
   malformed-manifest failures come from, and a broken manifest blocks every
   command after it.
5. **Read a file once, not a page at a time.** Measured in one build: 72 of 73
   truncated reads were one file being walked in 20-200 line windows, and a
   single 838-line test file took eight reads at one revision to cover 838
   lines twice over. Every window is a whole model turn. `readFile` already
   extends a slice to the end of the file whenever the context window affords
   it, so ask for the region you need and use what comes back. When a read is
   still truncated it prints the one call that returns everything left — both
   `offset` and `limit` given — and a map of the declarations, `describe` and
   `it` blocks it did not show, with their line numbers. Jump to one of those
   with `aroundLine`; never walk toward it.
- Inspect contracts and rendered state before writing consumers, tests, or selectors. Keep routes, links, API shapes, models, fixtures, and assertions aligned from the first implementation.
- Verify the requested durability contract. If the task says persistent, offline/local-first, or restart-safe, prove data survives the relevant reload or process restart; module-level arrays and client-only state do not satisfy that requirement unless the user explicitly requested a disposable demo.
- Preserve the lockfile and installed-version compatibility. Never run overlapping package-manager operations in one workspace or pair independently resolved `latest` packages that must share a version line.
- Run the cheapest relevant check after each slice so defects remain local; repair the owning implementation instead of weakening tests, increasing arbitrary waits/retries, or looping unchanged commands.
- While repairing one verification layer, rerun its affected check first. Do not repeatedly rerun an already-passing unrelated layer after every small edit; return to the complete ordered regression once the implementation is stable.
- Re-read a testing skill after context compaction, when returning to its phase after another verification layer, or when materially new failure evidence changes the repair strategy. Do not spend context rereading the same file between identical no-progress retries.
- Use actual shell syntax and interpret tool-specific exit codes correctly. Do not treat a platform mismatch or dependency-runtime failure as application syntax.
- Never claim bug-free, complete, or verified from generated code alone. Report exact current evidence and any remaining limitation.

## Finish cleanly

Stop task-owned temporary services and close test/database resources unless the user asked to keep the preview running. Keep generated reports and screenshots out of source control unless the project explicitly tracks them. Preserve user work and unrelated changes.


## Quality profile and phase ledger
Use the active Low/Medium/High/Ultra quality profile as the verification budget. The stack remains the single fixed builder contract; quality changes evidence depth, not framework choice.

For a full application, keep these outcomes in order:
1. requirements/project discovery,
2. material decisions/questions,
3. architecture + contracts + data/journey map,
4. dependency-ordered implementation,
5. project-native build/static checks where applicable,
6. real runtime/readiness/public-boundary evidence,
7. unit/component evidence,
8. asserted critical E2E journeys,
9. selected visual evidence where applicable,
10. final risk audit when the profile requires it.

A phase can be N/A only with project/task evidence. A failed or pending done-condition is a hard phase barrier: do not start or announce the next phase until it passes or is evidence-backed N/A. A failed verification returns to the owning phase; do not restart the whole build. Completion requires current evidence after the last relevant code edit.

### Ultra read/analyze/edit loop
Use targeted deep reading: failing source -> owning function/component -> callers/consumers -> contract/schema/config -> boundary/runtime evidence. Do not dump the repository into context. State one hypothesis, make the smallest coherent edit, rerun the affected check, then broaden verification. If the same fingerprint repeats without a state change, change the hypothesis instead of looping.

## Direct browser E2E

Use AgentX `browserRunJourney` for E2E. Keep E2E automation outside the generated application: no project-level browser-test package, config, spec suite, or browser installation is required. Record real UI assertions, browser diagnostics, screenshots when useful, and requirement IDs in the testing ledger.
