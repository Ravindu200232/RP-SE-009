# ULTRA-STRICT RULE — Reusable Next.js Component

Target files:
- `components/features/<feature>/<Name>.tsx`
- `components/layouts/<Role>Workspace.tsx`

You generate exactly ONE production-safe TSX file.

## DESIGN BAR — ship a designed product, never a wireframe
This component goes in front of a real user, and it must look like it belongs to the same app as every
other surface. Compiling is not the bar. Every component you write must satisfy ALL of these:
- **Hierarchy.** A labelled heading (`<Typography variant="h6">`) where the block needs a name, with
  supporting text in `color="text.secondary"`. Never an unlabelled form or table.
- **Rhythm.** 8px spacing scale (`spacing={2}`, `sx={{ p: 3 }}`), consistent gaps — never edge-to-edge.
- **Depth.** Group content in `<Card>`/`<Paper>` with real elevation and rounded corners.
- **Colour with intent.** Use the THEME (`color="primary"` for the main action, `color="error"` for
  destructive, `color="text.secondary"`, `sx={{ bgcolor: 'background.paper' }}`) — it already carries
  this app's palette. NEVER hard-code a hex.
- **One primary action**, `variant="contained"` with an icon; everything else outlined/text/IconButton.
- **Every state is designed.** Loading = `<CircularProgress />` with context. Empty = icon + headline +
  one-line prompt + the primary action, never "No data". Error = `<Alert severity="error">` + Retry.
- **Real domain copy** — never lorem ipsum, "Item 1", or a TODO.
- **Formatted data.** Dates via `toLocaleDateString()`, money with a currency, status as a coloured
  `<Chip>`, hover feedback on rows.
- **Responsive.** Deliberate at 375px and 1440px (`direction={{ xs: 'column', md: 'row' }}`).

## 0. OUTPUT CONTRACT — ABSOLUTE

1. Output TSX only. No markdown fence, explanation, heading, note, TODO, or trailing prose.
2. The first line must be exactly:
   `'use client'`
3. Emit exactly one default export.
4. The exported function name must exactly match `EXPORT_NAME` from the TASK, including capitalization.
5. Emit one complete file only. Never emit a second file, helper file, type file, API route, CSS file, or package command.
6. Never stop mid-file. Close every JSX tag, template literal, callback, object, array, brace, bracket, and parenthesis.
7. Never output placeholder syntax such as `...`, `/* fields */`, `// rest`, `TODO`, `FIXME`, or pseudo-code.
8. Never output invalid recovery text. The output must always remain valid TSX.
9. Prefer simple, boring, deterministic code over clever code.
10. Before emitting, silently perform the FINAL VALIDATION GATE at the end of this rule. Do not print the checklist.

## 1. TASK INPUT CONTRACT — SOURCE OF TRUTH

The TASK must provide, where relevant:
- `COMPONENT_KIND`: `feature` or `layout`
- `FILE_PATH`
- `EXPORT_NAME`
- `ENTITY`
- `API_BASE`
- `DTO_FIELDS`: exact fields that exist on the shared DTO
- `DISPLAY_FIELDS`
- `REQUIRED_FIELDS`
- `OPTIONAL_FIELDS`
- `READ_ONLY_FIELDS`
- `ENUM_FIELDS` with exact allowed values
- `BOOLEAN_FIELDS`
- `NUMBER_FIELDS`
- `DATE_FIELDS`
- `REFERENCE_FIELDS` with exact field name, target entity, endpoint, and label field
- `VALID_ROUTES`
- `NAV_ITEMS` for layouts

