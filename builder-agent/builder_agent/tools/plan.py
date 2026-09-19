"""Submitting a plan, reviewing a change, and reading a failure properly.

`submitPlan` exists so the planning pass ends on a deliberate act rather than
on a model deciding it has said enough. `inspectError` exists because a stack
trace names files and lines, and pulling those lines up next to the error is
the difference between diagnosing a failure and guessing at it.
"""
from __future__ import annotations

import subprocess

from ..evidence import failure_packet
from ..policy import SAFE
from .base import Tool


def submit_plan(args, ctx):
    plan = str(args["plan"]).strip()
    if len(plan) < 80:
        return {"ok": False, "content":
                "That plan is too short to execute. Give the goal and its invariants, what you "
                "found in the project, ordered phases with their done conditions, the acceptance "
                "evidence, and the real limitations."}
    ctx.state["plan"] = plan
    ctx.events.emit("plan", plan=plan, goal=str(args.get("goal") or "")[:400])
    return {"ok": True, "final": True, "content": plan}


def review_changes(args, ctx):
    """The current diff, or the working tree when there is no repository."""
    try:
        result = subprocess.run(["git", "diff", "--stat", "HEAD", "--", "."], cwd=ctx.sandbox.root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=30, check=False)
        detail = subprocess.run(["git", "diff", "HEAD", "--", "."], cwd=ctx.sandbox.root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return {"ok": False, "content": f"Could not read the change set: {error}"}
    if result.returncode != 0:
        return {"ok": True, "content":
                "This workspace is not a git repository, so there is no diff to review. "
                "Inspect the files the task touched directly."}
    body = (detail.stdout or "")[:30_000]
    return {"ok": True, "content": f"{result.stdout}\n\n{body}" if body else
            "Git reports no tracked changes under this workspace. Inspect any files created "
            "by this task directly, including untracked or ignored files."}


def inspect_error(args, ctx):
    output = str(args["output"])
    packet = failure_packet(ctx.sandbox, output, max_files=int(args.get("maxFiles") or 3))
    if not packet:
        return {"ok": True, "content":
                "That output names no workspace file and line I can resolve. Search for a "
                "distinctive fragment of the message instead."}
    return {"ok": True, "content": packet}


def register(registry):
    registry.add(Tool(
        name="submitPlan", risk=SAFE, review_safe=True, handler=submit_plan,
        description="Submit the finished plan as plain text or Markdown. Ends the planning pass. "
                    "Do not serialise it as JSON.",
        parameters={"type": "object", "required": ["plan"], "properties": {
            "plan": {"type": "string"},
            "goal": {"type": "string"},
        }},
        summarize=lambda a: "submit plan"))

    registry.add(Tool(
        name="reviewChanges", risk=SAFE, review_safe=True, handler=review_changes,
        description="Read the current uncommitted change set.",
        parameters={"type": "object", "properties": {}},
        summarize=lambda a: "review changes"))

    registry.add(Tool(
        name="inspectError", risk=SAFE, review_safe=True, handler=inspect_error,
        description="Paste failing output and get back the source around every file:line it "
                    "names. Do this before editing anything a failure points at.",
        parameters={"type": "object", "required": ["output"], "properties": {
            "output": {"type": "string"},
            "maxFiles": {"type": "integer", "default": 3},
        }},
        summarize=lambda a: "inspect error"))
