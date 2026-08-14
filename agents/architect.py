"""
ArchitectAgent — fully LLM-driven, continuous full-app generation.

Unlike BuilderAgent (which stitches LLM output into a fixed Python-generated
skeleton), nothing here is templated: the raw user prompt goes straight to the
model, the model writes a big ``plan.md``, and then it generates every file
itself by calling a ``write_file`` tool.

Generation is one uninterrupted pass. The model is handed the whole file list
once and then simply told "Continue" every time it stops, until every planned
file is on disk — rather than being re-prompted phase by phase. The plan's
phases survive as *reporting* structure only: they still drive the UI timeline
and still trigger the QA agent's test authoring as their files land.

Tool protocol
-------------
Native Ollama tool calls are accepted when the model emits them, but the
primary channel is a streaming text protocol that works with *every* model
and streams token-by-token into the UI:

    <write_file path="app/components/Board.jsx">
    ...file content...
    </write_file>

Two output stacks
-----------------
New builds emit **Next.js 16 (App Router) + MongoDB**, JavaScript only, with
the database reached exclusively through a scaffolded ``lib/mongodb.js``.
The **Vite + React** stack is kept because projects generated before the
migration must stay editable; ``load_existing()`` infers which one a project
uses from its config files.

Config files are always Python-generated. The model only writes application
code, and a set of deterministic post-passes repairs the Next.js rules that
mid-size local models reliably get wrong (missing ``'use client'``, missing
``force-dynamic``, Pages-Router imports).
"""
import json
import logging
import os
import re
import secrets
import textwrap
import time
from pathlib import Path

from . import docsindex
from .commands import CommandRunner
from .exports import check_named_imports, group_messages, strip_noncode
from .ollama_client import OllamaClient, is_cloud_model, max_context

log = logging.getLogger("architect")


CHARS_PER_TOKEN = 3.4


HISTORY_BUDGET = 0.62


SNAPSHOT_OPEN = ("## Current source on disk — this is the truth, ignore any "
                 "older copy of these files above")
SNAPSHOT_CLOSE = "## End of current source"
SNAPSHOT_RE = re.compile(
    re.escape(SNAPSHOT_OPEN) + r".*?" + re.escape(SNAPSHOT_CLOSE), re.S)


OPEN_RE = re.compile(
    r"<(write_file|file)\s+path\s*=\s*[\"']([^\"'>]+)[\"']\s*>", re.I)
PARTIAL_OPEN_RE = re.compile(r"<(write_file|file)\b", re.I)


CMD_RE = re.compile(r"<run_command>(.*?)</run_command>", re.I | re.S)
FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9+#-]*\s*\n(.*?)\n?\s*```\s*$", re.S)


_DOUBLED_TAG_RE = re.compile(r"</\s*([A-Za-z][\w.]*)_\1\s*>")


def _fix_doubled_tags(text: str) -> str:
    """
    Repair `</div_div>` to `</div>`.

    Not a guard — it constrains nothing about what the app may be. It corrects
    a malformed token on the way to disk, in the same breath as the code fence.

    Worth doing in Python rather than leaving to the model because the model is
    the one making the mistake, and asking it to fix its own tic by rewriting
    the file gives it another chance to make it. Measured: one build wrote
    `</div_div>` 38 times across seven files, `npm run build` named the file,
    the line and the token with a caret under it, and two repair rounds handed
    that error back and got the same tic returned both times. The build never
    went green, so the unit stage never ran at all. Every other project on disk
    has zero occurrences — this is a slip, not a habit, and a slip is exactly
    what a deterministic repair is for.

    Only `X_X` is touched. A real component called `Foo_Bar` is left alone,
    because its halves differ.
    """
    return _DOUBLED_TAG_RE.sub(r"</\1>", text or "")


def _strip_fence(text: str) -> str:
    """Models love wrapping file bodies in markdown fences. Remove them."""
    m = FENCE_RE.match(text)
    return m.group(1) if m else text


def _safe_flush_len(buf: str, tag: str) -> int:
    """
    How much of `buf` can be emitted without risking a tag split across
    chunk boundaries: everything except the longest suffix that is also a
    prefix of `tag`.
    """
    for k in range(min(len(tag) - 1, len(buf)), 0, -1):
        if buf.endswith(tag[:k]):
            return len(buf) - k
    return len(buf)


class _RefusalLoop(Exception):
    """
    Raised to end a turn that has stopped making progress.

    Not an error: the turn's work up to this point is on disk. It exists so a
    refusal deep inside the streaming parser can unwind the stream, which is
    the only way to stop a model that is re-emitting files it has already been
    told it may not write.
    """


class FileStreamParser:
    """Incremental parser splitting a token stream into prose and file bodies."""

    def __init__(self, on_text, on_file_start, on_file_token, on_file_end):
        self.on_text = on_text
        self.on_file_start = on_file_start
        self.on_file_token = on_file_token
        self.on_file_end = on_file_end
        self.buf = ""
        self.mode = "text"
        self.tag = None
        self.path = None
        self.content = ""

    def feed(self, chunk: str):
        self.buf += chunk
        self._drain()

    def close(self):
        """Flush leftovers — a file left unterminated is still salvaged."""
        if self.mode == "file":
            if self.buf:
                self.content += self.buf
                self.on_file_token(self.buf)
            self.buf = ""
            self.on_file_end(self.path, _strip_fence(self.content))
            self.mode, self.path, self.content = "text", None, ""
        elif self.buf:
            self.on_text(self.buf)
            self.buf = ""

    def _drain(self):
        while True:
            if self.mode == "text":
                m = OPEN_RE.search(self.buf)
                if m:
                    if m.start():
                        self.on_text(self.buf[:m.start()])
                    self.tag = m.group(1).lower()
                    self.path = m.group(2).strip()
                    self.buf = self.buf[m.end():]

                    if self.buf.startswith("\n"):
                        self.buf = self.buf[1:]
                    self.content = ""
                    self.mode = "file"
                    self.on_file_start(self.path)
                    continue

                p = PARTIAL_OPEN_RE.search(self.buf)
                if p:
                    if p.start():
                        self.on_text(self.buf[:p.start()])
                        self.buf = self.buf[p.start():]
                    return

                keep = _safe_flush_len(self.buf, "<write_file")
                if keep:
                    self.on_text(self.buf[:keep])
                    self.buf = self.buf[keep:]
                return

            close_tag = f"</{self.tag}>"
            idx = self.buf.find(close_tag)
            if idx >= 0:
                head = self.buf[:idx]
                if head:
                    self.content += head
                    self.on_file_token(head)
                self.buf = self.buf[idx + len(close_tag):]

                self.on_file_end(self.path, _strip_fence(self.content))
                self.mode, self.path, self.content = "text", None, ""
                continue

            keep = _safe_flush_len(self.buf, close_tag)
            if keep:
                part = self.buf[:keep]
                self.content += part
                self.on_file_token(part)
                self.buf = self.buf[keep:]
            return


WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Create or overwrite a file in the project. "
                       "Always send the COMPLETE file content.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Project-relative path, e.g. src/components/Board.jsx"},
                "content": {"type": "string",
                            "description": "Full file content"},
            },
            "required": ["path", "content"],
        },
    },
}


VITE_STACK_RULES = textwrap.dedent("""\
    STACK (fixed — do not deviate):
      • React 18 function components + hooks (NO TypeScript, NO class components)
      • Vite + JavaScript (.jsx files only)
      • Tailwind CSS utility classes for ALL styling
      • react-router-dom v6 for multi-page navigation
      • framer-motion for animation, lucide-react / react-icons for icons
      • State: useState / useReducer / useContext — no Redux, no Zustand
      • Persistence: localStorage only

    FRONTEND-ONLY — THIS IS ABSOLUTE:
      • NO backend, NO server, NO Express, NO database, NO Prisma
      • NO API keys, NO paid third-party services, NO authentication server
      • NO `fetch()` to any private/paid endpoint
      • Everything — data, "auth", persistence — lives in the browser
        (React state + localStorage). Seed realistic demo data in code.
      • Images: use Tailwind gradients, inline SVG, emoji or CSS shapes.
        NEVER link to an external image URL that could 404.
    """)

NEXT_STACK_RULES = textwrap.dedent("""\
    STACK (fixed — do not deviate):
      • Next.js 16 App Router, JavaScript. NO TypeScript, ever.
      • EXTENSIONS — one per role, never both. A file's extension is decided
        by what is in it, and getting this wrong silently breaks the app,
        because the bundler resolves `.jsx` BEFORE `.js`: if both
        `components/Card.js` and `components/Card.jsx` exist, `@/components/Card`
        loads the .jsx and the other is dead code nobody notices.
          .jsx  — anything containing a tag: app/**/page.jsx, app/**/layout.jsx,
                  app/**/error.jsx, app/**/not-found.jsx, components/*.jsx
          .js   — plain modules, which never contain a tag:
                  app/api/**/route.js, lib/*.js
        Never write the same name under both.
      • React 19 function components + hooks
      • Tailwind CSS utility classes for ALL styling
      • MongoDB via the official driver, reached ONLY through @/lib/mongodb
      • Routing is the filesystem: app/page.jsx, app/tasks/page.jsx,
        app/tasks/[id]/page.jsx — there is no router library
      • lucide-react for icons, framer-motion for animation

    PROJECT SHAPE — there is NO src/ directory:
      app/          routes, layouts, pages, route handlers
      components/   reusable UI
      lib/          data access and helpers
      Import across folders with the @/ alias:
        import Card from '@/components/Card'

    DATABASE — THIS IS THE POINT OF THE APP:
      • A local MongoDB is already running and already configured.
        NEVER write connection code, NEVER construct a MongoClient,
        NEVER read process.env.MONGODB_URI yourself.
      • import { getDb, getCollection, serialize, ObjectId } from '@/lib/mongodb'
      • Read and write from Server Components and route handlers only.
      • Seed realistic demo data through lib/seed.js so the app is never empty.
      • NO external APIs, NO API keys, NO Mongoose, NO Prisma.
      • Sign-in, if the app needs one, is ALREADY BUILT — Better Auth against
        this project's MongoDB, generated by AgentForge. Do NOT plan a login route,
        a register route, a logout route, a password hash, a sessions
        collection or a session cookie: every endpoint under /api/auth/*
        already exists and planning one would shadow it. NO next-auth, NO
        Auth0, NO JWT.
      • Images: Tailwind gradients, inline SVG or emoji. NEVER an external
        image URL that could 404.
    """)

VITE_PLANNER_SYSTEM = textwrap.dedent("""\
    You are a senior front-end architect. You take a rough app idea and produce
    a complete, buildable implementation plan for a REAL, multi-screen web app —
    not a landing page, not a demo stub.

    {stack}

    OUTPUT FORMAT — exactly two parts, in this order:

    PART 1 — a detailed markdown document. Use these headings:
      # <App Title>
      ## Overview            – what the app does, who it is for
      ## Core Features       – bullet list, be specific and ambitious
      ## Data Model          – the JS object shapes held in state/localStorage
      ## Routes              – every route path and what renders there
      ## Component Tree      – the full component hierarchy
      ## Design System       – colour palette (hex), typography, spacing, mood
      ## Build Tasks         – one `### Task N — <title>` per task, each with
                               its goal and the exact files it creates

    PART 2 — a single ```json fenced block, and nothing after it:
    ```json
    {
      "project_name": "kebab-case-name",
      "title": "Human Readable Title",
      "description": "one sentence",
      "dependencies": ["react-router-dom", "framer-motion", "lucide-react"],
      "tasks": [
        {
          "id": 1,
          "title": "Foundation & routing",
          "goal": "what this task must achieve",
          "files": [
            {"path": "src/App.jsx", "purpose": "router + layout shell"}
          ]
        }
      ]
    }
    ```

    PLANNING RULES:
      • 4 to 7 tasks. Task 1 is always the app shell + routing + theme.
        The last task is always polish (empty states, transitions, responsive).
      • Every task lists 2–6 files. Total 12–25 files — build something real.
        The build is driven one task at a time, so a task holding eight files
        is a task whose files all come out thin.
      • Paths are project-relative and start with `src/`.
      • A file is written in exactly ONE task. Never plan to rewrite a file.
      • Only list `dependencies` that are real npm packages you will import.
      • Do NOT write any code in the plan. The plan is prose + the JSON block.
    """)

VITE_BUILDER_SYSTEM = textwrap.dedent("""\
    You are a senior React engineer implementing an approved plan, working
    straight through the file list without stopping.

    {stack}

    HOW YOU WRITE FILES — you have one tool, `write_file`. Call it by emitting
    this exact syntax, with the complete file between the tags:

    <write_file path="src/components/Example.jsx">
    import { useState } from 'react'

    export default function Example() {
      return <div className="p-6">Hello</div>
    }
    </write_file>

    TOOL RULES:
      • One `<write_file>` block per file. Emit blocks back to back.
      • NEVER put markdown fences (```) inside a block. Raw code only.
      • ALWAYS write the complete file — never "…rest unchanged", never a diff.
      • Keep going down the requested file list, block after block. Stop only
        at a file boundary; you will be told to continue.
      • Between blocks you may write ONE short sentence about what you built.

    CODE RULES — violating these breaks the build:
      • Every .jsx file has exactly one `export default function Name()`.
      • All imports at the very top. Import every hook, icon and component used.
      • Only import files that already exist or that you are writing in this
        same pass.
      • Icons: `import { Plus, Trash2 } from 'lucide-react'` — verify the name
        is a real lucide icon. When unsure, use an inline <svg> instead.
      • No TypeScript syntax: no `:type`, no `interface`, no `as`, no generics.
      • Never assign THROUGH an optional chain — `a?.b = c` is a syntax error,
        not a safe assignment, and it stops the whole app compiling. Write
        `const el = a; if (el) el.b = c` instead. Same for `?.[i] =` and `+=`.
      • Escape apostrophes in JSX text as &apos; (Don&apos;t, not Don't).
      • Hoist regex literals and any `/` division above the `return`.
      • Tailwind classes only — no styled-components, no .css imports besides
        the existing `src/index.css`.
      • Components must be genuinely functional: working state, handlers,
        validation, empty states, hover/focus states, and responsive layout.
      • Aim for 80–250 lines per component. Polished, not placeholder.
    """)


NEXT_PLANNER_SYSTEM = textwrap.dedent("""\
    You are a senior full-stack architect. You take a rough app idea and produce
    a complete, buildable implementation plan for a REAL, multi-screen,
    database-backed web app — not a landing page, not a demo stub.

    {stack}

    OUTPUT FORMAT — exactly two parts, in this order:

    PART 1 — a detailed markdown document. Use these headings:
      # <App Title>
      ## Overview            – what the app does, who it is for
      ## Core Features       – bullet list, be specific and ambitious
      ## Data Model          – every MongoDB COLLECTION, its fields and types,
                               and how many demo documents to seed. Seed the
                               MINIMUM that proves the screen works: FEWER THAN
                               5 documents per collection. Users are the
                               exception — exactly one per role. Only seed more
                               when the idea above explicitly asked for sample
                               / demo / bulk data, and in that case write the
                               line `Sample data: requested` under this heading
                               so the tooling knows it was deliberate.
      ## Routes              – a table: | path | file | server/client | reads |
                               covering every page AND every /api handler.

                               GIVE EACH ROLE ITS OWN SECTION. If the request
                               describes what different roles see, every one of
                               them gets its own route prefix — /member,
                               /technician, /manager — and each screen the
                               request names becomes its OWN route under it,
                               not a tab inside one shared page. A request
                               naming three roles with four screens between
                               them is a plan with at least seven routes.

                               Collapsing them into a single /dashboard that
                               branches on `user.role` is the one thing not to
                               do here, and it is the failure this rule exists
                               for: measured on the same request twice, one
                               plan produced /member, /member/book, /technician,
                               /technician/report, /technician/add-session,
                               /manager, /manager/staff, /manager/stock — and
                               the other produced /dashboard and nothing else,
                               so two of the three roles had nowhere to go.

                               It also has to be guarded per route: Next does
                               NOT inherit a page's guard, so every page under
                               /manager checks the session itself, or the
                               section gets an app/manager/layout.jsx that
                               does it once for all of them.
      ## Server / Client Split
                             – list which files are Server Components (read the
                               database, no hooks) and which are Client
                               Components (`'use client'`, hooks, handlers).
                               Decide this NOW; a file is one or the other.
      ## Packages            – npm packages beyond the preinstalled ones, and
                               why each is needed. Write "none" if none.
      ## Demo Accounts       – ONLY if the app has sign-in: the exact email +
                               plaintext password for each role, which the seed
                               will hash. They are NEVER shown inside the app —
                               the tool running this build displays them to the
                               developer outside it.
                               Omit this heading entirely otherwise.
      ## Component Tree      – the full component hierarchy
      ## Images              – every picture this app needs, one per line as
                               `key — a prompt describing it — aspect`, where
                               aspect is banner, wide, landscape, square,
                               portrait or poster. A hero banner, a login
                               backdrop, one photo per seeded product, a
                               poster for a marketing section. Write each
                               prompt the way you would to an image model:
                               subject, setting, style, lighting. Omit the
                               heading entirely for an app with no pictures —
                               an admin dashboard usually has none.
      ## Design System       – ONE accent colour as a hex value and what it is
                               reserved for, the neutral ramp beside it, the
                               type scale, the spacing rhythm, the card style
                               (radius + border), and the mood in one line.
                               Be decidable: "indigo-600 for primary actions
                               only, slate for everything else" is a design
                               system; "modern and clean" is not. The build is
                               judged on how it looks, so this section is what
                               makes every screen agree with every other one.
      ## Build Tasks         – one `### Task N — <title>` per task, each with
                               its goal, the exact files it creates, a
                               **Done when:** line stating what must work, and —
                               when the brief below carries numbered
                               requirements — a **Covers:** line naming the ids
                               that task accounts for (`Covers: FR-003, FR-004`).
      ## Definition of Done  – the checks the finished app must pass:
                               every route returns 200, data persists, every
                               listed feature is reachable from the UI, and
                               every requirement a task claims to cover is
                               reachable in the running app

    PART 2 — a single ```json fenced block, and nothing after it:
    ```json
    {
      "project_name": "kebab-case-name",
      "title": "Human Readable Title",
      "description": "one sentence",
      "dependencies": ["lucide-react", "framer-motion", "date-fns"],
      "images": [
        {"key": "hero", "prompt": "a wide photograph of …", "aspect": "banner"},
        {"key": "login-bg", "prompt": "…", "aspect": "portrait"}
      ],
      "demo_accounts": [
        {"email": "admin@demo.com", "password": "password123", "role": "admin"}
      ],
      "tasks": [
        {
          "id": 1,
          "title": "Shell, theme & seed data",
          "goal": "what this task must achieve",
          "done_when": "the home page lists seeded records from MongoDB",
          "covers": ["FR-001", "FR-002"],
          "files": [
            {"path": "app/page.jsx", "kind": "server",
              "purpose": "dashboard, reads tasks from Mongo"},
            {"path": "components/TaskList.js", "kind": "client",
              "purpose": "filter + toggle, uses useState"}
          ]
        }
      ]
    }
    ```

    EVERY file entry MUST carry `"kind"`:
      • "server" — no hooks, no event handlers; may be `async` and read the
        database directly. This is the default.
      • "client" — needs useState/useEffect/onClick/framer-motion, so it will
        start with `'use client'` and fetch through /api instead of the driver.
      • "route"  — an `app/api/**/route.js` handler.
    Getting this wrong is the single most common way these apps fail to build,
    which is why it is decided here rather than while writing the file.

    `demo_accounts` is REQUIRED when the app has sign-in and must be OMITTED
    when it does not. Passwords are plaintext here; the seed hashes them.

    `covers` is REQUIRED when the brief carries numbered requirements and must
    be OMITTED when it does not. It is a record of your own reasoning, not a
    score: nothing counts these ids and nothing fails a build over them.

    PLANNING RULES:
      • THE SPECIFICATION IS THE CHECKLIST. When the idea below is followed by
        a specification with numbered requirements — FR-001, FR-002 — every one
        of them is somebody's job. Before you finish, walk that list and check
        each id appears in some task's `covers`. A requirement in no task is a
        feature the finished app will not have, and nobody will notice until
        they go looking for it. If one genuinely cannot be built on this stack,
        write one line under ## Overview saying which and why — do not drop it
        in silence.
      • 4 to 7 tasks — up to 9 when a numbered specification is supplied and
        the requirements genuinely do not fit in seven. Task 1 is the app shell
        + theme + `lib/seed.js` + ONE page that already reads from MongoDB —
        prove the data path early. The last task is always polish (empty
        states, transitions, responsive).
      • Every task lists 2–6 files. Total 12–25 files, or up to 30 for a
        numbered specification — build something real. The build runs one task
        at a time and each task gets its own turn, so a task holding eight
        files is a task whose files all come out thin. Split it. The 2–6 per
        task does not move: more requirements means more tasks, not fatter ones.
      • Paths start with `app/`, `components/` or `lib/`. There is NO `src/`.
      • Page files are `app/<route>/page.js`; API files are
        `app/api/<name>/route.js`.
      • The plan MUST include `lib/seed.js` and at least one
        `app/api/<name>/route.js`.
      • A page that needs BOTH database reads and interactivity is TWO files:
        a "server" page that fetches, plus a "client" component it renders.
        Never plan one file that is both — a second `'use client'` part-way
        down a file is a hard build error.
      • Every route you list in ## Routes must have a matching `page.js` in
        some task. A link to a path with no page file is a 404.
      • SIGN-IN IS NOT A DEFAULT. Plan it only if the brief has people who sign
        in — accounts, roles, "only the manager sees", "members book". A
        catalogue, a landing page, a calculator, a dashboard over public data:
        these have no users, and giving them a login page adds a door to a
        building with nothing behind it. Say so plainly in the plan when there
        is no sign-in, so nothing downstream goes looking for one.
        If the app DOES have sign-in, plan the WHOLE of it — a login page with
        no way to create an account is a dead end, and a signup link pointing
        at a page nobody wrote is a 404. That means BOTH of:
            app/login/page.jsx           app/signup/page.jsx
        and NOTHING else. The API side is generated: /api/auth/sign-in/email,
        /api/auth/sign-up/email, /api/auth/sign-out and /api/auth/get-session
        all exist already. A planned `app/api/auth/login/route.js` would sit on
        top of the real handler and break sign-in outright.
        These two pages are CLIENT components; they call `signIn.email(…)` and
        `signUp.email(…)` from `@/lib/auth-client`.
        Also plan a `## Demo Accounts` entry for every role. The users
        collection is Better Auth's and is called `user` — do not invent your
        own, and do not give it a password field.
        Name the signup route `signup`, and make every link agree with it —
        if the login page links to `/register`, plan `app/register/page.js`.
      • SECURITY IS PART OF THE PLAN, not something added afterwards. For every
        page and every route handler you list, the plan has to be able to
        answer "who may open this, and what happens to everybody else".
          – A section that belongs to one role is guarded on EVERY page in it,
            not just its landing page. `/staff` bouncing a customer while
            `/staff/orders` lets them in is the single most common hole in a
            generated app, and it is invisible from the outside: the page
            renders, so nothing looks wrong.
          – Every route handler that writes checks the session ITSELF. A page
            that hides a button is not a guard — the handler is still one POST
            away for anybody who knows the URL.
          – A handler that acts on a record checks the record BELONGS to the
            caller. `/api/bookings/[id]` that cancels whatever id it is given
            cancels other people's bookings.
          – Never plan a route that takes a role, a price, a total or a user id
            from the request body. Those come from the session and the
            database, or they are whatever the caller says they are.
        Say which role each page is for in its `purpose`. That sentence is what
        the code is written against.
      • QUALITY MEANS THE SCREEN IS FINISHED, not that the file exists. Every
        page in the plan needs: the real data it is about, an empty state worth
        looking at, the actions its role actually performs, and errors the user
        can act on. A page that renders a heading and a table with three
        columns of ids is not done. Plan enough seed data that every screen has
        something real on it — a list with two rows does not show whether the
        list works.
      • `dependencies` must name every real npm package the code will import,
        and nothing else. Already installed, so never list them: react,
        react-dom, next, mongodb, tailwindcss, lucide-react, framer-motion,
        better-auth. Auth needs NOTHING listed — when the app has sign-in,
        `lib/auth.js`, `lib/auth-client.js` and the `/api/auth` handler are
        written for you against better-auth; `bcryptjs` in particular means you
        are rebuilding something that is already there.
        Everything beyond that IS your responsibility. An import of a package nobody installed is a
        runtime crash, so this list is not decoration.
      • A file is written in exactly ONE task. Never plan to rewrite a file.
      • NEVER plan these — they already exist and are managed for you:
        package.json, next.config.mjs, jsconfig.json, tailwind.config.js,
        postcss.config.js, lib/mongodb.js, app/globals.css, .env.local,
        app/api/health/route.js
      • Do NOT write any code in the plan. The plan is prose + the JSON block.

    THE PLAN IS THE SPEC, NOT A SKETCH. Someone else builds from it without
    being able to ask you questions, so it has to be decidable: exact
    collection names and field names, exact file paths, exact route paths,
    exact demo credentials, exact colours. "Some kind of dashboard" is not a
    plan; "app/page.jsx reads `orders` and renders OrderTable" is.
    """)


