// STUB route-protection + role-access metadata. Overwritten by
// app_shell_generator.generate_access() once the data model planner runs -
// this permissive default just keeps the bare scaffold (e.g. landing-page-only
// test builds) buildable on its own.
export const protectedRoutes = ['/dashboard', '/manage', '/profile', '/settings', '/notifications'];
export const publicRoutes = ['/', '/login', '/register'];
export const roleAccess = {};

export function isProtected(pathname) {
  return protectedRoutes.some((p) => pathname === p || pathname.startsWith(p + '/'));
}
export function canAccess(role, collection) {
  const allowed = roleAccess[collection];
  return !allowed || allowed.length === 0 || allowed.includes(role) || role === 'Admin';
}
export function canAccessPage(role, pathname) {
  return true; // Permissive stub — overridden by app_shell_generator.generate_access()
}
