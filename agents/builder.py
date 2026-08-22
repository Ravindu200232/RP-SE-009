import json, logging, os, re, shutil, subprocess, textwrap
from pathlib import Path
import requests

log = logging.getLogger("builder")


def _find_npm_cmd():
    """The npm to shell out to, or None if there is not one.

    `BuilderAgent._install_deps` has always called this and it has never
    existed, so every run through `pipeline.py` — which builds a bare
    `BuilderAgent` rather than the studio's `UIBuilder` subclass — died with
    NameError the moment it reached npm install. The studio path never hit it
    because `UIBuilder._install_deps` overrides the method entirely and uses
    its own resolved `NPM_BIN`.

    The env vars are the ones the packaged Electron app sets, and are named in
    the error message this function's caller prints on failure.
    """
    explicit = os.environ.get("LOCODE_NPM") or os.environ.get("NPM")
    if explicit and Path(explicit).exists():
        return [explicit]
    found = shutil.which("npm")
    return [found] if found else None

_stream_callback = None
def set_stream_callback(fn):
    global _stream_callback
    _stream_callback = fn

def _emit(token):
    if _stream_callback:
        _stream_callback(token)


def _app_shell(title: str, sections: list) -> str:
    """Generate App.jsx that imports and renders all sections. Pure Python string — no fragile escaping."""
    non_navbar = [s for s in sections if s != "Navbar"]
    lines = [
        "import { motion } from 'framer-motion'",
        "import Navbar from './components/Navbar'",
    ]
    for s in non_navbar:
        lines.append(f"import {s} from './components/{s}'")
    lines += [
        "",
        "const fadeUp = { hidden:{opacity:0,y:40}, visible:{opacity:1,y:0,transition:{duration:0.65}} }",
        "",
        "export default function App() {",
        "  return (",
        "    <div className='bg-dark min-h-screen overflow-x-hidden'>",
        "      <Navbar />",
    ]
    for s in non_navbar:
        lines += [
            f"      <motion.div id='{s.lower()}' className='py-20 px-6 max-w-7xl mx-auto'",
            "        initial='hidden' whileInView='visible' viewport={{ once:true, amount:0.08 }} variants={fadeUp}>",
            f"        <{s} />",
            "      </motion.div>",
        ]
    lines += [
        "      <footer className='border-t border-white/10 py-6 text-center text-gray-500 text-sm'>",
        f"        <p>© 2024 {title}</p>",
        "      </footer>",
        "    </div>",
        "  )",
        "}",
    ]
    return "\n".join(lines) + "\n"


def _single_app_shell() -> str:
    return textwrap.dedent("""\
        import AppComponent from './components/App'
        export default function App() {
          return <div className='min-h-screen overflow-x-hidden'><AppComponent /></div>
        }
        """)


SAFE_COMPONENT = textwrap.dedent("""\
    import { motion } from 'framer-motion'
    export default function {name}() {
      return (
        <section id='{id}' className='py-20 px-6'>
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


SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert React + Tailwind developer.
    Output ONLY complete, valid JSX code. No markdown fences, no explanation, no preamble.

    ═══════════════════════════════════════════════════════════
    REFERENCE EXAMPLE — your output must follow this structure EXACTLY:
    ═══════════════════════════════════════════════════════════

    import { useState } from 'react'
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
    """)


