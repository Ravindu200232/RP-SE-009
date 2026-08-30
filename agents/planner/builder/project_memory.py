"""Project Memory for the application builder.

The methods in this file share one easy-to-find responsibility.
"""
from __future__ import annotations

# Source: builder_shared.py — shared builder constants and helper imports.
from agents.planner.builder.builder_shared import (
    json,
    log,
    os,
)

class ProjectMemoryMixin:
    """Keep project memory behavior in one place."""

    PLAN_JSON = ".agentforge/plan.json"
    CONVO_JSON = ".agentforge/convo.json"

    # Captures the current source state so a later repair can compare or restore it.
    def _snapshot(self, max_files: int = 35, per_file: int = 12_000) -> str:
        """Capture the current source state so a later repair can compare or restore it."""
        rows = []
        for path in sorted(self.files):
            # From: agents/planner/builder/builder_setup.py
            if not self.is_source(path):
                continue
            body = self.files[path]
            rows.append(f"--- {path} ---\n" + (body if len(body) <= per_file else body[:per_file] + "\n// …truncated…"))
            if len(rows) >= max_files:
                break
        return "\n\n".join(rows)

    # Builds the short source snapshot passed into an update conversation.
    def _context_snapshot(self, max_files: int = 35, per_file: int = 12_000, wanted=None) -> str:
        """Build the compact source snapshot passed into an update conversation."""
        return self._snapshot(max_files=max_files, per_file=per_file)

    # Returns context-size limits used when building a source snapshot.
    def _snapshot_caps(self) -> dict:
        """Return context-size limits used when building a source snapshot."""
        return {"max_files": 40 if self._budget_chars() >= 150_000 else 24,
                "per_file": 18_000 if self._budget_chars() >= 150_000 else 6_000}

    # Applies a follow-up change request to the current generated application.
    def update(self, instruction: str) -> int:
        """Apply a follow-up change request to the current generated application."""
        if not self.convo:
            # From: agents/planner/builder/build_tasks.py
            self.start_conversation(self.plan.get("source_input_summary") or self.plan_md or "existing app")
        prompt = (
            "CURRENT SOURCE\n" + self._snapshot(**self._snapshot_caps()) +
            "\n\nREQUESTED CHANGE\n" + instruction +
            "\n\nPreserve the approved plan/design unless the request explicitly changes it. "
            "Rewrite only complete affected files using <write_file> blocks."
        )
        # From: agents/planner/builder/build_tasks.py
        count = self._run_write_loop(prompt)
        # From: agents/planner/builder/dependency_manager.py
        self.repair_missing_imports()
        # From: agents/planner/builder/dependency_manager.py
        self.sync_dependencies()
        return count

    # Continues an interrupted generation using the saved plan and conversation state.
    def resume(self, brief: str = "") -> bool:
        """Continue an interrupted generation using the saved plan and conversation state."""
        if not self.plan.get("file_plan"):
            self._log("ERROR", "   ❌ No saved plan to resume")
            return False
        if not self.convo:
            # From: agents/planner/builder/build_tasks.py
            self.start_conversation((self.plan.get("source_input_summary") or self.plan_md) + "\n" + brief)
        # From: agents/planner/builder/file_writer.py
        if self._outstanding():
            # From: agents/planner/builder/build_tasks.py
            self.build_app()
        # From: agents/planner/builder/dependency_manager.py
        self.repair_missing_imports()
        # From: agents/planner/builder/dependency_manager.py
        self.sync_dependencies()
        # From: agents/planner/builder/dependency_manager.py
        self.install_unresolved()
        # From: agents/planner/builder/build_validation.py
        self.repair_lint()
        # From: agents/planner/builder/build_validation.py
        return self._verify_output()

    # Loads an existing generated project into the builder source map.
    def load_existing(self) -> None:
        """Load an existing generated project into the builder source map."""
        if (self.project_dir / "next.config.mjs").exists() or (self.project_dir / "next.config.js").exists():
            self.stack = "next"
        skip = {"node_modules", ".git", ".next", "dist", "out", ".agentforge", "public", "tests"}
        for path in self.project_dir.rglob("*"):
            if not path.is_file() or any(part in skip for part in path.parts) or path.name.startswith(".env"):
                continue
            if path.suffix not in {".js", ".jsx", ".mjs", ".json", ".css", ".html", ".md"} or path.stat().st_size > 250_000:
                continue
            rel = path.relative_to(self.project_dir).as_posix()
            self.files[rel] = path.read_text(encoding="utf-8", errors="replace")
        self.plan_md = self.files.get("plan.md", "")
        self.architecture_md = self.files.get("architecture.md", "")
        self.design_md = self.files.get("design.md", "")
        self.plan = self._load_plan_json()
        self.load_convo()

    # Writes a small state file atomically so an interrupted write cannot corrupt it.
    def _write_atomic(self, rel: str, text: str) -> None:
        """Write a small state file atomically so an interrupted write cannot corrupt it."""
        path = self.project_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        # From: agents/planner/builder/builder_shared.py
        os.replace(temporary, path)

    # Saves the saved structured approved plan beside the generated project.
    def _save_plan_json(self) -> None:
        """Save the machine-readable approved plan beside the generated project."""
        if self.plan:
            # From: agents/planner/builder/builder_shared.py
            self._write_atomic(self.PLAN_JSON, json.dumps(self.plan, ensure_ascii=False, indent=2))

    # Loads the previously saved saved structured plan when a project is resumed.
    def _load_plan_json(self) -> dict:
        """Load the previously saved machine-readable plan when a project is resumed."""
        try:
            # From: agents/planner/builder/builder_shared.py
            return json.loads((self.project_dir / self.PLAN_JSON).read_text(encoding="utf-8"))
        except Exception:
            return {}

    # Saves the builder conversation so generation can resume later.
    def save_convo(self) -> bool:
        """Save the builder conversation so generation can resume later."""
        if len(self.convo) < 3:
            return False
        try:
            messages = self.convo[-16:]
            # From: agents/planner/builder/builder_shared.py
            self._write_atomic(self.CONVO_JSON, json.dumps(
                {"model": self.model, "stack": self.stack, "messages": messages},
                ensure_ascii=False, indent=1))
            return True
        except Exception as exc:
            # From: agents/planner/builder/builder_shared.py
            log.warning("could not save conversation: %s", exc)
            return False

    # Loads the saved builder conversation for a resumed project.
    def load_convo(self) -> bool:
        """Load the saved builder conversation for a resumed project."""
        try:
            # From: agents/planner/builder/builder_shared.py
            data = json.loads((self.project_dir / self.CONVO_JSON).read_text(encoding="utf-8"))
            messages = [item for item in data.get("messages") or [] if isinstance(item, dict)]
            if len(messages) >= 3:
                self.convo = messages
                return True
        except Exception:
            pass
        return False

    # Builds a short list of user-visible capabilities already implemented.
    def _capability_ledger(self, wanted=None) -> str:
        """Build a compact list of user-visible capabilities already implemented."""
        paths = {item if isinstance(item, str) else item.get("path") for item in (wanted or [])}
        rows = []
        for cap in self.plan.get("capabilities") or []:
            if paths and not paths.intersection(cap.get("files") or []):
                continue
            proof = cap.get("proof_points") or cap.get("proof") or []
            proof = "; ".join(proof) if isinstance(proof, list) else str(proof)
            rows.append(f"{cap.get('id')}: {cap.get('behavior')} — {proof}")
        return "\n".join(rows)

    # Builds a short list of route, API, auth, and business contracts already implemented.
    def _contract_ledger(self, wanted=None) -> str:
        """Build a compact list of route, API, auth, and business contracts already implemented."""
        paths = {item if isinstance(item, str) else item.get("path") for item in (wanted or [])}
        rows = []
        for api in self.plan.get("api_contracts") or []:
            touched = {api.get("handler_file"), *(api.get("called_from") or [])}
            if paths and not paths.intersection(touched):
                continue
            rows.append(f"{api.get('name')}: {api.get('method')} {api.get('path')} — {api.get('success_effect')}")
        return "\n".join(rows)

    # Builds a short list of database entities and relationships already implemented.
    def _data_ledger(self) -> str:
        """Build a compact list of database entities and relationships already implemented."""
        rows = []
        for model in self.plan.get("data_model") or []:
            fields = ", ".join(f"{field.get('name')}:{field.get('type')}" for field in model.get("fields") or [])
            rows.append(f"{model.get('collection')} — {fields}")
        return "\n".join(rows)