Rules:
1. The TASK is the only source of truth. Never invent a field, endpoint, route, enum value, role, relationship, component, or package.
2. Use only fields listed in `DTO_FIELDS`.
3. Use only routes listed in `VALID_ROUTES`.
4. Use only API URLs explicitly supplied by `API_BASE` or `REFERENCE_FIELDS`.
5. Never infer an endpoint from an entity name when the endpoint is supplied.
6. Never pluralize, singularize, rename, or change the case of a supplied field or endpoint.
7. Never assume a relationship is populated. References are string IDs unless the TASK explicitly gives a populated DTO type.
8. If optional visual information is missing, omit that visual feature.
9. If metadata required for CRUD is missing, generate a read-only component instead of guessing CRUD fields.
10. If `COMPONENT_KIND`, `EXPORT_NAME`, or the named entity type is missing, generation must be rejected by the orchestrator before calling the model. Never invent these values.

## 2. COMPONENT BOUNDARY — NO DUPLICATE UI

### Feature component
Render only the component's own feature UI, such as:
- table
- cards
- board
- form
- filters
- summary panel

A feature component must NEVER render:
- sidebar
- top navigation
- role menu
- app brand header
- global footer
- page shell
- workspace wrapper
- authentication screen
- another role's navigation

The page/layout already owns global structure. Duplicating it is a hard failure.

### Layout component
A layout component may render only:
- one workspace navigation area
- one main content area
- `{children}` exactly once

A layout component must not:
- fetch data
- render feature tables/forms
- hard-code dashboard statistics
- include another layout/workspace
- render `{children}` more than once
- invent links

## 3. EXPORT AND FILE SHAPE

### When the TASK gives you PROPS, they are the whole contract
The page that renders you owns the state and passes exactly those props — it was generated against the
same list, and TypeScript checks the wiring the moment you are written.
- Declare them EXACTLY as given: same names, same types, no extras, no defaults, none optional.
- Do NOT fetch the data those props carry. `rows` are already loaded; render them.
- Report back only through the callbacks you are given (`onEdit`, `onDelete`, `onSaved`, `onClose`) —
  never reach for a router or mutate a parent's state directly.
- You may still own state that is entirely yours: a form's fields, a dialog's local validation.

### Feature signature
```tsx
export default function <EXPORT_NAME>() {
  // component
}
```

### Layout signature
Import `ReactNode` as a type and use:
```tsx
import type { ReactNode } from 'react'

export default function <EXPORT_NAME>({ children }: { children: ReactNode }) {
  // layout
}
```

Hard rules:
- Exactly one `export default`.
- Do not use an anonymous default export.
- Do not export extra helpers, constants, interfaces, or types.
- Local non-exported helpers are allowed only when used by this component.

## 4. IMPORT ALLOWLIST — INVENT NOTHING

Import only names that are actually used. Every used non-global name must be imported or locally declared.

### React
Allowed:
```tsx
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
```
Import only the hooks/types used by the file.

### Shared DTO
When the TASK names an entity:
```tsx
import type { <Entity> } from '@/types'
```

Use the shared DTO for records:
```tsx
const [rows, setRows] = useState<<Entity>[]>([])
```

Never:
- redefine the entity in a local `interface`
- copy entity fields into a fake entity type
- use a Mongoose model as a frontend type
- import a type from a server model file
- use `any`

A local UI-only type is allowed only for form state or generic reference options, for example:
```tsx
type ReferenceOption = {
  _id: string
  name?: string
  title?: string
  label?: string
}
```

### UI components — Material UI only
ALL UI components come from **`@mui/material`**; ALL icons from **`@mui/icons-material`**. Import the
components you actually use:
```tsx
import { Box, Container, Stack, Card, CardContent, CardHeader, Typography,
  Button, IconButton, TextField, MenuItem, Select, InputLabel, FormControl, Checkbox,
  FormControlLabel, Switch, Chip, Divider, CircularProgress, Alert,
  Table, TableContainer, TableHead, TableBody, TableRow, TableCell, Paper,
  Dialog, DialogTitle, DialogContent, DialogActions } from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
```

Rules:
- **This app runs Material UI v7. NEVER import or use `Grid`.** In v7 `Grid` took the old Grid2 API —
  the `item` prop and `xs`/`sm`/`md` props no longer exist, so the `<Grid item xs={12}>` form you may
  remember fails the build with "No overload matches this call". Lay out with:
  - a row: `<Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>…</Stack>`
  - a column: `<Stack spacing={2}>…</Stack>`
  - a responsive card grid: `<Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>…</Box>`
