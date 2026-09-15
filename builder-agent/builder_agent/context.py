"""Token budgeting for one request.

This measures the request about to be sent, not cumulative billed tokens: a
long run makes hundreds of requests and only ever has to fit the next one.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .llm import estimate_tokens

# One bounded native tool call, whole. Below this a cut-off answer is certain.
OUTPUT_FLOOR = 2048


def output_reserve(context_tokens: int, max_tokens: int) -> int:
    """How much of the window to hold back for the model's own answer.

    Two opposite failures bound this. Reserve too little and every substantial
    response - a whole component, a file write after a large page snapshot - is
    cut off mid-call: the turn is spent, no tool runs, nothing progresses.
    Reserve too much and a modest window can no longer hold the system prompt
    plus the native tool schemas, so the request fails before the model has
    even seen the task.

    A flat floor only ever guarded the second failure, so a 128K model wrote
    files through the same keyhole as an 8K one. Scaling with the window leaves
    small models exactly where they were and lets large ones answer in one
    piece. This is budget adaptation, not model-name special casing.
    """
    share = max(OUTPUT_FLOOR, context_tokens // 8)
    # A quarter of the window is the structural cap: under ~8K there is no room
    # for the floor, and what the prompt needs has to win.
    return min(max_tokens, context_tokens // 4, share)


@dataclass
class Measurement:
    estimate: int
    prompt_tokens: int
    limit: int
    input_limit: int
    reserve: int
    used_percent: int
    near_limit: bool
    should_compact: bool

    def as_event(self) -> dict:
        return {
            "tokens": self.prompt_tokens, "limit": self.limit,
            "input_limit": self.input_limit, "percent": self.used_percent,
        }


class ContextBudget:
    def __init__(self, context_tokens: int = 24_000, max_tokens: int = 4096) -> None:
        self.limit = max(4096, int(context_tokens))
        self.reserve = output_reserve(self.limit, max_tokens)
        self.safety = max(256, int(self.limit * 0.05))
        # Provider usage calibrates the character estimate for this model.
        self.calibration = 1.0
        self._last_actual = 0
        self._last_estimate = 0

    def measure(self, messages: list, tools: list | None = None,
                fresh: bool = False) -> Measurement:
        estimate = 3
        for message in messages:
            estimate += estimate_tokens(json.dumps(message, ensure_ascii=False, default=str)) + 4
        if tools:
            estimate += estimate_tokens(json.dumps(tools, ensure_ascii=False)) + 16

        # Never re-count every prior request: that would stop long runs early.
        additive = 0 if fresh else self._last_actual + estimate - self._last_estimate
        prompt_tokens = int(max(estimate * self.calibration, additive))
        input_limit = max(1, self.limit - self.reserve - self.safety)
        return Measurement(
            estimate=estimate,
            prompt_tokens=prompt_tokens,
            limit=self.limit,
            input_limit=input_limit,
            reserve=self.reserve,
            used_percent=min(100, round(prompt_tokens * 100 / input_limit)),
            near_limit=prompt_tokens >= input_limit,
            # Large model windows are capacity, not a reason to resend a
            # million-token transcript on every testing turn.
            should_compact=prompt_tokens >= min(input_limit, 64_000),
        )

    def observe(self, prompt_tokens: int, estimate: int) -> None:
        if not prompt_tokens or prompt_tokens <= 0:
            return
        self.calibration = max(self.calibration, prompt_tokens / max(1, estimate))
        self._last_actual = prompt_tokens
        self._last_estimate = estimate

    def reset_history(self) -> None:
        """A new checkpoint cannot be anchored to the old prompt's growth."""
        self._last_actual = 0
        self._last_estimate = 0


_CONTEXT_ERROR = re.compile(
    r"context[_ -]?(?:length[_ -]?exceeded|window|limit)"
    r"|maximum context length"
    r"|too many (?:input |prompt )?tokens"
    r"|(?:input|prompt).{0,40}(?:too long|exceeds|exceed)", re.I)


def is_context_error(error: BaseException | str) -> bool:
    return bool(_CONTEXT_ERROR.search(str(error)))
