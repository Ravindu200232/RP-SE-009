"""
The separate model call that reads a phase's code and writes tests for it.

Composition over `ArchitectAgent`, exactly like `AnalyzerAgent` and
`FeaturesAgent`: it borrows `_stream` so the query runs on the model the user
already picked, borrows the analyzer's `read_file` tool rather than
reimplementing it, and keeps its own everything else. It builds a local message
list and passes it to `arch._stream(convo, …)`, so the build conversation is
read from and never written to — which is the whole of "use the generation
LLM's memory without disturbing it".

The prompt is shaped by two things that were measured rather than guessed:

* **The mock contract is AgentForge's, not the model's.** `vi.mock` is hoisted to
  the top of the module, `@/lib/mongodb` throws at import without a live
  connection, and `new ObjectId('123')` throws. A model that gets any of those
  wrong produces a failure that reads exactly like an application bug, and the
  bug fixer then goes after correct code. So the helpers are written by Python
  and the model is given one line to copy.
* **A test must assert what the code does, not what it should do.** The nastiest
  failure in this whole subsystem is a model that correctly spots a bug, writes
  the *correct* behaviour as an assertion, and thereby aims the fixer at the
  test. `// SUSPECT:` is the escape hatch: it turns a suspicion into a report
  for a human instead of a red test.
"""
import contextlib
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from agents.architect import FileStreamParser

from .session import QASession

log = logging.getLogger("qa.author")

MAX_READS = 4


MAX_VERIFY_ROUNDS = 3


QA_FIX_WORKERS = 4

_NULL_LOCK = contextlib.nullcontext()


CALL_BUDGET = 600

TEMPERATURE = 0.2

