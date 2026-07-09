import { promises as fs } from 'fs';
import path from 'path';
import { projectDir } from '../workspace/fs';
import { syntaxErrors } from './verify';

/**
 * Deterministic API route generation.
 *
 * CRUD route handlers are formulaic: list+create, get+update+delete-by-id, and
 * the auth trio. Having a 7B/12B model hand-write 40-60 of them is the single
 * biggest time sink of a build (~15 LLM calls) AND a steady bug source. This
 * module writes them DIRECTLY from the Mongoose models already on disk —
 * grounded in the real export names and real schema fields, so imports always
 * line up and inputs are validated with zod. Zero LLM calls, zero syntax bugs,
 * instant. Endpoints with real business logic (reports, status workflows the
 * heuristic can't map) are left for the LLM waves.
 */

export interface ParsedModel {
  /** Named export used in `import { X } from "@/lib/models/<file>"`. */
  exportName: string;
  /** true when the model is only available as a default export. */
  isDefault: boolean;
  /** lib/models/<fileBase>.ts */
  fileBase: string;
  /** field name -> kind */
  fields: Map<string, 'string' | 'number' | 'boolean' | 'date' | 'mixed'>;
  /** field name -> enum values (subset of fields) */
  enums: Map<string, string[]>;
}

const RESERVED_MODEL_FILES = new Set(['index.ts', 'index.js']);

function fieldKind(t: string): 'string' | 'number' | 'boolean' | 'date' | 'mixed' {
  if (/String/.test(t)) return 'string';
  if (/Number|Decimal/.test(t)) return 'number';
  if (/Boolean/.test(t)) return 'boolean';
  if (/Date/.test(t)) return 'date';
  return 'mixed';
}

/** Parse one model file: export name + a flat view of its schema fields. */
export function parseModelSource(fileBase: string, src: string): ParsedModel | null {
  // export const Vehicle = mongoose.models.Vehicle || mongoose.model("Vehicle", ...)
  let exportName = '';
  let isDefault = false;
  const named = src.match(
    /export\s+const\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:mongoose\.)?models?\b/,
  );
  if (named) exportName = named[1];
  if (!exportName) {
    const namedModel = src.match(
      /export\s+const\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=[\s\S]{0,120}?mongoose\.model/,
    );
    if (namedModel) exportName = namedModel[1];
  }
  if (!exportName) {
    const def = src.match(/export\s+default\s+([A-Za-z_$][\w$]*)/);
    if (def) {
      exportName = def[1];
      isDefault = true;
    }
  }
  if (!exportName) return null;

  const fields = new Map<string, ParsedModel['fields'] extends Map<string, infer V> ? V : never>();
  const enums = new Map<string, string[]>();

  // Object form: name: { type: String, ... enum: [...] }
  const objRe =
    /(\w+)\s*:\s*\{([^{}]*?type\s*:\s*(?:mongoose\.)?(?:Schema\.Types\.)?(\w+)[^{}]*)\}/g;
  let m: RegExpExecArray | null;
  while ((m = objRe.exec(src))) {
    const [, name, body, type] = m;
    if (name === 'type') continue;
    fields.set(name, fieldKind(type));
    const en = body.match(/enum\s*:\s*\[([^\]]*)\]/);
    if (en) {
      const values = [...en[1].matchAll(/['"]([^'"]+)['"]/g)].map((v) => v[1]);
      if (values.length) enums.set(name, values);
    }
  }
  // Shorthand form: name: String,
  const shortRe = /(\w+)\s*:\s*(String|Number|Boolean|Date)\s*[,\n\r}]/g;
  while ((m = shortRe.exec(src))) {
    if (!fields.has(m[1])) fields.set(m[1], fieldKind(m[2]));
  }

  return { exportName, isDefault, fileBase, fields, enums };
}

/** Read + parse every model under lib/models/. */
export async function parseModelsFromDisk(id: string): Promise<ParsedModel[]> {
  const dir = path.join(projectDir(id), 'lib', 'models');
  let entries: string[] = [];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return [];
  }
  const out: ParsedModel[] = [];
  for (const f of entries) {
    if (!f.endsWith('.ts') || RESERVED_MODEL_FILES.has(f)) continue;
    try {
      const src = await fs.readFile(path.join(dir, f), 'utf8');
      const parsed = parseModelSource(f.replace(/\.ts$/, ''), src);
      if (parsed) out.push(parsed);
    } catch {
      /* skip unreadable */
    }
  }
  return out;
}

