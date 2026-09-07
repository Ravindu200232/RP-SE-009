"""One build, as a sequence of passes.

The planner and the design customiser are ported from AgentX, with their
approval prompts removed: nobody is sitting on a dialog during a studio build.
What has to hold instead is that both still happen, that what they produce is
written into the project, and that the build pass actually receives it.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from builder_agent.agent import BuilderAgent, wants_design
from builder_agent.config import Config
from builder_agent.events import Events
from builder_agent.llm import Reply, ToolCall

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
        self.assertFalse((self.root / "app.js").exists())

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

    def test_a_snapshot_describes_the_run_without_needing_a_model(self):
        snapshot = self.agent.snapshot()

        self.assertEqual(snapshot["stack"], "nextjs-mongo")
        self.assertEqual(snapshot["quality"], "default")
        self.assertIn("evidence", snapshot)


if __name__ == "__main__":
    unittest.main()
