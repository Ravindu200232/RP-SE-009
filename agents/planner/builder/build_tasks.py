"""Build Tasks for the application builder.

The methods in this file share one easy-to-find responsibility.
"""
from __future__ import annotations

# Source: sitemap_maker.py — imported helper(s) come from this file.
from agents.planner.planning.sitemap_maker import render_sitemap_xml

# Source: builder_shared.py — shared builder constants and helper imports.
from agents.planner.builder.builder_shared import (
    FileStreamParser,
    PlannerAgent,
    docsindex,
    json,
    log,
)

class BuildTasksMixin:
    """Keep build tasks behavior in one place."""

    # Builds plan in the format expected by the next pipeline steps.
    def make_plan(self, user_prompt: str, requirement_source: str = "") -> bool:
        """Build plan in the standard shape used by the rest of the pipeline."""
        self._log("INFO", "🧭 Planning — requirements, design, routes, architecture and E2E")
        self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "active"})
        # From: agents/planner/builder/builder_shared.py
        planner = PlannerAgent(self.client, self.model, stack=self.stack,
                               callbacks=self.cb, think=self.think, stream=self._stream)
        # From: agents/planner/planning/request_planner.py
        bundle = planner.create(user_prompt, requirement_source)
        if not bundle:
            self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "error"})
            return False
        self.plan, self.plan_md = bundle.data, bundle.markdown
        self.architecture_md, self.design_md = bundle.architecture_markdown, bundle.design_markdown
        for path, body in (("plan.md", self.plan_md), ("architecture.md", self.architecture_md),
                           ("design.md", self.design_md),
                           ("sitemap.xml", bundle.sitemap_xml)):
            # From: agents/planner/builder/file_writer.py
            self.write_file(path, body)
        # From: agents/planner/builder/project_memory.py
        self._save_plan_json()
        self.start_conversation(user_prompt)
        # From: agents/planner/builder/project_memory.py
        self.save_convo()
        self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "done", "plan": self.plan})
        self._log("INFO", f"   ✅ Plan ready — {len(self.plan.get('requirements') or [])} requirements, "
                            f"{len(self.plan.get('routes') or [])} routes, "
                            f"{len(self.plan.get('file_plan') or [])} implementation files")
        return True

    # Starts conversation.
    def start_conversation(self, user_prompt: str) -> None:
        """Start conversation safely without changing unrelated project behavior."""
        # From: agents/planner/builder/builder_shared.py
        plan_json = json.dumps(self.plan, ensure_ascii=False, indent=2)
        # From: agents/planner/builder/builder_setup.py
        self.convo = [
            {"role": "system", "content": self._builder_sys()},
            {"role": "user", "content": (
                "AUTHORITATIVE USER INPUT\n" + user_prompt +
                "\n\nAPPROVED PLAN JSON\n" + plan_json +
                "\n\nThe plan owns requirements, design, site map, routes, architecture, "
                "file contracts, and E2E proof. Do not alter it. Wait for the first build task.")},
            {"role": "assistant", "content": "Understood. I will implement the approved plan exactly, one complete file at a time."},
        ]

    # Builds the focused model prompt for one planned implementation task.
    def _task_prompt(self, task: dict, files: list[dict]) -> str:
        """Build the focused model prompt for one planned implementation task."""
        payload = dict(task)
        payload["files"] = files
        cap_ids = {rid for file in files for rid in file.get("requirements") or []}
        capabilities = [cap for cap in self.plan.get("capabilities") or []
                        if cap_ids & set(cap.get("requirement_ids") or []) or
                        set(cap.get("files") or []) & {file["path"] for file in files}]
        apis = [api for api in self.plan.get("api_contracts") or []
                if api.get("handler_file") in {file["path"] for file in files} or
                set(api.get("called_from") or []) & {file["path"] for file in files}]
        # From: agents/planner/builder/builder_shared.py
        return (
            "IMPLEMENT THIS APPROVED BUILD TASK. Write every listed file completely.\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + "\n\nCAPABILITIES TOUCHING THIS TASK\n"
            + json.dumps(capabilities, ensure_ascii=False, indent=2)
            + "\n\nAPI CONTRACTS TOUCHING THIS TASK\n"
            + json.dumps(apis, ensure_ascii=False, indent=2)
            + "\n\nUse exact planned names and paths. Output complete <write_file> blocks only."
        )

    # Provides the full site map again for every model build round.
    def _sitemap_block(self) -> str:
        """The whole site map, re-sent with every build round the model gets."""
        # From: agents/planner/planning/sitemap_maker.py
        xml = render_sitemap_xml(self.plan) if self.plan else ""
        if "<page" not in xml:
            return ""
        return ("\n\nAPPROVED SITE MAP — every route that exists, with its owner "
                "file, audience, composition and links. Link only to these paths.\n"
                + xml)

    # Runs the write loop step and returns the result.
    def _run_write_loop(self, user_content: str, _tool_depth: int = 0) -> int:
        """Run the write loop step and return its observable result."""
        self._workspace_tool_cache = {} if _tool_depth == 0 else self._workspace_tool_cache
        if _tool_depth == 0:
            user_content += self._sitemap_block()
        self.convo.append({"role": "user", "content": user_content})
        # From: agents/planner/builder/builder_setup.py
        self._trim_convo()
        raw, state = [], {"path": None, "count": 0}
        # From: agents/planner/builder/builder_shared.py
        # From: agents/planner/builder/file_writer.py
        # From: agents/planner/builder/project_memory.py
        parser = FileStreamParser(
            lambda text: self._fire("on_chat", text.strip()) if text.strip() and "BUILD COMPLETE" not in text.upper() else None,
            lambda path: (state.update(path=path), self._fire("on_file_start", path)),
            lambda token: self._fire("on_file_token", state["path"], token),
            lambda path, body: (self._fire("on_file_end", path, body),
                                state.update(count=state["count"] + (1 if self.write_file(path, body) else 0), path=None)),
        )
        try:
            # From: agents/planner/builder/builder_setup.py
            # From: agents/planner/builder/write_stream.py
            calls = self._stream(self.convo, lambda delta: (raw.append(delta), parser.feed(delta)), temperature=0.35)
        except Exception as exc:
            self._log("ERROR", f"   ❌ Generation failed: {exc}")
            calls = []
        # From: agents/planner/builder/write_stream.py
        parser.close()
        reply = "".join(raw)
        self.convo.append({"role": "assistant", "content": reply})
        # From: agents/planner/builder/build_validation.py
        self.run_requested_commands(reply)
        for call in calls:
            function = (call or {}).get("function") or {}
            if function.get("name") != "write_file":
                continue
            args = function.get("arguments") or {}
            if isinstance(args, str):
                try:
                    # From: agents/planner/builder/builder_shared.py
                    args = json.loads(args)
                except json.JSONDecodeError:
                    continue
            # From: agents/planner/builder/file_writer.py
            if args.get("path") and args.get("content") and self.write_file(args["path"], args["content"]):
                state["count"] += 1
        if state["count"] == 0 and _tool_depth < 2:
            try:
                # Source: source_workspace.py — imported helper(s) come from this file.
                from agents.core.workspace.source_workspace import WorkspaceTools
                # From: agents/core/workspace/source_workspace.py
                observations, used = WorkspaceTools(self).serve(reply)
            except Exception as exc:
                observations, used = "", 0
                # From: agents/planner/builder/builder_shared.py
                log.debug("workspace tool serving failed: %s", exc)
            # The builder prompt offers <read_docs topic="…"/> and promises the
            # page comes back next message, so the request has to be answered
            # here or the model waits for something that never arrives.
            try:
                # From: agents/core/workspace/source_workspace.py
                pages = docsindex.serve(self.project_dir, reply)
            except Exception as exc:
                pages = ""
                # From: agents/planner/builder/builder_shared.py
                log.debug("docs serving failed: %s", exc)
            if pages:
                observations = (observations + "\n\n" + pages).strip()
                used += 1
            if used:
                self.convo.append({"role": "user", "content": "Tool observations:\n" + observations})
                return self._run_write_loop("Continue the same task from those observations and write its files.", _tool_depth + 1)
        return state["count"]

    # Builds app in the format expected by the next pipeline steps.
    def build_app(self) -> int:
        """Build app in the standard shape used by the rest of the pipeline."""
        # From: agents/planner/builder/file_writer.py
        total, phases, written = len(self._planned_files()), self.plan.get("phases") or [], 0
        self._log("INFO", f"⚙️  Building {total} planned files across {len(phases)} tasks")
        for index, task in enumerate(phases, 1):
            # From: agents/planner/builder/file_writer.py
            files = [item for item in task.get("files") or [] if not self._implemented(item.get("path", ""))]
            if not files:
                continue
            self._fire("on_phase", {"phase": index, "total": len(phases), "title": task.get("title"),
                                    "status": "active", "files": [item["path"] for item in files]})
            written += self._run_write_loop(self._task_prompt(task, files))
            # From: agents/planner/builder/file_writer.py
            left = [item for item in files if not self._implemented(item["path"])]
            if left:
                written += self._run_write_loop(
                    "Finish the same approved task. These planned files are still absent or still defaults:\n"
                    + "\n".join("- " + item["path"] for item in left)
                    + "\nWrite each complete file now; do not change the plan.")
            # From: agents/planner/builder/file_writer.py
            done = total - len(self._outstanding())
            self._fire("on_progress", f"Task {index}/{len(phases)} — {done}/{total} files", 18 + int(58 * done / max(1, total)))
            # From: agents/planner/builder/file_writer.py
            self._fire("on_phase", {"phase": index, "total": len(phases), "title": task.get("title"),
                                    "status": "done",
                                    "written": sum(self._implemented(item["path"]) for item in files)})
            # From: agents/planner/builder/builder_setup.py
            self._fire("on_memory", self.memory_stats())
            # From: agents/planner/builder/project_memory.py
            self.save_convo()
        return written

    # Runs this pipeline step and returns the result.
    def run(self, user_prompt: str, *, requirement_source: str = "") -> bool:
        """Run this pipeline step and return its result."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._fire("on_progress", "Planning…", 5)
            if not self.make_plan(user_prompt, requirement_source):
                return False
            self._fire("on_progress", "Scaffolding…", 15)
            # From: agents/planner/builder/file_writer.py
            self.scaffold()
            # From: agents/planner/builder/dependency_manager.py
            self.install_planned_deps()
            self._fire("on_progress", "Writing files…", 18)
            self.build_app()
            # From: agents/planner/builder/file_writer.py
            if self._outstanding():
                # From: agents/planner/builder/file_writer.py
                self._log("WARN", f"   ⚠ Closing {len(self._outstanding())} remaining planned file(s)")
                # From: agents/planner/builder/file_writer.py
                self._run_write_loop(self._task_prompt(
                    {"id": "closure", "title": "Complete the approved plan", "goal": "No planned file remains"},
                    self._outstanding()))
            # From: agents/planner/builder/dependency_manager.py
            self.repair_missing_imports()
            # From: agents/planner/builder/dependency_manager.py
            self.sync_dependencies()
            # From: agents/planner/builder/dependency_manager.py
            self.install_unresolved()
            # From: agents/planner/builder/build_validation.py
            self.repair_lint()
            # From: agents/planner/builder/build_validation.py
            return self._verify_output()
        finally:
            # From: agents/planner/builder/project_memory.py
            self.save_convo()
