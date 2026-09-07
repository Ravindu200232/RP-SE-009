"""Execution evidence: what actually ran, and what it proved.

This is the ledger the completion gate reads and the studio's Testing tab
renders. It records command exit status and browser-journey outcomes, never a
model's assertion that something passed - which is the whole point. A model
that says "all tests pass" and a suite that exited 0 are different claims, and
only one of them is admissible here.

The ledger lives outside lossy context checkpoints: a summary may forget that a
suite failed, and a run must not.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from .errors import ToolError

KINDS = ("unit", "e2e", "runtime")
EVIDENCE_KINDS = KINDS + ("visual",)
SCOPE_PAGE = 200
DEFAULT_UNIT_TARGET = 90
DEFAULT_E2E_TARGET = 100

COVERAGE_METRICS = ("lines", "statements", "functions", "branches")


def clip(value, limit: int = 600) -> str:
    return str(value if value is not None else "")[:limit]


def _requirement_id(value, index: int, used: set) -> tuple[str, bool]:
    original = str(value or "").strip()
    ident = original
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", ident or ""):
        ident = re.sub(r"[^a-z0-9._-]+", "-", ident.lower()).strip("-")[:64]
    if not ident:
        ident = f"requirement-{index + 1}"
    base, suffix = ident, 2
    while ident in used:
        tail = f"-{suffix}"
        ident = base[:64 - len(tail)] + tail
        suffix += 1
    return ident, ident != original


def _evidence_kind(value) -> str | None:
    key = re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())
    key = re.sub(r"(?:test(?:ing|s)?|checks?|evidence)$", "", key)
    if key == "unit":
        return "unit"
    if key in {"e2e", "endtoend", "end2end", "integration", "browser"}:
        return "e2e"
    if key in {"runtime", "smoke", "boot", "startup"}:
        return "runtime"
    if key in {"visual", "screenshot", "pixel", "ui"}:
        return "visual"
    return None


def _normalise_evidence(item: dict) -> tuple[list[str], bool]:
    raw = item.get("evidence")
    values = raw if isinstance(raw, list) else ([raw] if isinstance(raw, str) else [])
    if isinstance(raw, str):
        values = [v for v in re.split(r"[,/|\s]+", raw) if v]
    mapped = [_evidence_kind(v) for v in values]
    unknown = any(m is None for m in mapped)
    kinds = list(dict.fromkeys(m for m in mapped if m))
    # Unknown or missing model vocabulary must never weaken verification: the
    # three execution layers are the conservative fallback. Visual stays
    # explicit, because it is opt-in.
    if not kinds or unknown:
        for kind in KINDS:
            if kind not in kinds:
                kinds.append(kind)
    return kinds, unknown or not values


def evaluate_unit_coverage(coverage: dict | None, target: float) -> dict:
    """Judge a machine coverage report against the floor, or say it is missing."""
    if not coverage:
        return {"status": "missing", "target": target, "metrics": None,
                "failures": [
                    f"No machine-readable coverage report was produced, and the floor is "
                    f"{target}%. Run the suite with coverage enabled and pass the report path "
                    'in coverageReports, e.g. ["coverage/coverage-summary.json"].']}
    metrics, failures = {}, []
    for name in COVERAGE_METRICS:
        entry = coverage.get(name)
        if not isinstance(entry, dict):
            continue
        pct = entry.get("pct")
        if not isinstance(pct, (int, float)):
            continue
        metrics[name] = {"pct": round(float(pct), 2)}
        if pct + 1e-9 < target:
            failures.append(f"{name} coverage {round(float(pct), 2)}% is below the {target}% floor")
    if not metrics:
        return {"status": "missing", "target": target, "metrics": None,
                "failures": ["The coverage report carried no usable percentages."]}
    return {"status": "passed" if not failures else "below-target",
            "target": target, "metrics": metrics, "failures": failures}


class Evidence:
    """The durable record of what this run has proved."""

    def __init__(self) -> None:
        self.revision = 0
        self.sequence = 0
        self.active = False
        self.workspace: str | None = None
        self.scope: dict | None = None
        self.suites: list[dict] = []
        self.visuals: list[dict] = []
        self.limitations: dict[str, str] = {}
        self.enabled_kinds: set[str] = set(KINDS)
        self.repairs: list[str] = []

    # -- lifecycle -------------------------------------------------------
    def bind(self, workspace: str) -> None:
        """Evidence from another project proves nothing about this one."""
        if self.workspace and self.workspace != workspace:
            self.suites, self.visuals, self.scope, self.limitations = [], [], None, {}
            self.active = False
            self.revision += 1
        self.workspace = workspace

    def changed(self) -> None:
        """A code change happened; passes taken before it are now outdated."""
        self.revision += 1

    @property
    def required_kinds(self) -> list[str]:
        """Runtime is never optional.

        It is the only check that exercises the real final application, and a
        green build plus a green unit suite have both been observed passing
        while the app served a blank page.
        """
        return [k for k in KINDS if k == "runtime" or k in self.enabled_kinds]

    @property
    def visual_required(self) -> bool:
        return "visual" in self.enabled_kinds

    # -- scope -----------------------------------------------------------
    def _clean_requirements(self, requirements) -> list[dict]:
        if not isinstance(requirements, list) or not requirements or len(requirements) > SCOPE_PAGE:
            raise ToolError(f"Provide 1-{SCOPE_PAGE} verification requirements per page. "
                            "Use another page rather than omitting public boundaries.")
        used, clean = set(), []
        self.repairs = []
        for index, item in enumerate(requirements):
            item = item if isinstance(item, dict) else {"description": str(item)}
            ident, repaired_id = _requirement_id(
                item.get("id") or item.get("requirementId") or item.get("key"), index, used)
            description = str(item.get("description") or item.get("behavior") or
                              item.get("requirement") or "").strip()
            if not description:
                description = f"Verify {ident.replace('_', ' ').replace('-', ' ')}."
            if len(description) > 240:
                description = description[:239].rstrip() + "…"
            kinds, repaired_kinds = _normalise_evidence(item)
            if repaired_id:
                self.repairs.append(f"requirement {index + 1}: normalised its id to {ident}")
            if repaired_kinds:
                self.repairs.append(f"requirement {ident}: normalised evidence to {', '.join(kinds)}")
            used.add(ident)
            clean.append({"id": ident, "description": description, "evidence": kinds})
        return clean

    def define_scope(self, project_type: str, stack: str, requirements,
                     finalize: bool = True, unit_target: float = DEFAULT_UNIT_TARGET,
                     e2e_target: float = DEFAULT_E2E_TARGET) -> dict:
        if not str(project_type or "").strip() or not str(stack or "").strip():
            raise ToolError("Project type and the detected stack are both required.")
        clean = self._clean_requirements(requirements)
        nxt = {"projectType": project_type.strip(), "stack": str(stack)[:500],
               "requirements": clean, "finalized": bool(finalize),
               "quality": {"unit": float(unit_target), "e2e": float(e2e_target)}}
        if self.scope and json.dumps(self.scope, sort_keys=True) != json.dumps(nxt, sort_keys=True):
            # The transcript keeps prior output. The ledger keeps evidence only
            # for the current scope, so obsolete suites cannot block completion.
            self.changed()
            self.suites, self.visuals = [], []
        self.scope = nxt
        self.active = True
        return self.scope

    def extend_scope(self, requirements, finalize: bool | None = None) -> tuple[dict, int]:
        if not self.scope:
            raise ToolError("Define the first verification-scope page before extending it.")
        page = self._clean_requirements(requirements)
        existing = {item["id"]: item for item in self.scope["requirements"]}
        additions = []
        for item in page:
            prior = existing.get(item["id"])
            if prior:
                if json.dumps(prior, sort_keys=True) != json.dumps(item, sort_keys=True):
                    raise ToolError(f"Requirement {item['id']} already exists with different evidence.")
                continue  # An exact retry after a transport hiccup is idempotent.
            existing[item["id"]] = item
            additions.append(item)
        sealed = self.scope["finalized"] if finalize is None and not additions else bool(finalize)
        if finalize is None and additions:
            sealed = False
        if additions or self.scope["finalized"] != sealed:
            self.changed()
            self.scope = {**self.scope,
                          "requirements": self.scope["requirements"] + additions,
                          "finalized": sealed}
        self.active = True
        return self.scope, len(additions)

    def validate_covers(self, kind: str, covers) -> list[str]:
        covers = covers or []
        if not isinstance(covers, list) or len(covers) > 200:
            raise ToolError("covers must contain at most 200 requirement IDs.")
        known = {r["id"] for r in (self.scope or {}).get("requirements", [])}
        clean = []
        for value in covers:
            ident = str(value or "").strip()
            if not ident:
                continue
            if ident not in known:
                # Some models decorate a known id with the evidence kind
                # ("checkout/e2e"). Accept an unambiguous base plus a matching
                # suffix; anything else stays an error.
                decorated = re.fullmatch(r"(.*?)[/:#|]\s*(unit|e2e|runtime|visual)", ident, re.I)
                if decorated and decorated.group(1) in known:
                    if decorated.group(2).lower() != kind:
                        raise ToolError(f"Coverage reference {ident} labels "
                                        f"{decorated.group(2)} evidence, but this suite is {kind}.")
                    ident = decorated.group(1)
            if ident not in clean:
                clean.append(ident)
        if clean and not self.scope:
            raise ToolError("Define the verification scope before assigning coverage.")
        for ident in clean:
            requirement = next((r for r in self.scope["requirements"] if r["id"] == ident), None)
            if not requirement:
                raise ToolError(f"Unknown verification requirement: {ident}")
            if kind not in requirement["evidence"]:
                raise ToolError(f"Requirement {ident} does not call for {kind} evidence.")
        return clean

    # -- suites ----------------------------------------------------------
    def _record(self, kind: str, suite: str) -> dict:
        if kind not in KINDS:
            raise ToolError("Test kind must be unit, e2e or runtime.")
        record = next((r for r in self.suites if r["kind"] == kind and r["suite"] == suite), None)
        if record is None:
            record = {"kind": kind, "suite": suite}
            self.suites.append(record)
        return record

    def start(self, kind: str, suite: str, command: str, test_files, covers,
              coverage_reports=()) -> dict:
        self.active = True
        covered = self.validate_covers(kind, covers)  # validate before mutating
        record = self._record(kind, suite)
        if record.get("status") == "running":
            raise ToolError("This suite is already running. Wait for it; do not restart it.")
        record.update({
            "command": clip(command, 4000), "testFiles": list(test_files or []),
            "coverageReports": list(coverage_reports or []), "coverage": None,
            "covers": covered, "revision": self.revision, "sequence": self._next(),
            "status": "running", "processId": None, "exitCode": None,
            "output": "", "reason": None, "timedOut": False,
        })
        self.limitations.pop(kind, None)
        return record

    def record_external(self, kind: str, suite: str, source: str, covers,
                        status: str, output: str = "", reason: str | None = None) -> dict:
        """Deterministic non-command evidence, such as a browser journey."""
        self.active = True
        if status not in ("passed", "failed"):
            raise ToolError("External evidence status must be passed or failed.")
        covered = self.validate_covers(kind, covers)
        record = self._record(kind, suite)
        record.update({
            "command": clip(source or "direct execution", 4000), "source": clip(source, 240),
            "testFiles": [], "coverageReports": [], "coverage": None, "covers": covered,
            "revision": self.revision, "sequence": self._next(), "status": status,
            "processId": None, "exitCode": 0 if status == "passed" else 1,
            "output": clip(output, 1200), "reason": clip(reason, 600) if reason else None,
            "timedOut": False,
        })
        self.limitations.pop(kind, None)
        return record

    def observe(self, record: dict, result: dict) -> None:
        record["processId"] = result.get("processId", record.get("processId"))
        joined = "\n".join(filter(None, [record.get("output", ""),
                                         result.get("stdout", ""), result.get("stderr", "")]))
        record["output"] = joined[-1200:]
        record["exitCode"] = result.get("exitCode")
        record["timedOut"] = result.get("timedOut") is True
        passed = (result.get("exitCode") == 0 and not result.get("timedOut")
                  and not result.get("service") and result.get("status") not in ("stopped", "failed"))
        record["status"] = "running" if result.get("pending") else ("passed" if passed else "failed")
        if result.get("coverage"):
            record["coverage"] = copy.deepcopy(result["coverage"])
        if record["status"] == "passed" and record["kind"] == "unit":
            target = (self.scope or {}).get("quality", {}).get("unit", DEFAULT_UNIT_TARGET)
            check = evaluate_unit_coverage(record.get("coverage"), target)
            if check["status"] != "passed":
                record["status"] = "failed"
                record["reason"] = "; ".join(check["failures"])

    def observe_process(self, result: dict) -> None:
        pid = result.get("processId")
        record = next((r for r in self.suites
                       if pid and r.get("processId") == pid and r.get("status") == "running"), None)
        if record:
            self.observe(record, result)

    def capture_visual(self, capture: dict) -> dict:
        self.active = True
        capture = {**capture, "covers": self.validate_covers("visual", capture.get("covers"))}
        record = next((r for r in self.visuals
                       if r.get("view") == capture.get("view")
                       and r.get("width") == capture.get("width")), None)
        if record is None:
            record = {}
            self.visuals.append(record)
        record.update(capture)
        record.update({"revision": self.revision, "status": "captured",
                       "findings": "Not visually reviewed.", "model": None})
        self.limitations.pop("visual", None)
        return record

    def review_visual(self, view: str, width: int, status: str, findings: str, model: str) -> dict:
        record = next((r for r in self.visuals
                       if r.get("view") == view and r.get("width") == width), None)
        if record is None:
            raise ToolError(f"No capture of {view} at {width}px to review.")
        record.update({"status": status, "findings": clip(findings, 1200), "model": model})
        return record

    def limit(self, kind: str, reason: str) -> None:
        """Record something that genuinely could not be verified.

        A limitation is never a pass, and it never erases a failed suite.
        """
        if kind not in EVIDENCE_KINDS or not str(reason).strip():
            raise ToolError("A test kind and a specific limitation are both required.")
        self.limitations[kind] = clip(reason)
        self.active = True

    def _next(self) -> int:
        self.sequence += 1
        return self.sequence

    # -- reporting -------------------------------------------------------
    def summary(self) -> dict:
        """Current state, with passes taken before the last edit marked outdated.

        Voiding a pass on every edit made each keystroke demand a full re-run,
        so a run spent its time re-proving work it had already proved and never
        converged. What has to hold is that the *finished* article is verified
        once, at the revision it is finished at - that is the regression check
        below, not a re-run after every change.
        """
        def aged(record):
            status = record.get("status")
            if status == "passed" and record.get("revision") != self.revision:
                return {**record, "status": "outdated"}
            return dict(record)

        suites = [aged(r) for r in self.suites]
        visuals = [aged(r) for r in self.visuals]
        required = self.required_kinds

        missing = [k for k in required
                   if not any(r["kind"] == k and r["status"] in ("passed", "outdated") for r in suites)]
        regression = [k for k in required
                      if any(r["kind"] == k and r["status"] == "outdated" for r in suites)
                      and not any(r["kind"] == k and r["status"] == "passed" for r in suites)]
        unresolved = [r for r in suites if r["status"] not in ("passed", "retired")]

        uncovered = []
        for requirement in (self.scope or {}).get("requirements", []):
            for kind in requirement["evidence"]:
                if kind == "visual":
                    if not self.visual_required:
                        continue
                    covered = any(v["status"] == "passed" and requirement["id"] in (v.get("covers") or [])
                                  for v in visuals)
                elif kind not in required:
                    continue
                else:
                    covered = any(r["kind"] == kind and r["status"] in ("passed", "outdated")
                                  and requirement["id"] in (r.get("covers") or []) for r in suites)
                if not covered:
                    uncovered.append({"id": requirement["id"], "kind": kind,
                                      "description": requirement["description"]})

        def requirement_coverage(kind):
            wanted = [r for r in (self.scope or {}).get("requirements", []) if kind in r["evidence"]]
            done = [r for r in wanted
                    if (any(v["status"] == "passed" and r["id"] in (v.get("covers") or []) for v in visuals)
                        if kind == "visual" else
                        any(s["kind"] == kind and s["status"] == "passed"
                            and r["id"] in (s.get("covers") or []) for s in suites))]
            total = len(wanted)
            return {"covered": len(done), "total": total,
                    "percent": round(len(done) * 100 / total, 2) if total else 100.0}

        quality = (self.scope or {}).get("quality", {})
        unit_target = quality.get("unit", DEFAULT_UNIT_TARGET)
        e2e_target = quality.get("e2e", DEFAULT_E2E_TARGET)
        latest_unit = next((r.get("coverage") for r in
                            sorted([s for s in suites if s["kind"] == "unit" and s.get("coverage")],
                                   key=lambda s: s.get("sequence", 0), reverse=True)), None)
        unit = {**evaluate_unit_coverage(latest_unit, unit_target),
                "requirementCoverage": requirement_coverage("unit")}
        e2e = {**requirement_coverage("e2e"), "target": e2e_target}
        e2e["status"] = "passed" if e2e["percent"] >= e2e_target else "below-target"

        scope_open = bool(self.scope) and self.scope.get("finalized") is not True
        if self.visual_required and any(v["status"] == "outdated" for v in visuals) \
                and not any(v["status"] == "passed" for v in visuals):
            regression.append("visual")

        # A floor only gates the layers this run actually has to produce. When
        # unit evidence is switched off there is no coverage report to measure,
        # and demanding one would block every such run on a file that was never
        # going to exist.
        unit_ok = unit["status"] == "passed" or "unit" not in required
        e2e_ok = e2e["status"] == "passed" or "e2e" not in required

        return {
            "revision": self.revision, "scope": copy.deepcopy(self.scope), "scopeOpen": scope_open,
            "suites": suites, "visuals": visuals, "missing": missing,
            "regressionPending": regression, "requiredKinds": required,
            "missingRequirements": uncovered,
            "coverage": {"unit": unit, "e2e": e2e},
            "limitations": dict(self.limitations),
            "ready": bool(self.scope) and not scope_open and not missing and not regression
                     and not unresolved and not uncovered and not self.limitations
                     and unit_ok and e2e_ok
                     and (not self.visual_required
                          or all(v["status"] in ("passed", "retired", "outdated") for v in visuals)),
        }

    def report(self) -> str:
        """The bounded text the model reads when it asks where verification stands."""
        state = self.summary()
        lines = ["Testing evidence (command exit status, not a guarantee of coverage):"]
        for record in state["suites"][-60:]:
            reason = f"; reason: {clip(record.get('reason'), 220)}" if record.get("reason") else ""
            lines.append(f"- {record['kind']} / {record['suite']}: {record['status']} "
                         f"(exit {record.get('exitCode', 'pending')}). "
                         f"Command: {clip(record.get('command'), 160)}{reason}")
        for kind in state["missing"]:
            lines.append(f"- {kind}: no current passing run.")
        unit = state["coverage"]["unit"]
        metrics = (" - " + ", ".join(f"{n} {v['pct']}%" for n, v in unit["metrics"].items())
                   ) if unit.get("metrics") else ""
        lines.append(f"- unit source coverage: {unit['status']}{metrics}; target {unit['target']}%.")
        e2e = state["coverage"]["e2e"]
        lines.append(f"- E2E requirement coverage: {e2e['covered']}/{e2e['total']} "
                     f"({e2e['percent']}%); target {e2e['target']}%.")
        if state["scope"]:
            seal = "OPEN - add the remaining pages, then seal" if state["scopeOpen"] else "SEALED"
            lines.append(f"Verification scope ({seal}): {state['scope']['projectType']}; "
                         f"{len(state['scope']['requirements'])} requirement(s).")
        else:
            lines.append("- verification scope: not defined.")
        for item in state["missingRequirements"][:30]:
            lines.append(f"- uncovered {item['id']} / {item['kind']}: {clip(item['description'], 120)}")
        for record in state["visuals"][-30:]:
            lines.append(f"- visual / {record.get('view')} ({record.get('width')}px): "
                         f"{record['status']}; {clip(record.get('findings'), 300)}")
        for kind, reason in state["limitations"].items():
            lines.append(f"- {kind} limitation: {reason}")
        return "\n".join(lines)

    def recovery_report(self) -> str:
        """A small packet for a checkpoint; the full history stays in the ledger."""
        state = self.summary()
        actionable = sorted([r for r in state["suites"] if r["status"] not in ("passed", "retired")],
                            key=lambda r: r.get("sequence", 0), reverse=True)
        lines = [
            f"Verification revision {state['revision']}; "
            f"scope {'defined' if state['scope'] else 'missing'}"
            f"{' and OPEN' if state['scopeOpen'] else ''}; ready={state['ready']}.",
            f"Missing layers: {', '.join(state['missing']) or 'none'}; "
            f"uncovered evidence: {len(state['missingRequirements'])}; "
            f"actionable suites: {len(actionable)}.",
        ]
        for record in actionable[:8]:
            lines.append(f"- {record['kind']}/{record['suite']}: {record['status']}; "
                         f"exit={record.get('exitCode', 'pending')}"
                         f"{'; timed out' if record.get('timedOut') else ''}"
                         f"{('; ' + clip(record['reason'], 200)) if record.get('reason') else ''}")
        for item in state["missingRequirements"][:15]:
            lines.append(f"- uncovered {item['id']}/{item['kind']}: {clip(item['description'], 140)}")
        return "\n".join(lines)

    def fingerprint(self) -> str:
        return hashlib.sha256(
            json.dumps(self.serialize(), sort_keys=True, default=str).encode()).hexdigest()

    def serialize(self) -> dict:
        return copy.deepcopy({
            "active": self.active, "revision": self.revision, "sequence": self.sequence,
            "workspace": self.workspace, "scope": self.scope, "suites": self.suites,
            "visuals": self.visuals, "limitations": self.limitations,
            "enabledKinds": sorted(self.enabled_kinds),
        })

    def restore(self, saved: dict) -> None:
        saved = saved or {}
        self.active = saved.get("active", False)
        self.revision = int(saved.get("revision") or 0)
        self.sequence = int(saved.get("sequence") or 0)
        self.workspace = saved.get("workspace")
        self.scope = copy.deepcopy(saved.get("scope"))
        self.suites = copy.deepcopy(saved.get("suites") or [])
        self.visuals = copy.deepcopy(saved.get("visuals") or [])
        self.limitations = dict(saved.get("limitations") or {})
        if saved.get("enabledKinds"):
            self.enabled_kinds = set(saved["enabledKinds"])
        # A historical pass cannot verify a machine that may have changed.
        self.revision += 1
        for record in self.suites:
            if record.get("status") == "running":
                record["status"] = "interrupted"
            record["processId"] = None


# ---------------------------------------------------------------------------
# Failure packets
# ---------------------------------------------------------------------------
_REF = re.compile(r"""(?:^|[\s("'`])((?:[A-Za-z]:[\\/]|\.?\.?[\\/])?[^\s:"'`()<>|]+?):(\d{1,7})""",
                  re.M)
CONTEXT_RADIUS = 18


def source_refs(text: str, limit: int = 6) -> list[dict]:
    """path:line references, without assuming a language or a framework."""
    refs, seen = [], set()
    for match in _REF.finditer(str(text or "")):
        path = match.group(1).replace("\\", "/").replace("file://", "")
        if not path or path.startswith(("http://", "https://")):
            continue
        key = f"{path}:{match.group(2)}"
        if key in seen:
            continue
        seen.add(key)
        refs.append({"file": path, "line": int(match.group(2))})
        if len(refs) >= limit:
            break
    return refs


def failure_packet(sandbox, output: str, max_files: int = 3) -> str:
    """Turn a failure into the source it points at.

    A stack trace names a file and a line. Handing the model those lines with
    the error is the difference between diagnosing a failure and guessing at
    it, and it costs one bounded read per reference.
    """
    parts = []
    for ref in source_refs(output)[:max_files]:
        try:
            target = sandbox.resolve(ref["file"], must_exist=True)
        except Exception:  # noqa: BLE001 - a reference into another project is normal
            continue
        try:
            if target.stat().st_size > 2 * 1024 * 1024:
                continue
            lines = Path(target).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        line = min(len(lines), max(1, ref["line"]))
        start, end = max(1, line - CONTEXT_RADIUS), min(len(lines), line + CONTEXT_RADIUS)
        body = "\n".join(f"{n:>5} | {lines[n - 1]}" for n in range(start, end + 1))
        parts.append(f"{sandbox.relative(target)}:{ref['line']}\n{body}")
    if not parts:
        return ""
    return ("Source context for the failure (read before editing):\n\n"
            + "\n\n".join(parts))[:14_000]
