"""Repairs test and runtime failures using observed evidence."""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

from agents.core.exports_parse import effective_exports, parse_imports, resolve_local
from agents.core.workspace import TOOL_HELP, WorkspaceTools
from agents.features.features_common import safe_change_path
from agents.features.picker import guard_scope
from agents.planner.architecture import FileStreamParser

log = logging.getLogger("agent.bugfixer")
TEMPERATURE, CALL_BUDGET, MAX_APP_FILES = 0.15, 600, 4
CODE_CHANGE_FRAC, CODE_CHANGE_MIN = 0.50, 40
RUNTIME_CHANGE_FRAC, RUNTIME_CHANGE_MIN, RUNTIME_MAX_FILES = 0.95, 400, None
VERDICT_RE = re.compile(r"^\s*VERDICT\s*::\s*(test|code|harness|unclear)\s*(?:::\s*(.*))?$", re.I | re.M)
VERDICT_HARNESS = "harness"
WEAKENED_RE = re.compile(r"\b(?:it|test|describe)\s*\.\s*(?:skip|todo)\b|expect\s*\(\s*(?:true|1)\s*\)\s*\.\s*toBe\s*\(\s*(?:true|1)\s*\)")
HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
NEVER_CODE = frozenset({"lib/mongodb.js"})
PROMPT_FILE = Path(__file__).with_name("analysis_prompt.md")


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

    @property
    def touched_code(self): return bool(self.written) and self.written == self.target


def _contract():
    try: return PROMPT_FILE.read_text("utf-8")
    except OSError: return "Decide from evidence before writing. Preserve passing tests and exports."


SYSTEM = _contract() + "\n\nMODE: TEST_ARBITRATION"
RUNTIME_SYSTEM = _contract() + "\n\nMODE: FINDING_REPAIR"


