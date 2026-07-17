"""
agents/scaffold.py — Deterministic Next.js + MongoDB file generators.

Everything in here is produced as a fixed Python string, so it is *always* valid.
These are exactly the files a 12B model gets wrong most often — the Mongo
connection singleton, the Mongoose overwrite guard, config files, CRUD route
handlers — so we never let the model write them. The LLM's job is reduced to the
frontend pages/components, given a fixed, documented API contract.

Public entry points
    scaffold_files(spec)   -> {relpath: content} for the whole deterministic base
    model_file(model)      -> a single Mongoose model source
    crud_routes(model)     -> {relpath: content} for one resource's REST routes
    api_contract(spec)     -> human-readable contract string for the frontend prompt
    route_name(name)       -> URL segment for a model (e.g. "Task" -> "tasks")
"""
import hashlib
import json
import re
import secrets

# Pinned stack — Next 16 App Router + React 19. One version everywhere (prompts/rules/package) so the
# LLM never mixes Next 14/15/16 route idioms (async `params`, middleware/proxy naming, config keys).
VERSIONS = {
    "next": "16.2.10",
    "react": "19.2.7",
    "react-dom": "19.2.7",
    "mongoose": "8.24.1",
    "mongodb-memory-server": "9.4.0",
    "framer-motion": "12.42.2",
    "react-icons": "5.7.0",
    "zod": "3.23.8",
    # Material UI (v7 — React 19 compatible) is the component library the generated PAGES/SECTIONS use.
    # gemma writes MUI far more reliably than shadcn (huge training presence, single-package imports),
    # so all LLM-authored UI imports `@mui/material` + `@mui/icons-material`. Emotion is MUI's styling
    # engine; @mui/material-nextjs supplies the App Router SSR cache provider.
    "@mui/material": "^7.1.0",
    "@mui/icons-material": "^7.1.0",
    "@mui/material-nextjs": "^7.1.0",
    "@emotion/react": "^11.13.5",
    "@emotion/styled": "^11.13.5",
    "@emotion/cache": "^11.13.5",
    # shadcn primitives remain installed ONLY for the fixed, deterministic auth/dashboard stack in
    # core.py/scaffold.py (login, sidebar, admin) — the model never imports them.
    "@radix-ui/react-slot": "1.3.0",
    "class-variance-authority": "0.7.1",
    "clsx": "2.1.1",
    "tailwind-merge": "3.6.0",
    "lucide-react": "1.24.0",
    "tailwindcss": "3.4.17",
    "postcss": "8.5.18",
    "autoprefixer": "10.4.21",
    # TypeScript toolchain — generated components are .tsx, so Next needs these to
    # compile them. Backbone (lib/models/routes) stays .js and rides along via allowJs.
    "typescript": "5.9.3",
    "@types/react": "19.2.17",
    "@types/react-dom": "19.2.3",
    "@types/node": "24.10.0",
    "eslint": "9.39.5",
    "eslint-config-next": "16.2.10",
    # Auth (multipage-app mode only): tiny, deterministic. bcryptjs = pure-JS
    # password hashing (Node route handlers); jose = JWT sign/verify (edge-safe,
    # so middleware can verify sessions without bcrypt).
    "bcryptjs": "2.4.3",
    "jose": "5.6.3",
    "@types/bcryptjs": "2.4.6",
}


# ── naming helpers ────────────────────────────────────────────────────────────