- Import every UI component from the single `@mui/material` package path — never a deep path such as
  `@mui/material/Button`, never `@/components/ui/*`.
- Never import from an empty path.
- **Style with the `sx` prop** (theme-aware), e.g. `<Box sx={{ p: 3, maxWidth: 1100, mx: 'auto' }}>`. The
  app theme is dark — do NOT hard-code background colors on MUI components; the theme handles them.
- **`sx` belongs to MUI components ONLY.** `<section sx={…}>`, `<div sx={…}>`, `<nav sx={…}>` do not
  compile — a raw DOM element has no `sx` prop. Need a semantic tag with `sx`? Use
  `<Box component="section">`. Need a raw element? Style it with `className` and Tailwind instead.
- Tailwind utility classes via `className` are allowed for LAYOUT only (spacing, grid, section bands).
  Every INTERACTIVE/UI element (buttons, inputs, selects, tables, cards, dialogs, chips, alerts) MUST be
  a Material UI component.
- MUI `Select` uses `<MenuItem>` children — NEVER a native `<option>`.
- `Checkbox` is controlled with `checked={boolean}` and `onChange={(event) => setValue(event.target.checked)}`,
  wrapped in `<FormControlLabel control={<Checkbox … />} label="…" />`.
- `Dialog` is real — use it for modals. Never hand-roll an overlay `<div>`.

### Icons
Icons are optional. Plain text buttons are always fine.

If icons are used, import each as a default import from `@mui/icons-material/<X>`, where `<X>` is a
PascalCase Material icon name:
`Add Edit Delete Search Close Check Home Person People Settings Logout Menu Dashboard CalendarToday AttachMoney ShoppingCart Inventory Description Notifications Visibility FilterList Download Refresh Favorite FavoriteBorder AutoAwesome TrendingUp AccessTime Email`

**Use the MATERIAL name, not the lucide/Feather one you are used to** — those modules do not exist and
the build fails: `Favorite` NOT `Heart`, `Delete` NOT `Trash`, `Add` NOT `Plus`, `Edit` NOT `Pencil`,
`Close` NOT `X`, `Person` NOT `User`, `People` NOT `Users`, `Settings` NOT `Gear`, `ShoppingCart` NOT
`Cart`, `CalendarToday` NOT `Calendar`, `Notifications` NOT `Bell`, `Visibility` NOT `Eye`,
`AttachMoney` NOT `DollarSign`. If unsure, use one from the list above.

Never:
- use `react-icons` or `lucide-react`
- import icons from `@mui/material` (icons live in `@mui/icons-material`)
- invent an icon name
- use underscores in icon names
- import an icon that is not rendered

### Next.js
Allowed only when required:
- `next/link`
- `next/image`
- `next/navigation`

For App Router navigation, never import from `next/router`.

### Animation
`framer-motion` is allowed only when the TASK explicitly requests animation. Otherwise do not import it.

### Forbidden packages
Never import:
- `@/components/ui/*` or any shadcn primitive
- `react-icons`
- `lucide-react`
- `@mui/x-*` / `@mui/lab`
- `antd`
- `@chakra-ui/*`
- `axios`
- `swr`
- `react-query` / `@tanstack/*`
- `recharts`
- `chart.js`
- `d3`
- `moment`
- `date-fns`
- `mongoose`
- `fs`
- `path`
- any package not explicitly allowed above

Every allowed import resolves to: `react`, `@mui/material`, `@mui/icons-material`, `next/*`,
`framer-motion`, `@/types`. Anything else fails the build.

Use built-in `fetch`, JavaScript date APIs, and simple MUI/Tailwind bars instead.

## 5. TYPESCRIPT SAFETY — ZERO ESCAPE HATCHES

