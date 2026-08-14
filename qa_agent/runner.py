"""
Running the generated tests, and turning what comes back into something a
fixer can act on.

Two details here are load-bearing rather than incidental:

* **The report goes to a file, never stdout.** `CommandRunner` truncates output
  at 4000 characters, and a truncated JSON document is unparseable — the stage
  would degrade to "we could not tell" without saying so. `--outputFile` writes
  the whole thing to disk and Python reads it back.
* **Every failure is mapped back to the app file it is about**, via the
  manifest the author wrote. Without that mapping there is no way to allowlist
  a fix: "which file may be edited to satisfy this test" would be a guess, and
  the fixer would be handed the whole project.

`kind` is classified here, in Python, because it decides arbitration. An
unresolved import while the build is green is the *test's* fault, not the app's,
and no model gets a vote on that.
"""
import hashlib
import json
import logging
import re
from pathlib import Path

from .spec import TestFailure

log = logging.getLogger("qa.runner")

REPORT = ".agentforge/qa/vitest.json"
TIMEOUT = 180


_KINDS = [
    ("IMPORT", re.compile(
        r"Failed to resolve import|Cannot find module|ERR_MODULE_NOT_FOUND"
        r"|does not provide an export", re.I)),

    ("SYNTAX", re.compile(
        r"SyntaxError|Transform failed|Unexpected token|Parse failure"
        r"|invalid JS syntax|Failed to parse source", re.I)),
    ("TIMEOUT", re.compile(r"Test timed out|hook timed out", re.I)),
    ("ASSERTION", re.compile(
        r"AssertionError|expected .* to |toBe|toEqual|toHaveBeenCalled", re.I)),
]


def classify(message: str) -> str:
    for kind, rx in _KINDS:
        if rx.search(message or ""):
            return kind
    return "RUNTIME"


_DIAGNOSES = [

    ("route handler crashed", re.compile(
        r"expected 500 to be [1-4]\d\d", re.I)),

    ("next/navigation not mocked", re.compile(
        r"invariant expected app router to be mounted", re.I)),

    ("submit-by-click", re.compile(
        r"expected \"spy\" to be called|toHaveBeenCalled.*never", re.I)),

    ("seed-data ambiguity", re.compile(r"Found multiple elements", re.I)),
    ("ObjectId vs JSON", re.compile(r"to be \{ ?Object \(buffer\)", re.I)),
    ("invented testid", re.compile(
        r"Unable to find an element by: \[data-testid", re.I)),
    ("role/name not in markup", re.compile(
        r"Unable to find an accessible element|Unable to find an element with"
        r" the role|Unable to find a label with the text", re.I)),
    ("exact copy not there", re.compile(
        r"Unable to find an element with the text", re.I)),
    ("missing helper or import", re.compile(
        r"is not a function|is not defined|No \S+ export is defined", re.I)),
    ("vi.mock hoisting", re.compile(
        r"Cannot access '\w+' before initialization", re.I)),
    ("timeout or async", re.compile(
        r"Test timed out|hook timed out|STACK_TRACE_ERROR", re.I)),
    ("presence assumption", re.compile(r"toBeInTheDocument|toBeVisible", re.I)),
]


_USELESS_TIMEOUT_RE = re.compile(r"STACK_TRACE_ERROR|Test timed out", re.I)


