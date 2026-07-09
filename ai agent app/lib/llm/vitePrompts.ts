/**
 * Prompts for the "Google AI Studio" format: Vite + React 19 SPA + a single
 * Express `server.ts` + `server/models.ts` + `src/types.ts` + `src/App.tsx` +
 * a few module components. Far fewer files than the Next.js path → far fewer of
 * the cross-file import / route-scatter / server-client-boundary bugs.
 *
 * Generation is staged so a 12B model never has to emit one giant file:
 *   1. src/types.ts + server/models.ts   (data layer)
 *   2. server.ts                          (all /api routes)
 *   3. src/App.tsx                        (state + tab/role routing shell)
 *   4. src/components/<Module>.tsx        (one focused module per call)
 */

import type { ChatMessage } from './ollama';

const cap = (s: string, n: number) => (s.length > n ? s.slice(0, n) + '\n…(truncated)' : s);

function planContext(plans: Record<string, string>): string {
  const parts: string[] = [];
  if (plans.datatypes) parts.push(`DATA MODEL (entities + fields — the source of truth for types & models):\n${cap(plans.datatypes, 4000)}`);
  if (plans.backend) parts.push(`BACKEND / API PLAN:\n${cap(plans.backend, 2500)}`);
  if (plans.master) parts.push(`APP OVERVIEW:\n${cap(plans.master, 1500)}`);
  return parts.join('\n\n');
}

function systemPrompt(appName: string): string {
  return `You are AI Web Builder generating a complete web app in the VITE + REACT SPA format (NOT Next.js).

STACK & STRUCTURE (fixed — the scaffold already created the config, index.html, src/main.tsx, src/index.css, server/db.ts):
- Frontend: React 19 SPA with Vite. Tailwind CSS v4 (utility classes only; theme tokens in src/index.css). Icons from "lucide-react". Charts from "recharts".
- Backend: ONE Express file "server.ts" holding EVERY /api route. Mongoose models live in "server/models.ts".
- ONE process serves both: the client calls fetch("/api/...") on the SAME origin.
- Routing is CLIENT-SIDE VIA STATE in src/App.tsx (an "activeTab" string + role-based switching) — there is NO react-router, NO file-based routes, NO URLs per page. Modules are React components App.tsx renders based on activeTab.

THE ONLY FILES YOU WRITE (everything else is scaffold-owned — never emit index.html, vite.config.ts, tsconfig.json, package.json, src/main.tsx, src/index.css, or server/db.ts):
- src/types.ts        — every TypeScript interface (shared by client + server thinking)
- server/models.ts    — connectDB re-export + every Mongoose model
- server.ts           — Express app + every /api route + the serve/listen block
- src/App.tsx         — top-level state, data fetching, tab + role routing, composes the module components
- src/components/*.tsx — module components (Sidebar, PublicWebsite, AuthPages, one per domain area e.g. VehiclesModule, AdminDashboard, PartsPOSModule …)

HARD RULES (these are what keep it bug-free):
- Output ONLY <file path="…">…full file…</file> blocks. No prose, no markdown fences.
- TypeScript everywhere. Import types from "@/src/types" or a relative path. Import models in server.ts from "./server/models.js" (note the .js extension — tsx resolves it to the .ts file). In server/models.ts import connectDB from "./db.js".
- Mongoose models: ONE "new Schema({...}, { timestamps: true })" per model, exported as "export const X = mongoose.models.X || mongoose.model('X', schema)". Foreign keys: field: { type: mongoose.Schema.Types.ObjectId, ref: "Other" }. NEVER "new mongoose.Types.ObjectId()" as a schema type. NEVER write a duplicate/"corrected" schema.
- Passwords: hash with bcryptjs (import bcrypt from "bcryptjs"; bcrypt.hashSync / bcrypt.compareSync). NEVER store plain text.
- Every API route is wrapped in try/catch and returns res.json(...) on success or res.status(code).json({ error: "…" }) on failure. Seed realistic data into a collection when it is empty, then return it (never fake arrays in the client).
- Client components fetch on mount with useEffect, keep useState for data + loading + error, and GUARD everything: const rows = Array.isArray(data) ? data : []; read nested fields with optional chaining + defaults (item?.x ?? "—"); money is Number(v ?? 0).toFixed(2). Controlled inputs always have value + onChange with non-undefined initial state.
- App.tsx does ROLE-BASED ROUTING after login: switch on user.role to set the initial activeTab (admins → an admin dashboard tab, staff → their module, customers → a customer tab). Every sidebar/nav item and button sets activeTab or performs a real fetch — NO dead buttons.
- Reference only components/exports that exist. Keep each file focused and correct over long.

App: ${appName}.`;
}

/** Stage 1 — src/types.ts + server/models.ts from the data model. */
export function buildViteDataLayerMessages(opts: {
  appName: string;
  plans: Record<string, string>;
}): ChatMessage[] {
  return [
    { role: 'system', content: systemPrompt(opts.appName) },
    {
      role: 'user',
      content: `${planContext(opts.plans)}

STEP 1 — DATA LAYER. Output exactly TWO files:
1. <file path="src/types.ts"> — a TypeScript interface for EVERY entity in the data model (include _id?: string; and every field, using precise union types for enums). Also a shared type for the API where useful.
2. <file path="server/models.ts"> — import connectDB from "./db.js" and RE-EXPORT it (export { connectDB }); then ONE Mongoose model per entity (named export, mongoose.models.X || mongoose.model(...), timestamps: true, ObjectId refs for foreign keys). Cover EVERY entity in the data model.
Output both files in full, nothing else.`,
    },
  ];
}

