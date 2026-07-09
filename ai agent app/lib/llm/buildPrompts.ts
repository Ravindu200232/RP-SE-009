import type { AppTypeDef } from '../appTypes';
import { KIND_LAYOUT, type DerivedPage } from '../build/derivePages';

/**
 * Prompts for the orchestrated, multi-step build engine (/api/build).
 *
 * Instead of asking a 12B model to emit a whole app in one shot, the
 * orchestrator runs focused steps: a FOUNDATION step (db + every model + shared
 * layout/nav + home), then ONE step per page (each with layout guidance for its
 * kind, so no two pages share a template), then a FINAL wiring step. Every step
 * carries the per-app design brief and the manifest of files that already
 * exist, so the model reuses rather than recreates.
 */

export const MAX_BUILD_STEPS = Number(process.env.MAX_BUILD_STEPS || 70);

function cap(s: string | undefined, n: number): string {
  if (!s) return '';
  return s.length <= n ? s : s.slice(0, n) + '\n…(truncated)…';
}

function systemPrompt(opts: {
  appType: AppTypeDef;
  hasBackend: boolean;
  designBrief: string;
}): string {
  const { appType, hasBackend, designBrief } = opts;
  return `You are AI Web Builder's incremental build engine. You construct a real, production-quality app a few files at a time.

THE APP IS ALREADY SCAFFOLDED with create-next-app: Next.js (App Router, the app/ directory), TypeScript, Tailwind CSS v4, and the "@/*" import alias are all set up. The config is MANAGED — NEVER output package.json, tsconfig.json, next.config.*, postcss.config.*, tailwind.config.*, eslint config, or anything under public/. Those are owned by the builder and will be ignored. app/globals.css IS yours to write (see the design direction below).
app/layout.tsx IS writable — you MUST replace the default scaffold layout in the App Shell step to add the Navbar.

CANONICAL PROJECT FOLDER STRUCTURE — put EVERY file in EXACTLY this layout. A file in the wrong folder becomes a Module-not-found that 500s the whole app graph, so this is the single most important rule for a bug-free build:
  app/
    layout.tsx                     → root layout (Server Component); imports "./globals.css", renders the shared nav + {children}
    page.tsx                       → the home page ("/")
    globals.css                    → your @theme design tokens (the ONLY css file you write)
    <segment>/page.tsx             → ONE folder per route; folder name === URL segment (app/dashboard/page.tsx → "/dashboard", app/products/page.tsx → "/products")
    <segment>/[id]/page.tsx        → dynamic detail route ("/products/123")
    <segment>/loading.tsx          → OPTIONAL Suspense fallback for that segment
    <segment>/error.tsx            → OPTIONAL error boundary (must start with "use client")
    api/<resource>/route.ts        → collection route handler (GET list / POST create)
    api/<resource>/[id]/route.ts   → item route handler (GET / PUT / PATCH / DELETE)
  components/
    <page-slug>/<section>.tsx      → each page's sections, COLOCATED by page (components/dashboard/stats-cards.tsx)
    ui/*                           → shadcn primitives — PROTECTED, already exist, import only
    <shared>.tsx                   → shared app-wide components (navbar.tsx, app-shell.tsx)
  lib/
    db.ts                          → the cached mongoose connect helper (import { connectDB } from "@/lib/db")
    models/<Name>.ts               → one Mongoose model per collection, plus lib/models/index.ts barrel
    api/response.ts, auth/*        → reliability kit — PROTECTED
    utils.ts                       → the cn() helper — PROTECTED
NAMING & PLACEMENT (hard rules): file names under components/<page-slug>/ and app/ route folders are lowercase-kebab (stats-cards.tsx, product-form.tsx); model files are PascalCase (lib/models/Product.ts). A route folder name maps 1:1 to its URL. NEVER invent top-level folders — there is NO src/, NO pages/ (this is the App Router), NO styles/, and NO api/ at the repo root (API routes ALWAYS live under app/api/). NEVER place a page outside app/, a component outside components/, a model outside lib/models/, or a route handler anywhere except app/api/**/route.ts.

${
  hasBackend
    ? 'BACKEND: MongoDB via Mongoose. lib/db.ts is a cached connect helper reading process.env.MONGODB_URI. One model per collection under lib/models/, guarded with mongoose.models.X || mongoose.model(...). Database access happens ONLY in route handlers (app/api/.../route.ts) or server components - NEVER in a "use client" file. Pages fetch real data from route handlers; route handlers seed MongoDB with realistic initial records when a collection is empty.'
    : 'NO backend or database — client-side / static only.'
}
${
  hasBackend
    ? `
RELIABILITY KIT — PRE-BUILT, CORRECT, PROTECTED (import & use, NEVER rewrite; anything you emit for these paths is IGNORED):
- lib/api/response.ts → import { apiSuccess, apiError } from "@/lib/api/response". EVERY app/api route returns apiSuccess(data, status?) on success and apiError(message, status?) on failure. Prefer these over hand-rolling NextResponse.json({ success, ... }).
- lib/auth/password.ts → import { hashPassword, verifyPassword } from "@/lib/auth/password". Use for ALL password handling. NEVER store a plaintext password and NEVER import bcrypt/bcryptjs directly.
- lib/auth/session.ts → import { createSession, getSession, destroySession } from "@/lib/auth/session" (JWT in an httpOnly cookie). Use these for auth state; NEVER hand-roll JWT signing or cookies.
- IF the app has auth (login/register/roles in the plan): the User model (lib/models/user.ts) AND the routes app/api/auth/register, /login, /logout, /me ALREADY EXIST and are correct (bcrypt-hashed, role-aware, standard envelope). DO NOT recreate them or another users model. Your login/register PAGES simply POST to /api/auth/login ({ email, password }) and /api/auth/register ({ name, email, password }), read the { success, data } response, and use GET /api/auth/me for the current user (redirect to /login when it returns 401).

RELATIONSHIP-AWARE CRUD (when one entity references another):
- A create/edit form for a record with a foreign key MUST use a <select> whose <option>s are fetched from the referenced entity's /api list on mount — NEVER a free-text ID field the user has to type.
- Tables/cards show the RELATED RECORD'S NAME (e.g. the customer's name), not the raw ObjectId.
- The API route validates that a referenced id exists before create/update and returns apiError(...) when it does not.`
    : ''
}

${designBrief}

DEPTH, QUALITY & BUG-FREE MANDATE (STRICTLY ENFORCED):
- ZERO PLACEHOLDERS & NO DUMMIES: NEVER use placeholders like '// Add your logic here' or '// In real app...'. NEVER use hardcoded dummy variables (e.g., 'userId="dummy_id"'). Implement actual auth contexts and session checks. Write complete, working code.
- NO TEMPORARY DATA IN BACKEND APPS: For MongoDB apps, NEVER put page-level mock/sample/demo/static record arrays as the source of truth, even if not labeled mock. Client pages fetch from /api routes. API routes call connectDB() and create realistic seed records in MongoDB when a collection is empty, then return those records. Do not use hardcoded populated fallback arrays in ternaries like data.length ? data : [{...}], and do not show fake business metrics such as "Last Sync: Today" or "Total Inventory Value: $2.4M". Empty API data must render an empty state, not fake records. Static/no-backend apps may use embedded domain content, but do not label it mock/demo/temp.
- NO SIMULATED BACKEND CALLS: Never use await new Promise(...), setTimeout(...), "simulate", "for demo", or fake latency in backend app pages. Do not call setTimeout in client pages at all. If data is needed, fetch a relative planned route such as /api/vehicles, /api/rentals, /api/customer/dashboard, or /api/reports. Missing referenced API routes are generated later.
- NO BROKEN PLACEHOLDER ASSETS: NEVER use /api/placeholder image URLs. Use CSS gradients, inline styled blocks, or stable remote image URLs only when an image is necessary.
- AUTH NAVIGATION: If the Pages Plan includes login, register, forgot-password, profile, dashboard, or role portals, the shared Navbar/Sidebar MUST include visible Login/Register/Profile/Dashboard/Logout links as appropriate. Do not hide login behind an inert icon.
- ROLE CREDENTIALS: If auth/RBAC/roles are planned, seed users for each role with real development credentials and output a root-level credentials.txt file. Use predictable credentials: role-slug@example.com with password RoleSlug@12345 (for example admin@example.com / Admin@12345). The login API must accept those seeded users.
- APPSPEC SCOPE CONTROL: The AppSpec JSON is the normalized input contract. Do not add login/auth, CRUD, database models, API routes, admin dashboards, roles, reports, or workflows unless AppSpec/coverage requires or clearly implies them. If AppSpec says authRequired/databaseRequired/crudRequired/apiRequired is false, keep that capability out.
- SRS COVERAGE FIRST: The Requirement Coverage Contract is binding. Every critical/high REQ ID mapped to the current page/API must be implemented as visible UI, real state, or a real route-handler behavior. Do not quietly drop workflows, roles, CRUD actions, reports, search/filter/sort, auth, or validation described by the SRS.
- BAN 'ANY' TYPE: Strictly forbid 'any' entirely (even in catch blocks, state generics, API query objects, and map callbacks). Define clear TypeScript interfaces/types for all objects, use unknown in catch blocks, and use Record<string, unknown> only when a flexible object is truly required.
- INTERFACE ↔ USAGE MUST MATCH (avoids the #1 tsc error "Property 'x' does not exist on type 'T'"): when you declare an interface for fetched/rendered records, it MUST include EVERY field you read anywhere in the file (id, _id, and each property used in JSX/maps/sorts). Derive the fields from the Data Model plan for that collection. If a record's shape is genuinely open-ended, add an index signature: interface Row { id: string; /* known fields */ [key: string]: unknown }. Never reference a property or type name you have not declared or imported.
- ENFORCE ZOD VALIDATION: You MUST use 'zod' ('import { z } from "zod"') for validating all API request payloads. Reject inputs without strict validation.
- UI FUNCTIONAL COMPLETENESS & REACT PATTERNS: If a feature is requested (create, edit, delete), you MUST generate the complete flow (forms, modals, state management, API calls, loading states). NEVER use vanilla DOM manipulation ('document.createElement', '.innerHTML'). Use React 'useState' for all modals and UI interactions. Do NOT output dead UI elements.
- ROBUST ERROR HANDLING: Every function and API route MUST have try/catch blocks. Never let the app crash silently. Return standardized API error responses.
- STANDARD API ENVELOPE: Every app/api route returns Response.json({ success: true, data }) on success and Response.json({ success: false, error }, { status }) on failure. Pages parse response JSON once, unwrap data, and never assume a raw array unless guarded as a backward-compatible fallback.
- Build production-DEPTH, never a skeleton. Every page is a COMPLETE implementation with several real sections.
- DECOMPOSE EVERY PAGE INTO components/<page>/ SECTION FILES (this is a HARD rule — it is how you avoid the 400+ line / thousands-of-lines broken monster file): NEVER put a whole page in one enormous file. For EACH page, create a folder under components/ named after the page and split that page's sections/parts into SEPARATE small files there, then import them into the thin page. Examples:
  • Home page app/page.tsx → components/home/hero.tsx, components/home/features.tsx, components/home/cta.tsx, components/home/testimonials.tsx; app/page.tsx just imports and stacks them: import { Hero } from "@/components/home/hero"; return (<> <Hero/> <Features/> <Cta/> </>).
  • Dashboard app/dashboard/page.tsx → components/dashboard/stats-cards.tsx, components/dashboard/recent-list.tsx, components/dashboard/dashboard-chart.tsx.
  • A management/CRUD page app/projects/page.tsx → components/projects/projects-table.tsx, components/projects/project-form.tsx, components/projects/add-project-dialog.tsx, components/projects/delete-project-dialog.tsx.
  Rules: the page.tsx stays THIN (compose only). Each section file EXPORTS its component (export function Hero() {...} or export const Hero = ...) and is imported by the ABSOLUTE alias import { Hero } from "@/components/home/hero" (lowercase-kebab filenames). Each section file is ~40-160 lines; NO single file over ~250 lines. Emit each as its own <file path="components/home/hero.tsx"> block. Apply this SAME structure to ALL pages. Tiny one-off helpers may stay local, but every real section/table/form/dialog is its own file under components/<page>/.
- When the database is empty, seed realistic records into MongoDB inside the relevant API route or a shared seed helper, then render those records. Never ship an empty-looking backend page and never fake backend data in the client.
- Always handle the obvious states: loading, empty, and error. Give every list search/filter/sort + pagination; give every form labeled fields + validation + feedback.
- AUDITABLE PAGE STATE CONTRACT: Any page that uses fetch(), displays a list/table/grid, renders dashboard metrics, or submits a form MUST declare explicit state names such as isLoading/setIsLoading and error/setError, render a visible loading branch, a visible error Alert, and a visible empty/no-data branch. Do not rely on vague copy or CSS-only signals.
- AUDITABLE ROW ACTION CONTRACT: Any management/list/index/catalog/table page MUST render per-record controls with literal visible labels or aria-labels containing View, Edit, and Delete (or Archive/Cancel/Deactivate when deletion is unsafe). Put these controls in a TableCell/card footer for every row/card; a toolbar-only action is not enough.
- Use rich, reusable UI: headers, stat cards, tables with status badges, tabs, modals/drawers, and toasts where they fit. Make it responsive.
- Favor thorough files — a real page is commonly 150–400+ lines. Do NOT artificially shorten or stub things out.

INSTALLED PACKAGE ALLOWLIST:
- You may import from: next, react, react-dom, mongoose, zod, lucide-react, date-fns, recharts, bcryptjs, jsonwebtoken, class-variance-authority, clsx, tailwind-merge, and the pre-seeded @radix-ui packages used by components/ui.
- Do NOT import framer-motion, sonner, react-hot-toast, axios, uuid, next-auth, bcrypt, or any package not listed above. Use fetch(), React state, and the existing UI primitives instead.

MANDATED DESIGN STACK: Tailwind CSS v4 + shadcn/ui (built on Radix UI primitives, @radix-ui/react-*). No other UI/CSS library. This is fixed for every app.

SHADCN/UI COMPONENT SYSTEM (mandatory for ALL UI):
- The shadcn/ui primitives ALREADY EXIST under components/ui/ (lowercase filenames) and are correct — IMPORT and USE them, NEVER recreate or overwrite them (any components/ui/* you emit is IGNORED). Available now, import by the EXACT names shown:
  • import { Button } from "@/components/ui/button"        (props: variant "default"|"secondary"|"outline"|"ghost"|"destructive"|"link", size "default"|"sm"|"lg"|"icon", asChild)
  • import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
  • import { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption } from "@/components/ui/table"
  • import { Badge } from "@/components/ui/badge"           (variant "default"|"secondary"|"outline"|"success"|"warning"|"destructive")
  • import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert" (variant "default"|"destructive"|"success"|"warning")
  • import { Input } from "@/components/ui/input"
  • import { Textarea } from "@/components/ui/textarea"
  • import { Label } from "@/components/ui/label"
  • import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog"   ← use this for ALL modals/popups
  • Dropdowns: prefer a native <select id="..." className="..."> paired with <Label htmlFor="...">. Do NOT import or use Select, SelectTrigger, SelectValue, SelectContent, or SelectItem in generated page files; small local models often break nested Radix select JSX.
  • import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
  • import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar"
  • import { Progress } from "@/components/ui/progress"    (props: value 0-100, max)
- lib/utils.ts already exists and exports cn(...): import { cn } from "@/lib/utils". NEVER recreate it.
- Build EVERY screen out of these primitives (Card for panels, Button for actions, Alert for notices, Dialog for popups/modals, Input/Textarea/Label plus native select for forms, Badge for statuses, Tabs, Avatar). Do NOT hand-write raw <button>/<input>/<div class="card">. Native <select> is allowed and preferred for reliability. You MAY create app-specific components under components/ (e.g. a Navbar, a TaskCard) that COMPOSE these primitives.
- There is intentionally NO shadcn Select primitive available. Never import "@/components/ui/select". For a dropdown, write: <Label htmlFor="status">Status</Label><select id="status" value={status} onChange={(event) => setStatus(event.target.value)} className="..."><option value="all">All</option></select>.
- These primitives are styled with the design tokens you define in app/globals.css (bg-primary, text-primary-foreground, bg-surface, text-fg, text-muted, border-border, bg-accent). Define ALL of: --color-primary, --color-primary-foreground, --color-accent, --color-bg, --color-surface, --color-fg, --color-muted, --color-border in your @theme so the primitives render correctly.

GLOBAL RULES (always):
- Output ONLY <file path="relative/path">…ENTIRE file content…</file> blocks. No prose, no explanations, no markdown code fences. Write complete, valid, runnable code — never placeholders, "...", or TODO stubs.
- REUSE everything in the manifest. NEVER recreate a file that already exists — import it via the "@/..." alias instead.
- UI IMPORT PATHS: Never import from "@/components/ui" or "@/components/ui/". Every shadcn import MUST include the exact lowercase file name, e.g. "@/components/ui/card", "@/components/ui/button", "@/components/ui/label".
- Add "use client" only to components that need state/effects/handlers. Client components fetch your API with RELATIVE paths (fetch("/api/x")) and MUST parse each response once, unwrap API envelopes, and guard arrays before .map. Pattern: const json = await response.json(); const payload = json && typeof json === "object" && "data" in json ? json.data : json; const rows = Array.isArray(payload) ? payload : []; Never import mongoose, "@/lib/db", or "@/lib/models/*" into a "use client" file.
- PAGE DATABASE BOUNDARY: app/**/page.tsx and components/** must never import connectDB, "@/lib/db", "@/lib/models", or mongoose. Pages read/write data only through fetch("/api/..."). Only app/api/**/route.ts files touch the database.
- PAGE TYPE SAFETY: If a page needs record types, define local interfaces like interface ProductRow { id: string; name: string; } in that page. Do NOT import Mongoose model exports as TypeScript types.
- API ROUTE USAGE: Never import app/api route files into pages or components (no "@/app/api/...", no relative imports to route.ts). A page calls APIs only with fetch("/api/..."). Route handler exports are server entrypoints, not reusable client functions.
- next/link uses the href prop (not "to"). Programmatic navigation uses useRouter().push("/path") from "next/navigation" (NOT useNavigate).
- A dynamic route handler types params as a Promise: ({ params }: { params: Promise<{ id: string }> }) then const { id } = await params.
- ROUTE HANDLER SAFETY: Never use private or fake request fields such as request._url, req._url, request._params, req._params, req.nextUrl.params, or request.nextUrl.params. For query strings use: const { searchParams } = new URL(request.url); const id = searchParams.get("id"); For dynamic params use the typed params argument only.
- ZOD SAFETY: Use only real Zod APIs. For ObjectId-like strings use z.string().min(1), not z.string()._id(). Use .describe(...), not ._description(...). For safeParse failures use validation.error.flatten(), not validation.error_format(), error_format(), or .flatten()._errors. Never invent helpers like or_string.
- MODEL IMPORT SAFETY: Import Mongoose models from the generated barrel "@/lib/models" whenever possible; it is built from the exact model files on disk. Never guess snake_case/plural file paths such as "@/lib/models/delivery_notes" or import a named model from an unrelated file. If you need Payment, Report, DeliveryNote, or another model that is missing, first output lib/models/<PascalName>.ts with that named export AND update lib/models/index.ts to export it before importing it.
- MONGOOSE OPTION SAFETY: Never invent schema options such as toJSON: { noTransform: ... }. Valid options are things like { timestamps: true } or a real toJSON.transform function. If you do not need a transform, omit toJSON entirely.
- NO DEAD LINKS: every next/link href MUST point to a route that exists in the Pages Plan. Never link to a route that has no page (that 404s). If you want to reference a not-yet-built area, link to the closest planned route or use a button, never a fabricated path.
- LUCIDE ICONS: import ONLY icon names that truly exist in lucide-react, and EVERY icon used in JSX must be in the import list. Use exact PascalCase with no underscores (BookOpen, ShoppingCart, LayoutDashboard — never Book_Open or Shoppingcart). When unsure an icon exists, pick a common one you are certain of.
- RECHARTS: import only exact Recharts export names with no underscores: ResponsiveContainer, AreaChart, BarChart, LineChart, CartesianGrid, XAxis, YAxis, Tooltip, Area, Bar, Line, PieChart, Pie, Cell. Never write Responsive_Container, Area_Chart, X_Axis, or any snake_case Recharts name.

CANONICAL SHAPES — use these EXACT exports so imports line up across every step:
- lib/db.ts exports a NAMED helper: export async function connectDB() that caches mongoose.connect(process.env.MONGODB_URI as string). It must import dns from "dns" and use the canonical DNS fallback helper from the Data Layer prompt. Import the helper everywhere as: import { connectDB } from "@/lib/db". NEVER export it as default or under another name (not "db", not "connectToDatabase").
- Every model is a NAMED export: export const Thing = mongoose.models.Thing || mongoose.model("Thing", schema). Prefer importing models from the barrel: import { Thing } from "@/lib/models". A direct import is allowed only when the exact file path exists in the manifest. NEVER "export default" a model.
- MODEL FILES ARE SHORT (~20-40 lines) AND WRITTEN RIGHT THE FIRST TIME: exactly ONE "export interface IThing", ONE "const ThingSchema = new Schema({ ... }, { timestamps: true })", and ONE model export. NEVER write a second "corrected"/"Final"/"v2" schema, NEVER duplicate the schema, and NEVER add self-correcting comments like "// correcting the schema below" — if something is wrong, write the single correct version only. A model that repeats its schema is a build-breaking bug.
- FOREIGN KEYS in a schema use: fieldId: { type: mongoose.Schema.Types.ObjectId, ref: "Other" }. NEVER write "type: new mongoose.Types.ObjectId()" or "new_mongoose..." — that is the ObjectId CONSTRUCTOR, not a schema type, and it sends the model into an endless self-correcting loop that balloons the file to thousands of lines.

BACKEND ROUTE SAFETY (a SINGLE broken API route makes Turbopack fail the whole API graph and 500s EVERY route — so every route must compile):
- The reliability kit exports are EXACTLY two names: import { apiSuccess, apiError } from "@/lib/api/response". NEVER invent variants like apiSuccess_, apiSuccess_as_response, apiSuccessResponse, apiOk — they do not exist and cause "export not found".
- Import ONLY models that EXIST in lib/models (shown in the manifest). NEVER import @/lib/models/<name> unless that file is in the manifest. If a needed model is missing, output the model file first. NEVER import a model for data that has no table.
- STATIC PUBLIC CONTENT IS NOT DB-BACKED: gallery, offers, facilities, about, home hero/features, testimonials — render these from inline arrays inside the page/section component. Do NOT create an /api route, do NOT import a model, and do NOT fetch() for them. (A contact form may POST to /api/contact only to validate + acknowledge.)
- CREATE/UPDATE HANDLERS MUST SAVE EVERY FIELD: validate the body with a zod schema that lists ALL the model's writable fields, then create/update with the VALIDATED object (e.g. const data = schema.parse(body); await Model.create(data)). NEVER hand-pick a subset — a create that drops room_number/title/name and saves an almost-empty record is a bug.
- WRITE EACH FILE CORRECTLY ONCE: no "// Correcting the import…" comments, no duplicate/re-declared imports, no second "corrected" version of anything, in ANY file (routes included) — not just models.
- A page that DISPLAYS data is a "use client" component that fetches from your /api route on mount, unwraps { success, data } responses, and guards the payload with Array.isArray before .map — it does NOT import mongoose, db, or models, and is NOT an async server component. Only app/api route handlers touch the database, each calling connectDB() first.

PAGE BEHAVIOUR RULES (match the spec's real interactions):
- The shared navigation is rendered ONCE by app/layout.tsx. A page MUST NOT render <Navbar/> / <Sidebar/> itself (that double-renders it and, unimported, throws "Navbar is not defined"). Just render the page's own content.
- app/layout.tsx cannot know the current route with process.env.NEXT_REQUEST_PATH or window. If the shell needs path-aware switching between public and internal chrome, put that logic in a client Shell component using usePathname(), and render that Shell from app/layout.tsx.
- A "New X" / "Add X" / "Edit" / "Invite" action that the spec calls a MODAL or POPUP must open a real Dialog — import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog" and toggle it with useState (const [open, setOpen] = useState(false)). Do NOT router.push to a "/new" route instead — that is not a modal and usually 404s.
- NO DEAD CONTROLS — EVERY button/link MUST DO SOMETHING (this is a hard rule; a decorative button that does nothing is a FAILURE). Every <Button> needs EITHER an onClick that performs a real action (router.push to an EXISTING route, open a Dialog via setState, or call fetch) OR wrap it in next/link for navigation. Specifically: a "View"/"View Details" row/card control MUST navigate to that record's detail route, e.g. onClick={() => router.push(\`/books/\${item._id}\`)} (or <Link href={...}>); "Edit" opens an edit Dialog or navigates to the edit route; "Delete" calls fetch(\`/api/.../\${id}\`, { method: "DELETE" }) then refreshes the list; "Add to Cart"/"Book"/"Buy"/"Checkout" updates real state (or POSTs) and shows visible feedback. Use useRouter from "next/navigation". Never leave onClick off an actionable button.
- ROLE-BASED REDIRECT AFTER AUTH: the login page reads the role from the /api/auth/login response (const json = await res.json(); const role = json.data?.role) and router.push()es to THAT ROLE'S landing route that EXISTS in the Pages Plan — admin/super_admin/manager/owner → the admin dashboard route (e.g. /admin/dashboard), staff/operational roles (receptionist, cashier, housekeeping, accountant, inventory_manager, teacher, agent, etc.) → their portal/dashboard route, customer/user/guest/student/parent → the customer/user dashboard (e.g. /customer/dashboard or /dashboard). Do NOT send every role to the same page. After register, redirect the new user to their role's home the same way. If the app has only one kind of user, a single dashboard is fine.
- Avoid long multi-tab monster pages. If a page needs several modes, use a small tab list and render compact subcomponents per tab; do not inline hundreds of JSX lines inside TabsContent. If you cannot keep the JSX obviously balanced, use stacked Card sections instead of Tabs.
- POS/CASHIER PAGES: If the route is /pos or the page is a point-of-sale/cashier screen, fetch sellable inventory from /api/spare-parts, /api/parts, /api/products, or /api/inventory; never hardcode quick-search products. Checkout MUST POST the cart to /api/pos/sales, /api/sales, or /api/orders with method: "POST". No fake delay, no Math.random transaction number as the source of truth, and no simulated receipt success.
- POS/CASHIER STATE CONTRACT: The POS page MUST include const [isLoading, setIsLoading], const [error, setError], an empty inventory/search state, and checkout loading/success/error feedback. Render these states before and after the inventory grid so the page never appears frozen.
- Reference ONLY components that exist: the shadcn primitives above, components you import, or components you DEFINE in the same file. Never use a bare <StatusBadge/> or <Something/> you never created — use <Badge variant="…"> or define the helper.
- For icons use lucide-react (e.g. <FolderKanban className="h-5 w-5" />). NEVER <img src="/something.png"> for an icon — those files don't exist and render broken.

RUNTIME CRASH PREVENTION (the #1 way a page that RENDERS still errors WHEN USED is reading a field off undefined — guard EVERYTHING):
- Never assume the shape of fetched data. After unwrapping { success, data }: arrays → const rows = Array.isArray(payload) ? payload : []; objects → read nested fields with optional chaining and defaults: item?.category?.name ?? "—". A bare data.map / row.customer.name crashes when the value is undefined.
- SAFE FORMATTING: money is Number(x ?? 0).toFixed(2) (NEVER x.toFixed(2) — x may be undefined or a string); dates are x ? new Date(x).toLocaleDateString() : "—". Guard before .toFixed/.toLocaleDateString/.slice/.charAt/.length on possibly-undefined values.
- CONTROLLED INPUTS: every <Input>/<Textarea>/native <select> that has a value MUST also have onChange, and its state field starts as "" or a real default (NEVER undefined) — an undefined→string switch throws a React error and can crash the page.
- KEYS: every element rendered from .map MUST have a stable key, e.g. key={item._id ?? item.id ?? index}.
- OPTIONAL CALLBACKS/COMPONENTS: never call something that might be undefined — guard with onDone?.() and only render a component you imported or defined. A dynamic icon is const Icon = item.icon ?? FileIcon; then <Icon/>.
- LOADING FIRST: render the loading branch BEFORE touching fetched data (if (isLoading) return <Spinner/>), and the empty branch before mapping, so the first render (data still []/null) never reads undefined.

NEXT.JS 16 APP ROUTER RULES (this is the App Router in app/ — follow these EXACTLY, never legacy pages/ patterns):
- SERVER BY DEFAULT: every file is a Server Component unless its FIRST line is "use client". Add "use client" ONLY to a file that uses state/effects/refs, event handlers (onClick/onChange/onSubmit), browser APIs (window/localStorage), or the hooks useState/useEffect/useRouter/usePathname/useSearchParams. A Server Component may be async and await data directly, but must NEVER use those hooks or handlers.
- DATA FETCHING IN THIS APP: interactive pages that list/filter/mutate are "use client" and fetch("/api/...") in useEffect (the convention used throughout this app). Do NOT turn them into async Server Components. Pure static/marketing sections may be Server Components with inline content.
- MUTATIONS = ROUTE HANDLERS, NOT SERVER ACTIONS: perform every create/update/delete by fetch()-ing an app/api/**/route.ts handler with method POST/PUT/PATCH/DELETE. Do NOT use Server Actions ("use server", form action={fn}) anywhere — this app is built entirely on Route Handlers + client fetch, and mixing in Server Actions breaks that contract.
- ROUTE HANDLERS: named HTTP exports (export async function GET/POST/PUT/PATCH/DELETE) in app/api/**/route.ts, using NextRequest/NextResponse (or Response.json). They are not cached. Read query with new URL(request.url).searchParams; read dynamic ids from the awaited params argument.
- ASYNC DYNAMIC APIS (Next 16): params and searchParams are Promises. Page: export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; }. Route handler: async function GET(req, { params }: { params: Promise<{ id: string }> }) { const { id } = await params; }. cookies()/headers() from next/headers are async: const store = await cookies(). NEVER read params.id / searchParams.q / cookies() synchronously.
- METADATA: set the page/app title with export const metadata = { title: "...", description: "..." } (or export async function generateMetadata()) from a Server Component layout/page — NEVER from a "use client" file. Do not hand-write <head>/<title> tags in JSX.
- SPECIAL FILES (use where they add polish): loading.tsx (Suspense fallback for a segment), error.tsx (a "use client" boundary exporting default function Error({ error, reset })), and not-found.tsx with notFound() for missing records. A component using useSearchParams() MUST be inside <Suspense>.
- NAVIGATION & IMAGES: next/link for navigation (href prop, never "to"); useRouter().push("/path") from "next/navigation" for programmatic navigation. next/image needs width+height (or fill); for decorative imagery prefer CSS gradients / inline styled blocks over remote images (the image config is managed and unknown remote hosts throw at runtime).

SYNTAX & IMPORT MISTAKES — these break the build every time, NEVER make them:
1. "use client" FIRST LINE: any file that uses useState, useEffect, usePathname, useRouter, useSearchParams, or an onClick/onChange/onSubmit handler MUST have "use client"; as its very first line. A Navbar/Sidebar using usePathname is a client component.
2. IMPORTS use "from", never "=", never "/ @...", never comments inside imports: write import { Card } from "@/components/ui/card"; — NEVER import { Card } = "@/components/ui/card", NEVER import { Badge }/ @components/ui/badge", NEVER import React, { useState } = React, NEVER import { A } of_item, and NEVER = require(...).
2a. No directory/barrel UI imports: NEVER write from "@/components/ui" or from "@/components/ui/". Use exact primitive file paths only.
3. EXPORT EVERY component a page imports. In components/ui/card.tsx export EACH part: export const Card, export const CardHeader, export const CardContent, export const CardTitle, export const CardDescription. A bare const Card = (...) with no export → "Export Card doesn't exist". A page may only import names a file actually exports.
4. cva is named "cva": import { cva } from "class-variance-authority"; const x = cva("base", {...}). NEVER import { variant } and NEVER call variant(...). Types: import { type VariantProps } from "class-variance-authority".
5. next/font subsets are real: Inter({ subsets: ["latin"] }). NEVER subsets: ["variable"].
6. FUNCTIONS: a declaration is function Name(args) { ... } (no =>). An arrow is const Name = (args) => { ... }. NEVER mix them as function Name(args) => { ... }.
7. NO NAME COLLISIONS: if you import an icon from lucide-react (e.g. Plus, CalendarIcon, Search), do NOT also declare a local function/const with that same name. Pick one. Never define a component that renders itself (function Icon(){ return <Icon/> }) — that is infinite recursion.
8. JSX TAGS MATCH EXACTLY AND CLOSE: <Label>…</Label> (never </label>), <Card>…</Card>. Every opening <div> needs exactly one matching </div> — count them. Self-close void content (<Input … />). Never write a stray spread like {...123}.
9. Import each name from its ONE real source: components from "@/components/...", icons from "lucide-react", hooks from "react"/"next/navigation". Never import a UI component from lucide-react or an icon from your components.
10. BEFORE outputting a file, mentally run the TypeScript parser: no unmatched JSX tags, no doubled braces in imports, no object keys with dots like lesson.type, no repeated spreads like [......items], no raw comma-color fragments inside JSX props. If a section becomes too nested, simplify it rather than emitting invalid JSX.

11. DO NOT duplicate imports from the same module. If you need Card and CardContent, write ONE line: import { Card, CardContent } from "@/components/ui/card"; with a semicolon and no trailing comment.
12. Badge variant must be one of: "default", "secondary", "outline", "success", "warning", "destructive". NEVER use "info".
13. If you use useEffect/useMemo/useCallback/etc, include that hook in the React import. Example: import React, { useEffect, useState } from "react";
14. If an object stores an icon component, render it as JSX later: const Icon = item.icon; return <Icon className="..." />. Never render the component reference as plain text like {item.icon}.
15. Keep app/layout.tsx a server component. Do NOT put "use client", usePathname, useRouter, useState, or useEffect in app/layout.tsx. If layout needs route-aware admin/public chrome, create a client component under components/ (for example components/app-shell.tsx) and render that from app/layout.tsx.
16. Never simulate server data in a page. No await new Promise, no setTimeout fake loading, no "simulate" comments. Use fetch("/api/...") in useEffect, unwrap { success, data } responses, use Array.isArray guards for lists, and real error/empty states.
17. Parse fetch responses once: const json = await response.json(); const payload = json && typeof json === "object" && "data" in json ? json.data : json; then Array.isArray(payload). NEVER call response.json() twice in a ternary or condition.
18. Backend pages must never use hardcoded fallback business records/metrics to make the UI look populated. Do not write data.length ? data : [{...}], KPI fallback arrays, static chart rows, or footer metrics like "Total Sales: $128,400". If the API returns empty, render an empty state and make the API route seed MongoDB.
19. Form controls must be labeled and parseable: every Input, Textarea, and native select MUST have a stable id and a matching <Label htmlFor="same-id">. Search/filter bars and newsletter/contact forms count too. Do not use SelectTrigger/SelectContent in page files.
20. A visible create/edit/add form must be a real form: <form onSubmit={handleSubmit}> with a handleSubmit function that prevents default, validates state, calls fetch("/api/...", { method: "POST" or "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }), handles loading/error/success, and refreshes the list. Do not render inert forms.
21. Never write UI copy or comments with "demo", "sample data", "mock", "placeholder", or "in a real app". Use finished product wording and real empty states.

App type: ${appType.label}. ${appType.guidance}`;
}