def timeout_hint(blob: str, duration_ms: float) -> str:
    """
    The advice a timed-out case needs, returned on its own.

    What vitest reports for one is `Error: STACK_TRACE_ERROR at task
    (chunk-hooks.js:638:27)` — it names neither the query that never resolved
    nor the component, so the repair loop is handed a failure with no evidence
    in it. Measured on one build: five such cases survived eight repair rounds
    and all three escalation tiers untouched, because there was nothing in the
    prompt to reason from. The causes are few and well known, so naming them is
    worth far more than the stack frame inside vitest's own runner.

    This used to APPEND the text to the blob and hand it back, and the advice
    then reached nobody. Measured on the bccycle build: the blob is 2365
    characters of vitest's own chunk-hooks.js frames, so the explanation began
    at index 2371 and `_parse` keeps `stack=rest[:2000]` — cut off entire. Even
    intact, `_failure_digest` keeps only lines starting "at ", and this is
    prose. Two independent filters, either one fatal.

    So it travels in `TestFailure.hint` instead, which is nobody's idea of a
    stack and is therefore never filtered like one. Returns "" for every
    failure class that has a message worth reading on its own.
    """
    if not blob or not _USELESS_TIMEOUT_RE.search(blob):
        return ""
    return ("--- what a timeout here actually means ---\n"
            "This case did not assert anything wrong; it never finished. It "
            f"ran for {int(duration_ms)}ms and was killed. Something it waited "
            "for never happened, and in this project that is nearly always one "
            "of three things:\n"
            "  1. `vi.useFakeTimers()` with an `await findBy…` or "
            "`await waitFor(…)` later in the file. Those poll the clock the "
            "fake timers froze, so they can never re-run. Fix: "
            "`vi.useFakeTimers({ shouldAdvanceTime: true })`, or drop the fake "
            "timers and pass `{ timeout: 2500 }` to waitFor.\n"
            "  2. A submit driven by `fireEvent.click` on the button. jsdom "
            "runs no default form submission, so `onSubmit` never fires and "
            "the success state never appears. Fix: "
            "`fireEvent.submit(container.querySelector('form'))`.\n"
            "  3. A `fetch` mock that resolves to nothing, so the handler "
            "awaits forever. Fix: make it resolve "
            "`{ ok: true, json: async () => ({}) }`.\n"
            "Check the file for those three in that order before changing any "
            "assertion — the assertions are probably fine.")


_OBJECTID_RE = re.compile(r"to be \{ ?Object \(buffer\)", re.I)


def objectid_hint(blob: str) -> str:
    """The string-versus-ObjectId comparison, named."""
    if not blob or not _OBJECTID_RE.search(blob):
        return ""
    return ("--- what `{ Object (buffer) }` means here ---\n"
            "The two sides are the same id in different types, so the values "
            "match and the comparison still fails. `oid()` returns a real "
            "ObjectId — an object — and anything that has been through a "
            "handler's JSON response, or through `.toString()`, is a 24-"
            "character string.\n"
            "So `expect(row._id.toString()).toBe(userId)` compares a string "
            "against an ObjectId and can never pass, however correct the code "
            "is. Convert BOTH sides: keep `const userId = String(oid())` at the "
            "top, or write `.toBe(userId.toString())` at the assertion. Do not "
            "change the handler — it is right to return a string.")


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_DOM_OPEN_RE = re.compile(r"^\s*<body\b", re.M)
_LONG_CLASS_RE = re.compile(r'class="[^"]{31,}"')
_SVG_RE = re.compile(r"<svg\b.*?</svg>", re.S)


DOM_CHARS = 1600


def _compact_dom(dom: str) -> str:
    """Squeeze pretty-printed markup down to the part that carries meaning."""

    out, buf = [], ""
    for line in dom.splitlines():
        buf = f"{buf} {line.strip()}" if buf else line.rstrip()
        if buf.rstrip().endswith(">") or not buf.strip():
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    text = "\n".join(out)

    text = _SVG_RE.sub("<svg/>", text)

    text = _LONG_CLASS_RE.sub('class="..."', text)
    if len(text) > DOM_CHARS:
        text = text[:DOM_CHARS] + "\n  … (markup truncated)"
    return text