class BugFixerAgent:
    """Review failing tests and repair proven runtime problems."""
    CASE_RE = re.compile(r"""\b(?:it|test)\s*(?:\.\s*\w+)?\s*\(\s*(['"`])(.+?)\1""", re.S)
    _CASE_START_RE = re.compile(r"""\b(?:it|test)(?:\s*\.\s*\w+)?\s*\(\s*(['"`])(?P<name>.+?)\1\s*,""", re.S)

    def __init__(self, arch, project_dir=None, *, callbacks=None, session=None, runner=None, model=None):
        self.arch, self.project_dir, self.cb = arch, Path(project_dir or arch.project_dir), callbacks or {}
        self.qa, self.runner, self.model = session, runner, model or None
        self.app_writes, self.verdicts, self.refusals, self._collapsed = set(), [], {}, set()
        self._lock = threading.Lock()

    def _fire(self, name, *args):
        fn = self.cb.get(name)
        if callable(fn):
            try: fn(*args)
            except Exception as exc: log.warning("callback %s failed: %s", name, exc)
    def _log(self, level, text):
        self._fire("on_log", level, text) if callable(self.cb.get("on_log")) else log.info(text)
    def _read(self, rel):
        if self.qa: return self.qa.read_source(rel)
        try:
            fp = self.arch._safe_path(rel); return fp.read_text("utf-8", errors="replace") if fp.is_file() else None
        except Exception: return None

    def editable(self, rel):
        rel = str(rel or "").strip().lstrip("./").replace("\\", "/")
        return bool(rel and rel not in NEVER_CODE and rel not in getattr(self.arch, "NEXT_PROTECTED", frozenset()) and rel.startswith(("app/", "components/", "lib/")) and not rel.startswith("app/api/auth/") and rel.endswith((".js", ".jsx")))
    def runtime_editable(self, rel, privileged_paths=None): return safe_change_path(rel)
    def _files_for(self, *rels): return {p: body for p in rels if (body := self._read(p)) is not None}
    def exports_of(self, target):
        try: return effective_exports(target, self._files_for(target)) or set()
        except Exception: return set()
    def imports_target(self, test_file, target):
        body = self._read(test_file)
        if not body or not target: return True
        files = self._files_for(test_file, target)
        try: return any(resolve_local(test_file, stmt.spec, files) == target for stmt in parse_imports(body))
        except Exception: return True
    def missing_export(self, test_file, target):
        body, files = self._read(test_file), self._files_for(test_file, target)
        if not body: return set()
        try:
            available = effective_exports(target, files)
            for stmt in parse_imports(body):
                if stmt.names and resolve_local(test_file, stmt.spec, files) == target and available is not None:
                    gap = {name for name, _ in stmt.names if name not in available}
                    if gap: return gap
        except Exception as exc: log.debug("missing_export %s: %s", test_file, exc)
        return set()

    @staticmethod
    def _threw_in(failure, target):
        want = str(target or "").replace("\\", "/").lstrip("./")
        for line in str(getattr(failure, "stack", "") or "").splitlines():
            norm = line.strip().replace("\\", "/")
            if not norm.startswith("at ") or "node_modules" in norm or "node:internal" in norm: continue
            if "/tests/" in norm: return False
            if want and want in norm: return True
        return False
    def prior(self, failures, *, build_ok=True, round_no=1):
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

    @classmethod
    def _case_blocks(cls, body):
        out, body = [], str(body or "")
        for match in cls._CASE_START_RE.finditer(body):
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
    @classmethod
    def _splice_passing(cls, old, new, failing):
        before, after = cls._case_blocks(old), cls._case_blocks(new)
        if not before or after is None: return ""
        failing = cls._failing_titles([n for n, _, _ in before] + [n for n, _, _ in after], failing)
        source, pieces, cursor = {n: (s, e) for n, s, e in before}, [], 0
        for name, start, end in after:
            if name in failing or name not in source: continue
            old_start, old_end = source[name]; pieces += [new[cursor:start], old[old_start:old_end]]; cursor = end
        return "" if not pieces else "".join(pieces) + new[cursor:]
    @classmethod
    def has_case(cls, body, name):
        """Whether a reported case name still names an `it(...)` in this file."""
        if not body or not name: return False
        if str(name) in body: return True
        return bool(cls._failing_titles([n for n, _, _ in (cls._case_blocks(body) or [])], [name]))
    @classmethod
    def _lost_cases(cls, old, new, failing):
        before = {m.group(2).strip() for m in cls.CASE_RE.finditer(old or "")}; after = {m.group(2).strip() for m in cls.CASE_RE.finditer(new or "")}; lost = (before-after)-cls._failing_titles(before|after, failing)
        return f"drops passing cases: {', '.join(sorted(lost)[:3])}" if lost else ""
    @staticmethod
    def _weakened(old, new):
        if not str(new or "").strip(): return "the rewrite is empty"
        if WEAKENED_RE.search(new) and not WEAKENED_RE.search(old or ""): return "introduces a skipped/totological test"
        before, after = len(re.findall(r"\bexpect\s*\(", old or "")), len(re.findall(r"\bexpect\s*\(", new))
        return f"assertions fell from {before} to {after}" if before and after * 2 < before else ""

    def _prompt(self, failures, test_body, target_body, forced, reason, refused="", tier=0):
        first = failures[0]; rows = [f"- {f.name}: {f.message}\n  {str(f.stack or '')[:1200]}" for f in failures[:6]]
        parts = [f"## Failing test: {first.test_file}\n```js\n{test_body[:12000]}\n```", f"## Production target: {first.target or '(none)'}\n```js\n{str(target_body or '')[:12000]}\n```", "## Failures\n" + "\n".join(rows)]
        if forced: parts.append(f"The evidence fixes the verdict as {forced}: {reason}")
        elif reason: parts.append("AgentForge observation (weigh it, do not blindly accept it): " + reason)
        if refused: parts.append("Your last write to this file did not stand: " + refused)
        if tier >= 2: parts.append("Earlier test rewrites did not resolve this; production code may be the owner.")
        if tier >= 3: parts.append("If both test and code match, inspect the harness and answer harness without writing.")
        parts.append("Use workspace tools when a dependency or contract is missing. Emit VERDICT first, then at most one complete write_file block.")
        return "\n\n".join(parts)

    def _refuse(self, verdict, path, why):
        verdict.rejected.append(path); self.refusals[verdict.test_file or path] = why; self._log("WARN", f"   ⛔ {path}: {why}")
    def _write_unit(self, path, content, said, verdict):
        old = self._read(path) or ""
        if said == "code":
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

    def fix(self, failures, *, build_ok=True, round_no=1, tier=0):
        if not failures: return FixVerdict(test_file="", evidence="there is nothing to repair")
        first, forced, reason_action = failures[0], *self.prior(failures, build_ok=build_ok, round_no=round_no)[:2]
        _, _, action = self.prior(failures, build_ok=build_ok, round_no=round_no)
        verdict = FixVerdict(first.test_file, str(first.target or "").strip(), failing=[f.name for f in failures if f.name], forced=reason_action if forced else "")
        if action in {"quarantine", "report"}: verdict.verdict, verdict.evidence, verdict.quarantine = forced or "test", reason_action, action == "quarantine"; self.verdicts.append(verdict); return verdict
        test_body, target_body = self._read(first.test_file) or "", self._read(first.target) if first.target else ""
        messages = [{"role": "system", "content": SYSTEM + "\n\n" + TOOL_HELP}, {"role": "user", "content": self._prompt(failures, test_body, target_body, forced, reason_action, self.refusals.get(first.test_file, "") if tier else "", tier)}]
        self.arch._workspace_tool_cache = {}; tools, raw, state = WorkspaceTools(self.arch), [], {"verdict": "", "evidence": ""}
        def decision():
            match = VERDICT_RE.search("".join(raw))
            if match: state.update(verdict=match.group(1).lower(), evidence=(match.group(2) or "")[:300])
            return state["verdict"]
        def on_end(path, content):
            key, said = str(path or "").strip().lstrip("./").replace("\\", "/"), forced or decision() or "test"; allowed = {first.test_file} if said != "code" else {verdict.target}
            if key not in allowed: self._refuse(verdict, key, f"not writable under {said} verdict")
            else: self._write_unit(key, content, said, verdict)
        parser = FileStreamParser(on_text=raw.append, on_file_start=lambda p: self._fire("on_file_start", p), on_file_token=lambda _: None, on_file_end=on_end)
        for _ in range(3):
            chunks = []
            try:
                def feed(token): chunks.append(token); parser.feed(token)
                self.arch._stream(messages, feed, temperature=TEMPERATURE, model=self.model, timeout=CALL_BUDGET)
            except Exception as exc: self._log("WARN", f"   ⚠ bug fixer failed: {exc}"); break
            reply = "".join(chunks); messages.append({"role": "assistant", "content": reply}); observation, used = tools.serve(reply)
            if used and not verdict.written: messages.append({"role": "user", "content": "Tool observations:\n\n" + observation + "\n\nContinue the same arbitration; verdict must precede a write."}); continue
            break
        parser.close(); said = decision(); verdict.verdict, verdict.evidence = forced or said or "test", state["evidence"] or reason_action
        if said in {"harness", "unclear"} and not verdict.written: verdict.quarantine = True
        self.verdicts.append(verdict); return verdict

    def fix_runtime(self, errors, spec, *, server_log="", round_no=1, privileged_paths=None):
        planned = [f for f in getattr(spec, "files", []) if self.runtime_editable(f.get("path"), privileged_paths)]
        if not planned: return []
        paths = {f["path"] for f in planned}; neighborhood = WorkspaceTools(self.arch).dependency_paths(paths, max_depth=3, cap=32); allowed = paths | set(neighborhood)
        evidence = {p: self._read(p) or "" for p in allowed}; context = getattr(spec, "context", {}) or {}
        parts = [f"## Runtime/browser evidence\n```\n{str(errors)[:6000]}\n{str(server_log)[:5000]}\n```", f"## Diagnosis\n{getattr(spec, 'summary', '')}\n{context}", "## Initial impact\n" + "\n".join(f"- {f['path']}: {f.get('why','suspected by diagnosis')}" for f in planned)]
        messages = [{"role": "system", "content": RUNTIME_SYSTEM + "\n\n" + TOOL_HELP}, {"role": "user", "content": "\n\n".join(parts) + "\n\nInspect the dependency chain, then emit complete files only."}]
        self.arch._workspace_tool_cache = {}; tools, written = WorkspaceTools(self.arch), []
        def on_end(path, content):
            key = str(path or "").strip().lstrip("./").replace("\\", "/")
            if not self.runtime_editable(key, privileged_paths): self._log("WARN", f"   ⛔ unsafe runtime repair {key}"); return
            old = evidence.get(key, self._read(key) or ""); before, after = effective_exports(key, {key: old}) or set(), effective_exports(key, {key: content}) or set()
            if before-after: self._log("WARN", f"   ⛔ {key} drops exports: {', '.join(sorted(before-after))}"); return
            if self.arch.write_file(key, content): written.append(key); self.app_writes.add(key)
        parser = FileStreamParser(on_text=lambda _: None, on_file_start=lambda p: self._fire("on_file_start", p), on_file_token=lambda _: None, on_file_end=on_end)
        for _ in range(4):
            chunks = []
            try:
                def feed(token): chunks.append(token); parser.feed(token)
                self.arch._stream(messages, feed, temperature=TEMPERATURE, model=self.model, timeout=CALL_BUDGET)
            except Exception as exc: self._log("WARN", f"   ⚠ runtime repair failed: {exc}"); break
            reply = "".join(chunks); messages.append({"role": "assistant", "content": reply}); observation, used = tools.serve(reply)
            if used and not written: messages.append({"role": "user", "content": "Tool observations:\n\n" + observation + "\n\nContinue the same root-cause repair."}); continue
            break
        parser.close()
        if written: self.arch.repair_missing_imports(); self.arch.sync_dependencies()
        return written

    def _commit_runtime(self, key, content, old):
        if not content or not content.strip() or not self.arch.write_file(key, content): return False
        self.app_writes.add(key); return True
    def _commit(self, key, content, said, verdict): self._write_unit(key, content, said, verdict)
    def summary(self):
        if not self.verdicts: return "no repairs attempted"
        code = sum(v.touched_code for v in self.verdicts); tests = sum(bool(v.written) and not v.touched_code for v in self.verdicts); held = sum(v.quarantine for v in self.verdicts)
        return f"{tests} test(s) corrected, {code} code fix(es), {held} set aside"


__all__ = ["BugFixerAgent", "FixVerdict", "SYSTEM", "RUNTIME_SYSTEM", "TEMPERATURE", "CALL_BUDGET", "MAX_APP_FILES", "CODE_CHANGE_FRAC", "CODE_CHANGE_MIN", "RUNTIME_CHANGE_FRAC", "RUNTIME_CHANGE_MIN", "RUNTIME_MAX_FILES", "VERDICT_RE", "VERDICT_HARNESS", "WEAKENED_RE", "HTTP_METHODS", "NEVER_CODE", "log"]
