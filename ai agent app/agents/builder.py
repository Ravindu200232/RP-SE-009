import json, logging, os, re, shutil, subprocess, textwrap
from pathlib import Path

from agents import llm, scaffold

log = logging.getLogger("builder")


def _npm():
    """Resolve npm; on Windows this is npm.cmd. PATH already includes bundled node."""
    return shutil.which("npm") or ("npm.cmd" if os.name == "nt" else "npm")


_stream_callback = None
def set_stream_callback(fn):
    global _stream_callback
    _stream_callback = fn

def _emit(token):
    if _stream_callback:
        _stream_callback(token)

# ── Static file generators (no LLM, guaranteed valid) ────────────────────────

def _page_shell(title: str, sections: list) -> str:
    """
    Deterministic app/page.tsx (a server component) that stacks the Navbar and
    every LLM-generated section as full-bleed bands, plus a footer. Each section
    owns its own background/id, giving a true long-scrolling page.
    """
    t = title.replace("'", "\\'")
    non_navbar = [s for s in sections if s != "Navbar"]
    lines = ["import Navbar from '@/components/Navbar'"]
    for s in non_navbar:
        lines.append(f"import {s} from '@/components/{s}'")
    lines += [
        "",
        "export default function Home() {",
        "  return (",
        "    <main className='min-h-screen bg-dark overflow-x-hidden'>",
        "      <Navbar />",
    ]
    for s in non_navbar:
        lines.append(f"      <{s} />")
    lines += [
        "      <footer className='border-t border-white/10 py-10 text-center text-gray-500 text-sm'>",
        f"        <p>© 2026 {t}</p>",
        "      </footer>",
        "    </main>",
        "  )",
        "}",
    ]
    return "\n".join(lines) + "\n"


SAFE_COMPONENT = textwrap.dedent("""\
    'use client'
    import { motion } from 'framer-motion'
    export default function {name}() {
      return (
        <section id='{id}' className='py-24 px-6 bg-dark'>
          <motion.div className='max-w-4xl mx-auto text-center'
            initial={{opacity:0,y:30}} whileInView={{opacity:1,y:0}}
            transition={{duration:0.6}} viewport={{once:true}}>
            <h2 className='text-5xl font-black mb-4' style={{
              background:'linear-gradient(135deg,#6366f1,#22d3ee)',
              WebkitBackgroundClip:'text', WebkitTextFillColor:'transparent'
            }}>{name}</h2>
            <p className='text-gray-400 text-lg'>Section content goes here.</p>
          </motion.div>
        </section>
      )
    }
    """)

def _safe_component(name: str) -> str:
    return SAFE_COMPONENT.replace("{name}", name).replace("{id}", name.lower())


def _page_component_name(page: dict) -> str:
    """Stable, collision-free PascalCase component name for a route."""
    path = str(page.get("path") or "/").strip("/") or "home"
    bits = [b for b in re.split(r"[^A-Za-z0-9]+", path.replace("[id]", "detail")) if b]
    stem = "".join(b[:1].upper() + b[1:] for b in bits) or "Home"
    kind = re.sub(r"[^A-Za-z0-9]", "", str(page.get("kind") or "page").title())
    return f"{stem}{kind}Content"


def _route_page_file(path: str) -> str:
    route = str(path or "/").strip("/")
    return f"app/{route + '/' if route else ''}page.tsx"


def _multipage_navbar(spec: dict) -> str:
    """Deterministic session-aware navigation shared by every public page."""
    from agents.auth_scaffold import normalize_roles

    title = str(spec.get("title") or "My App")
    roles = normalize_roles(spec)
    role_home = {r["name"]: r["home"] for r in roles}
    public_links = []
    seen = set()
    for page in spec.get("pages") or []:
        path = str(page.get("path") or "")
        if (page.get("access") == "public" and page.get("kind") not in {"auth", "detail"}
                and path and path not in seen):
            public_links.append({"href": path, "label": page.get("title") or path})
            seen.add(path)
    if "/" not in seen:
        public_links.insert(0, {"href": "/", "label": "Home"})
    signup_enabled = bool((spec.get("auth") or {}).get("signup", True))
    signup_desktop = ("<Link href='/signup' className='px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium'>"
                      "Sign up</Link>" if signup_enabled else "")
    signup_mobile = "<Link href='/signup'>Sign up</Link>" if signup_enabled else ""

    return textwrap.dedent(f"""\
        'use client'
        import Link from 'next/link'
        import {{ useEffect, useState }} from 'react'
        import {{ usePathname, useRouter }} from 'next/navigation'
        import {{ FiMenu, FiX }} from 'react-icons/fi'

        interface SessionUser {{
          userId: string
          email: string
          role: string
        }}

        export default function AppNavbar() {{
          const roleHome: Record<string, string> = {json.dumps(role_home)}
          const publicLinks: Array<{{ href: string; label: string }}> = {json.dumps(public_links)}
          const [user, setUser] = useState<SessionUser | null>(null)
          const [ready, setReady] = useState(false)
          const [open, setOpen] = useState(false)
          const pathname = usePathname()
          const router = useRouter()

          useEffect(() => {{
            let active = true
            fetch('/api/auth/me', {{ cache: 'no-store' }})
              .then(async (r) => r.ok ? r.json() : null)
              .then((data) => {{ if (active) setUser(data?.user || null) }})
              .finally(() => {{ if (active) setReady(true) }})
            return () => {{ active = false }}
          }}, [pathname])

          const logout = async () => {{
            await fetch('/api/auth/logout', {{ method: 'POST' }})
            setUser(null)
            setOpen(false)
            router.push('/')
            router.refresh()
          }}

          const dashboard = user ? (roleHome[user.role] || '/') : '/'
          return (
            <header className='sticky top-0 z-50 border-b border-white/10 bg-slate-950/90 backdrop-blur-xl'>
              <nav className='max-w-7xl mx-auto px-5 h-16 flex items-center justify-between'>
                <Link href='/' className='font-black text-xl gradient-text'>{title}</Link>
                <div className='hidden md:flex items-center gap-6'>
                  {{publicLinks.map((link) => (
                    <Link key={{link.href}} href={{link.href}}
                      className={{pathname === link.href ? 'text-white text-sm' : 'text-slate-400 hover:text-white text-sm'}}>
                      {{link.label}}
                    </Link>
                  ))}}
                  {{ready && user ? (
                    <>
                      <Link href={{dashboard}} className='px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium'>
                        {{user.role === 'admin' ? 'Admin' : 'Dashboard'}}
                      </Link>
                      <button onClick={{logout}} className='text-sm text-slate-400 hover:text-white'>Log out</button>
                    </>
                  ) : ready ? (
                    <>
                      <Link href='/login' className='text-sm text-slate-300 hover:text-white'>Log in</Link>
                      {signup_desktop}
                    </>
                  ) : <span className='w-24 h-8 rounded-lg bg-white/5 animate-pulse' />}}
                </div>
                <button type='button' aria-label='Toggle navigation' onClick={{() => setOpen(!open)}}
                  className='md:hidden text-white text-xl'>{{open ? <FiX /> : <FiMenu />}}</button>
              </nav>
              {{open && (
                <div className='md:hidden px-5 pb-5 flex flex-col gap-3 bg-slate-950'>
                  {{publicLinks.map((link) => <Link key={{link.href}} href={{link.href}} onClick={{() => setOpen(false)}}>{{link.label}}</Link>)}}
                  {{user ? <><Link href={{dashboard}} onClick={{() => setOpen(false)}}>Dashboard</Link><button onClick={{logout}} className='text-left'>Log out</button></>
                    : <><Link href='/login'>Log in</Link>{signup_mobile}</>}}
                </div>
              )}}
            </header>
          )
        }}
        """)


def _multipage_root_layout(spec: dict) -> str:
    title = str(spec.get("title") or "My App").replace("'", "\\'")
    description = str(spec.get("description") or title).replace("'", "\\'")[:160]
    return textwrap.dedent(f"""\
        import './globals.css'
        import AppNavbar from '@/components/AppNavbar'

        export const metadata = {{
          title: '{title}',
          description: '{description}',
        }}

        export default function RootLayout({{ children }}: {{ children: React.ReactNode }}) {{
          return (
            <html lang='en' data-scroll-behavior='smooth'>
              <body className='min-h-screen bg-dark text-slate-100'>
                <AppNavbar />
                {{children}}
              </body>
            </html>
          )
        }}
        """)


def _multipage_page_shell(page: dict, component: str, model: dict | None) -> str:
    """A deterministic route wrapper. Detail routes fetch server-side by id."""
    kind = str(page.get("kind") or "static")
    if kind == "detail" and model:
        name = scaffold.pascal(model.get("name", "Item"))
        return textwrap.dedent(f"""\
            import {{ notFound }} from 'next/navigation'
            import dbConnect from '@/lib/mongodb'
            import {name} from '@/models/{name}'
            import {component} from '@/components/{component}'

            export const dynamic = 'force-dynamic'
            type PageProps = {{ params: Promise<{{ id: string }}> }}

            export default async function Page({{ params }}: PageProps) {{
              const {{ id }} = await params
              await dbConnect()
              const raw = await {name}.findById(id).lean()
              if (!raw) notFound()
              const initialItem = JSON.parse(JSON.stringify(raw)) as Record<string, unknown>
              return <{component} initialItem={{initialItem}} />
            }}
            """)
    return textwrap.dedent(f"""\
        import {component} from '@/components/{component}'

        export default function Page() {{
          return <{component} />
        }}
        """)


