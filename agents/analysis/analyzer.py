"""Checks a finished app against its plan and observed behavior."""
from __future__ import annotations

import http.cookiejar
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from agents.core import nextdocs
from agents.core.commands import CommandRunner
from agents.core.exports_checks import check_default_imports, check_named_imports
from agents.core.exports_common import FRAMEWORK_EXPORTS, strip_noncode as _strip_noncode
from agents.core.exports_parse import parse_imports, resolve_local
from agents.core.exports_syntax import check_syntax
from agents.core.workspace import TOOL_HELP, WorkspaceTools
from agents.planner.architecture import FileStreamParser

log = logging.getLogger("analyzer")
SKIP_DIRS = {"node_modules", ".git", ".next", "dist", "out", ".vite", ".agentforge", ".turbo", "public", "coverage"}
SOURCE_EXT = {".js", ".jsx", ".mjs", ".css", ".json", ".md"}
CODE_EXT = {".js", ".jsx", ".mjs"}
NEXT_ROOTS = ("app/", "components/", "lib/")
ROOT_SOURCE = {"middleware.js", "middleware.jsx", "instrumentation.js"}
MAX_FILE_BYTES = 200_000
SEVERITIES = ("blocker", "major", "minor")
REPAIRABLE_MAJOR = frozenset({"UNBUILT_PROMISE", "BROKEN_CONTRACT", "MISSING_PLANNED_DATA", "INERT_CONTROL", "ROLE_REDIRECT", "ROLE_HOME_MISSING", "ROLE_PAGE_UNGUARDED", "MISSING_WORKFLOW_CONTROL", "SEED_IN_LAYOUT", "LINT", "DEAD_LINK"})
PROSE_PATH_RE = re.compile(r"`((?:app|components|lib)/[^`]+?\.jsx?)`")
PLACEHOLDER_RE = re.compile(r"[*?<>\s]|\.\.\.")
LINK_HREF_RE = re.compile(r"""<Link\b[^>]*?href\s*=\s*(?:["'](/[^"']*)["']|\{\s*["'](/[^"']*)["']\s*\})""")
ROUTER_PUSH_RE = re.compile(r"""(?:router\.(?:push|replace)|redirect)\(\s*["'](/[^"']*)["']""")
FETCH_URL_RE = re.compile(r"""fetch\(\s*['"](/api/[A-Za-z0-9_\-/\[\]]*)['"]""")
BCRYPT_LITERAL_RE = re.compile(r"""["'](\$2[aby]?\$\d\d\$[^"']*)["']""")
HTTP_METHOD_RE = re.compile(r"export\s+(?:async\s+)?(?:function\s+|const\s+)(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b")
PROMPT_FILE = Path(__file__).with_name("analysis_prompt.md")

# What the model is asked to go looking for. Written as instructions rather than
# category labels: the deterministic checks below only find the faults someone
# already thought to encode, and the ones that actually reach a served page —
# a missing import, a serialized date, an id that is not an ObjectId — are the
# ones no fixed list caught.
SEMANTIC_LENSES = (
    "Walk each accepted capability from its entry route to the outcome the user "
    "is supposed to see. Does a real control exist, does it reach a handler, "
    "does the handler persist, and does the page show the result without a "
    "manual refresh?",

    "Ask what each planned page does when the data is empty, when the request "
    "fails, and when a field is missing from a row. Look for a value used before "
    "it exists, and for a response rendered as a list when the handler can also "
    "return an object or an error.",

    "Read the source for what throws the moment the page is opened: a component "
    "or helper used without its import, a date or number method called on a "
    "value that arrives serialized as a string, and an id passed to ObjectId "
    "when the seed identifies that collection some other way.",

    "Follow identity and authorization: who the session says the user is, which "
    "routes read it, what a wrong-role visitor actually sees, and whether "
    "sign-in, sign-out and the seeded demo identities work end to end.",
)


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str = ""
    fix: str = ""
    extra: list = field(default_factory=list)

    def line(self) -> str:
        return f"[{self.severity}] " + (f"{self.path}: " if self.path else "") + self.message


@dataclass
class AnalyzerReport:
    findings: list = field(default_factory=list)
    planned: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    routes: dict = field(default_factory=dict)
    dead_links: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)
    credentials: dict = field(default_factory=dict)
    runtime_examples: dict = field(default_factory=dict)
    written: int = 0

    def blockers(self): return [f for f in self.findings if f.severity == "blocker"]
    def is_clean(self): return not self.blockers()
    def summary(self):
        if not self.findings: return "no problems found"
        by = {s: sum(f.severity == s for f in self.findings) for s in SEVERITIES}
        return ", ".join(f"{n} {s}" for s, n in by.items() if n)
    def as_prompt_block(self, limit=25):
        rows = []
        for n, f in enumerate(sorted(self.findings, key=lambda x: SEVERITIES.index(x.severity))[:limit], 1):
            rows.append(f"{n}. {f.line()}")
            if f.fix: rows.append(f"   → {f.fix}")
        if len(self.findings) > limit: rows.append(f"… and {len(self.findings)-limit} more")
        return "\n".join(rows)