def pascal(name: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", str(name))
    return "".join(p[:1].upper() + p[1:] for p in parts if p) or "Item"


def route_name(name: str) -> str:
    """Lowercase plural URL segment for a model name. Task -> tasks, Category -> categories."""
    n = pascal(name)
    low = re.sub(r"(?<!^)(?=[A-Z])", "-", n).lower()  # split camelCase → kebab
    low = low.replace("-", "")
    if low.endswith("y"):
        return low[:-1] + "ies"
    if low.endswith(("s", "x", "z", "ch", "sh")):
        return low + "es"
    return low + "s"


# ── field / model rendering ───────────────────────────────────────────────────

_MONGOOSE_TYPES = {
    "string": "String", "text": "String", "email": "String", "url": "String",
    "number": "Number", "int": "Number", "integer": "Number", "float": "Number",
    "boolean": "Boolean", "bool": "Boolean",
    "date": "Date", "datetime": "Date",
    "objectid": "mongoose.Schema.Types.ObjectId", "ref": "mongoose.Schema.Types.ObjectId",
    "mixed": "mongoose.Schema.Types.Mixed", "object": "mongoose.Schema.Types.Mixed",
    "array": "Array",
}


def _js_default(value, mtype: str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    s = str(value)
    if mtype == "Number":
        return s if re.fullmatch(r"-?\d+(\.\d+)?", s) else "0"
    if mtype == "Boolean":
        return "true" if s.lower() in ("true", "1", "yes") else "false"
    return json.dumps(s)  # quoted string


def _field_line(field: dict) -> str:
    """Render one schema field, e.g.  title: { type: String, required: true },"""
    fname = re.sub(r"[^A-Za-z0-9_]", "", str(field.get("name", ""))) or "field"
    raw_type = str(field.get("type", "String")).strip()

    # Array shorthand: "[String]" or type "array" with items
    if raw_type.startswith("[") and raw_type.endswith("]"):
        inner = _MONGOOSE_TYPES.get(raw_type[1:-1].lower(), "String")
        return f"  {fname}: [{{ type: {inner} }}],"

    mtype = _MONGOOSE_TYPES.get(raw_type.lower(), "String")

    if mtype == "Array":
        item = _MONGOOSE_TYPES.get(str(field.get("items", "String")).lower(), "String")
        return f"  {fname}: [{{ type: {item} }}],"

    opts = [f"type: {mtype}"]
    ref = field.get("ref")
    if mtype.endswith("ObjectId") and ref:
        opts.append(f"ref: '{pascal(ref)}'")
    if field.get("required"):
        opts.append("required: true")
    if field.get("unique"):
        opts.append("unique: true")
        # A unique index on an OPTIONAL field must be sparse, or a second document
        # that omits it collides on `null` (E11000 duplicate key on null).
        if not field.get("required"):
            opts.append("sparse: true")
    if "default" in field and field["default"] is not None:
        opts.append(f"default: {_js_default(field['default'], mtype)}")
    if isinstance(field.get("enum"), list) and field["enum"]:
        opts.append("enum: " + json.dumps(field["enum"]))
    return f"  {fname}: {{ {', '.join(opts)} }},"


def model_file(model: dict) -> str:
    name = pascal(model.get("name", "Item"))
    fields = model.get("fields") or [{"name": "name", "type": "String", "required": True}]
    lines = [_field_line(f) for f in fields]
    # Owned records carry an owner ref (the session userId) for ownership scoping.
    if model.get("ownedBy") == "User":
        lines.append("  owner: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },")
    return (
        "import mongoose from 'mongoose'\n\n"
        f"const {name}Schema = new mongoose.Schema({{\n"
        + "\n".join(lines)
        + "\n}, { timestamps: true })\n\n"
        # The guard prevents Next.js dev hot-reload OverwriteModelError.
        f"export default mongoose.models.{name} || mongoose.model('{name}', {name}Schema)\n"
    )


def validator_file(model: dict) -> str:
    """Generate a strict Zod payload validator from the normalized model."""
    name = pascal(model.get("name", "Item"))
    entries = []
    for field in model.get("fields") or []:
        fname = re.sub(r"[^A-Za-z0-9_]", "", str(field.get("name", "")))
        if not fname or fname in {"_id", "owner", "createdAt", "updatedAt"}:
            continue
        ftype = str(field.get("type", "String"))
        if ftype.startswith("[") or ftype == "Array":
            expr = "z.array(z.any())"
        elif ftype == "Number":
            expr = "z.number().finite()"
        elif ftype == "Boolean":
            expr = "z.boolean()"
        elif ftype == "Date":
            expr = "z.coerce.date()"
        elif ftype == "ObjectId":
            expr = "z.string().regex(/^[a-fA-F0-9]{24}$/, 'Invalid ObjectId')"
        else:
            expr = "z.string()"
        if field.get("enum"):
            vals = json.dumps([str(x) for x in field.get("enum") or []])
            expr = f"z.string().refine((v) => {vals}.includes(v), 'Invalid enum value')"
        if not field.get("required"):
            expr += ".optional()"
        entries.append(f"    {fname}: {expr},")
    body = "\n".join(entries) or "    _any: z.any().optional(),"
    return (
        "import { z } from 'zod'\n\n"
        f"const {name}Payload = z.object({{\n{body}\n  }}).strict()\n\n"
        "export function validatePayload(name: string, body: unknown, partial = false) {\n"
        f"  const schema = name === {json.dumps(name)} ? {name}Payload : null\n"
        "  if (!schema) return { ok: false as const, error: 'Unknown resource' }\n"
        "  const result = partial ? schema.partial().safeParse(body) : schema.safeParse(body)\n"
        "  if (!result.success) return { ok: false as const, error: result.error.issues.map((i) => i.message).join('; ') }\n"
        "  return { ok: true as const, data: result.data }\n"
        "}\n"
    )


def _inject_validation(files: dict, name: str) -> dict:
    """Attach Zod validation to every generated mutation route."""
    out = {}
    for rel, content in files.items():
        if "/api/" not in rel or "const body = await req.json()" not in content:
            out[rel] = content
            continue
        content = f"import {{ validatePayload }} from '@/lib/validators/{name}'\n" + content
        if not re.search(r"import\s*\{[^}]*\bNextResponse\b[^}]*\}\s*from\s*['\"]next/server", content):
            content = "import { NextResponse } from 'next/server'\n" + content
        replacement = (
            "const raw = await req.json()\n"
            f"    const parsed = validatePayload({json.dumps(name)}, raw)\n"
            "    if (!parsed.ok) return NextResponse.json({ success: false, error: parsed.error }, { status: 422 })\n"
            "    const body = parsed.data"
        )
        content = content.replace("const body = await req.json()", replacement)
        content = content.replace("delete body.owner", "delete (body as any).owner")
        content = content.replace("delete body._id", "delete (body as any)._id")
        # PUT accepts a partial payload while still enforcing known fields/types.
        marker = "export async function PUT"
        if marker in content:
            before, after = content.split(marker, 1)
            after = after.replace(f"validatePayload({json.dumps(name)}, raw)",
                                  f"validatePayload({json.dumps(name)}, raw, true)", 1)
            content = before + marker + after
        out[rel] = content
    return out


# ── CRUD route templates ──────────────────────────────────────────────────────

def _owned_crud_routes(name: str, seg: str) -> dict:
    """Ownership-scoped, session-verified CRUD (fully typed). Public list + detail;
    authed create (owner = session.userId); owner-or-admin update/delete (403 else);
    plus GET /<seg>/mine for the owner's own records."""
    collection = (
        "import { NextRequest, NextResponse } from 'next/server'\n"
        "import dbConnect from '@/lib/mongodb'\n"
        f"import {name} from '@/models/{name}'\n"
        "import { ok, created, serverError } from '@/lib/api'\n"
        "import { getSession } from '@/lib/auth'\n\n"
        "export const dynamic = 'force-dynamic'\n\n"
        "export async function GET() {\n"
        "  try {\n"
        "    await dbConnect()\n"
        f"    const items = await {name}.find({{}}).sort({{ createdAt: -1 }}).lean()\n"
        "    return ok(items)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n\n"
        "export async function POST(req: NextRequest) {\n"
        "  try {\n"
        "    const session = await getSession()\n"
        "    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })\n"
        "    await dbConnect()\n"
        "    const body = await req.json()\n"
        f"    const item = await {name}.create({{ ...body, owner: session.userId }})\n"
        "    return created(item)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n"
    )
    mine = (
        "import { NextResponse } from 'next/server'\n"
        "import dbConnect from '@/lib/mongodb'\n"
        f"import {name} from '@/models/{name}'\n"
        "import { ok, serverError } from '@/lib/api'\n"
        "import { getSession } from '@/lib/auth'\n\n"
        "export const dynamic = 'force-dynamic'\n\n"
        "export async function GET() {\n"
        "  try {\n"
        "    const session = await getSession()\n"
        "    if (!session) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })\n"
        "    await dbConnect()\n"
        f"    const items = await {name}.find({{ owner: session.userId }}).sort({{ createdAt: -1 }}).lean()\n"
        "    return ok(items)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n"
    )
    item = (
        "import { NextRequest, NextResponse } from 'next/server'\n"
        "import dbConnect from '@/lib/mongodb'\n"
        f"import {name} from '@/models/{name}'\n"
        "import { ok, fail, serverError } from '@/lib/api'\n"
        "import { getSession } from '@/lib/auth'\n\n"
        "export const dynamic = 'force-dynamic'\n\n"
        "type Ctx = { params: Promise<{ id: string }> }\n\n"
        "export async function GET(_req: NextRequest, { params }: Ctx) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    await dbConnect()\n"
        f"    const item = await {name}.findById(id).lean()\n"
        "    if (!item) return fail('Not found', 404)\n"
        "    return ok(item)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n\n"
        "async function gate(id: string) {\n"
        "  const session = await getSession()\n"
        "  if (!session) return { ok: false as const, status: 401 }\n"
        f"  const doc: any = await {name}.findById(id)\n"
        "  if (!doc) return { ok: false as const, status: 404 }\n"
        "  const isOwner = String(doc.owner) === session.userId\n"
        "  if (!isOwner && session.role !== 'admin') return { ok: false as const, status: 403 }\n"
        "  return { ok: true as const, status: 200 }\n"
        "}\n\n"
        "export async function PUT(req: NextRequest, { params }: Ctx) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    await dbConnect()\n"
        "    const g = await gate(id)\n"
        "    if (!g.ok) return NextResponse.json({ error: 'Forbidden' }, { status: g.status })\n"
        "    const body = await req.json()\n"
        "    delete body.owner\n"
        "    delete body._id\n"
        f"    const item = await {name}.findByIdAndUpdate(id, body, {{ new: true }}).lean()\n"
        "    return ok(item)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n\n"
        "export async function DELETE(_req: NextRequest, { params }: Ctx) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    await dbConnect()\n"
        "    const g = await gate(id)\n"
        "    if (!g.ok) return NextResponse.json({ error: 'Forbidden' }, { status: g.status })\n"
        f"    await {name}.findByIdAndDelete(id)\n"
        "    return ok({ success: true })\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n"
    )
    return {
        f"app/api/{seg}/route.ts": collection,
        f"app/api/{seg}/mine/route.ts": mine,
        f"app/api/{seg}/[id]/route.ts": item,
    }



def _staff_crud_routes(name: str, seg: str, model: dict) -> dict:
    """Role-wise CRUD: every method is authorized by the normalized resource
    permission matrix.  Page middleware is never treated as an API security rule."""
    permissions = model.get("permissions") or {
        role: ["read", "create", "update", "delete"]
        for role in (model.get("allowedRoles") or ["admin"])
    }
    permission_json = json.dumps(permissions, sort_keys=True)
    auth_helper = (
        f"const PERMISSIONS: Record<string, string[]> = {permission_json}\n"
        "async function authorize(operation: string) {\n"
        "  const session = await getSession()\n"
        "  if (!session) return { ok: false as const, status: 401 }\n"
        "  if (!(PERMISSIONS[session.role] || []).includes(operation)) return { ok: false as const, status: 403 }\n"
        "  return { ok: true as const, status: 200, session }\n"
        "}\n\n"
    )
    collection = (
        "import { NextRequest, NextResponse } from 'next/server'\n"
        "import dbConnect from '@/lib/mongodb'\n"
        f"import {name} from '@/models/{name}'\n"
        "import { ok, created, serverError } from '@/lib/api'\n"
        "import { getSession } from '@/lib/auth'\n\n"
        "export const dynamic = 'force-dynamic'\n\n"
        + auth_helper +
        "export async function GET() {\n"
        "  try {\n"
        "    const gate = await authorize('read')\n"
        "    if (!gate.ok) return NextResponse.json({ error: gate.status === 401 ? 'Unauthorized' : 'Forbidden' }, { status: gate.status })\n"
        "    await dbConnect()\n"
        f"    const items = await {name}.find({{}}).sort({{ createdAt: -1 }}).lean()\n"
        "    return ok(items)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n\n"
        "export async function POST(req: NextRequest) {\n"
        "  try {\n"
        "    const gate = await authorize('create')\n"
        "    if (!gate.ok) return NextResponse.json({ error: gate.status === 401 ? 'Unauthorized' : 'Forbidden' }, { status: gate.status })\n"
        "    await dbConnect()\n"
        "    const body = await req.json()\n"
        f"    const item = await {name}.create(body)\n"
        "    return created(item)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n"
    )
    item = (
        "import { NextRequest, NextResponse } from 'next/server'\n"
        "import dbConnect from '@/lib/mongodb'\n"
        f"import {name} from '@/models/{name}'\n"
        "import { ok, fail, serverError } from '@/lib/api'\n"
        "import { getSession } from '@/lib/auth'\n\n"
        "export const dynamic = 'force-dynamic'\n\n"
        + auth_helper +
        "type Ctx = { params: Promise<{ id: string }> }\n\n"
        "export async function GET(_req: NextRequest, { params }: Ctx) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    const gate = await authorize('read')\n"
        "    if (!gate.ok) return NextResponse.json({ error: gate.status === 401 ? 'Unauthorized' : 'Forbidden' }, { status: gate.status })\n"
        "    await dbConnect()\n"
        f"    const item = await {name}.findById(id).lean()\n"
        "    if (!item) return fail('Not found', 404)\n"
        "    return ok(item)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n\n"
        "export async function PUT(req: NextRequest, { params }: Ctx) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    const gate = await authorize('update')\n"
        "    if (!gate.ok) return NextResponse.json({ error: gate.status === 401 ? 'Unauthorized' : 'Forbidden' }, { status: gate.status })\n"
        "    await dbConnect()\n"
        "    const body = await req.json()\n"
        "    delete body._id\n"
        f"    const item = await {name}.findByIdAndUpdate(id, body, {{ new: true }}).lean()\n"
        "    if (!item) return fail('Not found', 404)\n"
        "    return ok(item)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n\n"
        "export async function DELETE(_req: NextRequest, { params }: Ctx) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    const gate = await authorize('delete')\n"
        "    if (!gate.ok) return NextResponse.json({ error: gate.status === 401 ? 'Unauthorized' : 'Forbidden' }, { status: gate.status })\n"
        "    await dbConnect()\n"
        f"    const item = await {name}.findByIdAndDelete(id)\n"
        "    if (!item) return fail('Not found', 404)\n"
        "    return ok({ success: true })\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n"
    )
    return {
        f"app/api/{seg}/route.ts": collection,
        f"app/api/{seg}/[id]/route.ts": item,
    }


def crud_routes(model: dict, auth: bool = False) -> dict:
    name = pascal(model.get("name", "Item"))
    seg = route_name(name)

    if model.get("ownedBy") == "User":
        return _owned_crud_routes(name, seg)
    if auth:
        return _staff_crud_routes(name, seg, model)

    collection_route = (
        "import dbConnect from '@/lib/mongodb'\n"
        f"import {name} from '@/models/{name}'\n"
        "import { ok, created, serverError } from '@/lib/api'\n\n"
        "export async function GET() {\n"
        "  try {\n"
        "    await dbConnect()\n"
        f"    const items = await {name}.find({{}}).sort({{ createdAt: -1 }}).lean()\n"
        "    return ok(items)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n\n"
        "export async function POST(req) {\n"
        "  try {\n"
        "    await dbConnect()\n"
        "    const body = await req.json()\n"
        f"    const item = await {name}.create(body)\n"
        "    return created(item)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n"
    )

    item_route = (
        "import dbConnect from '@/lib/mongodb'\n"
        f"import {name} from '@/models/{name}'\n"
        "import { ok, fail, serverError } from '@/lib/api'\n\n"
        "export async function GET(_req, { params }) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    await dbConnect()\n"
        f"    const item = await {name}.findById(id).lean()\n"
        "    if (!item) return fail('Not found', 404)\n"
        "    return ok(item)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n\n"
        "export async function PUT(req, { params }) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    await dbConnect()\n"
        "    const body = await req.json()\n"
        f"    const item = await {name}.findByIdAndUpdate(id, body, {{ new: true }}).lean()\n"
        "    if (!item) return fail('Not found', 404)\n"
        "    return ok(item)\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n\n"
        "export async function DELETE(_req, { params }) {\n"
        "  try {\n"
        "    const { id } = await params\n"
        "    await dbConnect()\n"
        f"    const item = await {name}.findByIdAndDelete(id)\n"
        "    if (!item) return fail('Not found', 404)\n"
        "    return ok({ success: true })\n"
        "  } catch (e) { return serverError(e) }\n"
        "}\n"
    )

    return {
        f"app/api/{seg}/route.ts": collection_route,
        f"app/api/{seg}/[id]/route.ts": item_route,
    }


def api_contract(spec: dict) -> str:
    """Human-readable REST contract injected into the frontend prompt."""
    models = spec.get("data_model") or []
    if not models:
        return "This app has NO backend API — it is a purely client-side page."
    lines = ["The backend already exists. Call ONLY these endpoints with fetch():"]
    for m in models:
        name = pascal(m.get("name", "Item"))
        seg = route_name(name)
        fields = ", ".join(
            f"{re.sub(r'[^A-Za-z0-9_]', '', str(f.get('name','')))}:{f.get('type','String')}"
            for f in (m.get("fields") or [])
        )
        owned = m.get("ownedBy") == "User"
        entry = (
            f"  - {name} ({{ {fields} }})\n"
            f"      GET    /api/{seg}          -> {{ success, data: {name}[] }} (each has _id)\n"
            f"      POST   /api/{seg}          -> body = new {name} fields, returns {{ success, data }}"
        )
        entry += "; login required, owner is set from the session\n" if owned else "\n"
        if owned:
            entry += f"      GET    /api/{seg}/mine     -> current user's objects; login required\n"
        entry += (
            f"      GET    /api/{seg}/<id>     -> {{ success, data: object }}\n"
            f"      PUT    /api/{seg}/<id>     -> body = updated fields, returns {{ success, data }}"
        )
        entry += "; owner or admin only\n" if owned else "\n"
        entry += f"      DELETE /api/{seg}/<id>     -> deletes, returns {{ success: true }}"
        if owned:
            entry += "; owner or admin only"
        lines.append(entry)
    if auth_enabled(spec):
        lines.extend([
            "Authentication contract:",
            "  - POST /api/auth/register -> { name, email, password, role }; sets an httpOnly session cookie",
            "  - POST /api/auth/login    -> { email, password }; sets an httpOnly session cookie",
            "  - POST /api/auth/logout   -> clears the session cookie",
            "  - GET  /api/auth/me       -> { user } when logged in, otherwise 401",
            "Never put a user id or owner id in a mutation body; the server derives ownership from the signed session.",
        ])
    lines.append(
        "Rules: use relative URLs only (never http://localhost). "
        "After POST/PUT/DELETE, re-fetch the list. Every record's id is `_id`."
    )
    return "\n".join(lines)


# ── deterministic config + framework files ────────────────────────────────────

def _package_json(app_name: str, auth: bool = False) -> str:
    v = VERSIONS
    deps = {
        "next": v["next"],
        "react": v["react"],
        "react-dom": v["react-dom"],
        "mongoose": v["mongoose"],
        "mongodb-memory-server": v["mongodb-memory-server"],
        "framer-motion": v["framer-motion"],
        "react-icons": v["react-icons"],
        "zod": v["zod"],
        "@mui/material": v["@mui/material"],
        "@mui/icons-material": v["@mui/icons-material"],
        "@mui/material-nextjs": v["@mui/material-nextjs"],
        "@emotion/react": v["@emotion/react"],
        "@emotion/styled": v["@emotion/styled"],
        "@emotion/cache": v["@emotion/cache"],
        "@radix-ui/react-slot": v["@radix-ui/react-slot"],
        "class-variance-authority": v["class-variance-authority"],
        "clsx": v["clsx"],
        "tailwind-merge": v["tailwind-merge"],
        "lucide-react": v["lucide-react"],
    }
    dev = {
        "tailwindcss": v["tailwindcss"],
        "postcss": v["postcss"],
        "autoprefixer": v["autoprefixer"],
        "typescript": v["typescript"],
        "@types/react": v["@types/react"],
        "@types/react-dom": v["@types/react-dom"],
        "@types/node": v["@types/node"],
        "eslint": v["eslint"],
        "eslint-config-next": v["eslint-config-next"],
    }
    if auth:
        deps["bcryptjs"] = v["bcryptjs"]
        deps["jose"] = v["jose"]
        dev["@types/bcryptjs"] = v["@types/bcryptjs"]
    pkg = {
        "name": app_name,
        "version": "0.1.0",
        "private": True,
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "start": "next start",
            "lint": "eslint . --max-warnings=0",
            "typecheck": "tsc --noEmit",
        },
        # Next 16.2.x still declares an older nested PostCSS release.  Keep the
        # application on a stable Next release while forcing the audited
        # patched PostCSS implementation throughout the dependency graph.
        "overrides": {
            "next": {
                "postcss": v["postcss"],
            },
        },
        "dependencies": deps,
        "devDependencies": dev,
    }
    return json.dumps(pkg, indent=2) + "\n"


_NEXT_CONFIG = (
    "/** @type {import('next').NextConfig} */\n"
    "const nextConfig = {\n"
    "  reactStrictMode: true,\n"
    "  // Strict quality mode: type and lint failures must block release.\n"
    "  // mongoose / mongodb-memory-server use native + dynamic requires; keep them\n"
    "  // external so Next does not try to bundle them (Next 14 option name).\n"
    "  serverExternalPackages: ['mongoose', 'mongodb-memory-server'],\n"
    "  // Generated projects can live below workspaces with unrelated lockfiles.\n"
    "  // Pin Turbopack discovery to the generated application itself.\n"
    "  turbopack: { root: process.cwd() },\n"
    "}\n"
    "export default nextConfig\n"
)

# Strict Next 16 TypeScript config. The whole project is TypeScript now (no .js
# source), so allowJs is off and the automatic React JSX runtime is explicit.
_TSCONFIG = json.dumps(
    {
        "compilerOptions": {
            "target": "ES2017",
            "lib": ["dom", "dom.iterable", "esnext"],
            "allowJs": False,
            "skipLibCheck": True,
            "strict": True,
            "noImplicitAny": False,
            "noEmit": True,
            "esModuleInterop": True,
            "module": "esnext",
            "moduleResolution": "bundler",
            "resolveJsonModule": True,
            "isolatedModules": True,
            "jsx": "react-jsx",
            "incremental": True,
            "plugins": [{"name": "next"}],
            "baseUrl": ".",
            "paths": {"@/*": ["./*"]},
        },
        "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts", ".next/dev/types/**/*.ts"],
        "exclude": ["node_modules"],
    },
    indent=2,
) + "\n"

