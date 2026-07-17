# RULE — Page body component (`components/pages/<Component>.tsx`)

You generate ONE client component that renders a page's content. Output **only** TSX, no markdown,
no prose. First line exactly: `'use client'`.

## DESIGN BAR — ship a designed product, never a wireframe (applies to EVERY page)
This page is going in front of a real user. A bare form stacked on a bare table is a FAILURE even if it
compiles. Every page you write must satisfy ALL of these:
- **Hierarchy.** One clear `<Typography variant="h4">` page title with a one-line
  `color="text.secondary"` subtitle that says what the user can DO here. Section headings step down
  (h5/h6). Never open with an unlabelled form or table.
- **Rhythm.** Consistent spacing on a 8px scale (`spacing={2}`/`{3}`, `sx={{ p: 3 }}`), a
  `maxWidth` container (`sx={{ maxWidth: 1100, mx: 'auto' }}`), and breathing room between bands
  (`mt: 4`+). Never cram controls edge-to-edge.
- **Depth.** Group content in `<Card>`/`<Paper>` with real elevation and rounded corners; separate
  bands with contrast, not just `<Divider>` everywhere.
- **Colour with intent.** Use the THEME (`color="primary"`, `color="secondary"`, `color="error"`,
  `color="text.secondary"`, `sx={{ bgcolor: 'background.paper' }}`) — the theme already carries this
  app's palette. Never hard-code a hex. Colour must MEAN something (primary = the main action,
  error = destructive, chips for status).
- **A real primary action.** The page's main action is one prominent `variant="contained"` Button with
  an icon; secondary actions are `variant="outlined"`/`text`/`IconButton`. Never two competing
  contained buttons side by side.
- **Every state is designed.** Loading = `<CircularProgress />` (or skeletons) with context, not a bare
  spinner in the corner. Empty = an icon + a headline + a one-line prompt + the primary action — never
  the word "No data". Error = `<Alert severity="error">` with the server's message and a Retry.
- **Real domain copy.** Headings, labels, empty states and helper text speak the app's domain in plain
  language. NEVER lorem ipsum, "Section content", "Item 1", or a TODO.
- **Never invent facts.** No made-up statistics ("10k+ Active Members", "50k+ Notes Shared"), fake
  testimonials, customer logos, ratings or awards — this app launched today with zero users, and
  printing numbers it did not earn is a lie on its front page. Every number on screen comes from the
  API. Sell with what the product DOES (how it works, what a user gets), not with invented proof.
- **Considered lists.** Tables/lists show the fields a human needs, formatted (dates as
  `toLocaleDateString()`, money with a currency, status as a coloured `<Chip>`), with hover feedback.
- **Responsive.** It must look deliberate at 375px and at 1440px — stack with
  `direction={{ xs: 'column', md: 'row' }}`, never a horizontal scrollbar on mobile.

## Universal requirements
- **NEVER render your own sidebar, top-nav, role menu, brand header, or page shell.** The app's section
  layout ALREADY wraps this page with the role sidebar + header — rendering another one produces TWO
  sidebars. Output ONLY this page's content (headings, sections, tables, forms, cards) inside a single
  root `<div>`/`<main>` — no `<aside>`, no nav links to other role pages, no `<Workspace>` wrapper.
- One default export: `export default function <Component>(props)`.
- TypeScript types for records/forms/props. When the TASK names a resource entity,
  `import type { <Entity> } from '@/types'` and type records with it (`useState<<Entity>[]>`) — do NOT
  redefine the entity's fields locally and do NOT use `interface Row { [k: string]: unknown }` for an
  entity record (that disables field checking). A generic `Row` is allowed only for an unnamed record.