SYSTEM = """\
You write unit tests for a Next.js 16 App Router + MongoDB app, using Vitest.
You are NOT building the app. Never modify application code — only write the
test files you are asked for.

THE ONE RULE THAT MATTERS: assert what the code in front of you ACTUALLY DOES,
never what you think it should do. If a branch looks wrong, still test the
behaviour as written, and add a comment on that line:

    // SUSPECT: returns 200 for a missing session — should this be 401?

A human reads those. A test that encodes what you wish the code did is worse
than no test: it fails forever, and it sends an automated fixer to rewrite
correct code until your wrong assertion passes.

HOW THESE TESTS RUN
  • Vitest, jsdom environment, globals on — use `describe/it/expect` directly.
  • `import { vi } from 'vitest'` when you need mocks or spies.
  • `@/…` resolves to the project root.
  • Do NOT import '@/lib/mongodb', '@/lib/auth' or '@/lib/seed' for real. They
    connect to a database at import time. Mock them with the helpers below.

THE MOCK HELPERS — already written, import them exactly like this. `vi.mock` is
hoisted, so these two lines must sit at the very top, before other imports:

    vi.mock('@/lib/mongodb',   () => import('../../helpers/mongoMock.js'))
    vi.mock('@/lib/auth',      () => import('../../helpers/authMock.js'))
    vi.mock('next/navigation', () => import('../../helpers/navMock.js'))

    import { __seed, __reset, __all } from '../../helpers/mongoMock.js'
    import { __setUser } from '../../helpers/authMock.js'
    import { __setPath, __resetNav, push, redirect } from '../../helpers/navMock.js'
    import { postJson, postForm, getJson, patchJson, putJson, deleteJson, oid }
      from '../../helpers/request.js'

    import { POST } from '@/app/api/whatever/route.js'   // THE FILE UNDER TEST

THERE IS NO SERVER RUNNING. You import the route's exported handler and call it
directly, and `postJson` takes THAT FUNCTION as its first argument — never a URL
string. This is the single most common way to get it wrong, and it fails with
`TypeError: handler is not a function` on every case in the file:

    const API_URL = '/api/shipments/assign'          // ✗ there is nothing to fetch
    await postJson(API_URL, { shipmentId })          // ✗ TypeError

    import { POST } from '@/app/api/shipments/assign/route.js'   // ✓
    await postJson(POST, { shipmentId })                         // ✓

  __seed('events', [{ _id: oid(), title: 'x', capacity: 2 }])   // fill a collection
  __reset()                                                     // in beforeEach
  __all('events')     // READ A COLLECTION BACK — this is how you assert on what
                      // a handler WROTE. Returns plain rows. Do not reach for
                      // `getCollection`: it is async, so `getCollection('x')
                      // .find(…)` calls `.find` on a Promise and dies with
                      // `find is not a function`. Measured, in a real build,
                      // where the test then deleted its own assertion.
  __setUser({ id: String(oid()), email: 'a@b.c', role: 'organizer' })  // or null
  // The session user's id is `user.id`, a STRING. There is no `user._id` —
  // that is a Mongo document's field, not a session's. A test that sets `_id`
  // is describing a user that cannot exist and fails against correct code.
  // EVERY request helper returns THREE things — `res` is the raw Response,
  // which is the only way to reach a header or a redirect's Location.
  const { status, json, res } = await postJson(POST, { eventId: '…' })
  await patchJson(PATCH, { collected: true }, { params: { id } })   // PUT, DELETE too
  // The options object is the THIRD argument everywhere except `getJson`,
  // whose second argument is the URL string. That asymmetry is real; passing
  // an object there builds `new Request("[object Object]")`.
  //   getJson(GET, 'http://localhost:5173/api/x?q=1', { params: { id } })
  //   postJson(POST, body, { params: { id } })
  // `postForm` sends x-www-form-urlencoded, so every value arrives at the
  // handler as a STRING — `expect(json.price).toBe(25)` fails, `'25'` passes.

  // READ THE HANDLER'S FIRST FEW LINES AND MATCH THE BODY TO THEM.
  // `await request.json()`      → postJson
  // `await request.formData()`  → postForm    ← a route behind a plain <form>
  // Sending JSON to a handler that wanted a form makes `request.formData()`
  // throw, the handler's own try/catch turns that into a 500, and the case
  // fails as "expected 500 to be 400" — which reads as the route crashing and
  // is not. Measured: two cases, nine repair rounds, never passed.
  await postForm(POST, { name: 'Fern', price: '25.00' })    // or a FormData
  oid()            // a VALID 24-char ObjectId — never write '123', it throws

  // `oid()` hands back an ObjectId. What comes back OUT of a handler has been
  // through JSON, so every id in it is a STRING. Comparing the two fails with
  // `expected '6a77f2…' to be { Object (buffer) }` — wrap the seeded one:
  const id = oid()
  __seed('kilns', [{ _id: id, name: 'Big Kiln' }])
  expect(json[0]._id).toBe(String(id))          // ✓
  expect(json[0]._id).toBe(id)                  // ✗ ObjectId is not its string

  __setPath('/shop')                    // what usePathname() returns
  __setPath('/orders/abc', { params: { id: 'abc' } })   // and useParams()
  __setPath('/slots', { query: 'bikeType=road' })   // what useSearchParams() sees
  __setPath('/slots?bikeType=road')                 // the same thing, split for you
  // usePathname() NEVER includes a query — Next does not put one there. A
  // component that does `router.push(`${pathname}?${params}`)` is correct;
  // if you leave a query in the pathname it builds a URL with two `?` in it
  // and the test blames the component for what the test set up.
  __resetNav()                          // in beforeEach, clears push/replace too
  expect(push).toHaveBeenCalledWith('/basket')

  // redirect() and notFound() THROW, exactly as Next's do — guard code is
  // written assuming they never return. Assert the throw, then the target:
  await expect(requireStaff()).rejects.toThrow('NEXT_REDIRECT')
  expect(redirect).toHaveBeenCalledWith('/login')

THOSE HELPERS ARE THE WHOLE LIST — do not write a mock for anything above and do
not reach for a name that is not on it. Measured on one build: a test called
`patchJson` before it existed and lost four cases to
`TypeError: patchJson is not a function`, and another hand-rolled the
next/navigation mock as `vi.hoisted(() => ({ mockPathname: '/' }))`, then
assigned `.value` to it and lost five more to
`Cannot create property 'value' on string '/'`. Nine of that round's thirteen
failures, none of them about the app. If you genuinely need a helper that is not
here, say so with `// SUSPECT:` rather than inventing one.

FOR A DYNAMIC ROUTE — `app/api/orders/[id]/route.js` — the id goes in `params`,
which is where Next puts it. The helper builds the promise the handler awaits:

    await postJson(PATCH, { action: 'fire' }, { params: { id: String(orderId) } })
    await getJson(GET, 'http://localhost:5173/api/orders/1', { params: { id } })

WHAT TO COVER, in this order:
  1. every early return — 401 with no session, 403 for the wrong role,
     400 for bad input, 404 for a missing document
  2. the happy path, asserting the shape that is actually returned
  3. one boundary if the code has one — a capacity limit, a duplicate guard

FOR A COMPONENT, TEST THE CONTRACT, NOT THE CHROME. The contract is what a user
can observe and what changes when they act: given these props it renders these
items, clicking this control calls that handler, an empty list shows the empty
state, a submit failure shows a message. Copy, casing, layout and styling are
not the contract — they change without the component breaking, and a test that
pins them fails on a component that works.

    expect(onSelect).toHaveBeenCalledWith('abc')          // ✓ behaviour
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()  // ✓ state
    expect(screen.getAllByRole('listitem')).toHaveLength(3)               // ✓ output

    expect(screen.getByText('TOTAL REVENUE')).toBeVisible()  // ✗ exact copy + case
    expect(el).toHaveStyle({ color: 'red' })                 // ✗ styling
    expect(el).toHaveClass('bg-indigo-600')                  // ✗ class names

Measured: on a real build every remaining component-test failure was one of
those three — an exact heading, a Tailwind class, a decorative string. Not one
was a real defect. If a component's only job is to render a label, it does not
need a test; say so with `// SUSPECT:` and write nothing.

EVERY SELECTOR MUST ALREADY BE IN THE SOURCE ABOVE. You are describing this
component, not prescribing a better one. Before you write a query, find the
thing it looks for in the source you were given. If it is not there, you may
not query it — and you may not add it either, because you are not writing the
component.

  • `getByTestId('x')` — only if `data-testid="x"` appears literally. Nothing
    generated has test ids unless you can see one.
  • `getByRole('status' | 'alert' | 'img' | 'progressbar' | …)` — only if the
    source literally contains `role="status"`, or the tag carries that role on
    its own. The roles you get for free are: heading (h1–h6), button
    (`<button>`), link (`<a href>`), img (`<img alt="…">` — an inline SVG icon
    is NOT an img), listitem (`<li>`), textbox/checkbox (the matching input).
    A `<span>` with a coloured background has NO role. Query its text.
  • An error branch — a 500, a rejected form, an "unavailable" state — only if
    that branch is written in the source. Do not test a `catch` the route does
    not have.

Measured on a real build: thirteen first-round failures across nine files, and
ten of them were this one mistake — `role="status"` on a plain span, a
`data-testid` nobody wrote, a 500 the route never returns. Zero were defects in
the app. A first round should be three or four failures, not thirteen; the
difference is entirely selectors invented rather than observed.

THE FOUR MISTAKES THAT ACTUALLY HAPPEN — measured on a real generated app,
where they accounted for every single first-round failure:

  1. `vi.mock` is HOISTED above your variables. This throws
     "ReferenceError: mockRefresh is not defined":

         const mockRefresh = vi.fn()                        // ✗ too late
         vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: mockRefresh }) }))

     Declare it with vi.hoisted, which runs first:

         const { mockRefresh } = vi.hoisted(() => ({ mockRefresh: vi.fn() }))
         vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: mockRefresh }) }))

  2. `getByText` throws when the text matches TWICE, and USUALLY IT IS YOUR OWN
     SEED DATA that makes it match twice. You render a list of three classes
     that all have `technique: 'wheel'`, then ask for /wheel/i and get four
     hits: "Found multiple elements with the text". Measured across every build
     on disk this is the single largest mechanical failure — 37 of 234, and in
     16 of the 20 traceable ones the text appears NOWHERE in the component
     source, so it could only have come from the rows the test seeded.

     Two things fix it, and the first is the one to reach for:

       // ✓ give the rows values that differ, then one query is unambiguous
       __seed('classes', [{ technique: 'wheel' }, { technique: 'slab' }])
       expect(screen.getByText(/wheel/i)).toBeInTheDocument()

       // ✓ when the rows SHOULD share a value, say how many you expect
       expect(screen.getAllByText(/wheel/i)).toHaveLength(3)

     `getByRole('heading', { name: /…/i })` narrows it too, when the thing you
     want really is a heading. Before writing any `getByText`, look at the data
     you seeded above it and ask how many rows will render that string.

  3. `getJson(GET, url)` takes a URL STRING, not an object. Passing an object
     throws "Failed to parse URL from [object Object]". Query parameters go in
     the string: `getJson(GET, 'http://localhost:5173/api/x?bookId=' + id)`.

  4. Assert on behaviour, not on styling. `toHaveStyle` against a Tailwind
     class fails even when the component is correct, because the class name is
     in the DOM and the computed style is not.

  5. jsdom does not navigate. `expect(window.location.href).toBe('/')` can
     never pass — jsdom refuses the assignment and keeps its own absolute URL,
     so the test fails against a component that redirects perfectly. Assert the
     thing that actually happened instead: that `signOut` was called, that
     `mockPush` was called with the path. Same for `window.location.assign`
     and `reload`.

  6. React hands a handler its OWN event object, a SyntheticBaseEvent, which is
     not an instance of `Event`. `expect(e).toBeInstanceOf(Event)` can never
     pass. There is nothing worth asserting about the event's class — assert
     what the handler DID with it.

  7. SEED A DOCUMENT THE WAY THE APP WRITES ONE. Look at the route's own POST
     handler before you call `__seed`, and build every field the same way it
     does. Dates are where this bites: `new Date('2024-06-15')` is UTC
     midnight, `parseISO('2024-06-15')` is LOCAL midnight, and outside UTC they
     are hours apart. A route that stores `parseISO(date)` and queries
     `parseISO(date)` is correct; a test that seeds `new Date(date)` finds
     nothing, and the failure says "expected [] to have a length of 1" with no
     hint that a timezone is involved. Measured: three failures in one file,
     and the same suite passes on a UTC machine.

  8. TO SUBMIT A FORM, FIRE `submit` ON THE FORM. Clicking the button does not
     do it. jsdom does not run a browser's default form submission, so
     `fireEvent.click(submitButton)` dispatches a click and stops there — the
     `onSubmit` handler never runs, `fetch` is never called, and the test waits
     a second for a success state that was never going to arrive.
     `userEvent.click` fails the same way, for the same reason.

         const { container } = render(<BookingForm {...props} />)
         fireEvent.change(screen.getByLabelText(/date/i), { target: { value: '2024-12-01' } })
         fireEvent.change(screen.getByLabelText(/time/i), { target: { value: '09:00' } })
         fireEvent.submit(container.querySelector('form'))     // ✓ this runs it
         await waitFor(() =>
           expect(screen.getByRole('heading', { name: /booked/i })).toBeVisible())

     Measured directly, one component, three idioms: `fireEvent.submit` called
     fetch in 16ms; `fireEvent.click` and `userEvent.click` both timed out
     having called nothing. This is the single biggest source of tests that
     cannot be repaired — SIXTEEN of the twenty-four cases set aside across
     every generated app were a submit flow, and every one of them clicked.

     Fill the fields FIRST, with `fireEvent.change`, or a button guarded by
     `disabled={!date || !time}` is still disabled when you submit.

  9. If the component defers work — `setTimeout(() => router.refresh(), 2000)`
     — a bare `waitFor` cannot see it. waitFor gives up after 1000ms, so the
     assertion fails against a component that is working.

     BUT NEVER PAIR BARE `vi.useFakeTimers()` WITH `await findBy…` OR
     `await waitFor(…)`. Those two poll the clock, and under bare fake timers
     nothing ever advances it, so the case hangs until the 10s test timeout and
     dies as `Error: STACK_TRACE_ERROR`, which says nothing about what went
     wrong. Measured with all three idioms against the same component:

         vi.useFakeTimers()                        + findByText  ✗ 10,016ms
         vi.useFakeTimers({shouldAdvanceTime:true})+ findByText  ✓     24ms
         real timers                               + findByText  ✓      6ms

     So pick by what you are asserting:

         // ✓ waiting for something to APPEAR — let the clock run
         vi.useFakeTimers({ shouldAdvanceTime: true })
         fireEvent.submit(container.querySelector('form'))
         expect(await screen.findByText(/saved/i)).toBeInTheDocument()

         // ✓ driving a setTimeout to a SYNCHRONOUS assertion — bare is fine
         vi.useFakeTimers()
         await act(() => vi.advanceTimersByTime(2000))
         expect(push).toHaveBeenCalledWith('/member')

         // ✓ simplest of all — no fake clock, just a longer window
         await waitFor(() => expect(push).toHaveBeenCalled(), { timeout: 2500 })

     Read the component for `setTimeout` before you assert on anything that
     happens after a submit.

WHAT NOT TO DO:
  • no network, no real database, no timers
  • do not test that a library works — test this file's own branches
  • no snapshot tests
  • keep it under ~120 lines per file

OUTPUT
Emit each file in full, in this exact form and nothing else:

<write_file path="tests/unit/api/example.test.js">
…the whole file…
</write_file>

You may read one more file first if you genuinely need it:

<read_file path="lib/permissions.js"/>
"""