_NEXT_ENV_DTS = (
    "/// <reference types=\"next\" />\n"
    "/// <reference types=\"next/image-types/global\" />\n"
    "\n"
    "// NOTE: This file should not be edited\n"
    "// see https://nextjs.org/docs/app/api-reference/config/typescript for more information.\n"
)

_POSTCSS = (
    "const config = {\n"
    "  plugins: { tailwindcss: {}, autoprefixer: {} },\n"
    "}\n"
    "export default config\n"
)

_GITIGNORE = "node_modules\n.next\n.env.local\n*.log\ndist\n"

_ESLINT_CONFIG = (
    "import { defineConfig, globalIgnores } from 'eslint/config'\n"
    "import nextVitals from 'eslint-config-next/core-web-vitals'\n"
    "import nextTypescript from 'eslint-config-next/typescript'\n\n"
    "export default defineConfig([\n"
    "  ...nextVitals,\n"
    "  ...nextTypescript,\n"
    "  { rules: { '@typescript-eslint/no-explicit-any': 'off', 'react/no-unescaped-entities': 'off' } },\n"
    "  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts']),\n"
    "])\n"
)

_ENV_EXAMPLE = (
    "# Optional. Leave unset to use the zero-setup in-memory database.\n"
    "# For a real database, uncomment and point at your MongoDB instance:\n"
    "# MONGODB_URI=mongodb://127.0.0.1:27017/app\n"
)


