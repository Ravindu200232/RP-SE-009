// Shared UI primitives for AgentForge Studio
import React, { useEffect, useRef, useState } from "react";

const LOADING_GIF_SRC = "/Tabextend%20GIF%20by%20Nightingale.gif";

// ── Inline SVG icon system (no CDN dependency) ────────────────────────────────
const ICON_PATHS = {
  LayoutDashboard: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
  Plus: "M12 5v14M5 12h14",
  Brain: "M9.5 2a2.5 2.5 0 0 1 0 5h-1a6 6 0 0 0-6 6 4 4 0 0 0 4 4h9a4 4 0 0 0 4-4 6 6 0 0 0-6-6h-1a2.5 2.5 0 0 1 0-5M9 13h.01M15 13h.01",
  Palette: "M12 2a10 10 0 1 0 10 10 4 4 0 0 1-4-4 4 4 0 0 1-4-4",
  Code2: "M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 13l-2-2 2-2M14 9l2 2-2 2",
  FlaskConical: "M10 2v7.31L5.5 15A2 2 0 0 0 7.25 18h9.5a2 2 0 0 0 1.75-3L14 9.31V2M6 2h12",
  Rocket: "M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09zM12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z",
  Archive: "M21 8v13H3V8M1 3h22v5H1zM10 12h4",
  GitBranch: "M6 3v12M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 9a9 9 0 0 1-9 9",
  Database: "M12 2c-5.52 0-10 2.24-10 5v10c0 2.76 4.48 5 10 5s10-2.24 10-5V7c0-2.76-4.48-5-10-5zM2 7c0 2.76 4.48 5 10 5s10-2.24 10-5M2 12c0 2.76 4.48 5 10 5s10-2.24 10-5",
  Settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
  ChevronRight: "M9 18l6-6-6-6",
  ChevronLeft: "M15 18l-6-6 6-6",
  ChevronDown: "M6 9l6 6 6-6",
  ChevronUp: "M18 15l-6-6-6 6",
  Search: "M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z",
  Bell: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0",
  Download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
  Mic: "M12 1a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3zM19 10a7 7 0 0 1-14 0M12 19v4M8 23h8",
  Upload: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12",
  Zap: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
  Check: "M20 6L9 17l-5-5",
  CheckCircle2: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM7 12l3 3 7-7",
  X: "M18 6L6 18M6 6l12 12",
  XCircle: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM15 9l-6 6M9 9l6 6",
  Edit2: "M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z",
  Lock: "M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2zM7 11V7a5 5 0 0 1 10 0v4",
  AlertCircle: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 8v4M12 16h.01",
  AlertTriangle: "M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01",
  Info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 8h.01M12 12v4",
  FolderOpen: "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z",
  FileText: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8",
  FileCode: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M10 13l-2 2 2 2M14 13l2 2-2 2",
  File: "M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM13 2v7h7",
  Image: "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2zM8.5 10a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM21 15l-5-5L5 21",
  ExternalLink: "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3",
  ArrowRight: "M5 12h14M12 5l7 7-7 7",
  ArrowLeft: "M19 12H5M12 19l-7-7 7-7",
  Send: "M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z",
  Save: "M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2zM17 21v-8H7v8M7 3v5h8",
  RefreshCw: "M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15",
  Play: "M5 3l14 9-14 9V3z",
  Pause: "M6 4h4v16H6zM14 4h4v16h-4z",
  Bug: "M8 2l1.88 1.88M14.12 3.88 16 2M9 7.13v-1a3.003 3.003 0 0 1 6 0v1M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6M12 20v-9M6.53 9C4.6 8.8 3 7.1 3 5M6 13H2M3 21c0-3 1.2-5.2 3.5-6M20.97 5c0 2.1-1.6 3.8-3.5 4M22 13h-4M20.5 21c-2.3.8-3.5-1-3.5-4",
  TestTube2: "M14.5 2v17.5c0 1.4-1.1 2.5-2.5 2.5h0c-1.4 0-2.5-1.1-2.5-2.5V2M8.5 2h7M14.5 16h-5",
  Link2: "M15 7h3a5 5 0 0 1 0 10h-3m-6 0H6A5 5 0 0 1 6 7h3M8 12h8",
  Star: "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
  Package: "M16.5 9.4l-9-5.19M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12",
  Box: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16zM3.27 6.96L12 12.01l8.73-5.05M12 22.08V12",
  Cloud: "M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z",
  Github: "M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22",
  GitMerge: "M18 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM6 9v4a3 3 0 0 0 3 3h6",
  Camera: "M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  Server: "M2 2h20v8H2zM2 14h20v8H2zM6 6h.01M6 18h.01",
  Terminal: "M4 17l6-6-6-6M12 19h8",
  Maximize2: "M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7",
  Columns: "M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7m0-18H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h7m0-18v18",
  Pin: "M12 17v5M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7M9 10.76V7M15 7H9M15 10.76V7",
  GripVertical: "M9 5h.01M9 12h.01M9 19h.01M15 5h.01M15 12h.01M15 19h.01",
  Sparkles: "M12 3l1.09 3.26L16.5 7.5l-3.41 1.24L12 12l-1.09-3.26L7.5 7.5l3.41-1.24L12 3zM5 14l.73 2.27L8 17l-2.27.73L5 20l-.73-2.27L2 17l2.27-.73L5 14zM20 14l.73 2.27L23 17l-2.27.73L20 20l-.73-2.27L17 17l2.27-.73L20 14z",
  Lightbulb: "M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5M9 18h6M10 22h4",
  MessageSquare: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z",
  Copy: "M20 9h-9a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2zM5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1",
  Eye: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  EyeOff: "M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19M1 1l22 22",
  Paintbrush: "M18.37 2.63 14 7l-1.59-1.59a2 2 0 0 0-2.82 0L8 7l9 9 1.59-1.59a2 2 0 0 0 0-2.82L17 10l4.37-4.37a2.12 2.12 0 1 0-3-3zM9 8c-2 3-4 3.5-7 4l8 10c2-1 6-5 6-7M14.5 17.5 4.5 15",
  HelpCircle: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01",
  Globe: "M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z",
  Tag: "M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01",
  RotateCcw: "M1 4v6h6M3.51 15a9 9 0 1 0 .49-3.6",
  Layers: "M12 2l10 6.5v7L12 22 2 15.5v-7zM12 22v-7M22 8.5l-10 7-10-7",
  Hash: "M4 9h16M4 15h16M10 3L8 21M16 3l-2 18",
  List: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  Loader2: "M21 12a9 9 0 1 1-6.219-8.56",
  ShieldCheck: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10zM9 12l2 2 4-4",
  ShieldOff: "M19.69 14a6.9 6.9 0 0 0 .31-2V5l-8-3-3.16 1.18M4.73 4.73 4 5v7c0 6 8 10 8 10a20.29 20.29 0 0 0 5.62-4.38M1 1l22 22",
  Trash2: "M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6",
  FileOutput: "M4 22h14a2 2 0 0 0 2-2V7.5L14.5 2H6a2 2 0 0 0-2 2v4M14 2v6h6M2 15h10M9 12l3 3-3 3",
  Square: "M3 3h18v18H3z",
  CheckSquare: "M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  Inbox: "M22 12h-6l-2 3h-4l-2-3H2M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
  GitCompare: "M18 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM13 6h3a2 2 0 0 1 2 2v7M11 18H8a2 2 0 0 1-2-2V9",
  FunctionSquare: "M3 3h18v18H3zM9 9h1l2 6 2-6h1M9 15h6",
  Cpu: "M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0M5 5h14v14H5zM2 12h3M19 12h3M12 2v3M12 19v3",
  Activity: "M22 12h-4l-3 9L9 3l-3 9H2",
  FlaskRound: "M10 2v7.31L5.5 15A2 2 0 0 0 7.25 18h9.5a2 2 0 0 0 1.75-3L14 9.31V2M6 2h12",
  Columns2: "M3 3h8v18H3zM13 3h8v18h-8z",
  FolderSearch: "M11 20H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2M13 20l2-2M17.5 17.5l3 3M15 16a3 3 0 1 0 6 0 3 3 0 0 0-6 0",
  Workflow: "M17 20h5v-2a3 3 0 0 0-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 0 1 5.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 0 1 9.288 0M15 7a3 3 0 1 1-6 0 3 3 0 0 1 6 0z",
  PanelRight: "M3 3h18v18H3zM15 3v18",
  MemoryStick: "M6 19v-4M10 19v-4M14 19v-4M18 19v-4M3 9l2.45-4.9A2 2 0 0 1 7.24 3h9.52a2 2 0 0 1 1.8 1.1L21 9M3 9h18v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  BrainCircuit: "M12 4a8 8 0 0 0-5.899 13.51M12 4a8 8 0 0 1 5.899 13.51M12 4v4M12 22v-4M12 8a4 4 0 0 0-4 4M12 8a4 4 0 0 1 4 4M8 12H4M20 12h-4",
};

