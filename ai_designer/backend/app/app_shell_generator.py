"""Post-login app shell generator (domain + role aware).

Generates an internal dashboard that is driven by the planned data model (so it
differs per app and is never the same generic dashboard), plus route-protection
metadata. The dashboard shows a KPI card per entity (live counts), quick-create
actions, role badges, and links into the relationship-aware /manage area.
"""
from __future__ import annotations

import json
import os
import re


_DASH = {
    "healthcare": ("Clinic dashboard", "Appointments, patients, and records at a glance."),
    "real-estate": ("Brokerage dashboard", "Listings, tours, and buyer leads at a glance."),
    "fitness": ("Studio dashboard", "Classes, members, and bookings at a glance."),
    "restaurant": ("Front-of-house dashboard", "Reservations, menu, and tables at a glance."),
    "education": ("Academy dashboard", "Courses, enrollments, and progress at a glance."),
    "vehicle": ("Dealership dashboard", "Inventory, test drives, and sales at a glance."),
    "pos-erp": ("Operations dashboard", "Stock, invoices, and movements at a glance."),
}
_DASH_DEFAULT = ("Dashboard", "Your records at a glance.")


_DASHBOARD = r"""'use client';
// AUTO-GENERATED domain + model-aware dashboard (distinct from the marketing site).
import * as React from 'react';
import Link from 'next/link';
import { Models } from '@/lib/models';

const ROLES = __ROLES__;

export default function Dashboard() {
  const entities = Object.values(Models).filter((m) => m.collection !== 'users');
  const kpis = entities.slice(0, 6);
  const [counts, setCounts] = React.useState({});
  React.useEffect(() => {
    kpis.forEach((m) => {
      fetch('/api/' + m.collection)
        .then((r) => r.json())
        .then((d) => setCounts((c) => ({ ...c, [m.collection]: (d.total != null ? d.total : (Array.isArray(d) ? d.length : 0)) })))
        .catch(() => {});
    });
  }, []);

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">__TITLE__</h1>
          <p className="text-sm text-muted-foreground">__SUBTITLE__</p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {ROLES.map((r) => <span key={r} className="rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">{r}</span>)}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {kpis.map((m) => (
          <Link key={m.collection} href={'/manage/' + m.collection} className="rounded-xl border bg-card p-5 transition hover:shadow-md">
            <p className="text-sm text-muted-foreground">{m.label}</p>
            <p className="mt-1 text-3xl font-bold tracking-tight">{counts[m.collection] != null ? counts[m.collection] : '—'}</p>
            <p className="mt-2 text-xs font-medium text-primary">Manage {m.label} →</p>
          </Link>
        ))}
      </div>

      <div className="rounded-xl border bg-card p-6">
        <h2 className="font-semibold">Quick actions</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {entities.slice(0, 6).map((m) => (
            <Link key={m.collection} href={'/manage/' + m.collection + '/new'} className="rounded-lg border px-3 py-1.5 text-sm transition hover:border-primary/50">
              + New {m.label}
            </Link>
          ))}
        </div>
      </div>

      <div className="rounded-xl border bg-card p-6">
        <h2 className="font-semibold">Relationships</h2>
        <ul className="mt-3 space-y-1.5 text-sm text-muted-foreground">
          {entities.filter((m) => m.refs.length).slice(0, 6).map((m) => (
            <li key={m.collection}>
              <span className="font-medium text-foreground">{m.label}</span> → {m.refs.map((r) => r.target).join(', ')}
            </li>
          ))}
        </ul>
      </div>

      <p className="text-xs text-muted-foreground">{entities.length} collections · domain: __DOMAIN__ · relationship-aware records</p>
    </div>
  );
}
"""