class AnalyzerAgent:
    """Compare the finished app with its plan and runtime evidence."""
    PLACEHOLDER_MARKERS = ("Building…", "Building&hellip;", "Building...")
    ALWAYS_CHECKED = ("app/page.jsx", "app/page.js")
    _UNAWAITED_RE = re.compile(r"(?<!await\s)(?<!await)\b(getCollection|getDb|getSessionUser)\s*\([^()]*\)\s*\.\s*([A-Za-z_$][\w$]*)")
    _OID_RE = re.compile(r"\bnew\s+ObjectId\s*\(\s*([^)]{1,80}?)\s*\)")
    _SELF_PARAMS_RE = re.compile(r"const\s*\{\s*(params|searchParams)\s*:\s*\w+[^}]*\}\s*=\s*await\s+\1\b")
    _DIRECT_PARAMS_RE = re.compile(r"(?:function|=>)[^{]{0,300}\{\s*params\s*\}[^\n{]*\{[\s\S]{0,1200}?\bparams\.")
    _CLIENT_RE = re.compile(r"^\s*(?:(?://[^\n]*\n)|(?:/\*.*?\*/\s*))*['\"]use client['\"]", re.S)
    _EVENT_RE = re.compile(r"\bon(?:Click|Change|Submit|Select|Blur|Focus|Key\w*|Mouse\w*|Pointer\w*|Drag\w*|Drop|Input|Toggle|Close|Open|Save|Delete|Update|Create)\s*=", re.I)

    def __init__(self, arch, project_dir=None, *, base_url="http://localhost:5173", callbacks=None, allow_reseed=False):
        self.arch, self.project_dir = arch, Path(project_dir or arch.project_dir)
        self.base_url, self.cb, self.allow_reseed = base_url.rstrip("/"), callbacks or {}, allow_reseed
        self.cmd = CommandRunner(self.project_dir, npm_bin=self.cb.get("npm_bin", "npm"), node_bin=self.cb.get("node_bin", "node"), on_log=lambda a, b: self._fire("on_log", a, b), on_event=lambda e: self._fire("on_command", e))
        self._files_cache, self._cache_seq, self._rewritten_this_stage = None, -1, set()
        self._semantic_cache = {}

    def _fire(self, name, *args):
        fn = self.cb.get(name)
        if callable(fn):
            try: fn(*args)
            except Exception as exc: log.warning("callback %s failed: %s", name, exc)
    def _log(self, level, text):
        self._fire("on_log", level, text) if callable(self.cb.get("on_log")) else log.info(text)

    def source_files(self, refresh=False):
        seq = getattr(self.arch, "write_seq", 0)
        if self._files_cache is not None and not refresh and seq == self._cache_seq: return self._files_cache
        out = {}
        for fp in sorted(self.project_dir.rglob("*")):
            if not fp.is_file() or any(p in SKIP_DIRS for p in fp.parts): continue
            if fp.suffix not in SOURCE_EXT or fp.name.startswith(".env") or fp.name in {"package-lock.json", "test_screenshot.png"}: continue
            try:
                if fp.stat().st_size <= MAX_FILE_BYTES: out[fp.relative_to(self.project_dir).as_posix()] = fp.read_text("utf-8", errors="replace")
            except OSError: pass
        self._files_cache, self._cache_seq = out, seq
        return out

    def _auth_invariants(self):
        files, plan, out = self.code_files(), getattr(self.arch, "plan", None) or {}, []
        auth, routes = files.get("lib/auth.js", ""), self.enumerate_routes()
        if "betterAuth(" in auth:
            seeds = {p: b for p, b in files.items() if "seed" in p.lower()}
            accounts = [a for a in plan.get("demo_accounts") or [] if isinstance(a, dict) and a.get("email") and a.get("password")]
            if accounts and not any(re.search(r"\b(?:auth\.api\.signUpEmail|ensureDemoAccounts)\s*\(", b) for b in seeds.values()): out.append(Finding("blocker", "BETTER_AUTH_DEMO_SEED", "planned demo users bypass Better Auth's credential provider, so sign-in/email returns 401", next(iter(seeds), "lib/seed.js"), "idempotently create every demo identity through auth.api.signUpEmail, then update that exact user's role", ["lib/auth.js"]))
            origins = set(re.findall(r"(?:https?://)?(localhost:\*|127\.0\.0\.1:\*)", auth))
            if origins != {"localhost:*", "127.0.0.1:*"}: out.append(Finding("blocker", "AUTH_ORIGIN", "Better Auth does not trust both loopback preview hosts on moving ports", "lib/auth.js", "trust http://localhost:* and http://127.0.0.1:* only"))
            provider = files.get("app/api/auth/[...all]/route.js", "")
            if not provider or not all(x in provider for x in ("GET", "POST")): out.append(Finding("blocker", "AUTH_PROVIDER_ROUTE", "Better Auth has no complete GET/POST catch-all provider route", "app/api/auth/[...all]/route.js", "delegate GET and POST to the auth instance exported by lib/auth.js"))
            access = plan.get("roles_and_access") or {}
            signup_open = str(access.get("signup") or "").strip().lower() == "open"
            signup = next((m for u, m in routes.items()
                           if u in {"/sign-up", "/signup", "/register"}), None)
            signup_body = files.get(signup["file"], "") if signup else ""
            if signup_open and "signUp.email" not in signup_body:
                out.append(Finding(
                    "blocker", "AUTH_SIGNUP_MISSING",
                    "open registration has no page completing Better Auth email signup",
                    signup["file"] if signup else "app/sign-up/page.jsx",
                    "serve an accessible form using signUp.email with failure and success states"))
        for target in self.dead_links(routes):
            if target in {"/sign-in", "/signin", "/login"}: out.append(Finding("blocker", "AUTH_PAGE_MISSING", f"auth code links or redirects to {target}, but no page serves it", f"app/{target.strip('/')}/page.jsx", "create the complete sign-in page using @/lib/auth-client, or consistently use a served auth page"))
        for rel, body in files.items():
            for var in re.findall(r"(?:const|let|var)\s+(\w+)\s*=\s*await\s+getSessionUser\s*\(", body):
                if re.search(rf"\b{re.escape(var)}\s*\.\s*_id\b", body): out.append(Finding("blocker", "SESSION_USER_ID", f"reads {var}._id from a Better Auth session; the string id is {var}.id", rel, f"use {var}.id and convert only at the Mongo boundary"))
            if re.search(r"if\s*\([^)]*(?:role|permission)[^)]*\)[\s\S]{0,100}redirect\(\s*['\"]/(?:login|sign-in)", body, re.I): out.append(Finding("blocker", "AUTHZ_REDIRECT", "a wrong-role signed-in user is redirected back to the sign-in page", rel, "separate no-session and wrong-role redirects"))
            seed, redirect = body.find("ensureSeeded("), body.find("redirect(")
            if seed >= 0 and 0 <= redirect < seed: out.append(Finding("blocker", "SEED_BEHIND_AUTH", "ensureSeeded runs after an auth redirect and cannot create the first demo identity", rel, "seed before reading the session"))
        return out + self.role_contract_findings() + self.role_page_findings() + self.auth_flow_findings()

    def role_contract_findings(self):
        plan, out = getattr(self.arch, "plan", None) or {}, []
        accounts = [a for a in plan.get("demo_accounts") or [] if isinstance(a, dict)]
        required = {self._role_key(a.get("role")) for a in accounts if a.get("role")}
        for flow in plan.get("workflows") or []:
            if isinstance(flow, dict):
                role = self._role_key(flow.get("who"))
                if role not in {"", "public", "visitor", "anonymous", "signedout"}: required.add(role)
        for phase in plan.get("phases") or []:
            for item in phase.get("files") or []:
                if isinstance(item, dict) and (m := re.match(r"\s*ROLE\s+([^—:-]+)", str(item.get("purpose") or ""), re.I)): required.update(self._role_key(x) for x in self._role_values(m.group(1)))
        by_role, by_email = {}, {}
        for account in accounts:
            role, email = self._role_key(account.get("role")), str(account.get("email") or "").lower()
            if role and email: by_role.setdefault(role, []).append(account); by_email.setdefault(email, set()).add(role)
        if len(required) < 2: return []
        for role in sorted(required - set(by_role)): out.append(Finding("blocker", "ROLE_ACCOUNT_CONTRACT", f"planned signed-in role '{role}' has no unique demo identity", "lib/seed.js", "seed one Better Auth demo account for this exact canonical role"))
        for role, rows in by_role.items():
            if len(rows) != 1: out.append(Finding("blocker", "ROLE_ACCOUNT_CONTRACT", f"role '{role}' has {len(rows)} demo identities; exactly one is required", "lib/seed.js", "keep one unique email/password per role"))
        for email, roles in by_email.items():
            if len(roles) > 1: out.append(Finding("blocker", "ROLE_ACCOUNT_CONTRACT", f"demo email {email} is assigned to multiple roles", "lib/seed.js", "use a distinct identity per role"))
        return out

    def role_page_findings(self):
        plan, files, out = getattr(self.arch, "plan", None) or {}, self.code_files(), []
        if len([a for a in plan.get("demo_accounts") or [] if isinstance(a, dict) and a.get("role")]) < 2: return []
        for phase in plan.get("phases") or []:
            for item in phase.get("files") or []:
                if not isinstance(item, dict): continue
                path = str(item.get("path") or ""); match = re.match(r"\s*ROLE\s+([^—:-]+)", str(item.get("purpose") or ""), re.I)
                if not match or path not in files or not self._route_from_page_path(path): continue
                body, roles = files[path], self._role_values(match.group(1))
                authish, roleish = re.search(r"getSessionUser|useSession|get-session|session\??\.?user", body, re.I), re.search(r"\brole\b", body, re.I)
                missing = [r for r in roles if roleish and not re.search(r"['\"]" + re.escape(r) + r"['\"]", body, re.I)]
                if missing: out.append(Finding("blocker", "ROLE_PAGE_WRONG_ROLE", f"planned role page never names {', '.join(missing)} in its guard", path, "allow every exact planned role", [path]))
                elif not authish and not roleish: out.append(Finding("major", "ROLE_PAGE_UNGUARDED", f"role-owned page for {', '.join(roles)} has no session/role guard", path, "establish the authenticated role here or in its layout", [path]))
        for role, home in self._role_homes().items():
            if not self._route_matches(home, self.enumerate_routes()): out.append(Finding("major", "ROLE_HOME_MISSING", f"role '{role}' maps to {home}, but no page serves it", fix="create the landing page or map the role to a served route"))
        return out

    def auth_flow_findings(self):
        plan, out = getattr(self.arch, "plan", None) or {}, []
        roles = {self._role_key(a.get("role")) for a in plan.get("demo_accounts") or [] if isinstance(a, dict) and a.get("role")}
        if len(roles) < 2: return []
        for path, body in self.code_files().items():
            if re.search(r"app/(?:login|sign-in|signin)/page\.jsx?$", path) and "signIn.email" in body and re.search(r"router\.(?:push|replace)\(\s*['\"]/['\"]", body) and not re.search(r"\brole\b", body): out.append(Finding("major", "ROLE_REDIRECT", "multi-role sign-in hard-codes every successful identity to /", path, "route the refreshed session role to its planned home", [path]))
        return out

    def _data_ui_invariants(self):
        out = []
        for rel, body in sorted(self.code_files().items()):
            if "seed" in rel.lower() and "ensureSeeded" in body:
                if re.search(r"countDocuments\s*\([^)]*\)[\s\S]{0,100}(?:===?|>|!==?)\s*0", body) and not re.search(r"\$setOnInsert|upsert\s*:\s*true|bulkWrite", body): out.append(Finding("blocker", "STALE_SEED_GUARD", "seeding stops whenever the collection is non-empty, so one signup can permanently prevent demo identities", rel, "upsert each seeded row by stable identity with $setOnInsert"))
                if "insertMany" in body and not re.search(r"ordered\s*:\s*false|code\s*!==?\s*11000|upsert\s*:\s*true|let\s+\w*[Ss]eed\w*\s*=\s*null", body): out.append(Finding("blocker", "SEED_RACE", "ensureSeeded can insert twice concurrently and fail with E11000", rel, "cache a seed promise and use idempotent upserts"))
                if re.search(r"createIndex\s*\([^)]*?unique\s*:\s*true", body, re.S): out.append(Finding("blocker", "UNIQUE_INDEX_IN_SEED", "the seed creates a unique index against data that survives regeneration", rel, "move migration out of request-time seeding or make it backward-compatible"))
            if rel.startswith(("app/", "components/")):
                if re.search(r"href\s*=\s*['\"]#['\"]|onClick\s*=\s*\{\s*\(?[^=]*=>\s*\{\s*\}\s*\}", body, re.S): out.append(Finding("major", "INERT_CONTROL", "renders a visible control with no reachable action", rel, "wire the accepted capability or remove the control", [rel]))
                if not self._CLIENT_RE.search(body) and self._EVENT_RE.search(body): out.append(Finding("blocker", "SERVER_CLIENT_EVENT_HANDLER", "a Server Component renders an event handler React cannot serialize", rel, "move the interactive subtree into a Client Component", [rel]))
                if re.search(r"<form\b[^>]*\bmethod\s*=\s*(?:\{\s*)?['\"](?:put|patch|delete)['\"]", body, re.I | re.S): out.append(Finding("blocker", "UNSUPPORTED_FORM_METHOD", "an HTML form declares PUT/PATCH/DELETE, but browsers submit only GET/POST", rel, "use client fetch or a server action", [rel]))
            for value in BCRYPT_LITERAL_RE.findall(body):
                if len(value) != 60: out.append(Finding("blocker", "FAKE_HASH", "contains a malformed bcrypt literal, so every password comparison fails", rel, "create credentials through the configured auth provider")); break
            if "seed" in rel.lower() and "passwordHash" in body and not re.search(r"hashSync|\bhash\(", body): out.append(Finding("blocker", "UNHASHED_SEED", "writes passwordHash without hashing", rel, "use the configured provider or hash the real password"))
        return out

    def _cross_file_invariants(self):
        files, out = self.code_files(), []
        written, read = set(), {}
        for rel, body in files.items():
            constants = dict(re.findall(r"\bconst\s+([A-Z_][A-Z0-9_]*)\s*=\s*['\"]([^'\"]+)['\"]", body))
            for literal, name in re.findall(r"\.set\(\s*(?:['\"]([^'\"]+)['\"]|([A-Z_][A-Z0-9_]*))", body):
                if literal or constants.get(name): written.add(literal or constants[name])
            for literal, name in re.findall(r"\.(?:get|delete)\(\s*(?:['\"]([^'\"]+)['\"]|([A-Z_][A-Z0-9_]*))", body):
                cookie = literal or constants.get(name)
                if cookie and re.search(r"session|token|auth|jwt|user", cookie, re.I): read.setdefault(cookie, []).append(rel)
            if "bcrypt" in body and re.search(r"Response\.json\(\s*\{\s*[^}]*\buser\s*(?:,|\})", body) and re.search(r"\buser\s*=\s*await\s+\w+\.findOne", body): out.append(Finding("major", "HASH_LEAK", "returns a whole credential user document to the browser", rel, "return only id, email, name, and role"))
        for cookie, paths in read.items():
            if cookie not in written: out.append(Finding("blocker", "SESSION_COOKIE_MISMATCH", f"reads session cookie '{cookie}', which no project source writes", paths[0], "export one cookie constant and use it in login, session, and logout", paths))
        oid_fields = set(re.findall(r"(?mi)^\s*[-*]\s*`?([A-Za-z_][\w]*)`?\s*:\s*ObjectId\b", self.plan_text()))
        for rel, body in files.items():
            for field in oid_fields:
                match = re.search(rf"\b(?:find|findOne|updateOne|deleteOne|findOneAndUpdate)\s*\(\s*\{{[^}}]{{0,500}}?\b{re.escape(field)}\s*:\s*([^,}}\n]+)", body, re.S)
                if not match: continue
                value = match.group(1).strip()
                if not re.search(r"\b(?:new\s+)?ObjectId\s*\(", value) and (value in {"id", "roomId", "userId", "ownerId"} or re.fullmatch(r"(?:user|session(?:\?\.user)?|session\.user)\??\.id", value)):
                    out.append(Finding("blocker", "MONGO_ID_TYPE", f"queries ObjectId field '{field}' with string expression {value}", rel, "validate and convert at the Mongo boundary; serialize outward IDs as strings", [rel])); break
        return out

    def contract_findings(self, routes=None):
        plan, files, out = getattr(self.arch, "plan", None) or {}, self.code_files(), []
        routes = routes or self.enumerate_routes()
        shell = self._mentions("app/layout.jsx") | self._mentions("app/layout.js")
        for contract in plan.get("contracts") or []:
            if not isinstance(contract, dict): continue
            src, target = str(contract.get("from") or "").lstrip("./").replace("\\", "/"), str(contract.get("target") or "")
            if src not in files or not target.startswith("/"): continue
            matched = self._route_for(target, routes); method = str(contract.get("method") or "").upper()
            if contract.get("kind") == "api" and (not matched or method and method not in matched.get("methods", [])): out.append(Finding("blocker", "BROKEN_CONTRACT", f"contract {contract.get('name') or target} requires {method or 'a handler'} {target}, but no matching method is served", src, "implement both ends of the API contract", [src] + ([matched["file"]] if matched else [])))
            if "[" not in target and target.rstrip("/") not in (self._mentions(src) | shell): out.append(Finding("major", "BROKEN_CONTRACT", f"contract says {src} must reach {target}, but its import closure never names it", src, f"wire the action to literal target {target}", [src]))
        return out[:12]

    def capability_shape_findings(self):
        plan, out = getattr(self.arch, "plan", None) or {}, []
        planned = {x.get("path") for p in plan.get("phases") or [] for x in p.get("files") or [] if isinstance(x, dict)}
        covered = {str(cid).upper() for flow in plan.get("workflows") or [] if isinstance(flow, dict) for cid in flow.get("covers") or []}
        for cap in plan.get("capabilities") or []:
            if not isinstance(cap, dict): continue
            cid, paths = str(cap.get("id") or "CAP"), [str(x) for x in cap.get("files") or []]; gap = [x for x in paths if x not in planned]
            if not paths or gap: out.append(Finding("blocker", "CAPABILITY_UNMAPPED", f"{cid} has no complete planned file map" + (f": {', '.join(gap)}" if gap else ""), paths[0] if paths else "", "map the complete implementation chain", paths))
            if cap.get("e2e", True) and cid.upper() not in covered: out.append(Finding("major", "CAPABILITY_UNWALKED", f"{cid} is user-visible but no accepted E2E workflow covers it", paths[0] if paths else "", "cover it with a journey performing and asserting the outcome", paths))
        return out[:12]

    def unresolved_packages(self):
        try:
            package = json.loads((self.project_dir / "package.json").read_text("utf-8")); declared = set(package.get("dependencies", {})) | set(package.get("devDependencies", {}))
        except Exception: declared = set()
        out, node_modules = [], self.project_dir / "node_modules"
        for body in self.code_files().values():
            for name in self.arch.imported_packages(body):
                if (name not in declared or not (node_modules / name / "package.json").exists()) and name not in out: out.append(name)
        return out

    def e2e_syntax_findings(self, paths=None):
        tests = {p: b for p, b in self.source_files(refresh=True).items() if p.startswith("tests/e2e/") and p.endswith((".js", ".jsx")) and (not paths or p in paths)}
        problems, reason = check_syntax(self.project_dir, tests, node_cmd=self.cb.get("node_bin"))
        if reason: self._log("WARN", f"   ⚠ E2E syntax preflight unavailable: {reason}"); return []
        return [Finding("blocker", "E2E_SYNTAX", f"generated browser spec is invalid JavaScript at line {p.get('line') or 0}: {p.get('message')}", p["path"], "repair scenario syntax before launching Playwright", [p["path"]]) for p in problems]

    def scan(self):
        report = AnalyzerReport(planned=self.planned_paths(), routes=self.enumerate_routes()); report.missing = self.missing_files(); report.dead_links = self.dead_links(report.routes); report.unresolved = self.unresolved_packages()
        for path in report.missing: report.findings.append(Finding("blocker", "MISSING_FILE", "this is still a scaffold placeholder" if self._is_placeholder(path) else "the accepted plan promises this file but it was never written", path, "write the complete planned file"))
        report.findings += self._code_invariants() + self._auth_invariants() + self._data_ui_invariants() + self._cross_file_invariants() + self.contract_findings(report.routes) + self.capability_shape_findings()
        report.findings += self.prop_contract_breaks() + self.credentials_exposed() + self.seed_volume() + self.layout_chrome()
        for url in self.dead_endpoints(report.routes): report.findings.append(Finding("blocker", "DEAD_ENDPOINT", f"source fetches {url}, but no API handler serves it", fix=f"implement app{url}/route.js", extra=[f"app{url}/route.js"]))
        for url in report.dead_links:
            if url not in {"/sign-in", "/signin", "/login"}: report.findings.append(Finding("major", "DEAD_LINK", f"something links to {url}, but no page serves it", fix="create the planned page or remove the link"))
        orphans = self.unreachable_pages(report.routes)
        if orphans:
            owners = [report.routes[u]["file"] for u in orphans[:10] if u in report.routes]; report.findings.append(Finding("blocker", "NO_WAY_THERE", f"{len(orphans)} page(s) are unreachable from /: {', '.join(orphans[:8])}", owners[0] if owners else "", "wire accepted navigation through the page shell or parent list", owners[1:]))
        for name in report.unresolved: report.findings.append(Finding("blocker", "MISSING_PACKAGE", f"'{name}' is imported but not installed", fix=f"npm install {name}"))
        try:
            for problem in self.arch.lint_generated():
                path = problem.split(":", 1)[0]
                if "imported but not installed" not in problem: report.findings.append(Finding("major", "LINT", problem, path, "repair the deterministic lint violation without changing behavior"))
        except Exception as exc: log.warning("lint_generated failed: %s", exc)
        unique, seen = [], set()
        for finding in report.findings:
            key = (finding.code, finding.path, finding.message)
            if key not in seen: seen.add(key); unique.append(finding)
        report.findings = unique
        return report
    def code_files(self):
        return {p: b for p, b in self.source_files().items() if Path(p).suffix in CODE_EXT and (p.startswith(NEXT_ROOTS) or p in ROOT_SOURCE)}
    def plan_text(self): return str(getattr(self.arch, "plan_md", "") or self.source_files().get("plan.md", ""))

    def planned_paths(self):
        found = {p for p in PROSE_PATH_RE.findall(self.plan_text()) if not PLACEHOLDER_RE.search(p)}
        plan = getattr(self.arch, "plan", None) or {}
        groups = [plan.get("files"), plan.get("file_plan"), (plan.get("implementation") or {}).get("files")]
        groups += [p.get("files") for p in plan.get("phases") or [] if isinstance(p, dict)]
        for group in groups:
            for item in group or []:
                path = item.get("path") if isinstance(item, dict) else item
                if path and not PLACEHOLDER_RE.search(str(path)): found.add(str(path).replace("\\", "/"))
        return sorted(found)
    def _exists(self, rel):
        stem = rel[:-4] if rel.endswith(".jsx") else rel[:-3] if rel.endswith(".js") else rel
        return any((self.project_dir / p).exists() for p in (rel, stem + ".js", stem + ".jsx"))
    def _is_placeholder(self, rel):
        body = self.source_files().get(rel, "")
        return bool(body) and len(body) < 400 and any(x in body for x in self.PLACEHOLDER_MARKERS)
    def missing_files(self):
        out = [p for p in self.planned_paths() if not self._exists(p) or self._is_placeholder(p)]
        return out + [p for p in self.ALWAYS_CHECKED if p not in out and self._is_placeholder(p)]

    def enumerate_routes(self):
        root, out = self.project_dir / "app", {}
        if not root.is_dir(): return out
        for leaf, kind in (("page", "page"), ("route", "api")):
            for suffix in (".js", ".jsx"):
                for fp in sorted(root.rglob(leaf + suffix)):
                    parts = [p for p in fp.relative_to(root).parts[:-1] if not (p.startswith("(") and p.endswith(")"))]
                    url = "/" + "/".join(parts) if parts else "/"
                    if url in out: continue
                    try: body = fp.read_text("utf-8", errors="replace")
                    except OSError: body = ""
                    out[url] = {"file": fp.relative_to(self.project_dir).as_posix(), "kind": kind, "dynamic": "[" in url, "methods": sorted(set(HTTP_METHOD_RE.findall(body))) or (["GET"] if kind == "page" else [])}
        return out
    @staticmethod
    def _route_matches(target, served):
        want = [x for x in target.strip("/").split("/") if x]
        for url in served:
            got = [x for x in url.strip("/").split("/") if x]
            if len(got) == len(want) and all(a == b or a.startswith("[") for a, b in zip(got, want)): return True
        return False
    @staticmethod
    def _route_for(target, routes):
        """The route that really serves a URL, preferring the literal one.

        `/api/rooms/available` and `/api/rooms/[roomId]` both match the shape
        `api/rooms/*`, and the dynamic folder sorts first, so a first-match
        lookup handed back the wrong handler and reported the live GET route as
        unserved — a blocker that no repair could ever clear.
        """
        want = str(target or "").rstrip("/") or "/"
        exact = routes.get(want) or routes.get(want + "/")
        if exact:
            return exact
        for url, meta in routes.items():
            if AnalyzerAgent._route_matches(want, [url]):
                return meta
        return None
    def dead_links(self, routes=None):
        pages = [u for u, m in (routes or self.enumerate_routes()).items() if m["kind"] == "page"]
        dead = set()
        for body in self.code_files().values():
            for raw in [a or b for a, b in LINK_HREF_RE.findall(body)] + ROUTER_PUSH_RE.findall(body):
                url = raw.split("?", 1)[0].split("#", 1)[0].rstrip("/") or "/"
                if not url.startswith("/api") and not self._route_matches(url, pages): dead.add(url)
        return sorted(dead)
    def dead_endpoints(self, routes=None):
        apis = [u for u, m in (routes or self.enumerate_routes()).items() if m["kind"] == "api"]
        return sorted({u.rstrip("/") or "/" for body in self.code_files().values() for u in FETCH_URL_RE.findall(body) if not self._route_matches(u, apis)})
    def _mentions(self, rel, seen=None):
        files, seen = self.code_files(), seen if seen is not None else set()
        if rel not in files or rel in seen: return set()
        seen.add(rel); body = files[rel]
        out = {x.rstrip("/") or "/" for x in re.findall(r"[\"'`](/(?:[a-z0-9][a-z0-9/_-]*)?)(?=(?:[?#]|\$\{|[\"'`]))", body, re.I)}
        out |= {x.rstrip("/") + "/*" for x in re.findall(r"[`](/(?:[a-z0-9][a-z0-9/_-]*/))\$\{", body, re.I)}
        for stmt in parse_imports(body):
            target = resolve_local(rel, stmt.spec, files)
            if target: out |= self._mentions(target, seen)
        return out
    def unreachable_pages(self, routes=None):
        pages = {u: m for u, m in (routes or self.enumerate_routes()).items() if m["kind"] == "page"}
        if "/" not in pages: return []
        shell, reached, queue = self._mentions("app/layout.jsx") | self._mentions("app/layout.js"), {"/"}, ["/"]
        while queue:
            meta = pages.get(queue.pop()) or {}
            for named in self._mentions(meta.get("file", "")) | shell:
                for url in pages:
                    dynamic_hit = named.endswith("/*") and "[" in url and url.startswith(named[:-1])
                    if (named == url or dynamic_hit or "[" in url and self._route_matches(named, [url])) and url not in reached: reached.add(url); queue.append(url)
        return sorted(set(pages) - reached)

    @staticmethod
    def _role_key(value):
        role = re.sub(r"^(?:as\s+)?role(?:\s+|[_:=\-]+\s*)", "", str(value or "").strip().lower())
        return re.sub(r"[^a-z0-9]+", "", role)
    @classmethod
    def _role_values(cls, value): return [x.strip() for x in re.split(r"\s*(?:,|\||&|/|\bor\b)\s*", str(value or ""), flags=re.I) if cls._role_key(x)]
    @staticmethod
    def _route_from_page_path(path):
        rel = str(path or "").replace("\\", "/")
        if not re.fullmatch(r"app/(?:.+/)?page\.jsx?", rel): return ""
        parts = [p for p in rel.split("/")[1:-1] if not (p.startswith("(") and p.endswith(")"))]
        return "/" + "/".join(parts) if parts else "/"
    def _role_homes(self):
        plan, out = getattr(self.arch, "plan", None) or {}, {}
        for role, route in (plan.get("role_homes") or {}).items():
            if self._role_key(role) and str(route).startswith("/"): out[self._role_key(role)] = str(route).split("?", 1)[0].rstrip("/") or "/"
        for phase in plan.get("phases") or []:
            for item in phase.get("files") or []:
                if not isinstance(item, dict): continue
                match = re.match(r"\s*ROLE\s+([^—:-]+)", str(item.get("purpose") or ""), re.I)
                route = self._route_from_page_path(item.get("path"))
                if match and route and "[" not in route:
                    for role in self._role_values(match.group(1)): out.setdefault(self._role_key(role), route)
        return out
    @staticmethod
    def _only(findings, *codes): return [f for f in findings if f.code in codes]

    def _code_invariants(self):
        files, out, suffixes = self.code_files(), [], (".jsx", ".js", ".tsx", ".ts", ".mjs", ".cjs")
        for rel, body in sorted(files.items()):
            clean = _strip_noncode(body)
            for match in self._UNAWAITED_RE.finditer(clean):
                fn, method = match.groups(); out.append(Finding("blocker", "UNAWAITED_COLLECTION", f"line {clean[:match.start()].count(chr(10))+1} calls .{method}() on async {fn}() without await", rel, f"await {fn}(…) before calling .{method}()", [rel]))
            for match in self._OID_RE.finditer(clean):
                arg = match.group(1).strip()
                if (arg[:1] in "'\"" and not re.fullmatch(r"['\"][0-9a-f]{24}['\"]", arg, re.I)) or re.search(r"\.(?:email|name|username|title|slug|password)\b", arg, re.I): out.append(Finding("blocker", "BAD_OBJECTID", f"new ObjectId({arg[:50]}) receives a value that cannot be an ObjectId", rel, "use a validated id or inserted document _id"))
            for match in self._SELF_PARAMS_RE.finditer(clean): out.append(Finding("blocker", "ASYNC_PARAM_CONFUSION", f"destructures {match.group(1)} from the object produced by awaiting itself", rel, f"destructure actual keys directly from await {match.group(1)}"))
            if self._DIRECT_PARAMS_RE.search(clean) and not re.search(r"await\s+params\b", clean): out.append(Finding("blocker", "UNAWAITED_PARAMS", "reads Next.js dynamic params before awaiting them", rel, "await params before reading route keys"))
            stray = getattr(self.arch, "STRAY_DIRECTIVE_RE", re.compile(r"['\"]use client['\"]"))
            for match in stray.finditer(body):
                if re.sub(r"//[^\n]*|/\*.*?\*/", "", body[:match.start()], flags=re.S).strip(): out.append(Finding("blocker", "STRAY_DIRECTIVE", "'use client' appears after executable code", rel, "move it to line 1 or split the component")); break
            for stmt in parse_imports(body):
                spec = stmt.spec or ""
                if not spec.startswith(("./", "../", "@/")) or spec.endswith((".css", ".json", ".svg", ".png", ".jpg", ".webp")): continue
                if resolve_local(rel, spec, files) is not None: continue
                raw = spec[2:] if spec.startswith("@/") else (PurePosixPath(rel).parent / spec).as_posix()
                target = raw if raw.endswith(suffixes) else raw + ".jsx"
                out.append(Finding("blocker", "MISSING_LOCAL_IMPORT", f"imports '{spec}' but no local module exists", rel, f"write {target} or use an existing module", [target]))
        for bad in check_default_imports(files): out.append(Finding("blocker", "BROKEN_IMPORT", f"imports {bad.name} as default from '{bad.spec}', which has no default export", bad.importer, f"use an existing export or add the intended default to {bad.module}", [bad.module]))
        groups = {}
        for bad in check_named_imports(files): groups.setdefault((bad.importer, bad.module, bad.spec), []).append(bad)
        for (src, module, spec), rows in groups.items():
            names = ", ".join(sorted({x.name for x in rows})); fix = "use the framework's real export" if module in FRAMEWORK_EXPORTS else f"preserve exports and add/fix the contract in {module}"
            out.append(Finding("blocker", "BROKEN_IMPORT", f"imports {{ {names} }} from '{spec}', which does not export those names", src, fix, [] if module in FRAMEWORK_EXPORTS else [module]))
        return out

    def inventory(self):
        rows = []
        for path, body in sorted(self.code_files().items()):
            exports = re.findall(r"export\s+(?:default\s+)?(?:async\s+)?(?:function|const)\s+(\w+)", body)
            rows.append(f"{path} · {len(body.splitlines())} lines · {'client' if self._CLIENT_RE.search(body) else 'server'}" + (f" · exports {', '.join(exports[:5])}" if exports else ""))
        return "\n".join(rows)
    @staticmethod
    def route_table(routes): return "\n".join(f"{u} → {m['file']} [{'/'.join(m['methods']) or '-'}]" for u, m in sorted(routes.items()))
    def _budget_chars(self): return int(getattr(self.arch, "num_ctx", getattr(self.arch, "context_tokens", 16384)) * 1.8)
    def _analysis_contract(self):
        try: return PROMPT_FILE.read_text("utf-8")
        except OSError: return "Audit accepted requirements only. Inspect source first. Emit strict JSON with exact evidence."
    def _evidence_ledger(self, report=None):
        plan = getattr(self.arch, "plan", None) or {}
        structured = {k: plan.get(k) or [] for k in ("source_requirements", "capabilities", "workflows", "contracts", "routes", "role_homes", "demo_accounts", "e2e")}
        routes = report.routes if report else self.enumerate_routes()
        return "## Structured plan\n" + json.dumps(structured, ensure_ascii=False, indent=2)[:18000] + "\n\n## Routes\n" + self.route_table(routes)[:8000] + "\n\n## Files\n" + self.inventory()[:8000] + "\n\n## Deterministic findings\n" + ((report.as_prompt_block() if report else "") or "(none)")
    @staticmethod
    def _json_object(text):
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text or "").strip(), flags=re.I | re.S); decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", clean):
            try:
                obj, _ = decoder.raw_decode(clean[match.start():])
                if isinstance(obj, dict): return obj
            except ValueError: pass
        return {}

    def _semantic_lens(self, lens, report, max_turns=4, max_tools=10):
        ledger, plan, files = self._evidence_ledger(report), self.plan_text(), self.source_files()
        messages = [{"role": "system", "content": self._analysis_contract() + "\n\n" + TOOL_HELP}, {"role": "user", "content": f"MODE: SEMANTIC_AUDIT\nLENS: {lens}\n\n## Accepted prose plan\n{plan[:18000]}\n\n{ledger}\n\nInspect the owner and every required hop. Emit tools until proven, then strict JSON."}]
        self.arch._workspace_tool_cache = {}; tools, reply, used = WorkspaceTools(self.arch), "", 0
        for _ in range(max_turns):
            chunks = []
            try: self.arch._stream(messages, chunks.append, temperature=0.15)
            except Exception as exc: self._log("WARN", f"   ⚠ semantic {lens} audit failed: {exc}"); return []
            reply = "".join(chunks); messages.append({"role": "assistant", "content": reply})
            observation, count = tools.serve(reply, max_calls=min(4, max(0, max_tools-used)))
            if count and used < max_tools:
                used += count; messages.append({"role": "user", "content": "Tool observations:\n\n" + observation + "\n\nContinue the same lens without repeating a request."}); continue
            break
        obj, evidence_space, out = self._json_object(reply), plan + "\n" + ledger, []
        for row in obj.get("findings") or []:
            if not isinstance(row, dict): continue
            severity, path = str(row.get("severity") or "major").lower(), str(row.get("path") or "").replace("\\", "/").lstrip("./")
            promise, evidence = str(row.get("plan_quote") or "").strip(), row.get("evidence") or []
            if severity not in SEVERITIES or path not in files or len(promise) < 12 or promise not in evidence_space or not evidence: continue
            related, valid = [], True
            for proof in evidence:
                if not isinstance(proof, dict): valid = False; break
                proof_path = str(proof.get("path") or "").replace("\\", "/").lstrip("./"); quote = str(proof.get("quote") or "")
                if proof_path not in files or len(quote.strip()) < 4 or quote not in files[proof_path]: valid = False; break
                related.append(proof_path)
            if not valid: continue
            related += [str(x).replace("\\", "/").lstrip("./") for x in row.get("related_paths") or [] if str(x).replace("\\", "/").lstrip("./") in files]
            out.append(Finding(severity, str(row.get("code") or "UNBUILT_PROMISE").upper(), str(row.get("message") or "planned behavior is disconnected")[:500], path, str(row.get("fix") or "implement the accepted behavior and rerun its proof")[:500], list(dict.fromkeys(related))))
            if len(out) >= 5: break
        return out

    def unbuilt_promises(self, max_reads=10):
        report, out = self.scan(), []
        for lens in SEMANTIC_LENSES:
            out += self._semantic_lens(lens, report, max_turns=4, max_tools=max(2, max_reads // len(SEMANTIC_LENSES)))
        unique, seen = [], set()
        for finding in out:
            key = (finding.code, finding.path, finding.message)
            if key not in seen: seen.add(key); unique.append(finding)
        return unique[:10]
    def diagnose(self, report, max_reads=12): return self._semantic_lens("general implementation meaning and current findings", report, max_turns=4, max_tools=max_reads)

    def _repair_paths(self, report):
        files, routes, direct = self.source_files(), self.enumerate_routes(), set(report.missing or [])
        for finding in report.findings:
            if finding.severity == "blocker" or finding.code in REPAIRABLE_MAJOR: direct.add(finding.path); direct.update(finding.extra or [])
        normalized = set()
        for raw in direct:
            path = str(raw or "").strip().replace("\\", "/").lstrip("./")
            if path.startswith("/"): path = str((routes.get(path) or {}).get("file") or "")
            if path: normalized.add(path)
        return normalized | set(WorkspaceTools(self.arch).dependency_paths([p for p in normalized if p in files], max_depth=2, cap=24))

    def repair(self, report, server_log=""):
        candidates = self._repair_paths(report)
        safe = {p for p in candidates if p.startswith(("app/", "components/", "lib/", "styles/")) or p in {"middleware.js", "middleware.jsx"}}
        if not safe: return 0
        guidance = nextdocs.guidance_for(server_log + "\n" + "\n".join(f.message for f in report.findings))
        listing = "\n".join(f"- {p} ({'exists' if p in self.source_files() else 'new'})" for p in sorted(safe))
        messages = [{"role": "system", "content": self._analysis_contract() + "\n\n" + self.arch._builder_sys() + "\n\n" + TOOL_HELP}, {"role": "user", "content": "MODE: FINDING_REPAIR\n\n" + self._evidence_ledger(report) + "\n\n## Runtime evidence\n" + server_log[-5000:] + "\n\n" + guidance + "\n\n## Writable dependency neighborhood\n" + listing + "\n\nInspect every affected owner first, then emit complete write_file blocks only."}]
        self.arch._workspace_tool_cache = {}; proposed, tools = {}, WorkspaceTools(self.arch)
        parser = FileStreamParser(on_text=lambda _: None, on_file_start=lambda _: None, on_file_token=lambda _: None, on_file_end=lambda p, b: proposed.__setitem__(str(p or "").strip().replace("\\", "/").lstrip("./"), b))
        for _ in range(4):
            chunks = []
            try:
                def feed(token): chunks.append(token); parser.feed(token)
                self.arch._stream(messages, feed, temperature=0.25)
            except Exception as exc: self._log("ERROR", f"   ❌ Analyzer repair failed: {exc}"); break
            reply = "".join(chunks); messages.append({"role": "assistant", "content": reply}); observation, used = tools.serve(reply)
            if used and not proposed: messages.append({"role": "user", "content": "Tool observations:\n\n" + observation + "\n\nContinue the same repair from this evidence."}); continue
            break
        parser.close(); files, written = self.source_files(), []
        direct = {f.path for f in report.findings}
        for path, content in sorted(proposed.items()):
            if path not in safe or not content.strip(): self._log("WARN", f"   ⛔ ignored unrelated/unsafe repair write {path}"); continue
            if path in self._rewritten_this_stage and path not in direct: continue
            old_exports = set(re.findall(r"export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class)\s+(\w+)", files.get(path, ""))); new_exports = set(re.findall(r"export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class)\s+(\w+)", content))
            if old_exports - new_exports: self._log("WARN", f"   ⛔ {path} drops exports: {', '.join(sorted(old_exports-new_exports))}"); continue
            self._fire("on_file_start", path); self._fire("on_file_end", path, content)
            if self.arch.write_file(path, content): written.append(path)
        self._files_cache = None; self._rewritten_this_stage.update(written); report.written += len(written)
        return len(written)

    def run(self, *, use_model=True, max_rounds=2, semantic=True):
        self._fire("on_phase", {"phase": -5, "title": "Analyzing project", "status": "active"}); report, total = self.scan(), 0
        first = list(report.findings)
        if use_model and report.unresolved: self.cmd.run("npm install " + " ".join(report.unresolved)); self._files_cache = None; report = self.scan()
        def targets(value): return [f for f in value.findings if f.severity == "blocker" or f.code in REPAIRABLE_MAJOR]
        for _ in range(max_rounds if use_model else 0):
            before = targets(report)
            if not before: break
            count = self.repair(AnalyzerReport(findings=before, missing=list(report.missing)))
            if not count: break
            total += count; self._files_cache = None; newer = self.scan()
            report = newer
            if len(targets(newer)) >= len(before): break
        # The model reads the app whether or not the fixed checks are happy. An
        # app with blockers left is the one whose remaining faults nothing in
        # the deterministic list knows how to name.
        if semantic and use_model:
            findings = self.unbuilt_promises(); first.extend(findings)
            if findings:
                total += self.repair(AnalyzerReport(findings=findings)); self._files_cache = None; report = self.scan()
                report.findings += self.unbuilt_promises(max_reads=8)
        report.written = total; self._fire("on_phase", {"phase": -5, "title": "Analyzing project", "status": "done", "written": total})
        try:
            from agents.core import lessons
            lessons.record(self.project_dir.name, lessons.from_findings(first))
        except Exception as exc: log.debug("lessons: %s", exc)
        return report

    @staticmethod
    def _get_status(url, timeout=60):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response: return response.status
        except urllib.error.HTTPError as exc: return exc.code
        except Exception: return None
    @staticmethod
    def _post_json(url, payload, timeout=15):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response: return response.status, response.read(2000).decode("utf-8", "replace")
        except urllib.error.HTTPError as exc: return exc.code, exc.read(2000).decode("utf-8", "replace")
        except Exception: return None, ""

    def probe_pages(self, report, *, skip_root=False):
        for url, meta in sorted(report.routes.items()):
            if meta["kind"] != "page" or meta["dynamic"] or skip_root and url == "/": continue
            status = self._get_status(self.base_url + url)
            if status is None: return
            self._fire("on_test", "fail" if status >= 400 else "pass", f"Route {url}", f"HTTP {status}")
            if status >= 400: report.findings.append(Finding("blocker", "ROUTE_ERROR", f"{url} returns HTTP {status}", meta["file"], f"fix {meta['file']} so {url} responds"))
    def probe_api_routes(self, report, *, skip_health=False):
        for url, meta in sorted(report.routes.items()):
            if meta["kind"] != "api" or meta["dynamic"] or "GET" not in meta["methods"] or skip_health and url == "/api/health": continue
            status = self._get_status(self.base_url + url)
            if status is None: return
            bad = status == 404 or status >= 500; self._fire("on_test", "fail" if bad else "pass", f"API {url}", f"HTTP {status}")
            if bad: report.findings.append(Finding("blocker", "ROUTE_ERROR", f"{url} returns HTTP {status}", meta["file"], f"fix {meta['file']} so {url} responds"))
    def probe_routes(self, report): self.probe_pages(report); self.probe_api_routes(report)
    def probe_linked_dynamic_routes(self, report, limit=24):
        dynamic = {u: m for u, m in report.routes.items() if m["kind"] == "page" and m["dynamic"]}; seen = set()
        for origin, meta in sorted(report.routes.items()):
            if len(seen) >= limit or meta["kind"] != "page" or meta["dynamic"]: continue
            try:
                with urllib.request.urlopen(self.base_url + origin, timeout=30) as response: html = response.read(1_500_000).decode("utf-8", "replace")
            except Exception: continue
            for raw in re.findall(r'''href=["'](/[^"']+)["']''', html, re.I):
                path = raw.split("?", 1)[0].split("#", 1)[0]; match = next(((pat, item) for pat, item in dynamic.items() if self._route_matches(path, [pat])), None)
                if not match or path in seen: continue
                seen.add(path); pattern, route = match; report.runtime_examples.setdefault(route["file"], []).append(raw); status = self._get_status(self.base_url + raw, 45)
                if status == 404 or status and status >= 500: report.findings.append(Finding("blocker", "DYNAMIC_ROUTE_ERROR", f"{origin} renders {raw}, matching {pattern}, but it returns HTTP {status}", route["file"], "repair the detail route for the real runtime id", [meta["file"], route["file"]]))
                if len(seen) >= limit: break

    def find_login_endpoint(self):
        routes, files = self.enumerate_routes(), self.source_files()
        for url, meta in routes.items():
            body = files.get(meta["file"], "")
            if meta["kind"] == "api" and ("bcrypt.compare" in body or "compareSync" in body): return url
        for url, meta in routes.items():
            body = files.get(meta["file"], "")
            if meta["kind"] == "api" and "better-auth" in body and "POST" in meta["methods"]: return re.sub(r"/\[\.\.\.[^\]]+\]$", "", url).rstrip("/") + "/sign-in/email"
        return next((u for u, m in routes.items() if m["kind"] == "api" and "POST" in m["methods"] and any(x in u.lower() for x in ("login", "signin", "authenticate"))), "")
    def demo_credentials(self):
        plan = getattr(self.arch, "plan", None) or {}; creds = [(a["email"], a["password"]) for a in plan.get("demo_accounts") or [] if isinstance(a, dict) and a.get("email") and a.get("password")]
        if creds: return creds
        section = re.search(r"^#+ Demo Accounts\s*$(.*?)(?=^#+ |\Z)", self.plan_text(), re.M | re.S); out = []
        for line in section.group(1).splitlines() if section else []:
            cells = [x.strip().strip("`*") for x in line.split("|")]
            for i, cell in enumerate(cells[:-1]):
                if re.fullmatch(r"[\w.+-]+@[\w.-]+\.\w+", cell) and len(cells[i+1]) >= 6: out.append((cell, cells[i+1])); break
        return out
    def _credentials_from_seed(self):
        seed = "\n".join(b for p, b in self.code_files().items() if "seed" in p.lower()); emails = re.findall(r"email\s*:\s*['\"]([\w.+-]+@[\w.-]+\.\w+)['\"]", seed)
        passwords = [a or b for a, b in re.findall(r"(?:password\s*:\s*['\"]([^'\"]{4,})['\"]|hashSync\s*\(\s*['\"]([^'\"]{4,})['\"])", seed)]
        return list(zip(emails, passwords)) if len(passwords) == len(emails) else []
    def _announce_credentials(self, report=None):
        roles = {a.get("email"): a.get("role", "") for a in (getattr(self.arch, "plan", None) or {}).get("demo_accounts") or [] if isinstance(a, dict)}; checked = {x.get("email"): x.get("status") for x in ((report.credentials.get("checked") if report else []) or [])}
        accounts = [{"email": e, "password": p, "role": roles.get(e, ""), "status": checked.get(e)} for e, p in self.demo_credentials()]
        if accounts: self._fire("on_creds", accounts, "plan" if roles else "project", report.credentials.get("ok") if report else None)
        return accounts
    def verify_credentials(self, report):
        if any(f.code == "ROUTE_ERROR" for f in report.findings): report.credentials = {"checked": [], "ok": None, "reason": "pages are failing"}; return
        creds, endpoint = self.demo_credentials() or self._credentials_from_seed(), self.find_login_endpoint()
        if not creds or not endpoint: report.credentials = {"checked": [], "ok": None, "reason": "no demo accounts" if not creds else "no login endpoint"}; return
        plan = getattr(self.arch, "plan", None) or {}; expected = {str(a.get("email") or "").lower(): str(a.get("role") or "") for a in plan.get("demo_accounts") or [] if isinstance(a, dict)}
        better, checked, failed = "betterAuth(" in self.code_files().get("lib/auth.js", ""), [], []
        for email, password in creds:
            jar = http.cookiejar.CookieJar(); opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)); req = urllib.request.Request(self.base_url + endpoint, data=json.dumps({"email": email, "password": password}).encode(), method="POST", headers={"Content-Type": "application/json"})
            try:
                with opener.open(req, timeout=15) as response: status = response.status
            except urllib.error.HTTPError as exc: status = exc.code
            except Exception: report.credentials = {"checked": checked, "ok": None, "reason": "endpoint unreachable"}; return
            role, actual = "", ""
            if status < 400 and better:
                try:
                    with opener.open(self.base_url + "/api/auth/get-session", timeout=10) as response: user = (json.loads(response.read(4000).decode() or "{}") or {}).get("user") or {}
                    role, actual = str(user.get("role") or ""), str(user.get("email") or "").lower()
                except Exception: pass
            good = status < 400 and (not better or actual == email.lower() and (not expected.get(email.lower()) or self._role_key(role) == self._role_key(expected[email.lower()])))
            checked.append({"email": email, "status": status, "expected_role": expected.get(email.lower(), ""), "session_email": actual, "session_role": role}); self._fire("on_test", "pass" if good else "fail", f"Login {email}", f"HTTP {status}" + (f", role {role or 'missing'}" if better else ""))
            if not good:
                failed.append(email); code = "BAD_CREDENTIALS" if status in (401, 403) else "ROLE_IDENTITY_MISMATCH"; report.findings.append(Finding("blocker", code, f"planned demo identity {email} was not restored exactly (HTTP {status}, role {role or 'missing'})", "lib/seed.js", "create it through Better Auth and preserve its exact role", ["lib/auth.js"]))
        report.credentials = {"endpoint": endpoint, "checked": checked, "ok": not failed}

    def run_runtime(self, mongo=None, node_bin="node", use_model=True, dev_log=None, probe_apis=False, skip_root=False):
        self._fire("on_phase", {"phase": -5, "title": "Verifying app", "status": "active"}); report = self.scan(); self.probe_pages(report, skip_root=skip_root)
        if probe_apis: self.probe_api_routes(report)
        self.probe_linked_dynamic_routes(report); self.verify_credentials(report); self._announce_credentials(report)
        bad = [f for f in report.findings if f.code in {"BAD_CREDENTIALS", "ROLE_IDENTITY_MISMATCH"}]
        if bad and use_model:
            report.written += self.repair(AnalyzerReport(findings=bad), server_log=dev_log() if dev_log else "")
            if report.written and self.allow_reseed and mongo is not None:
                reset = mongo.reset_project_db(self.project_dir, node_bin=node_bin)
                if reset.get("ok"): self._get_status(self.base_url + "/"); again = self.scan(); self.verify_credentials(again); again.written = report.written; report = again
        self._fire("on_phase", {"phase": -5, "title": "Verifying app", "status": "done"}); return report

    # Keep these focused checks available to existing callers.
    def unawaited_collection(self): return self._only(self._code_invariants(), "UNAWAITED_COLLECTION")
    def bad_objectid(self): return self._only(self._code_invariants(), "BAD_OBJECTID")
    def async_param_confusion(self): return self._only(self._code_invariants(), "ASYNC_PARAM_CONFUSION", "UNAWAITED_PARAMS")
    def stray_directives(self): return [f"{f.path}:1" for f in self._only(self._code_invariants(), "STRAY_DIRECTIVE")]
    def missing_local_imports(self): return self._only(self._code_invariants(), "MISSING_LOCAL_IMPORT")
    def broken_imports(self): return self._only(self._code_invariants(), "BROKEN_IMPORT")
    def better_auth_demo_seed(self): return self._only(self._auth_invariants(), "BETTER_AUTH_DEMO_SEED")
    def auth_origin(self): return self._only(self._auth_invariants(), "AUTH_ORIGIN")
    def session_user_id(self): return self._only(self._auth_invariants(), "SESSION_USER_ID")
    def authz_redirect(self): return self._only(self._auth_invariants(), "AUTHZ_REDIRECT")
    def seed_behind_auth(self): return self._only(self._auth_invariants(), "SEED_BEHIND_AUTH")
    def seed_race(self): return self._only(self._data_ui_invariants(), "SEED_RACE")
    def stale_seed_guard(self): return self._only(self._data_ui_invariants(), "STALE_SEED_GUARD")
    def unique_index_in_seed(self): return self._only(self._data_ui_invariants(), "UNIQUE_INDEX_IN_SEED")
    def inert_control_findings(self): return self._only(self._data_ui_invariants(), "INERT_CONTROL")
    def server_client_boundary_findings(self): return self._only(self._data_ui_invariants(), "SERVER_CLIENT_EVENT_HANDLER")
    def unsupported_form_method_findings(self): return self._only(self._data_ui_invariants(), "UNSUPPORTED_FORM_METHOD")
    def credential_smells(self): return self._only(self._data_ui_invariants(), "FAKE_HASH", "UNHASHED_SEED")
    def auth_completeness(self):
        return self._only(self._auth_invariants(), "AUTH_PAGE_MISSING",
                          "AUTH_SIGNUP_MISSING", "AUTH_PROVIDER_ROUTE")

    def _semantic_requirement(self, lens, code):
        """Return one cached semantic check for older callers."""
        key = (getattr(self.arch, "write_seq", 0), lens)
        if key not in self._semantic_cache:
            self._semantic_cache[key] = self._semantic_lens(
                lens, self.scan(), max_turns=4, max_tools=8)
        return [Finding(f.severity, code, f.message, f.path, f.fix,
                        list(f.extra)) for f in self._semantic_cache[key]]

    def planned_data_findings(self):
        return self._semantic_requirement(
            "planned collection reads, writes, API transport and persistence",
            "MISSING_PLANNED_DATA")

    def workflow_control_findings(self):
        return self._semantic_requirement(
            "accepted workflow controls, handlers, outcomes and E2E reachability",
            "MISSING_WORKFLOW_CONTROL")

    @staticmethod
    def _jsx_attrs(body, start):
        depth, quote, i = 0, "", start
        while i < len(body):
            char = body[i]
            if quote:
                if char == "\\": i += 1
                elif char == quote: quote = ""
            elif char in "'\"`": quote = char
            elif char == "{": depth += 1
            elif char == "}": depth -= 1
            elif char == ">" and depth == 0: return body[start:i]
            elif char == "<" and depth == 0: return None
            i += 1
        return None

    def prop_contract_breaks(self):
        files, contracts, out = self.code_files(), {}, []
        signature = re.compile(r"export\s+default\s+(?:async\s+)?function(?:\s+\w+)?\s*\(\s*\{([^}]*)\}")
        for path, body in files.items():
            if not path.startswith("components/") or not (match := signature.search(body)): continue
            required = []
            for raw in match.group(1).split(","):
                name = raw.strip()
                if not re.fullmatch(r"\w+", name) or name == "children": continue
                guarded = re.search(rf"\b{re.escape(name)}\s*(?:&&|\?\.|\|\||\?\?)", body)
                if not guarded and re.search(rf"\b{re.escape(name)}\s*(?:\.|\(|\[)", body): required.append(name)
            if required: contracts[path] = set(required)
        for path, body in files.items():
            imports = {stmt.default: resolve_local(path, stmt.spec, files)
                       for stmt in parse_imports(body) if stmt.default}
            for match in re.finditer(r"<([A-Z]\w*)\b", body):
                target, attrs = imports.get(match.group(1)), self._jsx_attrs(body, match.end())
                if target not in contracts or attrs is None or re.search(r"\{\s*\.\.\.", attrs): continue
                given = set(re.findall(r"(\w+)\s*=", attrs)); missing = contracts[target] - given
                if missing: out.append(Finding(
                    "blocker", "PROP_CONTRACT",
                    f"<{match.group(1)}> omits required prop(s): {', '.join(sorted(missing))}",
                    path, f"pass the required prop(s) or make {target} safely optional",
                    [target]))
        return out[:12]

    def credentials_exposed(self):
        passwords = {password for _, password in self.demo_credentials() if password}
        out = []
        for path, body in self.code_files().items():
            if not path.startswith(("app/", "components/")): continue
            visible = re.sub(r"placeholder\s*=\s*[\"'{][^\"'}]*[\"'}]", "", body)
            exposed = next((p for p in passwords if p in visible), "")
            panel = re.search(r"(?:Demo Accounts?|Test Credentials?)[\s\S]{0,500}[\w.+-]+@[\w.-]+\.\w+", visible, re.I)
            prefill = re.search(r"(?:defaultValue|useState)\s*[=(]\s*['\"][\w.+-]+@", visible)
            if exposed or panel or prefill: out.append(Finding(
                "major", "CREDS_IN_UI", "demo credentials are rendered inside the generated app",
                path, "remove credential panels and prefilled identities; show them only in AgentForge"))
        return out

    def seed_volume(self):
        if "Sample data: requested" in self.plan_text(): return []
        out = []
        for path, body in self.code_files().items():
            if "seed" not in path.lower(): continue
            counts = [int(a or b) for a, b in re.findall(
                r"Array\.from\s*\(\s*\{\s*length\s*:\s*(\d+)|for\s*\(\s*(?:let|var)\s+\w+\s*=\s*0\s*;\s*\w+\s*<\s*(\d+)", body)]
            if counts and max(counts) >= 5: out.append(Finding(
                "minor", "SEED_VOLUME", f"seeds {max(counts)} generated demo rows without a sample-data requirement",
                path, "keep only the few rows needed to prove the screens"))
        return out
    def session_cookie_mismatch(self): return self._only(self._cross_file_invariants(), "SESSION_COOKIE_MISMATCH")
    def layout_chrome(self):
        files, out = self.code_files(), []
        layout = next((p for p in ("app/layout.js", "app/layout.jsx") if p in files), "")
        if not layout: return out
        body = files[layout]
        if "ensureSeeded" in body: out.append(Finding(
            "major", "SEED_IN_LAYOUT", "root layout seeds on every page and API request",
            layout, "seed from the data/auth entry points that need it"))
        return out
    def leaks_password_hash(self): return self._only(self._cross_file_invariants(), "HASH_LEAK")
    def mongo_id_type_findings(self): return self._only(self._cross_file_invariants(), "MONGO_ID_TYPE")
    def orphan_components(self):
        files = self.code_files(); blob = "\n".join(files.values())
        return sorted(Path(p).stem for p in files if p.startswith("components/") and not re.search(r"from\s+['\"][^'\"]*/" + re.escape(Path(p).stem) + r"['\"]", blob))


__all__ = ["AnalyzerAgent", "AnalyzerReport", "Finding", "REPAIRABLE_MAJOR", "BCRYPT_LITERAL_RE", "CODE_EXT", "FETCH_URL_RE", "HTTP_METHOD_RE", "LINK_HREF_RE", "MAX_FILE_BYTES", "NEXT_ROOTS", "PLACEHOLDER_RE", "PROSE_PATH_RE", "ROOT_SOURCE", "ROUTER_PUSH_RE", "SEVERITIES", "SKIP_DIRS", "SOURCE_EXT", "log"]