def split_dom(blob: str) -> tuple:
    """
    `(everything else, the compacted markup)`.

    Inert for failures that carry no DOM — they come back unchanged with an
    empty second element, so nothing outside a render failure is affected.
    """
    text = _ANSI_RE.sub("", blob or "")
    open_at = _DOM_OPEN_RE.search(text)
    if not open_at:
        return text, ""
    close_at = text.find("</body>", open_at.start())
    if close_at < 0:
        return text, ""
    end = close_at + len("</body>")
    rest = text[:open_at.start()] + text[end:]
    return rest, _compact_dom(text[open_at.start():end])


def failure_hint(blob: str, duration_ms: float = 0) -> str:
    """
    The advice for whichever known class this failure belongs to, or "".

    Only for classes whose own error message does not say what is wrong. Most
    do — "Unable to find an element with the text: Home" needs no help — and a
    hint on those would be noise bought with the budget the source needs.
    """
    return timeout_hint(blob, duration_ms) or objectid_hint(blob)


def diagnose(message: str) -> str:
    """A short, human name for why one case failed. '' when nothing fits."""
    for name, rx in _DIAGNOSES:
        if rx.search(message or ""):
            return name
    return "value mismatch" if "AssertionError" in (message or "") else ""


def diagnose_all(failures) -> list:
    """`[(class, count), …]`, commonest first, for a round's failures."""
    counts = {}
    for f in failures or []:
        name = diagnose(getattr(f, "message", "") or "")
        if name:
            counts[name] = counts.get(name, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


class VitestRunner:
    """`npx vitest run`, parsed."""

    def __init__(self, project_dir, *, cmd=None, callbacks=None, session=None):
        self.project_dir = Path(project_dir)
        self.cmd = cmd
        self.cb = callbacks or {}
        self.qa = session

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn and callable(fn):
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):
        self._fire("on_log", lvl, txt)
        log.info(txt)

    def run(self, paths=None):
        """
        `(passed, failures, ok)`.

        `ok` is False when the suite could not be run at all — a missing
        runner, a config the reporter choked on. That is deliberately not the
        same as "the tests failed", and the caller must not treat it as a
        reason to edit anything.

        `paths` narrows the run to those test files. The author uses it to read
        back the one file it just wrote, which is the difference between
        writing a test and knowing whether it works — a whole-suite run there
        would be twenty seconds of other people's tests per revision.
        """

        from .harness import NPM_LOCK, npm_busy
        if npm_busy():
            self._log("INFO", "   ⏸ waiting for npm to finish before running "
                              "the tests")
        with NPM_LOCK:
            return self._run_locked(paths)

    def _run_locked(self, paths=None):

        rel = REPORT
        if paths:
            tag = hashlib.sha1(
                "|".join(sorted(str(p) for p in paths)).encode()
            ).hexdigest()[:10]
            rel = f".agentforge/qa/vitest-{tag}.json"
        out = self.project_dir / rel
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.exists():
                out.unlink()
        except Exception as e:
            log.debug(f"clearing {rel}: {e}")

        if not self.cmd:
            return 0, [], False

        only = ""
        if paths:
            only = " " + " ".join(str(p).replace("\\", "/") for p in paths)

        res = self.cmd.run(
            f"npx vitest run{only} --reporter=json --outputFile={rel}",
            timeout=TIMEOUT)

        data = None
        try:
            if out.is_file():
                data = json.loads(out.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            self._log("WARN", f"   ⚠ could not read the test report: {e}")

        if data is None:
            tail = (res.output or "").strip().splitlines()[-3:]
            self._log("WARN", "   ⚠ the test runner produced no report — "
                              "skipping the QA stage")
            for line in tail:
                self._log("WARN", f"      {line[:150]}")
            return 0, [], False

        passed, failures = self._parse(data)
        return passed, failures, True

    def _parse(self, data):
        passed, failures = 0, []

        self.last_cases = {}
        for suite in data.get("testResults") or []:
            rel = self._rel(suite.get("name") or suite.get("testFilePath") or "")
            target = self.qa.target_of(rel) if self.qa else ""
            stale = bool((self.qa.manifest.get(rel, {}) if self.qa else {}).get("stale"))

            if suite.get("status") == "failed" and not (suite.get("assertionResults") or []):
                msg = (suite.get("message") or "the test file could not be loaded").strip()
                failures.append(TestFailure(
                    test_file=rel, target=target, name="(the file did not load)",
                    message=msg.splitlines()[0][:400], stack=msg[:2000],
                    kind=classify(msg), stale=stale))
                continue

            for case in suite.get("assertionResults") or []:
                name = (case.get("fullName") or case.get("title") or "?")[:200]
                status = case.get("status") or "unknown"
                self.last_cases.setdefault(rel, {})[name] = status
                if status == "passed":
                    passed += 1
                    continue
                if status in ("skipped", "pending", "todo"):
                    continue
                msgs = case.get("failureMessages") or []
                blob = "\n".join(msgs)
                rest, dom = split_dom(blob)
                failures.append(TestFailure(
                    test_file=rel, target=target,
                    name=name,
                    message=(rest.strip().splitlines() or ["failed"])[0][:400],

                    stack=rest[:2000], kind=classify(blob), stale=stale,
                    dom=dom,
                    hint=failure_hint(blob, case.get("duration") or 0)))
        return passed, failures

    def case_names(self) -> set:
        """`{(test_file, case_name)}` for every case the last run saw."""
        return {(f, n) for f, cases in getattr(self, "last_cases", {}).items()
                for n in cases}

    def skipped(self) -> list:
        """`[(test_file, case_name)]` for cases the last run did not execute."""
        return sorted((f, n)
                      for f, cases in getattr(self, "last_cases", {}).items()
                      for n, st in cases.items()
                      if st in ("skipped", "pending", "todo"))

    def vanished(self, before: set) -> list:
        """
        Cases that existed in `before` and are not in the suite any more.

        A repair is allowed to make a case pass. It is not allowed to make a
        case disappear — that is how a suite reaches "100%" by deletion, which
        is the same lie as `it.skip` with the evidence removed.
        """
        return sorted(before - self.case_names())

    def _rel(self, abs_path):
        """
        The project-relative path, which is the manifest's key.

        Resolved on both sides first: vitest reports an absolute path with
        forward slashes, and `project_dir` is often relative — without
        resolving, `relative_to` raises and the fallback yields a bare
        filename, which finds nothing in the manifest. A failure with no target
        cannot be allowlisted, so the fixer would be handed the whole project.
        """
        raw = str(abs_path or "")
        norm = raw.replace("\\", "/").lstrip("./")

        if not Path(raw).is_absolute():
            return norm
        try:
            return str(Path(raw).resolve().relative_to(
                self.project_dir.resolve())).replace("\\", "/")
        except Exception:
            pass

        i = norm.find("/tests/")
        if i >= 0:
            return norm[i + 1:]
        return norm.split("/")[-1]

    def quarantine(self, test_file, why=""):
        """
        Move a test AgentForge could not make trustworthy out of the run.

        Kept rather than deleted so the mistake can be read. The config's
        `include` glob already excludes `tests/quarantine/`, so nothing else has
        to change.
        """
        src = self.project_dir / test_file
        if not src.is_file():
            return False
        dst = self.project_dir / "tests" / "quarantine" / Path(test_file).name
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            body = src.read_text(encoding="utf-8", errors="replace")
            note = f"// QUARANTINED by AgentForge: {why}\n" if why else ""
            dst.write_text(note + body, encoding="utf-8")
            src.unlink()
        except Exception as e:
            self._log("WARN", f"   ⚠ could not quarantine {test_file}: {e}")
            return False
        if self.qa:
            self.qa.manifest.pop(test_file, None)
            self.qa.report.quarantined.append(test_file)
            self.qa._save_manifest()
        self._log("WARN", f"   🚧 quarantined {test_file} — {why}")
        return True