function LoadingGif({ size = 16, className = "", alt = "Loading" }) {
  return (
    <img
      src={LOADING_GIF_SRC}
      alt={alt}
      width={size}
      height={size}
      className={`inline-block flex-shrink-0 object-contain rounded-none border-0 bg-transparent shadow-none ${className}`.trim()}
      style={{ width: size, height: size }}
    />
  );
}

function Icon({ name, size = 16, className = "" }) {
  if (name === "Loader2") {
    return <LoadingGif size={size} className={className.replace(/\banimate-spin\b/g, "").trim()} alt="Loading" />;
  }
  const d = ICON_PATHS[name];
  if (!d) return <span className={`inline-block flex-shrink-0 ${className}`} style={{ width: size, height: size }} />;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`flex-shrink-0 ${className}`}
      style={{ display: "inline-block" }}
    >
      <path d={d} />
    </svg>
  );
}

// ── Button ────────────────────────────────────────────────────────────────────
function Btn({ children, variant = "default", size = "sm", onClick, className = "", disabled = false, icon }) {
  const base = "inline-flex items-center gap-1.5 font-medium rounded-lg transition-all duration-150 cursor-pointer select-none whitespace-nowrap";
  const sizes = { xs: "px-2 py-1 text-xs", sm: "px-3 py-1.5 text-xs", md: "px-4 py-2 text-sm", lg: "px-5 py-2.5 text-sm" };
  const variants = {
    default: "bg-white hover:bg-gray-50 text-gray-900 border border-gray-200",
    primary: "bg-[#1f6feb] hover:bg-[#388bfd] text-white border border-transparent",
    ghost: "bg-transparent hover:bg-gray-100 text-gray-600 border border-transparent",
    danger: "bg-transparent hover:bg-[#3d1a1a] text-[#f85149] border border-[#f85149]/30",
    success: "bg-[#0a3d2e] hover:bg-[#0d5540] text-[#3fb950] border border-[#3fb950]/30",
    violet: "bg-[#000000] hover:bg-[#111111] text-white border border-[#000000]",
    amber: "bg-[#3d2400] hover:bg-[#5c3800] text-[#f0883e] border border-[#f0883e]/30",
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${base} ${sizes[size] || sizes.sm} ${variants[variant] || variants.default} ${disabled ? "opacity-40 cursor-not-allowed" : ""} ${className}`}
    >
      {icon && <Icon name={icon} size={12} />}
      {children}
    </button>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────
function Badge({ children, color = "default", dot = false }) {
  const colors = {
    default: "bg-white text-gray-600 border-gray-200",
    blue: "bg-[#000000] text-white border-[#000000]",
    violet: "bg-[#2d1f5e] text-[#a78bfa] border-[#a78bfa]/30",
    amber: "bg-[#3d2400] text-[#f0883e] border-[#d29922]/30",
    green: "bg-[#0a3d2e] text-[#3fb950] border-[#3fb950]/30",
    red: "bg-[#3d1a1a] text-[#f85149] border-[#f85149]/30",
    purple: "bg-[#2d1f5e] text-[#d2a8ff] border-[#d2a8ff]/20",
  };
  const dotColors = { blue: "bg-[#58a6ff]", violet: "bg-[#a78bfa]", amber: "bg-[#f0883e]", green: "bg-[#3fb950]", red: "bg-[#f85149]", default: "bg-[#8b949e]", purple: "bg-[#d2a8ff]" };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${colors[color] || colors.default}`}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full ${dotColors[color] || dotColors.default} ${color !== "default" && color !== "red" ? "animate-pulse" : ""}`} />}
      {children}
    </span>
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────
function Card({ children, className = "", onClick, hover = false }) {
  return (
    <div
      onClick={onClick}
      className={`bg-white/85 backdrop-blur-md border border-white/70 shadow-sm rounded-xl ${hover ? "hover:border-gray-300 hover:bg-white/95 cursor-pointer transition-all duration-150" : ""} ${className}`}
    >
      {children}
    </div>
  );
}

// ── KPI Card ──────────────────────────────────────────────────────────────────
function KPICard({ label, value, sub, color = "default", icon }) {
  const colors = { default: "text-gray-900", blue: "text-[#58a6ff]", violet: "text-[#a78bfa]", amber: "text-[#f0883e]", green: "text-[#3fb950]" };
  return (
    <Card className="p-4 flex flex-col gap-2 hover:border-gray-300 transition-all duration-150">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-500 font-medium">{label}</span>
        {icon && <Icon name={icon} size={14} className="text-gray-400" />}
      </div>
      <span className={`text-2xl font-bold tabular-nums ${colors[color] || colors.default}`}>{value}</span>
      {sub && <span className="text-xs text-gray-500">{sub}</span>}
    </Card>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function Tabs({ tabs, active, onChange, className = "" }) {
  return (
    <div className={`flex gap-1 border-b border-gray-200 ${className}`}>
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`px-3 py-2 text-xs font-medium transition-all duration-150 border-b-2 -mb-px ${
            active === t.id
              ? "border-[#58a6ff] text-gray-900"
              : "border-transparent text-gray-500 hover:text-gray-900 hover:border-gray-300"
          }`}
        >
          {t.label}
          {t.count !== undefined && (
            <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-xs ${active === t.id ? "bg-[#1f6feb] text-white" : "bg-gray-100 text-gray-500"}`}>{t.count}</span>
          )}
        </button>
      ))}
    </div>
  );
}