function planBlock(opts: {
  hasBackend: boolean;
  plans: Record<string, string>;
  full?: boolean;
}): string {
  const { hasBackend, plans, full } = opts;
  return [
    plans.appspec &&
      `APP SPEC JSON (normalized input contract; do not build features outside this scope):\n${cap(plans.appspec, full ? 3600 : 2200)}`,
    plans.reference &&
      `REFERENCE (the quality bar — build to THIS depth, not a demo):\n${cap(plans.reference, full ? 2600 : 1600)}`,
    plans.coverage &&
      `SRS REQUIREMENT COVERAGE CONTRACT (REQ IDs and acceptance checks):\n${cap(plans.coverage, full ? 5200 : 2600)}`,
    plans.uidesign &&
      `UI DESIGN PLAN (App Shell & Navigation decision, shadcn/Radix usage — FOLLOW this, do not re-decide it):\n${cap(plans.uidesign, full ? 2400 : 1800)}`,
    plans.pages && `PAGES PLAN:\n${cap(plans.pages, full ? 3800 : 1800)}`,
    hasBackend && plans.datatypes && `DATA MODELS:\n${cap(plans.datatypes, 4200)}`,
    plans.components && `COMPONENT PLAN:\n${cap(plans.components, full ? 2600 : 1400)}`,
    hasBackend && plans.backend && `BACKEND / APIS:\n${cap(plans.backend, full ? 3200 : 1600)}`,
  ]
    .filter(Boolean)
    .join('\n\n');
}

