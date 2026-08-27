"""JSX sanitation, dependency installation and terminal-error repair."""
from agents.build.builder_common import *


ICON_FAMILIES = {
    "Fa": "fa", "Fa6": "fa6", "Hi": "hi", "Hi2": "hi2",
    "Md": "md", "Io": "io", "Io5": "io5", "Bs": "bs",
    "Ri": "ri", "Si": "si", "Ti": "ti", "Ai": "ai",
    "Bi": "bi", "Ci": "ci", "Di": "di", "Fc": "fc",
    "Gi": "gi", "Go": "go", "Gr": "gr", "Im": "im",
    "Lu": "lu", "Pi": "pi", "Rx": "rx", "Sl": "sl",
    "Tb": "tb", "Tfi": "tfi", "Vsc": "vsc", "Wi": "wi",
    "Cg": "cg", "Fi": "fi", "Fl": "fa",
}

ICON_REPLACEMENTS = {
    "FiOval": "FiCircle", "FiO": "FiCircle", "FiRing": "FiCircle",
    "FiEllipse": "FiCircle", "FiDisc2": "FiDisc",
    "FiCircleFill": "FiCircle", "FiCross": "FiX", "FiXMark": "FiX",
    "FiTimes": "FiX", "FiPlus2": "FiPlus", "FiStar2": "FiStar",
    "FiHome2": "FiHome", "FiMenu2": "FiMenu",
    "FiArrow": "FiArrowRight", "FiButton": "FiSquare",
    "FiCode2": "FiCode", "FiPhone2": "FiPhone", "FiMail2": "FiMail",
    "FiGamepad": "FiGrid", "FiBoard": "FiGrid", "FiGrid2": "FiGrid",
    "FiRefresh": "FiRefreshCw", "FiReset": "FiRefreshCw",
    "FiMultiply": "FiX", "FiDivide": "FiSlash", "FiMinus": "FiMinus",
    "FiAdd": "FiPlus", "FiSubtract": "FiMinus",
    "FiCalculator": "FiHash", "FiDelete": "FiTrash2",
    "FiClose": "FiX", "FiCancel": "FiX",
    "FiDots": "FiMoreHorizontal", "FiEllipsis": "FiMoreHorizontal",
    "FaOval": "FaCircle", "FaCross": "FaTimes", "FaXMark": "FaTimes",
    "FaGamepad2": "FaGamepad", "FaBoard": "FaTh",
    "HiOval": "HiOutlineCircle", "HiXMark": "HiX",
}

BANNED_PACKAGES = (
    "react-leaflet", "leaflet", "react-router-dom", "react-router",
    "axios", "lodash", "lodash-es", "chart.js", "react-chartjs-2",
    "d3", "d3-scale", "d3-shape", "three", "@react-three/fiber",
    "@react-three/drei", "@mui/material", "@mui/icons-material",
    "@chakra-ui/react", "@chakra-ui/icons", "react-query",
    "@tanstack/react-query", "zustand", "jotai", "recoil",
    "styled-components", "@emotion/react", "@emotion/styled",
    "classnames", "clsx", "react-spring", "@react-spring/web",
    "react-use", "react-helmet", "react-helmet-async", "react-hot-toast",
    "sonner", "react-toastify", "react-dnd", "react-beautiful-dnd",
    "react-virtualized", "react-window", "react-table",
    "@tanstack/react-table", "react-hook-form", "formik", "yup",
    "date-fns", "dayjs", "moment", "uuid", "nanoid", "numeral",
    "accounting",
)

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


def _close_void_tags(text: str) -> str:
    """Self-close HTML void tags without being confused by JSX braces."""
    result, index, size = [], 0, len(text)
    while index < size:
        if text[index] != "<" or index + 1 >= size or not text[index + 1].isalpha():
            result.append(text[index])
            index += 1
            continue
        match = re.match(r"<([a-zA-Z0-9]+)\b", text[index:])
        if not match or match.group(1).lower() not in VOID_TAGS:
            result.append(text[index])
            index += 1
            continue
        start = index
        index += len(match.group(0))
        quote, braces = None, 0
        while index < size:
            char = text[index]
            if quote:
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
            elif char == "{":
                braces += 1
            elif char == "}":
                braces = max(0, braces - 1)
            elif char == ">" and not braces:
                suffix = " /" if text[index - 1] != "/" else ""
                result.extend((text[start:index], suffix, ">"))
                index += 1
                break
            index += 1
        else:
            result.append(text[start:])
        continue
    return "".join(result)


