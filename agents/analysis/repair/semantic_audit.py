"""Semantic Audit.

Every method here owns one closely related analyzer responsibility.
"""
from __future__ import annotations

# Source: analysis_shared.py — shared finding types, constants and helper imports.
from agents.analysis.analysis_shared import (
    Finding,
    PROMPT_FILE,
    SEMANTIC_LENSES,
    SEVERITIES,
    TOOL_HELP,
    WorkspaceTools,
    json,
    re,
)

class SemanticAuditMixin:
    """Keep semantic audit behavior together."""

    # Calculates a safe source-code context character budget for the current model.
    def _budget_chars(self):
        """Calculate a safe source-context character budget for the current model."""
        return int(getattr(self.arch, "num_ctx", getattr(self.arch, "context_tokens", 16384)) * 1.8)

    # Loads the Analyzer instruction contract used for semantic requirement checks.
    def _analysis_contract(self):
        """Prepare the analysis contract value or state used by this focused pipeline step."""
        # From: agents/analysis/analysis_shared.py
        try: return PROMPT_FILE.read_text("utf-8")
        except OSError: return "Audit accepted requirements only. Inspect source first. Emit strict JSON with exact evidence."

    # Turn analyzer findings into a short evidence list that can be given to the repair model.
    def _evidence_ledger(self, report=None):
        """Prepare the evidence ledger value or state used by this focused pipeline step."""
        plan = getattr(self.arch, "plan", None) or {}
        structured = {k: plan.get(k) or [] for k in ("source_requirements", "capabilities", "workflows", "contracts", "routes", "role_homes", "demo_accounts", "e2e")}
        # From: agents/analysis/checks/route_checks.py
        routes = report.routes if report else self.enumerate_routes()
        # From: agents/analysis/analysis_shared.py
        # From: agents/analysis/checks/scan_state.py
        return "## Structured plan\n" + json.dumps(structured, ensure_ascii=False, indent=2)[:18000] + "\n\n## Routes\n" + self.route_table(routes)[:8000] + "\n\n## Files\n" + self.inventory()[:8000] + "\n\n## Deterministic findings\n" + ((report.as_prompt_block() if report else "") or "(none)")

    # Extracts the first valid JSON object from a model response.
    @staticmethod
    def _json_object(text):
        """Prepare the json object value or state used by this focused pipeline step."""
        # From: agents/analysis/analysis_shared.py
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text or "").strip(), flags=re.I | re.S); decoder = json.JSONDecoder()
        # From: agents/analysis/analysis_shared.py
        for match in re.finditer(r"\{", clean):
            try:
                # From: agents/data/database_server.py
                obj, _ = decoder.raw_decode(clean[match.start():])
                if isinstance(obj, dict): return obj
            except ValueError: pass
        return {}

    # Builds the requirement-focused context used to judge whether generated behavior is still correct.
    def _semantic_lens(self, lens, report, max_turns=4, max_tools=10):
        """Prepare the semantic lens value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        ledger, plan, files = self._evidence_ledger(report), self.plan_text(), self.source_files()
        messages = [{"role": "system", "content": self._analysis_contract() + "\n\n" + TOOL_HELP}, {"role": "user", "content": f"MODE: SEMANTIC_AUDIT\nLENS: {lens}\n\n## Accepted prose plan\n{plan[:18000]}\n\n{ledger}\n\nInspect the owner and every required hop. Emit tools until proven, then strict JSON."}]
        # From: agents/analysis/analysis_shared.py
        self.arch._workspace_tool_cache = {}; tools, reply, used = WorkspaceTools(self.arch), "", 0
        for _ in range(max_turns):
            chunks = []
            try: self.arch._stream(messages, chunks.append, temperature=0.15)
            except Exception as exc: self._log("WARN", f"   ⚠ semantic {lens} audit failed: {exc}"); return []
            reply = "".join(chunks); messages.append({"role": "assistant", "content": reply})
            # From: agents/core/workspace/source_workspace.py
            observation, count = tools.serve(reply, max_calls=min(4, max(0, max_tools-used)))
            if count and used < max_tools:
                used += count; messages.append({"role": "user", "content": "Tool observations:\n\n" + observation + "\n\nContinue the same lens without repeating a request."}); continue
            break
        obj, evidence_space, out = self._json_object(reply), plan + "\n" + ledger, []
        for row in obj.get("findings") or []:
            if not isinstance(row, dict): continue
            severity, path = str(row.get("severity") or "major").lower(), str(row.get("path") or "").replace("\\", "/").lstrip("./")
            promise, evidence = str(row.get("plan_quote") or "").strip(), row.get("evidence") or []
            if severity not in SEVERITIES or path not in files or len(promise) < 12 or promise not in evidence_space or not evidence: continue
            related, valid = [], True
            for proof in evidence:
                if not isinstance(proof, dict): valid = False; break
                proof_path = str(proof.get("path") or "").replace("\\", "/").lstrip("./"); quote = str(proof.get("quote") or "")
                if proof_path not in files or len(quote.strip()) < 4 or quote not in files[proof_path]: valid = False; break
                related.append(proof_path)
            if not valid: continue
            related += [str(x).replace("\\", "/").lstrip("./") for x in row.get("related_paths") or [] if str(x).replace("\\", "/").lstrip("./") in files]
            # From: agents/analysis/analysis_shared.py
            out.append(Finding(severity, str(row.get("code") or "UNBUILT_PROMISE").upper(), str(row.get("message") or "planned behavior is disconnected")[:500], path, str(row.get("fix") or "implement the accepted behavior and rerun its proof")[:500], list(dict.fromkeys(related))))
            if len(out) >= 5: break
        return out

    # Compare promised requirements with the generated source and return promises that are still missing.
    def unbuilt_promises(self, max_reads=10):
        """Prepare the unbuilt promises value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        report, out = self.scan(), []
        for lens in SEMANTIC_LENSES:
            out += self._semantic_lens(lens, report, max_turns=4, max_tools=max(2, max_reads // len(SEMANTIC_LENSES)))
        unique, seen = [], set()
        for finding in out:
            key = (finding.code, finding.path, finding.message)
            if key not in seen: seen.add(key); unique.append(finding)
        return unique[:10]

    # Analyze the collected evidence and return a focused diagnosis for the next repair step.
    def diagnose(self, report, max_reads=12):
        """Prepare the diagnose value or state used by this focused pipeline step."""
        return self._semantic_lens("general implementation meaning and current findings", report, max_turns=4, max_tools=max_reads)
