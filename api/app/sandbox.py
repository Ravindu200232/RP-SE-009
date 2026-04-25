from __future__ import annotations

import json
import re
import time
from threading import Lock
from typing import Any
from uuid import uuid4

from .llm import build_llm, llm_invoke, strip_code_fence

# ---------------------------------------------------------------------------
# UI_LIBRARY_JSX
# A complete shadcn/ui-style component library that is injected into the
# sandbox iframe BEFORE the model-generated `App()` runs. Components are
# global inside the babel <script> block so the model just composes them by
# name (e.g. <Button>, <Card>, <Sidebar>) instead of writing raw class strings.
# ---------------------------------------------------------------------------
UI_LIBRARY_JSX = r"""
// ---------- Icons (string-name API, lucide-style 24x24 paths) ----------
const ICON_PATHS = {
  home: "M3 12L12 3l9 9 M5 10v10h14V10",
  user: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M22 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75",
  search: "M21 21l-6-6 M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z",
  settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
  bell: "M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9 M13.73 21a2 2 0 0 1-3.46 0",
  plus: "M12 5v14 M5 12h14",
  minus: "M5 12h14",
  x: "M18 6 6 18 M6 6l12 12",
  check: "M20 6 9 17l-5-5",
  "check-circle": "M22 11.08V12a10 10 0 1 1-5.93-9.14 M22 4 12 14.01l-3-3",
  edit: "M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z",
  trash: "M3 6h18 M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2 M10 11v6 M14 11v6",
  "more-horizontal": "M19 12a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M12 12a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M5 12a1 1 0 1 0 0-2 1 1 0 0 0 0 2z",
  "more-vertical": "M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M12 6a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M12 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2z",
  "chevron-down": "m6 9 6 6 6-6",
  "chevron-up": "m18 15-6-6-6 6",
  "chevron-right": "m9 18 6-6-6-6",
  "chevron-left": "m15 18-6-6 6-6",
  "arrow-right": "M5 12h14 M12 5l7 7-7 7",
  "arrow-left": "M19 12H5 M12 19l-7-7 7-7",
  "arrow-up": "M12 19V5 M5 12l7-7 7 7",
  "arrow-down": "M12 5v14 M19 12l-7 7-7-7",
  star: "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
  heart: "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z",
  bookmark: "m19 21-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z",
  calendar: "M19 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z M16 2v4 M8 2v4 M3 10h18",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2",
  mail: "M22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2 M22 6v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6 M22 6l-10 7L2 6",
  phone: "M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.37 1.9.72 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.35 1.85.59 2.81.72A2 2 0 0 1 22 16.92z",
  globe: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M2 12h20 M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z",
  download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M7 10l5 5 5-5 M12 15V3",
  upload: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4 M17 8l-5-5-5 5 M12 3v12",
  filter: "M22 3H2l8 9.46V19l4 2v-8.54L22 3z",
  menu: "M3 12h18 M3 6h18 M3 18h18",
  layout: "M3 3h18v18H3z M3 9h18 M9 21V9",
  "layout-grid": "M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z",
  "layout-list": "M3 6h.01 M3 12h.01 M3 18h.01 M8 6h13 M8 12h13 M8 18h13",
  "bar-chart": "M12 20V10 M18 20V4 M6 20v-4",
  "pie-chart": "M21.21 15.89A10 10 0 1 1 8 2.83 M22 12A10 10 0 0 0 12 2v10z",
  trending: "m22 7-8.5 8.5-5-5L2 17 M16 7h6v6",
  inbox: "M22 12h-6l-2 3h-4l-2-3H2 M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
  folder: "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z",
  package: "m16.5 9.4-9-5.19 M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96 12 12.01l8.73-5.05 M12 22.08V12",
  "shopping-cart": "M9 22a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M20 22a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6",
  "credit-card": "M21 4H3a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h18a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2z M1 10h22",
  "dollar-sign": "M12 1v22 M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6",
  briefcase: "M20 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2z M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16",
  building: "M3 21h18 M5 21V7l8-4v18 M19 21V11l-6-4 M9 9h.01 M9 13h.01 M9 17h.01",
  map: "m1 6 7-3 8 3 7-3v15l-7 3-8-3-7 3z M8 3v15 M16 6v15",
  "map-pin": "M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z M12 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  "alert-circle": "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 8v4 M12 16h.01",
  "alert-triangle": "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z M12 9v4 M12 17h.01",
  info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 16v-4 M12 8h.01",
  zap: "M13 2 3 14h9l-1 8 10-12h-9l1-8z",
  flag: "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z M4 22V15",
  send: "m22 2-7 20-4-9-9-4 20-7z",
  "log-out": "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  eye: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  "eye-off": "M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24 M1 1l22 22",
  lock: "M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z M7 11V7a5 5 0 0 1 10 0v4",
  unlock: "M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z M7 11V7a5 5 0 0 1 9.9-1",
  refresh: "M23 4v6h-6 M1 20v-6h6 M3.51 9a9 9 0 0 1 14.85-3.36L23 10 M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  copy: "M20 9h-9a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2z M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1",
  link: "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71 M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71",
  image: "M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2z M8.5 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z m21 15-5-5L5 21",
  "message-square": "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20 M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z",
  tag: "M20.59 13.41 13.42 20.58a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z M7 7h.01",
  award: "M12 15a7 7 0 1 0 0-14 7 7 0 0 0 0 14z m8.21 13.89L15 16l-3 5-3-5-5.21 4.89L7 14",
  activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  smile: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M8 14s1.5 2 4 2 4-2 4-2 M9 9h.01 M15 9h.01",
  help: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3 M12 17h.01",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z M12 1v2 M12 21v2 M4.22 4.22l1.42 1.42 M18.36 18.36l1.42 1.42 M1 12h2 M21 12h2 M4.22 19.78l1.42-1.42 M18.36 5.64l1.42-1.42",
  moon: "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z",
  "log-in": "M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4 M10 17l5-5-5-5 M15 12H3",
  list: "M8 6h13 M8 12h13 M8 18h13 M3 6h.01 M3 12h.01 M3 18h.01",
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z"
};

function Icon({ name, size = 16, className = "", strokeWidth = 2 }) {
  const d = ICON_PATHS[name] || ICON_PATHS.help || "";
  const segments = String(d).split(/\s+(?=M)/).filter(Boolean);
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={className}>
      {segments.map((seg, i) => <path key={i} d={seg} />)}
    </svg>
  );
}

// ---------- class-name helper ----------
function cx(...parts) {
  return parts.filter(Boolean).join(" ");
}

// ---------- avatar palette ----------
const AVATAR_PALETTE = [
  ["bg-zinc-100", "text-zinc-700"],
  ["bg-sky-100", "text-sky-700"],
  ["bg-emerald-100", "text-emerald-700"],
  ["bg-amber-100", "text-amber-700"],
  ["bg-rose-100", "text-rose-700"],
  ["bg-violet-100", "text-violet-700"],
  ["bg-indigo-100", "text-indigo-700"],
  ["bg-teal-100", "text-teal-700"]
];
function _hashStr(s) {
  let h = 0; const str = String(s || "");
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) | 0;
  return Math.abs(h);
}
function _initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// ---------- Button ----------
const _BTN_BASE = "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-950 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 shrink-0";
const _BTN_VARIANT = {
  primary: "bg-zinc-900 text-zinc-50 hover:bg-zinc-800",
  secondary: "bg-zinc-100 text-zinc-900 hover:bg-zinc-200",
  outline: "border border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-900",
  ghost: "hover:bg-zinc-100 text-zinc-700",
  destructive: "bg-red-500 text-zinc-50 hover:bg-red-600",
  link: "text-zinc-900 underline-offset-4 hover:underline"
};
const _BTN_SIZE = {
  sm: "h-8 px-3 text-xs",
  md: "h-9 px-4 py-2 text-sm",
  lg: "h-10 px-6 text-sm",
  icon: "h-9 w-9 p-0"
};
function Button({ variant = "primary", size = "md", className = "", children, leftIcon, rightIcon, ...rest }) {
  const v = _BTN_VARIANT[variant] || _BTN_VARIANT.primary;
  const s = _BTN_SIZE[size] || _BTN_SIZE.md;
  return (
    <button className={cx(_BTN_BASE, v, s, className)} {...rest}>
      {leftIcon ? <Icon name={leftIcon} size={size === "lg" ? 16 : 14} /> : null}
      {children}
      {rightIcon ? <Icon name={rightIcon} size={size === "lg" ? 16 : 14} /> : null}
    </button>
  );
}

function IconButton({ icon, variant = "ghost", size = "icon", className = "", ...rest }) {
  return (
    <Button variant={variant} size={size} className={className} {...rest}>
      <Icon name={icon} size={16} />
    </Button>
  );
}

// ---------- Card ----------
function Card({ className = "", children, ...rest }) {
  return <div className={cx("rounded-xl border border-zinc-200 bg-white text-zinc-950 shadow-sm", className)} {...rest}>{children}</div>;
}
function CardHeader({ className = "", children }) {
  return <div className={cx("flex flex-col space-y-1.5 p-6", className)}>{children}</div>;
}
function CardTitle({ className = "", children }) {
  return <h3 className={cx("text-lg font-semibold leading-none tracking-tight", className)}>{children}</h3>;
}
function CardDescription({ className = "", children }) {
  return <p className={cx("text-sm text-zinc-500", className)}>{children}</p>;
}
function CardContent({ className = "", children }) {
  return <div className={cx("p-6 pt-0", className)}>{children}</div>;
}
function CardFooter({ className = "", children }) {
  return <div className={cx("flex items-center p-6 pt-0 gap-2 flex-wrap", className)}>{children}</div>;
}

// ---------- KpiCard ----------
function KpiCard({ label, value, icon, trend, trendDir = "up", className = "" }) {
  const trendCls = trendDir === "down" ? "text-rose-600" : "text-emerald-600";
  return (
    <div className={cx("rounded-xl border border-zinc-200 bg-white p-6 min-w-0", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-medium text-zinc-500 truncate">{label}</p>
        {icon ? <div className="text-zinc-400 shrink-0"><Icon name={icon} size={16} /></div> : null}
      </div>
      <p className="text-2xl font-semibold tracking-tight tabular-nums mt-2 text-zinc-950">{value}</p>
      {trend ? <p className={cx("text-xs mt-1", trendCls)}>{trend}</p> : null}
    </div>
  );
}

// ---------- Badge ----------
const _BADGE_BASE = "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors whitespace-nowrap";
const _BADGE_VARIANT = {
  default: "border-transparent bg-zinc-900 text-zinc-50",
  secondary: "border-transparent bg-zinc-100 text-zinc-900",
  outline: "border-zinc-200 text-zinc-700 bg-white",
  destructive: "border-transparent bg-red-100 text-red-700",
  success: "border-transparent bg-emerald-100 text-emerald-700",
  warning: "border-transparent bg-amber-100 text-amber-700",
  info: "border-transparent bg-sky-100 text-sky-700",
  violet: "border-transparent bg-violet-100 text-violet-700"
};
function Badge({ variant = "secondary", className = "", children }) {
  return <span className={cx(_BADGE_BASE, _BADGE_VARIANT[variant] || _BADGE_VARIANT.secondary, className)}>{children}</span>;
}

// ---------- Avatar ----------
function Avatar({ name, src, size = 36, className = "" }) {
  const idx = _hashStr(name) % AVATAR_PALETTE.length;
  const [bg, fg] = AVATAR_PALETTE[idx];
  const dim = { width: size, height: size };
  if (src) {
    return <img src={src} alt={name || "avatar"} className={cx("shrink-0 rounded-full object-cover", className)} style={dim} />;
  }
  return (
    <div className={cx("shrink-0 rounded-full flex items-center justify-center font-semibold", bg, fg, className)} style={dim}>
      <span className="text-xs">{_initials(name)}</span>
    </div>
  );
}

// ---------- Input / Textarea / Select / Checkbox / Switch / Label / FormField ----------
function Input({ className = "", ...rest }) {
  return <input className={cx("flex h-9 w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm placeholder:text-zinc-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-950 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50", className)} {...rest} />;
}
function Textarea({ className = "", ...rest }) {
  return <textarea className={cx("flex min-h-[80px] w-full rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm placeholder:text-zinc-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-950 focus-visible:ring-offset-2", className)} {...rest} />;
}
function Select({ className = "", children, ...rest }) {
  return (
    <select className={cx("flex h-9 w-full items-center justify-between rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-950 focus-visible:ring-offset-2", className)} {...rest}>
      {children}
    </select>
  );
}
function Checkbox({ className = "", label, ...rest }) {
  if (label) {
    return (
      <label className="inline-flex items-center gap-2 cursor-pointer text-sm text-zinc-700">
        <input type="checkbox" className={cx("peer h-4 w-4 shrink-0 rounded-sm border border-zinc-300 accent-zinc-900 focus-visible:ring-2 focus-visible:ring-zinc-950 focus-visible:ring-offset-2", className)} {...rest} />
        <span>{label}</span>
      </label>
    );
  }
  return <input type="checkbox" className={cx("peer h-4 w-4 shrink-0 rounded-sm border border-zinc-300 accent-zinc-900 focus-visible:ring-2 focus-visible:ring-zinc-950 focus-visible:ring-offset-2", className)} {...rest} />;
}
function Switch({ checked, onCheckedChange, className = "" }) {
  return (
    <button type="button" role="switch" aria-checked={!!checked} onClick={() => onCheckedChange && onCheckedChange(!checked)} className={cx("relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-950 focus-visible:ring-offset-2", checked ? "bg-zinc-900" : "bg-zinc-200", className)}>
      <span className={cx("inline-block h-4 w-4 rounded-full bg-white shadow transition-transform", checked ? "translate-x-4" : "translate-x-0.5")} />
    </button>
  );
}
function Label({ className = "", children, htmlFor }) {
  return <label htmlFor={htmlFor} className={cx("text-xs font-medium text-zinc-700", className)}>{children}</label>;
}
function FormField({ label, hint, error, children, className = "" }) {
  return (
    <div className={cx("space-y-1.5", className)}>
      {label ? <Label>{label}</Label> : null}
      {children}
      {error ? <p className="text-xs text-red-600">{error}</p> : hint ? <p className="text-xs text-zinc-500">{hint}</p> : null}
    </div>
  );
}

// ---------- Separator ----------
function Separator({ orientation = "horizontal", className = "" }) {
  return <div className={cx("shrink-0 bg-zinc-200", orientation === "vertical" ? "w-px h-full" : "h-px w-full", className)} />;
}

// ---------- Tabs (controlled or uncontrolled) ----------
function Tabs({ value, defaultValue, onValueChange, items = [], className = "" }) {
  const [internal, setInternal] = useState(defaultValue || (items[0] && items[0].value));
  const current = value !== undefined ? value : internal;
  const setVal = (v) => { if (value === undefined) setInternal(v); onValueChange && onValueChange(v); };
  return (
    <div className={cx("inline-flex h-9 items-center justify-center rounded-lg bg-zinc-100 p-1 text-zinc-500 gap-1", className)} role="tablist">
      {(items || []).map((it) => {
        const active = it.value === current;
        return (
          <button key={it.value} role="tab" aria-selected={active} onClick={() => setVal(it.value)} className={cx("inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all", active ? "bg-white text-zinc-950 shadow-sm" : "text-zinc-500 hover:text-zinc-900")}>
            {it.label}
          </button>
        );
      })}
    </div>
  );
}

// ---------- Table ----------
function Table({ columns = [], rows = [], rowKey = "id", onRowClick, empty, className = "" }) {
  return (
    <div className={cx("w-full overflow-x-auto rounded-lg border border-zinc-200 bg-white", className)}>
      <table className="w-full caption-bottom text-sm">
        <thead className="border-b border-zinc-200 bg-zinc-50">
          <tr>
            {(columns || []).map((c, i) => (
              <th key={c.key || i} className={cx("h-10 px-4 text-left align-middle font-medium text-zinc-500 text-xs whitespace-nowrap", c.align === "right" && "text-right", c.align === "center" && "text-center")}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(rows || []).length === 0 ? (
            <tr><td colSpan={(columns || []).length || 1} className="p-0">
              {empty || <div className="flex flex-col items-center justify-center py-12 px-4 gap-2 text-center"><p className="text-sm text-zinc-500">No data yet.</p></div>}
            </td></tr>
          ) : (rows || []).map((r, ri) => (
            <tr key={r[rowKey] != null ? r[rowKey] : ri} onClick={onRowClick ? () => onRowClick(r) : undefined} className={cx("border-b border-zinc-100 transition-colors", onRowClick ? "hover:bg-zinc-50 cursor-pointer" : "")}>
              {(columns || []).map((c, ci) => (
                <td key={c.key || ci} className={cx("p-4 align-middle", c.align === "right" && "text-right", c.align === "center" && "text-center", c.cellClassName || "")}>
                  {c.render ? c.render(r) : (r[c.key] != null ? String(r[c.key]) : "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------- EmptyState ----------
function EmptyState({ icon = "inbox", title = "Nothing here yet", description = "", action, className = "" }) {
  return (
    <div className={cx("flex flex-col items-center justify-center py-12 px-4 gap-3 text-center", className)}>
      <div className="h-10 w-10 rounded-full bg-zinc-100 grid place-items-center text-zinc-500"><Icon name={icon} size={18} /></div>
      <div className="space-y-1 max-w-xs">
        <p className="text-sm font-medium text-zinc-900">{title}</p>
        {description ? <p className="text-xs text-zinc-500">{description}</p> : null}
      </div>
      {action || null}
    </div>
  );
}

// ---------- Dialog (modal) ----------
function Dialog({ open, onOpenChange, title, description, children, footer, size = "md" }) {
  if (!open) return null;
  const sz = size === "lg" ? "max-w-2xl" : size === "sm" ? "max-w-sm" : "max-w-lg";
  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm grid place-items-center p-4" onClick={() => onOpenChange && onOpenChange(false)}>
      <div className={cx("relative z-50 w-full grid gap-4 rounded-xl border border-zinc-200 bg-white p-6 shadow-2xl max-h-[calc(100vh-4rem)] overflow-y-auto", sz)} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title ? <h2 className="text-lg font-semibold leading-none tracking-tight text-zinc-950 truncate">{title}</h2> : null}
            {description ? <p className="text-sm text-zinc-500 mt-1.5">{description}</p> : null}
          </div>
          <button onClick={() => onOpenChange && onOpenChange(false)} className="shrink-0 rounded-md p-1 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900 transition-colors" aria-label="Close"><Icon name="x" size={16} /></button>
        </div>
        <div>{children}</div>
        {footer ? <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">{footer}</div> : null}
      </div>
    </div>
  );
}

// ---------- Sheet (slide-over) ----------
function Sheet({ open, onOpenChange, title, description, children, footer, side = "right" }) {
  if (!open) return null;
  const sideCls = side === "left" ? "left-0 border-r" : "right-0 border-l";
  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" onClick={() => onOpenChange && onOpenChange(false)}>
      <div className={cx("fixed inset-y-0 z-50 h-full w-full sm:max-w-md border-zinc-200 bg-white shadow-2xl flex flex-col gap-4 overflow-y-auto p-6", sideCls)} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title ? <h2 className="text-lg font-semibold leading-none tracking-tight text-zinc-950 truncate">{title}</h2> : null}
            {description ? <p className="text-sm text-zinc-500 mt-1.5">{description}</p> : null}
          </div>
          <button onClick={() => onOpenChange && onOpenChange(false)} className="shrink-0 rounded-md p-1 text-zinc-500 hover:bg-zinc-100" aria-label="Close"><Icon name="x" size={16} /></button>
        </div>
        <div className="flex-1 min-h-0">{children}</div>
        {footer ? <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2">{footer}</div> : null}
      </div>
    </div>
  );
}

// ---------- Toast (lightweight; mounted via ToastContainer) ----------
function ToastContainer({ toasts = [], onDismiss }) {
  return (
    <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 max-w-sm">
      {(toasts || []).map((t) => (
        <div key={t.id} className={cx("rounded-lg border bg-white shadow-lg px-4 py-3 flex items-start gap-3", t.variant === "error" ? "border-red-200" : t.variant === "success" ? "border-emerald-200" : "border-zinc-200")}>
          <div className={cx("mt-0.5", t.variant === "error" ? "text-red-500" : t.variant === "success" ? "text-emerald-500" : "text-zinc-500")}><Icon name={t.variant === "error" ? "alert-triangle" : t.variant === "success" ? "check-circle" : "info"} size={16} /></div>
          <div className="min-w-0 flex-1">
            {t.title ? <p className="text-sm font-medium text-zinc-900">{t.title}</p> : null}
            {t.description ? <p className="text-xs text-zinc-500">{t.description}</p> : null}
          </div>
          <button onClick={() => onDismiss && onDismiss(t.id)} className="shrink-0 text-zinc-400 hover:text-zinc-700"><Icon name="x" size={14} /></button>
        </div>
      ))}
    </div>
  );
}
function useToasts() {
  const [toasts, setToasts] = useState([]);
  const push = (t) => {
    const id = Math.random().toString(36).slice(2);
    setToasts((arr) => [...arr, { id, ...t }]);
    setTimeout(() => setToasts((arr) => arr.filter((x) => x.id !== id)), 4000);
  };
  const dismiss = (id) => setToasts((arr) => arr.filter((x) => x.id !== id));
  return { toasts, push, dismiss };
}

// ---------- DropdownMenu ----------
function DropdownMenu({ trigger, items = [], align = "right" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onClick = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);
  return (
    <div className="relative inline-block" ref={ref}>
      <div onClick={() => setOpen((v) => !v)}>{trigger}</div>
      {open ? (
        <div className={cx("absolute z-40 mt-2 min-w-[10rem] rounded-md border border-zinc-200 bg-white p-1 shadow-lg", align === "left" ? "left-0" : "right-0")}>
          {(items || []).map((it, i) => it.separator ? (
            <div key={i} className="my-1 h-px bg-zinc-100" />
          ) : (
            <button key={i} onClick={() => { setOpen(false); it.onClick && it.onClick(); }} className={cx("w-full flex items-center gap-2 rounded-sm px-2.5 py-1.5 text-sm text-left transition-colors", it.danger ? "text-red-600 hover:bg-red-50" : "text-zinc-700 hover:bg-zinc-100")}>
              {it.icon ? <Icon name={it.icon} size={14} /> : null}
              <span className="flex-1 truncate">{it.label}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// ---------- Breadcrumb ----------
function Breadcrumb({ items = [] }) {
  return (
    <nav className="flex items-center gap-1.5 text-sm text-zinc-500 flex-wrap">
      {(items || []).map((it, i) => (
        <Fragment key={i}>
          {i > 0 ? <Icon name="chevron-right" size={14} className="text-zinc-300" /> : null}
          {it.href || it.onClick ? (
            <button onClick={it.onClick} className="hover:text-zinc-900 transition-colors truncate max-w-[200px]">{it.label}</button>
          ) : (
            <span className="text-zinc-900 font-medium truncate max-w-[200px]">{it.label}</span>
          )}
        </Fragment>
      ))}
    </nav>
  );
}

// ---------- ProgressBar ----------
function ProgressBar({ value = 0, max = 100, className = "", barClassName = "" }) {
  const pct = Math.max(0, Math.min(100, (Number(value) / Number(max || 1)) * 100));
  return (
    <div className={cx("h-2 w-full rounded-full bg-zinc-100 overflow-hidden", className)}>
      <div className={cx("h-full bg-zinc-900 transition-all", barClassName)} style={{ width: pct + "%" }} />
    </div>
  );
}

// ---------- Skeleton ----------
function Skeleton({ className = "" }) {
  return <div className={cx("animate-pulse rounded-md bg-zinc-100", className)} />;
}

// ---------- StatList (label/value pairs) ----------
function StatList({ items = [], className = "" }) {
  return (
    <dl className={cx("grid gap-3", className)}>
      {(items || []).map((it, i) => (
        <div key={i} className="flex items-center justify-between gap-3">
          <dt className="text-xs text-zinc-500 truncate">{it.label}</dt>
          <dd className="text-sm font-medium text-zinc-900 tabular-nums truncate">{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---------- Section ----------
function Section({ title, description, action, children, className = "" }) {
  return (
    <section className={cx("space-y-4", className)}>
      {(title || description || action) ? (
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-0">
            {title ? <h2 className="text-lg font-semibold tracking-tight text-zinc-950 truncate">{title}</h2> : null}
            {description ? <p className="text-sm text-zinc-500 mt-0.5">{description}</p> : null}
          </div>
          {action ? <div className="flex items-center gap-2 flex-wrap shrink-0">{action}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  );
}

// ---------- PageHeader ----------
function PageHeader({ title, subtitle, breadcrumb, actions, className = "" }) {
  return (
    <div className={cx("space-y-3 mb-6", className)}>
      {breadcrumb ? <Breadcrumb items={breadcrumb} /> : null}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-950 truncate">{title}</h1>
          {subtitle ? <p className="text-sm text-zinc-500 mt-1">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex items-center gap-2 flex-wrap shrink-0">{actions}</div> : null}
      </div>
    </div>
  );
}

// ---------- Sidebar / SidebarItem ----------
function Sidebar({ brand, items = [], active, onSelect, footer, className = "" }) {
  return (
    <aside className={cx("w-60 shrink-0 border-r border-zinc-200 bg-white flex flex-col h-full", className)}>
      {brand ? (
        <div className="h-14 shrink-0 border-b border-zinc-200 flex items-center gap-2 px-4">
          {brand.icon ? <div className="h-8 w-8 rounded-md bg-zinc-900 text-zinc-50 grid place-items-center"><Icon name={brand.icon} size={16} /></div> : null}
          <div className="min-w-0">
            <p className="text-sm font-semibold text-zinc-950 truncate">{brand.name}</p>
            {brand.subtitle ? <p className="text-xs text-zinc-500 truncate">{brand.subtitle}</p> : null}
          </div>
        </div>
      ) : null}
      <nav className="flex-1 min-h-0 overflow-y-auto p-3 space-y-0.5">
        {(items || []).map((g, gi) => g.section ? (
          <div key={gi} className="px-3 pt-4 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">{g.section}</div>
        ) : (
          <button key={g.id || gi} onClick={() => onSelect && onSelect(g.id)} className={cx("w-full flex items-center gap-2.5 rounded-md px-3 h-9 text-sm transition-colors", active === g.id ? "bg-zinc-100 text-zinc-900 font-medium" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900")}>
            {g.icon ? <Icon name={g.icon} size={16} className="shrink-0" /> : null}
            <span className="flex-1 truncate text-left">{g.label}</span>
            {g.badge != null ? <Badge variant="secondary" className="ml-auto">{g.badge}</Badge> : null}
          </button>
        ))}
      </nav>
      {footer ? <div className="shrink-0 border-t border-zinc-200 p-3">{footer}</div> : null}
    </aside>
  );
}

// ---------- Topbar ----------
function Topbar({ search, onSearch, actions, user, className = "" }) {
  return (
    <header className={cx("h-14 shrink-0 border-b border-zinc-200 bg-white flex items-center gap-3 px-4", className)}>
      {search !== false ? (
        <div className="relative w-72 max-w-full">
          <Icon name="search" size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
          <Input placeholder={typeof search === "string" ? search : "Search..."} onChange={(e) => onSearch && onSearch(e.target.value)} className="pl-8" />
        </div>
      ) : <div />}
      <div className="flex-1" />
      <div className="flex items-center gap-1.5">
        {actions || null}
        {user ? <Avatar name={user.name} src={user.avatar} size={32} /> : null}
      </div>
    </header>
  );
}

// ---------- AppShell (root layout wrapper) ----------
function AppShell({ sidebar, topbar, children, className = "" }) {
  return (
    <div className={cx("flex h-full w-full bg-zinc-50 text-zinc-950 antialiased", className)}>
      {sidebar || null}
      <div className="flex-1 min-w-0 flex flex-col h-full">
        {topbar || null}
        <main className="flex-1 min-w-0 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}

// ---------- KanbanBoard ----------
function KanbanBoard({ columns = [], renderCard, onAdd, className = "" }) {
  return (
    <div className={cx("flex gap-4 overflow-x-auto pb-2 -mx-1 px-1", className)}>
      {(columns || []).map((col, ci) => (
        <div key={col.id || ci} className="w-72 shrink-0 flex flex-col gap-2">
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-sm font-medium text-zinc-900 truncate">{col.title}</span>
              <Badge variant="secondary">{(col.items || []).length}</Badge>
            </div>
            {onAdd ? <IconButton icon="plus" onClick={() => onAdd(col)} /> : null}
          </div>
          <div className="flex-1 min-h-[100px] rounded-lg bg-zinc-100/60 p-2 space-y-2">
            {(col.items || []).length === 0 ? (
              <div className="text-xs text-zinc-400 text-center py-6">Empty</div>
            ) : (col.items || []).map((it, ii) => (
              <div key={it.id != null ? it.id : ii} className="rounded-lg border border-zinc-200 bg-white p-3 shadow-sm hover:shadow-md transition-shadow">
                {renderCard ? renderCard(it, col) : <p className="text-sm">{it.title || JSON.stringify(it)}</p>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------- helpers exposed ----------
function formatDate(s) {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d.getTime())) return String(s);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
function formatMoney(n, currency = "USD") {
  const v = Number(n);
  if (!isFinite(v)) return String(n || "");
  try { return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(v); } catch { return "$" + v.toFixed(2); }
}
"""


