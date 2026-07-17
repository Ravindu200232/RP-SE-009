# RULE — Ultra-strict CRUD API route handlers
`app/api/<segment>/route.ts` and `app/api/<segment>/[id]/route.ts`

You generate exactly ONE final Next.js App Router route-handler file.

Output ONLY valid TypeScript source code. Do not output markdown fences, explanations, plans, alternatives, review notes, TODOs, placeholders, or a second corrected version.

---

## 1. Non-negotiable output contract

1. Generate only the file requested by `FILE_KIND`:
   - `COLLECTION` → export exactly `GET` and `POST`.
   - `ITEM` → export exactly `GET`, `PUT`, and `DELETE`.
2. Export each HTTP method exactly once.
3. Never export a method not requested.
4. Never duplicate imports, helpers, constants, handlers, or code blocks.
5. Never stop mid-file. Close every `{`, `(`, `[`, string, template literal, and comment.
6. Never use:
   - `any`
   - `as any`
   - `@ts-ignore`
   - `@ts-expect-error`
   - `eslint-disable`
   - `require(...)`
   - dynamic imports
   - CommonJS exports
7. Never invent a model, field, endpoint, role, ownership rule, enum value, relationship, computed formula, or response shape.
8. Never include commented-out alternative implementations.
9. The final file must pass TypeScript strict mode without relying on implicit `any`.
10. Keep the route deterministic and minimal. Do not add unrelated business logic.

---

## 2. Required TASK contract — fail closed, never guess

The TASK must provide all values required for the requested file:

- `FILE_KIND`: `COLLECTION` or `ITEM`
- `MODEL_NAME`: exact PascalCase model identifier
- `MODEL_IMPORT`: exact model import path
- `SEGMENT`: exact API segment
- `AUTH_RULE`: `USER` or `ROLE:<exact-role>`
- `READ_FIELDS`: exact fields allowed in API responses
- `CREATE_FIELDS`: exact client-writable fields for POST
- `UPDATE_FIELDS`: exact client-writable fields for PUT
- `REQUIRED_CREATE_FIELDS`
- `STRING_FIELDS`
- `NUMBER_FIELDS`
- `NON_NEGATIVE_FIELDS`
- `INTEGER_FIELDS`
- `BOOLEAN_FIELDS`
- `DATE_FIELDS`
- `ENUM_FIELDS` with exact allowed values
- `REFERENCE_FIELDS` with exact field names
- `ACTOR_FIELDS` owned by the server
- `OWNERSHIP_FILTER`, or the explicit value `NONE`
- `COMPUTED_FIELDS` with exact server formulas, or `NONE`
- `DELETE_POLICY`: `HARD`, `SOFT:<field>`, or `FORBIDDEN`

Optional metadata may include exact search fields, exact filter fields, exact sort fields, exact uniqueness rules, exact populate instructions, or transaction steps.

If a required value is missing, ambiguous, or contradictory:

- Do not infer it from the route name.
- Do not generate guessed CRUD behavior.
- Generate a compile-safe fail-closed file for the requested `FILE_KIND`.
- Import only `fail` from `@/lib/api`.
- Every requested handler must return `fail('Route contract incomplete', 500)`.

Never leave angle-bracket placeholders such as `<Model>` in final TypeScript.

---

## 3. Mandatory file header and imports

The first two executable statements must be exactly:

```ts
export const dynamic = 'force-dynamic'
export const runtime = 'nodejs'
```

Imports must follow those statements.

Allowed fixed imports:

```ts
import dbConnect from '@/lib/mongodb'
import mongoose from 'mongoose'
import ModelName from '@/models/ModelName'
import { ok, created, fail, serverError } from '@/lib/api'
import { requireUser, requireRole } from '@/lib/auth'
```

Rules:

- Replace `ModelName` and its path only with the exact TASK values.
- Import only names actually used in this file.
- Never import `NextResponse`.
- Never import from `next/server`.
- Never import `getSession` when `requireUser` or `requireRole` is sufficient.
- Never import a library not explicitly listed here.
- Never use an npm validation library unless the TASK explicitly states that it is installed and provides its exact import.
- `mongoose` is mandatory for ITEM routes and whenever reference ObjectIds are validated.

Always call authentication before database access.
Always call `await dbConnect()` before the first database query or mutation.

