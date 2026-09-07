---
name: mern-microservices-sketch
description: Copy the verified MERN + microservices skeleton — workspaces, gateway, service, Vite client, Vitest configs, single-port local runtime — instead of writing the boilerplate from memory.
---

# The MERN microservices sketch

Every application needs the same twenty files before it does anything specific:
a workspace manifest, a config module, a database connection, a model, a
router, an app that does not listen, a server that does, two Vitest configs
that disagree with each other in exactly one way, a gateway, a proxy, a client
that fetches, and a script that starts it all on one port.

Those files were the source of nearly every first-round failure measured across
real builds — a duplicate index warning, a seed writing to the wrong
collection, a client suite collecting zero tests, a gateway serving a blank
page with HTTP 200. None of them were interesting problems. They were the same
boilerplate, written slightly differently each time, from memory.

So it is not written from memory here. **`sketch/` in this skill directory is a
complete application that was installed, unit-tested, built, seeded, started
and opened in a browser.** Read those files and adapt them. Do not retype them
from what you remember this code looking like.

## What was actually verified

One run, in this order, all of it passing:

- `npm install` across the workspaces
- `npm test` — **15 tests, first run, no repairs**: catalog 7, gateway 4, client 4
- `npm run build` — 27 modules, one bundle
- `npm run seed` — 3 products, through the application's own model
- `npm run dev` — gateway and service under one command
- `GET /ready` → `{"ok":true,"clientBuilt":true}`
- `GET /api/products` → real documents, through the gateway
- browser at `/` → `Desk lamp $45.00 In stock`, `Notebook $8.50 Sold out`,
  `Oak chair $120.00 In stock`, **zero console errors**

That last line is the one that matters: the price left Mongo as `priceCents`,
crossed the service boundary, crossed the gateway, and reached the DOM
formatted. A blank page with HTTP 200 is the failure this sketch is shaped to
prevent.

## How to use it

1. `listDir` on `.agents/skills/mern-microservices-sketch/sketch` to see the
   tree.
2. `readFile` the sketch file that matches the file you are about to write.
3. Write the project's version: same structure, same lifecycle, the task's own
   names, fields and routes.

Adapt freely — a booking app has bookings, not products. Keep the **shape**:
where configuration is read, where the connection lives, which file listens,
what the two Vitest configs say, how the gateway falls back.

Files a tool would otherwise pick up are stored with a `.txt` suffix:
`package.json.txt` so npm does not treat the skill as a workspace, and
`*.test.js.txt` so the project's own Vitest run does not discover the sketch's
suites and count them as the application's. Write them back without the
suffix.

## The file tree

```
package.json                 workspaces: packages/*, client; dev/build/start/seed/test
.env.example                 PORT (public) + internal service ports + MONGODB_URI
scripts/dev-all.mjs          every service + gateway, one command, no Docker
scripts/seed.mjs             imports the application's own model
packages/gateway/
  src/config.js              the only public port; service URLs from env
  src/proxy.js               fetch-based forward; 503 when a service is down
  src/app.js                 /ready, /api/* proxy, static client, SPA fallback
  src/server.js              the only file that listens
  test/gateway.test.js       routing, upstream 404, 503, readiness
  vitest.config.js           environment: node
packages/catalog-service/
  src/config.js  src/db.js   one connection per process
  src/models/product.js      index declared once; toPublic() decides the API shape
  src/routes/products.routes.js  atomic stock guard in the query
  src/app.js  src/server.js  createApp() does not listen
  test/products.test.js      7 tests including a concurrency case
  vitest.config.js           environment: node, fileParallelism: false
client/
  vite.config.js             /api proxied to the gateway in dev only
  vitest.config.js           environment: jsdom, globals: true, setupFiles
  test/setup.js              @testing-library/jest-dom/vitest
  src/api.js                 relative URLs; cents formatted once
  src/App.jsx                loading / error / empty / ready are all visible states
  test/App.test.jsx          asserts the formatted price, not the raw field
```

## The decisions inside it, and why

These are the lines that were wrong in real builds. Each one costs a repair
cycle when it is written from memory.

- **`createApp()` never listens.** The app is a value; `server.js` is the only
  file that binds a port. This is what lets `supertest` drive the real app with
  no port, no teardown and no flake.
- **The gateway owns the only public port.** Service ports are internal and
  come from configuration. A client that talks to `http://localhost:4101`
  directly works on one machine and nowhere else.
- **A down service is a 503, never a 200.** `proxy.js` catches the fetch
  failure. A proxy that lets the error through returns a 200 with an empty
  body, and the client renders nothing while every status code says healthy.
- **The SPA fallback excludes `/api/`.** `app.get(/^(?!\/api\/).*/)`. Without
  the exclusion a missing API route returns `index.html` with status 200, and
  the client parses HTML as JSON — the error you get points at the client.
- **`/ready` reports this process only.** It must not claim the services behind
  it are healthy; a green gateway with a dead catalog is the exact state a
  status-only probe hides.
- **The model's index is declared once.** `unique: true` on the field *is* the
  index; adding `schema.index({ slug: 1 })` too makes Mongoose warn about a
  duplicate.
- **`mongoose.models.X ?? mongoose.model('X', schema)`.** A model compiled
  twice — test file and application both importing it — throws
  `OverwriteModelError`.
- **`toPublic()` decides the API shape once.** Every route serializes through
  it, so a field cannot reach one endpoint and be missing from another. The
  client's `.toFixed()` on `undefined` starts here.
- **The stock guard lives in the query.**
  `findOneAndUpdate({ slug, stock: { $gte: n } }, { $inc: { stock: -n } })`,
  and a null result is the rejection. Read-then-write cannot hold "never below
  zero" under two callers — the sketch has a test that fires eight concurrent
  reservations at a stock of five and asserts exactly five succeed.
- **The seed imports the application's model and clears the collection.** A
  seed with its own `SeedProduct` schema writes `seedproducts` while the app
  reads `products`: it reports success and the app serves nothing.
- **The service Vitest config sets `fileParallelism: false`.** One database,
  parallel files, and each one clears the other's collections.
- **The client Vitest config sets `globals: true` *and* a setup file.** The
  setup file extends `expect`, which only exists globally when that is on.
  Config without it and a setup file that extends matchers is a contradiction
  that fails at collection with `ReferenceError: expect is not defined` and
  points at the setup file, which is not what is broken. The sketch imports
  `@testing-library/jest-dom/vitest`, which brings its own `expect`, and
  enables globals as well — either alone works, together is unambiguous.
- **`beforeEach` clears collections, not `beforeAll`.** A document left behind
  changes the next test's result, and the failure reads as a product bug.
- **The client has four visible states.** loading, error, empty, ready. A
  component that renders nothing on failure is indistinguishable from one that
  crashed, and the E2E journey cannot tell you which.
- **Money is cents in the database and formatted once in `api.js`.** The test
  asserts `$45.00`, the string the page really contains — not `4500`, and not
  `2 × $22.50`.
- **`dev-all.mjs` takes the whole run down when one service dies.** A
  half-started system that looks alive is the more expensive failure.

## What this skill is not

It is not a licence to skip reading the project. If the workspace already has a
gateway, follow the one that is there. The sketch is what to write when there
is nothing yet, and what to compare against when something behaves oddly.