/** Normalised singular candidates for a route segment / model name. */
function normCandidates(raw: string): string[] {
  const flat = raw.toLowerCase().replace(/[-_]/g, '');
  const cands = new Set<string>([flat]);
  if (flat.endsWith('ies')) cands.add(flat.slice(0, -3) + 'y');
  if (flat.endsWith('es')) cands.add(flat.slice(0, -2));
  if (flat.endsWith('s')) cands.add(flat.slice(0, -1));
  return [...cands];
}

function matchScore(segment: string, model: ParsedModel): number {
  const want = normCandidates(segment);
  const have = [
    ...normCandidates(model.exportName),
    ...normCandidates(model.fileBase),
  ];
  for (const w of want) {
    for (const h of have) {
      if (w === h) return 100;
      if (w.length >= 4 && h.startsWith(w)) return 70;
    }
  }
  return 0;
}

function modelForSegment(segment: string, models: ParsedModel[]): ParsedModel | null {
  let best: { model: ParsedModel; score: number } | null = null;
  for (const model of models) {
    const score = matchScore(segment, model);
    if (score > (best?.score ?? 0)) best = { model, score };
  }
  return best ? best.model : null;
}

const API_NAMESPACE_SEGMENTS = new Set([
  'admin',
  'api',
  'customer',
  'customers',
  'internal',
  'operations',
  'pos',
  'private',
  'public',
  'system',
]);

const NON_CRUD_ENDPOINT_SEGMENTS = new Set([
  'analytics',
  'dashboard',
  'dashboards',
  'export',
  'health',
  'highlights',
  'me',
  'metrics',
  'report',
  'reports',
  'search',
  'stats',
  'summary',
  'testimonials',
]);

function isDynamicSegment(segment: string): boolean {
  return /^\[\w+\]$/.test(segment);
}

function isRouteNamespace(segment: string): boolean {
  return API_NAMESPACE_SEGMENTS.has(segment.toLowerCase());
}

function isNonCrudEndpoint(segment: string): boolean {
  return NON_CRUD_ENDPOINT_SEGMENTS.has(segment.toLowerCase());
}

function modelForApiSegments(
  segments: string[],
  models: ParsedModel[],
  upTo = segments.length,
): ParsedModel | null {
  const candidates = segments
    .slice(0, upTo)
    .filter(
      (segment) =>
        segment &&
        !isDynamicSegment(segment) &&
        !isRouteNamespace(segment) &&
        !isNonCrudEndpoint(segment),
    )
    .reverse();

  for (const segment of candidates) {
    const model = modelForSegment(segment, models);
    if (model) return model;
  }
  return null;
}

function importLine(model: ParsedModel): string {
  return model.isDefault
    ? `import ${model.exportName} from '@/lib/models/${model.fileBase}';`
    : `import { ${model.exportName} } from '@/lib/models/${model.fileBase}';`;
}

function zodFieldExpr(kind: string, enumVals?: string[]): string {
  if (enumVals && enumVals.length) {
    return `z.enum([${enumVals.map((v) => JSON.stringify(v)).join(', ')}]).optional()`;
  }
  switch (kind) {
    case 'number':
      return 'z.coerce.number().optional()';
    case 'boolean':
      return 'z.coerce.boolean().optional()';
    case 'date':
      return 'z.coerce.date().optional()';
    case 'string':
      return 'z.string().optional()';
    default:
      return 'z.unknown().optional()';
  }
}

/** The zod body schema for create/update: every known field, all optional
 *  (models are sanitized to non-required so inserts never fail on a field the
 *  UI doesn't send), unknown keys passed through. */
function zodSchemaSource(model: ParsedModel): string {
  const lines: string[] = [];
  for (const [name, kind] of model.fields) {
    if (name === '_id' || name === '__v') continue;
    lines.push(`  ${name}: ${zodFieldExpr(kind, model.enums.get(name))},`);
  }
  return `const bodySchema = z\n  .object({\n${lines.join('\n')}\n  })\n  .passthrough();`;
}

function searchableFields(model: ParsedModel): string[] {
  return [...model.fields.entries()]
    .filter(([name, kind]) => kind === 'string' && !model.enums.has(name) && !/password/i.test(name))
    .map(([name]) => name)
    .slice(0, 4);
}

function filterableFields(model: ParsedModel): string[] {
  return [...model.enums.keys()].slice(0, 4);
}

