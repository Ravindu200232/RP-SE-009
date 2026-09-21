"""Running commands, and living with the ones that do not end.

`executeTerminal` covers installs, builds and one-shot scripts. A dev server is
the same call with `service:true`: the engine keeps it, the model proves it is
up by reaching its URL, and nothing has to invent `nohup`, `start /b` or a
batch wrapper to detach it. Every one of those tricks hides the exit code,
which is the only thing that says whether the command worked.
"""
from __future__ import annotations

import json

from ..errors import ToolError
from ..policy import BLOCKED, DANGEROUS, MODERATE, SAFE, classify
from .base import Tool

TAIL = 6000


def format_result(result: dict, sandbox=None) -> str:
    """The observation the model reads. Exit code first: it decides everything."""
    lines = []
    if result.get("pending"):
        lines.append(f"Still running as process {result['processId']} after "
                     f"{result['elapsed']}s. Continue other work and call waitForProcess "
                     f"with this id; do not start it again.")
    elif result.get("timedOut"):
        lines.append(f"Timed out and was stopped after {result['elapsed']}s.")
    else:
        lines.append(f"Exit code {result.get('exitCode')} after {result['elapsed']}s.")
    if result.get("startupFailed"):
        lines.append("The service exited immediately instead of staying up - read the output.")
    for name in ("stdout", "stderr"):
        body = (result.get(name) or "").strip()
        if body:
            lines.append(f"--- {name} ---\n{body[-TAIL:]}")
    if not (result.get("stdout") or result.get("stderr")):
        lines.append("(no output)")
    return "\n".join(lines)


def execute_terminal(args, ctx):
    command = str(args["command"]).strip()
    risk, reason = classify(command)
    if risk == BLOCKED:
        raise ToolError(
            f'"{command[:120]}" is refused by the permanent security policy ({reason}). '
            "This is not negotiable in any mode - achieve the goal another way.")

    cwd = ctx.sandbox.resolve(args.get("cwd") or ".", must_exist=True)
    service = bool(args.get("service"))
    timeout = float(args.get("timeoutSeconds") or ctx.config.command_timeout)
    ctx.events.emit("notice", level="info",
                    message=f"$ {command[:200]}" + (" (service)" if service else ""))
    result = ctx.processes.run(command, cwd, timeout=timeout, service=service)

    # The loop owns revision updates. A service or diagnostic does not change
    # source merely because it was launched through the terminal tool.
    ctx.memory.digest["actions"] = (ctx.memory.digest["actions"] + [f"ran: {command[:160]}"])[-40:]
    if ctx.memory.evidence is not None:
        ctx.memory.evidence.observe_process(result)

    ok = result.get("pending") or result.get("exitCode") == 0
    return {"ok": bool(ok), "content": format_result(result), "process": result,
            "mutates": bool(args.get("changesProject")) and not service}


def wait_for_process(args, ctx):
    job = ctx.processes.jobs.get(str(args["processId"]))
    if not job:
        raise ToolError(f"No process {args['processId']}. Call backgroundProcess to list them.")
    result = ctx.processes.wait(job, float(args.get("timeoutSeconds") or 600))
    if ctx.memory.evidence is not None:
        ctx.memory.evidence.observe_process(result)
    return {"ok": result.get("pending") or result.get("exitCode") == 0,
            "content": format_result(result), "process": result}


def background_process(args, ctx):
    jobs = ctx.processes.list()
    if not jobs:
        return {"ok": True, "content": "No processes have been started by this run."}
    rows = [f"- {j.id}: {'service' if j.service else 'task'}, "
            f"{'running' if j.running else f'exited {j.exit_code}'}, "
            f"{round(j.summary()['elapsed'], 1)}s - {j.command[:140]}" for j in jobs]
    return {"ok": True, "content": "Processes started by this run:\n" + "\n".join(rows)}


def stop_process(args, ctx):
    stopped = ctx.processes.stop(str(args["processId"]))
    return {"ok": True,
            "content": (f"Stopped process {args['processId']} and its children."
                        if stopped else f"Process {args['processId']} was not running.")}


def register(registry):
    registry.add(Tool(
        name="runtimeInfo", risk=SAFE, review_safe=True,
        handler=lambda args, ctx: {"ok": True, "content": json.dumps(
            ctx.processes.runtime_info() if ctx.processes.runtime_info else
            {"note": "Use the project's configured available ports."})},
        description="Get this project's allocated PORT, service ports and PUBLIC_APP_URL before starting "
                    "or probing its runtime. Commands inherit these environment values. Use them; "
                    "never hardcode a different --port or kill a process holding another port.",
        parameters={"type": "object", "properties": {}}, summarize=lambda args: "runtime ports"))
    registry.add(Tool(
        name="executeTerminal", risk=MODERATE, mutates=True, handler=execute_terminal,
        description="Run a shell command in the workspace. For a dev server or watcher pass "
                    "service:true and then prove readiness by reaching its URL - never use "
                    "nohup, start /b, a trailing & or a batch wrapper to detach it.",
        parameters={"type": "object", "required": ["command"], "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string", "description": "Workspace-relative directory."},
            "service": {"type": "boolean",
                        "description": "A long-lived server or watcher that is not meant to exit."},
            "changesProject": {"type": "boolean",
                               "description": "True for generators, installs and migrations."},
            "timeoutSeconds": {"type": "number"},
        }},
        summarize=lambda a: str(a.get("command", ""))[:70]))

    registry.add(Tool(
        # Allow background process inspection and completion waiting for command-starting roles.
        name="waitForProcess", risk=SAFE, review_safe=True, handler=wait_for_process,
        description="Wait for a process started earlier and read its exit code and output. "
                    "This is how you wait - never spin on a no-op command to pass the time.",
        parameters={"type": "object", "required": ["processId"], "properties": {
            "processId": {"type": "string"},
            "timeoutSeconds": {"type": "number"},
        }},
        summarize=lambda a: a.get("processId", "")))

    registry.add(Tool(
        name="backgroundProcess", risk=SAFE, review_safe=True, handler=background_process,
        description="List the processes this run started, with their state.",
        parameters={"type": "object", "properties": {}},
        summarize=lambda a: "processes"))

    registry.add(Tool(
        name="stopProcess", risk=DANGEROUS, handler=stop_process,
        description="Stop a process this run started, including its children.",
        parameters={"type": "object", "required": ["processId"],
                    "properties": {"processId": {"type": "string"}}},
        summarize=lambda a: a.get("processId", "")))