def _remove_duplicate_component(code: str, name: str) -> str:
    """Remove an arrow declaration when a function with the same name exists."""
    pattern = re.compile(
        rf"\bconst\s+{re.escape(name)}\s*=\s*"
        rf"(?:\([^)]*\)|)\s*=>\s*",
        re.DOTALL,
    )
    match = pattern.search(code)
    if not match:
        return code
    start, position = match.start(), match.end()
    if position >= len(code) or code[position] not in "{(":
        return code
    opening = code[position]
    closing = "}" if opening == "{" else ")"
    depth = 1
    position += 1
    while position < len(code) and depth:
        depth += (code[position] == opening) - (code[position] == closing)
        position += 1
    while position < len(code) and code[position] in ";\n\r ":
        position += 1
    return code[:start] + code[position:]


def _safe_return(name: str) -> str:
    """A non-recursive render body used when a component calls itself."""
    return textwrap.dedent(f"""\
        return (
          <section id="{name.lower()}" className="py-20 px-6 text-center">
            <h2 className="text-4xl font-bold text-white mb-4">{name}</h2>
            <p className="text-gray-400">Content loading...</p>
          </section>
        )
        """).strip()


def _hoist_expressions(code: str, pattern, group: int, prefix: str,
                       jsx_attribute: bool = False):
    """Move matched expressions before the first return and expose what moved."""
    lines = code.splitlines(keepends=True)
    import_count = sum(1 for line in lines if re.match(r"^import\s", line.strip()))
    imports = "".join(lines[:import_count])
    body = "".join(lines[import_count:])
    extracted = []

    def replace(match):
        expression = match.group(group).strip()
        name = f"_{prefix}{len(extracted)}"
        extracted.append((name, expression))
        if jsx_attribute:
            return f"{match.group(1)}{name}{match.group(3)}"
        return name

    changed = pattern.sub(replace, body)
    if not extracted:
        return code, []
    declarations = "\n".join(
        f"  const {name} = {expression};" for name, expression in extracted
    )
    injection = f"\n{declarations}\n"
    changed, count = re.subn(
        r"(\n(\s*)return\s*[\(\n])",
        lambda match: injection + match.group(1),
        changed,
        count=1,
    )
    if not count:
        return code, []
    return imports + changed, [expression for _, expression in extracted]