function manifestBlock(manifest: string[]): string {
  return manifest.length
    ? `FILES THAT ALREADY EXIST — reuse them, do NOT recreate. Import each by its EXACT export names shown in "(exports: …)": a named export X → import { X } from the path; "default (X)" → import X from the path. Never guess a different name.\n${manifest
        .map((p) => '- ' + p)
        .join('\n')}`
    : 'Only the bare scaffold exists so far.';
}

function pageSpecificContract(page: DerivedPage): string {
  if (/\/pos\b/i.test(page.route)) {
    return `\nMANDATORY POS ROUTE CONTRACT:
- The page MUST fetch sellable inventory from fetch("/api/spare-parts") or another existing/planned inventory API inside useEffect. No hardcoded product/part arrays in JSX, useMemo, or constants.
- The page MUST submit checkout with fetch("/api/pos/sales", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(...) }).
- The page MUST render transaction/receipt data from the API response. Do not use Math.random for transaction ids except transient React keys.
- The page MUST declare isLoading/setIsLoading and error/setError, and render visible loading, error, empty search results, cart empty state, checkout loading, and checkout success/failure states.
- The output is invalid unless it contains both an inventory API fetch and a POST checkout fetch.\n`;
  }
  if (page.kind === 'list') {
    return `\nMANDATORY LIST ROUTE CONTRACT:
- Declare const [isLoading, setIsLoading] and const [error, setError]. Fetch records in useEffect, parse the response once, unwrap { success, data } into a payload, guard list data with Array.isArray(payload), and render explicit loading, error, and empty/no-data states.
- Render search and filter controls, plus pagination controls or a clear pagination/status footer with Next/Previous or Page labels.
- Every rendered record row/card MUST include row actions with literal labels or aria-labels containing View, Edit, and Delete (or Archive/Deactivate). These actions must be inside the row/card, not only in the header toolbar.
- Do not use hardcoded fallback records. If there are no API records, show the empty state.\n`;
  }
  if (page.kind === 'dashboard') {
    return `\nMANDATORY DASHBOARD STATE CONTRACT:
- Declare const [isLoading, setIsLoading] and const [error, setError] for fetched metrics/records.
- Render visible loading, error, and empty/no-data states before metric cards or recent-records tables.
- Recent-records tables/cards should include at least a View action where it makes domain sense.\n`;
  }
  return '';
}

