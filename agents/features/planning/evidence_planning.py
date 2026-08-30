"""Feature planning steps split by responsibility."""
# Source: feature_contract.py — imported helper(s) come from this file.
from agents.features.feature_contract import *
# Source: feature_prompts.py — imported helper(s) come from this file.
from agents.features.feature_prompts import render_feature_prompt

class FeatureEvidencePlanningMixin:
    # Returns protocol/evidence gaps that make a plan speculative.
    def _analysis_issues(self, spec: FeatureSpec, mode: str,
                             required_evidence_paths=None) -> list[str]:
        """Return protocol/evidence gaps that make a plan speculative."""
        ctx = spec.context or {}
        issues = []
        for key in ("current", "gap", "cause", "verify"):
            if not str(ctx.get(key) or "").strip():
                issues.append(f"missing {key.upper()} analysis")
        evidence = ctx.get("evidence") or []
        evidence_paths = {str(e.get("path") or "").replace("\\", "/")
                          for e in evidence if isinstance(e, dict)}
        if not evidence_paths:
            issues.append("no source EVIDENCE was cited")

        files = getattr(self.arch, "files", {}) or {}
        existing_edits = [f["path"] for f in spec.files
                          if f.get("action") == "edit" and f.get("path") in files]
        missing = [p for p in existing_edits if p not in evidence_paths]
        if missing:
            issues.append("planned edit(s) not yet evidenced: " + ", ".join(missing[:12]))

        for rel in required_evidence_paths or []:
            rel = str(rel or "").replace("\\", "/")
            if rel and rel in files and rel not in evidence_paths:
                issues.append(f"selected/failing owner {rel} was not evidenced")

        confidence = str(ctx.get("confidence") or "").strip().lower()
        if confidence not in ("high", "medium", "low"):
            issues.append("missing CONFIDENCE")
        elif confidence == "low":
            issues.append("analysis confidence is low")
        return issues

    # Deterministically expose source/import graph for unproven edits.
    def _evidence_bundle(self, paths) -> str:
        """Deterministically expose source/import graph for unproven edits."""
        # From: agents/core/workspace/source_workspace.py
        tools = WorkspaceTools(self.arch)
        files = getattr(self.arch, "files", {}) or {}
        out, used = [], 0
        budget = max(12000, int(self._budget_chars() * 0.18))
        for rel in paths or []:
            rel = str(rel or "").strip().replace("\\", "/")
            if not rel or rel not in files:
                continue
            # From: agents/core/workspace/dependency_tools.py
            # From: agents/core/workspace/file_tools.py
            blocks = [tools.read_file(rel), tools.importers(rel),
                      tools.dependency_closure(rel)]
            block = f"### Evidence for {rel}\n" + "\n".join(blocks)
            if out and used + len(block) > budget:
                break
            out.append(block)
            used += len(block)
        return "\n\n".join(out)

    # Builds a bounded feature-change plan from source evidence, model reasoning, and the exact files allowed for this
    # edit.
    def _plan(self, system: str, user: str, max_reads: int | None, what: str,
              *, allow_empty: bool = False, mode: str = "feature",
              required_evidence_paths=None, investigation_paths=None) -> FeatureSpec:
        """Run a bounded inspect→hypothesize→prove planning loop."""
        self.arch._workspace_tool_cache = {}
        # From: agents/features/feature_contract.py
        convo = ([{"role": "system", "content": system + "\n\n" + TOOL_HELP}]
                 + self._memory()
                 + [{"role": "user", "content": user}])
        budget, reads = self._budget_chars(), 0
        # From: agents/features/feature_contract.py
        spec = FeatureSpec()
        seen_tool_observations = set()
        previous_state = None
        best_evidence = 0
        no_progress = 0
        analysis_round = 0
        emergency_turn_cap = 30  # loop-safety only; never a file-count ceiling

        while analysis_round < emergency_turn_cap:
            analysis_round += 1
            tool_progress = False
            while True:
                buf = []
                try:
                    self.arch._stream(convo, buf.append, temperature=0.22,
                                      model=self.model)
                except Exception as e:
                    self._log("WARN", f"   ⚠ {what} failed: {e}")
                    return spec
                reply = "".join(buf)
                convo.append({"role": "assistant", "content": reply})

                used_chars = sum(len(str(m.get("content", ""))) for m in convo)
                # From: agents/core/workspace/source_workspace.py
                observations, tool_count = WorkspaceTools(self.arch).serve(reply)
                if tool_count and used_chars < budget * 0.92:
                    sig = observations.strip()
                    if sig and sig in seen_tool_observations:
                        self._log("WARN", f"   ↔ {what}: repeated the same workspace read — deciding with current evidence")
                    else:
                        if sig:
                            seen_tool_observations.add(sig)
                        reads += tool_count
                        tool_progress = True
                        self._log("INFO", f"   🧰 {what}: inspected {tool_count} workspace tool(s) ({reads} total)")
                        convo.append({"role": "user", "content":
                                      "Tool observations:\n\n" + observations +
                                      "\n\nContinue the SAME analysis. Do not write code. Establish CURRENT, GAP, CAUSE and source EVIDENCE before naming the impact files."})
                        continue
                break

            # From: agents/features/feature_planner.py
            spec = self._parse(reply)
            issues = self._analysis_issues(spec, mode, required_evidence_paths)
            # From: agents/features/feature_contract.py
            if not spec.is_empty() and not issues:
                self._log("INFO", f"   🧠 root cause/gap — {str(spec.context.get('cause') or '')[:160]}")
                self._log("INFO", f"   🔎 evidence — {len(spec.context.get('evidence') or [])} source fact(s), confidence {spec.context.get('confidence')}")
                return spec

            # From: agents/features/feature_contract.py
            if allow_empty and spec.is_empty():
                ctx = spec.context or {}
                if (ctx.get("current") and ctx.get("gap") and ctx.get("cause") and
                        ctx.get("evidence") and ctx.get("verify") and
                        ctx.get("confidence") in ("high", "medium")):
                    self._log("INFO", f"   ✅ {what}: evidence points to no source change")
                    return spec

            ctx = spec.context or {}
            ev = {str(e.get("path") or "") for e in (ctx.get("evidence") or [])
                  if isinstance(e, dict) and e.get("path")}
            evidence_count = len(ev)
            state = (
                tuple(sorted(f.get("path", "") for f in spec.files)),
                tuple(sorted(ev)),
                tuple(issues),
                str(ctx.get("cause") or "")[:180],
            )
            progressed = tool_progress or evidence_count > best_evidence
            if progressed:
                best_evidence = max(best_evidence, evidence_count)
                no_progress = 0
            elif previous_state == state:
                no_progress += 1
            else:
                # A changed hypothesis is worth one chance.
                no_progress = max(0, no_progress - 1)
            previous_state = state

            used_chars = sum(len(str(m.get("content", ""))) for m in convo)
            if no_progress >= 2:
                self._log("WARN", f"   ↔ {what}: source analysis stopped making progress")
                break
            if used_chars >= budget * 0.92:
                self._log("WARN", f"   ⚠ {what}: context is full before the impact map was proven")
                break

            files = getattr(self.arch, "files", {}) or {}
            missing = [f.get("path") for f in spec.files
                       if f.get("action") == "edit" and f.get("path") in files
                       and f.get("path") not in ev]
            for rel in required_evidence_paths or []:
                if rel and rel in files and rel not in ev and rel not in missing:
                    missing.append(rel)

            protocol_gap = any(x.startswith("missing ") or
                               x == "no source EVIDENCE was cited"
                               for x in issues)
            if protocol_gap or not missing:
                for rel in investigation_paths or []:
                    rel = str(rel or "").replace("\\", "/")
                    if rel in files and rel not in missing:
                        missing.append(rel)
                for rel in sorted(ev):
                    if rel in files and rel not in missing:
                        missing.append(rel)

            bundle = self._evidence_bundle(missing)
            issue_text = "; ".join(issues[:5] or ["analysis protocol incomplete"])
            self._log("WARN", f"   🔎 analysis needs proof — {issue_text[:420]}")
            convo.append({"role": "user", "content":
                "The proposed impact map is still speculative:\n- " +
                "\n- ".join(issues or ["analysis protocol incomplete"]) +
                ("\n\nController-provided source/import evidence for the unresolved points:\n" + bundle if bundle else "") +
                "\n\nImportant: symptom/focus files are investigation anchors, not mandatory edit owners. "
                "Follow the dependency/data-flow evidence to the real owner. Every EXISTING file you plan to edit must have its own concrete EVIDENCE line. "
                "Re-evaluate the root cause/ownership and output the COMPLETE analysis protocol again: CURRENT, GAP, CAUSE, EVIDENCE lines, SUMMARY, FILE lines, VERIFY, CONFIDENCE, DONE. Do not write code."})

        # Do not silently turn an unproven guess into a rewrite.
        issues = self._analysis_issues(spec, mode, required_evidence_paths)
        self._log("WARN", f"   ⚠ {what} could not establish a source-backed impact map: " +
                  "; ".join(issues[:6] or ["analysis inconclusive"]))
        # From: agents/features/feature_contract.py
        return FeatureSpec(context=spec.context)

