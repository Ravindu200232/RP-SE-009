"""Builds an application from its approved plan."""
from __future__ import annotations

import json
import logging
import os
import re
import textwrap
import time
from pathlib import Path

from agents.core import docsindex
from agents.core.commands import CommandRunner
from agents.core.exports_checks import check_named_imports, group_messages
from agents.core.ollama_client import OllamaClient, is_cloud_model, max_context
from agents.planner.architecture_runtime import (
    CMD_RE, FENCE_RE, OPEN_RE, PARTIAL_OPEN_RE, FileStreamParser, _strip_fence,
)
from agents.planner.build_templates import KNOWN_DEPENDENCIES, render_templates
from agents.planner.planning import (NEXT_STACK, PROMPT_PATH, PlannerAgent,
                                     render_sitemap_xml)

log = logging.getLogger("architect")
CHARS_PER_TOKEN = 3.4
HISTORY_BUDGET = 0.62
EDIT_TIMEOUT = 150

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Create or overwrite one complete project-relative file.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
}

NEXT_BUILDER_SYSTEM = """\
You are a senior Next.js engineer implementing one approved AgentForge plan.
The plan is a contract, not a suggestion. Write finished production-quality
files in plan order using complete <write_file path="…">…</write_file> blocks.

QUALITY BAR
- Implement every section, action, requirement, API contract, data read/write,
  design decision, responsive rule, and E2E-visible outcome assigned to a file.
- No TODO, placeholder, coming-soon screen, href="#", fake JSX record, dead
  button, console-only error, or permanently disabled feature.
- A control whose label names an action must PERFORM that action. "Add to cart",
  "Save", "Book", "Approve", "Refund" and their kind are never a plain <Link> to
  the page where the result would show: that navigates to an empty cart and
  reads, correctly, as the feature being missing. Write them as a <button> whose
  handler does the work — update the store, call the planned API, persist — and
  only then navigate or revalidate. If you find yourself writing
  `<Link href="/cart">Add to Cart</Link>`, the capability is not built yet.
  Navigation-only labels are the ones that merely go somewhere: "View cart",
  "Browse roasts", "Back to orders".
- A list/table/fetched panel has designed loading, empty, error, and success
  behavior. The empty state explains what belongs there and provides the real
  next action. Mutation success updates state, refreshes, or navigates without a
  manual reload. Pending controls disable and say what is happening.
- Treat CRUD as one end-to-end contract, not four unrelated buttons. Create,
  edit/update and delete each use the exact planned API URL + HTTP method + id
  shape, check `res.ok`, persist first, then update/revalidate the visible list.
  Never ship create-only CRUD where edit/delete controls call missing methods.
- Every mutation shows polished React feedback on both outcomes: a concise
  success toast/alert after persistence and an actionable error toast/alert on
  failure. Prefer the planned shared toast host (react-hot-toast is available)
  over `alert()`, console-only errors, or raw browser text.
- Preserve the approved palette, type scale, spacing, radii, depth, component
  states, content hierarchy, and mobile behavior. Every interactive element has
  rest, hover, visible keyboard focus, and disabled states when applicable.
- Use semantic elements, associated labels, stable accessible names, useful alt
  text, keyboard operation, readable contrast, and reduced-motion behavior.
- Put literal data-testid values only where the plan names them.

GLOBAL SHELL AND PAGE LAYOUT
- app/layout.jsx is the only file with <html>, <body>, and './globals.css'. It
  renders the planned Navbar, {children} inside the planned content container,
  and the Footer, so every route inherits the same chrome. A page never repeats
  that chrome and never declares its own <html>, <body>, header, or footer.
- Build the planned Navbar as a client component: brand, every planned link, the
  active state from usePathname, one primary action, a mobile menu that really
  opens and closes, and account controls only where the plan has accounts. Every
  href is a planned route.
- The same rule binds the Footer, and it is the one that gets broken: a footer
  is written last, from memory of what the app "should" have, and it ends up
  linking /vehicles, /assignments, /inventory — tidy names that no page serves.
  Every one of them is a 404 sitting on every single screen of the app. Before
  you write a footer href, find that exact path in the plan's site map. If the
  section you want has no page, either link the page that does the job under
  its real path, or write the words as plain text with no link at all. A footer
  of four honest links beats twelve that lead nowhere.
- When the plan has accounts, the Navbar reads the live session with
  `useSession()` from @/lib/auth-client and shows who is signed in right now.
  Signed in: render that user's own name — `session.user.name`, falling back to
  `session.user.email` when the name is empty — next to a real log-out control.
  That control awaits `signOut()` from @/lib/auth-client and then sends the user
  to the planned sign-in route with `router.push(...)` from next/navigation, so
  the session is gone and the page they land on reflects it. Signed out: render
  the sign-in link instead, and the sign-up link when signup is open. Never show
  both states at once, never print a hardcoded name, and never leave the log-out
  control on a page after the session ends. While `useSession()` is still
  loading, render the same layout with a neutral placeholder so the bar does not
  jump.
- Implement each page from its `layout` and `sections`: same order, same grid,
  same above-the-fold focus, collapsing at 360px as planned. A planned section is
  a real populated block, never a heading over a placeholder.
- Compose pages from components sharing one vocabulary of buttons, cards, tables,
  forms, section headers, and empty states; keep spacing, radii, and type scale
  identical across routes so the app reads as one product.
- Fill pages with real data from the planned collections and seed, so lists,
  grids, and detail pages look complete on first load.
- Every round carries the approved site map in XML. Each <page> is a real route
  with its owner file; every link, redirect, nav item, and empty-state action
  must target one of those paths, and no other route may be invented. Never add
  privacy, terms, careers, blog, or social destinations the site map does not
  serve — write that footer information as plain text instead of a link.
- lib/seed.js exports `ensureSeeded`: idempotent upserts, awaited before the
  first read of the data it creates. AgentForge also calls it through
  /api/seed, so the export name and its idempotence are part of the contract.
- When demo accounts exist, `lib/seed.js` owns PRODUCT DATA only. It MUST
  await `ensureDemoAccounts()` from @/lib/auth BEFORE user-owned rows, then read
  those provider-created users back and stamp their ids on owned records.
  Authentication implementation never belongs in the seeder: no `betterAuth`,
  no `auth.api.signUpEmail`, no user/account credential inserts, no hashes and
  no auth route logic in `lib/seed.js`. `lib/auth.js` alone creates credentials.
  Every planned demo email/password must sign in and retain its exact role.
  Never treat missing demo identities as a precondition; provisioning them via
  `ensureDemoAccounts()` is part of seeding, and product rows then reference the
  real provider user `_id` consistently across UI, API and database relations.
- Better Auth's identity collections are `user` and `account`, both SINGULAR.
  Read an account back with `getCollection('user')` and find it by email; its
  `_id` is the ObjectId to stamp on owned rows. `getCollection('users')` is a
  different, empty collection — a seed that reads it finds nothing, silently
  skips every row that needed an owner, and leaves the app with no bookings,
  orders or history while reporting success.

STACK AND FILE BOUNDARIES
- Next.js 16 App Router + React 19 + JavaScript. Never TypeScript, Pages Router,
  react-router-dom, Mongoose, Prisma, next/image, next/head, or a second Mongo client.
- JSX files contain UI; route and lib modules use .js. One default export per page
  or component. Route handlers have named GET/POST/PUT/PATCH/DELETE exports only.
- Server files must await every getCollection(name) and getSessionUser() call; both
  return promises. Server files must not use hooks or
  event handlers. Client files begin with 'use client', are never async, never
  import server/database modules, and reach persistence through planned APIs.
- A page needing DB reads and interaction stays a server page plus a planned
  client child. Serialize Mongo documents before crossing that boundary. Pass
  strings instead of icon component functions and never pass event callbacks
  from a server component into a client component.
- Await params and searchParams. Validate ObjectId strings and convert only at
  the database boundary. Use the declared field representation consistently.
- Files that read MongoDB export `const dynamic = 'force-dynamic'`.
- Imports use @/ across app/components/lib and may reference only files already
  present or named in the approved file plan. Fetch URLs are relative literals.
- AgentForge owns these modules and refuses every rewrite of them, so they will
  never gain an export. Import ONLY these names, and never invent a helper:
    @/lib/mongodb      getCollection, getDb, serialize, ObjectId
    @/lib/auth         auth, getSessionUser, ensureDemoAccounts, provisionUser
    @/lib/auth-client  authClient, signIn, signUp, signOut, useSession
  There is no insertDocument, updateDocument, deleteDocument, findDocuments or
  query helper. Writing data means awaiting getCollection(name) and calling the
  driver directly on it — insertOne, updateOne, deleteOne, find, findOne — so a
  create is `const rooms = await getCollection('rooms'); await rooms.insertOne(doc)`.

HOW THESE APPS ACTUALLY BREAK
Each item below is a crash seen in a served build. Write the right-hand pattern.
- `ReferenceError: X is not defined` — a component or helper was used without
  being imported. Before you finish a file, read your own JSX and confirm every
  capitalised tag and every helper you call has an import line. `<Link>` needs
  `import Link from 'next/link'`; icons need their named import from
  `lucide-react`; a planned component needs its `@/components/...` import.
- `Attempted import error: 'X' is not exported from 'lucide-react'` — the icon
  name was guessed. The build still compiles, so this one reaches the browser
  as a blank page. lucide renamed and dropped names over the years: there is no
  `Tool` (it is `Wrench`), no `Gas` (it is `Fuel`), no `Cog` on its own (it is
  `Settings`), no `Trash` (it is `Trash2`), no `Edit` (it is `Pencil` or
  `SquarePen`). Reach for the handful you are sure of — `Check`, `X`, `Plus`,
  `Search`, `User`, `Calendar`, `Clock`, `Car`, `Wrench`, `Fuel`, `Settings`,
  `AlertCircle`, `ChevronRight`, `LogOut`, `Trash2`, `Pencil` — and when the
  icon you want is not obviously among them, write the label as text instead.
  A word the user can read beats an icon that blanks the page.
- `TypeError: x.toLocaleDateString is not a function` — a Mongo `Date` becomes a
  string the moment the document is serialized for a client component or an API
  response. Never call a date method on a field you read back. Wrap it:
  `new Date(booking.checkIn).toLocaleDateString()`. The same applies to any
  field you format — a number you `.toFixed()` may arrive as a string too.
- `BSONError: input must be a 24 character hex string` — `new ObjectId(value)`
  was handed a slug such as `rooms-1`, because the seed identified rows by a
  readable field. Query by the identifier the seed actually wrote. When a route
  can receive either, branch on it:
  `const query = /^[0-9a-f]{24}$/i.test(id) ? { _id: new ObjectId(id) } : { slug: id }`
  Decide this once per collection and use the same rule in every route, link and
  seed that touches it.
- A related name that renders as the same fallback word on every row — every
  product tagged "General", every booking by "Customer". Nothing threw, so
  nothing reported it, and the page looks finished while the whole relationship
  is missing. The cause is always the same: `serialize()` turned that row's
  `brand_id` into a STRING, and the `_id` it has to match is still an ObjectId,
  so `findOne({ _id: p.brand_id })` matches nothing and `?? 'General'` hides it.
  Resolve the names BEFORE serializing, or key a lookup by string on both
  sides:
  `const names = new Map((await brands.find({}).toArray()).map(b => [String(b._id), b.name]))`
  then read `names.get(String(p.brand_id))`. One query for the whole list, not
  one per row — a per-row `findOne` inside `.map` is a page that gets slower
  with every record the customer adds. And write the empty case as the truth
  it is: an unlinked row says "Unassigned", never a plausible-looking category
  name that makes a broken join look like real data.
- `TypeError: rows.map is not a function` — a fetch result was assumed to be an
  array. A handler returns an object on error, and `await res.json()` gives that
  object. Normalise before rendering: `const rows = Array.isArray(data) ? data : []`
  and keep the planned empty state for the non-array case.
- A page that renders a list must survive an empty collection, a failed request,
  and a field that is absent from a row. Reach for optional chaining and a
  planned fallback instead of assuming the shape.
- A first visit has chosen no filters, so the unfiltered view is the default
  view, not an error. An API a page calls on load must answer a bare request
  with the full list; require a parameter only where the plan says the answer
  is meaningless without it, and let the page ask for it in the UI rather than
  firing the request and rendering the rejection. Never open a page on "SYSTEM
  ERROR — dates are required": show every room, with the date fields waiting.
  Never invent placeholder arguments to get past this either — a hardcoded
  date range silently answers a question the visitor did not ask.

DATA, AUTH, AND ACTIONS
- Use exact collection and field names from the plan. Seed every planned demo
  row with stable identity upserts and $setOnInsert; keep seeds small and
  idempotent. Never count-gate seeding, make a unique index, or open a transaction.
- Add auth only when roles_and_access.authentication_required is true. Better
  Auth defaults already exist. Server code imports getSessionUser from
  @/lib/auth; client code imports signIn/signUp/signOut/useSession from
  @/lib/auth-client. Never create /api/auth routes, sessions, cookies, hashes,
  auth wrappers, or show demo credentials in the app.
- When the plan needs a sign-in, the planned sign-in page is a finished screen,
  not a form sketch. It is a client component with a labelled email input
  (type="email", autocomplete="email"), a labelled password input
  (type="password", autocomplete="current-password"), and one submit control.
  Submitting awaits `signIn.email({ email, password })` from @/lib/auth-client
  inside the page's own submit handler. That call resolves to
  `{ data, error }` and NOTHING ELSE. There is no `success` field on it: test
  `if (result.error)` for the failure and read `result.data.user` for the
  person who just signed in — their role is `result.data.user.role`. Branching
  on `result.success` reads `undefined` on a sign-in that worked perfectly, so
  the session is created, the navbar updates to their name, and the page they
  are standing on tells them "Invalid email or password" and never moves. It
  is the worst failure of the lot, because every log says the sign-in
  succeeded. While the request is in flight the
  submit control is disabled and says so. A rejected sign-in renders a readable
  message beside the form — never a console log, never a silent no-op, never a
  blank screen. A successful sign-in sends the user to the home the plan gives
  their role, with `router.push(...)` followed by `router.refresh()` so the
  server sees the new session. Take the role off the value `signIn.email`
  resolves to — it carries the signed-in user, role included — and push that
  role's own planned home. Never push `/`: the landing route reads the session
  on the server, and at that instant the cookie the browser just received has
  not reached it, so it redirects straight back and the user is left staring at
  the sign-in form they just completed, signed in, going nowhere. For the same
  reason never pass a `callbackURL` pointing at the sign-in or sign-up page. If
  the result carries no role, push the plan's default signed-in home — any real
  page, never the one you are standing on. When signup is open the page links to the planned
  sign-up route; it never links to a route the site map does not serve.
- The planned sign-up page mirrors it with `signUp.email({ email, password, name })`,
  a labelled name input, autocomplete="new-password", the same pending, error and
  success behavior, and a link back to sign-in.
- Never leave either page rendering only markup: a submit control that calls no
  auth helper is a dead screen, and every other protected route in the app
  depends on this one working.
- Every picture the plan lists under `## Images` has to be rendered by some
  file. Artwork drawn for the sign-in and sign-up screens is the one that gets
  forgotten: the image model draws it, it lands in public/generated, and the
  auth pages ship as a bare form on white, so the app looks unfinished in the
  one place every user starts. If the plan names an image for those screens,
  the page shows it — as a side panel on wide screens or a covered backdrop
  behind the card — and the same goes for any other planned key. Do not write
  a picture the plan never listed, and never leave a listed one unused.
- Better Auth defaults expose `ensureDemoAccounts()` in `lib/auth.js`; product
  seed code only awaits that helper. Never copy provider/signup logic into the
  seeder or insert credential rows yourself.
- When an authorised admin/manager creates a real login account at runtime,
  call server helper `provisionUser({ email, password, name, role })` from
  @/lib/auth. Never `insertOne` a password into `user`: that creates a profile
  with no Better Auth credential, so the UI says created but login can never work.
- Ownership, role, price, totals, and user identity come from the session and
  database, never trusted request fields. API status/messages match the plan.
- A page the plan restricts to a role OPENS WITH THAT CHECK, in the page file
  itself. Read the session server-side, compare the role, and `redirect(...)`
  when it does not match — before a single query runs. That makes it a Server
  Component: no `'use client'` at the top, because `getSessionUser` and
  `redirect` do not exist in the browser and a client page importing them is a
  guard that never runs. When the screen also needs state or handlers, the page
  stays the server file that checks the role and fetches the data, and hands it
  to a `'use client'` child component that does the interacting. Leaving the check out
  is not a smaller bug than a crash: the page still renders, so nothing fails
  and nothing reports it, while anyone who types the URL reads the whole admin
  dashboard — revenue, customers, every order. Hiding the link in the navbar
  is not the check; the navbar is not what serves the page. The same holds one
  row down: a route that returns one record confirms the signed-in user owns
  that record before returning it, or every customer can read every other
  customer's order by changing the number in the URL.
- Compare a role against the SPELLING THE PLAN USES, character for character.
  `user.role === 'admin'` against a seeded role of `Admin` is false, and the
  branch it guards silently takes the other path: the admin gets scoped to
  their own rows and the management table they opened comes back empty, with
  no error anywhere to explain it. Copy the role strings out of the plan's
  demo accounts and use those exact values in every comparison, filter and
  redirect.
- Every visible action completes its full UI -> API/server -> persistence -> UI
  path and every navigation target exists in the site map.

Write only the requested files. Do not narrate and do not stop halfway through
a file. When all requested files are complete, say BUILD COMPLETE.
"""