Never use:
- `any`
- `as any`
- `unknown as <Type>`
- `@ts-ignore`
- `@ts-expect-error`
- `eslint-disable`
- non-null assertion `value!`
- fake index signatures to bypass DTO checking
- duplicate `id` when `_id` exists

Rules:
1. Entity records use the shared DTO.
2. Form state may use explicit writable fields only.
3. Enum form state must be `string`, not a literal union, because native select values are strings.
4. Number state must be `number` or an empty string only when the UI needs an unfilled numeric input.
5. Convert input values explicitly with `String(...)`, `Number(...)`, or `Boolean(...)`.
6. Never call string methods on a value unless it is known to be a string or first converted with `String(...)`.
7. Never call `.map`, `.filter`, or `.join` on unknown data without `Array.isArray(...)`.
8. Never render an object directly as a React child. Render a known field or `String(value ?? '')`.
9. Never use `.toFixed()` before checking `Number.isFinite(...)`.
10. Never access a DTO field not listed by the TASK.

## 6. REACT RULES — NO HOOK OR STATE BUGS

1. Call hooks only at the top level of the component.
2. Never call hooks inside conditions, loops, callbacks, or nested functions.
3. Never make the `useEffect` callback itself `async`.
4. Use this shape:
```tsx
useEffect(() => {
  void loadRows()
}, [loadRows])
```
5. If a loader is referenced by an effect and mutation handlers, define it with `useCallback`.
6. Include every referenced changing value in hook dependency arrays.
7. Never update state during render.
8. Never create infinite effects by depending on state that the same effect always changes.
9. Use stable record keys: `key={row._id}`. Never use `Math.random()` or array index when `_id` exists.
10. Do not use `Date.now()` or random values during render.
11. Controlled inputs must never switch between `undefined` and a defined value. Use safe defaults such as `''`, `0`, or `false`.
12. Reset form state explicitly when opening a create form and prefill it explicitly when editing.
13. Keep separate state for `loading`, `saving`, and `error` when CRUD exists.
14. Disable mutation buttons while `saving` to prevent duplicate requests.

## 7. API CONTRACT — EXACT AND DEFENSIVE

### URL rules
- Use relative URLs only: `/api/<segment>`.
- Never hard-code a host, port, domain, localhost, or environment URL.
- Use the exact supplied `API_BASE`.
- For record operations use `${API_BASE}/${encodeURIComponent(row._id)}`.
- Never invent query parameters.

### Response rules
All API responses use an envelope:
```ts
{ success: boolean, data?: T, error?: string, message?: string }
```

For every request:
1. Await the response.
2. Parse JSON inside `try/catch`.
3. Check both `response.ok` and `json.success`.
4. Surface `json.error` or `json.message` when present.
5. Never read records from the envelope itself; read `json.data`.
6. For list requests, normalize safely:
```tsx
setRows(Array.isArray(json.data) ? json.data : [])
```
7. Never silently swallow an API error.

### Canonical list loader
```tsx
const loadRows = useCallback(async () => {
  setLoading(true)
  setError('')
  try {
    const response = await fetch(API_BASE)
    const json = await response.json()
    if (!response.ok || !json.success) {
      throw new Error(json.error || json.message || 'Failed to load records')
    }
    setRows(Array.isArray(json.data) ? json.data : [])
  } catch (cause) {
    setRows([])
    setError(cause instanceof Error ? cause.message : 'Failed to load records')
  } finally {
    setLoading(false)
  }
}, [])
```

Replace `API_BASE` with the exact string literal from the TASK. Do not leave `API_BASE` as an undeclared identifier.

### Mutation rules
- Create: `POST API_BASE`
- Update: `PUT ${API_BASE}/${encodeURIComponent(editingId)}`
- Delete: `DELETE ${API_BASE}/${encodeURIComponent(row._id)}`
- Do not use `PATCH` unless the TASK explicitly requires it.
- `POST` and `PUT` must include:
```tsx
headers: { 'Content-Type': 'application/json' }
```
- Serialize only the allowed writable payload.
- After a successful mutation: close/reset form, then `await loadRows()`.
- Confirm destructive delete with `window.confirm(...)`.
- Never optimistic-update unless explicitly requested.

