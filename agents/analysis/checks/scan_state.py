"""Scan State.

Every method here owns one closely related analyzer responsibility.
"""
from __future__ import annotations

# Source: analysis_shared.py — shared finding types, constants and helper imports.
from agents.analysis.analysis_shared import (
    AnalyzerReport,
    CODE_EXT,
    CommandRunner,
    Finding,
    MAX_FILE_BYTES,
    NEXT_ROOTS,
    PLACEHOLDER_RE,
    PROSE_PATH_RE,
    Path,
    ROOT_SOURCE,
    SKIP_DIRS,
    SOURCE_EXT,
    log,
    re,
)

class ScanStateMixin:
    """Keep scan state behavior together."""

    # Prepares ScanStateMixin with the services and starting state it needs before it begins work.
    def __init__(self, arch, project_dir=None, *, base_url="http://localhost:5173", callbacks=None, allow_reseed=False):
        """Prepare this helper with the state it needs."""
        # From: agents/analysis/analysis_shared.py
        self.arch, self.project_dir = arch, Path(project_dir or arch.project_dir)
        self.base_url, self.cb, self.allow_reseed = base_url.rstrip("/"), callbacks or {}, allow_reseed
        # From: agents/analysis/analysis_shared.py
        self.cmd = CommandRunner(self.project_dir, npm_bin=self.cb.get("npm_bin", "npm"), node_bin=self.cb.get("node_bin", "node"), on_log=lambda a, b: self._fire("on_log", a, b), on_event=lambda e: self._fire("on_command", e))
        self._files_cache, self._cache_seq, self._rewritten_this_stage = None, -1, set()
        self._semantic_cache = {}

    # Sends one progress event to the UI callback when a callback exists.
    def _fire(self, name, *args):
        """Send one progress event to the UI callback when a callback exists."""
        fn = self.cb.get(name)
        if callable(fn):
            try: fn(*args)
            # From: agents/analysis/analysis_shared.py
            except Exception as exc: log.warning("callback %s failed: %s", name, exc)

    # Writes one readable status message through the configured logger.
    def _log(self, level, text):
        """Write one readable status message through the configured logger."""
        # From: agents/analysis/analysis_shared.py
        self._fire("on_log", level, text) if callable(self.cb.get("on_log")) else log.info(text)

    # Returns the current project source files that the analyzer is allowed to inspect.
    def source_files(self, refresh=False):
        """Return the current project source files that the analyzer is allowed to inspect."""
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

    # Read the generated project once and cache the source facts reused by many analyzer checks.
    def scan(self):
        """Scan current step and return clear evidence to the next pipeline step."""
        # From: agents/analysis/analysis_shared.py
        # From: agents/analysis/checks/route_checks.py
        report = AnalyzerReport(planned=self.planned_paths(), routes=self.enumerate_routes()); report.missing = self.missing_files(); report.dead_links = self.dead_links(report.routes); report.unresolved = self.unresolved_packages()
        # From: agents/analysis/analysis_shared.py
        for path in report.missing: report.findings.append(Finding("blocker", "MISSING_FILE", "this is still a scaffold placeholder" if self._is_placeholder(path) else "the accepted plan promises this file but it was never written", path, "write the complete planned file"))
        # From: agents/analysis/checks/auth_checks.py
        # From: agents/analysis/checks/code_checks.py
        # From: agents/analysis/checks/data_checks.py
        # From: agents/analysis/checks/route_checks.py
        report.findings += self._code_invariants() + self._auth_invariants() + self._data_ui_invariants() + self._data_contract_findings() + self._cross_file_invariants() + self.fetch_contract_findings(report.routes) + self.contract_findings(report.routes) + self.capability_shape_findings()
        # From: agents/analysis/checks/auth_checks.py
        # From: agents/analysis/checks/code_checks.py
        # From: agents/analysis/checks/data_checks.py
        report.findings += self.prop_contract_breaks() + self.credentials_exposed() + self.seed_volume() + self.layout_chrome()
        # From: agents/analysis/analysis_shared.py
        # From: agents/analysis/checks/route_checks.py
        for url in self.dead_endpoints(report.routes): report.findings.append(Finding("blocker", "DEAD_ENDPOINT", f"source fetches {url}, but no API handler serves it", fix=f"implement app{url}/route.js", extra=[f"app{url}/route.js"]))
        for url in report.dead_links:
            # From: agents/analysis/analysis_shared.py
            if url not in {"/sign-in", "/signin", "/login"}: report.findings.append(Finding("blocker", "DEAD_LINK", f"something links to {url}, but no page serves it", fix="create the planned page or remove the link"))
        # From: agents/analysis/checks/route_checks.py
        orphans = self.unreachable_pages(report.routes)
        if orphans:
            # From: agents/analysis/analysis_shared.py
            owners = [report.routes[u]["file"] for u in orphans[:10] if u in report.routes]; report.findings.append(Finding("blocker", "NO_WAY_THERE", f"{len(orphans)} page(s) are unreachable from /: {', '.join(orphans[:8])}", owners[0] if owners else "", "wire accepted navigation through the page shell or parent list", owners[1:]))
        # From: agents/analysis/analysis_shared.py
        for name in report.unresolved: report.findings.append(Finding("blocker", "MISSING_PACKAGE", f"'{name}' is imported but not installed", fix=f"npm install {name}"))
        try:
            for problem in self.arch.lint_generated():
                path = problem.split(":", 1)[0]
                # From: agents/analysis/analysis_shared.py
                if "imported but not installed" not in problem: report.findings.append(Finding("major", "LINT", problem, path, "repair the deterministic lint violation without changing behavior"))
        # From: agents/analysis/analysis_shared.py
        except Exception as exc: log.warning("lint_generated failed: %s", exc)
        unique, seen = [], set()
        for finding in report.findings:
            key = (finding.code, finding.path, finding.message)
            if key not in seen: seen.add(key); unique.append(finding)
        report.findings = unique
        return report

    # Returns the generated source files that should be treated as executable application code.
    def code_files(self):
        """Prepare the code files value or state used by this focused pipeline step."""
        # From: agents/analysis/analysis_shared.py
        return {p: b for p, b in self.source_files().items() if Path(p).suffix in CODE_EXT and (p.startswith(NEXT_ROOTS) or p in ROOT_SOURCE)}

    # Plan text in the format expected by the next pipeline steps.
    def plan_text(self):
        """Plan text in the standard shape used by the rest of the pipeline."""
        return str(getattr(self.arch, "plan_md", "") or self.source_files().get("plan.md", ""))

    # Returns the file paths promised by the plan so the analyzer can compare plan versus source.
    def planned_paths(self):
        """Prepare the planned paths value or state used by this focused pipeline step."""
        # From: agents/analysis/analysis_shared.py
        found = {p for p in PROSE_PATH_RE.findall(self.plan_text()) if not PLACEHOLDER_RE.search(p)}
        plan = getattr(self.arch, "plan", None) or {}
        groups = [plan.get("files"), plan.get("file_plan"), (plan.get("implementation") or {}).get("files")]
        groups += [p.get("files") for p in plan.get("phases") or [] if isinstance(p, dict)]
        for group in groups:
            for item in group or []:
                path = item.get("path") if isinstance(item, dict) else item
                # From: agents/analysis/analysis_shared.py
                if path and not PLACEHOLDER_RE.search(str(path)): found.add(str(path).replace("\\", "/"))
        return sorted(found)

    # Check whether a planned project path currently exists in the generated workspace.
    def _exists(self, rel):
        """Prepare the exists value or state used by this focused pipeline step."""
        stem = rel[:-4] if rel.endswith(".jsx") else rel[:-3] if rel.endswith(".js") else rel
        return any((self.project_dir / p).exists() for p in (rel, stem + ".js", stem + ".jsx"))

    # Checks whether placeholder is true for the current pipeline state.
    def _is_placeholder(self, rel):
        """Return whether placeholder is true for the current pipeline state."""
        body = self.source_files().get(rel, "")
        return bool(body) and len(body) < 400 and any(x in body for x in self.PLACEHOLDER_MARKERS)

    # Returns planned files that are still missing from the generated project.
    def missing_files(self):
        """Prepare the missing files value or state used by this focused pipeline step."""
        out = [p for p in self.planned_paths() if not self._exists(p) or self._is_placeholder(p)]
        return out + [p for p in self.ALWAYS_CHECKED if p not in out and self._is_placeholder(p)]

    # Filter a collection so this check works only with the requested file types or paths.
    @staticmethod
    def _only(findings, *codes):
        """Prepare the only value or state used by this focused pipeline step."""
        return [f for f in findings if f.code in codes]

    # Check the generated source for inventory and return the small result used by the Analyzer.
    def inventory(self):
        """Prepare the inventory value or state used by this focused pipeline step."""
        rows = []
        for path, body in sorted(self.code_files().items()):
            # From: agents/analysis/analysis_shared.py
            exports = re.findall(r"export\s+(?:default\s+)?(?:async\s+)?(?:function|const)\s+(\w+)", body)
            rows.append(f"{path} · {len(body.splitlines())} lines · {'client' if self._CLIENT_RE.search(body) else 'server'}" + (f" · exports {', '.join(exports[:5])}" if exports else ""))
        return "\n".join(rows)

    # Builds the route lookup table used by link, page, and API consistency checks.
    @staticmethod
    def route_table(routes):
        """Prepare the route table value or state used by this focused pipeline step."""
        return "\n".join(f"{u} → {m['file']} [{'/'.join(m['methods']) or '-'}]" for u, m in sorted(routes.items()))
