"""Auth Checks.

Every method here owns one closely related analyzer responsibility.
"""
from __future__ import annotations

# Source: analysis_shared.py — shared finding types, constants and helper imports.
from agents.analysis.analysis_shared import (
    Finding,
    _strip_noncode,
    re,
)
# Source: planning_helpers.py — the same auth route spellings the planner allows.
from agents.planner.planning.planning_helpers import SIGN_IN_PATHS, SIGN_UP_PATHS

class AuthChecksMixin:
    """Keep auth checks behavior together."""

    # Inspect the generated source for auth problems and return evidence only when a real issue is found.
    def _auth_invariants(self):
        """Prepare the auth invariants value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        files, plan, out = self.code_files(), getattr(self.arch, "plan", None) or {}, []
        # From: agents/analysis/checks/route_checks.py
        auth, routes = files.get("lib/auth.js", ""), self.enumerate_routes()
        if "betterAuth(" in auth:
            seeds = {p: b for p, b in files.items() if "seed" in p.lower()}
            account_rows = (plan.get("roles_and_access") or {}).get("demo_accounts") or plan.get("demo_accounts") or []
            accounts = [a for a in account_rows if isinstance(a, dict) and a.get("email") and a.get("password")]
            for path, body in seeds.items():
                # From: agents/analysis/analysis_shared.py
                if re.search(r"betterAuth\s*\(|from\s+['\"]better-auth|auth\.api\.signUpEmail", body):
                    # From: agents/analysis/analysis_shared.py
                    out.append(Finding("blocker", "AUTH_LOGIC_IN_SEED", "product seeding implements Better Auth credential logic instead of delegating to lib/auth", path, "call ensureDemoAccounts() from @/lib/auth; keep provider/signup logic only in lib/auth", ["lib/auth.js"]))
                # From: agents/analysis/analysis_shared.py
                if re.search(r"(?:getCollection|collection)\s*\(\s*['\"]users['\"]", body):
                    # From: agents/analysis/analysis_shared.py
                    out.append(Finding("blocker", "BETTER_AUTH_USER_COLLECTION", "seed reads plural users collection, but Better Auth stores identities in singular user", path, "await ensureDemoAccounts(), then read collection('user') by demo email before owned rows", ["lib/auth.js"]))
            # From: agents/analysis/analysis_shared.py
            if accounts and not any(re.search(r"\bensureDemoAccounts\s*\(", b) for b in seeds.values()): out.append(Finding("blocker", "BETTER_AUTH_DEMO_SEED", "planned demo users are not provisioned before product rows are seeded", next(iter(seeds), "lib/seed.js"), "await ensureDemoAccounts() from @/lib/auth before seeding owned product data", ["lib/auth.js"]))
            # From: agents/analysis/analysis_shared.py
            origins = set(re.findall(r"(?:https?://)?(localhost:\*|127\.0\.0\.1:\*)", auth))
            # From: agents/analysis/analysis_shared.py
            if origins != {"localhost:*", "127.0.0.1:*"}: out.append(Finding("blocker", "AUTH_ORIGIN", "Better Auth does not trust both loopback preview hosts on moving ports", "lib/auth.js", "trust http://localhost:* and http://127.0.0.1:* only"))
            provider = files.get("app/api/auth/[...all]/route.js", "")
            # From: agents/analysis/analysis_shared.py
            if not provider or not all(x in provider for x in ("GET", "POST")): out.append(Finding("blocker", "AUTH_PROVIDER_ROUTE", "Better Auth has no complete GET/POST catch-all provider route", "app/api/auth/[...all]/route.js", "delegate GET and POST to the auth instance exported by lib/auth.js"))
            access = plan.get("roles_and_access") or {}
            signup_open = str(access.get("signup") or "").strip().lower() == "open"
            signup = next((m for u, m in routes.items()
                           if u in {"/sign-up", "/signup", "/register"}), None)
            signup_body = files.get(signup["file"], "") if signup else ""
            if signup_open and "signUp.email" not in signup_body:
                # From: agents/analysis/analysis_shared.py
                out.append(Finding(
                    "blocker", "AUTH_SIGNUP_MISSING",
                    "open registration has no page completing Better Auth email signup",
                    signup["file"] if signup else "app/sign-up/page.jsx",
                    "serve an accessible form using signUp.email with failure and success states"))
        for rel, body in files.items():
            # From: agents/analysis/analysis_shared.py
            if rel != "lib/auth.js" and re.search(r'(?:getCollection|collection)\s*\(\s*[\'"]user[\'"]', body) and re.search(r"\bpassword\b", body) and re.search(r"\b(?:insertOne|replaceOne|updateOne)\s*\(", body): out.append(Finding("blocker", "AUTH_PROVIDER_BYPASS", "creates or mutates a login user directly in Mongo with a password, so Better Auth has no credential account", rel, "call provisionUser from @/lib/auth for runtime account creation; keep profile-only updates password-free", ["lib/auth.js"]))
        # From: agents/analysis/checks/route_checks.py
        for target in self.dead_links(routes):
            # From: agents/analysis/analysis_shared.py
            if target in {"/sign-in", "/signin", "/login"}: out.append(Finding("blocker", "AUTH_PAGE_MISSING", f"auth code links or redirects to {target}, but no page serves it", f"app/{target.strip('/')}/page.jsx", "create the complete sign-in page using @/lib/auth-client, or consistently use a served auth page"))
        for rel, body in files.items():
            # From: agents/analysis/analysis_shared.py
            for var in re.findall(r"(?:const|let|var)\s+(\w+)\s*=\s*await\s+getSessionUser\s*\(", body):
                # From: agents/analysis/analysis_shared.py
                if re.search(rf"\b{re.escape(var)}\s*\.\s*_id\b", body): out.append(Finding("blocker", "SESSION_USER_ID", f"reads {var}._id from a Better Auth session; the string id is {var}.id", rel, f"use {var}.id and convert only at the Mongo boundary"))
            # From: agents/analysis/analysis_shared.py
            if re.search(r"if\s*\([^)]*(?:role|permission)[^)]*\)[\s\S]{0,100}redirect\(\s*['\"]/(?:login|sign-in)", body, re.I): out.append(Finding("blocker", "AUTHZ_REDIRECT", "a wrong-role signed-in user is redirected back to the sign-in page", rel, "separate no-session and wrong-role redirects"))
            seed, redirect = body.find("ensureSeeded("), body.find("redirect(")
            # From: agents/analysis/analysis_shared.py
            if seed >= 0 and 0 <= redirect < seed: out.append(Finding("blocker", "SEED_BEHIND_AUTH", "ensureSeeded runs after an auth redirect and cannot create the first demo identity", rel, "seed before reading the session"))
        return out + self.role_contract_findings() + self.role_page_findings() + self.auth_flow_findings() + self.navbar_auth_findings()

    # An auth page asks for exactly one thing, so the shared bar has to stand down on it — a nav full of
    # destinations invites the visitor to leave before they finish signing in. The contract says to do it inside
    # the Navbar with the current pathname, so this reads the Navbar rather than guessing at layouts.
    def navbar_auth_findings(self):
        """No Navbar and no Footer on the planned sign-in and sign-up routes."""
        # From: agents/analysis/checks/scan_state.py
        plan, files = getattr(self.arch, "plan", None) or {}, self.code_files()
        owner = next((rel for rel in ("components/Chrome.jsx", "components/Chrome.js",
                                      "app/layout.jsx", "app/layout.js")
                      if files.get(rel)), "")
        auth_paths = sorted({str(route.get("path") or "") for route in plan.get("routes") or []
                             if str(route.get("path") or "") in SIGN_IN_PATHS | SIGN_UP_PATHS})
        if not owner or not auth_paths:
            return []
        # Naming the path is not standing down on it: a Navbar reads
        # `usePathname()` and spells `/login` for its own active-link highlight
        # and sign-in link while still rendering on every route.
        showing = [path for path in auth_paths
                   if not self._chrome_stands_down(files[owner], path)]
        if not showing:
            return []
        # From: agents/analysis/analysis_shared.py
        return [Finding("major", "NAVBAR_ON_AUTH_PAGE", f"the shared Navbar and Footer still render on {', '.join(showing)}, so the auth form competes with a bar full of destinations", owner, f"in components/Chrome.jsx read usePathname() from next/navigation and return the children alone, with no Navbar and no Footer, on {', '.join(auth_paths)}", [owner])]

    # Does the shared frame actually stand down on this path, rather than merely name it?.
    @staticmethod
    def _chrome_stands_down(body: str, path: str) -> bool:
        """Does the shared frame stand down on this path, rather than name it?"""
        # From: agents/analysis/analysis_shared.py
        quoted = re.compile(r"['\"`]" + re.escape(path) + r"['\"`]")
        # `const BARE = ['/login', '/register']`, tested further down the file.
        holders = {m.group(1) for m in
                   re.finditer(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:new\s+Set\s*\(\s*)?\[[^\]]*\]", body)
                   if quoted.search(m.group(0))}
        # From: agents/analysis/analysis_shared.py
        for hit in re.finditer(r"return\s+([^;\n]{0,160})", body):
            guard = body[max(0, hit.start() - 300):hit.start()]
            if "pathname" not in guard:
                continue
            if not (quoted.search(guard) or any(name in guard for name in holders)):
                continue
            # The early return for an auth route renders neither piece of chrome.
            if "Navbar" not in hit.group(1) and "Footer" not in hit.group(1):
                return True
        return False

    # Inspect the generated source for role contract problems and return evidence only when a real issue is found.
    def role_contract_findings(self):
        """Prepare the role contract findings value or state used by this focused pipeline step."""
        plan, out = getattr(self.arch, "plan", None) or {}, []
        accounts = [a for a in plan.get("demo_accounts") or [] if isinstance(a, dict)]
        required = {self._role_key(a.get("role")) for a in accounts if a.get("role")}
        for flow in plan.get("workflows") or []:
            # One workflow usually serves several roles, so `who` comes back as
            # "Customer/Store manager/Admin". Canonicalizing that whole string
            # asked for a role named `customerstoremanageradmin`, which no seed
            # can ever satisfy.
            if isinstance(flow, dict):
                for role in (self._role_key(x) for x in self._role_values(flow.get("who"))):
                    if role not in {"", "public", "visitor", "anonymous", "signedout"}: required.add(role)
        for phase in plan.get("phases") or []:
            for item in phase.get("files") or []:
                # From: agents/analysis/analysis_shared.py
                # From: agents/planner/builder/project_memory.py
                if isinstance(item, dict) and (m := re.match(r"\s*ROLE\s+([^—:-]+)", str(item.get("purpose") or ""), re.I)): required.update(self._role_key(x) for x in self._role_values(m.group(1)))
        # Only a name the plan declares is a role. That `ROLE\s+` match also
        # reads prose: the purpose "Role management API" — the API that manages
        # roles — asked for a role named `managementapi`, and every invented
        # name became a blocker no repair round could ever close.
        declared = {self._role_key(role.get("name")) for role in
                    (plan.get("roles_and_access") or {}).get("roles") or []
                    if isinstance(role, dict)}
        required &= declared | {self._role_key(a.get("role")) for a in accounts if a.get("role")}
        by_role, by_email = {}, {}
        for account in accounts:
            role, email = self._role_key(account.get("role")), str(account.get("email") or "").lower()
            if role and email: by_role.setdefault(role, []).append(account); by_email.setdefault(email, set()).add(role)
        if len(required) < 2: return []
        # From: agents/analysis/analysis_shared.py
        for role in sorted(required - set(by_role)): out.append(Finding("blocker", "ROLE_ACCOUNT_CONTRACT", f"planned signed-in role '{role}' has no unique demo identity", "lib/seed.js", "seed one Better Auth demo account for this exact canonical role"))
        for role, rows in by_role.items():
            # From: agents/analysis/analysis_shared.py
            if len(rows) != 1: out.append(Finding("blocker", "ROLE_ACCOUNT_CONTRACT", f"role '{role}' has {len(rows)} demo identities; exactly one is required", "lib/seed.js", "keep one unique email/password per role"))
        for email, roles in by_email.items():
            # From: agents/analysis/analysis_shared.py
            if len(roles) > 1: out.append(Finding("blocker", "ROLE_ACCOUNT_CONTRACT", f"demo email {email} is assigned to multiple roles", "lib/seed.js", "use a distinct identity per role"))
        return out

    # Inspect the generated source for role page problems and return evidence only when a real issue is found.
    def role_page_findings(self):
        """Prepare the role page findings value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        plan, files, out = getattr(self.arch, "plan", None) or {}, self.code_files(), []
        if len([a for a in plan.get("demo_accounts") or [] if isinstance(a, dict) and a.get("role")]) < 2: return []
        for phase in plan.get("phases") or []:
            for item in phase.get("files") or []:
                if not isinstance(item, dict): continue
                # From: agents/analysis/analysis_shared.py
                path = str(item.get("path") or ""); match = re.match(r"\s*ROLE\s+([^—:-]+)", str(item.get("purpose") or ""), re.I)
                # From: agents/analysis/checks/route_checks.py
                if not match or path not in files or not self._route_from_page_path(path): continue
                body, roles = files[path], self._role_values(match.group(1))
                # From: agents/analysis/analysis_shared.py
                authish, roleish = re.search(r"getSessionUser|useSession|get-session|session\??\.?user", body, re.I), re.search(r"\brole\b", body, re.I)
                # From: agents/analysis/analysis_shared.py
                missing = [r for r in roles if roleish and not re.search(r"['\"]" + re.escape(r) + r"['\"]", body, re.I)]
                # From: agents/analysis/analysis_shared.py
                if missing: out.append(Finding("blocker", "ROLE_PAGE_WRONG_ROLE", f"planned role page never names {', '.join(missing)} in its guard", path, "allow every exact planned role", [path]))
                # From: agents/analysis/analysis_shared.py
                elif not authish and not roleish: out.append(Finding("major", "ROLE_PAGE_UNGUARDED", f"role-owned page for {', '.join(roles)} has no session/role guard", path, "establish the authenticated role here or in its layout", [path]))
        for role, home in self._role_homes().items():
            # From: agents/analysis/analysis_shared.py
            # From: agents/analysis/checks/route_checks.py
            if not self._route_matches(home, self.enumerate_routes()): out.append(Finding("major", "ROLE_HOME_MISSING", f"role '{role}' maps to {home}, but no page serves it", fix="create the landing page or map the role to a served route"))
        return out

    # Inspect the generated source for auth flow problems and return evidence only when a real issue is found.
    def auth_flow_findings(self):
        """Prepare the auth flow findings value or state used by this focused pipeline step."""
        plan, out = getattr(self.arch, "plan", None) or {}, []
        roles = {self._role_key(a.get("role")) for a in plan.get("demo_accounts") or [] if isinstance(a, dict) and a.get("role")}
        if len(roles) < 2: return []
        # From: agents/analysis/checks/scan_state.py
        for path, body in self.code_files().items():
            # From: agents/analysis/analysis_shared.py
            if not re.search(r"app/(?:login|sign-in|signin)/page\.jsx?$", path) or "signIn.email" not in body: continue
            # From: agents/analysis/analysis_shared.py
            clean = _strip_noncode(body)
            # From: agents/analysis/analysis_shared.py
            if re.search(r"router\.(?:push|replace)\(\s*['\"]/['\"]", clean) and not re.search(r"\brole\b", clean): out.append(Finding("blocker", "ROLE_REDIRECT", "multi-role sign-in hard-codes every successful identity to /", path, "route result.data.user.role to its planned home; never bounce through /", [path]))
            # From: agents/analysis/analysis_shared.py
            if re.search(r"callbackURL\s*:\s*['\"]/(?:login|sign-in|signin)/?['\"]", clean): out.append(Finding("blocker", "AUTH_SELF_CALLBACK", "successful sign-in redirects back to the auth form itself", path, "remove the self callback and navigate to the signed-in role home", [path]))
        return out

    # A sign-in page branching on a field Better Auth never returns. `signIn.email` resolves to `{ data, error }`.
    # Reading `.success` off it is always undefined, so the correct-password path takes the failure branch: the cookie
    # is set and the navbar updates to the user's name while the form says "Invalid email or password" and never
    # navigates. Nothing else catches it — the network call is a 200, the session is real, and only a human looking at
    # the screen can tell.
    def _auth_result_misread(self):
        """A sign-in page branching on a field Better Auth never returns.

        `signIn.email` resolves to `{ data, error }`. Reading `.success` off it
        is always undefined, so the correct-password path takes the failure
        branch: the cookie is set and the navbar updates to the user's name
        while the form says "Invalid email or password" and never navigates.
        Nothing else catches it — the network call is a 200, the session is
        real, and only a human looking at the screen can tell.
        """
        out = []
        # From: agents/analysis/checks/scan_state.py
        for rel, body in sorted(self.code_files().items()):
            if not rel.startswith(("app/", "components/")):
                continue
            if not self._AUTH_CALL_RE.search(body):
                continue
            if not self._AUTH_SUCCESS_RE.search(body):
                continue
            # From: agents/analysis/analysis_shared.py
            out.append(Finding(
                "blocker", "AUTH_RESULT_MISREAD",
                "branches on a `success` field that signIn.email never returns, "
                "so a correct password takes the failure path and the form "
                "reports invalid credentials while the session is created",
                rel,
                "test `if (result.error)` for failure and read the signed-in "
                "person from `result.data.user`, whose role is "
                "`result.data.user.role`", [rel]))
        return out

    # Restricted pages written as Client Components, so nothing guards them. The pattern is not random: the page needs
    # a form or a modal, the model reaches for 'use client', and the session read has to go with it, because
    # getSessionUser and redirect do not exist in the browser. What ships is a page the plan restricts to one role
    # that anybody can open by typing the URL. Measured on a venue build: five of nine protected pages, every one of
    # them the interactive one. The repair is never "add a check to this file" — a client file cannot hold one. It is
    # the split: the page becomes the server file that reads the session, and its interactive half moves into a client
    # component.
    def _unguarded_client_pages(self):
        """Restricted pages written as Client Components, so nothing guards them.

        The pattern is not random: the page needs a form or a modal, the model
        reaches for 'use client', and the session read has to go with it,
        because getSessionUser and redirect do not exist in the browser. What
        ships is a page the plan restricts to one role that anybody can open by
        typing the URL. Measured on a venue build: five of nine protected
        pages, every one of them the interactive one.

        The repair is never "add a check to this file" — a client file cannot
        hold one. It is the split: the page becomes the server file that reads
        the session, and its interactive half moves into a client component.
        """
        plan = getattr(self.arch, "plan", None) or {}
        # From: agents/analysis/checks/route_checks.py
        routes = self.enumerate_routes()
        restricted = {}
        for entry in (plan.get("routes") or []) + (plan.get("site_map") or []):
            if not isinstance(entry, dict):
                continue
            audience = str(entry.get("audience") or "")
            if "ROLE" not in audience.upper():
                continue
            file = str(entry.get("file") or "")
            if not file:
                file = str((routes.get(str(entry.get("path") or "")) or {}).get("file") or "")
            if file.endswith((".js", ".jsx")):
                restricted.setdefault(file, audience.split("ROLE", 1)[-1].strip())

        # From: agents/analysis/checks/scan_state.py
        out, bodies = [], self.code_files()
        for rel, role in sorted(restricted.items()):
            body = bodies.get(rel)
            if not body or not self._CLIENT_RE.search(body) or "getSessionUser" in body:
                continue
            # From: agents/analysis/analysis_shared.py
            out.append(Finding(
                "blocker", "CLIENT_PAGE_UNGUARDED",
                f"the plan gives this page to {role}, but it is a Client "
                f"Component, so the session is never read and anyone who types "
                f"the URL opens it", rel,
                "make the page a Server Component that reads the session, "
                "checks the role and redirects, and move the interactive part "
                "into a client component it renders", [rel]))
        return out

    # Derive role key from the planned roles so authentication checks compare consistent values.
    @staticmethod
    def _role_key(value):
        """Prepare the role key value or state used by this focused pipeline step."""
        # From: agents/analysis/analysis_shared.py
        role = re.sub(r"^(?:as\s+)?role(?:\s+|[_:=\-]+\s*)", "", str(value or "").strip().lower())
        # From: agents/analysis/analysis_shared.py
        return re.sub(r"[^a-z0-9]+", "", role)

    # Derive role values from the planned roles so authentication checks compare consistent values.
    @classmethod
    def _role_values(cls, value):
        """Prepare the role values value or state used by this focused pipeline step."""
        # From: agents/analysis/analysis_shared.py
        return [x.strip() for x in re.split(r"\s*(?:,|\||&|/|\bor\b)\s*", str(value or ""), flags=re.I) if cls._role_key(x)]

    # Derive role homes from the planned roles so authentication checks compare consistent values.
    def _role_homes(self):
        """Prepare the role homes value or state used by this focused pipeline step."""
        plan, out = getattr(self.arch, "plan", None) or {}, {}
        for role, route in (plan.get("role_homes") or {}).items():
            if self._role_key(role) and str(route).startswith("/"): out[self._role_key(role)] = str(route).split("?", 1)[0].rstrip("/") or "/"
        for phase in plan.get("phases") or []:
            for item in phase.get("files") or []:
                if not isinstance(item, dict): continue
                # From: agents/analysis/analysis_shared.py
                match = re.match(r"\s*ROLE\s+([^—:-]+)", str(item.get("purpose") or ""), re.I)
                # From: agents/analysis/checks/route_checks.py
                route = self._route_from_page_path(item.get("path"))
                if match and route and "[" not in route:
                    for role in self._role_values(match.group(1)): out.setdefault(self._role_key(role), route)
        return out

    # Check the generated source for better auth demo seed and return the small result used by the Analyzer.
    def better_auth_demo_seed(self):
        """Prepare the better auth demo seed value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._auth_invariants(), "BETTER_AUTH_DEMO_SEED")

    # Check the generated source for auth origin and return the small result used by the Analyzer.
    def auth_origin(self):
        """Prepare the auth origin value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._auth_invariants(), "AUTH_ORIGIN")

    # Check the generated source for session user id and return the small result used by the Analyzer.
    def session_user_id(self):
        """Prepare the session user id value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._auth_invariants(), "SESSION_USER_ID")

    # Check the generated source for authz redirect and return the small result used by the Analyzer.
    def authz_redirect(self):
        """Prepare the authz redirect value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._auth_invariants(), "AUTHZ_REDIRECT")

    # Check the generated source for seed behind auth and return the small result used by the Analyzer.
    def seed_behind_auth(self):
        """Prepare the seed behind auth value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._auth_invariants(), "SEED_BEHIND_AUTH")

    # Check the generated source for seed race and return the small result used by the Analyzer.
    def seed_race(self):
        """Prepare the seed race value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/data_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._data_ui_invariants(), "SEED_RACE")

    # Check the generated source for stale seed guard and return the small result used by the Analyzer.
    def stale_seed_guard(self):
        """Prepare the stale seed guard value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/data_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._data_ui_invariants(), "STALE_SEED_GUARD")

    # Check the generated source for unique index in seed and return the small result used by the Analyzer.
    def unique_index_in_seed(self):
        """Prepare the unique index in seed value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/data_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._data_ui_invariants(), "UNIQUE_INDEX_IN_SEED")

    # Check the generated source for credential smells and return the small result used by the Analyzer.
    def credential_smells(self):
        """Prepare the credential smells value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/data_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._data_ui_invariants(), "FAKE_HASH", "UNHASHED_SEED")

    # Check the generated source for auth completeness and return the small result used by the Analyzer.
    def auth_completeness(self):
        """Prepare the auth completeness value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._auth_invariants(), "AUTH_PAGE_MISSING",
                          "AUTH_SIGNUP_MISSING", "AUTH_PROVIDER_ROUTE")

    # Inspect the generated source for session cookie mismatch problems and return evidence only when a real issue is
    # found.
    def session_cookie_mismatch(self):
        """Prepare the session cookie mismatch value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/code_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._cross_file_invariants(), "SESSION_COOKIE_MISMATCH")

    # Inspect the generated source for credentials exposed problems and return evidence only when a real issue is
    # found.
    def credentials_exposed(self):
        """Prepare the credentials exposed value or state used by this focused pipeline step."""
        # From: agents/analysis/runtime/runtime_probe.py
        passwords = {password for _, password in self.demo_credentials() if password}
        out = []
        # From: agents/analysis/checks/scan_state.py
        for path, body in self.code_files().items():
            if not path.startswith(("app/", "components/")): continue
            # From: agents/analysis/analysis_shared.py
            visible = re.sub(r"placeholder\s*=\s*[\"'{][^\"'}]*[\"'}]", "", body)
            exposed = next((p for p in passwords if p in visible), "")
            # From: agents/analysis/analysis_shared.py
            panel = re.search(r"(?:Demo Accounts?|Test Credentials?)[\s\S]{0,500}[\w.+-]+@[\w.-]+\.\w+", visible, re.I)
            # From: agents/analysis/analysis_shared.py
            prefill = re.search(r"(?:defaultValue|useState)\s*[=(]\s*['\"][\w.+-]+@", visible)
            # From: agents/analysis/analysis_shared.py
            if exposed or panel or prefill: out.append(Finding(
                "major", "CREDS_IN_UI", "demo credentials are rendered inside the generated app",
                path, "remove credential panels and prefilled identities; show them only in AgentForge"))
        return out