class BuilderAgent:
    def __init__(self, ollama_url: str, model: str, project_dir: Path):
        self.url          = f"{ollama_url}/api/chat"
        self.model        = model
        self.project_dir  = Path(project_dir)
        self.built_files: dict[str, str] = {}

    def build(self, refined_prompt: str) -> bool:
        spec = {}
        try: spec = json.loads(refined_prompt)
        except: pass

        title        = spec.get("title", "My App")
        description  = spec.get("description", refined_prompt[:300])
        color        = spec.get("color_scheme", "dark with indigo and cyan accents")
        style        = spec.get("style", "modern")
        features     = spec.get("key_features", spec.get("features", []))
        site_type    = spec.get("site_type", "general")
        strategy     = spec.get("strategy", "react-sections")
        sections     = spec.get("sections", ["Hero", "Features", "About", "Contact"])
        instructions = spec.get("special_instructions", description)

        log.info(f"Strategy: {strategy} | Sections: {sections}")
        _emit(f"Strategy: {strategy} | Sections: {sections}")

        files: dict[str, str] = {}
        files.update(self._config_files(title))
        files["index.html"]    = self._index_html(title)
        files["src/main.jsx"]  = self._main_jsx()
        files["src/index.css"] = self._index_css(color)

        if strategy == "react-app":
            files["src/App.jsx"] = _single_app_shell()
            log.info("   Generating App component...")
            code = self._gen("App", self._app_prompt(title, description, color, style, instructions, features, site_type))
            files["src/components/App.jsx"] = code or _safe_component("App")
        else:
            files["src/App.jsx"] = _app_shell(title, sections)
            log.info("   Generating Navbar...")
            files["src/components/Navbar.jsx"] = (
                self._gen("Navbar", self._navbar_prompt(title, sections))
                or self._fallback_navbar(title, sections)
            )
            for section in [s for s in sections if s != "Navbar"]:
                log.info(f"   Generating {section}...")
                code = self._gen(section, self._section_prompt(
                    section, title, description, color, style, features, site_type, instructions))
                files[f"src/components/{section}.jsx"] = code or _safe_component(section)

        self._write(files)
        return self._install_deps()

    def fix(self, errors: list):
        """
        1. Run `npm run build` to get the real compile error with exact file+line
        2. Parse which file(s) are broken
        3. Re-generate each broken file with full error context + full codebase context
        4. Write fixed files and emit to UI
        """
        log.info(f"   🔧 Starting fix pass ({len(errors)} tester errors)")

        build_errors = self._npm_build_errors()
        log.info(f"   npm build errors:\n{build_errors[:400] if build_errors else '  (none)'}")

        all_error_text = "\n".join(errors) + "\n" + build_errors

        broken = self._identify_broken(all_error_text)
        if not broken:

            broken = [f for f in self.built_files
                      if f.startswith("src/components/") and f.endswith(".jsx")]
            log.info(f"   No specific file found — regenerating all {len(broken)} components")
        else:
            log.info(f"   Broken files: {broken}")

        codebase_ctx = self._build_codebase_context()

        for fpath in broken:
            name = fpath.split("/")[-1].replace(".jsx", "").replace(".tsx", "")
            current = self.built_files.get(fpath, "")
            log.info(f"   Re-generating {fpath}...")

            file_errors = self._filter_errors_for_file(all_error_text, name, fpath)

            fixed = self._fix_component(name, current, file_errors, codebase_ctx)
            if not fixed:
                log.warning(f"   LLM fix failed for {fpath} — using safe fallback")
                fixed = _safe_component(name)

            self._write_one(fpath, fixed)
            log.info(f"   ✓ Saved {fpath} ({len(fixed)}B)")

    def _gen(self, component_name: str, user_prompt: str) -> str:
        """Stream generation, forward tokens to UI, return extracted code."""
        try:
            resp = requests.post(self.url, json={
                "model":   self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                "stream":  True,
                "options": {"temperature": 0.15, "num_predict": 4096},
            }, stream=True, timeout=240)
            resp.raise_for_status()

            _emit(f"\x00START:{component_name}")
            full = ""
            for line in resp.iter_lines():
                if not line: continue
                try:
                    chunk = json.loads(line)
                    tok   = chunk.get("message", {}).get("content", "")
                    if tok:
                        full += tok
                        _emit(tok)
                    if chunk.get("done"): break
                except: continue
            _emit("\x00END")

            if not hasattr(self, '_raw_llm_outputs'):
                self._raw_llm_outputs = {}
            self._raw_llm_outputs[component_name] = full
            return self._extract(full)

        except Exception as e:
            log.error(f"   LLM gen failed ({component_name}): {e}")
            _emit("\x00END")
            return ""

    def _fix_component(self, name: str, broken: str, errors: str, codebase: str, raw_context: str = "") -> str:
        """Ask LLM to fix a component, giving it full error context + full codebase."""

        console_errors = []
        for line in errors.splitlines():
            if "Console error" in line or "PageError" in line or "does not provide" in line:
                console_errors.append(line.strip())

        specific_fixes = []
        for err in console_errors:

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
            resp = requests.post(self.url, json={
                "model":   self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt},
                ],
                "stream":  True,
                "options": {"temperature": 0.05, "num_predict": 4096},
            }, stream=True, timeout=180)
            resp.raise_for_status()

            _emit(f"\x00START:{name} (fix)")
            full = ""
            for line in resp.iter_lines():
                if not line: continue
                try:
                    chunk = json.loads(line)
                    tok   = chunk.get("message", {}).get("content", "")
                    if tok:
                        full += tok
                        _emit(tok)
                    if chunk.get("done"): break
                except: continue
            _emit("\x00END")
            result = self._extract(full)
            return result if "export default" in result else ""
        except Exception as e:
            log.error(f"   fix LLM call failed: {e}")
            _emit("\x00END")
            return ""

    def _npm_build_errors(self) -> str:
        """
        Run `npm run build` (vite build) which exits with real compile errors on stderr.
        Much more reliable than trying to scrape the Vite dev server.
        """
        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=60,
                env={**__import__("os").environ, "CI": "true"}
            )

            output = (result.stdout + "\n" + result.stderr).strip()
            if result.returncode != 0:
                log.info(f"   npm build failed (good — we have the error)")
                return output[:2000]
            log.info("   npm build succeeded — no compile errors!")
            return ""
        except Exception as e:
            log.warning(f"   npm build check failed: {e}")
            return ""

    def _identify_broken(self, error_text: str) -> list:
        """
        Parse error text to find exactly which files are broken.
        Prioritises the file named directly in a Vite compile error over files
        that merely appear in stack traces (which causes innocent files like Navbar
        to be regenerated just because they're listed in the import chain).
        """

        compile_match = re.search(
            r'\[plugin:vite[^\]]*\][^\n]*/src/components/(\w{1,50})\.(?:jsx?|tsx?)',
            error_text, re.IGNORECASE
        )
        if compile_match:
            fpath = f"src/components/{compile_match.group(1)}.jsx"
            log.info(f"   _identify_broken → [{fpath}] (Vite compile error)")
            return self._filter_owned([fpath])

        react_match = re.search(
            r'The above error occurred in the <(\w{1,50})> component',
            error_text, re.IGNORECASE
        )
        if react_match:
            fpath = f"src/components/{react_match.group(1)}.jsx"
            log.info(f"   _identify_broken → [{fpath}] (React runtime error)")
            return self._filter_owned([fpath])

        found = []
        for line in error_text.splitlines():
            if len(line) > 300:
                continue

            if re.search(r'at \w+ \(http', line):
                continue
            for m in re.finditer(
                r'[/\\]src[/\\]components[/\\](\w{1,50})\.(?:jsx?|tsx?)',
                line, re.IGNORECASE
            ):
                fpath = f"src/components/{m.group(1)}.jsx"
                if fpath not in found:
                    found.append(fpath)

        if not found:
            for line in error_text.splitlines():
                if re.search(r'at \w+ \(http', line):
                    continue
                for m in re.finditer(r"components?[/\\](\w{1,50})['\".:]", line):
                    fpath = f"src/components/{m.group(1)}.jsx"
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

        priority = ["src/App.jsx", "src/main.jsx", "src/index.css"]
        all_files = priority + [f for f in sorted(self.built_files) if f not in priority]
        for fname in all_files:
            content = self.built_files.get(fname, "")
            if not content:
                fp = self.project_dir / fname
                if fp.exists():
                    content = fp.read_text(encoding="utf-8", errors="replace")
            if not content:
                continue
            limit = 800 if fname.startswith("src/components/") else 400
            snippet = content[:limit] + (" ...[truncated]" if len(content) > limit else "")
            parts.append(f"── {fname} ──\n{snippet}")
        return "\n\n".join(parts)

    def _extract(self, text: str) -> str:
        """Extract JSX code from LLM output, stripping markdown fences."""
        if not text:
            return ""

        for lang in ["jsx", "tsx", "javascript", "js", "typescript", "ts", ""]:
            m = re.search(rf"```{lang}\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(1).strip()

        t = text.strip()
        if any(k in t for k in ["import ", "export default", "function ", "const ", "return ("]):
            return t
        return ""

    def _config_files(self, title: str) -> dict:
        name = re.sub(r"[^a-z0-9-]", "-", title.lower())[:28].strip("-") or "app"
        pkg = {
            "name": name, "private": True, "version": "0.0.0", "type": "module",
            "scripts": {
                "dev":     "vite",
                "build":   "vite build",
                "preview": "vite preview",
            },
            "dependencies": {
                "react": "^18.2.0", "react-dom": "^18.2.0",
                "framer-motion": "^11.0.0", "react-icons": "^5.0.0",
            },
            "devDependencies": {
                "@vitejs/plugin-react": "^4.2.0",
                "autoprefixer": "^10.4.0",
                "postcss": "^8.4.0",
                "tailwindcss": "^3.4.0",
                "vite": "^5.0.0",
            },
        }
        return {
            "package.json": json.dumps(pkg, indent=2),
            "vite.config.js": textwrap.dedent(f"""\
                import {{ defineConfig }} from 'vite'
                import react from '@vitejs/plugin-react'
                export default defineConfig({{
                  plugins: [react()],
                  server: {{ port: 5173 }},
                }})
                """),
            "tailwind.config.js": textwrap.dedent("""\
                export default {
                  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
                  theme: {
                    extend: {
                      colors: {
                        accent:  '#6366f1',
                        accent2: '#22d3ee',
                        dark:    '#0a0a0f',
                        dark2:   '#12121a',
                        card:    '#1e1e2e',
                      },
                      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
                    },
                  },
                  plugins: [],
                }
                """),
            "postcss.config.js": "export default { plugins: { tailwindcss: {}, autoprefixer: {} } }\n",
        }

    def _index_html(self, title: str) -> str:
        return textwrap.dedent(f"""\
            <!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8" />
              <meta name="viewport" content="width=device-width,initial-scale=1.0" />
              <title>{title}</title>
              <link rel="preconnect" href="https://fonts.googleapis.com" />
              <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
            </head>
            <body>
              <div id="root"></div>
              <script type="module" src="/src/main.jsx"></script>
            </body>
            </html>
            """)

    def _main_jsx(self) -> str:
        return textwrap.dedent("""\
            import React from 'react'
            import ReactDOM from 'react-dom/client'
            import App from './App.jsx'
            import './index.css'

            ReactDOM.createRoot(document.getElementById('root')).render(
              <React.StrictMode>
                <App />
              </React.StrictMode>
            )
            """)

    def _index_css(self, color: str) -> str:
        acc = "#6366f1"; acc2 = "#22d3ee"
        cl  = color.lower()
        if   "red"    in cl or "mario" in cl: acc, acc2 = "#ff4444", "#ff9f43"
        elif "green"  in cl:                  acc, acc2 = "#10b981", "#059669"
        elif "orange" in cl:                  acc, acc2 = "#f59e0b", "#ef4444"
        elif "pink"   in cl:                  acc, acc2 = "#ec4899", "#8b5cf6"
        elif "gold"   in cl or "yellow" in cl: acc, acc2 = "#fbbf24", "#f59e0b"
        elif "purple" in cl:                  acc, acc2 = "#a855f7", "#6366f1"
        return textwrap.dedent(f"""\
            @tailwind base;
            @tailwind components;
            @tailwind utilities;

            @layer base {{
              * {{ scroll-behavior: smooth; box-sizing: border-box; }}
              /* Safety net: ensure body always has a dark bg + visible text.
                 Prevents blank-looking pages when a component forgets to set
                 a background or uses text that blends into the default white. */
              html, body, #root {{
                min-height: 100vh;
                background-color: #0a0a0f;
                color: #e2e8f0;
              }}
              body {{ @apply font-sans; }}
              ::-webkit-scrollbar {{ width: 5px; }}
              ::-webkit-scrollbar-track {{ @apply bg-dark2; }}
              ::-webkit-scrollbar-thumb {{ background: {acc}; border-radius: 99px; }}
            }}
            @layer utilities {{
              .gradient-text {{
                background: linear-gradient(135deg, {acc}, {acc2});
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
              }}
              .glass {{
                backdrop-filter: blur(20px);
                background: rgba(30,30,46,0.55);
                border: 1px solid rgba(255,255,255,0.08);
              }}
              .glow {{ box-shadow: 0 0 30px {acc}33; border: 1px solid {acc}44; }}
            }}
            """)

    def _app_prompt(self, title, description, color, style, instructions, features, site_type):
        return textwrap.dedent(f"""\
            Build a complete, fully functional React single-page {site_type} for:
            Title: {title}
            Style: {style} | Colors: {color}
            Description: {description[:250]}
            Key features: {', '.join(features[:6]) if features else 'standard features for this type'}
            Instructions: {instructions[:250]}

            Requirements:
            - All interactive logic with useState/useEffect
            - Visually stunning, production-quality design
            - Tailwind CSS + framer-motion animations + react-icons
            - Real content — no placeholders
            - Export default function App()

            Output ONLY the JSX starting with imports.
            """)

    def _navbar_prompt(self, title, sections):
        links = [{"label": s, "href": f"#{s.lower()}"} for s in sections if s != "Navbar"]
        return textwrap.dedent(f"""\
            Write a React Navbar component for '{title}'.
            Navigation links: {json.dumps(links)}

            Requirements:
            - Fixed top position, z-index: 50
            - Glassmorphism background that appears on scroll (useEffect + useState)
            - Gradient logo text
            - Smooth scroll to section on link click
            - Mobile hamburger menu (useState)
            - Export default function Navbar()

            Output ONLY the JSX starting with imports.
            """)

    def _section_prompt(self, section, title, description, color, style, features, site_type, instructions):
        return textwrap.dedent(f"""\
            Write a complete React '{section}' section component.
            Website: {title} ({site_type})
            Style: {style} | Colors: {color}
            Description: {description[:180]}
            Instructions: {instructions[:180]}

            Requirements:
            - Production quality, visually stunning
            - framer-motion whileInView animations (initial={{opacity:0,y:30}} → animate={{opacity:1,y:0}})
            - Tailwind CSS — use dark backgrounds, gradients, glass effects
            - Real, specific content matching the website theme (not placeholder text)
            - Fully responsive (mobile-first)
            - Export default function {section}()

            Output ONLY the JSX starting with imports.
            """)

    def _fallback_navbar(self, title: str, sections: list) -> str:
        links = [s for s in sections if s != "Navbar"]
        items = "\n          ".join(
            f'<a href="#{s.lower()}" onClick={{smoothScroll}} className="text-sm text-gray-400 hover:text-white transition-colors uppercase tracking-widest">{s}</a>'
            for s in links
        )
        return textwrap.dedent(f"""\
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

    def _write(self, files: dict):
        for fname, content in files.items():
            self._write_one(fname, content)

    def _write_one(self, fname: str, content: str):
        is_component = (
            fname.startswith("src/components/")
            and fname.endswith((".jsx", ".tsx"))
            and "import" in content
        )
        if is_component:
            component_name = Path(fname).stem

            content = self._extract_valid_component(content, component_name)

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

        code = re.sub(r"```[a-z]*", "", code).replace("```", "").strip()

        lines = code.splitlines()

        imports = []
        seen = set()
        for line in lines:
            s = line.strip()
            if re.match(r"^import\s", s) and s not in seen:
                imports.append(s)
                seen.add(s)

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

        def brace_extract(src: str, start_pos: int):
            bp = src.find("{", start_pos)
            if bp == -1:
                return None, -1
            depth = 0; pos = bp
            while pos < len(src):
                if src[pos] == "{": depth += 1
                elif src[pos] == "}": depth -= 1
                if depth == 0: break
                pos += 1
            return src[start_pos: pos + 1].strip(), pos

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

            if hm.start() == export_start:
                continue
            block, end_pos = brace_extract(code, hm.start())
            if block and len(block) > 30:
                helpers_code.append((fn_name, block))
                seen_helpers.add(fn_name)

        func_body, _ = brace_extract(code, export_start)
        if not func_body:
            log.warning(f"   _extract: no opening brace in {component_name} -> safe fallback")
            return _safe_component(component_name)

        func_lines = func_body.splitlines()
        if func_lines:
            indent = len(func_lines[0]) - len(func_lines[0].lstrip())
            if indent > 0:
                func_lines = [fl[indent:] if fl.startswith(" " * indent) else fl for fl in func_lines]
            func_body = "\n".join(func_lines)

        used_helpers = [
            (name, block) for name, block in helpers_code
            if (f"<{name}" in func_body or f"<{name}/" in func_body
                or f"{{{name}" in func_body)
        ]
        if used_helpers:
            log.info(f"   _extract: including helper(s): {[n for n,_ in used_helpers]}")

        if not used_helpers and len(func_body) < 350 and helpers_code:

            for name, block in helpers_code:
                if name in func_body:
                    used_helpers = [(name, block)]
                    log.info(f"   _extract: loose-match helper '{name}' included")
                    break

        if not used_helpers and len(func_body) < 350 and helpers_code:
            largest = max(helpers_code, key=lambda x: len(x[1]))
            log.warning(
                f"   _extract: thin wrapper ({len(func_body)}B) — adopting "
                f"'{largest[0]}' as main component"
            )
            adopted = largest[1]

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

        parts = ["\n".join(imports), ""]
        for _, block in used_helpers:
            parts.append(block)
            parts.append("")
        parts.append(func_body)
        result = "\n".join(parts) + "\n"

        if abs(result.count("{") - result.count("}")) > 4:
            log.warning(f"   _extract: unbalanced braces in {component_name} -> safe fallback")
            return _safe_component(component_name)

        log.info(f"   _extract: OK {component_name} ({len(imports)} imports, {len(result)}B)")
        return result

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
        changes = []

        def fix_react_icons_import(m):
            icons_str = m.group(1)
            icons = [i.strip() for i in icons_str.split(",") if i.strip()]

            groups: dict[str, list] = {}
            for icon in icons:
                prefix = re.match(r'^([A-Z][a-z]+)', icon)
                pkg = "fi"
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

        new_code, n = re.subn(
            r"import\s*\{([^}]+)\}\s*from\s*['\"]react-icons/all['\"]",
            fix_react_icons_import,
            code, flags=re.MULTILINE
        )
        if n:
            code = new_code
            changes.append(f"fixed {n} react-icons/all import(s)")

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

        console_err_match = re.search(
            r"//\\s*CONSOLE_ERROR:.*?does not provide an export named '(\\w+)'",
            code
        )
        if console_err_match:
            bad_name = console_err_match.group(1)
            if bad_name not in _ICON_REPLACE:

                code = re.sub(rf"\b{re.escape(bad_name)}\s*,?\s*", "", code)
                code = re.sub(r",\s*}", " }", code)
                changes.append(f"removed unknown icon {bad_name} from import")

            code = re.sub(r"//\s*CONSOLE_ERROR:[^\n]*\n", "", code)

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

            pkg_pattern = re.compile(
                rf"^import\b[^\n]*from\s+['\"]" + re.escape(pkg) + r"['\"][^\n]*\n?",
                re.MULTILINE
            )
            n_before = len(code)
            code = pkg_pattern.sub("", code)
            if len(code) != n_before:
                changes.append(f"removed banned package import: {pkg}")

        if "MapContainer" in code or "TileLayer" in code or "react-leaflet" in code:

            for tag in ["MapContainer", "TileLayer", "Marker", "Popup", "MapView",
                        "LeafletMap", "OpenStreetMap"]:
                code = re.sub(rf"<{tag}[^>]*/?>", "", code)
                code = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", code, flags=re.DOTALL)

            code = re.sub(
                r"\{/\*\s*map\s*\*/\}",
                '<div className="w-full h-64 bg-gray-800 rounded-xl flex items-center '
                'justify-center text-gray-500 border border-white/10">'
                '<span>📍 Stockholm, Sweden</span></div>',
                code, flags=re.IGNORECASE
            )
            changes.append("replaced react-leaflet map with styled placeholder")

        if "react-scroll" in code:

            code = re.sub(r"import\s+.*?from\s+['\"]react-scroll['\"];?\n?", "", code)

            code = re.sub(
                r'<Link\s+to=["\']([^"\']+)["\'][^>]*activeClass=[^>]*>',
                r'<a href="#\1">',
                code
            )
            code = re.sub(r'<Link\s+to=["\']([^"\']+)["\'][^>]*>', r'<a href="#\1">', code)
            code = re.sub(r'</Link>', r'</a>', code)
            changes.append("removed react-scroll, replaced with anchor links")

        if "lucide-react" in code:
            code = re.sub(
                r"from\s+['\"]lucide-react['\"]",
                "from 'react-icons/lu'",
                code
            )

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

        code = re.sub(r"from\s+['\"]@heroicons/react/[^'\"]+['\"]", "from 'react-icons/hi'", code)

        if "AnimatePresence" in code and "framer-motion" in code:
            fm_import = re.search(r"import\s*\{([^}]+)\}\s*from\s*['\"]framer-motion['\"]", code)
            if fm_import and "AnimatePresence" not in fm_import.group(1):
                old = fm_import.group(0)
                new = old.replace("{", "{ AnimatePresence, ", 1)
                code = code.replace(old, new, 1)
                changes.append("added AnimatePresence to framer-motion import")

        def _close_void(txt):
            vtags = {"br","hr","img","input","meta","link","area","base","col","embed","param","source","track","wbr"}
            res, i, n = [], 0, len(txt)
            while i < n:
                if txt[i] == '<' and i + 1 < n and txt[i+1].isalpha():
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

        code = re.sub(
            r'onClick="(window\.[^"]+)"',
            r'onClick={() => \1}',
            code
        )

        code = re.sub(r'className=(`[^`]+`)', r'className={\1}', code)

        component_name = fname.split("/")[-1].replace(".jsx", "").replace(".tsx", "")
        has_const = bool(re.search(rf'\bconst\s+{re.escape(component_name)}\s*=', code))
        has_func  = bool(re.search(rf'\bfunction\s+{re.escape(component_name)}\s*\(', code))
        if has_const and has_func:

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

                if pos < len(src) and src[pos] == '{':
                    depth, delim = 1, ('{', '}')
                elif pos < len(src) and src[pos] == '(':
                    depth, delim = 1, ('(', ')')
                else:
                    return src
                pos += 1
                while pos < len(src) and depth > 0:
                    if src[pos] == delim[0]: depth += 1
                    elif src[pos] == delim[1]: depth -= 1
                    pos += 1

                while pos < len(src) and src[pos] in ';\n\r ':
                    pos += 1
                return src[:start] + src[pos:]

            new_code = remove_const_block(code)
            if new_code != code:
                code = new_code
                changes.append(f"removed duplicate const {component_name} declaration")

        _JS_REGEX = re.compile(
            r'(?<![</\w])'
            r'(/(?=[^/\n]*[\\^\[\].*+?$|{}])(?:[^/<\\\n]|\\.)+/[gimsuy]*)',
            re.MULTILINE
        )
        _re_lines = code.splitlines(keepends=True)
        _re_imp_end = sum(1 for l in _re_lines if re.match(r"^import\s", l.strip()))
        _re_imp_block = "".join(_re_lines[:_re_imp_end])
        _re_rest = "".join(_re_lines[_re_imp_end:])

        if _JS_REGEX.search(_re_rest):
            _re_extracted = []
            def _hoist_re(m):
                regex_str = m.group(1)
                _name = f"_re{len(_re_extracted)}"
                _re_extracted.append(f"  const {_name} = {regex_str};")
                return _name
            new_re_rest = _JS_REGEX.sub(_hoist_re, _re_rest)
            if _re_extracted:
                inject = "\n" + "\n".join(_re_extracted) + "\n"
                new_re_rest = re.sub(
                    r'(\n(\s*)return\s*[\(\n])',
                    lambda m, _inj=inject: _inj + m.group(1),
                    new_re_rest, count=1
                )
                code = _re_imp_block + new_re_rest
                changes.append(f"hoisted {len(_re_extracted)} regex(es) before return")

        _DIV_ATTR = re.compile(
            r'(=\{)\s*(\d[\d.]*\s*/\s*\d[\d.]*|\w+\s*/\s*\d[\d.]*)\s*(\})'
        )
        _div_extracted = []
        _div_changes = []
        def _hoist_div(m):
            full_expr = m.group(2).strip()
            _name = f"_dv{len(_div_extracted)}"
            _div_extracted.append(f"  const {_name} = {full_expr};")
            _div_changes.append(f"{full_expr} → {_name}")
            return f"{m.group(1)}{_name}{m.group(3)}"

        _dv_lines = code.splitlines(keepends=True)
        _dv_imp_end = sum(1 for l in _dv_lines if re.match(r"^import\s", l.strip()))
        _dv_imp_block = "".join(_dv_lines[:_dv_imp_end])
        _dv_rest = "".join(_dv_lines[_dv_imp_end:])
        new_dv_rest = _DIV_ATTR.sub(_hoist_div, _dv_rest)
        if _div_extracted:
            inject2 = "\n" + "\n".join(_div_extracted) + "\n"
            new_dv_rest = re.sub(
                r'(\n(\s*)return\s*[\(\n])',
                lambda m, _inj=inject2: _inj + m.group(1),
                new_dv_rest, count=1
            )
            code = _dv_imp_block + new_dv_rest
            changes.append(f"hoisted {len(_div_extracted)} JSX division(s): {', '.join(_div_changes[:3])}")

        if re.search(rf'\bexport default function\s+{re.escape(component_name)}\b', code):
            selfref = re.search(
                rf'return\s*\(\s*<{re.escape(component_name)}\s*/?>\s*\)',
                code
            )
            if selfref:
                safe = f'return (<section id="{component_name.lower()}" className="py-20 px-6 text-center"><h2 className="text-4xl font-bold text-white mb-4">{component_name}</h2><p className="text-gray-400">Content loading...</p></section>)'
                code = code.replace(selfref.group(0), safe)
                changes.append(f"fixed self-referential render in {component_name}")

        if changes:
            log.info(f"   🔧 sanitize_jsx({fname.split('/')[-1]}): {', '.join(changes)}")

        return code

    def _on_write(self, fname: str, sz: str, content: str):
        """Hook for subclass to emit file events. No-op in base class."""
        pass

    def _install_deps(self) -> bool:
        log.info("   Running npm install...")

        npm_cmd = _find_npm_cmd()
        if not npm_cmd:
            log.error("   npm not found (no bundled npm and no system npm).")
            log.error("   If using the DMG, ensure Electron passes LOCODE_NPM/LOCODE_NODE and vendor/node is bundled.")
            return False
        try:
            r = subprocess.run(
                npm_cmd + ["install"],
                cwd=self.project_dir,
                capture_output=True, text=True, timeout=300,
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
                      if f.startswith("src/components/") and f.endswith(".jsx")]
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

            if not hasattr(self, '_fix_size_cache'):
                self._fix_size_cache = {}
            prev_size = self._fix_size_cache.get(fpath)
            curr_size = len(current.strip())
            if prev_size is not None and abs(curr_size - prev_size) < 30:
                log.warning(
                    f"   🔁 {name} identical after fix ({curr_size}B ≈ {prev_size}B) "
                    f"— LLM is stuck, writing safe fallback"
                )
                fixed = _safe_component(name)
                self._write_one(fpath, fixed)
                log.info(f"   ✓ {fpath} saved with safe fallback ({len(fixed)}B)")
                self._fix_size_cache.pop(fpath, None)
                continue
            self._fix_size_cache[fpath] = curr_size

            undef_match = re.search(r"(\w+) is not defined", all_error_text)
            raw_outputs = getattr(self, '_raw_llm_outputs', {})
            if undef_match and name in raw_outputs:
                log.info(f"   🔄 'is not defined' error — re-extracting from raw LLM output")
                raw = raw_outputs[name]
                rescued = self._extract_valid_component(raw, name)

                if len(rescued.strip()) > curr_size + 200:
                    log.info(f"   ✅ Rescued from raw output ({len(rescued)}B vs {curr_size}B thin)")
                    self._write_one(fpath, rescued)
                    log.info(f"   ✓ {fpath} saved rescued ({len(rescued)}B)")
                    self._fix_size_cache.pop(fpath, None)
                    continue
                else:
                    log.info(f"   ↩ Raw re-extraction didn't help ({len(rescued)}B) — using LLM fix")

            numbered = "\n".join(
                f"{i+1:3} | {l}" for i, l in enumerate(current.splitlines())
            )

            error_lines_ctx = ""

            line_match = re.search(
                rf"{re.escape(name)}\.jsx(?:[^)]*\(|:)(\d+):(\d+)",
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
                fixed = _safe_component(name)

            self._write_one(fpath, fixed)
            log.info(f"   ✓ {fpath} saved ({len(fixed)}B)")