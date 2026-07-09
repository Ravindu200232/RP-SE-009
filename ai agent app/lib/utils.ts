import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge conditional class names, de-duplicating conflicting Tailwind utilities. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Turn an arbitrary title into a filesystem/DB-safe slug. */
export function slugify(input: string): string {
  return (
    input
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || 'app'
  );
}

function stableShortHash(input: string): string {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36).padStart(6, '0').slice(-6);
}

/** MongoDB database names in Atlas/free tiers must stay short and ASCII-safe. */
export function safeMongoDbName(input: string): string {
  const clean =
    input
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9_-]+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-+|-+$/g, '') || 'app';
  const maxLength = 38;
  if (clean.length <= maxLength) return clean;

  const suffix = stableShortHash(clean);
  const prefixLength = maxLength - suffix.length - 1;
  const prefix = clean.slice(0, prefixLength).replace(/[-_]+$/g, '') || 'app';
  return `${prefix}-${suffix}`.slice(0, maxLength);
}