# ── BuilderAgent ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert Next.js (App Router) + Tailwind developer building ONE section
    component of a long, beautiful, full-stack page.
    Output ONLY complete, valid TSX/JSX code. No markdown fences, no explanation, no preamble.

    ═══════════════════════════════════════════════════════════
    REFERENCE EXAMPLE — your output must follow this structure EXACTLY:
    ═══════════════════════════════════════════════════════════

    'use client'
    import { useState, useEffect } from 'react'
    import { motion } from 'framer-motion'
    import { FiMail, FiCheck, FiArrowRight } from 'react-icons/fi'

    export default function Newsletter() {
      // ── All data and state go INSIDE the function ──────────
      const plans = [
        { id: 1, name: 'Weekly Digest', desc: 'Best articles every Monday' },
        { id: 2, name: 'Daily Brief',   desc: 'Quick updates every morning' },
      ]
      const [email, setEmail]   = useState('')
      const [plan, setPlan]     = useState(1)
      const [done, setDone]     = useState(false)

      // ── Regex and computed values hoisted ABOVE return() ───
      const reEmail = /[^a-zA-Z0-9@._+-]/g
      const reTrim  = /\\s+/g
      const halfLen = Math.floor(plans.length / 2)   // division OK inside Math.*
      const stepVal = 1 / plans.length                // division outside JSX

      const handleSubmit = (e) => {
        e.preventDefault()
        const cleaned = email.replace(reEmail, '').replace(reTrim, '')
        if (!cleaned.includes('@')) return
        setDone(true)
      }

      if (done) return (
        <div className="min-h-screen bg-gray-900 flex items-center justify-center">
          <motion.div initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="text-center text-white">
            <FiCheck className="text-5xl text-green-400 mx-auto mb-4" />
            <h2 className="text-3xl font-bold">You're subscribed!</h2>
          </motion.div>
        </div>
      )

      return (
        <div className="min-h-screen bg-gray-900 text-white py-20 px-6">
          <div className="max-w-2xl mx-auto">
            <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
              className="text-5xl font-black mb-4 gradient-text">
              Stay in the Loop
            </motion.h1>
            <ul className="mb-8 space-y-3">
              {plans.map(p => (
                <li key={p.id}
                  onClick={() => setPlan(p.id)}
                  className={`p-4 rounded-xl cursor-pointer border transition ${
                    plan === p.id ? 'border-indigo-500 bg-indigo-500/10' : 'border-white/10'
                  }`}>
                  <span className="font-semibold">{p.name}</span>
                  <span className="text-gray-400 ml-2 text-sm">{p.desc}</span>
                </li>
              ))}
            </ul>
            <form onSubmit={handleSubmit} className="flex gap-3">
              <input type="email" value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="your@email.com"
                className="flex-1 bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white" />
              <button type="submit"
                className="flex items-center gap-2 px-6 py-3 bg-indigo-500 hover:bg-indigo-400 rounded-xl font-semibold transition">
                Subscribe <FiArrowRight />
              </button>
            </form>
            <p className="text-gray-500 text-sm mt-4 flex items-center gap-2">
              <FiMail /> No spam. Unsubscribe anytime.
            </p>
          </div>
        </div>
      )
    }

    ═══════════════════════════════════════════════════════════
    MANDATORY RULES — violations cause runtime errors:
    ═══════════════════════════════════════════════════════════
    1. Imports first. Then IMMEDIATELY export default function. NOTHING between them.
    2. ALL data arrays, constants, state go INSIDE the function body.
    3. NEVER: const Component = () => {}  — arrow components are BANNED.
    4. NEVER: define function then export default separately at the bottom.
    5. NEVER split into multiple named functions.
       NO 'function Calculator()' + 'function App() { return <Calculator/> }'.
       ALL logic lives in ONE export default function. This is the most important rule.
    6. NEVER import from 'react-icons/all' — use 'react-icons/fi', '/fa', '/hi', etc.
    7. ONLY use packages from this EXACT allowed list — NO others:
       ALLOWED: react, react-dom, framer-motion, react-icons
       react-icons usage: import {{ FiHome }} from 'react-icons/fi'
       BANNED (will crash Vite): react-scroll, lucide-react, react-leaflet,
         react-router-dom, axios, lodash, chart.js, d3, three, @mui/material,
         @chakra-ui/react, react-query, zustand, styled-components, classnames,
         react-spring, react-use, @heroicons/react, react-helmet, react-hot-toast.
       If you need a MAP: use a plain <div> with a styled placeholder — no leaflet.
       If you need CHARTS: use pure CSS/SVG bars — no chart.js/d3.
       If you need ROUTING: use useState for view switching — no react-router.
    8. Self-close void elements: <br />, <img />, <input />, <hr />
    9. Outermost div MUST have explicit background: bg-gray-900, bg-slate-950, bg-black.
       NEVER leave root div transparent — causes blank white pages.
    10. Only real icon names: FiHome, FiX, FiCircle, FiStar, FiMenu, FiGrid, FiArrowRight,
        FiPhone, FiMail, FiUser, FiSettings, FiCode, FiHeart, FiPlus, FiTrash2, FiEdit.
        NEVER invent: FiOval, FiMultiply, FiCross, FiGamepad2, FiCalculator.
    11. NEVER write /regex/ inside JSX — hoist to const above return():
          WRONG: onChange={e => setValue(e.target.value.replace(/[^0-9]/g, ''))}
          RIGHT: const reDigits = /[^0-9]/g;  ...  .replace(reDigits, '')
    12. NEVER write division inside JSX {}: Babel misreads / as regex start.
          WRONG: <input step={30/60} />  or  <div>{count/total}</div>
          RIGHT: const stepVal = 30/60;  ...  <input step={stepVal} />

    ═══════════════════════════════════════════════════════════
    NEXT.JS + FULL-STACK RULES:
    ═══════════════════════════════════════════════════════════
    13. FIRST LINE must be exactly: 'use client'  (this is a client component that
        uses hooks / events / animation). Nothing before it.
    13b. This is a .tsx TypeScript file — TypeScript is allowed. Type annotations are
        OPTIONAL: write them (useState<Type>(), `const x: Type`, `(e: React.FormEvent)`,
        `interface`/`type`, `as Type`) or omit them — either compiles fine. Do not add
        markdown fences or a language tag; just output the component code.
    14. This is a section of a long landing/app page. The outermost element MUST be
        <section id="<lowercase-name>" className="..."> with an EXPLICIT dark background
        band (bg-dark, bg-gray-900, bg-slate-950 or a gradient) and generous vertical
        padding (py-20 / py-24). Inside, use a max-w-7xl mx-auto container.
    15. Make it visually rich: framer-motion whileInView reveals
        (initial={{opacity:0,y:30}} whileInView={{opacity:1,y:0}} viewport={{once:true}}),
        responsive grids, hover states, gradient headings, real specific copy — NEVER
        lorem ipsum or "Section content".
    16. DATA: never import mongoose, '@/lib/mongodb', or a model. To read/write data use
        the browser fetch() against the RELATIVE API routes given in the user prompt:
          const load = async () => { const r = await fetch('/api/things'); setItems(await r.json()) }
          useEffect(() => { load() }, [])
          // create: await fetch('/api/things', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) }); load()
          // delete: await fetch(`/api/things/${id}`, { method:'DELETE' }); load()
        Every record's id field is `_id`. Handle the empty-list state gracefully.
    """)


class BuilderAgent:
    def __init__(self, ollama_url: str = None, model: str = None, project_dir: Path = None):
        self.model        = model or llm.GEN_MODEL
        self.project_dir  = Path(project_dir)
        self._component_fallbacks: dict[str, str] = {}
        self._allowed_routes: set[str] = set()
        self._allowed_api_routes: set[str] = set()
        self.built_files: dict[str, str] = {}   # fname → content

    # ── Public API ────────────────────────────────────────────────────────────

    def build(self, refined_prompt) -> bool:
        """Convenience: write the deterministic base + generate the frontend (no install)."""
        spec = self._parse(refined_prompt)
        self.write_base(spec)
        self.build_frontend(spec)
        return True

    def _parse(self, refined_prompt) -> dict:
        if isinstance(refined_prompt, dict):
            return refined_prompt
        try:
            return json.loads(refined_prompt)
        except Exception:
            return {}

    def write_base(self, spec: dict):
        """Write the deterministic Next.js base — config, layout, globals, design system."""
        for rel, content in scaffold.base_files(spec).items():
            self._write_one(rel, content)
        from agents.component_registry import registry_files
        for rel, content in registry_files(spec).items():
            self._write_one(rel, content, verbatim=True)

    def build_frontend(self, spec: dict):
        """Generate Navbar + section components and the composing app/page.tsx shell."""
        if spec.get("app_kind") == "multipage-app":
            self.build_multipage_frontend(spec)
            return

        title    = spec.get("title", "My App")
        sections = spec.get("sections") or ["Hero", "Features", "About", "CTA"]
        contract = scaffold.api_contract(spec)

        log.info("   Frontend sections: %s", sections)
        _emit(f"Sections: {sections}")

        log.info("   Generating Navbar…")
        nav = self._gen("Navbar", self._navbar_prompt(title, sections))
        self._write_one("components/Navbar.tsx", nav or self._fallback_navbar(title, sections))

        for section in [s for s in sections if s != "Navbar"]:
            log.info("   Generating %s…", section)
            code = self._gen(section, self._section_prompt(section, spec, contract), num_predict=5120)
            self._write_one(f"components/{section}.tsx", code or _safe_component(section))

        # Deterministic shell composing every section into one long page.
        self._write_one("app/page.tsx", _page_shell(title, sections))
        # NOTE: suppress_type_errors() runs later in the pipeline, after deps are
        # installed (tsc needs node_modules) — see server.py post-install.

    def build_multipage_frontend(self, spec: dict):
        """Generate presentation leaves for declared pages. Navigation, route
        wrappers, auth gates, server fetching, and ownership remain deterministic."""
        if spec.get("input_schema") == "role-wise-srs/v1":
            return self.build_rolewise_frontend(spec)
        pages = [p for p in (spec.get("pages") or [])
                 if isinstance(p, dict) and p.get("path")]
        self._allowed_routes = {str(p.get("path")) for p in pages}
        self._allowed_routes.update({"/", "/login", "/signup", "/dashboard"})
        self._allowed_api_routes = {f"/api/{scaffold.route_name(m.get('name', 'Item'))}"
                                    for m in (spec.get("data_model") or [])}
        models = {scaffold.pascal(m.get("name", "Item")): m
                  for m in (spec.get("data_model") or [])}
        contract = scaffold.api_contract(spec)

        self._write_one("components/AppNavbar.tsx", _multipage_navbar(spec), verbatim=True)
        self._write_one("app/layout.tsx", _multipage_root_layout(spec))

        # Only genuinely creative, low-risk marketing pages go to the LLM. Every
        # FUNCTIONAL page (list/detail/form/dashboard/admin) is deterministic and
        # correctly wired — the LLM can't break navigation, forms, or business flow.
        LLM_KINDS = set() if spec.get("generation_mode") == "strict-fallback" else {"landing", "static"}
        llm_pages, det_pages = 0, 0
        for page in pages:
            kind = str(page.get("kind") or "static")
            if kind in {"auth", "manage-users"}:
                continue
            component = _page_component_name(page)
            model = models.get(scaffold.pascal(page.get("resource", "")))
            deterministic = self._multipage_fallback(component, page, model, spec)
            rel_component = f"components/{component}.tsx"
            self._component_fallbacks[rel_component] = deterministic

            if kind in LLM_KINDS:
                log.info("   Generating %s (%s, LLM)...", page.get("path"), kind)
                _emit(f"Page: {page.get('path')} ({kind})")
                code = self._gen(component,
                                 self._page_prompt(component, page, model, spec, contract),
                                 num_predict=5120)
                # Hard floor: public landing/static pages MUST have >= 4 sections.
                # If the model under-delivers (or failed), use the deterministic
                # >= 4-section fallback built from the SRS-declared sections.
                if kind in {"landing", "static"} and (not code or code.count("<section") < 4):
                    log.info("   %s: LLM produced <4 sections — using deterministic "
                             ">=4-section fallback", page.get("path"))
                    code = deterministic
                self._write_one(rel_component, code or deterministic)
                llm_pages += 1
            else:
                log.info("   Writing %s (%s, deterministic)...", page.get("path"), kind)
                _emit(f"Page: {page.get('path')} ({kind})")
                self._write_one(rel_component, deterministic, verbatim=True)
                det_pages += 1

            self._write_one(_route_page_file(page["path"]),
                            _multipage_page_shell(page, component, model))

        log.info("   Multi-page frontend: %d LLM page(s), %d deterministic, %d routes",
                 llm_pages, det_pages, len(pages))

    def build_rolewise_frontend(self, spec: dict):
        """Compile each declared component and section into its own file.

        Page files may contain route-level auth/data/business orchestration, but the
        UI inventory is never emitted as one page-sized model response.
        """
        from agents.component_pages import compile_component_pages
        pages = [p for p in (spec.get("pages") or []) if isinstance(p, dict) and p.get("path")]
        self._allowed_routes = {str(p.get("path")) for p in pages} | {"/", "/login"}
        self._allowed_api_routes = {f"/api/{scaffold.route_name(m.get('name', 'Item'))}"
                                    for m in (spec.get("data_model") or [])}
        self._write_one("components/AppNavbar.tsx", _multipage_navbar(spec), verbatim=True)
        self._write_one("app/layout.tsx", _multipage_root_layout(spec), verbatim=True)
        files = compile_component_pages(spec)
        for rel, content in files.items():
            self._write_one(rel, content, verbatim=True)
            if rel.endswith(".tsx") and ("/_components/" in rel or rel.startswith("components/features/")):
                self._component_fallbacks[rel] = content
        log.info("   Role-wise frontend: %d component/section/page file(s), %d exact routes",
                 len(files), len(pages))

    def fallback_for(self, fpath: str, component_name: str = "") -> str:
        """Return a route-aware fallback for an LLM-generated component."""
        return self._component_fallbacks.get(fpath) or _safe_component(
            component_name or Path(fpath).stem)

    def fix(self, errors: list):
        """
        1. Run `npm run build` to get the real compile error with exact file+line
        2. Parse which file(s) are broken
        3. Re-generate each broken file with full error context + full codebase context
        4. Write fixed files and emit to UI
        """
        log.info(f"   🔧 Starting fix pass ({len(errors)} tester errors)")

        # ── Step 1: get real compile errors from npm run build ────────────────
        build_errors = self._npm_build_errors()
        log.info(f"   npm build errors:\n{build_errors[:400] if build_errors else '  (none)'}")

        # Merge tester errors + build errors into one context string
        all_error_text = "\n".join(errors) + "\n" + build_errors

        # ── Step 2: identify broken files ─────────────────────────────────────
        broken = self._identify_broken(all_error_text)
        if not broken:
            # Last resort: regenerate all LLM-generated components
            broken = [f for f in self.built_files
                      if f.startswith("components/") and f.endswith((".jsx", ".tsx"))]
            log.info(f"   No specific file found — regenerating all {len(broken)} components")
        else:
            log.info(f"   Broken files: {broken}")

        # ── Step 3: build codebase context (all current files) ────────────────
        codebase_ctx = self._build_codebase_context()

        # ── Step 4: fix each broken file ──────────────────────────────────────
        for fpath in broken:
            name = fpath.split("/")[-1].replace(".jsx", "").replace(".tsx", "")
            current = self.built_files.get(fpath, "")
            log.info(f"   Re-generating {fpath}...")

            # Filter error text to lines relevant to this file
            file_errors = self._filter_errors_for_file(all_error_text, name, fpath)

            fixed = self._fix_component(name, current, file_errors, codebase_ctx)
            if not fixed:
                log.warning(f"   LLM fix failed for {fpath} — using safe fallback")
                fixed = self.fallback_for(fpath, name)

            self._write_one(fpath, fixed)
            log.info(f"   ✓ Saved {fpath} ({len(fixed)}B)")

    # ── LLM calls ─────────────────────────────────────────────────────────────

    def _gen(self, component_name: str, user_prompt: str, num_predict: int = 4096) -> str:
        """Stream generation via the shared LLM module, forward tokens to UI, return code."""
        try:
            _emit(f"\x00START:{component_name}")
            full = ""
            for tok in llm.stream_chat(
                [{"role": "user", "content": user_prompt}],
                model=self.model, system=SYSTEM_PROMPT, num_predict=num_predict,
            ):
                full += tok
                _emit(tok)
            _emit("\x00END")
            # Store raw LLM output so the fix pass can re-extract if needed.
            if not hasattr(self, "_raw_llm_outputs"):
                self._raw_llm_outputs = {}
            self._raw_llm_outputs[component_name] = full
            return self._extract(full)
        except Exception as e:
            log.error("   LLM gen failed (%s): %s", component_name, e)
            _emit("\x00END")
            return ""

    def _fix_component(self, name: str, broken: str, errors: str, codebase: str, raw_context: str = "") -> str:
        """Ask LLM to fix a component, giving it full error context + full codebase."""

        # Extract console/browser runtime errors separately — these are often the real cause
        console_errors = []
        for line in errors.splitlines():
            if "Console error" in line or "PageError" in line or "does not provide" in line:
                console_errors.append(line.strip())

        # Build specific actionable instructions from the errors
        specific_fixes = []
        for err in console_errors:
            # "does not provide an export named 'FiOval'" -> explicit fix instruction
            m = re.search(r"does not provide an export named '(\w+)'", err)
            if m:
                bad = m.group(1)
                specific_fixes.append(
                    f"- REMOVE \'{bad}\' from your imports — it does NOT EXIST in react-icons. "
                    f"Replace with a real icon: FiCircle for circles, FiX for X marks, FiGrid for grids."
                )
        for err in console_errors:
            if "Cannot find module" in err or "Failed to resolve" in err:
                specific_fixes.append(f"- Fix broken import: {err[:100]}")
            if "is not defined" in err:
                missing = re.search(r"(\w+) is not defined", err)
                if missing:
                    specific_fixes.append(
                        f"- '{missing.group(1)}' is not defined because you split it into a separate "
                        f"function. You MUST put ALL code into ONE single export default function {name}(). "
                        f"NO separate helper components allowed."
                    )

        # Blank page / invisible content fixes
        if "appears blank" in errors or "no visible content" in errors or "readable text" in errors:
            specific_fixes.append(
                "- The page renders BLANK. The component must have an EXPLICIT dark background. "
                "Add className='min-h-screen bg-gray-900 text-white' to your outermost div. "
                "Do NOT rely on tailwind defaults or transparent containers."
            )

        console_section = ""
        if console_errors:
            console_section = (
                "\n═══ BROWSER CONSOLE ERRORS (these are the REAL runtime errors) ═══\n"
                + "\n".join(f"  {e[:200]}" for e in console_errors[:5])
                + "\n"
            )
        fixes_section = ""
        if specific_fixes:
            fixes_section = (
                "\n═══ SPECIFIC THINGS YOU MUST FIX ═══\n"
                + "\n".join(specific_fixes)
                + "\n"
            )

        # If raw_context provided (previous full LLM output that had split components),
        # include it so the LLM can see the logic it wrote and merge it into one function
        raw_section = ""
        if raw_context:
            raw_section = (
                f"\n═══ PREVIOUS FULL OUTPUT (contains logic to merge into one function) ═══\n"
                f"{raw_context[:2000]}\n"
            )

        prompt = textwrap.dedent(f"""\
            Fix the broken React component below.
            {console_section}{fixes_section}
            ═══ ALL ERRORS ═══
            {errors[:400]}

            ═══ CODEBASE CONTEXT ═══
            {codebase[:1800]}

            ═══ BROKEN COMPONENT: {name} ═══
            {broken[:2500]}
            {raw_section}
            ═══ INSTRUCTIONS ═══
            - Fix EVERY error listed above — the browser console errors are the true cause
            - ONLY import from: react, react-dom, framer-motion, react-icons/*
            - BANNED packages (not installed, will crash): react-leaflet, react-router-dom,
              axios, lodash, chart.js, d3, three, @mui/material, @chakra-ui/react,
              react-query, zustand, styled-components, react-hot-toast, react-helmet
            - If you were using react-leaflet: replace with a <div> map placeholder
            - Only use icons that actually exist: FiHome, FiX, FiCircle, FiGrid, FiStar, FiMenu, etc.
            - Do NOT invent icon names — if unsure, use FiBox or FiSquare as a safe fallback
            - NEVER write /regex/ literals inside JSX — hoist them to const before return()
            - ALL logic must go inside the single export default function {name}() — no split components
            - Keep the same visual design and structure
            - Output ONLY the complete fixed JSX. Start with imports. No explanation.
            - Must end with: export default function {name}()
            """)
        try:
            _emit(f"\x00START:{name} (fix)")
            full = ""
            for tok in llm.stream_chat(
                [{"role": "user", "content": prompt}],
                model=self.model, system=SYSTEM_PROMPT,
                num_predict=4096, extra_opts={"temperature": 0.05},
            ):
                full += tok
                _emit(tok)
            _emit("\x00END")
            result = self._extract(full)
            return result if "export default" in result else ""
        except Exception as e:
            log.error("   fix LLM call failed: %s", e)
            _emit("\x00END")
            return ""

    # ── Error analysis ────────────────────────────────────────────────────────

    def _npm_build_errors(self) -> str:
        """
        Run `npm run build` (next build) which exits non-zero with the real
        compile error + file for the whole app. The strongest bug signal we have.
        """
        try:
            result = subprocess.run(
                [_npm(), "run", "build"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=240,
                env={**os.environ, "CI": "true", "MONGODB_URI": ""},
            )
            # next build writes compile errors to stderr/stdout.
            output = (result.stdout + "\n" + result.stderr).strip()
            if result.returncode != 0:
                log.info("   next build failed (good — we have the error)")
                return output[:2000]
            log.info("   next build succeeded — no compile errors!")
            return ""
        except Exception as e:
            log.warning("   next build check failed: %s", e)
            return ""

    def suppress_type_errors(self, max_passes: int = 3) -> int:
        """
        Neutralize genuine TypeScript type errors one exact line at a time by
        inserting `// @ts-ignore` directly above the offending line.

        Runs `npx tsc --noEmit` (needs node_modules → call AFTER deps install).
        Only errors in `components/*` are suppressed — the deterministic backbone
        (lib/models/routes) is clean by construction and left untouched. The build
        already can't fail on types (next.config ignoreBuildErrors), so this is a
        cleanup pass that keeps tsc/editor green — never load-bearing.

        Safety: we only suppress errors in the component *body* (before the render
        `return (`). Errors inside JSX are left to the ignoreBuildErrors net, so a
        `// @ts-ignore` line can never be injected into JSX (which would render as
        text, or worse, break a multi-line tag). Returns the number of lines added.
        """
        npx = shutil.which("npx") or ("npx.cmd" if os.name == "nt" else "npx")
        total = 0
        for _pass in range(max_passes):
            try:
                result = subprocess.run(
                    [npx, "tsc", "--noEmit", "--pretty", "false"],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    env={**os.environ, "CI": "true"},
                )
            except Exception as e:
                log.warning("   tsc type-check skipped: %s", e)
                return total
            out = (result.stdout or "") + "\n" + (result.stderr or "")
            if result.returncode == 0 or "error TS" not in out:
                break

            # Parse:  path/to/File.tsx(LINE,COL): error TSxxxx: message
            errors = {}
            for m in re.finditer(r'^(.+?\.tsx?)\((\d+),\d+\):\s*error TS', out, re.MULTILINE):
                errors.setdefault(m.group(1).strip(), set()).add(int(m.group(2)))
            if not errors:
                break

            pass_changes = 0
            for rel, line_nums in errors.items():
                # Only touch LLM-generated components. The deterministic backbone
                # (lib/models/routes) is clean by construction and must stay pristine;
                # any stray backbone error defers to the ignoreBuildErrors net.
                norm = rel.replace("\\", "/").lstrip("./")
                if not norm.startswith("components/"):
                    continue
                fp = self.project_dir / rel
                if not fp.exists():
                    fp = self.project_dir / rel.lstrip("./")
                if not fp.exists():
                    continue
                try:
                    lines = fp.read_text(encoding="utf-8").split("\n")
                except Exception:
                    continue

                # Render boundary: first top-level `return (` / `return <`. Only
                # suppress body errors above it (JSX errors → safety net).
                jsx_start = next(
                    (i for i, ln in enumerate(lines)
                     if re.match(r'\s*return\s*[\(<]', ln)),
                    len(lines),
                )

                changed = False
                # Bottom-to-top so earlier inserts don't shift later target lines.
                for ln in sorted(line_nums, reverse=True):
                    idx = ln - 1                       # 0-based offending line
                    if idx < 0 or idx >= jsx_start:    # out of range or inside JSX
                        continue
                    indent = re.match(r'[ \t]*', lines[idx]).group(0)
                    if idx > 0 and "@ts-ignore" in lines[idx - 1]:
                        continue                        # already suppressed
                    lines.insert(idx, f"{indent}// @ts-ignore")
                    changed = True
                    pass_changes += 1

                if changed:
                    new_text = "\n".join(lines)
                    try:
                        fp.write_text(new_text, encoding="utf-8")
                    except Exception:
                        continue
                    relkey = fp.relative_to(self.project_dir).as_posix()
                    if relkey in self.built_files:
                        self.built_files[relkey] = new_text

            total += pass_changes
            if pass_changes == 0:      # nothing suppressible left (all in JSX) → stop
                break

        if total:
            log.info("   suppress_type_errors: inserted %d // @ts-ignore line(s)", total)
        return total

    def _identify_broken(self, error_text: str) -> list:
        """
        Parse error text to find exactly which files are broken.
        Prioritises the file named directly in a Vite compile error over files
        that merely appear in stack traces (which causes innocent files like Navbar
        to be regenerated just because they're listed in the import chain).
        """
        # ── Priority 1: explicit compile error naming a component file ────────
        # next build / swc: "./components/Newsletter.tsx" or an absolute path.
        compile_match = re.search(
            r'[/\\.]components[/\\](\w{1,50})\.(?:jsx?|tsx?)',
            error_text, re.IGNORECASE
        )
        if compile_match:
            fpath = f"components/{compile_match.group(1)}.tsx"
            log.info("   _identify_broken → [%s] (compile error)", fpath)
            return self._filter_owned([fpath])

        # ── Priority 1b: React runtime error ──────────────────────────────────
        react_match = re.search(
            r'The above error occurred in the <(\w{1,50})> component',
            error_text, re.IGNORECASE
        )
        if react_match:
            fpath = f"components/{react_match.group(1)}.tsx"
            log.info("   _identify_broken → [%s] (React runtime error)", fpath)
            return self._filter_owned([fpath])

        # ── Priority 2: scan for any component file references ─────────────────
        found = []
        for line in error_text.splitlines():
            if len(line) > 300:
                continue
            if re.search(r'at \w+ \(http', line):   # skip browser stack-trace lines
                continue
            for m in re.finditer(
                r'[/\\.]components[/\\](\w{1,50})\.(?:jsx?|tsx?)',
                line, re.IGNORECASE
            ):
                fpath = f"components/{m.group(1)}.tsx"
                if fpath not in found:
                    found.append(fpath)

        # ── Priority 3: "Cannot find module" fallback ─────────────────────────
        if not found:
            for line in error_text.splitlines():
                if re.search(r'at \w+ \(http', line):
                    continue
                for m in re.finditer(r"components?[/\\](\w{1,50})['\".:]", line):
                    fpath = f"components/{m.group(1)}.tsx"
                    if fpath not in found:
                        found.append(fpath)

        result = self._filter_owned(found)
        log.info(f"   _identify_broken → {result}")
        return result

    def _filter_owned(self, fpaths: list) -> list:
        """Filter file paths to only those we generated (in built_files or on disk)."""
        result = []
        for f in fpaths:
            if len(f) > 120:
                continue
            if f in self.built_files:
                result.append(f)
            else:
                try:
                    if (self.project_dir / f).exists():
                        result.append(f)
                except OSError:
                    pass
        return result

    def _filter_errors_for_file(self, all_errors: str, name: str, fpath: str) -> str:
        """Return lines from error text relevant to the given file."""
        relevant = []
        for line in all_errors.splitlines():
            if name in line or fpath in line or fpath.split("/")[-1] in line:
                relevant.append(line)
        return "\n".join(relevant) if relevant else all_errors[:600]

    def _build_codebase_context(self) -> str:
        """
        Return a concise summary of all generated files so the LLM has full
        context when fixing — it can see what imports are available, etc.
        """
        parts = []
        # Show full content of small files, truncate large ones
        priority = ["app/page.tsx", "app/layout.tsx", "app/globals.css"]
        all_files = priority + [f for f in sorted(self.built_files) if f not in priority]
        for fname in all_files:
            content = self.built_files.get(fname, "")
            if not content:
                fp = self.project_dir / fname
                if fp.exists():
                    content = fp.read_text(encoding="utf-8", errors="replace")
            if not content:
                continue
            limit = 800 if fname.startswith("components/") else 400
            snippet = content[:limit] + (" ...[truncated]" if len(content) > limit else "")
            parts.append(f"── {fname} ──\n{snippet}")
        return "\n\n".join(parts)

    # ── Code extraction ───────────────────────────────────────────────────────

    def _extract(self, text: str) -> str:
        """Extract JSX code from LLM output, stripping markdown fences."""
        if not text:
            return ""
        # Strip markdown code fences
        for lang in ["jsx", "tsx", "javascript", "js", "typescript", "ts", ""]:
            m = re.search(rf"```{lang}\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(1).strip()
        # Raw code — looks like JSX/JS
        t = text.strip()
        if any(k in t for k in ["import ", "export default", "function ", "const ", "return ("]):
            return t
        return ""

    # ── Section / component prompts ───────────────────────────────────────────

    def _navbar_prompt(self, title, sections):
        links = [{"label": s, "href": f"#{s.lower()}"} for s in sections if s != "Navbar"]
        return textwrap.dedent(f"""\
            Write the Navbar client component for '{title}'.
            Navigation links (href = section id): {json.dumps(links)}

            Requirements:
            - First line: 'use client'
            - Fixed top, z-50, full width
            - Glassmorphism background that appears on scroll (useEffect + useState on window.scrollY)
            - Gradient logo text = '{title}'
            - Each link smooth-scrolls to its section id on click (document.getElementById(id).scrollIntoView)
            - Mobile hamburger menu (useState) using react-icons/fi (FiMenu, FiX)
            - export default function Navbar()

            Output ONLY the JSX starting with 'use client'.
            """)

    def _section_prompt(self, section, spec, contract):
        title       = spec.get("title", "My App")
        site_type   = spec.get("site_type", "general")
        color       = spec.get("color_scheme", "dark with indigo and cyan accents")
        style       = spec.get("style", "modern")
        description = spec.get("description", "")
        instructions = spec.get("special_instructions", "")
        features    = spec.get("key_features", [])
        return textwrap.dedent(f"""\
            Write the '{section}' section — one full-bleed band of a long, beautiful
            {site_type} page for '{title}'.

            Style: {style} | Colors: {color}
            App description: {description[:220]}
            Key features: {', '.join(features[:6]) if features else '(infer sensible ones)'}
            Notes: {instructions[:220]}

            ── BACKEND API CONTRACT ──
            {contract}

            Requirements:
            - First line: 'use client'
            - Outer element: <section id="{section.lower()}" className="py-24 px-6 ..."> with an
              EXPLICIT dark background band and a max-w-7xl mx-auto inner container
            - framer-motion whileInView reveals, responsive grid/layout, hover states,
              gradient heading, real specific copy (NO lorem, NO "Section content")
            - If this section shows or edits saved data, fetch the RELATIVE API routes above
              (load on mount with useEffect, re-fetch after create/update/delete, key by _id)
            - export default function {section}()

            Output ONLY the JSX starting with 'use client'.
            """)

    def _page_prompt(self, component: str, page: dict, model: dict | None,
                     spec: dict, contract: str) -> str:
        kind = str(page.get("kind") or "static")
        path = str(page.get("path") or "/")
        resource = scaffold.pascal(page.get("resource", "")) if page.get("resource") else ""
        seg = scaffold.route_name(resource) if resource else ""
        fields = (model or {}).get("fields") or []
        field_contract = json.dumps([
            {"name": f.get("name"), "type": f.get("type", "String"),
             "required": bool(f.get("required"))}
            for f in fields if f.get("name")
        ])
        behavior = {
            "landing": "Create a polished marketplace/app landing page with a strong hero, feature/value cards, and calls to the public list and sign-up routes.",
            "list": f"Load GET /api/{seg} on mount, render a responsive record grid, handle loading/error/empty states, and link each card to /{seg}/<record._id> with a normal <a>.",
            "detail": "Render the server-provided initialItem prop. Show its useful fields and a clear back link. Do not fetch the item again.",
            "form": f"Render controlled inputs for the resource fields. Submit JSON with POST /api/{seg}; show server errors and success, then navigate with window.location.href.",
            "dashboard-list": f"Load GET /api/{seg}/mine. Show only the signed-in user's records, link to the new form, and provide working edit/delete controls using /api/{seg}/<id>.",
            "admin": f"Load GET /api/{seg}. Render an admin management table/grid with working PUT/DELETE actions against /api/{seg}/<id>.",
            "dashboard": "Create a useful role dashboard overview with navigation cards based on the declared routes. Do not invent API endpoints.",
            "static": "Create a complete, polished static information page appropriate to its title and app domain.",
        }.get(kind, "Create a complete page appropriate to this route and title.")
        signature = (f"export default function {component}({{ initialItem }}: "
                     "{ initialItem: Record<string, unknown> })"
                     if kind == "detail" else f"export default function {component}()")
        # Public landing/marketing pages must render >= 4 distinct <section> bands
        # (a hard product requirement). Feed the LLM the SRS-declared sections and
        # relax the single-<section> root rule to a <main> wrapping several bands.
        srs_sections = [str(s).strip() for s in (page.get("sections") or []) if str(s).strip()]
        if kind in {"landing", "static"}:
            root_req = ("- Root element is a <main> that CONTAINS AT LEAST 4 sibling <section> bands; "
                        "each <section> has an explicit dark background and a responsive max-w-7xl "
                        "inner container with real headings and copy.")
            if srs_sections:
                section_directive = ("\n            - Render EACH of these required content sections as its "
                                     "own <section> band with domain-specific copy (heading + paragraphs + "
                                     "cards where useful): " + "; ".join(srs_sections)
                                     + ".\n            - There MUST be at least 4 <section> elements total.")
            else:
                section_directive = ("\n            - Include at least 4 <section> bands: a hero, a "
                                     "value/features band, a how-it-works band, and a contact/CTA band.")
        else:
            root_req = ("- Root element is a <section> with min-h-[calc(100vh-4rem)], explicit dark background, "
                        "responsive max-w-7xl content, visible heading, loading/error/empty states as applicable.")
            section_directive = ""
        return textwrap.dedent(f"""\
            Write the complete presentation component for this Next.js route.

            App: {spec.get('title', 'My App')}
            Description: {str(spec.get('description', ''))[:300]}
            Route: {path}
            Page title: {page.get('title', 'Page')}
            Page kind: {kind}
            Access: {page.get('access', 'public')}
            Resource: {resource or '(none)'}
            Resource fields: {field_contract}

            Required behavior:
            {behavior}

            FIXED BACKEND CONTRACT (never deviate from it):
            {contract}

            Requirements:
            - First line exactly: 'use client'
            - Use one exported component only, with this exact signature:
              {signature}
            - Use TypeScript interfaces/types for records, form values, and props.
            - Use relative fetch URLs only and credentials from the httpOnly cookie automatically.
            - Never send owner/userId from the browser and never implement auth or role checks client-side.
            - Do not invent routes, redirects, API endpoints, fields, metrics, or buttons. Use only
              the exact route/API contract above. Use `_id` for records and never `id`.
            - Every action button must perform a real declared API action or navigate to a declared route;
              no dead CTAs, placeholder handlers, or hardcoded business metrics.
            {root_req}
            - Use only React, framer-motion, react-icons/*, and browser APIs. Normal <a href> links are fine.
            - Make the page domain-specific and production-looking; no lorem ipsum or placeholder copy.{section_directive}
            - Output only complete TSX, with no markdown fences or explanation.
            """)

    def _multipage_fallback(self, component: str, page: dict, model: dict | None,
                            spec: dict) -> str:
        """Functional deterministic fallback used if generation or its fix loop fails."""
        kind = str(page.get("kind") or "static")
        title = str(page.get("title") or "Page").replace("'", "\\'")
        resource = scaffold.pascal(page.get("resource", "")) if page.get("resource") else ""
        seg = scaffold.route_name(resource) if resource else ""

        if kind == "detail":
            return textwrap.dedent(f"""\
                'use client'
                export default function {component}({{ initialItem }}: {{ initialItem: Record<string, unknown> }}) {{
                  const entries = Object.entries(initialItem).filter(([key]) => !['_id', '__v', 'owner'].includes(key))
                  return (
                    <section className='min-h-[calc(100vh-4rem)] bg-dark px-6 py-16'>
                      <div className='max-w-4xl mx-auto'>
                        <a href='/{seg}' className='text-accent text-sm'>Back to {seg}</a>
                        <h1 className='text-4xl font-black text-white mt-5 mb-8'>{title}</h1>
                        <div className='glass rounded-2xl p-8 grid sm:grid-cols-2 gap-6'>
                          {{entries.map(([key, value]) => (
                            <div key={{key}}><p className='text-xs uppercase text-slate-500'>{{key}}</p><p className='text-white mt-1'>{{String(value ?? '')}}</p></div>
                          ))}}
                        </div>
                      </div>
                    </section>
                  )
                }}
                """)

        if kind in {"list", "dashboard-list", "admin"} and seg:
            endpoint = f"/api/{seg}/mine" if kind == "dashboard-list" else f"/api/{seg}"
            can_delete = kind in {"dashboard-list", "admin"}
            path = str(page.get("path") or f"/{seg}")
            create_link = (f"<a href='{path}/new' className='bg-accent px-4 py-2 rounded-lg text-white text-sm font-medium'>Create new</a>"
                           if kind == "dashboard-list" else "")
            edit_link = ("<a className='text-accent text-sm' href={'" + path + "/' + row._id + '/edit'}>Edit</a>"
                         if kind == "dashboard-list" else "")
            delete_btn = ("<button onClick={() => remove(row._id)} className='text-red-400 text-sm'>Delete</button>"
                          if can_delete else "")
            return textwrap.dedent(f"""\
                'use client'
                import {{ useEffect, useState }} from 'react'
                interface Row {{ _id: string; [key: string]: unknown }}
                export default function {component}() {{
                  const [rows, setRows] = useState<Row[]>([])
                  const [loading, setLoading] = useState(true)
                  const [error, setError] = useState('')
                  const load = async () => {{
                    setLoading(true)
                    const r = await fetch('{endpoint}', {{ cache: 'no-store' }})
                    if (!r.ok) {{ setError('Unable to load records'); setLoading(false); return }}
                    const d = await r.json(); setRows(Array.isArray(d) ? d : (d.data || [])); setLoading(false)
                  }}
                  useEffect(() => {{ load() }}, [])
                  const remove = async (id: string) => {{
                    if (!window.confirm('Delete this record?')) return
                    const r = await fetch('/api/{seg}/' + id, {{ method: 'DELETE' }})
                    if (r.ok) load(); else setError('Delete was not allowed')
                  }}
                  return (
                    <section className='min-h-[calc(100vh-4rem)] bg-dark px-6 py-14'>
                      <div className='max-w-7xl mx-auto'>
                        <div className='flex items-end justify-between gap-4 mb-9'><div><p className='text-accent text-sm uppercase tracking-widest'>Collection</p><h1 className='text-4xl font-black text-white'>{title}</h1></div>
                          {create_link}</div>
                        {{loading ? <p className='text-slate-400'>Loading...</p> : error ? <p className='text-red-400'>{{error}}</p> : rows.length === 0 ? <div className='glass rounded-xl p-10 text-center text-slate-400'>No records yet.</div> :
                          <div className='grid md:grid-cols-2 xl:grid-cols-3 gap-5'>{{rows.map((row) => <article key={{row._id}} className='glass rounded-xl p-6'>
                            <h2 className='text-xl font-bold text-white'>{{String(row.title || row.name || '{resource}')}}</h2>
                            <p className='text-slate-400 text-sm mt-2 line-clamp-3'>{{String(row.description || row.summary || '')}}</p>
                            <div className='flex gap-4 mt-5 items-center'><a className='text-accent text-sm' href={{'/{seg}/' + row._id}}>View</a>
                              {edit_link}
                              {delete_btn}</div>
                          </article>)}}</div>}}
                      </div>
                    </section>
                  )
                }}
                """)

        if kind == "table-crud" and model and seg:
            fields = [f for f in (model.get("fields") or [])
                      if f.get("name") and f.get("name") not in ("owner",)]
            cols = fields[:4]
            initial = {str(f["name"]): (False if f.get("type") == "Boolean" else 0 if f.get("type") == "Number" else "") for f in fields}
            inputs = []
            for f in fields:
                fname = str(f["name"]); ftype = str(f.get("type", "String"))
                label = fname.replace("_", " ").title()
                enum = f.get("enum")
                if ftype == "Boolean":
                    inputs.append(f"<label className='flex items-center gap-2 text-sm text-slate-300'><input type='checkbox' checked={{Boolean(form.{fname})}} onChange={{(e) => setForm({{ ...form, {fname}: e.target.checked }})}} /> {label}</label>")
                elif enum:
                    opts = "".join(f"<option value='{v}'>{v}</option>" for v in enum)
                    inputs.append(f"<label className='block'><span className='text-xs text-slate-400'>{label}</span><select value={{String(form.{fname} ?? '')}} onChange={{(e) => setForm({{ ...form, {fname}: e.target.value }})}} className='mt-1 w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-white'>{opts}</select></label>")
                else:
                    html_type = "number" if ftype == "Number" else "date" if ftype == "Date" else "text"
                    cast = "Number(e.target.value)" if ftype == "Number" else "e.target.value"
                    inputs.append(f"<label className='block'><span className='text-xs text-slate-400'>{label}</span><input type='{html_type}' value={{form.{fname} == null ? '' : String(form.{fname})}} onChange={{(e) => setForm({{ ...form, {fname}: {cast} }})}} className='mt-1 w-full bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-white' /></label>")
            headers = "".join(f"<th className='text-left px-3 py-2 font-medium'>{str(c['name']).replace('_',' ').title()}</th>" for c in cols)
            cells = "".join(f"<td className='px-3 py-2'>{{String((row as any).{c['name']} ?? '')}}</td>" for c in cols)
            return textwrap.dedent(f"""\
                'use client'
                import {{ useEffect, useState }} from 'react'
                interface Row {{ _id: string; [k: string]: unknown }}
                export default function {component}() {{
                  const [rows, setRows] = useState<Row[]>([])
                  const [loading, setLoading] = useState(true)
                  const [error, setError] = useState('')
                  const [open, setOpen] = useState(false)
                  const [editId, setEditId] = useState<string | null>(null)
                  const [form, setForm] = useState<Record<string, unknown>>({json.dumps(initial)})
                  const load = async () => {{
                    setLoading(true)
                    const r = await fetch('/api/{seg}', {{ cache: 'no-store' }})
                    if (r.ok) {{ const d = await r.json(); setRows(Array.isArray(d) ? d : (d.data || [])) }} else setError('Unable to load')
                    setLoading(false)
                  }}
                  useEffect(() => {{ load() }}, [])
                  const startNew = () => {{ setEditId(null); setForm({json.dumps(initial)}); setOpen(true) }}
                  const startEdit = (row: Row) => {{ setEditId(row._id); setForm(row); setOpen(true) }}
                  const save = async (e: React.FormEvent) => {{
                    e.preventDefault(); setError('')
                    const url = editId ? '/api/{seg}/' + editId : '/api/{seg}'
                    const r = await fetch(url, {{ method: editId ? 'PUT' : 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(form) }})
                    if (r.ok) {{ setOpen(false); load() }} else {{ const d = await r.json().catch(() => ({{}})); setError(d.error || 'Save failed') }}
                  }}
                  const remove = async (id: string) => {{
                    if (!window.confirm('Delete this record?')) return
                    const r = await fetch('/api/{seg}/' + id, {{ method: 'DELETE' }})
                    if (r.ok) load(); else setError('Delete failed')
                  }}
                  return (
                    <section>
                      <div className='flex items-center justify-between mb-6'>
                        <h1 className='text-2xl font-bold text-white'>{title}</h1>
                        <button onClick={{startNew}} className='bg-accent px-4 py-2 rounded-lg text-white text-sm font-medium'>New</button>
                      </div>
                      {{error && <p className='text-red-400 mb-4'>{{error}}</p>}}
                      {{loading ? <p className='text-slate-400'>Loading...</p> : rows.length === 0 ? <div className='glass rounded-xl p-10 text-center text-slate-400'>No records yet.</div> :
                        <div className='overflow-x-auto glass rounded-xl'>
                          <table className='w-full text-sm text-slate-300'>
                            <thead className='text-slate-500 border-b border-white/10'><tr>{headers}<th className='px-3 py-2'></th></tr></thead>
                            <tbody>{{rows.map((row) => (
                              <tr key={{row._id}} className='border-b border-white/5'>{cells}
                                <td className='px-3 py-2 text-right whitespace-nowrap'>
                                  <button onClick={{() => startEdit(row)}} className='text-accent mr-3'>Edit</button>
                                  <button onClick={{() => remove(row._id)}} className='text-red-400'>Delete</button>
                                </td>
                              </tr>
                            ))}}</tbody>
                          </table>
                        </div>}}
                      {{open && (
                        <div className='fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50' onClick={{() => setOpen(false)}}>
                          <form onSubmit={{save}} onClick={{(e) => e.stopPropagation()}} className='bg-slate-900 border border-white/10 rounded-2xl p-6 w-full max-w-lg max-h-[85vh] overflow-y-auto space-y-3'>
                            <h2 className='text-lg font-bold text-white'>{{editId ? 'Edit' : 'New'}} {resource}</h2>
                            {''.join(inputs)}
                            <div className='flex gap-3 pt-2'><button type='submit' className='bg-accent px-4 py-2 rounded-lg text-white flex-1'>Save</button>
                              <button type='button' onClick={{() => setOpen(false)}} className='px-4 py-2 rounded-lg bg-white/10 text-white'>Cancel</button></div>
                          </form>
                        </div>
                      )}}
                    </section>
                  )
                }}
                """)

        if kind == "form" and model and seg:
            fields = [f for f in (model.get("fields") or []) if f.get("name") and f.get("name") != "owner"]
            initial = {str(f["name"]): (False if f.get("type") == "Boolean" else 0 if f.get("type") == "Number" else "") for f in fields}
            path = str(page.get("path") or f"/{seg}/new")
            back = re.sub(r"/(new|\[id\]/edit)$", "", path) or f"/{seg}"
            inputs = []
            for f in fields:
                fname = str(f["name"])
                ftype = str(f.get("type", "String"))
                label = fname.replace("_", " ").title()
                if ftype == "Boolean":
                    inputs.append(
                        f"<label className='flex items-center gap-3 text-sm text-slate-300'>"
                        f"<input type='checkbox' checked={{Boolean(form.{fname})}} onChange={{(e) => setForm({{ ...form, {fname}: e.target.checked }})}} /> {label}</label>"
                    )
                    continue
                html_type = "number" if ftype == "Number" else "date" if ftype == "Date" else "text"
                cast = "Number(e.target.value)" if ftype == "Number" else "e.target.value"
                inputs.append(
                    f"<label className='block'><span className='text-sm text-slate-400'>{label}</span>"
                    f"<input type='{html_type}' value={{form.{fname} == null ? '' : String(form.{fname})}} onChange={{(e) => setForm({{ ...form, {fname}: {cast} }})}}"
                    f" className='mt-1 w-full bg-slate-900 border border-white/10 rounded-lg px-4 py-3 text-white' /></label>"
                )
            return textwrap.dedent(f"""\
                'use client'
                import {{ useEffect, useState }} from 'react'
                import {{ useParams, useRouter }} from 'next/navigation'
                export default function {component}() {{
                  const params = useParams<{{ id?: string }}>()
                  const id = params?.id
                  const router = useRouter()
                  const [form, setForm] = useState<Record<string, unknown>>({json.dumps(initial)})
                  const [error, setError] = useState('')
                  const [saving, setSaving] = useState(false)
                  useEffect(() => {{
                    if (!id) return
                    fetch('/api/{seg}/' + id, {{ cache: 'no-store' }})
                      .then((r) => (r.ok ? r.json() : null))
                      .then((d) => {{ if (d) setForm(d) }})
                  }}, [id])
                  const submit = async (e: React.FormEvent) => {{
                    e.preventDefault(); setSaving(true); setError('')
                    const url = id ? '/api/{seg}/' + id : '/api/{seg}'
                    const method = id ? 'PUT' : 'POST'
                    const r = await fetch(url, {{ method, headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(form) }})
                    if (r.ok) {{ router.push('{back}'); router.refresh() }}
                    else {{ const data = await r.json().catch(() => ({{}})); setError(data.error || 'Unable to save'); setSaving(false) }}
                  }}
                  return <section className='min-h-[calc(100vh-4rem)] bg-dark px-6 py-14'><form onSubmit={{submit}} className='max-w-2xl mx-auto glass rounded-2xl p-8 space-y-5'>
                    <h1 className='text-3xl font-black text-white'>{{id ? 'Edit' : 'New'}} {resource}</h1>{''.join(inputs)}
                    {{error && <p className='text-red-400'>{{error}}</p>}}<button disabled={{saving}} className='w-full bg-accent text-white rounded-lg py-3'>{{saving ? 'Saving...' : 'Save'}}</button>
                  </form></section>
                }}
                """)

        if kind == "dashboard":
            endpoints = [f"/api/{scaffold.route_name(m.get('name', 'Item'))}" for m in (spec.get("data_model") or [])]
            return textwrap.dedent(f"""\
                'use client'
                import {{ useEffect, useState }} from 'react'
                export default function {component}() {{
                  const [counts, setCounts] = useState<Record<string, number>>({{}})
                  const [ready, setReady] = useState(false)
                  useEffect(() => {{
                    Promise.all({json.dumps(endpoints)}.map(async (endpoint) => {{
                      const r = await fetch(endpoint, {{ cache: 'no-store' }})
                      const d = r.ok ? await r.json() : []
                      const rows = Array.isArray(d) ? d : (d?.data || [])
                      return [endpoint, Array.isArray(rows) ? rows.length : 0] as const
                    }})).then((pairs) => setCounts(Object.fromEntries(pairs)))
                      .finally(() => setReady(true))
                  }}, [])
                  const cards = Object.entries(counts).map(([k, v]) => ({{ label: k.replace('/api/', '').replaceAll('-', ' '), value: v }}))
                  return (
                    <section>
                      <h1 className='text-2xl font-bold text-white mb-6'>{title}</h1>
                      {{!ready ? <p className='text-slate-400'>Loading...</p> :
                        <div className='grid grid-cols-2 md:grid-cols-4 gap-4'>
                          {{cards.map((c) => (
                            <div key={{c.label}} className='glass rounded-xl p-5'>
                              <p className='text-xs uppercase text-slate-500'>{{c.label}}</p>
                              <p className='text-3xl font-black text-white mt-1'>{{String(c.value)}}</p>
                            </div>
                          ))}}
                        </div>}}
                    </section>
                  )
                }}
                """)

        if kind == "reports":
            return textwrap.dedent(f"""\
                'use client'
                import {{ useEffect, useState }} from 'react'
                const TYPES = ['sales', 'pos', 'rentals', 'invoices']
                export default function {component}() {{
                  const [type, setType] = useState('sales')
                  const [data, setData] = useState<any>(null)
                  const load = () => fetch('/api/reports?type=' + type, {{ cache: 'no-store' }}).then((r) => (r.ok ? r.json() : null)).then((d) => setData(d?.data || null))
                  useEffect(() => {{ load() }}, [type])
                  const rows: any[] = data?.rows || []
                  const cols = rows[0] ? Object.keys(rows[0]).filter((k) => k !== '__v').slice(0, 6) : []
                  const csv = () => {{
                    if (!rows.length) return
                    const header = Object.keys(rows[0])
                    const lines = [header.join(','), ...rows.map((r) => header.map((c) => JSON.stringify(r[c] ?? '')).join(','))]
                    const blob = new Blob([lines.join('\\n')], {{ type: 'text/csv' }})
                    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = type + '-report.csv'; a.click()
                  }}
                  return (
                    <section>
                      <div className='flex items-center justify-between mb-6 gap-3 flex-wrap'>
                        <h1 className='text-2xl font-bold text-white'>{title}</h1>
                        <div className='flex gap-3'>
                          <select value={{type}} onChange={{(e) => setType(e.target.value)}} className='bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-white text-sm'>
                            {{TYPES.map((t) => <option key={{t}} value={{t}}>{{t}}</option>)}}
                          </select>
                          <button onClick={{csv}} className='bg-accent px-4 py-2 rounded-lg text-white text-sm'>Export CSV</button>
                        </div>
                      </div>
                      <p className='text-slate-400 mb-4'>Total: {{data?.total ?? 0}} — {{data?.count ?? 0}} records</p>
                      {{cols.length === 0 ? <div className='glass rounded-xl p-10 text-center text-slate-400'>No data.</div> :
                        <div className='overflow-x-auto glass rounded-xl'><table className='w-full text-sm text-slate-300'>
                          <thead className='text-slate-500 border-b border-white/10'><tr>{{cols.map((c) => <th key={{c}} className='text-left px-3 py-2'>{{c}}</th>)}}</tr></thead>
                          <tbody>{{rows.map((r, i) => <tr key={{i}} className='border-b border-white/5'>{{cols.map((c) => <td key={{c}} className='px-3 py-2'>{{String(r[c] ?? '')}}</td>)}}</tr>)}}</tbody>
                        </table></div>}}
                    </section>
                  )
                }}
                """)

        # Public landing / static marketing pages → guaranteed >= 4 <section> bands,
        # built from the SRS-declared page.sections (the user's hard requirement).
        if kind in {"landing", "static"}:
            def _t(s):
                return re.sub(r"[<>{}]", "", str(s)).strip()
            brand = _t(spec.get("brand_name") or spec.get("title") or title)
            tagline = _t(spec.get("tagline") or spec.get("description") or "")[:180]
            desc = _t(spec.get("description") or "")[:240] or tagline
            secs = [_t(s) for s in (page.get("sections") or []) if _t(s)]
            public_links = [str(pp.get("path")) for pp in (spec.get("pages") or [])
                            if pp.get("access") == "public"
                            and str(pp.get("path")) not in ("/", str(page.get("path")))]
            cta_href = public_links[0] if public_links else "/login"
            hero_label = secs[0] if (secs and "hero" in secs[0].lower()) else ""
            bands = secs[1:] if hero_label else list(secs)
            _pad = ["What we offer", "How it works", "Why choose us", "Get in touch"]
            while len(bands) < 3:
                bands.append(_pad[len(bands) % len(_pad)])
            band_jsx = []
            for idx, b in enumerate(bands):
                bid = re.sub(r"[^a-z0-9]+", "-", b.lower()).strip("-") or f"band-{idx}"
                if any(w in b.lower() for w in ("contact", "footer", "reach", "touch")):
                    band_jsx.append(
                        f"<section id='{bid}' className='py-20 px-6 bg-slate-950 border-t border-white/10'>"
                        f"<div className='max-w-4xl mx-auto text-center'>"
                        f"<h2 className='text-3xl font-bold text-white'>{b}</h2>"
                        f"<p className='text-slate-400 mt-3'>Get in touch with the {brand} team. We typically reply within one business day.</p>"
                        f"<a href='/login' className='inline-block mt-6 bg-accent text-white px-6 py-3 rounded-lg font-medium'>Staff sign in</a>"
                        f"</div></section>")
                else:
                    cards = "".join(
                        f"<div className='glass rounded-2xl p-6'>"
                        f"<h3 className='text-lg font-bold text-white'>{b} {n}</h3>"
                        f"<p className='text-slate-400 mt-2 text-sm'>Purpose-built for {brand}. Reliable, fast and easy to use.</p>"
                        f"</div>" for n in range(1, 4))
                    bg = "bg-dark" if idx % 2 else "bg-slate-950"
                    band_jsx.append(
                        f"<section id='{bid}' className='py-20 px-6 {bg}'>"
                        f"<div className='max-w-7xl mx-auto'>"
                        f"<h2 className='text-3xl md:text-4xl font-black text-white mb-3'>{b}</h2>"
                        f"<p className='text-slate-400 max-w-2xl mb-10'>{desc}</p>"
                        f"<div className='grid md:grid-cols-3 gap-6'>{cards}</div>"
                        f"</div></section>")
            hero_headline = hero_label or brand
            bands_joined = "".join(band_jsx)
            return textwrap.dedent(f"""\
                'use client'
                export default function {component}() {{
                  return (
                    <main>
                      <section id='hero' className='min-h-[70vh] flex items-center bg-gradient-to-b from-slate-950 to-dark px-6 py-24'>
                        <div className='max-w-5xl mx-auto text-center'>
                          <h1 className='text-5xl md:text-7xl font-black text-white'>{hero_headline}</h1>
                          <p className='text-slate-300 text-lg md:text-xl mt-6 max-w-2xl mx-auto'>{tagline or desc}</p>
                          <div className='flex gap-4 justify-center mt-10 flex-wrap'>
                            <a href='{cta_href}' className='bg-accent text-white px-7 py-3 rounded-lg font-semibold'>Get started</a>
                            <a href='/login' className='border border-white/20 text-white px-7 py-3 rounded-lg font-semibold'>Staff sign in</a>
                          </div>
                        </div>
                      </section>
                      {bands_joined}
                    </main>
                  )
                }}
                """)

        description = str(spec.get("description") or "A focused workspace for your next step.").replace("'", "\\'")
        return textwrap.dedent(f"""\
            'use client'
            import {{ motion }} from 'framer-motion'
            export default function {component}() {{
              return (
                <section className='min-h-[calc(100vh-4rem)] bg-gradient-to-b from-slate-950 to-dark px-6 py-20'>
                  <motion.div initial={{{{ opacity: 0, y: 24 }}}} animate={{{{ opacity: 1, y: 0 }}}} className='max-w-6xl mx-auto'>
                    <p className='text-accent uppercase tracking-[0.25em] text-sm mb-4'>{page.get('kind', 'page')}</p>
                    <h1 className='text-5xl md:text-7xl font-black text-white max-w-4xl'>{title}</h1>
                    <p className='text-slate-400 text-lg mt-6 max-w-2xl'>{description}</p>
                    <div className='grid md:grid-cols-3 gap-5 mt-12'>{{['Discover', 'Manage', 'Grow'].map((label) => <div key={{label}} className='glass rounded-2xl p-6'><h2 className='text-xl font-bold text-white'>{{label}}</h2><p className='text-slate-400 mt-2'>Everything you need, connected in one secure experience.</p></div>)}}</div>
                  </motion.div>
                </section>
              )
            }}
            """)

    def _fallback_navbar(self, title: str, sections: list) -> str:
        links = [s for s in sections if s != "Navbar"]
        items = "\n          ".join(
            f'<a href="#{s.lower()}" onClick={{smoothScroll}} className="text-sm text-gray-400 hover:text-white transition-colors uppercase tracking-widest">{s}</a>'
            for s in links
        )
        return textwrap.dedent(f"""\
            'use client'
            import {{ useState, useEffect }} from 'react'
            export default function Navbar() {{
              const [scrolled, setScrolled] = useState(false)
              const [open, setOpen] = useState(false)
              useEffect(() => {{
                const fn = () => setScrolled(window.scrollY > 50)
                window.addEventListener('scroll', fn)
                return () => window.removeEventListener('scroll', fn)
              }}, [])
              const smoothScroll = (e) => {{
                e.preventDefault()
                const id = e.target.getAttribute('href')?.slice(1)
                document.getElementById(id)?.scrollIntoView({{ behavior: 'smooth' }})
                setOpen(false)
              }}
              return (
                <nav className={{`fixed top-0 w-full z-50 transition-all duration-300 ${{scrolled ? 'backdrop-blur-xl bg-black/60 border-b border-white/10' : 'bg-transparent'}}`}}>
                  <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
                    <a href="#" className="text-xl font-black gradient-text">{title}</a>
                    <div className="hidden md:flex gap-8">
                      {items}
                    </div>
                    <button className="md:hidden text-white text-xl" onClick={{() => setOpen(!open)}}>☰</button>
                  </div>
                  {{open && (
                    <div className="md:hidden bg-black/90 px-6 py-4 flex flex-col gap-3">
                      {chr(10).join(f'<a href="#{s.lower()}" onClick={{smoothScroll}} className="text-gray-300 py-2 border-b border-white/10">{s}</a>' for s in links)}
                    </div>
                  )}}
                </nav>
              )
            }}
            """)

    # ── File I/O ──────────────────────────────────────────────────────────────

    def _write(self, files: dict):
        for fname, content in files.items():
            self._write_one(fname, content)

    def _write_one(self, fname: str, content: str, verbatim: bool = False):
        # Only LLM-generated leaf components (components/*.tsx) get extracted +
        # sanitized. Deterministic scaffold files (app/, lib/, models/, config) and
        # deterministic templates (verbatim=True) are written as-is.
        is_component = (
            not verbatim
            and fname.startswith("components/")
            and fname.endswith((".jsx", ".tsx"))
        )
        if is_component:
            component_name = Path(fname).stem
            # Step 1: extract only the valid portion of the LLM output
            content = self._extract_valid_component(content, component_name)
            # Step 2: apply import fixes (react-icons/all, react-scroll, etc.)
            content = self._sanitize_jsx(content, fname)

        fp = self.project_dir / fname
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        self.built_files[fname] = content
        sz = f"{len(content)//1024:.1f}KB" if len(content) >= 1024 else f"{len(content)}B"
        log.info(f"   ✎ {fname} ({sz})")
        self._on_write(fname, sz, content)


    def _extract_valid_component(self, code: str, component_name: str) -> str:
        """
        Extract a valid React component from messy LLM output.
        - Collects all import lines
        - Finds helper components (PascalCase functions before export default)
          that are actually referenced in the export default, and includes them
        - Handles the "split component" pattern: LLM writes Calculator() + App() { <Calculator/> }
        - Falls back to _safe_component if extraction fails
        """
        # Strip markdown code fences
        code = re.sub(r"```[a-z]*", "", code).replace("```", "").strip()

        lines = code.splitlines()

        # Collect all import lines from anywhere in the output
        imports = []
        seen = set()
        for line in lines:
            s = line.strip()
            if re.match(r"^import\s", s) and s not in seen:
                imports.append(s)
                seen.add(s)

        # ── Find export default function ────────────────────────────────────
        pat = re.compile(
            rf"^\s*export\s+default\s+function\s+{re.escape(component_name)}\s*\(",
            re.MULTILINE,
        )
        m = pat.search(code)
        if not m:
            m = re.search(r"^\s*export\s+default\s+function\s+\w+\s*\(", code, re.MULTILINE)
        if not m:
            log.warning(f"   _extract: no export default function in {component_name} -> safe fallback")
            return _safe_component(component_name)

        export_start = m.start()

        # ── Brace-count helper to extract a full block ───────────────────────
        # skip_params: for functions, skip a leading `(...)` parameter list so a
        # destructured/typed param like `({ x }: Props)` isn't mistaken for the
        # body — otherwise the component truncates at the destructuring brace.
        def brace_extract(src: str, start_pos: int, skip_params: bool = False):
            scan_from = start_pos
            if skip_params:
                pp = src.find("(", start_pos)
                bb = src.find("{", start_pos)
                if pp != -1 and (bb == -1 or pp < bb):
                    depth = 0; i = pp
                    while i < len(src):
                        if src[i] == "(": depth += 1
                        elif src[i] == ")":
                            depth -= 1
                            if depth == 0:
                                break
                        i += 1
                    scan_from = i          # search the body '{' after the params
            bp = src.find("{", scan_from)
            if bp == -1:
                return None, -1
            depth = 0; pos = bp
            while pos < len(src):
                if src[pos] == "{": depth += 1
                elif src[pos] == "}": depth -= 1
                if depth == 0: break
                pos += 1
            return src[start_pos: pos + 1].strip(), pos

        # ── Extract helper PascalCase functions defined BEFORE export ────────
        # Pattern: "function FooBar(" or "const FooBar = () => {" or "const FooBar = function"
        helper_pat = re.compile(
            r"^(?!export)\s*"
            r"(?:function\s+([A-Z]\w*)\s*\(|"
            r"const\s+([A-Z]\w*)\s*=\s*(?:\([^)]*\)\s*=>|function)\s*\{)",
            re.MULTILINE,
        )
        helpers_code = []
        seen_helpers = set()
        for hm in helper_pat.finditer(code):
            fn_name = hm.group(1) or hm.group(2)
            if not fn_name or fn_name == component_name:
                continue
            if fn_name in seen_helpers:
                continue
            # Skip if this match itself is inside an export default block
            # (we don't want to grab inner functions of the export default as helpers)
            if hm.start() == export_start:
                continue
            block, end_pos = brace_extract(code, hm.start(), skip_params=True)
            if block and len(block) > 30:
                helpers_code.append((fn_name, block))
                seen_helpers.add(fn_name)

        # ── Preserve top-level TypeScript type declarations ──────────────────
        # .tsx components legitimately declare `interface X {}` / `type X = …`
        # before the component. Extraction must keep them or the body's type
        # references (useState<X>(), `: X`, `as X`) dangle. Only those defined
        # OUTSIDE the export default block are hoisted.
        type_decls = []
        seen_types = set()
        for tm in re.finditer(r"^[ \t]*(?:export\s+)?(interface|type)\s+(\w+)", code, re.MULTILINE):
            kind, tname = tm.group(1), tm.group(2)
            if tname in seen_types or tm.start() >= export_start:
                continue
            brace_pos = code.find("{", tm.start())
            nl = code.find("\n", tm.start())
            if kind == "interface" or (brace_pos != -1 and (nl == -1 or brace_pos < nl)):
                block, _ = brace_extract(code, tm.start())
            else:
                # single-line `type X = A | B` → up to the statement end
                end_m = re.search(r"[;\n]", code[tm.start():])
                block = code[tm.start(): tm.start() + (end_m.start() if end_m else 0)].strip()
            if block:
                type_decls.append(block)
                seen_types.add(tname)
        if type_decls:
            log.info(f"   _extract: preserving type decl(s): {sorted(seen_types)}")

        # Preserve uppercase top-level data constants referenced by the component.
        # Dropping PROPERTY_TYPES/AMENITY_OPTIONS/ROLE_HOME can leave code that
        # compiles but throws a ReferenceError only when its route renders.
        const_decls = []
        seen_consts = set()
        const_pat = re.compile(
            r"^[ \t]*(?:export\s+)?const\s+([A-Z][A-Z0-9_]*)\b[^=\n]*=",
            re.MULTILINE,
        )
        for cm in const_pat.finditer(code):
            cname = cm.group(1)
            if cm.start() >= export_start or cname in seen_consts:
                continue
            pos, depth, quote, escaped = cm.end(), 0, None, False
            while pos < export_start:
                ch = code[pos]
                if quote:
                    if escaped:
                        escaped = False
                    elif ch == "\\":
                        escaped = True
                    elif ch == quote:
                        quote = None
                else:
                    if ch in "'\"`":
                        quote = ch
                    elif ch in "([{":
                        depth += 1
                    elif ch in ")]}":
                        depth = max(0, depth - 1)
                    elif (ch == ";" or ch == "\n") and depth == 0:
                        if ch == ";":
                            pos += 1
                        break
                pos += 1
            block = code[cm.start():pos].strip()
            if block:
                const_decls.append(block)
                seen_consts.add(cname)
        if const_decls:
            log.info(f"   _extract: preserving const(s): {sorted(seen_consts)}")

        # ── Extract the export default function body ─────────────────────────
        func_body, _ = brace_extract(code, export_start, skip_params=True)
        if not func_body:
            log.warning(f"   _extract: no opening brace in {component_name} -> safe fallback")
            return _safe_component(component_name)

        # Strip leading indent from function declaration
        func_lines = func_body.splitlines()
        if func_lines:
            indent = len(func_lines[0]) - len(func_lines[0].lstrip())
            if indent > 0:
                func_lines = [fl[indent:] if fl.startswith(" " * indent) else fl for fl in func_lines]
            func_body = "\n".join(func_lines)

        # ── Only include helpers actually used in the export default ─────────
        # Check for <Name, <Name/, or {Name} usage in the export body
        used_helpers = [
            (name, block) for name, block in helpers_code
            if (f"<{name}" in func_body or f"<{name}/" in func_body
                or f"{{{name}" in func_body)
        ]
        if used_helpers:
            log.info(f"   _extract: including helper(s): {[n for n,_ in used_helpers]}")

        # ── Thin-wrapper rescue: export is tiny, largest helper becomes main ──
        # Handles: LLM writes Calculator() (big) + App() { <Calculator/> } (tiny)
        # Works whether Calculator comes before OR after App in the file.
        if not used_helpers and len(func_body) < 350 and helpers_code:
            # But first: maybe used_helpers check missed something — re-check loosely
            for name, block in helpers_code:
                if name in func_body:  # any mention of the name
                    used_helpers = [(name, block)]
                    log.info(f"   _extract: loose-match helper '{name}' included")
                    break

        # ── Thin-wrapper rescue: if export is tiny but helpers are large ─────
        # The LLM split the real component into Helper() + thin App(){<Helper/>}
        # In this case adopt the LARGEST helper as the main component.
        if not used_helpers and len(func_body) < 350 and helpers_code:
            largest = max(helpers_code, key=lambda x: len(x[1]))
            log.warning(
                f"   _extract: thin wrapper ({len(func_body)}B) — adopting "
                f"'{largest[0]}' as main component"
            )
            adopted = largest[1]
            # Rename function to component_name
            adopted = re.sub(
                rf"\bfunction\s+{re.escape(largest[0])}\b",
                f"function {component_name}",
                adopted, count=1
            )
            adopted = re.sub(
                rf"\bconst\s+{re.escape(largest[0])}\b",
                f"const {component_name}",
                adopted, count=1
            )
            if adopted.lstrip().startswith("function "):
                adopted = "export default " + adopted.lstrip()
            func_body = adopted
            used_helpers = []

        if not imports:
            imports = ["import { motion } from 'framer-motion'"]

        # ── Reconstruct: imports + type decls + helpers + export default ─────
        parts = ["\n".join(imports), ""]
        for block in type_decls:
            parts.append(block)
            parts.append("")
        for block in const_decls:
            parts.append(block)
            parts.append("")
        for _, block in used_helpers:
            parts.append(block)
            parts.append("")
        parts.append(func_body)
        result = "\n".join(parts) + "\n"

        # Sanity: unbalanced braces means extraction went wrong
        if abs(result.count("{") - result.count("}")) > 4:
            log.warning(f"   _extract: unbalanced braces in {component_name} -> safe fallback")
            return _safe_component(component_name)

        log.info(f"   _extract: OK {component_name} ({len(imports)} imports, {len(result)}B)")
        return result

    # kept for backward compat — now only called from _write_one after extraction
    def _quick_check(self, code: str, component_name: str) -> str:
        """Lightweight sanity check after extraction. Returns reason if bad, '' if OK."""
        if not code or len(code.strip()) < 30:
            return "empty"
        if "export default" not in code:
            return "missing export default"
        if re.search(rf'return\s*\(\s*<{re.escape(component_name)}\s*/?>', code):
            return "self-referential render"
        return ""

    def _sanitize_jsx(self, code: str, fname: str) -> str:
        """
        Deterministic post-processing of every JSX file before writing to disk.
        Fixes the most common LLM mistakes that cause Vite compile errors.
        No LLM involved — pure regex, runs instantly on every file.
        """
        original = code
        changes = []

        # Recurring runtime defects are fixed at the shared source boundary so a
        # later generation cannot reintroduce them in an individual project.
        for bad, good, rule in [
            ("ameniments", "amenities", "field typo"),
            ("/owner/dashboard", "/owner", "invalid owner redirect"),
        ]:
            if bad in code:
                code = code.replace(bad, good)
                changes.append(f"regression fix {rule}")
        for prefix in ("item", "row", "record"):
            fixed, count = re.subn(rf"\b{prefix}\.id\b", f"{prefix}._id", code)
            if count:
                code = fixed
                changes.append(f"normalized {prefix}.id to {prefix}._id")
        if self._allowed_routes:
            fallback_route = next((r for r in self._allowed_routes if r not in {"/login", "/signup"}), "/")
            def _safe_route(match):
                prefix, href = match.group(1), match.group(2)
                if href == "/register" and "/signup" in self._allowed_routes:
                    return prefix + "/signup"
                if href in self._allowed_routes or href.startswith("/api/") or href.startswith("/#"):
                    return match.group(0)
                return prefix + fallback_route
            code, route_rewrites = re.subn(
                r"((?:href\s*=|router\.push\()\s*['\"])(/[^'\"#]+)",
                _safe_route, code
            )
            if route_rewrites:
                changes.append(f"rewrote {route_rewrites} undeclared route link(s)")

        # ── 0. (removed) TypeScript stripping ──────────────────────────────────
        # Components are now .tsx files, so TypeScript syntax (generics, interfaces,
        # annotations, `as` casts) is VALID — Next's SWC compiler strips the types
        # at build time. The old regex-based stripper corrupted real TSX and is gone;
        # genuine type *mismatches* are handled surgically by suppress_type_errors().

        # ── 1. react-icons/all  →  react-icons/fi ─────────────────────────────
        # The LLM loves importing from 'react-icons/all' which doesn't exist in v5.
        # Map common icon families by their prefix, default to /fi (feather icons).
        def fix_react_icons_import(m):
            icons_str = m.group(1)   # e.g. "FaHome, FaCoffee, MdStar"
            icons = [i.strip() for i in icons_str.split(",") if i.strip()]
            # Group by prefix
            groups: dict[str, list] = {}
            for icon in icons:
                prefix = re.match(r'^([A-Z][a-z]+)', icon)
                pkg = "fi"   # default
                if prefix:
                    p = prefix.group(1)
                    pkg = {
                        "Fa": "fa",   "Fa6": "fa6",
                        "Hi": "hi",   "Hi2": "hi2",
                        "Md": "md",   "Io": "io",   "Io5": "io5",
                        "Bs": "bs",   "Ri": "ri",    "Si": "si",
                        "Ti": "ti",   "Ai": "ai",    "Bi": "bi",
                        "Ci": "ci",   "Di": "di",    "Fc": "fc",
                        "Gi": "gi",   "Go": "go",    "Gr": "gr",
                        "Im": "im",   "Lu": "lu",    "Pi": "pi",
                        "Rx": "rx",   "Sl": "sl",    "Tb": "tb",
                        "Tfi": "tfi", "Vsc": "vsc",  "Wi": "wi",
                        "Cg": "cg",   "Fi": "fi",    "Fl": "fa",
                    }.get(p, "fi")
                groups.setdefault(pkg, []).append(icon)
            lines = [f"import {{ {', '.join(v)} }} from 'react-icons/{k}'" for k, v in groups.items()]
            return "\n".join(lines)

        # Match: import { ... } from 'react-icons/all'  (single or double quotes)
        new_code, n = re.subn(
            r"import\s*\{([^}]+)\}\s*from\s*['\"]react-icons/all['\"]",
            fix_react_icons_import,
            code, flags=re.MULTILINE
        )
        if n:
            code = new_code
            changes.append(f"fixed {n} react-icons/all import(s)")

        # ── 1b. Replace hallucinated icon names with real ones ──────────────────
        # LLM invents icon names like FiOval, FiCross that don't exist.
        # Map them to real icons before Vite chokes on the missing export.
        _ICON_REPLACE = {
            "FiOval": "FiCircle", "FiO": "FiCircle", "FiRing": "FiCircle",
            "FiEllipse": "FiCircle", "FiDisc2": "FiDisc", "FiCircleFill": "FiCircle",
            "FiCross": "FiX", "FiXMark": "FiX", "FiTimes": "FiX",
            "FiPlus2": "FiPlus", "FiStar2": "FiStar", "FiHome2": "FiHome",
            "FiMenu2": "FiMenu", "FiArrow": "FiArrowRight", "FiButton": "FiSquare",
            "FiCode2": "FiCode", "FiPhone2": "FiPhone", "FiMail2": "FiMail",
            "FiGamepad": "FiGrid", "FiBoard": "FiGrid", "FiGrid2": "FiGrid",
            "FiRefresh": "FiRefreshCw", "FiReset": "FiRefreshCw",
            "FiMultiply": "FiX", "FiDivide": "FiSlash", "FiMinus": "FiMinus",
            "FiAdd": "FiPlus", "FiSubtract": "FiMinus", "FiCalculator": "FiHash",
            "FiDelete": "FiTrash2", "FiClose": "FiX", "FiCancel": "FiX",
            "FiDots": "FiMoreHorizontal", "FiEllipsis": "FiMoreHorizontal",
            "FiShieldCheck": "FiShield", "FiBuilding": "FiHome",
            "FaOval": "FaCircle", "FaCross": "FaTimes", "FaXMark": "FaTimes",
            "FaGamepad2": "FaGamepad", "FaBoard": "FaTh",
            "HiOval": "HiOutlineCircle", "HiXMark": "HiX",
        }
        for bad_icon, good_icon in _ICON_REPLACE.items():
            if bad_icon in code:
                new_code, n = re.subn(rf'\b{bad_icon}\b', good_icon, code)
                if n > 0:
                    code = new_code
                    changes.append(f"icon {bad_icon}→{good_icon}")

        # ── 1c. Detect "does not provide an export named 'XYZ'" pattern ───────
        # If a Feather icon is used in JSX but omitted from the import, add it.
        # Some Next compilation paths tolerate the missing identifier and fail
        # only when that specific route renders, so fix it before the build.
        fi_import = re.search(
            r"import\s*\{([^}]+)\}\s*from\s*['\"]react-icons/fi['\"]",
            code,
        )
        if fi_import:
            without_imports = re.sub(r"^import[^\n]+$", "", code, flags=re.MULTILINE)
            used_fi = set(re.findall(r"\b(Fi[A-Z]\w*)\b", without_imports))
            imported_fi = set(re.findall(r"\b(Fi[A-Z]\w*)\b", fi_import.group(1)))
            missing_fi = sorted(used_fi - imported_fi)
            if missing_fi:
                replacement = (
                    "import { " + ", ".join(sorted(imported_fi | set(missing_fi)))
                    + " } from 'react-icons/fi'"
                )
                code = code[:fi_import.start()] + replacement + code[fi_import.end():]
                changes.append("added missing Feather icon import(s): " + ", ".join(missing_fi))

        # If the console error tells us exactly which icon name is wrong,
        # strip it from the import line entirely (safer than guessing a replacement).
        # This only runs if the error text was injected via a comment at the top of the file.
        # (The fix loop can prepend: // CONSOLE_ERROR: does not provide ... FiOval)
        console_err_match = re.search(
            r"//\\s*CONSOLE_ERROR:.*?does not provide an export named '(\\w+)'",
            code
        )
        if console_err_match:
            bad_name = console_err_match.group(1)
            if bad_name not in _ICON_REPLACE:
                # Strip the bad icon from any import line
                code = re.sub(rf"\b{re.escape(bad_name)}\s*,?\s*", "", code)
                code = re.sub(r",\s*}", " }", code)  # clean trailing comma
                changes.append(f"removed unknown icon {bad_name} from import")
            # Remove the comment header
            code = re.sub(r"//\s*CONSOLE_ERROR:[^\n]*\n", "", code)

        # ── 1d. Strip imports of packages NOT in our package.json ─────────────
        # The LLM frequently imports react-leaflet, react-router-dom, axios, etc.
        # None of these are installed → Vite crashes with "Failed to resolve import".
        # Auto-remove the import line and replace usage with safe inline fallbacks.
        _BANNED_PACKAGES = [
            "react-leaflet", "leaflet",
            "react-router-dom", "react-router",
            "axios", "lodash", "lodash-es",
            "chart.js", "react-chartjs-2",
            "d3", "d3-scale", "d3-shape",
            "three", "@react-three/fiber", "@react-three/drei",
            "@mui/material", "@mui/icons-material",
            "@chakra-ui/react", "@chakra-ui/icons",
            "react-query", "@tanstack/react-query",
            "zustand", "jotai", "recoil",
            "styled-components", "@emotion/react", "@emotion/styled",
            "classnames", "clsx",
            "react-spring", "@react-spring/web",
            "react-use",
            "react-helmet", "react-helmet-async",
            "react-hot-toast", "sonner",
            "react-toastify",
            "react-dnd", "react-beautiful-dnd",
            "react-virtualized", "react-window",
            "react-table", "@tanstack/react-table",
            "react-hook-form", "formik", "yup",
            "date-fns", "dayjs", "moment",
            "uuid", "nanoid",
            "numeral", "accounting",
        ]
        for pkg in _BANNED_PACKAGES:
            # Match: import ... from 'pkg'  or  import ... from "pkg"
            pkg_pattern = re.compile(
                rf"^import\b[^\n]*from\s+['\"]" + re.escape(pkg) + r"['\"][^\n]*\n?",
                re.MULTILINE
            )
            n_before = len(code)
            code = pkg_pattern.sub("", code)
            if len(code) != n_before:
                changes.append(f"removed banned package import: {pkg}")

        # ── 1e. Replace MapContainer/react-leaflet JSX with a styled placeholder ─
        # Even after removing the import, <MapContainer> tags stay and crash Vite.
        if "MapContainer" in code or "TileLayer" in code or "react-leaflet" in code:
            # Remove any remaining leaflet component usage
            for tag in ["MapContainer", "TileLayer", "Marker", "Popup", "MapView",
                        "LeafletMap", "OpenStreetMap"]:
                code = re.sub(rf"<{tag}[^>]*/?>", "", code)
                code = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", code, flags=re.DOTALL)
            # Replace with a styled map placeholder div
            code = re.sub(
                r"\{/\*\s*map\s*\*/\}",
                '<div className="w-full h-64 bg-gray-800 rounded-xl flex items-center '
                'justify-center text-gray-500 border border-white/10">'
                '<span>📍 Stockholm, Sweden</span></div>',
                code, flags=re.IGNORECASE
            )
            changes.append("replaced react-leaflet map with styled placeholder")

        # ── 2. react-scroll  →  native anchor links ────────────────────────────

        if "react-scroll" in code:
            # Remove the import line entirely
            code = re.sub(r"import\s+.*?from\s+['\"]react-scroll['\"];?\n?", "", code)
            # Replace <Link> scroll component with <a href="#...">
            code = re.sub(
                r'<Link\s+to=["\']([^"\']+)["\'][^>]*activeClass=[^>]*>',
                r'<a href="#\1">',
                code
            )
            code = re.sub(r'<Link\s+to=["\']([^"\']+)["\'][^>]*>', r'<a href="#\1">', code)
            code = re.sub(r'</Link>', r'</a>', code)
            changes.append("removed react-scroll, replaced with anchor links")

        # ── 3. lucide-react  →  react-icons/lu ────────────────────────────────
        # lucide-react is not installed; react-icons includes lucide icons under /lu
        if "lucide-react" in code:
            code = re.sub(
                r"from\s+['\"]lucide-react['\"]",
                "from 'react-icons/lu'",
                code
            )
            # Lucide icons in react-icons/lu are prefixed with Lu
            def prefix_lu_icon(m):
                icons = [i.strip() for i in m.group(1).split(",")]
                prefixed = []
                for icon in icons:
                    if icon and not icon.startswith("Lu"):
                        prefixed.append(f"Lu{icon} as {icon}")
                    elif icon:
                        prefixed.append(icon)
                return f"{{ {', '.join(prefixed)} }}"
            code = re.sub(r'\{([^}]+)\}(?=\s+from\s+[\'"]react-icons/lu)', prefix_lu_icon, code)
            changes.append("remapped lucide-react → react-icons/lu")

        # ── 4. @heroicons/react  →  react-icons/hi ────────────────────────────
        code = re.sub(r"from\s+['\"]@heroicons/react/[^'\"]+['\"]", "from 'react-icons/hi'", code)

        # ── 5. framer-motion AnimatePresence — ensure it's imported ───────────
        if "AnimatePresence" in code and "framer-motion" in code:
            fm_import = re.search(r"import\s*\{([^}]+)\}\s*from\s*['\"]framer-motion['\"]", code)
            if fm_import and "AnimatePresence" not in fm_import.group(1):
                old = fm_import.group(0)
                new = old.replace("{", "{ AnimatePresence, ", 1)
                code = code.replace(old, new, 1)
                changes.append("added AnimatePresence to framer-motion import")

        # ── 6. Unclosed void elements: <br> → <br /> etc ──────────────────────
        # Use a brace-aware and string-aware parser to safely auto-close tags
        # without tripping over arrow functions (=>) or braces ({}).
        def _close_void(txt):
            vtags = {"br","hr","img","input","meta","link","area","base","col","embed","param","source","track","wbr"}
            res, i, n = [], 0, len(txt)
            while i < n:
                # Only lowercase HTML tags are void elements. PascalCase JSX
                # components such as Next.js <Link> are normal paired elements.
                if txt[i] == '<' and i + 1 < n and txt[i+1].islower():
                    m = re.match(r'<([a-zA-Z0-9]+)\b', txt[i:])
                    if m and m.group(1).lower() in vtags:
                        start = i
                        i += len(m.group(0))
                        q, braces = None, 0
                        while i < n:
                            c = txt[i]
                            if q:
                                if c == q: q = None
                            else:
                                if c in '"\'': q = c
                                elif c == '{': braces += 1
                                elif c == '}': braces = max(0, braces - 1)
                                elif c == '>' and braces == 0:
                                    if txt[i-1] != '/': res.append(txt[start:i] + " /")
                                    else: res.append(txt[start:i])
                                    res.append('>')
                                    i += 1
                                    break
                            i += 1
                        else:
                            res.append(txt[start:])
                        continue
                res.append(txt[i])
                i += 1
            return "".join(res)
        
        code = _close_void(code)

        # ── 7. window.scrollTo usage in onClick strings (common mistake) ───────
        # Convert onClick="window.scrollTo..." to onClick={() => window.scrollTo...}
        code = re.sub(
            r'onClick="(window\.[^"]+)"',
            r'onClick={() => \1}',
            code
        )

        # ── 8. className with JS expressions without braces ────────────────────
        code = re.sub(r'className=(`[^`]+`)', r'className={\1}', code)

        # ── 9. Duplicate component declaration ────────────────────────────────
        # LLM sometimes outputs BOTH:
        #   const Gallery = () => { ... }         ← causes "already been declared"
        #   export default function Gallery() {}   ← the correct one
        # Strategy: if both exist, delete every `const Name = ...` line and its
        # immediately following arrow-function body, keeping only the named function.
        component_name = fname.split("/")[-1].replace(".jsx", "").replace(".tsx", "")
        has_const = bool(re.search(rf'\bconst\s+{re.escape(component_name)}\s*=', code))
        has_func  = bool(re.search(rf'\bfunction\s+{re.escape(component_name)}\s*\(', code))
        if has_const and has_func:
            # Remove `const Name = () => { ... }` blocks.
            # We count braces so we don't overshoot into the real function.
            def remove_const_block(src):
                pat = re.compile(
                    rf'\bconst\s+{re.escape(component_name)}\s*=\s*'
                    rf'(?:\([^)]*\)|)\s*=>\s*',
                    re.DOTALL
                )
                m = pat.search(src)
                if not m:
                    return src
                start = m.start()
                pos = m.end()
                # Skip the opening delimiter
                if pos < len(src) and src[pos] == '{':
                    depth, delim = 1, ('{', '}')
                elif pos < len(src) and src[pos] == '(':
                    depth, delim = 1, ('(', ')')
                else:
                    return src   # can't parse — leave alone
                pos += 1
                while pos < len(src) and depth > 0:
                    if src[pos] == delim[0]: depth += 1
                    elif src[pos] == delim[1]: depth -= 1
                    pos += 1
                # Skip optional semicolon and newline
                while pos < len(src) and src[pos] in ';\n\r ':
                    pos += 1
                return src[:start] + src[pos:]

            new_code = remove_const_block(code)
            if new_code != code:
                code = new_code
                changes.append(f"removed duplicate const {component_name} declaration")

        # ── 11 & 12. (removed) Inline-regex / division hoisting ────────────────
        # These transforms hoisted `/regex/` and `{a/b}` out of JSX to work around a
        # BABEL/Vite quirk ("Babel misreads / as a regex start"). locode now builds
        # with Next.js + SWC, whose JSX parser is context-aware and compiles inline
        # regex and division correctly. Worse, the regex-hoister false-positived on
        # ordinary JSX (spans of `{a/b} … {c/d}` matched as one "/…/" literal) and
        # CORRUPTED components into "Unexpected token — Expected jsx identifier"
        # build failures (seen on QuickAdd/CTA across generated apps). Removed: SWC
        # needs no hoisting, and the prompt still nudges the model away from inline
        # regex/division (rules 11/12), so genuine occurrences are rare and valid.

        # ── 10. Self-referential render ────────────────────────────────────────
        # LLM sometimes generates: export default function Menu() { return (<Menu />) }
        # The fix replaces the bad return with a safe fallback section.
        if re.search(rf'\bexport default function\s+{re.escape(component_name)}\b', code):
            selfref = re.search(
                rf'return\s*\(\s*<{re.escape(component_name)}\s*/?>\s*\)',
                code
            )
            if selfref:
                safe = f'return (<section id="{component_name.lower()}" className="py-20 px-6 text-center"><h2 className="text-4xl font-bold text-white mb-4">{component_name}</h2><p className="text-gray-400">Content loading...</p></section>)'
                code = code.replace(selfref.group(0), safe)
                changes.append(f"fixed self-referential render in {component_name}")

        # ── N1. Strip server-only imports from a client component ──────────────
        # A client component must never import mongoose / the db lib / a model —
        # it must talk to the API via fetch. Drop those import lines outright.
        _SERVER_ONLY = re.compile(
            r"^import[^\n]*from\s*['\"](?:mongoose|@/lib/mongodb|@/models/[^'\"]+|next/server)['\"][^\n]*\n?",
            re.MULTILINE,
        )
        new_code = _SERVER_ONLY.sub("", code)
        if new_code != code:
            code = new_code
            changes.append("removed server-only import from client component")

        # ── N2. Absolute localhost fetch → relative API path ───────────────────
        new_code = re.sub(
            r"""(['"`])https?://(?:localhost|127\.0\.0\.1)(?::\d+)?/api/""",
            r"\1/api/", code,
        )
        if new_code != code:
            code = new_code
            changes.append("rewrote absolute localhost fetch to relative /api")

        # ── N3. Ensure 'use client' is the first line if the file is interactive ─
        # (hooks / event handlers / framer-motion require a client component).
        stripped = code.lstrip()
        if not stripped.startswith(("'use client'", '"use client"')):
            if re.search(r"\b(useState|useEffect|useRef|useMemo|useReducer|"
                         r"onClick|onChange|onSubmit|onInput|motion\.|AnimatePresence)\b", code):
                code = "'use client'\n" + code
                changes.append("prepended 'use client'")

        if changes:
            log.info(f"   🔧 sanitize_jsx({fname.split('/')[-1]}): {', '.join(changes)}")

        return code

    def _on_write(self, fname: str, sz: str, content: str):
        """Hook for subclass to emit file events. No-op in base class."""
        pass

    def _install_deps(self) -> bool:
        log.info("   Running npm install...")
        try:
            r = subprocess.run(
                [_npm(), "install"],
                cwd=self.project_dir,
                capture_output=True, text=True, timeout=600,
                env={**os.environ, "CI": "true"}
            )
            if r.returncode == 0:
                log.info("   ✅ npm install complete")
                return True

            log.error("   npm install failed")
            log.error((r.stdout + "\n" + r.stderr)[-1500:])
            return False

        except Exception as e:
            log.error(f"   npm install failed: {e}")
            return False

    # ── Public fix entry point (called by server) ─────────────────────────────

    def fix_with_errors(self, all_error_text: str):
        """
        Called by server with the FULL pre-collected error text.
        Uses this to pinpoint broken files and re-generate them with full context.
        """
        log.info(f"   🔧 fix_with_errors() — {len(all_error_text)} chars of errors")
        log.info(f"   Error preview: {all_error_text[:300]}")

        broken = self._identify_broken(all_error_text)

        if not broken:
            broken = [f for f in self.built_files
                      if f.startswith("components/") and f.endswith((".jsx", ".tsx"))]
            log.info(f"   No specific file ID'd — regenerating all {len(broken)} components")
        else:
            log.info(f"   Targeting: {broken}")

        codebase_ctx = self._build_codebase_context()

        for fpath in broken:
            name    = Path(fpath).stem
            current = self.built_files.get(fpath, "")
            if not current:
                fp = self.project_dir / fpath
                if fp.exists():
                    current = fp.read_text(encoding="utf-8", errors="replace")

            # ── Detect stuck loop: if the file hasn't changed since last fix,
            #    the LLM is regenerating identically → go straight to safe fallback.
            #    Use self._fix_size_cache dict (not setattr) since fpath has slashes.
            if not hasattr(self, '_fix_size_cache'):
                self._fix_size_cache = {}
            prev_size = self._fix_size_cache.get(fpath)
            curr_size = len(current.strip())
            if prev_size is not None and abs(curr_size - prev_size) < 30:
                log.warning(
                    f"   🔁 {name} identical after fix ({curr_size}B ≈ {prev_size}B) "
                    f"— LLM is stuck, writing safe fallback"
                )
                fixed = self.fallback_for(fpath, name)
                self._write_one(fpath, fixed)
                log.info(f"   ✓ {fpath} saved with safe fallback ({len(fixed)}B)")
                self._fix_size_cache.pop(fpath, None)
                continue
            self._fix_size_cache[fpath] = curr_size

            # ── "X is not defined" — try re-extracting from raw LLM output ────
            # This error means the LLM split the component but extraction only kept
            # the thin wrapper. Re-run _extract_valid_component on the FULL raw output
            # (which contains both the helper component and the thin wrapper) to rescue it.
            undef_match = re.search(r"(\w+) is not defined", all_error_text)
            raw_outputs = getattr(self, '_raw_llm_outputs', {})
            if undef_match and name in raw_outputs:
                log.info(f"   🔄 'is not defined' error — re-extracting from raw LLM output")
                raw = raw_outputs[name]
                rescued = self._extract_valid_component(raw, name)
                # Only use rescue if it's substantially bigger than current
                if len(rescued.strip()) > curr_size + 200:
                    log.info(f"   ✅ Rescued from raw output ({len(rescued)}B vs {curr_size}B thin)")
                    self._write_one(fpath, rescued)
                    log.info(f"   ✓ {fpath} saved rescued ({len(rescued)}B)")
                    self._fix_size_cache.pop(fpath, None)
                    continue
                else:
                    log.info(f"   ↩ Raw re-extraction didn't help ({len(rescued)}B) — using LLM fix")

            # ── Annotate the broken file with line numbers for the LLM ────────
            numbered = "\n".join(
                f"{i+1:3} | {l}" for i, l in enumerate(current.splitlines())
            )

            # ── Parse error line number and extract surrounding lines ────
            error_lines_ctx = ""
            # Match `About.tsx: ... (23:35)` OR stack `About.tsx:23:35` (or .jsx legacy)
            line_match = re.search(
                rf"{re.escape(name)}\.(?:jsx|tsx)(?:[^)]*\(|:)(\d+):(\d+)",
                all_error_text
            )
            if line_match:
                err_line = int(line_match.group(1))
                file_lines = current.splitlines()
                start = max(0, err_line - 5)
                end   = min(len(file_lines), err_line + 5)
                ctx_lines = "\n".join(
                    f"{'→ ' if i+1 == err_line else '  '}{i+1:3} | {file_lines[i]}"
                    for i in range(start, end)
                )
                error_lines_ctx = (
                    f"\n═══ BROKEN AT LINE {err_line} ═══\n"
                    f"{ctx_lines}\n"
                    f"The error is on line {err_line}. Fix THAT specific line.\n"
                )

            file_errors = self._filter_errors_for_file(all_error_text, name, fpath)

            # If "X is not defined" and we have the raw original output, pass it as context
            raw_ctx = ""
            undef_m = re.search(r"\w+ is not defined", all_error_text)
            if undef_m:
                raw_outputs = getattr(self, '_raw_llm_outputs', {})
                if name in raw_outputs:
                    raw_ctx = raw_outputs[name]

            log.info(f"   Re-generating {fpath}…")
            fixed = self._fix_component(name, numbered, file_errors + error_lines_ctx, codebase_ctx, raw_ctx)

            if not fixed:
                log.warning(f"   LLM fix failed — using safe fallback for {name}")
                fixed = self.fallback_for(fpath, name)

            self._write_one(fpath, fixed)
            log.info(f"   ✓ {fpath} saved ({len(fixed)}B)")
