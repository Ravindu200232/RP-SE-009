import type { NextRequest } from 'next/server';
import { APP_TYPES, getAppType } from '@/lib/appTypes';
import { streamOllamaChat } from '@/lib/llm/ollama';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 300;

type Detection = {
  appType: string;
  hasBackend: boolean;
  name: string;
  confidence: number;
  reason: string;
  source: 'gemma' | 'fallback';
};

const VALID_TYPES = new Set(APP_TYPES.map((t) => t.key));
const DETECTION_PROMPT_CHAR_CAP = Number(process.env.DETECTION_PROMPT_CHAR_CAP || 16000);
const DETECTION_CTX = Math.max(8192, Number(process.env.OLLAMA_DETECTION_CTX || 32768));

function includesAny(text: string, words: string[]): boolean {
  return words.some((word) => text.includes(word));
}

function titleCaseName(input: string, fallback: string): string {
  const firstLine = input
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line && !/^#+\s*/.test(line));
  const cleaned = (firstLine || fallback)
    .replace(/^build\s+(a|an|the)?\s*/i, '')
    .replace(/^create\s+(a|an|the)?\s*/i, '')
    .replace(/^srs\s*[:\-]\s*/i, '')
    .replace(/[^\w\s&-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const words = cleaned.split(' ').filter(Boolean).slice(0, 7);
  if (words.length === 0) return fallback;
  return words
    .map((word) => (word.length <= 3 ? word : word[0].toUpperCase() + word.slice(1)))
    .join(' ');
}

function findStringByKeys(value: unknown, keys: string[], depth = 0): string {
  if (!value || typeof value !== 'object' || depth > 6) return '';
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = findStringByKeys(item, keys, depth + 1);
      if (found) return found;
    }
    return '';
  }

  const record = value as Record<string, unknown>;
  for (const key of keys) {
    const hit = Object.entries(record).find(([k]) => k.toLowerCase() === key);
    if (typeof hit?.[1] === 'string' && hit[1].trim()) return hit[1].trim();
  }
  for (const child of Object.values(record)) {
    const found = findStringByKeys(child, keys, depth + 1);
    if (found) return found;
  }
  return '';
}

function structuredName(input: string): string {
  const raw = input.trim().replace(/^```(?:json)?/i, '').replace(/```$/i, '').trim();
  if (!raw.startsWith('{')) return '';
  try {
    const parsed = JSON.parse(raw) as unknown;
    return findStringByKeys(parsed, ['project_name', 'app_name', 'system_name', 'name']);
  } catch {
    return '';
  }
}

function fallbackDetect(prompt: string): Detection {
  const text = prompt.toLowerCase();
  let appType = 'dynamic';

  const enterpriseSignals = [
    'pos',
    'inventory',
    'supplier',
    'purchase order',
    'staff management',
    'role-based',
    'rbac',
    'audit log',
    'reports',
    'analytics',
    'admin dashboard',
    'multi-module',
    'accountant',
    'warehouse',
  ].filter((word) => text.includes(word)).length;

  if (
    enterpriseSignals >= 4 ||
    includesAny(text, [
      'retail pos',
      'inventory management',
      'enterprise-grade',
      'business management platform',
    ])
  ) {
    appType = 'enterprise';
  } else if (includesAny(text, ['course', 'lesson', 'student', 'teacher', 'grading', 'lms'])) {
    appType = 'lms';
  } else if (includesAny(text, ['cart', 'checkout', 'product catalog', 'storefront', 'order'])) {
    appType = 'ecommerce';
  } else if (includesAny(text, ['marketplace', 'seller', 'buyer', 'listing'])) {
    appType = 'marketplace';
  } else if (includesAny(text, ['hotel', 'reservation', 'booking', 'room', 'audit log', 'report'])) {
    appType = 'enterprise';
  } else if (includesAny(text, ['multi tenant', 'workspace', 'subscription', 'billing', 'saas'])) {
    appType = 'saas';
  } else if (includesAny(text, ['admin portal', 'customer portal', 'role based portal'])) {
    appType = 'portal';
  } else if (includesAny(text, ['cms', 'publish', 'editorial', 'content authoring'])) {
    appType = 'cms';
  } else if (includesAny(text, ['blog', 'post detail', 'authoring'])) {
    appType = 'blog';
  } else if (includesAny(text, ['social', 'feed', 'follow', 'profile', 'likes'])) {
    appType = 'social';
  } else if (includesAny(text, ['landing page', 'marketing page', 'hero section'])) {
    appType = 'landing';
  } else if (includesAny(text, ['portfolio', 'projects gallery'])) {
    appType = 'portfolio';
  } else if (includesAny(text, ['calculator', 'converter', 'single-purpose', 'utility'])) {
    appType = 'utility';
  } else if (includesAny(text, ['pwa', 'offline', 'installable'])) {
    appType = 'pwa';
  } else if (includesAny(text, ['multi-page', 'many pages', 'routed pages'])) {
    appType = 'mpa';
  }

  const type = getAppType(appType) ?? getAppType('dynamic')!;
  const needsBackend = includesAny(text, [
    'mongodb',
    'mongoose',
    'database',
    'api',
    'crud',
    'auth',
    'login',
    'register',
    'admin',
    'dashboard',
    'report',
    'reservation',
    'booking',
    'order',
    'inventory',
    'payment',
  ]);

  const noBackend = includesAny(text, ['no database', 'static only', 'no backend', 'client-side only']);

  return {
    appType: type.key,
    hasBackend: noBackend ? false : needsBackend || type.defaultBackend,
    name: structuredName(prompt) || titleCaseName(prompt, `${type.label} app`),
    confidence: enterpriseSignals >= 4 ? 0.85 : 0.55,
    reason:
      enterpriseSignals >= 4
        ? 'Large structured SRS classified from enterprise module signals.'
        : 'Keyword fallback after classifier output was unavailable.',
    source: 'fallback',
  };
}