/** Step 1 (backend only) — the data layer: db + every Mongoose model. */
export function buildFoundationMessages(opts: {
  appType: AppTypeDef;
  hasBackend: boolean;
  designBrief: string;
  plans: Record<string, string>;
  manifest: string[];
}): { system: string; user: string } {
  const { appType, hasBackend, designBrief, plans, manifest } = opts;
  const system = systemPrompt({ appType, hasBackend, designBrief });

  const user = `${planBlock({ hasBackend, plans, full: true })}

${manifestBlock(manifest)}

STEP: DATA LAYER. Build ONLY the data layer now (focus entirely on this — do NOT run out of room):
- lib/db.ts — You MUST output EXACTLY this code for lib/db.ts (do not change a single character):
<file path="lib/db.ts">
import mongoose from "mongoose";
import dns from "dns";
const MONGODB_URI = process.env.MONGODB_URI as string;
const PUBLIC_DNS_SERVERS = ["8.8.8.8", "1.1.1.1"];
type MongooseCache = {
  conn: typeof mongoose | null;
  promise: Promise<typeof mongoose> | null;
};
const globalForMongoose = globalThis as typeof globalThis & {
  _mongoose?: MongooseCache;
};
const cached = globalForMongoose._mongoose ?? { conn: null, promise: null };
globalForMongoose._mongoose = cached;
function configuredDnsServers(): string[] {
  const value = process.env.DNS_SERVERS?.trim();
  if (!value || value.toLowerCase() === "auto") return [];
  if (value.toLowerCase() === "off") return [];
  return value.split(",").map((s) => s.trim()).filter(Boolean);
}
async function connectOnce() {
  mongoose.set("strictPopulate", false);
  return mongoose.connect(MONGODB_URI, { bufferCommands: false });
}
function shouldRetryWithPublicDns(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  return /querySrv|ENOTFOUND|ETIMEOUT|ECONNREFUSED/i.test(msg);
}
export async function connectDB() {
  if (!MONGODB_URI) throw new Error("Please define MONGODB_URI");
  if (cached.conn) return cached.conn;
  if (!cached.promise) {
    cached.promise = (async () => {
      const explicitServers = configuredDnsServers();
      if (explicitServers.length) {
        try { dns.setServers(explicitServers); } catch {}
      }
      try {
        return await connectOnce();
      } catch (err) {
        if (explicitServers.length || !shouldRetryWithPublicDns(err)) throw err;
        try { dns.setServers(PUBLIC_DNS_SERVERS); } catch { throw err; }
        return connectOnce();
      }
    })();
  }
  cached.conn = await cached.promise;
  return cached.conn;
}
</file>
- lib/models/*.ts — a COMPLETE, correct Mongoose model for EVERY collection in the Data Models plan (ONE file per model, all of them).
Output ONLY these files. Do NOT build layout, navigation, components, or any page here — those come in later rounds.`;

  return { system, user };
}

