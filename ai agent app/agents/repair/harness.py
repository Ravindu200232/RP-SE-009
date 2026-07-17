"""agents/repair/harness.py — the bounded, evidence-based repair harness (P1).

Replaces the old one-error-per-`next build` loop. Each round: **diagnose ALL blockers once** (module
gate + contract scan + `tsc --noEmit`), snapshot the best state, then repair every file cluster
producers-first — deterministic structural fixers, then ONE guarded LLM patch addressing all of that
file's errors at once. A patch that introduces a forbidden suppression is reverted; a round that
regresses the blocker count is rolled back; a file that won't converge is regenerated (round 3). Ends
with a real `next build` (tsc-clean ≠ build-green) and a bounded residual loop.

The LLM only diagnoses + patches; reproduction, ordering, validation, rollback and verification are
deterministic — this is why it converges in 1–2 rounds instead of dozens.
"""
from __future__ import annotations

from pathlib import Path

from agents import module_gate, llm
from agents.bugfix_agent import BugFixAgent
from agents.repair import forbidden
from agents.repair.checkpoint import Checkpoint
from agents.repair.diagnose import diagnose, _priority
from agents.tools.command_runner import CommandRunner
from agents.tools.fingerprint import fingerprint, is_protected


class RepairHarness:
    def __init__(self, project_dir, emit=None, model=None, registry=None, regen=None, repair_model=None,
                 on_revert=None):
        self.dir = Path(project_dir)
        self.emit = emit or (lambda *a, **k: None)
        self.runner = CommandRunner(project_dir, self.emit)
        self.fp = fingerprint(project_dir)
        self.registry = registry
        self.regen = regen or (lambda rel: False)
        # Told when a regen is rolled back, so the project's PROGRESS log doesn't count the discarded
        # write as churn. Optional — the harness works standalone.
        self.on_revert = on_revert or (lambda rel: None)
        # A file that regressed once under regen never recovered in testing (9->11, 8->11, 8->10 on the
        # same file), so each retry only burned a full-context LLM call. One attempt per file per run.
        self._regen_tried: set[str] = set()
        # Files whose LLM patch made the build worse — don't hand them the same knife twice.
        self._patch_banned: set[str] = set()
        # Repair uses the code-specialised model (qwen2.5-coder); generation stays on `model` (gemma),
        # used only by the `regen` fallback. Keeping them separate is the whole point.
        self.gen_model = model or llm.GEN_MODEL
        self.repair_model = repair_model or llm.REPAIR_MODEL
        self.bf = BugFixAgent(project_dir, self.emit, self.repair_model, regen=regen)
        self.ckpt = Checkpoint(project_dir)

    def _log(self, text: str):
        self.emit("log", {"text": text})

    # ── per-file repair ─────────────────────────────────────────────────────────
    def _deterministic(self, rel: str, errors: list[dict]) -> bool:
        """Cheap, always-safe structural fixers keyed off the error text."""
        msgs = " ".join(e["message"].lower() for e in errors)
        did = False
        if any(k in msgs for k in ("redeclare", "redefined", "duplicate", "already been declared")):
            did |= self.bf.dedup_exports(rel)
        if any(k in msgs for k in ("expected", "jsx", "unterminated", "unexpected token",
                                   "expression expected", "'</'")):
            did |= self.bf.fix_bad_closing_tags(rel)
            did |= self.bf.fix_import_syntax(rel)
        if "<eof>" in msgs or "end of file" in msgs:
            did |= self.bf.complete_truncated(rel)
        # invalid / hallucinated react-icons name → remap to the compiler's suggestion or a safe fallback
        if "react-icons" in msgs or "exported member" in msgs or "doesn't exist in target module" in msgs:
            for e in errors:
                did |= self.bf.fix_bad_icon_import(rel, e["message"])
        # entity/UI name clash (e.g. `Table` from @/types vs the UI primitive) → alias the UI import
        if any(k in msgs for k in ("duplicate identifier", "import declaration conflicts",
                                   "refers to a value, but is being used as a type",
                                   "only refers to a type, but is being used as a value")):
            did |= self.bf.fix_ui_entity_collision(rel)
        # used-but-not-imported UI primitive / React hook / feature component → add the import
        for e in errors:
            if "cannot find name" in e["message"].lower():
                did |= self.bf.fix_missing_ui_import(rel, e["message"])
        return did

    def _guarded_llm(self, rel: str, line: int, message: str, _retry: bool = False,
                     hard: bool = False) -> bool:
        """Run a repair (gemma `fix_one`, or the cloud `fix_hard` when hard=True), but REVERT a patch
        that introduced a forbidden suppression. On the first rejection, retry ONCE with explicit
        guidance to fix it genuinely — turning a reflexive `as any` into a real fix."""
        fp = self.dir / rel
        try:
            before = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        fixer = self.bf.fix_hard if hard else self.bf.fix_one
        if not fixer(rel, line or 1, message):
            return False
        after = fp.read_text(encoding="utf-8")
        bad = forbidden.introduced(after, before)
        if bad:
            fp.write_text(before, encoding="utf-8")
            self.emit("file", {"path": rel, "content": before})
            if not _retry:
                guided = (message + f"\n\nDO NOT use {', '.join(bad)} or any suppression — that is "
                          "forbidden. Fix it GENUINELY: type records with the entity DTO "
                          "(`import type {{ X }} from '@/types'`), or coerce values with "
                          "String(...)/Number(...)/Boolean(...), or add the correct type. Never cast to any.")
                return self._guarded_llm(rel, line, guided, _retry=True, hard=hard)
            self._log(f"rejected patch to {rel}: forbidden {', '.join(bad)} — reverted (retry failed)")
            return False
        return True

    def _repair_cluster(self, cluster: dict, rnd: int):
        rel = cluster["file"]
        if is_protected(rel, self.fp):
            return
        errors = cluster["errors"]
        self._deterministic(rel, errors)
        combined = "; ".join(dict.fromkeys(e["message"] for e in errors[:5]))
        # Escalation ladder: rounds 0-1 = gemma first-pass (fast/local). Round >=2 (still stuck) =
        # cloud model (nemotron, max ctx + thinking); if even that can't fix it, regenerate the file.
        if rnd >= 2:
            if self._guarded_llm(rel, errors[0]["line"], combined, hard=True):
                return
            self._guarded_regen(rel)
            return
        self._guarded_llm(rel, errors[0]["line"], combined)

    def _guarded_regen(self, rel: str):
        """Last-resort whole-file regeneration, guarded: keep the result ONLY if it strictly reduces the
        blocker count. A blind rewrite of a working-ish file can delete good behaviour and unmask many
        hidden errors (the 9->98 blow-up), so revert the single file if it didn't help. Capped at one
        attempt per file per run — a file that regressed once does not recover on a retry."""
        if rel in self._regen_tried:
            self._log(f"skipping regen of {rel} — already tried once this run")
            return
        self._regen_tried.add(rel)
        fp = self.dir / rel
        before_content = fp.read_text(encoding="utf-8") if fp.exists() else None
        before_b = diagnose(self.dir, self.runner, self.registry)["blockers"]
        if not self.regen(rel):
            return
        after_b = diagnose(self.dir, self.runner, self.registry)["blockers"]
        if after_b >= before_b:
            if before_content is not None:
                fp.write_text(before_content, encoding="utf-8")
                self.emit("file", {"path": rel, "content": before_content})
            self.on_revert(rel)
            self._log(f"regen of {rel} did not reduce blockers ({before_b}->{after_b}); reverted file")
        else:
            self._log(f"regenerated {rel} (cloud repair exhausted; blockers {before_b}->{after_b})")

    def _cluster_build(self, findings: list[dict]) -> list[dict]:
        """Group build findings by file, producers-first (same ordering as the tsc diagnose pass)."""
        by_file: dict[str, list[dict]] = {}
        for f in findings:
            by_file.setdefault(f["file"], []).append(f)
        clusters = [{"file": rel, "errors": sorted(errs, key=lambda e: e["line"])}
                    for rel, errs in by_file.items()]
        clusters.sort(key=lambda c: (_priority(c["file"]), c["file"]))
        return clusters

    def _build_fix_loop(self, max_iters: int = 4) -> bool:
        """tsc-clean ≠ build-green: `next build` also runs SWC parse + route-handler type checks that
        `tsc --noEmit` misses. Repair the located build errors, rebuild, repeat — bounded and
        oscillation-guarded (stop if the same top error survives), reusing the producers-first repair
        + `.locode` memory context of the tsc rounds. Replaces the old 'return the failure' dead end."""
        ok = False
        seen: dict[str, int] = {}
        prev_counts: dict[str, int] = {}
        patched: dict[str, str] = {}     # file -> content before this pass's patch
        for it in range(max_iters):
            ok, findings, _out = self.bf.build_findings()
            if ok:
                self._log(f"next build GREEN (after {it} build-fix pass(es))" if it else "next build GREEN")
                return True
            if not findings:
                self._log("next build failed but no error could be located — unresolved")
                return False

            counts: dict[str, int] = {}
            for f in findings:
                counts[f["file"]] = counts.get(f["file"], 0) + 1
            # A patch is only worth keeping if the file it touched got better. `forbidden.introduced`
            # catches a patch that cheats; nothing caught a patch that simply broke the file — that is
            # how a repair pass introduced `Expected 'from', got 'as'` into a file it was fixing.
            undone = []
            for rel, before in patched.items():
                if counts.get(rel, 0) > prev_counts.get(rel, 0):
                    (self.dir / rel).write_text(before, encoding="utf-8")
                    self.emit("file", {"path": rel, "content": before})
                    self._patch_banned.add(rel)
                    undone.append(rel)
            patched = {}
            if undone:
                self._log("reverted patch(es) that ADDED build errors: " + ", ".join(undone))
                prev_counts = {}
                continue                  # rebuild from the restored state before planning again
            prev_counts = counts

            top = f"{findings[0]['file']}:{findings[0]['message'][:80]}"
            seen[top] = seen.get(top, 0) + 1
            if seen[top] > 2:
                self._log(f"build error not converging ({top}) — stopping (release blocked)")
                return False
            self._log(f"build-fix pass {it + 1}: {len(findings)} build error(s); top = {top}")
            self.ckpt.snapshot(f"pre-build-fix-{it}")
            for c in self._cluster_build(findings):
                rel = c["file"]
                if is_protected(rel, self.fp):
                    continue
                if rel in self._patch_banned:
                    self._log(f"not patching {rel} again — its last patch made the build worse")
                    continue
                try:
                    patched[rel] = (self.dir / rel).read_text(encoding="utf-8")
                except Exception:  # noqa: BLE001
                    patched.pop(rel, None)
                # early passes = gemma first-pass; later passes escalate to the cloud model (rnd>=2).
                self._repair_cluster(c, rnd=0 if it == 0 else 2)
        # final measure after exhausting the loop
        ok, _ = self.bf.build()
        return ok

    # ── driver ──────────────────────────────────────────────────────────────────
    def run(self, max_rounds: int = 3) -> bool:
        # Free VRAM so the 14B repair model loads 100% on GPU (a CPU-spilled repair model is unusably
        # slow). Generation is done by now; regen (round 3) will transparently reload gemma if needed.
        if self.repair_model != self.gen_model:
            llm.unload(self.gen_model)
            llm.ensure_loaded(self.repair_model, llm.REPAIR_OPTS)
            self._log(f"repair model: {self.repair_model} (full-GPU; unloaded {self.gen_model})")
        # deterministic import repair up front (one-shot module-not-found cure)
        module_gate.repair_imports(self.dir)
        prev = None
        for rnd in range(max_rounds):
            dg = diagnose(self.dir, self.runner, self.registry)
            b = dg["blockers"]
            self._log(f"diagnose round {rnd + 1}: {b} blocker(s) in {dg['files']} file(s)  {dg['counts']}")
            if b == 0:
                break
            if prev is not None and b > prev and self.ckpt.has():
                restored = self.ckpt.restore()
                self._log(f"round regressed {prev}->{b}; rolled back {len(restored)} file(s), stopping escalation")
                break
            self.ckpt.snapshot(f"round-{rnd}", {"blockers": b})
            prev = b
            for c in dg["clusters"]:
                self._repair_cluster(c, rnd)

        # final deterministic sweep — catch trivial JSX typos (`</div>>`, stray/garbage closing tags,
        # `} }` imports) in files regenerated in the last round (no repair pass runs after a round-3
        # regen). Runs ONLY the NON-DESTRUCTIVE fixers (no-ops on clean files), ONLY on files that still
        # have a blocker, and is GUARDED: if it regresses the blocker count it is rolled back.
        final = diagnose(self.dir, self.runner, self.registry)
        if final["blockers"]:
            self.ckpt.snapshot("pre-sweep")
            swept = 0
            for c in final["clusters"]:
                rel = c["file"]
                if is_protected(rel, self.fp):
                    continue
                if self.bf.fix_bad_closing_tags(rel) | self.bf.fix_import_syntax(rel):
                    swept += 1
            if swept:
                after = diagnose(self.dir, self.runner, self.registry)["blockers"]
                if after > final["blockers"]:
                    self.ckpt.restore()
                    self._log(f"final sweep regressed {final['blockers']}->{after}; reverted")
                else:
                    self._log(f"final deterministic sweep fixed {final['blockers'] - after} blocker(s)")

        # tsc-clean is necessary but not sufficient — next build also runs SWC parse + route checks.
        # A BOUNDED, oscillation-guarded build-fix loop reads the real `next build` errors, feeds each
        # (with file location + `.locode` memory) to the repair LLM, and rebuilds. This is deliberately
        # small and guarded — the unguarded 8-pass loop is what let bad fixes mask/regress other files.
        ok = self._build_fix_loop(max_iters=4)
        self._log("next build GREEN" if ok else
                  "next build NOT green after the repair + build-fix loop — unresolved (release blocked)")
        return ok
