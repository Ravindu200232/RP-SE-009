"""One build, as a sequence of passes.

The planner and the design customiser are ported from AgentX, with their
approval prompts removed: nobody is sitting on a dialog during a studio build.
What has to hold instead is that both still happen, that what they produce is
written into the project, and that the build pass actually receives it.
"""
from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from builder_agent.agent import BuilderAgent, wants_design
from builder_agent.config import BUILD_QUALITY, Config
from builder_agent.events import Events
from builder_agent.approvals import Approvals
from builder_agent.llm import Reply, ToolCall
from builder_agent.prompts import system_prompt, task_message

PLAN = ("Goal: a hotel booking site.\n"
        "Findings: the workspace is empty.\n"
        "Phase 1 - models. Done when Room and Booking exist.\n"
        "Phase 2 - pages. Done when /rooms lists rooms.\n"
        "Acceptance: the unit suite and one browser journey pass.\n"
        "Limitations: no payment provider is configured here.")


class ScriptedRouter:
    def __init__(self, turns):
        self.turns = list(turns)
        self.asked = []
        self.offered = []
        self.usage = {"prompt": 0, "completion": 0, "requests": 0}
        self.label = "scripted/model"
        self.model = "scripted"

    def ask(self, messages, tools=None, **kwargs):
        self.asked.append(messages)
        self.offered.append({tool["function"]["name"] for tool in (tools or [])})
        if not self.turns:
            raise AssertionError("the scripted model ran out of turns")
        return self.turns.pop(0)

    @staticmethod
    def context_window():
        return 0


class AgentPassTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.events = Events()
        self.agent = BuilderAgent(
            Config(workspace=self.root, model="scripted", unit_tests=False,
                   e2e_tests=False, state_root=self.root / ".state"),
            events=self.events, client=object())

    def script(self, turns):
        self.agent.router = ScriptedRouter(turns)
        return self.agent.router

    def test_planning_investigates_and_ends_on_a_submitted_plan(self):
        self.script([
            Reply(calls=[ToolCall("a", "listDir", {"dirPath": "."})]),
            Reply(calls=[ToolCall("b", "submitPlan", {"plan": PLAN, "goal": "hotel site"})]),
        ])

        outcome = self.agent.plan("build a hotel booking site")

        self.assertEqual(outcome.status, "completed")
        self.assertEqual(self.agent.plan_text, PLAN)

    def test_the_planning_pass_investigates_but_does_not_implement(self):
        router = self.script([Reply(calls=[ToolCall("a", "writeFile",
                                                    {"filePath": "app.js", "content": "x"})]),
                              Reply(calls=[ToolCall("b", "submitPlan", {"plan": PLAN})])])

        self.agent.plan("build a hotel booking site")

        # A plan is written by reading, not by building. The file tools that
        # change the project are not on the table, so a call to one is answered
        # with a correction instead of quietly writing the file.
        self.assertNotIn("writeFile", router.offered[0])
        self.assertNotIn("patchFile", router.offered[0])
        self.assertIn("readFile", router.offered[0])
        self.assertIn("submitPlan", router.offered[0])
        # Design is decided from the product, not copied off other websites.
        self.assertNotIn("webResearch", router.offered[0])
        self.assertFalse((self.root / "app.js").exists())

    def test_planning_prompt_keeps_execution_skills_out_of_the_pass(self):
        task = task_message("build a long project-management site", stack="nextjs-mongo",
                            quality=BUILD_QUALITY, plan_only=True)
        system = system_prompt(workspace=self.root, model="scripted",
                               stack="nextjs-mongo", quality=BUILD_QUALITY,
                               context_tokens=64_000, plan_only=True)

        self.assertIn("inspectProject once", task)
        self.assertIn("do not inventory boilerplate", task)
        self.assertIn("Do not call listSkills", system)
        self.assertIn("Do not inventory the scaffold", system)
        self.assertNotIn("TEST-DRIVEN COMPLETION", system)
        self.assertNotIn("PHASE DISCIPLINE", system)

        # One skill is read during planning, because it is about how to read a
        # request rather than about how to build anything. Every other skill
        # still belongs to execution.
        self.assertIn("readSkill('planning')", task)
        self.assertIn("Read no skill but `planning`", task)
        self.assertIn("Read the `planning` skill first", system)

    def test_the_plan_is_told_to_enumerate_what_was_asked_for(self):
        """A request read once produces a plan about most of it."""
        task = task_message("a darkroom with three roles", stack="nextjs-mongo",
                            quality=BUILD_QUALITY, plan_only=True)
        self.assertIn("requirements enumerated from the request itself", task)
        self.assertIn("numbered requirement", task)
        self.assertIn("exactly one phase", task)

    def test_the_design_contract_is_decided_and_written_without_asking(self):
        written = self.agent.apply_design("build a hotel booking site with rooms and payments")

        self.assertIsNotNone(written)
        skill = self.root / ".agents/skills/design-system/SKILL.md"
        self.assertTrue(skill.is_file())
        self.assertIn("Sunset Ember", skill.read_text(encoding="utf-8"))

    def test_work_with_no_interface_gets_no_design_contract(self):
        self.assertFalse(wants_design("write a cron job that prunes old sessions"))
        self.assertFalse(wants_design("add a seed script"))
        self.assertTrue(wants_design("build a booking site with a rooms page"))
        self.assertIsNone(self.agent.apply_design("write a migration script"))

    def test_the_build_pass_receives_the_plan_and_the_design(self):
        self.agent.design = self.agent.apply_design("build a hotel booking site")
        # The completion gate will send "Built it." back for lacking evidence;
        # what this test is about is the instruction the build pass starts from.
        router = self.script([Reply(content="Built it.") for _ in range(8)])

        self.agent.build("build a hotel booking site", plan=PLAN)

        first = "\n".join(message.get("content") or "" for message in router.asked[0])
        self.assertIn("Phase 1 - models", first)
        self.assertIn("EXECUTION CONTRACT", first)
        self.assertIn("DESIGN CONTRACT", first)
        self.assertIn("design-system/SKILL.md", first)

    def test_a_review_pass_is_offered_nothing_that_can_change_anything(self):
        router = self.script([Reply(content="Two issues, both in the booking route.")])

        outcome = self.agent.review("Review the change set.")

        self.assertEqual(outcome.status, "completed")
        offered = router.offered[0]
        for name in ("writeFile", "patchFile", "deleteFile", "executeTerminal",
                     "runTests", "browserRunJourney"):
            self.assertNotIn(name, offered)
        self.assertIn("readFile", offered)
        self.assertIn("reviewChanges", offered)

    def test_a_plan_can_be_accepted(self):
        self.agent.approvals = Approvals(self.events, enabled=True, timeout=5)
        asked = []
        self.events.on("approval", lambda p: (
            asked.append(p),
            self.agent.approvals.resolve(p["id"], {"decision": "accept"})))
        self.script([Reply(calls=[ToolCall("a", "submitPlan", {"plan": PLAN})])])

        self.agent.plan("build a hotel booking site")

        self.assertEqual(len(asked), 1)
        self.assertEqual(asked[0]["kind"], "plan")
        self.assertIn("Phase 1 - models", asked[0]["plan"])
        self.assertEqual(self.agent.plan_text, PLAN)

    def test_a_plan_sent_back_is_written_again_with_the_feedback(self):
        self.agent.approvals = Approvals(self.events, enabled=True, timeout=5)
        rounds = []

        def answer(payload):
            rounds.append(payload)
            decision = "revise" if len(rounds) == 1 else "accept"
            self.agent.approvals.resolve(payload["id"],
                                         {"decision": decision, "feedback": "use two roles"})
        self.events.on("approval", answer)
        router = self.script([
            Reply(calls=[ToolCall("a", "submitPlan", {"plan": PLAN})]),
            Reply(calls=[ToolCall("b", "submitPlan",
                                  {"plan": PLAN + "\nPhase 3 - roles."})]),
        ])

        self.agent.plan("build a hotel booking site")

        self.assertEqual(len(rounds), 2)
        # The second planning pass is told what was wrong with the first.
        second = "\n".join(m.get("content") or "" for m in router.asked[1])
        self.assertIn("use two roles", second)
        self.assertIn("Phase 3 - roles.", self.agent.plan_text)

    def test_nobody_answering_lets_the_build_start_anyway(self):
        self.agent.approvals = Approvals(self.events, enabled=True, timeout=1)
        self.script([Reply(calls=[ToolCall("a", "submitPlan", {"plan": PLAN})])])

        outcome = self.agent.plan("build a hotel booking site")

        self.assertEqual(outcome.status, "completed")
        self.assertEqual(self.agent.plan_text, PLAN)

    def test_the_design_answer_is_applied_and_junk_in_it_is_not(self):
        self.agent.approvals = Approvals(self.events, enabled=True, timeout=5)
        self.events.on("approval", lambda p: self.agent.approvals.resolve(p["id"], {
            "decision": "apply",
            "selection": {"palette": "mono-contrast", "radius": "square",
                          "font": "not-a-font"}}))

        written = self.agent.apply_design("build a hotel booking site")

        self.assertEqual(written["selection"]["palette"], "mono-contrast")
        self.assertEqual(written["selection"]["radius"], "square")
        # An unknown id keeps what was chosen rather than failing the build.
        self.assertEqual(written["selection"]["font"],
                         self.agent.design["selection"]["font"])
        self.assertIn("Mono Contrast",
                      (self.root / ".agents/skills/design-system/SKILL.md").read_text(encoding="utf-8"))

    def test_the_design_can_be_left_to_the_build(self):
        self.agent.approvals = Approvals(self.events, enabled=True, timeout=5)
        self.events.on("approval",
                       lambda p: self.agent.approvals.resolve(p["id"], {"decision": "skip"}))

        self.assertIsNone(self.agent.apply_design("build a hotel booking site"))
        self.assertFalse((self.root / ".agents/skills/design-system").exists())

    def test_a_snapshot_describes_the_run_without_needing_a_model(self):
        snapshot = self.agent.snapshot()

        self.assertEqual(snapshot["stack"], "nextjs-mongo")
        self.assertEqual(snapshot["quality"], "default")
        self.assertIn("evidence", snapshot)


