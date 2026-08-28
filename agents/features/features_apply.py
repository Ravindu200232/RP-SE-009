"""Focused apply responsibilities for FeaturesAgent."""
from agents.features.features_common import *
from agents.features.source_guidance import render_feature_prompt


class FeaturesAgentApplyMixin:
    def apply(self, request: str, spec: FeatureSpec) -> int:
        """Implement the proven plan in context-sized, dependency-aware waves."""
        if spec.is_empty():
            return 0

        from .source_guidance import feature_image_prompt
        image_contract = feature_image_prompt(request)

        for pkg in spec.packages:
            if not package_requested(pkg):
                continue
            self._log("INFO", f"   📦 npm install {pkg}")
            self.az.cmd.run(f"npm install {pkg}")

        files = self.az.source_files()
        planned = list(spec.files)
        plan_paths = {f["path"] for f in planned}

        wave_budget = max(30_000, int(self._budget_chars() * 0.34))
        waves, current, used = [], [], 0
        for f in planned:
            body = files.get(f["path"], "") or ""
            cost = len(body) + 1200
            if current and used + cost > wave_budget:
                waves.append(current)
                current, used = [], 0
            current.append(f)
            used += cost
        if current:
            waves.append(current)

        if len(waves) > 1:
            self._log("INFO", f"   🧠 large change — {len(planned)} files across "
                              f"{len(waves)} context-sized implementation waves")

        full_listing = "\n".join(
            f"  • {f['path']}  [{f['action']}]"
            f"{'  — ' + f['why'] if f['why'] else ''}" for f in planned)

        self.arch._workspace_tool_cache = {}
        total_written_before = len(spec.written)

        for wave_no, wave in enumerate(waves, 1):
            wave_paths = {f["path"] for f in wave}
            bodies = []
            latest_files = getattr(self.arch, "files", {}) or files
            for f in wave:
                body = latest_files.get(f["path"])
                if body:
                    bodies.append(f"--- {f['path']} (COMPLETE current contents) ---\n{body}")
                else:
                    bodies.append(f"--- {f['path']} (NEW FILE) ---\n(create this file)")

            shown = set(wave_paths)
            ref_used = sum(len(x) for x in bodies)
            for f in wave:
                for mod in dict.fromkeys(LOCAL_IMPORT_RE.findall(latest_files.get(f["path"], ""))):
                    for ext in (".jsx", ".js", ""):
                        rel = f"{mod}{ext}"
                        if rel in latest_files and rel not in shown:
                            block = (f"--- {rel} (reference — do NOT rewrite unless the "
                                     f"change truly requires it) ---\n{latest_files[rel]}")
                            if ref_used + len(block) <= wave_budget:
                                shown.add(rel)
                                bodies.append(block)
                                ref_used += len(block)
                            break
            for helper in ("app/layout.jsx", "app/layout.js", "lib/mongodb.js",
                           "lib/auth.js", "lib/auth-client.js"):
                if helper in latest_files and helper not in shown:
                    block = (f"--- {helper} (reference) ---\n"
                             f"{latest_files[helper][:5000]}")
                    if ref_used + len(block) <= wave_budget:
                        shown.add(helper); bodies.append(block); ref_used += len(block)

            wave_listing = "\n".join(
                f"  • {f['path']}  [{f['action']}]"
                f"{'  — ' + f['why'] if f['why'] else ''}" for f in wave)
            reasoning = spec.context or {}
            evidence_lines = "\n".join(
                f"  • {e.get('path', '')}: {e.get('fact', '')}"
                for e in (reasoning.get('evidence') or []) if e.get('path'))
            user = render_feature_prompt(
                "APPLY", request=request,
                image_contract=("## Image generation contract\n" + image_contract
                                if image_contract else ""),
                current=reasoning.get("current") or "(not recorded)",
                gap=reasoning.get("gap") or "(not recorded)",
                cause=reasoning.get("cause") or "(not recorded)",
                evidence=evidence_lines or "  • (none — inspect before guessing)",
                verify=reasoning.get("verify") or "(not recorded)",
                summary=spec.summary, full_plan=full_listing,
                wave_number=wave_no, wave_total=len(waves),
                wave_plan=wave_listing, source="\n".join(bodies))

            convo = ([{"role": "system", "content": self.arch._builder_sys() + "\n\n" + TOOL_HELP}]
                     + self._memory()
                     + [{"role": "user", "content": user}])
            wave_written = []

            def on_end(path, content):
                key = normalise_change_path(path)
                if not safe_change_path(key):
                    self._log("WARN", f"   ⛔ ignored unsafe source path {key}")
                    return
                if key not in plan_paths:
                    self._log("INFO", f"   ↗ impact expanded to {key} after code inspection")
                old = (getattr(self.arch, "files", {}) or {}).get(key, "")
                if old and len(content) < 0.4 * len(old):
                    self._log("INFO", f"   ✂ {key} goes from {len(old)} to "
                                      f"{len(content)} characters — verifying the requested removal/restructure")
                self._fire("on_file_start", key)
                self._fire("on_file_end", key, content)
                if self.arch.write_file(key, content):
                    if key not in spec.written:
                        spec.written.append(key)
                    wave_written.append(key)

            parser = FileStreamParser(
                on_text=lambda t: None, on_file_start=lambda p: None,
                on_file_token=lambda t: None, on_file_end=on_end)
            raw = []
            seen_obs = set()
            try:
                while True:
                    turn_raw = []
                    def feed_turn(tok):
                        turn_raw.append(tok); raw.append(tok); parser.feed(tok)
                    self.arch._stream(convo, feed_turn, temperature=0.35, model=self.model)
                    reply = "".join(turn_raw)
                    convo.append({"role": "assistant", "content": reply})
                    observations, used_tools = WorkspaceTools(self.arch).serve(reply)
                    if used_tools and not wave_written:
                        sig = observations.strip()
                        if (sig and sig not in seen_obs and
                                sum(len(m["content"]) for m in convo) < self._budget_chars()):
                            seen_obs.add(sig)
                            self._log("INFO", f"   🧰 implementation inspected {used_tools} workspace tool(s)")
                            convo.append({"role": "user", "content":
                                          "Tool observations:\n\n" + observations +
                                          "\n\nContinue the same change. Follow the dependency evidence and write the files this wave needs."})
                            continue
                    break
            except Exception as e:
                self._log("WARN", f"   ⚠ Feature write failed in wave {wave_no}: {e}")
            finally:
                parser.close()

            for out in self.arch.run_requested_commands("".join(raw)):
                self._log("INFO", f"   📦 {out.splitlines()[0][:110]}")

            if not wave_written:
                self._log("WARN", f"   ⚠ implementation wave {wave_no} changed nothing")

        if len(spec.written) > total_written_before:
            self.arch.sync_dependencies()
        return len(spec.written) - total_written_before

    def remember(self, request: str, spec: FeatureSpec) -> bool:
        """Record a compact request/decision receipt for later edits."""
        if not spec.written:
            return False
        arch = self.arch
        try:
            if not arch.convo:

                arch.convo = [
                    {"role": "system", "content": arch._builder_sys()},
                    {"role": "user", "content":
                        "This is the app we are working on.\n\n## The plan\n"
                        + (arch.plan_md or self.az.plan_text() or "")[:8000]},
                    {"role": "assistant", "content":
                        "Understood. I have the plan for this project."},
                ]
            files = "\n".join(
                f"  • {f['path']} ({f['action']})"
                + (f" — {f['why']}" if f.get("why") else "")
                for f in spec.files if f["path"] in spec.written)
            arch.convo.append({"role": "user", "content":
                               f"Add this feature: {request}"})
            arch.convo.append({"role": "assistant", "content":
                               f"{spec.summary or 'Done.'}\n\nFiles:\n{files}"})
            arch._trim_convo()
            return True
        except Exception as e:
            log.warning(f"could not record the feature: {e}")
            return False

    def update_plan(self, request: str, spec: FeatureSpec) -> bool:
        """Append only successfully written files to plan.md."""
        landed = [f for f in spec.files if f["path"] in spec.written]
        if not landed:
            return False
        md = self.arch.plan_md or ""
        title = (spec.summary or request).strip().rstrip(".")[:70]
        section = [f"\n## Feature — {title}\n",
                   (spec.summary or request).strip()[:400], "", "Files:"]
        for f in landed:
            section.append(f"- `{f['path']}` — {f['why'] or f['action']}")
        if spec.routes:
            section.append("")
            section.append("Routes: " + ", ".join(f"`{r}`" for r in spec.routes))
        block = "\n".join(section) + "\n"

        marker = "\n## Definition of Done"
        if marker in md:
            md = md.replace(marker, block + marker, 1)
        else:
            md = md.rstrip() + "\n" + block
        self.arch.plan_md = md
        self.arch.write_file("plan.md", md)
        return True

    def run(self, request: str) -> FeatureSpec:
        self._fire("on_phase", {"phase": -9, "title": "Planning the feature",
                                "status": "active"})
        spec = self.plan_feature(request)
        self._fire("on_phase", {"phase": -9, "title": "Planning the feature",
                                "status": "done"})
        if spec.is_empty():
            self._log("WARN", "   ⚠ The model did not name any files to change")
            return spec

        spec = self.cover_whole_request(request, spec)

        self._log("INFO", f"   🧩 {spec.summary or request[:60]}")
        for f in spec.files:
            self._log("INFO", f"      {f['action']:4} {f['path']}")
        self._fire("on_feature_plan", {
            "summary": spec.summary, "files": spec.files,
            "packages": spec.packages, "routes": spec.routes})

        self._fire("on_phase", {"phase": -10, "title": "Writing the feature",
                                "status": "active"})
        n = self.apply(request, spec)
        self._fire("on_phase", {"phase": -10, "title": "Writing the feature",
                                "status": "done", "written": n})
        if n:
            spec = self.converge_semantics(request, spec, rounds=2)
            self.update_plan(request, spec)
            self.remember(request, spec)
        return spec

from agents.features.features_planning import FeaturesAgentPlanningMixin
from agents.features.features_audit import FeaturesAgentAuditMixin


class FeaturesAgent(FeaturesAgentPlanningMixin, FeaturesAgentApplyMixin,
                    FeaturesAgentAuditMixin, FeaturesAgentBase):
    """Concrete feature planner/applicator/auditor."""
    pass
