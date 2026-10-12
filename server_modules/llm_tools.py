"""A minimal, genuinely read-only tool loop for `llm.py`'s focused calls."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import ollama

from ollama_terminal.tools import MAX_OUTPUT, TOOL_SCHEMAS, WorkspaceTools, describe_call, tools_unsupported

from . import bus

READ_ONLY_NAMES = ("list_files", "read_file", "search_text", "web_search", "web_fetch", "browser_inspect")
READ_ONLY_SCHEMAS = [schema for schema in TOOL_SCHEMAS
                     if schema["function"]["name"] in READ_ONLY_NAMES]
MAX_TOOL_ROUNDS = 6

_SENSITIVE_NAMES = {".env", ".env.local", ".env.production"}

# Models that rejected a tools= call this process, so later calls for the same model skip straight to the tools-less path instead of failing again first.
_UNSUPPORTED_MODELS: set[str] = set()


def _sensitive(relative: str) -> bool:
    name = Path(relative).name
    return name in _SENSITIVE_NAMES or name.endswith(".secret")


def tag_effort(tools: "ReadOnlyTools | None", think: bool, label: str) -> None:
    """Log this call's effort level — only possible when it was made with a."""
    if tools is None or not tools.project:
        return
    bus.log(tools.project, "INFO",
            f"[effort:{effort_level(think, tools.rounds)}] {label}", agent=tools.role)


def effort_level(think: bool, tool_rounds: int) -> str:
    """A rough, informational four-level read on one call's weight."""
    if think:
        return "ultra" if tool_rounds >= 2 else "high"
    return "medium" if tool_rounds >= 1 else "low"


class ReadOnlyTools:
    """Workspace-rooted, read-only dispatcher."""

    def __init__(self, workspace: Path, project: str = "", role: str = "", client: Any = None,
                 use_local_web: bool = True, web_host: str = "http://localhost:11434"):
        self._tools = WorkspaceTools(workspace, client, approve=lambda _question: False,
                                     web_host=web_host, use_local_web=use_local_web)
        self.project = project
        self.role = role or bus.DEVELOPER
        self.rounds = 0
        # Focused LLM calls use WorkspaceTools rather than StudioTools, so provide the same managed-preview lookup explicitly.
        self._tools.browser_url = self._browser_url

    def _browser_url(self) -> str:
        if not self.project:
            return ""
        from . import preview_runtime

        state = preview_runtime.status(self.project)
        return str(state.get("url") or "") if state.get("status") in {"starting", "running"} else ""

    def call(self, name: str, args: dict[str, Any]) -> str:
        if name not in READ_ONLY_NAMES:
            return f"Tool error: {name} is not offered to this call (read-only)."
        self.rounds += 1
        try:
            result = str(getattr(self._tools, f"tool_{name}")(**args))[:MAX_OUTPUT]
        except Exception as exc:  # noqa: BLE001 - mirrors WorkspaceTools.execute()'s own wrapping
            result = f"Tool error: {exc}"
        if self.project:
            self._announce(name, args, result)
        return result

    def _announce(self, name: str, args: dict[str, Any], result: str) -> None:
        if result.startswith("Tool error"):
            bus.log(self.project, "WARN", f"{describe_call(name, args)} — {result}", agent=self.role)
            return
        if name == "read_file":
            try:
                relative = self._tools._path(str(args.get("path") or "")).relative_to(self._tools.root).as_posix()
            except Exception:  # noqa: BLE001 - a bad path is reported by the result itself
                return
            if _sensitive(relative):
                bus.log(self.project, "INFO", f"Read {relative} (content hidden)", agent=self.role)
                return
            bus.file_read(self.project, relative, result, agent=self.role)
            bus.log(self.project, "INFO",
                    f"Read {relative} ({len(result.splitlines())} lines)", agent=self.role)
        elif name == "list_files":
            bus.log(self.project, "INFO", f"Listed {args.get('path') or '.'}", agent=self.role)
        elif name == "search_text":
            bus.log(self.project, "INFO",
                    f'Searched for "{args.get("query", "")}" in {args.get("path", ".")}', agent=self.role)
        elif name == "web_search":
            bus.log(self.project, "INFO", f'Searched the web for "{args.get("query", "")}"', agent=self.role)
        elif name == "web_fetch":
            bus.log(self.project, "INFO", f'Fetched {args.get("url", "")}', agent=self.role)
        elif name == "browser_inspect":
            bus.log(self.project, "INFO",
                    f'Inspected local browser page {args.get("url") or "managed preview"}', agent=self.role)