class PendingQuestionTests(unittest.TestCase):
    """A question announced once must still be findable by a late arrival."""

    def gate(self, timeout=300.0):
        from builder_agent.approvals import Approvals
        from builder_agent.events import Events
        return Approvals(Events(), enabled=True, timeout=timeout)

    def test_a_waiting_question_can_be_read_back_in_full(self):
        """The studio reloads, and the run is still waiting on it."""
        approvals = self.gate()
        asked = threading.Thread(
            target=approvals.ask,
            args=("design", {"palettes": [{"id": "slate"}], "chosen": {"palette": "slate"}},
                  {"decision": "apply"}),
            daemon=True)
        asked.start()
        for _ in range(200):                       # let the gate publish
            if approvals.list():
                break
            time.sleep(0.01)

        waiting = approvals.list()
        self.assertEqual(len(waiting), 1)
        question = waiting[0]
        self.assertEqual(question["kind"], "design")
        self.assertEqual(question["palettes"], [{"id": "slate"}])
        self.assertEqual(question["chosen"], {"palette": "slate"})
        self.assertGreater(question["timeout"], 0)

        self.assertTrue(approvals.resolve(question["id"], {"decision": "apply"}))
        asked.join(timeout=5)
        self.assertEqual(approvals.list(), [])

    def test_the_time_left_shrinks_rather_than_restarting(self):
        """A recovered question shows what is left, not the whole budget."""
        from builder_agent.approvals import Decision
        decision = Decision("plan", {"plan": "do it"}, {"decision": "accept"}, timeout=300)
        decision.asked_at -= 120
        self.assertLessEqual(decision.as_question()["timeout"], 181)
        self.assertGreater(decision.as_question()["timeout"], 170)

    def test_a_question_nobody_can_answer_is_not_published(self):
        from builder_agent.approvals import Approvals
        from builder_agent.events import Events
        approvals = Approvals(Events(), enabled=False)
        answer = approvals.ask("plan", {"plan": "x"}, {"decision": "accept"})
        self.assertEqual(answer["decision"], "accept")
        self.assertFalse(answer["asked"])
        self.assertEqual(approvals.list(), [])



