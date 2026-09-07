"""Reading and changing files.

Four write tools instead of one, because "replace this whole file" is the most
expensive and most destructive way to change three lines, and a model handed
only that tool will use it for everything:

* `patchFile` replaces line ranges and carries a revision, so a stale edit is
  refused instead of silently clobbering a change made since the read.
* `patchJson` edits a manifest by path, so a comma or a brace can never be lost.
* `editFile` replaces one exact string, for a rename or a constant.
* `writeFile` creates a file, and is the only one that may send a whole body.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..errors import ToolError
from ..policy import DANGEROUS, MODERATE, SAFE
from ..sandbox import looks_binary
from .base import Tool

MAX_READ_CHARS = 60_000
MAX_WRITE_BYTES = 2 * 1024 * 1024


def revision_of(text: str) -> str:
    """A short content hash. Enough to catch a stale edit, cheap to carry."""
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:12]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write(ctx, path: Path, text: str, note: str) -> None:
    if len(text.encode("utf-8", "replace")) > MAX_WRITE_BYTES:
        raise ToolError(f"Refusing to write more than {MAX_WRITE_BYTES // 1024} KiB in one call.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    relative = ctx.sandbox.relative(path)
    ctx.memory.digest["files"].add(relative)
    ctx.events.emit("file", name=relative, size=len(text), content=text, note=note)


# ---------------------------------------------------------------------------
def read_file(args, ctx):
    path = ctx.sandbox.resolve(args["filePath"], must_exist=True)
    if path.is_dir():
        raise ToolError(f"{ctx.sandbox.relative(path)} is a directory. Use listDir.")
    if looks_binary(path):
        return {"ok": False, "content": f"{ctx.sandbox.relative(path)} is a binary file."}
    text = _read(path)
    lines = text.splitlines()
    offset = max(0, int(args.get("offset") or 0))
    limit = int(args.get("limit") or 0) or len(lines)
    window = lines[offset:offset + limit]
    body = "\n".join(f"{offset + i + 1:>5} | {line}" for i, line in enumerate(window))
    truncated = len(body) > MAX_READ_CHARS
    if truncated:
        body = body[:MAX_READ_CHARS]
    tail = ""
    if offset + len(window) < len(lines) or truncated:
        tail = (f"\n[showing lines {offset + 1}-{offset + len(window)} of {len(lines)}. "
                "Call readFile again with a larger offset for the rest.]")
    return {"ok": True,
            "content": (f"{ctx.sandbox.relative(path)} (revision {revision_of(text)}, "
                        f"{len(lines)} lines)\n{body}{tail}")}


def write_file(args, ctx):
    path = ctx.sandbox.resolve(args["filePath"])
    existed = path.exists()
    if existed and not args.get("overwrite", False):
        return {"ok": False,
                "content": (f"{ctx.sandbox.relative(path)} already exists. Use patchFile to change "
                            "part of it, or pass overwrite:true to replace it entirely.")}
    content = args.get("content") or ""
    _write(ctx, path, content, "written")
    return {"ok": True, "mutated": True,
            "content": (f"{'Replaced' if existed else 'Created'} {ctx.sandbox.relative(path)} "
                        f"({len(content.splitlines())} lines, revision {revision_of(content)}).")}


def patch_file(args, ctx):
    path = ctx.sandbox.resolve(args["filePath"], must_exist=True)
    text = _read(path)
    current = revision_of(text)
    expected = str(args.get("revision") or "").strip()
    if expected and expected != current:
        return {"ok": False,
                "content": (f"{ctx.sandbox.relative(path)} changed since you read it "
                            f"(revision {current}, you sent {expected}). Read it again and "
                            "re-derive the patch against the current text.")}
    lines = text.split("\n")
    edits = args.get("edits") or []
    if not isinstance(edits, list) or not edits:
        raise ToolError("edits must be a non-empty array of {startLine, endLine, newText}.")

    # Apply from the bottom up so earlier ranges keep their original numbers.
    applied = []
    for edit in sorted(edits, key=lambda e: int(e.get("startLine", 0)), reverse=True):
        start = int(edit.get("startLine", 0))
        end = int(edit.get("endLine", start))
        if start < 1 or end < start or start > len(lines) + 1:
            raise ToolError(f"Edit range {start}-{end} is outside {ctx.sandbox.relative(path)} "
                            f"({len(lines)} lines).")
        replacement = str(edit.get("newText", ""))
        lines[start - 1:end] = replacement.split("\n") if replacement else []
        applied.append(f"{start}-{end}")

    updated = "\n".join(lines)
    _write(ctx, path, updated, "patched")
    return {"ok": True, "mutated": True,
            "content": (f"Patched {ctx.sandbox.relative(path)} at line(s) "
                        f"{', '.join(reversed(applied))}. New revision {revision_of(updated)}, "
                        f"{len(lines)} lines.")}


def edit_file(args, ctx):
    path = ctx.sandbox.resolve(args["filePath"], must_exist=True)
    text = _read(path)
    old, new = str(args["oldString"]), str(args.get("newString") or "")
    count = text.count(old)
    if count == 0:
        return {"ok": False,
                "content": (f"That exact string is not in {ctx.sandbox.relative(path)}. "
                            "Read the file and copy the text you want to replace verbatim, "
                            "including its indentation.")}
    if count > 1 and not args.get("replaceAll"):
        return {"ok": False,
                "content": (f"That string appears {count} times in {ctx.sandbox.relative(path)}. "
                            "Include more surrounding context to make it unique, or pass "
                            "replaceAll:true.")}
    updated = text.replace(old, new) if args.get("replaceAll") else text.replace(old, new, 1)
    _write(ctx, path, updated, "edited")
    return {"ok": True, "mutated": True,
            "content": f"Replaced {count if args.get('replaceAll') else 1} occurrence(s) in "
                       f"{ctx.sandbox.relative(path)}. New revision {revision_of(updated)}."}


_JSON_SEGMENT = re.compile(r"[^.\[\]]+|\[\d+\]")


def _json_path(path: str) -> list:
    out = []
    for part in _JSON_SEGMENT.findall(str(path or "")):
        out.append(int(part[1:-1]) if part.startswith("[") else part)
    return out


def patch_json(args, ctx):
    path = ctx.sandbox.resolve(args["filePath"], must_exist=True)
    text = _read(path)
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        return {"ok": False, "content": f"{ctx.sandbox.relative(path)} is not valid JSON: {error}. "
                                        "Repair it with patchFile first."}
    operations = args.get("operations") or []
    if not isinstance(operations, list) or not operations:
        raise ToolError("operations must be a non-empty array of {op, path, value}.")

    for operation in operations:
        op = str(operation.get("op", "set")).lower()
        segments = _json_path(operation.get("path", ""))
        if not segments:
            raise ToolError("Each operation needs a dotted path, e.g. scripts.test")
        node = document
        for segment in segments[:-1]:
            if isinstance(segment, int):
                node = node[segment]
            else:
                node = node.setdefault(segment, {})
        leaf = segments[-1]
        if op in ("set", "add", "replace"):
            if isinstance(leaf, int):
                node[leaf] = operation.get("value")
            else:
                node[leaf] = operation.get("value")
        elif op == "remove":
            if isinstance(node, dict):
                node.pop(leaf, None)
            elif isinstance(leaf, int) and 0 <= leaf < len(node):
                node.pop(leaf)
        else:
            raise ToolError(f'Unknown JSON operation "{op}". Use set or remove.')

    indent = 2
    updated = json.dumps(document, indent=indent, ensure_ascii=False) + "\n"
    _write(ctx, path, updated, "patched")
    return {"ok": True, "mutated": True,
            "content": f"Applied {len(operations)} JSON operation(s) to "
                       f"{ctx.sandbox.relative(path)}; the file is still valid JSON."}


def delete_file(args, ctx):
    path = ctx.sandbox.resolve(args["filePath"], must_exist=True)
    if path.is_dir():
        raise ToolError("deleteFile removes one file. Remove a directory with an approved command.")
    relative = ctx.sandbox.relative(path)
    path.unlink()
    ctx.events.emit("file", name=relative, size=0, content="", note="deleted")
    return {"ok": True, "mutated": True, "content": f"Deleted {relative}."}


def list_dir(args, ctx):
    from ..sandbox import IGNORED_DIRS
    path = ctx.sandbox.resolve(args.get("dirPath") or ".", must_exist=True)
    if not path.is_dir():
        raise ToolError(f"{ctx.sandbox.relative(path)} is not a directory.")
    rows = []
    for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name in IGNORED_DIRS:
            rows.append(f"  {entry.name}/  (skipped)")
            continue
        if entry.is_dir():
            rows.append(f"  {entry.name}/")
        else:
            try:
                rows.append(f"  {entry.name}  ({entry.stat().st_size} bytes)")
            except OSError:
                rows.append(f"  {entry.name}")
        if len(rows) >= 400:
            rows.append("  … (listing truncated at 400 entries)")
            break
    return {"ok": True, "content": f"{ctx.sandbox.relative(path)}/\n" + "\n".join(rows or ["  (empty)"])}


def register(registry):
    registry.add(Tool(
        name="readFile", risk=SAFE, review_safe=True, handler=read_file,
        description="Read a file from the workspace with line numbers and a revision hash. "
                    "Use offset/limit to page through a large file.",
        parameters={"type": "object", "required": ["filePath"], "properties": {
            "filePath": {"type": "string", "description": "Workspace-relative path."},
            "offset": {"type": "integer", "description": "First line to show (0-based)."},
            "limit": {"type": "integer", "description": "How many lines to show."},
        }},
        summarize=lambda a: a.get("filePath", "")))

    registry.add(Tool(
        name="writeFile", risk=MODERATE, mutates=True, handler=write_file,
        description="Create a new file. To change part of an existing file use patchFile - "
                    "never resend an unchanged file to alter a few lines.",
        parameters={"type": "object", "required": ["filePath", "content"], "properties": {
            "filePath": {"type": "string"},
            "content": {"type": "string"},
            "overwrite": {"type": "boolean", "description": "Replace the file if it exists."},
        }},
        summarize=lambda a: a.get("filePath", "")))

    registry.add(Tool(
        name="patchFile", risk=MODERATE, mutates=True, handler=patch_file,
        description="Replace line ranges in an existing file. Pass the revision from readFile so a "
                    "stale patch is refused rather than clobbering someone else's change.",
        parameters={"type": "object", "required": ["filePath", "edits"], "properties": {
            "filePath": {"type": "string"},
            "revision": {"type": "string", "description": "Revision hash from readFile."},
            "edits": {"type": "array", "description":
                      "[{startLine, endLine, newText}] - 1-based inclusive line ranges."},
        }},
        summarize=lambda a: a.get("filePath", "")))

    registry.add(Tool(
        name="editFile", risk=MODERATE, mutates=True, handler=edit_file,
        description="Replace one exact string in a file. For a rename or a constant; "
                    "use patchFile for anything larger.",
        parameters={"type": "object", "required": ["filePath", "oldString", "newString"],
                    "properties": {
                        "filePath": {"type": "string"},
                        "oldString": {"type": "string"},
                        "newString": {"type": "string"},
                        "replaceAll": {"type": "boolean"},
                    }},
        summarize=lambda a: a.get("filePath", "")))

    registry.add(Tool(
        name="patchJson", risk=MODERATE, mutates=True, handler=patch_json,
        description="Edit a JSON file by path (e.g. scripts.test) so it stays valid JSON. "
                    "Preferred for package.json and config manifests.",
        parameters={"type": "object", "required": ["filePath", "operations"], "properties": {
            "filePath": {"type": "string"},
            "operations": {"type": "array", "description":
                           '[{op:"set"|"remove", path:"scripts.test", value:...}]'},
        }},
        summarize=lambda a: a.get("filePath", "")))

    registry.add(Tool(
        name="deleteFile", risk=DANGEROUS, mutates=True, handler=delete_file,
        description="Delete one file from the workspace.",
        parameters={"type": "object", "required": ["filePath"],
                    "properties": {"filePath": {"type": "string"}}},
        summarize=lambda a: a.get("filePath", "")))

    registry.add(Tool(
        name="listDir", risk=SAFE, review_safe=True, handler=list_dir,
        description="List one directory. Noise directories such as node_modules are skipped.",
        parameters={"type": "object", "properties": {
            "dirPath": {"type": "string", "description": "Defaults to the workspace root."}}},
        summarize=lambda a: a.get("dirPath", ".")))
