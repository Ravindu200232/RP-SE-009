"""Finding code without guessing at paths.

The single most common way a model breaks a build is inventing a file that
does not exist and then editing around the error it gets back. One search is
cheaper than three failed reads, so these are cheap, bounded and always
available.
"""
from __future__ import annotations

import fnmatch
import re

from ..errors import ToolError
from ..policy import SAFE
from ..sandbox import IGNORED_DIRS
from .base import Tool

MAX_HITS = 120
MAX_LINE = 240


def _iter_files(ctx, root, globs):
    patterns = [g for g in (globs or []) if g]
    for path in ctx.sandbox.walk(root):
        if patterns:
            relative = ctx.sandbox.relative(path)
            if not any(fnmatch.fnmatch(relative, p) or fnmatch.fnmatch(path.name, p)
                       for p in patterns):
                continue
        yield path


def _scan(ctx, pattern, args, regex: bool):
    root = ctx.sandbox.resolve(args.get("path") or ".", must_exist=True)
    flags = 0 if args.get("caseSensitive") else re.IGNORECASE
    try:
        matcher = re.compile(pattern if regex else re.escape(pattern), flags)
    except re.error as error:
        raise ToolError(f"Invalid regular expression: {error}") from None

    hits, scanned, truncated = [], 0, False
    for path in _iter_files(ctx, root, args.get("glob") and [args["glob"]]):
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if matcher.search(line):
                hits.append(f"{ctx.sandbox.relative(path)}:{number}: {line.strip()[:MAX_LINE]}")
                if len(hits) >= MAX_HITS:
                    truncated = True
                    break
        if truncated:
            break

    if not hits:
        return {"ok": True, "content":
                f'No match for "{pattern}" in {scanned} file(s) under '
                f"{ctx.sandbox.relative(root)}. The symbol may be named differently - "
                "search for a shorter fragment before assuming it is absent."}
    tail = f"\n[stopped at {MAX_HITS} matches]" if truncated else ""
    return {"ok": True, "content": f"{len(hits)} match(es) in {scanned} file(s):\n"
                                   + "\n".join(hits) + tail}


def search(args, ctx):
    return _scan(ctx, str(args["query"]), args, regex=False)


def grep_search(args, ctx):
    return _scan(ctx, str(args["pattern"]), args, regex=True)


def glob_files(args, ctx):
    root = ctx.sandbox.resolve(args.get("path") or ".", must_exist=True)
    pattern = str(args["pattern"])
    found = []
    for path in ctx.sandbox.walk(root):
        relative = ctx.sandbox.relative(path)
        if fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(path.name, pattern):
            found.append(relative)
            if len(found) >= 400:
                break
    if not found:
        return {"ok": True, "content": f'Nothing matches "{pattern}" under {ctx.sandbox.relative(root)}.'}
    return {"ok": True, "content": f"{len(found)} file(s):\n" + "\n".join(sorted(found))}


def inspect_project(args, ctx):
    """A structural read of the project: what exists and how it is laid out.

    Called before planning so a blueprint is written against the real tree
    rather than an imagined one.
    """
    from ..layout import inspect_layout, format_layout
    return {"ok": True, "content": format_layout(inspect_layout(ctx.sandbox.root))}


def register(registry):
    registry.add(Tool(
        name="search", risk=SAFE, review_safe=True, handler=search,
        description="Find a literal string across the workspace. Use this before assuming a "
                    "path, symbol or file extension.",
        parameters={"type": "object", "required": ["query"], "properties": {
            "query": {"type": "string"},
            "path": {"type": "string", "description": "Directory to search. Defaults to the root."},
            "glob": {"type": "string", "description": 'Restrict to matching files, e.g. "*.jsx".'},
            "caseSensitive": {"type": "boolean"},
        }},
        summarize=lambda a: a.get("query", "")))

    registry.add(Tool(
        name="grepSearch", risk=SAFE, review_safe=True, handler=grep_search,
        description="Search the workspace with a regular expression.",
        parameters={"type": "object", "required": ["pattern"], "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
            "glob": {"type": "string"},
            "caseSensitive": {"type": "boolean"},
        }},
        summarize=lambda a: a.get("pattern", "")))

    registry.add(Tool(
        name="globFiles", risk=SAFE, review_safe=True, handler=glob_files,
        description='List files matching a glob, e.g. "app/**/route.js".',
        parameters={"type": "object", "required": ["pattern"], "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string"},
        }},
        summarize=lambda a: a.get("pattern", "")))

    registry.add(Tool(
        name="inspectProject", risk=SAFE, review_safe=True, handler=inspect_project,
        description="Machine snapshot of the project layout: entry points, routes, models, "
                    "test config, package manager and scripts.",
        parameters={"type": "object", "properties": {}},
        summarize=lambda a: "project layout"))