_COLOR_KEYWORDS = ("red", "mario", "green", "orange", "pink", "gold", "yellow",
                   "purple", "blue", "navy", "teal", "cyan")


def _accents(color: str):
    """Derive two accent colors from a free-text color_scheme keyword (ported from builder)."""
    acc, acc2 = "#6366f1", "#22d3ee"
    cl = (color or "").lower()
    if "red" in cl or "mario" in cl:      acc, acc2 = "#ff4444", "#ff9f43"
    elif "green" in cl:                    acc, acc2 = "#10b981", "#059669"
    elif "orange" in cl:                   acc, acc2 = "#f59e0b", "#ef4444"
    elif "pink" in cl:                     acc, acc2 = "#ec4899", "#8b5cf6"
    elif "gold" in cl or "yellow" in cl:   acc, acc2 = "#fbbf24", "#f59e0b"
    elif "purple" in cl:                   acc, acc2 = "#a855f7", "#6366f1"
    elif "blue" in cl or "navy" in cl:     acc, acc2 = "#3b82f6", "#22d3ee"
    elif "teal" in cl or "cyan" in cl:     acc, acc2 = "#14b8a6", "#22d3ee"
    return acc, acc2


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """h in [0,360), s/l in [0,1] → #rrggbb."""
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if   h < 60:  r, g, b = c, x, 0
    elif h < 120: r, g, b = x, c, 0
    elif h < 180: r, g, b = 0, c, x
    elif h < 240: r, g, b = 0, x, c
    elif h < 300: r, g, b = x, 0, c
    else:         r, g, b = c, 0, x
    return "#%02x%02x%02x" % (round((r + m) * 255), round((g + m) * 255), round((b + m) * 255))


