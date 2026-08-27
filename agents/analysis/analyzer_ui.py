"""Auth completeness, layout, data-model and inert-control checks."""
from agents.analysis.analyzer_common import *


class AnalyzerUIMixin:
    _CLIENT_DIRECTIVE_RE = re.compile(
        r"^\s*(?:(?://[^\n]*\n)|(?:/\*.*?\*/\s*))*['\"]use client['\"]\s*;?",
        re.S)
    _EVENT_PROP_RE = re.compile(
        r"\bon(?:Click|Change|Submit|Select|Blur|Focus|Key\w*|Mouse\w*|"
        r"Pointer\w*|Drag\w*|Drop|Input|Toggle|Close|Open|Save|Delete|"
        r"Update|Create)\s*=", re.I)

    def _signup_required(self) -> bool:
        """Only require self-registration when the accepted requirements do.

        A demo-account/admin system can legitimately have login without public
        signup.  Treating every login as proof that registration is required
        caused late navbar/signup rewrites, a rebuild, and a full E2E rerun for
        features nobody asked for.
        """
        plan = getattr(self.arch, "plan", None) or {}
        chunks = list(plan.get("source_requirements") or [])
        for cap in plan.get("capabilities") or []:
            if isinstance(cap, dict):
                chunks.extend(str(cap.get(k) or "") for k in
                              ("requirement", "proof", "name", "title"))
        text = "\n".join(str(x or "") for x in chunks)
        # plan_md is included only as supporting evidence.
        if not text.strip():
            text = str(getattr(self.arch, "plan_md", "") or "")
        return bool(re.search(r"\b(sign[ -]?up|signup|register|registration|create (?:an? )?account|account creation)\b",
                              text, re.I))

    def auth_completeness(self) -> list:
        """A login with no signup, or links between them that 404."""
        routes = self.enumerate_routes()
        pages = {u for u, r in routes.items() if r["kind"] == "page"}
        has_login = any("login" in u or "signin" in u for u in pages)
        if not has_login:
            return []

        managed = any(p.startswith("app/api/auth/[") for p in self.code_files())

        out = []
        if not self._signup_required():
            return out
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

    def _plan_objectid_fields(self) -> set:
        """Mongo fields declared ObjectId in the approved Data Model."""
        md = self.plan_text() or ""
        fields = set()
        for name in re.findall(r"(?mi)^\s*[-*]\s*`?([A-Za-z_][\w]*)`?\s*:\s*ObjectId\b", md):
            fields.add(name)
        return fields

    def _plan_collections(self) -> set:
        """Collection names from `## Data Model` bullets."""
        md = self.plan_text() or ""
        m = re.search(r"(?ms)^## Data Model\s*$\n(.*?)(?=^## \S|\Z)", md)
        if not m:
            return set()
        out = set()
        for line in m.group(1).splitlines():
            # collection bullets are top-level; indented bullets are fields.
            x = re.match(r"^[-*]\s*\*\*([^*]+)\*\*\s*:", line)
            if not x:
                x = re.match(r"^[-*]\s*`?([A-Za-z_][\w-]*)`?\s*:", line)
            if x:
                out.add(x.group(1).strip())
        return out

    def mongo_id_type_findings(self) -> list:
        """ObjectId/string boundary mistakes that become detail-page 404s.

        Next route/search params and Better Auth's `user.id` are strings. Mongo
        fields declared ObjectId are not. `findOne({_id: id})` therefore returns
        no document without throwing: the page exists, builds, serves, and calls
        `notFound()` for every real record. This is deterministic enough to catch
        before the browser pays for it.
        """
        oid_fields = self._plan_objectid_fields()
        if not oid_fields:
            return []
        out = []
        for path, body in sorted(self.code_files().items()):
            if not path.startswith(("app/", "lib/")) or path.startswith("app/api/auth/"):
                continue
            string_vars = set()
            # params/searchParams are URL strings.
            for names in re.findall(r"const\s*\{([^}]+)\}\s*=\s*await\s+(?:params|searchParams)\b", body):
                for raw in names.split(","):
                    name = raw.split(":", 1)[-1].strip().split("=", 1)[0].strip()
                    if re.match(r"^[A-Za-z_$][\w$]*$", name):
                        string_vars.add(name)
            # Values unpacked from request JSON are transport values.
            if re.search(r"await\s+request\.json\s*\(", body):
                for names in re.findall(r"const\s*\{([^}]+)\}\s*=\s*(?:body|await\s+request\.json\s*\(\s*\))", body):
                    for raw in names.split(","):
                        name = raw.split(":", 1)[-1].strip().split("=", 1)[0].strip()
                        if re.match(r"^[A-Za-z_$][\w$]*$", name):
                            string_vars.add(name)

            for field in oid_fields:
                # Match the first query-object value for this field in common.
                rx = re.compile(
                    rf"\b(?:find|findOne|updateOne|deleteOne|findOneAndUpdate|replaceOne)\s*\(\s*\{{[^}}]{{0,500}}?\b{re.escape(field)}\s*:\s*([^,}}\n]+)",
                    re.S)
                for m in rx.finditer(body):
                    expr = m.group(1).strip()
                    if re.search(r"\b(?:new\s+)?ObjectId\s*\(", expr):
                        continue
                    if expr.endswith("._id") or re.search(r"\._id\b", expr):
                        continue
                    risky = (expr in string_vars or expr in {"id", "roomId", "userId", "ownerId"}
                             or re.fullmatch(r"(?:user|session(?:\?\.user)?|session\.user)\??\.id", expr))
                    if not risky:
                        continue
                    out.append(Finding(
                        "blocker", "MONGO_ID_TYPE",
                        f"{path} queries ObjectId field '{field}' with string expression `{expr}`; "
                        "the query silently matches nothing, so valid detail/list data can become a 404 or empty state",
                        path=path,
                        fix=(f"convert `{expr}` with ObjectId at the Mongo boundary (and validate route ids) "
                             f"before querying `{field}`; keep outward/client ids serialized as strings"),
                        extra=[path]))
                    break
        seen, uniq = set(), []
        for f in out:
            k = (f.path, f.message)
            if k not in seen:
                seen.add(k); uniq.append(f)
        return uniq[:12]

    def planned_data_findings(self) -> list:
        """A planned data obligation may be direct Mongo OR a real API hand-off.

        V13 compared a plan entry such as "inventory page reads products" only
        against `.collection('products')` inside the page.  That is wrong for a
        client page (and for a server/page intentionally delegated to a client
        child): `fetch('/api/products')` -> `app/api/products/route.js` -> Mongo
        is the same end-to-end read.  The false positive triggered a five-file
        verification rewrite and a complete E2E rerun in the field log.
        """
        plan = getattr(self.arch, "plan", None) or {}
        files = self.code_files()
        collections = self._plan_collections()
        out = []

        AUTH_ALIASES = {"users": "user", "sessions": "session",
                        "accounts": "account"}

        def _norm(name) -> str:
            n = str(name or "").strip()
            return AUTH_ALIASES.get(n.lower(), n)

        def _colls(body: str) -> set:
            got = set()
            for m in re.finditer(r"(?:getCollection|\.collection)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)", body or ""):
                got.add(_norm(m.group(1)))
            return got

        def _closure(path: str, seen: set = None) -> str:
            # The page plus every project file it imports, one blob. The
            # contract check already walks imports; measuring data edges on
            # the page body alone flagged every page that delegated its
            # fetch to a component, and the repair loop chased that ghost
            # for four rounds on one build.
            from agents.core import exports_parse as _ex
            seen = seen if seen is not None else set()
            if not path or path in seen or path not in files:
                return ""
            seen.add(path)
            body = files.get(path) or ""
            if not isinstance(body, str):
                return ""
            parts = [body]
            for stmt in _ex.parse_imports(body):
                target = _ex.resolve_local(path, stmt.spec, files)
                if target:
                    parts.append(_closure(target, seen))
            return "\n".join(parts)

        def _api_file_for(url: str) -> str:
            clean = str(url or "").split("?", 1)[0].strip()
            if not clean.startswith("/api/"):
                return ""
            segs = [x for x in clean[len('/api/'):].strip('/').split('/') if x]
            exact = "app/api/" + "/".join(segs) + "/route.js"
            if exact in files:
                return exact
            # Dynamic URL literals normally contain ${id}.
            cands = []
            for rel in files:
                if not rel.startswith("app/api/") or not rel.endswith("/route.js"):
                    continue
                mid = rel[len("app/api/"):-len("/route.js")]
                parts = mid.split('/') if mid else []
                if len(parts) != len(segs):
                    continue
                ok = True
                for a, b in zip(parts, segs):
                    if a.startswith('[') and a.endswith(']'):
                        continue
                    if a != b and '${' not in b:
                        ok = False; break
                if ok:
                    cands.append(rel)
            return sorted(cands)[0] if cands else ""

        def _api_edges(body: str) -> list[tuple[str, str]]:
            edges = []
            # Capture the common output shape.
            rx = re.compile(r"fetch\s*\(\s*([`'\"])(/api/.*?)(?:\1)\s*(?:,\s*\{(.*?)\})?\s*\)", re.S)
            for m in rx.finditer(body or ""):
                url = m.group(2)
                opts = m.group(3) or ""
                mm = re.search(r"method\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", opts, re.I)
                method = (mm.group(1).upper() if mm else "GET")
                edges.append((url, method))
            for url in re.findall(r"['\"](/api/[A-Za-z0-9_./${}\[\]-]+)['\"]", body or ""):
                if not any(u == url for u, _ in edges):
                    edges.append((url, "GET"))
            return edges

        for ph in plan.get("phases") or []:
            for spec in ph.get("files") or []:
                if not isinstance(spec, dict):
                    continue
                path = str(spec.get("path") or "")
                body = files.get(path, "")
                if not body:
                    continue
                reads = [str(x) for x in spec.get("reads") or [] if str(x)]
                writes = [str(x) for x in spec.get("writes") or [] if str(x)]
                # Backward-compatible recovery from old purpose prose.
                if not reads and collections:
                    purpose = str(spec.get("purpose") or "").lower()
                    if "read" in purpose:
                        reads = [c for c in collections if re.search(rf"\b{re.escape(c.lower())}\b", purpose)]

                direct = _colls(_closure(path))
                api_read, api_write = set(), set()
                for url, method in _api_edges(_closure(path)):
                    rel = _api_file_for(url)
                    if not rel:
                        continue
                    touched = _colls(files.get(rel, ""))
                    api_read |= touched
                    if method != "GET":
                        api_write |= touched

                for coll in dict.fromkeys(reads):
                    if _norm(coll) not in direct and _norm(coll) not in api_read:
                        api_hint = f"app/api/{str(coll).strip().lower()}/route.js"
                        route_hint = api_hint if api_hint not in files else "the page's existing API route"
                        api_url = f"/api/{str(coll).strip().lower()}"
                        out.append(Finding(
                            "major", "MISSING_PLANNED_DATA",
                            f"the plan says {path} reads Mongo collection '{coll}', but neither the file nor an API route it calls reaches that collection",
                            path=path,
                            fix=(f"wire the planned {coll} read end to end. If no suitable API exists, "
                                 f"create {route_hint} with a GET that reads collection '{coll}', then "
                                 f"make {path} call it. MACHINE CHECK: {path} (or a component it "
                                 f"imports) must contain either fetch('{api_url}') as a literal, or "
                                 f"getCollection('{coll}') directly. Any other wiring will fail this "
                                 f"check again."),
                            extra=[path, api_hint]))
                for coll in dict.fromkeys(writes):
                    if _norm(coll) not in direct and _norm(coll) not in api_write:
                        api_hint = f"app/api/{str(coll).strip().lower()}/route.js"
                        api_url = f"/api/{str(coll).strip().lower()}"
                        out.append(Finding(
                            "major", "MISSING_PLANNED_DATA",
                            f"the plan says {path} writes Mongo collection '{coll}', but neither the file nor a mutation API it calls reaches that collection",
                            path=path,
                            fix=(f"wire the planned write to {coll} end to end. If the mutation route is "
                                 f"missing, create {api_hint} and call it from {path}. MACHINE CHECK: "
                                 f"{path} (or a component it imports) must contain a fetch to "
                                 f"'{api_url}' with a non-GET method, or write via "
                                 f"getCollection('{coll}') directly."),
                            extra=[path, api_hint]))
        return out[:12]

    def inert_control_findings(self) -> list:
        """Visible controls that are permanently inert are unfinished UI."""
        out = []
        button_re = re.compile(r"<button\b([^>]*)>(.*?)</button>", re.S | re.I)
        for path, body in sorted(self.code_files().items()):
            if not path.startswith(("app/", "components/")) or not path.endswith((".jsx", ".js")):
                continue
            # explicit dead-link and empty handlers are always real defects.
            if re.search(r"href\s*=\s*['\"]#['\"]", body):
                out.append(Finding("major", "INERT_CONTROL",
                                   f"{path} renders href='#' — a visible link that cannot reach a real page",
                                   path=path, fix="point it at a planned route or remove the control", extra=[path]))
            if re.search(r"onClick\s*=\s*\{\s*\(?.*?\)?\s*=>\s*\{\s*\}\s*\}", body, re.S):
                out.append(Finding("major", "INERT_CONTROL",
                                   f"{path} contains an empty onClick handler",
                                   path=path, fix="implement the action named by the control or remove it", extra=[path]))
            for m in button_re.finditer(body):
                attrs, inner = m.group(1), m.group(2)
                label = re.sub(r"<[^>]+>", " ", inner)
                label = " ".join(re.sub(r"\{[^{}]*\}", " ", label).split())[:80] or "button"
                # disabled={loading} is state, bare `disabled` is permanent.
                if re.search(r"(?:^|\s)disabled(?:\s|>|$)", attrs) and not re.search(r"disabled\s*=\s*\{", attrs):
                    out.append(Finding(
                        "major", "INERT_CONTROL",
                        f"{path} renders permanently disabled '{label}' — the UI advertises an action nobody can perform",
                        path=path, fix="implement the action or remove the control instead of shipping a permanent placeholder",
                        extra=[path]))
                    continue
                if re.search(r"\bonClick\s*=", attrs) or re.search(r"\btype\s*=\s*['\"]submit['\"]", attrs, re.I):
                    continue
                # A button inside a form may legitimately rely on default submit.
                before = body[:m.start()]
                inside_form = before.rfind("<form") > before.rfind("</form>")
                if inside_form:
                    continue
                out.append(Finding(
                    "major", "INERT_CONTROL",
                    f"{path} renders '{label}' as a button with no click handler and no form submission",
                    path=path, fix="wire the button to its real action or remove it", extra=[path]))
        seen, uniq = set(), []
        for f in out:
            key = (f.path, f.message)
            if key not in seen:
                seen.add(key); uniq.append(f)
        return uniq[:12]

    def server_client_boundary_findings(self) -> list:
        """Event handlers that a Server Component cannot serialize to React."""
        files = self.code_files()
        out = []
        for path, body in sorted(files.items()):
            if (not path.startswith(("app/", "components/")) or
                    not path.endswith((".jsx", ".js")) or
                    self._CLIENT_DIRECTIVE_RE.search(str(body or ""))):
                continue

            # Native JSX event handlers require this module to be a Client
            # Component. They can hide in a conditional branch and therefore
            # pass both `next build` and a route probe that did not select it.
            native = re.search(
                r"<([a-z][\w.-]*)\b([^>]{0,2400}\bon(?:Click|Change|Submit|"
                r"Select|Blur|Focus|Key\w*|Mouse\w*|Pointer\w*|Drag\w*|Drop|"
                r"Input|Toggle|Close|Open|Save|Delete|Update|Create)\s*=)",
                str(body or ""), re.S)
            if native:
                line = str(body or "")[:native.start()].count("\n") + 1
                out.append(Finding(
                    "blocker", "SERVER_CLIENT_EVENT_HANDLER",
                    f"line {line} renders an event handler on <{native.group(1)}> from a Server Component; React cannot serialize it and the rendered branch throws at runtime",
                    path=path,
                    fix=("move the interactive subtree into a separate file beginning "
                         "with 'use client', and pass only serializable data from this "
                         "server file"),
                    extra=[path]))
                continue

            # The same boundary failure occurs when an imported Client
            # Component receives onSelect/onSave/etc. from a Server Component.
            client_imports = {}
            for statement in parse_imports(str(body or "")):
                if not statement.default or not statement.spec.startswith(("./", "../", "@/")):
                    continue
                target = resolve_local(path, statement.spec, files)
                if target and self._CLIENT_DIRECTIVE_RE.search(str(files.get(target) or "")):
                    client_imports[statement.default] = target
            for component, target in client_imports.items():
                for match in re.finditer(r"<" + re.escape(component) + r"\b", str(body or "")):
                    attrs = self._jsx_attrs(str(body or ""), match.end())
                    if attrs is None or not self._EVENT_PROP_RE.search(attrs):
                        continue
                    line = str(body or "")[:match.start()].count("\n") + 1
                    out.append(Finding(
                        "blocker", "SERVER_CLIENT_EVENT_HANDLER",
                        f"line {line} passes an event-handler prop from this Server Component to client module {target}; functions cannot cross that boundary",
                        path=path,
                        fix=(f"move the interaction and <{component}> call into a Client "
                             "Component, or replace the callback with a serializable "
                             "navigation/data contract"),
                        extra=[path, target]))
                    break
        return out[:12]

    def unsupported_form_method_findings(self) -> list:
        """HTML forms support only GET/POST; other methods silently degrade."""
        out = []
        for path, body in sorted(self.code_files().items()):
            if not path.startswith(("app/", "components/")) or not path.endswith((".jsx", ".js")):
                continue
            for match in re.finditer(
                    r"<form\b[^>]*\bmethod\s*=\s*(?:\{\s*)?['\"]"
                    r"(put|patch|delete)['\"](?:\s*\})?[^>]*>",
                    str(body or ""), re.I | re.S):
                method = match.group(1).upper()
                line = str(body or "")[:match.start()].count("\n") + 1
                out.append(Finding(
                    "blocker", "UNSUPPORTED_FORM_METHOD",
                    f"line {line} declares <form method=\"{method}\">, but browsers support only GET and POST forms; the action will not send the planned {method} mutation",
                    path=path,
                    fix=(f"submit {method} through a client fetch/event handler or a "
                         "server action that invokes the mutation, then render the "
                         "persisted result"),
                    extra=[path]))
        return out[:12]
