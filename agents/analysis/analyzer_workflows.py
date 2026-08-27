"""Workflow capability analysis, credential verification and login endpoint checks."""
from agents.analysis.analyzer_common import *


class AnalyzerWorkflowMixin:
    @staticmethod
    def _role_key(value) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

    @classmethod
    def _role_values(cls, value) -> list[str]:
        """Return the individual roles named by one plan role expression.

        Planner prose legitimately uses values such as ``front_desk, admin``
        for a page shared by two roles.  Treating that whole expression as one
        identity produced the synthetic role ``frontdeskadmin`` and sent the
        runtime repair loop into two correctly guarded pages.  Split only on
        explicit role separators; spaces remain valid inside a role name.
        """
        raw = str(value or "").strip()
        if not raw:
            return []
        parts = re.split(r"\s*(?:,|\||&|/|\bor\b)\s*", raw, flags=re.I)
        out = []
        for part in parts:
            part = part.strip()
            if part and cls._role_key(part) and part not in out:
                out.append(part)
        return out

    @staticmethod
    def _route_from_page_path(path: str) -> str:
        rel = str(path or "").replace("\\", "/")
        if not re.fullmatch(r"app/(?:.+/)?page\.jsx?", rel):
            return ""
        parts = [p for p in rel.split("/")[1:-1]
                 if not (p.startswith("(") and p.endswith(")"))]
        return "/" + "/".join(parts) if parts else "/"

    def _role_homes(self) -> dict:
        plan = getattr(self.arch, "plan", None) or {}
        roles = [str(a.get("role") or "").strip()
                 for a in (plan.get("demo_accounts") or [])
                 if isinstance(a, dict) and a.get("role")]
        homes = {}
        raw = plan.get("role_homes") or {}
        if isinstance(raw, dict):
            for role, route in raw.items():
                if self._role_key(role) and str(route or "").startswith("/"):
                    homes[self._role_key(role)] = str(route).split("?", 1)[0].rstrip("/") or "/"

        for wf in plan.get("workflows") or []:
            if not isinstance(wf, dict):
                continue
            key = self._role_key(wf.get("who"))
            if not key or key in homes:
                continue
            for step in wf.get("steps") or []:
                m = re.match(r"\s*(/[^\s—]+)", str(step or ""))
                if m and "[" not in m.group(1):
                    homes[key] = m.group(1).split("?", 1)[0].rstrip("/") or "/"
                    break

        for ph in plan.get("phases") or []:
            for f in (ph.get("files") or []):
                if not isinstance(f, dict):
                    continue
                purpose = str(f.get("purpose") or "")
                m = re.match(r"\s*ROLE\s+([^—:-]+)", purpose, re.I)
                if not m:
                    continue
                route = self._route_from_page_path(f.get("path", ""))
                if route and "[" not in route:
                    for role in self._role_values(m.group(1)):
                        homes.setdefault(self._role_key(role), route)
        return homes

    def role_contract_findings(self) -> list:
        """Make the plan/account/page role matrix decidable before E2E."""
        plan = getattr(self.arch, "plan", None) or {}
        accs = [a for a in (plan.get("demo_accounts") or []) if isinstance(a, dict)]
        planned_roles = {self._role_key(a.get("role")) for a in accs if a.get("role")}
        for wf in plan.get("workflows") or []:
            if isinstance(wf, dict):
                key = self._role_key(wf.get("who"))
                if key not in {"", "public", "visitor", "anonymous", "signedout"}:
                    planned_roles.add(key)
        for phase in plan.get("phases") or []:
            if not isinstance(phase, dict):
                continue
            for item in phase.get("files") or []:
                if not isinstance(item, dict):
                    continue
                m = re.match(r"\s*ROLE\s+([^—:-]+)", str(item.get("purpose") or ""), re.I)
                if m:
                    planned_roles.update(
                        self._role_key(role) for role in self._role_values(m.group(1)))
        planned_roles.discard("")
        if len(planned_roles) < 2:
            return []
        out = []
        by_role, by_email = {}, {}
        for a in accs:
            role = str(a.get("role") or "").strip()
            email = str(a.get("email") or "").strip().lower()
            if not role or not email:
                continue
            by_role.setdefault(self._role_key(role), []).append(a)
            by_email.setdefault(email, set()).add(self._role_key(role))
        for key, rows in by_role.items():
            if len(rows) != 1:
                out.append(Finding(
                    "blocker", "ROLE_ACCOUNT_CONTRACT",
                    f"role '{rows[0].get('role')}' has {len(rows)} demo accounts; "
                    "multi-role verification needs exactly one identity per role",
                    path="lib/seed.js",
                    fix="keep one unique demo email/password per role and seed each exact role value"))
        for email, roles in by_email.items():
            if len(roles) > 1:
                out.append(Finding(
                    "blocker", "ROLE_ACCOUNT_CONTRACT",
                    f"demo email {email} is assigned to multiple roles",
                    path="lib/seed.js",
                    fix="use a different demo account for every role"))

        known = set(by_role)
        missing_accounts = planned_roles - known
        for key in sorted(missing_accounts):
            out.append(Finding(
                "blocker", "ROLE_ACCOUNT_CONTRACT",
                f"planned signed-in role '{key}' has no unique demo identity",
                path="lib/seed.js",
                fix="seed one unique demo account for every signed-in role and preserve each exact role value"))
        for wf in plan.get("workflows") or []:
            if not isinstance(wf, dict):
                continue
            who = str(wf.get("who") or "").strip()
            key = self._role_key(who)
            if (key and key not in {"public", "visitor", "anonymous", "signedout"}
                    and key not in known and key not in missing_accounts):
                out.append(Finding(
                    "blocker", "ROLE_ACCOUNT_CONTRACT",
                    f"workflow '{wf.get('name') or 'journey'}' runs as role '{who}', "
                    "but no demo account owns that exact role",
                    path="lib/seed.js",
                    fix=f"seed one demo account whose role is exactly '{who}'"))

        homes = self._role_homes()
        signup = self._role_key(plan.get("signup_role"))
        for key, rows in by_role.items():
            if key == signup:
                continue
            if key not in homes:
                out.append(Finding(
                    "major", "ROLE_HOME_MISSING",
                    f"role '{rows[0].get('role')}' has an account but no distinct planned landing/page route",
                    fix="give this role a concrete page/workflow entry and route successful login there"))
        return out


    def role_page_findings(self) -> list:
        """Check each planned role page against its auth guard."""
        plan = getattr(self.arch, "plan", None) or {}
        accounts = [a for a in (plan.get("demo_accounts") or [])
                    if isinstance(a, dict) and a.get("role")]
        if len(accounts) < 2:
            return []
        files = self.code_files()
        out = []

        def guarded_source(path: str) -> str:
            parts = str(path or "").replace("\\", "/").split("/")
            chunks = [files.get(path, "")]
            if parts and parts[0] == "app":
                for end in range(1, max(1, len(parts) - 1)):
                    prefix = "/".join(parts[:end + 1])
                    for name in (f"{prefix}/layout.jsx", f"{prefix}/layout.js"):
                        if name != path and name in files:
                            chunks.append(files[name])
            return "\n".join(chunks)

        for phase in plan.get("phases") or []:
            if not isinstance(phase, dict):
                continue
            for item in phase.get("files") or []:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("path") or "").replace("\\", "/")
                if not re.fullmatch(r"app/(?:.+/)?page\.jsx?", path) or path not in files:
                    continue
                m = re.match(r"\s*ROLE\s+([^—:-]+)", str(item.get("purpose") or ""), re.I)
                if not m:
                    continue
                expected_roles = self._role_values(m.group(1))
                if not expected_roles:
                    continue
                body = guarded_source(path)
                authish = bool(re.search(
                    r"getSessionUser\s*\(|useSession\s*\(|/api/auth/get-session|session\??\.?user",
                    body, re.I))
                role_check = bool(re.search(r"(?:user|session(?:\?\.)?user)?(?:\?\.)?\.role|\brole\s*(?:===?|!==?)",
                                            body, re.I))
                missing_roles = [role for role in expected_roles if not re.search(
                    r"['\"]" + re.escape(role) + r"['\"]", body, re.I)]
                expected = ", ".join(expected_roles)
                if role_check and missing_roles:
                    out.append(Finding(
                        "blocker", "ROLE_PAGE_WRONG_ROLE",
                        f"{path} is planned for role(s) '{expected}', but its page/layout role guard never names: "
                        + ", ".join(missing_roles),
                        path=path,
                        fix=("guard this route for every exact planned role: "
                             + ", ".join(expected_roles)
                             + "; keep other role pages on their own role values"),
                        extra=[path]))
                elif not authish and not role_check:
                    out.append(Finding(
                        "major", "ROLE_PAGE_UNGUARDED",
                        f"{path} is a role-owned page for '{expected}' but neither the page nor its parent layouts establish an authenticated role",
                        path=path,
                        fix=f"read the session in the page or parent layout and allow the exact role '{expected}'",
                        extra=[path]))

        routes = self.enumerate_routes()
        for key, home in self._role_homes().items():
            if home not in routes:
                label = next((str(a.get("role") or "") for a in accounts
                              if self._role_key(a.get("role")) == key), key)
                out.append(Finding(
                    "major", "ROLE_HOME_MISSING",
                    f"role '{label}' is mapped to {home}, but no page serves that landing route",
                    fix=f"create the planned landing page {home} or map '{label}' to a real role-owned route"))
        return out

    def auth_flow_findings(self) -> list:
        """Role-aware apps must not authenticate everybody into the public root."""
        plan = getattr(self.arch, "plan", None) or {}
        roles = {str(a.get("role") or "").lower() for a in plan.get("demo_accounts") or []
                 if isinstance(a, dict) and a.get("role")}
        if len(roles) < 2:
            return []
        files = self.code_files()
        out = []
        for path, body in files.items():
            if not re.search(r"app/(?:login|sign-in|signin)/page\.jsx?$", path):
                continue
            if "signIn.email" not in body:
                continue
            hard_root = re.search(r"router\.(?:push|replace)\(\s*['\"]/['\"]\s*\)", body)
            role_logic = re.search(r"(?:data|session|user)(?:\?\.)?\.role|\brole\s*===?", body)
            if hard_root and not role_logic:
                out.append(Finding(
                    "major", "ROLE_REDIRECT",
                    f"{path} signs in a multi-role app but hard-codes every successful login to /; role-specific users can authenticate correctly and still land in the wrong area",
                    path=path,
                    fix="route successful login by the returned/session user role to each role's planned landing page",
                    extra=[path]))
                continue
            homes = self._role_homes()
            missing = []
            for acc in plan.get("demo_accounts") or []:
                if not isinstance(acc, dict):
                    continue
                role = str(acc.get("role") or "").strip()
                key = self._role_key(role)
                home = homes.get(key)
                if not home:
                    continue
                role_seen = bool(re.search(r"['\"]" + re.escape(role) + r"['\"]", body, re.I))
                home_seen = home == "/" or home in body
                if not (role_seen and home_seen):
                    missing.append(f"{role}→{home}")
            if missing:
                out.append(Finding(
                    "major", "ROLE_REDIRECT",
                    f"{path} does not encode the complete role landing matrix: " + ", ".join(missing[:8]),
                    path=path,
                    fix="after signIn.email, read the returned/refreshed session role and route each exact role to its planned landing page",
                    extra=[path]))
        return out


    def workflow_control_findings(self) -> list:
        """Quoted workflow clicks must exist in the page/component source.

        The E2E author cannot make a missing business control appear.  V13 let
        a plan say `/product/[id] — click 'Add to cart'` while the generated
        product UI exposed no such accessible action; Playwright then spent
        several rounds trying different selectors.  This conservative static
        gate only checks *quoted click labels from the accepted workflow*, so
        it does not invent UI requirements of its own.
        """
        plan = getattr(self.arch, "plan", None) or {}
        files = self.code_files()
        if not files:
            return []

        def route_file(route: str) -> str:
            route = str(route or "").strip().split('?', 1)[0]
            if not route.startswith('/'):
                return ""
            if route == '/':
                cands = ['app/page.jsx', 'app/page.js']
            else:
                tail = route.strip('/')
                cands = [f'app/{tail}/page.jsx', f'app/{tail}/page.js']
            for c in cands:
                if c in files:
                    return c
            # Dynamic route strings in the machine plan already use [id].
            return ""

        def imports(rel: str) -> list[str]:
            body = files.get(rel, "")
            out = []
            for spec in re.findall(r"(?:from\s+|import\s*\()\s*['\"](@/[^'\"]+|\.{1,2}/[^'\"]+)['\"]", body):
                if spec.startswith('@/'):
                    base = spec[2:]
                else:
                    base = str((Path(rel).parent / spec).as_posix())
                    while '/./' in base:
                        base = base.replace('/./','/')
                base = re.sub(r"\.(?:jsx?|tsx?)$", "", base)
                for ext in ('.jsx','.js','/index.jsx','/index.js'):
                    got = base + ext
                    if got in files:
                        out.append(got); break
            return out

        def closure(rel: str) -> list[str]:
            seen, q = set(), [(rel, 0)]
            while q:
                cur, depth = q.pop(0)
                if cur in seen or cur not in files or depth > 2:
                    continue
                seen.add(cur)
                if depth < 2:
                    q.extend((x, depth + 1) for x in imports(cur))
            return list(seen)

        def norm_words(text: str) -> set[str]:
            text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text or ""))
            stop = {'click','the','a','an','button','link','to','and','on','of'}
            return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3 and w not in stop}

        out = []
        seen = set()
        for wf in plan.get('workflows') or []:
            if not isinstance(wf, dict):
                continue
            for step in wf.get('steps') or []:
                step = str(step or '')
                # Accepted planner grammar: /route — click 'Control' — outcome
                m = re.search(r"^\s*(/[^—\n]*)\s*—\s*click\s+['\"]([^'\"]+)['\"]", step, re.I)
                if not m:
                    continue
                route, label = m.group(1).strip(), m.group(2).strip()
                owner = route_file(route)
                if not owner:
                    continue
                wanted = norm_words(label)
                if not wanted:
                    continue
                bundle = closure(owner)
                hay = ' '.join(files.get(x, '') + ' ' + x for x in bundle)
                got = norm_words(hay)
                if wanted <= got or len(wanted & got) >= max(1, len(wanted) - 1):
                    continue
                key = (owner, label.lower())
                if key in seen:
                    continue
                seen.add(key)
                out.append(Finding(
                    'major', 'MISSING_WORKFLOW_CONTROL',
                    f"workflow '{wf.get('name') or 'journey'}' requires clicking '{label}' on {route}, but that action is not present in the page/component source closure",
                    path=owner,
                    fix=f"implement the planned '{label}' action with an accessible name/testid and its real business effect",
                    extra=[x for x in bundle if x != owner][:3]))
        return out[:10]

    def capability_shape_findings(self) -> list:
        """Machine-plan completeness before semantic proof is attempted."""
        plan = getattr(self.arch, "plan", None) or {}
        caps = [c for c in plan.get("capabilities") or [] if isinstance(c, dict)]
        if not caps:
            return []
        planned = {f.get("path") for ph in plan.get("phases") or []
                   for f in ph.get("files") or [] if isinstance(f, dict)}
        covered = {str(cid).upper() for w in plan.get("workflows") or [] if isinstance(w, dict)
                   for cid in (w.get("covers") or [])}
        out = []
        for c in caps:
            cid = str(c.get("id") or "capability")
            cfiles = [str(x) for x in c.get("files") or []]
            missing = [x for x in cfiles if x not in planned]
            if not cfiles or missing:
                out.append(Finding(
                    "blocker", "CAPABILITY_UNMAPPED",
                    f"{cid} '{c.get('requirement','')}' has no complete planned file map" +
                    (f"; unplanned: {', '.join(missing)}" if missing else ""),
                    path=(cfiles[0] if cfiles else ""),
                    fix="repair the plan/build so every capability names the files that implement it",
                    extra=[x for x in cfiles if x]))
            if c.get("e2e", True) and cid.upper() not in covered:
                out.append(Finding(
                    "major", "CAPABILITY_UNWALKED",
                    f"{cid} '{c.get('requirement','')}' is user-visible but no E2E workflow covers it",
                    path=(cfiles[0] if cfiles else ""),
                    fix="add the capability to a workflow that actually performs and asserts it",
                    extra=[x for x in cfiles if x]))
        return out[:12]

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

        for f in self.missing_local_imports():
            r.findings.append(f)
        for f in self.broken_imports():
            r.findings.append(f)

        r.findings.extend(self.async_param_confusion())
        r.findings.extend(self.session_cookie_mismatch())
        r.findings.extend(self.unique_index_in_seed())
        r.findings.extend(self.prop_contract_breaks())
        r.findings.extend(self.credentials_exposed())
        r.findings.extend(self.seed_volume())
        r.findings.extend(self.mongo_id_type_findings())
        r.findings.extend(self.planned_data_findings())
        r.findings.extend(self.server_client_boundary_findings())
        r.findings.extend(self.unsupported_form_method_findings())
        r.findings.extend(self.inert_control_findings())
        r.findings.extend(self.role_contract_findings())
        r.findings.extend(self.role_page_findings())
        r.findings.extend(self.auth_flow_findings())
        r.findings.extend(self.capability_shape_findings())
        r.findings.extend(self.workflow_control_findings())

        for url in self.dead_endpoints(r.routes):
            handler = "app" + url + "/route.js"
            r.findings.append(Finding(
                "blocker", "DEAD_ENDPOINT",
                f"something fetches {url} but no route handler serves it, so "
                f"the call 404s — a client component that redirects when the "
                f"fetch fails will bounce the user out of the page",
                fix=f"write {handler}",
                extra=[handler]))

        r.findings.extend(self.contract_findings(r.routes))

        for url in r.dead_links:
            r.findings.append(Finding(
                "major", "DEAD_LINK",
                f"something links to {url} but no page serves it — a 404",
                fix=f"either create the page for {url} or remove the link"))

        orphans = self.unreachable_pages(r.routes)
        if orphans:
            shown = ", ".join(orphans[:8]) + ("…" if len(orphans) > 8 else "")

            files = self.code_files()
            repair_paths = []

            def add_path(rel):
                rel = str(rel or "").lstrip("./").replace("\\", "/")
                if rel and rel in files and rel not in repair_paths:
                    repair_paths.append(rel)

            add_path("components/Navbar.jsx")
            add_path("components/Navbar.js")
            add_path("app/page.jsx")
            add_path("app/page.js")

            contracts = (getattr(self.arch, "plan", None) or {}).get("contracts") or []
            for url in orphans[:12]:
                meta = r.routes.get(url) or {}
                add_path(meta.get("file"))

                for c in contracts:
                    if not isinstance(c, dict):
                        continue
                    target = str(c.get("target") or "").rstrip("/") or "/"
                    if target == (url.rstrip("/") or "/"):
                        add_path(c.get("from"))

                parent = url.rstrip("/")
                while "/" in parent.strip("/"):
                    parent = parent.rsplit("/", 1)[0] or "/"
                    pm = r.routes.get(parent) or {}
                    if pm.get("kind") == "page":
                        add_path(pm.get("file"))
                        break

            r.findings.append(Finding(
                "blocker", "NO_WAY_THERE",
                f"{len(orphans)} page(s) exist that nothing links to, so "
                f"nobody can reach them: {shown}",
                path=(repair_paths[0] if repair_paths else ""),
                fix="wire the planned navigation without changing page chrome: "
                    "put top-level role links in components/Navbar.jsx and render "
                    "that navbar on the applicable pages; link nested create/detail "
                    "routes from their parent list/card controls. Do NOT move the "
                    "navbar into the root layout when login/signup are meant to "
                    "stay bare",
                extra=repair_paths[1:12]))

        r.findings.extend(self.bad_objectid())
        r.findings.extend(self.unawaited_collection())

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
                r.findings.append(Finding(
                    "major", "LINT", problem, path=path,
                    fix=(f"repair {path} so the deterministic lint rule closes; "
                         "preserve existing behaviour and keep Server/Client "
                         "Component boundaries valid")))
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
        """Verify every demo login and, on Better Auth apps, its exact role."""
        if any(f.code == "ROUTE_ERROR" for f in report.findings):
            report.credentials = {"checked": [], "ok": None,
                                  "reason": "pages are failing; login cannot be judged until they serve"}
            self._log("INFO", "   ⏭  Skipping the login check — pages are still failing")
            return

        creds = self.demo_credentials()
        if not creds:
            report.credentials = {"checked": [], "ok": None, "reason": "no demo accounts"}
            return
        endpoint = self.find_login_endpoint()
        if not endpoint:
            report.credentials = {"checked": [], "ok": None, "reason": "no login endpoint"}
            report.findings.append(Finding(
                "major", "NO_LOGIN_ENDPOINT",
                "the plan lists demo accounts but no route handler verifies a password"))
            return

        expected = {str(a.get("email") or "").strip().lower(): str(a.get("role") or "").strip()
                    for a in (self.arch.plan or {}).get("demo_accounts", []) or []
                    if isinstance(a, dict) and a.get("email")}
        better = "betterAuth(" in self.code_files().get("lib/auth.js", "")
        checked, failures, unreachable = [], [], False

        import http.cookiejar
        for email, password in creds:
            jar = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            payload = json.dumps({"email": email, "password": password}).encode()
            req = urllib.request.Request(
                self.base_url + endpoint, data=payload, method="POST",
                headers={"Content-Type": "application/json"})
            status, body = None, ""
            try:
                with opener.open(req, timeout=15) as resp:
                    status, body = resp.status, resp.read(2000).decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                status = e.code
                try:
                    body = e.read(2000).decode("utf-8", "replace")
                except Exception:
                    body = ""
            except Exception:
                unreachable = True

            if unreachable or status is None:
                break

            actual_email = actual_role = ""
            if status < 400 and better:
                try:
                    with opener.open(self.base_url + "/api/auth/get-session", timeout=10) as resp:
                        session = json.loads(resp.read(4000).decode("utf-8", "replace") or "{}")
                    user = session.get("user") if isinstance(session, dict) else {}
                    if isinstance(user, dict):
                        actual_email = str(user.get("email") or "").strip().lower()
                        actual_role = str(user.get("role") or "").strip()
                except Exception as e:
                    log.debug(f"session identity after login {email}: {e}")

            exp_email = str(email).strip().lower()
            exp_role = expected.get(exp_email, "")
            row = {"email": email, "status": status, "expected_role": exp_role}
            if actual_email or actual_role:
                row.update({"session_email": actual_email, "session_role": actual_role})
            checked.append(row)

            good = status < 400
            if good and better:
                good = (actual_email == exp_email and
                        (not exp_role or self._role_key(actual_role) == self._role_key(exp_role)))
            self._fire("on_test", "pass" if good else "fail",
                       f"Login {email}",
                       f"HTTP {status}" + (f", role {actual_role or 'missing'}" if better else ""))

            if status in (401, 403):
                failures.append((email, password, status, body, "credentials"))
            elif status >= 400:
                report.findings.append(Finding(
                    "major", "LOGIN_ERROR",
                    f"POST {endpoint} returned {status} for {email}: {(body or '')[:160]}"))
            elif better and not good:
                failures.append((email, password, status, body, "identity"))
                report.findings.append(Finding(
                    "blocker", "ROLE_IDENTITY_MISMATCH",
                    f"{email} signs in, but /api/auth/get-session returned "
                    f"{actual_email or 'no email'} with role {actual_role or 'missing'}; "
                    f"the plan requires role {exp_role or 'unspecified'}",
                    path="lib/seed.js",
                    fix="seed every demo account through Better Auth, then update that exact user email with its exact planned role; do not reuse one role for every account",
                    extra=["lib/auth.js", "app/login/page.jsx"]))

        if unreachable:
            report.credentials = {"checked": checked, "ok": None, "reason": "endpoint unreachable"}
            return

        report.credentials = {"endpoint": endpoint, "checked": checked, "ok": not failures}
        for email, password, status, _, kind in failures:
            if kind != "credentials":
                continue
            report.findings.append(Finding(
                "blocker", "BAD_CREDENTIALS",
                f"POST {endpoint} with the planned demo credentials ({email}) returned {status}",
                path=self.enumerate_routes().get(endpoint, {}).get("file", ""),
                fix=f"create {email} through the app's auth provider with the planned password and preserve its planned role"))
