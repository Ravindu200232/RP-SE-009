# RULE — Database contract (reference; the DB lib itself is a fixed permanent file)

`lib/mongodb.ts` is a FIXED file (not generated). It exports `default dbConnect()` which:
- returns a cached Mongoose connection (safe across hot reloads),
- uses `process.env.MONGODB_URI` when set, else spins up an in-memory MongoDB (`mongodb-memory-server`)
  so the app runs with zero database setup.

All server code (routes, logic, detail pages) MUST `import dbConnect from '@/lib/mongodb'` and
`await dbConnect()` before any Mongoose query. Models use the overwrite guard
(`mongoose.models.X || mongoose.model('X', schema)`) so repeated imports never throw `OverwriteModelError`.

Response helpers are fixed in `lib/api.ts`: `ok(data)`, `created(data)`, `fail(message, status)`,
`serverError(e)` — always use these, never `NextResponse.json` directly in domain routes.