/** app/api/<segment>/route.ts — GET list (search/filter/pagination) + POST. */
function listRouteSource(model: ParsedModel): string {
  const search = searchableFields(model);
  const filters = filterableFields(model);
  return `import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { connectDB } from '@/lib/db';
${importLine(model)}

${zodSchemaSource(model)}

export async function GET(req: NextRequest) {
  try {
    await connectDB();
    const { searchParams } = new URL(req.url);
    const page = Math.max(1, Number(searchParams.get('page') || '1'));
    const limit = Math.min(200, Math.max(1, Number(searchParams.get('limit') || '100')));
    const search = (searchParams.get('search') || '').trim();
    const filter: Record<string, unknown> = {};
${filters
  .map(
    (f) => `    const ${f}Param = searchParams.get(${JSON.stringify(f)});
    if (${f}Param) filter[${JSON.stringify(f)}] = ${f}Param;`,
  )
  .join('\n')}
${
  search.length
    ? `    if (search) {
      filter.$or = [
${search.map((f) => `        { ${f}: { $regex: search, $options: 'i' } },`).join('\n')}
      ];
    }`
    : '    void search;'
}
    const items = await ${model.exportName}.find(filter)
      .sort({ createdAt: -1, _id: -1 })
      .skip((page - 1) * limit)
      .limit(limit)
      .lean();
    return NextResponse.json({ success: true, data: items });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load records';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    await connectDB();
    const raw = await req.json().catch(() => null);
    if (!raw || typeof raw !== 'object') {
      return NextResponse.json({ success: false, error: 'Invalid JSON body' }, { status: 400 });
    }
    const parsed = bodySchema.safeParse(raw);
    if (!parsed.success) {
      return NextResponse.json(
        { success: false, error: 'Validation failed', issues: parsed.error.issues },
        { status: 400 },
      );
    }
    const data = { ...parsed.data } as Record<string, unknown>;
    delete data._id;
    const created = await ${model.exportName}.create(data);
    return NextResponse.json({ success: true, data: created }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to create record';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
`;
}

/** app/api/<segment>/[id]/route.ts — GET one + PUT/PATCH update + DELETE. */
function idRouteSource(model: ParsedModel): string {
  return `import { NextRequest, NextResponse } from 'next/server';
import mongoose from 'mongoose';
import { z } from 'zod';
import { connectDB } from '@/lib/db';
${importLine(model)}

${zodSchemaSource(model)}

type Params = { params: Promise<{ id: string }> };

export async function GET(_req: NextRequest, { params }: Params) {
  try {
    await connectDB();
    const { id } = await params;
    if (!mongoose.isValidObjectId(id)) {
      return NextResponse.json({ success: false, error: 'Invalid id' }, { status: 400 });
    }
    const doc = await ${model.exportName}.findById(id).lean();
    if (!doc) return NextResponse.json({ success: false, error: 'Not found' }, { status: 404 });
    return NextResponse.json({ success: true, data: doc });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load record';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

async function update(req: NextRequest, { params }: Params) {
  try {
    await connectDB();
    const { id } = await params;
    if (!mongoose.isValidObjectId(id)) {
      return NextResponse.json({ success: false, error: 'Invalid id' }, { status: 400 });
    }
    const raw = await req.json().catch(() => null);
    if (!raw || typeof raw !== 'object') {
      return NextResponse.json({ success: false, error: 'Invalid JSON body' }, { status: 400 });
    }
    const parsed = bodySchema.safeParse(raw);
    if (!parsed.success) {
      return NextResponse.json(
        { success: false, error: 'Validation failed', issues: parsed.error.issues },
        { status: 400 },
      );
    }
    const data = { ...parsed.data } as Record<string, unknown>;
    delete data._id;
    const doc = await ${model.exportName}.findByIdAndUpdate(id, data, {
      new: true,
      runValidators: true,
    }).lean();
    if (!doc) return NextResponse.json({ success: false, error: 'Not found' }, { status: 404 });
    return NextResponse.json({ success: true, data: doc });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to update record';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

export const PUT = update;
export const PATCH = update;

export async function DELETE(_req: NextRequest, { params }: Params) {
  try {
    await connectDB();
    const { id } = await params;
    if (!mongoose.isValidObjectId(id)) {
      return NextResponse.json({ success: false, error: 'Invalid id' }, { status: 400 });
    }
    const doc = await ${model.exportName}.findByIdAndDelete(id).lean();
    if (!doc) return NextResponse.json({ success: false, error: 'Not found' }, { status: 404 });
    return NextResponse.json({ success: true, data: { ok: true }, ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to delete record';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
`;
}

