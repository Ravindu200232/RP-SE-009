# Codex final machine-validation prompt — AgentForge

You are finishing the AgentForge repository in this folder. Work on the real repository, inspect evidence before editing, and make only changes justified by failing checks. Do not redesign or roll back already-passing behavior.

## Current state that must be preserved

The repository has already been refactored and statically validated for these behaviors:

- Agent code is grouped under `agents/{planning,build,analysis,features,data,core,server}` and QA under `qa_agent/{core,unit,e2e,verification,server}`.
- Internal imports point directly at implementation modules. Do not recreate tiny compatibility/re-export facade files.
- No Python implementation file under `agents`, `qa_agent`, or `server_modules` exceeds 1000 lines.
- `server_modules/agent`, `server_modules/qa`, and `pipeline_core` are intentionally gone.
- Builder behavior must not be damaged by architecture cleanup.
- E2E performs a plan/SRS-vs-generated-code preflight before browser execution.
- E2E captures browser console/page errors and can use exact stack/source evidence for scoped repair.
- E2E stage reporting is authoritative: each final accepted journey reports `stage_passed/stage_total`, failed/not-reached stages, and all final journeys aggregate into one overall E2E proof percentage. Repair retries must never be double-counted.
- Example invariant already validated: 10/12 stages = 83%; with one passing global integrity proof, 11/13 = 85%.
- Targeted unit-test runs merge back into the whole-app Vitest report instead of erasing unrelated older suites.
- Generated apps must use server-derived authenticated ownership for user-specific data; never trust arbitrary client user IDs. Authentication-free apps must not get fake auth added.
- Mutations must update visible data without requiring a manual browser refresh.
- Auth/signup/role E2E flows must be inferred from requirements + current generated source/runtime evidence, never hard-coded to `/login` or one role landing route.
- E2E must not invent magic values/testids such as `WELCOME10`, `999`, `mark-paid`, or expected text unless grounded in the actual SRS/source/runtime DOM.
- SRS native rendering supports all 11 diagram kinds and must keep routed/curved connections and explicit system/data/integration content.
- The removed five-design/theme-selection flow must stay removed.
- Builder/SRS activity feeds use the supplied GIF assets and paced latest-five chat-style activity; do not revert to a fast log dump or progress rail.
- `Gemma 4 31B` is presented as Local in the UI, not Cloud.
- Windows Vercel `.cmd/.bat` launchers use COMSPEC-safe argv; AWS IAM Identity Center uses a non-blocking device-flow design.
- Electron/start integration source is present, but it was not used as a release blocker in the previous environment because dependency installation/launch timed out there.

## Checks already passed before this handoff

These passed in the source used to create this ZIP:

1. Python compile for `agents`, `qa_agent`, `server_modules`, SRS agent, deployment agent and root entrypoints.
2. `server_runtime` + direct Builder/Architect/Analyzer/BugFixer/Vitest/E2E import smoke.
3. Local-import graph scan: no missing internal Python module targets.
4. Studio static UI contracts: 24/24.
5. Human build activity mapper verification.
6. Upload naming verification.
7. Progress + E2E-rate verification, including 10/12 = 83% and 11/13 = 85%.
8. Unit-report merge regression: unrelated test suites survive targeted reruns.
9. SRS renderer smoke: all 11 native diagrams emitted non-empty SVGs.
10. Windows deployment launcher pure-argv regression for Vercel `.cmd` and native AWS executable.
11. Electron JS syntax checks for `desktop/main.js`, `desktop/runtime.js`, `desktop/preload.js`.
12. No exact duplicate Python implementation files and no >1000-line Python files in the main agent/server trees.

## Your job

Run the environment-dependent final checks on the user's real Windows machine and fix only real failures.

### A. Studio production install/build

From `studio/`:

```powershell
npm ci
npm run build
```

If `npm ci` fails because of network/registry/transient download issues, diagnose that separately from source failures. Do not mutate application code to hide a network failure. Once dependencies install, `npm run build` must exit 0.

Fix any real Next.js/React/build error you find, then rerun until green. Do not weaken lint/build/type/runtime checks merely to get a pass.