class RetargetTests(unittest.TestCase):
    """Switching model mid-conversation must not cost the conversation."""

    def agent(self, tmp, model="deepseek", think=False):
        from builder_agent.agent import BuilderAgent
        from builder_agent.config import Config
        return BuilderAgent(Config(workspace=tmp, model=model, think=think),
                            events=Events())

    def test_the_transcript_survives_a_change_of_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.agent(tmp)
            agent.memory.add_user("make the heading bigger")
            before = len(agent.memory)

            self.assertTrue(agent.retarget("qwen2.5-coder:14b"))

            self.assertEqual(agent.config.model, "qwen2.5-coder:14b")
            self.assertEqual(agent.router.model, "qwen2.5-coder:14b")
            self.assertEqual(len(agent.memory), before)

    def test_thinking_can_be_turned_on_without_starting_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.agent(tmp)
            agent.memory.add_user("and the price too")
            before = len(agent.memory)

            self.assertTrue(agent.retarget(think=True))

            self.assertTrue(agent.config.think)
            self.assertEqual(len(agent.memory), before)

    def test_retargeting_to_what_is_already_set_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.agent(tmp, model="deepseek", think=False)
            self.assertFalse(agent.retarget("deepseek", False))
            self.assertFalse(agent.retarget())

    def test_the_window_is_remeasured_so_a_smaller_model_is_not_overfilled(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.agent(tmp)
            agent.router.context_window = lambda: 8192

            agent.retarget("a-small-one")

            self.assertEqual(agent.config.context_tokens, 8192)
            self.assertEqual(agent.memory.budget_tokens, 8192)



if __name__ == "__main__":
    unittest.main()


class PrototypePassTests(unittest.TestCase):
    """The application is drawn in HTML before any of it is built.

    The cheapest place in the pipeline to be wrong: a layout that is wrong here
    costs a re-render, and the same layout wrong after the build costs the
    build, its tests and its browser journeys.
    """

    PAGE = "<!doctype html><html><head><link rel=stylesheet href=styles.css></head><body>x</body></html>"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.events = Events()
        self.agent = BuilderAgent(
            Config(workspace=self.root, model="scripted", unit_tests=False,
                   e2e_tests=False, state_root=self.root / ".state"),
            events=self.events, client=object())
        self.agent.design = {"selection": {
            "palette": "sunset-ember", "paletteName": "Sunset Ember",
            "mood": "Warm, energetic, consumer.", "themeMode": "light",
            "font": "grotesk-sharp", "typeScale": "comfortable", "radius": "soft",
            "density": "comfortable", "border": "hairline", "elevation": "subtle",
            "motion": "subtle", "tone": "friendly", "contrast": "aa",
            "container": "1280", "pages": []}}
        self.agent.screens = [
            {"id": "/", "route": "/", "label": "Home", "what": "today's soups"},
            {"id": "/menu", "route": "/menu", "label": "Menu", "what": "the whole menu"},
            {"id": "/admin/orders", "route": "/admin/orders", "label": "Admin orders",
             "what": "every order"},
        ]

    def draws(self, *names):
        return Reply(calls=[
            ToolCall(str(i), "writeFile",
                     {"filePath": f".agentforge/prototype/{name}", "content": self.PAGE})
            for i, name in enumerate(names)])

    def test_it_draws_a_file_for_every_agreed_screen(self):
        router = ScriptedRouter([self.draws("index.html", "menu.html", "admin-orders.html"),
                                 Reply(content="Drawn.")])
        self.agent.router = router

        out = self.agent.prototype("a small soup cafe")

        self.assertEqual([page["file"] for page in out["pages"]],
                         ["index.html", "menu.html", "admin-orders.html"])
        self.assertEqual([page["label"] for page in out["pages"]],
                         ["Home", "Menu", "Admin orders"])

    def test_a_drawing_pass_cannot_install_serve_or_test(self):
        """It writes HTML. A pass that can run npm will find a reason to."""
        router = ScriptedRouter([self.draws("index.html"), Reply(content="Drawn.")])
        self.agent.router = router

        self.agent.prototype("a small soup cafe")

        offered = router.offered[0]
        for name in ("executeTerminal", "runTests", "browserOpen", "backgroundProcess",
                     "defineVerificationScope"):
            self.assertNotIn(name, offered)
        for name in ("writeFile", "readFile", "readSkill"):
            self.assertIn(name, offered)

    def test_the_instruction_carries_the_plan_and_the_design_contract(self):
        task = self.agent._prototype_task(
            "an online bookshop",
            plan="## Requirements\n1. A reader browses books at /books.\n"
                 "2. A seller edits only their own listings.")

        # Everything already agreed is binding on the drawing.
        self.assertIn("1. A reader browses books", task)
        self.assertIn("Sunset Ember", task)
        self.assertIn("Every requirement it enumerates", task)
        # And it is a full page, not a sketch of one.
        self.assertIn("FULL SIZE", task.upper())
        self.assertIn("No stubs", task)
        # And something they can click through, not a picture of one.
        self.assertIn("demo.js", task)
        self.assertIn("localStorage", task)
        self.assertIn("no fetch", task)
        # Told to make it work, it moved the content into the script: empty
        # divs, four hollow sections, and nothing linking anywhere.
        self.assertIn("SCRIPT NEVER SUPPLIES THE CONTENT", task)
        self.assertIn("real anchor", task)

    def test_what_they_ask_for_is_sent_back_to_be_redrawn(self):
        asked = []

        class Answering(ScriptedRouter):
            def ask(inner, messages, tools=None, **kwargs):
                asked.append("\n".join(m.get("content") or "" for m in messages))
                return super().ask(messages, tools, **kwargs)

        self.agent.router = Answering([
            self.draws("index.html"), Reply(content="Drawn."),
            self.draws("index.html"), Reply(content="Redrawn."),
        ])
        self.agent.approvals.enabled = True

        answers = iter([{"decision": "revise", "feedback": "make the buttons blue"},
                        {"decision": "approve"}])

        def answer(kind, payload, default, timeout=None, cancel=None):
            return {**next(answers, {"decision": "approve"}), "asked": True}

        self.agent.approvals.ask = answer
        self.agent.prototype("a small soup cafe")

        self.assertTrue(any("make the buttons blue" in text for text in asked))

    def test_the_build_is_told_to_match_what_was_approved(self):
        drawn = self.root / ".agentforge" / "prototype"
        drawn.mkdir(parents=True)
        for name in ("index.html", "menu.html"):
            (drawn / name).write_text(self.PAGE, encoding="utf-8")
        self.agent.prototype_dir = drawn

        told = self.agent._with_prototype("BUILD IT")

        self.assertIn("APPROVED PROTOTYPE", told)
        self.assertIn("index.html", told)
        self.assertIn("menu.html", told)
        self.assertIn("the prototype wins", told)
        self.assertIn("BUILD IT", told)

    def test_a_build_that_drew_nothing_says_nothing_about_a_prototype(self):
        self.assertEqual(self.agent._with_prototype("BUILD IT"), "BUILD IT")
        self.agent.prototype_dir = self.root / ".agentforge" / "prototype"
        self.assertEqual(self.agent._with_prototype("BUILD IT"), "BUILD IT")

    def test_nothing_is_drawn_without_screens_to_draw(self):
        self.agent.screens = []
        self.assertIsNone(self.agent.prototype("a cron job"))


class LongPageInstructionTests(unittest.TestCase):
    """The page being long is said everywhere a page gets written.

    It used to be said once, in the middle of the drawing prompt, and a thin
    page came back anyway - so it now leads that prompt, rides in the system
    prompt of every generating pass, and comes back on each page written.
    """

    HEADING = "EVERY PAGE IS A LONG, BIG PAGE"

    def _system(self, **extra):
        kwargs = dict(workspace=Path("."), model="m", stack="next",
                      quality=BUILD_QUALITY, context_tokens=128000)
        kwargs.update(extra)
        return system_prompt(**kwargs)

    def test_every_generating_pass_carries_it(self):
        self.assertIn(self.HEADING, self._system())
        self.assertIn(self.HEADING, self._system(testing_enabled=False))
        self.assertIn(self.HEADING, self._system(verification_kinds=["unit"]))

    def test_a_small_window_does_not_drop_it(self):
        # _fit gives up the OPTIONAL blocks first; this one is never optional,
        # because the pass that most needs it is the one with least room.
        self.assertIn(self.HEADING, self._system(context_tokens=6000))

    def test_a_read_only_pass_does_not_carry_it(self):
        self.assertNotIn(self.HEADING, self._system(review=True))

    def test_planning_is_told_to_plan_the_sections(self):
        self.assertIn("long, big page", self._system(plan_only=True))

    def test_it_leads_the_drawing_prompt(self):
        root = Path(tempfile.mkdtemp())
        agent = BuilderAgent(
            Config(workspace=root, model="scripted", unit_tests=False,
                   e2e_tests=False, state_root=root / ".state"),
            events=Events(), client=object())
        agent.screens = [{"route": "/", "label": "Home", "what": "the front page"}]
        prompt = agent._prototype_task("a hotel booking site")
        # It leads everything except the one line asking for the whole app,
        # which now comes first in both passes.
        head = prompt.lstrip().split("\n\n", 1)
        self.assertTrue(head[0].startswith("THE WHOLE APPLICATION"), head[0][:60])
        self.assertTrue(head[1].lstrip().startswith(self.HEADING),
                        "the long-page directive has to come next, not fifth")

    def test_writing_a_page_says_it_again(self):
        from builder_agent.tools.files import _page_note
        for page in (".agentforge/prototype/rooms.html", "app/rooms/page.tsx",
                     "pages/checkout.jsx", "src/pages/basket.tsx"):
            self.assertTrue(_page_note(page, "x"), f"{page} should carry the reminder")

    def test_writing_something_that_is_not_a_page_stays_quiet(self):
        from builder_agent.tools.files import _page_note
        for other in ("app/components/Button.tsx", "app/api/rooms/route.ts",
                      "styles.css", "demo.js", "package.json", "app/layout.tsx"):
            self.assertFalse(_page_note(other, "x"), f"{other} should not carry it")

    def test_a_drawn_page_is_told_its_own_size(self):
        from builder_agent.tools.files import _page_note
        note = _page_note("rooms.html", "<html>" + "x" * 400)
        self.assertIn("9,000", note)
        self.assertIn("406 bytes", note)
        # A built page maps over data, so a byte count there would be wrong.
        self.assertNotIn("9,000", _page_note("app/rooms/page.tsx", "x" * 400))


class TheBuildKeepsTheDrawnPicturesTests(unittest.TestCase):
    """A drawn picture is part of what the user approved.

    The drawing seeded a bakery's loaf from `sourdough-country`; the build
    re-derived it from `product.slug` and got `country-sourdough`, which is a
    different photograph. The basket went further and seeded from the database
    id, so every re-seed changed the pictures. All three look reasonable in
    isolation and none of them shows what was agreed.
    """

    def _instruction(self):
        root = Path(tempfile.mkdtemp())
        proto = root / ".agentforge" / "prototype"
        proto.mkdir(parents=True)
        (proto / "index.html").write_text(
            '<img src="https://picsum.photos/seed/sourdough-country/600/400">',
            encoding="utf-8")
        agent = BuilderAgent(
            Config(workspace=root, model="scripted", unit_tests=False,
                   e2e_tests=False, state_root=root / ".state"),
            events=Events(), client=object())
        agent.prototype_dir = proto
        return agent._with_prototype("BUILD IT")

    def test_the_build_is_told_to_carry_the_addresses_over(self):
        text = self._instruction()
        self.assertIn("THE PICTURES ARE PART OF WHAT WAS APPROVED", text)
        self.assertIn("the same seed", text)

    def test_it_names_both_ways_the_address_gets_lost(self):
        text = self._instruction()
        # Re-derived from a neighbouring field, and derived from a row id.
        self.assertIn("product.slug", text)
        self.assertIn("re-seeded", text)

    def test_it_says_where_a_data_driven_picture_should_live(self):
        self.assertIn("put that drawn address on the record", self._instruction())


class UnconfiguredCapabilitiesTests(unittest.TestCase):
    """What was skipped at setup is not built as though it had been supplied.

    Stripe was skipped on a bakery build, and the checkout shipped a card
    number, an expiry and a CVC in plain inputs under the line "Payments are
    processed securely. Your card details are never stored by us." Nothing was
    sent anywhere and nothing was charged - the fields were validated for
    presence and dropped. A form that takes a real card and does nothing is a
    worse thing to ship than an unfinished page.
    """

    def _agent(self, notes):
        root = Path(tempfile.mkdtemp())
        agent = BuilderAgent(
            Config(workspace=root, model="scripted", unit_tests=False,
                   e2e_tests=False, state_root=root / ".state"),
            events=Events(), client=object())
        agent.setup_notes = notes
        return agent

    def test_the_rule_travels_with_the_settled_notes(self):
        text = self._agent(["Payments: names written to .env.local"])._with_settings("build it")
        self.assertIn("ALREADY SETTLED WITH THE USER", text)
        self.assertIn("does not collect a card", text)

    def test_a_build_that_settled_nothing_is_not_lectured(self):
        self.assertEqual(self._agent([])._with_settings("build it"), "build it")


class PicturesAreOfTheSubjectTests(unittest.TestCase):
    """A photograph of the product, not a photograph.

    A seeded address on a random-photo service is stable, pretty and unrelated:
    the bakery's Country Sourdough card came back a pine forest, and a supercar
    page a black-and-white photograph of somebody's arm. The page looks finished
    in a thumbnail and absurd the moment anyone reads it.
    """

    def _drawing_prompt(self):
        root = Path(tempfile.mkdtemp())
        agent = BuilderAgent(
            Config(workspace=root, model="scripted", unit_tests=False,
                   e2e_tests=False, state_root=root / ".state"),
            events=Events(), client=object())
        agent.screens = [{"route": "/", "label": "Home", "what": "front"}]
        return agent._prototype_task("a bakery")

    def test_the_address_carries_the_subject(self):
        text = self._drawing_prompt()
        self.assertIn("loremflickr.com", text)
        self.assertIn("sourdough,bread", text)
        self.assertNotIn("picsum", text)

    def test_it_asks_for_the_lock_that_keeps_it_stable(self):
        # Without it the same address is a different photograph every request.
        self.assertIn("?lock=", self._drawing_prompt())

    def test_the_skill_agrees_with_the_prompt(self):
        skill = (Path("builder-agent/builder_agent/assets/skills/html-prototype/SKILL.md")
                 .read_text(encoding="utf-8"))
        self.assertIn("loremflickr.com", skill)
        self.assertIn("?lock=", skill)
        self.assertNotIn("picsum", skill)


class MotionIsAskedForEverywhereTests(unittest.TestCase):
    """The drawing is asked for motion in a line, not a manual.

    The long version - mechanics, bullet lists, a section in two skills - was
    replaced by the ask itself. What stays is the part that is a requirement
    rather than taste: the page has to survive the animation being off and the
    script being deleted, because a Ferrari drawing whose content waited on an
    IntersectionObserver that never loaded came up as an empty black page.
    """

    def _drawing_prompt(self):
        root = Path(tempfile.mkdtemp())
        agent = BuilderAgent(
            Config(workspace=root, model="scripted", unit_tests=False,
                   e2e_tests=False, state_root=root / ".state"),
            events=Events(), client=object())
        agent.screens = [{"route": "/", "label": "Home", "what": "front"}]
        return agent._prototype_task("a bakery")

    def test_the_ask_is_there(self):
        self.assertIn("USING BEAUTIFUL ANIMATIONS AND MATCHED CONTENT",
                      self._drawing_prompt())

    def test_it_still_has_to_survive_the_animation_being_off(self):
        text = self._drawing_prompt()
        self.assertIn("prefers-reduced-motion", text)
        self.assertIn("script", text)

    def test_the_skills_no_longer_carry_a_motion_manual(self):
        skills = Path("builder-agent/builder_agent/assets/skills")
        for name in ("html-prototype", "frontend-design"):
            with self.subTest(name):
                text = (skills / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertNotIn("IntersectionObserver", text)
                self.assertNotIn("requestAnimationFrame", text)


class TheDrawingsScriptHasToParseTests(unittest.TestCase):
    """A drawing whose script is broken looks finished and does nothing.

    Every drawing of the twenty-screen Ferrari platform shipped a demo.js with a
    syntax error - the model patches that file repeatedly and leaves a
    duplicated tail after a closing brace. The pages render, the flow is dead,
    and nobody finds out until they click. The smaller products, with a smaller
    script, were all fine.
    """

    def _write(self, body):
        root = Path(tempfile.mkdtemp())
        path = root / "demo.js"
        path.write_text(body, encoding="utf-8")
        return path

    def test_a_broken_script_is_reported_with_its_error(self):
        from builder_agent.agent import _script_error
        # The shape that actually shipped: a block closed, then repeated.
        broken = self._write("items.forEach(function (i) {\n  i.hidden = true;\n});\n});\n")
        self.assertIn("SyntaxError", _script_error(broken))

    def test_a_good_script_is_silent(self):
        from builder_agent.agent import _script_error
        self.assertEqual(_script_error(self._write("const KEY='x';\nlocalStorage.getItem(KEY);\n")), "")

    def test_no_script_is_not_an_error(self):
        from builder_agent.agent import _script_error
        self.assertEqual(_script_error(Path(tempfile.mkdtemp()) / "absent.js"), "")


class TheWholeApplicationTests(unittest.TestCase):
    """Both passes are asked for all of it, in one line, before anything else."""

    def _agent(self):
        root = Path(tempfile.mkdtemp())
        proto = root / ".agentforge" / "prototype"
        proto.mkdir(parents=True)
        (proto / "index.html").write_text("<title>Home</title>", encoding="utf-8")
        agent = BuilderAgent(
            Config(workspace=root, model="scripted", unit_tests=False,
                   e2e_tests=False, state_root=root / ".state"),
            events=Events(), client=object())
        agent.prototype_dir = proto
        agent.screens = [{"route": "/", "label": "Home", "what": "front"}]
        return agent

    def test_the_drawing_is_asked_first(self):
        first = self._agent()._prototype_task("a shop").lstrip().splitlines()[0]
        self.assertTrue(first.startswith("THE WHOLE APPLICATION, NOT HALF OF IT"), first)

    def test_the_build_is_asked_first(self):
        first = self._agent()._with_prototype("BUILD IT").lstrip().splitlines()[0]
        self.assertTrue(first.startswith("THE WHOLE APPLICATION, NOT HALF OF IT"), first)