/** Map a status-workflow action segment (confirm / cancel / check-in …) onto an
 *  enum value of the model's status-like field. Returns null when unsure. */
function actionStatusTarget(
  model: ParsedModel,
  action: string,
): { field: string; value: string } | null {
  const flat = action.toLowerCase().replace(/[-_]/g, '');
  for (const [field, values] of model.enums) {
    if (!/status|state/i.test(field)) continue;
    for (const value of values) {
      const v = value.toLowerCase().replace(/[-_]/g, '');
      if (v === flat || v === flat + 'ed' || v === flat + 'd' || v.startsWith(flat)) {
        return { field, value };
      }
    }
  }
  return null;
}

/** app/api/<segment>/[id]/<action>/route.ts — PATCH status transition. */
function actionRouteSource(model: ParsedModel, field: string, value: string): string {
  return `import { NextRequest, NextResponse } from 'next/server';
import mongoose from 'mongoose';
import { connectDB } from '@/lib/db';
${importLine(model)}

type Params = { params: Promise<{ id: string }> };

async function transition(_req: NextRequest, { params }: Params) {
  try {
    await connectDB();
    const { id } = await params;
    if (!mongoose.isValidObjectId(id)) {
      return NextResponse.json({ success: false, error: 'Invalid id' }, { status: 400 });
    }
    const doc = await ${model.exportName}.findByIdAndUpdate(
      id,
      { ${field}: ${JSON.stringify(value)} },
      { new: true },
    ).lean();
    if (!doc) return NextResponse.json({ success: false, error: 'Not found' }, { status: 404 });
    return NextResponse.json({ success: true, data: doc });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to update status';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

export const PATCH = transition;
export const POST = transition;
`;
}

function findUserModel(models: ParsedModel[]): ParsedModel | null {
  return modelForSegment('users', models) ?? modelForSegment('user', models);
}

function passwordField(model: ParsedModel): string | null {
  for (const name of model.fields.keys()) if (/password/i.test(name)) return name;
  return null;
}

function authRouteSource(
  kind: 'login' | 'register' | 'me' | 'logout',
  user: ParsedModel,
  pwField: string,
): string {
  const header = `import { NextRequest, NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { z } from 'zod';
import { connectDB } from '@/lib/db';
${importLine(user)}

const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-me';
const TOKEN_COOKIE = 'token';
`;
  if (kind === 'login') {
    return `${header}
const bodySchema = z.object({ email: z.string().email(), password: z.string().min(1) });

export async function POST(req: NextRequest) {
  try {
    await connectDB();
    const raw = await req.json().catch(() => null);
    const parsed = bodySchema.safeParse(raw);
    if (!parsed.success) {
      return NextResponse.json({ success: false, error: 'Email and password are required' }, { status: 400 });
    }
    const user = await ${user.exportName}.findOne({ email: parsed.data.email.toLowerCase() });
    if (!user) return NextResponse.json({ success: false, error: 'Invalid credentials' }, { status: 401 });
    const stored = String(user.${pwField} ?? '');
    const ok = stored.startsWith('$2')
      ? await bcrypt.compare(parsed.data.password, stored)
      : stored === parsed.data.password;
    if (!ok) return NextResponse.json({ success: false, error: 'Invalid credentials' }, { status: 401 });
    const token = jwt.sign({ sub: String(user._id), email: user.email }, JWT_SECRET, {
      expiresIn: '7d',
    });
    const safe = user.toObject ? user.toObject() : user;
    delete (safe as Record<string, unknown>).${pwField};
    const res = NextResponse.json({ success: true, data: { user: safe, token }, user: safe, token });
    res.cookies.set(TOKEN_COOKIE, token, { httpOnly: true, sameSite: 'lax', path: '/' });
    return res;
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Login failed';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
`;
  }
  if (kind === 'register') {
    return `${header}
const bodySchema = z
  .object({ email: z.string().email(), password: z.string().min(6) })
  .passthrough();

export async function POST(req: NextRequest) {
  try {
    await connectDB();
    const raw = await req.json().catch(() => null);
    const parsed = bodySchema.safeParse(raw);
    if (!parsed.success) {
      return NextResponse.json(
        { success: false, error: 'Validation failed', issues: parsed.error.issues },
        { status: 400 },
      );
    }
    const email = parsed.data.email.toLowerCase();
    const existing = await ${user.exportName}.findOne({ email });
    if (existing) return NextResponse.json({ success: false, error: 'Email already registered' }, { status: 409 });
    const { password, ...rest } = parsed.data as Record<string, unknown> & { password: string };
    const created = await ${user.exportName}.create({
      ...rest,
      email,
      ${pwField}: await bcrypt.hash(password, 10),
    });
    const safe = created.toObject();
    delete (safe as Record<string, unknown>).${pwField};
    const token = jwt.sign({ sub: String(created._id), email }, JWT_SECRET, { expiresIn: '7d' });
    const res = NextResponse.json({ success: true, data: { user: safe, token }, user: safe, token }, { status: 201 });
    res.cookies.set(TOKEN_COOKIE, token, { httpOnly: true, sameSite: 'lax', path: '/' });
    return res;
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Registration failed';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
`;
  }
  if (kind === 'me') {
    return `${header}
export async function GET(req: NextRequest) {
  try {
    const bearer = req.headers.get('authorization') || '';
    const token =
      req.cookies.get(TOKEN_COOKIE)?.value ||
      (bearer.startsWith('Bearer ') ? bearer.slice(7) : '');
    if (!token) return NextResponse.json({ success: false, error: 'Not authenticated' }, { status: 401 });
    let payload: { sub?: string };
    try {
      payload = jwt.verify(token, JWT_SECRET) as { sub?: string };
    } catch {
      return NextResponse.json({ success: false, error: 'Invalid token' }, { status: 401 });
    }
    await connectDB();
    const user = await ${user.exportName}.findById(payload.sub).lean();
    if (!user) return NextResponse.json({ success: false, error: 'Not found' }, { status: 404 });
    delete (user as Record<string, unknown>).${pwField};
    return NextResponse.json({ success: true, data: { user }, user });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to load session';
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
`;
  }
  // logout
  return `import { NextResponse } from 'next/server';

export async function POST() {
  const res = NextResponse.json({ success: true, data: { ok: true }, ok: true });
  res.cookies.set('token', '', { httpOnly: true, sameSite: 'lax', path: '/', maxAge: 0 });
  return res;
}
`;
}

