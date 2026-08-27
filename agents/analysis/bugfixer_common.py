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
  `agents/core/exports_parse.py + agents/core/exports_checks.py` — the same check that found six real bugs in one project.
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

from agents.planning.architect import FileStreamParser
from agents.core.workspace import WorkspaceTools, TOOL_HELP
from agents.core.exports_parse import effective_exports, parse_imports, resolve_local
from agents.features.picker import guard_scope

log = logging.getLogger("agent.bugfixer")

TEMPERATURE = 0.15


# The whole-call budget for one repair.
CALL_BUDGET = 600


MAX_APP_FILES = 4


CODE_CHANGE_FRAC = 0.50
CODE_CHANGE_MIN = 40


RUNTIME_CHANGE_FRAC = 0.95
RUNTIME_CHANGE_MIN = 400
RUNTIME_MAX_FILES = None

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
The app compiles, but it breaks when it actually runs. You are fixing that from
runtime evidence. An initial impact plan is listed for you with current source,
but it is not a hard allowlist: inspect dependencies and expand to any other
safe project source file when the proven root cause requires it.

Write every changed file COMPLETE, one block per file:

<write_file path="app/cart/page.jsx">
…the whole file…
</write_file>

  • Never a diff, never "…rest unchanged", never a code fence inside a block.
  • If the real cause is in another source file, inspect it and write that file
    too. Do not make unrelated edits merely because more files are available.
  • Keep every export each file already has. Other files import them, and a
    repair that renames one turns a 500 into a build that does not compile.
  • Keep the file's existing role: a page that was a server component stays
    one, `'use client'` stays on line 1 where it already is.
  • CURRENT PROJECT CONVENTIONS WIN OVER FRAMEWORK MEMORY. Before creating or
    rewriting an API route, inspect `package.json` plus at least one working
    sibling route that uses the same auth/database layer. Never import
    `next-auth`, `mongoose`, `connectDB`, `getServerSession`, or any other helper
    just because it is familiar when this project uses a different stack. If a
    package is not already in package.json, do not introduce it unless the
    evidence-backed plan explicitly required that package.
  • Match the existing data contract. If sibling cart routes store `user: id`
    and product ObjectIds, a new GET route must read that shape and return the
    shape the current client actually consumes; do not invent `userId`, raw
    product ids, or another schema without source evidence.

FIRST RULE — TRUST THE RUNTIME LOCATION BEFORE GUESSING:

  • If the incident contains `RUNTIME SOURCE LOCATIONS` or a browser/Next stack
    frame naming a real project `file:line:column`, read that exact line and its
    nearby code first. The E2E selector/text symptom is downstream evidence.
    Do not rewrite a page chosen only because its copy resembles the error.
  • Preserve the named file's surrounding behavior and make the smallest change
    that removes the exception. If the exact frame is merely a caller and an
    API/auth failure is the deeper proven cause, follow that stronger evidence.

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
  • Do not assume auth/database helper code is correct because AgentForge wrote
    its first draft. Follow the runtime frame, request/response contract and
    dependency chain. Edit those source helpers only when that evidence leads
    there.

Do not weaken anything to silence an error: an empty catch, a component that
returns null, a removed await. A page that renders nothing passes a status
check and is worse than the crash it replaced.
"""

__all__ = [name for name in globals() if not name.startswith("__")]