def _stream_chat(chat: Callable[..., Any], kwargs: dict[str, Any],
                 on_token: Callable[[str], None],
                 on_usage: Callable[[Any], None] | None = None) -> Any:
    """One `chat(**kwargs, stream=True)` call, forwarding each content delta."""
    content: list[str] = []
    thinking: list[str] = []
    calls: list[Any] = []
    final = None
    for chunk in chat(**{**kwargs, "stream": True}):
        final = chunk
        delta = chunk.message
        if delta.content:
            content.append(delta.content)
            on_token(delta.content)
        if delta.thinking:
            thinking.append(delta.thinking)
        if delta.tool_calls:
            calls.extend(delta.tool_calls)
    if final is not None and on_usage is not None:
        on_usage(final)
    return ollama.Message(role="assistant", content="".join(content),
                          thinking="".join(thinking) or None, tool_calls=calls or None)


def run_chat(chat: Callable[..., Any], kwargs: dict[str, Any],
             tools: "ReadOnlyTools | None", max_rounds: int = MAX_TOOL_ROUNDS,
             on_stream_start: Callable[[], None] | None = None,
             on_stream_token: Callable[[str], None] | None = None,
             on_usage: Callable[[Any], None] | None = None) -> Any:
    """Drive one `chat(**kwargs)` call through read-only tool round trips."""
    def once(round_kwargs: dict[str, Any]) -> Any:
        # Cloud's terminal stream is where it reliably provides token counts.
        if on_stream_token is None and not round_kwargs.get("stream"):
            response = chat(**round_kwargs)
            if on_usage is not None:
                on_usage(response)
            return response.message
        if on_stream_start is not None:
            on_stream_start()
        return _stream_chat(chat, round_kwargs, on_stream_token or (lambda _token: None), on_usage)

    def call(round_kwargs: dict[str, Any]) -> Any:
        """One round, asked for again whole when its reply is cut off part-way."""
        attempt = 0
        owner = getattr(chat, "__self__", None)
        while True:
            try:
                return once(round_kwargs)
            except Exception as exc:  # noqa: BLE001 - raised again unless it is a bad minute of the service
                again = getattr(owner, "_next_attempt", None)
                if not callable(again):
                    raise
                attempt = again(exc, attempt)         # raises when it is not worth asking again, or the attempts are gone

    model = kwargs.get("model")
    if tools is None or model in _UNSUPPORTED_MODELS:
        return call(kwargs)
    tool_kwargs = {**kwargs, "tools": READ_ONLY_SCHEMAS}
    messages = tool_kwargs["messages"]
    for _ in range(max(1, max_rounds)):
        try:
            message = call(tool_kwargs)
        except Exception as exc:  # noqa: BLE001 - re-raised unless it's the one case handled
            if not tools_unsupported(exc):
                raise
            _UNSUPPORTED_MODELS.add(model)
            if tools.project:
                bus.log(tools.project, "WARN",
                        f"{model} does not support tool calling; continuing without "
                        f"a read tool for this and later calls to it.", agent=tools.role)
            return call(kwargs)   # the original, tools-less kwargs
        calls = message.tool_calls or []
        messages.append(message.model_dump(exclude_none=True))
        if not calls:
            return message
        for call_ in calls:
            name, args = call_.function.name, (call_.function.arguments or {})
            messages.append({"role": "tool", "tool_name": name, "content": tools.call(name, args)})
    # Rounds exhausted: force a final answer, with no more reads offered.
    tool_kwargs.pop("tools", None)
    return call(tool_kwargs)
