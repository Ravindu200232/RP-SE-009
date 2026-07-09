/**
 * Web application types the user can choose. The selected type drives the
 * planning prompts and the generation scale/strategy.
 */

export type AppScale = 'small' | 'medium' | 'big';

export interface AppTypeDef {
  key: string;
  label: string;
  scale: AppScale;
  defaultBackend: boolean;
  /** Short description shown in the picker. */
  description: string;
  /** Architecture/scale guidance injected into the planning + build prompts. */
  guidance: string;
}

export const APP_TYPES: AppTypeDef[] = [
  {
    key: 'spa',
    label: 'Single-Page Application (SPA)',
    scale: 'medium',
    defaultBackend: false,
    description: 'App-like, mostly client-side, few full reloads.',
    guidance:
      'Build a single-page-feeling app: a primary view with client-side state and smooth in-page navigation. Keep routes minimal; rich interactivity.',
  },
  {
    key: 'pwa',
    label: 'Progressive Web App (PWA)',
    scale: 'medium',
    defaultBackend: true,
    description: 'Installable, offline-friendly, mobile-first.',
    guidance:
      'Build a mobile-first installable app: include a web manifest, service-worker-friendly structure, responsive layout, and offline-tolerant data fetching.',
  },
  {
    key: 'static',
    label: 'Static Web App',
    scale: 'small',
    defaultBackend: false,
    description: 'Pre-rendered content pages, no database.',
    guidance:
      'Build static, pre-rendered content pages. No database, no auth. Focus on clean typography, fast load, and good information layout.',
  },
  {
    key: 'dynamic',
    label: 'Dynamic Web App',
    scale: 'medium',
    defaultBackend: true,
    description: 'Server-driven content and data.',
    guidance:
      'Build a server-rendered, data-driven app with MongoDB-backed content and a handful of interactive pages.',
  },
  {
    key: 'mpa',
    label: 'Multi-Page Application (MPA)',
    scale: 'medium',
    defaultBackend: true,
    description: 'Many distinct routed pages.',
    guidance:
      'Build many distinct pages, each with its own route and server data. Shared layout + navigation across pages.',
  },
  {
    key: 'ecommerce',
    label: 'E-Commerce Application',
    scale: 'big',
    defaultBackend: true,
    description: 'Storefront, cart, checkout, orders, admin.',
    guidance:
      'Build a large store: product catalog + detail, cart, checkout, orders, customer accounts, and an admin dashboard (products, orders, inventory). Many models and pages.',
  },
  {
    key: 'saas',
    label: 'SaaS Application',
    scale: 'big',
    defaultBackend: true,
    description: 'Auth, multi-tenant dashboards, billing.',
    guidance:
      'Build a multi-tenant SaaS: auth, organization/workspace scoping, role-based dashboards, settings, and the core product modules. Many CRUD modules.',
  },
  {
    key: 'portal',
    label: 'Portal Web Application',
    scale: 'big',
    defaultBackend: true,
    description: 'Role-based portals over shared data.',
    guidance:
      'Build role-specific portals (e.g. admin / staff / customer) over shared data, each with a tailored dashboard, navigation, and permissions.',
  },
  {
    key: 'cms',
    label: 'Content Management System (CMS)',
    scale: 'big',
    defaultBackend: true,
    description: 'Content authoring + public rendering.',
    guidance:
      'Build a CMS: content models, an authoring admin (create/edit/publish), media handling, and public rendering of published content.',
  },
  {
    key: 'enterprise',
    label: 'Enterprise Web Application',
    scale: 'big',
    defaultBackend: true,
    description: 'Many modules, roles, reports, audit.',
    guidance:
      'Build a large enterprise system: many modules with full CRUD, role-based access for many roles, data tables with filters, reports, and audit logging. Prioritize breadth and a consistent modular structure.',
  },
  {
    key: 'marketplace',
    label: 'Marketplace Application',
    scale: 'big',
    defaultBackend: true,
    description: 'Buyers, sellers, listings, transactions.',
    guidance:
      'Build a marketplace: seller and buyer roles, listings management, search/browse, orders/transactions, and an admin oversight dashboard.',
  },
  {
    key: 'social',
    label: 'Social Media & Networking',
    scale: 'big',
    defaultBackend: true,
    description: 'Profiles, feeds, posts, follows.',
    guidance:
      'Build a social app: user profiles, a feed, posts/comments/likes, follow relationships, and notifications.',
  },
  {
    key: 'lms',
    label: 'Educational / LMS',
    scale: 'big',
    defaultBackend: true,
    description: 'Courses, lessons, students, grading.',
    guidance:
      'Build a learning platform: courses/lessons, enrollments, assignments/submissions, grading, and role-based dashboards (admin / teacher / student).',
  },
  {
    key: 'landing',
    label: 'Landing Page',
    scale: 'small',
    defaultBackend: false,
    description: 'Single marketing page with sections.',
    guidance:
      'Build one polished marketing page: hero, features, testimonials, pricing/CTA, and footer. No auth, no database (a simple contact form is fine).',
  },
  {
    key: 'portfolio',
    label: 'Portfolio Web App',
    scale: 'small',
    defaultBackend: false,
    description: 'Personal showcase site.',
    guidance:
      'Build a personal portfolio: hero/about, projects gallery, skills, and contact. Clean and visual; no database needed.',
  },
  {
    key: 'blog',
    label: 'Personal / Company Blog',
    scale: 'medium',
    defaultBackend: true,
    description: 'Posts list, post detail, authoring.',
    guidance:
      'Build a blog: posts list, post detail, categories/tags, and a simple authoring/admin to create posts (MongoDB-backed).',
  },
  {
    key: 'utility',
    label: 'Single-Purpose Utility (Calculator, Converter)',
    scale: 'small',
    defaultBackend: false,
    description: 'One focused tool.',
    guidance:
      'Build one focused client-side tool (e.g. calculator/converter) with a clean UI. No database; all logic runs in the browser.',
  },
];

export function getAppType(key: string | undefined | null): AppTypeDef | undefined {
  if (!key) return undefined;
  return APP_TYPES.find((t) => t.key === key);
}
