"""Requirement extraction, capability-gap detection and plan generation."""
from agents.planning.architect_core import *
from agents.planning.architect_core import _fix_doubled_tags, _strip_fence, _safe_flush_len, _RefusalLoop
from agents.planning.architect_prompts import *


class ArchitectPlanningMixin:
    @staticmethod
    def _source_requirements(user_prompt: str) -> list:
        """Exact action clauses from a free-form user idea.

        Numbered SRS requirements already have a deterministic FR ledger.  A
        short natural-language idea does not, which used to let the planner
        silently drop one verb and then prove its own smaller plan.  Keep the
        user's own action clauses as the independent checklist.  This is a
        deliberately conservative extractor: it only keeps clauses containing
        an application-action verb, never invents a requirement.
        """
        text = " ".join(str(user_prompt or "").replace("\r", " ").split())
        if not text:
            return []
        action = re.compile(
            r"\b(?:browse(?:s|d|ing)?|check(?:s|ed|ing)?|book(?:s|ed|ing)?|"
            r"see(?:s|ing)?|view(?:s|ed|ing)?|list(?:s|ed|ing)?|search(?:es|ed|ing)?|"
            r"filter(?:s|ed|ing)?|create(?:s|d|ing)?|add(?:s|ed|ing)?|edit(?:s|ed|ing)?|"
            r"update(?:s|d|ing)?|change(?:s|d|ing)?|delete(?:s|d|ing)?|remove(?:s|d|ing)?|"
            r"mark(?:s|ed|ing)?|pay(?:s|ing|paid)?|track(?:s|ed|ing)?|manage(?:s|d|ing)?|"
            r"assign(?:s|ed|ing)?|approve(?:s|d|ing)?|reject(?:s|ed|ing)?|upload(?:s|ed|ing)?|"
            r"download(?:s|ed|ing)?|register(?:s|ed|ing)?|sign\s*[- ]?in|log\s*[- ]?in|"
            r"login|schedule(?:s|d|ing)?|reserve(?:s|d|ing)?|cancel(?:s|led|ing)?|"
            r"seed(?:s|ed|ing)?|show(?:s|ed|ing)?|set(?:s|ting)?|send(?:s|ing)?|"
            r"receive(?:s|d|ing)?|export(?:s|ed|ing)?|import(?:s|ed|ing)?)\b", re.I)
        actor_rx = re.compile(
            r"\b(?:guest|admin(?:istrator)?|customer|user|member|manager|owner|staff|"
            r"teacher|student|doctor|patient|employee|seller|buyer|visitor|organizer|"
            r"librarian|technician|agent)\b", re.I)
        out = []

        def action_parts(sentence):
            # Split ONLY when the next phrase has its own action verb.
            comma_chunks = [x.strip() for x in re.split(r"\s*,\s*", sentence) if x.strip()]
            chunks = []
            for ch in comma_chunks:
                if chunks and not action.search(ch):
                    chunks[-1] += ", " + ch
                else:
                    chunks.append(ch)
            final = []
            for ch in chunks:
                bits, start = [], 0
                joins = list(re.finditer(r"\s+(?:and|then)\s+", ch, re.I))
                for j, m in enumerate(joins):
                    end = joins[j + 1].start() if j + 1 < len(joins) else len(ch)
                    immediate_right = ch[m.end():end]
                    if action.search(immediate_right):
                        piece = ch[start:m.start()].strip()
                        if piece:
                            bits.append(piece)
                        start = m.end()
                tail = ch[start:].strip()
                if tail:
                    bits.append(tail)
                final.extend(bits)
            return final

        for sent in re.split(r"(?<=[.!?])\s+|[;\n]+", text):
            sent = sent.strip(" .")
            if not sent:
                continue
            actor = ""
            for bit in action_parts(sent):
                bit = bit.strip(" .")
                if not bit or not action.search(bit):
                    continue
                local_actor = actor_rx.search(bit)
                if local_actor:
                    actor = local_actor.group(0).lower()
                req = bit
                if actor and not local_actor:
                    req = f"{actor} {bit}"
                req = " ".join(req.split())[:320]
                if req and req.lower() not in {x.lower() for x in out}:
                    out.append(req)
                if len(out) >= 24:
                    return out
        return out

    @staticmethod
    def _core_features(markdown: str) -> list:
        """Core-feature bullets from the markdown half of the plan."""
        md = markdown or ""
        m = re.search(r"(?ms)^## Core Features\s*$\n(.*?)(?=^## \S|\Z)", md)
        if not m:
            return []
        out = []
        for line in m.group(1).splitlines():
            x = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
            if x:
                text = re.sub(r"[*_`]", "", x.group(1)).strip()
                if text:
                    out.append(text[:400])
        return out[:30]

    def _capability_gaps(self, plan: dict, markdown: str) -> tuple:
        """(core features with no capability, e2e capabilities with no workflow).

        Free-form ideas have no FR ids, so `covers` cannot protect them. Core
        Features are the planner's own explicit promise list; every one must
        survive into the machine plan, and every browser-visible capability
        must be walked by at least one workflow.
        """
        features = self._core_features(markdown)
        caps = [c for c in (plan or {}).get("capabilities") or [] if isinstance(c, dict)]
        stop = {"with","from","that","this","into","their","every","using","allows",
                "ability","engine","management","system","feature","users","user",
                "interface","instant","instantly","administrative"}
        # Product language varies even when the capability is identical.
        aliases = {
            "price":"pricing", "prices":"pricing", "pricing":"pricing",
            "rate":"pricing", "rates":"pricing", "cost":"pricing", "costs":"pricing",
            "admin":"admin", "administrator":"admin", "administrators":"admin",
            "booking":"booking", "bookings":"booking", "reservation":"booking",
            "reservations":"booking", "reserve":"booking", "reserved":"booking",
            "payment":"payment", "payments":"payment", "paid":"payment", "pay":"payment",
            "room":"room", "rooms":"room",
            "availability":"availability", "available":"availability",
            "guest":"guest", "guests":"guest",
            "customer":"customer", "customers":"customer",
        }
        def words(text):
            # Four-letter domain nouns such as room/rate/pay are load-bearing.
            raw = re.findall(r"[a-z0-9]+", (text or "").lower())
            return {w for w in raw if w not in stop and (len(w) >= 5 or w in aliases)}
        def stemmed_words(text):
            raw = words(text)
            out = set()
            for w in raw:
                if w in aliases:
                    out.add(aliases[w]); continue
                z = w
                if z.endswith("ies") and len(z) > 4:
                    z = z[:-3] + "y"
                elif z.endswith("ing") and len(z) > 5:
                    z = z[:-3]
                    if z.endswith(z[-1:] * 2):
                        z = z[:-1]
                elif z.endswith("ed") and len(z) > 4:
                    z = z[:-2]
                elif z.endswith("es") and len(z) > 4:
                    z = z[:-1] if z[-3] in "sgcz" else z[:-2]
                elif z.endswith("s") and len(z) > 4:
                    z = z[:-1]
                out.add(aliases.get(z, z))
            return out

        cap_words = [stemmed_words(str(c.get("requirement") or "") + " " +
                                   str(c.get("proof") or "") + " " +
                                   str(c.get("who") or "")) for c in caps]
        missing_features = []
        for feat in features:
            fw = stemmed_words(feat)
            if not fw:
                continue
            if not any(len(fw & cw) >= 1 for cw in cap_words):
                missing_features.append(feat)

        # Independent source ledger for free-form ideas.
        for req in (plan or {}).get("source_requirements") or []:
            rw = stemmed_words(str(req))
            if not rw:
                continue
            need = 1 if len(rw) == 1 else 2
            if not any(len(rw & cw) >= need for cw in cap_words):
                missing_features.append("SOURCE: " + str(req)[:280])

        covered = set()
        for w in (plan or {}).get("workflows") or []:
            for cid in (w.get("covers") or []) if isinstance(w, dict) else []:
                covered.add(str(cid).strip().upper())
        unwalked = [c.get("id") for c in caps
                    if c.get("e2e", True) and c.get("id") and
                    str(c.get("id")).upper() not in covered]
        planned = {f.get("path") for ph in (plan or {}).get("phases") or []
                   for f in ph.get("files") or [] if isinstance(f, dict)}
        unmapped = []
        for c in caps:
            bad = [x for x in c.get("files") or [] if x not in planned]
            if not c.get("files") or bad:
                unmapped.append(str(c.get("id") or c.get("requirement") or "capability"))

        # A plan can look complete on paper while explicitly scheduling.
        inert_rx = re.compile(
            r"\b(?:placeholder|coming\s+soon|under\s+construction|todo|"
            r"not\s+implemented|future\s+work|disabled\s+(?:for|until|button)|"
            r"stub(?:bed)?\s+(?:button|action|control))\b", re.I)
        for ph in (plan or {}).get("phases") or []:
            if not isinstance(ph, dict):
                continue
            for f in ph.get("files") or []:
                if not isinstance(f, dict):
                    continue
                # Scan the whole file spec, not only `actions`.
                def _spec_text(x):
                    if isinstance(x, dict):
                        return " ".join(_spec_text(v) for v in x.values())
                    if isinstance(x, (list, tuple)):
                        return " ".join(_spec_text(v) for v in x)
                    return str(x or "")
                blob = _spec_text(f)
                if inert_rx.search(blob):
                    unmapped.append("INERT-PLAN:" + str(f.get("path") or "unknown"))
        return missing_features[:12], unwalked[:12], list(dict.fromkeys(unmapped))[:12]

    def make_plan(self, user_prompt: str, requirement_source: str = "") -> bool:
        self._log("INFO", "🧭 Planning — writing plan.md")
        self._fire("on_phase", {"phase": 0, "title": "Planning",
                                "status": "active"})
        self._fire("on_file_start", "plan.md")

        # The requirement ids that actually exist, taken from the brief.
        requirement_source = str(requirement_source or user_prompt or "")
        self._known_fr = set(re.findall(r"\bFR-\d+\b", requirement_source))
        source_reqs = [] if self._known_fr else self._source_requirements(requirement_source)
        source_hint = ""
        if source_reqs:
            source_hint = (
                "\n\nAgentForge extracted this ORIGINAL ACTION CHECKLIST verbatim-ish "
                "from the idea. It is independent of your Core Features list. "
                "Every line must survive into a capability; do not merge away a verb:\n"
                + "\n".join(f"- {x}" for x in source_reqs)
            )

        # Keep provenance visible to the planner too.
        operational_context = ""
        if user_prompt != requirement_source:
            if str(user_prompt).startswith(requirement_source):
                operational_context = str(user_prompt)[len(requirement_source):].strip()
            else:
                operational_context = str(user_prompt).strip()

        planner_user = (
            "AUTHORITATIVE PRODUCT REQUIREMENTS — these and only these define "
            "what the app must do:\n\n" + requirement_source + source_hint
        )
        if operational_context:
            planner_user += (
                "\n\nAGENTFORGE BUILD CONTEXT — implementation constraints/resources only. "
                "Use these while planning, but DO NOT turn them into Core Features, "
                "source requirements, user capabilities, or workflows:\n\n"
                + operational_context
            )
        if self._known_fr:
            ordered_fr = sorted(self._known_fr, key=lambda x: int(x.split('-')[1]))
            planner_user += (
                "\n\nMANDATORY COVERAGE LEDGER — copy every id below into exactly "
                "the task(s) that implement it. Before emitting the plan, count "
                "these ids against task `covers`, then count every e2e capability "
                "against workflow `covers` in the SAME self-check. Do not wait for "
                "AgentForge to ask for a replan:\n" + ", ".join(ordered_fr))
        planner_user += "\n\nWrite the plan now."

        messages = [
            {"role": "system", "content": self._planner_sys()},
            {"role": "user", "content": planner_user},
        ]

        buf = []

        def on_delta(t):
            buf.append(t)
            self._fire("on_file_token", "plan.md", t)

        try:
            self._stream(messages, on_delta, temperature=0.7)
        except Exception as e:
            self._log("ERROR", f"   ❌ Planner failed: {e}")
            return False

        raw = "".join(buf)
        self.plan = self._extract_plan_json(raw)
        if not self.plan.get("phases"):
            self._log("WARN", "   ⚠ No usable JSON plan — using a default phase map")
            self.plan = self._fallback_plan(user_prompt)

        short = self._roles_without_areas(self.plan)
        if short:
            roles, areas = short
            self._log("WARN", f"   ⚠ the plan gives {len(roles)} role(s) only "
                              f"{len(areas)} area(s) — asking for one per role")
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content":
                    f"This plan has {len(roles)} roles — "
                    f"{', '.join(sorted(roles))} — and only "
                    f"{len(areas)} signed-in area"
                    f"{'' if len(areas) == 1 else 's'}"
                    + (f" ({', '.join(sorted(areas))})" if areas else "")
                    + ". Every role needs its own route prefix, and each screen "
                      "the request describes for a role belongs at its own route "
                      "under that prefix — not as a tab inside a shared page. "
                      "Rewrite the plan with a section per role, keeping "
                      "everything else you already decided. Emit the whole plan "
                      "again, including the JSON block."},
            ]
            buf2 = []
            try:
                self._stream(messages, buf2.append, temperature=0.7)
                again = self._extract_plan_json("".join(buf2))

                if again.get("phases") and not self._roles_without_areas(again):
                    self.plan, raw = again, "".join(buf2)
                    self._log("INFO", "   ✅ replanned with a section per role")
                else:
                    self._log("WARN", "   ⚠ the replan did not add them — "
                                      "keeping the first plan")
            except Exception as e:
                self._log("WARN", f"   ⚠ replan failed: {e}")

        # The second half-app: a specification the plan quietly shrank.
        missing = self._uncovered(self.plan)
        if missing:
            self._log("WARN", f"   ⚠ the plan leaves {len(missing)} "
                              f"requirement(s) with no task — "
                              f"{', '.join(missing[:6])}"
                              f"{'…' if len(missing) > 6 else ''} — asking "
                              f"for them to be placed")
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content":
                    f"These requirements from the specification appear in no "
                    f"task's `covers`: {', '.join(missing)}. Each one is a "
                    f"feature the finished app will not have. Put every one "
                    f"of them on the task that builds it — add a task if none "
                    f"fits, or add the files that were missing — and keep "
                    f"everything else you already decided. If one genuinely "
                    f"cannot be built, say so under ## Overview and still list "
                    f"it in `covers` on the task that comes closest. ALSO do the "
                    f"capability/workflow completeness check in this SAME rewrite: "
                    f"every browser-visible capability has exact files and e2e=true, "
                    f"and every e2e capability is covered by a workflow that performs "
                    f"its proof. This is one repair pass, not two. Emit the whole plan "
                    f"again, including the JSON block."},
            ]
            buf3 = []
            try:
                self._stream(messages, buf3.append, temperature=0.7)
                again = self._extract_plan_json("".join(buf3))
                left = self._uncovered(again) if again.get("phases") else missing
                if again.get("phases") and len(left) < len(missing):
                    self.plan, raw = again, "".join(buf3)
                    self._log("INFO", f"   ✅ replanned — "
                                      f"{len(missing) - len(left)} of "
                                      f"{len(missing)} placed"
                                      + (f", {len(left)} still loose: "
                                         f"{', '.join(left[:4])}" if left else ""))
                else:
                    self._log("WARN", "   ⚠ the replan did not place them — "
                                      "keeping the first plan")
            except Exception as e:
                self._log("WARN", f"   ⚠ replan failed: {e}")

        # The third half-app, and the one people actually see.
        stub = self._unbuilt_routes(self.plan, raw)
        if stub:
            self._log("WARN", f"   ⚠ the plan promises {len(stub)} route(s) "
                              f"no file serves — {', '.join(stub[:6])}"
                              f"{'…' if len(stub) > 6 else ''} — asking for "
                              f"them to be written or dropped")
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content":
                    f"These paths appear in your plan — in the Routes table, "
                    f"the Page Flow, or a link — but no task lists a file that "
                    f"serves them: {', '.join(stub)}.\n\n"
                    f"Every one is a 404 in the finished app. For each, do ONE "
                    f"of two things and do it everywhere:\n"
                    f"  • it belongs in the app — add its file to the task that "
                    f"builds that part (`app/<path>/page.jsx`, or "
                    f"`app/api/<name>/route.js` for an API path), or\n"
                    f"  • it does not — remove it from the Routes table, from "
                    f"the Page Flow, and from every link that points at it, so "
                    f"nothing links to a page that will not exist.\n\n"
                    f"A path mentioned once more than it is built is the whole "
                    f"defect, so check the three places agree. Keep everything "
                    f"else you already decided and emit the whole plan again, "
                    f"including the JSON block."},
            ]
            buf4 = []
            try:
                self._stream(messages, buf4.append, temperature=0.6)
                fixed = self._extract_plan_json("".join(buf4))
                if fixed.get("phases"):
                    left = self._unbuilt_routes(fixed, "".join(buf4))
                    if len(left) < len(stub):
                        self.plan, raw = fixed, "".join(buf4)
                        self._log("INFO", f"   ✅ replanned — "
                                          f"{len(stub) - len(left)} of "
                                          f"{len(stub)} route(s) settled"
                                          + (f", {len(left)} still loose"
                                             if left else ""))
                    else:
                        self._log("WARN", "   ⚠ the replan did not settle them "
                                          "— keeping the first plan")
            except Exception as e:
                self._log("WARN", f"   ⚠ route replan failed: {e}")

        # Free-form prompts have no FR ids.
        self.plan["source_requirements"] = source_reqs

        cap_missing, cap_unwalked, cap_unmapped = self._capability_gaps(self.plan, raw)
        if cap_missing or cap_unwalked or cap_unmapped:
            why = []
            if cap_missing:
                why.append("source/Core requirements with no machine capability: " + "; ".join(cap_missing))
            if cap_unwalked:
                why.append("e2e capabilities no workflow covers: " + ", ".join(cap_unwalked))
            if cap_unmapped:
                why.append("capabilities with missing/unplanned files or inert placeholder work: " + ", ".join(cap_unmapped))
            self._log("WARN", "   ⚠ plan completeness gap — " + " | ".join(why)[:500])
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content":
                    "The plan is not complete enough to build. " + "\n".join(why) +
                    "\n\nRewrite the WHOLE plan. Keep the routes/design that are already right, "
                    "but add/fix `capabilities`, their exact `files`, and workflow `covers`. "
                    "Every Core Features bullet and every meaningful verb in the original idea "
                    "must have an observable proof. Anything a person can do gets e2e=true and "
                    "must be covered by a workflow that actually performs it. Do not satisfy a "
                    "feature with decorative inputs or a dead button. Emit markdown + JSON again."},
            ]
            buf5 = []
            try:
                self._stream(messages, buf5.append, temperature=0.55)
                again_raw = "".join(buf5)
                again = self._extract_plan_json(again_raw)
                if again.get("phases"):
                    again["source_requirements"] = source_reqs
                gaps = self._capability_gaps(again, again_raw) if again.get("phases") else (cap_missing, cap_unwalked, cap_unmapped)
                if again.get("phases") and sum(map(len, gaps)) < (len(cap_missing)+len(cap_unwalked)+len(cap_unmapped)):
                    self.plan, raw = again, again_raw
                    self._log("INFO", "   ✅ replanned with a capability proof map")
                else:
                    self._log("WARN", "   ⚠ capability replan did not improve the map")
            except Exception as e:
                self._log("WARN", f"   ⚠ capability replan failed: {e}")

        final_cap_gaps = self._capability_gaps(self.plan, raw)
        if any(final_cap_gaps):
            pieces = []
            if final_cap_gaps[0]: pieces.append("unmapped source/Core requirements: " + "; ".join(final_cap_gaps[0][:5]))
            if final_cap_gaps[1]: pieces.append("unwalked capabilities: " + ", ".join(final_cap_gaps[1][:8]))
            if final_cap_gaps[2]: pieces.append("capabilities without planned files / inert plan work: " + ", ".join(final_cap_gaps[2][:8]))
            self._log("ERROR", "   ❌ Refusing to build an incomplete plan — " + " | ".join(pieces))
            self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "error",
                                    "reason": "capability map incomplete"})
            return False

        self.plan_md = re.sub(r"```json.*?```", "", raw, flags=re.S).strip()
        self._fire("on_file_end", "plan.md", self.plan_md)
        self.write_file("plan.md", self.plan_md)

        # The plan's companion: what to build, and how it should look.
        self.design_md = self._design_md()
        self.write_own("design.md", self.design_md)
        self._save_plan_json()

        n = len(self.plan["phases"])
        self._log("INFO", f"   ✅ Plan ready — {n} tasks, "
                          f"{sum(len(p.get('files', [])) for p in self.plan['phases'])} files")

        self.start_conversation(user_prompt)

        self.save_convo()

        self._fire("on_phase", {"phase": 0, "title": "Planning",
                                "status": "done", "plan": self.plan})
        return True
