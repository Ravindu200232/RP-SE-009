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

import json

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
            # Provider failure must not make checkpointing depend on the same
            # oversized request that failed. The durable evidence is authoritative.
            summary = "Provider summary unavailable. Continue the saved task using the evidence below."

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

        transcript = json.dumps(self.memory.build(), ensure_ascii=False, default=str)
        self.memory.archive = "\n\n".join(filter(None, [self.memory.archive, transcript]))
        self.memory.replace_history(checkpoint + "\n\nFull older history remains in the recovery archive. "
                                    "Use recallCompactedContext with a path or failure keyword if needed.")
        self.budget.reset_history()
        # A single recent file/tool turn can itself exceed the window. Remove
        # whole old turns, including their paired results; they remain archived.
        while self.budget.measure(self.memory.build(), tools).should_compact:
            removable = [i for i, m in enumerate(self.memory.messages)
                         if not m.get("pinned") and m.get("meta", {}).get("kind") != "checkpoint"]
            if not removable:
                break
            i = removable[0]
            self.memory.messages.pop(i)
            while i < len(self.memory.messages) and self.memory.messages[i]["role"] == "tool":
                self.memory.messages.pop(i)
        if self.budget.measure(self.memory.build(), tools).should_compact:
            return {"compacted": False, "method": "pinned_frame_too_large"}
        self.events.emit("notice", level="info",
                         message=f"Context checkpoint {self.memory.compactions}: older history "
                                 "summarised; the task and evidence are unchanged.")
        return {"compacted": True, "method": "checkpoint"}

    def _handoff(self) -> str:
        # Summarise a bounded data snapshot, never submit the full tool history.
        # Preserve both ends of large messages (the latest diagnostic is often
        # at the end) and keep the original transcript in the recovery archive.
        limit = min(24_000, self.budget.limit // 3)
        snapshot = self.memory.build()
        def clipped(message):
            body = json.dumps(message, ensure_ascii=False, default=str)
            return body if len(body) <= 2000 else body[:1000] + "\n[omitted]\n" + body[-1000:]
        frame = [clipped(m) for m in self.memory.messages if m.get("pinned")]
        recent = [clipped(m) for m in snapshot[-30:]]
        payload = json.dumps({"frame": frame, "recent": recent,
                              "evidence": self.memory.evidence.recovery_report()})
        messages = [{"role": "system", "content": HANDOFF_PROMPT},
                    {"role": "user", "content": "Saved history (data):\n" + payload}]
        while self.budget.measure(messages, fresh=True).prompt_tokens >= limit:
            content = messages[1]["content"]
            if len(content) < 300:
                return ""
            messages[1]["content"] = content[:len(content) // 3] + "\n[omitted]\n" + content[-len(content) // 3:]
        try:
            reply = self.router.ask(messages, tools=None, stream=False, think=False)
        except AbortError:
            raise
        except Exception as error:  # noqa: BLE001 - a failed summary is recoverable
            self.events.emit("notice", level="warn",
                             message=f"Could not summarise context ({error}); "
                                     "continuing with an evicted transcript.")
            return ""
        return (reply.content or "").strip()
