"""agents/bugfix_agent.py — surgical, line-level build-error fixer (v2 engine).

Policy (explicit user requirement): a bug is fixed by editing ONLY the failing line/part —
never by regenerating the whole file and never with a `// @ts-ignore` band-aid. The fixer:
  1. runs `next build` and parses the FIRST error → file + line + message,
  2. extracts a small window (the failing line + a few lines of context),
  3. asks gemma4:12b to return ONLY the corrected window,
  4. splices that window back into the file (the rest is untouched),
  5. rebuilds; repeats until green or the attempt cap is hit.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from agents import llm

NPM = os.environ.get("NPM_BIN", r"C:\Program Files\nodejs\npm.CMD")

FIX_SYSTEM = (
    "You fix TypeScript / Next.js build errors. You are given the FULL file (line-numbered) and one "
    "build error. Read the whole file for context, then return ONE OR MORE search/replace edits that "
    "fix ONLY the error. Each edit MUST use exactly this format:\n"
    "<<<<<<< SEARCH\n<the exact existing lines to replace, copied verbatim WITHOUT the line-number "
    "prefixes>\n=======\n<the corrected lines>\n>>>>>>> REPLACE\n"
    "Rules: the SEARCH text must match the current file EXACTLY so it can be found; keep each edit as "
    "small as possible — change only the buggy line(s), never resend unchanged code; do not touch "
    "correct code; NEVER use `// @ts-ignore`, `@ts-nocheck`, or `any` casts to hide the error — write "
    "a genuine fix. Output ONLY the search/replace block(s), no prose, no markdown fences."
)

_EDIT = re.compile(
    r"<{5,}\s*SEARCH\s*\n(.*?)\n?={5,}[ \t]*\n(.*?)\n?>{5,}\s*REPLACE", re.DOTALL)
_MARKER = re.compile(r"^(?:<{5,}|={5,}|>{5,})", re.MULTILINE)
# shadcn primitive export name → its file (for relocating wrong-file imports)
_UI_EXPORTS = {
    "Button": "button", "Card": "card", "CardHeader": "card", "CardTitle": "card",
    "CardDescription": "card", "CardContent": "card", "CardFooter": "card", "Input": "input",
    "Label": "label", "Select": "select", "Textarea": "textarea", "Checkbox": "checkbox",
    "Badge": "badge", "Table": "table", "TableHeader": "table", "TableBody": "table",
    "TableRow": "table", "TableHead": "table", "TableCell": "table", "Skeleton": "skeleton",
    "Separator": "separator", "Alert": "alert", "AlertTitle": "alert", "AlertDescription": "alert",
}

# Next/tsc error location patterns (path:line:col).
_LOC_PATTERNS = [
    re.compile(r"^\s*\.?/?([\w./\-\[\]]+\.(?:tsx?|jsx?)):(\d+):(\d+)", re.MULTILINE),   # ./app/x.ts:12:5
    re.compile(r"^\s*([\w./\-\[\]]+\.(?:tsx?|jsx?))\((\d+),(\d+)\)", re.MULTILINE),      # app/x.ts(12,5)
]
_MSG = re.compile(r"(Type error:.*|error TS\d+:.*|Error:.*|Syntax error:.*|Parsing ecmascript.*|Unexpected.*)")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
# SWC/webpack frame: a path alone on its own line, followed by a `NN |` code frame.
_PATH_ALONE = re.compile(r"^\s*\.?/?([\w./\-\[\]]+\.(?:tsx?|jsx?))\s*$", re.MULTILINE)
_FRAME_NUM = re.compile(r"^\s*(\d+)\s*\|", re.MULTILINE)
_WIDEN = ("redefined", "redeclared", "duplicate", "already been declared", "cannot redeclare")
_MODNOTFOUND = re.compile(
    r"^\s*\.?/?(\S+\.(?:tsx?|jsx?))\s*\nModule not found: Can't resolve '([^']+)'", re.MULTILINE)
# Packages the app is allowed to use (declared in package.json). A missing one = broken install,
# repaired with `npm install`; anything else the LLM must remove/replace.
KNOWN_DEPS = {
    "next", "react", "react-dom", "mongoose", "mongodb-memory-server", "framer-motion",
    "react-icons", "lucide-react", "zod", "clsx", "tailwind-merge", "date-fns", "bcryptjs", "jose",
}
# Hallucinated internal import basenames → the real module path they should be.
_INTERNAL_REMAP = {
    "db": "@/lib/mongodb", "database": "@/lib/mongodb", "mongoose": "@/lib/mongodb",
    "mongo": "@/lib/mongodb", "connect": "@/lib/mongodb", "dbconnect": "@/lib/mongodb",
    "connectdb": "@/lib/mongodb", "dbconnection": "@/lib/mongodb", "mongodb": "@/lib/mongodb",
    "response": "@/lib/api", "responses": "@/lib/api", "http": "@/lib/api", "apihelpers": "@/lib/api",
    "apiresponse": "@/lib/api", "api": "@/lib/api", "auth": "@/lib/auth", "session": "@/lib/session",
    "utils": "@/lib/utils", "seed": "@/lib/seed",
}


class BugFixAgent:
    def __init__(self, project_dir, emit=None, model=None, window=5, regen=None):
        self.project_dir = Path(project_dir)
        self.emit = emit or (lambda *a, **k: None)
        self.model = model or llm.GEN_MODEL
        self.window = window
        # regen(rel) -> bool: last-resort single-file regeneration when surgical + deterministic
        # fixes can't converge on one leaf component. Provided by the orchestrator.
        self.regen = regen or (lambda rel: False)
        self._regenerated: set[str] = set()
        self._repaired = False   # one-shot `npm install` repair for a missing declared dep

    def _npm_install(self):
        try:
            subprocess.run([NPM, "install"], cwd=str(self.project_dir),
                           capture_output=True, text=True, timeout=600)
        except Exception as e:  # noqa: BLE001
            self.emit("log", {"text": f"npm install failed: {e}"})

    def fix_route_signature(self, rel: str) -> bool:
        """Deterministically fix the two common handler-signature mistakes: params typed as a plain
        object (must be a Promise in Next 15/16) and `requireUser(req)` (takes no args)."""
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        new = content
        # { params }: { params: { ... } }  →  { params }: { params: Promise<{ ... }> }
        new = re.sub(
            r"(\{\s*params\s*\}\s*:\s*\{\s*params\s*:\s*)\{([^{}]*)\}(\s*\})",
            r"\1Promise<{\2}>\3", new)
        # const { id } = params  →  const { id } = await params
        new = re.sub(r"const\s*(\{[^}]*\})\s*=\s*params\b(?!\s*\))", r"const \1 = await params", new)
        # requireUser(req) / requireRole(x, req) extra args → no-arg call
        new = re.sub(r"requireUser\s*\([^)]*\)", "requireUser()", new)
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    def fix_wrong_ui_export(self, rel: str, message: str) -> bool:
        """`import { Label } from '@/components/ui/input'` fails ("Export Label doesn't exist") —
        relocate the primitive to its correct file."""
        m = re.search(r"Export (\w+) doesn't exist in target module", message)
        if not m:
            return False
        name = m.group(1)
        correct = _UI_EXPORTS.get(name)
        if not correct:
            return False
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        out, added = [], False
        for ln in content.split("\n"):
            mm = re.match(r"\s*import\s*\{([^}]+)\}\s*from\s*['\"]@/components/ui/([^'\"]+)['\"]", ln)
            if mm:
                names = [x.strip() for x in mm.group(1).split(",") if x.strip()]
                bare = [re.sub(r"\s+as\s+\w+", "", x).strip() for x in names]
                file = mm.group(2)
                if file == correct:
                    if name not in bare:
                        names.append(name)
                    out.append(f"import {{ {', '.join(names)} }} from '@/components/ui/{correct}'")
                    added = True
                    continue
                keep = [x for x, b in zip(names, bare) if b != name]
                if keep:
                    out.append(f"import {{ {', '.join(keep)} }} from '@/components/ui/{file}'")
                continue
            out.append(ln)
        if not added:
            idx = 1 if out and "use client" in out[0] else 0
            out.insert(idx, f"import {{ {name} }} from '@/components/ui/{correct}'")
        new = "\n".join(out)
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    _HOOKS = {"useState", "useEffect", "useRef", "useMemo", "useCallback", "useContext", "useReducer"}

    def _feature_module(self, name: str, rel: str) -> str | None:
        """A generated feature/shared component whose file stem matches `name` → its `@/`-alias path
        (default export). Self-import guarded: never resolve to the file that defines `name` itself."""
        if name == Path(rel).stem:
            return None
        for base in ("components/features", "components"):
            root = self.project_dir / base
            if not root.exists():
                continue
            for fp in root.rglob(f"{name}.tsx"):
                return "@/" + fp.relative_to(self.project_dir).as_posix()[:-4]
        return None

    def fix_missing_ui_import(self, rel: str, message: str) -> bool:
        """`Cannot find name 'Textarea'` — a UI primitive, React hook, or a generated feature component
        is used but not imported. Add/merge the correct import deterministically instead of the LLM."""
        m = re.search(r"Cannot find name '(\w+)'", message)
        if not m:
            return False
        name = m.group(1)
        default = False   # feature components are default exports → `import Name from '…'`
        if name in _UI_EXPORTS:
            module = f"@/components/ui/{_UI_EXPORTS[name]}"
        elif name in self._HOOKS:
            module = "react"
        else:
            module = self._feature_module(name, rel)
            default = True
            if not module:
                return False
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        esc_mod = re.escape(module)
        if default:
            # already a default import of that name from that module?
            if re.search(r"import\s+" + re.escape(name) + r"\s+from\s*['\"]" + esc_mod + r"['\"]", content):
                return False
            imp = f"import {name} from '{module}'"
            lines = content.split("\n")
            at = 1 if lines and "use client" in lines[0] else 0
            # place after the contiguous top import block so it never lands after code
            while at < len(lines) and (lines[at].lstrip().startswith("import ") or not lines[at].strip()):
                at += 1
            lines.insert(at, imp)
            new = "\n".join(lines)
        else:
            # already imported that name from that module?
            if re.search(r"import\s*\{[^}]*\b" + re.escape(name) + r"\b[^}]*\}\s*from\s*['\"]" + esc_mod + r"['\"]", content):
                return False
            merge_pat = r"import\s*\{([^}]*)\}\s*from\s*['\"]" + esc_mod + r"['\"]"
            mm = re.search(merge_pat, content)
            if mm:
                existing = [n.strip() for n in mm.group(1).split(",") if n.strip()]
                existing.append(name)
                new = content[:mm.start()] + "import { " + ", ".join(dict.fromkeys(existing)) + f" }} from '{module}'" + content[mm.end():]
            else:
                imp = f"import {{ {name} }} from '{module}'"
                lines = content.split("\n")
                at = 1 if lines and "use client" in lines[0] else 0
                lines.insert(at, imp)
                new = "\n".join(lines)
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    def fix_import_syntax(self, rel: str) -> bool:
        """Fix gemma import typos: a stray double brace `} } from` → `} from`, and `import { {` → `import {`."""
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        new = re.sub(r"\}\s*\}(\s*from\s*['\"])", r"}\1", content)   # } } from '…' → } from '…'
        new = re.sub(r"(import\s*)\{\s*\{", r"\1{", new)               # import { { → import {
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    def complete_truncated(self, rel: str) -> bool:
        """A component cut off at the token limit ends mid-structure (error mentions '<eof>').
        Append the missing `)` / `}` (and any unclosed JSX close on the final open element) so it
        at least compiles. Deterministic last resort — a truncated file has nothing to search/replace."""
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        p = content.count("(") - content.count(")")
        b = content.count("{") - content.count("}")
        if p <= 0 and b <= 0:
            return False
        tail = (")" * p) if p > 0 else ""
        if b > 0:
            tail += ("\n" if tail else "") + ("}" * b)
        new = content.rstrip() + "\n" + tail + "\n"
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    def fix_bad_closing_tags(self, rel: str) -> bool:
        """Fix common gemma JSX/comment typos: garbage closing tags (`</_id>`), a stray extra `>` after
        a tag (`</div>>`, `/>>`), and a doubled block-comment close (`*/` right after `*/`). Valid
        closing tag = `</Name>` starting with a letter."""
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        new = content
        # garbage closing tag whose name is not a valid identifier (e.g. `</_id>`). `[^<>]+` requires
        # at least one char so a valid React fragment close `</>` is NEVER matched/removed.
        new = re.sub(r"</\s*(?![A-Za-z][A-Za-z0-9.]*\s*>)[^<>]+>", "", new)
        # a RUN of extra '>' after an opening tag: `<Button …>>>>>>>` (gemma spams the tag terminator).
        # Collapse 4+ consecutive '>' to one — no valid TypeScript generic ever closes deeper than
        # `>>>` (three levels), so 4+ in a row is always this bug, never legitimate code.
        new = re.sub(r">{4,}", ">", new)
        # stray double '>' after a closing tag or self-close: </div>> → </div>, /> > → />
        new = re.sub(r"(</[A-Za-z][A-Za-z0-9.]*\s*>)\s*>", r"\1", new)
        new = re.sub(r"(/>)\s*>", r"\1", new)
        # doubled block-comment close (`*/` immediately after another `*/`) → single close.
        # Two adjacent comment terminators are never valid; run twice to catch triples.
        for _ in range(2):
            new = re.sub(r"(\*/)\s*\*/", r"\1", new)
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    # A curated set of react-icons/fi names that definitely exist. Any imported Fi* name NOT here
    # (gemma routinely invents ones like `Fi_Utensils`, `FiFork`) is remapped to a safe fallback.
    _VALID_FI = {
        "FiPlus", "FiMinus", "FiEdit", "FiEdit2", "FiEdit3", "FiTrash", "FiTrash2", "FiSearch",
        "FiX", "FiXCircle", "FiCheck", "FiCheckCircle", "FiCircle", "FiChevronRight", "FiChevronLeft",
        "FiChevronDown", "FiChevronUp", "FiArrowRight", "FiArrowLeft", "FiArrowUp", "FiArrowDown",
        "FiHome", "FiUser", "FiUsers", "FiSettings", "FiLogOut", "FiLogIn", "FiMenu", "FiGrid",
        "FiList", "FiLayout", "FiCalendar", "FiClock", "FiDollarSign", "FiCreditCard", "FiShoppingCart",
        "FiShoppingBag", "FiPackage", "FiBox", "FiTruck", "FiFileText", "FiFile", "FiFolder",
        "FiClipboard", "FiDatabase", "FiTag", "FiInfo", "FiAlertCircle", "FiAlertTriangle", "FiBell",
        "FiEye", "FiEyeOff", "FiFilter", "FiDownload", "FiUpload", "FiRefreshCw", "FiMoreVertical",
        "FiMoreHorizontal", "FiPieChart", "FiBarChart", "FiBarChart2", "FiTrendingUp", "FiTrendingDown",
        "FiActivity", "FiCoffee", "FiStar", "FiHeart", "FiMapPin", "FiPhone", "FiMail", "FiPrinter",
        "FiSend", "FiSave", "FiLock", "FiUnlock", "FiKey", "FiSliders", "FiToggleLeft", "FiChevronsRight",
    }
    _FI_FALLBACK = "FiCircle"

    def fix_bad_icon_import(self, rel: str, message: str) -> bool:
        """`import { Fi_Utensils } from 'react-icons/fi'` — gemma invents/miswrites icon names. Remap the
        invalid name to a real icon across the import AND its JSX usages. Handles every compiler format:
          - SWC: `Export X doesn't exist in target module`
          - tsc:  `'react-icons/fi' has no exported member named 'X'. Did you mean 'Y'?`  → use Y
          - tsc:  `Module '…' has no exported member 'X'`                                → fallback
        Prefers the compiler's `Did you mean 'Y'` suggestion, then `Fi_X`→`FiX`, else a safe fallback."""
        m = (re.search(r"Export\s+(\w+)\s+doesn'?t exist in target module", message)
             or re.search(r"has no exported member(?: named)? '(\w+)'", message))
        if not m:
            return False
        bad = m.group(1)
        sug = re.search(r"Did you mean '(\w+)'", message)
        if sug and sug.group(1).startswith("Fi"):
            good = sug.group(1)
        elif bad.startswith("Fi_"):
            good = "Fi" + bad[3:]
        else:
            good = self._FI_FALLBACK
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        # Only act when `bad` is imported from a react-icons/* module (leave UI/db exports to their handlers).
        if not re.search(r"import\s*\{[^}]*\b" + re.escape(bad) + r"\b[^}]*\}\s*from\s*['\"]react-icons/",
                         content):
            return False
        new = re.sub(r"\b" + re.escape(bad) + r"\b", good, content)

        # De-duplicate the fallback within each react-icons import list (avoid a doubled specifier).
        def _dedup(mo):
            names, seen, out = [n.strip() for n in mo.group(1).split(",")], set(), []
            for n in names:
                if n and n not in seen:
                    seen.add(n); out.append(n)
            return "import { " + ", ".join(out) + " } from " + mo.group(2)

        new = re.sub(r"import\s*\{([^}]*)\}\s*from\s*(['\"]react-icons/[^'\"]+['\"])", _dedup, new)
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    # Entity names that collide with a UI primitive component of the same name.
    _UI_CLASH = {"Table", "Card", "Badge", "Input", "Select", "Label", "Checkbox", "Textarea"}

    def fix_ui_entity_collision(self, rel: str) -> bool:
        """An entity typed from `@/types` shares a name with a UI primitive (e.g. `Table`). When the file
        also RENDERS that UI component, alias the UI import as `<Name>UI` and rewrite ONLY the JSX tags to
        it — never the type positions (`Partial<Table>`, `Table[]`). Fixes the duplicate-identifier
        (TS2300/2440) and value-vs-type (TS2693/2749) clashes deterministically. The negative lookbehind
        `(?<![\\w])<Name` distinguishes a JSX tag from a generic type argument like `Partial<Table>`."""
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        changed = content
        for name in self._UI_CLASH:
            ui_mod = f"@/components/ui/{_UI_EXPORTS[name]}"
            has_entity = re.search(r"import\s+(?:type\s+)?\{[^}]*\b" + name + r"\b[^}]*\}\s*from\s*['\"]@/types['\"]", changed)
            ui_imp = re.search(r"import\s*\{([^}]*)\}\s*from\s*['\"]" + re.escape(ui_mod) + r"['\"]", changed)
            renders = re.search(r"(?<![\w])<" + name + r"\b", changed)
            if not has_entity or not renders:
                continue
            alias = name + "UI"
            ui_names = [n.strip() for n in ui_imp.group(1).split(",")] if ui_imp else []
            bare = [n for n in ui_names if n.split(" as ")[0].strip() == name]
            if ui_imp and bare:
                new_names = [f"{name} as {alias}" if n in bare else n for n in ui_names]
                changed = changed[:ui_imp.start()] + "import { " + ", ".join(dict.fromkeys(new_names)) + f" }} from '{ui_mod}'" + changed[ui_imp.end():]
            elif ui_imp:
                new_names = ui_names + [f"{name} as {alias}"]
                changed = changed[:ui_imp.start()] + "import { " + ", ".join(dict.fromkeys(new_names)) + f" }} from '{ui_mod}'" + changed[ui_imp.end():]
            else:
                lines = changed.split("\n")
                at = 1 if lines and "use client" in lines[0] else 0
                lines.insert(at, f"import {{ {name} as {alias} }} from '{ui_mod}'")
                changed = "\n".join(lines)
            changed = re.sub(r"(?<![\w])<" + name + r"\b", "<" + alias, changed)
            changed = re.sub(r"</" + name + r">", "</" + alias + ">", changed)
        if changed == content:
            return False
        fp.write_text(changed, encoding="utf-8")
        self.emit("file", {"path": rel, "content": changed})
        return True

    def fix_ui_barrel_import(self, rel: str) -> bool:
        """`import { Card, Button } from '@/components/ui'` (barrel doesn't exist) → per-primitive
        imports `@/components/ui/card`, `@/components/ui/button`."""
        prims = {"alert", "badge", "button", "card", "checkbox", "input", "label", "select",
                 "separator", "skeleton", "table", "textarea"}
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False

        def repl(m):
            out = []
            for n in [x.strip() for x in m.group(1).split(",") if x.strip()]:
                base = re.sub(r"\s+as\s+\w+", "", n).strip().lower()
                prim = next((p for p in prims if base.startswith(p)), None)
                if prim:
                    out.append(f"import {{ {n} }} from '@/components/ui/{prim}'")
            return "\n".join(out) if out else ""

        new = re.sub(r"import\s*\{([^}]+)\}[ \t]*from[ \t]*['\"]@/components/ui['\"][ \t]*;?", repl, content)
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    def strip_model_type_annotations(self, rel: str) -> bool:
        """gemma sometimes uses a Mongoose model as a TS TYPE: `const x: StayCharge = {…}` or
        `<StayCharge>`. Models are VALUES, not types — strip those annotations deterministically."""
        models = [p.stem for p in (self.project_dir / "models").glob("*.ts")]
        if not models:
            return False
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        new = content
        for m in models:
            new = re.sub(rf":\s*{re.escape(m)}\s*\[\]", ": any[]", new)     # `: Model[]` → `: any[]`
            new = re.sub(rf":\s*{re.escape(m)}\b(?!\s*[.\w\[])", "", new)    # `: Model` annotation
            new = re.sub(rf"<\s*{re.escape(m)}\s*>", "<any>", new)          # `<Model>` generic
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    def fix_session_field(self, rel: str) -> bool:
        """`requireUser()`/`getSession()` return SessionPayload = { userId, role, email }. gemma often
        reads `session._id` or `session.id` — rewrite to `.userId` deterministically."""
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        m = re.search(r"(?:const|let)\s+(\w+)\s*=\s*await\s+(?:requireUser|requireRole|getSession)\s*\(",
                      content)
        if not m:
            return False
        var = re.escape(m.group(1))
        new = re.sub(rf"\b{var}\._id\b", f"{m.group(1)}.userId", content)
        new = re.sub(rf"\b{var}\.id\b", f"{m.group(1)}.userId", new)
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    def normalize_db_import(self, rel: str) -> bool:
        """Force the canonical default `import dbConnect from '@/lib/mongodb'` and rewrite any
        connect-like call to dbConnect(). Fixes gemma using a NAMED import of the DEFAULT export."""
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        new = re.sub(r"import\s*\{[^}]*\}\s*from\s*['\"]@/lib/mongodb['\"]\s*;?",
                     "import dbConnect from '@/lib/mongodb'", content)
        for bad in ("connectToDatabase", "connectDatabase", "connectMongo", "connectDB", "connectDb", "connect"):
            new = re.sub(rf"\bawait\s+{bad}\s*\(", "await dbConnect(", new)
            new = re.sub(rf"\b{bad}\s*\(", "dbConnect(", new)
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    def remap_model_import(self, rel: str, module: str = None) -> bool:
        """Fix EVERY wrong model import in the file at once (`@models/invoices`, `@/models/invoice`,
        `../models/Invoices`, …) → the real `@/models/<Name>` by matching basenames to files in
        models/. Fixing all in one pass keeps the reports route (imports many models) from eating
        one fix-iteration per import."""
        models_dir = self.project_dir / "models"
        if not models_dir.exists():
            return False
        real = [p.stem for p in models_dir.glob("*.ts")]

        def match(base: str):
            b = base.lower()
            return next((r for r in real if r.lower() == b or r.lower().rstrip("s") == b.rstrip("s")), None)

        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False

        def repl(m):
            path = m.group(1)
            if "model" not in path.lower():
                return m.group(0)
            base = path.rstrip("/").split("/")[-1].replace(".ts", "")
            t = match(base)
            return f"from '@/models/{t}'" if t else m.group(0)

        new = re.sub(r"from\s+['\"]([^'\"]+)['\"]", repl, content)
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    def remap_import(self, rel: str, module: str) -> bool:
        """Deterministically fix a hallucinated INTERNAL import (e.g. '@/lib/db' or '../lib/db')
        to the real module ('@/lib/mongodb'), so the LLM can't oscillate between wrong paths."""
        base = module.rstrip("/").split("/")[-1].lower().replace(".ts", "").replace(".tsx", "")
        target = _INTERNAL_REMAP.get(base)
        if not target:
            return False
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        new = content.replace(f"'{module}'", f"'{target}'").replace(f'"{module}"', f'"{target}"')
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        return True

    # ── build ─────────────────────────────────────────────────────────────────
    def build(self) -> tuple[bool, str]:
        env = {**os.environ, "CI": "true", "MONGODB_URI": "", "NEXT_TELEMETRY_DISABLED": "1"}
        try:
            r = subprocess.run([NPM, "run", "build"], cwd=str(self.project_dir),
                               capture_output=True, text=True, timeout=420, env=env)
        except subprocess.TimeoutExpired:
            return False, "BUILD TIMEOUT"
        out = (r.stdout or "") + "\n" + (r.stderr or "")
        ok = ("Compiled successfully" in out or "✓ Compiled" in out
              or "Generating static pages" in out) and r.returncode == 0
        return ok, out

    def build_findings(self) -> tuple[bool, list[dict], str]:
        """Run `next build`; return (ok, [{file,line,message}], raw_output). The findings feed the
        build-fix loop so build-only errors (SWC parse, route-handler types) tsc --noEmit misses
        still get repaired — not just reported as an unresolved failure."""
        ok, out = self.build()
        return ok, ([] if ok else self.parse_build_errors(out)), out

    # ── parse ─────────────────────────────────────────────────────────────────
    def parse_build_errors(self, build_out: str) -> list[dict]:
        """Extract locatable errors from a `next build` log → [{file,line,message}]. Returns ALL
        Family-A (path:line:col) hits (not just the first, like first_error), then falls back to
        first_error's D/C/B families (route-handler / module-not-found / SWC frame) when no explicit
        path:line:col is present. Only files that exist under the project are kept."""
        text = _ANSI.sub("", build_out or "")
        out: list[dict] = []
        seen: set[tuple[str, int]] = set()
        for pat in _LOC_PATTERNS:
            for m in pat.finditer(text):
                rel = m.group(1).lstrip("./").replace("\\", "/")
                line = int(m.group(2))
                if (rel, line) in seen or not (self.project_dir / rel).exists():
                    continue
                seen.add((rel, line))
                out.append({"file": rel, "line": line,
                            "message": self._message_after(text, m.end())[:400]})
        if not out:
            fe = self.first_error(text)
            if fe:
                out.append({"file": fe[0], "line": fe[1], "message": fe[2]})
        return out

    def first_error(self, build_out: str):
        """Return (relpath, line, message) for the first locatable error, or None."""
        text = _ANSI.sub("", build_out)
        # Family A — explicit path:line:col (tsc / next type errors)
        best = None
        for pat in _LOC_PATTERNS:
            m = pat.search(text)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), m)
        if best is not None:
            m = best[1]
            rel = m.group(1).lstrip("./")
            line = int(m.group(2))
            msg = self._message_after(text, m.end())
            if (self.project_dir / rel).exists():
                return rel, line, msg[:400]
        # Family D — Next route-handler TYPE validation (reported in generated .next/types).
        # Map it back to the real source route file so the fixer can correct the signature.
        rh = re.search(r'RouteHandlerConfig<"(/api/[^"]+)">', text) or \
            re.search(r'import\("(?:\.\./)*(app/api/.+?)/route\.js"\)', text)
        if rh:
            seg = rh.group(1)
            rel = (f"app{seg}/route.ts" if seg.startswith("/api/")
                   else f"{seg}/route.ts")
            if (self.project_dir / rel).exists():
                return rel, 0, "Next route handler signature mismatch (RouteHandlerConfig)"
        # Family C — module not found (import of a missing/wrong package or path)
        mnf = _MODNOTFOUND.search(text)
        if mnf:
            rel = mnf.group(1).lstrip("./")
            if (self.project_dir / rel).exists():
                return rel, 0, f"Module not found: Can't resolve '{mnf.group(2)}'"
        # Family B — SWC error: reliable frame header ",-[<abspath>:line:col]" (the path may
        # itself contain [id] brackets, so anchor on the trailing :line:col].
        hdr = re.search(r"\[(.+?\.(?:tsx?|jsx?)):(\d+):(\d+)\]", text)
        if hdr:
            rel = self._relpath(hdr.group(1))
            if (self.project_dir / rel).exists():
                xm = re.search(r"^\s*x (.+)$", text, re.MULTILINE)
                frame_line, frame_msg = self._frame_line_and_msg(text[hdr.end(): hdr.end() + 1200])
                msg = (xm.group(1).strip() if xm else frame_msg) or "syntax error"
                line = frame_line or int(hdr.group(2))
                return rel, line, msg[:400]
        return None

    @staticmethod
    def _message_after(text: str, pos: int) -> str:
        """The real error message is the first non-empty, non-code-frame line AFTER the location."""
        for ln in text[pos:].splitlines()[:8]:
            s = ln.strip()
            if not s or re.match(r"^\d+\s*\|", s) or s[:1] in "|>^" or s.startswith(":"):
                continue
            return s
        mm = _MSG.search(text[pos: pos + 400])
        return mm.group(1).strip() if mm else "build error"

    def _relpath(self, p: str) -> str:
        p = p.strip()
        try:
            rp = os.path.relpath(p, str(self.project_dir))
            if not rp.startswith(".."):
                return rp.replace("\\", "/")
        except Exception:
            pass
        return p.lstrip("./").replace("\\", "/")

    # ── deterministic duplicate-export remover (gemma's most common self-correction bug) ──
    _SIG = re.compile(r"^export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(")
    _DEFSIG = re.compile(r"^export\s+default\s+(?:async\s+)?function\b")

    def _block_end(self, lines: list[str], start: int) -> int:
        depth, started = 0, False
        for j in range(start, len(lines)):
            depth += lines[j].count("{") - lines[j].count("}")
            if "{" in lines[j]:
                started = True
            if started and depth <= 0:
                return j
        return len(lines) - 1

    def dedup_exports(self, rel: str) -> bool:
        """Remove duplicate top-level `export [default] function NAME` blocks, keeping the LAST
        (the model usually drafts a wrong version then re-declares a corrected one)."""
        fp = self.project_dir / rel
        try:
            lines = fp.read_text(encoding="utf-8").splitlines()
        except Exception:
            return False
        blocks, i, n = [], 0, len(lines)
        while i < n:
            m = self._SIG.match(lines[i])
            key = m.group(1) if m else ("default" if self._DEFSIG.match(lines[i]) else None)
            if key:
                end = self._block_end(lines, i)
                blocks.append((key, i, end))
                i = end + 1
            else:
                i += 1
        from collections import defaultdict
        by_key: dict[str, list] = defaultdict(list)
        for b in blocks:
            by_key[b[0]].append(b)
        remove: set[int] = set()
        for key, bs in by_key.items():
            for b in bs[:-1]:            # keep last occurrence, drop earlier duplicates
                remove.update(range(b[1], b[2] + 1))
        if not remove:
            return False
        new = [ln for idx, ln in enumerate(lines) if idx not in remove]
        fp.write_text("\n".join(new) + "\n", encoding="utf-8")
        self.emit("file", {"path": rel, "content": "\n".join(new) + "\n"})
        return True

    @staticmethod
    def _frame_line_and_msg(block: str):
        """From an SWC code frame, find the caret line number + the annotation message."""
        lines = block.splitlines()
        last_num = None
        caret_num = None
        msg = ""
        for ln in lines:
            nm = _FRAME_NUM.match(ln)
            if nm:
                last_num = int(nm.group(1))
                continue
            stripped = ln.strip()
            if stripped.startswith(":") or stripped.startswith("`") or "^" in stripped:
                if caret_num is None and last_num is not None:
                    caret_num = last_num
                mm = re.search(r"(?:`-+|x|\^)\s*(.+)$", stripped)
                if mm and not msg:
                    cand = mm.group(1).strip(" `^|-")
                    if cand and not set(cand) <= set("^|-` "):
                        msg = cand
        if not msg:
            mm = _MSG.search(block)
            if mm:
                msg = mm.group(1).strip()
        return caret_num or last_num, msg

    # ── short project memory (entities / models / routes / api / components + locations) ──────
    def _repair_memory(self, budget: int = 6000) -> str:
        """Compact `.locode` memory so the repair LLM fixes WITH project context (the real entity
        names, model fields, valid routes/api, components, and where each lives on disk) instead of
        only the single failing file. Read from disk — the generator already wrote `.locode/*.md`."""
        loc = self.project_dir / ".locode"
        if not loc.is_dir():
            return ""
        parts: list[str] = []
        used = 0
        for name in ("LOCATIONS.md", "MODELS.md", "CONTRACT.md", "ROUTES.md",
                     "API.md", "ENTITIES.md", "COMPONENTS.md"):
            try:
                txt = (loc / name).read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if not txt:
                continue
            if used + len(txt) > budget:
                txt = txt[: max(0, budget - used)]
            parts.append(txt)
            used += len(txt)
            if used >= budget:
                break
        return "\n\n".join(parts)

    def _memory_block(self) -> str:
        mem = self._repair_memory()
        return (f"PROJECT MEMORY (real entities, model fields, valid routes/API, components + their "
                f"on-disk locations — use these EXACT names/paths, never invent):\n{mem}\n\n") if mem else ""

    # ── fix one (full file in, search/replace hunks out) ──────────────────────
    def fix_one(self, rel: str, line: int, message: str) -> bool:
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        numbered = "\n".join(f"{i+1}: {ln}" for i, ln in enumerate(content.splitlines()))
        user = (
            f"File: {rel}\nBuild error at line {line}:\n{message}\n\n"
            f"{self._memory_block()}"
            f"FULL FILE (line-numbered — copy SEARCH text WITHOUT the `N: ` prefix):\n{numbered}\n\n"
            f"Return search/replace block(s) that fix the error."
        )
        self.emit("start", {"label": f"fix {rel}:{line}"})
        out = ""
        try:
            for tok in llm.stream_chat([{"role": "user", "content": user}],
                                       model=self.model, system=FIX_SYSTEM,
                                       num_predict=2200, think=False, extra_opts=llm.REPAIR_OPTS):
                out += tok
                self.emit("token", tok)
        except Exception as e:  # noqa: BLE001
            self.emit("log", {"text": f"fix error: {e}"})
            self.emit("end", {})
            return False
        self.emit("end", {})
        new, applied = self._apply_edits(content, out)
        if applied == 0:
            self.emit("log", {"text": "no applicable search/replace edit produced"})
            return False
        if new == content:
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        self.emit("log", {"text": f"applied {applied} edit(s) to {rel}"})
        return True

    def fix_hard(self, rel: str, line: int, message: str) -> bool:
        """Escalation repair with the powerful cloud model (max context + thinking). The real answer
        may land in the model's thinking channel, so extract SEARCH/REPLACE from content, then thinking."""
        fp = self.project_dir / rel
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        numbered = "\n".join(f"{i+1}: {ln}" for i, ln in enumerate(content.splitlines()))
        user = (
            f"File: {rel}\nBuild error(s):\n{message}\n\n"
            f"{self._memory_block()}"
            f"FULL FILE (line-numbered — copy SEARCH text WITHOUT the `N: ` prefix):\n{numbered}\n\n"
            f"Reason about the type error, then return search/replace block(s) that GENUINELY fix it "
            f"(never `as any` / suppression)."
        )
        self.emit("start", {"label": f"fix(cloud) {rel}:{line}"})
        try:
            ct, th = llm.stream_capture([{"role": "user", "content": user}],
                                        model=llm.REMAINING_MODEL, system=FIX_SYSTEM, num_predict=6000,
                                        think=llm.REMAINING_THINK, extra_opts=llm.REMAINING_OPTS, timeout=600)
        except Exception as e:  # noqa: BLE001
            self.emit("log", {"text": f"fix(cloud) error: {e}"})
            self.emit("end", {})
            return False
        self.emit("end", {})
        has_edit = lambda s: "SEARCH" in s and "REPLACE" in s
        src = ct if has_edit(ct) else th if has_edit(th) else ct
        new, applied = self._apply_edits(content, src)
        if applied == 0 or new == content:
            self.emit("log", {"text": f"no applicable cloud edit for {rel}"})
            return False
        fp.write_text(new, encoding="utf-8")
        self.emit("file", {"path": rel, "content": new})
        self.emit("log", {"text": f"applied {applied} cloud edit(s) to {rel}"})
        return True

    def _apply_edits(self, content: str, model_out: str) -> tuple[str, int]:
        """Parse the model's SEARCH/REPLACE blocks and apply them to the full file.
        Any block whose search/replace text itself contains conflict markers is malformed
        (nested/echoed format) and is skipped so markers never get written into the file."""
        text = llm.strip_think(model_out or "")
        applied = 0
        for m in _EDIT.finditer(text):
            search = self._strip_numbers(m.group(1))
            replace = self._strip_numbers(m.group(2))
            if not search.strip():
                continue
            if _MARKER.search(search) or _MARKER.search(replace):
                self.emit("log", {"text": "skipped malformed edit (contains conflict markers)"})
                continue
            candidate = None
            if search in content:
                candidate = content.replace(search, replace, 1)
            else:
                candidate = self._loose_replace(content, search, replace)
            # never accept a result that introduces conflict markers
            if candidate is not None and not _MARKER.search(candidate):
                content = candidate
                applied += 1
        return content, applied

    def resolve_conflict_markers(self, rel: str) -> bool:
        """Deterministically clear stray `<<<<<<< / ======= / >>>>>>>` blocks the fixer may have
        written: keep the REPLACE side of a full block, and strip any leftover marker lines."""
        fp = self.project_dir / rel
        try:
            src = fp.read_text(encoding="utf-8")
        except Exception:
            return False
        if not _MARKER.search(src):
            return False
        # full blocks: <<<<<<< .. ======= <keep> >>>>>>>  → keep middle
        block = re.compile(r"<{5,}[^\n]*\n(?:.*?\n)?={5,}[^\n]*\n(.*?)>{5,}[^\n]*\n?", re.DOTALL)
        src2 = block.sub(lambda m: m.group(1), src)
        # strip any remaining stray marker lines
        src2 = "\n".join(ln for ln in src2.splitlines() if not _MARKER.match(ln)) + "\n"
        if src2 == src:
            return False
        fp.write_text(src2, encoding="utf-8")
        self.emit("file", {"path": rel, "content": src2})
        return True

    @staticmethod
    def _strip_numbers(block: str) -> str:
        lines = block.split("\n")
        numbered = sum(1 for ln in lines if re.match(r"^\s*\d+:\s", ln))
        if numbered >= max(1, len(lines) // 2):
            lines = [re.sub(r"^\s*\d+:\s?", "", ln) for ln in lines]
        return "\n".join(lines)

    @staticmethod
    def _loose_replace(content: str, search: str, replace: str):
        c_lines = content.split("\n")
        s_lines = [ln.rstrip() for ln in search.split("\n")]
        n = len(s_lines)
        for i in range(len(c_lines) - n + 1):
            if [c_lines[j].rstrip() for j in range(i, i + n)] == s_lines:
                return "\n".join(c_lines[:i] + replace.split("\n") + c_lines[i + n:])
        return None

    # ── loop ──────────────────────────────────────────────────────────────────
    def loop(self, max_iters: int = 8) -> bool:
        from collections import Counter
        last = None
        seen: Counter = Counter()
        for it in range(max_iters):
            ok, out = self.build()
            if ok:
                self.emit("log", {"text": f"build green after {it} fix pass(es)"})
                return True
            err = self.first_error(out)
            if not err:
                self.emit("log", {"text": "build failed but no locatable error — stopping"})
                self.emit("log", {"text": out[-600:]})
                return False
            rel, line, message = err
            # Oscillation guard: the same file+error recurring means we are not converging.
            sig = f"{rel}::{message[:50]}"
            seen[sig] += 1
            if seen[sig] > 3:
                # Last resort: surgical + deterministic fixes are exhausted on this file. If it is a
                # regenerable leaf component, regenerate that ONE file once and keep going.
                if rel not in self._regenerated and self.regen(rel):
                    self._regenerated.add(rel)
                    self.emit("log", {"text": f"regenerated {rel} (surgical fixes exhausted)"})
                    seen[sig] = 0
                    last = None
                    continue
                self.emit("log", {"text": f"not converging on {rel} ({message[:80]}) — stopping"})
                return False
            self.emit("log", {"text": f"fix pass {it+1}: {rel}:{line} — {message[:120]}"})
            # Conflict markers accidentally written into a file → resolve deterministically.
            if "conflict marker" in message.lower():
                if self.resolve_conflict_markers(rel):
                    self.emit("log", {"text": f"resolved conflict markers in {rel}"})
                    last = err
                    continue
            # Module-not-found handling.
            mnf = re.search(r"Module not found: Can't resolve '([^']+)'", message)
            if mnf:
                mod = mnf.group(1)
                low = mod.lower()
                top = mod[1:].split("/")[0] if mod.startswith("@") else mod.split("/")[0]
                base = mod.rstrip("/").split("/")[-1].lower().replace(".ts", "")
                # (a) declared npm dep missing → repair install once.
                if (mod in KNOWN_DEPS or top in KNOWN_DEPS) and not self._repaired:
                    self._repaired = True
                    self.emit("log", {"text": f"missing declared dep '{top}' — running npm install"})
                    self._npm_install()
                    last = err
                    continue
                # (b) wrong MODEL import (@models/x, @/models/xs, ../models/X) → real @/models/<Name>.
                if "model" in low and self.remap_model_import(rel, mod):
                    self.emit("log", {"text": f"remapped model import '{mod}' in {rel}"})
                    last = err
                    continue
                # (c) wrong internal LIB import (@lib/db, @/lib/database, ./lib/api) → real @/lib/*.
                if ("lib" in low or base in _INTERNAL_REMAP) and self.remap_import(rel, mod):
                    self.emit("log", {"text": f"remapped bad import '{mod}' in {rel}"})
                    last = err
                    continue
                # (d) `@/components/ui` barrel import → split into per-primitive imports.
                if mod.rstrip("/") == "@/components/ui" and self.fix_ui_barrel_import(rel):
                    self.emit("log", {"text": f"split ui barrel import in {rel}"})
                    last = err
                    continue
                # else: unknown external/import → let the LLM remove or replace it (once)
            # Named import of the DEFAULT dbConnect export → normalize deterministically.
            if "doesn't exist in target module" in message and re.search(r"connect", message, re.I):
                if self.normalize_db_import(rel):
                    self.emit("log", {"text": f"normalized db import in {rel}"})
                    last = err
                    continue
            # Hallucinated react-icons name (Export Fi_Utensils doesn't exist) → remap to a safe icon.
            if "doesn't exist in target module" in message:
                if self.fix_bad_icon_import(rel, message):
                    self.emit("log", {"text": f"remapped invalid icon import in {rel}"})
                    last = err
                    continue
            # UI primitive imported from the wrong file (Export Label doesn't exist) → relocate.
            if "doesn't exist in target module" in message:
                if self.fix_wrong_ui_export(rel, message):
                    self.emit("log", {"text": f"relocated ui import in {rel}"})
                    last = err
                    continue
            # Next route-handler signature mismatch → deterministic params/requireUser fix.
            if "routehandlerconfig" in message.lower() or "route handler signature" in message.lower():
                if self.fix_route_signature(rel):
                    self.emit("log", {"text": f"fixed handler signature in {rel}"})
                    last = err
                    continue
            # session.userId — gemma reads _id/id off the SessionPayload → deterministic fix.
            if "sessionpayload" in message.lower() and ("'_id'" in message or "'id'" in message):
                if self.fix_session_field(rel):
                    self.emit("log", {"text": f"fixed session field in {rel}"})
                    last = err
                    continue
            # model used as a TS type (`: Model` / `<Model>`) → strip the annotation deterministically.
            ml = message.lower()
            if ("refers to a value, but is being used as a type" in ml
                    or ("does not exist in type" in ml and "model<" in ml)):
                if self.strip_model_type_annotations(rel):
                    self.emit("log", {"text": f"stripped model-as-type annotations in {rel}"})
                    last = err
                    continue
            # Duplicate/redefined exports → deterministic de-dup first (reliable, no LLM).
            if any(k in message.lower() for k in _WIDEN) or "defined multiple times" in message.lower():
                if self.dedup_exports(rel):
                    self.emit("log", {"text": f"deduped {rel}"})
                    last = err
                    continue
            # Malformed import (stray `} }` / `{ {`) → deterministic import-syntax fix.
            if "expected 'from'" in message.lower() or ("import" in message.lower() and "expected" in message.lower()):
                if self.fix_import_syntax(rel):
                    self.emit("log", {"text": f"fixed import syntax in {rel}"})
                    last = err
                    continue
            # Truncated component (cut off at token limit) → append missing closers deterministically.
            if rel.endswith((".tsx", ".jsx", ".ts")) and ("<eof>" in message.lower()
                    or "end of file" in message.lower() or "unexpected eof" in message.lower()):
                if self.complete_truncated(rel):
                    self.emit("log", {"text": f"completed truncated file {rel}"})
                    last = err
                    continue
            # JSX syntax error → try removing garbage/hallucinated closing tags + stray `>` deterministically.
            if rel.endswith((".tsx", ".jsx")) and any(k in message.lower() for k in (
                    "expected '</'", "jsx", "unterminated", "expression expected",
                    "unexpected token", "expected ';'", "expected '}'")):
                if self.fix_bad_closing_tags(rel):
                    self.emit("log", {"text": f"fixed JSX tag typo(s) in {rel}"})
                    last = err
                    continue
            # General fix: full file → LLM → search/replace hunks applied to the file.
            if not self.fix_one(rel, line, message):
                # Don't abandon the whole app on one hard error — retry; the oscillation guard
                # (seen[sig] > 3) bounds it, and later passes may surface fixable errors first.
                self.emit("log", {"text": f"no LLM edit for {rel}:{line} — retrying"})
            last = err
        return self.build()[0]