/** Step 2 — the app shell: shared navigation + base UI + layout that wraps every page. */
export function buildShellMessages(opts: {
  appType: AppTypeDef;
  hasBackend: boolean;
  designBrief: string;
  plans: Record<string, string>;
  manifest: string[];
}): { system: string; user: string } {
  const { appType, hasBackend, designBrief, plans, manifest } = opts;
  const system = systemPrompt({ appType, hasBackend, designBrief });

  const user = `${planBlock({ hasBackend, plans })}

${manifestBlock(manifest)}

STEP: APP SHELL. Build the shared chrome that wraps EVERY page, FOLLOWING the plan's decision.

FIRST, read the "App Shell & Navigation" decision in the UI DESIGN PLAN above. Build EXACTLY the navigation the plan calls for — do not invent chrome the plan did not ask for, and do not omit chrome the plan requires:
- If the plan chose a **Top navbar** or **Sidebar**: build that shared navigation component under components/ (named Navbar or Sidebar to match the plan). It MUST show the app/brand name, link to every in-nav route the plan lists with active-state highlighting (usePathname + cn), be responsive (mobile toggle for a navbar), and use lucide-react icons.
- If the plan chose **Both**: build the public top navbar now; a dashboard sidebar can be its own component too.
- If the plan explicitly chose **None** (a single-screen / kiosk / focused tool): do NOT fabricate a navbar. Build a clean layout without global navigation.
- If auth routes exist, the public navbar MUST include Login and Register links. Authenticated/portal navigation MUST include Dashboard/Profile and a Logout action. Do not replace these with a generic user icon unless the icon opens a real menu containing those links.
- If public and internal routes need different chrome, create a client component (for example components/AppShell.tsx) using usePathname() and render it from app/layout.tsx. Never use process.env.NEXT_REQUEST_PATH to detect the current route.

Your deliverables this round (a round that ships pages instead of the shell is a FAILURE):
0. app/globals.css — your OWN design system: keep the @import "tailwindcss"; line FIRST, then a @theme { … } block defining the app's color / font / radius tokens (a deliberate primary, accent, background, surface, foreground, border, plus fonts and radius), and base body + heading styles. This is the brand identity every page builds on — make it distinctive, not generic gray/blue.
1. The shared navigation component(s) the plan requires (skip ONLY if the plan said None).
2. app/layout.tsx — REPLACE the default scaffold layout. It MUST import "./globals.css", set <title> to the app name, render {children} as the main content area, and — unless the plan chose None — import and render the shared navigation so it appears on every page. (The scaffold layout has no navigation; you MUST replace it to realise the plan.)
3. If auth/RBAC/roles are planned, credentials.txt — a simple root-level text file listing the seeded role accounts and passwords.
4. Do NOT output components/ui/* files. They are already scaffolded and protected. Import them exactly as listed in the system prompt.

Output ONLY the shell files. Do NOT build individual pages here. app/layout.tsx MUST be in your output.`;

  return { system, user };
}