- Tailwind for styling. Dark, modern, responsive (`max-w-7xl mx-auto`, grids, hover states).
- Fetch RELATIVE API URLs only (`/api/<segment>`); the httpOnly cookie is sent automatically.
- API responses are enveloped: `{ success: true, data }`. After `await res.json()`, read `.data`.
- Never send `owner`/`userId` from the browser; never implement auth/role checks client-side.
- Always handle loading, error and empty states.
- Real domain copy — NO lorem ipsum, NO "Section content" placeholders.
- Any function that uses `await` MUST be declared `async` (e.g. `const load = async () => { await … }`).
- Close every JSX tag and every `.map(...)` callback; the file must be valid TSX that `next build` accepts.
- Every `import` must have a real module path. Import ALL UI components from **`@mui/material`** and ALL
  icons from **`@mui/icons-material`** (Material UI is the app's component library). Besides those, use
  ONLY: `react`, `framer-motion`, `next/*`, `@/types`. NEVER import from `@/components/ui/*`, shadcn,
  `@mui/x-*`, `@mui/lab`, `antd`, `@chakra-ui`, `react-icons`, or `lucide-react` — those are reserved for
  the app's fixed internal stack and must never appear in a file you write; mixing them with MUI breaks
  the page. NEVER import from an empty or blank string.
- You MAY still use Tailwind utility classes via `className` for page LAYOUT (spacing, grid, section
  bands) — Tailwind is configured. But every INTERACTIVE/UI element (buttons, inputs, selects, tables,
  cards, dialogs, chips, alerts) MUST be a Material UI component, styled with the `sx` prop.
- **Links must be real.** Every `<a href>` / router push MUST target a route in the VALID ROUTES
  list you are given. Never invent a route or link to one that isn't listed — that causes a 404.
  For acting on a record (view/edit/delete), call the API with `fetch`; only navigate to a detail
  page if that detail route is explicitly listed.

## Form fields — the #1 source of runtime bugs (follow EXACTLY)
- **Reference (ObjectId) fields MUST be MUI dropdowns, never text inputs.** For a field marked
  `type=ObjectId` with a `ref` (you are given a REFERENCE FIELDS list with each field's exact
  `/api/<seg>` endpoint), on mount `fetch` that endpoint and render a MUI `<Select>` with `<MenuItem>`
  (NOT `<option>`):
  `<FormControl fullWidth><InputLabel>Field</InputLabel><Select label="Field" value={form.field ?? ''} onChange={e => setForm({ ...form, field: e.target.value })}>{opts.map(o => <MenuItem key={o._id} value={o._id}>{o.name || o.title || o.code || o._id}</MenuItem>)}</Select></FormControl>`.
  Typing a name or number into an ObjectId field crashes the server ("Cast to ObjectId failed").
- **Enum fields → MUI `<Select>`+`<MenuItem>`** of the enum values. **Boolean →
  `<FormControlLabel control={<Checkbox checked={v} onChange={e=>setV(e.target.checked)} />} label="…" />`.
  Number → `<TextField type="number">` with `Number(e.target.value)`. Date → `<TextField type="date"
  InputLabelProps={{ shrink: true }}>`. Text → `<TextField>`.**
- **`<TextField>` takes `label`, NEVER `labelId`** — `labelId` belongs to `<Select>`/`<InputLabel>`
  only, and on a TextField it is a type error. In a form holding both, keep them apart:
  `<TextField label="Quantity" … />` and
  `<FormControl fullWidth><InputLabel id="s-label">Status</InputLabel><Select labelId="s-label" label="Status" …>`.
- **Array / `[String]` fields (e.g. `ingredients: string[]`) → `<TextField multiline minRows={4}>` bound
  to a LOCAL `string`**, one item per line, split on submit:
  `ingredients: form.ingredients.split('\n').map(s => s.trim()).filter(Boolean)`. Seed an edit form with
  `(initialItem.ingredients ?? []).join('\n')`. NEVER bind an array field straight to an input.
- **Form state is its OWN type, never the entity DTO.** `useState<Partial<Recipe>>({ ingredients: '' })`
  is a type error the moment a field is an array or a number — an input's value is always a `string`.
  Declare `type RecipeForm = { title: string; ingredients: string; prepTime: string }` (every field a
  string) and convert on submit: `Number(form.prepTime)`, `form.ingredients.split('\n')`. The DTO types
  API RECORDS (`useState<Recipe[]>([])`), not form state.
- **Do NOT put owner/actor fields in the form** (`owner`, `userId`, `createdBy`, `recordedBy`,
  `receivedBy`, `reviewedBy`, `processedBy`, `markedBy`, `publishedBy`) — the server sets those.
- **Include every REQUIRED field** in the form. For an OPTIONAL empty value, omit the key (do not send
  an empty string for an ObjectId/number).
- **Persist and show it live.** On submit, `await fetch('/api/<segment>', { method: 'POST', headers: {
  'Content-Type': 'application/json' }, body: JSON.stringify(payload) })`, then read the enveloped
  `{ success, data }`: on `success` **close the form/modal, reset the fields, and RE-FETCH the list** so
  the new record appears immediately; on failure show `data`/`error` inline. Never assume it saved — always
  re-fetch. Edits use `PUT /api/<segment>/<id>`; deletes use `DELETE` with a confirm, then re-fetch.

## By page kind

### `landing` / `static` (PUBLIC, no login) — NAVBAR + MINIMUM 4 `<section>` bands
- Root `<main>`. **First element is a sticky top `<nav>`** with the brand name on the left and, on the
  right, in-page anchor links to the section bands (`<a href="#feed">`). Example — copy this shape:
  `<nav className="sticky top-0 z-40 flex items-center justify-between px-6 py-4 bg-slate-950/80 backdrop-blur border-b border-white/10"><span className="font-black text-white">Brand</span><div className="flex items-center gap-4"><a href="#feed" className="text-slate-200">Feed</a><a href="#about" className="text-slate-200">About</a></div></nav>`.
- **Login / Sign up links ONLY if `/login` is in your VALID ROUTES.** An app with no accounts has no
  such pages: a "Login" or "Join" button there is a dead 404 button on the app's front door. When they
  ARE listed, add `<a href="/login">Login</a>` and `<a href="/signup">Sign up</a>` to the nav.
- **A band is `<Box component="section">`, NEVER a bare `<section>`.** `sx` is a MUI prop: putting it
  on a raw DOM element is a type error on every band (`Property 'sx' does not exist on type
  'DetailedHTMLProps<HTMLAttributes<HTMLElement>>'`). `<Box component="section">` renders a real
  `<section>` tag AND takes `sx`. Same for a MUI-styled nav/footer: `<Box component="nav" sx={…}>`.
  ```tsx
  <Box component="section" id="feed" sx={{ py: 10, bgcolor: 'background.paper' }}>
    <Container maxWidth="lg">…</Container>
  </Box>
  ```
- Then **at least 4** distinct bands: Band 1 = hero (headline from the app/brand, sub-tagline,
  CTA links to routes that exist); one band per provided page-section label with a heading + real
  copy + cards; a contact/footer band ends the page.
- **When a RESOURCE is supplied, this page IS the app — not a brochure.** Every section label that
  implies data (QuickAdd, NewEntry, Form, List, Feed, Grid, Board, Entries…) must be FULLY FUNCTIONAL
  on this page: a controlled MUI form that POSTs to `/api/<segment>` and, on success, resets and
  re-fetches; a live list rendered from `GET /api/<segment>` with loading/empty/error states. A
  single-page app has nowhere else to do its job — never replace the working form/list with marketing
  cards or a "coming soon" placeholder.
- Each band sets its own background (`sx={{ bgcolor: 'background.default' }}` / `'background.paper'`,
  alternating) and wraps its content in `<Container maxWidth="lg">`.

### `list` — read + (link only if a detail route exists)
- `useEffect` → `GET /api/<segment>`, render a responsive grid/table of the records. Link a row to
  `/<segment>/<id>` ONLY if that detail route is in VALID ROUTES; otherwise show the fields inline
  (no row link). Loading/empty/error states. Add a create link only if a create route is listed.

### `table-crud` (staff CRUD) — full CRUD
- Load `GET /api/<segment>`. A table with the first ~4 fields. A "New" button opens a modal form built
  from the resource fields (text/number/date/checkbox/select-for-enum). Save = `POST` (new) or
  `PUT /api/<segment>/<id>` (edit). Row actions: Edit (opens modal) + Delete (`DELETE`, with confirm).
  Re-fetch after every mutation. Show server error messages.
- **Keep it compact — the whole file must be COMPLETE and under ~200 lines so it is never truncated.**
  Show only the first ~5 fields as table columns. Do not over-decorate.

## UI components, icons & modals — use Material UI (MUI), import EXACTLY like this
ALL UI components come from **`@mui/material`**; ALL icons from **`@mui/icons-material`**. NEVER import
UI from `@/components/ui/*`, shadcn, or any other library. Import the components you actually use:
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
- **This app runs Material UI v7. NEVER use `Grid`.** In v7 `Grid` took the old Grid2 API — the `item`
  prop and `xs`/`sm`/`md` props no longer exist, so the `<Grid item xs={12}>` form you may remember
  fails the build with "No overload matches this call". Do not import `Grid` at all. Lay out with:
  - a row: `<Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>…</Stack>`
  - a column: `<Stack spacing={2}>…</Stack>`
  - a responsive card grid: `<Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr', md: 'repeat(3, 1fr)' }, gap: 2 }}>…</Box>`
- **Style with the `sx` prop** (theme-aware), e.g. `<Box sx={{ p: 3, maxWidth: 1100, mx: 'auto' }}>`. The
  app theme is dark — do NOT hard-code background colors on MUI components; the theme handles them.
- **`sx` belongs to MUI components ONLY.** `<section sx={…}>`, `<div sx={…}>`, `<nav sx={…}>` and
  `<footer sx={…}>` do not compile — a raw DOM element has no `sx` prop. Need a semantic tag with
  `sx`? Use `<Box component="section">` / `<Box component="nav">`. Need a raw element? Style it with
  `className` and Tailwind instead.
- **Button:** `<Button variant="contained">Save</Button>`, `<Button variant="outlined">`,
  `<IconButton size="small"><EditIcon /></IconButton>`. Give a Button a leading icon with `startIcon={<AddIcon />}`.
- **Text input:** `<TextField label="Name" value={v} onChange={e => setV(e.target.value)} fullWidth />`;
  multiline = add `multiline minRows={3}`; number = `type="number"`; date = `type="date" InputLabelProps={{ shrink: true }}`.
- **Select (enum / reference):** MUI Select uses `<MenuItem>` (NEVER `<option>`):
  `<FormControl fullWidth><InputLabel>Status</InputLabel><Select label="Status" value={v} onChange={e => setV(e.target.value)}>{opts.map(o => <MenuItem key={o} value={o}>{o}</MenuItem>)}</Select></FormControl>`.
- **Table:** `<TableContainer component={Paper}><Table><TableHead><TableRow><TableCell>Col</TableCell></TableRow></TableHead><TableBody>{rows.map(r => <TableRow key={r._id}><TableCell>{r.field}</TableCell></TableRow>)}</TableBody></Table></TableContainer>`.
- **Modal → use MUI `Dialog`** (there is a real Dialog now — do NOT build a hand-rolled overlay div):
  `<Dialog open={open} onClose={close} fullWidth maxWidth="sm"><DialogTitle>{editing ? 'Edit' : 'New'}</DialogTitle><DialogContent>…form fields…</DialogContent><DialogActions><Button onClick={close}>Cancel</Button><Button variant="contained" onClick={save}>Save</Button></DialogActions></Dialog>`.
- **States:** loading = `<CircularProgress />`; error = `<Alert severity="error">{msg}</Alert>`; empty =
  `<Typography color="text.secondary">No records yet.</Typography>`.
- **Icons:** OPTIONAL. Import each as a default import `import XIcon from '@mui/icons-material/X'` where `X`
  is a PascalCase Material icon name (`Add`, `Edit`, `Delete`, `Search`, `Close`, `Check`, `Home`, `Person`,
  `People`, `Settings`, `Logout`, `Menu`, `Dashboard`, `CalendarToday`, `AttachMoney`, `ShoppingCart`,
  `Inventory`, `Description`, `Notifications`, `Visibility`, `FilterList`, `Download`, `Refresh`,
  `Favorite`, `FavoriteBorder`, `AutoAwesome`, `TrendingUp`, `AccessTime`, `Email`, `Star`,
  `StarBorder`, `Bookmark`, `Share`, `Print`, `Timer`, `Language`, `LocalOffer`). Plain text is always fine.
- **Need a domain icon? Pick one of these REAL Material names** — do NOT coin one (`Cook`, `Chef`,
  `Recipe` do not exist and the build fails): food/cooking → `Restaurant`, `LocalDining`,
  `RestaurantMenu`, `MenuBook`, `Kitchen`, `Fastfood`, `Cake`, `LocalCafe`; shopping → `ShoppingCart`,
  `ShoppingBasket`, `LocalOffer`; health → `LocalHospital`, `MedicalServices`; travel → `Flight`,
  `Hotel`, `DirectionsCar`; media → `PhotoCamera`, `MusicNote`, `Movie`; work → `Work`, `Business`,
  `School`. If nothing fits, use no icon — a text button is always correct.
- **Use the MATERIAL name, not the lucide/Feather one you are used to** — those modules do not exist and
  the build fails: it is `Favorite` NOT `Heart`, `Delete` NOT `Trash`, `Add` NOT `Plus`, `Edit` NOT
  `Pencil`, `Close` NOT `X`, `Person` NOT `User`, `People` NOT `Users`, `Settings` NOT `Gear`,
  `ShoppingCart` NOT `Cart`, `CalendarToday` NOT `Calendar`, `Notifications` NOT `Bell`,
  `Visibility` NOT `Eye`, `AttachMoney` NOT `DollarSign`. If unsure, use one from the list above.

### `form` — create/edit
- Controlled inputs for the resource fields. On success navigate back to the list; show server
  validation errors.
- **NEW form** (route has no `[id]`): signature `()` — takes NO props. Submit `POST /api/<segment>`.
- **EDIT form** (route ends `/[id]/edit`): signature
  `({ initialItem }: { initialItem: Record<string, any> })` — the page already fetched the record and
  passes it. Seed the form state from `initialItem` and submit `PUT /api/<segment>/<id>` using
  `initialItem._id`. Do NOT re-fetch it, do NOT take an `id` prop, and do NOT rename the prop.

### `detail` — read one
- Signature `({ initialItem }: { initialItem: Record<string, any> })`. Render the passed record's
  fields (skip `_id`,`__v`,`owner`) + a Back link. Do NOT re-fetch.

### `dashboard` — role overview
- On mount `fetch('/api/reports?type=summary')` and read `.data` for KPI numbers (it returns
  `{ counts, revenue?, ... }`). Render KPI stat cards from those numbers, then quick-nav `<a>` cards to
  the role's routes (VALID ROUTES only). If the summary fetch fails, show 0s — never crash. Do not
  invent other endpoints.

### `finance` / `pos` / `workflow` / `reports`
- Functional screens for their flow. `finance`: invoices list + record-payment action
  (`POST /api/invoices/<id>/payments`). `pos`: item search + cart + checkout (`POST /api/pos/checkout`).
  `workflow`: status-driven list with allowed transitions. `reports`: pick a report, fetch it, show a
  table + CSV export. Use only endpoints that exist in the API memory.
