"""Config/component prompt helpers and generated component extraction."""
from agents.build.builder_common import *


def _load_scaffold() -> dict:
    """Load editable static files, with a minimal runnable fallback."""
    root = Path(__file__).with_name("scaffold")
    names = (
        "package.json", "vite.config.js", "tailwind.config.js",
        "postcss.config.js", "index.html", "main.jsx", "index.css",
        "Navbar.jsx",
    )
    try:
        files = {
            name: (root / name).read_text(encoding="utf-8")
            for name in names
        }
        if not all(content.strip() for content in files.values()):
            raise ValueError("one or more scaffold assets are empty")
        package = json.loads(files.pop("package.json"))
        if not isinstance(package, dict):
            raise ValueError("scaffold package.json must contain an object")
        return {
            "package": package,
            "config_files": {
                name: files.pop(name) for name in names[1:4]
            },
            "index_html": files["index.html"],
            "main_jsx": files["main.jsx"],
            "index_css": files["index.css"],
            "navbar": files["Navbar.jsx"],
        }
    except (OSError, TypeError, ValueError) as exc:
        log.warning("Builder scaffold unavailable at %s: %s", root, exc)
    return {
        "package": {
            "name": "app", "private": True, "version": "0.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite", "build": "vite build", "preview": "vite preview",
            },
            "dependencies": {
                "react": "^18.2.0", "react-dom": "^18.2.0",
                "framer-motion": "^11.0.0", "react-icons": "^5.0.0",
            },
            "devDependencies": {
                "@vitejs/plugin-react": "^4.2.0", "vite": "^5.0.0",
                "tailwindcss": "^3.4.0", "postcss": "^8.4.0",
                "autoprefixer": "^10.4.0",
            },
        },
        "config_files": {
            "vite.config.js":
                "import { defineConfig } from 'vite'\n"
                "import react from '@vitejs/plugin-react'\n"
                "export default defineConfig({ plugins: [react()] })\n",
            "tailwind.config.js":
                "export default { content: ['./index.html', "
                "'./src/**/*.{js,ts,jsx,tsx}'] }\n",
            "postcss.config.js":
                "export default { plugins: { tailwindcss: {}, "
                "autoprefixer: {} } }\n",
        },
        "index_html": "<div id=\"root\"></div><script type=\"module\" "
                      "src=\"/src/main.jsx\"></script>\n",
        "main_jsx": "import ReactDOM from 'react-dom/client'\n"
                    "import App from './App.jsx'\n"
                    "ReactDOM.createRoot(document.getElementById('root'))"
                    ".render(<App />)\n",
        "index_css": "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n",
        "navbar": "export default function Navbar() { return <nav /> }\n",
    }


SCAFFOLD = _load_scaffold()


class BuilderTemplateMixin:
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
        package = dict(SCAFFOLD["package"])
        package["name"] = name
        files = dict(SCAFFOLD["config_files"])
        return {"package.json": json.dumps(package, indent=2), **files}

    def _index_html(self, title: str) -> str:
        return SCAFFOLD["index_html"].replace("__TITLE__", title)

    def _main_jsx(self) -> str:
        return SCAFFOLD["main_jsx"]

    def _index_css(self, color: str) -> str:
        acc = "#6366f1"; acc2 = "#22d3ee"
        cl  = color.lower()
        if   "red"    in cl or "mario" in cl: acc, acc2 = "#ff4444", "#ff9f43"
        elif "green"  in cl:                  acc, acc2 = "#10b981", "#059669"
        elif "orange" in cl:                  acc, acc2 = "#f59e0b", "#ef4444"
        elif "pink"   in cl:                  acc, acc2 = "#ec4899", "#8b5cf6"
        elif "gold"   in cl or "yellow" in cl: acc, acc2 = "#fbbf24", "#f59e0b"
        elif "purple" in cl:                  acc, acc2 = "#a855f7", "#6366f1"
        return (
            SCAFFOLD["index_css"]
            .replace("__ACCENT__", acc)
            .replace("__ACCENT_2__", acc2)
        )

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
        desktop = "\n".join(self._nav_link(section, False) for section in links)
        mobile = "\n".join(self._nav_link(section, True) for section in links)
        return (SCAFFOLD["navbar"].replace("__TITLE__", title)
                .replace("__DESKTOP_LINKS__", desktop)
                .replace("__MOBILE_LINKS__", mobile))

    @staticmethod
    def _nav_link(section: str, mobile: bool) -> str:
        classes = ("text-gray-300 py-2 border-b border-white/10" if mobile else
                   "text-sm text-gray-400 hover:text-white transition-colors "
                   "uppercase tracking-widest")
        href = section.lower()
        return (
            f'<a href="#{href}" onClick={{smoothScroll}} '
            f'className="{classes}">{section}</a>'
        )

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