/** One step per page — distinct layout for the page's kind. */
/** Folder name under components/ for a page's colocated section files. */
function pageSlug(route: string): string {
  const clean = route
    .replace(/^\/+|\/+$/g, '')
    .replace(/\[[^\]]+\]/g, 'detail');
  return clean ? clean.replace(/\//g, '-').toLowerCase() : 'home';
}

/** Concrete example section-component names to seed the decomposition. */
function sectionHint(page: DerivedPage): string {
  const byKind: Record<string, string> = {
    landing: 'hero, featured, feature-grid, testimonials, cta',
    dashboard: 'stats-cards, recent-activity, chart-panel, quick-actions',
    list: 'toolbar, filters, data-table, add-dialog',
    detail: 'detail-header, details-panel, related-list',
    form: 'form-card, form-fields, form-actions',
    auth: 'auth-card, auth-form',
    settings: 'settings-tabs, profile-section, preferences-section',
    profile: 'profile-header, profile-details, activity-list',
    content: 'page-header, content-body, aside-panel',
    generic: 'page-header, main-panel, side-panel',
  };
  return byKind[page.kind] || 'page-header, main-section, secondary-section';
}

export function buildPageMessages(opts: {
  appType: AppTypeDef;
  hasBackend: boolean;
  designBrief: string;
  plans: Record<string, string>;
  manifest: string[];
  page: DerivedPage;
  pageSpec?: string;
}): { system: string; user: string } {
  const { appType, hasBackend, designBrief, plans, manifest, page, pageSpec } =
    opts;
  const system = systemPrompt({ appType, hasBackend, designBrief });
  const slug = pageSlug(page.route);

  const specBlock = pageSpec
    ? `THIS PAGE'S DETAILED SPEC — build EXACTLY these sections / functions / design:\n${pageSpec}\n\n`
    : plans.pagewise
      ? `PAGE-WISE DETAIL (find + follow the entry for ${page.route}):\n${cap(plans.pagewise, 1800)}\n\n`
      : '';

  const user = `${planBlock({ hasBackend, plans })}

${specBlock}${manifestBlock(manifest)}

STEP: BUILD ONE PAGE — ${page.route}  →  file: ${page.filePath}
Page name: ${page.title}
Purpose: ${page.purpose || '(see plan)'}
Access: ${page.access || '(any)'}

SRS COVERAGE DUTY: If the Requirement Coverage Contract maps REQ IDs or acceptance checks to this route/page, implement them in this page and any API endpoints it calls. A page that only looks good but drops required actions/data is a failure.

LAYOUT FOR THIS PAGE: ${KIND_LAYOUT[page.kind]}
${pageSpecificContract(page)}

QUALITY STATE DUTY: If this page fetches, lists, filters, displays dashboard data, or submits a form, it MUST include explicit isLoading/setIsLoading, error/setError, and empty/no-data UI states plus success/failure feedback. Do not rely on static arrays to make the page look populated in backend apps.

QUALITY GATE CONTRACT:
- Page output is invalid if it imports or renders SelectTrigger/SelectContent/SelectItem. Use native <select> with Label instead.
- Page output is invalid if it imports from "@/components/ui" or "@/components/ui/"; use exact file paths such as "@/components/ui/card".
- Page output is invalid if it imports "@/components/ui/select", "@/lib/db", "@/lib/models", or "mongoose". Pages must fetch API routes instead.
- Page output is invalid if it imports from "@/app/api/..." or any app/api/**/route.ts file. Use fetch("/api/...") instead.
- Page output is invalid if any Input/Textarea/select lacks a matching Label htmlFor/id pair.
- Page output is invalid if it shows an Add/Create/Edit form without <form onSubmit={handleSubmit}> and a fetch POST/PATCH submit handler.
- Backend page output is invalid if it contains setTimeout, await new Promise, fake delay code, or simulated data loading.
- List/index/catalog/management pages are invalid without literal View, Edit, and Delete/Archive/Deactivate row actions on each rendered record.
- Fetched/list/dashboard pages are invalid without code identifiers containing loading/isLoading, error/setError, and empty/no-data UI.
- POS pages are invalid without fetch("/api/spare-parts" | "/api/parts" | "/api/products" | "/api/inventory"), a POST checkout fetch, isLoading, error, empty inventory/search state, and checkout success/failure feedback.

YOUR OUTPUT — emit each file as its OWN <file path="..."> block, in THIS order:
1. ${page.filePath} — REQUIRED, output this FIRST and complete. Make it a THIN page (under ~80 lines, layout + composition only, no big JSX) that imports 3-6 section components from "@/components/${slug}/..." and stacks them, e.g.:
   import { Hero } from "@/components/${slug}/hero";
   import { FeatureGrid } from "@/components/${slug}/feature-grid";
   export default function Page() { return (<div className="..."> <Hero /> <FeatureGrid /> ... </div>); }
2. THEN each section component under components/${slug}/ that the page imports — one <file path="components/${slug}/<name>.tsx"> per section (lowercase-kebab; example sections for this page: ${sectionHint(page)}). Each EXPORTS its component (export function Hero() {…}), is ~40-160 lines, is rich/polished with real specific copy (NOT a stub), and holds this page's actual logic: fetch, useState, isLoading/error/empty states, forms with onSubmit + fetch POST/PATCH, tables with View/Edit/Delete row actions, Dialog modals. Interactive section files start with "use client".
${
    hasBackend
      ? '3. THEN, only if missing from the manifest, the app/api/.../route.ts endpoint(s) these sections call (reuse existing models, apiSuccess/apiError envelope).\n'
      : ''
  }HARD RULES: ${page.filePath} MUST be in your output — a round without it is a FAILURE. EVERY section component MUST live under the folder "components/${slug}/" and be imported from EXACTLY "@/components/${slug}/<name>". Correct: import { BookTable } from "@/components/${slug}/book-table"; and a matching <file path="components/${slug}/book-table.tsx">. WRONG (breaks the whole app): import { BookTable } from "@/components/book-table" (dropped the ${slug} folder) OR importing BookTable without also writing components/${slug}/book-table.tsx. The <file path> you write and the "@/components/${slug}/..." you import MUST be the identical path. Write EVERY component you import in THIS response; NEVER import one you do not create here (a missing or mis-pathed import 500s the WHOLE app). NEVER put the whole page in one file and NEVER exceed ~200 lines in any file — split into more components/${slug}/ sections instead. Give THIS page its OWN distinct layout per the LAYOUT note (do NOT reuse another page's structure). Reuse the shared navigation, existing models, and existing components by their EXACT export names in the manifest.`;

  return { system, user };
}

