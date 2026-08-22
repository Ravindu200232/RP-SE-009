"""
Repairing a failing test — after deciding whether the test or the code is wrong.

This is the piece that makes automated QA net-positive instead of net-negative.
Every other part of the subsystem produces evidence; this one acts on it, and
acting on evidence that points the wrong way is how automation makes an app
worse. A generated unit test is the **least** authoritative gate in the whole
pipeline, because it is the only one whose own correctness is in question: it
was written minutes ago by the same model that wrote the code it is judging.

So the design is arbitration first, repair second.

**The verdict decides the allowlist.** The model must emit

    VERDICT :: test :: <one sentence naming the evidence>

before any write block. `test` may write only the test file; `code` may write
only the target. A missing or unparseable verdict is `test` — fail safe toward
not touching working code. Because the stream is parsed incrementally, "before
any write block" is enforced literally: `on_end` reads the verdict accumulated
so far, so a model that writes first and explains afterwards gets the safe
default.

**Deterministic priors are shown to the model, not imposed on it.** They used
to outrank it, and the cost was paid in the one direction nobody sees: when the
prior was wrong, a correct test was rewritten until it agreed with a bug, and
the suite went green by giving up what it was checking. Both files are in the
prompt from the first attempt and either may be written; what AgentForge noticed
arrives as an observation. Only two things still decide by themselves — a file
that cannot be parsed, and a file nobody is allowed to edit — because neither
is a judgement call:

* An unresolved import while `npm run build` was green is the *test's* fault.
  The build proved every module in the app resolves.
* A test file that cannot be parsed says nothing about the app at all. AgentForge
  quarantines it and spends no model call.
* A test that imports a name its target does not export is wrong by
  `agents/exports.py` — the same check that found six real bugs in one project.
* `lib/mongodb.js` is never edited. It is the connection shape a standalone
  mongod requires rather than app logic, and a "fix" there is how a
  client/server boundary error became a webpack fallback that hid a 500. The
  auth files used to be on this list and are not any more: they are the app's
  code, AgentForge only wrote the first draft, and a fault in them has to be
  fixable by the thing that finds it.
* A test whose target was rewritten after it was authored is out of date rather
  than wrong — said to the model as much, and left for it to weigh.

**Weakening a test counts as failure, not as a fix.** `it.skip`, a deleted
assertion, `expect(true).toBe(true)` — each turns a red test green while making
it worthless, and each is exactly what a model reaches for when it cannot find
the real problem. That is checked in Python, after the write, and rejected.

What this class does *not* own: re-running the suite, re-running the build, and
restoring a snapshot when a round made things worse. Those belong to the caller,
because they are pipeline concerns and this must stay usable from a test.
"""
import logging
import threading
import re
from dataclasses import dataclass, field

from .architect import FileStreamParser
from .exports import effective_exports, parse_imports, resolve_local
from .picker import guard_scope

log = logging.getLogger("agent.bugfixer")

TEMPERATURE = 0.15


# The whole-call budget for one repair.
#
# A repair reads one test file and one target and rewrites one of them; ten
# minutes is already several times what that takes. Left unset, `_stream` says
# nothing to `chat_stream` and the call inherits its 1800s default, which is
# not a budget for this — it is the ceiling for a build that ran away, and four
# of these run at once. `MAX_TURN_CHARS` catches a model that floods; this
# catches the same model doing it slowly.
CALL_BUDGET = 600


MAX_APP_FILES = 4


CODE_CHANGE_FRAC = 0.50
CODE_CHANGE_MIN = 40


RUNTIME_CHANGE_FRAC = 0.95
RUNTIME_CHANGE_MIN = 400
RUNTIME_MAX_FILES = 6

VERDICT_RE = re.compile(
    r"^\s*VERDICT\s*::\s*(test|code|harness|unclear)\s*(?:::\s*(.*))?$",
    re.I | re.M)


VERDICT_HARNESS = "harness"


WEAKENED_RE = re.compile(
    r"\b(?:it|test|describe)\s*\.\s*(?:skip|todo)\b"
    r"|expect\s*\(\s*true\s*\)\s*\.\s*toBe\s*\(\s*true\s*\)"
    r"|expect\s*\(\s*1\s*\)\s*\.\s*toBe\s*\(\s*1\s*\)")


HTTP_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD",
                          "OPTIONS"})


NEVER_CODE = frozenset({"lib/mongodb.js"})


@dataclass
class FixVerdict:
    """What was decided about one failing test file, and what came of it."""
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
    def touched_code(self) -> bool:
        return bool(self.written) and self.written == self.target


