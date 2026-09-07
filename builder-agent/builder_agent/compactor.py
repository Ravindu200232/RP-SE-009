"""Making room without losing the task.

Compaction happens in escalating steps, cheapest and most exact first:

1. Evict observations a later one already replaced. Nothing is judged here,
   only replaced, so this is free of risk.
2. Strip file bodies out of write calls. The file is on disk; carrying its text
   in the transcript as well buys nothing a re-read would not buy.
3. Ask the model for a handoff summary and swap the unpinned history for it.
4. If even that summary is too large, archive it outside the window and pin a
   short pointer, so `recallCompactedContext` can still reach it by keyword.

Whatever happens, the system prompt, the task, the project layout and the
evidence ledger survive. Losing the task is the single worst failure mode an
agent loop has, and it is the one people describe as the agent going mad near
the end of a long run.
"""
from __future__ import annotations

from .errors import AbortError

HANDOFF_PROMPT = """Write a handoff for the next context window of this same task.

You are not finishing the task and not answering the user. Another window will
continue from your summary alone, so include, concisely and factually:

- The task and any constraint the user stated, in their terms.
- What has actually been done, with the files changed.
- What is verified, with the evidence, and what is still unproved.
- The current failure, if any: the exact error, the hypothesis, and what has
  already been ruled out.
- The immediate next action.

Do not speculate, do not claim success you have not seen, and do not repeat the
full contents of files. Under 700 words."""


class Compactor:
    def __init__(self, memory, budget, router, events) -> None:
        self.memory = memory
        self.budget = budget
        self.router = router
        self.events = events

    def compact(self, tools=None, force: bool = False) -> dict:
        """Free room. Returns what was done, so the loop can decide to continue."""
        freed = self.memory.evict_superseded() + self.memory.strip_written_bodies()
        measurement = self.budget.measure(self.memory.build(), tools)
        if freed and not measurement.should_compact and not force:
            self.events.emit("notice", level="info",
                             message=f"Reclaimed {freed} characters of superseded context.")
            return {"compacted": True, "method": "evict"}

        summary = self._handoff()
        if not summary:
            return {"compacted": False, "method": "none"}

        checkpoint = "\n\n".join(filter(None, [
            summary,
            self.memory.summarise(),
            self.memory.evidence.recovery_report(),
        ]))
        # An oversized handoff would reproduce the problem it exists to solve.
        # Keep it reachable instead of keeping it in the window.
        if len(checkpoint) > self.budget.limit * 2:
            self.memory.archive = checkpoint
            checkpoint = (summary[:4000] + "\n\n"
                          + self.memory.evidence.recovery_report()
                          + "\n\n[The full handoff was archived because it does not fit. Use "
                            "recallCompactedContext with a specific path, error or task keyword "
                            "before guessing at omitted history.]")

        self.memory.replace_history(checkpoint)
        self.budget.reset_history()
        self.events.emit("notice", level="info",
                         message=f"Context checkpoint {self.memory.compactions}: older history "
                                 "summarised; the task and evidence are unchanged.")
        return {"compacted": True, "method": "checkpoint"}

    def _handoff(self) -> str:
        messages = self.memory.build() + [{"role": "user", "content": HANDOFF_PROMPT}]
        try:
            reply = self.router.ask(messages, tools=None, stream=False)
        except AbortError:
            raise
        except Exception as error:  # noqa: BLE001 - a failed summary is recoverable
            self.events.emit("notice", level="warn",
                             message=f"Could not summarise context ({error}); "
                                     "continuing with an evicted transcript.")
            return ""
        return (reply.content or "").strip()