/** Final step — fill remaining shared components + API routes from the plans. */
/** Batched page step for large apps, with the route fallback handled by the caller. */
export function buildPageBatchMessages(opts: {
  appType: AppTypeDef;
  hasBackend: boolean;
  designBrief: string;
  plans: Record<string, string>;
  manifest: string[];
  pages: { page: DerivedPage; pageSpec?: string }[];
}): { system: string; user: string } {
  const { appType, hasBackend, designBrief, plans, manifest, pages } = opts;
  const system = systemPrompt({ appType, hasBackend, designBrief });
  const pageList = pages
    .map(({ page, pageSpec }, index) => {
      const detail = pageSpec
        ? `Detailed spec:\n${cap(pageSpec, 1400)}`
        : `Purpose: ${page.purpose || '(see pages plan)'}`;
      return `${index + 1}. Route ${page.route} -> ${page.filePath}
Page name: ${page.title}
Access: ${page.access || '(any)'}
Layout: ${KIND_LAYOUT[page.kind]}
${pageSpecificContract(page)}
${detail}`;
    })
    .join('\n\n');
  const expectedFiles = pages.map(({ page }) => page.filePath).join('\n- ');

  const user = `${planBlock({ hasBackend, plans })}

${manifestBlock(manifest)}

STEP: BUILD A SMALL BATCH OF PAGES.

You MUST output exactly these page files, complete and in full:
- ${expectedFiles}

Pages to build:
${pageList}

Rules for this batch:
- Output one <file path="..."> block per page file listed above. Do not skip any listed page.
- Build only these page files and tiny page-local helper components when absolutely necessary.
- Do not output app/api routes in this batch; the API batch and Finish & Wire Up steps create missing APIs. For backend apps, pages must fetch from existing or planned /api routes and must not define mock/sample/demo/static record arrays as their source of truth. For static/no-backend apps, embedded domain content is allowed.
- Never use SelectTrigger/SelectContent/SelectItem in page files. Use <Label htmlFor="..."> plus native <select id="..."> for filters/dropdowns.
- Never import from "@/components/ui" or "@/components/ui/"; import each primitive from its exact file path.
- Never import "@/components/ui/select", "@/lib/db", "@/lib/models", connectDB, or mongoose in a page/component file. Use fetch("/api/...") only.
- Never import app/api route files into a page/component. Do not import GET/POST handlers. Use fetch("/api/...") only.
- Every Input/Textarea/select in search bars, filters, forms, and CTAs must have a matching Label htmlFor/id pair.
- Every Add/Create/Edit form or Dialog form must include <form onSubmit={handleSubmit}> and handleSubmit must call fetch with method POST or PATCH plus JSON headers/body.
- Never use setTimeout, await new Promise, fake delay code, or simulated data loading in backend pages.
- Each page must have its own distinct layout, real data tables/cards/forms/search/filter states, and no placeholder sections.
- Every fetched/list/dashboard/form page must explicitly implement isLoading/setIsLoading, error/setError, empty/no-data, and success/failure feedback states in code. These words should appear naturally in variable names or UI copy so the quality audit can verify them.
- Every list/index/catalog/management page must render per-record row/card actions with literal visible labels or aria-labels containing View, Edit, and Delete (or Archive/Deactivate). Header-only buttons do not satisfy this; actions must be repeated for each row/card.
- Every POS/cashier page must fetch inventory from a real /api inventory route, POST checkout to a real /api sales/order route, and render loading/error/empty plus checkout success/failure states.
- The shared app navigation is already rendered by app/layout.tsx. Do not render Navbar/Sidebar inside these pages.
- Keep each page correct and parseable; if a page becomes too nested, split into local subcomponents inside the same file.

The output is invalid unless every expected page file appears exactly once.`;

  return { system, user };
}

