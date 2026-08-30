"""Repair Runner.

Every method here owns one closely related analyzer responsibility.
"""
from __future__ import annotations

# Source: analysis_shared.py — shared finding types, constants and helper imports.
from agents.analysis.analysis_shared import (
    AnalyzerReport,
    FileStreamParser,
    REPAIRABLE_MAJOR,
    TOOL_HELP,
    WorkspaceTools,
    log,
    nextdocs,
    re,
)

class RepairRunnerMixin:
    """Keep repair runner behavior together."""

    # From: agents/analysis/analysis_shared.py
    _IMPORT_RE = re.compile(r"""from\s+['"]@/(components/[\w./-]+)['"]""")
    # From: agents/analysis/analysis_shared.py
    _FETCH_RE = re.compile(r"""fetch\(\s*[`'"](/api/[\w./\[\]-]+)""")

    # Repairs paths.
    def _repair_paths(self, report):
        """Repair paths safely without changing unrelated project behavior."""
        # From: agents/analysis/checks/route_checks.py
        # From: agents/analysis/checks/scan_state.py
        files, routes, direct = self.source_files(), self.enumerate_routes(), set(report.missing or [])
        for finding in report.findings:
            # From: agents/planner/builder/project_memory.py
            if finding.severity == "blocker" or finding.code in REPAIRABLE_MAJOR: direct.add(finding.path); direct.update(finding.extra or [])
        normalized = set()
        for raw in direct:
            path = str(raw or "").strip().replace("\\", "/").lstrip("./")
            if path.startswith("/"): path = str((routes.get(path) or {}).get("file") or "")
            if path: normalized.add(path)
        # From: agents/analysis/analysis_shared.py
        return normalized | set(WorkspaceTools(self.arch).dependency_paths([p for p in normalized if p in files], max_depth=2, cap=24))

    # New files a page being repaired now reaches for. The one correct fix for a guarded page written as a Client
    # Component is to split it: the page becomes the server file that reads the session, and the interactive half
    # moves to a new client component beside it. The repair kept writing exactly that and the write kept being refused
    # as "unrelated", because a file that does not exist yet cannot be among the paths a finding named — so the only
    # correct repair was the one repair that could never land, and the same six pages stayed open round after round. A
    # new component is related when a file that IS in scope imports it in the very same reply.
    @staticmethod
    def _new_children_of(proposed: dict, safe: set, files: dict) -> set:
        """New files a page being repaired now reaches for.

        The one correct fix for a guarded page written as a Client Component is
        to split it: the page becomes the server file that reads the session,
        and the interactive half moves to a new client component beside it. The
        repair kept writing exactly that and the write kept being refused as
        "unrelated", because a file that does not exist yet cannot be among the
        paths a finding named — so the only correct repair was the one repair
        that could never land, and the same six pages stayed open round after
        round. A new component is related when a file that IS in scope imports
        it in the very same reply.
        """
        wanted, reach = set(), set(safe)
        # The chain is page -> new client component -> new handler, and each
        # link is only visible once the one before it is in scope, so widen
        # until nothing new appears rather than one step and stop.
        while True:
            found = RepairRunnerMixin._referenced_new(proposed, reach, files)
            if found <= wanted:
                return wanted
            wanted |= found
            reach |= found

    # New files that files already in scope name, one step out.
    @staticmethod
    def _referenced_new(proposed: dict, safe: set, files: dict) -> set:
        """New files that files already in scope name, one step out."""
        wanted = set()
        for path, content in proposed.items():
            if path not in safe:
                continue
            body = content or ""
            for rel in RepairRunnerMixin._IMPORT_RE.findall(body):
                for candidate in (rel, rel + ".jsx", rel + ".js"):
                    if candidate in proposed and candidate not in files:
                        wanted.add(candidate)
            # A handler the repaired page now calls. "This collection is never
            # used" can only be closed by writing the route that uses it, and a
            # route that does not exist yet can never be named by the finding,
            # so refusing every new file made that finding unclosable forever.
            for url in RepairRunnerMixin._FETCH_RE.findall(body):
                stem = "app" + url.rstrip("/") + "/route"
                for candidate in (stem + ".js", stem + ".jsx"):
                    if candidate in proposed and candidate not in files:
                        wanted.add(candidate)
        return wanted

    # Runs one repair attempt against the selected targets, then verify whether the change actually improves the
    # observed failure.
    def repair(self, report, server_log=""):
        """Repair current step safely without changing unrelated project behavior."""
        candidates = self._repair_paths(report)
        safe = {p for p in candidates if p.startswith(("app/", "components/", "lib/", "styles/")) or p in {"middleware.js", "middleware.jsx"}}
        if not safe: return 0
        # From: agents/analysis/analysis_shared.py
        guidance = nextdocs.guidance_for(server_log + "\n" + "\n".join(f.message for f in report.findings))
        # From: agents/analysis/checks/scan_state.py
        current = self.source_files(); listing = "\n".join(f"- {p} ({'exists' if p in current else 'new'})" for p in sorted(safe))
        bundle = "\n\n".join(f"### {p} — COMPLETE CURRENT FILE\n```js\n{current[p]}\n```" for p in sorted(safe) if p in current)
        # From: agents/analysis/repair/semantic_audit.py
        messages = [{"role": "system", "content": self._analysis_contract() + "\n\n" + self.arch._builder_sys() + "\n\n" + TOOL_HELP}, {"role": "user", "content": "MODE: FINDING_REPAIR\n\n" + self._evidence_ledger(report) + "\n\n## Runtime evidence\n" + server_log[-5000:] + "\n\n" + guidance + "\n\n## Writable dependency neighborhood\n" + listing + "\n\n## Complete current files\n" + bundle + "\n\nUse these complete files as authoritative current state; inspect tools only for dependencies not attached, then emit complete write_file blocks only."}]
        # From: agents/analysis/analysis_shared.py
        self.arch._workspace_tool_cache = {}; proposed, tools = {}, WorkspaceTools(self.arch)
        # From: agents/analysis/analysis_shared.py
        parser = FileStreamParser(on_text=lambda _: None, on_file_start=lambda _: None, on_file_token=lambda _: None, on_file_end=lambda p, b: proposed.__setitem__(str(p or "").strip().replace("\\", "/").lstrip("./"), b))
        for _ in range(4):
            chunks = []
            try:
                # Accepts another streamed model chunk and emit any complete file blocks.
                def feed(token):
                    """Accept another streamed model chunk and emit any complete file blocks."""
                    # From: agents/planner/builder/write_stream.py
                    chunks.append(token); parser.feed(token)
                self.arch._stream(messages, feed, temperature=0.25)
            except Exception as exc: self._log("ERROR", f"   ❌ Analyzer repair failed: {exc}"); break
            # From: agents/core/workspace/source_workspace.py
            reply = "".join(chunks); messages.append({"role": "assistant", "content": reply}); observation, used = tools.serve(reply)
            if used and not proposed: messages.append({"role": "user", "content": "Tool observations:\n\n" + observation + "\n\nContinue the same repair from this evidence."}); continue
            break
        # From: agents/analysis/checks/scan_state.py
        # From: agents/planner/builder/write_stream.py
        parser.close(); files, written = self.source_files(), []
        direct = {f.path for f in report.findings}
        safe |= self._new_children_of(proposed, safe, files)
        for path, content in sorted(proposed.items()):
            if path not in safe or not content.strip(): self._log("WARN", f"   ⛔ ignored unrelated/unsafe repair write {path}"); continue
            if path in self._rewritten_this_stage and path not in direct: continue
            # From: agents/analysis/analysis_shared.py
            old_exports = set(re.findall(r"export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class)\s+(\w+)", files.get(path, ""))); new_exports = set(re.findall(r"export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class)\s+(\w+)", content))
            if old_exports - new_exports: self._log("WARN", f"   ⛔ {path} drops exports: {', '.join(sorted(old_exports-new_exports))}"); continue
            self._fire("on_file_start", path); self._fire("on_file_end", path, content)
            if self.arch.write_file(path, content): written.append(path)
        self._files_cache = None; self._rewritten_this_stage.update(written); report.written += len(written)
        return len(written)

    # Runs this pipeline step and returns the result.
    def run(self, *, use_model=True, max_rounds=2, semantic=True):
        """Run this pipeline step and return its result."""
        # From: agents/analysis/checks/scan_state.py
        self._fire("on_phase", {"phase": -5, "title": "Analyzing project", "status": "active"}); report, total = self.scan(), 0
        first = list(report.findings)
        # From: agents/analysis/checks/scan_state.py
        if use_model and report.unresolved: self.cmd.run("npm install " + " ".join(report.unresolved)); self._files_cache = None; report = self.scan()
        # Returns the small set of source files that the current repair is allowed to inspect or change.
        def targets(value):
            """Prepare the targets value or state used by this focused pipeline step."""
            return [f for f in value.findings if f.severity == "blocker" or f.code in REPAIRABLE_MAJOR]
        for _ in range(max_rounds if use_model else 0):
            before = targets(report)
            if not before: break
            # From: agents/analysis/analysis_shared.py
            count = self.repair(AnalyzerReport(findings=before, missing=list(report.missing)))
            if not count: break
            # From: agents/analysis/checks/scan_state.py
            total += count; self._files_cache = None; newer = self.scan()
            report = newer
            if len(targets(newer)) >= len(before): break
        # The model reads the app whether or not the fixed checks are happy. An
        # app with blockers left is the one whose remaining faults nothing in
        # the deterministic list knows how to name.
        if semantic and use_model:
            # From: agents/analysis/repair/semantic_audit.py
            findings = self.unbuilt_promises(); first.extend(findings)
            if findings:
                # From: agents/analysis/analysis_shared.py
                # From: agents/analysis/checks/scan_state.py
                total += self.repair(AnalyzerReport(findings=findings)); self._files_cache = None; report = self.scan()
                # From: agents/analysis/repair/semantic_audit.py
                report.findings += self.unbuilt_promises(max_reads=8)
        report.written = total; self._fire("on_phase", {"phase": -5, "title": "Analyzing project", "status": "done", "written": total})
        try:
            # Source: core.py — imported helper(s) come from this file.
            from agents.core.learning import build_lessons as lessons
            lessons.record(self.project_dir.name, lessons.from_findings(first))
        # From: agents/analysis/analysis_shared.py
        except Exception as exc: log.debug("lessons: %s", exc)
        return report