NEXT_BUILDER_SYSTEM = textwrap.dedent("""\
    You are a senior Next.js engineer implementing an approved plan, working
    straight through the file list without stopping.

    {stack}

    HOW YOU WRITE FILES — you have one tool, `write_file`. Call it by emitting
    this exact syntax, with the complete file between the tags:

    <write_file path="app/tasks/page.jsx">
    import { getCollection, serialize } from '@/lib/mongodb'
    import TaskList from '@/components/TaskList'

    export const dynamic = 'force-dynamic'

    export default async function TasksPage() {
      const col = await getCollection('tasks')
      const tasks = (await col.find({}).toArray()).map(serialize)
      return (
        <main className="p-8">
          <h1 className="text-3xl font-bold mb-6">Tasks</h1>
          <TaskList tasks={tasks} />
        </main>
      )
    }
    </write_file>

    YOUR SECOND TOOL — `run_command`. Use it when you need a package that is
    not installed yet. Emit it BEFORE the file that imports the package:

    <run_command>npm install date-fns</run_command>

    COMMAND RULES:
      • One command per block, no `&&`, no pipes, no redirects — there is no
        shell. Send several blocks if you need several commands.
      • Allowed: npm install / uninstall / ls / why, npx, node.
        Everything else is refused.
      • You will be shown the real output. If an install fails, read the error
        and fix it — do not repeat a command that already succeeded.
      • Do NOT install: react, react-dom, next, mongodb, tailwindcss
        (already present), or react-router-dom / mongoose / prisma / next-auth
        (banned in this stack).

    TOOL RULES:
      • One `<write_file>` block per file. Emit blocks back to back.
      • NEVER put markdown fences (```) inside a block. Raw code only.
      • ALWAYS write the complete file — never "…rest unchanged", never a diff.
      • Keep going down the requested file list, block after block. Stop only
        at a file boundary; you will be told to continue.
      • Between blocks you may write ONE short sentence about what you built.

    IF — AND ONLY IF — THIS APP HAS LOGIN, ACCOUNTS OR ROLES:
    (Skip this whole section for apps with no sign-in. Do not invent auth.)

      A. Install NOTHING for auth. No bcryptjs, no next-auth, no jsonwebtoken.
         Better Auth is already installed and already wired up.
      B. NEVER hash a password yourself and never store one. Better Auth owns
         every credential. A `passwordHash` field anywhere in your code is a
         sign you are rebuilding what is already there — and a hand-written
         hash never matches, so every login fails.
      C. Sign in with `signIn.email({ email, password })` from
         '@/lib/auth-client', in a 'use client' file. Read the session with
         `await getSessionUser()` from '@/lib/auth', in a server file.

         DO NOT WRAP IT. No `lib/session.js`, no `getCurrentUser`, no helper
         that re-exports it under another name. Import `getSessionUser` from
         '@/lib/auth' in every file that needs the session, and nowhere else.

         A wrapper compiles and runs, so nothing catches it until the tests do:
         the mock the harness provides is keyed to the real module, the wrapper
         resolves to `undefined`, calling it throws, your own try/catch turns
         that into a 500, and every case in the file fails as "expected 500 to
         be 401" — which names the wrong problem. Measured on one build: a
         `lib/session.js` exporting `getCurrentUser` was imported by twelve
         route files and cost 32 of 46 failing tests.
      D. NEVER render demo credentials anywhere in the app. No "Demo Accounts"
         panel, no DEMO_ACCOUNTS array in a page or component, no click-to-fill
         buttons, no "Password for all demo accounts: …" line, no defaultValue
         or useState seed on the email or password input. Seed them and stop —
         the tool running this build shows them to the developer. A login
         screen that lists its own passwords is not a login screen.
      E. Sessions are Better Auth's. Do not call `cookies().set(...)` for auth,
         do not invent a cookie name, do not create a `sessions` collection.
      F. Registration is `signUp.email({ email, password, name })`. It already
         rejects a duplicate email and returns `{ error }` — show
         `error.message` on the form.
      I. Build the WHOLE flow or none of it. If there is a login page there is
         a signup page. Both are CLIENT pages calling @/lib/auth-client; there
         are no auth route handlers to write. Every link between them
         must point at a page you actually wrote — a "Sign up" link to a route
         with no `page.js` is a 404 the user hits immediately.
      J. Return 401 for a bad email or password, never 403. 403 means "you are
         known but not allowed"; using it for a failed login makes a wrong
         password indistinguishable from a permissions problem.
      K. NEVER return the user document from a login or register handler —
         `passwordHash` would go straight to the browser. Return only
         `{ id, email, name, role }`.
      L. The login and signup pages are FULL-SCREEN and carry no app chrome —
         no navbar, no sidebar, no footer. A signed-out visitor must not see
         navigation into pages they cannot open. Centre the form on its own
         background: `<main className="min-h-screen flex items-center
         justify-center …">`.
         This works because `app/layout.js` renders ONLY `<html>`, `<body>` and
         `{children}` — never a `<Navbar />`. Pages that want the navbar import
         and render it themselves, exactly like they render any other
         component. Putting it in the root layout is what forces it onto the
         login screen.
      L2. If you rewrite `app/layout.jsx`, KEEP `suppressHydrationWarning` on
         both `<html>` and `<body>`. Browser extensions — Grammarly, QuillBot,
         password managers — add attributes to those two elements before React
         hydrates, and without it every page shows a red "tree hydrated but
         some attributes … didn't match" overlay that has nothing to do with
         the app. Do not put it anywhere else: deeper in the tree it would hide
         real bugs.
      M. Do NOT call `ensureSeeded()` from `app/layout.jsx`. The root layout runs
         on every request, including API calls; seed from the pages that read
         the data.
      G. For roles (RBAC): put `role` on the user document, seed at least one
         of every role, and gate server-side in the route handler — reading the
         session cookie and returning 403 for the wrong role. Hiding a button
         in the UI is not access control.

         On a PAGE, the two failures are separate and must never share a
         branch. Write it as two statements, in this order:

           const user = await getSessionUser()
           if (!user) redirect('/login')              // not signed in
           if (user.role !== 'admin') redirect('/')   // signed in, not allowed

         AND ON EVERY PAGE UNDER IT, not just the section's landing page.
         Next does not inherit guards: a check in `app/admin/page.jsx` says
         nothing about `app/admin/reports/page.jsx`, which is reached by
         typing the URL. Measured across generated apps: a clinic where
         `/reception` correctly bounced a nurse and `/reception/book` — the
         page that creates appointments — answered them 200, and a shop with
         eight `/admin/*` pages of which one was guarded.

         A page that must be interactive stays a SERVER component with the
         guard at the top and puts the interactive part in a child component.
         `'use client'` on the page itself cannot read the session at all, so
         whatever it shows, it shows to anyone.

         NEVER `if (!user || user.role !== 'admin') redirect('/login')`.
         An allowed user with the wrong role would be dropped on the login
         form — which, from where they are sitting, is exactly what a wrong
         password looks like. They log in, bounce straight back to login, and
         report that login is broken. Wrong role goes HOME, never to /login.
      H. Seed enough users that every role can actually be demonstrated.
      O. A FAILED REQUEST MUST SAY SO ON THE SCREEN. Every `fetch` in a client
         component ends in a `catch`, and that catch has one job: put something
         where the user can read it.

           } catch (err) {
             setError(err.message || 'Something went wrong. Please try again.')
           }

         `console.error(err)` alone is not error handling — the console is not
         on the screen. Measured across generated apps: nineteen catch blocks
         that only logged, and the shape that reaches a user is a button that
         does nothing, forever, with no explanation. Read the status too: 401
         means "your session ended, sign in again", 403 means "you do not have
         permission", anything else is "that did not save".

      P. SEED IDEMPOTENTLY. `ensureSeeded()` runs on every cold start, so it
         runs again on every restart. Guard the whole thing:

           if (await ownersCol.countDocuments() > 0) return

         If you upsert instead, match on what IDENTIFIES the row — an email, a
         slug, a name — and never on a timestamp. `{ petId, date, reason }`
         where `date` came from `new Date()` is a different key every run, so
         nothing matches and the whole set is inserted again. Measured: five
         pets sharing eighty-four appointments, the same dog fourteen times on
         one screen.

      N. A ROUTE HANDLER THAT CHANGES AN EXISTING RECORD MUST READ THE SESSION
         FIRST. PUT, PATCH and DELETE always; POST when it goes on to call
         `updateOne`, `updateMany`, `deleteOne`, `deleteMany` or `bulkWrite`:

           export async function PATCH(request, context) {
             const user = await getSessionUser()
             if (!user) return NextResponse.json({ error: 'Sign in first' },
                                                 { status: 401 })
             if (user.role !== 'staff') return NextResponse.json(
               { error: 'Staff only' }, { status: 403 })
             …
           }

         CREATING a record is different and must stay open when the app is
         meant to be open: a contact form, a booking, a review, an order from a
         visitor who has no account. Do NOT put a session check in front of
         those — an app whose contact form demands a login is broken in a way
         no test will catch.

         The line is what the handler does, not the verb alone. Measured across
         thirty-five generated apps: twenty-five route handlers changed records
         that already existed — marking orders collected, adjusting inventory,
         closing shifts, bulk-updating reservations — and not one of them asked
         who was calling. Every other gate passed those apps.

    THE PLAN ALREADY DECIDED server vs client for every file, and it is shown
    in brackets next to each path. Follow it — do not re-decide while writing.
    If a file marked SERVER seems to need `useState`, that is the signal to put
    the interactive part in its own CLIENT component file, not to add a
    directive to the server file.

    THE RULES THAT DECIDE WHETHER THE APP RUNS — obey them exactly:

    1. BEFORE you write any file, decide what it is. Answer this ONE question
       first, and let it decide — never the other way round:

           Does this file await the database, read cookies, or use
           getSessionUser / getCollection / getDb ?

         YES → it is a SERVER file. It has NO 'use client' line. It MAY be
               `export default async function`. Every onClick, onChange,
               onSubmit, useState and useEffect it needs moves OUT into a
               separate file under components/ that starts with 'use client',
               and this file imports and renders that.

         NO  → it MAY be a client file. 'use client' goes on line 1, alone, in
               single quotes, before every import, exactly once. It may NEVER
               be `async`, may NEVER import '@/lib/mongodb', '@/lib/auth',
               '@/lib/seed', 'mongodb', 'bcryptjs' or 'next/headers', and gets
               its data with `fetch('/api/...')`.

       One onClick does NOT make a page a client component. It makes ONE SMALL
       CHILD a client component. A page that reads the database and also has a
       button is TWO files, always.

       A directive part-way down a file is a hard build error:
         "The 'use client' directive must be placed before other expressions".

    2. If the bundler complains that it cannot resolve `fs`, `net`, `tls`,
       `crypto`, `child_process`, `dns` or `timers/promises` — that message is
       telling you a CLIENT file is pulling in server code. Go find the file
       with 'use client' at the top that imports the database or the auth
       helper, and split it per rule 1.

       DO NOT edit next.config.mjs. DO NOT add webpack `resolve.fallback`.
       DO NOT use `await import('next/headers')` to hide a static import.
       DO NOT guard server code with `typeof window === 'undefined'`.
       Every one of those silences the build error and leaves a page that
       returns HTTP 500 on the first request — the bug becomes invisible
       instead of fixed. next.config.mjs, package.json, jsconfig.json,
       tailwind.config.js, postcss.config.js and lib/mongodb.js are generated
       for you and writing to them is refused.

    3. Any `page.js` or `route.js` that imports `@/lib/mongodb` MUST also have
       `export const dynamic = 'force-dynamic'` right after its imports.
       Without it the production build tries to prerender it and FAILS.

    4. AUTHENTICATION IS ALREADY BUILT. Do not write any of it.

       `lib/auth.js`, `lib/auth-client.js` and `app/api/auth/[...all]/route.js`
       are generated by AgentForge and writing to them is REFUSED. They set up
       Better Auth against this project's MongoDB. You never write a session
       cookie, never hash a password, never make a `sessions` collection.

       SERVER — in a page, layout or route handler:

         import { getSessionUser } from '@/lib/auth'
         const user = await getSessionUser()   // null when signed out
         // user.id, user.email, user.name, user.role

       THE SESSION USER HAS `id`, A STRING. THERE IS NO `user._id`.
       Measured on a running app, the object is exactly
       {createdAt, email, emailVerified, id, name, role, updatedAt}.
       `user._id` is undefined, and undefined is silent: every comparison
       against it is false and every document written with it stores nothing.
       Two real failures from one build — `appt.vetId.toString() !== user._id`
       meant no vet could ever record a visit, and `ownerId: user._id` meant a
       registered pet never appeared in its owner's list.

         doc.ownerId?.toString() === user.id        // compare — id is a string
         { ownerId: new ObjectId(user.id) }         // store into an ObjectId column
         { ownerId: user.id }                       // store into a string column

       Pick one and use it everywhere for a given field: a document written
       with `new ObjectId(user.id)` is never found by `find({ownerId: user.id})`.

       CLIENT — in a 'use client' file:

         import { signIn, signUp, signOut, useSession } from '@/lib/auth-client'

         await signIn.email({ email, password })          // login form
         await signUp.email({ email, password, name })    // signup form
         await signOut()                                  // logout button
         const { data: session } = useSession()           // navbar

       Every one of those returns `{ data, error }` — show `error.message` on
       the form rather than throwing.

       The endpoints already exist at /api/auth/*. Do NOT create
       app/api/auth/login, app/api/auth/register, app/api/auth/logout or
       app/api/auth/me. A route you add there would sit on top of the real
       handler and break sign-in outright — even if the plan lists one, skip
       it. There is nothing to write on the API side of auth.

       Hand-rolled sessions are why this app used to break. Every attempt set
       the cookie under one name and read it under another, or stored
       `user.id` from a document that only has `_id`, or looked the session up
       with a string against an ObjectId. All three return 200 from the login
       route and then drop the user straight back on the login form.

    5. EVERY PROP CROSSING INTO A CLIENT COMPONENT IS PLAIN DATA. Strings,
       numbers, booleans, null, arrays and plain objects cross. Functions,
       classes, Dates, ObjectIds and React components do not.

       a) Raw MongoDB documents — always `serialize(doc)` first. `_id` is an
          ObjectId and `createdAt` is a Date, and neither survives the
          boundary.

       b) ICONS. This is the one that breaks dashboards. A server page doing

            import { DollarSign } from 'lucide-react'
            <StatCard title="Revenue" value={total} icon={DollarSign} />

          is passing a FUNCTION, and React answers "Only plain objects can be
          passed to Client Components" — once per card, so a four-stat
          dashboard throws four times and still returns 200.

          Import the icons inside the client component and pass the NAME:

            // components/StatCard.jsx
            'use client'
            import { DollarSign, Package, Users, AlertTriangle } from 'lucide-react'
            const ICONS = { DollarSign, Package, Users, AlertTriangle }
            export default function StatCard({ title, value, icon, color }) {
              const Icon = ICONS[icon] ?? Package
              …
            }

            // app/admin/page.jsx  (server)
            <StatCard title="Revenue" value={total} icon="DollarSign" />

          Rendering the icon on the server and passing it as `children` is the
          other correct answer — a JSX element crosses, a bare component does
          not. Do NOT put 'use client' on the page to make this go away; that
          drags the database query into the browser.

       c) Event handlers. `onSomething={() => …}` in a server component is the
          same error, and `<img onError={…}>` is the one that actually happens.
          Adding a fallback to an image feels careful; in a Server Component it
          is a function crossing the boundary, and the page dies on its first
          render with "Event handlers cannot be passed to Client Component
          props". Measured three times in one project.

          NEVER put onError, onLoad, onClick or any other on* handler on an
          element in a file without 'use client' on line 1.

          For images specifically you do not need a fallback at all: the
          pictures the plan lists are generated into `public/generated/` before
          the app runs, so `/generated/<key>.png` is there. Write a plain
          <img src="/generated/hero.png" alt="…"> and stop.

          If some other element genuinely needs a handler, that element moves
          into its own small 'use client' component — the page does not.

       A component's props are a contract, exactly like its exports. If you
       wrote `function StockAdjustmentForm({ product })`, then every render of
       it says `<StockAdjustmentForm product={p} />` — singular, same spelling.
       Passing `products={products}` to it makes `product` undefined and the
       first `product.name` throws, which is a 500 on a page that compiled
       perfectly. Before you render a component you did not write in this same
       file, re-read its parameter list.

    6. `page.js`, `layout.js` and component files have exactly ONE default
       export. `route.js` files have NO default export — only named handlers:
         export async function GET(request) { ... }
         export async function POST(request) { ... }
       returning `Response.json(data)` or
       `Response.json({ error: 'msg' }, { status: 400 })`.

    7. `params` and `searchParams` are Promises — always await them.
       Next 16 throws where 15 only warned, so this is not optional:
         export default async function Page({ params }) {
           const { id } = await params
         }

    8. Imports you will get wrong unless you check:
         • `import Link from 'next/link'` — use `href=`, NEVER `to=`
         • `import { useRouter, usePathname } from 'next/navigation'`
           — NEVER 'next/router'
         • page titles: `export const metadata = { title: '…' }`
           — NEVER `next/head`. Only in files WITHOUT `'use client'`.

    BANNED — these break the build immediately:
      react-router-dom, a `pages/` directory, _app.js, _document.js,
      getServerSideProps, getStaticProps, next/image, useSearchParams,
      mongoose, prisma, `new MongoClient(...)`, TypeScript syntax of any kind.

    CODE RULES:
      • All imports at the very top. Import every hook, icon and component used.
      • Only import files that already exist or that are on the list you are
        working through.
      • Use the @/ alias for cross-folder imports: '@/components/X', '@/lib/y'.
      • All fetch() URLs are RELATIVE: fetch('/api/tasks').
        NEVER `http://localhost:3000/...`.
      • Icons: `import { Plus, Trash2 } from 'lucide-react'` — verify the name
        is a real lucide icon. When unsure, use an inline <svg> instead.
      • Escape apostrophes in JSX text as &apos; (Don&apos;t, not Don't).
      • Hoist regex literals and any `/` division above the `return`.
      • Tailwind classes only — no styled-components, no extra .css imports.
      • Seeding: `lib/seed.js` exports `ensureSeeded()`.

        `await ensureSeeded()` is the FIRST statement of any page that calls
        it — above the session read, above every `redirect()`. Put it after an
        auth guard and the app deadlocks: on a fresh database nobody is signed
        in, so the first visitor is redirected before the seed runs, and the
        seed is what creates the accounts they would have signed in with. Call
        it from `app/login/page.jsx` too — that is the page a signed-out
        visitor actually lands on:

          export default async function Page() {
            await ensureSeeded()                 // FIRST, always
            const user = await getSessionUser()
            if (!user) redirect('/login')
            …
          }

        DEMO USERS are created through Better Auth, never inserted. Its own
        password hashing is the only thing that produces a hash its login will
        accept, so a direct `users.insertOne({ passwordHash })` gives you an
        account that exists and can never sign in:

          import { auth } from '@/lib/auth'
          for (const u of DEMO_USERS) {
            try {
              await auth.api.signUpEmail({ body: {
                email: u.email, password: u.password, name: u.name } })
            } catch { /* already registered — Better Auth owns identity */ }
          }

        Give a role with one update after sign-up, against the `user`
        collection Better Auth created:

          await (await getCollection('user'))
            .updateOne({ email: u.email }, { $set: { role: u.role } })

        Everything else — products, orders, posts — is seeded normally.

        BANNED, in any spelling: `countDocuments`, `estimatedDocumentCount`,
        `findOne()` used as a "has anything been seeded yet" test, or any
        `if (count === 0)` / `if (count > 0)` / `if (!existing)` gate around
        the insert. Not `=== 0`, not `> 0`, not `< 1`, not a variable holding
        the count. If the word `countDocuments` appears in your seed file you
        have written the bug.

        The ONLY correct shape is one upsert per document, keyed on that
        document's own identity. It runs on every request, so it must be safe
        to call concurrently AND still work after real people have used the
        app:

          let seeding = null
          export async function ensureSeeded() {
            if (!seeding) seeding = doSeed()          // one run per process
            return seeding
          }
          async function doSeed() {
            // Accounts go through Better Auth — it is the only thing that can
            // produce a credential its own sign-in will accept.
            const demoUsers = [ /* built HERE, never module-level */ ]
            for (const u of demoUsers) {
              try {
                await auth.api.signUpEmail({ body: {
                  email: u.email, password: u.password, name: u.name } })
              } catch { /* already registered */ }
              await (await getCollection('user'))
                .updateOne({ email: u.email }, { $set: { role: u.role } })
            }
            const items = await getCollection('items')
            for (const d of [ /* … */ ]) {
              await items.updateOne({ slug: d.slug },
                                    { $setOnInsert: d }, { upsert: true })
            }
          }

        Every page that reads a collection awaits `ensureSeeded()` first.

        Why it must be this and not a count:

          if (await usersCol.countDocuments() > 0) return   // NEVER

        That line looks like it seeds once and stops. What it really does is
        stop the moment ANYONE signs up. The first real user makes the count
        non-zero forever, so the demo accounts are never created — while the
        app still offers them — and every demo login returns 401 from then on.
        The app is correct the day it is built and broken the day it is used.
        This has happened; it is not hypothetical.

        An upsert also solves the concurrency problem the count never did:
        it is atomic per document, so two simultaneous requests cannot
        double-insert and `E11000` cannot occur. And `$setOnInsert`, not
        `$set` — a bcrypt hash differs every time it is computed, so `$set`
        would rewrite it on every cold start and would silently overwrite a
        password a real user had changed.
      • NEVER create a unique index in the seed. Not on sku, not on barcode,
        not on any field except the one Mongo already gives you (`_id`).
        `createIndex({ sku: 1 }, { unique: true })` looks harmless and is the
        single worst line you can write here: the database survives between
        generations, so it will one day meet documents written before that
        field existed. Two of them have `sku: null`, the index build throws
        E11000, `ensureSeeded()` rejects — and because every page awaits it,
        EVERY PAGE RETURNS 500. If you create any index at all, never mark it
        unique.
      • Seed SMALL. Fewer than 5 documents per collection unless the plan
        explicitly says otherwise, and one user per role. A 40-row catalogue
        nobody asked for slows every page, buries the feature under fixtures
        and spends your output budget on data instead of screens.
      • Components must be genuinely functional: working state, handlers,
        validation, empty states, hover/focus states, and responsive layout.
      • Every form input needs BOTH a `placeholder` and a label tied to it:
        `<label htmlFor="email">` with `<input id="email" …>`. A bare <label>
        sitting next to an <input> looks right and is not: nothing associates
        the two, so a screen reader announces an unlabelled field and any test
        that looks the input up by its label finds nothing. Measured across the
        apps generated so far, 51 of 57 labelled forms have this bug.
      • Aim for 80–250 lines per component. Polished, not placeholder.
      • IMAGES the plan listed are generated for you and land in
        `public/generated/<key>.png`. Reference them as
        `/generated/<key>.png` with a plain <img> and a real `alt`. Do NOT
        use next/image, do not invent a key the plan did not list, and do
        not reach for an external placeholder service — the tag points at a
        file that may arrive after you, not at a dead CDN.

    THE DESIGN BAR — ULTRA BEAUTIFUL, PRODUCTION QUALITY.
    This app is judged on how it looks the second it opens. "Functional but
    plain" is a failed build here. Aim for something a designer would ship —
    and get there with these, not with decoration:

      • ONE accent colour from the plan's palette, used for exactly one thing
        per screen: the primary action. Everything else is neutral. A page
        with four competing colours reads as unfinished; a page with one
        confident accent reads as designed.
      • A SPACING RHYTHM, not arbitrary numbers. Stay on 4 / 6 / 8 / 12 / 16
        (p-4, gap-6, mb-8, py-12, px-16). Page padding p-6 md:p-8, card
        padding p-6, section gaps gap-6. Generous whitespace is most of what
        separates expensive-looking from cramped.
      • A TYPE SCALE with real hierarchy: page title text-3xl font-bold
        tracking-tight, section heading text-lg font-semibold, body text-sm,
        supporting text-xs text-slate-500. Never two headings the same size.
        Numbers in a dashboard are the content — text-3xl font-semibold with
        tabular-nums, and their label small and muted above them.
      • DEPTH FROM BORDERS, NOT SHADOWS. `border border-slate-200 rounded-xl
        bg-white` is the default card. Add `shadow-sm` at most; reserve
        `shadow-lg` for something that genuinely floats — a modal, a dropdown.
        Heavy drop shadows everywhere is the single clearest tell of a
        generated UI.
      • EVERY INTERACTIVE ELEMENT HAS FOUR STATES, always written out:
        rest, `hover:`, `focus-visible:ring-2 focus-visible:ring-offset-2`,
        and `disabled:opacity-50 disabled:cursor-not-allowed`. Add
        `transition-colors duration-150`. A button with no hover is the
        cheapest possible thing to fix and the most obvious thing to miss.
      • EMPTY, LOADING AND ERROR STATES ARE PART OF THE DESIGN. An empty list
        gets a centred block: a muted icon, one line saying what goes here,
        and the button that creates the first one. Never render a bare "No
        data". A pending action shows a disabled button with its verb in the
        present tense ("Saving…").
      • RESPONSIVE FROM THE FIRST LINE, mobile up: `grid grid-cols-1
        md:grid-cols-2 lg:grid-cols-4 gap-6`. A table that cannot shrink goes
        in `overflow-x-auto`. Nothing may overflow the viewport at 375px.
      • ALIGNMENT AND CONSISTENCY. The same kind of thing looks the same
        everywhere — every card the same radius, every button the same height
        (h-10 px-4 text-sm font-medium rounded-lg), every icon the same size
        (w-4 h-4 beside text, w-5 h-5 alone). Inconsistency reads as
        carelessness even when nobody can name what is wrong.
      • Icons are punctuation, not decoration: one per action or stat, never
        one per line of text.

    What NOT to do: rainbow gradients on everything, emoji as UI icons,
    `text-center` on body copy, five font weights, animated backgrounds,
    `shadow-2xl` on a list row. Restraint is what reads as quality.
    """)