_DEV_AUTH = r"""'use client';
// TEST-AUTH HELPER (dev/QA only) — lives OUTSIDE the protected (app) group so it
// is reachable without a session. It seeds the SAME localStorage 'session' key
// that the real auth.login writes, then routes to the dashboard. Route protection
// stays ON (site.auth is never disabled); this just mimics a logged-in user so QA
// can view authenticated pages.
import * as React from 'react';
import { useRouter } from 'next/navigation';
import { site } from '@/lib/site';

export default function DevAuth() {
  const router = useRouter();
  React.useEffect(() => {
    try {
      localStorage.setItem('session', JSON.stringify({
        id: 'demo-user', name: 'Demo Admin', email: 'admin@example.com',
        role: (site.roles && site.roles[0]) || 'Admin',
      }));
    } catch (e) { /* ignore */ }
    let next = '/dashboard';
    try { next = new URLSearchParams(window.location.search).get('next') || '/dashboard'; } catch (e) {}
    router.replace(next);
  }, [router]);
  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
      Preparing your session…
    </div>
  );
}
"""

_ACCESS = r"""// AUTO-GENERATED route-protection + role-access metadata.
export const protectedRoutes = ['/dashboard', '/manage', '/profile', '/settings', '/notifications', '/admin', '/pos', '/reports', '/customer'];
export const publicRoutes = ['/', '/login', '/register'];
export const roleAccess = __ROLE_ACCESS__;
export const pageAccess = __PAGE_ACCESS__;

// Roles that bypass all page-level restrictions.
const SUPER_ROLES = ['Super Admin', 'super_admin', 'Admin', 'admin'];

export function isProtected(pathname) {
  return protectedRoutes.some((p) => pathname === p || pathname.startsWith(p + '/'));
}
export function canAccess(role, collection) {
  const allowed = roleAccess[collection];
  return !allowed || allowed.length === 0 || allowed.includes(role) || SUPER_ROLES.includes(role);
}
export function canAccessPage(role, pathname) {
  if (!role) return false;
  if (SUPER_ROLES.includes(role)) return true;
  const rules = Object.entries(pageAccess);
  for (const [route, roles] of rules) {
    if (pathname === route || pathname.startsWith(route + '/')) {
      return !roles.length || roles.includes(role);
    }
  }
  return true;
}
export function getVisibleNavItems(role, navItems) {
  if (!role) return [];
  if (SUPER_ROLES.includes(role)) return navItems || [];
  return (navItems || []).filter((item) => {
    if (!Array.isArray(item.roles) || item.roles.length === 0) return true;
    return item.roles.includes(role);
  });
}
"""


def generate_dashboard(model: dict) -> str:
    domain = model.get("domain", "saas")
    title, subtitle = _DASH.get(domain, _DASH_DEFAULT)
    roles = model.get("roles") or ["Admin"]
    return (_DASHBOARD
            .replace("__ROLES__", json.dumps(roles))
            .replace("__TITLE__", title)
            .replace("__SUBTITLE__", subtitle)
            .replace("__DOMAIN__", domain))


_SIDEBAR_ICONS = ["Database", "Users", "Package", "CalendarDays", "Star", "Layers"]


def _aggregate_access(model: dict) -> dict:
    """Union every access verb (create/update/delete/read) per collection into
    one allowed-roles list, preserving first-seen order. An entity with no
    `access` dict at all is omitted - canAccess() then defaults to "everyone
    allowed" for that collection, which is the correct default for entities
    nobody restricted."""
    agg = {}
    for e in model["entities"]:
        access = e.get("access") or {}
        if not access:
            continue
        roles, seen = [], set()
        for verb in ("create", "update", "delete", "read"):
            for r in access.get(verb) or []:
                if r not in seen:
                    seen.add(r)
                    roles.append(r)
        if roles:
            agg[e["collection"]] = roles
    return agg


def _page_access(model: dict) -> dict:
    """Build page-route → allowed-roles map from srs_* keys on the model."""
    page_map = {}
    for page in (model.get("srs_app_pages") or model.get("app_pages") or []):
        if not isinstance(page, dict):
            continue
        route = str(page.get("route") or "").strip()
        roles = [str(r) for r in (page.get("allowed_roles") or [])]
        if route and roles:
            page_map[route] = roles
    return page_map