class UnitTestAuthor:
    """One model call per phase. Writes only the paths it was handed."""

    def __init__(self, arch, project_dir=None, *, callbacks=None,
                 analyzer=None, session=None):
        self.arch = arch
        self.project_dir = project_dir or arch.project_dir
        self.cb = callbacks or {}
        self.az = analyzer
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

    def _idea(self):
        """
        The app's idea and approved plan, copied out of the build conversation.

        Turn 1 is where `start_conversation` puts the prompt and plan, and
        `_trim_convo` never drops indices 0-2 — so this is stable for the whole
        build. A copy, not a reference: nothing here writes to `arch.convo`.
        """
        try:
            convo = getattr(self.arch, "convo", None) or []
            if len(convo) > 1 and convo[1].get("role") == "user":
                return convo[1]["content"][:4000]
        except Exception:
            pass
        return (getattr(self.arch, "plan_md", "") or "")[:4000]

    @staticmethod
    def _preamble_note(target_src: str) -> str:
        """
        The mocks this file's test needs, worked out and handed over.

        Not a rule to remember — the exact lines, for this file, derived from
        what it imports. The model still writes the whole test; this only
        removes the one thing it was most often getting wrong. And if it leaves
        them out anyway, `ensure_mocks` puts them back on the way to disk, so
        the failure they cause is no longer possible.
        """
        from .session import mock_line, required_mocks
        needed = required_mocks(target_src)
        if not needed:
            return ""
        lines = "\n".join(mock_line(mod, helper) for mod, helper in needed)
        return ("\n\nThis file needs these, at the very top — nothing it does "
                f"can be tested without them:\n{lines}")

    def _phase_goal(self, phase):
        try:
            ph = (self.arch.plan.get("phases") or [])[phase - 1]
            bits = [ph.get("title", ""), ph.get("goal", ""), ph.get("done_when", "")]
            return " — ".join(b for b in bits if b)[:400]
        except Exception:
            return ""

    def write_for(self, targets, phase=0, max_reads=MAX_READS):
        """Write a test for each target. Returns the paths actually written."""
        if not targets:
            return []

        assigned = {t.test_path: t for t in targets}
        blocks = []
        for t in targets:
            body = (self.qa.read_source(t.path) if self.qa else None) or ""
            if not body.strip():
                continue
            blocks.append(f"--- {t.path} ---\n{body}\n\n"
                          f"Write its test at: {t.test_path}"
                          + self._preamble_note(body))
        if not blocks:
            return []

        convo = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content":
                f"## The app\n{self._idea()}\n\n"
                f"## This phase\n{self._phase_goal(phase) or f'phase {phase}'}\n\n"
                f"## Files to test — read them, then write one test file each\n\n"
                + "\n\n".join(blocks)
                + "\n\nWrite the test files now, one <write_file> block each."},
        ]

        written, rejected, reads = [], [], 0

        self._advice = {}
        budget = self.az._budget_chars() if self.az else 40_000

        while True:
            raw = []
            parser = FileStreamParser(
                on_text=lambda t: raw.append(t),
                on_file_start=lambda p: self._fire("on_file_start", p),
                on_file_token=lambda tok: None,
                on_file_end=lambda p, c: self._accept(p, c, assigned, written,
                                                      rejected, phase))
            try:
                self.arch._stream(convo, parser.feed, temperature=TEMPERATURE,
                                  model=QASession.model_for(self.qa, self.arch),
                                  timeout=CALL_BUDGET)
            except Exception as e:
                self._log("WARN", f"   ⚠ test author failed: {e}")
                parser.close()
                break
            parser.close()
            reply = "".join(raw)
            convo.append({"role": "assistant", "content": reply})

            wanted = self.az.READ_RE.findall(reply) if self.az else []
            used = sum(len(m["content"]) for m in convo)
            if not wanted or reads >= max_reads or used >= budget:
                break
            served = []
            for rel in wanted[:4]:
                reads += 1
                served.append(f"--- {rel} ---\n{self.az._read_for_model(rel)}")
            convo.append({"role": "user",
                          "content": "\n\n".join(served)
                                     + "\n\nNow write the test files."})

        if rejected:
            self._log("WARN", f"   ⛔ ignored {len(rejected)} off-list write(s): "
                              f"{', '.join(rejected[:3])}")

        missed = [t for p, t in assigned.items() if p not in written]
        if missed:
            names = ", ".join(t.path for t in missed[:3])
            self._log("WARN", f"   ↻ {len(missed)} file(s) got no test — "
                              f"asking again for {names}")
            convo.append({"role": "user", "content":
                "You did not write a usable test for "
                + ", ".join(f"`{t.path}` (at `{t.test_path}`)" for t in missed)
                + ". Write "
                + ("it" if len(missed) == 1 else "them")
                + " now, querying ONLY things that appear in the source you "
                  "were shown — one <write_file> block each, nothing else."})
            parser = FileStreamParser(
                on_text=lambda t: None,
                on_file_start=lambda p: self._fire("on_file_start", p),
                on_file_token=lambda tok: None,
                on_file_end=lambda p, c: self._accept(p, c, assigned, written,
                                                      rejected, phase))
            try:
                self.arch._stream(convo, parser.feed, temperature=TEMPERATURE,
                                  model=QASession.model_for(self.qa, self.arch),
                                  timeout=CALL_BUDGET)
            except Exception as e:
                self._log("WARN", f"   ⚠ retry failed: {e}")
            parser.close()
            still = [t.path for p, t in assigned.items() if p not in written]
            if still:
                self._log("WARN", f"   ⚠ still untested: {', '.join(still[:4])}")

        self._verify(convo, assigned, written, rejected, phase)
        self._suspects(written)
        return written

    def _runner(self):
        """A VitestRunner, or None if there is nothing to run tests with."""
        cmd = getattr(self.qa, "cmd", None) if self.qa else None
        if not cmd:
            return None

        from .runner import VitestRunner
        return VitestRunner(self.project_dir, cmd=cmd, callbacks=self.cb,
                            session=self.qa)

    _UNSETTLED_RE = re.compile(
        r"Cannot read properties of null \(reading 'use[A-Z]"
        r"|Failed to load url|ERR_MODULE_NOT_FOUND", re.I)

    @classmethod
    def _looks_unsettled(cls, failures) -> bool:
        """True when most of this run's failures are the module graph, not tests."""
        hits = sum(1 for f in (failures or [])
                   if cls._UNSETTLED_RE.search(str(getattr(f, "message", ""))))
        return bool(failures) and hits >= max(2, len(failures) // 2)

    @staticmethod
    def _missing_packages(failures) -> list:
        """Packages the run says it could not resolve, across every failure."""
        from .harness import TestHarness
        text = "\n".join(f"{getattr(f, 'message', '')}\n{getattr(f, 'stack', '')}"
                         for f in (failures or []))
        return TestHarness.missing_packages(text)

    def _install_missing(self, packages) -> bool:
        from .harness import TestHarness
        cmd = getattr(self.qa, "cmd", None) if self.qa else None
        if not cmd:
            return False
        try:
            h = TestHarness(self.project_dir, callbacks=self.cb, cmd=cmd)
            return h.install_missing(packages)
        except Exception as e:                              # noqa: BLE001
            self._log("WARN", f"   ⚠ could not install {packages}: {e}")
            return False

    def _verify(self, convo, assigned, written, rejected, phase):
        """
        Run what was just written, and hand back what actually happened.

        This is the whole point. Every failure class that has been chased with
        a new static check this session — an invented `data-testid`, a role the
        markup does not have, a `vi.mock` closing over a `const` below it, a
        `waitFor` shorter than the component's `setTimeout`, a seeded Date in
        the wrong timezone — says exactly what is wrong the first time the test
        is run. Guessing at those from the source is what the checks were for;
        reading them is better, and generalises to the ones nobody has hit yet.

        One batched vitest run to find out which files are unhappy, then ONE
        FILE AT A TIME to fix them. Both halves are deliberate. The run is
        batched because vitest costs ~2s of startup whatever it executes. The
        fixing is not, because asking for nine corrected files in a single turn
        produces nine mediocre ones: measured on a backfill, a round that
        handed back every failure at once left seven invented `data-testid`s in
        one file untouched while it worked on the others. A person fixes one
        test, runs it, and moves on.
        """
        runner = self._runner()
        if runner is None or not written:
            return

        passed, failures, ok = runner.run(paths=written)

        if failures:
            missing = self._missing_packages(failures)
            if missing and self._install_missing(missing):
                passed, failures, ok = runner.run(paths=written)

        for wait in (3, 6, 10):
            if not (failures and self._looks_unsettled(failures)):
                break
            self._log("INFO", f"   ⏳ the module graph is still settling — "
                              f"waiting {wait}s and running again before "
                              f"judging these")
            time.sleep(wait)
            passed, failures, ok = runner.run(paths=written)
            if not ok:
                break

        if not ok or (passed == 0 and not failures):
            spent = getattr(getattr(self.qa, "cmd", None), "calls", None)
            cap = getattr(getattr(self.qa, "cmd", None), "max_calls", None)
            why = ""
            if spent is not None and cap is not None and spent >= cap:
                why = f" — the {cap}-command budget is spent"
            self._log("WARN", f"   ⚠ the new tests did not run{why} — leaving "
                              f"them for the unit stage")
            return

        by_file = {}
        for f in failures:
            by_file.setdefault(f.test_file, []).append(f)

        for p in self._advice:
            if p in written:
                by_file.setdefault(p, [])

        if not by_file:
            self._log("INFO", f"   ✅ {len(written)} new test file(s) pass "
                              f"({passed} case(s))")
            return

        self._log("WARN", f"   ↻ {len(by_file)} of {len(written)} new test "
                          f"file(s) failing — fixing them")

        stuck, lock = [], threading.Lock()

        def fix(path):
            ok = self._fix_one(path, assigned.get(path), by_file[path],
                               runner, written, rejected, phase, assigned, lock)
            if not ok:
                with lock:
                    stuck.append(path)

        with ThreadPoolExecutor(max_workers=QA_FIX_WORKERS) as pool:
            list(pool.map(fix, sorted(by_file)))
        if stuck:
            self._log("WARN", f"   ⚠ {len(stuck)} test file(s) still failing "
                              f"after {MAX_VERIFY_ROUNDS} round(s): "
                              f"{', '.join(p.split('/')[-1] for p in stuck[:4])}")

    def _fix_one(self, path, t, fails, runner, written, rejected, phase,
                 assigned, lock=None) -> bool:
        """
        One test file, fixed and re-run until it passes or the rounds run out.

        A fresh conversation per file, not a continuation of the authoring
        turn: by the third round that turn holds every component in the batch
        and every failure from all of them, and the file being fixed is a
        smaller and smaller part of what the model is looking at.
        """
        src = (self.qa.read_source(t.path) or "") if (self.qa and t) else ""

        start_body = (self.qa.read_source(path) or "") if self.qa else ""
        best = (len(fails or []), start_body) if start_body else None
        last_sig = self._failure_signature(fails)

        for rnd in range(1, MAX_VERIFY_ROUNDS + 1):
            body = (self.qa.read_source(path) or "") if self.qa else ""
            if not body:
                return False
            convo = [
                {"role": "system", "content": SYSTEM},
                {"role": "user",
                 "content": self._fix_prompt(path, t, src, body, fails)},
            ]
            parser = FileStreamParser(
                on_text=lambda x: None,
                on_file_start=lambda p: self._fire("on_file_start", p),
                on_file_token=lambda tok: None,
                on_file_end=lambda p, c: self._accept(p, c, assigned, written,
                                                      rejected, phase, lock))
            try:
                self.arch._stream(convo, parser.feed, temperature=TEMPERATURE,
                                  model=QASession.model_for(self.qa, self.arch),
                                  timeout=CALL_BUDGET)
            except Exception as e:
                self._log("WARN", f"   ⚠ {path}: fix round {rnd} failed: {e}")
                parser.close()
                return False
            parser.close()

            passed, failures, ok = runner.run(paths=[path])
            if not ok:
                return False
            fails = failures
            if not failures and passed:

                note = self._advice.get(path)
                self._log("INFO", f"   ✅ {path.split('/')[-1]} — "
                                  f"{passed} case(s) pass (round {rnd})"
                                  + (f"; note: {note}" if note else ""))
                return True

            fixed_body = (self.qa.read_source(path) or "") if self.qa else ""
            count = len(failures)
            if best is None or count < best[0]:
                best = (count, fixed_body)
            elif count > best[0] and fixed_body != best[1]:
                self._log("WARN", f"   ↩ {path.split('/')[-1]}: round {rnd} "
                                  f"made it worse ({count} vs {best[0]}) — "
                                  f"keeping the better version")
                self._restore(path, t, best[1], phase)

            sig = self._failure_signature(failures)
            if sig and sig == last_sig:
                self._log("INFO", f"   ⏹ {path.split('/')[-1]}: same "
                                  f"{count} failure(s) as the last round — "
                                  f"stopping instead of repeating it")
                break
            last_sig = sig

        if best is not None:
            current = (self.qa.read_source(path) or "") if self.qa else ""
            if current and current != best[1]:
                self._restore(path, t, best[1], phase)
        return False

    @staticmethod
    def _failure_signature(fails) -> str:
        """
        What this round failed on, as one comparable string.

        Sorted, because the runner's order is not stable, and truncated per
        message so a line number moving does not read as progress.
        """
        return "|".join(sorted(
            f"{getattr(f, 'name', '')}::{str(getattr(f, 'message', ''))[:80]}"
            for f in (fails or [])))

    def _restore(self, path, t, body, phase) -> None:
        """Put a known-better version of a test file back on disk."""
        if not (self.qa and body):
            return
        try:
            self.qa.write_test_file(path, body, target=(t.path if t else ""),
                                    phase=phase, tier=(t.tier if t else 0))
        except Exception as e:                              # noqa: BLE001
            self._log("WARN", f"   ⚠ could not restore {path}: {e}")

    @staticmethod
    def _failure_digest(fails, limit: int = 8) -> str:
        """
        The failures, with the same error said once.

        A file that forgot one `vi.mock` fails every case with the identical
        message. Listing it five times spends the prompt on repetition and
        makes five separate-looking problems out of one — measured, that is
        the exact shape of 39% of all first-run failures, where one mistake
        killed every case in the file.

        So: group by the message, name the cases it took down, and keep the
        stack from the copy that has one. Saying "5 cases, all of them this"
        is also the more useful sentence — it tells the model the fault is in
        the setup, not in five different assertions.
        """
        groups = {}
        for f in (fails or []):
            key = " ".join(str(getattr(f, "message", "")).split())[:200]
            g = groups.setdefault(key, {"names": [], "stack": "", "dom": "",
                                        "hint": ""})
            g["names"].append(str(getattr(f, "name", "")))
            if not g["stack"] and getattr(f, "stack", ""):
                g["stack"] = f.stack
            if not g["dom"] and getattr(f, "dom", ""):
                g["dom"] = f.dom
            if not g["hint"] and getattr(f, "hint", ""):
                g["hint"] = f.hint

        lines = []
        for index, (message, g) in enumerate(list(groups.items())[:limit]):
            names = g["names"]
            if len(names) == 1:
                head = f"  • {names[0]}"
            else:
                shown = ", ".join(names[:3])
                more = f" and {len(names) - 3} more" if len(names) > 3 else ""
                head = (f"  • {len(names)} cases failed with the SAME error "
                        f"— {shown}{more}")
            frames = [ln.strip() for ln in (g["stack"] or "").splitlines()
                      if ln.strip().startswith("at ")][:3]
            entry = (head + f"\n    {message}"
                     + ("\n" + "\n".join(f"      {ln}" for ln in frames)
                        if frames else ""))

            if g["dom"] and index < 2:
                body = "\n".join(f"      {ln}" for ln in g["dom"].splitlines())
                entry += "\n    what actually rendered:\n" + body

            if g["hint"]:
                body = "\n".join(f"    {ln}" for ln in g["hint"].splitlines())
                entry += "\n" + body
            lines.append(entry)
        if len(groups) == 1 and len(next(iter(groups.values()))["names"]) > 1:
            lines.append("\n  Every case failed the same way, so the fault is "
                         "almost certainly in the setup above the first test, "
                         "not in the assertions.")
        return "\n".join(lines)

    def _fix_prompt(self, path, t, target_src, test_src, fails) -> str:
        """Everything needed to fix one file, and nothing about the others."""

        parts = [f"This test file has been RUN and it is failing. Fix it.",
                 "",
                 "You may only write the TEST file — the application code is "
                 "not yours to change. But you are not required to pretend the "
                 "component is correct:\n"
                 "  • If the test asks for something the component genuinely "
                 "does differently, correct the test.\n"
                 "  • If `what actually rendered` shows the component produced "
                 "NOTHING where it should have produced something, then the "
                 "test is describing the app correctly and the APP is wrong. "
                 "Do NOT weaken the assertion to match empty output. Leave the "
                 "case as it is and add a comment above it beginning "
                 "`// AGENTFORGE-APP-BUG:` saying what the component should have "
                 "rendered and what it rendered instead.\n"
                 "Keep every case that already passes, and do NOT add new ones "
                 "— a round that fixes two cases and introduces three is a "
                 "round that made this file worse."]
        if t and target_src:
            parts.append(f"## The component under test — {t.path}\n"
                         f"```jsx\n{target_src[:12000]}\n```")
        parts.append(f"## The test as it stands — {path}\n"
                     f"```jsx\n{test_src[:12000]}\n```")

        advice = self._advice.get(path)
        if advice:
            parts.append(f"## A static check says\n{advice}.")
        if fails:
            parts.append("## What the run reported\n" + self._failure_digest(fails))

        parts.append(f"Emit the COMPLETE corrected file in ONE <write_file "
                     f'path="{path}"> block, and nothing else.')
        return "\n\n".join(parts)

    def _accept(self, path, content, assigned, written, rejected, phase,
                lock=None):
        """
        The write allowlist — the identity rule, not just the shape rule.

        `lock` is passed when several fixes are in flight at once. Only the
        shared bookkeeping needs it; the file write itself is one path per
        worker and cannot collide.

        `on_file_end` fires for a refused write too, and has to. It is the
        other half of the `on_file_start` the parser already fired when the
        model opened the block, and the studio's code pane treats an open
        stream as "a file is being written right now": it shows the live buffer
        and ignores clicks on the file list, because during a build the pane
        follows the writer rather than the reader. A write refused here never
        sent its end, so the pane stayed locked on a file that had stopped
        arriving — every click on every other file did nothing, for the rest of
        the session. Refusing the write is still refusing it: nothing is
        written to disk and the path goes on `rejected`.
        """
        guard = lock or _NULL_LOCK
        key = (path or "").strip().lstrip("./").replace("\\", "/")
        if key not in assigned:
            with guard:
                rejected.append(key)
            self._fire("on_file_end", key, content)
            return
        t = assigned[key]

        advice = ""

        if advice:
            self._log("WARN", f"   ⚠ {key}: {advice}")
        with guard:
            if advice:
                self._advice[key] = advice
            else:
                self._advice.pop(key, None)
        self._fire("on_file_end", key, content)

        with guard:
            if self.qa and self.qa.write_test_file(key, content, target=t.path,
                                                   phase=phase, tier=t.tier):

                if key not in written:
                    written.append(key)

    TESTID_Q_RE = re.compile(
        r"""\b(?:get|find|query)(?:All)?ByTestId\s*\(\s*(['"])(.+?)\1""")

    TEXTATTR_Q_RE = re.compile(
        r"""\b(?:get|find|query)(?:All)?By(LabelText|AltText|Title)\s*\(\s*(['"])(.+?)\2""")

    TEXTATTR_SOURCES = {
        "LabelText": ("aria-label", "<label", "aria-labelledby"),
        "AltText": ("alt",),
        "Title": ("title",),
    }

    ROLE_Q_RE = re.compile(
        r"""\b(?:get|find|query)(?:All)?ByRole\s*\(\s*(['"])(.+?)\1""")

    IMPLICIT_ROLES = {
        "heading": ("<h1", "<h2", "<h3", "<h4", "<h5", "<h6"),
        "button": ("<button",),
        "link": ("<a ", "<a\n", "<link", "<a>"),
        "img": ("<img", "<image"),
        "listitem": ("<li",),
        "list": ("<ul", "<ol"),
        "textbox": ("<input", "<textarea"),
        "searchbox": ("<input",),
        "checkbox": ("<input",),
        "radio": ("<input",),
        "switch": ("<input",),
        "slider": ("<input",),
        "spinbutton": ("<input",),
        "combobox": ("<select", "<input"),
        "option": ("<option",),
        "table": ("<table",),
        "row": ("<tr",),
        "cell": ("<td",),
        "columnheader": ("<th",),
        "rowheader": ("<th",),
        "form": ("<form",),
        "navigation": ("<nav",),
        "banner": ("<header",),
        "main": ("<main",),
        "contentinfo": ("<footer",),
        "article": ("<article",),
        "separator": ("<hr",),
        "dialog": ("<dialog",),

        "presentation": (),
        "none": (),
    }

    DECL_RE = re.compile(r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=", re.M)
    HOISTED_RE = re.compile(
        r"(?:const|let|var)\s+(?:\{([^}]*)\}|([A-Za-z_$][\w$]*))\s*=\s*vi\.hoisted")
    IDENT_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\b")

    @staticmethod
    def _mock_calls(test_src: str):
        """`(specifier, factory_body, start, end)` for every `vi.mock(…)`."""
        out = []
        for m in re.finditer(r"vi\.mock\s*\(\s*(['\"])(.+?)\1", test_src):
            i, depth = test_src.index("(", m.start()), 0
            while i < len(test_src):
                if test_src[i] == "(":
                    depth += 1
                elif test_src[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            out.append((m.group(2), test_src[m.end():i], m.start(), i))
        return out

    @classmethod
    def _mock_bodies(cls, test_src: str) -> list:
        return [b for _, b, _, _ in cls._mock_calls(test_src)]

    def _mock_paths(self, test_src: str, test_rel: str) -> str:
        """
        A `vi.mock` specifier that resolves to nothing.

        Vitest resolves the path against the file that CALLS `vi.mock` — the
        test — not against the component being tested. So a component at
        `components/RouteGrid.jsx` importing `'./RouteCard'` must be mocked
        from `tests/unit/components/RouteGrid.test.jsx` as
        `'@/components/RouteCard'`; copying the component's own `'./RouteCard'`
        points at `tests/unit/components/RouteCard`, which does not exist.

        Nothing complains. The mock is simply never applied, the real child
        renders, and every assertion about the stub's markup fails — measured
        as four failures in one file that survived three rounds of fixing,
        because the errors all pointed at a missing `data-testid` and none of
        them mentioned the mock.
        """
        if not self.project_dir:
            return ""
        base = Path(self.project_dir)
        here = (base / test_rel).parent
        bad = []
        for spec, _, _, _ in self._mock_calls(test_src):
            if not spec.startswith("."):
                continue
            cands = [here / spec, *(Path(str(here / spec) + e)
                                    for e in (".js", ".jsx", ".ts", ".tsx"))]
            if any(c.exists() for c in cands):
                continue

            name = Path(spec).name
            hit = next((p for p in base.glob(f"components/**/{name}.js*")), None)
            hint = (f" — write it as '@/{hit.relative_to(base).as_posix()}'"
                    .replace(".jsx'", "'").replace(".js'", "'")) if hit else ""
            bad.append(f"'{spec}'{hint}")
        if not bad:
            return ""
        return (f"its vi.mock path {', '.join(bad[:2])} resolves to nothing "
                f"from the TEST file, so the mock never applies")

    def _hoisting_error(self, test_src: str) -> str:
        """
        A `vi.mock` factory that closes over a variable declared below it.

        `vi.mock` is hoisted to the top of the file, above every `const`, so a
        factory referring to one throws
        "Cannot access 'MockThing' before initialization" at import time. The
        whole file then collects zero tests and AgentForge reports it as
        "the test file does not parse" — which sends the repair agent looking
        for a syntax error that is not there. Measured: one build quarantined a
        perfectly good component test for exactly this.

        `vi.hoisted` is the fix and the prompt already says so; this is the
        half that does not rely on the model remembering.
        """
        safe = set()
        for braced, plain in self.HOISTED_RE.findall(test_src):
            if plain:
                safe.add(plain)
            for part in (braced or "").split(","):
                part = part.split(":")[-1].strip()
                if part:
                    safe.add(part)

        bodies, spans = [], []
        for m in re.finditer(r"vi\.mock\s*\(", test_src):
            i, depth = m.end() - 1, 0
            while i < len(test_src):
                if test_src[i] == "(":
                    depth += 1
                elif test_src[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            bodies.append(test_src[m.end():i])
            spans.append((m.start(), i))

        if not bodies:
            return ""
        outside = test_src
        for start, end in reversed(spans):
            outside = outside[:start] + outside[end:]
        declared = set(self.DECL_RE.findall(outside)) - safe
        if not declared:
            return ""

        bad = set()
        for body in bodies:
            bad |= {n for n in self.IDENT_RE.findall(body) if n in declared}
        if not bad:
            return ""
        return (f"its vi.mock factory uses {', '.join(sorted(bad)[:3])}, which "
                f"is declared below it — vi.mock is hoisted, so this throws "
                f"\"Cannot access before initialization\". Use vi.hoisted")

    NATIVE_EVENT_RE = re.compile(
        r"toBeInstanceOf\s*\(\s*(Event|MouseEvent|KeyboardEvent|SubmitEvent)\s*\)")

    SET_TIMEOUT_RE = re.compile(r"setTimeout\s*\([^,]+,\s*(\d+)\s*\)")
    WAIT_FOR_RE = re.compile(r"\bwaitFor\s*\(")
    TIMER_CONTROL_RE = re.compile(r"useFakeTimers|advanceTimersBy|runAllTimers"
                                  r"|timeout\s*:\s*\d+")

    CLICK_SUBMIT_RE = re.compile(
        r"(?:fireEvent\.click|user\.click|userEvent\.click)\s*\([^)]*"
        r"(?:submit|confirm|book|save|send|create|sign in|log in|add|update|"
        r"pay|place order)[^)]*\)", re.I)
    SUBMITS_PROPERLY_RE = re.compile(r"fireEvent\.submit\s*\(")

    BARE_FAKE_TIMERS_RE = re.compile(r"vi\s*\.\s*useFakeTimers\s*\(\s*\)")
    ADVANCING_TIMERS_RE = re.compile(
        r"useFakeTimers\s*\(\s*\{[^)]*shouldAdvanceTime")
    AWAITS_POLLING_RE = re.compile(
        r"await\s+(?:screen\s*\.\s*)?findBy[A-Z]\w*\s*\(|await\s+waitFor\s*\(")

    NEEDS_ROUTER_RE = re.compile(
        r"\buse(?:Router|Pathname|SearchParams|Params|SelectedLayoutSegment)\s*\(")
    MOCKS_NAV_RE = re.compile(r"""vi\.mock\s*\(\s*['"]next/navigation['"]""")

    def _unmocked_router(self, test_src: str, target_src: str) -> str:
        """
        A component that calls `useRouter`, in a test that never mocked
        `next/navigation`.

        Next throws its own invariant — "expected app router to be mounted" —
        the moment the hook runs, which is before the component renders and
        before any assertion is reached. So every case in the file dies with a
        message about routing, whatever it was actually checking, and the
        repair loop is handed fourteen identical failures that say nothing
        about the tests.

        Measured on one build: exactly that, fourteen of forty-six, and
        `diagnose()` had no class for it, so the round-one report did not even
        name the cause.

        The harness already ships `navMock.js` with `__setPath`, `__resetNav`
        and spies for push/replace/back. This only fires when the target really
        does use a routing hook and the test really has not mocked it.
        """
        if not self.NEEDS_ROUTER_RE.search(target_src or ""):
            return ""
        if self.MOCKS_NAV_RE.search(test_src or ""):
            return ""
        return ("the component calls a Next routing hook and this test does "
                "not mock next/navigation, so Next throws "
                "\"invariant expected app router to be mounted\" before "
                "anything renders. Add "
                "`vi.mock('next/navigation', () => import('../../helpers/navMock.js'))` "
                "at the top, and `__resetNav()` in beforeEach")

    _NOT_CODE_RE = re.compile(
        r"//[^\n]*"
        r"|/\*.*?\*/"
        r"|(?P<pre>[(,=:!&|?{;\[]\s*)"
        r"/(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n])+/[gimsuyd]*"
        r"|'(?:\\.|[^'\\\n])*'"
        r"|\"(?:\\.|[^\"\\\n])*\""
        r"|`(?:\\.|[^`\\])*`", re.S)

    @classmethod
    def _strip_not_code(cls, src: str) -> str:
        """Blank out what is not code, keeping every newline where it was so
        the line a bracket is reported on is the line it is on."""
        def blank(m):
            pre = m.group("pre") or ""
            return pre + "\n" * m.group(0)[len(pre):].count("\n")
        return cls._NOT_CODE_RE.sub(blank, src or "")
    _PAIRS = {")": "(", "]": "[", "}": "{"}

    def _unbalanced(self, test_src: str) -> str:
        """
        A bracket left open — the file cannot parse, so no case in it runs.

        esbuild says exactly where ("Expected \")\" but found \"expect\""), and
        the author's verify loop does hand that back, but three rounds of it
        did not put the character in: measured on a `render(<PlantFilter … />`
        whose closing paren was missing, which cost the whole file. The unit
        stage then quarantines an unparseable file without spending a call —
        correctly, since a file that does not parse says nothing about the app
        — so the component silently ends up with no test at all.

        Counting is not parsing, and it is not trying to be. It answers one
        question, mechanically, before the model is asked anything: did every
        bracket that was opened get closed.
        """
        code = self._strip_not_code(test_src)
        stack, line = [], 1
        for ch in code:
            if ch == "\n":
                line += 1
            elif ch in "([{":
                stack.append((ch, line))
            elif ch in self._PAIRS:
                if not stack:
                    return (f"there is a stray `{ch}` on line {line} — the file "
                            f"cannot parse, so none of its cases run")
                want = self._PAIRS[ch]
                got, at = stack.pop()
                if got != want:
                    return (f"the `{got}` opened on line {at} is closed by `{ch}` "
                            f"on line {line} — the file cannot parse, so none "
                            f"of its cases run")
        if stack:
            got, at = stack[0]
            return (f"the `{got}` opened on line {at} is never closed — the "
                    f"file cannot parse, so none of its cases run. Add the "
                    f"missing `{ {'(': ')', '[': ']', '{': '}'}[got] }`.")
        return ""

    READS_FORM_RE = re.compile(r"\brequest\s*\.\s*formData\s*\(")
    READS_JSON_RE = re.compile(r"\brequest\s*\.\s*json\s*\(")
    SENDS_JSON_RE = re.compile(r"\b(?:postJson|patchJson|putJson|deleteJson)\s*\(")
    SENDS_FORM_RE = re.compile(r"\bpostForm\s*\(")

    def _wrong_body_kind(self, test_src: str, target_src: str) -> str:
        """
        A test that sends JSON to a handler that reads `request.formData()`.

        The handler's `formData()` throws on a JSON body, its own `try/catch`
        turns the throw into a 500, and the case fails as "expected 500 to be
        400". That reads as the route crashing — `diagnose()` even has a class
        called exactly that — so the repair loop spends its rounds looking at a
        route which is correct, and never passes. Measured: two cases in
        `plants_add.test.js` survived nine rounds and both escalation tiers.

        `postJson` now forwards a FormData object rather than stringifying it
        to "{}", which closes the common half. This is the other half: a plain
        object handed to the JSON helper, which nothing downstream can tell
        apart from a test of a JSON route.
        """
        if not self.READS_FORM_RE.search(target_src or ""):
            return ""

        if self.READS_JSON_RE.search(target_src or ""):
            return ""
        if not self.SENDS_JSON_RE.search(test_src or ""):
            return ""
        if self.SENDS_FORM_RE.search(test_src or ""):
            return ""
        return ("the handler reads `request.formData()` and this test sends a "
                "JSON body, so `formData()` throws, the handler's own catch "
                "returns 500 and every case fails as \"expected 500 to be …\". "
                "Use `postForm(HANDLER, { field: 'value' })` instead.")

    def _frozen_clock(self, test_src: str) -> str:
        """
        `vi.useFakeTimers()` in a file that then awaits `findBy…`/`waitFor`.

        Both of those poll, and polling is scheduled on the clock the fake
        timers froze — so nothing advances it, the query never re-runs, and the
        case hangs until the 10s test timeout. It dies as
        `Error: STACK_TRACE_ERROR at chunk-hooks.js`, which names neither the
        query nor the component, so the repair loop is handed a failure with no
        information in it and cannot fix it however many rounds it is given.
        Measured: this was five of the six cases that survived eight repair
        rounds and all three escalation tiers on one build, and the pattern is
        in twelve test files across eight generated projects.

        The one-word fix is `{ shouldAdvanceTime: true }` — same component,
        24ms instead of a timeout.
        """
        if not self.BARE_FAKE_TIMERS_RE.search(test_src or ""):
            return ""
        if self.ADVANCING_TIMERS_RE.search(test_src or ""):
            return ""
        if not self.AWAITS_POLLING_RE.search(test_src or ""):
            return ""
        return ("it calls `vi.useFakeTimers()` and then awaits `findBy…` or "
                "`waitFor`, which poll the clock the fake timers froze — the "
                "case will hang until the 10s timeout and die as "
                "STACK_TRACE_ERROR. Use "
                "`vi.useFakeTimers({ shouldAdvanceTime: true })`, or drop the "
                "fake timers and pass `{ timeout: 2500 }` to waitFor")

    def _clicks_instead_of_submitting(self, test_src: str,
                                      target_src: str) -> str:
        """
        A submit flow driven by a click, which in jsdom does nothing.

        jsdom does not implement a browser's default form submission, so a
        click on `<button type="submit">` dispatches the click and stops. The
        `onSubmit` handler never runs. The test then waits for the success
        state and times out, and the failure — "unable to find heading
        /booked/" — reads as a component that does not render its success
        state, which is why no amount of repair fixes it.

        Measured on one component with all three idioms: `fireEvent.submit`
        reached `fetch` in 16ms, `fireEvent.click` and `userEvent.click` both
        timed out having called nothing. Sixteen of the twenty-four cases set
        aside across every generated app were this.

        Only fires when the target really is a form and the test really does
        wait for something afterwards — a click that asserts nothing async is
        just a click.
        """
        if "<form" not in (target_src or ""):
            return ""
        if "onSubmit" not in (target_src or ""):
            return ""
        if self.SUBMITS_PROPERLY_RE.search(test_src):
            return ""
        if not self.CLICK_SUBMIT_RE.search(test_src):
            return ""
        if "waitFor" not in test_src and "findBy" not in test_src:
            return ""
        return ("it submits by clicking the button, which does nothing in "
                "jsdom — the form's onSubmit never runs. Fill the fields, then "
                "`fireEvent.submit(container.querySelector('form'))`")

    def _bad_async_assumptions(self, test_src: str, target_src: str) -> str:
        """
        Assertions about React or about time that cannot hold.

        Both were measured on one build, as the last two failures standing
        after every repair round had run — neither is about the app, and no
        amount of rewriting the test file fixes either without knowing the rule.
        """
        m = self.NATIVE_EVENT_RE.search(test_src)
        if m:
            return (f"it asserts toBeInstanceOf({m.group(1)}) — React passes a "
                    f"SyntheticBaseEvent to handlers, which is never an "
                    f"instance of {m.group(1)}. Assert what the handler did "
                    f"with the event instead")

        delays = [int(d) for d in self.SET_TIMEOUT_RE.findall(target_src or "")]
        slow = [d for d in delays if d >= 1000]
        if (slow and self.WAIT_FOR_RE.search(test_src)
                and not self.TIMER_CONTROL_RE.search(test_src)):
            return (f"the component defers work by {max(slow)}ms "
                    f"(setTimeout), but waitFor gives up after 1000ms. Use "
                    f"vi.useFakeTimers() and advance the clock, or pass "
                    f"{{ timeout: {max(slow) + 500} }} to waitFor")
        return ""

    STYLE_ASSERT_RE = re.compile(r"\.(toHaveClass|toHaveStyle)\s*\(")

    def _asserts_styling(self, test_src: str) -> str:
        """Styling assertions, which are forbidden and cannot be made to hold."""
        hits = {m.group(1) for m in self.STYLE_ASSERT_RE.finditer(test_src)}
        if not hits:
            return ""

        return (f"it asserts styling with {', '.join(sorted(hits))} — classes "
                f"and inline styles are not the contract")

    def _invented_selectors(self, test_src: str, target_rel: str) -> str:
        """
        Selectors this test looks for that the component does not contain.

        Measured on a real build: thirteen first-round failures across nine
        files, ten of them a `role="status"` on a plain span, a `data-testid`
        nobody wrote, or an error branch the route does not have. The author is
        shown the component source and still writes the test it wishes existed,
        because good testing practice says prefer `getByRole` and nothing tells
        it which roles are actually there. This checks.
        """
        body = (self.qa.read_source(target_rel) or "") if self.qa else ""
        if not body:
            return ""

        body += "\n" + "\n".join(self._mock_bodies(test_src))

        missing = []
        for _, tid in self.TESTID_Q_RE.findall(test_src):
            if f'data-testid="{tid}"' not in body and f"data-testid='{tid}'" not in body:
                missing.append(f'testid "{tid}"')

        low_body = body.lower()
        for kind, _, text in self.TEXTATTR_Q_RE.findall(test_src):

            attrs = self.TEXTATTR_SOURCES[kind]
            if not any(a in low_body for a in attrs):
                missing.append(f'{kind} "{text}" (no {attrs[0]} in the source)')
            elif text.lower() not in low_body:
                missing.append(f'{kind} "{text}"')
        low = body.lower()
        for _, role in self.ROLE_Q_RE.findall(test_src):
            r = role.strip().lower()
            if f'role="{r}"' in low or f"role='{r}'" in low:
                continue
            tags = self.IMPLICIT_ROLES.get(r)
            if tags is None:
                missing.append(f'role "{role}"')
            elif tags and not any(t in low for t in tags):

                missing.append(f'role "{role}" (no {tags[0]}… in the source)')
        if not missing:
            return ""
        uniq = list(dict.fromkeys(missing))
        return (f"it queries {', '.join(uniq[:3])} — "
                f"{'that is' if len(uniq) == 1 else 'those are'} not in "
                f"{target_rel}")

    SUSPECT_RE = re.compile(r"//\s*SUSPECT:\s*(.+)")

    def _suspects(self, written):
        """Surface `// SUSPECT:` notes as findings for a human, not as failures."""
        if not self.qa:
            return
        for rel in written:
            body = self.qa.read_source(rel) or ""
            for m in self.SUSPECT_RE.finditer(body):
                note = m.group(1).strip()[:160]
                self.qa.report.suspects.append({"test": rel, "note": note})
                self._log("WARN", f"   🔎 {rel}: {note}")