SYSTEM = """\
A unit test is failing in a Next.js 16 App Router + MongoDB app. Almost always
one of two things is true, and deciding which is your actual job:

  • THE TEST IS WRONG — it asserts behaviour the code never promised, mocks the
    wrong module, calls a function that does not exist, or was written against
    an older version of the file.
  • THE CODE IS WRONG — the test describes what the app is supposed to do and
    the code demonstrably does something else.

Answer with ONE line, FIRST, before anything else you write:

VERDICT :: test :: <one sentence naming the evidence you used>
VERDICT :: code :: <one sentence naming the evidence you used>
VERDICT :: unclear :: <why you cannot tell from what you were given>

Then write exactly ONE file, complete, and nothing else:

<write_file path="tests/unit/api/example.test.js">
…the whole file…
</write_file>

THE VERDICT DECIDES WHAT YOU MAY WRITE. `test` may write only the test file.
`code` may write only the file under test. A write to any other path is thrown
away, and so is a write that arrives before the verdict line.

DECIDE FROM THE EVIDENCE IN FRONT OF YOU. Both files are here and you may write
either. Read what the test asks for, read what the code does, and say which one
is wrong about the app this is meant to be. Some background, not a rule: the
test was written minutes ago and has never been reviewed, while the code was
built to a plan and has served real requests — so the test is the more likely
offender. But if the code is the one that is wrong, say `code` and fix it.
Rewriting a correct test until it agrees with a bug is the one outcome that
looks like success and is not.

DO NOT MAKE THE TEST PASS BY MAKING IT MEANINGLESS. `it.skip`, deleting the
assertion, wrapping the call in try/catch, `expect(true).toBe(true)` — all of
these are rejected automatically and count as a failed repair. If the test
cannot be made honest, answer `unclear` and write nothing; it will be set aside
for a human, which is a better outcome than a green test that checks nothing.

THE MOCK CONTRACT — AgentForge wrote these helpers; they are correct, do not
reimplement them, and do not mock '@/lib/mongodb' or '@/lib/auth' any other way:

    vi.mock('@/lib/mongodb', () => import('../../helpers/mongoMock.js'))
    vi.mock('@/lib/auth',    () => import('../../helpers/authMock.js'))

    __seed('events', [{ _id: oid(), title: 'x' }])   // fill a collection
    __reset()                                        // in beforeEach
    __setUser({ id: oid(), role: 'admin' }) or null  // who is signed in
    const { status, json } = await postJson(POST, { … })
    const { status, json } = await getJson(GET, 'http://localhost:5173/api/x?q=1')
    oid()   // a VALID 24-char ObjectId — '123' throws inside the driver

If you write the code file, keep every export it already has. Other files import
them, and a repair that renames one turns a single failing test into a build
that does not compile.

CHANGE ONLY THE CASES THAT FAILED. You are handed the whole test file because
you must emit the whole test file, NOT because the whole file is in question.
Every `it(…)` block that is not in the failure list above is passing right now.
Reproduce those byte for byte — same name, same body, same imports, same
setup. Touch only the failing ones.

This is the single most expensive mistake available to you here. A file with
five cases and one failure, rewritten wholesale, comes back with three
failures: the one you were asked about plus two you broke on the way past. Two
rounds of that and the suite is worse than when you started, every round gets
reverted, and the stage ends with more red than it began with. Measured: a
build went 13 failures → 6 → 7 → 11 doing exactly this, with the fixer
choosing `test` and rewriting whole files every time.
"""


RUNTIME_SYSTEM = """\
The app compiles, but it breaks when it actually runs. You are fixing that, and
the files you may write have already been decided — they are listed for you,
with their current contents.

Write each of those files COMPLETE, one block per file, nothing else:

<write_file path="app/cart/page.jsx">
…the whole file…
</write_file>

  • Never a diff, never "…rest unchanged", never a code fence inside a block.
  • A write to any path that is not on the list is thrown away. If the real
    cause is somewhere else, write nothing and say so in one sentence.
  • Keep every export each file already has. Other files import them, and a
    repair that renames one turns a 500 into a build that does not compile.
  • Keep the file's existing role: a page that was a server component stays
    one, `'use client'` stays on line 1 where it already is.

WHAT THESE ERRORS USUALLY ARE, in the order they are worth checking:

  • "Only plain objects can be passed to Client Components" / "Functions
    cannot be passed directly to Client Components". A server component is
    handing a client component something that cannot cross the wire — almost
    always a lucide icon passed as a prop:

        // app/admin/page.jsx — SERVER, and this is the bug
        import { DollarSign } from 'lucide-react'
        <StatCard title="Revenue" value={total} icon={DollarSign} />

    The icon is a function. Props crossing the boundary must be plain data:
    strings, numbers, arrays, plain objects, null. Fix it in the CLIENT
    component by importing the icon there and selecting it by name:

        // components/StatCard.jsx — 'use client'
        import { DollarSign, Package, Users, AlertTriangle } from 'lucide-react'
        const ICONS = { DollarSign, Package, Users, AlertTriangle }
        export default function StatCard({ title, value, icon, color }) {
          const Icon = ICONS[icon] ?? Package
          return <div className={color}><Icon className="w-5 h-5" />…</div>
        }

        // the server page then passes a string
        <StatCard title="Revenue" value={total} icon="DollarSign" />

    Rendering the icon on the server and passing it as `children` works too —
    JSX elements cross the boundary fine, bare components do not. Never
    "solve" this by putting 'use client' on the page: that would drag the
    database query into the browser.

  • A Mongo document passed straight into a client component. `_id` is an
    ObjectId and `createdAt` is a Date — neither is a plain object. Everything
    read from a collection goes through `serialize` from '@/lib/mongodb'
    before it is handed down.

  • "X is not defined" from a page that compiles. An identifier rendered in
    JSX that the file never imported — nearly always one lucide icon missing
    from an import line that lists all the others. The fix is the import, not
    a rewrite of the page: read the top of the file, add the name, change
    nothing else.

  • A server component calling a hook, or a client component importing
    '@/lib/mongodb'. The boundary is the single most common 500 in this stack.
  • Reading a property of something that is undefined because a `find()`
    returned nothing, or `params`/`searchParams` was used without `await`.
  • A fetch to an API route that does not exist, or that exists with a
    different method than the one being called.
  • A missing `export const dynamic = 'force-dynamic'` on a page that reads
    the database, which serves stale HTML instead of throwing.

WHAT THESE ERRORS ARE NOT:

  • A route that redirects an unauthenticated visitor to /login is working
    correctly. Do not remove a login requirement to make a probe go green.
  • AgentForge wrote lib/mongodb.js, lib/auth.js, lib/auth-client.js and
    next.config.mjs, and they are correct. The bug is in the app code.

Do not weaken anything to silence an error: an empty catch, a component that
returns null, a removed await. A page that renders nothing passes a status
check and is worse than the crash it replaced.
"""


