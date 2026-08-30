"""Repairs test and runtime failures using observed evidence."""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

# Source: import_reader.py — imported helper(s) come from this file.
from agents.core.imports.import_reader import effective_exports, parse_imports, resolve_local
# Source: source_workspace.py — imported helper(s) come from this file.
from agents.core.workspace.source_workspace import TOOL_HELP, WorkspaceTools
# Source: feature_contract.py — imported helper(s) come from this file.
from agents.features.feature_contract import safe_change_path
# Source: element_selector.py — imported helper(s) come from this file.
from agents.features.element_selector import guard_scope
# Source: app_builder.py — imported helper(s) come from this file.
from agents.planner.builder.app_builder import FileStreamParser

log = logging.getLogger("agent.bugfixer")
TEMPERATURE, CALL_BUDGET, MAX_APP_FILES = 0.15, 600, 4
CODE_CHANGE_FRAC, CODE_CHANGE_MIN = 0.50, 40
RUNTIME_CHANGE_FRAC, RUNTIME_CHANGE_MIN, RUNTIME_MAX_FILES = 0.95, 400, None
VERDICT_RE = re.compile(r"^\s*VERDICT\s*::\s*(test|code|harness|unclear)\s*(?:::\s*(.*))?$", re.I | re.M)
VERDICT_HARNESS = "harness"
WEAKENED_RE = re.compile(r"\b(?:it|test|describe)\s*\.\s*(?:skip|todo)\b|expect\s*\(\s*(?:true|1)\s*\)\s*\.\s*toBe\s*\(\s*(?:true|1)\s*\)")
HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
NEVER_CODE = frozenset({"lib/mongodb.js"})
PROMPT_FILE = Path(__file__).resolve().parents[1] / "analysis_prompt.txt"


@dataclass
class FixVerdict:
    test_file: str
    target: str = ""
    verdict: str = "test"
    evidence: str = ""
    forced: str = ""
    written: str = ""
    quarantine: bool = False
    rejected: list = field(default_factory=list)
    failing: list = field(default_factory=list)

    # Checks whether this repair changed production source code.
    @property
    def touched_code(self):
        """Return whether this repair changed production source code."""
        return bool(self.written) and self.written == self.target


# Loads the Bug Fixer instruction contract that tells the repair model how to judge evidence.
def _contract():
    """Prepare the contract value or state used by this focused pipeline step."""
    try: return PROMPT_FILE.read_text("utf-8")
    except OSError: return "Decide from evidence before writing. Preserve passing tests and exports."


SYSTEM = _contract() + "\n\nMODE: TEST_ARBITRATION"
RUNTIME_SYSTEM = _contract() + "\n\nMODE: FINDING_REPAIR"