### B. Electron on Windows

From `desktop/`:

```powershell
npm ci
npm start
```

Then run root `start.bat` and confirm it opens the Electron app, starts the Python backend from the repository root, starts/uses Studio correctly, and shuts child processes down cleanly.

If Electron itself times out only because package installation/network is slow, record that as an environment issue. If it crashes from paths/process management, fix the actual root cause.

### C. Deployment sign-in on Windows

Test both real flows from the UI:

- Vercel sign-in: must not crash when `vercel.cmd` is launched; completion/status should be detected without freezing the app.
- AWS IAM Identity Center/device sign-in: opening/polling/completing the flow must not open a crashing transient CMD path and must not block the server thread.

Do not store raw credentials in persistent project files/logs.

### D. One real generated-app end-to-end validation

Generate at least one realistic authenticated, role-based app with user-owned data (booking/cart/history style is ideal) and one auth-free app (portfolio/content style).

For the authenticated app verify:

- signup/login/session/role landing behavior is learned from the generated app rather than assumed;
- user A never sees user B's records;
- records written by a user immediately appear in list/table/history UI without manual refresh;
- role-restricted controls/routes behave correctly;
- browser console and `pageerror` evidence is captured and repaired when a real app bug occurs;
- E2E starts only after comparing the approved plan/SRS with the code currently on disk;
- Testing UI shows each journey as `passed stages / total stages`, failed/not-reached stages, and the aggregate overall E2E percentage;
- repair attempts are not double-counted as extra tests.

For the auth-free app verify the builder does not invent login/ownership/session infrastructure.

### E. SRS visual quality

Create a non-trivial SRS with multiple actors, workflows, entities, integrations and lifecycle states. Verify all 11 diagrams are readable in the actual SRS UI/PDF:

- connectors touch intended nodes/ports;
- lines do not visually terminate in empty space;
- relationships use routed/curved/orthogonal paths where appropriate instead of a wall of straight crossing lines;
- architecture diagrams contain meaningful actors, system boundary, modules, data stores and integrations;
- diagrams do not silently fall back to an empty/stub image.

Fix renderer geometry if the real rendered output shows overlap/disconnection.

### F. Final regression gates

After any edits rerun at minimum:

```powershell
python -m compileall -q agents qa_agent server_modules srs-agent\srs_agent deployment-agent\deploy_agent server.py server_runtime.py pipeline.py
node studio\scripts\verify_test_counts.mjs
node studio\scripts\verify_progress.mjs
node studio\scripts\verify_activity.mjs
node studio\scripts\verify_uploads.mjs
python studio\scripts\verify_ui_contract.py
node --check desktop\main.js
node --check desktop\runtime.js
node --check desktop\preload.js
```

Also rerun `npm run build` in `studio/` after the final code change.

Search for stale imports/references to removed paths and ensure no new tiny import-only facades were introduced. Keep implementation modules under 1000 lines where practical and comments short/human-readable.

## Non-negotiable rules

- Do not hard-code one sample app's routes, copy, role names, IDs, promo codes, prices, testids, statuses or database collections into generic AgentForge logic.
- Do not make a failing test pass by deleting the test, weakening an assertion, skipping E2E, or converting failures to warnings.
- Do not count retry attempts as separate E2E tests.
- Do not trust client-provided ownership IDs in authenticated generated apps.
- Do not restore removed design/theme selection infrastructure.
- Do not recreate `pipeline_core`, `server_modules/agent`, `server_modules/qa`, or old flat compatibility wrappers.
- Do not replace the user's supplied GIFs with generated images.
- Prefer deterministic/source/runtime evidence before LLM guesses.
- Preserve Builder output behavior while fixing infrastructure.

## Completion output

When finished, give a concise report with:

1. exact failures found and root causes;
2. files changed;
3. commands/tests run with pass counts;
4. Studio production-build result;
5. Electron Windows result;
6. AWS/Vercel live sign-in result;
7. real generated-app unit/E2E result including overall E2E stage percentage;
8. any remaining environment-only limitation.

Do not say “100% complete” unless all applicable checks above actually passed.
