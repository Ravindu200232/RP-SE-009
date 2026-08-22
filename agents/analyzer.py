"""
Post-generation audit.

Generation can finish "successfully" and still ship a broken app, because every
gate in the pipeline answers a different question from "did we build what the
plan said". Measured against the nine generated projects on disk:

* one project promises 19 source files in its `plan.md` and has **17 missing** —
  the build was interrupted, nothing noticed, and the UI lists it as finished;
* another silently never wrote the `app/api/logout/route.js` it planned;
* a third links to four pages that do not exist.

None of those is a compile error, so `next build` is happy. Nothing imports a
Next.js page, so import repair cannot see a missing one. And a login whose
seeded password hash is wrong returns a perfectly valid 401, so Playwright
screenshots a working form and the pipeline goes green.

So this module reads the finished project back and compares it against the plan.
The split is deliberate:

* **file paths are checked in Python** — measured 0 false positives across all
  nine projects, so this needs no model and no tokens;
* **meaning is checked by the model** — "does this app actually do what the plan
  described" is not a regex, and trying to make it one produces noise;
* **credentials are checked by a real HTTP request** — the login page here shows
  `user1@example.com` while the seed *generates* emails from a template, so no
  static comparison can settle it.

The analyzer runs on whatever model the build used; there is nothing extra to
configure.
"""
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .architect import FileStreamParser
from .commands import CommandRunner
from . import nextdocs
from .exports import (FRAMEWORK_EXPORTS, check_named_imports,
                      parse_imports, resolve_local)

log = logging.getLogger("analyzer")


SKIP_DIRS = {"node_modules", ".git", ".next", "dist", "out", ".vite", ".agentforge",
             ".turbo", "public", "coverage"}
SOURCE_EXT = {".js", ".jsx", ".mjs", ".css", ".json", ".md"}
CODE_EXT = {".js", ".jsx", ".mjs"}


NEXT_ROOTS = ("app/", "components/", "lib/")


ROOT_SOURCE = {"middleware.js", "middleware.jsx", "instrumentation.js"}
MAX_FILE_BYTES = 200_000


PROSE_PATH_RE = re.compile(r"`((?:app|components|lib)/[^`]+?\.jsx?)`")


PLACEHOLDER_RE = re.compile(r"[*?<>\s]|\.\.\.")


LINK_HREF_RE = re.compile(
    r"""<Link\b[^>]*?href\s*=\s*(?:["'](/[^"']*)["']|\{\s*["'](/[^"']*)["']\s*\})""")
ROUTER_PUSH_RE = re.compile(r"""router\.(?:push|replace)\(\s*["'](/[^"']*)["']""")


FETCH_URL_RE = re.compile(r"""fetch\(\s*['"](/api/[A-Za-z0-9_\-/\[\]]*)['"]""")


BCRYPT_LITERAL_RE = re.compile(r"""["'](\$2[aby]?\$\d\d\$[^"']*)["']""")

HTTP_METHOD_RE = re.compile(
    r"export\s+(?:async\s+)?(?:function\s+|const\s+)"
    r"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")

SEVERITIES = ("blocker", "major", "minor")


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str = ""
    fix: str = ""

    extra: list = field(default_factory=list)

    def line(self) -> str:
        where = f"{self.path}: " if self.path else ""
        return f"[{self.severity}] {where}{self.message}"


@dataclass
class AnalyzerReport:
    findings: list = field(default_factory=list)
    planned: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    routes: dict = field(default_factory=dict)
    dead_links: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    credentials: dict = field(default_factory=dict)
    written: int = 0

    def blockers(self) -> list:
        return [f for f in self.findings if f.severity == "blocker"]

    def is_clean(self) -> bool:
        return not self.blockers()

    def summary(self) -> str:
        if not self.findings:
            return "no problems found"
        by = {s: sum(1 for f in self.findings if f.severity == s)
              for s in SEVERITIES}
        return ", ".join(f"{n} {s}" for s, n in by.items() if n)

    def as_prompt_block(self, limit: int = 25) -> str:
        ranked = sorted(self.findings, key=lambda f: SEVERITIES.index(f.severity))
        lines = []
        for i, f in enumerate(ranked[:limit], 1):
            lines.append(f"{i}. {f.line()}")
            if f.fix:
                lines.append(f"   → {f.fix}")
        if len(ranked) > limit:
            lines.append(f"… and {len(ranked) - limit} more")
        return "\n".join(lines)


