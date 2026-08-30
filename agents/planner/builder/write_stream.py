"""Reads file blocks from a model response as it arrives."""
from __future__ import annotations

import re


FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9+#-]*\s*\n(.*?)\n?\s*```\s*$", re.S)
OPEN_RE = re.compile(r"<(write_file|file)\s+path\s*=\s*[\"']([^\"'>]+)[\"']\s*>", re.I)
PARTIAL_OPEN_RE = re.compile(r"<(write_file|file)\b", re.I)
CMD_RE = re.compile(r"<run_command>(.*?)</run_command>", re.I | re.S)


# Cleans fence in the format expected by the next pipeline steps.
def _strip_fence(text: str) -> str:
    """Clean fence in the standard shape used by the rest of the pipeline."""
    match = FENCE_RE.match(text or "")
    return match.group(1) if match else str(text or "")


# Finds the last complete streamed block that can be safely parsed now.
def _safe_flush_len(buffer: str, tag: str) -> int:
    """Find the last complete streamed block that can be safely parsed now."""
    for size in range(min(len(tag) - 1, len(buffer)), 0, -1):
        if buffer.endswith(tag[:size]):
            return len(buffer) - size
    return len(buffer)


class FileStreamParser:
    """Separate normal text from complete file blocks while streaming."""

    # Prepares FileStreamParser with the services and starting state it needs before it begins work.
    def __init__(self, on_text, on_file_start, on_file_token, on_file_end):
        """Prepare this helper with the state it needs."""
        self.on_text, self.on_file_start = on_text, on_file_start
        self.on_file_token, self.on_file_end = on_file_token, on_file_end
        self.buf, self.mode, self.tag, self.path, self.content = "", "text", None, None, ""

    # Accepts another streamed model chunk and emit any complete file blocks.
    def feed(self, chunk: str) -> None:
        """Accept another streamed model chunk and emit any complete file blocks."""
        self.buf += chunk
        self._drain()

    # Finishes parsing streamed model output and flush any final generated file that has not yet been emitted.
    def close(self) -> None:
        """Finish current step safely without changing unrelated project behavior."""
        if self.mode == "file":
            if self.buf:
                self.content += self.buf
                self.on_file_token(self.buf)
            self.on_file_end(self.path, _strip_fence(self.content))
        elif self.buf:
            self.on_text(self.buf)
        self.buf, self.mode, self.path, self.content = "", "text", None, ""

    # Parses complete streamed file or command blocks from the buffered model text.
    def _drain(self) -> None:
        """Parse complete streamed file or command blocks from the buffered model text."""
        while True:
            if self.mode == "text":
                match = OPEN_RE.search(self.buf)
                if match:
                    # From: agents/data/database_server.py
                    if match.start():
                        # From: agents/data/database_server.py
                        self.on_text(self.buf[:match.start()])
                    self.tag, self.path = match.group(1).lower(), match.group(2).strip()
                    self.buf = self.buf[match.end():]
                    if self.buf.startswith("\n"):
                        self.buf = self.buf[1:]
                    self.content, self.mode = "", "file"
                    self.on_file_start(self.path)
                    continue
                partial = PARTIAL_OPEN_RE.search(self.buf)
                if partial:
                    # From: agents/data/database_server.py
                    if partial.start():
                        # From: agents/data/database_server.py
                        self.on_text(self.buf[:partial.start()])
                        # From: agents/data/database_server.py
                        self.buf = self.buf[partial.start():]
                    return
                size = _safe_flush_len(self.buf, "<write_file")
                if size:
                    self.on_text(self.buf[:size])
                    self.buf = self.buf[size:]
                return
            close = f"</{self.tag}>"
            index = self.buf.find(close)
            if index >= 0:
                head, self.buf = self.buf[:index], self.buf[index + len(close):]
                if head:
                    self.content += head
                    self.on_file_token(head)
                self.on_file_end(self.path, _strip_fence(self.content))
                self.mode, self.path, self.content = "text", None, ""
                continue
            size = _safe_flush_len(self.buf, close)
            if size:
                part, self.buf = self.buf[:size], self.buf[size:]
                self.content += part
                self.on_file_token(part)
            return


__all__ = [
    "CMD_RE", "FENCE_RE", "OPEN_RE", "PARTIAL_OPEN_RE", "FileStreamParser",
    "_strip_fence",
]
