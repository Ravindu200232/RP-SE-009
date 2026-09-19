"""The terminal front end.

The same engine the studio drives, rendered for a terminal. Nothing here has
privileged access to anything the studio lacks: it subscribes to the event bus
like any other surface, which is what keeps the two consistent.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path

from . import __version__
from .agent import BuilderAgent
from .config import Config, DEFAULT_STACK, STACKS, detect_stack
from .errors import AgentError
from .events import Events
from .llm import OllamaClient, load_settings

# A Windows console defaults to cp1252, which cannot encode the symbols below;
# without this the first tick mark crashes the run rather than the build failing.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


DIM = lambda t: _c("2", t)          # noqa: E731 - a table of one-liners reads better inline
BOLD = lambda t: _c("1", t)         # noqa: E731
CYAN = lambda t: _c("36", t)        # noqa: E731
GREEN = lambda t: _c("32", t)       # noqa: E731
RED = lambda t: _c("31", t)         # noqa: E731
YELLOW = lambda t: _c("33", t)      # noqa: E731


class Renderer:
    """Turns the event stream into something readable at a prompt."""

    def __init__(self, stream: bool = True, verbose: bool = False) -> None:
        self.stream = stream
        self.verbose = verbose
        self.streaming = False
        self.lock = threading.Lock()

    def attach(self, events: Events) -> None:
        events.on("agent:start", self.on_start)
        events.on("iteration", self.on_iteration)
        events.on("token", self.on_token)
        events.on("tool:start", self.on_tool_start)
        events.on("tool:end", self.on_tool_end)
        events.on("notice", self.on_notice)
        events.on("phase", self.on_phase)
        events.on("test", self.on_test)
        events.on("e2e", self.on_e2e)
        events.on("context", self.on_context)

    def _line(self, text: str) -> None:
        with self.lock:
            if self.streaming:
                sys.stdout.write("\n")
                self.streaming = False
            print(text, flush=True)

    def on_start(self, p):
        self._line(f"\n{CYAN('▸')} {BOLD(p['task'][:120])}")
        self._line(DIM(f"  {p['model']} · {p['stack']} · {p['quality']} · {p['workspace']}"))

    def on_iteration(self, p):
        if self.verbose:
            self._line(DIM(f"  — step {p['iteration']}"))

    def on_token(self, p):
        if not self.stream:
            return
        with self.lock:
            sys.stdout.write(p.get("token", ""))
            sys.stdout.flush()
            self.streaming = True

    def on_tool_start(self, p):
        self._line(f"  {DIM('›')} {p['tool']} {DIM(p.get('summary', ''))}")

    def on_tool_end(self, p):
        mark = GREEN("✓") if p.get("ok") else RED("✗")
        detail = (p.get("detail") or "").strip().splitlines()
        head = detail[0][:160] if detail else ""
        if not p.get("ok") or self.verbose:
            self._line(f"    {mark} {head}")

    def on_notice(self, p):
        colour = {"warn": YELLOW, "error": RED}.get(p.get("level"), DIM)
        self._line(f"  {colour(p.get('message', ''))}")

    def on_phase(self, p):
        if p.get("status") == "active":
            self._line(f"\n{CYAN('◆')} {BOLD(p.get('title', p.get('phase', '')))}")

    def on_test(self, p):
        state = p.get("state")
        if state == "scope":
            self._line(DIM(f"  scope: {p.get('requirements')} requirement(s), "
                           f"{'sealed' if p.get('sealed') else 'open'}"))
        elif state == "run":
            self._line(f"  {DIM('⏵')} {p.get('kind')}/{p.get('suite')}")
        elif state == "result":
            mark = GREEN("PASS") if p.get("status") == "passed" else RED(p.get("status", "").upper())
            self._line(f"    {mark} {p.get('kind')}/{p.get('suite')} {DIM(p.get('detail', ''))}")

    def on_e2e(self, p):
        if p.get("state") == "journey_done":
            mark = GREEN("PASS") if p.get("status") == "passed" else RED("FAIL")
            self._line(f"    {mark} journey {p.get('suite')}")

    def on_context(self, p):
        if self.verbose:
            self._line(DIM(f"  context {p['tokens']}/{p['input_limit']} ({p['percent']}%)"))


def build_config(args) -> Config:
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    model = args.model or str(settings.get("agent_model") or "").strip()
    if not model:
        raise AgentError("No model selected. Pass --model, or set agent_model in "
                         "~/.agentforge/settings.json.")
    return Config(
        workspace=workspace, model=model, host=args.host or "",
        stack=args.stack or DEFAULT_STACK, think=args.think,
        max_iterations=args.max_iterations, temperature=args.temperature,
        command_timeout=args.timeout, unit_tests=not args.no_unit,
        e2e_tests=not args.no_e2e,
        context_tokens=args.context_tokens or 24_000,
    )


def cmd_models(args) -> int:
    client = OllamaClient(args.host or None)
    catalog = client.catalog()
    print(BOLD("\nCloud"))
    for entry in catalog["cloud"][:20]:
        mark = GREEN("●") if entry.get("installed") else DIM("○")
        print(f"  {mark} {entry['id']:<44} {DIM(entry['desc'])}")
    print(BOLD("\nLocal"))
    for entry in catalog["local_models"][:30]:
        print(f"  {GREEN('●')} {entry['id']:<44} {DIM(entry['desc'])}")
    if not catalog["local_models"]:
        print(DIM("  (none installed)"))
    print(DIM(f"\n  host {catalog['host']} · daemon "
              f"{'up' if catalog['ollama_ready'] else 'not answering'} · "
              f"cloud {catalog['cloud_via']}\n"))
    return 0


def _run(args, kind: str) -> int:
    task = " ".join(args.task).strip()
    if not task and kind != "review":
        print(f'Usage: builder-agent {kind} "<task>"', file=sys.stderr)
        return 1
    config = build_config(args)
    if not args.stack:
        config.stack = detect_stack(task)
    events = Events()
    renderer = Renderer(stream=not args.no_stream, verbose=args.verbose)
    if not args.json:
        renderer.attach(events)

    agent = BuilderAgent(config, events=events)
    try:
        if kind == "plan":
            outcome = agent.plan(task)
        elif kind == "review":
            outcome = agent.review(task or "Review the current change set.")
        else:
            outcome = agent.run(task)
    except AgentError as error:
        print(f"\n{RED('✗')} {error}\n", file=sys.stderr)
        return 1
    finally:
        agent.dispose()

    if args.json:
        print(json.dumps(outcome.as_dict(), indent=2, default=str))
    else:
        mark = GREEN("✓") if outcome.status == "completed" else YELLOW(outcome.status)
        print(f"\n{mark} {outcome.result}\n")
        evidence = outcome.evidence or {}
        if evidence.get("suites"):
            print(BOLD("Evidence"))
            for record in evidence["suites"]:
                tick = GREEN("pass") if record["status"] == "passed" else RED(record["status"])
                print(f"  {tick:<12} {record['kind']}/{record['suite']}")
            print()
        print(DIM(f"  {outcome.iterations} steps · {outcome.tool_calls} tool calls · "
                  f"{len(outcome.files)} files · {outcome.duration:.0f}s\n"))
    return 0 if outcome.status == "completed" else 2


def cmd_run(args) -> int:
    return _run(args, "run")


def cmd_plan(args) -> int:
    return _run(args, "plan")


def cmd_review(args) -> int:
    return _run(args, "review")


def cmd_chat(args) -> int:
    """An interactive session: one workspace, one memory, many turns."""
    config = build_config(args)
    events = Events()
    Renderer(stream=not args.no_stream, verbose=args.verbose).attach(events)
    agent = BuilderAgent(config, events=events)
    print(f"\n{CYAN('▸')} {BOLD('builder-agent')} {DIM(__version__)}  "
          f"{DIM(f'{config.model} · {config.workspace}')}")
    print(DIM("  Type a task. /plan <task>, /review, /status, /quit.\n"))
    try:
        while True:
            try:
                line = input(CYAN("› ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not line:
                continue
            if line in ("/quit", "/exit"):
                return 0
            if line == "/status":
                print(json.dumps(agent.snapshot(), indent=2, default=str))
                continue
            try:
                if line.startswith("/plan "):
                    outcome = agent.plan(line[6:].strip())
                elif line.startswith("/review"):
                    outcome = agent.review(line[7:].strip() or "Review the current change set.")
                else:
                    outcome = agent.run(line)
                print(f"\n{GREEN('✓') if outcome.status == 'completed' else YELLOW(outcome.status)} "
                      f"{outcome.result}\n")
            except AgentError as error:
                print(f"{RED('✗')} {error}")
    finally:
        agent.dispose()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="builder-agent",
        description="Plans, designs, builds and verifies one application.")
    parser.add_argument("-v", "--version", action="version", version=__version__)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-M", "--model", help="model id, e.g. qwen2.5-coder:14b")
    common.add_argument("-w", "--workspace", default=".", help="project directory")
    common.add_argument("--host", help="Ollama host")
    common.add_argument("--stack", choices=sorted(STACKS),
                        help="application stack (detected from the task by default)")
    common.add_argument("--think", action="store_true", help="ask the model to reason first")
    common.add_argument("--no-unit", action="store_true", help="skip unit-test evidence")
    common.add_argument("--no-e2e", action="store_true", help="skip end-to-end evidence")
    common.add_argument("--max-iterations", type=int, default=0,
                        help="stop after N steps (0: no cap)")
    common.add_argument("--context-tokens", type=int, default=0,
                        help="override the detected context window")
    common.add_argument("--timeout", type=int, default=1800, help="per-command timeout, seconds")
    common.add_argument("--temperature", type=float, default=0.2)
    common.add_argument("--json", action="store_true", help="emit JSON instead of text")
    common.add_argument("--no-stream", action="store_true", help="do not stream tokens")
    common.add_argument("--verbose", action="store_true")

    subparsers = parser.add_subparsers(dest="command")
    for name, handler, help_text in (
        ("run", cmd_run, "build the task and verify it"),
        ("plan", cmd_plan, "investigate and write a plan, changing nothing"),
        ("review", cmd_review, "read-only defect review of the current change set"),
        ("chat", cmd_chat, "interactive session"),
    ):
        sub = subparsers.add_parser(name, parents=[common], help=help_text)
        sub.add_argument("task", nargs="*")
        sub.set_defaults(handler=handler)
    models = subparsers.add_parser("models", help="list available models")
    models.add_argument("--host")
    models.set_defaults(handler=cmd_models)

    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 0
    try:
        return args.handler(args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
    except AgentError as error:
        print(f"\n{RED('✗')} {error}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
