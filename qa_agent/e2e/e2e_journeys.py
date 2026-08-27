"""Journey discovery and scenario authoring."""
from qa_agent.e2e.e2e_common import *
from qa_agent.e2e.e2e_contract import capability_contract

class E2EJourneyAuthoringMixin:
    def _journeys_from_plan_md(self, roles: list) -> list:
        """The `### Journeys` chains out of the architect's plan.md.

        Ten of the fifteen projects on disk have no `workflows` anywhere, so
        the E2E author was being handed "What the librarian does here" with no
        steps — a journey with nothing in it. The plan wrote the journeys
        down in prose the whole time.
        """
        md = getattr(self.arch, "plan_md", "") or ""
        i = md.find("## Page Flow")
        if i < 0:
            return []
        body = md[i:]
        end = body.find("\n## ", 4)
        body = body[:end] if end > 0 else body

        out = []
        for line in body.splitlines():
            if not self._BULLET.match(line):
                continue
            # Strip the markdown before parsing rather than trying to match.
            plain = self._BULLET.sub("", line).replace("`", "").replace("*", "")
            title, sep, rest = plain.partition(":")
            if not sep:
                continue
            title = " ".join(title.split())[:60]
            hops = [h.strip() for h in self._ARROW.split(rest)]
            hops = [h for h in hops if h.startswith("/")]
            if not title or len(hops) < 2:
                continue
            steps = [f"go to {h}" if n == 0 else f"then reach {h}"
                     for n, h in enumerate(hops)]
            # whose section does this chain spend its time in
            role = ""
            for r in roles:
                if r and any(h.lstrip("/").split("/")[0] == r for h in hops):
                    role = r
                    break
            out.append({"title": title, "steps": steps, "role": role})
            if len(out) >= MAX_FLOWS:
                break
        if out:
            self._log("INFO", f"   🧭 {len(out)} journey(s) read from the "
                              f"plan's Page Flow — the workflows were empty")
        return out

    def testids_in_app(self, limit: int = 40) -> list:
        """Every `data-testid` the app really sets, read from its own markup.

        The scenario author had the routes, the journey and the real source,
        and still had to name controls by their accessible name — so it wrote
        `CLICK :: link role /basket/i` for a link the page does not have, and
        all three journeys of a bookshop build failed on that shape without a
        single line of the app being wrong.

        The plan now asks for testids and the builder writes them; this is the
        other half. Read from the markup rather than the plan on purpose: what
        matters is the attribute that is actually there, and a plan entry the
        builder skipped would be exactly the invented selector this exists to
        stop.
        """
        files = getattr(self.arch, "files", None) or {}
        out = []
        for path in sorted(files):
            if not path.startswith(("app/", "components/")):
                continue
            for name in self._TESTID_RE.findall(files[path] or ""):
                if name not in out:
                    out.append(name)
                    if len(out) >= limit:
                        return out
        return out

    def testids_for_journey(self, journey: dict = None, limit: int = 40) -> list:
        """Literal test ids only from source files relevant to this journey."""
        files = getattr(self.arch, "files", None) or {}
        out = []
        for path in self._journey_pages(journey):
            body = str(files.get(path) or self.source_of(path, 12_000) or "")
            # Include directly-rendered local components through markup_for.
            body += "\n" + self.markup_for(path, 12_000)
            for name in self._TESTID_RE.findall(body):
                if name not in out:
                    out.append(name)
                    if len(out) >= limit:
                        return out
        return out

    def _auto_journeys(self, roles: list, covered_ids=None, max_flows: int = MAX_FLOWS) -> list:
        """Synthesize meaningful E2E journeys when the project did not declare them.

        Existing/imported apps often have pages and capabilities but no
        `workflows` and no `tests/e2e/*.spec.js`.  Skipping E2E in that case is
        backwards: it is exactly the project whose user flows have never been
        proved.  Build a small deterministic journey ledger from the machine
        capability map first, and from the route tree as a last resort.  The
        model still authors selectors from real DOM/source evidence; Python
        decides WHAT must be covered so it cannot silently choose one pretty
        page and call the app tested.
        """
        covered_ids = {str(x or "").upper() for x in (covered_ids or []) if str(x or "").strip()}
        plan = getattr(self.arch, "plan", None) or {}
        caps = [c for c in (plan.get("capabilities") or [])
                if isinstance(c, dict) and bool(c.get("e2e", True))]
        contracts = [c for c in (plan.get("contracts") or []) if isinstance(c, dict)]
        out = []

        # Uncovered capabilities are grouped by role.
        pending = [c for c in caps
                   if str(c.get("id") or "").upper() not in covered_ids]
        groups = {}
        for c in pending:
            role = str(c.get("who") or "").strip().lower()
            groups.setdefault(role, []).append(c)

        # Fit all requirement capabilities into the available journey budget.
        # Previously this hard-chunked by three and then truncated at max_flows,
        # which silently dropped later requirements. Give every role at least one
        # flow, then spend spare slots on the densest roles; each allocated flow
        # receives a balanced slice of that role's capabilities.
        role_items = list(groups.items())
        slots = max(0, int(max_flows or 0))
        if slots <= 0:
            return []
        if len(role_items) > slots:
            role_items = sorted(role_items, key=lambda x: (-len(x[1]), x[0]))[:slots]
            self._log("WARN", "   ⚠ more E2E roles than the flow budget — prioritizing the roles with the most required capabilities")
        allocations = {role: 1 for role, _group in role_items} if slots else {}
        spare = max(0, slots - len(allocations))
        while spare and allocations:
            candidates = [(len(group) / allocations[role], role)
                          for role, group in role_items
                          if allocations[role] < len(group)]
            if not candidates:
                break
            _density, role = max(candidates)
            allocations[role] += 1
            spare -= 1

        for role, group in role_items:
            parts = max(1, allocations.get(role, 1))
            chunk_size = max(1, (len(group) + parts - 1) // parts)
            for off in range(0, len(group), chunk_size):
                chunk = group[off:off + chunk_size]
                routes = []
                def add_route(url):
                    url = str(url or "").strip()
                    if url and url.startswith("/") and url not in routes:
                        routes.append(url)

                files = set()
                for c in chunk:
                    for rel in (c.get("files") or []):
                        rel = str(rel or "").strip()
                        if not rel:
                            continue
                        files.add(rel)
                        add_route(self._url_for_file(rel))

                contract_steps = []
                for c in contracts:
                    frm = str(c.get("from") or "").strip()
                    target = str(c.get("target") or "").strip()
                    if frm not in files and not any(f and f in target for f in files):
                        continue
                    add_route(self._url_for_file(frm))
                    if target.startswith("/") and "[" not in target:
                        add_route(target)
                    trigger = str(c.get("trigger") or "").strip()
                    effect = str(c.get("effect") or "").strip()
                    if trigger or effect:
                        contract_steps.append(
                            "perform " + (trigger or "the planned action")
                            + (" — prove " + effect if effect else ""))

                steps = []
                for url in routes[:4]:
                    if "[" not in url:
                        steps.append(f"go to {url}")
                steps.extend(contract_steps[:3])
                for c in chunk:
                    req = str(c.get("requirement") or "").strip()
                    proof = str(c.get("proof") or "").strip()
                    steps.append("prove " + req + (f" — expected: {proof}" if proof else ""))

                reqs = [str(c.get("requirement") or "").strip() for c in chunk]
                label = "; ".join(r for r in reqs if r)[:110] or "app capability"
                out.append({
                    "title": f"Auto E2E — {label}",
                    "steps": steps[:10],
                    "role": role,
                    "covers": [str(c.get("id") or "").upper() for c in chunk
                               if str(c.get("id") or "").strip()],
                    "generated": True,
                })
                if len(out) >= max_flows:
                    return out

        # If a machine capability map exists.
        if caps:
            return out

        # No machine capability map either: existing/legacy app.
        try:
            route_map = self.az.enumerate_routes() or {} if self.az else {}
        except Exception:
            route_map = {}
        static = [u for u, m in sorted(route_map.items())
                  if m.get("kind") == "page" and not m.get("dynamic")
                  and "[" not in u and not self._is_auth_route(u)]
        if not static:
            return []

        roles_to_make = list(roles) or [""]
        for role in roles_to_make:
            scored = []
            for u in static:
                low = u.lower()
                hit = 0
                if role and (low == f"/{role}" or low.startswith(f"/{role}/")
                             or role in low.replace("-", " ").replace("_", " ")):
                    hit = 2
                elif u == "/":
                    hit = 1
                scored.append((-hit, u.count("/"), u))
            chosen = [u for _, _, u in sorted(scored)[:4]]
            steps = [f"go to {u}" for u in chosen]
            steps.append("exercise one enabled navigation/form/action visible on these pages "
                         "and assert its URL or visible state changes")
            out.append({
                "title": f"Auto E2E — {role or 'visitor'} route and interaction coverage",
                "steps": steps,
                "role": role,
                "covers": [],
                "generated": True,
            })
            if len(out) >= max_flows:
                break
        return out

    def journeys(self) -> list:
        """Every journey the app should be able to walk, from the plan.

        The plan's `workflows` are the app's own definition of what it is for
        — "Buying clothes", "Updating shop stock" — and each names the role
        that walks it. Until now the E2E stage wrote ONE scenario for "the
        most important journey", so a shop with a customer flow and a manager
        flow proved one and shipped the other untested. This hands back all
        of them, so the driver can run one flow per journey.

        If declared workflows are missing, AgentForge synthesizes journey
        blueprints from e2e capabilities and, for legacy apps with neither,
        from the real route tree. The authored scenario is then exported to
        tests/e2e/*.spec.js, so "no E2E supplied" means "generate E2E", never
        "skip E2E".
        """
        out = []
        accs = self.accounts()
        roles = sorted({(a.get("role") or "").lower() for a in accs
                        if a.get("role")})

        sources = []
        plan = getattr(self.arch, "plan", None) or {}
        if plan.get("workflows"):
            sources.append(plan["workflows"])
        try:
            srs_plan = self.project_dir / ".agentforge" / "srs" / "plan.json.srs"
            if srs_plan.is_file():
                d = json.loads(srs_plan.read_text(encoding="utf-8"))
                d = d.get("plan") or d
                if d.get("workflows"):
                    sources.append(d["workflows"])
        except Exception as e:
            log.debug(f"srs plan: {e}")

        if not sources:
            plan_flows = self._journeys_from_plan_md(roles)
            if plan_flows:
                sources.append(plan_flows)

        seen = set()
        for wfs in sources:
            for wf in wfs or []:
                if not isinstance(wf, dict):
                    continue
                title = str(wf.get("name") or wf.get("title") or "").strip()
                steps = [str(s).strip() for s in (wf.get("steps") or []) if str(s).strip()]
                if not title or not steps or title.lower() in seen:
                    continue
                seen.add(title.lower())
                # the role, if the workflow names one.
                role = str(wf.get("who") or wf.get("role") or wf.get("actor")
                           or "").strip().lower()
                if not role:
                    text = " ".join(steps).lower()
                    role = next((r for r in roles if r and r in text), "")
                covers = [str(x).strip().upper() for x in (wf.get("covers") or [])
                          if str(x).strip()] if isinstance(wf.get("covers"), list) else []
                out.append({"title": title, "steps": steps, "role": role,
                            "covers": covers})

        # If workflows are absent (common on imported/legacy apps).
        covered_ids = {str(x or "").upper()
                       for j in out for x in (j.get("covers") or [])}
        # Declared workflows are already meaningful E2E blueprints.
        has_capability_map = bool((plan.get("capabilities") or []))
        available_flows = max(0, MAX_FLOWS - len(out))
        auto = ([] if (sources and not has_capability_map)
                else self._auto_journeys(roles, covered_ids, available_flows))
        if auto:
            existing_specs = list((self.project_dir / "tests" / "e2e").glob("*.spec.js"))                 if (self.project_dir / "tests" / "e2e").is_dir() else []
            if not sources:
                self._log("INFO", f"   🧪 no declared E2E workflows — generated "
                                  f"{len(auto)} journey blueprint(s) from "
                                  f"capabilities/routes")
            elif any(j.get("covers") for j in auto):
                self._log("INFO", f"   🧪 generated {len(auto)} extra E2E "
                                  f"journey blueprint(s) for uncovered capabilities")
            if not existing_specs:
                self._log("INFO", "   🧪 project had no E2E specs — AgentForge "
                                  "will write tests/e2e/*.spec.js from these journeys")
            for j in auto:
                if len(out) >= MAX_FLOWS:
                    break
                key = (j.get("title", "").lower(), j.get("role", ""))
                if not any((x.get("title", "").lower(), x.get("role", "")) == key
                           for x in out):
                    out.append(j)

        covered_roles = {j["role"] for j in out if j.get("role")}
        for r in roles:
            if r not in covered_roles and len(out) < MAX_FLOWS:
                out.append({"title": f"Auto E2E — what the {r} does here",
                            "steps": [f"exercise the primary {r} workflow end to end "
                                      "using only controls observed in the real DOM"],
                            "role": r, "covers": [], "generated": True})
        if not out:
            out.append({"title": "Auto E2E — visitor smoke and interaction",
                        "steps": ["open the public entry page",
                                  "exercise one enabled user action and assert its result"],
                        "role": "", "covers": [], "generated": True})
        final = out[:MAX_FLOWS]

        # Final requirement ledger: do not silently lose capabilities merely
        # because declared workflows consumed the flow budget. Pack uncovered
        # capabilities into an existing journey for the same actor. The machine
        # proof contract then forces the scenario author to exercise and assert
        # every packed capability, without adding another browser startup.
        required_caps = {
            str(c.get("id") or "").strip().upper(): c
            for c in (plan.get("capabilities") or [])
            if isinstance(c, dict) and bool(c.get("e2e", True))
            and str(c.get("id") or "").strip()
        }
        covered = {str(cid or "").upper() for item in final
                   for cid in (item.get("covers") or [])}
        for cid, cap in required_caps.items():
            if cid in covered:
                continue
            role = str(cap.get("who") or "").strip().lower()
            candidates = [j for j in final
                          if str(j.get("role") or "").strip().lower() == role]
            if not candidates and len(final) < MAX_FLOWS:
                j = {
                    "title": f"Auto E2E — {role or 'visitor'} requirement coverage",
                    "steps": [], "role": role, "covers": [], "generated": True,
                }
                final.append(j)
                candidates = [j]
            if not candidates:
                continue
            target = min(candidates, key=lambda j: len(j.get("covers") or []))
            target.setdefault("covers", []).append(cid)
            req = str(cap.get("requirement") or "").strip()
            proof = str(cap.get("proof") or "").strip()
            if req and len(target.setdefault("steps", [])) < 12:
                target["steps"].append(
                    "prove " + req + (f" — expected: {proof}" if proof else ""))
            covered.add(cid)

        missing = [cid for cid in required_caps if cid not in covered]
        if missing:
            self._log("WARN", "   ⚠ E2E flow budget cannot represent every actor requirement: "
                      + ", ".join(missing[:12]))
        elif required_caps:
            self._log("INFO", f"   ✅ E2E requirement ledger covers {len(required_caps)}/{len(required_caps)} capabilities")

        for item in final:
            item["contract"] = capability_contract(self.arch, item)
        return final

    def author(self, previous: Scenario = None, why: str = "",
               page: str = "", journey: dict = None) -> Scenario:
        """One model call. Returns a parsed scenario — possibly an empty one.

        `journey` names the workflow this scenario must walk — its title, its
        steps and its role. Without it the model chose "the most important
        journey", which was always the same one, so the rest of the app never
        got exercised.
        """
        accs = self.accounts()
        roles = ", ".join(sorted({(a.get("role") or "user") for a in accs})) \
            or "there are no demo accounts — write a signed-out journey"
        idea = self._idea()

        ask = (f"## The app\n{idea}\n\n"
               f"## Pages and endpoints it serves\n{self._routes() or '  (unknown)'}\n\n"
               f"## Demo accounts available\nRoles: {roles}\n"
               f"Use {{{{email}}}} and {{{{password}}}} — AgentForge fills in the "
               f"real values for the role you name with AS.\n")

        if journey:
            steps = "\n".join(f"  {i}. {s}" for i, s in
                              enumerate(journey.get("steps") or [], start=1))
            ask += (f"\n## THE JOURNEY THIS SCENARIO WALKS\n"
                    f"{journey['title']}"
                    + (f" — as the {journey['role']}" if journey.get("role") else "")
                    + "\n" + (steps or "  (walk it end to end)") + "\n"
                    f"Walk EVERY step above, in order, and assert on what each "
                    f"one leaves behind — the row that appeared, the total that "
                    f"changed, the status that moved. A scenario that signs in "
                    f"and looks at one page has not walked this journey.\n")
            contract = journey.get("contract") or capability_contract(self.arch, journey)
            ask += ("\n## EXECUTABLE PROOF CONTRACT\n"
                    + json.dumps(contract, ensure_ascii=False, indent=2)[:7000]
                    + "\nThis contract is authoritative. Do not invent a field, control, route, "
                      "success sentence, or role outside it. Assertions must prove the listed "
                      "effects/proofs, not merely that a page rendered.\n")

            covers = {str(x).upper() for x in (journey.get("covers") or [])}
            if covers:
                caps = []
                for c in (getattr(self.arch, "plan", None) or {}).get("capabilities") or []:
                    if str(c.get("id") or "").upper() in covers:
                        caps.append(f"  {c.get('id')}: {c.get('requirement')} — PROVE: {c.get('proof')}")
                if caps:
                    ask += ("\n## CAPABILITIES THIS JOURNEY MUST PROVE\n" + "\n".join(caps) +
                            "\nDo not finish DONE until every proof above has an assertion after the action. "
                            "For filters/search/availability, enter values, trigger the filter, and assert "
                            "the result changed or an occupied/unavailable record is absent.\n")

        if journey:
            jroutes = self._journey_routes(journey)
            if jroutes:
                ask += ("\n## ROUTES RELEVANT TO THIS JOURNEY\n  "
                        + " · ".join(jroutes)
                        + "\nUse these exact routes. After login, explicitly GOTO the "
                          "route where the next job happens instead of asserting "
                          "that the login landing page has guessed copy.\n")

            live = self.runtime_evidence(journey)
            if live:
                ask += ("\n## RUNTIME DOM EVIDENCE — OBSERVED IN A REAL BROWSER\n"
                        + live
                        + "\nThese names/fields/routes are facts. For page identity use "
                          "EXPECT_URL. For controls/fields choose only things "
                          "listed here or in the source markup below. Never "
                          "invent headings such as 'Room Management' or marketing "
                          "copy merely because the journey sounds like it.\n"
                          "If this journey TYPES a new value (for example a review "
                          "body, title, status or price), it is valid to assert that "
                          "exact value after the save even though it was not present "
                          "in source before the run. For any other success copy, use "
                          "only wording observed here/source — never invent a nice-"
                          "sounding confirmation sentence.\n")

        shown = ([page] if page else []) + self._journey_pages(journey)
        blocks, used = [], 0
        for rel in dict.fromkeys(s for s in shown if s):
            block = self.markup_for(rel)
            if not block:
                continue
            if used + len(block) > self.MARKUP_BUDGET and blocks:
                break
            blocks.append(block)
            used += len(block)
        body = "\n\n".join(blocks)
        if body:
            ask += (f"\n## The real markup\n```jsx\n{body}\n```\n"
                    f"Copy the placeholders, button labels and visible text "
                    f"above into your selectors. Do not guess at wording that "
                    f"is written down right here — and do not assert text that "
                    f"is not in it.\n")

        tids = self.testids_for_journey(journey)
        if tids:
            ask += (f"\n## Controls this app labels for you\n  "
                    + ", ".join(tids)
                    + "\nThese are `data-testid` values that really are in the "
                      "markup above. When the control you need is one of them, "
                      "write `testid=<name>` — it is the one selector the app "
                      "promises not to reword. Never invent one that is not on "
                      "this list.\n")

        if journey:
            ask += (f"\nWrite ONE scenario that walks the journey above — "
                    f"'{journey['title']}' — end to end.")
        else:
            ask += ("\nWrite ONE scenario for the most important journey this "
                    "app exists to support.")
        if previous is not None and why:
            ask += (f"\n\n## Your previous scenario did not work\n{why}\n\n"
                    f"It was:\n{self._render(previous)}\n\n"
                    f"Write it again. Keep every valid step. Replace only the "
                    f"ungrounded assertion/locator identified above. Match observed "
                    f"markup/DOM exactly, and for post-save state prefer the exact "
                    f"value the scenario entered over invented success copy.")

        convo = [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": ask}]
        raw = []
        parser = FileStreamParser(on_text=lambda t: raw.append(t),
                                  on_file_start=lambda p: None,
                                  on_file_token=lambda t: None,
                                  on_file_end=lambda p, c: None)
        try:
            self.arch._stream(convo, parser.feed, temperature=TEMPERATURE,
                              model=QASession.model_for(self.qa, self.arch),
                              timeout=CALL_BUDGET)
        except Exception as e:
            self._log("WARN", f"   ⚠ could not write an end-to-end flow: {e}")
            return Scenario()
        parser.close()

        text = "".join(raw)
        sc = parse_scenario(text, account=self.account_for_scenario(text, journey))
        for _, line, reason in sc.dropped[:4]:
            self._log("WARN", f"   ⚠ dropped `{line}` — {reason}")
        return sc
