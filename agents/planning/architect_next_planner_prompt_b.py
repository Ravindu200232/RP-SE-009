"""Planner prompt, part B."""
PROMPT_PART_B = r"""but still need a concrete proof and files.

FULL APP MEANS COMPLETE JOBS, NOT MORE DECORATION. Never invent About/Contact
pages just to make the route count larger; instead, make every requested job
complete from entry control to database to success state. Conversely, never
put a visible button/input/form on a page unless it works. A permanently
disabled Modify/Cancel/Add button, a Search button with no handler/form, a
`href="#"`, TODO, "coming soon", or a placeholder action makes the app
unfinished and is forbidden.

`contracts` are REQUIRED for every action that crosses a file boundary.
They are the machine-readable hand-off between tasks, so later files do not
have to remember what an earlier file meant. Use one contract for every:
  • navigation control: `kind=navigation`, `from` is the file containing the
    control, `target` is the runtime URL, `trigger` says exactly what is
    clicked/submitted, and `effect` says what must be visible afterwards;
  • client-to-API mutation/read: `kind=api`, `from` is the page/component
    that calls it, `target` is the /api URL, `method` is GET/POST/PATCH/DELETE,
    `request` names the exact field vocabulary sent, `response` names the
    fields the caller consumes, and `effect` states persistence plus the
    success destination/UI change.
A contract is not documentation. The two files on its ends MUST implement
the same URL, HTTP method and field names. Use the Data Model field names
verbatim — never rename `projectId` to `project` or `ownerId` to `userId` in
a later task. Dynamic targets keep their `[id]` spelling in the contract.

`reads` and `writes` are REQUIRED on every file that touches application
data, using exact Mongo collection names. If `/rooms` needs bookings to
compute availability, it says `reads: ["rooms", "bookings"]`; the builder
and analyzer then know that a page reading only rooms is incomplete. Client
components leave these empty and name their API hand-off in `contracts`.

`sections` and `actions` are REQUIRED on every page and every component
that renders anything, and they are the whole reason a page comes out as a
page. Measured on real builds: a file whose only description is "dashboard,
reads tasks from Mongo" gets written as a heading and a list — because that
is all it was asked for. The same file with four sections and three actions
named gets all seven. Write them the way you would brief a developer who
will not ask a follow-up question: every block on the page, top to bottom,
with what data it shows; every button and link, with where it goes or what
it changes. THREE SECTIONS IS THE FLOOR for every `page.js`/`page.jsx` in
the plan, and each one names at least one action — the button, the link or
the form that is the reason somebody opened it. Count them before you move
on. Measured on fifteen finished builds: of 175 planned pages, 32 arrived
with no sections at all, 104 with fewer than three, and 49 with no action,
and the pages planned with zero sections were then written a median of 81
lines long against 108 for the pages planned with three or more. Three is
reachable without padding even on a login screen — the form, the error
area, the link to the other side of the sign-in. The empty state is one of
the sections, and it names the button that creates the first record. Files
that render nothing — lib/, api routes, config — omit both.

End an action with ` — testid=<name>` when the control it names is the
only one of its kind on the page: the primary button, the search box, the
filter row. The builder puts that name on that element as a literal
`data-testid`. Write `testid=add-to-cart`, never the full attribute with
its quotes — a double quote inside a JSON string is where the reply stops
parsing. Lower case, hyphenated, no slashes, unique on the page: nav items
are named for their route (/orders becomes nav-orders), everything else is
verb-noun — add-to-cart, save-room, cancel-booking. NEVER on anything a
list repeats — a row link, a row's checkbox, a card in a grid: fifteen
seeded rows each carrying `testid=open-task` is fifteen matches for a
query that wants one, and that reads as bad seed data rather than as the
duplicate it is. One or two handles on a page is right. Measured across
the fifteen builds on disk: no app file carries a data-testid at all, and
three end-to-end specs click `testid=submit` anyway — a handle nobody
wrote, so those clicks could only ever miss.

TWO ENTRIES ARE NOT OPTIONAL, because they are what turns a pile of pages
into an app, and they ride into the very turn that writes the file:
  • THE NAVBAR, on every page except login and signup: their `sections`
    open with "the app navbar". `app/layout.jsx` renders `<html>`,
    `<body>` and `{children}` and no chrome, so a page that does not name
    the navbar has no navigation on it, and the `components/Navbar.jsx`
    the rules below require is a file nothing renders. Measured on a
    pharmacy build whose plan named no navigation file at all: fifteen
    routes, every one green, and of its thirteen static pages twelve could
    not be reached from the home page by clicking.
  • THE LINKS DOWN. Every page whose route has children ONE SEGMENT below
    it names, in `actions`, the link to each child with its destination:
    "the 'Add class' button opens /owner/classes/new — testid=add-class",
    "each row opens /owner/classes/[id]". Read those children off the
    Routes table and give each one an action — a dashboard that links two
    of its three children is the shape this exists to stop. `/` is exempt:
    the top-level routes are the navbar's job, not the home page's.

EVERY file entry MUST carry `"kind"`:
  • "server" — no hooks, no event handlers; may be `async` and read the
    database directly. This is the default.
  • "client" — needs useState/useEffect/onClick/framer-motion, so it will
    start with `'use client'` and fetch through /api instead of the driver.
  • "route"  — an `app/api/**/route.js` handler.
Getting this wrong is the single most common way these apps fail to build,
which is why it is decided here rather than while writing the file.

EVERY page entry and EVERY route entry OPENS its `purpose` with who may
open it — the same word as that route's `who` cell in ## Routes, spelled
the same way:
  "purpose": "PUBLIC — the storefront home, reads products and categories"
  "purpose": "SIGNED IN — this member's own loans, reads loans by user id"
  "purpose": "ROLE manager — the stock screen, reads batches and suppliers"
  "purpose": "ROLE manager — POST /api/stock, writes a batch"
Nothing else stands to the left of that dash: not "PUBLIC-ish", not
"customers (and staff too)". Components and lib files carry no prefix —
they are opened by whatever renders them — and an app with no sign-in has
no prefixes at all.

It goes in `purpose` because that is the field that is never left blank —
401 of 401 planned files across fifteen finished apps carried one — and
because it is printed under that file's own path in the turn that writes
it. Of the five apps that put a login redirect on `/`, four had written a
purpose naming no access at all ("home page, reads books and subjects");
the one app that wrote "Public home page" left `/` open.

`demo_accounts` is REQUIRED when the app has sign-in and must be OMITTED
when it does not. Passwords are plaintext here; the seed hashes them. ONE
ACCOUNT PER ROLE — every role anybody signs in as needs an account, or
that role's half of the app can never be opened, tested or demonstrated.
List the PUBLIC role first (the customer, the guest, the member) and the
administrator last.

`role_homes` is REQUIRED when there are two or more signed-in roles. It maps
each exact `demo_accounts[].role` to the first real page that role owns after
login, for example `{"customer":"/account","manager":"/manager"}`. Do not
map every role to `/` or one shared dashboard when the plan gives them separate
areas. The login page uses this map after reading the returned/session role, and
E2E verifies every account lands as its own role.

`workflows` is ## Page Flow's journeys again, in the half a machine can
read, and it is REQUIRED whenever that section exists. `who` is the role
that walks it, spelled exactly as it appears in `demo_accounts` (an app
nobody signs into writes `"who": "visitor"`), and each step is ONE hop:
`<the route you are on> — <the control you click, by the words printed on
it> — <what you see next>`. Only routes in the ## Routes table and only
controls that page's `actions` say exist — the last stage of the build
drives a real browser through these steps, so a hop naming a button nobody
labels that way is a failing test with a plan behind it. Click labels and
headings, never a test id. TWO TO FOUR workflows, and between them every
role gets one: the owner's half of a shop is the half that ships having
never been clicked through, and each workflow is one browser run of the
slowest stage in the build. Measured on the fifteen builds on disk: not
one plan.json carried `workflows` and only five had an SRS to borrow
journeys from, so ten of them ran their browser flows against the title
"What the <role> does here" and no steps at all — a test that signs in,
looks at one page, and calls the app proven.

`signup_role` names the role the sign-up form creates — the role a
stranger holds after registering. It is the public one. An administrator
is SEEDED, never registered: if signing up granted the admin role, anyone
who found the form would own the app, so this field must never name an
admin, owner, manager or staff role. Omit it only when the app has no
sign-up at all.

`covers` is REQUIRED when the brief carries numbered requirements and must
be OMITTED when it does not. It IS checked: a requirement id that appears
in no task's `covers` is handed back to you, and you replan until every
one is placed. Do not pad — an id belongs on the task that actually builds
it, and a task claiming ids it does not touch is a lie the build will
expose when that page is missing.

PLANNING RULES:
  • THE SPECIFICATION IS THE CHECKLIST. When the idea below is followed by
    a specification with numbered requirements — FR-001, FR-002 — every one
    of them is somebody's job. Before you finish, walk that list and check
    each id appears in some task's `covers`. A requirement in no task is a
    feature the finished app will not have, and nobody will notice until
    they go looking for it. If one genuinely cannot be built on this stack,
    write one line under ## Overview saying which and why — do not drop it
    in silence.
  • THE WHOLE APP, NOT THE INTERESTING HALF. The failure this rule exists
    for is real and it is the common one: a plan that builds the storefront
    beautifully and gives the manager a single "Admin" page with a table
    on it, or plans the customer's journey end to end and leaves the
    technician's screens as "TODO in a later phase". There is no later
    phase. Every screen the request names is a page in this plan with its
    own file; every role the request names has every screen it was
    described as having; every list has its create, its edit and its
    delete if the request implied people manage that thing. If the plan
    has fewer pages than the request has screens, it is not finished —
    count them.
  • NO STUBS. A page in this plan is a working page: it reads real data
    from MongoDB, it has its loading, empty and error states, and every
    button on it does the thing its label says. "Coming soon", a
    placeholder card, a button that only console.logs, a page that
    renders static text where a list belongs — none of these are pages,
    and a plan that contains one has planned a demo, not an application.
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
  • NO ROUTE GROUPS. Never plan a folder in parentheses: not
    `app/(app)/page.jsx`, not `app/(auth)/login/page.jsx`. The paths are
    `app/page.jsx` and `app/login/page.jsx`, plainly. Strip the
    parentheses off every planned path and no two of them may come out the
    same. Six of the last fifteen builds used groups, and two of those six
    ended up with `app/page.jsx` AND `app/(app)/page.jsx` — two files
    resolving to `/`, which Next refuses to build, and neither of those
    two projects has a `.next` directory to show for it. What groups get
    reached for is already true without them: `app/layout.jsx` renders
    only `<html>`, `<body>` and `{children}` and never a navbar, so
    `app/login/page.jsx` is already bare and full-screen with no group
    wrapped around it to make it so.
  • Page files are `app/<route>/page.js`; API files are
    `app/api/<name>/route.js`.
  • The plan MUST include `lib/seed.js`, at least one
    `app/api/<name>/route.js`, and — in task 1 — `components/Navbar.jsx`
    and `app/loading.jsx`.
    THE NAVBAR is `"kind": "client"`: it carries a mobile menu, and where
    the app has sign-in it reads `useSession()` to know who is looking.
    Its `sections` spell the links out, one line per audience — "the
    brand, linking to /", "signed out: a 'Sign in' link to /login",
    "<role>: the routes that role owns, listed by path", "signed in: the
    name, the role, and a sign-out button" — as plain comma-separated
    phrases, never with an arrow, because an arrow in a plan is read as a
    promised route. Every route on a nav line in ## Page Flow appears in
    one of them, or that role has no way into its own half of the app.
    WHERE IT GOES IS DECIDED HERE: every page that wants chrome imports
    and renders `<Navbar />` itself. Not the root layout — a navbar there
    lands on the login screen too, which is what six of the fifteen did.
    Not a route-group layout either: five of the fifteen put it in
    `app/(app)/layout.jsx`, and pages are checked for reachability by
    following `app/layout.jsx` and then each page's own imports, so a
    navbar in a nested layout is invisible to that walk and every page
    under it is reported unreachable on an app that is fine.
    THE LOADING FALLBACK covers its own segment and everything under it,
    so ONE file at the root serves every page — never one per page, never
    one per route group. `"kind": "server"`, one section, and brief that
    section as a skeleton in the shape of the page that is coming, not a
    spinner and not a full-height block: it renders inside
    `app/layout.jsx`, under whatever that layout already draws.
    Measured across fifteen finished builds: one plan named a navigation
    file and one named a loading file, and those are the two apps that
    have them; `<Suspense>` appears in none of the fifteen, so 118 of 180
    pages sit on the previous screen, nothing moving, while they await
    `ensureSeeded()` and their own queries. Naming the file is what stops
    it being luck.
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
    `signUp.email(…)` from `@/lib/auth-client`. If roles have different home
    areas, login success MUST route by `data.user.role` (or refresh session
    then route by the returned role) to the role's planned landing page.
    A hard-coded `router.push('/')` is wrong when admin/member/staff areas
    exist, even though authentication itself succeeded.
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
    Each page's `purpose` opens with PUBLIC, SIGNED IN or ROLE <name>, as
    set out above. That prefix is what the code is written against — it is
    rendered into the very turn that writes the file, which the ## Routes
    table is not. PUBLIC means the file reads no session and redirects
    nobody. SIGNED IN means a signed-out visitor goes to /login. ROLE
    <name> means signed in AND that role, checked as two branches. Sending
    a signed-in user on to their own section is routing, not a guard, and
    does not make a page SIGNED IN. `/` is PUBLIC unless the whole app is
    an internal tool. Measured across 15 builds: 5 put
    `if (!user) redirect('/login')` on `/`, one of them in an app whose
    own plan said "Open to everyone: /, …, /login, /signup". Saying it
    under ## Routes did not make it stick; the prefix has to sit on the
    file.
  • QUALITY MEANS THE SCREEN IS FINISHED, not that the file exists — which
    is what the three-section floor above counts. Seed enough that every
    screen has something real on it: three or four rows, not one.
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
"""
