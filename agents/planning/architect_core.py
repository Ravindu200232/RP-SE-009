"""
ArchitectAgent — fully LLM-driven, continuous full-app generation.

Unlike BuilderAgent (which stitches LLM output into a fixed Python-generated
skeleton), nothing here is templated: the raw user prompt goes straight to the
model, the model writes a big ``plan.md``, and then it generates every file
itself by calling a ``write_file`` tool.

Generation is one uninterrupted pass. The model is handed the whole file list
once and then simply told "Continue" every time it stops, until every planned
file is on disk — rather than being re-prompted phase by phase. The plan's
phases survive as *reporting* structure only: they still drive the UI timeline
and still trigger the QA agent's test authoring as their files land.

Tool protocol
-------------
Native Ollama tool calls are accepted when the model emits them, but the
primary channel is a streaming text protocol that works with *every* model
and streams token-by-token into the UI:

    <write_file path="app/components/Board.jsx">
    ...file content...
    </write_file>

Two output stacks
-----------------
New builds emit **Next.js 16 (App Router) + MongoDB**, JavaScript only, with
the database reached exclusively through a scaffolded ``lib/mongodb.js``.
The **Vite + React** stack is kept because projects generated before the
migration must stay editable; ``load_existing()`` infers which one a project
uses from its config files.

Config files are always Python-generated. The model only writes application
code, and a set of deterministic post-passes repairs the Next.js rules that
mid-size local models reliably get wrong (missing ``'use client'``, missing
``force-dynamic``, Pages-Router imports).
"""
import json
import logging
import os
import re
import secrets
import textwrap
import time
from pathlib import Path

from agents.core import docsindex
from agents.core.commands import CommandRunner
from agents.core.exports_checks import check_named_imports, group_messages
from agents.core.exports_common import strip_noncode
from agents.core.ollama_client import OllamaClient, is_cloud_model, max_context

log = logging.getLogger("architect")


CHARS_PER_TOKEN = 3.4


HISTORY_BUDGET = 0.62


SNAPSHOT_OPEN = ("## Current source on disk — this is the truth, ignore any "
                 "older copy of these files above")
SNAPSHOT_CLOSE = "## End of current source"
SNAPSHOT_RE = re.compile(
    re.escape(SNAPSHOT_OPEN) + r".*?" + re.escape(SNAPSHOT_CLOSE), re.S)

STUB_MARK = "[written earlier —"


OPEN_RE = re.compile(
    r"<(write_file|file)\s+path\s*=\s*[\"']([^\"'>]+)[\"']\s*>", re.I)
PARTIAL_OPEN_RE = re.compile(r"<(write_file|file)\b", re.I)


CMD_RE = re.compile(r"<run_command>(.*?)</run_command>", re.I | re.S)
FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9+#-]*\s*\n(.*?)\n?\s*```\s*$", re.S)


_DOUBLED_TAG_RE = re.compile(r"</\s*([A-Za-z][\w.]*)_\1\s*>")


def _fix_doubled_tags(text: str) -> str:
    """
    Repair `</div_div>` to `</div>`.

    Not a guard — it constrains nothing about what the app may be. It corrects
    a malformed token on the way to disk, in the same breath as the code fence.

    Worth doing in Python rather than leaving to the model because the model is
    the one making the mistake, and asking it to fix its own tic by rewriting
    the file gives it another chance to make it. Measured: one build wrote
    `</div_div>` 38 times across seven files, `npm run build` named the file,
    the line and the token with a caret under it, and two repair rounds handed
    that error back and got the same tic returned both times. The build never
    went green, so the unit stage never ran at all. Every other project on disk
    has zero occurrences — this is a slip, not a habit, and a slip is exactly
    what a deterministic repair is for.

    Only `X_X` is touched. A real component called `Foo_Bar` is left alone,
    because its halves differ.
    """
    return _DOUBLED_TAG_RE.sub(r"</\1>", text or "")


def _strip_fence(text: str) -> str:
    """Models love wrapping file bodies in markdown fences. Remove them."""
    m = FENCE_RE.match(text)
    return m.group(1) if m else text


