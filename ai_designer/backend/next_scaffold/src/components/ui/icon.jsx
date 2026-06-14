'use client';
// Name-based icon resolver over lucide-react: accepts PascalCase, kebab/lower
// case and common synonyms, so template/LLM icon names ALWAYS render something.
import * as Icons from 'lucide-react';

const ALIASES = {
  chart: 'TrendingUp', graph: 'TrendingUp', analytics: 'TrendingUp', activity: 'Activity',
  notifications: 'Bell', notification: 'Bell', alert: 'BellRing', bell: 'Bell',
  delete: 'Trash2', trash: 'Trash2', remove: 'Trash2', edit: 'Pencil', pencil: 'Pencil',
  user: 'User', users: 'Users', person: 'User', team: 'Users',
  money: 'DollarSign', dollar: 'DollarSign', price: 'DollarSign',
  location: 'MapPin', pin: 'MapPin', time: 'Clock', clock: 'Clock',
  close: 'X', x: 'X', cancel: 'X', check: 'Check', tick: 'Check', checkmark: 'CheckCheck',
  view: 'Eye', eye: 'Eye', search: 'Search', inbox: 'Inbox', plus: 'Plus', add: 'Plus',
  star: 'Star', heart: 'Heart', zap: 'Zap', shield: 'Shield', award: 'Award',
  calendar: 'Calendar', mail: 'Mail', email: 'Mail', phone: 'Phone', send: 'Send',
  download: 'Download', upload: 'Upload', filter: 'Filter', settings: 'Settings',
  menu: 'Menu', globe: 'Globe', lock: 'Lock', logout: 'LogOut', login: 'LogIn',
  'arrow-right': 'ArrowRight', 'arrow-left': 'ArrowLeft', 'arrow-up-right': 'ArrowUpRight',
  'chevron-down': 'ChevronDown', 'chevron-right': 'ChevronRight', 'chevron-up': 'ChevronUp',
  sparkle: 'Sparkles', sparkles: 'Sparkles', leaf: 'Leaf', building: 'Building2',
  'message-square': 'MessageSquare', message: 'MessageSquare', comment: 'MessageSquare',
  'play-circle': 'PlayCircle', play: 'Play', 'trending-up': 'TrendingUp',
  'layout-dashboard': 'LayoutDashboard', dashboard: 'LayoutDashboard',
};

function toPascal(name) {
  return String(name)
    .split(/[-_ ]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join('');
}

export function Icon({ name, className = 'h-5 w-5', ...props }) {
  let Cmp = null;
  if (name && Icons[name]) Cmp = Icons[name];
  if (!Cmp && name && ALIASES[String(name).toLowerCase()]) Cmp = Icons[ALIASES[String(name).toLowerCase()]];
  if (!Cmp && name) Cmp = Icons[toPascal(String(name).toLowerCase())];
  if (!Cmp) Cmp = Icons.Sparkles; // never an empty tile
  return <Cmp className={className} {...props} />;
}

export default Icon;