/** Batched API route step: forces backend endpoints to materialize as route handlers. */
export function buildApiBatchMessages(opts: {
  appType: AppTypeDef;
  hasBackend: boolean;
  designBrief: string;
  plans: Record<string, string>;
  manifest: string[];
  apiFiles: string[];
}): { system: string; user: string } {
  const { appType, hasBackend, designBrief, plans, manifest, apiFiles } = opts;
  const system = systemPrompt({ appType, hasBackend, designBrief });
  const expectedFiles = apiFiles.join('\n- ');

  const user = `${planBlock({ hasBackend, plans, full: true })}

${manifestBlock(manifest)}

STEP: BUILD A SMALL BATCH OF BACKEND API ROUTE HANDLERS.

You MUST output exactly these route files, complete and in full:
- ${expectedFiles}

Rules for this API batch:
- Output one <file path="..."> block per API route file listed above. Do not skip any listed file.
- Use Next.js App Router route handlers with named HTTP exports: GET, POST, PUT, PATCH, DELETE as appropriate for the Backend Plan endpoints mapped to each file.
- Import connectDB from "@/lib/db" and existing Mongoose models from "@/lib/models" (the barrel) whenever possible; use the exact model exports visible in the manifest. Never invent snake_case/plural model paths like "@/lib/models/delivery_notes". Direct model-file imports are allowed only when the exact file path exists in the manifest.
- Return Response.json(...) with correct HTTP status codes and clear validation errors.
- For collection routes, implement list/create. For [id] routes, read params.id and implement read/update/delete/action behavior as the backend plan requires.
- Use only public Request/NextRequest APIs. Query values come from new URL(request.url).searchParams. Dynamic ids come only from the params argument. Never write request._url, request._params, nextUrl.params, error_format(), _id(), _description(), or invented types such as or_string.
- If an endpoint needs a model that is not in the manifest, output the missing lib/models/<PascalName>.ts file with a named export and add/export it from lib/models/index.ts in the same response before importing it. Do not import a named model from a file that does not export it.
- Include defensive try/catch, await connectDB(), and realistic query/body handling. Never import mongoose directly in a route handler and never create a local connectDB helper; use the canonical helper only.
- If a GET/list route would otherwise return an empty array, seed a small realistic set of records into MongoDB first, then return the seeded database records. Seed users/roles with the credentials convention when auth/RBAC is planned.
- If auth/RBAC/roles are planned and credentials.txt is not in the manifest, output credentials.txt with one seeded email/password per role.
- Do not leave TODOs, placeholder messages, mock/demo comments, or prose-only output.
- Do not output pages, layout, globals, package.json, or scaffold/config files in this batch.

The output is invalid unless every expected API route file appears exactly once.`;

  return { system, user };
}

export function buildFinalMessages(opts: {
  appType: AppTypeDef;
  hasBackend: boolean;
  designBrief: string;
  plans: Record<string, string>;
  manifest: string[];
}): { system: string; user: string } {
  const { appType, hasBackend, designBrief, plans, manifest } = opts;
  const system = systemPrompt({ appType, hasBackend, designBrief });

  const user = `${planBlock({ hasBackend, plans, full: true })}

${manifestBlock(manifest)}

STEP: FINISH & WIRE UP. Create anything important that is still MISSING versus the plans:
- reusable components from the Component Plan that no page created yet,${
    hasBackend
      ? '\n- API route handlers from the Backend Plan that are not in the manifest yet,'
      : ''
  }
- make sure pages render real data (replace any leftover hardcoded sample data with fetches/queries).
- for backend apps, move any remaining mock/sample/demo arrays out of client pages and into MongoDB seed logic inside API routes.
- if auth/RBAC/roles are planned, ensure credentials.txt exists and login/register/profile/dashboard links are visible in the shared navigation.
- compare the current manifest against the Requirement Coverage Contract and add any missing critical/high REQ behavior, page, API route, validation, search/filter/sort, CRUD action, role check, or report.
Do NOT recreate files that already exist. Output only the missing files.`;

  return { system, user };
}