---

## 4. Exact handler signatures

### COLLECTION file

```ts
export async function GET(req: Request)
export async function POST(req: Request)
```

### ITEM file

Use these signatures exactly:

```ts
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
)
```

```ts
export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
)
```

```ts
export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
)
```

Inside every ITEM handler:

```ts
const { id } = await params
if (!mongoose.Types.ObjectId.isValid(id)) {
  return fail('Invalid id', 400)
}
```

Never:

- Parse an id from `req.url`.
- Use `req.url.split('/')`.
- Read `params.id` without awaiting `params`.
- Rename the dynamic parameter.
- Accept an id from the request body.
- Query MongoDB before validating the id.

---

## 5. Authentication and authorization

Use exactly one auth rule supplied by the TASK.

For `AUTH_RULE: USER`:

```ts
const session = await requireUser()
```

For `AUTH_RULE: ROLE:admin`:

```ts
const session = await requireRole('admin')
```

Rules:

1. Use the exact role string supplied by the TASK.
2. Never implement authorization from body fields, query parameters, headers, local storage, or client-sent role values.
3. Never trust `userId`, `owner`, `createdBy`, role, branch, tenant, or actor values sent by the browser.
4. Apply the exact `OWNERSHIP_FILTER` to every read, update, and delete query when it is not `NONE`.
5. Never use `findById(...)` alone for an owned or tenant-scoped resource. Use a scoped filter such as:
   ```ts
   { _id: id, owner: session.userId }
   ```
6. A role check does not automatically replace an ownership or tenant filter.
7. Never return records outside the permitted scope.
8. Map auth errors exactly:
   - `UNAUTHORIZED` → `fail('Sign in required', 401)`
   - `FORBIDDEN` → `fail('Access denied', 403)`

---

## 6. Safe request-body parsing

POST and PUT must parse JSON inside `try/catch`.

The parsed value must be a plain object:

```ts
const raw: unknown = await req.json()
if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
  return fail('Request body must be an object', 400)
}
const body = raw as Record<string, unknown>
```

This `Record<string, unknown>` assertion is allowed. `any` is never allowed.

Reject or ignore all keys not explicitly listed in `CREATE_FIELDS` or `UPDATE_FIELDS`.

Use an explicit whitelist:

```ts
function pickFields(
  body: Record<string, unknown>,
  allowedFields: readonly string[],
): Record<string, unknown> {
  const data: Record<string, unknown> = {}

  for (const field of allowedFields) {
    const value = body[field]
    if (value !== '' && value !== null && value !== undefined) {
      data[field] = value
    }
  }

  return data
}
```

Security rules:

- Never use `{ ...body }` as create or update data.
- Never pass raw `body` to Mongoose.
- Never use body-provided keys dynamically in a Mongo query.
- Never accept keys beginning with `$`.
- Never accept keys containing `.`.
- Never accept `__proto__`, `prototype`, or `constructor`.
- Never permit client updates to:
  - `_id`
  - `id`
  - `__v`
  - `createdAt`
  - `updatedAt`
  - actor fields
  - ownership fields
  - tenant fields
  - computed fields
- Preserve valid `false` and `0` values.
- Omit optional `''`, `null`, and `undefined` values.
- If no writable values remain, return `fail('No valid fields provided', 400)`.

---

## 7. Field validation before Mongoose

Validate only fields declared by the TASK. Never guess field types.

### Required create fields

For every `REQUIRED_CREATE_FIELDS` entry:

```ts
if (!(field in data)) {
  return fail(`${field} is required`, 400)
}
```

A required string containing only whitespace is missing.

### Strings

- Require `typeof value === 'string'`.
- Trim declared normal text fields.
- Reject blank required strings.
- Never trim secret material unless the TASK explicitly says to do so.

### Numbers

- Require `typeof value === 'number'`.
- Require `Number.isFinite(value)`.
- For `NON_NEGATIVE_FIELDS`, reject values below zero.
- For `INTEGER_FIELDS`, require `Number.isInteger(value)`.
- Do not reject all negative numbers globally; some domains legitimately use them.

### Booleans

Require `typeof value === 'boolean'`.
Never convert `'false'` to `true` with `Boolean(value)`.

### Dates

