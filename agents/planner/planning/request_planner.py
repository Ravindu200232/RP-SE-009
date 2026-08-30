"""Request Planner.

One planning responsibility lives in this file so the flow is easy to follow.
"""
from __future__ import annotations

# Source: sitemap_maker.py — imported helper(s) come from this file.
from agents.planner.planning.sitemap_maker import render_sitemap_xml
# Source: image_plan.py — imported helper(s) come from this file.
from agents.planner.planning.image_plan import _design_archetype

# Source: planning_helpers.py — shared planning constants and small helper functions.
from agents.planner.planning.planning_helpers import (
    Callable,
    NEXT_STACK,
    OllamaClient,
    PROMPT_PATH,
    PlanBundle,
    _json_object,
    _plan_is_empty,
    log,
    max_context,
)

class RequestPlannerMixin:
    """Keep request planner behavior together."""

    # Prepares RequestPlannerMixin with the services and starting state it needs before it begins work.
    def __init__(self, client: OllamaClient, model: str, *, stack: str = "next",
                 callbacks: dict | None = None, think: bool | None = None,
                 stream: Callable | None = None):
        """Prepare this helper with the state it needs."""
        self.client = client
        self.model = model
        self.stack = "next"
        self.cb = callbacks or {}
        self.think = think
        self.stream = stream
        self.tokens_in = 0
        self.tokens_out = 0

    # Sends one progress event to the UI callback when a callback exists.
    def _fire(self, name: str, *args) -> None:
        """Send one progress event to the UI callback when a callback exists."""
        callback = self.cb.get(name)
        if callable(callback):
            try:
                callback(*args)
            except Exception as exc:  # A callback failure must not stop planning.
                # From: agents/planner/planning/planning_helpers.py
                log.warning("planner callback %s failed: %s", name, exc)

    # Writes one readable status message through the configured logger.
    def _log(self, level: str, message: str) -> None:
        """Write one readable status message through the configured logger."""
        callback = self.cb.get("on_log")
        if callable(callback):
            self._fire("on_log", level, message)
        else:
            # From: agents/planner/planning/planning_helpers.py
            log.info(message)

    # Returns the planner system prompt with the current runtime rules attached.
    def _system_prompt(self) -> str:
        """Return the planner system prompt with the current runtime rules attached."""
        # From: agents/planner/planning/planning_helpers.py
        return PROMPT_PATH.read_text(encoding="utf-8") + "\n\n" + NEXT_STACK

    # Sends one planning request to the LLM and return its text response.
    def _call(self, messages: list[dict], on_delta: Callable[[str], None]) -> None:
        """Send one planning request to the LLM and return its text response."""
        if self.stream:
            self.stream(messages, on_delta, temperature=0.25, timeout=900)
            return
        # From: agents/planner/planning/planning_helpers.py
        options = {"temperature": 0.25, "top_p": 0.9,
                   "num_ctx": max_context(self.model)}
        for chunk in self.client.chat_stream(
                self.model, messages, options=options, keep_alive="10m",
                think=self.think, timeout=900):
            message = chunk.get("message") or {}
            delta = message.get("content") or ""
            if delta:
                on_delta(delta)
            if chunk.get("done"):
                self.tokens_in += chunk.get("prompt_eval_count", 0) or 0
                self.tokens_out += chunk.get("eval_count", 0) or 0

    # Creates the first complete application plan from the user requirement, close planning gaps, and return the
    # plan/design/architecture bundle.
    def create(self, user_input: str, requirement_source: str = "") -> PlanBundle | None:
        """Create current step in the standard shape used by the rest of the pipeline."""
        requirements = str(requirement_source or user_input or "").strip()
        context = str(user_input or "").strip()
        if not requirements:
            self._log("ERROR", "   ❌ Planning needs non-empty user input")
            return None
        # From: agents/planner/planning/image_plan.py
        user = (
            "AUTHORITATIVE USER INPUT\n\n" + requirements +
            ("\n\nBUILD CONTEXT (implementation resources/constraints, not extra product requirements)\n\n"
             + context if context and context != requirements else "") +
            "\n\nSTARTING ART DIRECTION for this app: " +
            _design_archetype(requirements) +
            ". Interpret it for this domain and audience — derive the palette, "
            "type, spacing and composition from it. Do not fall back to a "
            "generic gold-and-serif luxury look, and do not reuse a direction "
            "from another product."
            "\n\nCreate the complete JSON plan now. Preserve every stated detail."
        )
        messages = [
            {"role": "system", "content": self._system_prompt()},
            {"role": "user", "content": user},
        ]
        chunks = []
        self._fire("on_file_start", "plan.md")

        # Accepts a streamed planner response and keep only complete usable JSON text.
        def receive(delta: str) -> None:
            """Accept a streamed planner response and keep only complete usable JSON text."""
            chunks.append(delta)
            self._fire("on_file_token", "plan.md", delta)

        try:
            self._call(messages, receive)
        except Exception as exc:
            self._log("ERROR", f"   ❌ Planner failed: {exc}")
            return None
        raw = "".join(chunks)
        # From: agents/planner/planning/planning_helpers.py
        parsed = _json_object(raw)
        if not parsed:
            self._log("ERROR", "   ❌ Planner returned no JSON object")
            return None
        # From: agents/planner/planning/gap_closer.py
        plan = self.normalize(parsed, requirements)
        # From: agents/planner/planning/gap_closer.py
        plan, raw = self._close_gaps(messages, plan, raw, requirements)
        # From: agents/planner/planning/planning_helpers.py
        if _plan_is_empty(plan):
            # Every later stage reads this plan. An empty one builds nothing,
            # leaves the scaffold placeholder serving, and still passes a
            # journey that only opens "/" — a green result for no product.
            self._log("ERROR", "   ❌ The planner produced no routes and no "
                               "files. Refusing to build from an empty plan — "
                               "the model's answer was probably truncated.")
            return None
        # From: agents/planner/planning/documents/plan_md_maker.py
        markdown = self.render_markdown(plan)
        # From: agents/planner/planning/documents/architecture_md_maker.py
        architecture = "# Architecture\n\n" + self.render_architecture(plan)
        # From: agents/planner/planning/documents/design_md_maker.py
        design = "# Product Design\n\n" + self.render_design(plan)
        self._fire("on_file_end", "plan.md", markdown)
        # From: agents/planner/planning/planning_helpers.py
        # From: agents/planner/planning/sitemap_maker.py
        return PlanBundle(plan, markdown, architecture, design, raw,
                          render_sitemap_xml(plan))