### Browser payload denylist
Never send these from the client unless the TASK explicitly marks one writable:
- `_id`
- `id`
- `owner`
- `ownerId`
- `userId`
- `createdBy`
- `updatedBy`
- `recordedBy`
- `receivedBy`
- `approvedBy`
- `tenantId`
- `organizationId`
- `role`
- `permissions`
- `createdAt`
- `updatedAt`
- `__v`

Authentication and authorization are server responsibilities. Never implement role trust, ownership trust, or permission enforcement in the browser.

## 8. FORM CONTRACT — EXACT FIELD MAPPING

1. Include every field listed in `REQUIRED_FIELDS`.
2. Include optional fields only when they are useful and fully specified.
3. Never include `READ_ONLY_FIELDS` in editable controls.
4. Every input must be controlled.
5. Every label must describe the actual field.
6. Use `htmlFor` and matching stable `id` values.
7. A form submit button must have `type="submit"`.
8. Every non-submit button inside a form must have `type="button"`.
9. Never nest a `<form>` inside another `<form>`.
10. Call `event.preventDefault()` in the submit handler.
11. Trim required text values before submission.
12. Validate required values before calling the API and show a useful error.
13. Never submit `NaN`.
14. Never submit an invalid date string.
15. Never send an empty string for an optional ObjectId or optional number. Omit that key with conditional spread.

### Exact control mapping
- text/string -> `<TextField label="…" value={v} onChange={e => setV(e.target.value)} fullWidth />`
- email -> `<TextField type="email">`
- phone -> `<TextField type="tel">`
- long text -> `<TextField multiline minRows={3}>`
- enum -> MUI `<Select>`+`<MenuItem>` with only supplied enum values, wrapped in `<FormControl fullWidth>`
- boolean -> `<FormControlLabel control={<Checkbox checked={v} onChange={e => setV(e.target.checked)} />} label="…" />`
- integer/decimal -> `<TextField type="number">` and explicit `Number(...)`
- date -> `<TextField type="date" InputLabelProps={{ shrink: true }}>`
- reference/ObjectId -> MUI `<Select>`+`<MenuItem>` loaded from the exact supplied reference endpoint
- **`<TextField>` takes `label`, NEVER `labelId`.** `labelId` belongs to `<Select>`/`<InputLabel>`
  only; on a TextField it is a type error ("Object literal may only specify known properties"). A
  dialog holding both a Select and text inputs is where this slips — keep them apart:
  ```tsx
  <TextField label="Quantity" type="number" value={form.qty} onChange={…} fullWidth />
  <FormControl fullWidth>
    <InputLabel id="status-label">Status</InputLabel>
    <Select labelId="status-label" label="Status" value={form.status} onChange={…}>…</Select>
  </FormControl>
  ```
- **array / `[String]` (e.g. `ingredients: string[]`) -> `<TextField multiline minRows={4}>` bound to a
  LOCAL `string`**, one item per line, split on submit:
  `ingredients: form.ingredients.split('\n').map(s => s.trim()).filter(Boolean)`. When editing, seed it
  with `(initialItem.ingredients ?? []).join('\n')`. NEVER bind an array field straight to an input.

### Form state is its own type — never the entity DTO
```tsx
type RecipeForm = { title: string; ingredients: string; prepTime: string }   // every field a string
const [form, setForm] = useState<RecipeForm>({ title: '', ingredients: '', prepTime: '' })
```
The DTO types API RECORDS, not form state. `useState<Partial<Recipe>>({ ingredients: '' })` is a type
error the moment a field is an array or a number — an input's value is always a `string`. Declare a
local form type whose fields are all `string`, and convert to the DTO's shapes on submit
(`Number(form.prepTime)`, `form.ingredients.split('\n')`).

### Enum rule
Use string state:
```tsx
const [status, setStatus] = useState<string>('draft')
```
Never use a literal union state that forces a cast from `event.target.value`.

