---
name: nextjs-sketch
description: Copy the verified Next.js App Router + MongoDB skeleton — cached connection, model, server page, route handler, client component, Vitest config with mixed environments — instead of writing the boilerplate from memory.
---

# The Next.js + MongoDB sketch

The first fifteen files of a Next.js application are the same every time, and
they are where the avoidable failures live: a connection opened per hot reload,
`params` read as an object when it is a Promise, a page cached at build time
that never shows new data, a test suite that collects zero tests because the
config and the setup file disagree.

`sketch/` in this skill directory is a complete application that was
**installed, unit-tested, seeded, built, started and driven in a browser**.
Read those files and adapt them. Do not retype them from memory.

## What was actually verified

One run, in this order, all of it passing, against Next.js 15.5 and Vitest 2.1:

- `npm install`
- `npm test` — **11 tests, first run, no repairs**: 3 money, 4 component
  (jsdom), 4 data layer (node)
- `npm run seed` — 3 products, through the application's own model
- `npm run build` — compiled, 4 routes, `/` and `/products/[slug]` dynamic
- `npm start`, then:
  - `GET /api/products` → real documents as JSON
  - `GET /products/desk-lamp` → **200**, `GET /products/nope` → **404**
  - browser at `/` → `Desk lamp $45.00 In stock`, `Notebook $8.50 Sold out`,
    `Oak chair $120.00 In stock`, each linking to `/products/<slug>`
  - browser at `/products/desk-lamp` → `Desk lamp`, `$45.00`, `In stock`
  - **zero console errors on both pages**

## How to use it

1. `listDir` on `.agents/skills/nextjs-sketch/sketch` to see the tree.
2. `readFile` the sketch file matching the file you are about to write.
3. Write the project's version: same structure, same lifecycle, the task's own
   entities, routes and fields.

Files a tool would otherwise pick up are stored with a `.txt` suffix:
`package.json.txt` so npm does not treat the skill as a workspace, and
`*.test.js.txt` / `*.test.jsx.txt` so the project's own Vitest run does not
discover the sketch's suites and count them as the application's. Write them
back without the suffix.

## The file tree

```
package.json            next / react / mongoose; dev, build, start, seed, test
jsconfig.json           the @/* alias the app and the tests both use
next.config.mjs         empty on purpose
vitest.config.js        jsdom + globals + setup + the same @ alias
vitest.setup.js         @testing-library/jest-dom/vitest
.env.example            MONGODB_URI
lib/db.js               the connection cached on globalThis
lib/money.js            cents formatted in one place
lib/products.js         data access the pages share
models/Product.js       index declared once; toPublic() fixes the API shape
app/layout.js           html + body, metadata
app/page.js             server component; reads the database directly
app/products/[slug]/page.js   await params; notFound(); Link back
app/api/products/route.js     dynamic route handler with a real error path
components/ProductList.jsx    'use client'; props only; four visible states
test/money.test.js            pure logic
test/ProductList.test.jsx     component, jsdom
test/product.model.test.js    data layer, node via a docblock
scripts/seed.mjs              imports the app's own model, clears the collection
```

## The decisions inside it, and why

- **The connection is cached on `globalThis`.** Next.js re-evaluates modules on
  every hot reload, so a module-level `let` opens a new connection each time
  until the pool is exhausted — and the symptom is timeouts that read as slow
  queries. A failed attempt clears the cached promise, or every later request
  replays the same failure.
- **`params` is a Promise: `const { slug } = await params`.** Reading
  `params.slug` directly yields `undefined`, the lookup misses, and the page
  404s on every request with nothing in the log to explain it.
- **`export const dynamic = 'force-dynamic'` on anything that reads the
  database.** Without it Next.js serves a build-time snapshot: seeded rows
  appear once and never change again. This is the "my new data doesn't show up"
  bug, and it is a one-line cause.
- **A server component reads the data directly.** Calling the app's own
  `/api/...` from a server component costs a network round trip to itself and
  gives the page a way to fail that the data layer does not have.
- **`'use client'` only where interaction lives.** `ProductList` takes props;
  the page above it is the only thing that touches Mongo. Marking the page a
  client component instead is what forces the fetch-from-yourself pattern.
- **`Link`, never a bare `<a>`, for internal navigation.** An anchor forces a
  full document load and drops client state; the E2E journey then fails on a
  page that looks correct in a screenshot.
- **`notFound()` for a missing record.** It renders the 404 route with a 404
  status. Returning a "not found" paragraph with status 200 passes every
  status-only probe.
- **The route handler catches and returns 503.** The client gets a status it
  can act on and the detail stays in the server log. An uncaught throw in a
  route handler is a 500 with a stack the browser cannot use.
- **The model's index is declared once**, and the model is exported as
  `mongoose.models.Product ?? mongoose.model(...)` so a hot reload or a test
  import cannot throw `OverwriteModelError`.
- **`toPublic()` decides the API shape once.** A field present in the model and
  absent from one response is where `undefined.toFixed()` comes from.
- **Money is cents, formatted in `lib/money.js`.** The test asserts `$45.00` —
  the string the page really contains — and `lineTotal` exists so a cart
  renders a computed total rather than `2 × $22.50`.
- **One Vitest config, two environments.** `environment: 'jsdom'` for
  components, and `// @vitest-environment node` as the first line of the data
  test. A second config file drifts from the first; making server code pass by
  running it in a browser-like environment hides where it really runs.
- **`globals: true` *and* the setup file.** The setup file extends `expect`,
  which exists globally only when that flag is on. A config without it plus a
  matcher setup file fails at collection with
  `ReferenceError: expect is not defined`, pointing at the setup file — which
  is not the thing that is wrong.
- **The Vitest config repeats the `@` alias.** Vitest does not inherit
  `jsconfig.json` paths, and a test that reaches around the alias with `../../`
  breaks the first time a file moves.
- **`beforeEach` clears the collection, not `beforeAll`.** Rows left behind
  change the next test's result, and the failure reads as a product bug.
- **`await Product.init()` before asserting on a unique index.** `unique` is an
  index, not a validator: it does nothing until the index exists, and it fails
  at write time with code 11000 rather than during `validate()`.
- **The seed imports the application's model and clears the collection.** A
  seed with its own schema writes `seedproducts` while the app reads
  `products`: it prints a success line and the app shows nothing.
- **Every list has an empty state with words in it.** A component that renders
  nothing when there is no data is indistinguishable from one that crashed, and
  a browser journey cannot tell you which happened.

## What this skill is not

It is not a reason to skip reading the project. If the app already exists,
follow what is there. The sketch is what to write when there is nothing yet,
and the thing to compare against when a page behaves strangely.