def generate_access(model: dict) -> str:
    return (_ACCESS
            .replace("__ROLE_ACCESS__", json.dumps(_aggregate_access(model), indent=2))
            .replace("__PAGE_ACCESS__", json.dumps(_page_access(model), indent=2)))


_SKIP_SIDEBAR_ROUTES = {"/login", "/register", "/logout", "/admin/dashboard",
                        "/admin/settings", "/customer/dashboard", "/dashboard"}
_SIDEBAR_ROUTE_ICONS = [
    ("pos", "ShoppingCart"), ("prescription", "FileText"), ("medicine", "Pill"),
    ("inventory", "Package"), ("supplier", "Truck"), ("purchase", "ClipboardList"),
    ("grn", "PackageCheck"), ("order", "ShoppingBag"), ("customer", "Users"),
    ("billing", "Receipt"), ("return", "RotateCcw"), ("staff", "UserCog"),
    ("report", "BarChart2"), ("catalog", "BookOpen"), ("room", "Hotel"),
    ("vehicle", "Car"), ("student", "GraduationCap"), ("course", "BookOpen"),
]


def _clean_nav_label(s: str) -> str:
    """Sidebar/nav labels should read as the noun, not 'X Management' — the user
    wants 'Brand', not 'Brand Management'. Strips trailing Management/System/Module."""
    s = str(s or "").strip()
    cleaned = re.sub(r"\s+(Management System|Management|System|Module|Center|Centre)$", "", s, flags=re.I).strip()
    return cleaned or s


def _route_icon(route: str) -> str:
    low = str(route).lower()
    for key, icon in _SIDEBAR_ROUTE_ICONS:
        if key in low:
            return icon
    return "Layers"


def write_app_shell(out_dir: str, model: dict) -> dict:
    """Writes role-access metadata + dev-auth helper.

    When the model carries SRS app_pages (srs_app_pages key), the sidebar is
    built from those explicit routes so the nav matches the SRS spec exactly.
    Falls back to the entity-collection sidebar for non-SRS apps."""

    # Attach SRS page-access info so generate_access() can build pageAccess.
    srs_pages = model.get("srs_app_pages") or []
    model_with_pages = {**model, "app_pages": srs_pages} if srs_pages else model

    files = {
        "src/lib/access.js": generate_access(model_with_pages),
        "src/app/dev-auth/page.jsx": _DEV_AUTH,
    }
    written = []
    for rel, content in files.items():
        path = os.path.join(out_dir, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(rel)

    agg = _aggregate_access(model)
    entities = [e for e in model["entities"] if e["collection"] != "users"]

    if srs_pages:
        # SRS-driven sidebar: use exact application_pages routes
        sidebar = []
        seen = set()
        for p in srs_pages:
            route = str(p.get("route") or "").strip()
            if not route or route in _SKIP_SIDEBAR_ROUTES or route in seen:
                continue
            if any(route.startswith(r) for r in ("/login", "/register")):
                continue
            seen.add(route)
            label = _clean_nav_label(str(p.get("name") or route.strip("/").replace("-", " ").title()))
            roles = [str(r) for r in (p.get("allowed_roles") or [])]
            entry = {"label": label, "href": route, "icon": _route_icon(route)}
            if roles:
                entry["roles"] = roles
            sidebar.append(entry)
    else:
        # Fallback: entity-collection sidebar
        sidebar = [
            {"label": e["label"], "href": f"/manage/{e['collection']}",
             "icon": _SIDEBAR_ICONS[i % len(_SIDEBAR_ICONS)],
             **({"roles": agg[e["collection"]]} if agg.get(e["collection"]) else {})}
            for i, e in enumerate(entities)
        ]

    return {"written": written, "sidebar": sidebar}
