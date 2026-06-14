# V2: AI Designer outputs a COMPLETE Next.js app

User requirement: "user says I want a web app -> our agentic app generates a full,
complete Next.js app (frontend + backend combined, local database)."

## Architecture decisions

1. **Next.js 14 (App Router), JavaScript** — file-based routing makes routes
   DETERMINISTIC (folders, not LLM-written router config: kills the route-bug class).
2. **Backend = Next API route handlers + local JSON database**
   - `data/db.json` (seeded per project by the generator)
   - `src/lib/db.js` — server-side read/write with simple locking
   - **Generic CRUD API, zero LLM backend code**:
     - `src/app/api/records/[entity]/route.js` (GET list, POST create)
     - `src/app/api/records/[entity]/[id]/route.js` (GET one, PUT, DELETE)
     - `src/app/api/auth/login|register/route.js` (checks users in db.json)
   - Frontend calls via `src/lib/api.js` client helpers (`api.list('Patient')` ...).
3. **UI stack pre-installed in the scaffold** (`next_scaffold/`, npm install ONCE,
   node_modules shared to each project via junction):
   react, next, lucide-react (icon pack), tailwindcss, shadcn-style ui kit
   (button/card/form/extras vendored in src/components/ui), shadcn color tokens
   (CSS variables in globals.css; per-project accent written to theme.css by the
   Color Planner), cva + clsx + tailwind-merge.
4. **All generated pages are client components** (`'use client'`) — avoids every
   server-component pitfall for LLM code. Layouts/shells are deterministic:
   - `src/app/(marketing)/layout.jsx` — Navbar shell (logo, links, login CTA)
   - `src/app/(app)/layout.jsx` — Sidebar shell + client auth guard
   - route folders generated per plan: marketing pages, auth, dashboard,
     entity CRUD (list/new/detail/edit via `[id]` where sensible), role workspaces.
5. **Images: 14 slots, NO duplicates** — Fooocus writes to `public/assets/`:
   logo, hero, feature1, feature2, about1, about2, auth, contact, banner, cta,
   gallery1..4. A slot-assignment map gives every page DISTINCT images; QA agent
   rejects any page that uses the same asset twice.
6. **Pipeline with gated preview** (`status.json` phases, studio shows status):
   plan -> scaffold copy -> pages -> db seeds -> [phase: images] Fooocus (blocking,
   "image generating" status) -> [phase: qa, HIDDEN] bug-fixing agent: audits the
   build against the plan (every planned route exists & builds, no dup images,
   no placeholders, lint-level checks) and fixes immediately -> `next build`
   (errors -> auto-fix loop, max 2) -> [phase: done] -> backend starts
   `next start -p <port>` and the studio iframe shows the REAL app.
   The user only ever sees: generating -> image generating -> quality check -> preview.
7. **LLM code guard** (filter before any file lands):
   - must start with 'use client' + valid ESM; imports whitelist (react,
     next/link, next/navigation, lucide-react, @/components/ui/*, @/lib/api)
   - babel parse check; banned: require(), window.AppDB (use api.*), <br> auto-close,
     asset paths normalized to /assets/* (public), no fetch to external hosts
   - default export required; retry loop, then deterministic fallback page.
8. **Library templates** (landing x3, dashboard x2, pro-table) converted to
   Next + shadcn + lucide; landing copy-slots system carries over unchanged.

## Build order
S1 scaffold + npm install + smoke `next build`
S2 deterministic core: layouts, auth guard, generic API, db.js/api.js, theme writer
S3 generator: page conventions + templates conversion + code guard
S4 pipeline: status.json + images phase + QA agent + build loop + preview server mgmt
S5 studio frontend: status display + gated iframe
S6 validate 1 app end-to-end, then the 5-app live accuracy loop