class BugFixerAgent:
    """Review failing tests and repair proven runtime problems."""
    CASE_RE = re.compile(r"""\b(?:it|test)\s*(?:\.\s*\w+)?\s*\(\s*(['"`])(.+?)\1""", re.S)
    _CASE_START_RE = re.compile(r"""\b(?:it|test)(?:\s*\.\s*\w+)?\s*\(\s*(['"`])(?P<name>.+?)\1\s*,""", re.S)

    # Prepares BugFixerAgent with the services and starting state it needs before it begins work.
    def __init__(self, arch, project_dir=None, *, callbacks=None, session=None, runner=None, model=None):
        """Prepare this helper with the state it needs."""
        self.arch, self.project_dir, self.cb = arch, Path(project_dir or arch.project_dir), callbacks or {}
        self.qa, self.runner, self.model = session, runner, model or None
        self.app_writes, self.verdicts, self.refusals, self._collapsed = set(), [], {}, set()
        self._lock = threading.Lock()

    # Sends one progress event to the UI callback when a callback exists.
    def _fire(self, name, *args):
        """Send one progress event to the UI callback when a callback exists."""
        fn = self.cb.get(name)
        if callable(fn):
            try: fn(*args)
            except Exception as exc: log.warning("callback %s failed: %s", name, exc)
    # Writes one readable status message through the configured logger.
    def _log(self, level, text):
        """Write one readable status message through the configured logger."""
        self._fire("on_log", level, text) if callable(self.cb.get("on_log")) else log.info(text)
    # Read one current source file from the QA session or project workspace so repair decisions use the latest code.
    def _read(self, rel):
        """Read current step in the standard shape used by the rest of the pipeline."""
        if self.qa: return self.qa.read_source(rel)
        try:
            fp = self.arch._safe_path(rel); return fp.read_text("utf-8", errors="replace") if fp.is_file() else None
        except Exception: return None

    # Checks whether this path is allowed to be changed by this repair step.
    def editable(self, rel):
        """Return whether this path is allowed to be changed by this repair step."""
        rel = str(rel or "").strip().lstrip("./").replace("\\", "/")
        return bool(rel and rel not in NEVER_CODE and rel not in getattr(self.arch, "NEXT_PROTECTED", frozenset()) and rel.startswith(("app/", "components/", "lib/")) and not rel.startswith("app/api/auth/") and rel.endswith((".js", ".jsx")))
    # Checks whether this path is safe for a runtime repair.
    def runtime_editable(self, rel, privileged_paths=None):
        """Return whether this path is safe for a runtime repair."""
        # From: agents/features/feature_contract.py
        return safe_change_path(rel)
    # Read the requested source files and return a path-to-content map for repair analysis.
    def _files_for(self, *rels):
        """Prepare the files for value or state used by this focused pipeline step."""
        return {p: body for p in rels if (body := self._read(p)) is not None}
    # Read a target file and return the names that it actually exports.
    def exports_of(self, target):
        """Prepare the exports of value or state used by this focused pipeline step."""
        # From: agents/core/imports/import_reader.py
        try: return effective_exports(target, self._files_for(target)) or set()
        except Exception: return set()
    # Check whether the failing test really imports the application file it claims to test.
    def imports_target(self, test_file, target):
        """Prepare the imports target value or state used by this focused pipeline step."""
        body = self._read(test_file)
        if not body or not target: return True
        files = self._files_for(test_file, target)
        # From: agents/core/imports/import_reader.py
        try: return any(resolve_local(test_file, stmt.spec, files) == target for stmt in parse_imports(body))
        except Exception: return True
    # Compare a test import with the target file exports and return any missing names.
    def missing_export(self, test_file, target):
        """Prepare the missing export value or state used by this focused pipeline step."""
        body, files = self._read(test_file), self._files_for(test_file, target)
        if not body: return set()
        try:
            # From: agents/core/imports/import_reader.py
            available = effective_exports(target, files)
            # From: agents/core/imports/import_reader.py
            for stmt in parse_imports(body):
                # From: agents/core/imports/import_reader.py
                if stmt.names and resolve_local(test_file, stmt.spec, files) == target and available is not None:
                    gap = {name for name, _ in stmt.names if name not in available}
                    if gap: return gap
        except Exception as exc: log.debug("missing_export %s: %s", test_file, exc)
        return set()

    # Check the captured stack trace to see whether the runtime exception came from the target source file.
    @staticmethod
    def _threw_in(failure, target):
        """Prepare the threw in value or state used by this focused pipeline step."""
        want = str(target or "").replace("\\", "/").lstrip("./")
        for line in str(getattr(failure, "stack", "") or "").splitlines():
            norm = line.strip().replace("\\", "/")
            if not norm.startswith("at ") or "node_modules" in norm or "node:internal" in norm: continue
            if "/tests/" in norm: return False
            if want and want in norm: return True
        return False
    # Classify a failure before asking the model, using deterministic evidence whenever possible.
    def prior(self, failures, *, build_ok=True, round_no=1):
        """Prepare the prior value or state used by this focused pipeline step."""
        if not failures: return "test", "there is nothing to repair", "quarantine"
        first, kinds = failures[0], {f.kind for f in failures}; target = str(first.target or "").strip()
        if "SYNTAX" in kinds:
            named = re.search(r"((?:[A-Za-z]:)?[A-Za-z0-9_./\\-]+\.(?:jsx?|tsx?))\s*:\s*\d+\s*:\s*\d+", "\n".join((f.message or "") + "\n" + (f.stack or "") for f in failures))
            broken = (named.group(1).replace("\\", "/") if named else "").replace(str(self.project_dir).replace("\\", "/") + "/", "")
            if broken and broken != first.test_file and self.editable(broken): return "code", f"{broken} does not parse", "model"
            return "test", "the test file does not parse", "quarantine"
        if "CRASH" in kinds: return ("code", f"{target} threw during execution", "model") if target and self.editable(target) else ("test", "the crash is outside editable app source", "report")
        if not target: return "test", "the failure names no app target", "model"
        if not self.editable(target): return "test", f"{target} is not unit-fix editable", "model"
        if any(f.kind == "RUNTIME" and self._threw_in(f, target) for f in failures): return "code", f"{target} threw rather than failing an assertion", "model"
        missing = self.missing_export(first.test_file, target)
        if missing: return "", f"{target} does not export {', '.join(sorted(missing))}", "model"
        if not self.imports_target(first.test_file, target): return "", f"the test never imports its target; available exports: {', '.join(sorted(self.exports_of(target) & HTTP_METHODS))}", "model"
        if first.stale and round_no <= 1: return "", f"{target} changed after this test was authored", "model"
        return None, "", "model"

    # Split a test file into individual test-case blocks so passing cases can be preserved.
    @classmethod
    def _case_blocks(cls, body):
        """Prepare the case blocks value or state used by this focused pipeline step."""
        out, body = [], str(body or "")
        for match in cls._CASE_START_RE.finditer(body):
            # From: agents/data/database_server.py
            start, i, depth, quote, escaped = match.start(), body.index("(", match.start()), 0, "", False
            while i < len(body):
                char = body[i]
                if quote:
                    if escaped: escaped = False
                    elif char == "\\": escaped = True
                    elif char == quote: quote = ""
                elif char in "'\"`": quote = char
                elif char == "/" and i+1 < len(body) and body[i+1] == "/":
                    i = body.find("\n", i)
                    if i < 0: return None
                    continue
                elif char == "/" and i+1 < len(body) and body[i+1] == "*":
                    i = body.find("*/", i)
                    if i < 0: return None
                    i += 2; continue
                elif char == "(": depth += 1
                elif char == ")":
                    depth -= 1
                    if depth == 0:
                        end = i + 1 + (i+1 < len(body) and body[i+1] == ";"); out.append((match.group("name").strip(), start, end)); break
                i += 1
            else: return None
        return out
    # Which `it(...)` titles the reported failing case names are about. Vitest reports a case by `fullName` — its
    # `ancestorTitles` joined to its title — so a case inside `describe('Navbar')` arrives as `Navbar toggles mobile
    # menu` while the source says `it('toggles mobile menu')`. Every generated test file is wrapped in a describe, so
    # the two sets never intersected, and the consequences ran the whole repair loop: * `_splice_passing` found the
    # failing case missing from its failing set, concluded it was passing, and spliced the OLD failing body back over
    # the model's repair. The only part of a rewrite that survived was the text between the cases — imports, `vi.mock`
    # factories, `beforeEach`, seeded rows — which is the shared setup every case depends on. So a round could not fix
    # the case it was about, and could only change the one thing that breaks the cases it was not about. Measured on
    # the luxestay build: three failing Navbar cases, zero overlap with the source titles, six writes, four still
    # failing. * `_lost_cases` subtracted fullNames from a set of titles, so renaming the failing case read as
    # dropping a passing one and the write was refused. Matched by suffix, because the ancestors are not in the
    # failure record and reconstructing the describe nesting is a parser this does not need. The longest match wins,
    # so `it('b')` sitting next to `it('a b')` is not swept up by a report of `D a b`.
    @classmethod
    def _failing_titles(cls, titles, reported):
        """
        Which `it(...)` titles the reported failing case names are about.

        Vitest reports a case by `fullName` — its `ancestorTitles` joined to its
        title — so a case inside `describe('Navbar')` arrives as `Navbar toggles
        mobile menu` while the source says `it('toggles mobile menu')`. Every
        generated test file is wrapped in a describe, so the two sets never
        intersected, and the consequences ran the whole repair loop:

        * `_splice_passing` found the failing case missing from its failing set,
          concluded it was passing, and spliced the OLD failing body back over
          the model's repair. The only part of a rewrite that survived was the
          text between the cases — imports, `vi.mock` factories, `beforeEach`,
          seeded rows — which is the shared setup every case depends on. So a
          round could not fix the case it was about, and could only change the
          one thing that breaks the cases it was not about. Measured on the
          luxestay build: three failing Navbar cases, zero overlap with the
          source titles, six writes, four still failing.
        * `_lost_cases` subtracted fullNames from a set of titles, so renaming
          the failing case read as dropping a passing one and the write was
          refused.

        Matched by suffix, because the ancestors are not in the failure record
        and reconstructing the describe nesting is a parser this does not need.
        The longest match wins, so `it('b')` sitting next to `it('a b')` is not
        swept up by a report of `D a b`.
        """
        reported = [t for t in (str(n or "").strip() for n in (reported or [])) if t]
        titles = [t for t in (str(t or "").strip() for t in (titles or [])) if t]
        out = set()
        for name in reported:
            hits = [t for t in titles if name == t or name.endswith(" " + t)]
            if hits: out.add(max(hits, key=len))
        return out
    # Put already-passing test cases back after a repair so the model cannot silently remove them.
    @classmethod
    def _splice_passing(cls, old, new, failing):
        """Prepare the splice passing value or state used by this focused pipeline step."""
        before, after = cls._case_blocks(old), cls._case_blocks(new)
        if not before or after is None: return ""
        failing = cls._failing_titles([n for n, _, _ in before] + [n for n, _, _ in after], failing)
        source, pieces, cursor = {n: (s, e) for n, s, e in before}, [], 0
        for name, start, end in after:
            if name in failing or name not in source: continue
            old_start, old_end = source[name]; pieces += [new[cursor:start], old[old_start:old_end]]; cursor = end
        return "" if not pieces else "".join(pieces) + new[cursor:]
    # Whether a reported case name still names an `it(...)` in this file.
    @classmethod
    def has_case(cls, body, name):
        """Whether a reported case name still names an `it(...)` in this file."""
        if not body or not name: return False
        if str(name) in body: return True
        return bool(cls._failing_titles([n for n, _, _ in (cls._case_blocks(body) or [])], [name]))
    # Finds test cases that disappeared from a rewritten test file.
    @classmethod
    def _lost_cases(cls, old, new, failing):
        """Prepare the lost cases value or state used by this focused pipeline step."""
        before = {m.group(2).strip() for m in cls.CASE_RE.finditer(old or "")}; after = {m.group(2).strip() for m in cls.CASE_RE.finditer(new or "")}; lost = (before-after)-cls._failing_titles(before|after, failing)
        return f"drops passing cases: {', '.join(sorted(lost)[:3])}" if lost else ""
    # Detect whether a repair weakened tests by skipping them or replacing assertions with trivial checks.
    @staticmethod
    def _weakened(old, new):
        """Prepare the weakened value or state used by this focused pipeline step."""
        if not str(new or "").strip(): return "the rewrite is empty"
        if WEAKENED_RE.search(new) and not WEAKENED_RE.search(old or ""): return "introduces a skipped/totological test"
        before, after = len(re.findall(r"\bexpect\s*\(", old or "")), len(re.findall(r"\bexpect\s*\(", new))
        return f"assertions fell from {before} to {after}" if before and after * 2 < before else ""

    # Builds the evidence-rich prompt that is sent to the Bug Fixer model.
    def _prompt(self, failures, test_body, target_body, forced, reason, refused="", tier=0):
        """Build current step in the standard shape used by the rest of the pipeline."""
        first = failures[0]; rows = [f"- {f.name}: {f.message}\n  {str(f.stack or '')[:1200]}" for f in failures[:6]]
        parts = [f"## Failing test: {first.test_file}\n```js\n{test_body[:12000]}\n```", f"## Production target: {first.target or '(none)'}\n```js\n{str(target_body or '')[:12000]}\n```", "## Failures\n" + "\n".join(rows)]
        if forced: parts.append(f"The evidence fixes the verdict as {forced}: {reason}")
        elif reason: parts.append("AgentForge observation (weigh it, do not blindly accept it): " + reason)
        if refused: parts.append("Your last write to this file did not stand: " + refused)
        if tier >= 2: parts.append("Earlier test rewrites did not resolve this; production code may be the owner.")
        if tier >= 3: parts.append("If both test and code match, inspect the harness and answer harness without writing.")
        parts.append("Use workspace tools when a dependency or contract is missing. Emit VERDICT first, then at most one complete write_file block.")
        return "\n\n".join(parts)

    # Returns a readable refusal result for a command that is outside the allowed workspace policy.
    def _refuse(self, verdict, path, why):
        """Return a readable refusal result for a command that is outside the allowed workspace policy."""
        verdict.rejected.append(path); self.refusals[verdict.test_file or path] = why; self._log("WARN", f"   ⛔ {path}: {why}")
    # Saves the unit owned by this pipeline step.
    def _write_unit(self, path, content, said, verdict):
        """Save the unit owned by this pipeline step."""
        old = self._read(path) or ""
        if said == "code":
            # From: agents/features/element_selector.py
            problem = "that file is not editable" if not self.editable(path) else guard_scope(old, content, adding=True, retexting=True)
            if problem: self._refuse(verdict, path, problem); return
            if self.arch.write_file(path, content): self.app_writes.add(path); verdict.written = path
            return
        problem = self._weakened(old, content) or self._lost_cases(old, content, verdict.failing)
        if problem: self._refuse(verdict, path, problem); return
        spliced = self._splice_passing(old, content, verdict.failing)
        if spliced and not self._weakened(old, spliced): content = spliced
        if self.qa:
            meta = self.qa.manifest.get(path) or {}
            if self.qa.write_test_file(path, content, target=meta.get("target", verdict.target), phase=meta.get("phase", 0), tier=meta.get("tier", 0)): verdict.written = path

    # Runs the evidence-based repair flow for the current failures and return the accepted repair verdict/result.
    def fix(self, failures, *, build_ok=True, round_no=1, tier=0):
        """Repair current step safely without changing unrelated project behavior."""
        if not failures: return FixVerdict(test_file="", evidence="there is nothing to repair")
        first, forced, reason_action = failures[0], *self.prior(failures, build_ok=build_ok, round_no=round_no)[:2]
        _, _, action = self.prior(failures, build_ok=build_ok, round_no=round_no)
        verdict = FixVerdict(first.test_file, str(first.target or "").strip(), failing=[f.name for f in failures if f.name], forced=reason_action if forced else "")
        if action in {"quarantine", "report"}: verdict.verdict, verdict.evidence, verdict.quarantine = forced or "test", reason_action, action == "quarantine"; self.verdicts.append(verdict); return verdict
        test_body, target_body = self._read(first.test_file) or "", self._read(first.target) if first.target else ""
        messages = [{"role": "system", "content": SYSTEM + "\n\n" + TOOL_HELP}, {"role": "user", "content": self._prompt(failures, test_body, target_body, forced, reason_action, self.refusals.get(first.test_file, "") if tier else "", tier)}]
        # From: agents/core/workspace/source_workspace.py
        self.arch._workspace_tool_cache = {}; tools, raw, state = WorkspaceTools(self.arch), [], {"verdict": "", "evidence": ""}
        # Choose the repair verdict and next action from the current failure evidence.
        def decision():
            """Prepare the decision value or state used by this focused pipeline step."""
            match = VERDICT_RE.search("".join(raw))
            # From: agents/planner/builder/project_memory.py
            if match: state.update(verdict=match.group(1).lower(), evidence=(match.group(2) or "")[:300])
            return state["verdict"]
        # Finishes the current streamed model response and process the complete text collected for this turn.
        def on_end(path, content):
            """Prepare the on end value or state used by this focused pipeline step."""
            key, said = str(path or "").strip().lstrip("./").replace("\\", "/"), forced or decision() or "test"; allowed = {first.test_file} if said != "code" else {verdict.target}
            if key not in allowed: self._refuse(verdict, key, f"not writable under {said} verdict")
            else: self._write_unit(key, content, said, verdict)
        # From: agents/planner/builder/app_builder.py
        parser = FileStreamParser(on_text=raw.append, on_file_start=lambda p: self._fire("on_file_start", p), on_file_token=lambda _: None, on_file_end=on_end)
        for _ in range(3):
            chunks = []
            try:
                # Accepts another streamed model chunk and emit any complete file blocks.
                def feed(token):
                    """Accept another streamed model chunk and emit any complete file blocks."""
                    # From: agents/planner/builder/write_stream.py
                    chunks.append(token); parser.feed(token)
                self.arch._stream(messages, feed, temperature=TEMPERATURE, model=self.model, timeout=CALL_BUDGET)
            except Exception as exc: self._log("WARN", f"   ⚠ bug fixer failed: {exc}"); break
            # From: agents/core/workspace/source_workspace.py
            reply = "".join(chunks); messages.append({"role": "assistant", "content": reply}); observation, used = tools.serve(reply)
            if used and not verdict.written: messages.append({"role": "user", "content": "Tool observations:\n\n" + observation + "\n\nContinue the same arbitration; verdict must precede a write."}); continue
            break
        # From: agents/planner/builder/write_stream.py
        parser.close(); said = decision(); verdict.verdict, verdict.evidence = forced or said or "test", state["evidence"] or reason_action
        if said in {"harness", "unclear"} and not verdict.written: verdict.quarantine = True
        self.verdicts.append(verdict); return verdict

    # Repairs runtime.
    def fix_runtime(self, errors, spec, *, server_log="", round_no=1, privileged_paths=None):
        """Repair runtime safely without changing unrelated project behavior."""
        planned = [f for f in getattr(spec, "files", []) if self.runtime_editable(f.get("path"), privileged_paths)]
        if not planned: return []
        # From: agents/core/workspace/source_workspace.py
        paths = {f["path"] for f in planned}; neighborhood = WorkspaceTools(self.arch).dependency_paths(paths, max_depth=3, cap=32); allowed = paths | set(neighborhood)
        evidence = {p: self._read(p) or "" for p in allowed}; context = getattr(spec, "context", {}) or {}
        proved = list(dict.fromkeys([str(x.get("path") or "") for x in context.get("evidence") or [] if isinstance(x, dict)] + [f["path"] for f in planned]))
        source = "\n\n".join(f"### {p} — COMPLETE CURRENT FILE\n```js\n{evidence[p]}\n```" for p in proved if p in evidence)
        parts = [f"## Runtime/browser evidence\n```\n{str(errors)[:6000]}\n{str(server_log)[:5000]}\n```", f"## Analyzer diagnosis — ALREADY PROVEN\n{getattr(spec, 'summary', '')}\n{context}", "## Initial impact\n" + "\n".join(f"- {f['path']}: {f.get('why','suspected by diagnosis')}" for f in planned)]
        if source: parts.append("## Analyzer source evidence — COMPLETE CURRENT FILES\n" + source)
        messages = [{"role": "system", "content": RUNTIME_SYSTEM + "\n\n" + TOOL_HELP}, {"role": "user", "content": "\n\n".join(parts) + "\n\nDo not re-prove Analyzer evidence. Read the attached complete files as authoritative current state, trace only missing dependencies, repair every manifestation of the proven root contract, and emit complete files only."}]
        # From: agents/core/workspace/source_workspace.py
        self.arch._workspace_tool_cache = {}; tools, written = WorkspaceTools(self.arch), []
        # Finishes the current streamed model response and process the complete text collected for this turn.
        def on_end(path, content):
            """Prepare the on end value or state used by this focused pipeline step."""
            key = str(path or "").strip().lstrip("./").replace("\\", "/")
            if not self.runtime_editable(key, privileged_paths): self._log("WARN", f"   ⛔ unsafe runtime repair {key}"); return
            # From: agents/core/imports/import_reader.py
            old = evidence.get(key, self._read(key) or ""); before, after = effective_exports(key, {key: old}) or set(), effective_exports(key, {key: content}) or set()
            if before-after: self._log("WARN", f"   ⛔ {key} drops exports: {', '.join(sorted(before-after))}"); return
            if self.arch.write_file(key, content): written.append(key); self.app_writes.add(key)
        # From: agents/planner/builder/app_builder.py
        parser = FileStreamParser(on_text=lambda _: None, on_file_start=lambda p: self._fire("on_file_start", p), on_file_token=lambda _: None, on_file_end=on_end)
        for _ in range(4):
            chunks = []
            try:
                # Accepts another streamed model chunk and emit any complete file blocks.
                def feed(token):
                    """Accept another streamed model chunk and emit any complete file blocks."""
                    # From: agents/planner/builder/write_stream.py
                    chunks.append(token); parser.feed(token)
                self.arch._stream(messages, feed, temperature=TEMPERATURE, model=self.model, timeout=CALL_BUDGET)
            except Exception as exc: self._log("WARN", f"   ⚠ runtime repair failed: {exc}"); break
            # From: agents/core/workspace/source_workspace.py
            reply = "".join(chunks); messages.append({"role": "assistant", "content": reply}); observation, used = tools.serve(reply)
            if used and not written: messages.append({"role": "user", "content": "Tool observations:\n\n" + observation + "\n\nContinue the same root-cause repair."}); continue
            break
        # From: agents/planner/builder/write_stream.py
        parser.close()
        if written: self.arch.repair_missing_imports(); self.arch.sync_dependencies()
        return written

    # Accepts a runtime repair only after its changed files pass the runtime safety rules.
    def _commit_runtime(self, key, content, old):
        """Prepare the commit runtime value or state used by this focused pipeline step."""
        if not content or not content.strip() or not self.arch.write_file(key, content): return False
        self.app_writes.add(key); return True
    # Accepts a test/code repair only after the proposed changes pass the repair safety checks.
    def _commit(self, key, content, said, verdict):
        """Prepare the commit value or state used by this focused pipeline step."""
        self._write_unit(key, content, said, verdict)
    # Turn the current result into a short human-readable summary.
    def summary(self):
        """Turn the current result into a short human-readable summary."""
        if not self.verdicts: return "no repairs attempted"
        code = sum(v.touched_code for v in self.verdicts); tests = sum(bool(v.written) and not v.touched_code for v in self.verdicts); held = sum(v.quarantine for v in self.verdicts)
        return f"{tests} test(s) corrected, {code} code fix(es), {held} set aside"


__all__ = ["BugFixerAgent", "FixVerdict", "SYSTEM", "RUNTIME_SYSTEM", "TEMPERATURE", "CALL_BUDGET", "MAX_APP_FILES", "CODE_CHANGE_FRAC", "CODE_CHANGE_MIN", "RUNTIME_CHANGE_FRAC", "RUNTIME_CHANGE_MIN", "RUNTIME_MAX_FILES", "VERDICT_RE", "VERDICT_HARNESS", "WEAKENED_RE", "HTTP_METHODS", "NEVER_CODE", "log"]
