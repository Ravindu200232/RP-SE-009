---
name: debugging
description: Diagnose and repair bugs, crashes, failing tests, regressions, and runtime errors using bounded evidence instead of repeated guesses or stack-specific fix tables.
---

# Evidence-first debugging

Use this skill when the task is a bug fix, test failure, crash, regression, broken behavior, or repair request. Preserve the project's actual stack and conventions; never select a framework, database, package manager, port, route, or command from this skill.

## Repair loop

1. **Reproduce exactly.** Run the smallest existing check that demonstrates the failure and retain literal output, exit status, failing command/tool, and source references.
2. **Fingerprint and cluster the failure.** Distinguish the current failure from later secondary failures. When one build emits many local import/path errors, treat them as a cluster and inspect alias/baseUrl plus the machine project-layout snapshot before touching individual imports. Do not treat a successful file read as proof that the behavior is repaired.
3. **Read around evidence.** Start at observed `file:line` locations, then inspect the owning function/module and only the callers, consumers, contracts, schema/config, or runtime boundary needed to test the hypothesis. Prefer bounded line windows and targeted search over dumping whole large files.
4. **Form one falsifiable hypothesis.** Explain how the observed source/state can produce the literal failure. If evidence contradicts it, discard it rather than layering speculative fixes.
5. **Patch the smallest coherent cause.** Repair one shared layout/config cause once when evidence clusters. For existing source, use the latest bounded read revision and send only changed line ranges with `patchFile`; for valid JSON manifests/config use `patchJson`; do not resend the full file or duplicate a large old block. Preserve public contracts unless the requirement changes them. Do not mask errors, weaken tests, add skips, inflate timeouts without a measured timing cause, or hardcode fixture-specific values.
6. **Verify the failed boundary.** Rerun the exact affected check after the edit. A read, lint-only pass, successful process spawn, screenshot, or unrelated test does not close a behavior failure.
7. **Broaden once stable.** Run the relevant regression/unit/E2E/runtime checks invalidated by the repair and inspect the final high-risk diff/owner path.

## Stagnation rule

If the same action/fingerprint fails again without a project/runtime state change, compare new evidence with the previous packet. After two unchanged failures, do not issue the same action a third time. Change the hypothesis, inspect a different ownership boundary, or make a justified state-changing repair first.

## Evidence packet expectations

Give the model enough proof to reason without guessing: tool/command, exit status, normalized fingerprint/category, concise raw output, relevant source context around observed lines, and the current verification requirement. Never paste credentials, unrelated private data, or an entire repository into the packet. Keep repeated evidence compact: if the category/fingerprint and relevant source/layout facts are unchanged, reference them instead of re-emitting long logs.

## Small-model search and research discipline

Before reading a path you have not observed, call `search` with the filename fragment, symbol, failing owner, or config topic. Use its best observed path exactly. Do not burn retries on extension variants or sibling directories. Use `inspectProject` for source roots, actual manifest script commands, observed test roots/files and config candidates before writing shell commands.

If the diagnosis depends on current package, framework, CLI, migration or API behavior, use `webResearch` to search and READ the most relevant current primary/official page before the repair command. Search snippets alone are not command evidence. If project-local `recallKnowledge` returns a previously verified repair lesson, use it as a hypothesis shortcut, then re-read the current owner and re-verify current external facts before editing.

A successful repair may be stored automatically as a small project-local verified lesson only after fresh verification closes the failure. Never "teach" the store from an unverified guess; this learning is retrieval memory, not model-weight training.