### Number rule
On change:
```tsx
onChange={(event) => setQuantity(Number(event.target.value))}
```
Before submit:
```tsx
if (!Number.isFinite(quantity)) {
  setError('Quantity must be a valid number')
  return
}
```

### Date rule
A date input value must be `YYYY-MM-DD`.
When prefilling an ISO date, use a guarded conversion such as:
```tsx
const dateValue = rawDate ? String(rawDate).slice(0, 10) : ''
```
For display, guard invalid dates before formatting.

### Optional payload rule
Use conditional spread:
```tsx
const payload = {
  name: name.trim(),
  ...(categoryId ? { categoryId } : {}),
  ...(Number.isFinite(price) ? { price } : {}),
}
```
Never construct a broad payload by spreading an entire DTO or form object.

## 9. REFERENCE FIELDS — OBJECTID SAFETY

A reference field such as `orderId`, `tableId`, `supplierId`, `categoryId`, or `menuItemId` is a plain string ID.

Hard rules:
1. Never render a reference field as a free-text input.
2. Fetch the exact supplied reference endpoint once.
3. Store reference options separately from entity rows.
4. Use `<MenuItem value={option._id}>` inside a MUI `<Select>` — never a native `<option>`.
5. Submit only the selected `_id` string.
6. Never access a sub-property of a string reference.

Forbidden:
```tsx
ticket.orderId.orderNo
row.supplierId.name
item.categoryId.title
```

Allowed:
```tsx
String(ticket.orderId ?? '').slice(-6)
```

To show a related label, look it up safely:
```tsx
const supplierName = suppliers.find((supplier) => supplier._id === row.supplierId)?.name
```

If the TASK does not provide a reference endpoint, do not invent one. For a required missing reference configuration, generate read-only UI rather than a broken form.

## 10. TABLE, LIST, AND DISPLAY SAFETY

1. Use the supplied table primitives. Never hand-roll a raw `<table>`, `<thead>`, `<tbody>`, `<tr>`, or `<td>` structure.
2. Every `<TableRow>` in a map must have `key={row._id}`.
3. Show a practical subset of supplied `DISPLAY_FIELDS`; do not invent columns.
4. Use safe rendering:
```tsx
String(row.name ?? '')
```
5. For nullable values, render a clear fallback such as `—`.
6. For arrays, first check `Array.isArray(value)`.
7. Do not render raw JSON blobs unless the TASK explicitly asks for them.
8. Do not assume populated relations.
9. Do not call `.slice`, `.toLowerCase`, or `.toLocaleDateString` on a nullable value without guarding it.
10. Search and filter only fields that exist and convert nullable values with `String(...)` first.

## 11. LOADING, EMPTY, ERROR, AND MUTATION STATES

Every data-driven feature must handle all applicable states:
- initial loading
- load error
- empty data
- loaded data
- saving/mutating
- mutation error

Rules:
1. Loading text must be domain-specific when possible.
2. Empty state must not be mistaken for an error.
3. An error must remain visible until cleared by retry or a new operation.
4. Do not render the data table before loading completes unless stale data behavior is explicitly designed.
5. Do not hide server error messages.
6. Add a Retry button for a failed initial load when `Button` is already used or can be safely imported.
7. Disable Save/Delete/Edit controls while a mutation is active.
8. Prevent double submission with a `saving` guard.

## 12. MODAL CONTRACT — USE MUI `Dialog`

MUI ships a real `Dialog`. Use it — never hand-roll an overlay `<div>`:
```tsx
<Dialog open={open} onClose={closeModal} fullWidth maxWidth="sm">
  <DialogTitle>{editing ? 'Edit' : 'New'}</DialogTitle>
  <DialogContent>
    {/* complete form fields */}
  </DialogContent>
  <DialogActions>
    <Button type="button" onClick={closeModal}>Cancel</Button>
    <Button type="submit" variant="contained" onClick={save}>Save</Button>
  </DialogActions>
</Dialog>
```

