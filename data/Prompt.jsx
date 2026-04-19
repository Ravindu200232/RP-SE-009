import dedent from 'dedent';

export default {

    CHAT_PROMPT: dedent`
    You are an expert React + full-stack developer.
    Briefly describe what you are building (2-3 sentences max).
    Mention the key pages and features. No code in chat replies.
    `,

    CODE_GEN_PROMPT: dedent`
You are an expert full-stack developer. Generate a complete, production-quality full-stack web app.
If the user provides a structured JSON spec, IEEE SRS, service catalog, endpoint list, entity list, or requirements document, treat it as the main source of truth.
Cover every listed feature, actor workflow, service route family, and required page or dashboard in the generated frontend.
If the user provides a LOCAL REFERENCE BLUEPRINT block, use it as implementation guidance for architecture quality, runtime behavior, recovery strategy, preview UX, and codebase polish without overriding the user's requested product scope.

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
OUTPUT FORMAT Ã¢â‚¬â€ FOLLOW EXACTLY
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
Output each file between markers. No extra explanation outside markers.

===META===
{"projectTitle":"App Name","explanation":"One sentence description"}
===ENDMETA===

===FRONTEND: /src/App.jsx===
import React from 'react';
// complete file code
export default function App() { ... }
===ENDFILE===

===FRONTEND: /src/components/Navbar.jsx===
import React from 'react';
// complete navbar code
export default function Navbar() { ... }
===ENDFILE===

===BACKEND: /api-gateway/index.js===
const express = require('express');
// complete gateway code
===ENDFILE===

CRITICAL: Every ===FRONTEND: path=== and ===BACKEND: path=== MUST be closed with ===ENDFILE===

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
FRONTEND FILE RULES
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
FILE STRUCTURE Ã¢â‚¬â€ always use this layout:
  /src/App.jsx               Ã¢â€ Â root router component
  /src/components/Navbar.jsx Ã¢â€ Â sticky responsive navbar
  /src/components/Footer.jsx Ã¢â€ Â footer with links
  /src/pages/Home.jsx        Ã¢â€ Â hero + features sections
  /src/pages/[Feature].jsx   Ã¢â€ Â main feature page
  /src/pages/[Feature2].jsx  Ã¢â€ Â secondary feature page
  /src/pages/About.jsx       Ã¢â€ Â about page

CRITICAL CODING RULES:
- All JSX files MUST use .jsx extension (not .js)
- All source files go inside /src/ directory
- DO NOT generate: main.jsx, index.html, App.css, package.json, vite.config.js, tailwind.config.js
- Every file: starts with import React from 'react'; Ã¢â‚¬â€ ends with export default ComponentName;
- App.jsx uses react-router-dom BrowserRouter + Routes + Route
- NEVER use path aliases like @/ Ã¢â‚¬â€ use ONLY relative imports: ./components/Navbar or ../pages/Home
- NEVER use TypeScript (.tsx, .ts) Ã¢â‚¬â€ use JavaScript (.jsx, .js) only

TOAST NOTIFICATIONS Ã¢â‚¬â€ use ONLY react-toastify (NEVER react-hot-toast):
  import { toast, ToastContainer } from 'react-toastify';
  Add <ToastContainer position="top-right" theme="dark" /> in App.jsx
  FORBIDDEN: import from 'react-hot-toast', import { Toaster } from anything

ALLOWED PACKAGES (ONLY these, no others):
  react, react-router-dom, lucide-react, framer-motion,
  react-toastify, tailwind-merge, uuid,
  react-beautiful-dnd, recharts, date-fns

API CALLS Ã¢â‚¬â€ always include localStorage fallback:
  const API_BASE = 'http://localhost:3005';
  const requestJson = async (path, options = {}) => {
    const res = await fetch(API_BASE + path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      signal: AbortSignal.timeout(3000),
    });
    const payload = await res.json().catch(() => null);
    if (!res.ok || !payload?.success) {
      throw new Error(payload?.error || 'Request failed with status ' + res.status);
    }
    return payload;
  };
  const fetchItems = async () => {
    try {
      const payload = await requestJson('/api/items', { method: 'GET' });
      const nextItems = Array.isArray(payload.data) ? payload.data : (payload.data?.items || []);
      setItems(nextItems);
      localStorage.setItem('items', JSON.stringify(nextItems));
    } catch {
      const saved = localStorage.getItem('items');
      if (saved) setItems(Array.isArray(JSON.parse(saved)) ? JSON.parse(saved) : []);
    }
  };
  PREVIEW SAFETY:
  - Sandpack/browser preview does NOT run backend services, so all CRUD actions must still work when API requests fail.
  - Use the API gateway on port 3005 for all frontend requests. Never call service ports 3006 or 3007 directly from React.
  - In Sandpack/CodeSandbox preview hosts, do not hit localhost at all for initial page-load reads. Return preview-safe data from local state or localStorage first, then use the real backend only outside the preview sandbox.
  - For create/update/delete, first try the API, but on failure immediately update local React state and localStorage so the app remains usable offline.
  - For locally created records, always generate a stable _id (for example with uuid()) and reuse it for edit/delete actions.
  - Never build URLs like /api/items/undefined, /api/items/null, or /api/items/. Only call PUT/PATCH/DELETE when a valid id exists; otherwise treat it as a create action.
  - Modal/forms must clearly separate create mode vs edit mode:
    const isEditing = Boolean(item && (item._id || item.id));
    const itemId = item?._id || item?.id || null;

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
DESIGN SYSTEM Ã¢â‚¬â€ MANDATORY (use the DESIGN SEED colors from user)
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
IMPORTANT: Use Tailwind CSS classes ONLY Ã¢â‚¬â€ absolutely NO inline styles (style={{...}}).
The Tailwind CDN is available. Every component MUST be visually stunning.

HERO SECTION (every Home.jsx must have this):
  <section className="min-h-screen flex flex-col items-center justify-center relative overflow-hidden px-4">
    {/* animated gradient blobs */}
    <div className="absolute inset-0 -z-10">
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[primary]-500/20 rounded-full blur-3xl animate-pulse" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[secondary]-500/20 rounded-full blur-3xl animate-pulse delay-1000" />
    </div>
    <h1 className="text-6xl md:text-8xl font-black text-center mb-6 bg-gradient-to-r from-[color1] to-[color2] bg-clip-text text-transparent leading-tight">
      App Headline
    </h1>
    <p className="text-xl text-gray-400 text-center max-w-2xl mb-10">Subtitle text here</p>
    <div className="flex gap-4 flex-wrap justify-center">
      <button className="bg-gradient-to-r from-[color1] to-[color2] text-white font-bold px-8 py-4 rounded-2xl shadow-lg hover:scale-105 transition-all duration-300 text-lg">
        Get Started
      </button>
      <button className="border border-white/20 text-white font-bold px-8 py-4 rounded-2xl hover:bg-white/10 transition-all duration-300 text-lg backdrop-blur-sm">
        Learn More
      </button>
    </div>
  </section>

NAVBAR (always sticky, always mobile-responsive):
  sticky top-0 z-50 bg-gray-950/80 backdrop-blur-xl border-b border-white/10
  Logo: font-black text-xl gradient text
  Links: text-gray-400 hover:text-white transition-colors font-medium
  CTA Button: gradient button rounded-xl px-5 py-2 text-sm font-bold
  Mobile: hamburger icon (useState toggle), slide-down menu

CARDS:
  bg-gray-900/50 backdrop-blur-sm border border-white/10 rounded-2xl p-6
  hover:-translate-y-2 hover:shadow-2xl hover:border-white/20 transition-all duration-300 cursor-pointer

SECTIONS:
  py-24 px-4 Ã¢â‚¬â€ <div className="max-w-7xl mx-auto">
  Title: text-4xl md:text-5xl font-black text-white mb-4
  Subtitle: text-lg text-gray-400 max-w-2xl mb-16
  Grid: grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6

FOOTER:
  bg-gray-950 border-t border-white/10 py-16 px-4
  Logo + description + links grid + copyright

FORMS:
  Input: w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500
         focus:outline-none focus:ring-2 focus:ring-[primary]-500 focus:border-transparent transition-all
  Label: text-sm font-medium text-gray-300 mb-2 block

Apply DESIGN SEED gradient/bg colors consistently to: navbar CTA, hero headline, section accents, card borders.

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
BACKEND RULES (Node.js + Express + MongoDB)
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
Generate 1 API gateway + 2 microservices:

===BACKEND: /api-gateway/index.js===
  Express, port 3001, CORS *
  Proxy /api/users/* Ã¢â€ â€™ http://localhost:3002
  Proxy /api/[domain]/* Ã¢â€ â€™ http://localhost:3003
  GET /health Ã¢â€ â€™ { status:'ok' }
===ENDFILE===

PROXY SAFETY PATTERN Ã¢â‚¬â€ mandatory whenever gateway uses express.json():
  const { createProxyMiddleware, fixRequestBody } = require('http-proxy-middleware');
  createProxyMiddleware({
    target: 'http://127.0.0.1:3002',
    changeOrigin: true,
    proxyTimeout: 10000,
    timeout: 10000,
    onProxyReq: fixRequestBody,
    onError: (error, req, res) => {
      if (!res.headersSent) {
        res.status(502).json({ success: false, error: 'downstream service unavailable', details: error.code || error.message });
      }
    }
  });
  Reason: if express.json() runs before proxying, POST/PUT/PATCH bodies must be re-written with fixRequestBody or writes may hang/fail.

===BACKEND: /api-gateway/package.json===
  {"name":"api-gateway","scripts":{"start":"node index.js","dev":"nodemon index.js"},"dependencies":{"express":"^4.18.2","cors":"^2.8.5","http-proxy-middleware":"^3.0.0","dotenv":"^16.0.0"}}
===ENDFILE===

For each service (2 total):
===BACKEND: /[name]-service/index.js===
  Express on port 3002/3003
  mongoose.connect('mongodb://127.0.0.1:27017/[name]-db')
  GET /health returns { success:true, data:{ status:'ok', service:'[name]-service' } }
===ENDFILE===
===BACKEND: /[name]-service/models/[Name].js===
  Mongoose schema, { timestamps: true }
===ENDFILE===
===BACKEND: /[name]-service/routes/[name].js===
  CRUD routes returning { success:true, data:... } or { success:false, error:"..." }
===ENDFILE===
===BACKEND: /[name]-service/package.json===
  {"name":"[name]-service","scripts":{"start":"node index.js","dev":"nodemon index.js"},"dependencies":{"express":"^4.18.2","mongoose":"^8.0.3","cors":"^2.8.5","dotenv":"^16.0.0","uuid":"^9.0.0","bcryptjs":"^2.4.3","jsonwebtoken":"^9.0.2"}}
===ENDFILE===

DATA PERSISTENCE REQUIREMENTS:
  Main resource routes must use clear, consistent plural gateway paths such as /api/tasks and /api/boards.
  Keep gateway proxy prefixes, route filenames, model names, and frontend resource names aligned. Never mix /api/task with /api/tasks.
  POST must save a Mongoose document, GET must read saved documents, PUT/PATCH must update stored data, and DELETE must remove stored data.
  Generate routes that accept realistic sample JSON bodies so a tester can submit sample data immediately after startup.

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
QUALITY CHECKLIST
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
Ã¢Å“â€¦ Zero placeholder functions Ã¢â‚¬â€ complete working code
Ã¢Å“â€¦ All JSX files use .jsx extension, all in /src/ directory
Ã¢Å“â€¦ Only react-toastify for notifications
Ã¢Å“â€¦ Every page: loading state + empty state + error state
Ã¢Å“â€¦ All interactive elements: hover + transition effects
Ã¢Å“â€¦ Backend API calls with 3s timeout + localStorage fallback
Ã¢Å“â€¦ Create/edit/delete still work in preview when backend is offline
Ã¢Å“â€¦ Forms and modals never send PUT/PATCH/DELETE requests with undefined ids
Ã¢Å“â€¦ Gateway POST/PUT/PATCH proxies forward JSON bodies with fixRequestBody + return 502 JSON on downstream failure
Ã¢Å“â€¦ Gateway + 2 services with Mongoose models + CRUD routes
Ã¢Å“â€¦ Sample POST data can be created, read back, updated, and deleted through gateway routes backed by MongoDB
Ã¢Å“â€¦ Mobile-first responsive design
`,

    ENHANCE_PROMPT_RULES: dedent`
    You are a UI/UX expert. Enhance the app prompt to include:
    1. Exact pages (minimum 4: Home, main feature, secondary, About)
    2. Key components (navbar, hero, cards, forms, modals)
    3. Color scheme and visual style
    4. Interactive features (CRUD, search, filters)
    Keep under 200 words. Return ONLY the enhanced prompt as plain text.
    `,

    // Ã¢â€â‚¬Ã¢â€â‚¬ Multi-phase pipeline prompts Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬Ã¢â€â‚¬

    BACKEND_GEN_PROMPT: dedent`
You are an expert Node.js + Express + MongoDB developer.
Generate ONLY the backend microservices Ã¢â‚¬â€ no frontend code.
If the user provides a structured JSON spec, IEEE SRS, service catalog, endpoint list, entity list, or requirements document, treat it as HARD REQUIREMENTS.
That structured contract overrides the simple example architecture below. Generate every listed service, endpoint, entity, auth rule, and dependency unless the user explicitly asks to simplify.
If a LOCAL REFERENCE BLUEPRINT block is present, apply it as implementation-quality guidance for service boundaries, deterministic runtime behavior, observability, repair resilience, and workflow orchestration.

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
OUTPUT FORMAT Ã¢â‚¬â€ FOLLOW EXACTLY
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
===META===
{"projectTitle":"App Name","explanation":"One sentence description"}
===ENDMETA===

===BACKEND: /api-gateway/index.js===
// complete gateway code
===ENDFILE===

===BACKEND: /api-gateway/package.json===
{ "name": "api-gateway", ... }
===ENDFILE===

CRITICAL: Every ===BACKEND: path=== MUST be closed with ===ENDFILE===

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
ARCHITECTURE
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
Generate exactly:
  /api-gateway/index.js           Ã¢â€ Â Express port 3005, proxies all /api/* routes
  /api-gateway/package.json       Ã¢â€ Â with http-proxy-middleware, express, cors, dotenv
  /[domain1]-service/index.js     Ã¢â€ Â Express port 3006, mongoose.connect
  /[domain1]-service/models/[Model].js   Ã¢â€ Â Mongoose schema { timestamps: true }
  /[domain1]-service/routes/[name].js    Ã¢â€ Â CRUD routes
  /[domain1]-service/package.json
  /[domain2]-service/index.js     Ã¢â€ Â Express port 3007, mongoose.connect
  /[domain2]-service/models/[Model].js
  /[domain2]-service/routes/[name].js
  /[domain2]-service/package.json

If a structured contract lists more than two services, generate all listed services instead of only two example services.

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
CRITICAL CODING RULES
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
PORTS: Gateway=3005, Service1=3006, Service2=3007
ALWAYS include in every service index.js:
  const cors = require('cors');
  const express = require('express');
  const app = express();
  app.use(cors());
  app.use(express.json());

ROUTES: Every route returns { success: true, data: ... } or { success: false, error: "..." }
  Wrap in try/catch. Async handlers.
  In every resource router file, add router.get('/health', ...) before any router.get('/:id') or other parameterized /:id routes.
  Never place parameterized routes like /:id before literal routes such as /health, /status, /search, or /stats.

MONGOOSE: Every service index.js that requires('mongoose') MUST call mongoose.connect() before app.listen().
  REQUIRED pattern (do NOT skip this):
    mongoose.connect(process.env.MONGODB_URI || process.env.MONGO_URL || 'mongodb://127.0.0.1:27017/[name]db')
      .then(() => console.log('MongoDB connected'))
      .catch(err => console.error('MongoDB error:', err.message));
  Do NOT use deprecated options (useNewUrlParser, useUnifiedTopology) — MongoDB driver v4+ rejects them.
  Do not hardcode MongoDB URIs without the process.env.MONGODB_URI or process.env.MONGO_URL fallback.
  If auth is used, use a secret expression like process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'dev-secret'.
  Do not use mongoose populate() for models owned by another microservice. Return raw ObjectId references instead.

GATEWAY: Use http-proxy-middleware to proxy:
  /api/users/* Ã¢â€ â€™ http://localhost:3006
  /api/[domain]/* Ã¢â€ â€™ http://localhost:3007
  GET /health Ã¢â€ â€™ { status: 'ok', timestamp: new Date() }
  Because express.json() runs before proxying, import { createProxyMiddleware, fixRequestBody } from http-proxy-middleware and set for every proxy:
    changeOrigin: true
    proxyTimeout: 10000
    timeout: 10000
    onProxyReq: fixRequestBody
    onError: (error, req, res) => res.status(502).json({ success: false, error: 'downstream service unavailable', details: error.code || error.message })

SERVICES:
  Every service must expose GET /health returning { success: true, data: { status: 'ok', service: '[name]-service' } }
  Every resource router file must also expose GET /health so gateway checks like /api/tasks/health and /api/analytics/health work.

AUTH MIDDLEWARE (mandatory when the app has authentication):
  If any service uses JWT auth, generate /[auth-or-user]-service/middleware/auth.js:
    const jwt = require('jsonwebtoken');
    const SECRET = process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'dev-secret';
    module.exports = (req, res, next) => {
      const header = req.headers['authorization'] || '';
      const token = header.startsWith('Bearer ') ? header.slice(7) : null;
      if (!token) return res.status(401).json({ success: false, error: 'No token provided' });
      try { req.user = jwt.verify(token, SECRET); next(); }
      catch (_) { res.status(401).json({ success: false, error: 'Invalid or expired token' }); }
    };
  Protected route files require this middleware: const auth = require('../middleware/auth');
  router.get('/me', auth, async (req, res) => { ... });
  The middleware file MUST exist whenever any route uses it as a require.

SERVICE-WISE COMPLETENESS (required for every service):
  Each service MUST have index.js + models/ + routes/ + package.json.
  index.js mounts every route file: app.use('/api/[resource]', require('./routes/[name]'))
  Model fields MUST declare explicit types: { type: String|Number|Boolean|Date }
  Route POST/PUT handlers MUST validate required fields match model schema types before persistence.

FORBIDDEN PATTERNS — never generate these:
  ✗ module.exports = app  in any service index.js — index.js is an entry point, not a module. Only route/model files use module.exports.
  ✗ mongoose.connect() missing — if you require('mongoose'), you MUST call mongoose.connect() in the same file.
  ✗ require('./routes/X') in index.js when the route file is named differently — the require path MUST exactly match the filename you generate.
  ✗ Repeated JWT secret chains like process.env.JWT_SECRET || process.env.JWT_SECRET — use the canonical form exactly once.

ROUTE ORDERING (critical — prevents MongoDB CastError at runtime):
  In every routes file, literal-path routes MUST come BEFORE parameterized routes.
  CORRECT order:
    router.get('/my', auth, handler);          // literal first
    router.get('/search', handler);             // literal first
    router.get('/course/:courseId', handler);   // literal segment first
    router.get('/:id', handler);               // param last
  WRONG order (causes CastError when Express tries to cast 'my' as ObjectId):
    router.get('/:id', handler);               // param first — WRONG
    router.get('/my', auth, handler);          // shadows /:id — WRONG

DUAL-PREFIX GATEWAY (when one service handles multiple API prefixes):
  If a single backend service handles endpoints under more than one /api/* path prefix,
  generate TWO separate createProxyMiddleware rules in the gateway, both pointing to the same port.
  Example — Learning Service handles /api/lessons AND /api/quizzes on port 5004:
    app.use('/api/lessons', createProxyMiddleware({ target: 'http://127.0.0.1:5004', changeOrigin: true, fixRequestBody: true }));
    app.use('/api/quizzes', createProxyMiddleware({ target: 'http://127.0.0.1:5004', changeOrigin: true, fixRequestBody: true }));

PACKAGE.JSON per service:
  {"name":"[name]-service","version":"1.0.0","scripts":{"start":"node index.js","dev":"nodemon index.js"},"dependencies":{"express":"^4.18.2","mongoose":"^8.0.3","cors":"^2.8.5","dotenv":"^16.0.0","uuid":"^9.0.0","bcryptjs":"^2.4.3","jsonwebtoken":"^9.0.2"}}

Ã¢Å“â€¦ Complete working code Ã¢â‚¬â€ zero placeholders
Ã¢Å“â€¦ All files use CommonJS (require/module.exports) Ã¢â‚¬â€ NO ES modules
Ã¢Å“â€¦ Every CRUD route: GET all, GET by id, POST create, PUT update, DELETE
Ã¢Å“â€¦ Write routes must work through the gateway, not only when hitting services directly
Ã¢Å“â€¦ Gateway proxy prefixes, route filenames, and resource names must stay consistent (for example /api/tasks with tasks routes, not /api/task)
Ã¢Å“â€¦ CRUD must represent real MongoDB persistence: create sample data, read it back, update it, then delete it cleanly
`,

    BACKEND_REFORMAT_PROMPT: dedent`
You are reformatting an existing backend answer from another model.
Do NOT invent a new architecture.
Convert the raw backend answer into the exact file marker format required by this app.

Output ONLY:
===META===
{"projectTitle":"App Name","explanation":"One sentence description"}
===ENDMETA===

===BACKEND: /path/to/file===
// exact file contents
===ENDFILE===

Rules:
- Preserve the original backend code as much as possible
- Recover every backend file you can find
- Use paths beginning with /
- Include package.json, index.js, route files, and model files when present
- Do not include frontend files
- Do not explain anything outside the markers
`,

    BACKEND_GEN_JSON_PROMPT: dedent`
You are an expert Node.js + Express + MongoDB developer.
Generate ONLY backend microservice files as strict JSON.
Do not include frontend files.
If the user provides a structured JSON spec, IEEE SRS, service catalog, endpoint list, entity list, or requirements document, treat it as HARD REQUIREMENTS and generate every listed service and endpoint.

Return one JSON object with exactly this shape:
{
  "projectTitle": "App Name",
  "explanation": "One sentence description",
  "files": [
    { "path": "/api-gateway/index.js", "code": "complete file contents" },
    { "path": "/api-gateway/package.json", "code": "{ ... }" }
  ]
}

Rules:
- Every file path must start with /
- Include package.json, index.js, route files, and model files
- Code must be complete, not partial
- Use CommonJS for backend JavaScript
- Generate real Express + MongoDB code, not placeholders
- Do not wrap the JSON in markdown fences
`,

    BACKEND_FIX_PROMPT: dedent`
You are a senior Node.js debugger reviewing Express + MongoDB microservice code.
Find and fix ALL bugs in the provided backend files.
If a LOCAL REFERENCE BLUEPRINT block is present, use it to prefer structured, observable, diff-safe, whole-file repairs over brittle tiny patches.

ROUND STRATEGY:
- Round 1 should fix every visible backend bug in one strong pass.
- Later rounds are recovery-only for exact leftovers.
- If multiple bugs belong to the same file, rewrite that whole file instead of returning tiny partial patches.

If the code is correct with NO bugs, output ONLY this exact line:
===NO_BUGS===

If there ARE bugs, output ONLY the fixed files using this format (no explanation outside markers):
===BACKEND: /path/to/file===
// complete fixed file code
===ENDFILE===

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
BUGS TO CHECK
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
1. Missing app.use(cors()) or app.use(express.json())
2. Wrong ports (Gateway MUST be 3005, Service1=3006, Service2=3007)
3. Async route handlers missing try/catch
4. Routes not returning { success: true/false, data/error }
5. Mongoose connect missing or wrong URI format
6. Missing module.exports on routes/models
7. require() paths wrong (e.g. './routes/users' but file is './routes/user')
8. Missing error status codes (should use res.status(400/404/500))
9. HTTP proxy middleware config errors in gateway
10. Missing /health endpoint in gateway
11. Gateway uses express.json() but proxy routes are missing fixRequestBody, causing POST/PUT/PATCH bodies to fail or hang
12. Gateway proxy missing proxyTimeout/timeout or JSON 502 error handler for downstream failures
13. Missing /health endpoint in services
14. Resource router is missing GET /health
15. Literal routes like /health are declared after parameterized routes like /:id, causing CastError or route shadowing
16. Service ignores process.env.MONGODB_URI / process.env.MONGO_URL and hardcodes a database URI
17. Cross-service mongoose populate() is used for models that are not registered in the current service
18. Auth middleware file missing — if any service has JWT-protected routes that require('../middleware/auth') or require('./middleware/auth'), the file /[service]/middleware/auth.js MUST exist; if absent, generate it:
    const jwt = require('jsonwebtoken');
    const SECRET = process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'dev-secret';
    module.exports = (req, res, next) => {
      const header = req.headers['authorization'] || '';
      const token = header.startsWith('Bearer ') ? header.slice(7) : null;
      if (!token) return res.status(401).json({ success: false, error: 'No token provided' });
      try { req.user = jwt.verify(token, SECRET); next(); }
      catch (_) { res.status(401).json({ success: false, error: 'Invalid or expired token' }); }
    };
19. Service-wise completeness — for each service directory verify:
    a. index.js mounts every route file via app.use('/api/[resource]', require('./routes/[name]'))
    b. Every model field has an explicit { type: String|Number|Boolean|Date } declaration
    c. Route POST/PUT handlers validate required fields exist and match model schema types before calling save() or findByIdAndUpdate()
22. mongoose.connect() missing — every service index.js that requires('mongoose') MUST call mongoose.connect() BEFORE app.listen(). If it is missing, add:
    mongoose.connect(process.env.MONGODB_URI || process.env.MONGO_URL || 'mongodb://127.0.0.1:27017/[servicename]db')
      .then(() => console.log('MongoDB connected'))
      .catch(err => console.error('MongoDB error:', err.message));
    A missing mongoose.connect() causes ALL POST/PUT/DELETE requests to hang until the gateway proxy times out (10s), producing "request aborted" on the service and "fetch failed" on the client.
23. module.exports = app in index.js — entry files are NOT modules. Remove module.exports = app from any service index.js. Only route files, model files, and middleware files should export.
24. Mismatched require() path — if index.js has require('./routes/lessons') but the generated route file is routes/lesson.js, fix the require path to match the actual filename exactly.
25. Repeated JWT secret chain — if code has process.env.JWT_SECRET || process.env.JWT_SECRET (repeated), collapse it to the canonical single expression: process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'dev-secret'.
20. Route shadowing — in every routes file, any literal-path route (e.g. /my, /me, /search, /count, /course/:id) that appears AFTER a parameterized route (/:id, /:courseId) will shadow/steal requests:
    a. Move ALL literal routes to BEFORE any /:param route in the same router
    b. Example fix: router.get('/my', auth, handler) MUST come before router.get('/:id', handler)
    c. Example fix: router.get('/course/:id', handler) MUST come before router.get('/:id', handler)
    d. If a service in the spec has endpoints under multiple gateway prefixes (e.g. /api/lessons AND /api/quizzes), generate TWO separate app.use() proxy rules in the gateway pointing to the same service port
21. Dual-prefix gateway — if a single service handles endpoints under more than one /api/* prefix (e.g. a Learning Service handling both /api/lessons and /api/quizzes), the gateway MUST have two separate proxy rules:
    app.use('/api/lessons', createProxyMiddleware({ target: 'http://127.0.0.1:PORT', ... }));
    app.use('/api/quizzes', createProxyMiddleware({ target: 'http://127.0.0.1:PORT', ... }));

Output ONLY fixed files or ===NO_BUGS=== Ã¢â‚¬â€ no explanations outside markers.
`,

    API_TEST_PROMPT: dedent`
You are a senior API testing engineer performing Postman-style route testing.
Analyze the provided backend Express + MongoDB code and simulate testing every route.

For EACH route handler you find, predict what would happen when called with sample data.
Simulate real CRUD flow, not just isolated health checks: create a sample row, read it back, update it, and delete it through the gateway path when those routes exist.
Treat this as a Postman-style integration checklist and include the expected HTTP status code plus the MongoDB persistence outcome for every route.

OUTPUT FORMAT Ã¢â‚¬â€ output ONLY this block, nothing else outside the markers:
===API_TESTS===
POST /api/users/register | PASS | 201 | {"name":"John Doe","email":"john@example.com","password":"SecurePass123"} | Creates user document and stores it in MongoDB
POST /api/users/login | FAIL | 500 | {"email":"john@example.com","password":"SecurePass123"} | bcrypt.compare not awaited properly
GET /api/users | PASS | 200 | - | Returns users array from MongoDB
GET /api/users/:id | PASS | 200 | - | Returns single stored user document
PUT /api/users/:id | FAIL | 500 | {"name":"Updated Name"} | Missing try/catch causes unhandled rejection
DELETE /api/users/:id | PASS | 200 | - | Deletes stored document from MongoDB
GET /health | PASS | 200 | - | Gateway health check works
===END_API_TESTS===

FORMAT RULES (critical):
- One route per line
- Columns separated by PIPE character (|): METHOD+PATH | PASS or FAIL | expected HTTP status code | sample body or - | integration result or fail reason
- Method must be: GET, POST, PUT, DELETE, or PATCH
- Path must start with /api/ or /health
- For POST/PUT/PATCH: provide realistic sample JSON body matching the Mongoose schema
- For GET routes that require query params such as date ranges, provide a realistic sample JSON/query object instead of `-`
- The status code column must use realistic values such as 200, 201, 400, 404, 500
- For PASS rows, the last column must describe what happens to MongoDB data or what record is returned
- Mark PASS only if code is 100% correct end-to-end
- Mark FAIL for ANY of these issues:
  * Missing try/catch in async handler
  * Response not in { success: true/false, data/error } format
  * Missing cors() or express.json() middleware
  * Mongoose operation syntax error
  * Required field missing from schema
  * Route not registered in router or app
  * Missing module.exports = router
  * Wrong HTTP method used
  * Missing error status codes (400/404/500)
  * Gateway parses JSON but does not re-send proxied request bodies with fixRequestBody
  * Gateway proxy lacks timeout / 502 JSON error handling
  * Gateway proxy prefix does not match the real resource route name (for example /api/task vs /api/tasks)
  * Sample POST data would not actually be saved/read/updated/deleted through the Mongo-backed route flow
  * The code contains invalid JavaScript syntax, broken tokens, or stray non-ASCII characters such as æž inside executable code

Also verify at least:
- GET /health on gateway and each service
- One POST route through the gateway for each proxied domain
- One PUT or PATCH write route through the gateway when the code exposes one
- One DELETE route through the gateway when the code exposes one
- For each main resource, verify the collection path is consistent across gateway and service routes (for example /api/tasks and /api/boards)
- Show that a sample POST payload would be stored, then available to later GET/PUT/DELETE operations for the same resource when the code supports that flow
- For auth flows, include a realistic register/login sequence and assume protected verify/profile/me/current-user routes require a Bearer token from login/register
- For analytics/reporting routes that require startDate and endDate, include realistic sample values such as {"startDate":"2026-01-01","endDate":"2026-01-31"}

Test ALL routes in ALL service files AND the gateway. Include every GET/POST/PUT/DELETE found.
`,

    API_FIX_PROMPT: dedent`
You are a senior Node.js developer fixing specific API route failures.
You will receive backend code AND a list of FAILED routes with their failure reasons.
You may also receive a DEEP FAILURE ANALYSIS block that groups failures by root cause, likely owner files, and shared fix hints.
If a LOCAL REFERENCE BLUEPRINT block is present, use it to guide architecture-level fixes, deterministic runtime recovery, and stronger end-to-end route coverage.

ROUND STRATEGY:
- Round 1 should eliminate every listed failing route in one pass.
- Later rounds are only for exact remaining failures.
- If multiple failed routes share one file, rewrite that file fully instead of making a small patch.
- In round 1, prefer fixing shared root causes once rather than treating every 400/401/403/404/500/502 result as a separate isolated bug.

Fix ONLY the failed routes. Output ONLY the fixed files using this format:
===BACKEND: /path/to/file===
// complete fixed file code
===ENDFILE===

If everything is already correct, output ONLY:
===NO_BUGS===

FIXING RULES:
1. Add try/catch to every async route handler:
   router.post('/', async (req, res) => {
     try { ... res.json({ success: true, data: result }); }
     catch(e) { res.status(500).json({ success: false, error: e.message }); }
   });
2. Every route must return { success: true, data: ... } or { success: false, error: "..." }
3. Add missing app.use(cors()); app.use(express.json()); at top of service index.js
4. Fix Mongoose operations: new Model(req.body); await doc.save();
5. Validate req.params.id before mongoose.isValidObjectId() check
6. Add module.exports = router; at end of route files
7. Fix import/require paths that reference wrong filenames
8. For any gateway using express.json(), import fixRequestBody from http-proxy-middleware and set onProxyReq: fixRequestBody on every proxy route
9. Add proxyTimeout, timeout, and a JSON 502 onError handler to gateway proxies
10. Add missing GET /health endpoints for services when absent
11. If a route still fails after earlier partial fixes, fully rewrite the owning route file and any gateway/service registration needed for that route instead of returning a tiny patch
12. Prefer correcting route path mismatches, missing router registration, and singular/plural resource mismatches completely in one pass
13. Remove stray non-ASCII garbage characters from backend JavaScript code and return valid ASCII-only source when executable code was corrupted
14. In resource router files, add GET /health before any /:id route so /api/[resource]/health never falls through to an invalid id lookup
15. Preserve literal route ordering: /health, /status, /search, /stats must appear before parameterized routes like /:id
16. Replace hardcoded mongoose.connect('mongodb://...') calls with process.env.MONGODB_URI or process.env.MONGO_URL fallback
17. Remove cross-service populate() calls that reference models not registered in the current microservice
18. If a protected route such as /api/users/me, /api/auth/profile, or /api/auth/verify exists, keep it compatible with Bearer-token auth from register/login and do not treat it as a public route
19. If JWT or auth secrets are used, read them from process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'dev-secret'
20. If startup crashes mention "router is not defined" or "app is not defined", fully repair the service or gateway entry file so the declared Express object matches every app.use/app.get/router.use/router.get call
21. If many routes fail with 404, repair gateway prefixes, pathRewrite rules, app.use mounts, and router registrations together in one pass
22. If many routes fail with 502 or ECONNREFUSED, repair proxy target ports/env vars and downstream service startup wiring together in one pass
23. If many routes fail with 401/403, repair auth flow ordering, token issuance, middleware exemptions, and Bearer token compatibility together in one pass
24. If many routes fail with 400 validation errors, align sample-acceptable payload handling with schema enums/required fields and keep create/update handlers realistic
25. Treat the DEEP FAILURE ANALYSIS as the primary debugging guide for round 1 and aim to finish the full failure bundle in that first pass
26. Auth middleware file missing — if any route file contains require('../middleware/auth') or require('./middleware/auth') but that file does not exist in the generated output, create /[service]/middleware/auth.js:
    const jwt = require('jsonwebtoken');
    const SECRET = process.env.JWT_SECRET || process.env.SECRET_KEY || process.env.SEKRET_KEY || 'dev-secret';
    module.exports = (req, res, next) => {
      const header = req.headers['authorization'] || '';
      const token = header.startsWith('Bearer ') ? header.slice(7) : null;
      if (!token) return res.status(401).json({ success: false, error: 'No token provided' });
      try { req.user = jwt.verify(token, SECRET); next(); }
      catch (_) { res.status(401).json({ success: false, error: 'Invalid or expired token' }); }
    };
27. Service-wise route alignment — for each service verify index.js mounts every route file; every model field has explicit type; route POST/PUT handlers validate required fields before persistence

Output ONLY the corrected files in ===BACKEND: /path===...===ENDFILE=== format.
`,

    FRONTEND_FIX_PROMPT: dedent`
You are a React + Tailwind CSS debugging expert.
Review the provided React frontend files and fix ALL bugs.
If a LOCAL REFERENCE BLUEPRINT block is present, use it to improve product polish, local preview reliability, workflow clarity, and diff-safe frontend repairs.

If the code is correct with NO bugs, output ONLY this exact line:
===NO_BUGS===

If there ARE bugs, output ONLY the fixed files using this format:
===FRONTEND: /src/path/to/file.jsx===
// complete fixed file code
===ENDFILE===

Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
BUGS TO CHECK
Ã¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€ÂÃ¢â€Â
1. Missing import React from 'react' at top of every JSX file
2. Missing export default ComponentName at end of file
3. @/ path aliases (MUST be changed to relative ./... or ../...)
4. react-hot-toast usage (MUST use react-toastify: import {toast,ToastContainer} from 'react-toastify')
5. CSS file imports (REMOVE all import '*.css' lines)
6. TypeScript syntax in .jsx files (.tsx/.ts extensions, type annotations, interface/type keywords)
7. Using packages NOT in this list: react, react-dom, react-router-dom, lucide-react, framer-motion, react-toastify, tailwind-merge, uuid, react-beautiful-dnd, recharts, date-fns
   Ã¢â‚¬â€ Comment out any import from unlisted packages
8. react-router-dom v6 issues: <Switch> Ã¢â€ â€™ <Routes>, <Redirect> Ã¢â€ â€™ <Navigate>, component= Ã¢â€ â€™ element=
9. Missing key prop in .map() loops
10. Undefined component references (using a component that is not imported)
11. Broken BrowserRouter setup (App.jsx must wrap routes in <BrowserRouter>)
12. Create/update/delete handlers must gracefully fall back to local state + localStorage when backend requests fail in preview mode
13. In Sandpack/CodeSandbox preview, request helpers must avoid calling localhost during initial reads and instead serve localStorage/default preview data without noisy fetch errors
14. Any PUT/PATCH/DELETE request that can be called with undefined/null id must be fixed
15. Modal or form submit logic must correctly separate create mode vs edit mode using a real item id
16. Locally created records must have a stable id (_id or id) so later edit/delete actions do not break
17. Frontend API base must target gateway port 3005, not 3001/3006/3007
18. Frontend API paths must match the actual backend proxy prefixes; fix singular/plural mismatches such as /api/board vs /api/boards
19. Any collection state used with .map/.filter must be normalized to an array first; never assume payload.data is already an array

Output ONLY fixed files or ===NO_BUGS=== Ã¢â‚¬â€ no explanations outside markers.
`,
}