- Accept only the exact representation specified by the TASK.
- When accepting a date string, reject it if `Number.isNaN(Date.parse(value))`.
- Never silently replace an invalid date with the current date.

### Enums

- Use the exact allowed values supplied by `ENUM_FIELDS`.
- Reject unknown values with status 400.
- Never add fallback enum values.
- **Narrow with `typeof` before comparing.** A value off `Record<string, unknown>` is `unknown`, and
  `!== undefined` narrows it to `{} | null` — not `string`. `allowed.includes(body.status)` is then a
  type error (`Argument of type '{} | null' is not assignable to parameter of type 'string'`). One
  `typeof` check narrows it properly and validates at the same time:
  ```ts
  const ALLOWED = ['Easy', 'Medium', 'Hard'] as const
  const difficulty = body.difficulty
  if (difficulty !== undefined) {
    if (typeof difficulty !== 'string' || !ALLOWED.includes(difficulty as typeof ALLOWED[number])) {
      return fail('difficulty must be one of: Easy, Medium, Hard', 400)
    }
  }
  ```
  The same applies to every value read off the body: `typeof x === 'string'` / `typeof x === 'number'`
  BEFORE using it as one. Never reach for `any` or a non-null assertion to silence it.

### ObjectId references

For each present field in `REFERENCE_FIELDS`:

```ts
if (
  typeof value !== 'string' ||
  !mongoose.Types.ObjectId.isValid(value)
) {
  return fail(`${field} must be a valid id`, 400)
}
```

- Never accept populated objects as reference values.
- Never read a nested id from a client object.
- Never convert arbitrary values to strings to make ObjectId validation pass.
- Validate arrays of ObjectIds element by element when the TASK explicitly declares such a field.

### Arrays and nested objects

Only accept them when the TASK supplies their exact shape and validation rules.
Otherwise exclude them from writable fields.

---

## 8. Server-owned actor, ownership, and computed fields

POST:

1. Sanitize and validate client data first.
2. Set exact server-owned actor/ownership fields from the authenticated session.
3. Ignore client values for those fields even when present.
4. Apply exact server formulas for `COMPUTED_FIELDS`.
5. Never trust browser-sent totals, balances, prices, tax, discounts, status transitions, or audit fields when the TASK marks them as computed/server-owned.

Use schema existence checks only for actor fields explicitly listed by the TASK:

```ts
if (ModelName.schema.path('createdBy')) {
  data.createdBy = session.userId
}
```

PUT:

- Never overwrite actor, ownership, tenant, immutable, or computed fields from the body.
- Recompute exact computed fields after validating dependencies.
- If the formula is not supplied, exclude that computed field instead of inventing a formula.

When one request mutates multiple documents and the TASK requires atomicity, use a Mongoose transaction exactly as specified. Never invent a transaction workflow.

---

## 9. COLLECTION GET — list behavior

Required order:

1. Authenticate.
2. Connect to MongoDB.
3. Parse pagination safely.
4. Build a fixed server-controlled query.
5. Apply ownership/tenant scope.
6. Apply only exact allowed filters/search.
7. Execute the query.
8. Return `ok(items)`.

Safe pagination:

```ts
function parsePositiveInt(
  value: string | null,
  fallback: number,
  maximum: number,
): number {
  if (value === null || value.trim() === '') return fallback

  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 1) return fallback

  return Math.min(parsed, maximum)
}
```

Use:

```ts
const { searchParams } = new URL(req.url)
const page = parsePositiveInt(searchParams.get('page'), 1, 1_000_000)
const limit = parsePositiveInt(searchParams.get('limit'), 50, 100)
const skip = (page - 1) * limit
```

Rules:

- Never use `Math.max(1, Number(value))`; invalid input can become `NaN`.
- Never allow `limit` above 100.
- Never spread query parameters into a Mongo filter.
- Never accept raw client sort objects.
- Search only exact TASK-declared string fields.
- Escape regex metacharacters before constructing a regex.
- Filter only exact TASK-declared fields and validate each value.
- Use a server-owned sort allowlist.
- Default to:
  ```ts
  .sort({ createdAt: -1, _id: -1 })
  ```
