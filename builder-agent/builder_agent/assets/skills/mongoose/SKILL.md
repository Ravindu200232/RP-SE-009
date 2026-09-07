---
name: mongoose
description: Model, query, migrate, debug, and test MongoDB data access with Mongoose using the project's installed version and real persistence contracts.
---

# Mongoose data work

Use this skill only when Mongoose is selected or detected. Inspect the installed Mongoose/MongoDB versions, connection module, schemas/models, indexes, validators, hooks, queries, serializers, transaction needs, seed/migration code, and tests.

- Reuse a deliberate connection lifecycle suitable for the runtime; do not create a new connection per request or leak clients during tests/reload.
- Encode true invariants with schema validation and indexes, while still validating untrusted API input before database calls. Treat unique indexes as race-safe constraints whose duplicate-key failures need handling.
- Keep ObjectId/reference shapes, population, projections, serialization, timestamps, defaults, and API DTOs consistent.
- Use `lean()` only for read-only queries that do not need document getters, virtuals, defaults, change tracking, validation, or `save()` behavior.
- Use transactions only when the deployment supports them and the business invariant spans multiple writes. Pass the session through every participating operation and test rollback/failure behavior.
- Avoid query-per-item patterns, unbounded list queries, accidental sensitive-field projection, and indexes added without query evidence.

Test validation, duplicate/race behavior, not-found/invalid identifiers, authorization-scoped queries, serialization, and relevant transaction failures against an isolated test database. Never point automated tests at production data.

## Mistakes that fail the first run

These are not subtle. They are the ones that appear in a freshly generated
Mongoose layer and cost a repair cycle each, so write the model correctly the
first time rather than discovering them from a warning.

- **Declare an index once.** `unique: true` or `index: true` on a field already
  creates it; adding `schema.index({ field: 1 })` for the same field declares it
  twice and Mongoose warns about a duplicate index. Choose the field option for
  a single-field index and `schema.index()` only for compound or partial ones.
- **The model name chooses the collection.** `mongoose.model('Product', …)`
  reads and writes `products`; `mongoose.model('SeedProduct', …)` reads and
  writes `seedproducts`. Measured: a seed script that declared its own
  throwaway `SeedProduct` model reported "12 products seeded" and the
  application served none of them, because the service was reading a different
  collection the whole time. A script that seeds, migrates or repairs data must
  either import the application's own model or pin the collection explicitly —
  `mongoose.model('SeedProduct', schema, 'products')` — never rely on a name it
  invented locally.
- **A seed owns the collection it writes, so it must clear it.** In the same
  build, documents left by an earlier version of the app survived in
  `products` with a different field shape (`priceCents` where the current model
  had `price`), and were served in place of the seed's own rows: the client
  rendered `undefined.toFixed()` and the page went blank. Deleting only the
  documents the seed recognises is not enough — clear the collection, or key
  every seeded document so a stale one cannot be mistaken for a current one.
  A database outlives the workspace it was built in.
- **Compile each model once.** A model compiled twice — because a test file and
  the application both import the module, or a watch run re-imports it — throws
  `OverwriteModelError`. Export
  `mongoose.models.Thing ?? mongoose.model('Thing', schema)` so re-import is
  harmless.
- **Reuse one connection.** Create it in a single module that returns the
  existing connection when one is already open, and await it before the first
  query. Connecting per request or per test exhausts the pool and produces
  timeouts that look like slow queries.
- **`unique` is an index, not a validator.** It does not run on `validate()`, it
  fails at write time with duplicate-key error code 11000, and it does nothing
  at all until the index actually exists. Handle 11000 explicitly, and let the
  index build before a test asserts uniqueness.
- **A concurrent-safe decrement is one atomic update.** Read-then-write cannot
  hold "never below zero" under two callers. Express the guard in the query —
  `findOneAndUpdate({ _id, stock: { $gte: n } }, { $inc: { stock: -n } })` — and
  treat a null result as the rejection.
- **Compare instants.** Store dates as instants and compare them as such; an
  assertion on a locale-formatted date passes only in the timezone that wrote
  it.
- **Clear collections between tests, not just between files**, and let each test
  create the documents it needs with unique keys.

Current official references:

- https://mongoosejs.com/docs/guides.html
- https://mongoosejs.com/docs/validation.html
- https://mongoosejs.com/docs/transactions.html
- https://mongoosejs.com/docs/tutorials/lean.html

