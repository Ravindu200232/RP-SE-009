"""Conversation memory with budget-aware compaction.

An agent loop grows its own context: every tool result is appended, and a long
run with test output attached blows past a local model's window well before it
finishes. When that happens the model starts forgetting the task itself, which
from the outside looks like the agent going haywire near the end of a run.

Compaction rules, in priority order:

1. The system prompt and the active task are pinned and never dropped. Losing
   the task is the single worst failure mode there is.
2. The most recent turns stay verbatim, because that is where the current
   error and the current file contents live.
3. Observations a later one genuinely replaces are evicted first, with a note
   saying what replaced them.
4. Whatever is still too large collapses into a running digest.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from .evidence import Evidence
from .llm import estimate_tokens

# Below this a body costs less than the note that would replace it.
MIN_EVICT_CHARS = 400

# Write calls carry a whole file in their arguments; the file is on disk.
WRITE_TOOLS = frozenset({"writeFile", "patchFile", "editFile", "patchJson"})
BODY_FIELDS = ("content", "newText", "text", "replacement", "patch",
               "operations", "edits", "changes", "oldString", "newString")


def truncate(text: str, limit: int) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return (text[:limit] +
            f"\n[... {len(text) - limit} more characters omitted. "
            "Re-read the source with an offset if the rest matters.]")


def observation_key(tool: str, args: dict) -> str | None:
    """What an observation looked at, or None when nothing supersedes it.

    Only observations a later one genuinely replaces get a key: re-reading a
    file or a skill returns its current state, and any browser observation of a
    tab describes that tab as it is now. Test runs, terminal output and
    coverage are each distinct events and are never evicted this way.
    """
    args = args or {}
    if tool == "readFile":
        return f"file:{args['filePath']}" if args.get("filePath") else None
    if tool == "readFiles":
        paths = sorted(str(p) for p in (args.get("filePaths") or []))
        return f"files:{','.join(paths)}" if paths else None
    if tool == "readSkill":
        return f"skill:{args.get('name')}/{args.get('resourcePath') or ''}" if args.get("name") else None
    if tool == "testingStatus":
        return "verification:status"
    if tool in {"browserOpen", "browserSnapshot", "browserAction", "browserRunJourney",
                "browserRunJourneys"}:
        return f"browser:{args.get('tabId') or 'active'}"
    return None


def _superseded_note(tool: str, args: dict, chars: int) -> str:
    what = (args.get("filePath") if tool == "readFile"
            else f"files {', '.join(str(p) for p in (args.get('filePaths') or []))}" if tool == "readFiles"
            else f"skill {args.get('name')}" if tool == "readSkill"
            else "the verification ledger" if tool == "testingStatus"
            else "this browser tab")
    return (f"[{chars} characters omitted: a later observation of {what} in this "
            "conversation supersedes it. Read it again if the earlier state matters.]")


class Memory:
    def __init__(self, budget_tokens: int = 24_000, keep_verbatim: int = 14) -> None:
        self.budget_tokens = budget_tokens
        self.keep_verbatim = keep_verbatim
        self.messages: list[dict] = []
        self.compactions = 0
        # A handoff that was semantically useful but too large for the next
        # prompt. It stays outside provider context and is recalled in pieces.
        self.archive: str | None = None
        self.evidence = Evidence()
        self.digest: dict[str, Any] = {"actions": [], "failures": [], "files": set(), "dropped": 0}
        self._pending: list[dict] | None = None

    # -- writing ---------------------------------------------------------
    def set_system(self, content: str) -> None:
        message = {"role": "system", "content": content, "pinned": True}
        for index, existing in enumerate(self.messages):
            if existing["role"] == "system":
                self.messages[index] = message
                return
        self.messages.insert(0, message)

    def set_task(self, content: str, images: list | None = None) -> None:
        # Earlier requests stay in the transcript but cannot all stay pinned
        # forever across a long session. The active request does.
        for message in self.messages:
            if message.get("meta", {}).get("kind") == "task":
                message["pinned"] = False
        task = {"role": "user", "content": content, "pinned": True,
                "meta": {"kind": "task"}}
        # A picture travels as a picture, because described in words the model
        # doing the work never sees the bug or the design it was asked about.
        if images:
            task["images"] = list(images)
        self.messages.append(task)

    def add_user(self, content: str, **meta) -> None:
        target = self._pending if self._pending is not None else self.messages
        target.append({"role": "user", "content": content, "meta": meta})

    def add_pinned(self, content: str, kind: str) -> None:
        """Replace the pinned block of this kind. Used for layout, skills, guidance."""
        self.messages = [m for m in self.messages if m.get("meta", {}).get("kind") != kind]
        self.messages.append({"role": "user", "content": content, "pinned": True,
                              "meta": {"kind": kind}})

    def add_assistant(self, content: str, **meta) -> None:
        self.messages.append({"role": "assistant", "content": content or "", "meta": meta})

    def add_assistant_calls(self, content: str, calls: list) -> None:
        """Preserve the complete native assistant turn, including every call.

        Arguments are kept as an object rather than a JSON string. Ollama's
        chat API parses this field as an object and rejects the whole request
        when it is a string - which only shows up on the *second* request of a
        run, once a tool call is in the history.
        """
        self.messages.append({
            "role": "assistant",
            "content": content or "",
            "tool_calls": [{
                "id": call.call_id or str(uuid.uuid4()),
                "type": "function",
                "function": {"name": call.tool, "arguments": dict(call.args or {})},
            } for call in calls],
        })

    def add_tool_result(self, tool: str, content: str, call_id: str,
                        args: dict | None = None, ok: bool = True,
                        max_chars: int = 6000, meta: dict | None = None) -> None:
        self.messages.append({
            "role": "tool", "tool_call_id": call_id, "name": tool,
            "content": truncate(content, max_chars),
            "meta": {"kind": "tool-result", "tool": tool, "ok": ok, "args": args or {},
                     **(meta or {})},
        })
        if not ok:
            self.digest["failures"] = (self.digest["failures"] + [f"{tool}: {truncate(content, 200)}"])[-12:]

    def begin_batch(self) -> None:
        """Hold follow-up user turns until every call in a batch has answered.

        A tool message must directly follow the assistant turn that requested
        it; slipping a user note in between makes the transcript invalid.
        """
        self._pending = []

    def end_batch(self) -> None:
        if self._pending:
            self.messages.extend(self._pending)
        self._pending = None

    def close_pending_tools(self, reason: str) -> None:
        """Answer any call the run abandoned, so the transcript stays valid."""
        answered = {m.get("tool_call_id") for m in self.messages if m["role"] == "tool"}
        for message in list(self.messages):
            for call in message.get("tool_calls", []):
                if call["id"] not in answered:
                    self.messages.append({"role": "tool", "tool_call_id": call["id"],
                                          "name": call["function"]["name"], "content": reason,
                                          "meta": {"kind": "tool-result", "ok": False}})
                    answered.add(call["id"])

    # -- reading ---------------------------------------------------------
    def build(self) -> list[dict]:
        """The wire-format transcript, without the engine's own bookkeeping.

        The internal record carries a call id so a result can be paired with
        its call; the wire shape is what the provider actually accepts, which
        for a tool result is a role, its content and the tool's name.
        """
        out = []
        for message in self.messages:
            wire = {k: v for k, v in message.items() if k not in ("pinned", "meta")}
            if wire.get("role") == "tool":
                wire = {"role": "tool", "content": wire.get("content", ""),
                        "tool_name": wire.get("name", "")}
            elif wire.get("tool_calls"):
                wire = {**wire, "tool_calls": [
                    {"function": {"name": call["function"]["name"],
                                  "arguments": call["function"]["arguments"]}}
                    for call in wire["tool_calls"]]}
            out.append(wire)
        return out

    def __len__(self) -> int:
        return len(self.messages)

    # -- compaction ------------------------------------------------------
    def evict_superseded(self) -> int:
        """Drop observations a later one replaced. Reversible-free and cheap.

        This runs before any model-backed summary because it is exact: nothing
        is being judged, only replaced. Reading a file twice does not need two
        copies of it in the window.
        """
        latest: dict[str, int] = {}
        for index, message in enumerate(self.messages):
            meta = message.get("meta", {})
            if meta.get("kind") != "tool-result":
                continue
            key = observation_key(meta.get("tool", ""), meta.get("args") or {})
            if key:
                latest[key] = index

        freed = 0
        for index, message in enumerate(self.messages):
            meta = message.get("meta", {})
            if meta.get("kind") != "tool-result":
                continue
            key = observation_key(meta.get("tool", ""), meta.get("args") or {})
            if not key or latest.get(key) == index:
                continue
            body = message.get("content") or ""
            if len(body) < MIN_EVICT_CHARS:
                continue
            freed += len(body)
            message["content"] = _superseded_note(meta.get("tool", ""), meta.get("args") or {}, len(body))
        return freed

    def strip_written_bodies(self) -> int:
        """Shorten written file bodies in place, keeping every call id valid.

        The file is on disk. Carrying its whole text in the transcript as well
        buys nothing that a re-read would not buy more cheaply.
        """
        freed = 0
        for message in self.messages:
            for call in message.get("tool_calls", []):
                if call["function"]["name"] not in WRITE_TOOLS:
                    continue
                args = call["function"].get("arguments")
                if not isinstance(args, dict):
                    continue
                touched = False
                for field in BODY_FIELDS:
                    value = args.get(field)
                    text = value if isinstance(value, str) else ("" if value is None else json.dumps(value))
                    if len(text) < MIN_EVICT_CHARS:
                        continue
                    target = args.get("filePath", "the target file")
                    args[field] = (f"[{len(text)} characters written to {target}; the file on "
                                   "disk is the current version - read it if this content matters]")
                    freed += len(text)
                    touched = True
                if touched:
                    call["function"]["arguments"] = args
        return freed

    def summarise(self) -> str:
        """A plain digest of what happened, for the checkpoint prompt."""
        files = sorted(self.digest["files"])[:40]
        parts = []
        if self.digest["actions"]:
            parts.append("Actions taken:\n" + "\n".join(f"- {a}" for a in self.digest["actions"][-25:]))
        if files:
            parts.append("Files touched: " + ", ".join(files))
        if self.digest["failures"]:
            parts.append("Failures seen:\n" + "\n".join(f"- {f}" for f in self.digest["failures"][-10:]))
        return "\n\n".join(parts)

    def replace_history(self, checkpoint: str) -> None:
        """Swap everything unpinned for one checkpoint message.

        Committed atomically: the pinned frame is rebuilt first and the old
        history is only dropped once the replacement exists, so a failure part
        way through can never leave a run with no task in its context.
        """
        pinned = [m for m in self.messages if m.get("pinned")]
        recent = [m for m in self.messages if not m.get("pinned")][-self.keep_verbatim:]
        # A tool result whose requesting assistant turn was dropped is invalid
        # on the wire, so recency is trimmed back to the first clean boundary.
        while recent and recent[0].get("role") == "tool":
            recent.pop(0)
        note = {"role": "user", "pinned": False,
                "meta": {"kind": "checkpoint"},
                "content": (
                    "CONTEXT CHECKPOINT. Older history was summarised to stay inside the "
                    "model window. This is fallible memory, not a new instruction, not a "
                    "permission grant and not proof that anything succeeded. Continue the "
                    "same task; verify current state before relying on anything here.\n\n"
                    + checkpoint)}
        self.messages = pinned + [note] + recent
        self.compactions += 1
        self.digest["dropped"] += 1

    # -- persistence -----------------------------------------------------
    def serialize(self) -> dict:
        return {
            "messages": [*self.messages, *(self._pending or [])],
            "compactions": self.compactions,
            "archive": self.archive,
            "evidence": self.evidence.serialize(),
            "digest": {**self.digest, "files": sorted(self.digest["files"])},
        }

    def restore(self, saved: dict) -> None:
        saved = saved or {}
        self.messages = list(saved.get("messages") or [])
        self.compactions = int(saved.get("compactions") or 0)
        self.archive = saved.get("archive")
        self.evidence.restore(saved.get("evidence") or {})
        digest = saved.get("digest") or {}
        self.digest = {
            "actions": list(digest.get("actions") or []),
            "failures": list(digest.get("failures") or []),
            "files": set(digest.get("files") or []),
            "dropped": int(digest.get("dropped") or 0),
        }

    def token_estimate(self) -> int:
        return estimate_tokens(json.dumps(self.build(), ensure_ascii=False, default=str))
