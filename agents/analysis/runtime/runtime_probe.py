"""Runtime Probe.

Every method here owns one closely related analyzer responsibility.
"""
from __future__ import annotations

# Source: analysis_shared.py — shared finding types, constants and helper imports.
from agents.analysis.analysis_shared import (
    AnalyzerReport,
    Finding,
    http,
    json,
    re,
    urllib,
)

class RuntimeProbeMixin:
    """Keep runtime probe behavior together."""

    # Read the status used by this pipeline step.
    @staticmethod
    def _get_status(url, timeout=60):
        """Read the status used by this pipeline step."""
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response: return response.status
        except urllib.error.HTTPError as exc: return exc.code
        except Exception: return None

    # Sends a small JSON POST request to the running app and return its status and response data.
    @staticmethod
    def _post_json(url, payload, timeout=15):
        """Prepare the post json value or state used by this focused pipeline step."""
        # From: agents/analysis/analysis_shared.py
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json"})
        try:
            # From: agents/data/database_helpers.py
            with urllib.request.urlopen(req, timeout=timeout) as response: return response.status, response.read(2000).decode("utf-8", "replace")
        # From: agents/data/database_helpers.py
        except urllib.error.HTTPError as exc: return exc.code, exc.read(2000).decode("utf-8", "replace")
        except Exception: return None, ""

    # Probe pages and return clear evidence to the next pipeline step.
    def probe_pages(self, report, *, skip_root=False):
        """Probe pages and return clear evidence to the next pipeline step."""
        for url, meta in sorted(report.routes.items()):
            if meta["kind"] != "page" or meta["dynamic"] or skip_root and url == "/": continue
            status = self._get_status(self.base_url + url)
            if status is None: return
            self._fire("on_test", "fail" if status >= 400 else "pass", f"Route {url}", f"HTTP {status}")
            # From: agents/analysis/analysis_shared.py
            if status >= 400: report.findings.append(Finding("blocker", "ROUTE_ERROR", f"{url} returns HTTP {status}", meta["file"], f"fix {meta['file']} so {url} responds"))

    # Probe api routes and return clear evidence to the next pipeline step.
    def probe_api_routes(self, report, *, skip_health=False):
        """Probe api routes and return clear evidence to the next pipeline step."""
        for url, meta in sorted(report.routes.items()):
            if meta["kind"] != "api" or meta["dynamic"] or "GET" not in meta["methods"] or skip_health and url == "/api/health": continue
            status = self._get_status(self.base_url + url)
            if status is None: return
            bad = status == 404 or status >= 500; self._fire("on_test", "fail" if bad else "pass", f"API {url}", f"HTTP {status}")
            # From: agents/analysis/analysis_shared.py
            if bad: report.findings.append(Finding("blocker", "ROUTE_ERROR", f"{url} returns HTTP {status}", meta["file"], f"fix {meta['file']} so {url} responds"))

    # Probe routes and return clear evidence to the next pipeline step.
    def probe_routes(self, report):
        """Probe routes and return clear evidence to the next pipeline step."""
        self.probe_pages(report); self.probe_api_routes(report)

    # Probe linked dynamic routes and return clear evidence to the next pipeline step.
    def probe_linked_dynamic_routes(self, report, limit=24):
        """Probe linked dynamic routes and return clear evidence to the next pipeline step."""
        dynamic = {u: m for u, m in report.routes.items() if m["kind"] == "page" and m["dynamic"]}; seen = set()
        for origin, meta in sorted(report.routes.items()):
            if len(seen) >= limit or meta["kind"] != "page" or meta["dynamic"]: continue
            try:
                # From: agents/data/database_helpers.py
                with urllib.request.urlopen(self.base_url + origin, timeout=30) as response: html = response.read(1_500_000).decode("utf-8", "replace")
            except Exception: continue
            # From: agents/analysis/analysis_shared.py
            for raw in re.findall(r'''href=["'](/[^"']+)["']''', html, re.I):
                # From: agents/analysis/checks/route_checks.py
                path = raw.split("?", 1)[0].split("#", 1)[0]; match = next(((pat, item) for pat, item in dynamic.items() if self._route_matches(path, [pat])), None)
                if not match or path in seen: continue
                seen.add(path); pattern, route = match; report.runtime_examples.setdefault(route["file"], []).append(raw); status = self._get_status(self.base_url + raw, 45)
                # From: agents/analysis/analysis_shared.py
                if status == 404 or status and status >= 500: report.findings.append(Finding("blocker", "DYNAMIC_ROUTE_ERROR", f"{origin} renders {raw}, matching {pattern}, but it returns HTTP {status}", route["file"], "repair the detail route for the real runtime id", [meta["file"], route["file"]]))
                if len(seen) >= limit: break

    # Finds login endpoint and return clear evidence to the next pipeline step.
    def find_login_endpoint(self):
        """Find login endpoint and return clear evidence to the next pipeline step."""
        # From: agents/analysis/checks/route_checks.py
        # From: agents/analysis/checks/scan_state.py
        routes, files = self.enumerate_routes(), self.source_files()
        for url, meta in routes.items():
            body = files.get(meta["file"], "")
            if meta["kind"] == "api" and ("bcrypt.compare" in body or "compareSync" in body): return url
        for url, meta in routes.items():
            body = files.get(meta["file"], "")
            # From: agents/analysis/analysis_shared.py
            if meta["kind"] == "api" and "better-auth" in body and "POST" in meta["methods"]: return re.sub(r"/\[\.\.\.[^\]]+\]$", "", url).rstrip("/") + "/sign-in/email"
        return next((u for u, m in routes.items() if m["kind"] == "api" and "POST" in m["methods"] and any(x in u.lower() for x in ("login", "signin", "authenticate"))), "")

    # Collect the demo login credentials that runtime checks can safely use.
    def demo_credentials(self):
        """Prepare the demo credentials value or state used by this focused pipeline step."""
        plan = getattr(self.arch, "plan", None) or {}; creds = [(a["email"], a["password"]) for a in plan.get("demo_accounts") or [] if isinstance(a, dict) and a.get("email") and a.get("password")]
        if creds: return creds
        # From: agents/analysis/analysis_shared.py
        # From: agents/analysis/checks/scan_state.py
        section = re.search(r"^#+ Demo Accounts\s*$(.*?)(?=^#+ |\Z)", self.plan_text(), re.M | re.S); out = []
        for line in section.group(1).splitlines() if section else []:
            cells = [x.strip().strip("`*") for x in line.split("|")]
            for i, cell in enumerate(cells[:-1]):
                # From: agents/analysis/analysis_shared.py
                if re.fullmatch(r"[\w.+-]+@[\w.-]+\.\w+", cell) and len(cells[i+1]) >= 6: out.append((cell, cells[i+1])); break
        return out

    # Read demo credentials from the generated seed/auth source when they are available.
    def _credentials_from_seed(self):
        """Prepare the credentials from seed value or state used by this focused pipeline step."""
        # From: agents/analysis/analysis_shared.py
        # From: agents/analysis/checks/scan_state.py
        seed = "\n".join(b for p, b in self.code_files().items() if "seed" in p.lower()); emails = re.findall(r"email\s*:\s*['\"]([\w.+-]+@[\w.-]+\.\w+)['\"]", seed)
        # From: agents/analysis/analysis_shared.py
        passwords = [a or b for a, b in re.findall(r"(?:password\s*:\s*['\"]([^'\"]{4,})['\"]|hashSync\s*\(\s*['\"]([^'\"]{4,})['\"])", seed)]
        return list(zip(emails, passwords)) if len(passwords) == len(emails) else []

    # Report which demo credentials were discovered without changing the authentication state.
    def _announce_credentials(self, report=None):
        """Prepare the announce credentials value or state used by this focused pipeline step."""
        roles = {a.get("email"): a.get("role", "") for a in (getattr(self.arch, "plan", None) or {}).get("demo_accounts") or [] if isinstance(a, dict)}; checked = {x.get("email"): x.get("status") for x in ((report.credentials.get("checked") if report else []) or [])}
        accounts = [{"email": e, "password": p, "role": roles.get(e, ""), "status": checked.get(e)} for e, p in self.demo_credentials()]
        if accounts: self._fire("on_creds", accounts, "plan" if roles else "project", report.credentials.get("ok") if report else None)
        return accounts

    # Verifies credentials and return clear evidence to the next pipeline step.
    def verify_credentials(self, report):
        """Verify credentials and return clear evidence to the next pipeline step."""
        if any(f.code == "ROUTE_ERROR" for f in report.findings): report.credentials = {"checked": [], "ok": None, "reason": "pages are failing"}; return
        creds, endpoint = self.demo_credentials() or self._credentials_from_seed(), self.find_login_endpoint()
        if not creds or not endpoint: report.credentials = {"checked": [], "ok": None, "reason": "no demo accounts" if not creds else "no login endpoint"}; return
        plan = getattr(self.arch, "plan", None) or {}; expected = {str(a.get("email") or "").lower(): str(a.get("role") or "") for a in plan.get("demo_accounts") or [] if isinstance(a, dict)}
        # From: agents/analysis/checks/scan_state.py
        better, checked, failed = "betterAuth(" in self.code_files().get("lib/auth.js", ""), [], []
        for email, password in creds:
            # From: agents/analysis/analysis_shared.py
            jar = http.cookiejar.CookieJar(); opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)); req = urllib.request.Request(self.base_url + endpoint, data=json.dumps({"email": email, "password": password}).encode(), method="POST", headers={"Content-Type": "application/json"})
            try:
                with opener.open(req, timeout=15) as response: status = response.status
            except urllib.error.HTTPError as exc: status = exc.code
            except Exception: report.credentials = {"checked": checked, "ok": None, "reason": "endpoint unreachable"}; return
            role, actual = "", ""
            if status < 400 and better:
                try:
                    # From: agents/analysis/analysis_shared.py
                    # From: agents/data/database_helpers.py
                    with opener.open(self.base_url + "/api/auth/get-session", timeout=10) as response: user = (json.loads(response.read(4000).decode() or "{}") or {}).get("user") or {}
                    role, actual = str(user.get("role") or ""), str(user.get("email") or "").lower()
                except Exception: pass
            # From: agents/analysis/checks/auth_checks.py
            good = status < 400 and (not better or actual == email.lower() and (not expected.get(email.lower()) or self._role_key(role) == self._role_key(expected[email.lower()])))
            checked.append({"email": email, "status": status, "expected_role": expected.get(email.lower(), ""), "session_email": actual, "session_role": role}); self._fire("on_test", "pass" if good else "fail", f"Login {email}", f"HTTP {status}" + (f", role {role or 'missing'}" if better else ""))
            if not good:
                # From: agents/analysis/analysis_shared.py
                failed.append(email); code = "BAD_CREDENTIALS" if status in (401, 403) else "ROLE_IDENTITY_MISMATCH"; report.findings.append(Finding("blocker", code, f"planned demo identity {email} was not restored exactly (HTTP {status}, role {role or 'missing'})", "lib/seed.js", "create it through Better Auth and preserve its exact role", ["lib/auth.js"]))
        report.credentials = {"endpoint": endpoint, "checked": checked, "ok": not failed}

    # Runs the runtime step and returns the result.
    def run_runtime(self, mongo=None, node_bin="node", use_model=True, dev_log=None, probe_apis=False, skip_root=False):
        """Run the runtime step and return its observable result."""
        # From: agents/analysis/checks/scan_state.py
        self._fire("on_phase", {"phase": -5, "title": "Verifying app", "status": "active"}); report = self.scan(); self.probe_pages(report, skip_root=skip_root)
        if probe_apis: self.probe_api_routes(report)
        self.probe_linked_dynamic_routes(report); self.verify_credentials(report); self._announce_credentials(report)
        bad = [f for f in report.findings if f.code in {"BAD_CREDENTIALS", "ROLE_IDENTITY_MISMATCH"}]
        if bad and use_model:
            # From: agents/analysis/analysis_shared.py
            # From: agents/analysis/repair/repair_runner.py
            report.written += self.repair(AnalyzerReport(findings=bad), server_log=dev_log() if dev_log else "")
            if report.written and self.allow_reseed and mongo is not None:
                # From: agents/data/database_records.py
                reset = mongo.reset_project_db(self.project_dir, node_bin=node_bin)
                # From: agents/analysis/checks/scan_state.py
                if reset.get("ok"): self._get_status(self.base_url + "/"); again = self.scan(); self.verify_credentials(again); again.written = report.written; report = again
        self._fire("on_phase", {"phase": -5, "title": "Verifying app", "status": "done"}); return report