def _hex(value) -> str | None:
    if isinstance(value, str):
        v = value.strip().lstrip("#")
        if re.fullmatch(r"[0-9a-fA-F]{6}", v):
            return "#" + v.lower()
    return None


def _palette(spec: dict):
    """Single source of truth for the two brand accents.

    1. An explicit palette in ``spec['theme']`` wins (accent/primary/brand + accent2/secondary).
    2. A colour keyword in ``color_scheme`` (free-text specs) maps via ``_accents``.
    3. Otherwise the accent is derived deterministically from the app seed, so every app
       gets a distinct hue instead of the fixed indigo/cyan default.
    """
    theme = spec.get("theme") or {}
    if isinstance(theme, dict):
        acc = _hex(theme.get("accent")) or _hex(theme.get("primary")) or _hex(theme.get("brand"))
        acc2 = _hex(theme.get("accent2")) or _hex(theme.get("secondary"))
        if acc:
            return acc, (acc2 or acc)

    color_scheme = str(spec.get("color_scheme") or "")
    if any(k in color_scheme.lower() for k in _COLOR_KEYWORDS):
        return _accents(color_scheme)

    seed = (spec.get("design_brief") or {}).get("seed")
    if not isinstance(seed, int):
        basis = str(spec.get("title") or spec.get("brand_name") or "app")
        seed = int(hashlib.sha1(basis.encode("utf-8")).hexdigest()[:8], 16)
    hue = seed % 360
    return _hsl_to_hex(hue, 0.72, 0.58), _hsl_to_hex((hue + 32) % 360, 0.75, 0.56)