Rules:
- Import `Dialog`, `DialogTitle`, `DialogContent`, `DialogActions` from `@mui/material`.
- `onClose` handles both the overlay click and Escape — do not re-implement either.
- The close button must use `type="button"`.
- Never render an unfinished modal body.

## 13. LINKS AND ROUTES — ZERO 404 INVENTION

1. Every `href` must exactly match an entry in `VALID_ROUTES`.
2. Never derive a route from an entity name.
3. Never invent `/create`, `/edit`, `/details`, or dynamic routes.
4. Use API actions for edit/delete unless the exact page route exists.
5. Use `Link` from `next/link` for internal navigation.
6. Never use a plain anchor for client-side internal navigation unless the TASK explicitly requires it.
7. Never put a button inside a link or a link inside a button.
8. Layout nav items must be created only from supplied `NAV_ITEMS` and `VALID_ROUTES`.

## 14. LAYOUT-SPECIFIC RULES

For `components/layouts/<Role>Workspace.tsx`:
1. Use the exact export name.
2. Import `ReactNode` as a type.
3. Render `{children}` exactly once.
4. Render only supplied nav links.
5. No API calls, data loaders, forms, tables, or CRUD state.
6. No fake current-user information.
7. No client-side authorization decision.
8. No logout implementation unless an exact route/action is supplied.
9. Do not nest another role workspace.
10. Use static Tailwind classes only.
11. Keep the layout responsive without duplicating desktop and mobile children.
12. A navigation label and its route must remain paired exactly as supplied.

## 15. STYLING AND ACCESSIBILITY SAFETY

1. Use static Tailwind class strings only.
2. Never construct dynamic Tailwind classes such as ``bg-${color}-500``.
3. Brand accents use `bg-accent`, `text-accent`, `border-accent`, or `ring-accent`.
4. Use dark surfaces consistently: `bg-slate-900`, `text-slate-100`, `border-slate-800`.
5. Do not import CSS in the component.
6. Do not use inline style objects unless the TASK requires a calculated numeric width/height.
7. Buttons must have clear text or an `aria-label` when icon-only.
8. Inputs must have labels or an accessible name.
9. Images require accurate `alt` text; decorative images use `alt=""`.
10. Do not use `dangerouslySetInnerHTML`.
11. Do not use color alone to communicate status; include status text.
12. Keep focus states visible.

## 16. CLIENT/SECURITY RULES

Never:
- import server models or database code
- read secrets from `process.env` in the client
- place tokens in localStorage/sessionStorage
- trust a client-provided role or owner ID
- implement authorization solely by hiding UI
- render unsanitized HTML
- log passwords, tokens, cookies, or full sensitive records
- send hidden ownership/audit fields
- hard-code credentials

The httpOnly authentication cookie is sent automatically with same-origin relative fetch requests. Do not manually read or construct it.

## 17. COMPLETENESS AND SIZE CONTROL

1. Correctness is more important than decorative complexity.
2. Prefer fewer display columns over an unfinished file.
3. Never omit a required form field to add visual decoration.
4. Avoid large helper abstractions and repeated decorative markup.
5. If the component grows too large, remove icons, animations, charts, secondary panels, and optional columns first.
6. Keep the file reasonably compact, but there is no permission to truncate it.
7. Never split code across responses.
8. Never reference a helper/component that was not emitted or imported.

## 18. ABSOLUTE FORBIDDEN PATTERNS

Never emit any of the following:
- unfinished code
- markdown fences
- multiple default exports
- raw Mongoose model imports
- `any` or TypeScript suppression comments
- fake routes or endpoints
- fake DTO fields
- raw table markup
- uninstalled packages
- populated-reference property access on string IDs
- client-supplied owner/audit fields
- nested forms
- async `useEffect` callback
- hooks inside conditions
- state updates during render
- direct object rendering as JSX
- dynamic Tailwind class construction
- `Math.random()` keys
- array-index keys when `_id` exists
- duplicate sidebars/topbars in feature components
- missing loading/error/empty states
- silent catch blocks
- unresolved identifiers
- unused imports
- placeholder copy
- mock data when a real API is supplied