function shouldSkipLlmDetection(prompt: string): boolean {
  if (prompt.length >= Number(process.env.DETECTION_LLM_SKIP_CHAR_THRESHOLD || 50000)) {
    return true;
  }
  const stripped = prompt.trim().replace(/^```(?:json)?/i, '').replace(/```$/i, '').trim();
  if (stripped.startsWith('{') && stripped.length >= 20000) return true;
  return false;
}

function extractJson(text: string): Record<string, unknown> | null {
  const trimmed = text.trim().replace(/^```(?:json)?/i, '').replace(/```$/i, '').trim();
  const start = trimmed.indexOf('{');
  const end = trimmed.lastIndexOf('}');
  if (start < 0 || end <= start) return null;
  try {
    return JSON.parse(trimmed.slice(start, end + 1)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function normalizeDetection(raw: Record<string, unknown>, prompt: string): Detection | null {
  const appType = typeof raw.appType === 'string' ? raw.appType.trim() : '';
  if (!VALID_TYPES.has(appType)) return null;
  const type = getAppType(appType);
  if (!type) return null;
  const hasBackend =
    typeof raw.hasBackend === 'boolean' ? raw.hasBackend : type.defaultBackend;
  const rawName = typeof raw.name === 'string' ? raw.name.trim() : '';
  const name = rawName
    ? rawName.replace(/\s+/g, ' ').slice(0, 80)
    : titleCaseName(prompt, `${type.label} app`);
  const confidence =
    typeof raw.confidence === 'number' && Number.isFinite(raw.confidence)
      ? Math.max(0, Math.min(1, raw.confidence))
      : 0.75;
  const reason =
    typeof raw.reason === 'string' && raw.reason.trim()
      ? raw.reason.trim().slice(0, 180)
      : `Detected ${type.label} from the user request.`;

  return { appType, hasBackend, name, confidence, reason, source: 'gemma' };
}

export async function POST(req: NextRequest) {
  let body: { prompt?: unknown };
  try {
    body = await req.json();
  } catch {
    return new Response('Invalid JSON body', { status: 400 });
  }

  const prompt =
    typeof body.prompt === 'string'
      ? body.prompt.trim()
      : Array.isArray(body.prompt)
        ? body.prompt.map((part) => String(part)).join('\n').trim()
        : '';
  if (!prompt) return new Response('No prompt provided', { status: 400 });
  if (shouldSkipLlmDetection(prompt)) {
    return Response.json(fallbackDetect(prompt));
  }
  const classifierPrompt =
    prompt.length > DETECTION_PROMPT_CHAR_CAP
      ? `${prompt.slice(0, DETECTION_PROMPT_CHAR_CAP)}

[Input truncated for app-type classification only. Full input is still used by the planner.]`
      : prompt;

  const typeList = APP_TYPES.map(
    (t) =>
      `- ${t.key}: ${t.label}; scale=${t.scale}; defaultBackend=${t.defaultBackend}; ${t.description}`,
  ).join('\n');

  const messages = [
    {
      role: 'system' as const,
      content:
        'You classify app-generation requests for a local Next.js builder. Return ONLY compact JSON, no markdown.',
    },
    {
      role: 'user' as const,
      content: `Choose exactly one appType key from this list and decide whether MongoDB/API backend is required.

Available app types:
${typeList}

Return this JSON shape only:
{"appType":"enterprise","hasBackend":true,"name":"Short App Name","confidence":0.9,"reason":"short reason"}

Rules:
- If the request is an SRS for a large management system with many modules, roles, reports, audit, reservations, inventory, finance, HR, or operations, choose "enterprise".
- If it is education/course/student/teacher/grading, choose "lms".
- If it is store/cart/checkout/orders, choose "ecommerce".
- If it has auth, roles, CRUD, reports, dashboards, API, MongoDB, or persistent business data, hasBackend must be true.
- If it explicitly says static/no database/client-only, hasBackend can be false.

User request:
"""
${classifierPrompt}
"""`,
    },
  ];

  let full = '';
  try {
    for await (const delta of streamOllamaChat(messages, {
      context: 'plan',
      numCtx: DETECTION_CTX,
      think: false,
      temperature: 0,
      signal: req.signal,
    })) {
      full += delta;
    }
    const json = extractJson(full);
    const normalized = json ? normalizeDetection(json, prompt) : null;
    return Response.json(normalized ?? fallbackDetect(prompt));
  } catch (err) {
    console.error('[detect-app]', err);
    return Response.json(fallbackDetect(prompt));
  }
}
