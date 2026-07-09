import { promises as fs } from 'fs';
import path from 'path';
import bcrypt from 'bcryptjs';
import mongoose from 'mongoose';
import { projectDir } from '../workspace/fs';

const KNOWN_ROLES = [
  'super admin',
  'admin',
  'manager',
  'staff',
  'front desk',
  'receptionist',
  'housekeeper',
  'cashier',
  'accountant',
  'inventory manager',
  'teacher',
  'student',
  'parent',
  'customer',
  'guest',
  'supplier',
  'sales agent',
  'dealer',
  'buyer',
  'seller',
  'user',
];

function hasAuthSignal(text: string): boolean {
  return /\b(auth|authentication|login|register|session|jwt|password|rbac|role|permission|profile)\b/i.test(
    text,
  );
}

function titleCase(role: string): string {
  return role
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(' ');
}

function roleSlug(role: string): string {
  return role
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function passwordFor(role: string): string {
  const compact = titleCase(role).replace(/[^A-Za-z0-9]/g, '') || 'User';
  return `${compact}@12345`;
}

function rolesFromPlans(plans: Record<string, string>): string[] {
  const text = Object.values(plans).join('\n');
  if (!hasAuthSignal(text)) return [];

  const roles = new Set<string>();
  for (const role of KNOWN_ROLES) {
    const re = new RegExp(`\\b${role.replace(/\s+/g, '\\s+')}\\b`, 'i');
    if (re.test(text)) roles.add(role);
  }

  if (roles.size === 0) {
    roles.add('admin');
    roles.add('user');
  }

  return [...roles].sort((a, b) => a.localeCompare(b));
}

export async function writeCredentialsTxt(
  projectId: string,
  appName: string,
  plans: Record<string, string>,
): Promise<boolean> {
  const roles = rolesFromPlans(plans);
  if (!roles.length) return false;

  const lines = [
    `${appName || 'Generated app'} development credentials`,
    '',
    'These accounts are generated for local development and seeded-data login flows.',
    'Email format: role-slug@example.com',
    '',
    ...roles.flatMap((role) => {
      const slug = roleSlug(role);
      return [
        `Role: ${titleCase(role)}`,
        `Email: ${slug}@example.com`,
        `Password: ${passwordFor(role)}`,
        '',
      ];
    }),
  ];

  await fs.writeFile(path.join(projectDir(projectId), 'credentials.txt'), lines.join('\n'), 'utf8');
  return true;
}

/**
 * DETERMINISTICALLY seed the credentials.txt role accounts into the generated
 * app's own MongoDB database, so login works on first run. The prompts ask the
 * model to seed users, but a 12B model routinely writes a login route that only
 * CHECKS credentials (seen live) — making credentials.txt a broken promise.
 * This runs builder-side at the end of every build pass (idempotent upserts):
 * 1. Find the users model file (a lib/models/*.ts with a password-ish field)
 *    and read the exact field names it uses.
 * 2. Hash each role password with the generated app's own bcryptjs.
 * 3. Upsert one user per role straight into the app's database (raw driver,
 *    field names matched to the schema; a role_id ref also upserts Role docs).
 */
export async function ensureSeededUsers(
  projectId: string,
  plans: Record<string, string>,
): Promise<{ seeded: number; reason?: string }> {
  const roles = rolesFromPlans(plans);
  if (!roles.length) return { seeded: 0, reason: 'no auth roles planned' };

  const dir = projectDir(projectId);

  // The generated app's DB connection string (written by writeProjectEnv).
  let uri = '';
  try {
    const env = await fs.readFile(path.join(dir, '.env.local'), 'utf8');
    uri = (env.match(/^MONGODB_URI=(.+)$/m) ?? [])[1]?.trim() ?? '';
  } catch {
    /* fall through */
  }
  if (!uri) return { seeded: 0, reason: 'no MONGODB_URI in project env' };

  // Locate the users model + its real field names.
  const modelsDir = path.join(dir, 'lib', 'models');
  let userSrc = '';
  try {
    for (const f of await fs.readdir(modelsDir)) {
      if (!f.endsWith('.ts') || f === 'index.ts') continue;
      const src = await fs.readFile(path.join(modelsDir, f), 'utf8');
      if (/password/i.test(src) && /email/i.test(src)) {
        userSrc = src;
        break;
      }
    }
  } catch {
    /* fall through */
  }
  if (!userSrc) return { seeded: 0, reason: 'no users model with password field' };

  const modelName = (userSrc.match(/mongoose\.model(?:<[^>]*>)?\(\s*["']([^"']+)["']/) ?? [])[1];
  if (!modelName) return { seeded: 0, reason: 'could not read users model name' };
  const passwordField =
    (userSrc.match(/^\s*([A-Za-z0-9_]*password[A-Za-z0-9_]*)\s*:/im) ?? [])[1] ?? 'password_hash';
  const nameField = /^\s*full_name\s*:/m.test(userSrc)
    ? 'full_name'
    : /^\s*fullName\s*:/m.test(userSrc)
      ? 'fullName'
      : 'name';
  const roleStringField = /^\s*role\s*:/m.test(userSrc)
    ? 'role'
    : /^\s*role_key\s*:/m.test(userSrc)
      ? 'role_key'
      : null;
  const roleRefField = /^\s*(role_id|roleId)\s*:/m.exec(userSrc)?.[1] ?? null;

  // Standard $2a/$2b bcrypt hashes — the generated app's bcryptjs compare()
  // accepts them regardless of which side produced the hash.
  const hash = (pw: string) => bcrypt.hashSync(pw, 10);

  const pluralize = mongoose.pluralize();
  const usersCollection = pluralize ? pluralize(modelName) : `${modelName.toLowerCase()}s`;

  const conn = mongoose.createConnection(uri, { bufferCommands: false });
  try {
    await conn.asPromise();
    const users = conn.collection(usersCollection);

    // role_id ref mode: upsert Role docs first so users can link to them.
    const roleIds = new Map<string, unknown>();
    if (roleRefField) {
      try {
        const roleSrc = await fs.readFile(path.join(modelsDir, 'roles.ts'), 'utf8');
        const roleModelName =
          (roleSrc.match(/mongoose\.model(?:<[^>]*>)?\(\s*["']([^"']+)["']/) ?? [])[1] ?? 'Role';
        const rolesCollection = pluralize ? pluralize(roleModelName) : 'roles';
        const rolesCol = conn.collection(rolesCollection);
        for (const role of roles) {
          const slug = roleSlug(role);
          const doc: Record<string, unknown> = {};
          if (/^\s*role_key\s*:/m.test(roleSrc)) doc.role_key = slug;
          if (/^\s*role_name\s*:/m.test(roleSrc)) doc.role_name = titleCase(role);
          if (/^\s*name\s*:/m.test(roleSrc) && !doc.role_name) doc.name = titleCase(role);
          if (!Object.keys(doc).length) doc.role_key = slug;
          const filter = { [Object.keys(doc)[0]]: Object.values(doc)[0] };
          await rolesCol.updateOne(filter, { $setOnInsert: doc }, { upsert: true });
          const saved = await rolesCol.findOne(filter);
          if (saved?._id) roleIds.set(role, saved._id);
        }
      } catch {
        /* roles model missing — users are seeded without the ref */
      }
    }

    let seeded = 0;
    for (const role of roles) {
      const slug = roleSlug(role);
      const email = `${slug}@example.com`;
      const doc: Record<string, unknown> = {
        email,
        [passwordField]: hash(passwordFor(role)),
        [nameField]: `${titleCase(role)} User`,
        status: 'active',
      };
      if (roleStringField) doc[roleStringField] = slug;
      if (roleRefField && roleIds.has(role)) doc[roleRefField] = roleIds.get(role);
      const res = await users.updateOne({ email }, { $setOnInsert: doc }, { upsert: true });
      if (res.upsertedCount > 0) seeded += 1;
    }
    return { seeded };
  } finally {
    await conn.close().catch(() => {});
  }
}