class BuilderSanitizeMixin:
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
                    pkg = ICON_FAMILIES.get(prefix.group(1), "fi")
                groups.setdefault(pkg, []).append(icon)
            lines = [
                f"import {{ {', '.join(icons)} }} from 'react-icons/{family}'"
                for family, icons in groups.items()
            ]
            return "\n".join(lines)

        new_code, n = re.subn(
            r"import\s*\{([^}]+)\}\s*from\s*['\"]react-icons/all['\"]",
            fix_react_icons_import,
            code, flags=re.MULTILINE
        )
        if n:
            code = new_code
            changes.append(f"fixed {n} react-icons/all import(s)")

        for bad_icon, good_icon in ICON_REPLACEMENTS.items():
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
            if bad_name not in ICON_REPLACEMENTS:

                code = re.sub(rf"\b{re.escape(bad_name)}\s*,?\s*", "", code)
                code = re.sub(r",\s*}", " }", code)
                changes.append(f"removed unknown icon {bad_name} from import")

            code = re.sub(r"//\s*CONSOLE_ERROR:[^\n]*\n", "", code)

        for pkg in BANNED_PACKAGES:
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

        code = _close_void_tags(code)

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
            new_code = _remove_duplicate_component(code, component_name)
            if new_code != code:
                code = new_code
                changes.append(f"removed duplicate const {component_name} declaration")

        _JS_REGEX = re.compile(
            r'(?<![</\w])'
            r'(/(?=[^/\n]*[\\^\[\].*+?$|{}])(?:[^/<\\\n]|\\.)+/[gimsuy]*)',
            re.MULTILINE
        )
        code, regexes = _hoist_expressions(code, _JS_REGEX, 1, "re")
        if regexes:
            changes.append(f"hoisted {len(regexes)} regex(es) before return")

        _DIV_ATTR = re.compile(
            r'(=\{)\s*(\d[\d.]*\s*/\s*\d[\d.]*|\w+\s*/\s*\d[\d.]*)\s*(\})'
        )
        code, divisions = _hoist_expressions(
            code,
            _DIV_ATTR,
            2,
            "dv",
            jsx_attribute=True,
        )
        if divisions:
            summary = ", ".join(divisions[:3])
            changes.append(f"hoisted {len(divisions)} JSX division(s): {summary}")

        if re.search(rf'\bexport default function\s+{re.escape(component_name)}\b', code):
            selfref = re.search(
                rf'return\s*\(\s*<{re.escape(component_name)}\s*/?>\s*\)',
                code
            )
            if selfref:
                code = code.replace(selfref.group(0), _safe_return(component_name))
                changes.append(f"fixed self-referential render in {component_name}")

        if changes:
            log.info(f"   🔧 sanitize_jsx({fname.split('/')[-1]}): {', '.join(changes)}")

        return code

    def _on_write(self, fname: str, sz: str, content: str):
        """Hook for subclass to emit file events. No-op in base class."""
        pass

    @staticmethod
    def _entry_missing(pkg_dir) -> str:
        """A declared entry of an installed package that is not on disk."""
        import json as _json
        meta = os.path.join(pkg_dir, "package.json")
        if not os.path.isfile(meta):
            return "package.json"
        try:
            with open(meta, encoding="utf-8") as fh:
                data = _json.load(fh)
        except Exception:                                  # noqa: BLE001
            return ""
        declared = [v for v in (data.get("main"), data.get("module"))
                    if isinstance(v, str) and v.strip()]
        if not declared:
            return ""
        for rel in declared:
            rel = rel.lstrip("./").replace("/", os.sep)
            target = os.path.join(pkg_dir, rel)
            if os.path.isfile(target):
                continue
            if os.path.isdir(target) and os.path.isfile(os.path.join(target, "index.js")):
                continue
            if os.path.isfile(target + ".js"):
                continue
            return rel
        return ""

    def _heal_partial_install(self, npm_cmd) -> bool:
        """
        Check that npm left every declared package whole, and repair it if not.

        npm can exit 0 having written only part of the tree. On Windows it
        aborts a directory it cannot replace -- measured here as
        `ENOTEMPTY: directory not empty, rmdir .../node_modules/next/dist/build/jest`
        while the project's own dev server held the folder open -- and what
        survives is a package directory with its package.json and its small
        files but without the bundle its `main` points at. Every downstream
        signal then says the dependency is fine: it is declared, `npm ls`
        prints the right version, and only the bundler disagrees, with
        `Module not found` against whichever source file imported it. The
        build loop believes that label and rewrites correct source instead.

        Re-running `npm install` does not fix it either: the lockfile already
        records the version, so npm answers "up to date" -- verified for
        `npm install`, `npm install <name>` and `npm install <name> --force`.
        `npm ci` is the one command that removes the tree first.
        """
        import json as _json
        nm = os.path.join(self.project_dir, "node_modules")
        pkg_path = os.path.join(self.project_dir, "package.json")
        if not os.path.isdir(nm) or not os.path.isfile(pkg_path):
            return True
        try:
            with open(pkg_path, encoding="utf-8") as fh:
                pkg = _json.load(fh)
        except Exception:                                  # noqa: BLE001
            return True

        declared = list(pkg.get("dependencies", {})) + list(pkg.get("devDependencies", {}))
        broken = []
        for name in declared:
            missing = self._entry_missing(os.path.join(nm, *name.split("/")))
            if missing:
                broken.append(f"{name} (missing {missing})")
        if not broken:
            return True

        log.warning("   ⚠ npm exited 0 but left %d package(s) incomplete: %s",
                    len(broken), ", ".join(broken[:4]))
        log.info("   📦 repairing the dependency tree with npm ci")
        try:
            r = subprocess.run(
                npm_cmd + ["ci", "--no-audit", "--no-fund"],
                cwd=self.project_dir,
                capture_output=True, text=True, timeout=600,
                env={**os.environ, "CI": "true"},
            )
        except Exception as e:                             # noqa: BLE001
            log.error("   npm ci failed: %s", e)
            return False
        if r.returncode != 0:
            log.error("   npm ci failed")
            log.error((r.stdout + "\n" + r.stderr)[-1200:])
            return False

        still = [n for n in declared
                 if self._entry_missing(os.path.join(nm, *n.split("/")))]
        if still:
            log.error("   npm ci ran but %d package(s) are still incomplete: %s",
                      len(still), ", ".join(still[:4]))
            return False
        log.info("   ✅ dependency tree repaired")
        return True

    def _install_deps(self) -> bool:
        log.info("   Running npm install...")

        npm_cmd = _find_npm_cmd()
        if not npm_cmd:
            log.error("   npm not found (no bundled npm and no system npm).")
            log.error("   If using the desktop app, ensure Electron passes AGENTFORGE_NPM/AGENTFORGE_NODE and vendor/node is bundled.")
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
                return self._heal_partial_install(npm_cmd)

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