# ---------------------------------------------------------------------------
# HTML_SHELL — uses placeholder tokens that we substitute with .replace().
# This avoids escaping every JSX `{` `}` as `{{` `}}` (which str.format demands).
# Tokens: __TITLE__, __UI_LIBRARY__, __APP_JSX__
# ---------------------------------------------------------------------------
HTML_SHELL = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = { theme: { extend: { fontFamily: { sans: ['Inter','system-ui','sans-serif'], mono: ['JetBrains Mono','monospace'] } } } };
</script>
<script src="https://unpkg.com/react@18.3.1/umd/react.development.js" crossorigin></script>
<script src="https://unpkg.com/react-dom@18.3.1/umd/react-dom.development.js" crossorigin></script>
<script src="https://unpkg.com/@babel/standalone@7.29.0/babel.min.js" crossorigin></script>
<style>
*, *::before, *::after { box-sizing: border-box; }
html, body, #root { height: 100%; margin: 0; padding: 0; }
body { background: #f8fafc; color: #111827; font-family: 'Inter', system-ui, sans-serif; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 10px; }
.__sandbox_err { padding: 24px; font-family: 'JetBrains Mono', monospace; color: #991b1b; background: #fef2f2; min-height: 100vh; }
.__sandbox_err h2 { font-size: 14px; font-weight: 700; margin-bottom: 8px; }
.__sandbox_err pre { white-space: pre-wrap; font-size: 11px; line-height: 1.5; background: #ffffff; border: 1px solid #fecaca; padding: 12px; border-radius: 6px; max-height: 60vh; overflow: auto; }
</style>
</head>
<body>
<div id="root"><div style="padding:24px;color:#9ca3af;font-family:Inter,sans-serif">Loading sandbox...</div></div>
<script>
function __postSandboxError__(message, stack) {
  try {
    window.parent.postMessage({ type: 'sandbox-error', message: String(message || ''), stack: stack ? String(stack) : '' }, '*');
  } catch (e) {}
}
function __showSandboxError__(message, stack) {
  const root = document.getElementById('root');
  root.className = '';
  const safe = (s) => String(s || '').replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
  root.innerHTML = '<div class="__sandbox_err"><h2>Sandbox runtime error</h2><pre>' +
    safe(message) + (stack ? '\\n\\n' + safe(stack) : '') +
    '</pre></div>';
  __postSandboxError__(message, stack);
}
window.addEventListener('error', (event) => {
  __showSandboxError__(event.message, event.error && event.error.stack);
});
window.addEventListener('unhandledrejection', (event) => {
  __showSandboxError__('Unhandled promise rejection: ' + (event.reason && event.reason.message ? event.reason.message : event.reason));
});
</script>
<script type="text/babel">
try {
  const { useState, useEffect, useMemo, useRef, useCallback, Fragment } = React;

  // ===== UI library (pre-loaded, available globally to App) =====
__UI_LIBRARY__
  // ===== model-generated App =====
__APP_JSX__

  if (typeof App !== 'function') {
    throw new Error('No top-level `function App()` was defined by the model.');
  }
  const __root__ = ReactDOM.createRoot(document.getElementById('root'));
  __root__.render(<App />);
} catch (err) {
  __showSandboxError__(err && err.message, err && err.stack);
  console.error(err);
}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# COMPONENT_REFERENCE — the prompt-side spec the LLM reads. MUST stay in sync
# with UI_LIBRARY_JSX.
# ---------------------------------------------------------------------------
COMPONENT_REFERENCE = """A complete shadcn/ui-style component library is ALREADY DEFINED and AVAILABLE GLOBALLY before your code runs. You MUST compose UIs from these components by name. Do NOT redefine them. Do NOT write raw <button>, <div className="rounded-xl border ...">, etc. when a component exists for it.

LAYOUT:
- <AppShell sidebar={...} topbar={...}>...</AppShell>            // root wrapper. children render inside the scrollable main area.
- <Sidebar brand={{ name, subtitle?, icon? }} items={[...]} active={id} onSelect={fn} footer={node?} />
    items entries: { id, label, icon?, badge? } OR { section: "GROUP NAME" } for headers.
- <Topbar search="Search..." onSearch={fn} actions={node} user={{ name, avatar? }} />
- <PageHeader title="..." subtitle="..." breadcrumb={[{label,onClick?}]} actions={node} />
- <Section title="..." description="..." action={node}>...</Section>
- <Separator orientation="horizontal" | "vertical" />

CARDS:
- <Card>, <CardHeader>, <CardTitle>, <CardDescription>, <CardContent>, <CardFooter>
- <KpiCard label="Active users" value="1,248" icon="users" trend="+12% vs last week" trendDir="up" />

BUTTONS:
- <Button variant="primary|secondary|outline|ghost|destructive|link" size="sm|md|lg|icon" leftIcon="plus" rightIcon="arrow-right" onClick={...}>Save</Button>
- <IconButton icon="settings" variant="ghost" onClick={...} />

FORMS:
- <FormField label="Email" hint="..." error={msg}><Input ... /></FormField>
- <Input placeholder="..." value={v} onChange={...} />
- <Textarea ... />
- <Select value={v} onChange={...}><option>...</option></Select>
- <Checkbox label="Notify me" checked={...} onChange={...} />
- <Switch checked={v} onCheckedChange={fn} />
- <Label>...</Label>

DISPLAY:
- <Badge variant="default|secondary|outline|destructive|success|warning|info|violet">In progress</Badge>
- <Avatar name="Ada Lovelace" src={url?} size={36} />
- <Table columns={[{ key, header, render?:(row)=>node, align?:'left|right|center' }]} rows={[...]} rowKey="id" onRowClick={fn} empty={node?} />
- <EmptyState icon="inbox" title="No tasks yet" description="..." action={<Button>Add task</Button>} />
- <StatList items={[{ label, value }]} />
- <ProgressBar value={42} max={100} barClassName="bg-emerald-500" />
- <Skeleton className="h-4 w-32" />

NAVIGATION:
- <Tabs items={[{label:'All',value:'all'},...]} value={tab} onValueChange={setTab} />
- <Breadcrumb items={[{label,onClick?}]} />
- <DropdownMenu trigger={<IconButton icon="more-horizontal" />} items={[{ label, icon?, onClick, danger?:bool }, { separator: true }]} />

OVERLAYS:
- <Dialog open={open} onOpenChange={setOpen} title="Edit task" description="..." size="sm|md|lg" footer={<><Button variant="outline" onClick={...}>Cancel</Button><Button onClick={...}>Save</Button></>}>...form...</Dialog>
- <Sheet open={open} onOpenChange={setOpen} title="..." side="right|left" footer={...}>...</Sheet>
- <ToastContainer toasts={toasts} onDismiss={dismiss} /> + const { toasts, push, dismiss } = useToasts();

KANBAN:
- <KanbanBoard columns={[{ id, title, items:[{id,...}] }]} renderCard={(item,col)=>...} onAdd={col=>...} />

ICONS:
- <Icon name="user" size={16} className="..." />  // string-name only. NEVER <Icons.User />.
  Available names (lowercase, kebab): home, user, users, search, settings, bell, plus, minus, x, check, check-circle, edit, trash, more-horizontal, more-vertical, chevron-down, chevron-up, chevron-right, chevron-left, arrow-right, arrow-left, arrow-up, arrow-down, star, heart, bookmark, calendar, clock, mail, phone, globe, download, upload, filter, menu, layout, layout-grid, layout-list, bar-chart, pie-chart, trending, inbox, file, folder, package, shopping-cart, credit-card, dollar-sign, briefcase, building, map, map-pin, alert-circle, alert-triangle, info, zap, flag, send, log-out, eye, eye-off, lock, unlock, refresh, copy, link, image, message-square, book, tag, award, activity, smile, help, sun, moon, log-in, list, grid.

HELPERS (already available globally):
- formatDate(isoString)        -> "Mar 12"
- formatMoney(amount, currency) -> "$1,234.00"
- cx(...classes)               -> joined class string

CANONICAL APP STRUCTURE — copy this skeleton and fill it in:

  function App() {
    const [view, setView] = useState("dashboard");
    const [tasks, setTasks] = useState(SEED_TASKS);
    // ...other state...

    const sidebar = (
      <Sidebar
        brand={{ name: "ProjectX", subtitle: "Workspace", icon: "layout-grid" }}
        items={[
          { id: "dashboard", label: "Dashboard", icon: "home" },
          { id: "tasks",     label: "Tasks",     icon: "check-circle", badge: tasks.length },
          { section: "WORKSPACE" },
          { id: "team",      label: "Team",      icon: "users" },
          { id: "settings",  label: "Settings",  icon: "settings" }
        ]}
        active={view}
        onSelect={setView}
      />
    );
    const topbar = (
      <Topbar
        search="Search tasks, people, projects..."
        actions={<><IconButton icon="bell" /><Button leftIcon="plus" onClick={...}>New task</Button></>}
        user={{ name: "Ada Lovelace" }}
      />
    );

    return (
      <AppShell sidebar={sidebar} topbar={topbar}>
        {view === "dashboard" && <DashboardPage ... />}
        {view === "tasks" && <TasksPage ... />}
        ...
      </AppShell>
    );
  }
"""


GENERATE_SYSTEM = """You are a senior product engineer producing a COMPLETE single-page React application that runs inside an in-browser Babel runtime. The output must look like a polished shadcn/ui interface — beautiful, dense with realistic data, and free of layout bugs.

You DO NOT write a design system from scratch. A complete shadcn/ui-style component library is ALREADY DEFINED and AVAILABLE GLOBALLY before your code runs. Compose UIs by USING these components — never re-implement them with raw Tailwind classes when a component already exists.

═══════════════════════════════════════════════════════════════════
PART 1 — RUNTIME CONTRACT (hard rules; violations crash the sandbox)
═══════════════════════════════════════════════════════════════════
- Output ONLY raw JSX/JS — no markdown fences, no prose before or after.
- The host pre-destructures: `const { useState, useEffect, useMemo, useRef, useCallback, Fragment } = React;`. Do NOT redeclare these.
- The host has ALREADY defined every component in PART 2 below (Button, Card, Sidebar, AppShell, Dialog, Table, etc.) as well as the Icon helper, ICON_PATHS, useToasts, formatDate, formatMoney, and cx. Do NOT redefine, reimport, or shadow them.
- Declare exactly one top-level component named `App` with a function declaration: `function App() { ... }`. No `const App = () => ...`. No rename.
- You MAY declare additional helper components (page components like `DashboardPage`, `TasksPage`). EVERY top-level helper MUST receive every variable it uses as a prop. NEVER reference a value that lives inside `App` (state, derived values, handlers) from a top-level helper. If it's easier, define page components INSIDE `App` so they close over locals — that's fine and often safest.
- DEFENSIVE DATA ACCESS: before `.map`, `.filter`, `.length`, or spreading, ALWAYS guard. Use `(items || []).map(...)`, `Array.isArray(x) ? x : []`, destructure with defaults `const { tags = [] } = task;`. Every state list MUST initialize to `[]`. Every record array field MUST default to `[]` when accessed.
- No `import` / `export` / `require`. No `<script>` / `<html>` / `<head>`. No `ReactDOM.createRoot` calls — the host adds those.
- Tailwind CDN is preloaded; ONLY Tailwind utility classes for any extra styling. No external CSS, no inline `<style>` tags.
- Icons: ALWAYS `<Icon name="user" />` with a string name (lowercase, kebab). NEVER `<Icons.User />`, `<icons.User />`, `<Lucide.User />`, or any object-dot-component reference — those crash with "Cannot read properties of undefined".
- The app MUST be fully interactive: forms submit, lists add/edit/delete, navigation switches views, modals open/close, toggles toggle, filters apply.
- Seed 6-10 realistic items per entity from the SRS so screens are populated on first paint.
- 300-700 lines of `App` + helpers is the sweet spot. Every feature in the SRS must be reachable in the UI.
- Use ONLY widely-supported JS syntax. No decorators, no top-level await. Use `<Fragment>` instead of `<>`.

═══════════════════════════════════════════════════════════════════
PART 2 — COMPONENT LIBRARY (available globally — USE BY NAME)
═══════════════════════════════════════════════════════════════════
""" + COMPONENT_REFERENCE + """

═══════════════════════════════════════════════════════════════════
PART 3 — APP COMPOSITION RULES
═══════════════════════════════════════════════════════════════════
1. ROOT MUST be: `<AppShell sidebar={<Sidebar .../>} topbar={<Topbar .../>}>{pageContent}</AppShell>`. AppShell already provides the scrollable main region — do NOT add extra `flex h-full` wrappers around it.
2. View switching: a single `view` state + `Sidebar onSelect`. Render the active page component inside AppShell.
3. Page composition pattern:
     <Fragment>
       <PageHeader title="Tasks" subtitle="..." actions={<><Button variant="outline" leftIcon="filter">Filter</Button><Button leftIcon="plus" onClick={...}>New</Button></>} />
       <div className="grid gap-6">
         <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
           <KpiCard ... /> <KpiCard ... /> ...
         </div>
         <Card><CardHeader><CardTitle>Recent</CardTitle></CardHeader><CardContent><Table .../></CardContent></Card>
       </div>
     </Fragment>
4. Lists: prefer `<Table columns={...} rows={...} />`. Inside `render`, return real components: `<Badge variant="success">Active</Badge>`, `<Avatar name={row.owner} />`, `<Button size="sm" variant="ghost">Edit</Button>`. Do NOT inline raw className strings when a component fits.
5. Dashboards: KPI grid (`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4`) on top, then a 2-column section (recent activity + quick stats) below. Use `<Section>` for grouped content blocks.
6. Forms: `<Card><CardContent className="space-y-4 pt-6">` with `<FormField label="..."><Input .../></FormField>` rows; primary action in `<CardFooter>` using `<Button>`.
7. Modals: ALWAYS the `<Dialog>` component (it already handles backdrop, max-h scroll, footer stacking). Pass form fields as children and Cancel/Save as `footer` Buttons.
8. Empty data: `<EmptyState icon="..." title="..." description="..." action={<Button>...</Button>} />` — never a blank pane.
9. Kanban: use `<KanbanBoard columns={...} renderCard={...} />`.
10. Status / type tags: `<Badge variant="success|warning|destructive|info|secondary">{label}</Badge>`. Map status strings to variants.
11. Avatars: `<Avatar name={user.name} />` (auto-deterministic color from name hash).
12. Dates: `formatDate(iso)`. Money: `formatMoney(n, "USD")`. Numbers in KPI/table cells should use `tabular-nums` (KpiCard already does).
13. NEVER use fixed `style={{width:..., height:...}}` for layout — only Tailwind utilities and the components above. AppShell, Sidebar, Topbar already enforce the right shrink/min-w-0 layout, so you don't need to fight overflow.

═══════════════════════════════════════════════════════════════════
PART 4 — INTERACTION & POLISH
═══════════════════════════════════════════════════════════════════
- Hover/active/focus states are already baked into the components — just use them.
- Use `useToasts()` for confirmations: `const { toasts, push, dismiss } = useToasts();` then mount `<ToastContainer toasts={toasts} onDismiss={dismiss} />` once at the top level. Call `push({ title, description, variant: "success" })` after mutations.
- DropdownMenu for row actions (edit / duplicate / delete).
- Filtering: a `<Tabs>` row above the table, plus an `<Input>` search box. Drive the displayed `rows` from the filter state.
- Realistic seeds: actual-sounding names, dates within ±60 days, varied statuses/priorities, plausible amounts. No "Lorem ipsum".

═══════════════════════════════════════════════════════════════════
PART 5 — SELF-CHECK BEFORE OUTPUTTING (verify each silently)
═══════════════════════════════════════════════════════════════════
1. Did I USE the component library (Button, Card, Sidebar, Topbar, AppShell, Dialog, Table, Badge, Avatar, KpiCard, EmptyState, Tabs, FormField, Input...) instead of writing raw className strings?
2. Did I NOT redefine any of those components?
3. Is the root `<AppShell sidebar={<Sidebar...>} topbar={<Topbar...>}>...</AppShell>`?
4. Are status pills `<Badge>`s, user chips `<Avatar>`s, KPIs `<KpiCard>`s?
5. Are arrays guarded against undefined before `.map`?
6. Is every top-level helper fully prop-driven (no closure leakage), OR defined inside `App`?
7. Is `function App() { ... }` declared exactly once?
8. Did I use `<Icon name="..." />` and never `<Icons.User />`?
9. Is every page populated with realistic seed data (6-10 records per entity)?
10. Are there modals (Dialog) for create/edit and an EmptyState for empty lists?

If any answer is "no", fix before outputting."""


def generate_user_prompt(srs_json: dict) -> str:
    srs_str = json.dumps(srs_json, indent=2, ensure_ascii=False)
    return f"""Build the application described by this SRS as a complete single-page React app composed from the pre-loaded shadcn-style component library described in your system prompt.

Infer the domain (task manager, hotel booking, inventory, CRM, blog, e-commerce, etc.) from the SRS and produce ALL the screens it implies — dashboard, list, detail/form, settings — wired together with internal page state.

- If `entities` are present, model them in JS objects with realistic fields and seed 6-10 examples per entity.
- If `features` are present, every feature must be reachable in the UI (a sidebar item, page button, or row action).
- If `pages[].layout` is set, render that page using the matching composition:
    dashboard → `<KpiCard>` grid + `<Card><Table/></Card>` recent table + secondary `<Card>` blocks
    list      → `<Tabs>` filter + search `<Input>` + `<Table>` (with `<Badge>`/`<Avatar>` cells, `<DropdownMenu>` row actions) + `<EmptyState>` fallback
    kanban    → `<KanbanBoard>` with statuses as columns
    calendar  → month grid `<Card>` with day cells; click a day to open a `<Dialog>` of events
    form      → `<Card>` with stacked `<FormField>` rows, primary CTA in `<CardFooter>` `<Button>`
    detail    → 2-column: left `<Card>` summary + `<StatList>`, right `<Card>` activity / sub-list
    settings  → multiple `<Section>`s, each with `<Card>` and `<FormField>` rows + a `<Switch>` row
- If `navigation` is present, expose primary entries via `<Sidebar items={...} />` and secondary in a settings sub-nav.
- Mount `<ToastContainer>` once and call `push({{ ... }})` after create/edit/delete mutations.

REMEMBER — components are PRE-DEFINED and global. Use them by name. Do NOT redefine `Button`, `Card`, `Sidebar`, `AppShell`, `Dialog`, `Table`, `Badge`, `Avatar`, `KpiCard`, `EmptyState`, `Tabs`, `Input`, `FormField`, `Icon`, etc. Never write `<Icons.User />` — only `<Icon name="user" />`.

SRS JSON:
```json
{srs_str}
```

Return ONLY the JSX body (any helpers + `function App()`) as plain text. No markdown fences."""


PLAN_SYSTEM = """You are a senior product analyst and UI architect. You receive a rough or partial SRS and must return a HIGH-QUALITY, COMPREHENSIVE SRS as a JSON object that will fully drive a sample shadcn/ui frontend application.

HARD RULES:
- Output ONLY a single valid JSON object. No prose, no markdown fences.
- Preserve every fact the user already provided; never contradict it.
- Infer the domain from project name / description / features and fill in everything missing so a developer could build the full app from this spec alone.
- The JSON MUST contain these top-level keys:
  - project_name (string)
  - domain (string, e.g. "task management", "hotel booking")
  - description (1-3 sentences)
  - brand: { name, tagline, primary_color (hex), accent_color (hex) }
  - entities: array of { name, fields: [{ name, type, required, enum?, example }] } — core entities needed to make the app work
  - features: array of { name, description, primary_screen } — every feature the SRS hints at, plus essentials (search, filtering, settings) when reasonable
  - pages: array of { id, name, role, key_components, layout } — every screen the user will navigate. `layout` is one of: "dashboard" | "list" | "kanban" | "calendar" | "form" | "detail" | "settings".
  - navigation: { primary: [string], secondary?: [string] }
  - sample_data: object keyed by entity name → array of 6-10 realistic seed records using the entity's fields
  - ui_preferences: { density: "comfortable"|"compact", style: "shadcn", radius: "rounded-md"|"rounded-lg"|"rounded-xl", scheme: "zinc" (default) }
- Keep the JSON SELF-CONSISTENT — entity names referenced in `pages` and `sample_data` must match exactly.
- Sample records must be realistic: real-sounding names, realistic dates within ±60 days of today, varied statuses/priorities, plausible amounts. No "Lorem ipsum"."""


def plan_user_prompt(rough_srs: dict) -> str:
    return f"""Enrich the following SRS into the full structured spec described in the system prompt. Keep all user-provided facts intact and fill in everything missing.

INPUT SRS:
```json
{json.dumps(rough_srs, indent=2, ensure_ascii=False)}
```

Return ONLY the enriched JSON object."""


REFINE_SYSTEM = """You are updating an existing single-page React app (Babel-runtime, Tailwind, shadcn-style component library pre-loaded) based on a user instruction.

A pre-loaded component library is GLOBALLY AVAILABLE: AppShell, Sidebar, Topbar, PageHeader, Section, Card/CardHeader/CardTitle/CardDescription/CardContent/CardFooter, KpiCard, Button, IconButton, Badge, Avatar, Input, Textarea, Select, Checkbox, Switch, Label, FormField, Separator, Tabs, Table, EmptyState, Dialog, Sheet, ToastContainer, useToasts, DropdownMenu, Breadcrumb, ProgressBar, Skeleton, StatList, KanbanBoard, Icon (string-name), formatDate, formatMoney, cx. Do NOT redefine them.

HARD RULES:
- Return the FULL updated JSX body, not a diff or partial snippet.
- Preserve all existing functionality unless the instruction explicitly removes it.
- Honor the user's visual / structural request precisely (e.g. 'smaller navbar', 'glass banner', 'teal accent', 'add dark mode toggle').
- Do not add `import`, `export`, or top-level `ReactDOM.createRoot` calls. Do not redeclare destructured hooks.
- Do not redefine library components — extend them by passing props/className overrides.
- Output ONLY the JSX code (helpers + `function App()`). No markdown fences, no explanations.

CONTRACT (do not break the runtime):
- `function App() { ... }` exactly once. Top-level helpers must be fully prop-driven OR defined inside `App`.
- Defensive arrays: `(items || []).map(...)`, `Array.isArray(x) ? x : []`.
- Icons: `<Icon name="..." />` only. Never `<Icons.User />` or any object-dot-component reference.
- Never reference `App`'s state/handlers from a top-level helper — pass via props or move the helper inside `App`."""


def refine_user_prompt(current_code: str, instruction: str) -> str:
    return f"""USER INSTRUCTION:
{instruction}

CURRENT JSX CODE:
```jsx
{current_code}
```

Return the full updated JSX body."""


REPAIR_SYSTEM = """You are repairing a single-page React app (Babel-runtime, Tailwind, shadcn-style component library pre-loaded) that crashed at runtime OR has a broken layout.

A pre-loaded component library is GLOBALLY AVAILABLE: AppShell, Sidebar, Topbar, PageHeader, Section, Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter, KpiCard, Button, IconButton, Badge, Avatar, Input, Textarea, Select, Checkbox, Switch, Label, FormField, Separator, Tabs, Table, EmptyState, Dialog, Sheet, ToastContainer, useToasts, DropdownMenu, Breadcrumb, ProgressBar, Skeleton, StatList, KanbanBoard, Icon (string-name), formatDate, formatMoney, cx. They are already defined — do NOT redefine.

HARD RULES:
- Return the FULL fixed JSX body, not a diff or partial snippet.
- Diagnose the error message, locate the cause in the current code, and fix it WITHOUT changing the app's intended behavior, screens, or visual design.
- Preserve all existing functionality and the shadcn/ui aesthetic.
- Do not add `import`, `export`, or top-level `ReactDOM.createRoot` calls.
- The host already destructures `{ useState, useEffect, useMemo, useRef, useCallback, Fragment } = React;` — do NOT redeclare.
- Output ONLY the JSX code (helpers + `function App()`). No markdown fences, no explanations.

COMMON BUG CLASSES (check each):
1. **Closure leak (most common runtime crash):** a top-level helper references a variable (state / derived value / handler) that lives inside `App`. FIX: pass it as a prop, or move the helper inside `App`.
2. **Undefined `.map` / `.filter` / `.length`:** an array field was undefined. FIX: guard with `(items || []).map(...)`, `Array.isArray(x) ? x : []`, or destructure with defaults `const { tags = [] } = task;`.
2b. **`Cannot read properties of undefined (reading 'X')`** (where X is a PascalCase name like `User`, `Home`, `Settings`): the code is doing `<Icons.User />` or `Icons.User`. FIX: replace EVERY such reference with `<Icon name="user" />` (lowercase string name). The `Icon` helper is already provided globally — do NOT define a new one.
2c. **Redefining a library component:** if the model declared `function Button(...)`, `function Card(...)`, `function Sidebar(...)`, etc., DELETE that declaration — the host already provides it. Use the global one.
2d. **Constant referenced before declaration:** any `const STATUSES = {...}` etc. used by a top-level helper or `App` MUST be declared at the very top of the file. If it's currently inside `App` and used outside, move it OUT.
3. **Layout bugs (cut-off buttons / overflow):** prefer the library components — `<PageHeader actions={...}>`, `<Card>`, `<Table>` already enforce the right wrap/shrink/min-w-0 rules. If raw flex rows are mixing text + buttons, switch to `<PageHeader>` or apply `flex flex-wrap items-center justify-between gap-3` parent + `min-w-0 truncate` on text + `shrink-0 whitespace-nowrap` on buttons.
4. **Modal bleeds off-screen:** replace ad-hoc modals with `<Dialog open={...} onOpenChange={...} title="..." footer={...}>`. It handles backdrop, max-h scroll, and footer stacking automatically.
5. **Page won't scroll / sidebar pushes content off:** use the global `<AppShell sidebar={<Sidebar.../>} topbar={<Topbar.../>}>...</AppShell>` instead of hand-rolling the layout.
6. **Table overflows the card:** use `<Table columns={...} rows={...} />` — it wraps in `overflow-x-auto`.
7. **Misnamed component:** `App` must be `function App() { ... }`, exactly once."""


def repair_user_prompt(current_code: str, error_message: str, error_stack: str) -> str:
    stack = (error_stack or "").strip()
    return f"""RUNTIME ERROR:
{error_message}

{('STACK:\n' + stack) if stack else ''}

CURRENT JSX CODE:
```jsx
{current_code}
```

Return the full repaired JSX body."""


def _clean_jsx(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:jsx|tsx|js|javascript|react)?\s*\n([\s\S]*?)\n```", text)
    if fence:
        text = fence.group(1)
    else:
        text = strip_code_fence(text)
    text = re.sub(r"^\s*import\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*export\s+default\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*export\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"</?script[^>]*>", "", text)
    text = re.sub(
        r"const\s*\{\s*useState[^}]*\}\s*=\s*React\s*;?\s*",
        "",
        text,
    )
    text = re.sub(r"ReactDOM\.createRoot\([\s\S]*?\)\s*\.\s*render\([\s\S]*?\)\s*;?", "", text)
    text = re.sub(r"ReactDOM\.render\([\s\S]*?\)\s*;?", "", text)
    return text.strip()


class SandboxStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, dict[str, Any]] = {}

    def create(self, srs_json: dict, model: str | None) -> dict:
        sandbox_id = str(uuid4())
        record = {
            "sandbox_id": sandbox_id,
            "srs_json": srs_json,
            "model": model,
            "code": "",
            "html": "",
            "version": 0,
            "history": [],
            "status": "generating",
            "created_at": time.time(),
            "error": None,
        }
        with self._lock:
            self._sessions[sandbox_id] = record
        return record

    def get(self, sandbox_id: str) -> dict | None:
        with self._lock:
            return self._sessions.get(sandbox_id)

    def update(self, sandbox_id: str, **changes) -> dict | None:
        with self._lock:
            record = self._sessions.get(sandbox_id)
            if not record:
                return None
            record.update(changes)
            return record

    def append_history(self, sandbox_id: str, entry: dict) -> None:
        with self._lock:
            record = self._sessions.get(sandbox_id)
            if record is not None:
                record["history"].append(entry)


STORE = SandboxStore()


def _project_title(srs_json: dict) -> str:
    return (
        srs_json.get("project_name")
        or srs_json.get("name")
        or (srs_json.get("brand") or {}).get("name")
        or (srs_json.get("metadata") or {}).get("project")
        or "Generated App"
    )


def _wrap_html(srs_json: dict, app_jsx: str) -> str:
    title = _project_title(srs_json)
    safe_title = str(title).replace("<", "&lt;").replace(">", "&gt;")
    return (
        HTML_SHELL
        .replace("__TITLE__", safe_title)
        .replace("__UI_LIBRARY__", UI_LIBRARY_JSX)
        .replace("__APP_JSX__", app_jsx)
    )


def run_generation(sandbox_id: str) -> dict:
    record = STORE.get(sandbox_id)
    if not record:
        raise KeyError("sandbox not found")
    srs_json = record["srs_json"]
    model = record.get("model")
    try:
        llm = build_llm(model=model, temperature=0.4)
        raw = llm_invoke(
            llm,
            [
                ("system", GENERATE_SYSTEM),
                ("human", generate_user_prompt(srs_json)),
            ],
        )
        code = _clean_jsx(raw)
        if not code:
            raise RuntimeError("LLM returned empty JSX")
        html = _wrap_html(srs_json, code)
        STORE.update(sandbox_id, code=code, html=html, version=1, status="ready")
        STORE.append_history(
            sandbox_id,
            {"version": 1, "kind": "generate", "prompt": "(initial)", "ts": time.time()},
        )
    except Exception as exc:
        STORE.update(sandbox_id, status="failed", error=str(exc))
    return STORE.get(sandbox_id)


def generate_sandbox(srs_json: dict, model: str | None = None) -> dict:
    record = STORE.create(srs_json, model)
    return run_generation(record["sandbox_id"])


def plan_srs(rough_srs: dict, model: str | None = None) -> dict:
    llm = build_llm(model=model, temperature=0.2)
    raw = llm_invoke(
        llm,
        [
            ("system", PLAN_SYSTEM),
            ("human", plan_user_prompt(rough_srs)),
        ],
    )
    cleaned = strip_code_fence(raw).strip()
    fence = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Planner did not return a JSON object")
    return json.loads(cleaned[start : end + 1])


def repair_sandbox(sandbox_id: str, error_message: str, error_stack: str = "") -> dict:
    record = STORE.get(sandbox_id)
    if not record:
        raise KeyError("sandbox not found")
    if not record.get("code"):
        raise ValueError("sandbox has no code yet")
    llm = build_llm(model=record.get("model"), temperature=0.2)
    raw = llm_invoke(
        llm,
        [
            ("system", REPAIR_SYSTEM),
            ("human", repair_user_prompt(record["code"], error_message, error_stack)),
        ],
    )
    code = _clean_jsx(raw)
    if not code:
        raise RuntimeError("LLM returned empty JSX during repair")
    html = _wrap_html(record["srs_json"], code)
    new_version = (record.get("version") or 0) + 1
    STORE.update(sandbox_id, code=code, html=html, version=new_version, status="ready", error=None)
    STORE.append_history(
        sandbox_id,
        {
            "version": new_version,
            "kind": "repair",
            "prompt": f"auto-repair: {error_message[:120]}",
            "ts": time.time(),
        },
    )
    return STORE.get(sandbox_id)


def refine_sandbox(sandbox_id: str, instruction: str) -> dict:
    record = STORE.get(sandbox_id)
    if not record:
        raise KeyError("sandbox not found")
    if not record.get("code"):
        raise ValueError("sandbox has no code yet")
    llm = build_llm(model=record.get("model"), temperature=0.3)
    raw = llm_invoke(
        llm,
        [
            ("system", REFINE_SYSTEM),
            ("human", refine_user_prompt(record["code"], instruction)),
        ],
    )
    code = _clean_jsx(raw)
    if not code:
        raise RuntimeError("LLM returned empty JSX during refine")
    html = _wrap_html(record["srs_json"], code)
    new_version = (record.get("version") or 0) + 1
    STORE.update(sandbox_id, code=code, html=html, version=new_version, status="ready")
    STORE.append_history(
        sandbox_id,
        {"version": new_version, "kind": "refine", "prompt": instruction, "ts": time.time()},
    )
    return STORE.get(sandbox_id)