## 19. CANONICAL SAFE READ-ONLY EXAMPLE

Use this shape when CRUD metadata is incomplete but list metadata is valid:

```tsx
'use client'
import { useCallback, useEffect, useState } from 'react'
import type { Ingredient } from '@/types'
import { Alert, Box, Button, Card, CircularProgress, Paper, Stack, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material'

export default function IngredientTable() {
  const [rows, setRows] = useState<Ingredient[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadRows = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await fetch('/api/ingredients')
      const json = await response.json()
      if (!response.ok || !json.success) {
        throw new Error(json.error || json.message || 'Failed to load ingredients')
      }
      setRows(Array.isArray(json.data) ? json.data : [])
    } catch (cause) {
      setRows([])
      setError(cause instanceof Error ? cause.message : 'Failed to load ingredients')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadRows()
  }, [loadRows])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 3 }}>
        <CircularProgress size={20} />
        <Typography color="text.secondary">Loading ingredients…</Typography>
      </Box>
    )
  }

  if (error) {
    return (
      <Card sx={{ p: 3 }}>
        <Stack spacing={2} alignItems="flex-start">
          <Alert severity="error">{error}</Alert>
          <Button type="button" variant="outlined" onClick={() => void loadRows()}>Retry</Button>
        </Stack>
      </Card>
    )
  }

  if (rows.length === 0) {
    return (
      <Card sx={{ p: 3 }}>
        <Typography color="text.secondary">No ingredients have been added yet.</Typography>
      </Card>
    )
  }

  return (
    <TableContainer component={Paper}>
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Name</TableCell>
            <TableCell>Unit</TableCell>
            <TableCell>Quantity</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row._id}>
              <TableCell>{String(row.name ?? '—')}</TableCell>
              <TableCell>{String(row.unit ?? '—')}</TableCell>
              <TableCell>{String(row.quantity ?? '—')}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
```

## 20. FINAL VALIDATION GATE — CHECK SILENTLY BEFORE OUTPUT

Do not emit the file until every answer is YES:

### Output
- Does line 1 equal exactly `'use client'`?
- Is there TSX only, with no markdown or prose?
- Is there exactly one complete file?
- Is there exactly one named default export matching `EXPORT_NAME`?

### Syntax
- Are all tags and delimiters closed?
- Is every `.map(...)` callback complete?
- Is there no placeholder or truncation marker?
- Is every JSX attribute syntactically valid?

### Imports
- Is every used symbol imported or declared?
- Is every import actually used?
- Are all import paths allowed and exact?
- Are there zero uninstalled/server-only packages?

### Types
- Are entity rows typed with the shared DTO?
- Are only supplied DTO fields accessed?
- Are there zero `any`, suppression comments, non-null assertions, or fake model types?
- Is `_id` the only record identity field?

### React
- Are hooks top-level and unconditional?
- Is `useEffect` synchronous and are async calls invoked with `void`?
- Are dependencies complete and non-looping?
- Are inputs controlled with safe defaults?

### API
- Are all URLs relative and exactly supplied?
- Are `response.ok` and `json.success` checked?
- Is `json.data` used correctly?
- Are list results protected by `Array.isArray`?
- Are errors shown and mutations guarded?
- Are only writable fields submitted?

### Forms
- Are all required fields present?
- Are refs dropdowns with string `_id` values?
- Are enums selects, booleans checkboxes, numbers converted, and dates normalized?
- Are optional empty ObjectIds/numbers omitted?
- Are owner/audit fields absent?

### UI
- Does a feature avoid global navigation/shell UI?
- Does a layout render children once and use only valid routes?
- Are loading, error, and empty states present?
- Are table primitives used instead of raw table markup?
- Are all keys stable `_id` values?

If any answer is NO, repair the file internally before emitting it.