def _tailwind_config(acc: str = "#6366f1", acc2: str = "#22d3ee") -> str:
    return (
        "import type { Config } from 'tailwindcss'\n\n"
        "const config: Config = {\n"
        "  content: [\n"
        "    './app/**/*.{js,jsx,ts,tsx}',\n"
        "    './components/**/*.{js,jsx,ts,tsx}',\n"
        "  ],\n"
        "  theme: {\n"
        "    extend: {\n"
        "      colors: {\n"
        f"        accent:  '{acc}',\n"
        f"        accent2: '{acc2}',\n"
        "        dark:    '#0a0a0f',\n"
        "        dark2:   '#12121a',\n"
        "        card:    '#1e1e2e',\n"
        "      },\n"
        "      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },\n"
        "    },\n"
        "  },\n"
        "  plugins: [],\n"
        "}\n"
        "export default config\n"
    )


def _globals_css(acc: str = "#6366f1", acc2: str = "#22d3ee") -> str:
    return (
        "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n\n"
        f":root {{ --accent: {acc}; --accent2: {acc2}; }}\n\n"
        "@layer base {\n"
        "  * { scroll-behavior: smooth; box-sizing: border-box; }\n"
        "  /* Dark-first safety net: pages never render blank-white even if a\n"
        "     component forgets its own background. */\n"
        "  html, body { min-height: 100vh; background-color: #0a0a0f; color: #e2e8f0; }\n"
        "  body { @apply font-sans antialiased; }\n"
        "  ::-webkit-scrollbar { width: 6px; }\n"
        "  ::-webkit-scrollbar-track { background: #12121a; }\n"
        f"  ::-webkit-scrollbar-thumb {{ background: {acc}; border-radius: 99px; }}\n"
        "}\n"
        "@layer utilities {\n"
        "  .gradient-text {\n"
        f"    background: linear-gradient(135deg, {acc}, {acc2});\n"
        "    -webkit-background-clip: text; background-clip: text;\n"
        "    -webkit-text-fill-color: transparent;\n"
        "  }\n"
        "  .glass {\n"
        "    backdrop-filter: blur(20px);\n"
        "    background: rgba(30,30,46,0.55);\n"
        "    border: 1px solid rgba(255,255,255,0.08);\n"
        "  }\n"
        f"  .glow {{ box-shadow: 0 0 30px {acc}33; border: 1px solid {acc}44; }}\n"
        "}\n"
    )


