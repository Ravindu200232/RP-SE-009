"""Build Validation for the application builder.

The methods in this file share one easy-to-find responsibility.
"""
from __future__ import annotations

# Source: builder_shared.py — shared builder constants and helper imports.
from agents.planner.builder.builder_shared import (
    CMD_RE,
    check_named_imports,
    group_messages,
    log,
    re,
)

class BuildValidationMixin:
    """Keep build validation behavior in one place."""

    # Runs the configured lint command against the generated application.
    def lint_generated(self) -> list[str]:
        """Run the configured lint command against the generated application."""
        errors = []
        better_auth = "betterAuth(" in self.files.get("lib/auth.js", "")
        for path, body in self.files.items():
            if not path.endswith((".js", ".jsx", ".mjs")):
                continue
            directive = self.STRAY_DIRECTIVE_RE.search(body)
            # From: agents/data/database_server.py
            if directive and body[:directive.start()].strip():
                errors.append(f"{path}: 'use client' is not the first statement")
            # From: agents/planner/builder/builder_shared.py
            if re.search(r"^\s*interface\s+\w+|:\s*(?:string|number|boolean|any)\s*[,)=;]", body, re.M):
                errors.append(f"{path}: contains TypeScript syntax")
            if self.stack == "next" and "react-router-dom" in body:
                errors.append(f"{path}: imports react-router-dom in a Next app")
            # From: agents/planner/builder/builder_shared.py
            if path.endswith("route.js") and re.search(r"export\s+default", body):
                errors.append(f"{path}: route handlers cannot default export")
            # From: agents/planner/builder/builder_shared.py
            if re.search(r"\b(?:const|let|var)\s+\w+\s*=\s*(?:getCollection|getSessionUser)\s*\(", body):
                errors.append(f"{path}: await async getCollection/getSessionUser before using its result")
            # From: agents/planner/builder/builder_shared.py
            if ("{ params }" in body
                    and re.search(r"\b(?:const|let|var)\s+\{[^}]+\}\s*=\s*params\s*;", body)):
                errors.append(f"{path}: await Next.js dynamic-route params before destructuring")
            # From: agents/planner/builder/builder_shared.py
            if (re.match(r"\s*[\"']use client[\"']", body)
                    and re.search(r"@/lib/(?:mongodb|auth|seed)(?:[\"'/]|$)|from\s+[\"']mongodb", body)):
                errors.append(f"{path}: client file imports server/database code")
            if better_auth and "seed" in path.lower():
                # From: agents/planner/builder/builder_shared.py
                if re.search(r"betterAuth\s*\(|from\s+['\"]better-auth|auth\.api\.signUpEmail", body):
                    errors.append(f"{path}: auth provider/signup logic belongs only in lib/auth; call ensureDemoAccounts()")
                # From: agents/planner/builder/builder_shared.py
                if re.search(r"\bpassword\s*:", body) and not re.search(r"\bensureDemoAccounts\s*\(", body):
                    errors.append(f"{path}: do not call auth.api.signUpEmail here; provision identities with ensureDemoAccounts() from lib/auth")
        try:
            # Source: syntax_checker.py — imported helper(s) come from this file.
            from agents.core.syntax.syntax_checker import check_syntax, syntax_messages
            # From: agents/core/syntax/syntax_checker.py
            broken, _ = check_syntax(self.project_dir, self.files)
            # From: agents/core/syntax/syntax_checker.py
            errors.extend(syntax_messages(broken))
        except Exception as exc:
            # From: agents/planner/builder/builder_shared.py
            log.debug("syntax scan unavailable: %s", exc)
        # From: agents/planner/builder/builder_shared.py
        errors.extend(group_messages(check_named_imports(self.files)))
        # From: agents/planner/builder/file_writer.py
        errors.extend(f"{path}: planned file was not implemented" for path in self.unfinished())
        return list(dict.fromkeys(errors))

    # Repairs lint.
    def repair_lint(self) -> int:
        """Repair lint safely without changing unrelated project behavior."""
        if "betterAuth(" in self.files.get("lib/auth.js", ""):
            for path, body in list(self.files.items()):
                if "seed" not in path.lower(): continue
                # From: agents/planner/builder/builder_shared.py
                fixed = re.sub(r"((?:getCollection|collection)\s*\(\s*['\"])users(['\"]\s*\))", r"\1user\2", body)
                if fixed != body:
                    # From: agents/planner/builder/project_memory.py
                    self._write_atomic(path, fixed); self.files[path] = fixed; self.write_seq += 1
                    self._log("INFO", f"   🔐 normalized Better Auth user collection in {path}")
        errors = self.lint_generated()
        if not errors:
            return 0
        self._log("WARN", f"🔍 Repairing {len(errors)} generated-code issue(s)")
        # From: agents/planner/builder/build_tasks.py
        return self._run_write_loop(
            "Fix these deterministic issues while preserving the approved plan. Rewrite complete affected files only.\n"
            + "\n".join("- " + item for item in errors[:30]))

    # Verifies output and return clear evidence to the next pipeline step.
    def _verify_output(self) -> bool:
        """Verify output and return clear evidence to the next pipeline step."""
        if not any(path in self.files for path in self.active_prompts["entry"]):
            self._log("ERROR", f"   ❌ Missing entry file {self.active_prompts['entry'][0]}")
            return False
        # From: agents/planner/builder/file_writer.py
        missing = self.unfinished()
        if missing:
            self._log("ERROR", "   ❌ Planned files remain: " + ", ".join(missing[:12]))
            return False
        errors = self.lint_generated()
        if errors:
            for error in errors[:10]:
                self._log("WARN", "   ⚠ " + error)
        return not errors

    # Runs the requested commands step and returns the result.
    def run_requested_commands(self, reply: str) -> list[str]:
        """Run the requested commands step and return its observable result."""
        results = []
        # From: agents/planner/builder/builder_shared.py
        for command in [item.strip() for item in CMD_RE.findall(reply or "") if item.strip()][:5]:
            results.append(self.cmd.run(command).as_feedback())
        return results