class AnalyzerAgent:
    """
    Reads a finished project back and compares it against its plan.

    Holds a reference to the `ArchitectAgent` that built it and borrows five
    things: `_stream` (so queries run on the same model without touching the
    build conversation), `write_file`, `plan`, `plan_md` and `lint_generated`.
    Everything else — the command budget, the conversation, the tools — is its
    own, because an analyzer that shares the builder's budget arrives to find it
    spent, and one that shares its conversation trims away the history it is
    supposed to be auditing.
    """

    def __init__(self, arch, project_dir: Path = None, *,
                 base_url: str = "http://localhost:5173",
                 callbacks: dict = None,
                 allow_reseed: bool = False):
        self.arch = arch
        self.project_dir = Path(project_dir or arch.project_dir)
        self.base_url = base_url.rstrip("/")
        self.cb = callbacks or {}
        self.allow_reseed = allow_reseed

        self.cmd = CommandRunner(
            self.project_dir,
            npm_bin=(self.cb or {}).get("npm_bin", "npm"),
            node_bin=(self.cb or {}).get("node_bin", "node"),
            on_log=lambda lvl, txt: self._fire("on_log", lvl, txt),
            on_event=lambda ev: self._fire("on_command", ev))
        self._files_cache = None

        self._cache_seq = -1

    def _fire(self, name, *a):
        fn = self.cb.get(name)
        if fn and callable(fn):
            try:
                fn(*a)
            except Exception as e:
                log.warning(f"callback {name} failed: {e}")

    def _log(self, lvl, txt):

        if self.cb and self.cb.get("on_log"):
            self._fire("on_log", lvl, txt)
            return
        log.info(txt)

    def source_files(self, refresh: bool = False) -> dict:
        """
        Every source file, read from disk.

        Deliberately not `arch.files`: that dict holds `.env.local` verbatim
        (it is written through `write_file`), and its `package.json` goes stale
        the moment a `run_command` installs anything. Reading disk with an
        explicit `.env` filter makes a credential leak impossible by
        construction rather than by remembering to filter later, and it is the
        only thing that works when the project is opened cold with no build
        behind it.
        """

        seq = getattr(self.arch, "write_seq", 0)
        if (self._files_cache is not None and not refresh
                and self._cache_seq == seq):
            return self._files_cache
        out = {}
        for fp in sorted(self.project_dir.rglob("*")):
            if not fp.is_file() or any(s in fp.parts for s in SKIP_DIRS):
                continue
            if fp.suffix not in SOURCE_EXT or fp.name.startswith(".env"):
                continue
            if fp.name in ("package-lock.json", "test_screenshot.png"):
                continue
            try:
                if fp.stat().st_size > MAX_FILE_BYTES:
                    continue
                rel = str(fp.relative_to(self.project_dir)).replace("\\", "/")
                out[rel] = fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        self._files_cache = out
        self._cache_seq = seq
        return out

    def code_files(self) -> dict:
        """
        Next.js source only.

        A project rebuilt over an older Vite one keeps a dead `src/` tree
        alongside `app/`. Scanning it reports its `react-router-dom` and `vite`
        imports as missing packages — true of that leftover code, useless as a
        finding. `pages/` is likewise not part of this stack.
        """
        return {p: c for p, c in self.source_files().items()
                if Path(p).suffix in CODE_EXT
                and (p.startswith(NEXT_ROOTS) or p in ROOT_SOURCE)}

    def plan_text(self) -> str:
        """The prose plan. Prefer the live agent, fall back to disk."""
        if getattr(self.arch, "plan_md", ""):
            return self.arch.plan_md
        return self.source_files().get("plan.md", "")

    def planned_paths(self) -> list:
        """
        Source files the plan committed to, from the prose AND the JSON.

        The prose is the richer of the two — models describe every route there
        while the JSON `files` arrays sometimes omit one — and it is the only
        source that survives `load_existing()`, which restores `plan_md` but
        leaves `plan` empty.
        """
        found = set()
        for raw in PROSE_PATH_RE.findall(self.plan_text()):
            if not PLACEHOLDER_RE.search(raw):
                found.add(raw)
        for phase in (self.arch.plan or {}).get("phases", []):
            for f in phase.get("files", []):
                p = f.get("path") if isinstance(f, dict) else f
                if p and not PLACEHOLDER_RE.search(p):
                    found.add(p)
        return sorted(found)

    def _exists(self, rel: str) -> bool:
        """`.js` and `.jsx` name the same file as far as a plan is concerned."""
        base = rel[:-4] if rel.endswith(".jsx") else rel[:-3]
        return any((self.project_dir / c).exists()
                   for c in (rel, base + ".js", base + ".jsx"))

    PLACEHOLDER_MARKERS = ("Building…", "Building&hellip;", "Building...")

    def _is_placeholder(self, rel: str) -> bool:
        body = self.source_files().get(rel, "")
        return (bool(body) and len(body) < 400
                and any(m in body for m in self.PLACEHOLDER_MARKERS))

    ALWAYS_CHECKED = ("app/page.jsx", "app/page.js")

    def missing_files(self) -> list:
        out = [p for p in self.planned_paths()
               if not self._exists(p) or self._is_placeholder(p)]
        seen = set(out)
        for rel in self.ALWAYS_CHECKED:
            if rel not in seen and self._is_placeholder(rel):
                out.append(rel)
        return out

    def enumerate_routes(self) -> dict:
        """
        Every URL the app serves — uncapped, including dynamic segments and
        `app/api/**/route.js`, unlike the tester's five-page sample.
        """
        app = self.project_dir / "app"
        routes = {}
        if not app.is_dir():
            return routes

        def url_for(fp: Path) -> str:
            segs = [s for s in fp.relative_to(app).parts[:-1]
                    if not (s.startswith("(") and s.endswith(")"))]
            return "/" + "/".join(segs) if segs else "/"

        for name, kind in (("page", "page"), ("route", "api")):
            for suffix in (".js", ".jsx"):
                for fp in sorted(app.rglob(f"{name}{suffix}")):
                    if any(s in fp.parts for s in SKIP_DIRS):
                        continue
                    url = url_for(fp)
                    if url in routes:
                        continue
                    try:
                        body = fp.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        body = ""
                    routes[url] = {
                        "file": str(fp.relative_to(self.project_dir)).replace("\\", "/"),
                        "kind": kind,
                        "dynamic": "[" in url,
                        "methods": sorted(set(HTTP_METHOD_RE.findall(body))) or
                                   (["GET"] if kind == "page" else []),
                    }
        return routes

    @staticmethod
    def _route_matches(target: str, served) -> bool:
        tp = [s for s in target.strip("/").split("/") if s]
        for url in served:
            sp = [s for s in url.strip("/").split("/") if s]
            if len(sp) != len(tp):
                continue
            if all(b.startswith("[") or a == b for a, b in zip(tp, sp)):
                return True
        return False

    def dead_links(self, routes: dict = None) -> list:
        """Literal in-app links that resolve to no page."""
        routes = self.enumerate_routes() if routes is None else routes
        pages = [u for u, r in routes.items() if r["kind"] == "page"]
        dead = set()
        for path, content in self.code_files().items():
            targets = [a or b for a, b in LINK_HREF_RE.findall(content)]
            targets += ROUTER_PUSH_RE.findall(content)
            for raw in targets:
                url = raw.split("?")[0].split("#")[0].rstrip("/") or "/"
                if url.startswith("/api"):
                    continue
                if not self._route_matches(url, pages):
                    dead.add(url)
        return sorted(dead)

    DEMO_HEADING_RE = re.compile(r"[Dd]emo\s+[Aa]ccounts?|[Tt]est\s+[Cc]redentials?")
    EMAIL_LITERAL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}")

    PREFILL_RE = re.compile(r"""(?:defaultValue|useState)\s*[=(]\s*['"][\w.+-]+@""")
    PLACEHOLDER_ATTR_RE = re.compile(r"""placeholder\s*=\s*["'{][^"'}]*["'}]""")

    def credentials_exposed(self) -> list:
        """
        Demo credentials rendered inside the generated app.

        AgentForge knows the demo accounts and shows them in its own UI, so a
        "Demo Accounts" card listing five emails and a shared password above
        the login form is noise at best. Measured across ten projects: five
        hits, at most one per project, every one of them a login page or modal.

        `placeholder="you@example.com"` is not a credential and is stripped
        before matching; `lib/seed.js` is where the values belong and is
        excluded.
        """
        out = []
        passwords = {p for _e, p in self.demo_credentials() if p}
        files = self.code_files()
        for path, content in sorted(files.items()):
            if not path.startswith(("app/", "components/")):
                continue
            if "seed" in path.lower():
                continue
            vis = self.PLACEHOLDER_ATTR_RE.sub("", content)
            why = []
            if any(p in vis for p in passwords):
                why.append("a seeded password appears in the markup")
            for m in self.DEMO_HEADING_RE.finditer(vis):
                if self.EMAIL_LITERAL_RE.search(vis[m.start():m.start() + 400]):
                    why.append("a 'Demo Accounts' panel lists real addresses")
                    break

            if re.search(r"""DEMO_ACCOUNTS|demoAccounts""", vis):
                why.append("it renders a DEMO_ACCOUNTS list")
            if self.PREFILL_RE.search(vis):
                why.append("the sign-in form is pre-filled with an address")
            if why:
                out.append(Finding(
                    "major", "CREDS_IN_UI",
                    f"demo credentials are visible in the app — {why[0]}",
                    path=path,
                    fix="remove the demo-account panel and any pre-filled "
                        "values; the accounts stay seeded and AgentForge shows "
                        "them to the developer outside the app"))
        return out

    SEED_COUNT_RE = re.compile(r"Array\.from\s*\(\s*\{\s*length\s*:\s*(\d+)"
                               r"|for\s*\(\s*(?:let|var)\s+\w+\s*=\s*0\s*;"
                               r"\s*\w+\s*<\s*(\d+)")

    def seed_volume(self) -> list:
        """
        More demo rows than anyone asked for.

        `lib/seed.js` ranges from 59 to 757 lines across the projects on disk,
        and 0 to 22 accounts. Generation time goes into fixtures instead of
        screens. Reported as **minor** on purpose: this is taste, not breakage,
        so it never enters repair()'s blocker allowlist and never triggers a
        rewrite of working code.
        """
        if "Sample data: requested" in self.plan_text():
            return []
        out = []
        for path, content in sorted(self.code_files().items()):
            if "seed" not in path.lower() or not path.startswith("lib/"):
                continue
            counts = []
            for m in re.finditer(r"const\s+(\w+)\s*=\s*\[", content):
                n = self._count_top_level_objects(content, m.end() - 1)
                if n >= 5:
                    counts.append((m.group(1), n))
            for m in self.SEED_COUNT_RE.finditer(content):
                n = int(m.group(1) or m.group(2))
                if n >= 5:
                    counts.append(("generated", n))

            counts = [(name, n) for name, n in counts
                      if "user" not in (name or "").lower()]
            if counts:
                worst = max(counts, key=lambda c: c[1])
                out.append(Finding(
                    "minor", "SEED_VOLUME",
                    f"seeds {worst[1]} `{worst[0]}` documents; the plan did not "
                    f"ask for sample data, so fewer than 5 is enough to prove "
                    f"the screens work",
                    path=path,
                    fix="cut the demo rows down unless the idea asked for "
                        "sample data"))
        return out

    @staticmethod
    def _count_top_level_objects(src: str, open_bracket: int) -> int:
        """Objects directly inside the array literal starting at `[`."""
        depth, n, i = 0, 0, open_bracket
        while i < len(src):
            c = src[i]
            if c in "[{":
                depth += 1
                if depth == 2 and c == "{":
                    n += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    return n
            i += 1
        return n

    COOKIE_SET_RE = re.compile(r"\.set\(\s*(?:['\"]([^'\"]+)['\"]|([A-Z_][A-Z0-9_]*))")
    COOKIE_GET_RE = re.compile(
        r"\.(?:get|delete)\(\s*(?:['\"]([^'\"]+)['\"]|([A-Z_][A-Z0-9_]*))")
    CONST_STR_RE = re.compile(r"\bconst\s+([A-Z_][A-Z0-9_]*)\s*=\s*['\"]([^'\"]+)['\"]")

    SESSIONISH_RE = re.compile(r"session|token|auth|jwt|user", re.I)

    def session_cookie_mismatch(self) -> list:
        """
        The session cookie is written under one name and read under another.

        This is the "logs in, then immediately gets logged out again" bug, and
        it is invisible to every other gate: the login route returns 200, the
        browser really does receive a Set-Cookie, and the redirect happens. The
        next request then reads a *different* cookie name, finds nothing, and
        bounces the user back to the login page.

        Measured live: `app/api/auth/login/route.js` sets `session_user_id`,
        while `lib/auth.js` — which `getSessionUser()`, `/api/auth/me` and every
        guarded page go through — reads `megamart_session`. Nothing writes
        `megamart_session`, so no session ever existed.

        Same family as a broken named import: a contract spread across two files
        and agreed in neither.
        """
        files = self.code_files()
        written, read_at = set(), {}
        for path, content in sorted(files.items()):
            consts = dict(self.CONST_STR_RE.findall(content))
            if "cookies" not in content and "cookieStore" not in content:
                continue
            for lit, ident in self.COOKIE_SET_RE.findall(content):
                name = lit or consts.get(ident)
                if name:
                    written.add(name)
            for lit, ident in self.COOKIE_GET_RE.findall(content):
                name = lit or consts.get(ident)
                if name and self.SESSIONISH_RE.search(name):
                    read_at.setdefault(name, []).append(path)

        out = []

        login = self.find_login_endpoint()
        login_file = (f"app{login}/route.js" if login else "")
        reader = "lib/auth.js" if "lib/auth.js" in files else ""
        if login_file in files and reader:
            def names(src, rx):
                consts = dict(self.CONST_STR_RE.findall(files[src]))
                got = set()
                for lit, ident in rx.findall(files[src]):
                    n = lit or consts.get(ident)
                    if n and self.SESSIONISH_RE.search(n):
                        got.add(n)
                return got

            sets = names(login_file, self.COOKIE_SET_RE)
            gets = names(reader, self.COOKIE_GET_RE)
            if sets and gets and not (sets & gets):
                out.append(Finding(
                    "blocker", "SESSION_COOKIE_MISMATCH",
                    f"sets the cookie `{sorted(sets)[0]}`, but {reader} — which "
                    f"getSessionUser(), /api/auth/me and every guarded page go "
                    f"through — reads `{sorted(gets)[0]}`. Login returns 200 "
                    f"and really does set a cookie, the redirect happens, and "
                    f"then the very next request finds no session and sends the "
                    f"user straight back to the login page",
                    path=login_file,
                    fix=f"delete the inline cookie write in {login_file} and "
                        f"call the session helper {reader} already exports, so "
                        f"one constant is the only cookie name in the app",
                    extra=[reader]))

        covered = {p for f in out for p in [f.path] + list(f.extra)}
        for name, paths in sorted(read_at.items()):
            if name in written or set(paths) <= covered:
                continue
            where = ", ".join(sorted(set(paths))[:3])
            out.append(Finding(
                "blocker", "SESSION_COOKIE_MISMATCH",
                f"reads the cookie `{name}`, which nothing in this app ever "
                f"sets. "
                + (f"The cookie that IS written is "
                   f"`{sorted(written)[0]}`. " if len(written) == 1 else
                   f"The cookies that ARE written: "
                   f"{', '.join(sorted(written))}. " if written else
                   "No cookie is written anywhere. ")
                + "Login will return 200 and set a cookie, the redirect will "
                  "happen, and the very next request will find no session and "
                  "send the user straight back to the login page",
                path=sorted(set(paths))[0],
                fix=f"use ONE cookie name everywhere: export a single constant "
                    f"from lib/auth.js and have the login route, the session "
                    f"reader and the logout route all import it. Read at: "
                    f"{where}",
                extra=sorted(set(paths))))
        return out

    UNIQUE_INDEX_RE = re.compile(
        r"createIndex\s*\([^)]*?\{\s*unique\s*:\s*true", re.S)

    def unique_index_in_seed(self) -> list:
        """
        A unique index built by the seed, over data that outlives the code.

        This is the one that makes failures look random between generation
        rounds. The code is regenerated; the database is not. A later seed adds
        `createIndex({ sku: 1 }, { unique: true })`, meets products written
        before `sku` existed, and the build throws E11000 on `{ sku: null }`.
        The rejection propagates out of `ensureSeeded()` — which every page
        awaits — so every page 500s at once, and which pages those are depends
        on nothing in the source.

        Observed live: `agentforge_json_srs_document_docum.products index: sku_1
        dup key: { sku: null }`, every route 500, `next build` perfectly happy.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            if "seed" not in path.lower():
                continue
            for m in self.UNIQUE_INDEX_RE.finditer(content):
                field = re.search(r"createIndex\s*\(\s*\{\s*([\w.]+)",
                                  content[m.start():m.start() + 120])
                name = field.group(1) if field else "?"
                line = content[:m.start()].count("\n") + 1
                out.append(Finding(
                    "blocker", "UNIQUE_INDEX_IN_SEED",
                    f"builds a unique index on `{name}` at line {line}. The "
                    f"database survives regeneration, so this will meet "
                    f"documents written before `{name}` existed; two nulls "
                    f"make the build throw E11000 inside ensureSeeded(), and "
                    f"every page that awaits it returns 500",
                    path=path,
                    fix=f"drop the unique index on `{name}`, or at minimum move "
                        f"every createIndex inside the same "
                        f"`if (await col.countDocuments() > 0) return` guard as "
                        f"the insert and remove `unique: true`"))
                break
        return out

    COMPONENT_PROPS_RE = re.compile(
        r"export\s+default\s+(?:async\s+)?function\s+(\w+)\s*\(\s*\{([^}]*)\}"
        r"|export\s+default\s+function\s*\(\s*\{([^}]*)\}")
    JSX_OPEN_RE = re.compile(r"<([A-Z]\w*)(?=[\s/>])")
    JSX_PROP_RE = re.compile(r"(\w+)\s*=\s*[{\"']")

    @staticmethod
    def _jsx_attrs(src: str, start: int):
        """
        The attribute text of the JSX tag opening at `start`, or None.

        A regex cannot do this. `onAddToCart={(p) => add(p)}` contains a `>`,
        so any `<Comp[^>]*>` pattern stops inside the arrow function and reports
        every prop after it as missing — which is how one call site passing all
        seven props came back as "missing five". Depth-aware scanning is the
        only way to find the real end of the tag.
        """
        i, depth, quote = start, 0, ""
        while i < len(src):
            c = src[i]
            if quote:
                if c == "\\":
                    i += 2
                    continue
                if c == quote:
                    quote = ""
            elif c in "\"'`":
                quote = c
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == ">" and depth == 0:
                return src[start:i]
            elif c == "<" and depth == 0 and i > start:
                return None
            i += 1
        return None

    @staticmethod
    def _prop_is_required(body: str, name: str) -> bool:
        """
        True when the component would throw if this prop were undefined.

        Bias is toward silence: any guard anywhere in the file — `prop &&`,
        `prop ?`, `prop?.`, `if (prop)`, `prop ||`, `prop ??` — makes it
        optional, even if some other use is unguarded. A missed real break
        costs one bug; a false one sends the repair model into working code.
        """
        n = re.escape(name)
        if re.search(rf"\b{n}\s*(?:&&|\?\.|\?[^.]|\|\||\?\?)", body):
            return False
        if re.search(rf"\bif\s*\(\s*!?\s*{n}\b", body):
            return False

        return bool(re.search(rf"\b{n}\s*(?:\.|\(|\[)", body)
                    or re.search(rf"\{{\s*\.\.\.\s*{n}\b", body))

    def prop_contract_breaks(self) -> list:
        """
        A component rendered without the prop it destructures.

        The same disease as a broken named import, one level down: the contract
        lives in one file and the call site in another, and JavaScript checks
        neither. Observed live — `StockAdjustmentForm({ product })` rendered as
        `<StockAdjustmentForm products={products} />`, so `product` was
        undefined and `product.image` threw a 500 on a page that compiled.

        A prop counts as REQUIRED only when the component dereferences or calls
        it with no guard anywhere in the file. That test is what makes this
        usable: `StatCard({ title, value, trend })` renders `{trend && …}`, so
        four call sites omitting `trend` are perfectly correct — measured, they
        were four of the fifteen first-draft findings. A component that takes a
        rest prop or `children` is skipped entirely.
        """
        files = self.code_files()

        contracts = {}
        for path, content in files.items():
            if not path.startswith("components/"):
                continue
            m = self.COMPONENT_PROPS_RE.search(content)
            if not m:
                continue
            body = m.group(2) or m.group(3) or ""
            if "..." in body:
                continue
            names = []
            for part in body.split(","):
                part = part.strip()
                if not part or "=" in part or ":" in part:
                    continue
                if not re.fullmatch(r"\w+", part) or part == "children":
                    continue
                if self._prop_is_required(content, part):
                    names.append(part)
            if names:
                contracts[path] = set(names)

        out = []
        for path, content in sorted(files.items()):

            local = {}
            for st in parse_imports(content):
                if not st.default or not st.spec.startswith(("./", "../", "@/")):
                    continue
                target = resolve_local(path, st.spec, files)
                if target:
                    local[st.default] = target

            for m in self.JSX_OPEN_RE.finditer(content):
                comp = m.group(1)
                src = local.get(comp)
                if src is None or src not in contracts or src == path:
                    continue
                required = contracts[src]
                attrs = self._jsx_attrs(content, m.end())
                if attrs is None:
                    continue
                if re.search(r"\{\s*\.\.\.", attrs):
                    continue
                given = set(self.JSX_PROP_RE.findall(attrs))
                missing = required - given
                if not missing:
                    continue
                line = content[:m.start()].count("\n") + 1
                out.append(Finding(
                    "blocker", "PROP_CONTRACT",
                    f"line {line} renders <{comp}> without "
                    f"{', '.join(sorted(missing))}, which {src} destructures "
                    f"and uses. It will be undefined at runtime and the first "
                    f"property read on it throws — a 500 on a page that "
                    f"compiles cleanly"
                    + (f". Given instead: {', '.join(sorted(given))}"
                       if given else ""),
                    path=path,
                    fix=f"pass {', '.join(sorted(missing))} to <{comp}>, or "
                        f"change {src} to accept what this call site actually "
                        f"has",
                    extra=[src]))
        return out

    def dead_endpoints(self, routes: dict = None) -> list:
        """
        `fetch('/api/…')` calls that no route handler serves.

        This is the other half of the "login bounces back to login" bug, and
        the half nothing else can see. In the project that reported it, a client
        layout does:

            const menuRes = await fetch('/api/admin/menu')
            if (!menuRes.ok) router.push('/login?redirect=' + pathname)

        and `app/api/admin/menu/route.js` was never written. The page compiles,
        renders, returns 200 — and then throws the user straight back to the
        login screen a moment later. A server-side route probe sees only the
        200; the failure lives in an effect that runs after it.

        Measured across all ten Next projects: three findings, one per affected
        project, all real, zero elsewhere.
        """
        routes = self.enumerate_routes() if routes is None else routes
        apis = [u for u, r in routes.items() if r["kind"] == "api"]
        dead = set()
        for path, content in self.code_files().items():
            for raw in FETCH_URL_RE.findall(content):
                url = raw.split("?")[0].rstrip("/") or "/"
                if not self._route_matches(url, apis):
                    dead.add(url)
        return sorted(dead)

    def stray_directives(self) -> list:
        """`'use client'` that is not the first statement — a hard build error."""
        out = []
        for path, content in self.code_files().items():
            for m in self.arch.STRAY_DIRECTIVE_RE.finditer(content):
                head = re.sub(r"//[^\n]*|/\*.*?\*/", "", content[:m.start()],
                              flags=re.S).strip()
                if head:
                    out.append(f"{path}:{content[:m.start()].count(chr(10)) + 1}")
                    break
        return out

    def broken_imports(self) -> list:
        """
        Named imports of a local module that the module does not export.

        This is the check that catches the "login reaches the dashboard and
        bounces back" class of bug. JavaScript has no compile-time export
        checking, so `next build` passes and the route 500s at request time
        instead; the missing-file check above cannot see it, because the file
        being imported exists perfectly well — only the names are wrong.

        `extra` carries the target module, because the fix usually belongs
        there (write the missing function) rather than in the importer.
        """
        out = []
        groups = {}
        for b in check_named_imports(self.code_files()):
            groups.setdefault((b.importer, b.module, b.spec), []).append(b)
        for (importer, module, spec), items in sorted(groups.items()):
            names = ", ".join(sorted({i.name for i in items}))
            avail = ", ".join(items[0].available) or "(nothing)"
            framework = module in FRAMEWORK_EXPORTS
            out.append(Finding(
                "blocker", "BROKEN_IMPORT",
                f"imports {{ {names} }} from '{spec}', which exports only: "
                f"{avail}. Calling one of those throws at request time, so the "
                f"route returns 500 — `next build` cannot catch this",
                path=importer,
                fix=("use one of those instead — NextResponse.json(…) is "
                     "almost always what is meant" if framework else
                     f"either add the missing export to {module} or use one "
                     f"that already exists. Do not rename or remove the "
                     f"existing exports — other files import them"),

                extra=[] if framework else [module]))
        return out

    def unresolved_packages(self) -> list:
        """Imported but neither declared nor installed. Node builtins excluded."""
        try:
            pkg = json.loads((self.project_dir / "package.json")
                             .read_text(encoding="utf-8"))
            declared = set(pkg.get("dependencies", {})) | \
                set(pkg.get("devDependencies", {}))
        except Exception:
            declared = set()
        nm = self.project_dir / "node_modules"
        missing = []
        for content in self.code_files().values():
            for name in self.arch.imported_packages(content):
                if name in declared or (nm / name / "package.json").exists():
                    continue
                if name not in missing:
                    missing.append(name)
        return missing

    def seed_race(self) -> list:
        """
        A seed that is not safe to call twice at once.

        Generated apps call `ensureSeeded()` from the root layout, so it runs on
        every request. `if (await col.countDocuments() === 0) insertMany(docs)`
        is a race: two requests arriving together both read 0, both insert, and
        the loser dies with E11000 — which turns into an HTTP 500 on a page
        that is otherwise correct. `insertMany` also stamps `_id` onto the
        documents it was given, so a module-level array cannot be reused.

        This is intermittent, which is what makes it so confusing in the wild.
        """
        out = []
        for path, content in self.code_files().items():
            if "ensureSeeded" not in content or "insertMany" not in content:
                continue
            if "seed" not in path.lower():
                continue
            guarded = ("ordered: false" in content or "ordered:false" in content
                       or "e.code !== 11000" in content
                       or "code !== 11000" in content
                       or re.search(r"\blet\s+\w*[Ss]eed\w*\s*=\s*null", content)
                       or re.search(r"upsert\s*:\s*true", content))
            if guarded:
                continue
            out.append(Finding(
                "blocker", "SEED_RACE",
                "ensureSeeded() inserts without guarding against a concurrent "
                "run — two requests at once both see an empty collection and "
                "the second insertMany fails with E11000, which 500s the page",
                path=path,
                fix="cache the run in a module-level promise, build the "
                    "documents inside the function, and use "
                    "insertMany(docs, { ordered: false }) inside a try/catch "
                    "that ignores e.code === 11000"))
        return out

    COUNT_GUARD_RE = re.compile(
        r"countDocuments\s*\([^)]*\)\s*\)*\s*(?:[><=!]=?=?)\s*0"
        r"|\.length\s*(?:[><=!]=?=?)\s*0"
        r"|if\s*\(\s*!\s*(?:existing|found|already)\w*\s*\)")

    COUNT_VAR_RE = re.compile(
        r"(?:const|let|var)\s+(\w+)\s*=\s*await\s+[\w.]*countDocuments\s*\(")
    UPSERT_RE = re.compile(r"upsert\s*:\s*true|\$setOnInsert|bulkWrite")

    def stale_seed_guard(self) -> list:
        """
        A seed that stops working the first time a real person signs up.

        `if (await usersCol.countDocuments() > 0) return` reads like "seed
        once". What it actually means is "seed only while nobody has ever
        registered". One signup makes the count non-zero permanently, so the
        demo accounts are never created — while the app still advertises them —
        and every demo login returns 401 from then on.

        Observed exactly that way: a user signed up, and
        `agentforge_json_srs_document_docum_2.users` then held one real account and
        zero of its three demo accounts. The app was correct the day it was
        built and broken the day it was used, which is why nothing caught it:
        every other gate here runs at build time, against a database AgentForge had
        just dropped.

        Measured across the corpus: **13 of 13 seeded projects** have this, and
        not one uses an upsert — because the builder prompt handed them the
        count-guard as its template. Note `seed_race()` above treats
        `upsert: true` as proof of concurrency-safety, which it is; this check
        is the other half of the same fact, and the two agree that an upsert is
        the right shape.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            if "seed" not in path.lower() or "ensureSeeded" not in content:
                continue
            if self.UPSERT_RE.search(content):
                continue
            m = self.COUNT_GUARD_RE.search(content)
            if not m:

                for v in self.COUNT_VAR_RE.finditer(content):
                    name = re.escape(v.group(1))
                    m = re.search(rf"\b{name}\s*(?:[><=!]=?=?)\s*0", content)
                    if m:
                        break
                    m = None
            if not m:
                continue
            line = content[:m.start()].count("\n") + 1
            out.append(Finding(
                "blocker", "STALE_SEED_GUARD",
                f"line {line} gates seeding on whether the collection is "
                f"already populated. The first real signup makes that "
                f"permanently true, so the demo accounts are never created "
                f"and every demo login 401s from then on — while the app goes "
                f"on offering them",
                path=path,
                fix="seed by identity instead: one "
                    "`updateOne({ email }, { $setOnInsert: {…} }, "
                    "{ upsert: true })` per document. `$setOnInsert`, not "
                    "`$set` — a bcrypt hash differs every time it is computed, "
                    "so `$set` would rewrite it on every start and could "
                    "overwrite a password a real user had changed"))
        return out

    def authz_redirect(self) -> list:
        """
        A signed-in user sent to the login page because of their role.

            if (!user || user.role !== 'admin') redirect('/login')

        Two different failures share one branch here. No session means "sign
        in", and `/login` is right. A session with the wrong role means "you may
        not see this" — and sending that user to the login page is
        indistinguishable, from where they are sitting, from having their login
        rejected. They sign in, land back on the login form, and conclude the
        password is wrong.

        That is the "I log in and it throws me back to login" report, and it is
        measured at 7 occurrences across 5 projects — three of them in the app
        that was reported.

        Parenthesis-balanced rather than regex-matched: the common shape is
        `(user.role !== 'a' && user.role !== 'b')`, and a `[^)]*` pattern stops
        at the inner `)` and misses every multi-role guard, which is most of
        them.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            for m in re.finditer(r"if\s*\(\s*!\s*\w+\s*\|\|", content):
                open_paren = content.rindex("(", m.start(), m.end())
                depth = 0
                for k in range(open_paren, min(len(content), open_paren + 800)):
                    if content[k] == "(":
                        depth += 1
                    elif content[k] == ")":
                        depth -= 1
                        if depth:
                            continue
                        cond, tail = content[open_paren:k + 1], content[k + 1:k + 140]
                        if re.search(r"\brole\b|\bisAdmin\b|\bpermission", cond) \
                                and re.search(r"redirect\(\s*['\"]/login", tail):
                            line = content[:open_paren].count("\n") + 1
                            out.append(Finding(
                                "blocker", "AUTHZ_REDIRECT",
                                f"line {line} sends a signed-in user to "
                                f"/login because their role does not match. "
                                f"From the user's side that is identical to a "
                                f"rejected password: they log in, bounce back "
                                f"to the login form, and report that login is "
                                f"broken",
                                path=path,
                                fix="split the two cases — `if (!user) "
                                    "redirect('/login')` for no session, then a "
                                    "separate `if (user.role !== '…') "
                                    "redirect('/')` for the wrong role"))
                        break
        return out

    def seed_behind_auth(self) -> list:
        """
        The seeder placed after an auth guard, so it can never run.

        Observed exactly this, and it deadlocks the app:

            const user = await getSessionUser()
            if (!user) redirect('/login')     // everyone, on a fresh database
            await ensureSeeded()              // never reached

        The first visitor is signed out, so they are redirected before the seed
        runs; the seed is what creates the demo accounts; so no account exists
        to sign in with. You need an account to trigger the code that creates
        accounts. Every gate passes — the page compiles, `/` answers 307, the
        route probe is happy — and the user meets it as "login doesn't work"
        with an empty `user` collection.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            m = re.search(r"\bensureSeeded\s*\(", content)
            if not m:
                continue
            guard = re.search(r"\bredirect\s*\(\s*['\"]", content[:m.start()])
            if not guard:
                continue
            line = content[:m.start()].count("\n") + 1
            gline = content[:guard.start()].count("\n") + 1
            out.append(Finding(
                "blocker", "SEED_BEHIND_AUTH",
                f"calls ensureSeeded() at line {line}, after the redirect at "
                f"line {gline}. On a fresh database nobody is signed in, so "
                f"every visitor is redirected before the seed runs — and the "
                f"seed is what creates the accounts they would sign in with",
                path=path,
                fix="move `await ensureSeeded()` above the session read, so it "
                    "is the first thing the page does. Better still, also call "
                    "it from the login page — that is the page a signed-out "
                    "visitor actually reaches"))
        return out

    LOOPBACK_ORIGIN_RE = re.compile(
        r"trustedOrigins[^\]]*?(localhost:\*|127\.0\.0\.1:\*)", re.S)

    def auth_origin(self) -> list:
        """
        Better Auth configured to refuse the origin the app is viewed from.

        It compares the request's `Origin` header against `trustedOrigins` and
        answers `403 Invalid origin` for anything else — which reaches the user
        as a red line on the login form, with an empty database and nothing at
        all in the build output. Every other gate passes: the app compiles, the
        routes return 200, the seeder works (it is a direct server-side call and
        carries no Origin header).

        The port cannot be pinned down, which is why the check is for a pattern
        rather than a value: AgentForge previews the app through a proxy on a
        different port from the dev server, the dev port moves when one is
        busy, and `localhost` and `127.0.0.1` are distinct origins to a browser.
        """
        auth = self.code_files().get("lib/auth.js", "")
        if "betterAuth(" not in auth:
            return []
        if self.LOOPBACK_ORIGIN_RE.search(auth):
            return []
        listed = "trustedOrigins" in auth
        return [Finding(
            "blocker", "AUTH_ORIGIN",
            "Better Auth "
            + ("lists specific origins" if listed else "trusts only its baseURL")
            + ", so a request from the preview — which is served on a different "
              "port than the dev server — is answered 403 'Invalid origin'. "
              "Login and signup fail on the form with nothing in the log",
            path="lib/auth.js",
            fix="trustedOrigins: ['http://localhost:*', 'http://127.0.0.1:*'] "
                "— a pattern, because the port moves and localhost and "
                "127.0.0.1 are different origins. A remote origin is still "
                "refused.")]

    SESSION_IMPORT_RE = re.compile(
        r"""import\s*\{[^}]*\bgetSessionUser\b[^}]*\}\s*from\s*['"]@/lib/auth""")
    SESSION_ASSIGN_RE = re.compile(
        r"(?:const|let|var)\s+(\w+)\s*=\s*await\s+getSessionUser\s*\(")

    def session_user_id(self) -> list:
        """
        `user._id` on the object Better Auth returns, which has no `_id`.

        Measured against a running generated app: the session user is
        `{createdAt, email, emailVerified, id, name, role, updatedAt}` — `id`
        is a **string**, and `_id` is simply absent. So `user._id` is
        `undefined`, and every comparison against it is false while every
        document written with it stores `undefined`.

        Nothing else can see this. It compiles, the route returns 200 or a
        perfectly ordinary 403, and the page renders — it is only wrong for the
        user. Two real examples from one build: `appt.vetId.toString() !==
        user._id` meant no vet could ever record a visit, and `ownerId:
        user._id` meant a registered pet never appeared in its owner's list,
        because the list queries `{ownerId: user.id}`.

        Scoped to the variable actually assigned from `getSessionUser()`,
        because `._id` on a Mongo document is correct and common — a blanket
        search reports 43 occurrences across the corpus, of which 21 are real.
        """
        out = []
        for rel, body in sorted(self.code_files().items()):
            if not self.SESSION_IMPORT_RE.search(body):
                continue
            for var in dict.fromkeys(self.SESSION_ASSIGN_RE.findall(body)):
                n = len(re.findall(rf"\b{re.escape(var)}\s*\.\s*_id\b", body))
                if not n:
                    continue
                out.append(Finding(
                    "blocker", "SESSION_USER_ID",
                    f"reads `{var}._id` from Better Auth's session "
                    f"({n} time{'s' if n > 1 else ''}), which is always "
                    f"undefined — the session user's id is `{var}.id`, a "
                    f"string. Comparisons against it are never true and "
                    f"documents written with it store undefined",
                    path=rel,
                    fix=f"use `{var}.id` throughout. It is a string, so "
                        f"compare with `doc.someId?.toString() === {var}.id` "
                        f"and store `someId: new ObjectId({var}.id)` when the "
                        f"column holds an ObjectId."))
        return out

    def auth_completeness(self) -> list:
        """A login with no signup, or links between them that 404."""
        routes = self.enumerate_routes()
        pages = {u for u, r in routes.items() if r["kind"] == "page"}
        has_login = any("login" in u or "signin" in u for u in pages)
        if not has_login:
            return []

        managed = any(p.startswith("app/api/auth/[") for p in self.code_files())

        out = []
        if not any(w in u for u in pages for w in ("signup", "register")):
            out.append(Finding(
                "major", "NO_SIGNUP",
                "there is a login page but no way to create an account",
                fix="add app/signup/page.jsx — a client page calling "
                    "signUp.email() from @/lib/auth-client"
                    if managed else
                    "add app/signup/page.jsx and app/api/auth/register/route.js"))
        if managed:
            return out

        apis = {u for u, r in routes.items() if r["kind"] == "api"}
        if not any("register" in u or "signup" in u for u in apis):
            out.append(Finding(
                "major", "NO_REGISTER_API",
                "nothing handles account creation",
                fix="add app/api/auth/register/route.js"))
        return out

    CHROME_RE = re.compile(r"<\s*(Nav\w*|Navbar|Header|Sidebar|TopBar|AppShell)\b")

    def layout_chrome(self) -> list:
        """
        Navigation in the root layout.

        `app/layout.js` wraps every route, so a `<Navbar />` there also lands on
        the login and signup screens — a signed-out visitor sees links into
        pages they cannot open, and the auth screen is not the full-screen page
        it should be. Chrome belongs to the pages that want it.
        """
        out = []
        files = self.code_files()
        layout = next((p for p in ("app/layout.js", "app/layout.jsx")
                       if p in files), None)
        if not layout:
            return out
        body = files[layout]
        pages = {u for u, r in self.enumerate_routes().items()
                 if r["kind"] == "page"}
        has_auth = any(w in u for u in pages for w in ("login", "signin",
                                                       "signup", "register"))
        m = self.CHROME_RE.search(body)
        if m and has_auth:
            out.append(Finding(
                "major", "LAYOUT_CHROME",
                f"the root layout renders <{m.group(1)} />, so it appears on "
                f"the login and signup screens too",
                path=layout,
                fix="remove it from app/layout.js and render it in the pages "
                    "that want it; auth pages stay full-screen"))
        if "ensureSeeded" in body:
            out.append(Finding(
                "major", "SEED_IN_LAYOUT",
                "the root layout calls ensureSeeded(), so it runs on every "
                "request including API calls",
                path=layout,
                fix="seed from the pages that read the data instead"))
        return out

    def leaks_password_hash(self) -> list:
        """A login handler returning the whole user document."""
        out = []
        for path, content in self.code_files().items():
            if "route.js" not in path or "bcrypt" not in content:
                continue
            if re.search(r"Response\.json\(\s*\{\s*[^}]*\buser\s*(?:,|\})", content) \
                    and "passwordHash" not in content.split("Response.json")[-1]:

                if re.search(r"\buser\s*=\s*await\s+\w+\.findOne", content):
                    out.append(Finding(
                        "major", "HASH_LEAK",
                        "the response returns the whole user document, so "
                        "passwordHash is sent to the browser",
                        path=path,
                        fix="return only { id, email, name, role }"))
        return out

    def credential_smells(self) -> list:
        """
        Static hints about a broken login. Advisory only — the runtime probe
        decides, because a seed that builds emails from a template cannot be
        compared against a login page's literals.
        """
        out = []
        for path, content in self.code_files().items():
            for lit in BCRYPT_LITERAL_RE.findall(content):
                if len(lit) != 60:
                    out.append(Finding(
                        "blocker", "FAKE_HASH",
                        f"the string {lit[:24]}… is {len(lit)} characters; a "
                        f"bcrypt hash is exactly 60, so bcrypt.compare against "
                        f"it can never succeed and every login returns 401",
                        path=path,
                        fix="hash the real demo password at seed time with "
                            "bcrypt.hashSync(DEMO_PASSWORD, 10)"))
                    break
            if "seed" in path.lower() and "passwordHash" in content \
                    and "hashSync" not in content and "hash(" not in content:
                out.append(Finding(
                    "blocker", "UNHASHED_SEED",
                    "the seed sets passwordHash without ever calling bcrypt",
                    path=path,
                    fix="import bcrypt from 'bcryptjs' and use "
                        "bcrypt.hashSync(password, 10)"))
        return out

    def scan(self) -> AnalyzerReport:
        r = AnalyzerReport()
        r.planned = self.planned_paths()
        r.missing = self.missing_files()
        r.routes = self.enumerate_routes()
        r.dead_links = self.dead_links(r.routes)
        r.unresolved = self.unresolved_packages()

        plan_lines = self.plan_text().splitlines()
        for p in r.missing:
            why = next((ln.strip(" *-\t") for ln in plan_lines if f"`{p}`" in ln), "")
            stub = self._is_placeholder(p)
            r.findings.append(Finding(
                "blocker", "MISSING_FILE",
                "this is still the scaffold placeholder — the real page was "
                "never written" if stub else
                "the plan promises this file but it was never written",
                path=p,
                fix=(f"write it. The plan says: {why[:160]}" if why
                     else "write it, matching the plan")))

        for f in self.broken_imports():
            r.findings.append(f)

        r.findings.extend(self.async_param_confusion())
        r.findings.extend(self.session_cookie_mismatch())
        r.findings.extend(self.unique_index_in_seed())
        r.findings.extend(self.prop_contract_breaks())
        r.findings.extend(self.credentials_exposed())
        r.findings.extend(self.seed_volume())

        for url in self.dead_endpoints(r.routes):
            handler = "app" + url + "/route.js"
            r.findings.append(Finding(
                "blocker", "DEAD_ENDPOINT",
                f"something fetches {url} but no route handler serves it, so "
                f"the call 404s — a client component that redirects when the "
                f"fetch fails will bounce the user out of the page",
                fix=f"write {handler}",
                extra=[handler]))

        for url in r.dead_links:
            r.findings.append(Finding(
                "major", "DEAD_LINK",
                f"something links to {url} but no page serves it — a 404",
                fix=f"either create the page for {url} or remove the link"))

        for loc in self.stray_directives():
            r.findings.append(Finding(
                "blocker", "STRAY_DIRECTIVE",
                "a 'use client' directive appears after other code, which "
                "fails to compile",
                path=loc.split(":")[0],
                fix="split the file: the server half stays, the interactive "
                    "half moves to its own file under components/ with "
                    "'use client' on line 1"))

        for name in r.unresolved:
            r.findings.append(Finding(
                "blocker", "MISSING_PACKAGE",
                f"'{name}' is imported but not installed",
                fix=f"npm install {name}"))

        r.findings.extend(self.credential_smells())
        r.findings.extend(self.seed_race())
        r.findings.extend(self.stale_seed_guard())
        r.findings.extend(self.authz_redirect())
        r.findings.extend(self.seed_behind_auth())
        r.findings.extend(self.auth_origin())
        r.findings.extend(self.session_user_id())
        r.findings.extend(self.auth_completeness())
        r.findings.extend(self.layout_chrome())
        r.findings.extend(self.leaks_password_hash())

        try:
            seen = {f.path for f in r.findings}
            for problem in self.arch.lint_generated():
                path = problem.split(":")[0]
                if path in seen or "imported but not installed" in problem:
                    continue
                if any(problem.startswith(p) for p in r.missing):
                    continue
                r.findings.append(Finding("major", "LINT", problem))
        except Exception as e:
            log.warning(f"lint_generated failed: {e}")

        return r

    def find_login_endpoint(self) -> str:
        """
        The URL that verifies a password.

        Found by looking for `bcrypt.compare` rather than by guessing a path —
        that is what actually distinguishes a hand-rolled login handler, and it
        matched all three real auth projects on disk.

        Better Auth defeats all three of those tests at once, and it is what
        these apps are generated with. Its whole surface is one catch-all,
        `app/api/auth/[...all]/route.js`, which enumerates as
        `/api/auth/[...all]`: no `bcrypt.compare`, because the library does the
        comparing; no "login"/"signin" in the path, because the segment is
        literally `[...all]`; and no "password" in the body, because the file
        does nothing but delegate. So this returned "" for the app it was most
        likely to be pointed at, the browser reproduction went to the page
        anonymously, got the login redirect, and reported "nothing went wrong"
        about a page it never reached. Measured live on
        app-name-spoke-and-chain before this was added.
        """
        routes = self.enumerate_routes()
        api = {u: r for u, r in routes.items() if r["kind"] == "api"}
        files = self.source_files()

        for url, r in api.items():
            body = files.get(r["file"], "")
            if "bcrypt.compare" in body or "compareSync" in body:
                return url

        # `/api/auth/[...all]` + `/sign-in/email` — the path the catch-all's
        # own comment documents, and the one the login form posts to.
        for url, r in api.items():
            body = files.get(r["file"], "")
            if "better-auth" in body and "POST" in r["methods"]:
                base = re.sub(r"/\[\.\.\.[^\]]+\]$", "", url).rstrip("/")
                return f"{base}/sign-in/email"

        for url, r in api.items():
            if any(w in url.lower() for w in ("login", "signin", "authenticate")) \
                    and "POST" in r["methods"]:
                return url
        for url, r in api.items():
            if "POST" in r["methods"] and "password" in files.get(r["file"], ""):
                return url
        return ""

    def demo_credentials(self) -> list:
        """(email, password) pairs the app claims will work."""
        creds = []
        for a in (self.arch.plan or {}).get("demo_accounts", []) or []:
            if a.get("email") and a.get("password"):
                creds.append((a["email"], a["password"]))
        if creds:
            return creds

        section = re.search(r"^#+ Demo Accounts\s*$(.*?)(?=^#+ |\Z)",
                            self.plan_text(), re.M | re.S)
        if section:
            for line in section.group(1).splitlines():

                cells = [c.strip().strip("`*") for c in line.split("|")]
                if len(cells) > 2:
                    for i, c in enumerate(cells[:-1]):
                        if re.fullmatch(r"[\w.+-]+@[\w.-]+\.\w+", c):
                            nxt = cells[i + 1]
                            if re.fullmatch(r"[A-Za-z0-9!@#$%^&*_-]{6,}", nxt):
                                creds.append((c, nxt))
                            break
                    continue
                m = re.search(r"([\w.+-]+@[\w.-]+)\D+?([A-Za-z0-9!@#$%^&*_-]{6,})\s*$",
                              line)
                if m:
                    creds.append((m.group(1), m.group(2)))
        if creds:
            return creds

        creds = self._credentials_from_seed()
        if creds:
            return creds

        for path, content in self.code_files().items():
            if "login" not in path.lower() and "signin" not in path.lower():
                continue

            visible = re.sub(r"""placeholder\s*=\s*["'{][^"'}]*["'}]""", "",
                             content)
            emails = re.findall(r"[\w.+-]+@[\w.-]+\.\w+", visible)

            pw = re.search(
                r"[Pp]assword\b[^:<\n]{0,40}:\s*(?:<[^>]*>\s*)*"
                r"([A-Za-z0-9!@#$%^&*_-]{6,})",
                content)
            if emails and pw:
                creds = [(e, pw.group(1)) for e in dict.fromkeys(emails)]
                break
        return creds

    SEED_EMAIL_RE = re.compile(r"""email\s*:\s*['"]([\w.+-]+@[\w.-]+\.\w+)['"]""")
    SEED_PW_FIELD_RE = re.compile(
        r"""(?:password\s*:\s*['"]([^'"]{4,})['"]"""
        r"""|hashSync\s*\(\s*['"]([^'"]{4,})['"])""")
    SEED_PW_CONST_RE = re.compile(
        r"""\b\w*PASSWORD\w*\s*=\s*['"]([^'"]{4,})['"]""")

    SEED_INDIRECT_HASH_RE = re.compile(r"""hashSync\s*\(\s*[^'"\s)]""")

    def _credentials_from_seed(self) -> list:
        """
        Read the demo accounts out of `lib/seed.js`.

        This beats scraping the login page, and not only because the markup
        varies wildly — across the projects on disk the panel is a `<li>` with
        `email / password`, a two-column grid with the password in a sibling
        `<span>`, and a shared "Password for all demo accounts" footer. The seed
        is the ground truth: it is the value that actually gets hashed, so if
        the page and the seed ever disagree, the seed is the one that works.
        """
        seed = "\n".join(c for p, c in sorted(self.code_files().items())
                         if "seed" in p.lower())
        if not seed:
            return []
        hits = list(self.SEED_EMAIL_RE.finditer(seed))
        if not hits:
            return []

        if self.SEED_INDIRECT_HASH_RE.search(seed):
            return []

        creds = []
        for i, m in enumerate(hits):
            end = hits[i + 1].start() if i + 1 < len(hits) else len(seed)
            pw = self.SEED_PW_FIELD_RE.search(seed, m.end(), end)
            if not pw:
                creds = []
                break
            creds.append((m.group(1), pw.group(1) or pw.group(2)))
        if creds:
            return creds

        literals = {(a or b) for a, b in self.SEED_PW_FIELD_RE.findall(seed)}
        literals |= set(self.SEED_PW_CONST_RE.findall(seed))
        if len(literals) == 1:
            shared = literals.pop()
            return [(m.group(1), shared) for m in hits]
        return []

    def _announce_credentials(self, report: AnalyzerReport = None) -> list:
        """
        Hand the demo accounts to AgentForge's UI.

        The generated app no longer prints them on its login page, so this is
        the only way the developer learns them. Each account carries whether a
        real POST to the login route accepted it, so a stale or mis-attributed
        password shows as a failure rather than as a promise.
        """
        creds = self.demo_credentials()
        if not creds:
            return []
        roles = {a.get("email"): a.get("role", "")
                 for a in (self.arch.plan or {}).get("demo_accounts", []) or []}
        by_email = {c.get("email"): c.get("status")
                    for c in (report.credentials.get("checked") if report else []) or []}
        accounts = [{"email": e, "password": p, "role": roles.get(e, ""),
                     "status": by_email.get(e)}
                    for e, p in creds]
        source = ("plan" if (self.arch.plan or {}).get("demo_accounts")
                  else "project")
        self._fire("on_creds", accounts, source,
                   (report.credentials.get("ok") if report else None))
        return accounts

    def verify_credentials(self, report: AnalyzerReport) -> None:
        """
        POST the demo credentials at the running app.

        This is the only check that can catch a wrong password hash: a bad hash
        produces a 401, which is a perfectly valid HTTP response, so the build
        compiles, the page renders, and every other gate passes.
        """

        if any(f.code == "ROUTE_ERROR" for f in report.findings):
            report.credentials = {"checked": [], "ok": None,
                                  "reason": "pages are failing; login cannot "
                                            "be judged until they serve"}
            self._log("INFO", "   ⏭  Skipping the login check — pages are "
                              "still failing")
            return

        creds = self.demo_credentials()
        if not creds:
            report.credentials = {"checked": [], "ok": None,
                                  "reason": "no demo accounts"}
            return
        endpoint = self.find_login_endpoint()
        if not endpoint:
            report.credentials = {"checked": [], "ok": None,
                                  "reason": "no login endpoint"}
            report.findings.append(Finding(
                "major", "NO_LOGIN_ENDPOINT",
                "the plan lists demo accounts but no route handler verifies a "
                "password"))
            return

        url = self.base_url + endpoint
        checked, failures, unreachable = [], [], False
        for email, password in creds[:3]:
            status, body = self._post_json(url, {"email": email,
                                                 "password": password})
            if status == 400 and "username" in (body or "").lower():
                status, body = self._post_json(url, {"username": email,
                                                     "password": password})
            checked.append({"email": email, "status": status})
            if status is None:
                unreachable = True
                break
            self._fire("on_test", "pass" if status < 400 else "fail",
                       f"Login {email}", f"HTTP {status}")
            if status in (401, 403):
                failures.append((email, password, status, body))
            elif status >= 400:
                report.findings.append(Finding(
                    "major", "LOGIN_ERROR",
                    f"POST {endpoint} returned {status} for {email}: "
                    f"{(body or '')[:160]}"))

        if unreachable:
            report.credentials = {"checked": checked, "ok": None,
                                  "reason": "endpoint unreachable"}
            return

        report.credentials = {"endpoint": endpoint, "checked": checked,
                              "ok": not failures}
        for email, password, status, _ in failures:
            report.findings.append(Finding(
                "blocker", "BAD_CREDENTIALS",
                f"POST {endpoint} with the demo credentials the app advertises "
                f"({email} / {password}) returned {status} — bcrypt.compare "
                f"fails, so the seeded passwordHash does not correspond to "
                f"this password",
                path=self.enumerate_routes().get(endpoint, {}).get("file", ""),
                fix=f"seed passwordHash with bcrypt.hashSync('{password}', 10) "
                    f"for {email}. Do NOT display the credentials in the app — "
                    f"they are shown to the developer outside it"))

    @staticmethod
    def _post_json(url: str, payload: dict, timeout: int = 15):
        """(status, body). status is None when the server could not be reached."""
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read(2000).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            try:
                return e.code, e.read(2000).decode("utf-8", "replace")
            except Exception:
                return e.code, ""
        except Exception:
            return None, ""

    def probe_routes(self, report: AnalyzerReport) -> None:
        """
        GET every page *and* every GET API route the app serves.

        The tester samples five pages in alphabetical order; on a real project
        that skipped `/login`, `/orders`, `/products`, `/search` and `/signup`.
        Plain HTTP is sub-second per route, so there is no reason to sample.

        API routes matter as much as pages and used to be skipped entirely. A
        client component that fetches one and redirects when the fetch fails
        turns a broken endpoint into "the page flashes and throws me back to
        login" — while the page itself serves a perfectly good 200. Measured on
        a real project: 12 API routes, none of them probed, one of them 500ing.

        A 401 or 403 from an API route is not a fault: these run unauthenticated
        here, and refusing is the correct answer. Only 5xx and 404 are.
        """
        for url, r in sorted(report.routes.items()):
            if r["dynamic"]:
                continue
            is_api = r["kind"] == "api"
            if is_api and "GET" not in r.get("methods", []):
                continue
            status = self._get_status(self.base_url + url)
            if status is None:
                return
            bad = status >= 500 or status == 404 if is_api else status >= 400
            self._fire("on_test", "fail" if bad else "pass",
                       f"{'API' if is_api else 'Route'} {url}", f"HTTP {status}")
            if bad:
                report.findings.append(Finding(
                    "blocker", "ROUTE_ERROR",
                    f"{url} returns HTTP {status}",
                    path=r["file"],
                    fix=f"fix {r['file']} so {url} responds"))

    @staticmethod
    def _get_status(url: str, timeout: int = 60):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return None

    def inventory(self) -> str:
        """
        One line per file: enough to reason about the project without reading
        it. The model pulls the bodies it actually needs with `read_file`.
        """
        lines = []
        for path, content in sorted(self.code_files().items()):
            first = next((l.strip() for l in content.splitlines() if l.strip()), "")
            directive = "'use client'" if first.startswith(("'use client'", '"use client"')) else "server"
            exports = re.findall(
                r"export\s+(?:default\s+)?(?:async\s+)?(?:function|const)\s+(\w+)",
                content)
            if re.search(r"export\s+default\s+(?:async\s+)?function\s*\(", content):
                exports.append("default")
            pkgs = self.arch.imported_packages(content)
            lines.append(
                f"{path} · {len(content) // 1024 or 1}KB · {directive}"
                + (f" · exports {', '.join(exports[:4])}" if exports else "")
                + (f" · uses {', '.join(pkgs[:4])}" if pkgs else ""))
        for path in sorted(self.source_files()):
            if path.endswith(".css") or path == "package.json":
                lines.append(f"{path} · (not code)")
        return "\n".join(lines)

    def route_table(self, routes: dict) -> str:
        rows = []
        for url in sorted(routes):
            r = routes[url]
            m = "/".join(r["methods"]) if r["methods"] else "-"
            rows.append(f"{url}  →  {r['file']}  [{m}]")
        return "\n".join(rows)

    READ_RE = re.compile(r"<read_file\s+path\s*=\s*[\"']([^\"'>]+)[\"']\s*/?>", re.I)

    def _read_for_model(self, rel: str) -> str:
        """Serve one `read_file`. Refuses anything outside the project or secret."""
        try:
            fp = self.arch._safe_path(rel)
            key = str(fp.relative_to(self.project_dir)).replace("\\", "/")
        except Exception:
            return f"[refused: {rel} is not a path in this project]"
        if Path(key).name.startswith(".env"):
            return "[refused: environment files are not readable]"
        body = self.source_files().get(key)
        if body is None:
            if not fp.exists():
                return f"[{rel} does not exist]"
            return f"[refused: {rel} is not a source file]"
        return body

    def _budget_chars(self) -> int:
        """Scale the read loop to whatever model the build is using."""
        return int(getattr(self.arch, "num_ctx", 16384) * 0.55 * 3.4)

    def diagnose(self, report: AnalyzerReport, max_reads: int = 12) -> list:
        """
        Ask the model what the deterministic pass cannot see: whether the app
        actually does what the plan describes. Runs on its own message list via
        `arch._stream`, so the build conversation is untouched.
        """
        system = (
            "You are auditing a finished Next.js 16 App Router + MongoDB "
            "project against the plan it was built from.\n\n"
            "You are given the plan, an inventory of every source file, the "
            "routes the app serves, and the problems a static checker already "
            "found. To read a file, emit exactly:\n"
            "<read_file path=\"lib/seed.js\"/>\n"
            "One per line; you will be given the contents and may then read "
            "more.\n\n"
            "Look for things a checker cannot: features the plan promises that "
            "no code implements, a collection the Data Model describes that "
            "nothing ever reads, a page that renders nothing real, seed data "
            "that does not match the plan.\n\n"
            "When finished, output one line per problem, nothing else:\n"
            "FINDING <blocker|major|minor> <path-or-> :: <what is wrong>\n"
            "If the project matches its plan, output exactly: FINDING none - :: ok")

        user = (f"## The plan\n{self.plan_text()}\n\n"
                f"## Files\n{self.inventory()}\n\n"
                f"## Routes served\n{self.route_table(report.routes)}\n\n"
                f"## Already found by the static checker\n"
                f"{report.as_prompt_block() or '(nothing)'}\n\n"
                f"Read what you need, then report.")

        convo = [{"role": "system", "content": system},
                 {"role": "user", "content": user}]
        budget = self._budget_chars()
        findings, reads = [], 0

        while True:
            buf = []
            try:
                self.arch._stream(convo, buf.append, temperature=0.3)
            except Exception as e:
                self._log("WARN", f"   ⚠ Analyzer query failed: {e}")
                break
            reply = "".join(buf)
            convo.append({"role": "assistant", "content": reply})

            wanted = self.READ_RE.findall(reply)
            used = sum(len(m["content"]) for m in convo)
            if wanted and reads < max_reads and used < budget:
                served = []
                for rel in wanted[:4]:
                    reads += 1
                    served.append(f"--- {rel} ---\n{self._read_for_model(rel)}")
                self._log("INFO", f"   📖 read {', '.join(wanted[:4])}")
                convo.append({"role": "user", "content": "\n\n".join(served)})
                continue

            for line in reply.splitlines():
                m = re.match(r"\s*FINDING\s+(\w+)\s+(\S+)\s*::\s*(.+)", line)
                if not m:
                    continue
                sev, path, msg = m.group(1).lower(), m.group(2), m.group(3).strip()
                if sev == "none":
                    break
                if sev not in SEVERITIES:
                    sev = "minor"
                findings.append(Finding(sev, "REVIEW", msg,
                                        path=("" if path == "-" else path)))
            break

        if findings:
            self._log("INFO", f"   🔍 Model reported {len(findings)} extra "
                              f"problem(s)")
        return findings

    SELF_DESTRUCTURE_RE = re.compile(
        r"const\s*\{\s*(params|searchParams)\s*:\s*\w+[^}]*\}\s*=\s*await\s+\1\b")

    def async_param_confusion(self) -> list:
        """
        `const { searchParams: x } = await searchParams` — a guaranteed 500.

        Next 15 handed pages a plain object and 16 hands them a Promise, and
        this is what the confusion looks like when a model half-applies the
        change: it awaits correctly, then reaches for a key that is not there.
        `x` is `undefined` and the next property read throws.

        Verified in node, and verified invisible: `next build` compiles it, and
        a route behind a login is never reached by the probe. It was produced
        by a real repair pass on `app/admin/page.js`, which is why it exists.

        Zero false positives by construction — no query string has a `params`
        or `searchParams` key of its own, and if one did, reading it this way
        would still be a mistake.
        """
        out = []
        for path, content in sorted(self.code_files().items()):
            for m in self.SELF_DESTRUCTURE_RE.finditer(content):
                name = m.group(1)
                line = content[:m.start()].count("\n") + 1
                out.append(Finding(
                    "blocker", "ASYNC_PARAM_CONFUSION",
                    f"line {line} does `const {{ {name}: … }} = await {name}` — "
                    f"awaiting `{name}` already yields the object, so this pulls "
                    f"a `{name}` key that does not exist and the result is "
                    f"undefined. The first property read on it throws, which is "
                    f"a 500 on a page that compiles",
                    path=path,
                    fix=f"`const {{ … }} = await {name}` — destructure the keys "
                        f"you actually want straight out of it"))
        return out

    def orphan_components(self) -> list:
        """
        Components under `components/` that no file imports.

        Not a finding on its own — measured across the corpus there are 45, and
        most are `EmptyState` / `LoadingSpinner` that a model writes on spec and
        never needs. Reporting them directly would repeat the `date-fns`
        mistake. Exposed only as evidence for `unbuilt_promises`, where the plan
        decides whether an orphan means a dropped feature.
        """
        files = self.code_files()
        names = {Path(p).stem for p in files if p.startswith("components/")}
        blob = "\n".join(files.values())
        return sorted(
            n for n in names
            if not re.search(r"""from\s+['"][^'"]*/""" + re.escape(n) + r"""['"]""",
                             blob))

    PROMISE_RE = re.compile(
        r"PROMISE:\s*(.+?)\s*\n\s*FILE:\s*([^\n]+?)\s*\n\s*MISSING:\s*(.+?)(?=\n\s*PROMISE:|\Z)",
        re.S)

    @staticmethod
    def _norm(s: str) -> str:
        """Whitespace- and punctuation-insensitive, for quote matching."""
        return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

    def unbuilt_promises(self, max_reads: int = 10) -> list:
        """
        Behaviour the plan promised in prose that no file actually implements.

        This is the gap every other check leaves open. `planned_paths()` asks
        "does the file exist"; nothing asks "does it do what the plan said".
        Measured on a real build: the plan promised *"a sales dashboard with
        date-range filters driven by the URL"*, `app/admin/page.js` was written,
        served HTTP 200, contained zero `searchParams`, and the scan reported
        "no problems found".

        A deterministic version of this does not exist, and I tried: the
        obvious proxy — a dependency the plan asked for that nothing imports —
        is worthless in both directions. `date-fns` is unimported in 7 of 16
        projects with no feature missing, and in the very project that dropped
        the date filter it *was* imported, for formatting. So this asks the
        model.

        The anti-hallucination guard is the point: every finding must quote the
        promise **verbatim from plan.md** and name a file that exists. A model
        inventing a requirement fails both tests and is dropped in Python, so
        the worst case is silence rather than the repair pass rewriting working
        code to satisfy something nobody asked for.
        """
        plan = self.plan_text()
        if not plan.strip():
            return []
        files = self.code_files()
        if not files:
            return []

        orphans = self.orphan_components()
        hint = (f"\n\n## Components that exist but nothing renders\n"
                f"{', '.join(orphans[:12])}\n"
                f"Each one is either a dropped feature or harmless scaffolding "
                f"— the plan decides which.\n" if orphans else "")

        messages = [
            {"role": "system", "content":
                "You audit a finished Next.js App Router app against the plan "
                "it was built from. You are looking for ONE thing: behaviour "
                "the plan promised in prose that the code does not implement.\n\n"
                "Not style. Not missing files — another check owns those. Not "
                "polish. Only a specific, named capability the plan committed "
                "to and the code lacks.\n\n"
                "Read files before judging:\n"
                "  <read_file path=\"app/admin/page.js\"/>\n"
                "Up to 4 per reply. Read the file that would hold the feature "
                "before claiming it is absent — a promise implemented somewhere "
                "you did not look is the mistake that makes this audit useless.\n\n"
                "When done, output one block per finding, nothing else:\n"
                "  PROMISE: <the exact sentence or bullet from the plan, copied "
                "character for character>\n"
                "  FILE: <the one project-relative file that should implement it>\n"
                "  MISSING: <what specifically is not there, in one sentence>\n\n"
                "The PROMISE must be copied verbatim from the plan — a quote "
                "that is not in the plan is discarded. If everything the plan "
                "promised is implemented, output exactly: NONE"},
            {"role": "user", "content":
                f"## The plan\n{plan[:14000]}\n\n"
                f"## Files on disk\n{self.inventory()[:6000]}{hint}\n\n"
                "Read what you need, then report."},
        ]

        reads, used, out = 0, 0, ""
        budget = self._budget_chars()
        while True:
            chunks = []
            try:
                self.arch._stream(messages, lambda t: chunks.append(t),
                                  temperature=0.2)
            except Exception as e:
                self._log("WARN", f"   promise audit failed: {e}")
                return []
            out = "".join(chunks)
            messages.append({"role": "assistant", "content": out})
            used += len(out)

            wanted = [p for p in self.READ_RE.findall(out)][:4]
            if not (wanted and reads < max_reads and used < budget):
                break
            served = [f"--- {p} ---\n{self._read_for_model(p)}" for p in wanted]
            reads += len(wanted)
            used += sum(len(s) for s in served)
            messages.append({"role": "user",
                             "content": "\n\n".join(served) + "\n\nContinue."})

        if "NONE" in out and not self.PROMISE_RE.search(out):
            return []

        plan_norm = self._norm(plan)
        findings = []
        for promise, path, missing in self.PROMISE_RE.findall(out):
            promise, path = promise.strip().strip("`\"'"), path.strip().strip("`")

            if len(self._norm(promise)) < 25:
                continue
            if self._norm(promise) not in plan_norm:
                self._log("INFO", f"   ↯ dropped an invented promise: "
                                  f"{promise[:60]}")
                continue
            if path not in files:
                self._log("INFO", f"   ↯ dropped a promise naming no real "
                                  f"file: {path}")
                continue
            findings.append(Finding(
                "major", "UNBUILT_PROMISE",
                f"the plan promises “{promise[:180]}” but "
                f"{missing.strip()[:200]}",
                path=path,
                fix=f"implement it in {path}, changing nothing else",
                extra=[path]))
            if len(findings) >= 5:
                break
        return findings

    def repair(self, report: AnalyzerReport, server_log: str = "") -> int:
        """
        Write the missing files.

        `server_log` is whatever the dev server printed while the failing
        requests were being made. A route finding says only "returned HTTP
        500"; the trace says `at Inventory (app/inventory/page.js:86:48)`.
        Passing it turns a guess into a fix.

        The write path is allowlisted: only paths the deterministic pass said
        are missing, or that carry a blocker, are accepted. Without that a
        model handed a whole project and told to "fix what's missing" will
        cheerfully rewrite files that were already correct — which would make
        this feature a net loss.
        """
        allowed = set(report.missing)
        allowed |= {f.path for f in report.findings
                    if f.severity == "blocker" and f.path}

        allowed |= {p for f in report.findings
                    if f.severity == "blocker" for p in f.extra}

        allowed |= {p for f in report.findings
                    if f.code == "UNBUILT_PROMISE" for p in f.extra}
        if not allowed:
            return 0

        files = self.source_files()

        helpers = sorted(p for p in files
                         if p.startswith("lib/") and p.endswith((".js", ".jsx")))

        helpers.sort(key=lambda p: ("seed" in p, p))
        context = []
        for helper in ["app/layout.js"] + helpers:
            body = files.get(helper)
            if body:
                budget = 1500 if "seed" in helper else 4000
                context.append(f"--- {helper} ---\n{body[:budget]}")

        rewrites = []
        for p in sorted(allowed):
            body = files.get(p)
            if body:
                rewrites.append(f"--- {p} (rewrite this, preserving everything "
                                f"that already works) ---\n{body[:6000]}")

        blockers = [f for f in report.findings
                    if f.severity == "blocker" or f.code == "UNBUILT_PROMISE"]
        listing = "\n".join(f"  • {p}" + ("  (exists — edit it)" if p in files
                                          else "  (new)")
                            for p in sorted(allowed))

        guidance = nextdocs.guidance_for(
            server_log + "\n" + "\n".join(f.message for f in blockers))

        user = (f"## The plan\n{self.plan_text()}\n\n"
                f"## Files that already exist\n{self.inventory()}\n\n"
                f"## Existing code you must integrate with\n"
                f"{chr(10).join(context)}\n\n"
                + (f"## Current contents of the files you are editing\n"
                   f"{chr(10).join(rewrites)}\n\n" if rewrites else "")
                + (f"## What the server printed while these requests failed\n"
                   f"```\n{server_log.strip()[-4000:]}\n```\n"
                   f"The frames above name the exact file and line. Fix what "
                   f"they point at, not what you assume the problem is.\n\n"
                   if server_log.strip() else "")
                + (guidance + "\n\n" if guidance else "")
                + f"## Problems to fix\n"
                f"{chr(10).join('  • ' + f.line() + (chr(10) + '    → ' + f.fix if f.fix else '') for f in blockers[:20])}\n\n"
                f"Write these files, complete, and NOTHING else:\n{listing}\n\n"
                + ("For a file listed as (exists — edit it), keep everything it "
                   "already does and ADD what is missing. Deleting working "
                   "behaviour, or returning it unchanged, both count as "
                   "failure.\n\n" if rewrites else "")
                + f"Reuse the helpers above rather than reimplementing them — "
                f"import the session, database and permission functions that "
                f"already exist. Do not invent a second cookie name, a second "
                f"MongoClient or a parallel auth check.\n\n"
                f"One <write_file path=\"…\"> block per file.")

        convo = [{"role": "system", "content": self.arch._builder_sys()},
                 {"role": "user", "content": user}]

        written, rejected = [], []

        def on_end(path, content):
            key = (path or "").strip().lstrip("./").replace("\\", "/")

            fresh = (key.endswith((".jsx", ".js"))
                     and key.startswith(("components/", "app/", "lib/"))
                     and key not in self.arch.files
                     and not (self.project_dir / key).exists())
            if key not in allowed and not fresh:
                rejected.append(key)
                self._log("WARN", f"   ⛔ {key} is not on the repair list — skipped")
                return
            if fresh and key not in allowed:
                self._log("INFO", f"   ➕ {key} — new file the repair needs")
            self._fire("on_file_start", key)
            self._fire("on_file_end", key, content)
            if self.arch.write_file(key, content):
                written.append(key)

        parser = FileStreamParser(
            on_text=lambda t: None,
            on_file_start=lambda p: None,
            on_file_token=lambda t: None,
            on_file_end=on_end)

        try:
            self.arch._stream(convo, parser.feed, temperature=0.4)
        except Exception as e:
            self._log("ERROR", f"   ❌ Analyzer repair failed: {e}")
        parser.close()

        if rejected:
            self._log("WARN", f"   ⛔ Refused {len(rejected)} write(s) outside "
                              f"the repair list")
        self._files_cache = None
        report.written += len(written)
        return len(written)

    def run(self, *, use_model: bool = True, max_rounds: int = 2) -> AnalyzerReport:
        """
        Scan, then repair, then re-scan — stopping as soon as it stops helping.
        """
        self._fire("on_phase", {"phase": -5, "title": "Analyzing project",
                                "status": "active"})
        report = self.scan()
        self._log("INFO", f"🔍 Analyzer: {len(report.planned)} files planned, "
                          f"{len(report.routes)} routes served — {report.summary()}")
        for f in report.findings[:8]:
            self._log("WARN", f"   • {f.line()[:150]}")

        # What the build got wrong is what this FIRST scan found. Recording the
        # report at the end instead would record only what the repair loop
        # failed to fix — so the faults the loop is good at, which are exactly
        # the ones worth teaching the next build not to make, would never be
        # learned from at all.
        first_findings = list(report.findings)

        if use_model and self.unresolved_packages():
            pkgs = " ".join(self.unresolved_packages())
            self._log("INFO", f"   📦 Installing {pkgs}")
            self.cmd.run(f"npm install {pkgs}")
            self._files_cache = None

        if use_model and not report.blockers():
            promises = self.unbuilt_promises()
            if promises:
                report.findings.extend(promises)
                self._log("INFO", f"   📋 {len(promises)} promise(s) in the plan "
                                  f"with no implementation")
                for f in promises:
                    self._log("WARN", f"   • {f.line()[:150]}")

        rounds = 0
        while use_model and report.blockers() and rounds < max_rounds:
            rounds += 1
            before = len(report.blockers())
            n = self.repair(report)
            if not n:
                break
            self._log("INFO", f"   ✍️  Wrote {n} file(s)")
            report = self.scan()
            report.written = n

            if len(report.blockers()) >= before:
                break

        self._fire("on_phase", {"phase": -5, "title": "Analyzing project",
                                "status": "done", "written": report.written})
        self._log("INFO", f"🔍 Analyzer done — {report.summary()}")

        # What this build got wrong, kept where the next one will be told.
        # Everything above already had a stable `code` and a `fix` sentence;
        # they were used to repair this project and then thrown away, which is
        # how "13 of 13 seeded projects have this" happened — the check caught
        # it every time and nothing ever taught the builder.
        try:
            from . import lessons
            lessons.record(self.project_dir.name,
                           lessons.from_findings(first_findings))
        except Exception as e:                                  # noqa: BLE001
            log.debug(f"lessons: {e}")
        return report

    def run_runtime(self, mongo=None, node_bin: str = "node",
                    use_model: bool = True, dev_log=None) -> AnalyzerReport:
        """
        The checks that need the app actually running.

        Probes every page, then verifies the demo login really works. A wrong
        password hash cannot be seen any other way, and fixing it takes two
        steps: rewrite the seed, then drop the database — because the generated
        `ensureSeeded()` refuses to run while rows already exist.

        `dev_log` is an optional callable returning whatever the dev server has
        printed since the probe started. AgentForge passes one; it carries the
        stack frames that turn "HTTP 500" into a file and a line.
        """
        self._fire("on_phase", {"phase": -5, "title": "Verifying app",
                                "status": "active"})
        report = self.scan()
        self.probe_routes(report)
        self.verify_credentials(report)
        self._announce_credentials(report)

        bad_login = [f for f in report.findings if f.code == "BAD_CREDENTIALS"]
        if bad_login and use_model:
            self._log("WARN", "   🔑 Demo login is rejected — repairing the seed")
            seed = next((p for p in self.source_files() if "seed" in p.lower()
                         and p.endswith((".js", ".jsx"))), "lib/seed.js")
            report.missing = []
            for f in bad_login:
                f.path = f.path or seed

            report.findings.append(Finding("blocker", "BAD_CREDENTIALS",
                                           "rewrite the seed so the demo "
                                           "password hashes correctly",
                                           path=seed))
            self.repair(report, server_log=(dev_log() if dev_log else ""))

            if self.allow_reseed and mongo is not None:
                res = mongo.reset_project_db(self.project_dir, node_bin=node_bin)
                if res.get("ok"):
                    self._fire("on_mongo", {"state": "reset",
                                            "db": res.get("db", "")})

                    self._get_status(self.base_url + "/")
                    again = self.scan()
                    self.verify_credentials(again)
                    again.written = report.written
                    report = again
                    if again.credentials.get("ok"):
                        self._log("INFO", "   ✅ Demo login works after re-seed")
                else:
                    self._log("WARN", f"   ⚠ Could not reset the database: "
                                      f"{res.get('error')}")
            elif not self.allow_reseed:
                self._log("WARN", "   ⚠ The seed was corrected, but the existing "
                                  "demo rows block it from running. Reset is "
                                  "disabled for this project.")

        self._fire("on_phase", {"phase": -5, "title": "Verifying app",
                                "status": "done"})
        self._log("INFO", f"🔍 Verification — {report.summary()}")
        return report