// ── Section Header ────────────────────────────────────────────────────────────
function SectionHeader({ title, subtitle, actions, className = "" }) {
  return (
    <div className={`flex items-start justify-between gap-4 ${className}`}>
      <div>
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  );
}

// ── Page Header ───────────────────────────────────────────────────────────────
function PageHeader({ title, subtitle, actions, breadcrumb }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div>
        {breadcrumb && (
          <div className="flex items-center gap-1 text-xs text-gray-400 mb-1">
            {breadcrumb.map((b, i) => (
              <span key={i} className="flex items-center gap-1">
                {i > 0 && <Icon name="ChevronRight" size={10} />}
                <span className={i === breadcrumb.length - 1 ? "text-gray-600" : ""}>{b}</span>
              </span>
            ))}
          </div>
        )}
        <h1 className="text-xl font-bold text-gray-900">{title}</h1>
        {subtitle && <p className="text-sm text-gray-500 mt-1 max-w-2xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0 pt-1">{actions}</div>}
    </div>
  );
}

// ── Status Badge (agent-colored) ──────────────────────────────────────────────
function AgentBadge({ agent, status }) {
  const cfg = {
    "Agent 1": { color: "blue", icon: "Brain" },
    "Agent 2": { color: "violet", icon: "Code2" },
    "Agent 3": { color: "amber", icon: "FlaskConical" },
    "Agent 4": { color: "green", icon: "Rocket" },
  };
  const c = cfg[agent] || { color: "default", icon: "Bot" };
  return <Badge color={c.color} dot>{agent}: {status}</Badge>;
}