NEXT_PLANNER_SYSTEM = PROMPT_PATH.read_text(encoding="utf-8") + "\n\n" + NEXT_STACK
NEXT_STACK_RULES = NEXT_STACK
PROMPTS = {
    "next": {"planner": NEXT_PLANNER_SYSTEM, "builder": NEXT_BUILDER_SYSTEM,
             "rules": NEXT_STACK_RULES, "roots": ("app/", "components/", "lib/"),
             "entry": ("app/page.jsx", "app/page.js")},
}

class ArchitectAgent:
    """Build, resume, and update one generated application."""

    # Scaffold files the product is EXPECTED to replace. app/page.jsx ships as
    # a "Building…" placeholder and lib/seed.js as a no-op stub, purely so the
    # app compiles before the product exists. Guarding them the same way as the
    # real defaults meant that when the plan came back empty, nothing could
    # ever overwrite the placeholder — not the builder, not the repair pass —
    # and the app served "Building…" while still passing its own journey.
    NEXT_PLACEHOLDERS = frozenset({"app/page.jsx", "lib/seed.js"})
    NEXT_SCAFFOLD = NEXT_PLACEHOLDERS | frozenset({
        "package.json", "next.config.mjs", "jsconfig.json", "tailwind.config.js",
        "postcss.config.js", "app/globals.css", "app/layout.jsx",
        "lib/mongodb.js", "app/api/health/route.js", "app/api/seed/route.js",
        ".env.local", ".gitignore",
        "lib/auth.js", "lib/auth-client.js", "app/api/auth/[...all]/route.js",
    })
    NEXT_PROTECTED = (NEXT_SCAFFOLD - NEXT_PLACEHOLDERS) | {
        "vitest.config.mjs", "playwright.config.js"}
    NODE_BUILTINS = {"assert", "buffer", "child_process", "crypto", "events", "fs",
                     "fs/promises", "http", "https", "module", "net", "os", "path",
                     "process", "stream", "timers", "tls", "url", "util", "zlib"}
    PREINSTALLED = {"react", "react-dom", "next", "mongodb", "better-auth",
                    "@better-auth/mongo-adapter", "lucide-react", "framer-motion"}
    PKG_NAME_RE = re.compile(r"^(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$", re.I)
    IMPORT_SPEC_RE = re.compile(r"(?:\bfrom\s*|\brequire\s*\(\s*|\bimport\s*\(\s*|\bimport\s+)[\"']([^\"'\s()]+)[\"']")
    LOCAL_IMPORT_RE = re.compile(r"(?:from\s+|import\s*)[\"'](\.[^\"']+)[\"']")
    ALIAS_IMPORT_RE = re.compile(r"(?:from\s+|import\s*)[\"']@/([^\"']+)[\"']")
    STRAY_DIRECTIVE_RE = re.compile(r"^[^\S\n]*[\"']use client[\"'][^\S\n]*;?", re.M)
    UNRESOLVED_RE = re.compile(r"(?:Can't resolve|Cannot find module)\s*[\"']([^\"'\n]+)[\"']")
    EDIT_TIMEOUT = EDIT_TIMEOUT

    def __init__(self, client: OllamaClient, model: str, project_dir: Path,
                 callbacks: dict | None = None, stack: str = "next",
                 mongo_uri: str = "", db_name: str = "", dev_port: int = 5173,
                 think: bool | None = None):
        self.client, self.model = client, model
        self.project_dir, self.cb = Path(project_dir), callbacks or {}
        self.stack = stack if stack in PROMPTS else "next"
        self.mongo_uri, self.db_name, self.dev_port = mongo_uri, db_name, dev_port
        self.files, self.plan, self.convo = {}, {}, []
        self.plan_md = self.architecture_md = self.design_md = ""
        self.tokens_in = self.tokens_out = self.write_seq = 0
        self.num_ctx, self.is_cloud, self.think = max_context(model), is_cloud_model(model), think
        self._scaffolding, self._scaffold_baseline = False, {}
        self._workspace_tool_cache, self._e2e_privileged_paths = {}, set()
        self.cmd = CommandRunner(
            self.project_dir, npm_bin=self.cb.get("npm_bin", "npm"),
            node_bin=self.cb.get("node_bin", "node"),
            on_log=lambda level, message: self._fire("on_log", level, message),
            on_event=lambda event: self._fire("on_command", event))

    def _fire(self, name: str, *args) -> None:
        callback = self.cb.get(name)
        if callable(callback):
            try:
                callback(*args)
            except Exception as exc:
                log.warning("callback %s failed: %s", name, exc)

    def _log(self, level: str, message: str) -> None:
        if callable(self.cb.get("on_log")):
            self._fire("on_log", level, message)
        else:
            log.info(message)

    @property
    def _P(self) -> dict:
        return PROMPTS[self.stack]

    def _planner_sys(self) -> str:
        return self._P["planner"]

    def _builder_sys(self) -> str:
        prompt = self._P["builder"]
        try:
            learned = __import__("agents.core.lessons", fromlist=["prompt_block"]).prompt_block()
            if learned:
                prompt += "\n\nPROJECT-GENERATION LESSONS\n" + learned
        except Exception as exc:
            log.debug("builder lessons unavailable: %s", exc)
        docs = docsindex.index_block(self.project_dir) if self.stack == "next" else ""
        return prompt + ("\n\nINSTALLED NEXT.JS DOCUMENT INDEX\n" + docs if docs else "")

    @property
    def source_roots(self) -> tuple:
        return self._P["roots"]

    def is_source(self, path: str) -> bool:
        return path.startswith(self.source_roots) and path.endswith((".js", ".jsx"))

    def _stream(self, messages, on_delta, tools=None, temperature=0.5,
                model=None, timeout=None, think=None):
        options = {"temperature": temperature, "top_p": 0.9, "num_ctx": self.num_ctx}
        selected_think = self.think if think is None else think
        started, chars = time.time(), 0
        calls = []
        for chunk in self.client.chat_stream(
                model or self.model, messages, tools=tools, options=options,
                keep_alive="10m", think=selected_think, timeout=timeout or 900):
            message = chunk.get("message") or {}
            delta = message.get("content") or ""
            if delta:
                chars += len(delta)
                on_delta(delta)
            calls.extend(message.get("tool_calls") or [])
            if chunk.get("done"):
                self.tokens_in += chunk.get("prompt_eval_count", 0) or 0
                self.tokens_out += chunk.get("eval_count", 0) or 0
            if chars >= 250_000:
                self._log("WARN", f"   ✂ stopped an oversized model turn after {chars:,} characters")
                break
            if time.time() - started > (timeout or 900):
                break
        return calls

    def _budget_chars(self) -> int:
        return int(self.num_ctx * HISTORY_BUDGET * CHARS_PER_TOKEN)

    def _trim_convo(self) -> None:
        budget = self._budget_chars()
        while sum(len(str(item.get("content") or "")) for item in self.convo) > budget and len(self.convo) > 4:
            self.convo.pop(3)

    def memory_stats(self) -> dict:
        chars = sum(len(str(item.get("content") or "")) for item in self.convo)
        return {"turns": len(self.convo), "approx_tokens": int(chars / CHARS_PER_TOKEN),
                "num_ctx": self.num_ctx, "cloud": self.is_cloud}

    def _safe_path(self, rel: str) -> Path:
        raw = str(rel or "").strip().replace("\\", "/").lstrip("/")
        parts = [part for part in raw.split("/") if part not in {"", ".", ".."}]
        if not parts:
            raise ValueError("empty project path")
        target = (self.project_dir / "/".join(parts)).resolve()
        root = self.project_dir.resolve()
        if target != root and root not in target.parents:
            raise ValueError("path leaves project")
        return target

    def write_file(self, rel: str, content: str) -> bool:
        try:
            target = self._safe_path(rel)
            key = target.relative_to(self.project_dir.resolve()).as_posix()
            protected = self.NEXT_PROTECTED
            planned = {item.get("path") for item in self._planned_files()}
            if key in protected and not self._scaffolding and key not in planned:
                self._log("WARN", f"   ⛔ kept scaffold-owned default {key}")
                return False
            body = _strip_fence(content).rstrip() + "\n"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            self.files[key], self.write_seq = body, self.write_seq + 1
            size = f"{len(body) / 1024:.1f}KB" if len(body) >= 1024 else f"{len(body)}B"
            self._fire("on_file_written", key, size, body)
            self._log("INFO", f"   📝 {key} ({size})")
            return True
        except Exception as exc:
            self._log("ERROR", f"   ❌ write failed {rel}: {exc}")
            return False

    def write_own(self, rel: str, content: str) -> bool:
        return self.write_file(rel, content)

    def make_plan(self, user_prompt: str, requirement_source: str = "") -> bool:
        self._log("INFO", "🧭 Planning — requirements, design, routes, architecture and E2E")
        self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "active"})
        planner = PlannerAgent(self.client, self.model, stack=self.stack,
                               callbacks=self.cb, think=self.think, stream=self._stream)
        bundle = planner.create(user_prompt, requirement_source)
        if not bundle:
            self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "error"})
            return False
        self.plan, self.plan_md = bundle.data, bundle.markdown
        self.architecture_md, self.design_md = bundle.architecture_markdown, bundle.design_markdown
        for path, body in (("plan.md", self.plan_md), ("architecture.md", self.architecture_md),
                           ("design.md", self.design_md),
                           ("sitemap.xml", bundle.sitemap_xml)):
            self.write_file(path, body)
        self._save_plan_json()
        self.start_conversation(user_prompt)
        self.save_convo()
        self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "done", "plan": self.plan})
        self._log("INFO", f"   ✅ Plan ready — {len(self.plan.get('requirements') or [])} requirements, "
                            f"{len(self.plan.get('routes') or [])} routes, "
                            f"{len(self.plan.get('file_plan') or [])} implementation files")
        return True

    def start_conversation(self, user_prompt: str) -> None:
        plan_json = json.dumps(self.plan, ensure_ascii=False, indent=2)
        self.convo = [
            {"role": "system", "content": self._builder_sys()},
            {"role": "user", "content": (
                "AUTHORITATIVE USER INPUT\n" + user_prompt +
                "\n\nAPPROVED PLAN JSON\n" + plan_json +
                "\n\nThe plan owns requirements, design, site map, routes, architecture, "
                "file contracts, and E2E proof. Do not alter it. Wait for the first build task.")},
            {"role": "assistant", "content": "Understood. I will implement the approved plan exactly, one complete file at a time."},
        ]

    def scaffold(self) -> None:
        self._log("INFO", f"🧱 Writing {self.stack} runtime defaults")
        self._scaffolding = True
        try:
            defaults = render_templates(self.stack, self.plan, mongo_uri=self.mongo_uri,
                                        db_name=self.db_name, dev_port=self.dev_port)
            for path, body in defaults.items():
                self.write_file(path, body)
                self._scaffold_baseline[path] = body.rstrip() + "\n"
        finally:
            self._scaffolding = False

    def _planned_files(self) -> list[dict]:
        return [item for item in self.plan.get("file_plan") or [] if isinstance(item, dict) and item.get("path")]

    def _implemented(self, path: str) -> bool:
        body = self.files.get(path)
        return body is not None and body != self._scaffold_baseline.get(path)

    def _outstanding(self) -> list[dict]:
        return [item for item in self._planned_files() if not self._implemented(item["path"])]

    def unfinished(self) -> list[str]:
        return [item["path"] for item in self._outstanding()]

    def _task_prompt(self, task: dict, files: list[dict]) -> str:
        payload = dict(task)
        payload["files"] = files
        cap_ids = {rid for file in files for rid in file.get("requirements") or []}
        capabilities = [cap for cap in self.plan.get("capabilities") or []
                        if cap_ids & set(cap.get("requirement_ids") or []) or
                        set(cap.get("files") or []) & {file["path"] for file in files}]
        apis = [api for api in self.plan.get("api_contracts") or []
                if api.get("handler_file") in {file["path"] for file in files} or
                set(api.get("called_from") or []) & {file["path"] for file in files}]
        return (
            "IMPLEMENT THIS APPROVED BUILD TASK. Write every listed file completely.\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + "\n\nCAPABILITIES TOUCHING THIS TASK\n"
            + json.dumps(capabilities, ensure_ascii=False, indent=2)
            + "\n\nAPI CONTRACTS TOUCHING THIS TASK\n"
            + json.dumps(apis, ensure_ascii=False, indent=2)
            + "\n\nUse exact planned names and paths. Output complete <write_file> blocks only."
        )

    def _sitemap_block(self) -> str:
        """The whole site map, re-sent with every build round the model gets."""
        xml = render_sitemap_xml(self.plan) if self.plan else ""
        if "<page" not in xml:
            return ""
        return ("\n\nAPPROVED SITE MAP — every route that exists, with its owner "
                "file, audience, composition and links. Link only to these paths.\n"
                + xml)

    def _run_write_loop(self, user_content: str, _tool_depth: int = 0) -> int:
        self._workspace_tool_cache = {} if _tool_depth == 0 else self._workspace_tool_cache
        if _tool_depth == 0:
            user_content += self._sitemap_block()
        self.convo.append({"role": "user", "content": user_content})
        self._trim_convo()
        raw, state = [], {"path": None, "count": 0}
        parser = FileStreamParser(
            lambda text: self._fire("on_chat", text.strip()) if text.strip() and "BUILD COMPLETE" not in text.upper() else None,
            lambda path: (state.update(path=path), self._fire("on_file_start", path)),
            lambda token: self._fire("on_file_token", state["path"], token),
            lambda path, body: (self._fire("on_file_end", path, body),
                                state.update(count=state["count"] + (1 if self.write_file(path, body) else 0), path=None)),
        )
        try:
            calls = self._stream(self.convo, lambda delta: (raw.append(delta), parser.feed(delta)), temperature=0.35)
        except Exception as exc:
            self._log("ERROR", f"   ❌ Generation failed: {exc}")
            calls = []
        parser.close()
        reply = "".join(raw)
        self.convo.append({"role": "assistant", "content": reply})
        self.run_requested_commands(reply)
        for call in calls:
            function = (call or {}).get("function") or {}
            if function.get("name") != "write_file":
                continue
            args = function.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    continue
            if args.get("path") and args.get("content") and self.write_file(args["path"], args["content"]):
                state["count"] += 1
        if state["count"] == 0 and _tool_depth < 2:
            try:
                from agents.core.workspace import WorkspaceTools
                observations, used = WorkspaceTools(self).serve(reply)
            except Exception as exc:
                observations, used = "", 0
                log.debug("workspace tool serving failed: %s", exc)
            # The builder prompt offers <read_docs topic="…"/> and promises the
            # page comes back next message, so the request has to be answered
            # here or the model waits for something that never arrives.
            try:
                pages = docsindex.serve(self.project_dir, reply)
            except Exception as exc:
                pages = ""
                log.debug("docs serving failed: %s", exc)
            if pages:
                observations = (observations + "\n\n" + pages).strip()
                used += 1
            if used:
                self.convo.append({"role": "user", "content": "Tool observations:\n" + observations})
                return self._run_write_loop("Continue the same task from those observations and write its files.", _tool_depth + 1)
        return state["count"]

    def build_app(self) -> int:
        total, phases, written = len(self._planned_files()), self.plan.get("phases") or [], 0
        self._log("INFO", f"⚙️  Building {total} planned files across {len(phases)} tasks")
        for index, task in enumerate(phases, 1):
            files = [item for item in task.get("files") or [] if not self._implemented(item.get("path", ""))]
            if not files:
                continue
            self._fire("on_phase", {"phase": index, "total": len(phases), "title": task.get("title"),
                                    "status": "active", "files": [item["path"] for item in files]})
            written += self._run_write_loop(self._task_prompt(task, files))
            left = [item for item in files if not self._implemented(item["path"])]
            if left:
                written += self._run_write_loop(
                    "Finish the same approved task. These planned files are still absent or still defaults:\n"
                    + "\n".join("- " + item["path"] for item in left)
                    + "\nWrite each complete file now; do not change the plan.")
            done = total - len(self._outstanding())
            self._fire("on_progress", f"Task {index}/{len(phases)} — {done}/{total} files", 18 + int(58 * done / max(1, total)))
            self._fire("on_phase", {"phase": index, "total": len(phases), "title": task.get("title"),
                                    "status": "done",
                                    "written": sum(self._implemented(item["path"]) for item in files)})
            self._fire("on_memory", self.memory_stats())
            self.save_convo()
        return written

    def run(self, user_prompt: str, *, requirement_source: str = "") -> bool:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._fire("on_progress", "Planning…", 5)
            if not self.make_plan(user_prompt, requirement_source):
                return False
            self._fire("on_progress", "Scaffolding…", 15)
            self.scaffold()
            self.install_planned_deps()
            self._fire("on_progress", "Writing files…", 18)
            self.build_app()
            if self._outstanding():
                self._log("WARN", f"   ⚠ Closing {len(self._outstanding())} remaining planned file(s)")
                self._run_write_loop(self._task_prompt(
                    {"id": "closure", "title": "Complete the approved plan", "goal": "No planned file remains"},
                    self._outstanding()))
            self.repair_missing_imports()
            self.sync_dependencies()
            self.install_unresolved()
            self.repair_lint()
            return self._verify_output()
        finally:
            self.save_convo()

    @classmethod
    def imported_packages(cls, content: str) -> list[str]:
        out = []
        for spec in cls.IMPORT_SPEC_RE.findall(content or ""):
            if spec.startswith((".", "/", "@/", "node:")) or spec.startswith("next/"):
                continue
            name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
            if name not in cls.NODE_BUILTINS and name not in cls.PREINSTALLED and cls.PKG_NAME_RE.match(name) and name not in out:
                out.append(name)
        return out

    def unresolved_packages(self) -> list[str]:
        try:
            package = json.loads((self.project_dir / "package.json").read_text(encoding="utf-8"))
        except Exception:
            package = {}
        declared = set(package.get("dependencies") or {}) | set(package.get("devDependencies") or {})
        modules = self.project_dir / "node_modules"
        used = {name for path, body in self.files.items() if self.is_source(path)
                for name in self.imported_packages(body)}
        return sorted(name for name in used if name not in declared or not (modules / name / "package.json").exists())

    def sync_dependencies(self) -> int:
        path = self.project_dir / "package.json"
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        dependencies, added = package.setdefault("dependencies", {}), []
        for file, body in self.files.items():
            if not self.is_source(file):
                continue
            for name in self.imported_packages(body):
                if name not in dependencies and name in KNOWN_DEPENDENCIES:
                    dependencies[name], added = KNOWN_DEPENDENCIES[name], added + [name]
        if added:
            text = json.dumps(package, indent=2) + "\n"
            path.write_text(text, encoding="utf-8")
            self.files["package.json"] = text
            self._log("INFO", "   📦 Declared " + ", ".join(added))
        return len(added)

    def install_packages(self, names: list[str]) -> list[str]:
        names = list(dict.fromkeys(name for name in names if self.PKG_NAME_RE.match(name)))
        if not names:
            return []
        result = self.cmd.run("npm install " + " ".join(names))
        return names if result.ok else []

    def install_planned_deps(self) -> int:
        names = [item.get("name") if isinstance(item, dict) else item for item in self.plan.get("dependencies") or []]
        unknown = [str(name) for name in names if name and name not in KNOWN_DEPENDENCIES and name not in self.PREINSTALLED]
        return len(self.install_packages(unknown))

    def install_unresolved(self) -> int:
        return len(self.install_packages(self.unresolved_packages()))

    def packages_named_in(self, text: str) -> list[str]:
        out = []
        for spec in self.UNRESOLVED_RE.findall(text or ""):
            name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
            if self.PKG_NAME_RE.match(name) and name not in out:
                out.append(name)
        return out

    def _resolve_import(self, owner: str, spec: str) -> bool:
        if spec.startswith("@/"):
            base = spec[2:]
        elif spec.startswith("."):
            base = os.path.normpath(str(Path(owner).parent / spec)).replace("\\", "/")
        else:
            return True
        return any(candidate in self.files or (self.project_dir / candidate).is_file()
                   for candidate in (base, base + ".js", base + ".jsx", base + "/index.js", base + "/index.jsx"))

    def repair_missing_imports(self) -> int:
        missing = []
        for owner, body in self.files.items():
            if not owner.endswith((".js", ".jsx")):
                continue
            for spec in self.LOCAL_IMPORT_RE.findall(body) + ["@/" + value for value in self.ALIAS_IMPORT_RE.findall(body)]:
                if not self._resolve_import(owner, spec):
                    missing.append(f"{owner} imports {spec}")
        if not missing:
            return 0
        return self._run_write_loop(
            "Resolve these missing local imports using approved file-plan paths. Create a planned file when absent or correct the importing file.\n"
            + "\n".join("- " + item for item in dict.fromkeys(missing)))

    def lint_generated(self) -> list[str]:
        errors = []
        better_auth = "betterAuth(" in self.files.get("lib/auth.js", "")
        for path, body in self.files.items():
            if not path.endswith((".js", ".jsx", ".mjs")):
                continue
            directive = self.STRAY_DIRECTIVE_RE.search(body)
            if directive and body[:directive.start()].strip():
                errors.append(f"{path}: 'use client' is not the first statement")
            if re.search(r"^\s*interface\s+\w+|:\s*(?:string|number|boolean|any)\s*[,)=;]", body, re.M):
                errors.append(f"{path}: contains TypeScript syntax")
            if self.stack == "next" and "react-router-dom" in body:
                errors.append(f"{path}: imports react-router-dom in a Next app")
            if path.endswith("route.js") and re.search(r"export\s+default", body):
                errors.append(f"{path}: route handlers cannot default export")
            if re.search(r"\b(?:const|let|var)\s+\w+\s*=\s*(?:getCollection|getSessionUser)\s*\(", body):
                errors.append(f"{path}: await async getCollection/getSessionUser before using its result")
            if ("{ params }" in body
                    and re.search(r"\b(?:const|let|var)\s+\{[^}]+\}\s*=\s*params\s*;", body)):
                errors.append(f"{path}: await Next.js dynamic-route params before destructuring")
            if (re.match(r"\s*[\"']use client[\"']", body)
                    and re.search(r"@/lib/(?:mongodb|auth|seed)(?:[\"'/]|$)|from\s+[\"']mongodb", body)):
                errors.append(f"{path}: client file imports server/database code")
            if better_auth and "seed" in path.lower():
                if re.search(r"betterAuth\s*\(|from\s+['\"]better-auth|auth\.api\.signUpEmail", body):
                    errors.append(f"{path}: auth provider/signup logic belongs only in lib/auth; call ensureDemoAccounts()")
                if re.search(r"\bpassword\s*:", body) and not re.search(r"\bensureDemoAccounts\s*\(", body):
                    errors.append(f"{path}: do not call auth.api.signUpEmail here; provision identities with ensureDemoAccounts() from lib/auth")
        try:
            from agents.core.exports_syntax import check_syntax, syntax_messages
            broken, _ = check_syntax(self.project_dir, self.files)
            errors.extend(syntax_messages(broken))
        except Exception as exc:
            log.debug("syntax scan unavailable: %s", exc)
        errors.extend(group_messages(check_named_imports(self.files)))
        errors.extend(f"{path}: planned file was not implemented" for path in self.unfinished())
        return list(dict.fromkeys(errors))

    def repair_lint(self) -> int:
        if "betterAuth(" in self.files.get("lib/auth.js", ""):
            for path, body in list(self.files.items()):
                if "seed" not in path.lower(): continue
                fixed = re.sub(r"((?:getCollection|collection)\s*\(\s*['\"])users(['\"]\s*\))", r"\1user\2", body)
                if fixed != body:
                    self._write_atomic(path, fixed); self.files[path] = fixed; self.write_seq += 1
                    self._log("INFO", f"   🔐 normalized Better Auth user collection in {path}")
        errors = self.lint_generated()
        if not errors:
            return 0
        self._log("WARN", f"🔍 Repairing {len(errors)} generated-code issue(s)")
        return self._run_write_loop(
            "Fix these deterministic issues while preserving the approved plan. Rewrite complete affected files only.\n"
            + "\n".join("- " + item for item in errors[:30]))

    def _verify_output(self) -> bool:
        if not any(path in self.files for path in self._P["entry"]):
            self._log("ERROR", f"   ❌ Missing entry file {self._P['entry'][0]}")
            return False
        missing = self.unfinished()
        if missing:
            self._log("ERROR", "   ❌ Planned files remain: " + ", ".join(missing[:12]))
            return False
        errors = self.lint_generated()
        if errors:
            for error in errors[:10]:
                self._log("WARN", "   ⚠ " + error)
        return not errors

    def run_requested_commands(self, reply: str) -> list[str]:
        results = []
        for command in [item.strip() for item in CMD_RE.findall(reply or "") if item.strip()][:5]:
            results.append(self.cmd.run(command).as_feedback())
        return results

    def _snapshot(self, max_files: int = 35, per_file: int = 12_000) -> str:
        rows = []
        for path in sorted(self.files):
            if not self.is_source(path):
                continue
            body = self.files[path]
            rows.append(f"--- {path} ---\n" + (body if len(body) <= per_file else body[:per_file] + "\n// …truncated…"))
            if len(rows) >= max_files:
                break
        return "\n\n".join(rows)

    def _context_snapshot(self, max_files: int = 35, per_file: int = 12_000, wanted=None) -> str:
        return self._snapshot(max_files=max_files, per_file=per_file)

    def _snapshot_caps(self) -> dict:
        return {"max_files": 40 if self._budget_chars() >= 150_000 else 24,
                "per_file": 18_000 if self._budget_chars() >= 150_000 else 6_000}

    def update(self, instruction: str) -> int:
        if not self.convo:
            self.start_conversation(self.plan.get("source_input_summary") or self.plan_md or "existing app")
        prompt = (
            "CURRENT SOURCE\n" + self._snapshot(**self._snapshot_caps()) +
            "\n\nREQUESTED CHANGE\n" + instruction +
            "\n\nPreserve the approved plan/design unless the request explicitly changes it. "
            "Rewrite only complete affected files using <write_file> blocks."
        )
        count = self._run_write_loop(prompt)
        self.repair_missing_imports()
        self.sync_dependencies()
        return count

    def resume(self, brief: str = "") -> bool:
        if not self.plan.get("file_plan"):
            self._log("ERROR", "   ❌ No saved plan to resume")
            return False
        if not self.convo:
            self.start_conversation((self.plan.get("source_input_summary") or self.plan_md) + "\n" + brief)
        if self._outstanding():
            self.build_app()
        self.repair_missing_imports()
        self.sync_dependencies()
        self.install_unresolved()
        self.repair_lint()
        return self._verify_output()

    def load_existing(self) -> None:
        if (self.project_dir / "next.config.mjs").exists() or (self.project_dir / "next.config.js").exists():
            self.stack = "next"
        skip = {"node_modules", ".git", ".next", "dist", "out", ".agentforge", "public", "tests"}
        for path in self.project_dir.rglob("*"):
            if not path.is_file() or any(part in skip for part in path.parts) or path.name.startswith(".env"):
                continue
            if path.suffix not in {".js", ".jsx", ".mjs", ".json", ".css", ".html", ".md"} or path.stat().st_size > 250_000:
                continue
            rel = path.relative_to(self.project_dir).as_posix()
            self.files[rel] = path.read_text(encoding="utf-8", errors="replace")
        self.plan_md = self.files.get("plan.md", "")
        self.architecture_md = self.files.get("architecture.md", "")
        self.design_md = self.files.get("design.md", "")
        self.plan = self._load_plan_json()
        self.load_convo()

    PLAN_JSON, CONVO_JSON = ".agentforge/plan.json", ".agentforge/convo.json"

    def _write_atomic(self, rel: str, text: str) -> None:
        path = self.project_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)

    def _save_plan_json(self) -> None:
        if self.plan:
            self._write_atomic(self.PLAN_JSON, json.dumps(self.plan, ensure_ascii=False, indent=2))

    def _load_plan_json(self) -> dict:
        try:
            return json.loads((self.project_dir / self.PLAN_JSON).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_convo(self) -> bool:
        if len(self.convo) < 3:
            return False
        try:
            messages = self.convo[-16:]
            self._write_atomic(self.CONVO_JSON, json.dumps(
                {"model": self.model, "stack": self.stack, "messages": messages},
                ensure_ascii=False, indent=1))
            return True
        except Exception as exc:
            log.warning("could not save conversation: %s", exc)
            return False

    def load_convo(self) -> bool:
        try:
            data = json.loads((self.project_dir / self.CONVO_JSON).read_text(encoding="utf-8"))
            messages = [item for item in data.get("messages") or [] if isinstance(item, dict)]
            if len(messages) >= 3:
                self.convo = messages
                return True
        except Exception:
            pass
        return False

    def _capability_ledger(self, wanted=None) -> str:
        paths = {item if isinstance(item, str) else item.get("path") for item in (wanted or [])}
        rows = []
        for cap in self.plan.get("capabilities") or []:
            if paths and not paths.intersection(cap.get("files") or []):
                continue
            proof = cap.get("proof_points") or cap.get("proof") or []
            proof = "; ".join(proof) if isinstance(proof, list) else str(proof)
            rows.append(f"{cap.get('id')}: {cap.get('behavior')} — {proof}")
        return "\n".join(rows)

    def _contract_ledger(self, wanted=None) -> str:
        paths = {item if isinstance(item, str) else item.get("path") for item in (wanted or [])}
        rows = []
        for api in self.plan.get("api_contracts") or []:
            touched = {api.get("handler_file"), *(api.get("called_from") or [])}
            if paths and not paths.intersection(touched):
                continue
            rows.append(f"{api.get('name')}: {api.get('method')} {api.get('path')} — {api.get('success_effect')}")
        return "\n".join(rows)

    def _data_ledger(self) -> str:
        rows = []
        for model in self.plan.get("data_model") or []:
            fields = ", ".join(f"{field.get('name')}:{field.get('type')}" for field in model.get("fields") or [])
            rows.append(f"{model.get('collection')} — {fields}")
        return "\n".join(rows)

__all__ = [
    "ArchitectAgent", "FileStreamParser", "CHARS_PER_TOKEN", "HISTORY_BUDGET",
    "EDIT_TIMEOUT", "CMD_RE", "FENCE_RE", "OPEN_RE", "PARTIAL_OPEN_RE",
    "WRITE_FILE_TOOL", "NEXT_PLANNER_SYSTEM", "NEXT_BUILDER_SYSTEM",
    "NEXT_STACK_RULES", "PROMPTS", "log",
]
