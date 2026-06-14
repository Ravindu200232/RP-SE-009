'use client';
// Entity metadata helpers over site.js - the generic CRUD pages resolve the
// active entity from the URL slug and render columns/forms from its fields.
import { site } from '@/lib/site';

export function allEntities() {
  return Array.isArray(site.entities) ? site.entities : [];
}

export function entityBySlug(slug) {
  return allEntities().find((e) => e.slug === slug) || null;
}

export function fieldLabel(f) {
  return f.label || String(f.name || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function listColumns(entity, max = 4) {
  const fields = (entity?.fields || []).filter((f) => f.type !== 'textarea');
  return fields.slice(0, max);
}

export function statusVariant(value) {
  const v = String(value || '').toLowerCase();
  if (['active', 'approved', 'completed', 'paid', 'available', 'confirmed', 'in stock'].includes(v)) return 'success';
  if (['pending', 'processing', 'scheduled', 'on hold'].includes(v)) return 'warning';
  if (['inactive', 'cancelled', 'canceled', 'rejected', 'overdue', 'out of stock'].includes(v)) return 'destructive';
  return 'secondary';
}
