# RULE — Business-logic endpoints (custom, non-CRUD routes)

You generate a custom transaction endpoint. Output **only** TypeScript, no markdown, no prose.
All the fixed `route.md` conventions apply (`export const dynamic = 'force-dynamic'`, `await dbConnect()`,
auth via `requireUser()`, response via `ok/created/fail/serverError`, try/catch → 401/403/500).

**Imports — use ONLY these exact paths (they are the only files that exist):**
- `import dbConnect from '@/lib/mongodb'`  ← the DB connect helper. There is NO `@/lib/db`.
- `import { ok, created, fail, serverError } from '@/lib/api'`  ← there is NO `@/lib/response`.
- `import { requireUser } from '@/lib/auth'`
- `import <Model> from '@/models/<Model>'` for each model you touch (models listed in MEMORY).
Define each HTTP method (`GET`/`POST`/…) exactly once. Return JSON via the helpers — do NOT build CSV
strings in the route (CSV export is done client-side).

**Auth + dynamic segments:**
- `requireUser()` takes NO arguments — call it as `await requireUser()` (never `requireUser(req)`).
- It returns `SessionPayload = { userId: string; role: string; email: string }`. To reference the acting
  user's id use `session.userId` — there is NO `._id` or `.id` on the session.
- Mongoose models are **values, not types**. NEVER annotate a variable with a model name
  (`const x: StayCharge = {…}`) or use it as a generic (`<StayCharge>`). For a plain object use no
  annotation or `Record<string, unknown>`. Use models only as values: `await StayCharge.create({…})`.
- If the route path contains a dynamic `[id]` segment, the handler signature MUST be
  `export async function POST(req: Request, { params }: { params: Promise<{ id: string }> })`
  and read it with `const { id } = await params`. `params` is a Promise in Next 15/16 — never type it
  as a plain object and never read it without `await`.

Every rule below runs **on the server** and is authoritative — never trust client-sent totals/stock.

## Inventory / stock movements
- One helper concept: adjusting a stock quantity ALWAYS writes a `StockMovement` record
  `{ item, type, quantity, before, after, refType?, refId?, createdBy }` in the same request.
- Stock must never go below 0 — reject with `fail('Insufficient stock', 409)`.
- Use a fresh read of the item quantity, compute `after`, `updateOne`, then create the movement.

## POS checkout (`app/api/pos/checkout/route.ts`)
- Body: `{ items: [{ <itemRef>: id, quantity }], customer?, discount?, paymentMethod? }`.
- For each line: load the item, verify `quantity <= item.<qtyField>` (else 409), decrement stock +
  write a `StockMovement` (type `sale`). Compute `subtotal`/`total` on the server from item prices.
- Create the sale record and (if the app has invoices) an `Invoice` with the computed total.
- Return `created({ sale, invoice })`. If any line fails validation, make NO changes.

## Booking / rental create (overlap-guarded)
- Before creating a booking, reject overlaps: an existing booking for the SAME asset whose
  date range intersects `[pickupDate, returnDate)` and whose status is active/confirmed →
  `fail('Asset not available for those dates', 409)`.
- Compute `days = max(1, ceil((return - pickup) / 1 day))` and `total = days * rate` on the server.

## Invoicing / payments (`app/api/invoices/<id>/payments/route.ts`)
- Body: `{ amount, method }`. Load the invoice. Reject `amount <= 0` and any amount that would make
  `paidAmount` exceed `total` → `fail('Payment exceeds balance', 400)`.
- Append the payment, recompute `paidAmount`, set `status`: `paid` if `paidAmount >= total`, else
  `partial` if `paidAmount > 0`, else `unpaid`; recompute `balance = total - paidAmount`. Return `ok(invoice)`.

## Reports (`app/api/reports/route.ts`)
- `?type=` selects a report. Aggregate REAL values from the collections (counts, sums, group-bys).
  Return `ok({ type, rows, total, count })`. Never fabricate numbers.