def _root_layout(title: str, description: str) -> str:
    t = title.replace("'", "\\'")
    d = (description or title).replace("'", "\\'")[:160]
    return (
        "import './globals.css'\n"
        "import { AppRouterCacheProvider } from '@mui/material-nextjs/v15-appRouter'\n"
        "import Providers from './providers'\n\n"
        "export const metadata = {\n"
        f"  title: '{t}',\n"
        f"  description: '{d}',\n"
        "}\n\n"
        "export default function RootLayout({ children }) {\n"
        "  return (\n"
        "    <html lang=\"en\" data-scroll-behavior=\"smooth\">\n"
        "      <head>\n"
        "        <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\" />\n"
        "        <link\n"
        "          href=\"https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap\"\n"
        "          rel=\"stylesheet\"\n"
        "        />\n"
        "      </head>\n"
        "      <body>\n"
        "        <AppRouterCacheProvider options={{ key: 'mui' }}>\n"
        "          <Providers>{children}</Providers>\n"
        "        </AppRouterCacheProvider>\n"
        "      </body>\n"
        "    </html>\n"
        "  )\n"
        "}\n"
    )


# MUI theme + dark-mode provider (client). Wrapped by AppRouterCacheProvider in the root layout so
# Emotion styles are SSR-safe under the App Router (no hydration flash). CssBaseline applies the dark
# background globally; the model styles components with the `sx` prop against this theme.
def _providers(acc: str = "#6366f1", acc2: str = "#22d3ee") -> str:
    """The theme is built from the app's OWN palette. It used to hard-code indigo/cyan, and since every
    LLM-authored surface is now a themed MUI component, that made every generated app look identical
    no matter what palette the spec asked for."""
    return (
        "'use client'\n\n"
        "import { ThemeProvider, createTheme } from '@mui/material/styles'\n"
        "import CssBaseline from '@mui/material/CssBaseline'\n\n"
        "const theme = createTheme({\n"
        "  palette: {\n"
        "    mode: 'dark',\n"
        f"    primary: {{ main: '{acc}' }},\n"
        f"    secondary: {{ main: '{acc2}' }},\n"
        "    background: { default: '#0a0a0f', paper: '#1e1e2e' },\n"
        "  },\n"
        "  shape: { borderRadius: 12 },\n"
        "  typography: { fontFamily: 'Inter, system-ui, sans-serif' },\n"
        "})\n\n"
        "export default function Providers({ children }: { children: React.ReactNode }) {\n"
        "  return (\n"
        "    <ThemeProvider theme={theme}>\n"
        "      <CssBaseline />\n"
        "      {children}\n"
        "    </ThemeProvider>\n"
        "  )\n"
        "}\n"
    )


# The connection singleton — the single most important deterministic file.
_DB_LIB = (
    "import mongoose from 'mongoose'\n\n"
    "// Augment the Node global so the cross-reload caches type-check under TS.\n"
    "declare global {\n"
    "  var _mongoose: { conn: any; promise: any } | undefined\n"
    "  var _mongod: any\n"
    "}\n\n"
    "// Cache the connection across Next.js dev hot-reloads to avoid connection\n"
    "// storms and OverwriteModelError.\n"
    "const cached: { conn: any; promise: any } = global._mongoose || { conn: null, promise: null }\n"
    "global._mongoose = cached\n\n"
    "async function resolveUri() {\n"
    "  if (process.env.MONGODB_URI) return process.env.MONGODB_URI\n"
    "  // Zero-setup fallback: spin up an in-memory MongoDB so the app runs with\n"
    "  // no database installed. A real MONGODB_URI always takes precedence.\n"
    "  const { MongoMemoryServer } = await import('mongodb-memory-server')\n"
    "  if (!global._mongod) global._mongod = await MongoMemoryServer.create()\n"
    "  return global._mongod.getUri()\n"
    "}\n\n"
    "export default async function dbConnect() {\n"
    "  if (cached.conn) return cached.conn\n"
    "  if (!cached.promise) {\n"
    "    cached.promise = resolveUri().then((uri) =>\n"
    "      mongoose.connect(uri, { bufferCommands: false })\n"
    "    )\n"
    "  }\n"
    "  try {\n"
    "    cached.conn = await cached.promise\n"
    "  } catch (e) {\n"
    "    cached.promise = null\n"
    "    throw e\n"
    "  }\n"
    "  return cached.conn\n"
    "}\n"
)