export interface ApiGenResult {
  written: string[];
  skipped: string[];
}

/**
 * Generate every missing API file this module can produce deterministically.
 * Files it can't confidently map (reports, exotic actions) are returned in
 * `skipped` and remain for the LLM waves. Every file is parse-checked before
 * it is written — a generator bug can never plant a broken file.
 */
export async function generateDeterministicApis(
  id: string,
  missingApiFiles: string[],
): Promise<ApiGenResult> {
  const models = await parseModelsFromDisk(id);
  const written: string[] = [];
  const skipped: string[] = [];
  if (!models.length) return { written, skipped: [...missingApiFiles] };

  const userModel = findUserModel(models);
  const pwField = userModel ? passwordField(userModel) : null;

  for (const rel of missingApiFiles) {
    const norm = rel.replace(/\\/g, '/');
    const m = norm.match(/^app\/api\/(.+)\/route\.ts$/);
    if (!m) {
      skipped.push(rel);
      continue;
    }
    const segments = m[1].split('/');
    let source: string | null = null;

    const dynamicIndex = segments.findIndex(isDynamicSegment);

    if (segments[0] === 'auth' && segments.length === 2 && userModel && pwField) {
      const kind = segments[1] as 'login' | 'register' | 'me' | 'logout';
      if (['login', 'register', 'me', 'logout'].includes(kind)) {
        source = authRouteSource(kind, userModel, pwField);
      }
    } else if (dynamicIndex === -1) {
      const model = modelForApiSegments(segments, models);
      if (model) source = listRouteSource(model);
    } else if (dynamicIndex === segments.length - 1) {
      const model = modelForApiSegments(segments, models, dynamicIndex);
      if (model) source = idRouteSource(model);
    } else if (dynamicIndex === segments.length - 2) {
      const model = modelForApiSegments(segments, models, dynamicIndex);
      const target = model ? actionStatusTarget(model, segments[dynamicIndex + 1]) : null;
      if (model && target) source = actionRouteSource(model, target.field, target.value);
    }

    if (!source || syntaxErrors(norm, source).length > 0) {
      skipped.push(rel);
      continue;
    }
    const full = path.join(projectDir(id), norm);
    await fs.mkdir(path.dirname(full), { recursive: true });
    await fs.writeFile(full, source, 'utf8');
    written.push(norm);
  }

  return { written, skipped };
}