- Use `.skip(skip).limit(limit).lean()`.
- Use an explicit safe `.select(...)` when `READ_FIELDS` is provided.
- Never expose password hashes, tokens, secrets, reset codes, API keys, or internal audit data.
- Do not call `.populate(...)` unless the TASK gives exact paths and exact selected fields.
- Return an array, including `[]` when no records exist.
- Keep the fixed success envelope: `ok(items)`.

---

## 10. COLLECTION POST — create behavior

Required order:

1. Authenticate.
2. Connect to MongoDB.
3. Parse and verify plain-object JSON.
4. Pick only `CREATE_FIELDS`.
5. Validate all declared fields.
6. Set server-owned fields.
7. Recompute exact computed fields.
8. Create exactly one document unless the TASK explicitly requires more.
9. Return `created(doc)`.

Use:

```ts
const doc = await ModelName.create(data)
return created(doc)
```

Rules:

- Never call `insertMany` for a normal single-create route.
- Never use body-provided `_id`.
- Never trust client actor/owner/tenant fields.
- Never create related documents unless explicitly specified.
- Never return HTTP 200 for successful creation; use `created(...)`.
- Validation errors must return status 400.
- Duplicate-key errors must return status 409.

---

## 11. ITEM GET — read-one behavior

Required order:

1. Authenticate.
2. Connect to MongoDB.
3. Await and validate `id`.
4. Build the exact scoped filter.
5. Query with `.lean()`.
6. Return 404 when absent.
7. Return `ok(doc)` when present.

Use a scoped filter:

```ts
const filter: Record<string, unknown> = { _id: id }
```

Add only the exact TASK-supplied ownership/tenant values.

Query:

```ts
const doc = await ModelName.findOne(filter).lean()
if (!doc) return fail('Not found', 404)
return ok(doc)
```

Never use unscoped `findById` when `OWNERSHIP_FILTER` is not `NONE`.

---

## 12. ITEM PUT — safe partial update behavior

Required order:

1. Authenticate.
2. Connect to MongoDB.
3. Await and validate `id`.
4. Parse and verify plain-object JSON.
5. Pick only `UPDATE_FIELDS`.
6. Validate every present field.
7. Reject an empty update.
8. Recompute exact computed fields.
9. Build the scoped filter.
10. Update with `$set`.
11. Run validators.
12. Return 404 when absent.
13. Return `ok(doc)`.

Use:

```ts
const doc = await ModelName.findOneAndUpdate(
  filter,
  { $set: data },
  {
    new: true,
    runValidators: true,
    context: 'query',
  },
)
```

Rules:

- Never pass raw `body` to `findByIdAndUpdate` or `findOneAndUpdate`.
- Never pass client Mongo operators.
- Never use `overwrite: true`.
- Never use `upsert: true` in an item update route.
- Never alter `_id`, actor fields, ownership fields, timestamps, or computed fields from client data.
- Never return success when the record does not exist.
- Never use an unscoped update query for owned/tenant data.

---

## 13. ITEM DELETE — exact policy

Apply only the TASK-supplied `DELETE_POLICY`.

### `HARD`

```ts
const doc = await ModelName.findOneAndDelete(filter)
if (!doc) return fail('Not found', 404)
return ok({ deleted: true })
```

### `SOFT:<field>`

Update only the exact soft-delete field/value specified by the TASK, using the scoped filter.
Return 404 when no document matched.

### `FORBIDDEN`

Return:

```ts
return fail('Delete is not allowed', 405)
```

Rules:

- Never report `{ deleted: true }` when nothing was deleted.
- Never hard-delete when the TASK requires soft delete.
- Never implement cascading deletion unless exact dependent models and transaction steps are provided.
- Never accept delete authorization from the request body.
- Never call `req.json()` in DELETE unless the TASK explicitly requires and defines a body contract.

---

## 14. Consistent error handling

Every handler body must be wrapped in one `try/catch`.

Catch variable must be `unknown`:

```ts
} catch (error: unknown) {
```

Use safe helper checks. Do not access arbitrary properties without narrowing.

Canonical mapper:

```ts
function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Unexpected error'
}

function getErrorName(error: unknown): string {
  return error instanceof Error ? error.name : ''
}

function getErrorCode(error: unknown): number | undefined {
  if (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    typeof (error as { code?: unknown }).code === 'number'
  ) {
    return (error as { code: number }).code
  }

  return undefined
}
```

Catch order:

```ts
const message = getErrorMessage(error)

if (message === 'UNAUTHORIZED') {
  return fail('Sign in required', 401)
}

if (message === 'FORBIDDEN') {
  return fail('Access denied', 403)
}

if (error instanceof SyntaxError) {
  return fail('Invalid JSON body', 400)
}

if (
  getErrorName(error) === 'ValidationError' ||
  getErrorName(error) === 'CastError'
) {
  return fail(message, 400)
}

if (getErrorCode(error) === 11000) {
  return fail('A record with the same unique value already exists', 409)
}

return serverError(error)
```

Rules:

- Never expose stack traces.
- Never return raw error objects.
- Never use `error.message` without narrowing.
- Never map validation or cast errors to status 500.
- Never swallow an error and return success.
- Never use `console.log` as error handling.
- Keep error messages domain-safe; do not expose secrets or connection strings.

---

## 15. Database-query safety

Forbidden:

- `$where`
- `eval`
- JavaScript query functions
- raw client Mongo operators
- raw client projection
- raw client sort
- raw client populate
- unbounded list queries
- regex built from unescaped user input
- `Model.find(body)`
- `Model.updateOne(body, body)`
- `Model.findOneAndUpdate({ _id: id }, body)`
- string concatenation to build Mongo expressions

Required:

- Fixed server-built filters.
- Exact allowed query fields.
- Validated ObjectIds.
- Bounded pagination.
- Explicit writable field whitelists.
- Explicit response-field rules.
- Ownership/tenant filters on every relevant operation.

---

## 16. Response contract

Use only:

```ts
ok(data)
created(data)
fail(message, status)
serverError(error)
```

Never return:

- `Response.json(...)`
- `NextResponse.json(...)`
- bare objects
- plain strings
- inconsistent envelopes
- `ok({ success: true, data })`
- manually duplicated `success` fields

The helpers already create the envelope.

Success:

- List → `ok(items)`
- Get one → `ok(doc)`
- Create → `created(doc)`
- Update → `ok(doc)`
- Delete → `ok({ deleted: true })`

Errors:

- Bad input → 400
- Unauthorized → 401
- Forbidden → 403
- Missing record → 404
- Method/policy forbidden → 405
- Duplicate unique value → 409
- Unexpected server/database error → `serverError(error)`

---

## 17. Absolute forbidden-pattern list

The final TypeScript must not contain any of these patterns:

```ts
catch (e: any)
catch (error: any)
Record<string, any>
req.url.split('/')
const body = await req.json()
ModelName.create(body)
findByIdAndUpdate(id, body
findOneAndUpdate(filter, body
{ ...body }
return ok(null)
return ok({ deleted: true }) // without verifying a matched/deleted document
Math.max(1, Number(
limit(Number(
req.nextUrl
NextResponse
@ts-ignore
@ts-expect-error
as any
```

The line `const body = raw as Record<string, unknown>` is allowed only after plain-object validation.

---

## 18. Final silent pre-output validation gate

Before outputting the file, silently verify every item:

### Structure
- Correct `FILE_KIND`.
- Exact required methods only.
- Each handler exported once.
- No duplicate code.
- All syntax closed.
- No markdown or prose.
- No unresolved placeholders.

### Imports and types
- Every used symbol is imported or declared.
- Every import is used.
- No forbidden package.
- No `any`.
- No implicit-any parameters.
- No unsafe catch-property access.

### Runtime
- `dynamic = 'force-dynamic'`.
- `runtime = 'nodejs'`.
- Auth runs first.
- DB connects before queries.
- ITEM params are awaited.
- ObjectIds are validated.
- JSON is checked as a plain object.
- Only whitelisted fields reach Mongoose.
- Empty updates are rejected.
- Validators run on update.
- Missing records return 404.
- Pagination cannot become `NaN`.
- Query size is bounded.

### Security
- No client-controlled actor/owner/tenant/computed fields.
- No Mongo operator injection.
- Ownership/tenant scope applied consistently.
- No sensitive fields leaked.
- Exact role enforced.
- No guessed authorization.

### Responses
- Only fixed helper envelopes.
- Correct status mapping.
- Create uses `created`.
- Delete success occurs only after a matched deletion.
- Validation/Cast/JSON errors return 400.
- Duplicate key returns 409.

If any check fails, repair the file before output. Output only when all checks pass.