class BugFixerAgent:
    """
    One model call per failing test file. Composition over `ArchitectAgent`.

    Same shape as `AnalyzerAgent` and `FeaturesAgent`: it borrows `_stream` so
    the repair runs on the model the user picked, builds its own message list so
    `arch.convo` is never appended to, and gates every write behind an
    allowlist.
    """

    def __init__(self, arch, project_dir=None, *, callbacks=None,
                 session=None, runner=None, model=None):
        self.arch = arch
        self.project_dir = project_dir or arch.project_dir
        self.cb = callbacks or {}
        self.qa = session
        self.runner = runner

        self.model = model or None
        self.app_writes = set()
        self.verdicts = []

        self.refusals = {}

        self._lock = threading.Lock()

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn and callable(fn):
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):

        if self.cb and self.cb.get("on_log"):
            self._fire("on_log", lvl, txt)
            return
        log.info(txt)

    def _read(self, rel):
        if self.qa:
            return self.qa.read_source(rel)
        try:
            fp = self.arch._safe_path(rel)
            return fp.read_text(encoding="utf-8", errors="replace") if fp.is_file() else None
        except Exception:
            return None

    def editable(self, rel) -> bool:
        """
        Whether `rel` may be rewritten to satisfy a test.

        Deliberately narrow. Everything AgentForge generates is correct by
        construction and a "fix" there lands in the wrong file — the measured
        case being a client/server boundary error the model repaired by writing
        webpack fallbacks into `next.config.mjs`, which silenced the build error
        and left the 500 in place.
        """
        rel = (rel or "").strip().lstrip("./").replace("\\", "/")
        if not rel or rel in NEVER_CODE:
            return False
        if rel in getattr(self.arch, "NEXT_PROTECTED", frozenset()):
            return False
        if not rel.startswith(("app/", "components/", "lib/")):
            return False
        if rel.startswith("app/api/auth/"):
            return False
        return rel.endswith((".js", ".jsx"))

    @staticmethod
    def _threw_in(f, target: str) -> bool:
        """
        Did `target` throw, or did the test?

        Reads the stack top-down and stops at the first frame that is the
        project's own code — skipping the runner, the dependencies and node's
        internals. If that frame is the test, the test threw and this is not a
        code bug however the message reads; `Cannot read properties of
        undefined` from a test that destructured `container` wrongly looks
        identical to a component crash until you look at the frame. Measured on
        a real failure that would otherwise have been blamed on the component.
        """
        if not target:
            return False
        want = target.replace("\\", "/").lstrip("./")
        for line in (f.stack or "").splitlines():
            line = line.strip()
            if not line.startswith("at "):
                continue
            norm = line.replace("\\", "/")
            if "node_modules" in norm or "node:internal" in norm:
                continue
            if "/tests/" in norm:
                return False
            if want in norm:
                return True
        return False

    _PARSE_PATH_RE = re.compile(
        r"((?:[A-Za-z]:)?[A-Za-z0-9_./\\-]+\.(?:jsx?|tsx?))\s*:\s*\d+\s*:\s*\d+")

    def _unparseable_file(self, failures) -> str:
        """The project-relative path the transform error names, or ''."""
        root = str(self.project_dir).replace("\\", "/").rstrip("/")
        for f in failures:
            for blob in (getattr(f, "message", ""), getattr(f, "stack", "")):
                for hit in self._PARSE_PATH_RE.findall(blob or ""):
                    rel = hit.replace("\\", "/")
                    if rel.lower().startswith(root.lower()):
                        rel = rel[len(root):]
                    rel = rel.lstrip("/")
                    if rel.startswith("./"):
                        rel = rel[2:]

                    if rel and (self.project_dir / rel).is_file():
                        return rel
        return ""

    def prior(self, failures, *, build_ok=True, round_no=1):
        """
        `(verdict, reason, action)` when Python already knows, else
        `(None, "", "model")`.

        `action` is `"model"` (ask, but with the verdict fixed), or
        `"quarantine"` (set the test aside and spend nothing).
        """
        if not failures:
            return ("test", "there is nothing to repair", "quarantine")
        f = failures[0]
        kinds = {x.kind for x in failures}
        target = (f.target or "").strip()

        if "SYNTAX" in kinds:
            broken = self._unparseable_file(failures)
            if broken and broken != f.test_file:
                if self.editable(broken):
                    return ("code", f"{broken} does not parse — the test is "
                                    f"fine and that file is what has to be "
                                    f"fixed", "model")
                return ("test", f"{broken} does not parse and is not a file "
                                f"that may be edited", "report")
            return ("test", "the test file does not parse", "quarantine")

        if "CRASH" in kinds:
            if target and self.editable(target):
                return ("code", f"{target} returned an error rather than a "
                                f"page — that is not an assertion anyone can "
                                f"argue with", "model")
            return ("test", "the crash is not in a file that may be edited",
                    "report")

        if "IMPORT" in kinds and build_ok:
            return ("", "the build is green, so every module in the app "
                        "resolves — this import names something that does "
                        "not exist", "model")

        if not target:
            return ("test", "this failure is not attributable to any app file",
                    "model")

        if not self.editable(target):
            return ("test", f"{target} is generated by AgentForge and is not "
                            f"editable", "model")

        if not (self._read(target) or "").strip():
            return ("test", f"{target} is missing or empty", "model")

        if any(x.kind == "RUNTIME" and self._threw_in(x, target)
               for x in failures):
            return ("code", f"{target} threw while the test ran, rather than "
                            f"an assertion failing — the component is what "
                            f"broke", "model")

        if f.stale and round_no <= 1:
            return ("", f"{target} was rewritten after this test was "
                            f"written", "model")

        missing = self.missing_export(f.test_file, target)
        if missing:
            return ("", f"{target} does not export "
                            f"{', '.join(sorted(missing))}", "model")

        if not self.imports_target(f.test_file, target):
            avail = self.exports_of(target)

            methods = sorted(avail & HTTP_METHODS)
            names = ", ".join(methods or sorted(avail - {"dynamic", "revalidate",
                                                         "runtime", "fetchCache"})[:4])
            return ("", f"this test never imports anything from {target} — "
                            f"it has to `import {{ {names} }}` from it and pass "
                            f"the function to postJson/getJson, not a URL",
                    "model")

        return (None, "", "model")

    def _files_for(self, *rels) -> dict:
        out = {}
        for rel in rels:
            src = self._read(rel)
            if src is not None:
                out[rel] = src
        return out

    def exports_of(self, target) -> set:
        """The names `target` offers, for evidence the model can act on."""
        try:
            return effective_exports(target, self._files_for(target)) or set()
        except Exception:
            return set()

    def imports_target(self, test_file, target) -> bool:
        """Whether the test imports anything at all from the file it is about."""
        body = self._read(test_file)
        if not body or not target:
            return True
        try:
            files = self._files_for(test_file, target)
            if target not in files:

                return True
            for stmt in parse_imports(body):
                if resolve_local(test_file, stmt.spec, files) == target:
                    return True

            stem = re.sub(r"\.jsx?$", "", target)
            return bool(re.search(rf"from\s+['\"]@?/?{re.escape(stem)}(\.jsx?)?['\"]",
                                  body))
        except Exception as e:
            log.debug(f"imports_target {test_file}: {e}")
            return True

    def missing_export(self, test_file, target) -> set:
        """
        Names the test imports from its target that the target does not export.

        Wrong by `agents/exports.py` — the same parser that found six real
        broken imports in one generated project with zero false positives. A
        test cannot be right about a function that is not there.
        """
        body = self._read(test_file)
        if not body:
            return set()
        try:
            files = {}
            for rel in (test_file, target):
                src = self._read(rel)
                if src is not None:
                    files[rel] = src
            avail = None
            for stmt in parse_imports(body):
                if not stmt.names:
                    continue
                resolved = resolve_local(test_file, stmt.spec, files)
                if resolved != target:
                    continue
                if avail is None:

                    avail = effective_exports(target, files)
                    if avail is None:
                        return set()

                gap = {imported for imported, _local in stmt.names
                       if imported not in avail}
                if gap:
                    return gap
        except Exception as e:
            log.debug(f"missing_export {test_file}: {e}")
        return set()

    def fix(self, failures, *, build_ok=True, round_no=1,
            tier=0) -> FixVerdict:
        """
        Arbitrate and repair one test file's failures. One model call at most.

        `tier` is how hard to try, and it only goes up when repeating the
        current strategy has stopped paying. Every rung hands the model
        something the rung below did not have, because a retry that asks the
        same question with the same context is not a second attempt:

          0  the usual repair
          1  the reason its last write was REFUSED, plus more of the file's
             neighbourhood. The refusal reasons — "it introduces it.skip",
             "it drops 3 passing case(s)" — were already being computed and
             then dropped on the floor, so the model retried blind and
             reproduced the same rewrite. This is the cheapest new information
             in the system: no extra retrieval, no extra tokens spent looking.
          2  permission to fix the COMPONENT rather than the test. `prior`
             sends almost everything to "test", so a case that is red because
             the component genuinely lacks the role or label it should have
             gets the test rewritten to match the broken component, forever.
             That is the shape that never converges.
        """
        if not failures:
            return FixVerdict(test_file="", verdict="test",
                              evidence="there is nothing to repair")
        f0 = failures[0]
        test_file = f0.test_file
        target = (f0.target or "").strip()
        v = FixVerdict(test_file=test_file, target=target,
                       failing=[f.name for f in failures if f.name])

        forced, reason, action = self.prior(failures, build_ok=build_ok,
                                            round_no=round_no)
        if forced:
            v.forced = reason
        if action == "quarantine":
            v.verdict, v.evidence, v.quarantine = "test", reason, True
            self._log("WARN", f"   🚧 {test_file} — {reason}")
            with self._lock:
                self.verdicts.append(v)
            return v
        if action == "report":

            v.verdict, v.evidence = forced, reason
            self._log("WARN", f"   ⚠ {test_file} — {reason}")
            with self._lock:
                self.verdicts.append(v)
            return v

        test_body = self._read(test_file) or ""
        target_body = self._read(target) if target else ""
        if not test_body.strip():
            v.verdict, v.evidence = "test", "the test file is gone"
            with self._lock:
                self.verdicts.append(v)
            return v

        if tier >= 2 and target:
            reason = (reason + " — and two corrections of the test did not "
                      "make it pass, so the component is the thing left to "
                      "doubt").strip(" —")
        allowed = {test_file, target} - {""}
        convo = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": self._prompt(
                     failures, test_body, target_body, forced, reason,
                     refused=self.refusals.get(test_file, "") if tier else "",
                     tier=tier)}]

        raw = []
        state = {"verdict": "", "evidence": ""}

        def read_verdict():
            m = VERDICT_RE.search("".join(raw))
            if m:
                state["verdict"] = m.group(1).lower()
                state["evidence"] = (m.group(2) or "").strip()[:200]
            return state["verdict"]

        def on_end(path, content):
            key = (path or "").strip().lstrip("./").replace("\\", "/")

            said = read_verdict() or "test"
            if forced:
                said = forced
            want = {test_file} if said != "code" else ({target} if target else set())
            if key not in want or key not in allowed:
                v.rejected.append(key)
                self._log("WARN", f"   ⛔ {key} is not writable under a "
                                  f"'{said}' verdict — skipped")
                return
            self._commit(key, content, said, v)

        parser = FileStreamParser(
            on_text=lambda t: raw.append(t),
            on_file_start=lambda p: self._fire("on_file_start", p),
            on_file_token=lambda t: None,
            on_file_end=on_end)
        try:
            self.arch._stream(convo, parser.feed, temperature=TEMPERATURE,
                              model=self.model, timeout=CALL_BUDGET)
        except Exception as e:
            self._log("WARN", f"   ⚠ bug fixer failed on {test_file}: {e}")
        parser.close()

        said = read_verdict()
        v.verdict = forced or said or "test"
        v.evidence = state["evidence"] or reason
        if said == VERDICT_HARNESS:

            v.quarantine = True
            self._log("WARN", f"   🧰 {test_file} — the fixer says the fault is "
                              f"in AgentForge's own test harness, not this app:")
            self._log("WARN", f"      {v.evidence or 'no detail given'}")
            self._log("WARN", f"      Nothing was rewritten. This one needs a "
                              f"change to AgentForge itself.")
        elif said == "unclear" and not v.written:
            v.quarantine = True
            self._log("WARN", f"   🚧 {test_file} — the fixer could not tell: "
                              f"{v.evidence or 'no evidence given'}")
        elif not said:

            self._log("WARN", f"   ⚠ no verdict from the fixer on {test_file} "
                              f"— treated as a test problem")

        with self._lock:

            self.verdicts.append(v)
        return v

    def fix_runtime(self, errors: str, spec, *, server_log: str = "",
                    round_no: int = 1) -> list:
        """
        Repair what broke when the app ran, against a plan of which files change.

        Separate from `fix()` on purpose. That one arbitrates between a test and
        the code it tests, and its whole prompt is that question — a route
        returning 500 has no test to be wrong, so the verdict line has nothing
        to decide and the safe default ("blame the test") is not even available.
        What is shared is everything that makes a repair safe: the write
        allowlist, `editable()`, and the scope guard.

        The allowlist here is the planner's file list, intersected with what is
        editable at all. Returns the paths actually written.
        """

        planned = [f for f in getattr(spec, "files", [])
                   if self.editable(f["path"])]
        refused = [f["path"] for f in getattr(spec, "files", [])
                   if not self.editable(f["path"])]
        for path in refused:
            self._log("WARN", f"   ⛔ {path} is not editable — dropped from "
                              f"the repair plan")
        if not planned:
            return []

        allowed = {f["path"] for f in planned}
        bodies = {f["path"]: (self._read(f["path"]) or "") for f in planned}
        written = []

        parts = [f"## What went wrong\n```\n{errors[:5000]}\n```"]
        if server_log.strip():
            parts.append("## The dev server's own output — the stack frames "
                         "name the file and line\n"
                         f"```\n{server_log[:3500]}\n```")
        if getattr(spec, "summary", ""):
            parts.append(f"## What the plan concluded\n{spec.summary}")

        ref = {p: b for p, b in getattr(spec, "context", {}).items()
               if p not in allowed and b}
        if ref:
            parts.append("## Read these — you may NOT write them\n"
                         "They are how this project already does it. Use the "
                         "exports, hooks, context and storage keys they define. "
                         "Do not reimplement what is here and do not invent a "
                         "second way to do the same thing.")
            for p, b in list(ref.items())[:6]:
                parts.append(f"### {p} (reference only)\n```js\n{b[:6000]}\n```")

        parts.append("## The files you may write, and why each one is on the list")
        for f in planned:
            body = bodies[f["path"]]
            why = f.get("why") or "named by the repair plan"
            if body:
                parts.append(f"### {f['path']} — {why}\n```js\n{body[:9000]}\n```")
            else:
                parts.append(f"### {f['path']} — {why}\n"
                             f"(this file does not exist yet; create it)")
        parts.append(f"Write {'that file' if len(planned) == 1 else 'those files'}"
                     f", complete, one <write_file> block each. Nothing else.")

        convo = [{"role": "system", "content": RUNTIME_SYSTEM},
                 {"role": "user", "content": "\n\n".join(parts)}]

        def on_end(path, content):
            key = (path or "").strip().lstrip("./").replace("\\", "/")

            fresh = (key not in allowed and self.editable(key)
                     and not (self.project_dir / key).exists())
            if key not in allowed and not fresh:
                self._log("WARN", f"   ⛔ {key} is not on the repair plan "
                                  f"— skipped")
                return
            if fresh:
                self._log("INFO", f"   ➕ {key} — new file the repair needs")
            if self._commit_runtime(key, content, bodies.get(key, "")):
                written.append(key)

        parser = FileStreamParser(
            on_text=lambda t: None,
            on_file_start=lambda p: self._fire("on_file_start", p),
            on_file_token=lambda t: None,
            on_file_end=on_end)
        try:
            self.arch._stream(convo, parser.feed, temperature=TEMPERATURE,
                              model=self.model, timeout=CALL_BUDGET)
        except Exception as e:
            self._log("WARN", f"   ⚠ runtime repair failed: {e}")
        parser.close()

        if not written:
            self._log("WARN", f"   ⚠ Round {round_no} changed nothing")
            return written

        self.arch.repair_missing_imports()
        self.arch.sync_dependencies()
        return written

    def _commit_runtime(self, key, content, old) -> bool:
        """
        A runtime repair write.

        The file-count budget and the changed-line ceiling are both gone. A
        page that 500s is broken by observation, not by a test's opinion, and a
        repair that is honest about it often rewrites most of the file or
        touches a seventh one. Refusing on size or on a tally left the app
        broken and called it caution.

        What is still refused is what a rewrite never justifies: a truncated
        file, and an export other files import going missing. Those are not
        opinions about how much should change — they are the two ways a write
        breaks something that was working.
        """
        if old:
            bad = guard_scope(old, content, adding=True, retexting=True)
            if bad:
                self._log("WARN", f"   ⛔ {key}: {bad}")
                return False
        if not self.arch.write_file(key, content):
            return False
        self.app_writes.add(key)
        self._log("INFO", f"   🔧 {key} — rewritten")
        return True

    def _refuse(self, v, key, why: str) -> None:
        """
        Throw a write away, and REMEMBER WHY.

        The reason used to be logged and dropped, so the next attempt was
        handed the same file, the same failure and the same prompt, and wrote
        the same thing again. Two of those in a row is what the stage read as
        "no progress" before it gave up — but nothing had gone wrong with the
        model's reasoning, it simply was never told what had been rejected.
        """
        v.rejected.append(key)
        self._log("WARN", f"   ⛔ {key}: {why}")
        with self._lock:
            self.refusals[v.test_file or key] = why

    def _commit(self, key, content, said, v):
        """Write, after the guards that the verdict alone cannot enforce."""
        old = self._read(key) or ""

        if said == "code":
            if not self.editable(key):
                self._refuse(v, key, "that file is not editable")
                return

            bad = guard_scope(old, content, adding=True, retexting=True)
            if bad:
                self._refuse(v, key, bad)
                return
            if not self.arch.write_file(key, content):
                return
            self.app_writes.add(key)
            v.written = key
            self._log("INFO", f"   🔧 {key} — {v.evidence or 'fixed'}")
            return

        weak = self._weakened(old, content)
        if weak:
            self._refuse(v, key, f"{weak} — the test is not repaired, it is "
                                 f"disabled")
            return

        lost = self._lost_cases(old, content, v.failing)
        if lost:
            self._refuse(v, key, lost)
            return
        if self.qa:
            meta = self.qa.manifest.get(key) or {}
            ok = self.qa.write_test_file(key, content,
                                         target=meta.get("target", v.target),
                                         phase=meta.get("phase", 0),
                                         tier=meta.get("tier", 0))
            if ok:

                if key in self.qa.manifest:
                    self.qa.manifest[key]["stale"] = False
                v.written = key
                self._log("INFO", f"   🧪 {key} — {v.evidence or 'test corrected'}")

    CASE_RE = re.compile(
        r"""\b(?:it|test)\s*(?:\.\s*\w+)?\s*\(\s*(['"`])(.+?)\1""", re.S)

    @classmethod
    def _lost_cases(cls, old, new, failing) -> str:
        """Passing cases this rewrite dropped, or `""`."""
        before = {m.group(2).strip() for m in cls.CASE_RE.finditer(old or "")}
        after = {m.group(2).strip() for m in cls.CASE_RE.finditer(new or "")}

        lost = (before - after) - {f.strip() for f in (failing or [])}
        if not lost:
            return ""
        shown = ", ".join(f'"{n[:44]}"' for n in sorted(lost)[:3])
        more = f" (+{len(lost) - 3} more)" if len(lost) > 3 else ""
        return (f"it drops {len(lost)} passing case(s) that nothing was wrong "
                f"with — {shown}{more}")

    @staticmethod
    def _weakened(old, new) -> str:
        """Why this rewrite makes the test worthless, or `""`."""
        if not new or not new.strip():
            return "the rewrite is empty"
        m = WEAKENED_RE.search(new)
        if m and not WEAKENED_RE.search(old or ""):
            return f"it introduces {m.group(0).strip()}"
        before = len(re.findall(r"\bexpect\s*\(", old or ""))
        after = len(re.findall(r"\bexpect\s*\(", new))
        if before and after * 2 < before:
            return f"the assertions went from {before} to {after}"
        if before and after == 0:
            return "every assertion was removed"
        return ""

    NEIGHBOUR_MAX = 5
    NEIGHBOUR_CHARS = 4000

    HARNESS_GLOBS = ("tests/helpers/*.js", "tests/setup.js", "vitest.config.js")

    def _harness_bodies(self) -> dict:
        """The harness files a test runs through, {path: body}."""
        out = {}
        for pat in self.HARNESS_GLOBS:
            try:
                for fp in sorted(self.project_dir.glob(pat)):
                    if not fp.is_file():
                        continue
                    rel = str(fp.relative_to(self.project_dir)).replace("\\", "/")
                    body = self._read(rel)
                    if body:
                        out[rel] = body
            except Exception as e:
                log.debug(f"harness bodies {pat}: {e}")
        return out

    def _neighbours(self, seen: dict) -> dict:
        """
        The local modules the test and its target import, {path: body}.

        The fixer used to see exactly two files: the failing test and the file
        it tests. That is enough to judge which of the two is wrong and not
        enough to rewrite either, because a component's behaviour lives partly
        in what it imports — the context that supplies its data, the helper
        that formats its dates, the constants it switches on. Asked to fix it
        blind, the model reconstructs those from the names alone, confidently
        and wrongly, and the rewrite breaks tests that were passing.

        Measured on a build: the unit stage went 13 failing → 6 → 7 → 11, each
        round undoing more than it fixed, until the no-progress guard stopped
        it. The same blindness produced a repair that polled
        `localStorage['cart']` in a project that stores the cart under
        `greenthumb_cart`, and one that imported CartProvider from a path that
        has never existed.
        """
        out = {}
        for rel, body in seen.items():
            if not rel or not body:
                continue
            for stmt in parse_imports(body):
                target = resolve_local(rel, stmt.spec, self.arch.files)
                if not target or target in seen or target in out:
                    continue
                if target.endswith(".css"):
                    continue
                out[target] = self.arch.files[target]
                if len(out) >= self.NEIGHBOUR_MAX:
                    return out
        return out

    def _prompt(self, failures, test_body, target_body, forced, reason,
                refused="", tier=0):
        f0 = failures[0]
        cases = []
        for f in failures[:6]:
            frames = [ln for ln in (f.stack or "").splitlines()
                      if ln.strip().startswith("at ")][:4]
            cases.append(f"  • {f.name}\n    {f.message}\n"
                         + ("\n".join(f"      {ln.strip()}" for ln in frames)))

        parts = [f"## The failing test — {f0.test_file}\n```js\n{test_body[:9000]}\n```"]
        if target_body:
            parts.append(f"## The file it is testing — {f0.target}\n"
                         f"```js\n{target_body[:9000]}\n```")
        else:
            parts.append("## The file it is testing\nThere is none — this "
                         "failure could not be attributed to any app file, so "
                         "only the test can be wrong.")

        ref = self._neighbours({f0.test_file: test_body, f0.target: target_body})
        if ref:
            parts.append("## What those files import — READ ONLY, do not write "
                         "them\nThis is how the project already does it. Use "
                         "these exports, hooks, props, and storage keys exactly "
                         "as they are written here. Do not invent a second way "
                         "to do something this already does.")
            for p, b in ref.items():
                parts.append(f"### {p} (reference)\n"
                             f"```js\n{b[:self.NEIGHBOUR_CHARS]}\n```")

        parts.append(f"## What Vitest reported ({len(failures)} case(s) failing)\n"
                     + "\n".join(cases))

        if forced:

            parts.append(f"## The verdict is already decided: {forced}\n"
                         f"{reason.capitalize()}. Do not argue with this — write "
                         f"the corrected {'test' if forced == 'test' else 'code'} "
                         f"file. Still emit the VERDICT line, with the evidence "
                         f"you would have given.")
        elif reason:

            parts.append(f"## What AgentForge noticed\n{reason.capitalize()}.\n\n"
                         f"That is an observation, not the answer. Weigh it "
                         f"against the two files and decide for yourself.")
        if f0.stale:
            parts.append("## Note\nThis test was written before its target was "
                         "last rewritten, so it may be describing code that no "
                         "longer exists.")

        if refused:
            parts.append(
                f"## Your last attempt at this file was THROWN AWAY\n"
                f"{refused.capitalize()}.\n\n"
                f"That write never reached disk, which is why you are seeing "
                f"the same failure again — it is not that your fix did not "
                f"work, it is that it was refused before it ran. Write "
                f"something that does not have that problem. If the only fix "
                f"you can see is the one that was refused, then the premise is "
                f"wrong: say so in the VERDICT line rather than writing it "
                f"again.")
        if tier >= 2 and target_body:
            parts.append(
                "## This is the third attempt on this file\n"
                "Two corrections of the TEST have already failed to make it "
                "pass. That is evidence about the component, not just the "
                "test: a case stays red like this when the component really "
                "is missing the role, label or behaviour the test looks for. "
                "You may write EITHER file now. Choose the one the evidence "
                "actually points at, and say which in the VERDICT line.")

        if tier >= 3:
            harness = self._harness_bodies()
            parts.append(
                "## Neither file may be the problem\n"
                "Rewriting the test failed. Rewriting the component failed. "
                "When both of those are true the remaining possibility is that "
                "the failure is not in this app at all — it is in the harness "
                "the test runs THROUGH, which is written by AgentForge and shown "
                "below.\n\n"
                "Real examples, both of which cost a whole stage:\n"
                "  • the request helper sent a JSON body to a handler that "
                "reads `request.formData()`, so the handler threw, its own "
                "`try/catch` returned 500, and the case failed as "
                "\"expected 500 to be 400\" — the route was correct\n"
                "  • a mock exported a different name than the module it "
                "stands in for, so every call came back undefined\n\n"
                "If that is what is happening here, answer "
                "`VERDICT :: harness :: <which file and what is wrong with "
                "it>` and write NOTHING. You cannot edit these files and you "
                "are not being asked to — naming it is the fix, and it is more "
                "useful than another rewrite of a file that is already right. "
                "If the harness is genuinely fine, ignore this section and "
                "answer as before.")
            for p, b in harness.items():
                parts.append(f"### {p} (AgentForge's, read only)\n"
                             f"```js\n{b[:4000]}\n```")

        parts.append("Emit the VERDICT line first, then exactly one "
                     "<write_file> block.")
        return "\n\n".join(parts)

    def summary(self) -> str:
        if not self.verdicts:
            return "no repairs attempted"
        code = sum(1 for v in self.verdicts if v.touched_code)
        tests = sum(1 for v in self.verdicts if v.written and not v.touched_code)
        held = sum(1 for v in self.verdicts if v.quarantine)
        return (f"{tests} test(s) corrected, {code} code fix(es), "
                f"{held} set aside")
