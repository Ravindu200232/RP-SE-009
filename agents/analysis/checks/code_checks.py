"""Code Checks.

Every method here owns one closely related analyzer responsibility.
"""
from __future__ import annotations

# Source: analysis_shared.py — shared finding types, constants and helper imports.
# Source: react_dom_props.py — React DOM property validation used by the Analyzer.
from agents.core.syntax.react_dom_props import find_invalid_react_dom_props

from agents.analysis.analysis_shared import (
    FRAMEWORK_EXPORTS,
    Finding,
    Path,
    PurePosixPath,
    _strip_noncode,
    check_default_imports,
    check_named_imports,
    check_syntax,
    field,
    json,
    parse_imports,
    re,
    resolve_local,
)

class CodeChecksMixin:
    """Keep code checks behavior together."""

    # Inspect the generated source for cross file problems and return evidence only when a real issue is found.
    def _cross_file_invariants(self):
        """Prepare the cross file invariants value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        files, out = self.code_files(), []
        written, read = set(), {}
        for rel, body in files.items():
            # From: agents/analysis/analysis_shared.py
            constants = dict(re.findall(r"\bconst\s+([A-Z_][A-Z0-9_]*)\s*=\s*['\"]([^'\"]+)['\"]", body))
            # From: agents/analysis/analysis_shared.py
            for literal, name in re.findall(r"\.set\(\s*(?:['\"]([^'\"]+)['\"]|([A-Z_][A-Z0-9_]*))", body):
                if literal or constants.get(name): written.add(literal or constants[name])
            # From: agents/analysis/analysis_shared.py
            for literal, name in re.findall(r"\.(?:get|delete)\(\s*(?:['\"]([^'\"]+)['\"]|([A-Z_][A-Z0-9_]*))", body):
                cookie = literal or constants.get(name)
                # From: agents/analysis/analysis_shared.py
                if cookie and re.search(r"session|token|auth|jwt|user", cookie, re.I): read.setdefault(cookie, []).append(rel)
            # From: agents/analysis/analysis_shared.py
            if "bcrypt" in body and re.search(r"Response\.json\(\s*\{\s*[^}]*\buser\s*(?:,|\})", body) and re.search(r"\buser\s*=\s*await\s+\w+\.findOne", body): out.append(Finding("major", "HASH_LEAK", "returns a whole credential user document to the browser", rel, "return only id, email, name, and role"))
        for cookie, paths in read.items():
            # From: agents/analysis/analysis_shared.py
            if cookie not in written: out.append(Finding("blocker", "SESSION_COOKIE_MISMATCH", f"reads session cookie '{cookie}', which no project source writes", paths[0], "export one cookie constant and use it in login, session, and logout", paths))
        # From: agents/analysis/analysis_shared.py
        # From: agents/analysis/checks/scan_state.py
        oid_fields = set(re.findall(r"(?mi)^\s*[-*]\s*`?([A-Za-z_][\w]*)`?\s*:\s*ObjectId\b", self.plan_text()))
        for rel, body in files.items():
            for field in oid_fields:
                # From: agents/analysis/analysis_shared.py
                match = re.search(rf"\b(?:find|findOne|updateOne|deleteOne|findOneAndUpdate)\s*\(\s*\{{[^}}]{{0,500}}?\b{re.escape(field)}\s*:\s*([^,}}\n]+)", body, re.S)
                if not match: continue
                value = match.group(1).strip()
                # From: agents/analysis/analysis_shared.py
                if not re.search(r"\b(?:new\s+)?ObjectId\s*\(", value) and (value in {"id", "roomId", "userId", "ownerId"} or re.fullmatch(r"(?:user|session(?:\?\.user)?|session\.user)\??\.id", value)):
                    # From: agents/analysis/analysis_shared.py
                    out.append(Finding("blocker", "MONGO_ID_TYPE", f"queries ObjectId field '{field}' with string expression {value}", rel, "validate and convert at the Mongo boundary; serialize outward IDs as strings", [rel])); break
        return out

    # Inspect the generated source for contract problems and return evidence only when a real issue is found.
    def contract_findings(self, routes=None):
        """Prepare the contract findings value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        plan, files, out = getattr(self.arch, "plan", None) or {}, self.code_files(), []
        # From: agents/analysis/checks/route_checks.py
        routes = routes or self.enumerate_routes()
        # From: agents/analysis/checks/route_checks.py
        shell = self._mentions("app/layout.jsx") | self._mentions("app/layout.js")
        for contract in plan.get("contracts") or []:
            if not isinstance(contract, dict): continue
            src, target = str(contract.get("from") or "").lstrip("./").replace("\\", "/"), str(contract.get("target") or "")
            if src not in files or not target.startswith("/"): continue
            # From: agents/analysis/checks/route_checks.py
            matched = self._route_for(target, routes); method = str(contract.get("method") or "").upper()
            # From: agents/analysis/analysis_shared.py
            if contract.get("kind") == "api" and (not matched or method and method not in matched.get("methods", [])): out.append(Finding("blocker", "BROKEN_CONTRACT", f"contract {contract.get('name') or target} requires {method or 'a handler'} {target}, but no matching method is served", src, "implement both ends of the API contract", [src] + ([matched["file"]] if matched else [])))
            # From: agents/analysis/analysis_shared.py
            # From: agents/analysis/checks/route_checks.py
            if "[" not in target and target.rstrip("/") not in (self._mentions(src) | shell): out.append(Finding("major", "BROKEN_CONTRACT", f"contract says {src} must reach {target}, but its import closure never names it", src, f"wire the action to literal target {target}", [src]))
        return out[:12]

    # Inspect the generated source for capability shape problems and return evidence only when a real issue is found.
    def capability_shape_findings(self):
        """Prepare the capability shape findings value or state used by this focused pipeline step."""
        plan, out = getattr(self.arch, "plan", None) or {}, []
        planned = {x.get("path") for p in plan.get("phases") or [] for x in p.get("files") or [] if isinstance(x, dict)}
        covered = {str(cid).upper() for flow in plan.get("workflows") or [] if isinstance(flow, dict) for cid in flow.get("covers") or []}
        for cap in plan.get("capabilities") or []:
            if not isinstance(cap, dict): continue
            cid, paths = str(cap.get("id") or "CAP"), [str(x) for x in cap.get("files") or []]; gap = [x for x in paths if x not in planned]
            # From: agents/analysis/analysis_shared.py
            if not paths or gap: out.append(Finding("blocker", "CAPABILITY_UNMAPPED", f"{cid} has no complete planned file map" + (f": {', '.join(gap)}" if gap else ""), paths[0] if paths else "", "map the complete implementation chain", paths))
            # From: agents/analysis/analysis_shared.py
            if cap.get("e2e", True) and cid.upper() not in covered: out.append(Finding("major", "CAPABILITY_UNWALKED", f"{cid} is user-visible but no accepted E2E workflow covers it", paths[0] if paths else "", "cover it with a journey performing and asserting the outcome", paths))
        return out[:12]

    # Returns imported packages that are still missing from package.json or node_modules.
    def unresolved_packages(self):
        """Return imported packages that are still missing from package.json or node_modules."""
        try:
            # From: agents/analysis/analysis_shared.py
            package = json.loads((self.project_dir / "package.json").read_text("utf-8")); declared = set(package.get("dependencies", {})) | set(package.get("devDependencies", {}))
        except Exception: declared = set()
        out, node_modules = [], self.project_dir / "node_modules"
        # From: agents/analysis/checks/scan_state.py
        for body in self.code_files().values():
            for name in self.arch.imported_packages(body):
                if (name not in declared or not (node_modules / name / "package.json").exists()) and name not in out: out.append(name)
        return out

    # Inspect the generated source for e2e syntax problems and return evidence only when a real issue is found.
    def e2e_syntax_findings(self, paths=None):
        """Prepare the e2e syntax findings value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        tests = {p: b for p, b in self.source_files(refresh=True).items() if p.startswith("tests/e2e/") and p.endswith((".js", ".jsx")) and (not paths or p in paths)}
        # From: agents/analysis/analysis_shared.py
        problems, reason = check_syntax(self.project_dir, tests, node_cmd=self.cb.get("node_bin"))
        if reason: self._log("WARN", f"   ⚠ E2E syntax preflight unavailable: {reason}"); return []
        # From: agents/analysis/analysis_shared.py
        return [Finding("blocker", "E2E_SYNTAX", f"generated browser spec is invalid JavaScript at line {p.get('line') or 0}: {p.get('message')}", p["path"], "repair scenario syntax before launching Playwright", [p["path"]]) for p in problems]

    # Inspect the generated source for code problems and return evidence only when a real issue is found.
    def _code_invariants(self):
        """Prepare the code invariants value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        files, out, suffixes = self.code_files(), [], (".jsx", ".js", ".tsx", ".ts", ".mjs", ".cjs")
        for rel, body in sorted(files.items()):
            # From: agents/analysis/analysis_shared.py
            clean = _strip_noncode(body)
            # From: agents/core/syntax/react_dom_props.py
            for bad, good in find_invalid_react_dom_props(body):
                out.append(Finding("major", "INVALID_REACT_DOM_PROP", f"uses JSX DOM property {bad}=, which React expects as {good}=", rel, f"rename {bad} to {good}"))
            for match in self._UNAWAITED_RE.finditer(clean):
                # From: agents/analysis/analysis_shared.py
                # From: agents/data/database_server.py
                fn, method = match.groups(); out.append(Finding("blocker", "UNAWAITED_COLLECTION", f"line {clean[:match.start()].count(chr(10))+1} calls .{method}() on async {fn}() without await", rel, f"await {fn}(…) before calling .{method}()", [rel]))
            for match in self._OID_RE.finditer(clean):
                arg = match.group(1).strip()
                # From: agents/analysis/analysis_shared.py
                if (arg[:1] in "'\"" and not re.fullmatch(r"['\"][0-9a-f]{24}['\"]", arg, re.I)) or re.search(r"\.(?:email|name|username|title|slug|password)\b", arg, re.I): out.append(Finding("blocker", "BAD_OBJECTID", f"new ObjectId({arg[:50]}) receives a value that cannot be an ObjectId", rel, "use a validated id or inserted document _id"))
            # From: agents/analysis/analysis_shared.py
            for match in self._SELF_PARAMS_RE.finditer(clean): out.append(Finding("blocker", "ASYNC_PARAM_CONFUSION", f"destructures {match.group(1)} from the object produced by awaiting itself", rel, f"destructure actual keys directly from await {match.group(1)}"))
            # From: agents/analysis/analysis_shared.py
            if self._DIRECT_PARAMS_RE.search(clean) and not re.search(r"await\s+params\b", clean): out.append(Finding("blocker", "UNAWAITED_PARAMS", "reads Next.js dynamic params before awaiting them", rel, "await params before reading route keys"))
            # From: agents/analysis/analysis_shared.py
            stray = getattr(self.arch, "STRAY_DIRECTIVE_RE", re.compile(r"['\"]use client['\"]"))
            for match in stray.finditer(body):
                # From: agents/analysis/analysis_shared.py
                # From: agents/data/database_server.py
                if re.sub(r"//[^\n]*|/\*.*?\*/", "", body[:match.start()], flags=re.S).strip(): out.append(Finding("blocker", "STRAY_DIRECTIVE", "'use client' appears after executable code", rel, "move it to line 1 or split the component")); break
            # From: agents/analysis/analysis_shared.py
            for stmt in parse_imports(body):
                spec = stmt.spec or ""
                if not spec.startswith(("./", "../", "@/")) or spec.endswith((".css", ".json", ".svg", ".png", ".jpg", ".webp")): continue
                # From: agents/analysis/analysis_shared.py
                if resolve_local(rel, spec, files) is not None: continue
                # From: agents/analysis/analysis_shared.py
                raw = spec[2:] if spec.startswith("@/") else (PurePosixPath(rel).parent / spec).as_posix()
                target = raw if raw.endswith(suffixes) else raw + ".jsx"
                # From: agents/analysis/analysis_shared.py
                out.append(Finding("blocker", "MISSING_LOCAL_IMPORT", f"imports '{spec}' but no local module exists", rel, f"write {target} or use an existing module", [target]))
        # From: agents/analysis/analysis_shared.py
        for bad in check_default_imports(files): out.append(Finding("blocker", "BROKEN_IMPORT", f"imports {bad.name} as default from '{bad.spec}', which has no default export", bad.importer, f"use an existing export or add the intended default to {bad.module}", [bad.module]))
        groups = {}
        # From: agents/analysis/analysis_shared.py
        for bad in check_named_imports(files): groups.setdefault((bad.importer, bad.module, bad.spec), []).append(bad)
        for (src, module, spec), rows in groups.items():
            names = ", ".join(sorted({x.name for x in rows})); fix = "use the framework's real export" if module in FRAMEWORK_EXPORTS else f"preserve exports and add/fix the contract in {module}"
            # From: agents/analysis/analysis_shared.py
            out.append(Finding("blocker", "BROKEN_IMPORT", f"imports {{ {names} }} from '{spec}', which does not export those names", src, fix, [] if module in FRAMEWORK_EXPORTS else [module]))
        return out

    # Inspect the generated source for unawaited collection problems and return evidence only when a real issue is
    # found.
    def unawaited_collection(self):
        """Prepare the unawaited collection value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._code_invariants(), "UNAWAITED_COLLECTION")

    # Inspect the generated source for bad objectid problems and return evidence only when a real issue is found.
    def bad_objectid(self):
        """Prepare the bad objectid value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._code_invariants(), "BAD_OBJECTID")

    # Inspect the generated source for async param confusion problems and return evidence only when a real issue is
    # found.
    def async_param_confusion(self):
        """Prepare the async param confusion value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._code_invariants(), "ASYNC_PARAM_CONFUSION", "UNAWAITED_PARAMS")

    # Inspect the generated source for stray directives problems and return evidence only when a real issue is found.
    def stray_directives(self):
        """Prepare the stray directives value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return [f"{f.path}:1" for f in self._only(self._code_invariants(), "STRAY_DIRECTIVE")]

    # Inspect the generated source for missing local imports problems and return evidence only when a real issue is
    # found.
    def missing_local_imports(self):
        """Prepare the missing local imports value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._code_invariants(), "MISSING_LOCAL_IMPORT")

    # Inspect the generated source for broken imports problems and return evidence only when a real issue is found.
    def broken_imports(self):
        """Prepare the broken imports value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._code_invariants(), "BROKEN_IMPORT")

    # Inspect the generated source for inert control problems and return evidence only when a real issue is found.
    def inert_control_findings(self):
        """Prepare the inert control findings value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/data_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._data_ui_invariants(), "INERT_CONTROL")

    # Inspect the generated source for server client boundary problems and return evidence only when a real issue is
    # found.
    def server_client_boundary_findings(self):
        """Prepare the server client boundary findings value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/data_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._data_ui_invariants(), "SERVER_CLIENT_EVENT_HANDLER")

    # Inspect the generated source for unsupported form method problems and return evidence only when a real issue is
    # found.
    def unsupported_form_method_findings(self):
        """Prepare the unsupported form method findings value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/data_checks.py
        # From: agents/analysis/checks/scan_state.py
        return self._only(self._data_ui_invariants(), "UNSUPPORTED_FORM_METHOD")

    # Returns one cached semantic check for older callers.
    def _semantic_requirement(self, lens, code):
        """Return one cached semantic check for older callers."""
        key = (getattr(self.arch, "write_seq", 0), lens)
        if key not in self._semantic_cache:
            # From: agents/analysis/checks/scan_state.py
            # From: agents/analysis/repair/semantic_audit.py
            self._semantic_cache[key] = self._semantic_lens(
                lens, self.scan(), max_turns=4, max_tools=8)
        # From: agents/analysis/analysis_shared.py
        return [Finding(f.severity, code, f.message, f.path, f.fix,
                        list(f.extra)) for f in self._semantic_cache[key]]

    # Inspect the generated source for workflow control problems and return evidence only when a real issue is found.
    def workflow_control_findings(self):
        """Prepare the workflow control findings value or state used by this focused pipeline step."""
        return self._semantic_requirement(
            "accepted workflow controls, handlers, outcomes and E2E reachability",
            "MISSING_WORKFLOW_CONTROL")

    # Check the generated source for jsx attrs and return the small result used by the Analyzer.
    @staticmethod
    def _jsx_attrs(body, start):
        """Prepare the jsx attrs value or state used by this focused pipeline step."""
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

    # Check the generated source for prop contract breaks and return the small result used by the Analyzer.
    def prop_contract_breaks(self):
        """Prepare the prop contract breaks value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        files, contracts, out = self.code_files(), {}, []
        # From: agents/analysis/analysis_shared.py
        signature = re.compile(r"export\s+default\s+(?:async\s+)?function(?:\s+\w+)?\s*\(\s*\{([^}]*)\}")
        for path, body in files.items():
            if not path.startswith("components/") or not (match := signature.search(body)): continue
            required = []
            for raw in match.group(1).split(","):
                name = raw.strip()
                # From: agents/analysis/analysis_shared.py
                if not re.fullmatch(r"\w+", name) or name == "children": continue
                # From: agents/analysis/analysis_shared.py
                guarded = re.search(rf"\b{re.escape(name)}\s*(?:&&|\?\.|\|\||\?\?)", body)
                # From: agents/analysis/analysis_shared.py
                if not guarded and re.search(rf"\b{re.escape(name)}\s*(?:\.|\(|\[)", body): required.append(name)
            if required: contracts[path] = set(required)
        for path, body in files.items():
            # From: agents/analysis/analysis_shared.py
            imports = {stmt.default: resolve_local(path, stmt.spec, files)
                       for stmt in parse_imports(body) if stmt.default}
            # From: agents/analysis/analysis_shared.py
            for match in re.finditer(r"<([A-Z]\w*)\b", body):
                target, attrs = imports.get(match.group(1)), self._jsx_attrs(body, match.end())
                # From: agents/analysis/analysis_shared.py
                if target not in contracts or attrs is None or re.search(r"\{\s*\.\.\.", attrs): continue
                # From: agents/analysis/analysis_shared.py
                given = set(re.findall(r"(\w+)\s*=", attrs)); missing = contracts[target] - given
                # From: agents/analysis/analysis_shared.py
                if missing: out.append(Finding(
                    "blocker", "PROP_CONTRACT",
                    f"<{match.group(1)}> omits required prop(s): {', '.join(sorted(missing))}",
                    path, f"pass the required prop(s) or make {target} safely optional",
                    [target]))
        return out[:12]

    # Check the generated source for layout chrome and return the small result used by the Analyzer.
    def layout_chrome(self):
        """Prepare the layout chrome value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        files, out = self.code_files(), []
        layout = next((p for p in ("app/layout.js", "app/layout.jsx") if p in files), "")
        if not layout: return out
        body = files[layout]
        # From: agents/analysis/analysis_shared.py
        if "ensureSeeded" in body: out.append(Finding(
            "major", "SEED_IN_LAYOUT", "root layout seeds on every page and API request",
            layout, "seed from the data/auth entry points that need it"))
        return out

    # Inspect the generated source for orphan components problems and return evidence only when a real issue is found.
    def orphan_components(self):
        """Prepare the orphan components value or state used by this focused pipeline step."""
        # From: agents/analysis/checks/scan_state.py
        files = self.code_files(); blob = "\n".join(files.values())
        # From: agents/analysis/analysis_shared.py
        return sorted(Path(p).stem for p in files if p.startswith("components/") and not re.search(r"from\s+['\"][^'\"]*/" + re.escape(Path(p).stem) + r"['\"]", blob))
