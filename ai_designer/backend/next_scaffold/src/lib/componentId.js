// Stable componentId derivation for Select-Element editing.
// GUARANTEE: never returns null or undefined - so the studio can never send
// component_id: null during normal editing.
//
// Rules:
//   - element inside a [data-component-id] ancestor -> that exact id
//   - otherwise derive from the route:
//       "/"                 -> "home"
//       "/dashboard"        -> "dashboard"   (and profile/settings/notifications/login/register)
//       "/courses"          -> "page-courses"
//       "/events-calendar"  -> "page-events-calendar"
//       nested / CRUD route -> "route:<path>"  (backend _route_to_file maps the full path,
//                                               so detail/edit/new/create all resolve)

const APP_PAGES = ['dashboard', 'profile', 'settings', 'notifications', 'login', 'register'];

export function routeComponentId(pathname) {
  const path = (pathname || '/').split('?')[0].split('#')[0].replace(/\/+$/, '') || '/';
  if (path === '/') return 'home';
  const segs = path.split('/').filter(Boolean);
  // CRUD + any nested app route -> keep the full path so the backend resolves
  // list / detail / edit / new / create from it.
  if (segs.length > 1 || segs[0] === 'e' || segs[0] === 'workspace') return 'route:' + path;
  const slug = segs[0].toLowerCase().replace(/[^a-z0-9-]/g, '') || 'home';
  if (APP_PAGES.includes(slug)) return slug;
  return 'page-' + slug;                       // a marketing sub-page
}

export function selectedComponentId(el, pathname) {
  const container = el && typeof el.closest === 'function' ? el.closest('[data-component-id]') : null;
  const marked = container && container.getAttribute && container.getAttribute('data-component-id');
  return (marked && String(marked)) || routeComponentId(pathname);  // never null / undefined
}

export default selectedComponentId;
