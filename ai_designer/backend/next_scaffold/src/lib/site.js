// Site configuration - REWRITTEN per project by the generator.
// The deterministic shells (Navbar/Sidebar/layouts) read everything from here,
// so generated code never has to touch navigation again.
export const site = {
  appName: 'App',
  tagline: 'A modern web application',
  marketingLinks: [
    { label: 'Home', href: '/' },
    { label: 'Features', href: '/features' },
    { label: 'About', href: '/about' },
    { label: 'Contact', href: '/contact' },
  ],
  sidebarLinks: [
    { label: 'Dashboard', href: '/dashboard', icon: 'LayoutDashboard' },
    { label: 'Profile', href: '/profile', icon: 'User' },
    { label: 'Settings', href: '/settings', icon: 'Settings' },
  ],
  entities: [],
  roles: ['Admin', 'User'],
};
