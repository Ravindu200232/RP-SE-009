"""Feature planning steps split by responsibility."""
# Source: feature_contract.py — imported helper(s) come from this file.
from agents.features.feature_contract import *
# Source: feature_prompts.py — imported helper(s) come from this file.
from agents.features.feature_prompts import feature_image_prompt, render_feature_prompt

class FeatureRequestPlanningMixin:
    # Plan feature in the format expected by the next pipeline steps.
    def plan_feature(self, request: str, max_reads: int | None = MAX_READS) -> FeatureSpec:
        """Plan feature in the standard shape used by the rest of the pipeline."""
        routes = self.az.enumerate_routes()
        route_hint = str(getattr(self, "route_hint", "") or "").split("?", 1)[0].rstrip("/") or "/"
        focus = []
        meta = routes.get(route_hint) or {}
        route_owner = str(meta.get("file") or "")
        if route_owner:
            focus.append(route_owner)
        # From: agents/features/feature_contract.py
        for rel in self.feature_focus_paths(request):
            if rel not in focus:
                focus.append(rel)
        # From: agents/features/feature_contract.py
        source = self._focused_source(focus, budget=int(self._budget_chars() * 0.20))
        # From: agents/features/feature_prompts.py
        image_contract = feature_image_prompt(request)
        # From: agents/features/feature_prompts.py
        user = render_feature_prompt(
            "PLAN_REQUEST", plan=self.az.plan_text()[:6000],
            routes=self.az.route_table(routes), route_hint=route_hint,
            route_owner=route_owner or "(not resolved)", request=request,
            image_contract=("## Image generation contract\n" + image_contract
                            if image_contract else ""),
            inventory=self.az.inventory(), source=source or "(none)")
        # From: agents/features/planning/evidence_planning.py
        return self._plan(PLAN_SYSTEM, user, max_reads, "Feature planning", mode="feature")

    # Plan visual-editor impact before choosing focused or full apply.
    def plan_change(self, request: str, *, selected_path: str = "",
                    selected_route: str = "", selected_element: str = "") -> FeatureSpec:
        """Plan visual-editor impact before choosing focused or full apply."""
        routes = self.az.enumerate_routes()
        focus = []
        if selected_path:
            focus.append(selected_path)
        # From: agents/features/feature_contract.py
        for rel in self.feature_focus_paths(request):
            if rel not in focus:
                focus.append(rel)
        # From: agents/features/feature_contract.py
        source = self._focused_source(focus, budget=int(self._budget_chars() * 0.40))
        selected = ""
        if selected_path or selected_route or selected_element:
            selected = ("## The exact UI context\n"
                        f"Route: {selected_route or '/'}\n"
                        f"Current source file: {selected_path or '(unknown)'}\n"
                        f"Selected region: {selected_element or '(not described)'}\n\n")
        # From: agents/features/feature_prompts.py
        user = render_feature_prompt(
            "CHANGE_REQUEST", plan=self.az.plan_text()[:6000],
            routes=self.az.route_table(routes), selection=selected,
            request=request, inventory=self.az.inventory(),
            source=source or "(none)")
        # From: agents/features/planning/evidence_planning.py
        return self._plan(PLAN_SYSTEM, user, None, "Change impact analysis",
                          mode="visual", required_evidence_paths=[selected_path] if selected_path else None)

    # Ask a second model pass whether every request clause has an owner.
    def cover_whole_request(self, request: str, spec: FeatureSpec) -> FeatureSpec:
        """Ask a second model pass whether every request clause has an owner."""
        if not spec.files:
            return spec
        listing = "\n".join(f"  {f.get('action', 'edit'):4} {f['path']}"
                            for f in spec.files)
        ask = (f"## What was asked for\n{request}\n\n"
               f"## What the plan says it will do\n{spec.summary or '(no summary)'}\n\n"
               f"## The files it will change\n{listing}\n\n"
               f"Name the parts of the request no file above will deliver.")
        buf = []
        try:
            self.arch._stream([{"role": "system", "content": self.COVER_SYSTEM},
                               {"role": "user", "content": ask}],
                              buf.append, temperature=0.1, model=self.model)
        except Exception as e:
            self._log("WARN", f"   ⚠ could not check the plan covers the "
                              f"request ({str(e)[:60]}) — building it as planned")
            return spec

        gaps = [(m.group(1).strip(), m.group(2).strip()) for m in
                re.finditer(r"^\s*MISSING\s*::\s*(.+?)\s*::\s*(.+?)\s*$",
                            "".join(buf), re.M)]
        if not gaps:
            return spec

        self._log("WARN", f"   🧩 the plan leaves {len(gaps)} part(s) of the "
                          f"request undone — asking for them too")
        for what, where in gaps:
            self._log("WARN", f"      · {what[:90]} → {where}")

        tail = "\n".join(f"- {what}  (belongs in {where})" for what, where in gaps)
        again = self.plan_feature(
            f"{request}\n\nA first plan missed these parts of it. The new plan "
            f"must deliver them as well as everything else:\n{tail}")
        # From: agents/features/feature_contract.py
        if again.is_empty():
            self._log("WARN", "   ⚠ the second plan came back empty — keeping "
                              "the first")
            return spec

        # Union, not replacement.
        # From: agents/features/feature_contract.py
        have = spec.paths()
        merged = list(spec.files) + [f for f in again.files
                                     if f["path"] not in have]
        added = len(merged) - len(spec.files)
        spec.files = merged
        spec.summary = again.summary or spec.summary
        for pkg in again.packages:
            if pkg not in spec.packages:
                spec.packages.append(pkg)

        # Keep the source proof that justified the added coverage files.
        ctx = spec.context or {}
        more = again.context or {}
        ev = list(ctx.get("evidence") or [])
        seen_ev = {str(x.get("path") or "") for x in ev if isinstance(x, dict)}
        for item in (more.get("evidence") or []):
            if isinstance(item, dict) and item.get("path") not in seen_ev:
                ev.append(item); seen_ev.add(item.get("path"))
        ctx["evidence"] = ev
        if more.get("cause"):
            base = str(ctx.get("cause") or "").strip()
            extra = str(more.get("cause") or "").strip()
            ctx["cause"] = (base + "; coverage analysis: " + extra) if base else extra
        if more.get("verify"):
            ctx["verify"] = str(more.get("verify"))
        if more.get("confidence") in ("high", "medium"):
            ctx["confidence"] = more.get("confidence")
        spec.context = ctx

        self._log("INFO", f"   ✅ {added} more file(s) planned so the whole "
                          f"request gets built")
        return spec

    # Expand evidence files into the connected source neighborhood.
    def repair_focus_paths(self, focus_paths=None, evidence: str = "") -> list[str]:
        """Expand evidence files into the connected source neighborhood."""
        files = getattr(self.arch, "files", {}) or {}
        chosen = []

        # Add one item to this local collection only when it is valid and not already present.
        def add_focus_path(rel, *, allow_missing=False):
            """Add one item to this local collection only when it is valid and not already present."""
            rel = str(rel or "").strip().lstrip("./").replace("\\", "/")
            valid = rel.startswith(("app/", "components/", "lib/", "src/", "hooks/",
                                      "utils/", "services/", "store/", "stores/")) and \
                    rel.endswith((".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".css"))
            if valid and (allow_missing or rel in files) and rel not in chosen:
                chosen.append(rel)

        for rel in focus_paths or []:
            add_focus_path(rel, allow_missing=True)
        for rel in re.findall(
                r"\b(?:app|components|lib|src|hooks|utils|services|store|stores)/[A-Za-z0-9_./\[\]()-]+\.(?:js|jsx|mjs|cjs|ts|tsx|css)\b",
                evidence or ""):
            add_focus_path(rel, allow_missing=True)

        routes = self.az.enumerate_routes()
        for url in re.findall(r"(?:https?://[^/\s]+)?(/api/[A-Za-z0-9_./\[\]-]+)",
                              evidence or ""):
            clean = url.split("?", 1)[0].rstrip("/") or "/"
            for route, meta in routes.items():
                if self.az._route_matches(clean, [route]):
                    add_focus_path(meta.get("file"))
                    break

        authish = bool(re.search(
            r"\b401\b|\b403\b|unauthori[sz]ed|forbidden|sign.?in|log.?in|session|role|/api/auth/",
            evidence or "", re.I))
        if authish:
            for rel in ("app/login/page.jsx", "app/login/page.js",
                        "lib/auth-client.js", "lib/auth.js",
                        "app/api/auth/[...all]/route.js"):
                if rel in files:
                    add_focus_path(rel)

        existing = [p for p in chosen if p in files]
        if existing:
            try:
                # From: agents/core/workspace/source_workspace.py
                graph = WorkspaceTools(self.arch).dependency_paths(
                    existing, max_depth=4, cap=44)
                for rel in graph:
                    add_focus_path(rel)
            except Exception as exc:
                log.debug(f"repair dependency neighborhood: {exc}")

        return chosen[:48]

    # Builds an evidence-backed impact map for observed runtime failures.
    def plan_repair(self, errors: str, *, server_log: str = "",
                    max_reads: int | None = MAX_READS, focus_paths=None) -> FeatureSpec:
        """Build an evidence-backed impact map for observed runtime failures."""
        routes = self.az.enumerate_routes()

        focus = self.repair_focus_paths(
            focus_paths, "\n".join([errors or "", server_log or ""])) if focus_paths else []
        if focus:
            # From: agents/features/feature_contract.py
            source = self._focused_source(
                focus, budget=int(self._budget_chars() * 0.40))
        else:
            # From: agents/features/feature_contract.py
            source = self.full_source(budget=int(self._budget_chars() * 0.42))
        # From: agents/features/feature_prompts.py
        user = render_feature_prompt(
            "REPAIR_REQUEST", plan=self.az.plan_text()[:4000],
            source=source or self.az.inventory(),
            routes=self.az.route_table(routes), errors=errors[:6000],
            server_log=server_log[:4000] or "(none)")
        # From: agents/features/planning/evidence_planning.py
        return self._plan(REPAIR_SYSTEM, user, max_reads,
                          "Repair planning", allow_empty=True, mode="repair",
                          investigation_paths=focus or None)

