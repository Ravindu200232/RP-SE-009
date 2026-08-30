"""Builder Setup for the application builder.

The methods in this file share one easy-to-find responsibility.
"""
from __future__ import annotations

# Source: builder_shared.py — shared builder constants and helper imports.
from agents.planner.builder.builder_shared import (
    CHARS_PER_TOKEN,
    CommandRunner,
    HISTORY_BUDGET,
    OllamaClient,
    PROMPTS,
    Path,
    docsindex,
    is_cloud_model,
    log,
    max_context,
    time,
)

class BuilderSetupMixin:
    """Keep builder setup behavior in one place."""

    # Prepares BuilderSetupMixin with the services and starting state it needs before it begins work.
    def __init__(self, client: OllamaClient, model: str, project_dir: Path,
                 callbacks: dict | None = None, stack: str = "next",
                 mongo_uri: str = "", db_name: str = "", dev_port: int = 5173,
                 think: bool | None = None):
        """Prepare this helper with the state it needs."""
        self.client, self.model = client, model
        # From: agents/planner/builder/builder_shared.py
        self.project_dir, self.cb = Path(project_dir), callbacks or {}
        self.stack = stack if stack in PROMPTS else "next"
        self.mongo_uri, self.db_name, self.dev_port = mongo_uri, db_name, dev_port
        self.files, self.plan, self.convo = {}, {}, []
        self.plan_md = self.architecture_md = self.design_md = ""
        self.tokens_in = self.tokens_out = self.write_seq = 0
        # From: agents/planner/builder/builder_shared.py
        self.num_ctx, self.is_cloud, self.think = max_context(model), is_cloud_model(model), think
        self._scaffolding, self._scaffold_baseline = False, {}
        self._workspace_tool_cache, self._e2e_privileged_paths = {}, set()
        # From: agents/planner/builder/builder_shared.py
        self.cmd = CommandRunner(
            self.project_dir, npm_bin=self.cb.get("npm_bin", "npm"),
            node_bin=self.cb.get("node_bin", "node"),
            on_log=lambda level, message: self._fire("on_log", level, message),
            on_event=lambda event: self._fire("on_command", event))

    # Sends one progress event to the UI callback when a callback exists.
    def _fire(self, name: str, *args) -> None:
        """Send one progress event to the UI callback when a callback exists."""
        callback = self.cb.get(name)
        if callable(callback):
            try:
                callback(*args)
            except Exception as exc:
                # From: agents/planner/builder/builder_shared.py
                log.warning("callback %s failed: %s", name, exc)

    # Writes one readable status message through the configured logger.
    def _log(self, level: str, message: str) -> None:
        """Write one readable status message through the configured logger."""
        if callable(self.cb.get("on_log")):
            self._fire("on_log", level, message)
        else:
            # From: agents/planner/builder/builder_shared.py
            log.info(message)

    # Returns the active planner and builder prompt set for the selected stack.
    @property
    def active_prompts(self) -> dict:
        """Return the active planner and builder prompt set for the selected stack."""
        return PROMPTS[self.stack]

    # Returns the system prompt used for application planning.
    def _planner_sys(self) -> str:
        """Return the system prompt used for application planning."""
        return self.active_prompts["planner"]

    # Returns the system prompt used for application code generation.
    def _builder_sys(self) -> str:
        """Return the system prompt used for application code generation."""
        prompt = self.active_prompts["builder"]
        try:
            learned = __import__("agents.core.learning.build_lessons", fromlist=["prompt_block"]).prompt_block()
            if learned:
                prompt += "\n\nPROJECT-GENERATION LESSONS\n" + learned
        except Exception as exc:
            # From: agents/planner/builder/builder_shared.py
            log.debug("builder lessons unavailable: %s", exc)
        # From: agents/planner/builder/builder_shared.py
        docs = docsindex.index_block(self.project_dir) if self.stack == "next" else ""
        return prompt + ("\n\nINSTALLED NEXT.JS DOCUMENT INDEX\n" + docs if docs else "")

    # Returns the folders that can contain generated application source code.
    @property
    def source_roots(self) -> tuple:
        """Return the folders that can contain generated application source code."""
        return self.active_prompts["roots"]

    # Checks whether this path is a generated application source file.
    def is_source(self, path: str) -> bool:
        """Return whether this path is a generated application source file."""
        return path.startswith(self.source_roots) and path.endswith((".js", ".jsx"))

    # Sends one request to the selected AI model and stream response chunks to the caller.
    def _stream(self, messages, on_delta, tools=None, temperature=0.5,
                model=None, timeout=None, think=None):
        """Send one request to the configured LLM and stream response chunks to the caller."""
        options = {"temperature": temperature, "top_p": 0.9, "num_ctx": self.num_ctx}
        selected_think = self.think if think is None else think
        # From: agents/planner/builder/builder_shared.py
        started, chars = time.time(), 0
        calls = []
        for chunk in self.client.chat_stream(
                model or self.model, messages, tools=tools, options=options,
                keep_alive="10m", think=selected_think, timeout=timeout or 900):
            message = chunk.get("message") or {}
            delta = message.get("content") or ""
            if delta:
                chars += len(delta)
                on_delta(delta)
            calls.extend(message.get("tool_calls") or [])
            if chunk.get("done"):
                self.tokens_in += chunk.get("prompt_eval_count", 0) or 0
                self.tokens_out += chunk.get("eval_count", 0) or 0
            if chars >= 250_000:
                self._log("WARN", f"   ✂ stopped an oversized model turn after {chars:,} characters")
                break
            # From: agents/planner/builder/builder_shared.py
            if time.time() - started > (timeout or 900):
                break
        return calls

    # Calculates a safe source-code context character budget for the current model.
    def _budget_chars(self) -> int:
        """Calculate a safe source-context character budget for the current model."""
        return int(self.num_ctx * HISTORY_BUDGET * CHARS_PER_TOKEN)

    # Trims older conversation turns so the model context stays inside its budget.
    def _trim_convo(self) -> None:
        """Trim older conversation turns so the model context stays inside its budget."""
        budget = self._budget_chars()
        while sum(len(str(item.get("content") or "")) for item in self.convo) > budget and len(self.convo) > 4:
            self.convo.pop(3)

    # Returns a small summary of the saved conversation context.
    def memory_stats(self) -> dict:
        """Return a small summary of the saved conversation context."""
        chars = sum(len(str(item.get("content") or "")) for item in self.convo)
        return {"turns": len(self.convo), "approx_tokens": int(chars / CHARS_PER_TOKEN),
                "num_ctx": self.num_ctx, "cloud": self.is_cloud}

    # Resolves a project path and reject paths that escape the project folder.
    def _safe_path(self, rel: str) -> Path:
        """Resolve a project path and reject paths that escape the project folder."""
        raw = str(rel or "").strip().replace("\\", "/").lstrip("/")
        parts = [part for part in raw.split("/") if part not in {"", ".", ".."}]
        if not parts:
            raise ValueError("empty project path")
        target = (self.project_dir / "/".join(parts)).resolve()
        root = self.project_dir.resolve()
        if target != root and root not in target.parents:
            raise ValueError("path leaves project")
        return target