PROMPTS = {
    "vite": {
        "rules":   VITE_STACK_RULES,
        "planner": VITE_PLANNER_SYSTEM,
        "builder": VITE_BUILDER_SYSTEM,
        "roots":   ("src/",),
        "entry":   ("src/App.jsx", "src/App.js"),
    },
    "next": {
        "rules":   NEXT_STACK_RULES,
        "planner": NEXT_PLANNER_SYSTEM,
        "builder": NEXT_BUILDER_SYSTEM,
        "roots":   ("app/", "components/", "lib/"),
        "entry":   ("app/page.js", "app/page.jsx"),
    },
}


class ArchitectAgent:
    """
    Emits everything through injected callbacks so the transport (WebSocket)
    stays in server.py.

    Callbacks (all optional):
      on_log(level, text)          on_phase(payload)
      on_chat(text)                on_file_start(path)
      on_file_token(path, token)   on_file_end(path, content)
      on_file_written(path, size, content)
      on_progress(label, pct)
    """

    def __init__(self, client: OllamaClient, model: str, project_dir: Path,
                 callbacks: dict = None, stack: str = "next",
                 mongo_uri: str = "", db_name: str = "", dev_port: int = 5173,
                 think: bool = None):
        self.client = client
        self.model = model
        self.project_dir = Path(project_dir)
        self.cb = callbacks or {}
        self.stack = stack if stack in PROMPTS else "next"
        self.mongo_uri = mongo_uri
        self.db_name = db_name

        self.dev_port = dev_port
        self.files = {}

        self.write_seq = 0

        self._scaffolding = False
        self.plan = {}
        self.plan_md = ""
        self.tokens_in = 0
        self.tokens_out = 0

        self.convo = []

        self._last_truncated = None

        self._refused = {}
        self.num_ctx = max_context(model)
        self.is_cloud = is_cloud_model(model)

        self.think = think

        self.cmd = CommandRunner(
            self.project_dir,
            npm_bin=(self.cb or {}).get("npm_bin", "npm"),
            node_bin=(self.cb or {}).get("node_bin", "node"),
            on_log=lambda lvl, txt: self._fire("on_log", lvl, txt),
            on_event=lambda ev: self._fire("on_command", ev))

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn:
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):

        if self.cb and self.cb.get("on_log"):
            self._fire("on_log", lvl, txt)
            return
        log.info(txt)

    @property
    def _P(self) -> dict:
        return PROMPTS[self.stack]

    def _builder_sys(self) -> str:
        base = self._P["builder"].replace("{stack}", self._P["rules"])

        idx = (docsindex.index_block(self.project_dir)
               if self.stack == "next" else "")
        if not idx:
            return base
        return base + "\n\n    NEXT.JS DOCUMENTATION — READ IT:\n" + idx

    def _planner_sys(self) -> str:
        return self._P["planner"].replace("{stack}", self._P["rules"])

    @property
    def source_roots(self) -> tuple:
        return self._P["roots"]

    def is_source(self, path: str) -> bool:
        return path.startswith(self.source_roots) and path.endswith((".jsx", ".js"))

    EDIT_TIMEOUT = 150

    def _stream(self, messages, on_delta, tools=None, temperature=0.6,
                model=None, timeout=None):
        """
        Stream a chat completion. `on_delta(text)` gets content deltas.
        Native tool_calls are collected and returned as a list.

        `model` overrides the build model for one call. The pencil tool needs
        this: the selected model often has no vision capability, so a
        vision-capable one is borrowed for the single request that carries an
        image.
        """
        tool_calls, thought = [], False
        options = {"temperature": temperature, "top_p": 0.9,
                   "num_ctx": self.num_ctx}
        kw = {"timeout": timeout} if timeout else {}
        started = time.time()
        spoke = started
        thinks = 0
        chars = 0
        chunks = 0
        first_at = 0.0
        for chunk in self.client.chat_stream(
                model or self.model, messages, tools=tools, options=options,
                keep_alive="10m", think=self.think, **kw):
            msg = chunk.get("message") or {}

            if msg.get("thinking"):
                thinks += 1
                if not thought:
                    thought = True
                    self._log("INFO", "   🤔 Thinking…")

            delta = msg.get("content") or ""
            if delta:
                chars += len(delta)
                if not first_at:
                    first_at = time.time()
            now = time.time()
            if now - spoke >= 30:
                spoke = now
                elapsed = now - started
                if chars:
                    wrote = f"{chars:,} characters written"
                elif thinks:
                    wrote = f"thinking, {thinks:,} token(s), nothing written yet"
                else:

                    wrote = (f"{chunks:,} empty chunk(s) — the model has sent "
                             f"nothing usable yet")
                self._log("INFO", f"   ⏳ still working — {elapsed:.0f}s, {wrote}")
            chunks += 1
            if delta:
                on_delta(delta)
            for tc in (msg.get("tool_calls") or []):
                tool_calls.append(tc)
            if chunk.get("done"):
                self.tokens_in += chunk.get("prompt_eval_count", 0) or 0
                self.tokens_out += chunk.get("eval_count", 0) or 0
        return tool_calls

    def start_conversation(self, user_prompt: str):
        """Open the single chat thread the whole build runs in."""
        self.convo = [
            {"role": "system", "content": self._builder_sys()},
            {"role": "user", "content": textwrap.dedent(f"""\
                We are building this app together, in one continuous pass.

                ## The idea
                {user_prompt}

                ## The approved plan
                {self.plan_md}

                In a moment I will give you the whole build broken into
                numbered tasks. You write ONE task at a time and stop; I will
                say "Continue task 2", and so on to the end — I will never ask
                you to start over. Remember every file you write: later tasks
                import from them and must stay consistent with the naming,
                styling and data shapes you have already used. Do not write any
                code yet.
                """)},
            {"role": "assistant", "content":
                "Understood. I have the plan and I will keep track of every "
                "file I write. Send me the tasks and I will finish them one at "
                "a time."},
        ]

    def _convo_chars(self) -> int:
        return sum(len(m.get("content") or "") for m in self.convo)

    def _budget_chars(self) -> int:
        return int(self.num_ctx * HISTORY_BUDGET * CHARS_PER_TOKEN)

    @staticmethod
    def _stub_files(text: str) -> str:
        """
        Replace written-out file bodies with a one-line receipt.

        The model still remembers *what* it created and where, it just stops
        re-reading its own source. Current file contents are re-injected from
        disk when a later phase actually needs them.
        """
        def repl(m):
            path = m.group(2)
            lines = m.group(3).count("\n") + 1
            return (f'<write_file path="{path}">'
                    f'\n// [written earlier — {lines} lines, still on disk]\n'
                    f'</{m.group(1)}>')

        return re.sub(r"<(write_file|file)\s+path\s*=\s*[\"']([^\"'>]+)[\"']\s*>"
                      r"(.*?)</\1>", repl, text, flags=re.S | re.I)

    @staticmethod
    def _strip_snapshot(text: str) -> str:
        """
        Take the fenced current-source block back out.

        A snapshot is worth everything for the turn it is attached to and worse
        than nothing after it. `_stub_files` only ever touched assistant turns,
        so these blocks — which are USER turns — survived into `convo.json`
        untouched and were replayed by `FeaturesAgent._memory()` at every later
        edit under "this is how we built this app together". The model then had
        two versions of the same file in front of it, one current and one
        weeks old, with nothing to say which was which.
        """
        return SNAPSHOT_RE.sub(
            "(source snapshot removed — re-read the files from disk)", text)

    def _trim_convo(self):
        """
        Keep the thread inside the context window.

        Cloud models have room for the whole build, so this is usually a no-op
        there. Local models compact oldest-first: full bodies → receipts, then
        drop the oldest turns entirely if still over budget.
        """
        budget = self._budget_chars()
        if self._convo_chars() <= budget:
            return

        for i in range(3, len(self.convo) - 1):
            stripped = self._strip_snapshot(self.convo[i]["content"])
            if stripped != self.convo[i]["content"]:
                self.convo[i]["content"] = stripped
                if self._convo_chars() <= budget:
                    self._log("INFO", "   🧠 Dropped an old source snapshot "
                                      "from memory")
                    return

        for i in range(3, len(self.convo) - 1):
            if self.convo[i]["role"] != "assistant":
                continue
            stubbed = self._stub_files(self.convo[i]["content"])
            if stubbed != self.convo[i]["content"]:
                self.convo[i]["content"] = stubbed
                if self._convo_chars() <= budget:
                    self._log("INFO", "   🧠 Compacted older code out of memory")
                    return

        dropped = 0
        while self._convo_chars() > budget and len(self.convo) > 5:
            self.convo.pop(3)
            dropped += 1
        if dropped:
            self._log("INFO", f"   🧠 Dropped {dropped} old turn(s) from memory")

        if self._convo_chars() > budget:
            preamble = sum(len(m["content"]) for m in self.convo[:3])
            self._log("WARN",
                      f"   🧠 Context is tight: {self._convo_chars():,} chars "
                      f"vs a {budget:,} budget "
                      f"({preamble:,} of it is the prompt and plan). "
                      f"A larger model, or a bigger local context window in "
                      f"Settings, would give the agent more room.")

    def memory_stats(self) -> dict:
        chars = self._convo_chars()
        return {
            "turns": len(self.convo),
            "approx_tokens": int(chars / CHARS_PER_TOKEN),
            "num_ctx": self.num_ctx,
            "cloud": self.is_cloud,
        }

    def _safe_path(self, rel: str) -> Path:
        """Normalise and confine a model-supplied path to the project dir."""
        rel = (rel or "").strip().strip("/\\").replace("\\", "/")
        rel = re.sub(r"^\./", "", rel)
        parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
        if not parts:
            raise ValueError("empty path")
        return self.project_dir / "/".join(parts)

    JS_ONLY_RE = re.compile(r"^(lib/|app/(.+/)?route\.jsx?$)")
    JSX_ROLE_RE = re.compile(
        r"^(components/|app/(.+/)?"
        r"(page|layout|template|loading|error|global-error|not-found|default)\.jsx?$)")

    @classmethod
    def canonical_path(cls, key: str) -> str:
        """
        `key` with the extension its role requires, or `key` unchanged.

        JSX lives in pages, layouts and components; route handlers and lib
        modules are plain modules that never contain a tag. Anything else —
        config, css, json, markdown — is left alone.
        """
        if not key.endswith((".js", ".jsx")):
            return key
        stem = key[:-4] if key.endswith(".jsx") else key[:-3]
        if cls.JS_ONLY_RE.match(key):
            return stem + ".js"
        if cls.JSX_ROLE_RE.match(key):
            return stem + ".jsx"
        return key

    def _drop_tests_for(self, key: str, content: str) -> None:
        """
        A file just lost its exports. Take its tests with it.

        Removing a component is a legitimate repair — "nothing imported
        SiteNav, so it was replaced with a comment explaining why" is a real
        and correct fix. What is not correct is leaving nine tests pointed at
        it. They cannot pass, no repair can make them honest, they burn every
        round of the QA loop, and the file is set aside at the end as a silent
        loss of cases. Measured on one build: exactly that, nine of them.

        The manifest is the authority on which test belongs to which file, and
        it is on disk, so this needs no reference to the QA session. Reading it
        costs one file read on the rare write that empties a component.
        """
        if not key.endswith((".jsx", ".js")):
            return
        if key.startswith(("tests/", "app/api/")):
            return

        if re.search(r"^\s*export\b", content, re.M):
            return

        manifest_path = self.project_dir / ".agentforge" / "qa" / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return
        doomed = [t for t, meta in manifest.items()
                  if (meta or {}).get("target") == key]
        if not doomed:
            return

        for test_path in doomed:
            try:
                (self.project_dir / test_path).unlink(missing_ok=True)
            except OSError as e:
                log.debug(f"drop {test_path}: {e}")
                continue
            manifest.pop(test_path, None)
            self.files.pop(test_path, None)
            self._log("INFO", f"   🗑 {test_path} — {key} no longer exports "
                              f"anything, so its tests went with it")
        try:
            manifest_path.write_text(json.dumps(manifest, indent=2),
                                     encoding="utf-8")
        except OSError as e:
            log.debug(f"manifest after drop: {e}")

    REFUSE_SAME_PATH = 3
    REFUSE_TOTAL = 10

    def _stuck_on_refusals(self) -> bool:
        counts = [v["n"] for v in self._refused.values()]
        return (bool(counts) and (max(counts) >= self.REFUSE_SAME_PATH
                                  or sum(counts) >= self.REFUSE_TOTAL))

    def _refusal_note(self) -> str:
        """
        What was refused this turn, said once, for the next turn to read.

        The whole reason the loop was possible is that this never existed: a
        refusal was a log line, and the model reads its own output, not ours.
        """
        if not self._refused:
            return ""
        lines = [f"  {path} — {v['why']}"
                 for path, v in list(self._refused.items())[:12]]
        return ("\n\nThese writes were REFUSED and are not on disk. Writing "
                "them again will be refused again — do not retry them, and do "
                "not write anything else under the same paths:\n"
                + "\n".join(lines))

    def _refuse(self, key: str, why: str) -> bool:
        """
        Say no to a write, out loud, and remember that we did.

        Every guard in `write_file` used to `return False` and log a line the
        model never sees. From inside the stream a refusal is invisible: the
        block was emitted, nothing came back, so the model writes it again.
        Measured on a real build — 3,832 refused writes, the same eleven
        `app/api/auth/*` paths cycling for over twelve minutes in a single
        turn, and the build never finished.

        So the refusal is recorded here and `_run_write_loop` does two things
        with it: stops the turn once the model is plainly stuck, and tells it
        what was refused and why before the next one.
        """
        self._log("WARN", f"   ⛔ {key} {why}")
        seen = self._refused.setdefault(key, {"n": 0, "why": why})
        seen["n"] += 1
        return False

    def write_file(self, rel: str, content: str) -> bool:
        try:
            fp = self._safe_path(rel)
            key0 = str(fp.relative_to(self.project_dir)).replace("\\", "/")

            if self.stack == "next" and key0 not in self.files:
                canon = self.canonical_path(key0)
                if canon != key0:
                    self._log("INFO", f"   ↪ {key0} → {canon}")
                    fp = self._safe_path(canon)
                    key0 = canon

                twin = (key0[:-4] + ".js" if key0.endswith(".jsx")
                        else key0[:-3] + ".jsx")
                tp = self.project_dir / twin
                if tp.is_file():
                    try:
                        tp.unlink()
                        self.files.pop(twin, None)
                        self._log("WARN", f"   🗑 removed the shadowed {twin}")
                    except Exception as e:
                        self._log("WARN", f"   could not remove {twin}: {e}")

            if (self.stack == "next" and not self._scaffolding
                    and key0.startswith("app/api/auth/")
                    and not key0.startswith("app/api/auth/[")
                    and "app/api/auth/[...all]/route.js" in self.files):
                return self._refuse(
                    key0, "would shadow the generated /api/auth handler — auth "
                          "is already built, use signIn.email / getSessionUser "
                          "instead")

            if (self.stack == "next" and not self._scaffolding
                    and key0.startswith("app/") and key0.endswith((".jsx", ".js"))
                    and re.search(r"^\s*['\"]use client['\"]", content, re.M)
                    and re.search(r"from\s+['\"]@/lib/auth['\"]", content)):
                return self._refuse(key0, f"is a client component and imports "
                          f"`@/lib/auth`, which cannot run in a browser — it "
                          f"brings the MongoDB driver with it and the build "
                          f"fails on 'tls'. Read the session in a SERVER page "
                          f"and pass what it needs to a client child, or use "
                          f"`useSession()` from `@/lib/auth-client`.")

            if (self.stack == "next" and not self._scaffolding
                    and key0.startswith("app/")
                    and re.search(r"""['"]/api/auth/me['"]""", content)):
                return self._refuse(key0, f"fetches `/api/auth/me`, which Better "
                          f"Auth does not serve — it answers 404 and the page "
                          f"sends everyone to /login. The session endpoint is "
                          f"`/api/auth/get-session`, and from a client "
                          f"component `useSession()` is better than fetching "
                          f"at all.")

            if (self.stack == "next" and not self._scaffolding
                    and key0 in ("middleware.js", "middleware.ts")):
                if any((self.project_dir / f"proxy{e}").is_file()
                       or f"proxy{e}" in self.files for e in (".js", ".ts")):
                    return self._refuse(key0, f"— Next 16 uses proxy.js, and "
                              f"having both is a startup error, not a "
                              f"compatibility shim. proxy.js is already there; "
                              f"put the logic in that.")
            if (self.stack == "next" and key0 in ("proxy.js", "proxy.ts")):
                for ext in (".js", ".ts"):
                    mw = self.project_dir / f"middleware{ext}"
                    if mw.is_file():
                        try:
                            mw.unlink()
                            self.files.pop(f"middleware{ext}", None)
                            self._log("WARN", f"   🗑 removed middleware{ext} — "
                                              f"Next 16 refuses to start with "
                                              f"both it and proxy.js")
                        except Exception as e:
                            self._log("WARN", f"   could not remove "
                                              f"middleware{ext}: {e}")

            if (self.stack == "next" and not self._scaffolding
                    and key0.startswith("app/")):
                folder = key0.rsplit("/", 1)[0]
                name = key0.rsplit("/", 1)[-1]
                twins = {"route.js": ("page.jsx", "page.js"),
                         "route.jsx": ("page.jsx", "page.js"),
                         "page.jsx": ("route.js", "route.ts"),
                         "page.js": ("route.js", "route.ts")}.get(name, ())
                clash = next((f"{folder}/{t}" for t in twins
                              if f"{folder}/{t}" in self.files
                              or (self.project_dir / folder / t).is_file()), "")
                if clash:
                    kind = "route handler" if name.startswith("route") else "page"
                    return self._refuse(key0, f"cannot be a {kind}: {clash} is "
                              f"already there, and Next refuses a segment that "
                              f"is both — it fails to compile and the URL 404s. "
                              f"Put the handler one level down, at "
                              f"{folder}/api/route.js, or use a Server Action.")

            if (self.stack == "next" and not self._scaffolding
                    and self.canonical_path(key0) in self.NEXT_PROTECTED):

                return self._refuse(key0, f"is generated by AgentForge and "
                                  f"cannot be edited — fix the file that "
                                  f"actually has the problem")
            content = _strip_fence(content).rstrip() + "\n"
            content = _fix_doubled_tags(content)

            if (self.stack == "next" and key0 in ("app/layout.jsx", "app/layout.js")
                    and "globals.css" not in content):
                content = "import './globals.css'\n" + content.lstrip("\n")
                self._log("WARN", "   🔧 app/layout — put back "
                                  "`import './globals.css'`; without it the "
                                  "whole app renders unstyled and every check "
                                  "still passes")

            if self.stack == "next":
                content = self._drop_layout_duplicates(key0, content)

            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content, encoding="utf-8")
            key = str(fp.relative_to(self.project_dir)).replace("\\", "/")
            self.files[key] = content

            self.write_seq = getattr(self, "write_seq", 0) + 1
            size = (f"{len(content) / 1024:.1f}KB" if len(content) >= 1024
                    else f"{len(content)}B")
            self._fire("on_file_written", key, size, content)
            self._log("INFO", f"   📝 {key}  ({size})")
            self._drop_tests_for(key, content)
            return True
        except Exception as e:
            self._log("ERROR", f"   ❌ write failed {rel}: {e}")
            return False

    PUBLIC_AREAS = frozenset({
        "login", "signup", "register", "auth", "about", "contact", "products",
        "shop", "catalogue", "catalog", "sessions", "classes", "tools",
        "browse", "search", "cart", "checkout"})

    def _roles_without_areas(self, plan):
        """
        `(roles, areas)` when a plan has fewer signed-in areas than roles.

        Counted structurally rather than by name: matching section names to
        role names calls `/admin` a miss for a role called `super_admin`, and
        a shop's `customer` legitimately lives on the public pages. What is
        never right is three roles sharing one area — that is the shape where
        the plan has quietly become a single dashboard with an `if` in it.

        One role is allowed to have no area of its own, because that case is
        real and common: a shop's `customer` browses `/products` and `/cart`
        like anyone else. Requiring an area for every role flagged two shops
        that were correctly built — a `/pos` for the cashier and the public
        pages for the customer — so the bar is `roles - 1`.

        Measured across the plans on disk: two of the fifteen with three or
        more roles are flagged, and the thirteen that are fine pass untouched.
        The one this exists for gave three roles a single `/dashboard`.
        """
        roles = {a.get("role", "").lower()
                 for a in (plan.get("demo_accounts") or [])
                 if isinstance(a, dict) and a.get("role")}
        if len(roles) < 3:
            return None
        pages = [f if isinstance(f, str) else (f or {}).get("path", "")
                 for ph in plan.get("phases", []) for f in ph.get("files", [])]
        areas = {p[4:].split("/")[0] for p in pages
                 if p.endswith(("page.jsx", "page.js"))
                 and p.startswith("app/") and p[4:].count("/") >= 1}
        areas -= self.PUBLIC_AREAS
        return (roles, areas) if len(areas) < len(roles) - 1 else None

    def make_plan(self, user_prompt: str) -> bool:
        self._log("INFO", "🧭 Planning — writing plan.md")
        self._fire("on_phase", {"phase": 0, "title": "Planning",
                                "status": "active"})
        self._fire("on_file_start", "plan.md")

        # The requirement ids that actually exist, taken from the brief the
        # planner is about to be shown. `covers` is checked against these
        # because a planner asked to cite ids will invent ones that run past
        # the end of the list — measured on a real run: a 33-requirement SRS
        # came back with tasks citing FR-035, FR-036 and FR-037.
        self._known_fr = set(re.findall(r"\bFR-\d+\b", user_prompt or ""))

        messages = [
            {"role": "system",
             "content": self._planner_sys()},
            {"role": "user",
             "content": f"App idea:\n\n{user_prompt}\n\n"
                        "Write the plan now."},
        ]

        buf = []

        def on_delta(t):
            buf.append(t)
            self._fire("on_file_token", "plan.md", t)

        try:
            self._stream(messages, on_delta, temperature=0.7)
        except Exception as e:
            self._log("ERROR", f"   ❌ Planner failed: {e}")
            return False

        raw = "".join(buf)
        self.plan = self._extract_plan_json(raw)
        if not self.plan.get("phases"):
            self._log("WARN", "   ⚠ No usable JSON plan — using a default phase map")
            self.plan = self._fallback_plan(user_prompt)

        short = self._roles_without_areas(self.plan)
        if short:
            roles, areas = short
            self._log("WARN", f"   ⚠ the plan gives {len(roles)} role(s) only "
                              f"{len(areas)} area(s) — asking for one per role")
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content":
                    f"This plan has {len(roles)} roles — "
                    f"{', '.join(sorted(roles))} — and only "
                    f"{len(areas)} signed-in area"
                    f"{'' if len(areas) == 1 else 's'}"
                    + (f" ({', '.join(sorted(areas))})" if areas else "")
                    + ". Every role needs its own route prefix, and each screen "
                      "the request describes for a role belongs at its own route "
                      "under that prefix — not as a tab inside a shared page. "
                      "Rewrite the plan with a section per role, keeping "
                      "everything else you already decided. Emit the whole plan "
                      "again, including the JSON block."},
            ]
            buf2 = []
            try:
                self._stream(messages, buf2.append, temperature=0.7)
                again = self._extract_plan_json("".join(buf2))

                if again.get("phases") and not self._roles_without_areas(again):
                    self.plan, raw = again, "".join(buf2)
                    self._log("INFO", "   ✅ replanned with a section per role")
                else:
                    self._log("WARN", "   ⚠ the replan did not add them — "
                                      "keeping the first plan")
            except Exception as e:
                self._log("WARN", f"   ⚠ replan failed: {e}")

        self.plan_md = re.sub(r"```json.*?```", "", raw, flags=re.S).strip()
        self._fire("on_file_end", "plan.md", self.plan_md)
        self.write_file("plan.md", self.plan_md)
        self._save_plan_json()

        n = len(self.plan["phases"])
        self._log("INFO", f"   ✅ Plan ready — {n} tasks, "
                          f"{sum(len(p.get('files', [])) for p in self.plan['phases'])} files")

        self.start_conversation(user_prompt)

        self.save_convo()

        self._fire("on_phase", {"phase": 0, "title": "Planning",
                                "status": "done", "plan": self.plan})
        return True

    def _extract_plan_json(self, raw: str) -> dict:
        blocks = re.findall(r"```json\s*(.*?)```", raw, re.S)
        blocks += re.findall(r"```\s*(\{.*?\})\s*```", raw, re.S)
        for b in reversed(blocks):
            try:
                data = json.loads(b.strip())
                if isinstance(data, dict) and (data.get("tasks")
                                               or data.get("phases")):
                    return self._normalise_plan(data)
            except json.JSONDecodeError:
                continue

        i, j = raw.find("{"), raw.rfind("}")
        if i >= 0 and j > i:
            try:
                data = json.loads(raw[i:j + 1])
                if isinstance(data, dict) and (data.get("tasks")
                                               or data.get("phases")):
                    return self._normalise_plan(data)
            except json.JSONDecodeError:
                pass
        return {}

    def _normalise_plan(self, data: dict) -> dict:

        phases = []
        for i, p in enumerate(data.get("tasks") or data.get("phases") or [],
                              start=1):
            if not isinstance(p, dict):
                continue
            files = []
            for f in p.get("files", []):
                if isinstance(f, str):
                    files.append({"path": f, "purpose": "",
                                  "kind": self._infer_kind(f)})
                elif isinstance(f, dict) and f.get("path"):
                    kind = str(f.get("kind", "")).strip().lower()
                    if kind not in ("server", "client", "route"):
                        kind = self._infer_kind(f["path"])
                    files.append({"path": f["path"],
                                  "purpose": f.get("purpose", ""),
                                  "kind": kind})

            raw = p.get("covers") or []
            if isinstance(raw, str):
                raw = re.split(r"[,;]\s*|\s+", raw)
            covers = [str(c).strip() for c in raw if str(c).strip()]

            # An id that is in no brief is not a requirement, it is a number
            # the planner made up. Keeping it would put fiction in plan.json
            # and print it next to real ids on the turn that writes the files.
            known = getattr(self, "_known_fr", None)
            if known:
                invented = [c for c in covers if c.upper().startswith("FR-")
                            and c.upper() not in known]
                if invented:
                    covers = [c for c in covers if c not in invented]
                    self._log("INFO", "   ⚠ dropped invented requirement ids "
                                      f"from a task: {', '.join(invented)}")
            phases.append({
                "id": p.get("id", i),
                "title": p.get("title", f"Task {i}"),
                "goal": p.get("goal", ""),
                "done_when": p.get("done_when", ""),
                "covers": covers,
                "files": files,
            })
        data["phases"] = [p for p in phases if p["files"]]

        if data["phases"]:
            planned = {f["path"] for p in data["phases"] for f in p["files"]}
            if not planned & {"app/page.jsx", "app/page.js"}:
                data["phases"][0]["files"].insert(0, {
                    "path": "app/page.jsx",
                    "purpose": "The home page — the first thing anyone sees. "
                               "AgentForge scaffolds a placeholder here that says "
                               "'Building…'; this replaces it.",
                    "kind": "server"})
                self._log("WARN", "   📋 The plan did not include app/page.jsx "
                                  "— added it, or the app would ship the "
                                  "'Building…' placeholder as its home page")

        deps = [d for d in data.get("dependencies", []) if isinstance(d, str)]
        data["dependencies"] = deps

        images = []
        for im in data.get("images") or []:
            if isinstance(im, dict) and im.get("prompt"):
                images.append({
                    "key": re.sub(r"[^a-z0-9-]+", "-",
                                  str(im.get("key") or "image").lower()).strip("-")
                           or "image",
                    "prompt": str(im["prompt"])[:400],
                    "aspect": str(im.get("aspect", "landscape")).lower(),
                })

        seen, unique = set(), []
        for im in images:
            if im["key"] in seen:
                continue
            seen.add(im["key"])
            unique.append(im)
        data["images"] = unique[:12]

        accounts = []
        for a in data.get("demo_accounts") or []:
            if isinstance(a, dict) and a.get("email") and a.get("password"):
                accounts.append({"email": a["email"], "password": a["password"],
                                 "role": a.get("role", "user")})
        data["demo_accounts"] = accounts
        return data

    @staticmethod
    def _infer_kind(path: str) -> str:
        """Fallback when the plan omits `kind` — route handlers are obvious,
        everything else is assumed server until the code says otherwise."""
        if re.match(r"^app/.*route\.jsx?$", path or ""):
            return "route"
        return "server"

    def _fallback_plan(self, user_prompt: str) -> dict:
        name = re.sub(r"[^a-z0-9]+", "-", user_prompt.lower()).strip("-")[:24]
        base = {
            "project_name": name or "app",
            "title": user_prompt[:60],
            "description": user_prompt[:160],
        }
        if self.stack == "vite":
            return {**base,
                    "dependencies": ["react-router-dom", "framer-motion", "lucide-react"],
                    "phases": [
                        {"id": 1, "title": "App shell & routing", "goal":
                         "Router, layout, navigation, theme context",
                         "files": [{"path": "src/App.jsx", "purpose": "router shell"},
                                   {"path": "src/components/Layout.jsx", "purpose": "nav + shell"}]},
                        {"id": 2, "title": "Core screens", "goal":
                         "The main functional pages of the app",
                         "files": [{"path": "src/pages/Home.jsx", "purpose": "main screen"}]},
                        {"id": 3, "title": "State & persistence", "goal":
                         "Context store persisted to localStorage",
                         "files": [{"path": "src/store/AppContext.jsx", "purpose": "global state"}]},
                        {"id": 4, "title": "Polish", "goal":
                         "Empty states, animation, responsive pass",
                         "files": [{"path": "src/components/EmptyState.jsx", "purpose": "empty states"}]},
                    ]}
        return {**base,
                "dependencies": ["lucide-react", "framer-motion", "date-fns"],
                "phases": [
                    {"id": 1, "title": "Shell, theme & seed data", "goal":
                     "Layout, navigation, and demo data in MongoDB",
                     "files": [{"path": "app/layout.jsx", "purpose": "shell + nav"},
                               {"path": "lib/seed.js", "purpose": "idempotent demo data"},
                               {"path": "components/Nav.js", "purpose": "navigation"}]},
                    {"id": 2, "title": "Main dashboard", "goal":
                     "The primary screen, reading from MongoDB",
                     "files": [{"path": "app/page.jsx", "purpose": "dashboard"},
                               {"path": "components/ItemCard.js", "purpose": "record card"}]},
                    {"id": 3, "title": "CRUD API & detail route", "goal":
                     "Route handlers plus a per-record page",
                     "files": [{"path": "app/api/items/route.js", "purpose": "GET/POST"},
                               {"path": "app/items/[id]/page.js", "purpose": "detail view"}]},
                    {"id": 4, "title": "Create & edit flow", "goal":
                     "Forms that write to the database",
                     "files": [{"path": "app/items/new/page.js", "purpose": "create form"},
                               {"path": "components/ItemForm.js", "purpose": "form component"}]},
                    {"id": 5, "title": "Polish", "goal":
                     "Empty states, animation, responsive pass",
                     "files": [{"path": "components/EmptyState.js", "purpose": "empty states"},
                               {"path": "app/not-found.js", "purpose": "404 page"}]},
                ]}

    VITE_EXTRA_DEPS = {
        "react-router-dom": "^6.26.2",
        "framer-motion": "^11.5.4",
        "lucide-react": "^0.441.0",
        "react-icons": "^5.3.0",
        "recharts": "^2.12.7",
        "date-fns": "^3.6.0",
        "clsx": "^2.1.1",
        "uuid": "^10.0.0",
        "zustand": "^4.5.5",
        "react-hot-toast": "^2.4.1",
    }

    NEXT_EXTRA_DEPS = {
        "framer-motion": "^11.5.4",
        "lucide-react": "^0.441.0",
        "react-icons": "^5.3.0",
        "recharts": "^2.12.7",
        "date-fns": "^3.6.0",
        "dayjs": "^1.11.13",
        "clsx": "^2.1.1",
        "uuid": "^10.0.0",
        "nanoid": "^5.0.7",
        "slugify": "^1.6.6",
        "zod": "^3.23.8",
        "swr": "^2.2.5",
        "react-hot-toast": "^2.4.1",
        "react-hook-form": "^7.53.0",
        "zustand": "^4.5.5",

        "bcryptjs": "^2.4.3",
    }

    NEXT_BANNED_DEPS = {"react-router-dom", "vite", "@vitejs/plugin-react",
                        "mongoose", "prisma", "@prisma/client", "express",
                        "next-auth"}
    VITE_BANNED_DEPS = {"next", "mongodb", "mongoose", "prisma",
                        "@prisma/client", "express", "next-auth"}

    @property
    def BANNED_DEPS(self) -> set:
        return (self.VITE_BANNED_DEPS if self.stack == "vite"
                else self.NEXT_BANNED_DEPS)

    NEXT_SCAFFOLD = frozenset({
        "package.json", "next.config.mjs", "jsconfig.json",
        "tailwind.config.js", "postcss.config.js", "app/globals.css",
        "app/layout.jsx", "app/page.jsx", "lib/mongodb.js",
        "app/api/health/route.js", ".env.local", ".gitignore",
        "AGENTS.md", "CLAUDE.md",
        "lib/auth.js", "lib/auth-client.js",
        "app/api/auth/[...all]/route.js",
    })

    NEXT_PROTECTED = frozenset({
        "package.json", "next.config.mjs", "jsconfig.json",
        "tailwind.config.js", "postcss.config.js", "app/globals.css",
        "lib/mongodb.js", "app/api/health/route.js", ".env.local", ".gitignore",
        "AGENTS.md", "CLAUDE.md",

        "vitest.config.mjs", "playwright.config.js",
    })

    @property
    def EXTRA_DEPS(self) -> dict:
        return self.VITE_EXTRA_DEPS if self.stack == "vite" else self.NEXT_EXTRA_DEPS

    NEXT_MARK_BEGIN = "<!-- BEGIN:nextjs-agent-rules -->"
    NEXT_MARK_END = "<!-- END:nextjs-agent-rules -->"

    UI_PORT = 7824

    def trusted_origins(self) -> list:
        """
        Every origin a browser can reach this app from.

        Four, not one. The dev server answers directly on `dev_port`, and
        AgentForge also proxies it through its own UI port so the preview iframe is
        same-origin. Each is reachable as both `localhost` and `127.0.0.1`, and
        those are *different origins* to a browser — Electron loads the UI from
        127.0.0.1 while a normal tab uses localhost. Better Auth checks the
        Origin header against this list and answers "Invalid origin" on the
        form for anything missing, which is what a user sees instead of an
        account being created.
        """
        return [f"http://{host}:{port}"
                for port in (self.dev_port, self.UI_PORT)
                for host in ("localhost", "127.0.0.1")]

    def write_agent_files(self):
        """
        `AGENTS.md` + `CLAUDE.md`, cooperating with Next rather than fighting it.

        From 16.3 `next dev` generates both itself when it detects an agent in
        the environment, wrapping its content in BEGIN/END markers and upserting
        on every start — its block is the version-skew warning ("This is NOT the
        Next.js you know"), which is half the reason for moving to 16.

        `write_file` overwrites whole files, so scaffolding over an existing
        project would delete that block; the next `next dev` would put it back,
        but the file would churn on every build. So this reads what is there and
        replaces only the region outside the markers — the same upsert
        discipline Next itself uses.
        """
        if self.stack != "next":
            return
        ours = textwrap.dedent(f"""\
            # {self.plan.get('title', 'AgentForge app')}

            Generated and maintained by AgentForge. Next.js App Router + MongoDB,
            JavaScript only.

            ## Rules that decide whether this app runs

            - A file that awaits the database, reads cookies, or calls
              `getSessionUser` / `getCollection` is a **Server Component**: no
              `'use client'`, may be `async`. Its interactive parts belong in a
              separate `components/` file that starts with `'use client'`.
            - A `'use client'` file may never be `async`, never import
              `@/lib/mongodb`, `@/lib/auth`, `@/lib/seed`, `mongodb`, `bcryptjs`
              or `next/headers`. It fetches through `/api/...`.
            - The session user from `getSessionUser()` has **`id`, a string**.
              There is no `user._id` — it is `undefined`, so every comparison
              against it is false and every document written with it stores
              nothing. Compare with `doc.ownerId?.toString() === user.id` and
              store `new ObjectId(user.id)` into an ObjectId column. Use the
              same form everywhere for a given field: a document written with
              an ObjectId is never found by a query on the plain string.
            - `lib/auth.js` owns the session cookie name, alone. One exported
              constant; the login route, the session reader and the logout route
              all import it.
            - Every page or route handler that reads the database also exports
              `const dynamic = 'force-dynamic'`.
            - `serialize(doc)` before any Mongo document crosses to a Client
              Component.
            - The seed upserts by identity — `updateOne({{ email }},
              {{ $setOnInsert: … }}, {{ upsert: true }})` — and **never** guards
              on `countDocuments()`. A count guard stops seeding the moment the
              first real user signs up, and the demo accounts the app still
              advertises are never created.
            - The seed creates fewer than five rows per collection and **never**
              a unique index.
            - Never edit `next.config.mjs`, `package.json`, `jsconfig.json`,
              `tailwind.config.js`, `postcss.config.js` or `lib/mongodb.js` —
              AgentForge generates them and refuses writes to them.

            ## Reading the docs

            The documentation for the exact installed version is in
            `node_modules/next/dist/docs/`. Prefer it over recollection.
            """)

        fp = self.project_dir / "AGENTS.md"
        managed = ""
        if fp.is_file():
            try:
                old = fp.read_text(encoding="utf-8", errors="replace")
                i, j = (old.find(self.NEXT_MARK_BEGIN),
                        old.find(self.NEXT_MARK_END))
                if 0 <= i < j:
                    managed = old[i:j + len(self.NEXT_MARK_END)].strip() + "\n\n"
            except Exception as e:
                self._log("WARN", f"   could not read AGENTS.md: {e}")

        self._scaffolding = True
        try:
            self.write_file("AGENTS.md", managed + ours)
            self.write_file("CLAUDE.md", "@AGENTS.md\n")
        finally:
            self._scaffolding = False

    AUTH_WORDS = (
        "sign in", "signin", "sign-in", "log in", "login", "log-in", "sign up",
        "signup", "sign-up", "register", "account", "session", "password",
        "auth", "role", "roles", "permission", "admin", "staff", "member",
        "manager", "owner", "customer", "user", "who can", "only the",
        "logged in", "signed in", "access",
    )

    def _needs_auth(self) -> bool:
        """
        Whether this app has people who sign in.

        The plan answers this, and it answers it in structure rather than in
        prose: `demo_accounts` is the planner's considered decision about
        whether anybody has an account, and a planned `app/login` page is the
        same decision written another way. Both are unambiguous.

        Prose is the fallback and only the fallback, for a project with no plan
        — a resumed or imported one. Scanning prose for words like "user" and
        "auth" reads a sentence without reading what it says: measured on a
        coffee catalogue whose plan contained "auth" once and "user" once, in
        *"no authentication is needed"* and *"users can filter the list"*, and
        which was given a full login stack on the strength of it. The planner
        had already got it right — `demo_accounts` was empty — and the keyword
        scan overruled it.
        """
        plan = self.plan or {}
        if plan.get("demo_accounts"):
            return True
        planned = {str(f.get("path", "")).lower()
                   for ph in (plan.get("phases") or [])
                   for f in (ph.get("files") or [])}
        if any(p.startswith(("app/login", "app/signup", "app/register",
                             "app/(auth)")) for p in planned):
            return True
        if plan.get("phases"):
            return False
        hay = " ".join([str(plan.get("description") or ""),
                        str(plan.get("title") or ""),
                        self.plan_md or ""]).lower()
        return any(w in hay for w in self.AUTH_WORDS)

    def scaffold(self):
        """Config files are always Python-generated — if these are wrong,
        nothing else the model writes can run."""
        self._scaffolding = True
        try:
            if self.stack == "next":
                return self._scaffold_next()
            return self._scaffold_vite()
        finally:
            self._scaffolding = False

    def _scaffold_vite(self):
        self._log("INFO", "🧱 Scaffolding Vite + Tailwind")
        title = self.plan.get("title", "AgentForge App")
        deps = {"react": "^18.3.1", "react-dom": "^18.3.1"}
        for d in self.plan.get("dependencies", []):
            key = d.strip().split("@")[0]
            if key in self.EXTRA_DEPS:
                deps[key] = self.EXTRA_DEPS[key]

        for k in ("react-router-dom", "framer-motion", "lucide-react", "react-icons"):
            deps.setdefault(k, self.EXTRA_DEPS[k])

        pkg = {
            "name": self.plan.get("project_name", "agentforge-app"),
            "private": True,
            "version": "0.1.0",
            "type": "module",
            "scripts": {"dev": "vite", "build": "vite build",
                        "preview": "vite preview"},
            "dependencies": dict(sorted(deps.items())),
            "devDependencies": {
                "@vitejs/plugin-react": "^4.3.1",
                "autoprefixer": "^10.4.20",
                "postcss": "^8.4.47",
                "tailwindcss": "^3.4.13",
                "vite": "^5.4.8",
            },
        }
        self.write_file("package.json", json.dumps(pkg, indent=2))

        self.write_file("vite.config.js", textwrap.dedent("""\
            import { defineConfig } from 'vite'
            import react from '@vitejs/plugin-react'

            export default defineConfig({
              plugins: [react()],
              server: { host: true, port: 5173, strictPort: true },
            })
            """))

        self.write_file("tailwind.config.js", textwrap.dedent("""\
            /** @type {import('tailwindcss').Config} */
            export default {
              content: ['./index.html', './src/**/*.{js,jsx}'],
              theme: { extend: {} },
              plugins: [],
            }
            """))

        self.write_file("postcss.config.js", textwrap.dedent("""\
            export default {
              plugins: { tailwindcss: {}, autoprefixer: {} },
            }
            """))

        self.write_file("index.html", textwrap.dedent(f"""\
            <!doctype html>
            <html lang="en">
              <head>
                <meta charset="UTF-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1.0" />
                <title>{title}</title>
              </head>
              <body>
                <div id="root"></div>
                <script type="module" src="/src/main.jsx"></script>
              </body>
            </html>
            """))

        self.write_file("src/main.jsx", textwrap.dedent("""\
            import React from 'react'
            import ReactDOM from 'react-dom/client'
            import { BrowserRouter } from 'react-router-dom'
            import App from './App.jsx'
            import './index.css'

            ReactDOM.createRoot(document.getElementById('root')).render(
              <React.StrictMode>
                <BrowserRouter>
                  <App />
                </BrowserRouter>
              </React.StrictMode>
            )
            """))

        self.write_file("src/index.css", textwrap.dedent("""\
            @tailwind base;
            @tailwind components;
            @tailwind utilities;

            * { -webkit-font-smoothing: antialiased; }
            html, body, #root { height: 100%; }
            body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; }
            ::-webkit-scrollbar { width: 10px; height: 10px; }
            ::-webkit-scrollbar-thumb { background: rgba(120,120,140,.35); border-radius: 8px; }
            ::-webkit-scrollbar-track { background: transparent; }
            """))

    def _scaffold_next(self):
        """
        Next.js 16 App Router + MongoDB.

        Versions are pinned exactly.

        **Next 16.3**, moved up from 15.5 so the model can read the framework's
        own documentation: 16.2+ ships the full docs inside the package at
        `node_modules/next/dist/docs/` (measured: 444 files, 3.9 MB, matched to
        the installed version), and `next dev` writes an `AGENTS.md` pointing
        at them. The trade is real — 16 hard-errors where 15 only warned, most
        notably on sync `params` access, which mid-size models still write —
        and the docs are the mitigation for exactly that.

        AgentForge runs 16 on **webpack**, not its new default Turbopack, because
        `Failed to compile` / `Module not found` / `Can't resolve` are the
        strings the build fix loop parses; all three were verified present with
        `--webpack` on 16.3.

        mongodb 6 because 7 requires Node >= 20.19 and the vendored Node is
        20.18.1 — 16.3 itself needs only >= 20.9.0, so no Node bump. Tailwind 3
        because v4's CSS-first config is not what models emit.
        """
        self._log("INFO", "🧱 Scaffolding Next.js + Tailwind + MongoDB")
        title = self.plan.get("title", "AgentForge App")
        slug = self.plan.get("project_name", "agentforge-app")
        db = self.db_name or f"agentforge_{re.sub(r'[^a-z0-9_]+', '_', slug.lower())}"

        deps = {"next": "16.3.0", "react": "19.0.8", "react-dom": "19.0.8",
                "mongodb": "6.21.0", "lucide-react": "^0.441.0",

                "better-auth": "1.6.26",
                "@better-auth/mongo-adapter": "1.6.26"}
        for d in self.plan.get("dependencies", []):
            key = d.strip().split("@")[0]
            if key in self.NEXT_EXTRA_DEPS and key not in self.BANNED_DEPS:
                deps[key] = self.NEXT_EXTRA_DEPS[key]
        deps.setdefault("framer-motion", self.NEXT_EXTRA_DEPS["framer-motion"])

        pkg = {
            "name": slug,
            "private": True,
            "version": "0.1.0",

            "scripts": {"dev": "next dev --webpack",
                        "build": "next build --webpack",
                        "start": "next start"},
            "dependencies": dict(sorted(deps.items())),
            "devDependencies": {
                "autoprefixer": "^10.4.20",
                "postcss": "^8.4.47",
                "tailwindcss": "3.4.19",
            },
        }
        self.write_file("package.json", json.dumps(pkg, indent=2))

        self.write_file("next.config.mjs", textwrap.dedent("""\
            /** @type {import('next').NextConfig} */
            const nextConfig = {
              // StrictMode double-invokes effects, which double-inserts seed rows.
              reactStrictMode: false,
              typescript: { ignoreBuildErrors: true },
              outputFileTracingRoot: process.cwd(),
              // Forward browser console warnings and errors to the dev server's
              // terminal, WITH their source location:
              //   [browser] ShoppingCart is not defined (app/checkout/page.js:164:11)
              // AgentForge captures that stream, so a client-side crash arrives with
              // a file and a line instead of a bare message. Added in 16.2.
              logging: { browserToTerminal: 'warn' },
            }

            export default nextConfig
            """))

        self.write_file("jsconfig.json", json.dumps({
            "compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./*"]}}
        }, indent=2))

        self.write_file("tailwind.config.js", textwrap.dedent("""\
            /** @type {import('tailwindcss').Config} */
            module.exports = {
              content: [
                './app/**/*.{js,jsx}',
                './components/**/*.{js,jsx}',
                './lib/**/*.{js,jsx}',
              ],
              theme: { extend: {} },
              plugins: [],
            }
            """))

        self.write_file("postcss.config.js", textwrap.dedent("""\
            module.exports = {
              plugins: { tailwindcss: {}, autoprefixer: {} },
            }
            """))

        self.write_file("app/globals.css", textwrap.dedent("""\
            @tailwind base;
            @tailwind components;
            @tailwind utilities;

            * { -webkit-font-smoothing: antialiased; }
            html, body { height: 100%; }
            body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif; }
            ::-webkit-scrollbar { width: 10px; height: 10px; }
            ::-webkit-scrollbar-thumb { background: rgba(120,120,140,.35); border-radius: 8px; }
            ::-webkit-scrollbar-track { background: transparent; }
            """))

        self.write_file("app/layout.jsx", textwrap.dedent(f"""\
            import './globals.css'

            export const metadata = {{
              title: {json.dumps(title)},
              description: {json.dumps(self.plan.get('description', title))},
            }}

            export default function RootLayout({{ children }}) {{
              // suppressHydrationWarning is on <html> and <body> because
              // extensions — Grammarly (data-gr-ext-installed), QuillBot
              // (data-qb-installed), password managers — inject attributes
              // into exactly these two elements before React hydrates. That
              // produces a red "tree hydrated but some attributes … didn't
              // match" overlay on every page for anyone running one, and it
              // is not a fault in the app. The suppression is one level deep:
              // real mismatches inside the tree are still reported.
              return (
                <html lang="en" suppressHydrationWarning>
                  <body className="min-h-screen antialiased" suppressHydrationWarning>
                    {{children}}
                  </body>
                </html>
              )
            }}
            """))

        self.write_file("app/page.jsx", textwrap.dedent("""\
            export default function Page() {
              return (
                <main className="min-h-screen flex items-center justify-center">
                  <p className="text-lg text-gray-500">Building…</p>
                </main>
              )
            }
            """))

        self.write_file("lib/mongodb.js", textwrap.dedent("""\
            import { MongoClient, ObjectId } from 'mongodb'

            const uri = process.env.MONGODB_URI
            const dbName = process.env.MONGODB_DB

            // Connected on FIRST USE, never when this file is imported.
            //
            // `new MongoClient(uri).connect()` at module scope opens a socket
            // the moment anything imports this module — and `next build`
            // imports every page and route during its "Collecting page data"
            // pass. That made a running database a requirement to COMPILE the
            // app, which is not a requirement it should have. It worked on a
            // machine with mongod running and failed in CI, where the build
            // died with `MongoServerSelectionError: connect ECONNREFUSED
            // 127.0.0.1:27017`, blaming whichever route the collection worker
            // happened to reach first.
            let clientPromise

            // Reuse across HMR reloads so dev doesn't leak a connection per edit.
            if (process.env.NODE_ENV === 'development' && global._mongoClientPromise) {
              clientPromise = global._mongoClientPromise
            }

            function connection() {
              if (!clientPromise) {
                if (!uri) throw new Error('MONGODB_URI is not set — check .env.local')
                clientPromise = new MongoClient(uri).connect()
                if (process.env.NODE_ENV === 'development') {
                  global._mongoClientPromise = clientPromise
                }
              }
              return clientPromise
            }

            /** Awaitable exactly like the promise this replaced — it just does
             *  not exist until something awaits it. */
            export default { then: (ok, no) => connection().then(ok, no) }

            export async function getDb() {
              const client = await connection()
              return client.db(dbName)
            }

            export async function getCollection(name) {
              const db = await getDb()
              return db.collection(name)
            }

            /** ObjectId -> string, Date -> ISO string, so it can cross to a
             *  Client Component without React complaining. */
            export function serialize(doc) {
              return doc == null ? doc : JSON.parse(JSON.stringify(doc))
            }

            export { ObjectId }
            """))

        self.write_file("app/api/health/route.js", textwrap.dedent("""\
            import { getDb } from '@/lib/mongodb'

            export const dynamic = 'force-dynamic'

            export async function GET() {
              try {
                const db = await getDb()
                await db.command({ ping: 1 })
                return Response.json({ ok: true, db: db.databaseName })
              } catch (e) {
                return Response.json({ ok: false, error: String(e) }, { status: 500 })
              }
            }
            """))

        uri = self.mongo_uri or f"mongodb://127.0.0.1:27017/{db}"
        self.write_file(".env.local", textwrap.dedent(f"""\
            MONGODB_URI={uri}
            MONGODB_DB={db}
            BETTER_AUTH_SECRET={secrets.token_hex(32)}
            BETTER_AUTH_URL=http://localhost:{self.dev_port}
            NEXT_TELEMETRY_DISABLED=1
            """))

        roles = [str(a.get("role") or "").strip()
                 for a in ((self.plan or {}).get("demo_accounts") or [])]
        signup_role = next((r for r in roles if r), "user")

        auth_src = textwrap.dedent("""\
            import { betterAuth } from 'better-auth'
            import { mongodbAdapter } from '@better-auth/mongo-adapter'
            import { nextCookies } from 'better-auth/next-js'
            import { MongoClient } from 'mongodb'

            const uri = process.env.MONGODB_URI
            const globalForAuth = globalThis
            const client =
              globalForAuth._authMongoClient ?? new MongoClient(uri)
            if (process.env.NODE_ENV !== 'production') {
              globalForAuth._authMongoClient = client
            }

            export const auth = betterAuth({
              // No `client` here — that would enable transactions, which need
              // a replica set. AgentForge's mongod is standalone.
              database: mongodbAdapter(client.db(process.env.MONGODB_DB)),
              emailAndPassword: { enabled: true },
              user: {
                additionalFields: {
                  role: { type: 'string', defaultValue: 'user', input: false },
                },
              },
              secret: process.env.BETTER_AUTH_SECRET,
              baseURL: process.env.BETTER_AUTH_URL,
              // Better Auth answers "Invalid origin" — visible on the form,
              // with no account created — for any Origin not matched here.
              // This app is reachable several ways: the dev server directly,
              // AgentForge's preview proxy on another port, each under both
              // `localhost` and `127.0.0.1` (different origins to a browser;
              // Electron uses one and a normal tab the other), and the port
              // moves when one is busy.
              //
              // Enumerating them is how this broke the first time, so match on
              // the pattern instead — `*` is supported and only widens to
              // loopback. A remote origin is still refused with 403, verified.
              trustedOrigins: {TRUSTED_ORIGINS},
              // Must be last: it is what lets a Server Action or route handler
              // set the session cookie on the response.
              plugins: [nextCookies()],
            })

            /** The signed-in user, or null. Safe in any server file. */
            export async function getSessionUser() {
              const { headers } = await import('next/headers')
              const session = await auth.api.getSession({ headers: await headers() })
              return session?.user ?? null
            }
            """).replace("{TRUSTED_ORIGINS}", self.TRUSTED_ORIGINS)
        auth_src = auth_src.replace("defaultValue: 'user'",
                                    f"defaultValue: {json.dumps(signup_role)}")
        if signup_role != "user":
            self._log("INFO", f"   🔐 people who sign up get the "
                              f"`{signup_role}` role — the plan's own first "
                              f"role, not Better Auth's 'user'")

        if self._needs_auth():
            self.write_file("lib/auth.js", auth_src)

            self.write_file("app/api/auth/[...all]/route.js", textwrap.dedent("""\
                import { toNextJsHandler } from 'better-auth/next-js'

                // Serves every auth endpoint: /api/auth/sign-in/email,
                // /api/auth/sign-up/email, /api/auth/sign-out,
                // /api/auth/get-session.

                // Never at module scope: importing `@/lib/auth` builds the
                // Better Auth instance, which connects to MongoDB, and
                // `next build` imports this file while collecting page data.
                // Built once and reused, on the first request.
                let handlers
                async function ready() {
                  if (!handlers) {
                    const { auth } = await import('@/lib/auth')
                    handlers = toNextJsHandler(auth.handler)
                  }
                  return handlers
                }

                export const dynamic = 'force-dynamic'

                export async function GET(request) {
                  return (await ready()).GET(request)
                }

                export async function POST(request) {
                  return (await ready()).POST(request)
                }
                """))

            self.write_file("lib/auth-client.js", textwrap.dedent("""\
                'use client'
                import { createAuthClient } from 'better-auth/react'

                export const authClient = createAuthClient()
                export const { signIn, signUp, signOut, useSession } = authClient
                """))
        else:
            self._log("INFO", "   🔓 Nothing in the brief signs in — building "
                              "without authentication")

        self.write_file(".gitignore", textwrap.dedent("""\
            node_modules/
            .next/
            out/
            .env*.local
            .agentforge/
            *.log
            """))

        self.write_agent_files()

    def _context_snapshot(self, max_files: int = 14, per_file: int = 1400) -> str:
        """Existing source, trimmed — so later files can import correctly."""
        src = [(p, c) for p, c in self.files.items() if self.is_source(p)]
        if not src:
            return "(no source files yet)"
        priority = ({"src/App.jsx": 0} if self.stack == "vite"
                    else {"lib/mongodb.js": 0, "app/layout.jsx": 1, "app/page.jsx": 2})
        src.sort(key=lambda x: (priority.get(x[0], 99), x[0]))
        out = []
        for path, content in src[:max_files]:
            body = content if len(content) <= per_file else \
                content[:per_file] + "\n// …truncated…\n"
            out.append(f"--- {path} ---\n{body}")
        return "\n\n".join(out)

    KIND_LABEL = {
        "server": "SERVER component — may be async and read the DB directly, "
                  "NO hooks, NO 'use client'",
        "client": "CLIENT component — 'use client' on line 1, hooks allowed, "
                  "fetch via /api, never touch @/lib/mongodb",
        "route":  "ROUTE HANDLER — named exports GET/POST/…, no default "
                  "export, no 'use client'",
    }

    def _planned_files(self) -> list:
        """Every file the plan promised, in plan order, de-duplicated."""
        out, seen = [], set()
        for ph in self.plan.get("phases", []):
            for f in ph.get("files", []):
                path = f["path"]
                if path in seen:
                    continue
                seen.add(path)
                out.append(f)
        return out

    def _file_list_block(self, files: list) -> str:
        return "\n".join(
            f"  • {f['path']}  [{self.KIND_LABEL.get(f.get('kind', 'server'), self.KIND_LABEL['server'])}]"
            + (f"\n      {f['purpose']}" if f.get("purpose") else "")
            for f in files)

    def _task_list_block(self, tasks: list) -> str:
        """The plan as numbered tasks — the shape the build is driven in."""
        out = []
        for i, t in enumerate(tasks, start=1):
            head = f"### Task {i} — {t.get('title', f'Task {i}')}"
            if t.get("goal"):
                head += f"\nGoal: {t['goal']}"
            if t.get("done_when"):
                head += f"\nDone when: {t['done_when']}"

            if t.get("covers"):
                head += f"\nCovers: {', '.join(t['covers'])}"
            out.append(head + "\n" + self._file_list_block(t.get("files", [])))
        return "\n\n".join(out)

    def _current_task(self):
        """
        `(number, task, files still missing)` for the first unfinished task.

        Driving the loop off what is on disk rather than a counter is what
        makes it safe to say "continue task 3": if the model got ahead of
        itself and wrote task 4's files too, task 4 is simply already done and
        never asked for again.
        """
        for i, t in enumerate(self.plan.get("phases", []), start=1):
            left = [f for f in t.get("files", []) if not self._on_disk(f["path"])]
            if left:
                return i, t, left
        return 0, None, []

    def _on_disk(self, path: str) -> bool:
        """Has this planned path been written, whatever extension it landed on?"""
        rel = path.lstrip("./")
        return rel in self.files or re.sub(r"\.jsx?$", "", rel) in self._stems()

    def _outstanding(self) -> list:
        """Planned file entries not yet on disk, still in plan order."""
        return [f for f in self._planned_files() if not self._on_disk(f["path"])]

    def _sync_phases(self, seen: dict, final: bool = False) -> None:
        """
        Keep the phase timeline in step with what is actually on disk.

        Generation no longer runs one turn per phase, but two things downstream
        still key off phase events: the UI timeline, and the QA agent — whose
        `active` fire carries the file list and whose `done` fire is what makes
        it author tests for those files. So the plan's phases are still
        reported; they are just driven by the files that have landed rather
        than by the turn that happens to be running.

        `final=True` closes out whatever never completed, using the files that
        do exist — so a half-finished phase still gets tests for its real half
        instead of leaving the timeline lit forever.
        """
        phases = self.plan.get("phases", [])
        total = len(phases)
        announced_active = False

        for i, ph in enumerate(phases, start=1):
            if seen.get(i) == "done":
                continue
            title = ph.get("title", f"Phase {i}")
            want = [f["path"] for f in ph.get("files", [])]
            have = [p for p in want if self._on_disk(p)]

            if len(have) < len(want) and not final:

                if not announced_active:
                    announced_active = True
                    if seen.get(i) != "active":
                        self._fire("on_phase", {
                            "phase": i, "total": total, "title": title,
                            "status": "active", "goal": ph.get("goal", ""),
                            "files": want})
                        seen[i] = "active"
                continue

            if len(have) < len(want):
                self._log("WARN", f"   ⚠ Never written: "
                                  f"{', '.join(p for p in want if p not in have)}")

            if seen.get(i) != "active" or have != want:
                self._fire("on_phase", {
                    "phase": i, "total": total, "title": title,
                    "status": "active", "goal": ph.get("goal", ""),
                    "files": have})
            self._fire("on_phase", {"phase": i, "total": total, "title": title,
                                    "status": "done", "written": len(have)})
            seen[i] = "done"

    def build_app(self) -> int:
        """
        Write the whole app in one flowing conversation, one task per turn.

        Two things are being balanced here. Re-prompting per phase with the
        whole plan restated used to invite the model to treat each phase as a
        fresh start — re-deciding a component's props, restyling a page it had
        already styled — so the thread is never restarted and the plan is
        stated once. But a bare "Continue" with fourteen files still listed
        makes the model budget one turn's output across all fourteen, and they
        all come out thin.

        So: one conversation, one plain "Continue" every time it stops, and
        the work always shown grouped under its task. The tasks are what give
        the model somewhere to aim — it can see that these three files are one
        coherent piece of the app — without the loop ever telling it to stop at
        a boundary. It writes until it runs out of room, and carries on.

        What is still outstanding comes from what is on disk, not a counter, so
        a model that jumps around is simply never asked for a file it already
        wrote.
        """
        planned = self._planned_files()
        total_files = len(planned)
        if not planned:
            self._log("WARN", "   ⚠ Plan named no files — nothing to build")
            return 0

        extras = ""
        if self.plan.get("demo_accounts"):
            accounts = ", ".join(f"{a['email']} / {a['password']} ({a['role']})"
                                 for a in self.plan["demo_accounts"])
            extras += (f"\n\nDemo accounts (seed these EXACT values, hashed "
                       f"with bcrypt.hashSync. Do NOT display them anywhere "
                       f"in the UI): {accounts}")

        tasks = self.plan.get("phases", [])

        already = total_files - len(self._outstanding())
        resuming = already > 0
        if resuming:
            self._log("INFO", f"⚙️  Continuing — {already}/{total_files} files "
                              f"already on disk, {total_files - already} to write")
        else:
            self._log("INFO", f"⚙️  Building {total_files} files across "
                              f"{len(tasks)} tasks")

        opening = (textwrap.dedent("""\
            ## Finishing a build that was interrupted

            Most of this app is already written and on disk. Do not touch it,
            and do not write any file that is not listed below — what follows
            is only what is still missing, grouped by task. Match what is
            already there: keep the same naming, styling and data shapes.
            """) if resuming else textwrap.dedent("""\
            ## The build, broken into tasks

            The whole app is below, grouped into tasks so you can see which
            files belong together. Work straight down it, task by task, and do
            not stop between tasks — when you run out of room I will say
            "Continue" and you carry on where you left off.
            """))
        user = (opening
            + "\n" + (self._outstanding_by_task() if resuming
                      else self._task_list_block(tasks)) + extras + "\n"
            + textwrap.dedent("""\

            How this works:
              • One <write_file path="…">…</write_file> block per file. Real,
                finished code — no TODOs, no placeholders, no "rest of the
                code unchanged".
              • Take the tasks in order and keep going. Never rewrite a file
                you have already written.
              • Every file gets the full attention of its own task. A page
                that renders a heading and an empty div is not a finished
                page: it needs the real data, loading and empty states, the
                actions the feature promises, and a layout that holds together
                on a phone.
              • Hold the design bar on every screen — the plan's one accent
                colour, the spacing rhythm, the type scale, hover and focus
                states on everything clickable, and a designed empty state.
                Ultra beautiful is the target, and restraint is how it is
                reached.
              • Stay consistent: what you write early is what the later tasks
                import, so keep the naming, props, styling and data shapes
                identical throughout.
              • Do not narrate between files and do not ask questions.
              • If you run out of room, stop at a file boundary — I will say
                "Continue" and you pick up at the next unwritten file.
              • When every task is done, reply exactly: BUILD COMPLETE

            Start now.
            """))

        max_turns = max(6, min(40, total_files + 6))
        seen, written_total, stalls = {}, 0, 0

        for turn in range(1, max_turns + 1):
            written = self._run_write_loop(user)
            written_total += written
            self._sync_phases(seen)
            self._fire("on_memory", self.memory_stats())

            self.save_convo()

            outstanding = self._outstanding()
            done_n = total_files - len(outstanding)
            index, _task, left = self._current_task()
            self._fire("on_progress",
                       (f"Task {index}/{len(tasks)}… {done_n}/{total_files} files"
                        if index else f"Writing files… {done_n}/{total_files}"),
                       int(18 + 60.0 * done_n / total_files))
            self._log("INFO", f"   📝 {done_n}/{total_files} files on disk "
                              f"(turn {turn}, +{written})")

            if not outstanding:
                break

            if written:
                stalls = 0
            else:
                stalls += 1
                if stalls >= 2:
                    self._log("WARN", "   ⚠ Two turns produced no files — "
                                      "handing what exists to the repair passes")
                    break

                self._log("WARN", "   ⚠ No files emitted — pushing harder")
                user = ("You produced no <write_file> blocks. Output ONLY "
                        "<write_file path=\"…\">…</write_file> blocks, starting "
                        "immediately with '<write_file', for these files:\n"
                        + self._file_list_block(left or outstanding))
                continue

            user = self._continue_prompt(outstanding)
        else:
            self._log("WARN", f"   ⚠ Stopped after {max_turns} turns with "
                              f"{len(self._outstanding())} file(s) unwritten")

        self._sync_phases(seen, final=True)
        return written_total

    def _outstanding_by_task(self) -> str:
        """
        What is left, under the task each file belongs to.

        The grouping is the point. A flat list of eleven paths is eleven
        unrelated chores; the same eleven under "Task 3 — Room inventory, done
        when a room can be taken out of service" tells the model what the next
        three files are FOR, which is what stops them coming out thin. It is
        presentation only — the loop never asks it to stop at a boundary.
        """
        blocks = []
        for i, t in enumerate(self.plan.get("phases", []), start=1):
            left = [f for f in t.get("files", []) if not self._on_disk(f["path"])]
            if not left:
                continue
            head = f"### Task {i} — {t.get('title', f'Task {i}')}"
            if t.get("goal"):
                head += f"\nGoal: {t['goal']}"
            if t.get("done_when"):
                head += f"\nDone when: {t['done_when']}"
            if t.get("covers"):
                head += f"\nCovers: {', '.join(t['covers'])}"
            blocks.append(head + "\n" + self._file_list_block(left))
        return "\n\n".join(blocks)

    def _continue_prompt(self, outstanding: list) -> str:
        """The "keep going" turn: what is left, and nothing else to re-read."""
        parts = ["Continue."]

        if self._last_truncated:
            parts.append(f"`{self._last_truncated}` was cut off mid-file. "
                         f"Write it again in full first, then carry on.")

        if self._convo_chars() > self._budget_chars():
            parts.append(f"{SNAPSHOT_OPEN}\n" + self._context_snapshot()
                         + f"\n{SNAPSHOT_CLOSE}")

        grouped = self._outstanding_by_task()
        parts.append("Still to write:\n\n" + (grouped
                     or self._file_list_block(outstanding)))
        parts.append("Keep going until they all exist. Complete files, one "
                     "<write_file> block each, no narration. Finished pages "
                     "with real data, empty and loading states, the actions "
                     "the feature promises, and the design bar held: one "
                     "accent colour, the spacing rhythm, hover and focus "
                     "states, and a layout that works at 375px.")
        return "\n\n".join(parts)

    def _run_write_loop(self, user_content: str) -> int:
        """
        Continue the running conversation with one more turn, routing
        <write_file> blocks onto disk as they stream in.

        The assistant's reply is appended back to the thread, so the next turn
        sees everything this one produced. `_last_truncated` records the file
        the model was still mid-way through when the turn ended — the normal
        way a continuous pass hits the output limit, and the one thing the next
        turn cannot work out for itself, since the partial file is on disk and
        therefore looks written.
        """

        self.convo.append({"role": "user",
                           "content": user_content + self._refusal_note()})
        self._refused = {}
        self._trim_convo()
        self._last_truncated = None

        state = {"count": 0, "path": None, "buf": []}
        raw = []

        def on_text(t):
            t = t.strip()

            if t and len(t) > 2 and t.upper().strip(".!* ") != "BUILD COMPLETE":
                self._fire("on_chat", t)

        def on_start(path):
            state["path"] = path
            state["buf"] = []
            self._fire("on_file_start", path)

        def on_token(tok):
            state["buf"].append(tok)
            self._fire("on_file_token", state["path"], tok)

        def on_end(path, content):
            self._fire("on_file_end", path, content)
            if self.write_file(path, content):
                state["count"] += 1
            elif self._stuck_on_refusals():

                raise _RefusalLoop()
            state["path"] = None

        parser = FileStreamParser(on_text, on_start, on_token, on_end)

        def feed(delta):
            raw.append(delta)
            parser.feed(delta)

        def close_parser():

            if parser.mode == "file":
                self._last_truncated = parser.path
            parser.close()

        try:
            tool_calls = self._stream(self.convo, feed, temperature=0.5)
        except _RefusalLoop:

            self._log("WARN", "   ⏹ stopped this turn — it was re-writing "
                              "files that had already been refused")
            close_parser()
            self.convo.append({"role": "assistant", "content": "".join(raw)})
            return state["count"]
        except Exception as e:
            self._log("ERROR", f"   ❌ Generation failed: {e}")
            close_parser()
            self.convo.append({"role": "assistant", "content": "".join(raw)})
            return state["count"]

        close_parser()
        reply = "".join(raw)

        self.convo.append({"role": "assistant", "content": reply})

        if self.stack == "next":
            docs = docsindex.serve(self.project_dir, reply)
            if docs:
                asked = docsindex.READ_RE.findall(reply)
                self._log("INFO", f"   📖 read_docs: {', '.join(asked[:3])}")
                self.convo.append({
                    "role": "user",
                    "content": docs + "\n\nThat is the documentation for the "
                                      "version installed here. Continue.",
                })

        results = self.run_requested_commands(reply)
        if results:
            self.convo.append({
                "role": "user",
                "content": "Command output:\n\n" + "\n\n".join(results)
                           + "\n\nContinue. Do not repeat a command that "
                             "already succeeded.",
            })

        for tc in tool_calls:
            fn = (tc or {}).get("function") or {}
            if fn.get("name") != "write_file":
                continue
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    continue
            path, content = args.get("path"), args.get("content")
            if path and content and path not in self.files:
                self._fire("on_file_start", path)
                self._fire("on_file_end", path, content)
                if self.write_file(path, content):
                    state["count"] += 1

        return state["count"]

    LOCAL_IMPORT_RE = re.compile(
        r"""import\s+(?:\w+|\{[^}]*\}|\w+\s*,\s*\{[^}]*\})\s+from\s+['"](\.[^'"]+)['"]""")

    ALIAS_IMPORT_RE = re.compile(
        r"""import\s+(?:\w+|\{[^}]*\}|\w+\s*,\s*\{[^}]*\})\s+from\s+['"]@/([^'"]+)['"]""")

    @staticmethod
    def _normalise(path: str) -> str:
        parts = []
        for seg in path.split("/"):
            if seg == "..":
                if parts:
                    parts.pop()
            elif seg not in (".", ""):
                parts.append(seg)
        return "/".join(parts)

    NAMED_IMPORT_RE = re.compile(
        r"""import\s+(?:\w+\s*,\s*)?\{([^}]*)\}\s+from\s+(['"])([^'"]+)\2""")

    DECL_EXPORT_RE = re.compile(
        r"""export\s+(?:async\s+)?(?:function|const|let|var|class)\s+(\w+)""")

    LIST_EXPORT_RE = re.compile(r"""export\s*\{([^}]*)\}""")

    def _named_exporters(self) -> dict:
        """symbol -> the set of files that export it by that name."""
        out = {}
        for path, content in self.files.items():
            if not path.endswith((".js", ".jsx")):
                continue
            names = set(self.DECL_EXPORT_RE.findall(content))
            for group in self.LIST_EXPORT_RE.findall(content):
                for entry in group.split(","):
                    entry = entry.strip()
                    if not entry:
                        continue

                    names.add(re.split(r"\s+as\s+", entry)[-1].strip())
            for n in names:
                out.setdefault(n, set()).add(path)
        return out

    def _resolves(self, target: str) -> bool:
        """Does a root-relative import specifier point at a file we have?"""
        return any(c in self.files for c in
                   (target, f"{target}.js", f"{target}.jsx",
                    f"{target}/index.js", f"{target}/index.jsx"))

    def redirect_dead_imports(self) -> int:
        """
        Repoint an import whose path does not exist at the file that really
        exports the symbol.

        This is the other half of `repair_missing_imports`, and it has to run
        first. That one makes every import resolve by CREATING the module,
        which is right when the file was simply never written and badly wrong
        when the symbol already lives somewhere else: a repair that wrote
        `import { CartProvider } from '@/components/CartContext'` against a
        project whose provider is in `lib/cart-context.js` would get a second
        CartProvider generated for it, so the tree would mount one context and
        every `useCart` would read the other. The app compiles and stays
        broken, which is worse than the module-not-found it started as.
        Measured on a real repair — it 500'd every route in the app.

        Deterministic and provable, not a guess: it only moves an import when
        the path resolves to nothing AND exactly one file in the project
        exports every name being imported. Anything ambiguous is left for
        `repair_missing_imports` to generate.
        """
        exporters = self._named_exporters()
        fixed = 0
        for path, content in list(self.files.items()):
            if not path.endswith((".js", ".jsx")):
                continue
            base = Path(path).parent
            out = content
            for m in self.NAMED_IMPORT_RE.finditer(content):
                spec = m.group(3)
                if spec.startswith("."):
                    target = self._normalise((base / spec).as_posix())
                elif spec.startswith("@/"):
                    target = self._normalise(spec[2:])
                else:
                    continue
                if not target or self._resolves(target):
                    continue

                symbols = [re.split(r"\s+as\s+", s.strip())[0].strip()
                           for s in m.group(1).split(",") if s.strip()]
                if not symbols:
                    continue

                homes = set.intersection(*(exporters.get(s, set())
                                           for s in symbols)) \
                    if all(s in exporters for s in symbols) else set()
                homes.discard(path)
                if len(homes) != 1:
                    continue

                home = homes.pop()
                alias = "@/" + re.sub(r"\.jsx?$", "", home)
                out = out.replace(m.group(0),
                                  m.group(0).replace(f"{m.group(2)}{spec}"
                                                     f"{m.group(2)}",
                                                     f"{m.group(2)}{alias}"
                                                     f"{m.group(2)}"))
                fixed += 1
                self._log("INFO", f"   🔗 {path}: {spec} does not exist — "
                                  f"{', '.join(symbols)} comes from {home}")
            if out != content:
                self.write_file(path, out)
        return fixed

    def repair_missing_imports(self) -> int:
        """
        Generate any local module that is imported but was never written.
        A single missing file blanks the whole app, so this is worth a pass.

        Repointing comes first — see `redirect_dead_imports`. An import that
        names a symbol some other file already exports is a wrong path, not a
        missing module, and generating the module would duplicate the symbol.
        """
        self.redirect_dead_imports()

        def _ext_for(t: str) -> str:
            if self.stack == "vite":
                return ".jsx"
            return ".js" if self.canonical_path(t + ".js").endswith(".js") else ".jsx"

        missing = set()
        for path, content in list(self.files.items()):
            if not path.endswith((".jsx", ".js")):
                continue
            base = Path(path).parent
            specs = [(base / s).as_posix() for s in self.LOCAL_IMPORT_RE.findall(content)]
            specs += self.ALIAS_IMPORT_RE.findall(content)
            for target in specs:
                target = self._normalise(target)
                if not target or target.endswith(".css"):
                    continue
                cands = [target, f"{target}.js", f"{target}.jsx",
                         f"{target}/index.js", f"{target}/index.jsx"]
                if not any(c in self.files for c in cands):
                    missing.add(self.canonical_path(target)
                                if target.endswith((".jsx", ".js"))
                                else f"{target}{_ext_for(target)}")

        if not missing:
            return 0

        self._log("WARN", f"🔗 {len(missing)} imported file(s) missing — generating")
        self._fire("on_phase", {"phase": -1, "title": "Repairing imports",
                                "status": "active"})

        n = self._run_write_loop(textwrap.dedent(f"""\
            These modules are imported by the app but were never written:
            {chr(10).join('  • ' + m for m in sorted(missing))}

            Create each one so every import resolves. Match the visual style
            and the named/default exports the importing files expect —
            you wrote those imports, so use what they ask for.
            One <write_file> block per file.
            """))
        self._fire("on_phase", {"phase": -1, "title": "Repairing imports",
                                "status": "done", "written": n})
        return n

    def run_requested_commands(self, reply: str) -> list:
        """
        Execute every <run_command> block in a model reply.

        Returns the feedback strings to hand back to the model. Refusals are
        included deliberately — "npm publish is not allowed" is information the
        model needs, and silently dropping it invites a retry loop.
        """
        commands = [c.strip() for c in CMD_RE.findall(reply or "")]
        commands = [c for c in commands if c]
        if not commands:
            return []

        out = []
        for command in commands[:5]:

            if self._already_satisfied(command):
                self._log("INFO", f"   ↩ skipped (already installed): {command}")
                out.append(f"$ {command}\n[skipped — already installed]")
                continue
            out.append(self.cmd.run(command).as_feedback())
        return out

    _INSTALL_RE = re.compile(r"^\s*(npm|yarn|pnpm)\s+(install|i|add)\s+(.+)$", re.I)

    @staticmethod
    def _pkg_name(spec: str) -> str:
        """`bcryptjs@^2.4.3` → `bcryptjs`; `@scope/pkg@1.0` → `@scope/pkg`."""
        spec = spec.strip()
        if spec.startswith("@"):
            return "@" + spec[1:].split("@", 1)[0]
        return spec.split("@", 1)[0]

    def _already_satisfied(self, command: str) -> bool:
        """True when an install would be a no-op — each one costs ~a minute."""
        m = self._INSTALL_RE.match(command or "")
        if not m:
            return False
        names = [self._pkg_name(p) for p in m.group(3).split()
                 if not p.startswith("-")]
        if not names:
            return False
        nm = self.project_dir / "node_modules"
        return all((nm / n / "package.json").exists() for n in names)

    CLIENT_HINTS = re.compile(
        r"\buse(State|Effect|Ref|Reducer|Context|Memo|Callback|Router|Pathname)\s*\("
        r"|on(Click|Change|Submit|Input|KeyDown|KeyUp|Focus|Blur)\s*="
        r"|from\s+['\"]framer-motion['\"]"
        r"|\b(window|document|localStorage)\s*\.")
    IMPORT_LINE_RE = re.compile(r"^\s*import\s.+$", re.M)

    def _next_files(self):
        for path, content in list(self.files.items()):
            if path in self.NEXT_PROTECTED or not path.endswith((".js", ".jsx")):
                continue
            if path.startswith(("app/", "components/", "lib/")):
                yield path, content

    IMG_HANDLER_RE = re.compile(
        r"\s*\bon(?:Error|Load)\s*=\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")

    def strip_server_img_handlers(self) -> int:
        """
        Delete image event handlers from Server Components.

        This is the one boundary mistake the model makes over and over: a
        fallback on an image. `<img onError={e => e.target.src = placeholder}>`
        reads as defensive programming and is, in a Server Component, a
        function crossing the wire — the page returns 200 and then dies in the
        browser with "Event handlers cannot be passed to Client Component
        props". It happened three times in one generated project and again in
        the feature added to it afterwards.

        Removing it is safe in a way that fixing it by hand is not. The handler
        is decoration: it swaps in a placeholder when a picture 404s, and the
        pictures are generated into `public/generated/` before the app runs. So
        the attribute goes and nothing else moves — no 'use client' added, no
        component extracted, no database query dragged into the browser.

        Only `onError` and `onLoad` on images. A stray `onClick` is a real
        interaction and its file may genuinely need to become a client
        component, which is a judgement call — that one goes to the lint and
        the repair pass instead.
        """
        fixed = 0
        for path, content in list(self._next_files()):
            if re.match(r"\s*['\"]use client['\"]", content):
                continue
            out, n = self.IMG_HANDLER_RE.subn("", content)
            if n:
                self.write_file(path, out)
                fixed += n
                self._log("INFO", f"   🔧 Removed {n} image handler(s) from "
                                  f"{path} — it is a Server Component")
        return fixed

    def enforce_use_client(self) -> int:
        """Prepend `'use client'` where the file clearly needs it."""
        fixed = 0
        for path, content in self._next_files():
            if self.DIRECTIVE_RE.match(content):
                continue

            if self.STRAY_DIRECTIVE_RE.search(content):
                self._log("WARN", f"   ⚠ {path} has a misplaced 'use client' — "
                                  f"leaving it for the fix pass")
                continue
            if path.endswith("route.js") or "/route.js" in path:
                continue
            if not self.CLIENT_HINTS.search(content):
                continue
            if re.search(r"^\s*export\s+const\s+metadata\b", content, re.M):

                self._log("WARN", f"   ⚠ {path} needs 'use client' but exports "
                                  f"metadata — leaving it for the fix pass")
                continue
            self.write_file(path, "'use client'\n\n" + content)
            fixed += 1
        if fixed:
            self._log("INFO", f"   🔧 Added 'use client' to {fixed} file(s)")
        return fixed

    DIRECTIVE_RE = re.compile(r"""\A\s*(['"])use (?:client|server)\1\s*;?[^\S\n]*\n""")

    def enforce_dynamic(self) -> int:
        """DB-reading routes must opt out of static prerendering."""
        fixed = 0
        for path, content in self._next_files():
            if not re.match(r"^app/(.+/)?(page|route)\.jsx?$", path):
                continue
            if "@/lib/mongodb" not in content:
                continue
            if re.search(r"^\s*export\s+const\s+dynamic\b", content, re.M):
                continue

            m = self.DIRECTIVE_RE.match(content)
            at = m.end() if m else 0
            patched = (content[:at] + "export const dynamic = 'force-dynamic'\n\n"
                       + content[at:])
            self.write_file(path, patched)
            fixed += 1
        if fixed:
            self._log("INFO", f"   🔧 Added force-dynamic to {fixed} route(s)")
        return fixed

    def fix_next_imports(self) -> int:
        """Rewrite the Pages-Router habits models fall back into."""
        fixed = 0
        for path, content in self._next_files():
            out = content
            out = out.replace("from 'next/router'", "from 'next/navigation'")
            out = out.replace('from "next/router"', 'from "next/navigation"')

            if "<Head" not in out:
                out = re.sub(r"^\s*import\s+\w+\s+from\s+['\"]next/head['\"].*$\n?",
                             "", out, flags=re.M)
            out = re.sub(r"(<Link\b[^>]*?)\sto=", r"\1 href=", out)

            out = re.sub(r"https?://localhost:\d+", "", out)
            if out != content:
                self.write_file(path, out)
                fixed += 1
        if fixed:
            self._log("INFO", f"   🔧 Fixed Next.js imports in {fixed} file(s)")
        return fixed

    TRUSTED_ORIGINS = "['http://localhost:*', 'http://127.0.0.1:*']"
    TRUSTED_RE = re.compile(r"^\s*trustedOrigins:.*?,\s*$\n?", re.M | re.S)

    def verify_auth_config(self) -> bool:
        """
        Make sure Better Auth trusts the origin the app is actually viewed from.

        Without this the login and signup forms answer "Invalid origin" and no
        account is created — and the user meets it as a red message on a form,
        with nothing in the build output.

        It is a healing pass, not just a guard, because the config can be wrong
        for a reason no build-time check would catch: Python does not reload an
        imported module, so an AgentForge server started before this rule existed
        goes on scaffolding the old file for as long as it runs. Repairing on
        every build and every update means such a project is corrected the
        first time anything touches it, rather than staying broken until
        somebody notices and regenerates.
        """
        auth = self.files.get("lib/auth.js")
        if not auth or "betterAuth(" not in auth:
            return True
        if self.TRUSTED_ORIGINS in auth:
            return True

        if "trustedOrigins" in auth:

            fixed = self.TRUSTED_RE.sub("", auth, count=1)
            why = "replacing a hardcoded origin list"
        else:
            fixed, why = auth, "it trusted no origin but its own baseURL"

        anchor = "  plugins:"
        if anchor not in fixed:
            anchor = "})"
        if anchor not in fixed:
            self._log("WARN", "   ⚠ lib/auth.js has no place to add "
                              "trustedOrigins — leaving it alone")
            return False
        fixed = fixed.replace(
            anchor,
            f"  trustedOrigins: {self.TRUSTED_ORIGINS},\n{anchor}", 1)

        self._log("WARN", f"   🔧 lib/auth.js — {why}; the preview is served "
                          f"from a different port than the dev server, and "
                          f"Better Auth answers 'Invalid origin' for it")
        self._scaffolding = True
        try:
            return self.write_file("lib/auth.js", fixed)
        finally:
            self._scaffolding = False

    _SOLE_ELEMENT_RE = r"^[ \t]*<%s(?:\s[^>]*?)?/>[ \t]*\r?\n"

    def _drop_layout_duplicates(self, key: str, content: str) -> str:
        """
        Take out what the ROOT LAYOUT already renders.

        The root layout wraps every page, so a component it renders is on the
        screen once already. A page that renders it again puts two of them
        there — measured on this build, `<Header />` in both `app/layout.jsx`
        and `app/page.jsx`, and the home page served two identical navbars.
        Nothing catches it: it compiles, it renders, there is no error, and the
        browser pass counts characters rather than headers. The same shape was
        reported on a 404 page an earlier build shipped, so it recurs.

        Only pages and nested layouts are touched, only for components the root
        layout really renders, and only where the element stands alone on its
        line. Anything less clear-cut is left alone and said out loud.
        """
        if not key.startswith("app/") or not key.endswith((".jsx", ".js")):
            return content
        name = key.rsplit("/", 1)[-1]
        if not (name.startswith("page.") or name.startswith("layout.")):
            return content
        if key in ("app/layout.jsx", "app/layout.js"):
            return content

        root = self.files.get("app/layout.jsx") or self.files.get("app/layout.js")
        if not root:
            return content
        rendered = {m for m in re.findall(r"<([A-Z]\w*)\s*(?:\s[^>]*?)?/>", root)}
        if not rendered:
            return content

        for comp in sorted(rendered):
            if f"<{comp}" not in content:
                continue
            fixed, n = re.subn(self._SOLE_ELEMENT_RE % comp, "", content,
                               flags=re.M)
            if not n:
                self._log("WARN", f"   ⚠ {key} renders <{comp}/>, which the "
                                  f"root layout already renders — that is two "
                                  f"of them on the page. Left as it is: it is "
                                  f"not on a line of its own.")
                continue

            if f"<{comp}" not in fixed:
                fixed = re.sub(
                    r"^import\s+%s\s+from\s+['\"][^'\"]+['\"];?[ \t]*\r?\n" % comp,
                    "", fixed, flags=re.M)
            self._log("WARN", f"   🔧 {key} — removed <{comp}/>; the root "
                              f"layout already renders it, so the page was "
                              f"showing two")
            content = fixed
        return content

    def verify_root_layout(self) -> bool:
        """The model may overwrite layout.js and drop what makes it a layout."""
        layout = self.files.get("app/layout.js") or self.files.get("app/layout.jsx")
        if layout and all(t in layout for t in ("<html", "<body", "globals.css")):
            return True
        self._log("WARN", "   🔧 Restoring app/layout.js — it lost <html>/<body>")
        title = self.plan.get("title", "AgentForge App")
        self.write_file("app/layout.jsx", textwrap.dedent(f"""\
            import './globals.css'

            export const metadata = {{ title: {json.dumps(title)} }}

            export default function RootLayout({{ children }}) {{
              // suppressHydrationWarning is on <html> and <body> because
              // extensions — Grammarly (data-gr-ext-installed), QuillBot
              // (data-qb-installed), password managers — inject attributes
              // into exactly these two elements before React hydrates. That
              // produces a red "tree hydrated but some attributes … didn't
              // match" overlay on every page for anyone running one, and it
              // is not a fault in the app. The suppression is one level deep:
              // real mismatches inside the tree are still reported.
              return (
                <html lang="en" suppressHydrationWarning>
                  <body className="min-h-screen antialiased" suppressHydrationWarning>
                    {{children}}
                  </body>
                </html>
              )
            }}
            """))
        return False

    STRAY_DIRECTIVE_RE = re.compile(
        r"^[^\S\n]*['\"]use client['\"][^\S\n]*;?[^\S\n]*$", re.M)

    def lint_generated(self) -> list:
        """Problems worth one targeted repair turn rather than shipping."""
        errors = []
        for path, content in self._next_files():
            hits = list(self.STRAY_DIRECTIVE_RE.finditer(content))

            for m in hits:
                head = content[:m.start()]
                head = re.sub(r"//[^\n]*|/\*.*?\*/", "", head, flags=re.S).strip()
                if head:
                    line = content[:m.start()].count("\n") + 1
                    errors.append(
                        f"{path}:{line}: a 'use client' directive appears after "
                        f"other code — it must be the first line of the file, "
                        f"and only once. Move the interactive part into its own "
                        f"file under components/ and import it.")
                    break
        ts = re.compile(r"^\s*interface\s+\w+|:\s*(string|number|boolean|any)\s*[,)=;]"
                        r"|\bas\s+(string|number|const)\b")
        for path, content in self._next_files():
            if ts.search(content):
                errors.append(f"{path}: contains TypeScript syntax — this is a "
                              f"JavaScript project")
            if "react-router-dom" in content:
                errors.append(f"{path}: imports react-router-dom — Next.js uses "
                              f"filesystem routing, not a router library")
            if re.search(r"\bnew\s+MongoClient\b", content):
                errors.append(f"{path}: constructs a MongoClient — import "
                              f"getDb/getCollection from '@/lib/mongodb' instead")
            if "next/head" in content and "<Head" in content:
                errors.append(f"{path}: uses next/head — the App Router has no "
                              f"<Head>; export a `metadata` object instead")
            if path.endswith("route.js") and re.search(r"export\s+default", content):
                errors.append(f"{path}: route handlers must use named exports "
                              f"(GET/POST/...), never export default")
        for path in self.files:
            if path.startswith("pages/"):
                errors.append(f"{path}: the Pages Router is banned — put routes "
                              f"under app/")
            if path.endswith((".ts", ".tsx")):
                errors.append(f"{path}: TypeScript files are banned — use .js/.jsx")

        try:
            from agents.exports import check_syntax, syntax_messages
            broken, _why = check_syntax(self.project_dir, self.files)
            errors.extend(syntax_messages(broken))
        except Exception:                                  # noqa: BLE001

            pass

        for name in self.unresolved_packages():
            errors.append(f"'{name}' is imported but not installed — run "
                          f"<run_command>npm install {name}</run_command>")

        errors.extend(self.client_server_mix())
        errors.extend(self.undefined_jsx_components())
        errors.extend(self.orphaned_components())
        errors.extend(self.event_handlers_in_server())
        errors.extend(self.component_props_to_client())
        errors.extend(self.broken_named_imports())

        for path in self.missing_planned_files():
            errors.append(f"{path}: the plan lists this file but it was never "
                          f"written — the route it serves will 404")
        return errors

    JSX_TAG_RE = re.compile(r"</?([A-Z][\w.]*)")

    def orphaned_components(self) -> list:
        """
        Components written and then never rendered by anything.

        The opposite of `undefined_jsx_components`, and the quieter of the two:
        a component nobody imports does not break a build, does not fail a
        test, and does not show up in a route probe. It simply is not there.

        Measured shape: a bakery whose `components/Navbar.jsx` held the site's
        entire navigation and its logo, and whose `app/layout.jsx` rendered
        `{children}` and nothing else. Every gate passed. The app shipped with
        no navigation on any page, and the logo the user had picked and
        approved was on disk, referenced, and invisible. Six other generated
        apps had the same shape — `TopBar`, `CartDrawer`, `ProductTable`.

        Layouts and pages are excluded: Next mounts those by their path, so
        `app/**/page.jsx` being imported by nobody is how routing works.
        """
        out = []
        comps = {p: c for p, c in self._next_files()
                 if p.startswith("components/") and p.endswith((".jsx", ".js"))}
        if not comps:
            return out
        others = [(p, c) for p, c in self._next_files() if p not in comps]
        for path in sorted(comps):
            name = Path(path).stem
            if name.lower() in ("index",):
                continue
            used = re.compile(rf"\b{re.escape(name)}\b")
            if any(used.search(body) for _, body in others):
                continue

            if any(used.search(b) for p, b in comps.items() if p != path):
                continue
            out.append(
                f"{path}: nothing imports or renders {name}. It was written "
                f"and then left out of the tree, so none of it reaches a "
                f"page. Either render it where it belongs — a navbar goes in "
                f"app/layout.jsx around {{children}} — or say why it is not "
                f"needed and delete it.")
        return out

    def undefined_jsx_components(self) -> list:
        """
        Components rendered in JSX that the file never imports or defines.

        The measured shape: `app/page.jsx` renders `<ShoppingCart size={20}/>`
        and the lucide import at the top lists every icon on the page except
        that one. It compiles — JavaScript has no compile-time check for a free
        identifier — and dies at request time with `ReferenceError:
        ShoppingCart is not defined`, taking the whole page with it.

        The test is deliberately conservative: a name is only reported when
        EVERY occurrence of it in the file is a JSX tag. One mention anywhere
        else — an import, a `function` of that name, a destructured prop, an
        assignment — and it is left alone. That way a component arriving by a
        route this cannot model is never falsely accused, at the cost of
        missing a name that is also used as a bare prop value.
        """
        out = []
        for path, content in self._next_files():
            code = strip_noncode(content)
            used = {m.group(1).split(".")[0]
                    for m in self.JSX_TAG_RE.finditer(code)}
            missing = []
            for name in sorted(used):
                total = len(re.findall(rf"\b{re.escape(name)}\b", code))
                as_tag = len(re.findall(rf"</?{re.escape(name)}\b", code))
                if total and total == as_tag:
                    missing.append(name)
            if missing:
                out.append(
                    f"{path}: renders {', '.join(missing[:5])} but never "
                    f"imports or defines "
                    f"{'them' if len(missing) > 1 else 'it'} — this compiles "
                    f"and then throws \"{missing[0]} is not defined\" the "
                    f"first time the page is requested. Add the missing "
                    f"import at the top (lucide icons come from "
                    f"'lucide-react'), or remove the element.")
        return out

    EVENT_PROP_RE = re.compile(r"\bon[A-Z]\w*\s*=\s*{")

    def event_handlers_in_server(self) -> list:
        """
        Event handlers in files that are not Client Components.

        React cannot send a function across the server boundary, so
        `<img onError={…}>` in a Server Component throws "Event handlers cannot
        be passed to Client Component props" the first time the page renders.
        It compiles, so nothing before this notices.

        Measured: a generated shop put an `onError` fallback on every product
        image — a sensible instinct — and two of the four files holding one
        were Server Components. The page shipped and died on the first request.

        The fix is almost never to add 'use client' to the page: that drags a
        database read into the browser. It is to move the element that needs
        the handler into its own small client component.
        """
        out = []
        for path, content in self._next_files():
            if re.match(r"\s*['\"]use client['\"]", content):
                continue
            hits = sorted({m.group(0).rstrip("={ ").strip()
                           for m in self.EVENT_PROP_RE.finditer(content)})
            if hits:
                out.append(
                    f"{path}: has {', '.join(hits[:4])} but is a Server "
                    f"Component — React throws \"Event handlers cannot be "
                    f"passed to Client Component props\" on the first render. "
                    f"Move just that element into its own 'use client' "
                    f"component and render it here; do NOT add 'use client' to "
                    f"this file.")
        return out

    COMPONENT_PROP_RE = re.compile(r"\b(\w+)\s*=\s*\{\s*([A-Z]\w*)\s*\}")

    def component_props_to_client(self) -> list:
        """
        Server files handing a React component down as a prop.

        This is the error that ships green: React logs "Only plain objects can
        be passed to Client Components" on the server, the page still returns
        200, and nothing that reads status codes or the browser console ever
        sees it. A four-stat dashboard throws it four times.

        Detected rather than inferred: the file has no 'use client', it imports
        a name from lucide-react (or defines a component), and it passes that
        exact name as a prop value. Anything imported from '@/components/…' is
        excluded — passing a component to a *server* component is fine, and the
        check cannot tell which the target is, so the icon case is the one
        worth being sure about.
        """
        out = []
        for path, content in self._next_files():
            if re.match(r"\s*['\"]use client['\"]", content):
                continue
            icons = set()
            for m in re.finditer(r"import\s*\{([^}]*)\}\s*from\s*['\"]lucide-react['\"]",
                                 content):
                icons.update(n.strip().split(" as ")[-1].strip()
                             for n in m.group(1).split(",") if n.strip())
            if not icons:
                continue
            named = sorted({v for _, v in self.COMPONENT_PROP_RE.findall(content)
                            if v in icons})
            if named:
                out.append(
                    f"{path}: passes the lucide icon(s) "
                    f"{', '.join(named[:4])} as a prop from a Server "
                    f"Component. A function cannot cross into a Client "
                    f"Component — React throws \"Only plain objects can be "
                    f"passed to Client Components\" and the page still "
                    f"returns 200. Import the icons inside the client "
                    f"component, keep a name→icon map there, and pass the "
                    f"NAME as a string.")
        return out

    SERVER_ONLY_RE = re.compile(
        r"""(?:from|import)\s*\(?\s*['"](@/lib/(?:mongodb|auth|seed)"""
        r"""|next/headers|mongodb|bcryptjs)['"]""")
    CLIENT_FEATURE_RE = re.compile(
        r"\buse(?:State|Effect|Ref|Reducer|Context|Callback|Memo|Router|"
        r"Pathname|SearchParams|Params|FormState|Transition)\s*\(|\bon[A-Z]\w+\s*=\s*\{")

    def client_server_mix(self) -> list:
        """
        `'use client'` on a file that does Server-Component-only work.

        This is the failure that moves around between generation rounds: the
        model marks a page `'use client'` because it has one onClick, then keeps
        the database read, the cookie check and the `async` default export in
        the same file. `next build` compiles it — so every existing gate is
        happy — and the route 500s on the first request.

        The observed instance had all three markers at once:

            'use client'
            import { getCollection } from '@/lib/mongodb'
            import { getSessionUser } from '@/lib/auth'
            export default async function InventoryPage() { … }

        A client component cannot be async, cannot reach the driver and cannot
        read cookies. The repair is the one a person would make: the page stays
        a Server Component and the interactive part moves to its own file.
        """
        out = []
        for path, content in self._next_files():
            first = next((l.strip() for l in content.splitlines() if l.strip()), "")
            if not first.startswith(("'use client'", '"use client"')):
                continue
            body = content[len(first):]
            reasons = []
            m = self.SERVER_ONLY_RE.search(body)
            if m:
                reasons.append(f"imports {m.group(1)}")
            if re.search(r"export\s+default\s+async\s+function", body):
                reasons.append("its default export is `async`, which a Client "
                               "Component may never be")
            if not reasons:
                continue
            keeps = bool(self.CLIENT_FEATURE_RE.search(body))
            out.append(
                f"{path}: is marked 'use client' but " + " and ".join(reasons) +
                ". Delete the 'use client' line and keep this file a Server "
                "Component" +
                (", then move ONLY the interactive markup — the parts with "
                 "onClick/onChange/useState — into a new file under "
                 "components/ that starts with 'use client', and render it "
                 "from here."
                 if keeps else
                 ". It uses no hooks or handlers, so nothing else has to move.")

                + " Do NOT touch next.config.mjs and do NOT add webpack "
                  "resolve.fallback — that hides this error instead of fixing "
                  "it, and the page still returns 500.")
        return out

    def broken_named_imports(self) -> list:
        """
        Named imports of a local module that the module does not export.

        JavaScript has no compile-time export checking, so `next build` compiles
        these happily and the app 500s at request time instead — which is how a
        login can reach the dashboard and bounce straight back with nothing in
        the logs but a stack trace. `repair_missing_imports()` above checks that
        the *file* exists; this checks that the *names* do.
        """
        return group_messages(check_named_imports(self.files))

    def _stems(self) -> set:
        """Every written path with its .js/.jsx extension stripped."""
        return {re.sub(r"\.jsx?$", "", p) for p in self.files}

    def missing_planned_files(self) -> list:
        """
        Files the plan promised that no phase actually produced.

        Compared on the extension-stripped stem, because this function used to
        MANUFACTURE the very collision the extension rule exists to prevent: a
        plan entry `components/TaskList.jsx` satisfied by a written
        `components/TaskList.js` was reported missing, that message reached
        `lint_generated()` and then `repair_lint()`, and the model dutifully
        created the second stem. `write_file` now canonicalises extensions, so
        the two can only differ while a plan written before the rule is being
        replayed — which is exactly when a false "missing" is most expensive.
        """
        planned = [f["path"] for p in self.plan.get("phases", [])
                   for f in p.get("files", [])]
        stems = self._stems()
        return [p for p in planned
                if p not in self.files and re.sub(r"\.jsx?$", "", p) not in stems]

    def apply_next_fixes(self) -> None:
        """All mechanical repairs, in dependency order."""
        if self.stack != "next":
            return
        self.fix_next_imports()
        self.strip_server_img_handlers()
        self.enforce_use_client()
        self.enforce_dynamic()
        self.verify_root_layout()
        self.verify_auth_config()

    def unresolved_packages(self) -> list:
        """
        Imported npm packages that are neither declared nor installed.

        Without this, an unplanned `import bcrypt from 'bcryptjs'` produced a
        `Module not found` only at request time — long after the pipeline had
        declared success. Surfacing them lets the fix loop tell the model to
        install them with its command tool.
        """
        try:
            pkg = json.loads((self.project_dir / "package.json")
                             .read_text(encoding="utf-8"))
            declared = set(pkg.get("dependencies", {})) | set(pkg.get("devDependencies", {}))
        except Exception:
            declared = set()

        nm = self.project_dir / "node_modules"
        missing = []
        for path, content in self.files.items():
            if not path.endswith((".js", ".jsx")):
                continue
            for name in self.imported_packages(content):
                if name in declared or (nm / name / "package.json").exists():
                    continue
                if name not in missing:
                    missing.append(name)
        return missing

    IMPORT_SPEC_RE = re.compile(
        r"""(?:\bfrom\s*|\brequire\s*\(\s*|\bimport\s*\(\s*|\bimport\s+)"""
        r"""['"]([^'"\s()]+)['"]""")

    PKG_NAME_RE = re.compile(r"^(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$", re.I)

    NODE_BUILTINS = {
        "assert", "buffer", "child_process", "cluster", "console", "constants",
        "crypto", "dgram", "diagnostics_channel", "dns", "domain", "events",
        "fs", "fs/promises", "http", "http2", "https", "inspector", "module",
        "net", "os", "path", "perf_hooks", "process", "punycode", "querystring",
        "readline", "repl", "stream", "string_decoder", "timers", "tls",
        "trace_events", "tty", "url", "util", "v8", "vm", "worker_threads",
        "zlib",
    }
    PREINSTALLED = {"react", "react-dom", "next", "mongodb"}

    @classmethod
    def imported_packages(cls, content: str) -> list:
        """npm package names a source file imports, in any syntax."""
        out = []
        for spec in cls.IMPORT_SPEC_RE.findall(content or ""):
            if spec.startswith((".", "/", "@/")):
                continue
            if spec.startswith("node:"):
                continue
            name = ("/".join(spec.split("/")[:2]) if spec.startswith("@")
                    else spec.split("/")[0])
            if (name in cls.NODE_BUILTINS or spec in cls.NODE_BUILTINS
                    or name in cls.PREINSTALLED or spec.startswith("next/")):
                continue
            if not cls.PKG_NAME_RE.match(name):
                continue
            if name not in out:
                out.append(name)
        return out

    def sync_dependencies(self) -> None:
        """Add any npm package the generated code imports but package.json lacks."""
        used = set()
        bare = re.compile(r"""from\s+['"]([^.'"][^'"]*)['"]""")
        for path, content in self.files.items():
            if path.endswith((".jsx", ".js")):
                for spec in bare.findall(content):
                    pkg = "/".join(spec.split("/")[:2]) if spec.startswith("@") \
                        else spec.split("/")[0]
                    used.add(pkg)

        pkg_path = self.project_dir / "package.json"
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
        except Exception:
            return
        deps = data.get("dependencies", {})
        added = []
        for name in sorted(used):
            if name in deps or name in data.get("devDependencies", {}):
                continue
            if name in self.BANNED_DEPS:
                self._log("WARN", f"   ⚠ Refusing to install {name} — it does "
                                  f"not belong in this stack")
                continue
            if name in self.EXTRA_DEPS:
                deps[name] = self.EXTRA_DEPS[name]
                added.append(name)
        if added:
            data["dependencies"] = dict(sorted(deps.items()))
            pkg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.files["package.json"] = json.dumps(data, indent=2)

            self.write_seq = getattr(self, "write_seq", 0) + 1
            self._log("INFO", f"   📦 Added deps: {', '.join(added)}")

    def run(self, user_prompt: str) -> bool:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        where = "☁️  cloud" if self.is_cloud else "💻 local"
        self._log("INFO", f"🤖 Agent mode — {self.model} ({where}, "
                          f"ctx {self.num_ctx:,})")

        try:
            self._fire("on_progress", "Planning…", 5)
            if not self.make_plan(user_prompt):
                return False

            self._fire("on_progress", "Scaffolding…", 15)
            self.scaffold()
            self.install_planned_deps()

            self._fire("on_progress", "Writing files…", 18)
            self.build_app()
            self._fire("on_memory", self.memory_stats())

            self._fire("on_progress", "Checking imports…", 80)
            self.repair_missing_imports()
            self.apply_next_fixes()
            self.sync_dependencies()
            self.install_unresolved()
            self.repair_lint()

            return self._verify_output()
        finally:

            self.save_convo()

    def unfinished(self) -> list:
        """
        Planned files this project never produced, or `[]` if it is complete.

        The whole resume story rests on this being derived from disk rather
        than from a saved cursor: a cursor can disagree with reality after a
        crash, a directory listing cannot.
        """
        if not self.plan.get("phases"):
            return []
        return self.missing_planned_files()

    def resume(self) -> bool:
        """
        Pick a half-finished build back up where it stopped.

        Nothing here re-plans and nothing re-scaffolds. `build_app` asks the
        disk which planned files are missing and continues the same
        conversation — reloaded from `.agentforge/convo.json` — so a machine that
        lost power mid-build carries on from the next unwritten file with the
        model still knowing every decision it had already made.

        The one thing a resume must not do is start over. That is why the plan
        is loaded rather than regenerated: a second planning pass would produce
        a different file list, and the half of the app already on disk would
        belong to a plan nobody has any more.
        """
        missing = self.unfinished()
        if not self.plan.get("phases"):
            self._log("ERROR", "   ❌ No plan on disk — this project cannot be "
                               "resumed, only rebuilt")
            return False
        if not self.convo:

            self._log("WARN", "   ⚠ No saved conversation — resuming from the "
                              "plan alone")
            self.start_conversation(self.plan.get("description")
                                    or self.plan.get("title") or "this app")

        total = sum(len(p.get("files", [])) for p in self.plan["phases"])
        self._log("INFO", f"⏭️  Resuming — {total - len(missing)}/{total} files "
                          f"already written, {len(missing)} to go")
        try:
            self._fire("on_progress", "Resuming…", 18)
            if missing:
                self.build_app()
                self._fire("on_memory", self.memory_stats())

            self._fire("on_progress", "Checking imports…", 80)
            self.repair_missing_imports()
            self.apply_next_fixes()
            self.sync_dependencies()
            self.install_unresolved()
            self.repair_lint()
            return self._verify_output()
        finally:
            self.save_convo()

    def repair_lint(self) -> int:
        """
        Hand the static findings to the model, once.

        `lint_generated()` has always detected misplaced directives, TypeScript
        syntax, Pages-Router files and hand-rolled MongoClients — but its output
        only ever reached a WARN log line, so nothing was ever done about it.
        Here is the one place `_run_write_loop` is the right primitive: the
        build thread is still open and the model still remembers writing these
        files, so a single turn fixes them in context.

        Deliberately not a loop — a lint-fix-relint cycle is how a build starts
        thrashing. Whatever survives is reported by the analyzer and the build.
        """
        if self.stack != "next":
            return 0

        problems = [p for p in self.lint_generated()
                    if "imported but not installed" not in p]
        if not problems:
            return 0

        self._log("WARN", f"🔍 {len(problems)} static problem(s) found — "
                          f"asking for a repair pass")
        self._fire("on_phase", {"phase": -6, "title": "Lint repair",
                                "status": "active"})
        n = self._run_write_loop(textwrap.dedent(f"""\
            A static check found these problems in the files you wrote:
            {chr(10).join('  • ' + p for p in problems[:12])}

            Fix every one. Rewrite the COMPLETE file for each file named above,
            and touch no other file. If a file has a 'use client' part-way down,
            split it: the server half stays, the interactive half moves to its
            own file under components/ with 'use client' on line 1.

            WHEN YOU SPLIT, THE HANDLER GOES WITH THE STATE. The server half
            may pass strings, numbers, arrays and plain objects to the client
            half — never a function. If the server page currently passes an
            onSelect or onChange prop, that state belongs inside the new client
            component, which owns it and needs no prop at all. A server
            component that passes a handler compiles cleanly and then throws
            "Event handlers cannot be passed to Client Component props" on the
            first request, which is exactly the failure this split is supposed
            to prevent.
            """))
        self._fire("on_phase", {"phase": -6, "title": "Lint repair",
                                "status": "done", "written": n})

        if n:
            self._fix_boundary_props()
        return n

    def _fix_boundary_props(self) -> int:
        """Rewrite server components caught passing a function to a client one."""
        bad = self.event_handlers_in_server()
        if not bad:
            return 0
        self._log("WARN", f"🚧 {len(bad)} server component(s) still pass a "
                          f"handler across the boundary — repairing")
        self._fire("on_phase", {"phase": -6, "title": "Boundary repair",
                                "status": "active"})
        n = self._run_write_loop(textwrap.dedent(f"""\
            These files are Server Components that pass an event handler to a
            Client Component. React throws "Event handlers cannot be passed to
            Client Component props" on the first request — the build does not
            catch it, so it ships:
            {chr(10).join('  • ' + p for p in bad[:8])}

            Fix each one by MOVING THE STATE, not by adding 'use client' to the
            page. The component that needs the handler owns it: give it the
            data as plain props and let it hold its own useState. Rewrite the
            COMPLETE file for each file named above, plus the client component
            that should now own the state. Touch nothing else.
            """))
        self._fire("on_phase", {"phase": -6, "title": "Boundary repair",
                                "status": "done", "written": n})
        return n

    def install_planned_deps(self) -> int:
        """
        Install plan dependencies that the scaffold could not pin.

        `_scaffold_next` writes package.json from a version-pinned allowlist,
        so a package the plan named but the allowlist does not know would be
        silently dropped and only surface as `Module not found` much later.
        Install those up front — deterministically, without spending an LLM
        turn on it.
        """
        if self.stack != "next":
            return 0
        unknown = [d.strip().split("@")[0] for d in self.plan.get("dependencies", [])
                   if isinstance(d, str) and d.strip()]
        unknown = [d for d in unknown
                   if d and d not in self.NEXT_EXTRA_DEPS
                   and d not in self.BANNED_DEPS
                   and d not in ("react", "react-dom", "next", "mongodb",
                                 "tailwindcss", "postcss", "autoprefixer")]
        if not unknown:
            return 0
        self._log("INFO", f"📦 Plan needs {', '.join(unknown)} — installing")
        res = self.cmd.run("npm install " + " ".join(unknown))
        return 1 if res.ok else 0

    def install_unresolved(self) -> int:
        """
        Let the model install anything it imported but never declared.

        sync_dependencies() only knows a fixed allowlist, so a package outside
        it (bcryptjs for a hand-rolled login, say) would otherwise reach the
        browser as `Module not found`. Asking the model to install it turns a
        silent runtime 500 into a one-command fix.
        """
        if self.stack != "next":
            return 0
        missing = self.unresolved_packages()
        if not missing:
            return 0

        self._log("WARN", f"📦 {len(missing)} package(s) imported but not "
                          f"installed: {', '.join(missing)}")
        self._fire("on_phase", {"phase": -4, "title": "Installing packages",
                                "status": "active"})
        n = self._run_write_loop(textwrap.dedent(f"""\
            These packages are imported by the code you wrote but are not
            installed:
            {chr(10).join('  • ' + m for m in missing)}

            Install each one now, one block per command:
            <run_command>npm install {missing[0]}</run_command>

            If a package should not be there at all, rewrite the file that
            imports it instead. Do not write any other files.
            """))
        self._fire("on_phase", {"phase": -4, "title": "Installing packages",
                                "status": "done"})
        still = self.unresolved_packages()
        if still:
            self._log("WARN", f"   ⚠ Still unresolved: {', '.join(still)}")
        return n

    def _verify_output(self) -> bool:
        """Did the model actually build something, or just inherit the scaffold?"""
        entry = self._P["entry"]
        if not any(p in self.files for p in entry):
            self._log("ERROR", f"   ❌ No {entry[0]} was generated")
            return False

        if self.stack == "next":
            scaffolded = self.NEXT_SCAFFOLD | {"plan.md"}
            generated = [p for p in self.files if p not in scaffolded]
            if len(generated) < 3:
                self._log("ERROR", f"   ❌ Only {len(generated)} file(s) beyond "
                                   f"the scaffold — the model produced nothing")
                return False
            for problem in self.lint_generated()[:6]:
                self._log("WARN", f"   ⚠ {problem}")
        return True

    def update(self, instruction: str) -> int:
        """Agentic edit of an existing project — same tool loop, no plan."""
        self._log("INFO", f"✏️  Agent update — {instruction[:70]}")
        return self._update(instruction)

    def _update_turn(self, instruction: str) -> str:
        """
        The user turn an update is asked with: current source, then the ask.

        Always the current source. This used to be attached only when the
        thread was empty — `if not self.convo` — and the thread is never empty
        for a project AgentForge built, because `load_existing()` restores
        `convo.json` first. So the block was skipped every time it mattered,
        and the model was left editing from the receipts `_stub_files` leaves
        behind: `// [written earlier — 84 lines, still on disk]`. Measured on a
        real project: 29 of 31 file bodies stubbed, including the page the user
        was asking about. What a model does with that is regenerate the file
        from the plan, which quietly throws away every edit made since.

        Separate from `update()` so the prompt can be asserted without a model
        call.
        """
        snap = self._context_snapshot(**self._snapshot_caps())
        return (f"{SNAPSHOT_OPEN}\n{snap}\n{SNAPSHOT_CLOSE}\n\n"
                + textwrap.dedent(f"""\
                ## Change requested
                {instruction}

                Rewrite only the files that must change, complete, via
                <write_file> blocks. Create new files when the change needs
                them. Keep everything else untouched and preserve the existing
                style.

                A file shown above ending in `// …truncated…` is NOT the whole
                file. Do not rewrite one of those from what you were shown —
                you would delete the part you cannot see. Say so instead.
                """))

    def _snapshot_caps(self) -> dict:
        """
        How much source a snapshot may carry, from the window we actually have.

        The old fixed `18 × 2000` cut a 6 KB page in half on a 262k-token
        model, and a half file invites the model to invent the rest — the same
        silent damage as a stale one, arriving by a different road.
        """
        budget = self._budget_chars()
        if budget >= 200_000:
            return {"max_files": 40, "per_file": 24_000}
        if budget >= 80_000:
            return {"max_files": 28, "per_file": 8_000}
        return {"max_files": 18, "per_file": 2_000}

    def _update(self, instruction: str) -> int:

        if not self.convo:
            self.convo = [
                {"role": "system",
                 "content": self._builder_sys()},
                {"role": "user", "content":
                    f"Here is the existing app we are editing.\n\n"
                    f"## Plan\n{self.plan_md[:3000] or '(no plan.md)'}"},
                {"role": "assistant", "content":
                    "I have read the plan. Show me the code and tell me what "
                    "to change."},
            ]

        n = self._run_write_loop(self._update_turn(instruction))
        self.repair_missing_imports()
        self.apply_next_fixes()
        self.sync_dependencies()
        return n

    SKIP_DIRS = {"node_modules", ".git", "dist", ".vite", ".next", "out",
                 ".turbo", "public", ".agentforge", "tests"}

    SKIP_FILES = {"vitest.config.mjs", "playwright.config.js"}

    def load_existing(self):
        """Populate self.files from disk — needed before update()."""

        if (self.project_dir / "next.config.mjs").exists() or \
                (self.project_dir / "next.config.js").exists():
            self.stack = "next"
        elif (self.project_dir / "vite.config.js").exists():
            self.stack = "vite"

        for fp in self.project_dir.rglob("*"):
            if not fp.is_file() or any(s in fp.parts for s in self.SKIP_DIRS):
                continue
            if fp.name in self.SKIP_FILES:
                continue
            if fp.suffix not in (".jsx", ".js", ".mjs", ".json", ".css",
                                 ".html", ".md"):
                continue

            if fp.name.startswith(".env"):
                continue
            try:
                if fp.stat().st_size > 200_000:
                    continue
                rel = str(fp.relative_to(self.project_dir)).replace("\\", "/")
                self.files[rel] = fp.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
        plan_fp = self.project_dir / "plan.md"
        if plan_fp.exists():
            self.plan_md = self.files.get("plan.md", "")
        self.plan = self.plan or self._load_plan_json()

        if self.load_convo():
            log.info("restored the build conversation "
                     f"({len(self.convo)} turns)")

    def _write_atomic(self, rel: str, text: str) -> None:
        """
        Write via a temp file and one rename.

        A build saves its thread after every turn, so a machine that loses
        power is overwhelmingly likely to do it during one of those writes. A
        plain `write_text` truncates first, which means the failure mode is a
        half-written or empty file — and the resume that file exists to make
        possible is exactly what would then be impossible. `os.replace` is
        atomic on both NTFS and POSIX, so the file is either the old one or the
        new one, never a fragment.
        """
        fp = self.project_dir / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        tmp = fp.with_suffix(fp.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, fp)

    PLAN_JSON = ".agentforge/plan.json"

    def _save_plan_json(self) -> None:
        """
        Keep the parsed plan next to the project.

        `plan.md` is written with the ```json block stripped out, so everything
        machine-readable in it — `demo_accounts`, each file's server/client
        `kind`, the phase list — used to die with the session. Reopening a
        project left `self.plan` empty forever, which is why AgentForge could not
        tell anyone the demo credentials of an app it had generated itself.

        It lives under `.agentforge/` rather than at the root so it does not show up
        in the project's file tree or its export zip.
        """
        if not self.plan:
            return
        try:
            self._write_atomic(self.PLAN_JSON,
                               json.dumps(self.plan, indent=2))
        except Exception as e:
            log.warning(f"could not save plan.json: {e}")

    def _load_plan_json(self) -> dict:
        try:
            fp = self.project_dir / self.PLAN_JSON
            if fp.exists():
                return json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"could not read plan.json: {e}")
        return {}

    CONVO_JSON = ".agentforge/convo.json"

    CONVO_SAVE_CHARS = 400_000

    def save_convo(self) -> bool:
        """
        Persist the build conversation, so a later edit inherits its memory.

        The thread is the most valuable thing a build produces and the only
        thing that used to die with the process. It holds every decision the
        model made and why — which component owns which prop, which collection
        a page reads, why the cart lives in a client component. A feature added
        an hour later opened a fresh context and had to re-derive all of it
        from the file inventory, which is exactly how a "small addition" ends
        up restyling three pages.

        Bodies are replaced by receipts first, the same compaction
        `_trim_convo` uses: the code itself is on disk and `_context_snapshot`
        re-injects whatever the next turn actually needs. What is worth keeping
        is the reasoning around it.
        """
        if len(self.convo) < 3:
            return False
        try:
            self._back_up_thread_once()
            slim = []
            for m in self.convo:

                content = self._strip_snapshot(m.get("content") or "")
                content = self._stub_files(content)
                slim.append({"role": m.get("role", "user"), "content": content})

            total = sum(len(m["content"]) for m in slim)
            head, tail = slim[:3], slim[3:]
            while total > self.CONVO_SAVE_CHARS and tail:
                total -= len(tail.pop(0)["content"])

            self._write_atomic(self.CONVO_JSON, json.dumps(
                {"model": self.model, "stack": self.stack,
                 "messages": head + tail}, indent=1))
            return True
        except Exception as e:
            log.warning(f"could not save convo.json: {e}")
            return False

    CONVO_BACKUP = ".agentforge/convo.pre-strip.json"

    def _back_up_thread_once(self) -> None:
        """
        Keep one copy of the thread as it was before the first strip.

        Widening the compaction to user turns rewrites `convo.json` in place
        and there is no undo. For a project whose disk has drifted from its
        thread, that copy is the only record of what the model was told. One
        file, written once, never touched again.
        """
        try:
            src = self.project_dir / self.CONVO_JSON
            dst = self.project_dir / self.CONVO_BACKUP
            if src.is_file() and not dst.exists():
                dst.write_text(src.read_text(encoding="utf-8"),
                               encoding="utf-8")
        except Exception as e:
            log.debug(f"convo backup: {e}")

    def load_convo(self) -> bool:
        """Restore a saved build thread. False when there is none to restore."""
        if self.convo:
            return False
        try:
            fp = self.project_dir / self.CONVO_JSON
            if not fp.is_file():
                return False
            data = json.loads(fp.read_text(encoding="utf-8"))
            msgs = [m for m in (data.get("messages") or [])
                    if isinstance(m, dict) and m.get("role") and m.get("content")]
            if len(msgs) < 3:
                return False
            self.convo = msgs
            self._trim_convo()
            return True
        except Exception as e:
            log.warning(f"could not read convo.json: {e}")
            return False
