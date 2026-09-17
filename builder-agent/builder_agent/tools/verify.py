"""Declaring what has to be proved, and proving it.

The scope comes first and is sealed before the suites run, so a run cannot
quietly narrow what it promised once a flow turns out to be hard. Every suite
then names the requirement ids it covers, which is what turns "the tests
passed" into "these behaviours are proved and these are not".

Coverage is read from the runner's own machine-readable report. A model's
summary of its coverage is not coverage.
"""
from __future__ import annotations

import json
import time
import re
from pathlib import Path

from ..errors import ToolError
from ..evidence import DEFAULT_E2E_TARGET, DEFAULT_UNIT_TARGET, failure_packet
from ..policy import MODERATE, SAFE, classify, BLOCKED
from .base import Tool
from .terminal import format_result


def _read_coverage(ctx, reports) -> dict | None:
    """Load a coverage summary the runner wrote, or nothing.

    Only the runner's own file counts. Istanbul's `coverage-summary.json` is
    what Vitest and Jest both emit, so that is the shape read here.
    """
    for relative in reports or []:
        try:
            path = ctx.sandbox.resolve(relative, must_exist=True)
        except Exception:  # noqa: BLE001 - a missing report is an ordinary outcome
            continue
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        total = data.get("total") if isinstance(data, dict) else None
        if isinstance(total, dict):
            return total
    return None


def define_scope(args, ctx):
    quality = ctx.config.quality
    scope = ctx.memory.evidence.define_scope(
        project_type=str(args["projectType"]),
        stack=str(args["stack"]),
        requirements=args["requirements"],
        finalize=bool(args.get("finalize", True)),
        unit_target=float(args.get("unitCoverageTarget") or quality.unit_floor or DEFAULT_UNIT_TARGET),
        e2e_target=float(args.get("e2eCoverageTarget") or quality.e2e_floor or DEFAULT_E2E_TARGET),
    )
    repairs = ctx.memory.evidence.repairs
    seal = "sealed" if scope["finalized"] else "OPEN - extend it, then seal the last page"
    ctx.events.emit("test", state="scope", requirements=len(scope["requirements"]), sealed=scope["finalized"])
    body = (f"Verification scope {seal} with {len(scope['requirements'])} requirement(s):\n"
            + "\n".join(f"- {r['id']} [{', '.join(r['evidence'])}]: {r['description']}"
                        for r in scope["requirements"]))
    if repairs:
        body += "\n\nNormalised: " + "; ".join(repairs)
    return {"ok": True, "content": body}


def extend_scope(args, ctx):
    scope, added = ctx.memory.evidence.extend_scope(
        args["requirements"],
        None if args.get("finalize") is None else bool(args["finalize"]))
    seal = "sealed" if scope["finalized"] else "still OPEN"
    return {"ok": True, "content": f"Added {added} requirement(s); the scope is {seal} with "
                                   f"{len(scope['requirements'])} in total."}


def run_tests(args, ctx):
    kind = str(args["kind"]).lower()
    suite = str(args["suite"])
    command = str(args["command"]).strip()
    if re.fullmatch(r"(?:echo|printf|Write-Output)\s+[^;&|]+|true|exit\s+0", command, re.I):
        raise ToolError("A success message is not test evidence. Run a real test command or browserRunJourneys.")
    risk, reason = classify(command)
    if risk == BLOCKED:
        raise ToolError(f"That test command is refused by the security policy ({reason}).")

    covered = ctx.memory.evidence.validate_covers(kind, args.get("covers") or [])
    cached = next((r for r in ctx.memory.evidence.suites
                   if r["kind"] == kind and r["suite"] == suite
                   and r.get("command") == command and r.get("status") == "passed"
                   and kind != "runtime"
                   and r.get("revision") == ctx.memory.evidence.revision
                   and set(r.get("covers") or []) == set(covered)), None)
    if cached:
        return {"ok": True, "content": f"{kind} / {suite}: passed (reused at unchanged revision). "
                "Do not rerun this suite until code or runtime inputs change. Continue remaining checks."}

    record = ctx.memory.evidence.start(
        kind=kind, suite=suite, command=command,
        test_files=args.get("testFiles") or [], covers=args.get("covers") or [],
        coverage_reports=args.get("coverageReports") or [])

    cwd = ctx.sandbox.resolve(args.get("cwd") or ".", must_exist=True)
    ctx.events.emit("test", state="run", kind=kind, suite=suite, command=command[:200])
    started = time.time()
    result = ctx.processes.run(command, cwd,
                               timeout=float(args.get("timeoutSeconds") or 900),
                               service=False, yield_after=900)
    record["processId"] = result.get("processId")
    if not result.get("pending"):
        result["coverage"] = _read_coverage(ctx, args.get("coverageReports"))
        # The scaffold's own `npm test` writes test-report.json, so look there
        # when the call did not name a path. A run recorded without one carries
        # totals and nothing else, and "37 passing, 3 files" cannot name the
        # test that broke. The mtime check below still refuses a stale file, so
        # guessing the usual name costs nothing when it is not there.
        if kind == "unit":
            try:
                path = ctx.sandbox.resolve(args.get("reportPath") or "test-report.json")
                if not path.is_file():
                    raise FileNotFoundError(path)
                data = json.loads(path.read_text(encoding="utf-8"))
                if (path.stat().st_mtime >= started and isinstance(data, dict)
                        and isinstance(data.get("testResults"), list)):
                    record["report"] = data
            except (OSError, ValueError, ToolError):
                pass  # The command result remains evidence when no fresh JSON exists.
    ctx.memory.evidence.observe(record, result)

    body = format_result(result)
    if record["status"] == "failed":
        if record.get("reason"):
            body += f"\n\nEvidence gate: {record['reason']}"
        packet = failure_packet(ctx.sandbox, (result.get("stdout") or "") + (result.get("stderr") or ""))
        if packet:
            body += "\n\n" + packet
    ctx.events.emit("test", state="result", kind=kind, suite=suite,
                    status=record["status"], detail=(record.get("reason") or "")[:300])
    return {"ok": record["status"] != "failed",
            "content": f"{kind} / {suite}: {record['status']}\n{body}"}


