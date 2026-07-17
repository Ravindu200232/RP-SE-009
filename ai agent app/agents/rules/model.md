# RULE — Mongoose model file (`models/<Name>.ts`)

You generate ONE Mongoose model file. Output **only** TypeScript, no markdown fences, no prose.

## Required structure (follow exactly)
1. First line: `import mongoose, { Schema } from 'mongoose'`
2. Define `const <Name>Schema = new Schema({ ... }, { timestamps: true })`.
3. Last line MUST be the overwrite guard:
   `export default mongoose.models.<Name> || mongoose.model('<Name>', <Name>Schema)`

## Field rules
- Map each spec field to a Schema path. Types: `String`, `Number`, `Boolean`, `Date`,
  `Schema.Types.ObjectId`, `[String]`/`[Number]` for arrays, `Schema.Types.Mixed` for embedded
  arrays/objects/json.
- `enum` field → `{ type: String, enum: [...values], default: <first value> }`.
- `required` field → add `required: true`.
- `unique` field:
  - if it is ALSO required → `{ type: ..., unique: true }`
  - if it is unique but OPTIONAL → `{ type: ..., unique: true, sparse: true }`  ← always add `sparse: true` so multiple null values don't collide (E11000).
- `ref` field → `{ type: Schema.Types.ObjectId, ref: '<RefModel>' }`.
- `default` → add `default: <value>`.
- Never add a `password`/`passwordHash` field to a domain model — auth owns the User model.
- Do NOT redefine `_id`, `createdAt`, `updatedAt` (timestamps handles the last two).

## Example (a rentals model with an optional-unique code + enum + refs)
```ts
import mongoose, { Schema } from 'mongoose'

const RentalBookingSchema = new Schema({
  bookingNo: { type: String, unique: true, sparse: true },
  vehicle: { type: Schema.Types.ObjectId, ref: 'Vehicle', required: true },
  customer: { type: Schema.Types.ObjectId, ref: 'Customer', required: true },
  pickupDate: { type: Date, required: true },
  returnDate: { type: Date, required: true },
  days: { type: Number, default: 1 },
  total: { type: Number, default: 0 },
  status: { type: String, enum: ['reserved', 'active', 'completed', 'cancelled'], default: 'reserved' },
}, { timestamps: true })

export default mongoose.models.RentalBooking || mongoose.model('RentalBooking', RentalBookingSchema)
```