_API_LIB = (
    "import { NextResponse } from 'next/server'\n\n"
    "export const ok = (data, status = 200, meta = undefined) =>\n"
    "  NextResponse.json({ success: true, data, ...(meta ? { meta } : {}) }, { status })\n"
    "export const created = (data) =>\n"
    "  NextResponse.json({ success: true, data }, { status: 201 })\n"
    "export const fail = (message, status = 400) =>\n"
    "  NextResponse.json({ success: false, error: message }, { status })\n"
    "export const serverError = (e?: any) => {\n"
    "  console.error(e)\n"
    "  return NextResponse.json({ success: false, error: String(e?.message || e || 'Server error') }, { status: 500 })\n"
    "}\n"
)


def auth_enabled(spec: dict) -> bool:
    """True when the spec is a multipage-app that needs authentication."""
    a = spec.get("auth") or {}
    return bool(a.get("enabled")) or spec.get("app_kind") == "multipage-app"


def base_files(spec: dict) -> dict:
    """Config, layout shell and the design-system CSS (owned by the frontend agent)."""
    title = spec.get("title") or spec.get("brand_name") or "My App"
    description = spec.get("description", title)
    acc, acc2 = _palette(spec)
    app_name = re.sub(r"[^a-z0-9-]", "-", title.lower())[:40].strip("-") or "app"
    return {
        "package.json": _package_json(app_name, auth=auth_enabled(spec)),
        "next.config.mjs": _NEXT_CONFIG,
        "tsconfig.json": _TSCONFIG,
        "next-env.d.ts": _NEXT_ENV_DTS,
        "tailwind.config.ts": _tailwind_config(acc, acc2),
        "postcss.config.mjs": _POSTCSS,
        ".gitignore": _GITIGNORE,
        "eslint.config.mjs": _ESLINT_CONFIG,
        ".env.example": _ENV_EXAMPLE,
        "app/layout.tsx": _root_layout(title, description),
        "app/providers.tsx": _providers(acc, acc2),
        "app/globals.css": _globals_css(acc, acc2),
    }


def data_layer_files(spec: dict) -> dict:
    """Connection singleton, API helpers and Mongoose models (owned by the schema agent)."""
    files = {
        "lib/mongodb.ts": _DB_LIB,
        "lib/api.ts": _API_LIB,
    }
    for model in (spec.get("data_model") or []):
        name = pascal(model.get('name', 'Item'))
        files[f"models/{name}.ts"] = model_file(model)
        files[f"lib/validators/{name}.ts"] = validator_file(model)
    return files


def api_files(spec: dict) -> dict:
    """CRUD route handlers for every model (owned by the API agent)."""
    auth = auth_enabled(spec)
    files = {}
    for model in (spec.get("data_model") or []):
        name = pascal(model.get('name', 'Item'))
        files.update(_inject_validation(crud_routes(model, auth=auth), name))
    return files


def reports_route(spec: dict) -> str:
    """Deterministic `/api/reports?type=summary` → `{ success, data: { counts, revenue } }`.
    EVERY dashboard the LLM writes fetches this endpoint for KPI numbers (per the section rule), so it
    must always exist — otherwise the fetch 404s, returns Next's HTML error page, and `res.json()`
    throws 'Unexpected token <'. Counts are keyed by API segment so a dashboard can map them directly."""
    models = [m for m in (spec.get("data_model") or []) if pascal(m.get("name", "")) != "User"]
    if not models:
        return ""
    imports = "".join(f"import {pascal(m['name'])} from '@/models/{pascal(m['name'])}'\n" for m in models)
    count_lines = "".join(
        f"    counts['{route_name(m['name'])}'] = await {pascal(m['name'])}.countDocuments()\n"
        for m in models)
    # Revenue: sum the `total` field of the first model that has one (typically Order/Payment/Invoice).
    rev_model = next((m for m in models
                      if any(f.get("name") == "total" for f in (m.get("fields") or []))), None)
    if rev_model:
        rn = pascal(rev_model["name"])
        rev = (f"    const _rev = await {rn}.aggregate([{{ $group: {{ _id: null, sum: {{ $sum: '$total' }} }} }}])\n"
               "    const revenue = _rev[0]?.sum || 0\n"
               "    return ok({ counts, revenue })\n")
    else:
        rev = "    return ok({ counts, revenue: 0 })\n"
    return (
        "import dbConnect from '@/lib/mongodb'\n"
        + imports +
        "import { ok, serverError } from '@/lib/api'\n\n"
        "export const dynamic = 'force-dynamic'\n\n"
        "export async function GET() {\n"
        "  try {\n"
        "    await dbConnect()\n"
        "    const counts: Record<string, number> = {}\n"
        + count_lines
        + rev +
        "  } catch (e) { return serverError(e) }\n"
        "}\n"
    )


def auth_files(spec: dict) -> dict:
    """Deterministic auth + multi-role dashboard files (multipage-app mode only)."""
    if not auth_enabled(spec):
        return {}
    from agents import auth_scaffold  # lazy import avoids a circular dependency
    return auth_scaffold.auth_files(spec)


def kit_files(spec: dict) -> dict:
    """Deterministic business-behaviour kits (inventory/invoicing/pos/booking/…)."""
    if not spec.get("kits"):
        return {}
    from agents import kits  # lazy import
    return kits.kit_files(spec)


def scaffold_files(spec: dict) -> dict:
    """Every deterministic file (all except LLM-generated pages/components)."""
    files = {}
    files.update(base_files(spec))
    files.update(data_layer_files(spec))
    files.update(api_files(spec))
    files.update(auth_files(spec))
    files.update(kit_files(spec))
    return files