def record_external(args, ctx):
    record = ctx.memory.evidence.record_external(
        kind=str(args["kind"]).lower(), suite=str(args["suite"]),
        source=str(args["source"]), covers=args.get("covers") or [],
        status=str(args["status"]).lower(), output=str(args.get("output") or ""),
        reason=args.get("reason"))
    ctx.events.emit("test", state="result", kind=record["kind"], suite=record["suite"],
                    status=record["status"], detail=(record.get("reason") or "")[:300])
    return {"ok": record["status"] == "passed",
            "content": f"Recorded {record['kind']} / {record['suite']} as {record['status']}."}


def testing_status(args, ctx):
    evidence = ctx.memory.evidence
    state = evidence.summary()
    body = evidence.recovery_report() + "\n\n" + evidence.report()
    if state["ready"]:
        body += "\n\nEvery required layer has current evidence at this revision."
    else:
        body += "\n\nNot ready. Close the gaps above before reporting completion."
    return {"ok": True, "content": body, "state": state}


def record_limitation(args, ctx):
    ctx.memory.evidence.limit(str(args["kind"]).lower(), str(args["reason"]))
    return {"ok": True, "content": f"Recorded a {args['kind']} limitation. This is not a pass - "
                                   "it will be reported as unverified."}


def register(registry):
    registry.add(Tool(
        name="defineVerificationScope", risk=SAFE, handler=define_scope,
        description="Declare what this task must prove, before writing tests. Each requirement "
                    "names the evidence it needs (unit/e2e/runtime/visual). Page large scopes "
                    "with finalize:false, then seal the last page.",
        parameters={"type": "object",
                    "required": ["projectType", "stack", "requirements"], "properties": {
                        "projectType": {"type": "string"},
                        "stack": {"type": "string", "description": "The stack you detected."},
                        "requirements": {"type": "array", "description":
                                         '[{id, description, evidence:["unit","e2e"]}]'},
                        "finalize": {"type": "boolean", "default": True},
                        "e2eCoverageTarget": {"type": "number"},
                    }},
        summarize=lambda a: str(a.get("projectType", "scope"))))

    registry.add(Tool(
        name="extendVerificationScope", risk=SAFE, handler=extend_scope,
        description="Add another page of requirements to an open verification scope.",
        parameters={"type": "object", "required": ["requirements"], "properties": {
            "requirements": {"type": "array"},
            "finalize": {"type": "boolean"},
        }},
        summarize=lambda a: "extend scope"))

    registry.add(Tool(
        name="runTests", risk=MODERATE, handler=run_tests,
        description="Run a test suite and record its exit code as evidence. Name the requirement "
                    "ids in covers. Optional coverageReports provide diagnostic percentages; "
                    "they do not determine pass/fail.",
        parameters={"type": "object",
                    "required": ["kind", "suite", "command"], "properties": {
                        "kind": {"type": "string", "enum": ["unit", "e2e", "runtime"]},
                        "suite": {"type": "string", "description": "Stable name for this suite."},
                        "command": {"type": "string"},
                        "cwd": {"type": "string"},
                        "testFiles": {"type": "array"},
                        "reportPath": {"type": "string", "description":
                                       "Optional Vitest JSON output from this same run, for per-case reporting."},
                        "covers": {"type": "array", "description": "Requirement ids this proves."},
                        "coverageReports": {"type": "array", "description":
                                            'e.g. ["coverage/coverage-summary.json"]'},
                        "timeoutSeconds": {"type": "number"},
                    }},
        summarize=lambda a: f"{a.get('kind')}/{a.get('suite')}"))

    registry.add(Tool(
        name="recordTestEvidence", risk=SAFE, handler=record_external,
        description="Record deterministic evidence that did not come from a shell command, "
                    "such as a browser journey the engine executed directly.",
        parameters={"type": "object",
                    "required": ["kind", "suite", "source", "status"], "properties": {
                        "kind": {"type": "string", "enum": ["unit", "e2e", "runtime"]},
                        "suite": {"type": "string"},
                        "source": {"type": "string"},
                        "status": {"type": "string", "enum": ["passed", "failed"]},
                        "covers": {"type": "array"},
                        "output": {"type": "string"},
                        "reason": {"type": "string"},
                    }},
        summarize=lambda a: f"{a.get('kind')}/{a.get('suite')}"))

    registry.add(Tool(
        name="testingStatus", risk=SAFE, review_safe=True, handler=testing_status,
        description="Read where verification stands: which layers have current passing evidence, "
                    "which requirements are uncovered, and what still blocks completion.",
        parameters={"type": "object", "properties": {}},
        summarize=lambda a: "testing status"))

    registry.add(Tool(
        name="recordLimitation", risk=SAFE, handler=record_limitation,
        description="Record something that genuinely cannot be verified here, with the specific "
                    "reason. This is reported as unverified, never as a pass.",
        parameters={"type": "object", "required": ["kind", "reason"], "properties": {
            "kind": {"type": "string", "enum": ["unit", "e2e", "runtime", "visual"]},
            "reason": {"type": "string"},
        }},
        summarize=lambda a: f"{a.get('kind')} limitation"))