def _strip_accidental_path_close(text: str, path: str | None) -> str:
    """
    Remove a leaked file-protocol/path closing tag from the end of a file body.

    Some models occasionally terminate an unterminated ``<write_file>`` block
    with the source path itself, for example ``</components/Card.jsx>``.  That
    token is protocol noise, not valid JSX, and persisting it guarantees a
    compile error.  Only an exact trailer matching the current file path is
    removed; ordinary JSX/HTML closing tags are untouched.
    """
    body = text or ""
    rel = (path or "").strip().replace("\\", "/").lstrip("./")
    if not rel:
        return body
    trimmed = body.rstrip()
    suffix_ws = body[len(trimmed):]
    candidates = (f"</{rel}>", f"</./{rel}>")
    for marker in candidates:
        if trimmed.endswith(marker):
            return trimmed[:-len(marker)].rstrip() + suffix_ws
    return body


def _clean_streamed_file_body(text: str, path: str | None) -> str:
    return _fix_doubled_tags(_strip_accidental_path_close(_strip_fence(text), path))


def _safe_flush_len(buf: str, tag: str) -> int:
    """
    How much of `buf` can be emitted without risking a tag split across
    chunk boundaries: everything except the longest suffix that is also a
    prefix of `tag`.
    """
    for k in range(min(len(tag) - 1, len(buf)), 0, -1):
        if buf.endswith(tag[:k]):
            return len(buf) - k
    return len(buf)


class _RefusalLoop(Exception):
    """
    Raised to end a turn that has stopped making progress.

    Not an error: the turn's work up to this point is on disk. It exists so a
    refusal deep inside the streaming parser can unwind the stream, which is
    the only way to stop a model that is re-emitting files it has already been
    told it may not write.
    """


class FileStreamParser:
    """Incremental parser splitting a token stream into prose and file bodies."""

    def __init__(self, on_text, on_file_start, on_file_token, on_file_end):
        self.on_text = on_text
        self.on_file_start = on_file_start
        self.on_file_token = on_file_token
        self.on_file_end = on_file_end
        self.buf = ""
        self.mode = "text"
        self.tag = None
        self.path = None
        self.content = ""

    def feed(self, chunk: str):
        self.buf += chunk
        self._drain()

    def close(self):
        """Flush leftovers — a file left unterminated is still salvaged."""
        if self.mode == "file":
            if self.buf:
                self.content += self.buf
                self.on_file_token(self.buf)
            self.buf = ""
            self.on_file_end(self.path, _clean_streamed_file_body(self.content, self.path))
            self.mode, self.path, self.content = "text", None, ""
        elif self.buf:
            self.on_text(self.buf)
            self.buf = ""

    def _drain(self):
        while True:
            if self.mode == "text":
                m = OPEN_RE.search(self.buf)
                if m:
                    if m.start():
                        self.on_text(self.buf[:m.start()])
                    self.tag = m.group(1).lower()
                    self.path = m.group(2).strip()
                    self.buf = self.buf[m.end():]

                    if self.buf.startswith("\n"):
                        self.buf = self.buf[1:]
                    self.content = ""
                    self.mode = "file"
                    self.on_file_start(self.path)
                    continue

                p = PARTIAL_OPEN_RE.search(self.buf)
                if p:
                    if p.start():
                        self.on_text(self.buf[:p.start()])
                        self.buf = self.buf[p.start():]
                    return

                keep = _safe_flush_len(self.buf, "<write_file")
                if keep:
                    self.on_text(self.buf[:keep])
                    self.buf = self.buf[keep:]
                return

            close_tag = f"</{self.tag}>"
            idx = self.buf.find(close_tag)
            if idx >= 0:
                head = self.buf[:idx]
                if head:
                    self.content += head
                    self.on_file_token(head)
                self.buf = self.buf[idx + len(close_tag):]

                self.on_file_end(self.path, _clean_streamed_file_body(self.content, self.path))
                self.mode, self.path, self.content = "text", None, ""
                continue

            keep = _safe_flush_len(self.buf, close_tag)
            if keep:
                part = self.buf[:keep]
                self.content += part
                self.on_file_token(part)
                self.buf = self.buf[keep:]
            return
