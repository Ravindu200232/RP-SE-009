/**
 * Backend reliability kit — the app-agnostic backend "plumbing" that local
 * models get wrong over and over (auth register/login, password hashing,
 * session cookies, API response shape). Per the reliability-rules upgrade we do
 * NOT hardcode whole apps; we seed only the UNIVERSAL primitives + the auth
 * module (which is identical across every app), and let the LLM compose the
 * app-specific logic ON TOP by importing these. Uniqueness lives in the pages,
 * entities and workflows the LLM writes — never in "how register works".
 *
 * Seeded like the shadcn primitives (correct-by-construction, protected), and
 * only when the app actually needs it: the primitives whenever there's a
 * backend, the auth module only when the plan has an auth/login signal.
 */

import { promises as fs } from 'fs';
import path from 'path';
import { projectDir } from '../workspace/fs';

// ---- role helpers (kept in sync with credentials.ts seeding) ---------------

const KNOWN_ROLES = [
  'super admin', 'admin', 'manager', 'staff', 'front desk', 'receptionist',
  'housekeeper', 'cashier', 'accountant', 'inventory manager', 'teacher',
  'student', 'parent', 'customer', 'guest', 'supplier', 'sales agent',
  'dealer', 'buyer', 'seller', 'user',
];

function roleSlug(role: string): string {
  return role.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

export function authSignal(plans: Record<string, string>): boolean {
  const text = Object.values(plans).join('\n');
  return /\b(auth|authentication|login|register|sign[\s-]?in|sign[\s-]?up|session|jwt|password|rbac|role|permission)\b/i.test(
    text,
  );
}

/** Role slugs the app uses, for the User model enum + register default. */
export function rolesForAuth(plans: Record<string, string>): string[] {
  const text = Object.values(plans).join('\n');
  const roles = new Set<string>();
  for (const role of KNOWN_ROLES) {
    const re = new RegExp(`\\b${role.replace(/\s+/g, '\\s+')}\\b`, 'i');
    if (re.test(text)) roles.add(roleSlug(role));
  }
  if (roles.size === 0) {
    roles.add('admin');
    roles.add('user');
  }
  return [...roles].sort();
}

/** The role a public self-registration should get (a non-privileged one). */
function defaultRegisterRole(roles: string[]): string {
  for (const pref of ['user', 'customer', 'guest', 'student', 'member']) {
    if (roles.includes(pref)) return pref;
  }
  // Otherwise the least-privileged-looking role (avoid admin/manager/owner).
  const nonAdmin = roles.find((r) => !/admin|manager|owner|super/.test(r));
  return nonAdmin ?? roles[roles.length - 1] ?? 'user';
}

// ---- universal primitives (always seeded when there's a backend) -----------

const API_RESPONSE_TS = `import { NextResponse } from "next/server";

/**
 * Standard API responses. Every API route returns one of these two shapes so
 * the client always knows what to expect: { success: true, data } | { success: false, error }.
 */
export function apiSuccess<T>(data: T, status = 200) {
  return NextResponse.json({ success: true, data }, { status });
}

export function apiError(error: string, status = 400) {
  return NextResponse.json({ success: false, error }, { status });
}
`;

const AUTH_PASSWORD_TS = `import bcrypt from "bcryptjs";

/** Hash a plain-text password before storing it. NEVER store plain passwords. */
export function hashPassword(plain: string): Promise<string> {
  return bcrypt.hash(plain, 10);
}

/** Verify a plain-text password against a stored hash. */
export function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash);
}
`;

const AUTH_SESSION_TS = `import { cookies } from "next/headers";
import jwt from "jsonwebtoken";

const COOKIE_NAME = "auth_token";
const SECRET = process.env.AUTH_SECRET || "dev-secret-change-me";
const MAX_AGE = 60 * 60 * 24 * 7; // 7 days

export interface SessionPayload {
  userId: string;
  role: string;
}

/** Sign a JWT and store it in an httpOnly cookie. */
export async function createSession(payload: SessionPayload): Promise<void> {
  const token = jwt.sign(payload, SECRET, { expiresIn: "7d" });
  const store = await cookies();
  store.set(COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: MAX_AGE,
  });
}

/** Read + verify the current session, or null if not signed in. */
export async function getSession(): Promise<SessionPayload | null> {
  const store = await cookies();
  const token = store.get(COOKIE_NAME)?.value;
  if (!token) return null;
  try {
    return jwt.verify(token, SECRET) as unknown as SessionPayload;
  } catch {
    return null;
  }
}

/** Clear the session cookie (logout). */
export async function destroySession(): Promise<void> {
  const store = await cookies();
  store.delete(COOKIE_NAME);
}
`;

// ---- auth module (seeded only when the plan needs auth) --------------------

function userModelTs(roles: string[]): string {
  const def = defaultRegisterRole(roles);
  const union = roles.map((r) => `"${r}"`).join(' | ');
  const enumList = roles.map((r) => `"${r}"`).join(', ');
  return `import mongoose, { Schema, Document } from "mongoose";

export type UserRole = ${union};

export interface IUser extends Document {
  email: string;
  passwordHash: string;
  name: string;
  role: UserRole;
  status: "active" | "inactive";
  createdAt: Date;
  updatedAt: Date;
}

const UserSchema = new Schema<IUser>(
  {
    email: { type: String, required: true, unique: true, lowercase: true, trim: true, index: true },
    passwordHash: { type: String, required: true },
    name: { type: String, required: true },
    role: { type: String, enum: [${enumList}], default: "${def}" },
    status: { type: String, enum: ["active", "inactive"], default: "active" },
  },
  { timestamps: true },
);

export const User = mongoose.models.User || mongoose.model<IUser>("User", UserSchema);
`;
}

const REGISTER_TS = (def: string) => `import { NextRequest } from "next/server";
import { z } from "zod";
import { connectDB } from "@/lib/db";
import { User } from "@/lib/models/user";
import { hashPassword } from "@/lib/auth/password";
import { createSession } from "@/lib/auth/session";
import { apiSuccess, apiError } from "@/lib/api/response";

// Field-tolerant: the register FORM may send name, full_name or fullName.
const schema = z
  .object({
    name: z.string().optional(),
    full_name: z.string().optional(),
    fullName: z.string().optional(),
    email: z.string().email("Invalid email address"),
    password: z.string().min(8, "Password must be at least 8 characters"),
  })
  .passthrough();

export async function POST(req: NextRequest) {
  try {
    await connectDB();
    const parsed = schema.safeParse(await req.json());
    if (!parsed.success) return apiError(parsed.error.errors[0].message, 400);

    const name = (parsed.data.name || parsed.data.full_name || parsed.data.fullName || "").trim();
    if (name.length < 2) return apiError("Name must be at least 2 characters", 400);

    const email = parsed.data.email.toLowerCase();
    const existing = await User.findOne({ email });
    if (existing) return apiError("Email already in use", 409);

    const user = await User.create({
      name,
      email,
      passwordHash: await hashPassword(parsed.data.password),
      role: "${def}",
    });

    await createSession({ userId: String(user._id), role: user.role });
    return apiSuccess(
      { id: user._id, name: user.name, email: user.email, role: user.role },
      201,
    );
  } catch (err) {
    console.error("register error", err);
    return apiError("Registration failed", 500);
  }
}
`;

const LOGIN_TS = `import { NextRequest } from "next/server";
import { z } from "zod";
import { connectDB } from "@/lib/db";
import { User } from "@/lib/models/user";
import { verifyPassword } from "@/lib/auth/password";
import { createSession } from "@/lib/auth/session";
import { apiSuccess, apiError } from "@/lib/api/response";

const schema = z
  .object({
    email: z.string().optional(),
    username: z.string().optional(),
    password: z.string().min(1, "Password is required"),
  })
  .passthrough();

export async function POST(req: NextRequest) {
  try {
    await connectDB();
    const parsed = schema.safeParse(await req.json());
    if (!parsed.success) return apiError(parsed.error.errors[0].message, 400);

    const email = (parsed.data.email || parsed.data.username || "").toLowerCase().trim();
    if (!email) return apiError("Email is required", 400);
    const user = await User.findOne({ email });
    if (!user) return apiError("Invalid email or password", 401);

    const ok = await verifyPassword(parsed.data.password, user.passwordHash);
    if (!ok) return apiError("Invalid email or password", 401);

    await createSession({ userId: String(user._id), role: user.role });
    return apiSuccess({ id: user._id, name: user.name, email: user.email, role: user.role });
  } catch (err) {
    console.error("login error", err);
    return apiError("Login failed", 500);
  }
}
`;

const LOGOUT_TS = `import { destroySession } from "@/lib/auth/session";
import { apiSuccess } from "@/lib/api/response";

export async function POST() {
  await destroySession();
  return apiSuccess({ loggedOut: true });
}
`;

const ME_TS = `import { connectDB } from "@/lib/db";
import { User } from "@/lib/models/user";
import { getSession } from "@/lib/auth/session";
import { apiSuccess, apiError } from "@/lib/api/response";

export async function GET() {
  const session = await getSession();
  if (!session) return apiError("Not authenticated", 401);
  try {
    await connectDB();
    const user = await User.findById(session.userId).select("-passwordHash");
    if (!user) return apiError("User not found", 404);
    return apiSuccess({ id: user._id, name: user.name, email: user.email, role: user.role });
  } catch (err) {
    console.error("me error", err);
    return apiError("Failed to load session", 500);
  }
}
`;

export interface BackendKitResult {
  seeded: string[];
  auth: boolean;
  paths: string[]; // all kit-owned paths, for protection
}

/**
 * Seed the reliability primitives (always, when there's a backend) + the auth
 * module (only when the plan needs auth). Returns the paths it owns so the build
 * can protect them from being overwritten by the model.
 */
export async function seedBackendKit(
  id: string,
  plans: Record<string, string>,
): Promise<BackendKitResult> {
  const dir = projectDir(id);
  const write = async (rel: string, content: string) => {
    const dest = path.join(dir, rel);
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.writeFile(dest, content, 'utf8');
  };

  const seeded: string[] = [];
  const primitives: Array<[string, string]> = [
    ['lib/api/response.ts', API_RESPONSE_TS],
    ['lib/auth/password.ts', AUTH_PASSWORD_TS],
    ['lib/auth/session.ts', AUTH_SESSION_TS],
  ];
  for (const [rel, content] of primitives) {
    await write(rel, content);
    seeded.push(rel);
  }

  const auth = authSignal(plans);
  const authPaths: string[] = [];
  if (auth) {
    const roles = rolesForAuth(plans);
    const def = defaultRegisterRole(roles);
    const authFiles: Array<[string, string]> = [
      ['lib/models/user.ts', userModelTs(roles)],
      ['app/api/auth/register/route.ts', REGISTER_TS(def)],
      ['app/api/auth/login/route.ts', LOGIN_TS],
      ['app/api/auth/logout/route.ts', LOGOUT_TS],
      ['app/api/auth/me/route.ts', ME_TS],
    ];
    for (const [rel, content] of authFiles) {
      await write(rel, content);
      seeded.push(rel);
      authPaths.push(rel);
    }
  }

  return { seeded, auth, paths: [...primitives.map(([p]) => p), ...authPaths] };
}