/** Stage 2 — server.ts with all API routes. */
export function buildViteServerMessages(opts: {
  appName: string;
  plans: Record<string, string>;
  types: string;
  modelNames: string[];
}): ChatMessage[] {
  return [
    { role: 'system', content: systemPrompt(opts.appName) },
    {
      role: 'user',
      content: `${planContext(opts.plans)}

TYPES (src/types.ts) already generated:
${cap(opts.types, 2500)}

Models available in server/models.ts (import what you need): connectDB, ${opts.modelNames.join(', ')}.

STEP 2 — BACKEND. Output ONE file <file path="server.ts"> containing:
- Imports: express, path, { createServer as createViteServer } from "vite", and { connectDB, <models> } from "./server/models.js".
- const app = express(); const PORT = Number(process.env.PORT) || 3000; app.use(express.json());
- A "await connectDB()" middleware: app.use(async (req, res, next) => { try { await connectDB(); next(); } catch (e) { res.status(500).json({ error: "DB connection failed" }); } });
- EVERY /api route from the API plan: auth (POST /api/auth/register with bcrypt hash + POST /api/auth/login with bcrypt compare, returning the user WITHOUT the password), plus full CRUD (GET list, POST create, PUT/PATCH update, DELETE) for each entity the app manages. Each route: try/catch, seed the collection with a few realistic records when empty on GET, return JSON.
- FINALLY this EXACT serve block at the end:
  async function startApp() {
    if (process.env.NODE_ENV !== "production") {
      const vite = await createViteServer({ server: { middlewareMode: true }, appType: "spa" });
      app.use(vite.middlewares);
    } else {
      const distPath = path.join(process.cwd(), "dist");
      app.use(express.static(distPath));
      app.get("*", (_req, res) => res.sendFile(path.join(distPath, "index.html")));
    }
    app.listen(PORT, "0.0.0.0", () => console.log("Server running on http://localhost:" + PORT));
  }
  startApp();
Output the whole server.ts in full, nothing else.`,
    },
  ];
}

/** Stage 3 — src/App.tsx shell (state + routing). */
export function buildViteAppShellMessages(opts: {
  appName: string;
  plans: Record<string, string>;
  moduleFiles: string[]; // e.g. ["Sidebar", "PublicWebsite", "AdminDashboard"]
}): ChatMessage[] {
  return [
    { role: 'system', content: systemPrompt(opts.appName) },
    {
      role: 'user',
      content: `${planContext(opts.plans)}

STEP 3 — APP SHELL. Output ONE file <file path="src/App.tsx"> that:
- Holds top-level state: currentUser (User | null), activeTab (string), and any shared lists.
- On mount, if there is a public website, show it; a login/register modal or auth view sets currentUser.
- ROLE-BASED ROUTING: after a successful login, switch on user.role to choose the initial activeTab (admins/managers → an admin dashboard tab, operational staff → their module, customer → a customer tab). Provide a logout that clears currentUser.
- Renders a Sidebar/nav (for logged-in users) whose items set activeTab, and renders the matching module component for the current activeTab. Public visitors see the public website + an auth entry.
- Imports and composes the module components you will create next: ${opts.moduleFiles.map((m) => `./components/${m}`).join(', ')}. Import each as a default import.
- Every nav item and button sets activeTab or calls a real handler — NO dead buttons.
Keep it a clean shell (~120-220 lines) — the heavy UI lives in the module components. Output the whole file.`,
    },
  ];
}

/** Stage 4 — one module component. */
export function buildViteModuleMessages(opts: {
  appName: string;
  plans: Record<string, string>;
  moduleName: string; // e.g. "VehiclesModule"
  purpose: string;
  types: string;
}): ChatMessage[] {
  return [
    { role: 'system', content: systemPrompt(opts.appName) },
    {
      role: 'user',
      content: `${planContext(opts.plans)}

TYPES available (import from "@/src/types"):
${cap(opts.types, 2000)}

STEP 4 — MODULE COMPONENT. Output ONE file <file path="src/components/${opts.moduleName}.tsx">:
- A default-exported React component for: ${opts.purpose}
- It owns its state (useState) for data + loading + error + any form/modal fields, fetches from the relevant /api routes in useEffect, and renders a polished, real UI (tables, cards, filters, a create/edit modal via useState toggle, action buttons that actually fetch). Use lucide-react icons and Tailwind v4 classes.
- GUARD all data: Array.isArray before .map, optional chaining + defaults on fields, Number(v ?? 0).toFixed(2) for money, safe dates. Controlled inputs have value + onChange + non-undefined initial state. Every button does something real.
- Props: accept whatever App.tsx passes (e.g. currentUser). Keep it ~120-300 focused lines.
Output the whole file.`,
    },
  ];
}