// ── Status color helper ───────────────────────────────────────────────────────
function statusBadge(status) {
  const map = {
    complete: <Badge color="green">Complete</Badge>,
    active: <Badge color="blue" dot>Active</Badge>,
    pending: <Badge color="default">Pending</Badge>,
    "in-progress": <Badge color="violet" dot>In Progress</Badge>,
    generated: <Badge color="green">Generated</Badge>,
    approved: <Badge color="green">Approved</Badge>,
    review: <Badge color="amber">Under Review</Badge>,
    failed: <Badge color="red">Failed</Badge>,
    warning: <Badge color="amber">Warning</Badge>,
    healthy: <Badge color="green">Healthy</Badge>,
    done: <Badge color="green">Done</Badge>,
    resolved: <Badge color="green">Resolved</Badge>,
    "fix-applied": <Badge color="violet">Fix Applied</Badge>,
    "not-started": <Badge color="default">Not Started</Badge>,
    live: <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-[#50e61e] text-black border border-[#50e61e]"><span className="w-1.5 h-1.5 rounded-full bg-black" />Live</span>,
    blocked: <Badge color="red">Blocked</Badge>,
  };
  return map[status?.toLowerCase()] || <Badge color="default">{status}</Badge>;
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function ToastContainer({ toasts }) {
  return (
    <div className="fixed bottom-16 right-4 z-50 flex flex-col gap-2 pointer-events-none" style={{ maxWidth: 380 }}>
      {toasts.map(t => (
        <div key={t.id} className="pointer-events-auto bg-white border border-gray-200 rounded-xl px-4 py-3 shadow-2xl flex items-start gap-3 animate-slideup">
          <Icon name={t.type === "success" ? "CheckCircle2" : t.type === "error" ? "XCircle" : "Info"} size={16} className={t.type === "success" ? "text-[#3fb950] mt-0.5" : t.type === "error" ? "text-[#f85149] mt-0.5" : "text-[#58a6ff] mt-0.5"} />
          <p className="text-xs text-gray-900 leading-relaxed">{t.msg}</p>
        </div>
      ))}
    </div>
  );
}

// ── Empty State ───────────────────────────────────────────────────────────────
function EmptyState({ icon = "Inbox", title, subtitle, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="w-12 h-12 rounded-2xl bg-gray-100 flex items-center justify-center mb-4">
        <Icon name={icon} size={22} className="text-gray-400" />
      </div>
      <p className="text-sm font-medium text-gray-700">{title}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1 max-w-xs">{subtitle}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ── Progress Bar ──────────────────────────────────────────────────────────────
function ProgressBar({ value, color = "blue", className = "" }) {
  const colors = { blue: "bg-[#1f6feb]", violet: "bg-[#7c3aed]", amber: "bg-[#d97706]", green: "bg-[#50e61e]", default: "bg-gray-300" };
  return (
    <div className={`h-1.5 bg-gray-200 rounded-full overflow-hidden ${className}`}>
      <div className={`h-full rounded-full transition-all duration-500 ${colors[color] || colors.blue}`} style={{ width: `${value}%` }} />
    </div>
  );
}

// ── Code Block ────────────────────────────────────────────────────────────────
function CodeBlock({ code, lang = "yaml", className = "" }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(code).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className={`relative bg-white border border-gray-200 rounded-lg overflow-hidden ${className}`}>
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200">
        <span className="text-xs text-gray-400 font-mono">{lang}</span>
        <button onClick={copy} className="text-xs text-gray-500 hover:text-gray-900 flex items-center gap-1 transition-colors">
          <Icon name={copied ? "Check" : "Copy"} size={12} />
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="p-3 text-xs font-mono text-gray-700 overflow-x-auto leading-relaxed">{code}</pre>
    </div>
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────
function Table({ cols, rows, className = "" }) {
  return (
    <div className={`overflow-x-auto ${className}`}>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-200">
            {cols.map((c, i) => (
              <th key={i} className="text-left px-3 py-2.5 text-gray-400 font-medium whitespace-nowrap">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2.5 text-gray-600">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Input ─────────────────────────────────────────────────────────────────────
function Input({ label, placeholder, value, onChange, type = "text", className = "" }) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label && <label className="text-xs font-medium text-gray-600">{label}</label>}
      <input
        type={type}
        value={value || ""}
        onChange={e => onChange?.(e.target.value)}
        placeholder={placeholder}
        className="bg-white border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#388bfd] transition-colors"
      />
    </div>
  );
}

// ── Select ────────────────────────────────────────────────────────────────────
function Select({ label, options, value, onChange, className = "" }) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label && <label className="text-xs font-medium text-gray-600">{label}</label>}
      <select
        value={value || ""}
        onChange={e => onChange?.(e.target.value)}
        className="bg-white border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-900 focus:outline-none focus:border-[#388bfd] transition-colors"
      >
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
}

// ── Textarea ──────────────────────────────────────────────────────────────────
function Textarea({ label, placeholder, value, onChange, rows = 4, className = "" }) {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label && <label className="text-xs font-medium text-gray-600">{label}</label>}
      <textarea
        value={value || ""}
        onChange={e => onChange?.(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="bg-white border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-900 placeholder-gray-400 focus:outline-none focus:border-[#388bfd] transition-colors resize-none leading-relaxed"
      />
    </div>
  );
}

// ── Inspector Panel ───────────────────────────────────────────────────────────
function InspectorPanel({ title = "Inspector", children, className = "" }) {
  return (
    <aside className={`w-64 flex-shrink-0 border-l border-gray-200 bg-white flex flex-col overflow-y-auto ${className}`}>
      <div className="px-4 py-3 border-b border-gray-200">
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">{title}</span>
      </div>
      <div className="flex-1 overflow-y-auto">{children}</div>
    </aside>
  );
}

function InspectorSection({ title, children }) {
  return (
    <div className="px-4 py-3 border-b border-gray-200">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">{title}</p>
      {children}
    </div>
  );
}

function InspectorRow({ label, value }) {
  return (
    <div className="flex items-center justify-between gap-2 mb-1.5">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="text-xs text-gray-600 text-right truncate max-w-[120px]">{value}</span>
    </div>
  );
}

export { Icon, LoadingGif, Btn, Badge, Card, KPICard, Tabs, SectionHeader, PageHeader, AgentBadge, statusBadge, ToastContainer, EmptyState, ProgressBar, CodeBlock, Table, Input, Select, Textarea, InspectorPanel, InspectorSection, InspectorRow };
